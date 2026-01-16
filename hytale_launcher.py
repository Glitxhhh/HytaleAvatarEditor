import sys
import os
import subprocess
import threading
import time
import re

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLineEdit, QLabel, QSlider, QCheckBox,
    QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor, QIcon

#      ▄████  ██▓     ██▓▄▄▄█████▓▒██   ██▒ ██░ ██ 
#     ██▒ ▀█▒▓██▒    ▓██▒▓  ██▒ ▓▒▒▒ █ █ ▒░▓██░ ██▒
#    ▒██░▄▄▄░▒██░    ▒██▒▒ ▓██░ ▒░░░  █   ░▒██▀▀██░
#    ░▓█  ██▓▒██░    ░██░░ ▓██▓ ░  ░ █ █ ▒ ░▓█ ░██ 
#    ░▒▓███▀▒░██████▒░██░  ▒██▒ ░ ▒██▒ ▒██▒░▓█▒░██▓
#     ░▒   ▒ ░ ▒░▓  ░░▓    ▒ ░░   ▒▒ ░ ░▓ ░ ▒ ░░▒░▒
#      ░   ░ ░ ░ ▒  ░ ▒ ░    ░    ░░   ░▒ ░ ▒ ░▒░ ░
#    ░ ░   ░   ░ ░    ▒ ░  ░       ░    ░   ░  ░░ ░
#          ░     ░  ░ ░            ░    ░   ░  ░  ░
#                                                  

# ---------------- CONFIG ----------------

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(APP_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "server.log")

os.makedirs(LOG_DIR, exist_ok=True)

ANSI_REGEX = re.compile(r"\x1b\[(\d+(?:;\d+)*)m")

ANSI_COLORS = {
    30: QColor("#000000"),
    31: QColor("#ff5555"),
    32: QColor("#55ff55"),
    33: QColor("#ffff55"),
    34: QColor("#5599ff"),
    35: QColor("#ff55ff"),
    36: QColor("#55ffff"),
    37: QColor("#ffffff"),
}

DEFAULT_TEXT_COLOR = QColor("#b266ff")  # purple

# ---------------- SIGNALS ----------------

class Signals(QObject):
    text = pyqtSignal(str)
    stopped = pyqtSignal(bool)

signals = Signals()

# ---------------- SERVER THREAD ----------------

class ServerProcess(threading.Thread):
    def __init__(self, min_ram, max_ram, auto_restart):
        super().__init__(daemon=True)
        self.min_ram = min_ram
        self.max_ram = max_ram
        self.auto_restart = auto_restart
        self.process = None
        self.stop_requested = False

    def run(self):
        while True:
            self.start_process()
            self.process.wait()

            if self.stop_requested:
                signals.stopped.emit(False)
                break

            signals.text.emit("\n[Server crashed]\n")
            if not self.auto_restart:
                signals.stopped.emit(True)
                break

            time.sleep(2)
            signals.text.emit("Restarting server...\n")

    def start_process(self):
        cmd = [
            "java",
            "-Dfile.encoding=UTF-8",
            f"-Xms{self.min_ram}G",
            f"-Xmx{self.max_ram}G",
            "-jar",
            "HytaleServer.jar",
            "--assets",
            os.path.join(APP_DIR, "..", "Assets.zip"),
            "--auth-mode",
            "offline",
        ]

        self.process = subprocess.Popen(
            cmd,
            cwd=APP_DIR,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW
            if sys.platform == "win32"
            else 0,
        )

        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as log:
            for line in self.process.stdout:
                signals.text.emit(line)
                log.write(line)

    def send(self, text):
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(text + "\n")
                self.process.stdin.flush()
            except Exception:
                pass

    def stop(self):
        self.stop_requested = True
        self.send("/stop")

# ---------------- GUI ----------------

class Launcher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hytale Server Console")
        self.resize(980, 580)

        self.server = None
        self.current_color = DEFAULT_TEXT_COLOR
        self.exit_after_stop = False

        self.init_ui()
        self.init_tray()

        signals.text.connect(self.append_ansi)
        signals.stopped.connect(self.on_stopped)

    # ---------- UI ----------

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.setStyleSheet("""
            QWidget { background-color: #0b1f14; color: #aaffcc; }
            QPushButton {
                background-color: #1f6f4a;
                border: 1px solid #55ffaa;
                padding: 6px 14px;
            }
            QPushButton:hover { background-color: #2fa36d; }
            QLineEdit {
                background-color: #102b1c;
                border: 1px solid #55ffaa;
                padding: 6px;
            }
            QSlider::groove:horizontal { height: 8px; background: #2a2a2a; }
            QSlider::sub-page:horizontal { background: #b266ff; }
            QSlider::handle:horizontal {
                width: 16px;
                background: #b266ff;
                border-radius: 8px;
                margin: -4px 0;
            }
        """)

        top = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop)")
        self.auto_restart = QCheckBox("Auto-restart")
        self.auto_restart.setChecked(True)

        self.status_label = QLabel("● Stopped")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")

        top.addWidget(self.start_btn)
        top.addWidget(self.stop_btn)
        top.addWidget(self.auto_restart)
        top.addStretch()
        top.addWidget(self.status_label)
        layout.addLayout(top)

        ram = QHBoxLayout()
        self.min_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_slider.setRange(1, 16)
        self.max_slider.setRange(2, 32)
        self.min_slider.setValue(4)
        self.max_slider.setValue(6)

        self.min_label = QLabel("Min RAM: 4G")
        self.max_label = QLabel("Max RAM: 6G")

        ram.addWidget(self.min_label)
        ram.addWidget(self.min_slider)
        ram.addWidget(self.max_label)
        ram.addWidget(self.max_slider)
        layout.addLayout(ram)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(
            "background-color: black; font-family: Consolas; color: #b266ff;"
        )
        layout.addWidget(self.console)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter server command...")
        layout.addWidget(self.input)

        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)
        self.input.returnPressed.connect(self.send_command)

        self.min_slider.valueChanged.connect(
            lambda v: self.min_label.setText(f"Min RAM: {v}G")
        )
        self.max_slider.valueChanged.connect(
            lambda v: self.max_label.setText(f"Max RAM: {v}G")
        )

        self.append_text("Ready.\n")

    # ---------- Tray ----------

    def init_tray(self):
        self.tray = QSystemTrayIcon(QIcon.fromTheme("applications-games"), self)
        self.tray.setToolTip("Hytale Server")

        menu = QMenu()
        menu.addAction("Show", self.showNormal)
        menu.addAction("Stop Server", self.stop_server)
        menu.addSeparator()
        menu.addAction("Exit", self.tray_exit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.showNormal()
            if r == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
        self.tray.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "Hytale Server",
            "Running in system tray",
            QSystemTrayIcon.MessageIcon.Information,
            2500,
        )

    # ---------- Output ----------

    def append_text(self, text):
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.console.setTextCursor(cursor)

    def append_ansi(self, text):
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        pos = 0
        color = self.current_color

        for m in ANSI_REGEX.finditer(text):
            cursor.insertText(text[pos:m.start()], self.format(color))
            for code in map(int, m.group(1).split(";")):
                color = DEFAULT_TEXT_COLOR if code == 0 else ANSI_COLORS.get(code, color)
            pos = m.end()

        cursor.insertText(text[pos:], self.format(color))
        self.current_color = color
        self.console.setTextCursor(cursor)

    def format(self, color):
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        return fmt

    # ---------- Server ----------

    def set_status(self, text, color):
        self.status_label.setText(f"● {text}")
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def start_server(self):
        if self.server:
            return
        self.set_status("Starting", "yellow")
        self.detect_addons()
        self.server = ServerProcess(
            self.min_slider.value(),
            self.max_slider.value(),
            self.auto_restart.isChecked(),
        )
        self.server.start()

    def stop_server(self):
        if self.server:
            self.set_status("Stopping", "#55aaff")
            self.server.stop()

    def send_command(self):
        if self.server:
            text = self.input.text().strip()
            if text:
                self.server.send(text)
                self.input.clear()

    def on_stopped(self, crashed):
        self.server = None
        self.set_status("Stopped", "red")
        if self.exit_after_stop:
            QTimer.singleShot(500, QApplication.quit)

    # ---------- Addons ----------

    def detect_addons(self):
        found = []
        for folder in ("plugins", "mods"):
            path = os.path.join(APP_DIR, folder)
            if os.path.isdir(path):
                found += [f"{folder}/{f}" for f in os.listdir(path) if f.endswith((".jar", ".zip"))]
        if found:
            self.append_text("\nDetected Addons:\n")
            for f in found:
                self.append_text(f"  - {f}\n")

    # ---------- Graceful Tray Exit ----------

    def tray_exit(self):
        if self.server:
            self.exit_after_stop = True
            self.stop_server()
        else:
            QApplication.quit()

# ---------------- MAIN ----------------

app = QApplication(sys.argv)
win = Launcher()
win.show()
sys.exit(app.exec())

