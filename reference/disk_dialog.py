import os
import sys
import subprocess
import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QMessageBox, QFileDialog
)

def list_physical_disks() -> list[dict]:
    """
    Returns a list of dictionaries with keys: 'device', 'model', 'size_gb', 'removable'.
    Filters out obvious non-physical loops/rams where possible.
    """
    disks = []
    if sys.platform == "win32":
        try:
            output = subprocess.check_output(
                ["wmic", "diskdrive", "get", "DeviceID,Model,Size,MediaType", "/format:csv"],
                text=True,
            )
            for line in output.strip().splitlines():
                if not line.strip() or line.startswith("Node"):
                    continue
                parts = line.strip().split(",")
                if len(parts) < 5:
                    continue
                # CSV columns: Node, DeviceID, MediaType, Model, Size
                device = parts[1].strip()
                media_type = parts[2].strip()
                model = parts[3].strip()
                try:
                    size_bytes = int(parts[4].strip())
                    gb = size_bytes / (1024 ** 3)
                except ValueError:
                    continue
                removable = "Removable" in media_type
                disks.append({"device": device, "model": model, "size_gb": gb, "removable": removable})
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            output = subprocess.check_output(["diskutil", "list"], text=True)
            for line in output.split("\n"):
                if not line.startswith("/dev/disk"):
                    continue
                device = line.split()[0]
                removable = False
                try:
                    info = subprocess.check_output(
                        ["diskutil", "info", device], text=True, stderr=subprocess.DEVNULL
                    )
                    removable = any(
                        marker in info for marker in (
                            "Removable Media:           Yes",
                            "Removable Media:           Removable",
                        )
                    )
                except Exception:
                    pass
                disks.append({"device": device, "model": "Mac Disk", "size_gb": 0.0, "removable": removable})
        except Exception:
            pass
    else:  # Linux
        block_dir = "/sys/block"
        if os.path.exists(block_dir):
            for dev in os.listdir(block_dir):
                if dev.startswith(("loop", "ram", "sr")):
                    continue
                dev_path = f"/dev/{dev}"
                size_path = os.path.join(block_dir, dev, "size")
                model_path = os.path.join(block_dir, dev, "device/model")
                removable_path = os.path.join(block_dir, dev, "removable")
                try:
                    with open(size_path) as f:
                        size_gb = (int(f.read().strip()) * 512) / (1024 ** 3)
                    model = "Disco Desconhecido"
                    if os.path.exists(model_path):
                        with open(model_path) as f:
                            model = f.read().strip()
                    removable = False
                    if os.path.exists(removable_path):
                        with open(removable_path) as f:
                            removable = f.read().strip() == "1"
                    disks.append({"device": dev_path, "model": model, "size_gb": size_gb, "removable": removable})
                except Exception:
                    pass
    return disks


class DiskSelectionDialog(QDialog):
    """
    Shows a list of physical raw disks found on the system.
    Also provides a fallback "Abrir Imagem (.bin / .img)" button.
    """
    disk_selected = pyqtSignal(str)

    def __init__(self, parent=None, removable_only: bool = False):
        super().__init__(parent)
        self._removable_only = removable_only
        title = "Selecionar SD Card / Imagem WFS" if removable_only else "Selecionar Disco Físico WFS"
        self.setWindowTitle(title)
        self.setMinimumSize(400, 300)
        self._setup_ui()
        self._populate_list()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        lbl = QLabel("Selecione o disco USB / HD físico desejado:")
        layout.addWidget(lbl)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { font-size: 14px; padding: 5px; background: #1e1e1e; color: #eee; border-radius: 4px; }"
            "QListWidget::item { padding: 8px; border-bottom: 1px solid #333; }"
            "QListWidget::item:selected { background: #2d7dd2; color: #fff; }"
        )
        self.list_widget.itemDoubleClicked.connect(self._accept_selected)
        layout.addWidget(self.list_widget)

        warn_lbl = QLabel(
            "Nota: Em Linux/Mac, o sistema pode exigir privilégios de 'sudo' "
            "ou permissões de grupo para ler discos físicos (Permission Denied)."
        )
        warn_lbl.setStyleSheet("color: #ebcb8b; font-size: 11px;")
        warn_lbl.setWordWrap(True)
        layout.addWidget(warn_lbl)

        btn_layout = QHBoxLayout()

        fallback_label = "Abrir Arquivo Imagem (.iso / .bin / .img)..." \
            if self._removable_only else "Abrir Arquivo Imagem..."
        fallback_btn = QPushButton(fallback_label)
        fallback_btn.clicked.connect(self._fallback_image)
        btn_layout.addWidget(fallback_btn)
        
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.ok_btn = QPushButton("Abrir")
        self.ok_btn.setStyleSheet("background: #2d7dd2; color: white;")
        self.ok_btn.clicked.connect(self._accept_selected)
        btn_layout.addWidget(self.ok_btn)

        layout.addLayout(btn_layout)

    def _populate_list(self) -> None:
        disks = list_physical_disks()
        if self._removable_only:
            disks = [d for d in disks if d.get("removable", False)]
        if not disks:
            label = "Nenhum SD card / disco removível encontrado." \
                if self._removable_only else "Nenhum disco físico encontrado."
            item = QListWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.list_widget.addItem(item)
            self.ok_btn.setEnabled(False)
            return

        for d in disks:
            size_str = f"{d['size_gb']:.1f} GB" if d['size_gb'] > 0 else "Tamanho Desconhecido"
            display_text = f"{d['model']} ({size_str})\nEm: {d['device']}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, d['device'])
            self.list_widget.addItem(item)

    def _accept_selected(self) -> None:
        selected = self.list_widget.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Erro", "Selecione um disco da lista, ou use 'Abrir Arquivo'.")
            return
        device_path = selected[0].data(Qt.ItemDataRole.UserRole)
        if device_path:
            self.disk_selected.emit(device_path)
            self.accept()

    def _fallback_image(self) -> None:
        start = os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Imagem de Disco WFS", start,
            "Imagens de disco (*.iso *.bin *.img *.raw);;Todos os arquivos (*)",
        )
        if path:
            self.disk_selected.emit(path)
            self.accept()
