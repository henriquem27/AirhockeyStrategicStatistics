"""
Direct reader for XM/Xiongmai DVR raw disk images.

Opens a raw block device or .bin image, parses the WFS index, and exposes
recorded segments as (cam_id, t_start, t_end, fragments) without copying files.
"""

import struct
import mmap
import datetime
from dataclasses import dataclass, field

from .log import logger

WFS_SUPERBLOCK_OFFSET   = 0x3000          # default; overridden by scan in _find_superblock()
WFS_SIG_OFFSET_IN_SB    = 0x14C
WFS_SIGNATURE           = 0x789ABCDE
WFS_INDEX_START         = 0x501000
WFS_DESCRIPTOR_SIZE     = 32
WFS_END_SENTINEL        = 0xFE
WFS_MAX_DESCRIPTORS     = 100_000
_SCAN_STEP              = 65_536           # 64 KiB
_SCAN_MAX               = 100 << 30       # 100 GiB
_SB_SCAN_MAX            = 32  << 20       # scan up to 32 MiB for the superblock
_SPS_START              = b'\x00\x00\x00\x01\x67'
_IDR_START              = b'\x00\x00\x00\x01\x65'

# Known superblock offsets across XM/Xiongmai DVR firmware variants.
# 0x14B0 = WFS0.4 (newer firmware); others = WFS0.3 and earlier.
_SB_CANDIDATES = [
    0x000000, 0x000200, 0x000400, 0x000800,
    0x001000, 0x001200, 0x001400, 0x001600,
    0x001800, 0x001A00, 0x001C00, 0x001E00,
    0x002000, 0x002200, 0x002400, 0x002600,
    0x002800, 0x002A00, 0x002C00, 0x002E00,
    0x003000, 0x004000, 0x005000,
    0x010000, 0x020000, 0x100000,
]


# ── Windows raw-device helpers ─────────────────────────────────────────────────

def _is_win_raw_device(path: str) -> bool:
    """Return True for paths like \\\\.\\PHYSICALDRIVE0 on Windows."""
    import sys
    if sys.platform != "win32":
        return False
    normalized = path.replace("/", "\\").upper()
    return normalized.startswith("\\\\.\\PHYSICALDRIVE") or normalized.startswith("\\\\.\\")


def _win_device_size(fh) -> int:
    """
    Query the byte size of a Windows raw block device via
    IOCTL_DISK_GET_LENGTH_INFO (0x7405C).

    Returns the device size in bytes, or 0 on failure (which lets mmap
    fall back to the regular auto-detect path).
    """
    try:
        import ctypes
        import ctypes.wintypes

        IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C
        buf = ctypes.create_string_buffer(8)
        bytes_returned = ctypes.wintypes.DWORD(0)

        import msvcrt
        handle = msvcrt.get_osfhandle(fh.fileno())

        ok = ctypes.windll.kernel32.DeviceIoControl(
            ctypes.wintypes.HANDLE(handle),
            ctypes.wintypes.DWORD(IOCTL_DISK_GET_LENGTH_INFO),
            None,
            ctypes.wintypes.DWORD(0),
            buf,
            ctypes.wintypes.DWORD(8),
            ctypes.byref(bytes_returned),
            None,
        )
        if ok:
            size = int.from_bytes(buf.raw[:8], "little")
            logger.debug("_win_device_size: DeviceIoControl returned %d bytes (%.2f GB)",
                         size, size / (1024**3))
            return size
        err = ctypes.windll.kernel32.GetLastError()
        logger.warning("_win_device_size: DeviceIoControl failed, GetLastError=%d", err)
    except Exception:
        logger.exception("_win_device_size: unexpected error")
    return 0


class _WindowsDiskBuffer:
    """
    mmap-compatible slice interface for Windows raw physical drives.

    Windows does not allow CreateFileMapping on \\\\.\\PHYSICALDRIVEn handles
    (mmap.mmap() raises WinError 193 / ERROR_BAD_EXE_FORMAT).  This class
    provides the same __getitem__ / __len__ API that WfsReader relies on,
    backed by seek() + read() with a 1 MB read-ahead cache so sequential
    index scans stay performant.
    """
    _CACHE_BLOCK = 4 << 20   # 4 MiB cache block (reduces cross-boundary hits)
    _SECTOR      = 512        # Windows raw-device minimum read granularity

    def __init__(self, fh, size: int) -> None:
        self._fh         = fh
        self._size       = size
        self._cache_off  = -1         # start offset of cached block
        self._cache_data = b""        # cached bytes

    def __len__(self) -> int:
        return self._size

    @staticmethod
    def _align_down(n: int, a: int) -> int:
        return (n // a) * a

    @staticmethod
    def _align_up(n: int, a: int) -> int:
        return ((n + a - 1) // a) * a

    def _read(self, start: int, end: int) -> bytes:
        """Return bytes [start, end) with a sector-aligned block cache.

        Windows raw devices (\\.\PHYSICALDRIVEn) require every fh.seek()
        position and every fh.read() byte count to be a multiple of the
        sector size (512 bytes). Failing this raises [Errno 22] Invalid
        argument on any cross-sector-unaligned request.
        """
        if end > self._size:
            end = self._size
        if start >= end:
            return b""

        # ── Cache hit? ────────────────────────────────────────────────────────
        cache_end = self._cache_off + len(self._cache_data)
        if self._cache_off >= 0 and start >= self._cache_off and end <= cache_end:
            return self._cache_data[start - self._cache_off : end - self._cache_off]

        # ── Compute the aligned 4 MiB block that covers start ─────────────────
        block_start = self._align_down(start, self._CACHE_BLOCK)
        block_end   = min(block_start + self._CACHE_BLOCK, self._size)

        if end <= block_end:
            # ── Single-block cache read (most common path) ─────────────────────
            # Align read length up to sector so Windows accepts it.
            read_end = min(self._align_up(block_end, self._SECTOR), self._size)
            read_len = read_end - block_start
            if read_len <= 0:
                return b""
            self._fh.seek(block_start)           # block_start is CACHE_BLOCK-aligned → sector-aligned ✓
            self._cache_data = self._fh.read(read_len)
            self._cache_off  = block_start
            return self._cache_data[start - block_start : end - block_start]

        # ── Cross-block read: align both edges to sector boundary ─────────────
        read_start = self._align_down(start, self._SECTOR)
        read_end   = min(self._align_up(end, self._SECTOR), self._size)
        self._fh.seek(read_start)
        data = self._fh.read(read_end - read_start)   # length is multiple of 512 ✓
        return data[start - read_start : end - read_start]

    def __getitem__(self, key):
        if isinstance(key, slice):
            start, stop, step = key.indices(self._size)
            data = self._read(start, stop)
            return data if step in (None, 1) else data[::step]
        if isinstance(key, int):
            if key < 0:
                key += self._size
            b = self._read(key, key + 1)
            return b[0] if b else 0
        raise TypeError(f"_WindowsDiskBuffer indices must be int or slice, not {type(key).__name__}")

    def close(self) -> None:
        self._cache_data = b""


@dataclass
class WfsFragment:
    offset: int
    size: int


@dataclass
class WfsSegment:
    cam_id: int
    t_start: datetime.datetime
    t_end: datetime.datetime
    fragments: list[WfsFragment] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(f.size for f in self.fragments)


def _decode_ts(ts: int) -> datetime.datetime | None:
    if ts in (0, 0xFFFFFFFF):
        return None
    try:
        return datetime.datetime(
            year   = ((ts >> 26) & 0x3F) + 2000,
            month  =  (ts >> 22) & 0x0F,
            day    =  (ts >> 17) & 0x1F,
            hour   =  (ts >> 12) & 0x1F,
            minute =  (ts >>  6) & 0x3F,
            second =   ts        & 0x3F,
        )
    except ValueError:
        return None


def _decode_cam(b: int) -> int:
    if b < 0x02 or (b - 0x02) % 4 != 0:
        return 0
    cam = (b - 0x02) // 4 + 1
    return cam if 1 <= cam <= 8 else 0


class WfsReader:
    """
    Usage:
        with WfsReader("/dev/sdb") as r:
            for seg in r.scan_segments():
                data = r.read_segment(seg)   # raw Annex-B H.264 bytes
    """

    def __init__(self, disk_path: str):
        logger.info("WfsReader: opening disk path: %s", disk_path)
        self._fh = open(disk_path, "rb")
        try:
            if _is_win_raw_device(disk_path):
                # Windows cannot mmap raw block device handles —
                # CreateFileMapping rejects them with WinError 193.
                # Use a seek/read buffer that exposes the same slice API.
                size = _win_device_size(self._fh)
                if size == 0:
                    raise OSError("Could not determine device size via DeviceIoControl")
                logger.debug("WfsReader: using _WindowsDiskBuffer, size=%.2f GB",
                             size / (1024 ** 3))
                self._mm = _WindowsDiskBuffer(self._fh, size)
            else:
                logger.debug("WfsReader: creating mmap...")
                self._mm = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)
                logger.debug("WfsReader: mmap OK, map size=%d bytes", len(self._mm))

            sb = self._read_superblock()
            self.block_size      = sb["block_size"]
            self.fragment_size   = sb["fragment_size_blocks"] * self.block_size
            logger.info("WfsReader: block_size=%d  fragment_size=%d",
                        self.block_size, self.fragment_size)
            self.data_area_start = self._discover_data_area()
            logger.info("WfsReader: data_area_start=0x%X", self.data_area_start)
        except Exception:
            logger.exception("WfsReader: failed to initialise disk %s", disk_path)
            self._fh.close()
            raise

    def close(self) -> None:
        self._mm.close()
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------------------
    def _find_superblock(self) -> int:
        """
        Locate the WFS superblock by searching for its signature bytes
        (0x789ABCDE at offset WFS_SIG_OFFSET_IN_SB within the superblock).

        Strategy:
          1. Byte-search the first 128 KiB (catches any alignment, ~0 ms).
          2. Full-disk scan as last resort.
        """
        sig_bytes = struct.pack("<I", WFS_SIGNATURE)
        disk_size  = len(self._mm)
        header_end = min(disk_size, 128 << 10)   # 128 KiB

        # ── Fast path: search first 128 KiB for the raw signature bytes ──────
        header = self._mm[0: header_end]
        idx = header.find(sig_bytes) if isinstance(header, (bytes, bytearray)) else \
              bytes(header).find(sig_bytes)
        if idx != -1:
            sb_off = idx - WFS_SIG_OFFSET_IN_SB
            if sb_off >= 0:
                logger.info("WfsReader: superblock found at 0x%X (128KiB scan)", sb_off)
                return sb_off

        # ── Slow path: full-disk scan ──────────────────────────────────
        logger.warning("WfsReader: signature not in first 128 KiB — full-disk scan")
        scan_end = min(disk_size - WFS_SIG_OFFSET_IN_SB - 4, _SB_SCAN_MAX)
        pos = 0
        while pos < scan_end:
            chunk = self._mm[pos: pos + _SCAN_STEP]
            chunk_b = bytes(chunk) if not isinstance(chunk, (bytes, bytearray)) else chunk
            idx = chunk_b.find(sig_bytes)
            if idx != -1:
                sb_off = pos + idx - WFS_SIG_OFFSET_IN_SB
                if sb_off >= 0:
                    logger.info("WfsReader: superblock found at 0x%X (full scan)", sb_off)
                    return sb_off
            pos += _SCAN_STEP - len(sig_bytes)

        raise ValueError(
            f"WFS superblock not found in first {_SB_SCAN_MAX >> 20} MiB of disk.\n"
            "This may not be a WFS-formatted XM/Xiongmai DVR drive."
        )

    def _read_superblock(self) -> dict:
        sb_off = self._find_superblock()
        self._superblock_offset = sb_off
        sb = self._mm[sb_off: sb_off + 512]

        # Check for WFS0.4 magic (version string at disk offset 0)
        magic = bytes(self._mm[0:8])
        self.is_wfs04 = magic.startswith(b'WFS0.')
        if self.is_wfs04:
            logger.info("WfsReader: WFS0.4 format detected (magic=%s)", magic[:6])
        else:
            logger.info("WfsReader: WFS0.3 format (no WFS magic at offset 0)")

        # Try standard offsets first, then alternates used by WFS0.4
        block_size = fragment_size_blocks = 0
        for bsz_off, fblk_off in [(0x2C, 0x30), (0x34, 0x38), (0x28, 0x2C), (0x24, 0x28)]:
            bsz  = struct.unpack_from("<I", sb, bsz_off)[0]
            fblk = struct.unpack_from("<I", sb, fblk_off)[0]
            if 0 < bsz <= 65536 and 0 < fblk <= 65536:
                block_size, fragment_size_blocks = bsz, fblk
                logger.debug("WfsReader: block_size=%d frag_blocks=%d (offsets +0x%X/+0x%X)",
                             bsz, fblk, bsz_off, fblk_off)
                break

        if block_size == 0 or fragment_size_blocks == 0:
            logger.warning("WfsReader: could not find valid block_size in superblock — "
                           "using WFS0.4 defaults (512, 256)")
            block_size           = 512
            fragment_size_blocks = 256

        return {"block_size": block_size, "fragment_size_blocks": fragment_size_blocks}

    def _discover_data_area(self) -> int:
        disk_size = len(self._mm)
        logger.debug("WfsReader: scanning for data area, disk_size=%d bytes (%.2f GB)",
                     disk_size, disk_size / (1024**3))
        pos = WFS_INDEX_START
        while pos < min(disk_size, _SCAN_MAX):
            chunk = self._mm[pos: pos + _SCAN_STEP + len(_SPS_START)]
            idx = chunk.find(_SPS_START)
            if idx != -1:
                sps_abs = pos + idx
                window = self._mm[sps_abs: min(sps_abs + 2 * 1024 * 1024, disk_size)]
                if _IDR_START in window:
                    # rewind over zero padding and align to 4 KiB
                    rewind = sps_abs
                    stop = max(0, sps_abs - 4096)
                    while rewind > stop and self._mm[rewind - 1] == 0:
                        rewind -= 1
                    result = rewind & ~0xFFF
                    logger.debug("WfsReader: data area found at 0x%X (scanned %d bytes)",
                                 result, pos - WFS_INDEX_START)
                    return result
            pos += _SCAN_STEP
        logger.error("WfsReader: could not locate H.264 data area after scanning %d bytes",
                     min(disk_size, _SCAN_MAX) - WFS_INDEX_START)
        raise RuntimeError("Could not locate H.264 data area — is this a WFS disk?")

    # ------------------------------------------------------------------
    def scan_segments(
        self,
        cam_filter: int | None = None,
        date_filter: datetime.date | None = None,
    ) -> list[WfsSegment]:
        """
        Return all segments, optionally filtered by camera ID and/or date.

        WFS0.4 descriptor layout (32 bytes):
          [1]     tipo       0x01/0x02/0x03=valid, 0xFE=end
          [8:12]  next_ptr   block-address of NEXT fragment (0=last)
          [12:16] ts_start
          [16:20] ts_end
          [22:24] last_frag_blocks
          [24:28] offset_main  block-address of THIS fragment data
          [31]    cam_byte

        Fragments are chained: offset_main -> next_ptr -> next_ptr -> 0.
        """
        logger.debug("WfsReader: scan_segments(cam_filter=%s, date_filter=%s)",
                     cam_filter, date_filter)

        # WFS0.3: fragments are stored sequentially by descriptor index i.
        # WFS0.4: offset_main is the actual block address in the data area.
        use_offset_main = self.is_wfs04

        # Pass 1: collect all valid descriptors
        # Key = offset_main (WFS0.4) or i (WFS0.3) — whichever is the block address.
        all_frags: dict[int, dict] = {}
        pos = WFS_INDEX_START
        for i in range(WFS_MAX_DESCRIPTORS):
            rec = self._mm[pos: pos + WFS_DESCRIPTOR_SIZE]
            pos += WFS_DESCRIPTOR_SIZE
            if len(rec) < WFS_DESCRIPTOR_SIZE:
                break
            tipo = rec[1]
            if tipo == WFS_END_SENTINEL:
                break
            if tipo not in (0x01, 0x02, 0x03):
                continue

            next_ptr, ts_start, ts_end = struct.unpack_from("<III", rec, 8)
            last_frag_blocks           = struct.unpack_from("<H",   rec, 0x16)[0]
            offset_main                = struct.unpack_from("<I",   rec, 0x18)[0]
            cam_byte                   = rec[0x1F]

            cam_id  = _decode_cam(cam_byte)
            t_start = _decode_ts(ts_start)
            t_end   = _decode_ts(ts_end)

            if cam_id == 0 or t_start is None or t_end is None:
                continue
            if offset_main == 0:
                continue

            is_last     = (next_ptr == 0)
            size        = last_frag_blocks * self.block_size if is_last else self.fragment_size
            block_addr  = offset_main if use_offset_main else i
            data_offset = self.data_area_start + block_addr * self.fragment_size

            all_frags[block_addr] = {
                "next":    next_ptr if use_offset_main else 0,
                "t_start": t_start,
                "t_end":   t_end,
                "cam_id":  cam_id,
                "offset":  data_offset,
                "size":    size,
                "seq":     i,
                "group":   offset_main,   # grouping key for WFS0.3
            }

        # Pass 2: chain roots = blocks not referenced as next_ptr by anyone
        pointed_at = {v["next"] for v in all_frags.values() if v["next"] != 0}
        roots = [b for b in all_frags if b not in pointed_at]

        # Pass 3: build segments
        segments = []
        if use_offset_main:
            # WFS0.4: walk next_ptr chains
            visited: set[int] = set()
            for root in roots:
                chain, blk = [], root
                for _ in range(WFS_MAX_DESCRIPTORS):
                    if blk == 0 or blk not in all_frags or blk in visited:
                        break
                    visited.add(blk)
                    chain.append(all_frags[blk])
                    blk = all_frags[blk]["next"]

                if not chain:
                    continue

                cam_id  = chain[0]["cam_id"]
                t_start = chain[0]["t_start"]
                t_end   = chain[-1]["t_end"]

                if cam_filter  is not None and cam_id        != cam_filter:
                    continue
                if date_filter is not None and t_start.date() != date_filter:
                    continue

                segments.append(WfsSegment(
                    cam_id    = cam_id,
                    t_start   = t_start,
                    t_end     = t_end,
                    fragments = [WfsFragment(offset=fd["offset"], size=fd["size"])
                                 for fd in chain],
                ))
        else:
            # WFS0.3: group by (offset_main, cam_id), order by descriptor index i
            groups: dict[tuple, list] = {}
            for fd in all_frags.values():
                key = (fd["group"], fd["cam_id"])
                groups.setdefault(key, []).append(fd)

            for (_, cam_id), frags in groups.items():
                frags.sort(key=lambda fd: fd["seq"])
                t_start = frags[0]["t_start"]
                t_end   = frags[-1]["t_end"]

                if t_start > t_end:
                    continue
                if cam_filter  is not None and cam_id        != cam_filter:
                    continue
                if date_filter is not None and t_start.date() != date_filter:
                    continue

                segments.append(WfsSegment(
                    cam_id    = cam_id,
                    t_start   = t_start,
                    t_end     = t_end,
                    fragments = [WfsFragment(offset=fd["offset"], size=fd["size"])
                                 for fd in frags],
                ))

        logger.info("WfsReader: scan_segments found %d segments", len(segments))
        return sorted(segments, key=lambda s: (s.t_start, s.cam_id))


    def read_fragment(self, frag: WfsFragment) -> bytes:
        return bytes(self._mm[frag.offset: frag.offset + frag.size])

    def read_segment(self, seg: WfsSegment) -> bytes:
        """Return raw Annex-B H.264 bytes for the entire segment (all fragments)."""
        return b"".join(self.read_fragment(f) for f in seg.fragments)

    def write_segment_to_file(self, seg: WfsSegment, out_path: str) -> None:
        """Write raw H.264 to a file — can be opened directly by cv2.VideoCapture."""
        with open(out_path, "wb") as fh:
            for frag in seg.fragments:
                fh.write(self.read_fragment(frag))

    def available_dates(self) -> list[datetime.date]:
        seen: set[datetime.date] = set()
        pos = WFS_INDEX_START
        for _ in range(WFS_MAX_DESCRIPTORS):
            rec = self._mm[pos: pos + WFS_DESCRIPTOR_SIZE]
            pos += WFS_DESCRIPTOR_SIZE
            if len(rec) < WFS_DESCRIPTOR_SIZE:
                break
            tipo = rec[1]
            if tipo == WFS_END_SENTINEL:
                break
            if tipo not in (0x01, 0x02, 0x03):
                continue
            ts_start = struct.unpack_from("<I", rec, 0x0C)[0]
            t = _decode_ts(ts_start)
            if t:
                seen.add(t.date())
        return sorted(seen)
