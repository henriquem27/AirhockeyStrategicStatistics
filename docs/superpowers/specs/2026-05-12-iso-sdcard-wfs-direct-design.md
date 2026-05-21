# ISO / SD Card Direct WFS Reading

**Date:** 2026-05-12
**Status:** Approved

## Problem

The player's existing "Extrair Disco" button routes through an external API server (`localhost:7474`) that handles WFS reading for the main DVR SSD. Users also have raw disk images (`.iso` files that are exact clones of XM/Xiongmai SD cards) and physical SD cards that need to play in the same player. These should be read directly — no API server required.

## Scope

- Open a `.iso` / `.bin` / `.img` / `.raw` file that is a raw sector-by-sector clone of an XM/Xiongmai SD card
- Enumerate removable physical devices (SD cards) and read them the same way
- Produce the same `CAMxx_date.h264` temp files that `scan_folder()` already knows how to load
- **Zero changes to the existing "Extrair Disco" → API flow**

## What We Know About the ISO

- 30 GB raw binary dump of an XM/Xiongmai SD card — no ISO 9660 wrapper
- Same WFS filesystem as the DVR's internal SSD, possibly with different superblock offsets
- `WfsReader` already scans a list of candidate offsets (`_SB_CANDIDATES`) for exactly this variation
- **Implementation-time step:** open the actual ISO, run `WfsReader`, confirm the superblock scan succeeds before writing any extraction logic around it

## Architecture

```
"Extrair SD Card" button
    → DiskSelectionDialog (removable_only=True)
        user picks SD card device  OR  image file (.iso/.bin/.img/.raw)
    → _run_wfs_direct(path)
    → WfsDirectThread(path)
        → WfsReader(path)              # mmap on file; _WindowsDiskBuffer on Win device
        → scan_segments()
        → write_segment_to_file() × N  # temp dir, CAMxx filename format
        → emit folder_ready(tmp_dir)
    → _load_folder(tmp_dir)            # existing path, unchanged
        → scan_folder() → player
```

The existing `ExtractionThread` → API path is untouched.

## New Components

### `canguru/wfs_direct.py` — `WfsDirectThread`

`QThread` with the same signal interface as `ExtractionThread`:

| Signal | Type | Meaning |
|--------|------|---------|
| `progress_updated` | `int` | 0–100 percent |
| `folder_ready` | `str` | path to temp dir with extracted `.h264` files |
| `extraction_error` | `str` | human-readable error message |

`run()` logic:
1. Open `WfsReader(self._path)` — catches any open/mmap errors → `extraction_error`
2. `segments = reader.scan_segments()` — if empty, emit error "Nenhum segmento WFS encontrado"
3. Create a `tempfile.mkdtemp()` output directory
4. For each segment, call `reader.write_segment_to_file(seg, out_path)` where `out_path` follows the pattern `CAM{cam_id:02d}_{t_start:%Y-%m-%d}_{t_start:%H-%M-%S}_{t_end:%Y-%m-%d}_{t_end:%H-%M-%S}_wfs.h264`
5. Emit `progress_updated(pct)` after each segment
6. Emit `folder_ready(tmp_dir)` when done

Error handling: any exception in `run()` emits `extraction_error(str(e))`.

### `DiskSelectionDialog` — `removable_only` mode

Add `removable_only: bool = False` constructor parameter.

When `True`:
- `list_physical_disks()` is enhanced to detect the `removable` flag per platform:
  - **macOS:** `diskutil info /dev/diskN` — check `Removable Media: Yes`
  - **Linux:** `/sys/block/sdX/removable == "1"`
  - **Windows:** `wmic diskdrive get MediaType` — contains `Removable`
- Only removable devices are shown in the list
- Dialog title becomes "Selecionar SD Card / Imagem WFS"
- File picker label becomes "Abrir Arquivo Imagem (.iso / .bin / .img)..."
- File filter: `"Imagens de disco (*.iso *.bin *.img *.raw);;Todos os arquivos (*)"`

### `canguru/widgets/main_window.py` — new button + handlers

New sidebar button `self.sd_btn = QPushButton("Extrair SD Card")` placed directly below the existing `self.extract_btn`.

New methods (mirror of existing extraction methods, no overlap):

```python
def _start_wfs_direct(self) -> None: ...   # opens DiskSelectionDialog(removable_only=True)
def _run_wfs_direct(self, path: str) -> None: ...  # starts WfsDirectThread
def _on_wfs_progress(self, pct: int) -> None: ...
def _on_wfs_folder(self, folder: str) -> None: ...
def _on_wfs_error(self, message: str) -> None: ...
```

A `self._wfs_thread: WfsDirectThread | None = None` instance variable tracks the thread.

## File Naming

Segments are written as:
```
CAM01_2024-01-15_08-30-00_2024-01-15_08-45-00_wfs.h264
```

This matches `FILE_PATTERN` in `canguru/constants.py` exactly, so `scan_folder()` picks them up without any changes.

## Dependencies

No new Python packages required for the raw-binary path (which covers the known ISO use case).

If a future ISO turns out to be a proper ISO 9660 disc image, `pycdlib` would be added at that point. For now, if `WfsReader` raises `ValueError` (superblock not found), `WfsDirectThread` emits a clear error message rather than silently failing.

## What Is Not Changing

- `ExtractionThread` and its API client — untouched
- `_start_extraction` / `_run_extraction` in main window — untouched
- `scan_folder()`, `scanner.py`, video widgets, player — untouched
- `WfsReader` in `reference/wfs_reader.py` — used as-is, no modifications
