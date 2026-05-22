## Why PhotoMeta Restorer?
Most Google Takeout metadata fixers are either paid, limited to 100 photos, or require complex command-line arguments. **PhotoMeta Restorer** bridges this gap by providing a completely free, high-performance, and secure graphical user interface (GUI) to repair your Google Photos library instantly.

# 📸 PhotoMeta Restorer

> Restore lost dates, GPS locations, and timestamps from your Google Photos Takeout export — automatically.

When you download your photos from Google Takeout, all the metadata (dates, GPS coordinates, descriptions) gets stripped from the actual files and stored separately in `.json` sidecar files. PhotoMeta Restorer reads those JSON files and writes the metadata back into the photos — so your memories are correctly dated and located again, forever.

---

## ✨ Features

| Feature | Details |
|---|---|
| **JPEG / JPG** | Embeds date, GPS coordinates, and description into EXIF |
| **Videos** | Writes creation date and title via FFmpeg (no re-encoding) |
| **PNG / HEIC / WebP / GIF** | Restores file creation and modification timestamps |
| **God Mode** | Deep recursive scan — handles any folder structure at unlimited depth |
| **Duplicate Detection** | MD5 hash comparison — skips identical files, saves storage |
| **Date Range Filter** | Process only photos from specific years or date ranges |
| **Output Organization** | Original / Flat / By Year / By Year & Month |
| **Conflict Resolution** | Rename, Skip, or Overwrite existing files |
| **Verification** | Sample-checks output files to confirm metadata was correctly written |
| **Error Report** | Exports a CSV of any files that failed, with error details |
| **Year Distribution** | Visual chart showing how many photos you have per year |

---

## 🗂️ Project Structure

```
photometa-restorer/
│
├── app.py              ← Streamlit web interface  (run this)
├── processor.py        ← Core logic — EXIF, video, timestamps, God Mode
├── requirements.txt    ← Python dependencies
└── README.md           ← This file
```

---

## ⚙️ Setup

### Requirements

- Python 3.9 or higher
- FFmpeg (optional — required only for video internal metadata)

---

### Step 1 — Install Python

Download and install Python 3.9+ from [python.org](https://www.python.org/downloads/).

Make sure to check **"Add Python to PATH"** during installation on Windows.

---

### Step 2 — Install Python Dependencies

Open a terminal in the project folder and run:

```bash
pip install -r requirements.txt
```

---

### Step 3 — Install FFmpeg *(optional, for video metadata)*

**Windows:**
```bash
winget install ffmpeg
```
Or download manually from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) → extract to `C:\ffmpeg\bin` → add to System PATH.

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu / Debian):**
```bash
sudo apt install ffmpeg
```

After installing, restart your terminal and run `ffmpeg -version` to confirm it works.

> **Without FFmpeg:** Videos will still be copied and their file timestamps will be fixed — only the internal video metadata (readable by media players) won't be embedded.

---

## 🚀 Running the App

```bash
streamlit run app.py
```

The app will open automatically in your browser at **http://localhost:8501**

---

## 📋 How to Use

### 1. Download Your Google Takeout

Go to [takeout.google.com](https://takeout.google.com), select **Google Photos**, and download your export. Extract the ZIP file — you'll have a folder like:

```
Takeout/
└── Google Photos/
    ├── Photos from 2021/
    ├── Photos from 2022/
    ├── My Album/
    └── ...
```

---

### 2. Configure Paths

- **Source Folder Path** — The root of your Takeout export (e.g. `D:\Takeout\Google Photos`)
- **Output Folder Path** — Where fixed files will be saved (e.g. `D:\Photos_Fixed`)

> Your original files are **never modified**. Everything is written to the output folder.

---

### 3. Choose God Mode (Recommended for Large Exports)

Enable **God Mode** if:
- Your photos are nested in many layers of sub-folders
- You have multiple Takeout ZIPs merged together
- You're not sure how the folders are structured

God Mode performs a fully recursive scan — it will find every photo and video no matter how deep or disorganized the folder structure is.

---

### 4. Configure Options

**Output Folder Structure** — How your photos are organized in the output:

| Option | Result |
|---|---|
| Original | Preserves Google's album folder structure |
| Flat | All files in a single folder |
| By Year | `2022/`, `2023/`, `2024/` ... |
| By Year & Month | `2023/05/`, `2023/06/` ... |

**If a file already exists in output:**

| Option | Behavior |
|---|---|
| Rename | Adds `_1`, `_2` suffix — safe, keeps all files |
| Skip | Leaves existing file untouched — good for resuming interrupted runs |
| Overwrite | Replaces the existing file |

**Advanced Options:**

- **Skip duplicate files** — Uses MD5 content hashing to detect and skip identical files. Useful if you have multiple Takeout exports with overlapping photos.
- **Filter by date range** — Only process photos taken within a specific date range.

---

### 5. Scan & Preview

Click **Scan Folder & Preview Stats** to see:
- Total files found (JPEG, Video, Other)
- How many have JSON sidecars (metadata available)
- Total storage size
- Year-by-year photo distribution chart

---

### 6. Start Restoration

Click **Start Metadata Restoration**. You'll see:
- A real-time progress bar with ETA
- A live processing log (color-coded by result)
- Final summary stats when complete

---

### 7. Verify Results

After processing, click **Run Verification Check** to sample-inspect output files and confirm that dates, GPS, and timestamps were correctly written.

---

## 🔍 What Gets Fixed

### JPEG / JPG
- `DateTimeOriginal` EXIF field (the "date taken" shown in all photo apps)
- `DateTime` and `DateTimeDigitized` EXIF fields
- GPS coordinates (latitude, longitude, altitude)
- Image description
- File creation and modification timestamps

### Videos (.mp4, .mov, .avi, .mkv, .m4v, .3gp)
- `creation_time` metadata tag (via FFmpeg stream copy — no quality loss)
- `date` metadata tag
- Title and comment fields
- File creation and modification timestamps

### PNG / HEIC / WebP / GIF
- File creation and modification timestamps
*(These formats do not have a universal metadata standard for date embedding)*

---

## ⚠️ Important Notes

- **Originals are never touched.** All output goes to the folder you specify.
- **No re-encoding.** Videos are copied with stream copy — quality is identical to the original.
- **50,000+ photos supported.** Processing is memory-efficient and handles large libraries.
- **Resumable.** Set conflict mode to "Skip" and re-run to process only new files.
- **JSON match rate matters.** If Google didn't include a `.json` sidecar for a file, that file will be copied as-is without metadata changes.

---

## ❓ Troubleshooting

**"Path not found" error**
- Double-check the folder path. On Windows, use backslashes: `D:\Takeout\Google Photos`
- Make sure the folder exists before starting

**FFmpeg not found**
- Install FFmpeg (see Step 3 above) and restart your terminal
- Run `ffmpeg -version` to confirm it's in your PATH

**Low JSON match rate**
- This is normal for some Takeout exports. Files without a JSON sidecar are copied with their original timestamps intact.
- God Mode sometimes improves the match rate by finding JSON files that are in sibling or parent folders.

**App is slow on large libraries**
- This is expected. For 50,000+ photos, processing can take 30–90 minutes depending on your hardware and whether FFmpeg is being used for videos.
- Set conflict mode to "Skip" so you can safely resume if interrupted.

**"Module not found" error**
- Run `pip install -r requirements.txt` again and make sure you're using the correct Python environment.

---

## 📦 Dependencies

```
streamlit >= 1.35.0
piexif    >= 1.1.3
Pillow    >= 10.0.0
```

FFmpeg is an external binary (not a Python package) — install it separately as described above.

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

*Built for recovering memories.*
