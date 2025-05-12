#!/usr/bin/env python3
import sys
import os
import configparser
from PyQt5 import QtCore, QtGui, QtWidgets


# Configuration file path
HOME_CONFIG = os.path.expanduser('~/.radio.conf')
CONFIG_PATH = HOME_CONFIG

# Shared palette/styles helper
STYLE_SHEET = (
    "QWidget { background: black; color: lightgreen; }"
    "QTabBar::tab { padding: 8px; }"
)


def load_config(config_path):
    """Load the configuration file and handle errors gracefully"""
    cfg = configparser.ConfigParser()
    if not os.path.exists(config_path):
        print(f"Warning: Configuration file not found at {config_path}. Using defaults.")
    else:
        try:
            cfg.read(config_path)
        except configparser.Error as e:
            print(f"Error reading configuration file: {e}")
    return cfg


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
        try:
            import pat_tab
            import gps_tab
            import config_tab
        except ImportError as e:
            print(f"Error importing tab modules: {e}")
            sys.exit(1)

        # Adding tabs dynamically
        self.add_tab(tabs, pat_tab.MainWindow, 'Pat', 'media-playback-start')
        self.add_tab(tabs, gps_tab.GPSWindow, 'GPS', 'gps')
        self.add_tab(tabs, config_tab.ConfigWindow, 'Configure', 'configure')

        # Timer for system time
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.update_system_time)
        timer.start(1000)
        self.update_system_time()

    def apply_shared_style(self):
        """Apply shared styles and palette"""
        app = QtWidgets.QApplication.instance()
        if app:
            pal = app.palette()
            self.setPalette(pal)
        self.setStyleSheet(STYLE_SHEET)

    def build_header(self):
        """Build the header layout with callsign, time, date, and grid"""
        cfg_qt = QtCore.QSettings(CONFIG_PATH, QtCore.QSettings.IniFormat)
        call = cfg_qt.value('rigctld/my_call', 'Unknown')
        grid = cfg_qt.value('rigctld/my_grid', 'Unknown')

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
        """Update the displayed system time and date"""
        now = QtCore.QDateTime.currentDateTime()
        self.lblTime.setText(now.toString('HH:mm:ss'))
        self.lblDate.setText(now.toString('yyyy-MM-dd'))

    def add_tab(self, tabs, window_class, name, icon_theme):
        """Add a tab dynamically"""
        try:
            win = window_class()
            self.prepare_child(win)
            icon = QtGui.QIcon.fromTheme(icon_theme)
            tabs.addTab(win.centralWidget(), icon, name)
        except Exception as e:
            print(f"Error adding tab {name}: {e}")

    def prepare_child(self, win):
        """Ensure child windows use the shared style"""
        if hasattr(win, 'apply_shared_palette'):
            win.apply_shared_palette()
        win.setStyleSheet(STYLE_SHEET)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
