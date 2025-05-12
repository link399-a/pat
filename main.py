#!/usr/bin/env python3
import sys
import os
import configparser
from PyQt5 import QtCore, QtGui, QtWidgets

# Configuration file path
HOME_CONFIG = os.path.expanduser('~/.radio.conf')
CONFIG_PATH = HOME_CONFIG

# Load settings
cfg = configparser.ConfigParser()
cfg.read(CONFIG_PATH)

# Shared palette/styles helper
STYLE_SHEET = (
    "QWidget { background: black; color: lightgreen; }"
    "QTabBar::tab { padding: 8px; }"
)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Radio GUI")
        self.resize(1200, 800)

        # Apply global palette and stylesheet
        self.apply_shared_style()

        # Central widget and layout
        central = QtWidgets.QWidget()
        central.setStyleSheet('background:black;')
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # Header: callsign, time, date, grid
        hdr = self.build_header()
        layout.addLayout(hdr)

        # Tabs
        tabs = QtWidgets.QTabWidget()
        tabs.setTabPosition(QtWidgets.QTabWidget.West)
        tabs.setIconSize(QtCore.QSize(48, 48))
        tabs.setStyleSheet(STYLE_SHEET)
        layout.addWidget(tabs)

        # Load and add tabs in order: Pat, GPS, Config
        import pat_tab
        import gps_tab
        import config_tab

        pat_win = pat_tab.MainWindow()
        self.prepare_child(pat_win)
        tabs.addTab(pat_win.centralWidget(), QtGui.QIcon.fromTheme('media-playback-start'), 'Pat')

        gps_win = gps_tab.GPSWindow()
        self.prepare_child(gps_win)
        tabs.addTab(gps_win.centralWidget(), QtGui.QIcon.fromTheme('gps'), 'GPS')

        cfg_win = config_tab.ConfigWindow()
        self.prepare_child(cfg_win)
        tabs.addTab(cfg_win.centralWidget(), QtGui.QIcon.fromTheme('configure'), 'Configure')

        # Timer for system time
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.update_system_time)
        timer.start(1000)
        self.update_system_time()

    def apply_shared_style(self):
        # Use QApplication from QtWidgets, not QtGui
        app = QtWidgets.QApplication.instance()
        if app:
            pal = app.palette()
            self.setPalette(pal)
        self.setStyleSheet(STYLE_SHEET)

    def build_header(self):
        cfg_qt = QtCore.QSettings(CONFIG_PATH, QtCore.QSettings.IniFormat)
        call = cfg_qt.value('rigctld/my_call', '')
        grid = cfg_qt.value('rigctld/my_grid', '')

        hdr = QtWidgets.QHBoxLayout()
        lblCall = QtWidgets.QLabel(f"My Call: {call}")
        lblCall.setStyleSheet('font-size:16pt; font-weight:bold; color:lightgreen;')
        hdr.addWidget(lblCall)
        hdr.addStretch()

        timeL = QtWidgets.QVBoxLayout()
        self.lblTime = QtWidgets.QLabel()
        self.lblTime.setAlignment(QtCore.Qt.AlignCenter)
        self.lblTime.setStyleSheet('color:lightgreen;')
        self.lblDate = QtWidgets.QLabel()
        self.lblDate.setAlignment(QtCore.Qt.AlignCenter)
        self.lblDate.setStyleSheet('color:lightgreen;')
        timeL.addWidget(self.lblTime)
        timeL.addWidget(self.lblDate)
        hdr.addLayout(timeL)
        hdr.addStretch()

        lblGrid = QtWidgets.QLabel(f"My Grid: {grid}")
        lblGrid.setStyleSheet('font-size:16pt; font-weight:bold; color:lightgreen;')
        hdr.addWidget(lblGrid)
        return hdr

    def update_system_time(self):
        now = QtCore.QDateTime.currentDateTime()
        self.lblTime.setText(now.toString('HH:mm:ss'))
        self.lblDate.setText(now.toString('yyyy-MM-dd'))

    def prepare_child(self, win):
        # Ensure child windows use the shared style
        # If the child has its own apply_shared_palette, call it
        if hasattr(win, 'apply_shared_palette'):
            win.apply_shared_palette()
        win.setStyleSheet(STYLE_SHEET)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

