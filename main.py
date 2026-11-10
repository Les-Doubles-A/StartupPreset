#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StartupPreset Manager
======================
Application de bureau permettant de definir plusieurs "presets" nommes,
chacun composé d'applications et de sites web a lancer automatiquement
selon le jour de la semaine, avec integration optionnelle au demarrage
de Windows.

Stack : Python 3.10+ / PySide6

Fonctionnement general :
- En mode normal (double-clic, `python main.py`) -> ouvre l'interface graphique.
- En mode `--autostart` (utilise par le registre Windows au demarrage de
  session) -> ne lance PAS l'interface, parcourt TOUS les presets et lance
  ceux dont le jour actuel correspond, puis se ferme.
"""

import sys
import os
import json
import subprocess
import webbrowser
import datetime
from pathlib import Path

# winreg n'existe que sous Windows. On l'importe de facon protegee pour
# pouvoir au moins ouvrir/tester le code sur d'autres OS (sans la fonction
# "demarrage Windows").
try:
    import winreg
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QLineEdit, QLabel,
    QCheckBox, QFileDialog, QMessageBox, QGroupBox, QGridLayout,
    QInputDialog
)
from PySide6.QtCore import Qt

# ---------------------------------------------------------------------------
# Constantes et configuration
# ---------------------------------------------------------------------------

APP_NAME = "StartupPresetManager"          # Nom utilise dans le registre Windows
CONFIG_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "StartupPreset"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Jours de la semaine dans l'ordre de datetime.weekday() (0 = lundi)
DAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

def _empty_preset(name: str) -> dict:
    return {"name": name, "apps": [], "urls": [], "days": []}

DEFAULT_CONFIG = {
    "presets": [],
    "autostart": False
}


# ---------------------------------------------------------------------------
# Gestion de la configuration (lecture / ecriture JSON)
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """
    Charge le fichier de config JSON. Gere aussi la migration automatique
    depuis l'ancien format (un seul preset implicite, sans nom) vers le
    nouveau format a plusieurs presets nommes.
    """
    if not CONFIG_FILE.exists():
        config = dict(DEFAULT_CONFIG)
        config["presets"] = [_empty_preset("Preset 1")]
        return config

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        data = {}

    # --- Migration depuis l'ancien format (apps/urls/days a la racine) ---
    if "presets" not in data and ("apps" in data or "urls" in data or "days" in data):
        migrated = {
            "name": "Preset 1",
            "apps": data.get("apps", []),
            "urls": data.get("urls", []),
            "days": data.get("days", []),
        }
        data = {
            "presets": [migrated],
            "autostart": data.get("autostart", False),
        }

    merged = dict(DEFAULT_CONFIG)
    merged.update(data)

    if not merged.get("presets"):
        merged["presets"] = [_empty_preset("Preset 1")]

    return merged


def save_config(data: dict) -> None:
    """Sauvegarde la configuration sur le disque (cree le dossier si besoin)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Logique d'automatisation : verification du jour + lancement
# ---------------------------------------------------------------------------

def is_today_selected(days_selected: list) -> bool:
    """Renvoie True si le jour actuel fait partie des jours coches."""
    weekday_index = datetime.datetime.now().weekday()  # 0 = lundi ... 6 = dimanche
    today_name = DAYS_FR[weekday_index]
    return today_name in days_selected


def launch_all(apps: list, urls: list) -> list:
    """
    Lance les applications et ouvre les URL activees (enabled=True) pour
    UN preset donne. Renvoie une liste de messages d'erreur eventuels.
    """
    errors = []

    for app in apps:
        if not app.get("enabled", True):
            continue
        path = app.get("path", "")
        try:
            subprocess.Popen([path], shell=False)
        except Exception as e:
            errors.append(f"Impossible de lancer '{path}' : {e}")

    for url_entry in urls:
        if not url_entry.get("enabled", True):
            continue
        url = url_entry.get("url", "")
        try:
            webbrowser.open(url)
        except Exception as e:
            errors.append(f"Impossible d'ouvrir '{url}' : {e}")

    return errors


def run_autostart_check():
    """
    Mode silencieux appele au demarrage de Windows (argument --autostart).
    Ne montre AUCUNE fenetre : parcourt TOUS les presets, lance ceux dont
    le jour correspond, puis quitte.
    """
    config = load_config()
    for preset in config.get("presets", []):
        if is_today_selected(preset.get("days", [])):
            launch_all(preset.get("apps", []), preset.get("urls", []))
    sys.exit(0)


# ---------------------------------------------------------------------------
# Integration au demarrage de Windows (cle de registre HKCU\...\Run)
# ---------------------------------------------------------------------------

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _build_startup_command() -> str:
    if getattr(sys, "frozen", False):
        exe_path = sys.executable
        return f'"{exe_path}" --autostart'
    else:
        python_dir = Path(sys.executable).parent
        pythonw = python_dir / "pythonw.exe"
        interpreter = str(pythonw) if pythonw.exists() else sys.executable
        script_path = os.path.abspath(__file__)
        return f'"{interpreter}" "{script_path}" --autostart'


def set_windows_startup(enable: bool) -> None:
    if not IS_WINDOWS:
        raise RuntimeError("Le demarrage automatique Windows n'est disponible que sous Windows.")

    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_ALL_ACCESS)
    try:
        if enable:
            command = _build_startup_command()
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)


def is_windows_startup_enabled() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Interface graphique
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("StartupPreset Manager")
        self.resize(680, 760)

        self.config = load_config()
        self.presets = self.config.get("presets", [_empty_preset("Preset 1")])
        self.current_index = 0

        self._build_ui()
        self._populate_preset_list()
        self.preset_list_widget.setCurrentRow(0)  # declenche le chargement du 1er preset
        self.startup_checkbox.setChecked(is_windows_startup_enabled())

    # -- Construction de l'UI -------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(14)

        # --- Section Presets ---
        presets_group = QGroupBox("Presets")
        presets_layout = QVBoxLayout(presets_group)

        self.preset_list_widget = QListWidget()
        self.preset_list_widget.currentRowChanged.connect(self.on_preset_selected)
        presets_layout.addWidget(self.preset_list_widget)

        presets_btn_row = QHBoxLayout()
        btn_new_preset = QPushButton("Nouveau preset")
        btn_new_preset.clicked.connect(self.on_new_preset)
        btn_rename_preset = QPushButton("Renommer")
        btn_rename_preset.clicked.connect(self.on_rename_preset)
        btn_delete_preset = QPushButton("Supprimer")
        btn_delete_preset.clicked.connect(self.on_delete_preset)
        presets_btn_row.addWidget(btn_new_preset)
        presets_btn_row.addWidget(btn_rename_preset)
        presets_btn_row.addWidget(btn_delete_preset)
        presets_layout.addLayout(presets_btn_row)

        main_layout.addWidget(presets_group)

        # --- Section Applications ---
        apps_group = QGroupBox("Applications a lancer (preset selectionne)")
        apps_layout = QVBoxLayout(apps_group)

        self.apps_list = QListWidget()
        apps_layout.addWidget(self.apps_list)

        apps_btn_row = QHBoxLayout()
        btn_add_app = QPushButton("Parcourir... (.exe)")
        btn_add_app.clicked.connect(self.on_add_app)
        btn_remove_app = QPushButton("Supprimer la selection")
        btn_remove_app.clicked.connect(self.on_remove_app)
        apps_btn_row.addWidget(btn_add_app)
        apps_btn_row.addWidget(btn_remove_app)
        apps_layout.addLayout(apps_btn_row)

        main_layout.addWidget(apps_group)

        # --- Section Sites web ---
        urls_group = QGroupBox("Sites web a ouvrir (preset selectionne)")
        urls_layout = QVBoxLayout(urls_group)

        self.urls_list = QListWidget()
        urls_layout.addWidget(self.urls_list)

        url_input_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://exemple.com")
        self.url_input.returnPressed.connect(self.on_add_url)
        btn_add_url = QPushButton("Ajouter")
        btn_add_url.clicked.connect(self.on_add_url)
        url_input_row.addWidget(self.url_input)
        url_input_row.addWidget(btn_add_url)
        urls_layout.addLayout(url_input_row)

        btn_remove_url = QPushButton("Supprimer la selection")
        btn_remove_url.clicked.connect(self.on_remove_url)
        urls_layout.addWidget(btn_remove_url)

        main_layout.addWidget(urls_group)

        # --- Section Jours de la semaine ---
        days_group = QGroupBox("Jours de declenchement (preset selectionne)")
        days_layout = QGridLayout(days_group)
        self.day_checkboxes = {}
        for i, day in enumerate(DAYS_FR):
            cb = QCheckBox(day)
            self.day_checkboxes[day] = cb
            days_layout.addWidget(cb, i // 4, i % 4)
        main_layout.addWidget(days_group)

        # --- Section Demarrage Windows (globale, pas par preset) ---
        startup_group = QGroupBox("Demarrage automatique (global)")
        startup_layout = QHBoxLayout(startup_group)
        self.startup_checkbox = QCheckBox("Lancer cette application au demarrage de Windows")
        if not IS_WINDOWS:
            self.startup_checkbox.setEnabled(False)
            self.startup_checkbox.setText(
                "Lancer au demarrage de Windows (indisponible hors Windows)"
            )
        startup_layout.addWidget(self.startup_checkbox)
        main_layout.addWidget(startup_group)

        # --- Boutons principaux ---
        actions_row = QHBoxLayout()
        btn_test = QPushButton("Tester le lancement (preset selectionne)")
        btn_test.clicked.connect(self.on_test_launch)
        btn_save = QPushButton("Sauvegarder tous les presets")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.on_save)
        actions_row.addWidget(btn_test)
        actions_row.addWidget(btn_save)
        main_layout.addLayout(actions_row)

        # --- Barre de statut ---
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.status_label)

    # -- Gestion de la liste de presets -----------------------------------------

    def _populate_preset_list(self):
        self.preset_list_widget.blockSignals(True)
        self.preset_list_widget.clear()
        for preset in self.presets:
            self.preset_list_widget.addItem(preset["name"])
        self.preset_list_widget.blockSignals(False)

    def _sync_ui_into_preset(self, index: int):
        """Relit l'etat actuel de l'UI (apps/urls/jours) et le stocke dans self.presets[index]."""
        if index < 0 or index >= len(self.presets):
            return
        apps = []
        for i in range(self.apps_list.count()):
            item = self.apps_list.item(i)
            apps.append({"path": item.text(), "enabled": item.checkState() == Qt.Checked})

        urls = []
        for i in range(self.urls_list.count()):
            item = self.urls_list.item(i)
            urls.append({"url": item.text(), "enabled": item.checkState() == Qt.Checked})

        days = [day for day, cb in self.day_checkboxes.items() if cb.isChecked()]

        self.presets[index]["apps"] = apps
        self.presets[index]["urls"] = urls
        self.presets[index]["days"] = days

    def _load_preset_into_ui(self, index: int):
        """Vide et repeuple les listes/checkboxes avec le contenu de self.presets[index]."""
        self.apps_list.clear()
        self.urls_list.clear()
        for cb in self.day_checkboxes.values():
            cb.setChecked(False)

        if index < 0 or index >= len(self.presets):
            return

        preset = self.presets[index]
        for app in preset.get("apps", []):
            self._add_app_item(app["path"], app.get("enabled", True))
        for url_entry in preset.get("urls", []):
            self._add_url_item(url_entry["url"], url_entry.get("enabled", True))
        for day in preset.get("days", []):
            if day in self.day_checkboxes:
                self.day_checkboxes[day].setChecked(True)

    def on_preset_selected(self, row: int):
        if row < 0:
            return
        # On sauvegarde d'abord l'edition en cours (en memoire) avant de changer
        # de preset, pour ne pas perdre les modifications non enregistrees.
        if 0 <= self.current_index < len(self.presets) and self.current_index != row:
            self._sync_ui_into_preset(self.current_index)
        self.current_index = row
        self._load_preset_into_ui(row)
        self.status_label.setText(f"Preset selectionne : {self.presets[row]['name']}")

    def on_new_preset(self):
        name, ok = QInputDialog.getText(self, "Nouveau preset", "Nom du preset :")
        if not ok or not name.strip():
            return
        # Sauvegarde l'edition en cours avant de creer le nouveau preset.
        self._sync_ui_into_preset(self.current_index)
        self.presets.append(_empty_preset(name.strip()))
        self._populate_preset_list()
        self.preset_list_widget.setCurrentRow(len(self.presets) - 1)

    def on_rename_preset(self):
        if not (0 <= self.current_index < len(self.presets)):
            return
        current_name = self.presets[self.current_index]["name"]
        name, ok = QInputDialog.getText(self, "Renommer le preset", "Nouveau nom :", text=current_name)
        if not ok or not name.strip():
            return
        self.presets[self.current_index]["name"] = name.strip()
        self._populate_preset_list()
        self.preset_list_widget.setCurrentRow(self.current_index)

    def on_delete_preset(self):
        if not (0 <= self.current_index < len(self.presets)):
            return
        if len(self.presets) <= 1:
            QMessageBox.warning(self, "Suppression impossible",
                                 "Il doit rester au moins un preset.")
            return
        name = self.presets[self.current_index]["name"]
        confirm = QMessageBox.question(
            self, "Confirmer la suppression",
            f"Supprimer le preset « {name} » ?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        del self.presets[self.current_index]
        self.current_index = max(0, self.current_index - 1)
        self._populate_preset_list()
        self.preset_list_widget.setCurrentRow(self.current_index)

    # -- Ajout/suppression d'items dans les listes -------------------------------

    def _add_app_item(self, path: str, enabled: bool = True):
        item = QListWidgetItem(path)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
        self.apps_list.addItem(item)

    def _add_url_item(self, url: str, enabled: bool = True):
        item = QListWidgetItem(url)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
        self.urls_list.addItem(item)

    def on_add_app(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selectionner un executable", "", "Executables (*.exe);;Tous les fichiers (*)"
        )
        if path:
            self._add_app_item(path, True)
            self.status_label.setText(f"Application ajoutee : {path}")

    def on_remove_app(self):
        for item in self.apps_list.selectedItems():
            self.apps_list.takeItem(self.apps_list.row(item))

    def on_add_url(self):
        url = self.url_input.text().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self._add_url_item(url, True)
        self.url_input.clear()

    def on_remove_url(self):
        for item in self.urls_list.selectedItems():
            self.urls_list.takeItem(self.urls_list.row(item))

    # -- Sauvegarde / test --------------------------------------------------------

    def on_save(self):
        # On synchronise le preset actuellement affiche avant d'ecrire sur le disque.
        self._sync_ui_into_preset(self.current_index)

        data = {
            "presets": self.presets,
            "autostart": self.startup_checkbox.isChecked()
        }
        save_config(data)
        self.config = data

        if IS_WINDOWS:
            try:
                set_windows_startup(data["autostart"])
            except Exception as e:
                QMessageBox.warning(self, "Demarrage Windows", f"Erreur registre : {e}")

        self.status_label.setText("Tous les presets ont ete sauvegardes.")
        QMessageBox.information(self, "Sauvegarde", "Les presets ont ete sauvegardes avec succes.")

    def on_test_launch(self):
        # Teste uniquement le preset actuellement affiche a l'ecran,
        # sans tenir compte du jour actuel.
        apps = []
        for i in range(self.apps_list.count()):
            item = self.apps_list.item(i)
            apps.append({"path": item.text(), "enabled": item.checkState() == Qt.Checked})

        urls = []
        for i in range(self.urls_list.count()):
            item = self.urls_list.item(i)
            urls.append({"url": item.text(), "enabled": item.checkState() == Qt.Checked})

        errors = launch_all(apps, urls)
        if errors:
            QMessageBox.warning(self, "Erreurs de lancement", "\n".join(errors))
        else:
            self.status_label.setText("Lancement de test effectue.")


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

def main():
    if "--autostart" in sys.argv:
        run_autostart_check()
        return

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
