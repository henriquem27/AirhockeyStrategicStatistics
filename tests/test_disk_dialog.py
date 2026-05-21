import os
import sys
from unittest.mock import patch


# ── macOS ──────────────────────────────────────────────────────────────────────

DISKUTIL_LIST_OUTPUT = """\
/dev/disk0 (internal):
   #:                       TYPE NAME                    SIZE       IDENTIFIER
/dev/disk2 (external, physical):
   #:                       TYPE NAME                    SIZE       IDENTIFIER
"""

DISKUTIL_INFO_INTERNAL = "   Removable Media:           Fixed\n   Device Location: Internal\n"
DISKUTIL_INFO_REMOVABLE = "   Removable Media:           Removable\n   Device Location: External\n"


def test_list_physical_disks_mac_removable_flag(monkeypatch):
    monkeypatch.setattr("reference.disk_dialog.sys.platform", "darwin")

    def fake_check_output(cmd, **kwargs):
        if cmd == ["diskutil", "list"]:
            return DISKUTIL_LIST_OUTPUT
        if cmd[:2] == ["diskutil", "info"]:
            device = cmd[2]
            return DISKUTIL_INFO_REMOVABLE if "disk2" in device else DISKUTIL_INFO_INTERNAL
        raise FileNotFoundError

    monkeypatch.setattr("reference.disk_dialog.subprocess.check_output", fake_check_output)

    from reference.disk_dialog import list_physical_disks
    disks = list_physical_disks()
    by_device = {d["device"]: d for d in disks}

    assert by_device["/dev/disk2"]["removable"] is True
    assert by_device["/dev/disk0"]["removable"] is False


# ── Linux ──────────────────────────────────────────────────────────────────────

def test_list_physical_disks_linux_removable_flag(monkeypatch, tmp_path):
    monkeypatch.setattr("reference.disk_dialog.sys.platform", "linux")

    # Build fake /sys/block structure under tmp_path
    for dev_name in ("sda", "sdb"):
        dev_dir = tmp_path / dev_name
        dev_dir.mkdir()
        (dev_dir / "size").write_text("62500000\n")
        model_dir = dev_dir / "device"
        model_dir.mkdir()
        (model_dir / "model").write_text("Disk\n")
    (tmp_path / "sda" / "removable").write_text("0\n")
    (tmp_path / "sdb" / "removable").write_text("1\n")

    _real_exists = os.path.exists

    def fake_exists(p):
        return _real_exists(p.replace("/sys/block", str(tmp_path)))

    monkeypatch.setattr("reference.disk_dialog.os.path.exists", fake_exists)
    monkeypatch.setattr("reference.disk_dialog.os.listdir", lambda p: ["sda", "sdb"])

    real_open = open

    def fake_open(path, *args, **kwargs):
        new_path = path.replace("/sys/block", str(tmp_path))
        return real_open(new_path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)

    from reference.disk_dialog import list_physical_disks
    disks = list_physical_disks()
    by_device = {d["device"]: d for d in disks}

    assert by_device["/dev/sdb"]["removable"] is True
    assert by_device["/dev/sda"]["removable"] is False


# ── DiskSelectionDialog removable_only mode ────────────────────────────────────

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

_qapp = QApplication.instance() or QApplication(sys.argv)

_FAKE_DISKS = [
    {"device": "/dev/disk0", "model": "Internal SSD", "size_gb": 500.0, "removable": False},
    {"device": "/dev/disk2", "model": "SD Card 32GB", "size_gb": 32.0, "removable": True},
]


def test_removable_only_shows_only_removable_devices():
    from reference.disk_dialog import DiskSelectionDialog
    with patch("reference.disk_dialog.list_physical_disks", return_value=_FAKE_DISKS):
        dlg = DiskSelectionDialog(removable_only=True)
    items = [
        dlg.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
        for i in range(dlg.list_widget.count())
    ]
    assert "/dev/disk2" in items
    assert "/dev/disk0" not in items


def test_removable_only_false_shows_all_devices():
    from reference.disk_dialog import DiskSelectionDialog
    with patch("reference.disk_dialog.list_physical_disks", return_value=_FAKE_DISKS):
        dlg = DiskSelectionDialog(removable_only=False)
    items = [
        dlg.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
        for i in range(dlg.list_widget.count())
    ]
    assert "/dev/disk0" in items
    assert "/dev/disk2" in items


def test_removable_only_sets_correct_title():
    from reference.disk_dialog import DiskSelectionDialog
    with patch("reference.disk_dialog.list_physical_disks", return_value=_FAKE_DISKS):
        dlg = DiskSelectionDialog(removable_only=True)
    assert "SD" in dlg.windowTitle()
