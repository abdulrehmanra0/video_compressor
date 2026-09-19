# 🎬 Desktop Video Compressor (v0.1)

A clean, modern Windows desktop video compressor built using **Python 3.11+**, **PySide6 (Qt6)**, and **FFmpeg**.

Designed with a strict separation of concerns: core media detection and encoding logic run completely decoupled from the presentation layer, keeping the UI fast, responsive, and maintainable.

---

## 🚀 Tech Stack & Architecture

- **GUI Framework:** PySide6 (Qt 6.x) with custom dark mode theme (`QSS`)
- **Process Engine:** `QProcess` for non-blocking asynchronous FFmpeg execution
- **Media Backend:** External `ffmpeg` and `ffprobe` binaries (supports system PATH and WinGet installations)
- **Core Separation:** `ffmpeg_core.py` contains zero GUI imports, acting as a standalone backend service

---

## 🛠️ Current Progress (v0.1 - Step 1)

- [x] Native dark-themed PySide6 main window
- [x] Automatic system binary detection (`ffmpeg` & `ffprobe`)
  - Scans system `PATH`
  - Scans local WinGet package directories (`Gyan.FFmpeg`)
  - Supports manual override file picker if binaries are missing
- [ ] Drag-and-drop input video selection & media probing
- [ ] CRF-based quality presets (High / Balanced / Small)
- [ ] Real-time progress monitoring parsed via `-progress pipe:1`
- [ ] Process cancellation and partial file cleanup

---

## 📦 Getting Started

### Prerequisites
- Python 3.11 or higher
- FFmpeg installed (recommended via WinGet: `winget install Gyan.FFmpeg`)

### Installation & Run

```bash
# Clone the repository
git clone https://github.com/abdulrehmanra0/video_compressor.git
cd video-compressor

# Install PySide6
pip install PySide6

# Launch the application
python main.py