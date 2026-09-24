# 🎬 Video Compressor Desktop

> A high-performance, dark-mode desktop application built with Python & PySide6 for effortlessly compressing screen recordings, Zoom meetings, and large videos with zero command-line friction.

---

## ✨ Key Features

- **⚡ Zero Setup (Auto-FFmpeg Downloader):**
  - No need to manually install FFmpeg or configure Windows environment PATH variables.
  - Built-in one-click downloader fetches, verifies, and configures FFmpeg automatically in the background.

- **🎯 Smart Target Size Engine:**
  - Need to fit under Discord's 25 MB upload limit or an email's 10 MB limit? Just pick a preset or type your target in MB.
  - Automatically calculates the required video bitrate using `ffprobe` metadata and dynamically manages audio bandwidth.

- **🩺 Live Feasibility Health Gauge:**
  - Real-time safety check (`OPTIMAL`, `GOOD`, `TIGHT`, `IMPRACTICAL`) warns you before encoding if your target size is too aggressive for the video duration.
  - Dynamic auto-downscaling recommendations protect text clarity and prevent macro-blocking on low bitrates.

- **🎛️ Dual Compression Modes:**
  - **Smart Target Size:** Hit exact file size limits every time (`-b:v`, `-maxrate`, `-bufsize`).
  - **CRF Quality Presets:** Standard constant rate factor encoding (Minimal, Recommended, High Compression).

- **📊 Live Activity & Progress Log:**
  - Real-time progress bar with percentage, speed multiplier, and estimated time remaining.
  - Collapsible terminal inspection log showing the exact FFmpeg commands and output.

- **🌙 Clean Dark Modern UI:**
  - Sleek, eye-friendly dark theme with styled system dialogs and intuitive status badges.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- Windows 10/11 (or macOS / Linux)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/your-repo-name.git
   cd your-repo-name
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   # On Windows PowerShell:
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install PySide6
   ```

4. **Run the application:**
   ```bash
   python main.py
   ```

**Note on FFmpeg:** On first launch, if FFmpeg is not found on your system, simply click the green "Download FFmpeg (Auto)" button in the app header to download it automatically.

---

## 🛠️ Tech Stack

- **GUI Framework:** [PySide6](https://pypi.org/project/PySide6/)
- **Media Engine:** [FFmpeg](https://ffmpeg.org/) & [FFprobe](https://ffmpeg.org/ffprobe.html)
- **Language:** Python 3.10+
- **Styling:** Custom QSS (Qt Style Sheets) Dark Palette

---

## 📋 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.