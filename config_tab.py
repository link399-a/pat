#!/usr/bin/env python3
import os
import configparser
import subprocess
import re
from PyQt5 import QtCore, QtWidgets, QtGui

# Configuration file path
HOME_CONFIG = os.path.expanduser('~/.radio.conf')
CONFIG_PATH = HOME_CONFIG

# Load settings
cfg = configparser.ConfigParser()
cfg.read(CONFIG_PATH)

class ConfigWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configure Radio")
        self.resize(400, 600)

        # Central scrollable area
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        scroll.setWidget(container)
        self.setCentralWidget(scroll)

        # Apply shared styles to container
        self.apply_shared_style(container)

        # Build UI inside container
        layout = QtWidgets.QVBoxLayout(container)

        # My Info group
        grp = QtWidgets.QGroupBox('My Info')
        gL = QtWidgets.QFormLayout(grp)
        self.eCall = QtWidgets.QLineEdit(cfg.get('rigctld', 'my_call', fallback=''))
        gL.addRow('Call:', self.eCall)
        self.eGrid = QtWidgets.QLineEdit(cfg.get('rigctld', 'my_grid', fallback=''))
        gL.addRow('Grid:', self.eGrid)
        layout.addWidget(grp)

        # CAT Control group
        grp2 = QtWidgets.QGroupBox('CAT Control')
        g2L = QtWidgets.QFormLayout(grp2)
        rigs = self.list_rigs()
        opts = [f"{n} - {m} {d}" for n, m, d in rigs]
        self.cbRig = QtWidgets.QComboBox()
        self.cbRig.addItems(opts)
        current_model = cfg.get('rigctld', 'model', fallback='')
        if current_model:
            for i, opt in enumerate(opts):
                if opt.startswith(current_model):
                    self.cbRig.setCurrentIndex(i)
                    break
        g2L.addRow('Rig:', self.cbRig)

        devs = self.list_serial_devices()
        self.cbDev = QtWidgets.QComboBox()
        self.cbDev.addItems(devs)
        self.cbDev.setCurrentText(cfg.get('rigctld','device',fallback=''))
        g2L.addRow('Device:', self.cbDev)

        bauds = ['4800','9600','19200','38400','57600','115200']
        self.cbBaud = QtWidgets.QComboBox()
        self.cbBaud.addItems(bauds)
        self.cbBaud.setCurrentText(cfg.get('rigctld','baud',fallback='9600'))
        g2L.addRow('Baud:', self.cbBaud)
        layout.addWidget(grp2)

        # PTT / DCD group
        grp3 = QtWidgets.QGroupBox('PTT / DCD')
        g3L = QtWidgets.QFormLayout(grp3)
        ptt_types = ['RIG','DTR','RTS','PARALLEL','CM108','GPIO','GPION','NONE']
        self.cbPTT = QtWidgets.QComboBox()
        self.cbPTT.addItems(ptt_types)
        self.cbPTT.setCurrentText(cfg.get('rigctld','ptt_type',fallback='RTS'))
        g3L.addRow('PTT Type:', self.cbPTT)
        dcd_types = ['RIG','DSR','CTS','CD','PARALLEL','CM108','GPIO','GPION','NONE']
        self.cbDCD = QtWidgets.QComboBox()
        self.cbDCD.addItems(dcd_types)
        self.cbDCD.setCurrentText(cfg.get('rigctld','dcd_type',fallback='RIG'))
        g3L.addRow('DCD Type:', self.cbDCD)
        layout.addWidget(grp3)

        # Audio group
        grp4 = QtWidgets.QGroupBox('Audio')
        g4L = QtWidgets.QFormLayout(grp4)
        aud = self.list_audio_pairs()
        aud_opts = [f"Card {c} hw:{hw}" for c, hw in aud]
        self.cbAudio = QtWidgets.QComboBox()
        self.cbAudio.addItems(aud_opts)
        current_card = cfg.get('audio','card',fallback='')
        current_hw = cfg.get('audio','hw',fallback='')
        for i, (c, hw) in enumerate(aud):
            if c == current_card and hw == current_hw:
                self.cbAudio.setCurrentIndex(i)
                break
        g4L.addRow('Audio:', self.cbAudio)
        layout.addWidget(grp4)

        # GPS group
        grp5 = QtWidgets.QGroupBox('GPS')
        g5L = QtWidgets.QFormLayout(grp5)
        self.cbGPS = QtWidgets.QComboBox()
        self.cbGPS.addItems(devs)
        self.cbGPS.setCurrentText(cfg.get('gps','device',fallback=''))
        g5L.addRow('Port:', self.cbGPS)
        layout.addWidget(grp5)

        # Save/Cancel buttons
        btns = QtWidgets.QHBoxLayout()
        btns.addStretch()
        save = QtWidgets.QPushButton('Save')
        save.clicked.connect(self.save_config)
        cancel = QtWidgets.QPushButton('Cancel')
        cancel.clicked.connect(self.cancel_config)
        btns.addWidget(save)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def apply_shared_style(self, widget):
        # Apply palette and stylesheet to widget
        app = QtWidgets.QApplication.instance()
        if app:
            widget.setPalette(app.palette())
            widget.setAutoFillBackground(True)
        widget.setStyleSheet(
            "QGroupBox { background: black; color: lightgreen; border: 1px solid lightgreen; margin-top: 6px; }"
            "QWidget, QLineEdit, QComboBox, QPushButton { background: #000; color: lightgreen; }"
        )

    def list_serial_devices(self):
        try:
            return sorted(f"/dev/{d}" for d in os.listdir('/dev') if d.startswith(('ttyUSB','ttyACM','ttyS')))
        except FileNotFoundError:
            return []

    def list_rigs(self):
        rigs = []
        try:
            out = subprocess.run(['rigctl','-l'], capture_output=True, text=True, check=True).stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    rigs.append((parts[0], parts[1], parts[2]))
        except subprocess.CalledProcessError:
            pass
        return rigs

    def list_audio_pairs(self):
        pairs = []
        try:
            out = subprocess.run(['./ardopcf','-m'], capture_output=True, text=True, check=True).stdout
            for c, hw in re.findall(r"Card\s+(\d+).*?hw:(\d+,\d+)", out, re.DOTALL):
                if (c, hw) not in pairs:
                    pairs.append((c, hw))
        except subprocess.CalledProcessError:
            pass
        return pairs

    def save_config(self):
        if not cfg.has_section('rigctld'):
            cfg.add_section('rigctld')
        if not cfg.has_section('audio'):
            cfg.add_section('audio')
        if not cfg.has_section('gps'):
            cfg.add_section('gps')
        cfg['rigctld']['my_call'] = self.eCall.text()
        cfg['rigctld']['my_grid'] = self.eGrid.text()
        cfg['rigctld']['model'] = self.cbRig.currentText().split()[0]
        cfg['rigctld']['device'] = self.cbDev.currentText()
        cfg['rigctld']['baud'] = self.cbBaud.currentText()
        cfg['rigctld']['ptt_type'] = self.cbPTT.currentText()
        cfg['rigctld']['dcd_type'] = self.cbDCD.currentText()
        audio_text = self.cbAudio.currentText().split()
        if len(audio_text) >= 3 and audio_text[0] == 'Card':
            cfg['audio']['card'] = audio_text[1]
            cfg['audio']['hw'] = audio_text[2].split(':', 1)[1]
        cfg['gps']['device'] = self.cbGPS.currentText()
        with open(CONFIG_PATH, 'w') as f:
            cfg.write(f)

    def cancel_config(self):
        cfg.read(CONFIG_PATH)
        self.close()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = ConfigWindow()
    win.show()
    sys.exit(app.exec_())
