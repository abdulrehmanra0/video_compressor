"""
ffmpeg_core.py
Core binary detection and ffprobe metadata extraction.
Zero GUI imports.
"""

import os
import shutil
import json
import subprocess
from pathlib import Path
from typing import NamedTuple, Optional


class BinaryDetectionResult(NamedTuple):
    ffmpeg_path: Optional[str]
    ffprobe_path: Optional[str]


class VideoMetadata(NamedTuple):
    file_path: str
    file_name: str
    file_size_bytes: int
    duration_seconds: float
    width: int
    height: int
    codec_name: str

    @property
    def formatted_size(self) -> str:
        """Returns human-readable size (e.g. '3.12 GB' or '450.2 MB')."""
        bytes_val = float(self.file_size_bytes)
        if bytes_val >= 1024 ** 3:
            return f"{bytes_val / (1024 ** 3):.2f} GB"
        return f"{bytes_val / (1024 ** 2):.1f} MB"

    @property
    def formatted_duration(self) -> str:
        """Returns HH:MM:SS format."""
        total_seconds = int(self.duration_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def resolution_str(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "Unknown"


def locate_binaries(custom_ffmpeg_path: Optional[str] = None) -> BinaryDetectionResult:
    ffmpeg_path: Optional[str] = None
    ffprobe_path: Optional[str] = None

    # 1. Custom path override check
    if custom_ffmpeg_path and os.path.isfile(custom_ffmpeg_path):
        ffmpeg_path = os.path.abspath(custom_ffmpeg_path)
        candidate_probe = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe.exe")
        if os.path.isfile(candidate_probe):
            ffprobe_path = candidate_probe

    # 2. Check System PATH
    if not ffmpeg_path:
        found_ffmpeg = shutil.which("ffmpeg")
        if found_ffmpeg:
            ffmpeg_path = os.path.abspath(found_ffmpeg)

    if not ffprobe_path:
        found_probe = shutil.which("ffprobe")
        if found_probe:
            ffprobe_path = os.path.abspath(found_probe)

    # 3. Check WinGet Gyan.FFmpeg installation directory
    if not ffmpeg_path or not ffprobe_path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            winget_packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
            if winget_packages.exists():
                for bin_dir in winget_packages.glob("*Gyan.FFmpeg*/**/bin"):
                    cand_ffmpeg = bin_dir / "ffmpeg.exe"
                    cand_ffprobe = bin_dir / "ffprobe.exe"

                    if not ffmpeg_path and cand_ffmpeg.is_file():
                        ffmpeg_path = str(cand_ffmpeg.resolve())
                    if not ffprobe_path and cand_ffprobe.is_file():
                        ffprobe_path = str(cand_ffprobe.resolve())

                    if ffmpeg_path and ffprobe_path:
                        break

    return BinaryDetectionResult(ffmpeg_path=ffmpeg_path, ffprobe_path=ffprobe_path)


def probe_video(ffprobe_path: str, video_path: str) -> VideoMetadata:
    """
    Executes ffprobe to extract structural video metadata.
    Raises RuntimeError or FileNotFoundError on failure.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Input video file not found: {video_path}")

    if not os.path.isfile(ffprobe_path):
        raise FileNotFoundError(f"ffprobe binary not found at: {ffprobe_path}")

    cmd = [
        ffprobe_path,
        "-v", "error",
        "-show_entries", "stream=width,height,duration,codec_name",
        "-show_entries", "format=duration,size",
        "-of", "json",
        video_path,
    ]

    # Prevent console popup window on Windows
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=startupinfo,
        timeout=15,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    format_data = data.get("format", {})
    streams = data.get("streams", [])

    # Find the primary video stream
    width = 0
    height = 0
    codec_name = "unknown"
    stream_duration = 0.0

    for stream in streams:
        if "width" in stream and "height" in stream:
            width = int(stream["width"])
            height = int(stream["height"])
            codec_name = stream.get("codec_name", "unknown")
            if "duration" in stream:
                try:
                    stream_duration = float(stream["duration"])
                except (ValueError, TypeError):
                    pass
            break

    # Determine duration: prefer format.duration, fallback to stream.duration
    duration = 0.0
    try:
        duration = float(format_data.get("duration", stream_duration))
    except (ValueError, TypeError):
        duration = stream_duration

    # Determine total file size
    size_bytes = os.path.getsize(video_path)
    try:
        format_size = int(format_data.get("size", size_bytes))
        size_bytes = format_size if format_size > 0 else size_bytes
    except (ValueError, TypeError):
        pass

    return VideoMetadata(
        file_path=os.path.abspath(video_path),
        file_name=os.path.basename(video_path),
        file_size_bytes=size_bytes,
        duration_seconds=duration,
        width=width,
        height=height,
        codec_name=codec_name,
    )