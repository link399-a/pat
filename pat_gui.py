import os
import re
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import webbrowser 

def list_usb_devices():
    """Return a list of all /dev/ttyUSB* devices."""
    return [dev for dev in os.listdir('/dev') if dev.startswith('ttyUSB')]

def run_ardopcf_probe():
    """Run ./ardopcf once to list sound cards."""
    try:
        result = subprocess.run(
            ['./ardopcf'],
            capture_output=True, text=True, check=True
        )
        pattern = re.compile(r'Card\s+(\d+).*?hw:(\d+,\d+)', re.DOTALL)
        return set(pattern.findall(result.stdout))
    except subprocess.CalledProcessError as e:
        return set()

def build_service_commands(usb_dev, audio_pair):
    """Return the three service commands as lists."""
    card, hw = audio_pair
    rig_cmd = [
        'rigctld', '-m', '2050',
        '-r', f'/dev/{usb_dev}',
        '-s', '9600', '-P', 'RTS', '-D', 'RIG'
    ]
    ardop_cmd = [
        './ardopcf', '--logdir', os.path.expanduser('~/ardop_logs'),
        '-p', f'/dev/{usb_dev}', '8515',
        f'plughw:{hw}', f'plughw:{hw}'
    ]
    pat_cmd = ['pat', '--listen=ardop,telnet', 'http']
    return rig_cmd, ardop_cmd, pat_cmd

class RadioGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pat Radio GUI")
        self.processes = []
        
        # USB selector
        tk.Label(self, text="USB Device:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.usb_var = tk.StringVar()
        self.usb_menu = ttk.OptionMenu(self, self.usb_var, "")
        self.usb_menu.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        ttk.Button(self, text="Refresh USB", command=self.refresh_usb).grid(row=0, column=2, padx=5)

        # Audio selector
        tk.Label(self, text="Audio Device:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.audio_var = tk.StringVar()
        self.audio_menu = ttk.OptionMenu(self, self.audio_var, "")
        self.audio_menu.grid(row=1, column=1, padx=5, pady=5, sticky="we")
        ttk.Button(self, text="Refresh Audio", command=self.refresh_audio).grid(row=1, column=2, padx=5)

        # Action buttons
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=10)
        ttk.Button(btn_frame, text="Show Commands", command=self.show_commands).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Start Services", command=self.start_services).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Stop Services",  command=self.stop_services).grid(row=0, column=2, padx=5)
        ttk.Button(btn_frame, text="Open Web UI", command=self.open_web_ui).grid(row=0, column=3, padx=5)

        # Output console
        self.console = scrolledtext.ScrolledText(self, wrap="word", height=15)
        self.console.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")

        # Make columns expand
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Initial populate
        self.refresh_usb()
        self.refresh_audio()

    def refresh_usb(self):
        devices = list_usb_devices()
        menu = self.usb_menu["menu"]
        menu.delete(0, "end")
        for dev in devices:
            menu.add_command(label=dev, command=lambda d=dev: self.usb_var.set(d))
        if devices:
            self.usb_var.set(devices[0])
        else:
            self.usb_var.set("")

    def refresh_audio(self):
        pairs = run_ardopcf_probe()
        items = [f"Card {c} hw:{hw}" for c, hw in pairs]
        menu = self.audio_menu["menu"]
        menu.delete(0, "end")
        for item in items:
            menu.add_command(label=item, command=lambda i=item: self.audio_var.set(i))
        if items:
            self.audio_var.set(items[0])
        else:
            self.audio_var.set("")

    def parse_audio(self):
        text = self.audio_var.get()
        m = re.match(r"Card\s+(\d+)\s+hw:(\d+,\d+)", text)
        return (m.group(1), m.group(2)) if m else None

    def show_commands(self):
        usb = self.usb_var.get()
        audio = self.parse_audio()
        if not usb or not audio:
            messagebox.showwarning("Missing selection", "Select both USB and audio first.")
            return
        rig, ardop, pat = build_service_commands(usb, audio)
        self.console.insert("end", "# rigctld:\n" + " ".join(rig) + "\n\n")
        self.console.insert("end", "# ardopcf:\n" + " ".join(ardop) + "\n\n")
        self.console.insert("end", "# pat:\n" + " ".join(pat) + "\n\n")
        self.console.see("end")

    def start_services(self):
        usb = self.usb_var.get()
        audio = self.parse_audio()
        if not usb or not audio:
            messagebox.showwarning("Missing selection", "Select both USB and audio first.")
            return
        
        rig_cmd, ardop_cmd, pat_cmd = build_service_commands(usb, audio)
        self.console.insert("end", "Starting services...\n")
        
        # Launch and capture output
        for name, cmd in [("rigctld", rig_cmd),
                          ("ardopcf", ardop_cmd),
                          ("pat",    pat_cmd)]:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.processes.append(p)
            threading.Thread(target=self._stream_output, args=(p, name), daemon=True).start()

        self.console.insert("end", "Services started.\n\n")
        self.console.see("end")

    def stop_services(self):
        self.console.insert("end", "Stopping services...\n")
        for p in self.processes:
            try:
                p.terminate()
            except Exception:
                pass
        subprocess.run(['killall', 'rigctld'])
        subprocess.run(['killall', 'ardopcf'])
        subprocess.run(['killall', 'pat'])
        self.console.insert("end", "Services stopped.\n\n")
        self.console.see("end")
        self.processes.clear()

    def _stream_output(self, proc, name):
        for line in proc.stdout:
            self.console.insert("end", f"[{name}] {line}")
            self.console.see("end")
            
    def open_web_ui(self):
        webbrowser.open("http://localhost:8080")

if __name__ == "__main__":
    app = RadioGUI()
    app.mainloop()
