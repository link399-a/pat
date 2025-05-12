#!/usr/bin/env python3
import os
import sys
import configparser
from PyQt5 import QtCore, QtGui, QtWidgets

# Load configuration
CONFIG_PATH = os.path.expanduser('~/.radio.conf')
cfg = configparser.ConfigParser()
cfg.read(CONFIG_PATH)
rig_cfg = cfg['rigctld'] if cfg.has_section('rigctld') else {}
audio_cfg = cfg['audio'] if cfg.has_section('audio') else {}

# Build commands for services
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

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Pat Radio GUI')
        self.resize(800, 600)
        self.processes = []
        self.services_running = False

        # Status bar
        self.setStatusBar(QtWidgets.QStatusBar())
        self.update_status()

        # Central widget
        central = QtWidgets.QWidget()
        central.setStyleSheet('background:black;')
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # Pat Tab area (single tab for simplicity)
        hdr = QtWidgets.QHBoxLayout()
        # Toggle button
        btnToggle = QtWidgets.QPushButton()
        btnToggle.setIcon(QtGui.QIcon.fromTheme('media-playback-start'))
        btnToggle.setIconSize(QtCore.QSize(48,48))
        btnToggle.clicked.connect(self.toggle_services)
        hdr.addWidget(btnToggle)
        # Browser button
        btnBrowser = QtWidgets.QPushButton()
        btnBrowser.setIcon(QtGui.QIcon.fromTheme('internet-web-browser'))
        btnBrowser.setIconSize(QtCore.QSize(48,48))
        btnBrowser.clicked.connect(self.open_browser)
        hdr.addWidget(btnBrowser)
        hdr.addStretch()
        layout.addLayout(hdr)

        # Output console
        self.output_console = QtWidgets.QPlainTextEdit(readOnly=True)
        self.output_console.setStyleSheet('background:black;color:lightgreen')
        layout.addWidget(self.output_console)

    def update_status(self):
        msg = 'Services running' if self.services_running else 'Services stopped'
        self.statusBar().showMessage(msg)

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

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.Window, QtGui.QColor('black'))
    pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor('lightgreen'))
    app.setPalette(pal)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

