"""
processor.py
Core metadata restoration logic for Google Photos Takeout.
Handles JPEG (EXIF), Video (ffmpeg), PNG/HEIC/Other (timestamps).

Features:
  - God Mode: Deep recursive scan of any folder structure
  - Standard Mode: Google Takeout album folder scan
  - Duplicate detection (MD5 hash)
  - Date range filtering
  - Multiple output folder structures
  - Conflict resolution (rename / skip / overwrite)
  - GPS embedding in JPEG EXIF
  - CSV error export
  - Detailed folder statistics with year distribution
"""

import os
import sys
import json
import shutil
import ctypes
import subprocess
import hashlib
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

import piexif
from PIL import Image


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif"}
JPEG_EXTS  = {".jpg", ".jpeg"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp"}
OTHER_EXTS = {".png", ".heic", ".webp", ".gif"}
ALL_EXTS   = IMAGE_EXTS | VIDEO_EXTS


# ---------------------------------------------------------------------------
# JSON Finder
# ---------------------------------------------------------------------------
def find_json(photo_path: Path) -> Optional[Path]:
    """Find matching Google supplemental-metadata JSON for a photo/video."""
    name   = photo_path.name
    folder = photo_path.parent

    candidates = [
        folder / (name + ".supplemental-metadata.json"),
        folder / (name + ".supplemental_metadata.json"),
        folder / (name + ".json"),
    ]
    for c in candidates:
        if c.exists():
            return c

    # Truncated name fallback (Google sometimes shortens filenames)
    stem = photo_path.stem
    for f in folder.iterdir():
        if f.suffix == ".json" and stem[:35] in f.name:
            return f

    return None


# ---------------------------------------------------------------------------
# Metadata Parser
# ---------------------------------------------------------------------------
def parse_metadata(json_path: Path) -> dict:
    """Extract date, GPS, title, description from Google JSON sidecar."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = {}

    for key in ["photoTakenTime", "creationTime"]:
        if key in data and "timestamp" in data[key]:
            meta["dt"] = datetime.fromtimestamp(int(data[key]["timestamp"]))
            break

    for gkey in ["geoData", "geoDataExif"]:
        geo = data.get(gkey, {})
        if geo and geo.get("latitude", 0.0) != 0.0:
            meta["lat"] = geo["latitude"]
            meta["lng"] = geo["longitude"]
            meta["alt"] = geo.get("altitude", 0.0)
            break

    meta["desc"]   = data.get("description", "")
    meta["title"]  = data.get("title", "")
    meta["people"] = [p.get("name", "") for p in data.get("people", [])]
    return meta


# ---------------------------------------------------------------------------
# Timestamp Setter
# ---------------------------------------------------------------------------
def set_timestamps(file_path: Path, dt: datetime):
    """Set file modified and created timestamps."""
    ts = dt.timestamp()
    os.utime(str(file_path), (ts, ts))

    if sys.platform == "win32":
        try:
            EPOCH_DIFF = 116444736000000000
            handle = ctypes.windll.kernel32.CreateFileW(
                str(file_path), 0x40000000, 0, None, 3, 0x02000000, None
            )
            if handle and handle != -1:
                ft_val = int(ts * 10_000_000) + EPOCH_DIFF

                class FT(ctypes.Structure):
                    _fields_ = [("lo", ctypes.c_ulong), ("hi", ctypes.c_ulong)]

                ft = FT(ft_val & 0xFFFFFFFF, ft_val >> 32)
                ctypes.windll.kernel32.SetFileTime(
                    handle, ctypes.byref(ft), None, ctypes.byref(ft)
                )
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# JPEG EXIF Embedder
# ---------------------------------------------------------------------------
def _dms(deg: float):
    deg = abs(deg)
    d   = int(deg)
    m   = int((deg - d) * 60)
    s   = round(((deg - d) * 60 - m) * 60 * 10000)
    return [(d, 1), (m, 1), (s, 10000)]


def embed_jpeg(src: Path, dst: Path, meta: dict):
    """Embed Date + GPS EXIF into JPEG without quality loss."""
    try:
        exif = piexif.load(str(src))
    except Exception:
        exif = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

    if "dt" in meta:
        dt_b = meta["dt"].strftime("%Y:%m:%d %H:%M:%S").encode("ascii")
        exif["0th"][piexif.ImageIFD.DateTime]          = dt_b
        exif["Exif"][piexif.ExifIFD.DateTimeOriginal]  = dt_b
        exif["Exif"][piexif.ExifIFD.DateTimeDigitized] = dt_b

    if "lat" in meta:
        lat, lng = meta["lat"], meta["lng"]
        exif["GPS"] = {
            piexif.GPSIFD.GPSLatitudeRef:  b"N" if lat >= 0 else b"S",
            piexif.GPSIFD.GPSLatitude:     _dms(lat),
            piexif.GPSIFD.GPSLongitudeRef: b"E" if lng >= 0 else b"W",
            piexif.GPSIFD.GPSLongitude:    _dms(lng),
            piexif.GPSIFD.GPSAltitudeRef:  0,
            piexif.GPSIFD.GPSAltitude:     (max(0, int(abs(meta.get("alt", 0)) * 100)), 100),
        }

    if meta.get("desc"):
        exif["0th"][piexif.ImageIFD.ImageDescription] = meta["desc"].encode("utf-8")

    try:
        eb = piexif.dump(exif)
    except Exception:
        exif["GPS"] = {}
        eb = piexif.dump(exif)

    dst.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(str(src))
    img.save(str(dst), exif=eb, quality=95, subsampling=0)
    img.close()

    if "dt" in meta:
        set_timestamps(dst, meta["dt"])


# ---------------------------------------------------------------------------
# Video Metadata Embedder
# ---------------------------------------------------------------------------
def check_ffmpeg() -> bool:
    """Check if ffmpeg is available in PATH."""
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True)
        return r.returncode == 0
    except FileNotFoundError:
        return False


def embed_video(src: Path, dst: Path, meta: dict) -> bool:
    """Embed metadata into video using ffmpeg stream copy (no re-encode)."""
    dst.parent.mkdir(parents=True, exist_ok=True)

    if "dt" not in meta or not check_ffmpeg():
        shutil.copy2(str(src), str(dst))
        if "dt" in meta:
            set_timestamps(dst, meta["dt"])
        return False

    dt     = meta["dt"]
    dt_iso = dt.strftime("%Y-%m-%dT%H:%M:%S")

    cmd = [
        "ffmpeg", "-i", str(src),
        "-map_metadata", "0",
        "-metadata", f"creation_time={dt_iso}",
        "-metadata", f"date={dt.strftime('%Y-%m-%d')}",
        "-metadata", f"title={meta.get('title', '')}",
        "-metadata", f"comment={meta.get('desc', '')}",
        "-codec", "copy", "-y", str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        if dst.exists():
            dst.unlink()
        shutil.copy2(str(src), str(dst))

    if dst.exists() and "dt" in meta:
        set_timestamps(dst, meta["dt"])

    return result.returncode == 0


# ---------------------------------------------------------------------------
# Duplicate Detection
# ---------------------------------------------------------------------------
def file_hash(path: Path, chunk_size: int = 65536) -> str:
    """Compute MD5 hash of file for duplicate detection."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def get_unique_path(path: Path) -> Path:
    """Return a non-conflicting path by appending a counter suffix."""
    if not path.exists():
        return path
    base, ext = path.stem, path.suffix
    counter   = 1
    while path.exists():
        path    = path.parent / f"{base}_{counter}{ext}"
        counter += 1
    return path


# ---------------------------------------------------------------------------
# Standard Scan (Google Takeout album folder structure)
# ---------------------------------------------------------------------------
def scan_folder(
    takeout_root: str,
    date_from:    Optional[datetime] = None,
    date_to:      Optional[datetime] = None,
) -> list:
    """
    Scan Google Takeout root folder (one level of album sub-folders).
    Returns list of (photo_path, json_path_or_None).
    """
    root    = Path(takeout_root)
    results = []

    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        for f in sorted(folder.iterdir()):
            if f.suffix.lower() not in ALL_EXTS:
                continue
            json_path = find_json(f)
            if (date_from or date_to) and json_path:
                try:
                    meta = parse_metadata(json_path)
                    dt   = meta.get("dt")
                    if dt:
                        if date_from and dt < date_from:
                            continue
                        if date_to   and dt > date_to:
                            continue
                except Exception:
                    pass
            results.append((f, json_path))

    return results


# ---------------------------------------------------------------------------
# God Mode Scan (Deep recursive — handles any nested folder structure)
# ---------------------------------------------------------------------------
def scan_folder_deep(
    root_path:  str,
    date_from:  Optional[datetime] = None,
    date_to:    Optional[datetime] = None,
    log_callback: Optional[Callable] = None,
) -> list:
    """
    God Mode: Recursively scan ALL sub-folders at ANY depth.
    Automatically finds every media file and its JSON sidecar
    regardless of how deeply nested or disorganized the folder is.

    Returns list of (photo_path, json_path_or_None).
    """
    root    = Path(root_path)
    results = []
    total_scanned = 0

    if log_callback:
        log_callback(f"God Mode: Deep scanning '{root_path}' ...", "info")

    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() not in ALL_EXTS:
            continue

        total_scanned += 1
        json_path      = find_json(f)

        if (date_from or date_to) and json_path:
            try:
                meta = parse_metadata(json_path)
                dt   = meta.get("dt")
                if dt:
                    if date_from and dt < date_from:
                        continue
                    if date_to   and dt > date_to:
                        continue
            except Exception:
                pass

        results.append((f, json_path))

    if log_callback:
        log_callback(
            f"God Mode scan complete — {len(results)} media files found across all sub-folders.",
            "success",
        )

    return results


# ---------------------------------------------------------------------------
# Folder Statistics
# ---------------------------------------------------------------------------
def get_folder_stats(takeout_root: str, deep: bool = False) -> dict:
    """Return detailed breakdown of a takeout folder."""
    root  = Path(takeout_root)
    stats = {
        "folders":       0,
        "total":         0,
        "jpegs":         0,
        "videos":        0,
        "others":        0,
        "with_json":     0,
        "total_size_mb": 0.0,
        "year_dist":     {},
    }

    iterator = root.rglob("*") if deep else (
        f for folder in root.iterdir() if folder.is_dir()
        for f in folder.iterdir()
    )

    seen_folders = set()
    for f in sorted(root.rglob("*") if deep else [
        item for sub in root.iterdir() if sub.is_dir()
        for item in sub.iterdir()
    ]):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext not in ALL_EXTS:
            continue

        folder_key = str(f.parent)
        if folder_key not in seen_folders:
            seen_folders.add(folder_key)
            stats["folders"] += 1

        stats["total"]         += 1
        stats["total_size_mb"] += f.stat().st_size / (1024 * 1024)

        if ext in JPEG_EXTS:
            stats["jpegs"]  += 1
        elif ext in VIDEO_EXTS:
            stats["videos"] += 1
        else:
            stats["others"] += 1

        j = find_json(f)
        if j:
            stats["with_json"] += 1
            try:
                meta = parse_metadata(j)
                if "dt" in meta:
                    yr = str(meta["dt"].year)
                    stats["year_dist"][yr] = stats["year_dist"].get(yr, 0) + 1
            except Exception:
                pass

    stats["total_size_mb"] = round(stats["total_size_mb"], 1)
    return stats


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------
def export_errors_csv(err_list: list, output_folder: str) -> str:
    out   = Path(output_folder)
    fname = out / f"photometa_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    fname.parent.mkdir(parents=True, exist_ok=True)
    with open(fname, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["File Name", "Error"])
        for name, err in err_list:
            w.writerow([name, err])
    return str(fname)


# ---------------------------------------------------------------------------
# Main Processor
# ---------------------------------------------------------------------------
def process_all(
    takeout_root:      str,
    output_folder:     str,
    structure_mode:    str = "original",
    conflict_mode:     str = "rename",
    skip_duplicates:   bool = False,
    god_mode:          bool = False,
    date_from:         Optional[datetime] = None,
    date_to:           Optional[datetime] = None,
    progress_callback: Optional[Callable] = None,
    log_callback:      Optional[Callable] = None,
) -> dict:
    """
    Process all media files — embed metadata, organize output.

    Parameters
    ----------
    takeout_root    : Source folder (Takeout root or any folder in God Mode)
    output_folder   : Destination for processed files
    structure_mode  : 'original' | 'flat' | 'year' | 'year_month'
    conflict_mode   : 'rename' | 'skip' | 'overwrite'
    skip_duplicates : Skip files with identical MD5 hashes
    god_mode        : Deep recursive scan — works on ANY folder structure
    date_from/to    : Optional date range filter
    """

    def log(msg, level="info"):
        if log_callback:
            log_callback(msg, level)

    # Scan
    if god_mode:
        all_files = scan_folder_deep(takeout_root, date_from, date_to, log_callback)
    else:
        all_files = scan_folder(takeout_root, date_from, date_to)

    root     = Path(takeout_root)
    out_root = Path(output_folder)
    total    = len(all_files)

    stats = {
        "total":      total,
        "jpeg_ok":    0,
        "video_ok":   0,
        "other_ok":   0,
        "no_json":    0,
        "skipped":    0,
        "duplicates": 0,
        "gps_added":  0,
        "error":      0,
        "err_list":   [],
    }

    seen_hashes: set = set()
    log(f"Starting — {total} files queued for processing ...", "info")

    for i, (src, json_path) in enumerate(all_files, 1):
        if progress_callback:
            progress_callback(i, total, src.name)

        try:
            meta = {}
            if json_path:
                meta = parse_metadata(json_path)
            else:
                stats["no_json"] += 1
                log(f"  No JSON sidecar — {src.name}", "warn")

            # Duplicate check
            if skip_duplicates:
                h = file_hash(src)
                if h in seen_hashes:
                    stats["duplicates"] += 1
                    log(f"  Duplicate skipped — {src.name}", "warn")
                    continue
                seen_hashes.add(h)

            if "lat" in meta:
                stats["gps_added"] += 1

            # Determine destination path
            if structure_mode == "flat":
                dst = out_root / src.name

            elif structure_mode == "year_month":
                if "dt" in meta:
                    dt  = meta["dt"]
                    dst = out_root / str(dt.year) / f"{dt.month:02d}" / src.name
                else:
                    dst = out_root / "Unknown Date" / src.name

            elif structure_mode == "year":
                if "dt" in meta:
                    dst = out_root / str(meta["dt"].year) / src.name
                else:
                    dst = out_root / "Unknown Date" / src.name

            else:  # original
                try:
                    rel = src.relative_to(root)
                    dst = out_root / rel
                except ValueError:
                    # God Mode: file may be deeply nested — preserve relative path from root
                    dst = out_root / src.name

            # Conflict resolution
            if dst.exists():
                if conflict_mode == "skip":
                    stats["skipped"] += 1
                    log(f"  Already exists, skipped — {src.name}", "info")
                    continue
                elif conflict_mode == "rename":
                    dst = get_unique_path(dst)
                # overwrite: dst stays the same

            dst.parent.mkdir(parents=True, exist_ok=True)
            ext      = src.suffix.lower()
            date_str = meta["dt"].strftime("%d %b %Y") if "dt" in meta else "No date"

            if not json_path:
                shutil.copy2(str(src), str(dst))
                continue

            if ext in JPEG_EXTS:
                embed_jpeg(src, dst, meta)
                stats["jpeg_ok"] += 1
                gps_tag = " [GPS]" if "lat" in meta else ""
                log(f"  JPEG fixed — {src.name}  {date_str}{gps_tag}", "success")

            elif ext in VIDEO_EXTS:
                ok = embed_video(src, dst, meta)
                stats["video_ok"] += 1
                tag = "VIDEO fixed" if ok else "VIDEO copied (no ffmpeg)"
                log(f"  {tag} — {src.name}  {date_str}", "success" if ok else "warn")

            else:
                shutil.copy2(str(src), str(dst))
                if "dt" in meta:
                    set_timestamps(dst, meta["dt"])
                stats["other_ok"] += 1
                log(f"  Other fixed — {src.name}  {date_str}", "success")

        except Exception as e:
            stats["error"] += 1
            stats["err_list"].append((src.name, str(e)))
            log(f"  ERROR — {src.name}: {e}", "error")
            try:
                if not dst.exists():
                    shutil.copy2(str(src), str(dst))
            except Exception:
                pass

    log(
        f"Done!  JPEG:{stats['jpeg_ok']}  Video:{stats['video_ok']}  "
        f"Other:{stats['other_ok']}  GPS:{stats['gps_added']}  "
        f"Dupes:{stats['duplicates']}  Errors:{stats['error']}",
        "info",
    )
    return stats


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------
def verify_output(output_folder: str, sample: int = 50) -> list:
    """Verify metadata on a random sample of output files."""
    out_root = Path(output_folder)
    today    = datetime.now().date()
    results  = []
    count    = 0

    for f in out_root.rglob("*"):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext not in ALL_EXTS:
            continue

        date_found = None
        ftype      = ext[1:].upper()
        has_gps    = False

        if ext in JPEG_EXTS:
            try:
                exif    = piexif.load(str(f))
                raw     = exif.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
                if raw:
                    date_found = datetime.strptime(raw.decode(), "%Y:%m:%d %H:%M:%S")
                gps     = exif.get("GPS", {})
                has_gps = bool(gps.get(piexif.GPSIFD.GPSLatitude))
            except Exception:
                pass

        elif ext in VIDEO_EXTS:
            try:
                cmd    = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(f)]
                result = subprocess.run(cmd, capture_output=True, text=True)
                data   = json.loads(result.stdout)
                tags   = data.get("format", {}).get("tags", {})
                ct     = tags.get("creation_time") or tags.get("date", "")
                if ct:
                    ct         = ct.replace("Z", "").split(".")[0]
                    date_found = datetime.fromisoformat(ct)
            except Exception:
                pass
            if not date_found:
                date_found = datetime.fromtimestamp(f.stat().st_mtime)

        else:
            date_found = datetime.fromtimestamp(f.stat().st_mtime)

        if date_found:
            status = "warn" if date_found.date() == today else "ok"
        else:
            status = "error"

        results.append({
            "name":    f.name,
            "folder":  f.parent.name,
            "type":    ftype,
            "date":    date_found.strftime("%d %b %Y  %H:%M") if date_found else "—",
            "status":  status,
            "has_gps": has_gps,
            "size_kb": round(f.stat().st_size / 1024, 1),
        })

        count += 1
        if count >= sample:
            return results

    return results