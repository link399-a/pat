#!/usr/bin/env python3
import os
import sys
import configparser
import subprocess
import re
import math
from PyQt5 import QtCore, QtGui, QtWidgets

# Configuration paths
LOCAL_CONFIG = os.path.join(os.getcwd(), '.radio.conf')
HOME_CONFIG = os.path.expanduser('~/.radio.conf')
CONFIG_PATH = LOCAL_CONFIG if os.path.exists(LOCAL_CONFIG) else HOME_CONFIG

# Load settings
cfg = configparser.ConfigParser()
cfg.read(CONFIG_PATH)
rig_cfg = cfg['rigctld'] if cfg.has_section('rigctld') else {}
audio_cfg = cfg['audio'] if cfg.has_section('audio') else {}

# Build service commands
def build_service_commands():
    model = rig_cfg.get('model', '2050')
    device = rig_cfg.get('device', '/dev/ttyUSB0')
    baud = rig_cfg.get('baud', '9600')
    ptt = rig_cfg.get('ptt_type', 'RTS')
    dcd = rig_cfg.get('dcd_type', 'RIG')
    hw = audio_cfg.get('hw', '0,0')
    return [
        ['rigctld', '-m', model, '-r', device, '-s', baud, '-P', ptt, '-D', dcd],
        ['./ardopcf', '--logdir', os.path.expanduser('~/ardop_logs'), '-p', device, '8515', f'plughw:{hw}', f'plughw:{hw}'],
        ['pat', '--listen=ardop,telnet', 'http']
    ]

# List serial devices including GPS ports
def list_serial_devices():
    try:
        return sorted(f"/dev/{d}" for d in os.listdir('/dev') if d.startswith(('ttyUSB', 'ttyACM', 'ttyS')))
    except FileNotFoundError:
        return []

# List available rigs via rigctl
def list_rigs():
    rigs = []
    try:
        out = subprocess.run(['rigctl', '-l'], capture_output=True, text=True, check=True).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                rigs.append((parts[0], parts[1], parts[2]))
    except subprocess.CalledProcessError:
        pass
    return rigs

# List audio pairs via ardopcf
def list_audio_pairs():
    pairs = []
    try:
        out = subprocess.run(['./ardopcf', '-m'], capture_output=True, text=True, check=True).stdout
        for c, hw in re.findall(r"Card\s+(\d+).*?hw:(\d+,\d+)", out, re.DOTALL):
            if (c, hw) not in pairs:
                pairs.append((c, hw))
    except subprocess.CalledProcessError:
        pass
    return pairs

# Convert lat/lon to Maidenhead grid locator
def latlon_to_grid(lat, lon):
    lon += 180.0
    lat += 90.0
    A = ord('A')
    lon_field = int(lon // 20)
    lat_field = int(lat // 10)
    lon_square = int((lon % 20) // 2)
    lat_square = int((lat % 10) // 1)
    lon_rem = lon - lon_field * 20 - lon_square * 2
    lat_rem = lat - lat_field * 10 - lat_square * 1
    lon_sub = int(lon_rem * 12)
    lat_sub = int(lat_rem * 24)
    return (f"{chr(A + lon_field)}{chr(A + lat_field)}"
            f"{lon_square}{lat_square}"
            f"{chr(A + lon_sub).lower()}{chr(A + lat_sub).lower()}")

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pat Radio GUI")
        self.resize(1200, 800)
        self.processes = []
        self.services_running = False
        self.gps_override = False
        self.rmc_time = None
        self.rmc_date = None

        # Status bar
        self.setStatusBar(QtWidgets.QStatusBar())
        self.update_status()

        # Central widget
        central = QtWidgets.QWidget()
        central.setStyleSheet('background:black;')
        self.setCentralWidget(central)
        mainLayout = QtWidgets.QVBoxLayout(central)

        # Header layout
        hdr = QtWidgets.QHBoxLayout()
        self.lblCall = QtWidgets.QLabel(f"My Call: {rig_cfg.get('my_call', '')}")
        self.lblCall.setStyleSheet('color:lightgreen;font-size:16pt;font-weight:bold')
        hdr.addWidget(self.lblCall)
        hdr.addStretch()

        timeL = QtWidgets.QVBoxLayout()
        self.lblTime = QtWidgets.QLabel()
        self.lblTime.setStyleSheet('color:orange;font-size:48pt')
        self.lblTime.setAlignment(QtCore.Qt.AlignCenter)
        self.lblDate = QtWidgets.QLabel()
        self.lblDate.setStyleSheet('color:lightblue;font-size:10pt')
        self.lblDate.setAlignment(QtCore.Qt.AlignCenter)
        timeL.addWidget(self.lblTime)
        timeL.addWidget(self.lblDate)
        hdr.addLayout(timeL)
        hdr.addStretch()

        self.lblGrid = QtWidgets.QLabel(f"My Grid: {rig_cfg.get('my_grid', '')}")
        self.lblGrid.setStyleSheet('color:lightgreen;font-size:16pt;font-weight:bold')
        hdr.addWidget(self.lblGrid)
        mainLayout.addLayout(hdr)

        # System time timer
        self.sys_timer = QtCore.QTimer(self)
        self.sys_timer.timeout.connect(self.system_time)
        self.sys_timer.start(1000)
        self.system_time()

        # Tab widget
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabPosition(QtWidgets.QTabWidget.West)
        self.tabs.setIconSize(QtCore.QSize(64, 64))
        mainLayout.addWidget(self.tabs)
        icoDir = 'icons'
        icoPat = QtGui.QIcon(os.path.join(icoDir, 'pat-logo.png'))
        icoGps = QtGui.QIcon(os.path.join(icoDir, 'gps.png'))
        icoCfg = QtGui.QIcon(os.path.join(icoDir, 'configure.png'))

        # --- Pat Tab ---
        wPat = QtWidgets.QWidget()
        self.tabs.addTab(wPat, icoPat, 'Pat')
        lp = QtWidgets.QVBoxLayout(wPat)
        bh = QtWidgets.QHBoxLayout()
        pwr = QtGui.QIcon(os.path.join(icoDir, 'power.png'))
        self.btnToggle = QtWidgets.QPushButton()
        self.btnToggle.setIcon(pwr)
        self.btnToggle.setIconSize(QtCore.QSize(64, 64))
        self.btnToggle.clicked.connect(self.toggle_services)
        bh.addWidget(self.btnToggle)
        ff = QtGui.QIcon(os.path.join(icoDir, 'firefox.png'))
        self.btnBrowser = QtWidgets.QPushButton()
        self.btnBrowser.setIcon(ff)
        self.btnBrowser.setIconSize(QtCore.QSize(64, 64))
        self.btnBrowser.clicked.connect(self.open_browser)
        bh.addWidget(self.btnBrowser)
        bh.addStretch()
        lp.addLayout(bh)
        self.output_console = QtWidgets.QPlainTextEdit(readOnly=True)
        self.output_console.setStyleSheet('background:black;color:lightgreen')
        lp.addWidget(self.output_console)

        # --- GPS Tab ---
        wGps = QtWidgets.QWidget()
        self.tabs.addTab(wGps, icoGps, 'GPS')
        form = QtWidgets.QFormLayout(wGps)
        self.gps_time = QtWidgets.QLabel('--')
        form.addRow('Time:', self.gps_time)
        self.gps_date = QtWidgets.QLabel('--')
        form.addRow('Date:', self.gps_date)
        self.gps_lat = QtWidgets.QLabel('--')
        form.addRow('Latitude:', self.gps_lat)
        self.gps_lon = QtWidgets.QLabel('--')
        form.addRow('Longitude:', self.gps_lon)
        self.gps_sats = QtWidgets.QLabel('--')
        form.addRow('Satellites:', self.gps_sats)
        self.gps_alt = QtWidgets.QLabel('--')
        form.addRow('Altitude:', self.gps_alt)
        self.gps_grid = QtWidgets.QLabel('--')
        form.addRow('Grid:', self.gps_grid)
        # Raw NMEA display
        self.gps_raw = QtWidgets.QPlainTextEdit(readOnly=True)
        self.gps_raw.setStyleSheet('background:black;color:white')
        self.gps_raw.setFixedHeight(150)
        form.addRow('Raw NMEA:', self.gps_raw)
        # Start gpspipe
        self.gps_proc = QtCore.QProcess(self)
        self.gps_proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.gps_proc.readyReadStandardOutput.connect(self.parse_gps)
        self.gps_proc.start('gpspipe', ['-r'])

        # --- Configure Tab ---
        wCfg = QtWidgets.QScrollArea()
        wCfg.setWidgetResizable(True)
        cont = QtWidgets.QWidget()
        wCfg.setWidget(cont)
        self.tabs.addTab(wCfg, icoCfg, 'Configure')
        self.build_config_ui(cont)

    def system_time(self):
        now = QtCore.QDateTime.currentDateTime()
        if not self.gps_override:
            self.lblTime.setText(now.toString('HH:mm:ss'))
            self.lblDate.setText(now.toString('yyyy-MM-dd'))

    def parse_gps(self):
        raw = self.gps_proc.readAllStandardOutput().data().decode()
        lines = raw.split('\n')
        self.gps_raw.appendPlainText(raw.rstrip())
        for line in lines:
            if line.startswith('$GPRMC'):
                parts = line.split(',')
                if len(parts) > 9 and parts[2] == 'A':
                    self.rmc_time, self.rmc_date = parts[1], parts[9]
            elif line.startswith('$GPGGA') and self.rmc_time:
                p2 = line.split(',')
                if len(p2) > 9 and p2[6] != '0':
                    lat, lat_h = p2[2], p2[3]
                    lon, lon_h = p2[4], p2[5]
                    sats, alt = p2[7], p2[9]
                    t, d = self.rmc_time, self.rmc_date
                    self.gps_time.setText(f"{t[:2]}:{t[2:4]}:{t[4:6]}")
                    self.lblTime.setText(self.gps_time.text())
                    self.gps_date.setText(f"{d[2:4]}/{d[4:6]}/{d[:2]}")
                    self.lblDate.setText(self.gps_date.text())
                    def fmt(v, h):
                        deg_len = 2 if len(v.split('.')[0]) <= 4 else 3
                        return f"{v[:deg_len]}° {v[deg_len:]} '{h}'"
                    self.gps_lat.setText(fmt(lat, lat_h))
                    self.gps_lon.setText(fmt(lon, lon_h))
                    self.gps_sats.setText(sats)
                    self.gps_alt.setText(f"{alt} m")
                    # Convert to signed decimal degrees, accounting for N/S and E/W
                    lat_dd = (float(lat[:2]) + float(lat[2:]) / 60) * (1 if lat_h == 'N' else -1)
                    lon_dd = (float(lon[:3]) + float(lon[3:]) / 60) * (1 if lon_h == 'E' else -1)
                    self.gps_grid.setText(latlon_to_grid(lat_dd, lon_dd))
                    self.gps_override = True
                break

    def toggle_services(self):
        if not self.services_running:
            for cmd in build_service_commands():
                p = QtCore.QProcess(self)
                p.setProcessChannelMode(QtCore.QProcess.MergedChannels)
                p.readyReadStandardOutput.connect(lambda pr=p: self.output_console.appendPlainText(pr.readAllStandardOutput().data().decode()))
                p.start(cmd[0], cmd[1:])
                self.processes.append(p)
            self.services_running = True
        else:
            for p in self.processes:
                p.kill()
            os.system('killall rigctld ardopcf pat')
            self.processes.clear()
            self.services_running = False
        self.update_status()

    def open_browser(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl('http://localhost:8080'))

    def build_config_ui(self, parent):
        layout = QtWidgets.QVBoxLayout(parent)
        # My Info
        grp = QtWidgets.QGroupBox('My Info')
        layout.addWidget(grp)
        gL = QtWidgets.QFormLayout(grp)
        self.eCall = QtWidgets.QLineEdit(rig_cfg.get('my_call', ''))
        gL.addRow('Call:', self.eCall)
        self.eGrid = QtWidgets.QLineEdit(rig_cfg.get('my_grid', ''))
        gL.addRow('Grid:', self.eGrid)
        # CAT Control
        grp2 = QtWidgets.QGroupBox('CAT Control')
        layout.addWidget(grp2)
        g2L = QtWidgets.QFormLayout(grp2)
        rigs = list_rigs()
        opts = [f"{n} - {m} {d}" for n, m, d in rigs]
        self.cbRig = QtWidgets.QComboBox()
        self.cbRig.addItems(opts)
        if rig_cfg.get('model'):
            idx = next((i for i, v in enumerate(opts) if v.startswith(rig_cfg['model'])), 0)
            self.cbRig.setCurrentIndex(idx)
        g2L.addRow('Rig:', self.cbRig)
        devs = list_serial_devices()
        self.cbDev = QtWidgets.QComboBox()
        self.cbDev.addItems(devs)
        if rig_cfg.get('device'):
            self.cbDev.setCurrentText(rig_cfg['device'])
        g2L.addRow('Device:', self.cbDev)
        bauds = ['4800', '9600', '19200', '38400', '57600', '115200']
        self.cbBaud = QtWidgets.QComboBox()
        self.cbBaud.addItems(bauds)
        if rig_cfg.get('baud'):
            self.cbBaud.setCurrentText(rig_cfg['baud'])
        g2L.addRow('Baud:', self.cbBaud)
        # PTT/DCD
        grp3 = QtWidgets.QGroupBox('PTT / DCD')
        layout.addWidget(grp3)
        g3L = QtWidgets.QFormLayout(grp3)
        ptt_types = ['RIG', 'DTR', 'RTS', 'PARALLEL', 'CM108', 'GPIO', 'GPION', 'NONE']
        self.cbPTT = QtWidgets.QComboBox()
        self.cbPTT.addItems(ptt_types)
        if rig_cfg.get('ptt_type'):
            self.cbPTT.setCurrentText(rig_cfg['ptt_type'])
        g3L.addRow('PTT Type:', self.cbPTT)
        dcd_types = ['RIG', 'DSR', 'CTS', 'CD', 'PARALLEL', 'CM108', 'GPIO', 'GPION', 'NONE']
        self.cbDCD = QtWidgets.QComboBox()
        self.cbDCD.addItems(dcd_types)
        if rig_cfg.get('dcd_type'):
            self.cbDCD.setCurrentText(rig_cfg['dcd_type'])
        g3L.addRow('DCD Type:', self.cbDCD)
        # Audio
        grp4 = QtWidgets.QGroupBox('Audio')
        layout.addWidget(grp4)
        g4L = QtWidgets.QFormLayout(grp4)
        aud = list_audio_pairs()
        aud_opts = [f"Card {c} hw:{hw}" for c, hw in aud]
        self.cbAudio = QtWidgets.QComboBox()
        if aud_opts:
            self.cbAudio.addItems(aud_opts)
            cur = (audio_cfg.get('card',''), audio_cfg.get('hw',''))
            for i, (c, hw) in enumerate(aud):
                if (c, hw) == cur:
                    self.cbAudio.setCurrentIndex(i)
        g4L.addRow('Audio:', self.cbAudio)
        # GPS Device
        grp5 = QtWidgets.QGroupBox('GPS Device')
        layout.addWidget(grp5)
        g5L = QtWidgets.QFormLayout(grp5)
        devs = list_serial_devices()
        self.cbGPS = QtWidgets.QComboBox()
        self.cbGPS.addItems(devs)
        if rig_cfg.get('gps_device'):
            self.cbGPS.setCurrentText(rig_cfg['gps_device'])
        g5L.addRow('Port:', self.cbGPS)
        # Buttons
        btns = QtWidgets.QHBoxLayout()
        layout.addLayout(btns)
        btns.addStretch()
        btnSave = QtWidgets.QPushButton('Save')
        btnSave.clicked.connect(self.save_config)
        btns.addWidget(btnSave)
        btnCancel = QtWidgets.QPushButton('Cancel')
        btnCancel.clicked.connect(self.cancel_config)
        btns.addWidget(btnCancel)

    def update_status(self):
        msg = 'Services running: rigctld, ardopcf, pat' if self.services_running else 'Services stopped'
        self.statusBar().showMessage(msg)

    def open_browser(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl('http://localhost:8080'))

    def save_config(self):
        if not cfg.has_section('rigctld'):
            cfg.add_section('rigctld')
        if not cfg.has_section('audio'):
            cfg.add_section('audio')
        cfg['rigctld']['my_call'] = self.eCall.text()
        cfg['rigctld']['my_grid'] = self.eGrid.text()
        cfg['rigctld']['model'] = self.cbRig.currentText().split()[0]
        cfg['rigctld']['device'] = self.cbDev.currentText()
        cfg['rigctld']['baud'] = self.cbBaud.currentText()
        cfg['rigctld']['ptt_type'] = self.cbPTT.currentText()
        cfg['rigctld']['dcd_type'] = self.cbDCD.currentText()
        # c, hw = self.cbAudio.currentText().split()[1].split(':')
        # Parse “Card X hw:Y,Z”
        audio_text = self.cbAudio.currentText().split()
        if len(audio_text) >= 3 and audio_text[0] == 'Card':
            c = audio_text[1]
            hw = audio_text[2].split(':', 1)[1]
        else:
            c = audio_cfg.get('card', '')
            hw = audio_cfg.get('hw', '')
        cfg['audio']['card'] = c
        cfg['audio']['hw'] = hw
        cfg['rigctld']['gps_device'] = self.cbGPS.currentText()
        with open(CONFIG_PATH, 'w') as f:
            cfg.write(f)
        self.lblCall.setText(f"My Call: {self.eCall.text()}")
        self.lblGrid.setText(f"My Grid: {self.eGrid.text()}")

    def cancel_config(self):
        cfg.read(CONFIG_PATH)
        self.eCall.setText(cfg['rigctld'].get('my_call', ''))
        self.eGrid.setText(cfg['rigctld'].get('my_grid', ''))
        self.cbRig.setCurrentText(rig_cfg.get('model', ''))
        self.cbDev.setCurrentText(rig_cfg.get('device', ''))
        self.cbBaud.setCurrentText(rig_cfg.get('baud', ''))
        self.cbPTT.setCurrentText(rig_cfg.get('ptt_type', ''))
        self.cbDCD.setCurrentText(rig_cfg.get('dcd_type', ''))
        if audio_cfg:
            self.cbAudio.setCurrentText(f"Card {audio_cfg.get('card','')} hw:{audio_cfg.get('hw','')}")
        if rig_cfg.get('gps_device'):
            self.cbGPS.setCurrentText(rig_cfg['gps_device'])

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.Window, QtGui.QColor('black'))
    pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor('lightblue'))
    pal.setColor(QtGui.QPalette.Base, QtGui.QColor('black'))
    pal.setColor(QtGui.QPalette.Text, QtGui.QColor('lightgreen'))
    pal.setColor(QtGui.QPalette.Button, QtGui.QColor('black'))
    pal.setColor(QtGui.QPalette.ButtonText, QtGui.QColor('lightblue'))
    app.setPalette(pal)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

