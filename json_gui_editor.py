import os
import sys
import json
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt

# ---------------------- Paths ----------------------
script_dir = os.path.dirname(os.path.abspath(__file__))

# HytaleLauncher.exe in the same folder as the script
launcher_path = os.path.join(script_dir, "HytaleLauncher.exe")
if not os.path.exists(launcher_path):
    raise FileNotFoundError(f"HytaleLauncher.exe not found: {launcher_path}")

# AvatarPresets.json in the game folder
avatar_json_path = os.path.join(
    script_dir,
    "install", "release", "package", "game", "latest", "Client", "Data", "Game", "AvatarPresets.json"
)
if not os.path.exists(avatar_json_path):
    raise FileNotFoundError(f"AvatarPresets.json not found: {avatar_json_path}")

# AllowedValues_Full.json in the same folder as the script
allowed_values_path = os.path.join(script_dir, "AllowedValues.json")
if not os.path.exists(allowed_values_path):
    raise FileNotFoundError(f"AllowedValues.json not found: {allowed_values_path}")

# ---------------------- Load JSON ----------------------
with open(allowed_values_path, "r", encoding="utf-8") as f:
    allowed_values = json.load(f)

with open(avatar_json_path, "r", encoding="utf-8") as f:
    avatar_data = json.load(f)

# ---------------------- PyQt6 GUI ----------------------
class AvatarEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Avatar Presets Editor")
        self.setMinimumWidth(500)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.entries = {}
        for key, options in allowed_values.items():
            if key in avatar_data:
                self.add_entry(key, options, avatar_data[key])
        
        # Save button
        save_btn = QPushButton("Save & Launch Hytale")
        save_btn.clicked.connect(self.save_and_launch)
        self.layout.addWidget(save_btn)

    def add_entry(self, key, options, current_value):
        h_layout = QHBoxLayout()
        label = QLabel(key)
        label.setFixedWidth(150)
        combo = QComboBox()
        combo.addItems(sorted(options))
        if current_value in options:
            combo.setCurrentText(current_value)
        h_layout.addWidget(label)
        h_layout.addWidget(combo)
        self.layout.addLayout(h_layout)
        self.entries[key] = combo

    def save_and_launch(self):
        # Update avatar_data
        for key, combo in self.entries.items():
            avatar_data[key] = combo.currentText()
        
        # Save JSON
        try:
            with open(avatar_json_path, "w", encoding="utf-8") as f:
                json.dump(avatar_data, f, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save JSON:\n{e}")
            return

        # Kill HytaleClient.exe
        subprocess.run(["taskkill", "/F", "/IM", "HytaleClient.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Launch HytaleLauncher.exe
        try:
            subprocess.Popen([launcher_path], cwd=script_dir)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to launch HytaleLauncher.exe:\n{e}")
            return

        QMessageBox.information(self, "Done", "Saved and launched Hytale!")
        self.close()

# ---------------------- Run App ----------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = AvatarEditor()
    editor.show()
    sys.exit(app.exec())
