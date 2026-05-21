import datetime
import os
import tempfile
from unittest.mock import patch, MagicMock

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


# ── extract_wfs_to_dir ─────────────────────────────────────────────────────────

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


# ── WfsDirectThread ────────────────────────────────────────────────────────────

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
            thread.run()

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
