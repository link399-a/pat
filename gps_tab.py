#!/usr/bin/env python3
import os
import sys
import configparser
import re
from PyQt5 import QtWidgets, QtCore, QtGui

# Maidenhead locator conversion
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

# Read configuration
CONFIG_PATH = os.path.expanduser('~/.radio.conf')
cfg = configparser.ConfigParser()
cfg.read(CONFIG_PATH)
if not cfg.has_section('gps'):
    cfg.add_section('gps')
gps_cfg = cfg['gps']

gps_cmd = ['gpspipe', '-r']

class GPSWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('GPS Display')
        self.resize(500, 360)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central)

        # Time (large, centered)
        self.lblTime = QtWidgets.QLabel('--')
        self.lblTime.setAlignment(QtCore.Qt.AlignCenter)
        self.lblTime.setStyleSheet('font-size:48pt; font-weight:bold;')
        vbox.addWidget(self.lblTime)

        # Date (smaller, centered)
        self.lblDate = QtWidgets.QLabel('--')
        self.lblDate.setAlignment(QtCore.Qt.AlignCenter)
        self.lblDate.setStyleSheet('font-size:16pt;')
        vbox.addWidget(self.lblDate)

        # Row: Latitude, Longitude, Altitude
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel('Lat:'))
        self.lblLat = QtWidgets.QLabel('--')
        row2.addWidget(self.lblLat)
        row2.addStretch(1)
        row2.addWidget(QtWidgets.QLabel('Lon:'))
        self.lblLon = QtWidgets.QLabel('--')
        row2.addWidget(self.lblLon)
        row2.addStretch(1)
        row2.addWidget(QtWidgets.QLabel('Alt:'))
        self.lblAlt = QtWidgets.QLabel('--')
        row2.addWidget(self.lblAlt)
        vbox.addLayout(row2)

        # Grid and Update button
        row3 = QtWidgets.QHBoxLayout()
        row3.addWidget(QtWidgets.QLabel('Grid:'))
        self.lblGrid = QtWidgets.QLabel('--')
        row3.addWidget(self.lblGrid)
        row3.addStretch(1)
        btnUpdate = QtWidgets.QPushButton('Update Grid in Config')
        btnUpdate.clicked.connect(self.update_grid_config)
        row3.addWidget(btnUpdate)
        vbox.addLayout(row3)

        # Raw NMEA display
        vbox.addWidget(QtWidgets.QLabel('Raw NMEA:'))
        self.txtRaw = QtWidgets.QPlainTextEdit(readOnly=True)
        self.txtRaw.setFixedHeight(120)
        vbox.addWidget(self.txtRaw)

        # Start GPS process
        self.current_grid = None
        self.gps_proc = QtCore.QProcess(self)
        self.gps_proc.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.gps_proc.readyReadStandardOutput.connect(self.parse_gps)
        self.gps_proc.start(gps_cmd[0], gps_cmd[1:])

    def parse_gps(self):
        raw = bytes(self.gps_proc.readAllStandardOutput()).decode(errors='ignore')
        self.txtRaw.appendPlainText(raw.rstrip())
        lat_dd = lon_dd = None
        for line in raw.splitlines():
            if line.startswith('$GPRMC'):
                parts = line.split(',')
                if len(parts) > 9 and parts[2] == 'A':
                    t, d = parts[1], parts[9]
                    hh, mm, ss = t[:2], t[2:4], t[4:6]
                    self.lblTime.setText(f"{hh}:{mm}:{ss}")
                    self.lblDate.setText(f"{d[0:2]}/{d[2:4]}/20{d[4:6]}")
            elif line.startswith('$GPGGA'):
                parts = line.split(',')
                if len(parts) > 9 and parts[6] != '0':
                    lat_val, lat_h = parts[2], parts[3]
                    lon_val, lon_h = parts[4], parts[5]
                    lat_dd = (float(lat_val[:2]) + float(lat_val[2:]) / 60) * (1 if lat_h == 'N' else -1)
                    lon_dd = (float(lon_val[:3]) + float(lon_val[3:]) / 60) * (1 if lon_h == 'E' else -1)
                    self.lblLat.setText(self._format_coord(lat_val, lat_h))
                    self.lblLon.setText(self._format_coord(lon_val, lon_h))
                    self.lblAlt.setText(parts[9] + ' m')
        if lat_dd is not None and lon_dd is not None:
            grid = latlon_to_grid(lat_dd, lon_dd)
            if grid != self.current_grid:
                self.current_grid = grid
                self.lblGrid.setText(grid)

    def _format_coord(self, val, hemi):
        deg_len = 2 if hemi in ['N','S'] else 3
        return f"{val[:deg_len]}° {val[deg_len:]} '{hemi}"

    def update_grid_config(self):
        if self.current_grid:
            cfg['gps']['grid'] = self.current_grid
            with open(CONFIG_PATH, 'w') as f:
                cfg.write(f)
            QtWidgets.QMessageBox.information(self, 'Grid Updated',
                f"Saved grid {self.current_grid} to {CONFIG_PATH}.")
        else:
            QtWidgets.QMessageBox.warning(self, 'No Grid', 'GPS grid not yet determined.')

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = GPSWindow()
    win.show()
    sys.exit(app.exec_())

