# ISO / SD Card Direct WFS Reading — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Extrair SD Card" button that reads WFS footage directly from a raw disk image file (`.iso`/`.bin`/`.img`/`.raw`) or a physical SD card, bypassing the existing extraction API entirely.

**Architecture:** A new `WfsDirectThread` (in `canguru/wfs_direct.py`) uses the existing `WfsReader` to scan segments and write `.h264` files into a temp dir, then signals `folder_ready` — the same interface as `ExtractionThread` so the downstream `_load_folder()` path is untouched. `DiskSelectionDialog` gains a `removable_only` mode that filters the device list to SD cards. The main window gets a new "Extrair SD Card" button wired to this thread; the existing "Extrair Disco" → API flow is not touched.

**Tech Stack:** Python 3.11+, PyQt6, `reference/wfs_reader.py` (WfsReader — existing, no changes), `tempfile`, `subprocess`, pytest + unittest.mock

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| **Create** | `canguru/wfs_direct.py` | `_make_segment_filename`, `extract_wfs_to_dir`, `WfsDirectThread` |
| **Create** | `tests/__init__.py` | make tests a Python package |
| **Create** | `tests/test_wfs_direct.py` | unit tests for extraction logic |
| **Create** | `tests/test_disk_dialog.py` | unit tests for removable detection + filter |
| **Modify** | `reference/disk_dialog.py` | add `removable` key to `list_physical_disks()`; add `removable_only` param to dialog |
| **Modify** | `canguru/widgets/main_window.py` | add `self._wfs_thread`, `self.sd_btn`, `self.sd_status_lbl`, and five handler methods |

---

## Task 1: Test infrastructure

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_wfs_direct.py` (stub only)

- [ ] **Step 1.1: Create the tests package**

```bash
mkdir tests
touch tests/__init__.py
```

- [ ] **Step 1.2: Create a stub test file to confirm pytest discovery**

Create `tests/test_wfs_direct.py`:

```python
# placeholder — real tests added in Tasks 2–4
def test_placeholder():
    pass
```

- [ ] **Step 1.3: Verify pytest runs**

```bash
cd /Users/henriquerio/code/CanguruPlayer-Pro
python -m pytest tests/ -v
```

Expected output: `1 passed`

- [ ] **Step 1.4: Commit**

```bash
git add tests/__init__.py tests/test_wfs_direct.py
git commit -m "test: add tests package scaffold"
```

---

## Task 2: `_make_segment_filename` helper

**Files:**
- Create: `canguru/wfs_direct.py` (initial stub)
- Modify: `tests/test_wfs_direct.py`

- [ ] **Step 2.1: Write the failing test**

Replace `tests/test_wfs_direct.py` contents:

```python
import datetime
import pytest


def test_make_segment_filename_single_digit_cam():
    from canguru.wfs_direct import _make_segment_filename
    t1 = datetime.datetime(2024, 1, 15, 8, 30, 0)
    t2 = datetime.datetime(2024, 1, 15, 8, 45, 0)
    assert _make_segment_filename(1, t1, t2) == \
        "CAM01_2024-01-15_08-30-00_2024-01-15_08-45-00_wfs.h264"


def test_make_segment_filename_double_digit_cam():
    from canguru.wfs_direct import _make_segment_filename
    t1 = datetime.datetime(2024, 3, 5, 23, 59, 1)
    t2 = datetime.datetime(2024, 3, 5, 23, 59, 59)
    assert _make_segment_filename(12, t1, t2) == \
        "CAM12_2024-03-05_23-59-01_2024-03-05_23-59-59_wfs.h264"
```

- [ ] **Step 2.2: Run tests — verify they fail**

```bash
python -m pytest tests/test_wfs_direct.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` (file doesn't exist yet).

- [ ] **Step 2.3: Create `canguru/wfs_direct.py` with just the helper**

```python
import os
import datetime
import tempfile

from PyQt6.QtCore import QThread, pyqtSignal

from reference.wfs_reader import WfsReader


def _make_segment_filename(
    cam_id: int,
    t_start: datetime.datetime,
    t_end: datetime.datetime,
) -> str:
    return (
        f"CAM{cam_id:02d}_{t_start:%Y-%m-%d}_{t_start:%H-%M-%S}"
        f"_{t_end:%Y-%m-%d}_{t_end:%H-%M-%S}_wfs.h264"
    )
```

- [ ] **Step 2.4: Run tests — verify they pass**

```bash
python -m pytest tests/test_wfs_direct.py -v
```

Expected: `2 passed`

- [ ] **Step 2.5: Commit**

```bash
git add canguru/wfs_direct.py tests/test_wfs_direct.py
git commit -m "feat: add _make_segment_filename helper + tests"
```

---

## Task 3: `extract_wfs_to_dir` function

**Files:**
- Modify: `canguru/wfs_direct.py`
- Modify: `tests/test_wfs_direct.py`

- [ ] **Step 3.1: Write failing tests — append to `tests/test_wfs_direct.py`**

```python
import os
import tempfile
from unittest.mock import patch, MagicMock


def _make_mock_segment(cam_id=1, hour_start=8, hour_end=9):
    seg = MagicMock()
    seg.cam_id = cam_id
    seg.t_start = datetime.datetime(2024, 1, 15, hour_start, 0, 0)
    seg.t_end = datetime.datetime(2024, 1, 15, hour_end, 0, 0)
    return seg


def _mock_reader(segments):
    r = MagicMock()
    r.__enter__ = lambda s: s
    r.__exit__ = MagicMock(return_value=False)
    r.scan_segments.return_value = segments
    r.write_segment_to_file = MagicMock()
    return r


def test_extract_wfs_writes_correct_filenames():
    from canguru.wfs_direct import extract_wfs_to_dir
    seg = _make_mock_segment(cam_id=2, hour_start=8, hour_end=9)
    reader = _mock_reader([seg])

    with patch("canguru.wfs_direct.WfsReader", return_value=reader):
        with tempfile.TemporaryDirectory() as tmp:
            paths = extract_wfs_to_dir("/fake/disk.iso", tmp)

    assert len(paths) == 1
    assert os.path.basename(paths[0]) == \
        "CAM02_2024-01-15_08-00-00_2024-01-15_09-00-00_wfs.h264"


def test_extract_wfs_calls_write_segment_for_each():
    from canguru.wfs_direct import extract_wfs_to_dir
    segs = [_make_mock_segment(hour_start=i, hour_end=i+1) for i in range(3)]
    reader = _mock_reader(segs)

    with patch("canguru.wfs_direct.WfsReader", return_value=reader):
        with tempfile.TemporaryDirectory() as tmp:
            paths = extract_wfs_to_dir("/fake/disk.iso", tmp)

    assert reader.write_segment_to_file.call_count == 3
    for path in paths:
        assert path.startswith(tmp)


def test_extract_wfs_raises_on_no_segments():
    from canguru.wfs_direct import extract_wfs_to_dir
    reader = _mock_reader([])

    with patch("canguru.wfs_direct.WfsReader", return_value=reader):
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(ValueError, match="Nenhum segmento WFS encontrado"):
                extract_wfs_to_dir("/fake/disk.iso", tmp)


def test_extract_wfs_reports_progress():
    from canguru.wfs_direct import extract_wfs_to_dir
    segs = [_make_mock_segment(hour_start=i, hour_end=i+1) for i in range(4)]
    reader = _mock_reader(segs)
    progress = []

    with patch("canguru.wfs_direct.WfsReader", return_value=reader):
        with tempfile.TemporaryDirectory() as tmp:
            extract_wfs_to_dir("/fake/disk.iso", tmp, progress_cb=progress.append)

    assert progress == [25, 50, 75, 100]
```

- [ ] **Step 3.2: Run tests — verify new ones fail**

```bash
python -m pytest tests/test_wfs_direct.py -v
```

Expected: 4 new failures (`ImportError: cannot import name 'extract_wfs_to_dir'`).

- [ ] **Step 3.3: Implement `extract_wfs_to_dir` — add to `canguru/wfs_direct.py` after `_make_segment_filename`**

```python
def extract_wfs_to_dir(
    path: str,
    out_dir: str,
    progress_cb=None,
) -> list[str]:
    with WfsReader(path) as reader:
        segments = reader.scan_segments()
        if not segments:
            raise ValueError("Nenhum segmento WFS encontrado.")
        written: list[str] = []
        total = len(segments)
        for i, seg in enumerate(segments):
            fname = _make_segment_filename(seg.cam_id, seg.t_start, seg.t_end)
            out_path = os.path.join(out_dir, fname)
            reader.write_segment_to_file(seg, out_path)
            written.append(out_path)
            if progress_cb:
                progress_cb(int((i + 1) / total * 100))
        return written
```

- [ ] **Step 3.4: Run all tests — verify all pass**

```bash
python -m pytest tests/test_wfs_direct.py -v
```

Expected: `6 passed`

- [ ] **Step 3.5: Commit**

```bash
git add canguru/wfs_direct.py tests/test_wfs_direct.py
git commit -m "feat: add extract_wfs_to_dir + tests"
```

---

## Task 4: `WfsDirectThread`

**Files:**
- Modify: `canguru/wfs_direct.py`
- Modify: `tests/test_wfs_direct.py`

- [ ] **Step 4.1: Write failing test — append to `tests/test_wfs_direct.py`**

```python
import sys
from PyQt6.QtWidgets import QApplication

_qapp = QApplication.instance() or QApplication(sys.argv)


def test_wfs_direct_thread_emits_folder_ready(tmp_path):
    from canguru.wfs_direct import WfsDirectThread
    received = {}

    thread = WfsDirectThread("/fake/disk.iso")
    thread.folder_ready.connect(lambda p: received.__setitem__("path", p))

    with patch("canguru.wfs_direct.extract_wfs_to_dir", return_value=[]):
        with patch("canguru.wfs_direct.tempfile.mkdtemp", return_value=str(tmp_path)):
            thread.run()  # call run() directly — signals fire synchronously in same thread

    assert received.get("path") == str(tmp_path)


def test_wfs_direct_thread_emits_extraction_error_on_value_error(tmp_path):
    from canguru.wfs_direct import WfsDirectThread
    received = {}

    thread = WfsDirectThread("/fake/disk.iso")
    thread.extraction_error.connect(lambda m: received.__setitem__("msg", m))

    with patch("canguru.wfs_direct.extract_wfs_to_dir",
               side_effect=ValueError("Nenhum segmento WFS encontrado.")):
        with patch("canguru.wfs_direct.tempfile.mkdtemp", return_value=str(tmp_path)):
            thread.run()

    assert "Nenhum segmento WFS encontrado" in received.get("msg", "")


def test_wfs_direct_thread_emits_extraction_error_on_os_error(tmp_path):
    from canguru.wfs_direct import WfsDirectThread
    received = {}

    thread = WfsDirectThread("/fake/disk.iso")
    thread.extraction_error.connect(lambda m: received.__setitem__("msg", m))

    with patch("canguru.wfs_direct.extract_wfs_to_dir",
               side_effect=OSError("[Errno 13] Permission denied: '/fake/disk.iso'")):
        with patch("canguru.wfs_direct.tempfile.mkdtemp", return_value=str(tmp_path)):
            thread.run()

    assert "Permission denied" in received.get("msg", "")
```

- [ ] **Step 4.2: Run tests — verify new ones fail**

```bash
python -m pytest tests/test_wfs_direct.py::test_wfs_direct_thread_emits_folder_ready -v
```

Expected: `ImportError: cannot import name 'WfsDirectThread'`

- [ ] **Step 4.3: Implement `WfsDirectThread` — append to `canguru/wfs_direct.py`**

```python
class WfsDirectThread(QThread):
    progress_updated = pyqtSignal(int)
    folder_ready = pyqtSignal(str)
    extraction_error = pyqtSignal(str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self) -> None:
        tmp_dir = tempfile.mkdtemp(prefix="canguru_wfs_")
        try:
            extract_wfs_to_dir(self._path, tmp_dir, progress_cb=self.progress_updated.emit)
            self.folder_ready.emit(tmp_dir)
        except Exception as e:
            self.extraction_error.emit(str(e))
```

- [ ] **Step 4.4: Run all tests**

```bash
python -m pytest tests/test_wfs_direct.py -v
```

Expected: `9 passed`

- [ ] **Step 4.5: Commit**

```bash
git add canguru/wfs_direct.py tests/test_wfs_direct.py
git commit -m "feat: add WfsDirectThread + tests"
```

---

## Task 5: `list_physical_disks` — add `removable` flag

**Files:**
- Modify: `reference/disk_dialog.py`
- Create: `tests/test_disk_dialog.py`

- [ ] **Step 5.1: Write failing tests — create `tests/test_disk_dialog.py`**

```python
import sys
from unittest.mock import patch, MagicMock


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

    # Fake /sys/block structure
    sda = tmp_path / "sda"
    sdb = tmp_path / "sdb"
    for dev in (sda, sdb):
        dev.mkdir()
        (dev / "size").write_text("62500000\n")
        d = dev / "device"
        d.mkdir()
        (d / "model").write_text("Disk\n")
    (sda / "removable").write_text("0\n")
    (sdb / "removable").write_text("1\n")

    monkeypatch.setattr("reference.disk_dialog.os.path.exists",
                        lambda p: p == str(tmp_path) or p.startswith(str(tmp_path)))
    monkeypatch.setattr("reference.disk_dialog.os.listdir", lambda p: ["sda", "sdb"])

    # Patch open to redirect /sys/block reads to tmp_path
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
```

- [ ] **Step 5.2: Run tests — verify they fail**

```bash
python -m pytest tests/test_disk_dialog.py -v
```

Expected: `KeyError: 'removable'` (key doesn't exist yet)

- [ ] **Step 5.3: Update `list_physical_disks()` in `reference/disk_dialog.py`**

Replace the entire `list_physical_disks` function:

```python
def list_physical_disks() -> list[dict]:
    """
    Returns list of dicts with keys: device, model, size_gb, removable.
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
```

- [ ] **Step 5.4: Run tests**

```bash
python -m pytest tests/test_disk_dialog.py -v
```

Expected: `2 passed`

- [ ] **Step 5.5: Commit**

```bash
git add reference/disk_dialog.py tests/test_disk_dialog.py
git commit -m "feat: add removable flag to list_physical_disks + tests"
```

---

## Task 6: `DiskSelectionDialog` — `removable_only` mode

**Files:**
- Modify: `reference/disk_dialog.py`
- Modify: `tests/test_disk_dialog.py`

- [ ] **Step 6.1: Write failing tests — append to `tests/test_disk_dialog.py`**

```python
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
```

- [ ] **Step 6.2: Run tests — verify new ones fail**

```bash
python -m pytest tests/test_disk_dialog.py -v
```

Expected: `TypeError: DiskSelectionDialog.__init__() got an unexpected keyword argument 'removable_only'`

- [ ] **Step 6.3: Update `DiskSelectionDialog.__init__` signature in `reference/disk_dialog.py`**

Change:
```python
def __init__(self, parent=None):
    super().__init__(parent)
    self.setWindowTitle("Selecionar Disco Físico WFS")
    self.setMinimumSize(400, 300)
    self._setup_ui()
    self._populate_list()
```

To:
```python
def __init__(self, parent=None, removable_only: bool = False):
    super().__init__(parent)
    self._removable_only = removable_only
    title = "Selecionar SD Card / Imagem WFS" if removable_only else "Selecionar Disco Físico WFS"
    self.setWindowTitle(title)
    self.setMinimumSize(400, 300)
    self._setup_ui()
    self._populate_list()
```

- [ ] **Step 6.4: Update `_populate_list` to filter when `removable_only` is set**

Change `_populate_list`:
```python
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
```

- [ ] **Step 6.5: Update the file picker label/filter for removable_only mode**

In `_setup_ui`, change the fallback button creation to respect `_removable_only`:

```python
fallback_label = "Abrir Arquivo Imagem (.iso / .bin / .img)..." \
    if self._removable_only else "Abrir Arquivo Imagem..."
fallback_btn = QPushButton(fallback_label)
fallback_btn.clicked.connect(self._fallback_image)
btn_layout.addWidget(fallback_btn)
```

And update `_fallback_image` filter to always include `.iso`:
```python
def _fallback_image(self) -> None:
    start = os.path.expanduser("~")
    path, _ = QFileDialog.getOpenFileName(
        self, "Selecionar Imagem de Disco WFS", start,
        "Imagens de disco (*.iso *.bin *.img *.raw);;Todos os arquivos (*)",
    )
    if path:
        self.disk_selected.emit(path)
        self.accept()
```

- [ ] **Step 6.6: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: all pass (`12 passed` or similar)

- [ ] **Step 6.7: Commit**

```bash
git add reference/disk_dialog.py tests/test_disk_dialog.py
git commit -m "feat: add removable_only mode to DiskSelectionDialog + tests"
```

---

## Task 7: Main window — new button and handlers

**Files:**
- Modify: `canguru/widgets/main_window.py`

No automated tests — the widget layer requires a full running window. Manual smoke test is in Task 8.

- [ ] **Step 7.1: Add `_wfs_thread` instance variable**

In `canguru/widgets/main_window.py`, find line 149:
```python
self._extraction_thread: ExtractionThread | None = None
```

Add directly after it:
```python
self._wfs_thread: "WfsDirectThread | None" = None
```

- [ ] **Step 7.2: Add `sd_btn` and `sd_status_lbl` to the sidebar**

In `_setup_ui`, find the block that ends at line 362:
```python
        self.extract_status_lbl.hide()
        sb.addWidget(self.extract_status_lbl)
```

Add immediately after:
```python
        self.sd_btn = QPushButton("Extrair SD Card")
        self.sd_btn.setStyleSheet(_btn())
        self.sd_btn.clicked.connect(self._start_wfs_direct)
        sb.addWidget(self.sd_btn)

        self.sd_status_lbl = QLabel()
        self.sd_status_lbl.setStyleSheet(f"color: {p['ACCENT']}; font-size: 11px;")
        self.sd_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sd_status_lbl.hide()
        sb.addWidget(self.sd_status_lbl)
```

- [ ] **Step 7.3: Add the five handler methods**

Add after the `_on_extraction_error` method (around line 631), keeping them grouped together:

```python
    # ── SD Card / ISO direct WFS ───────────────────────────────────────────────

    def _start_wfs_direct(self) -> None:
        if self._wfs_thread and self._wfs_thread.isRunning():
            return
        from reference.disk_dialog import DiskSelectionDialog
        dlg = DiskSelectionDialog(self, removable_only=True)
        dlg.disk_selected.connect(self._run_wfs_direct)
        dlg.exec()

    def _run_wfs_direct(self, path: str) -> None:
        from canguru.wfs_direct import WfsDirectThread
        self.sd_btn.setEnabled(False)
        self.sd_status_lbl.setText("Lendo WFS...")
        self.sd_status_lbl.show()
        self._wfs_thread = WfsDirectThread(path, parent=self)
        self._wfs_thread.progress_updated.connect(self._on_wfs_progress)
        self._wfs_thread.folder_ready.connect(self._on_wfs_folder)
        self._wfs_thread.extraction_error.connect(self._on_wfs_error)
        self._wfs_thread.start()
        logger.info("WfsDirectThread started for %s", path)

    def _on_wfs_progress(self, pct: int) -> None:
        self.sd_status_lbl.setText(f"Extraindo... {pct}%")

    def _on_wfs_folder(self, folder: str) -> None:
        self.sd_status_lbl.setText("Pronto.")
        self.sd_btn.setEnabled(True)
        self._load_folder(folder)
        logger.info("WfsDirect done, folder: %s", folder)

    def _on_wfs_error(self, message: str) -> None:
        self.sd_status_lbl.setText("Erro.")
        self.sd_btn.setEnabled(True)
        QMessageBox.critical(self, "Erro — Leitura WFS", message)
        logger.error("WfsDirect error: %s", message)
```

- [ ] **Step 7.4: Run the full test suite to confirm nothing is broken**

```bash
python -m pytest tests/ -v
```

Expected: all pass

- [ ] **Step 7.5: Commit**

```bash
git add canguru/widgets/main_window.py canguru/wfs_direct.py
git commit -m "feat: add Extrair SD Card button wired to WfsDirectThread"
```

---

## Task 8: Pre-flight ISO verification (manual)

Before using the new button with real footage, verify that `WfsReader` finds the superblock in the actual ISO. This step runs outside the normal TDD cycle — it is an inspection of a real file.

- [ ] **Step 8.1: Run the superblock probe script**

```bash
python3 - <<'EOF'
import sys
sys.path.insert(0, "/Users/henriquerio/code/CanguruPlayer-Pro")
from reference.wfs_reader import WfsReader

ISO_PATH = "/path/to/your/actual.iso"   # <-- replace with real path

try:
    with WfsReader(ISO_PATH) as r:
        print(f"block_size:       {r.block_size}")
        print(f"fragment_size:    {r.fragment_size}")
        print(f"data_area_start:  0x{r.data_area_start:X}")
        print(f"is_wfs04:         {r.is_wfs04}")
        segs = r.scan_segments()
        print(f"segments found:   {len(segs)}")
        if segs:
            s = segs[0]
            print(f"first segment:    CAM{s.cam_id} {s.t_start} → {s.t_end}")
except Exception as e:
    print(f"FAILED: {e}")
EOF
```

- [ ] **Step 8.2: Interpret the output**

  - If `segments found: N` where N > 0 → WfsReader works as-is. The button is ready to use.
  - If `FAILED: WFS superblock not found` → the ISO may use an unusual superblock offset. Open an issue to investigate further before shipping. The `_SB_CANDIDATES` list in `reference/wfs_reader.py` may need the new offset added.
  - If `segments found: 0` → superblock was found but the index is empty. Check `is_wfs04` and report for further debugging.

- [ ] **Step 8.3: If probe succeeds — launch the player and test end-to-end**

```bash
python3 player_gui.py
```

1. Click "Extrair SD Card"
2. Select the `.iso` file via "Abrir Arquivo Imagem..."
3. Confirm the progress label updates and footage loads in the timeline

- [ ] **Step 8.4: Commit probe findings to the daily log**

Append to `~/Vault/Canguru Player/2026-05-12.md`:

```markdown
## Log
- WFS probe on ISO: block_size=X fragment_size=X segments=N — [working / needs investigation]
```
