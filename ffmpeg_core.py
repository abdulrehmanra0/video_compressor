"""
ffmpeg_core.py - Core video inspection, BPP math engine, WinGet discovery,
and Hardware-Accelerated encoding engine (Intel QSV, NVENC, AMF, CPU).
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

FFMPEG_ESSENTIALS_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


@dataclass
class BinaryDetectionResult:
    ffmpeg_path: Optional[str]
    ffprobe_path: Optional[str]

    @property
    def is_valid(self) -> bool:
        return bool(self.ffmpeg_path and self.ffprobe_path)


@dataclass
class VideoMetadata:
    file_path: str
    file_name: str
    file_size_bytes: int
    formatted_size: str
    duration_seconds: float
    formatted_duration: str
    width: int
    height: int
    resolution_str: str
    codec_name: str
    bitrate_kbps: int
    fps: float


@dataclass
class TargetSizeCalculation:
    target_mb: float
    video_bitrate_kbps: int
    audio_bitrate_kbps: int
    total_bitrate_kbps: int
    bpp: float
    status: str  # 'optimal', 'tight', 'impractical'
    status_message: str
    recommended_scale: Optional[str]
    is_feasible: bool


def format_bytes(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {units[i]}"


def format_seconds(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def parse_time_str_to_seconds(time_str: str) -> float:
    try:
        parts = time_str.split(":")
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    except Exception:
        pass
    return 0.0


def parse_progress_line(line: str) -> Dict[str, str]:
    if "=" in line:
        k, v = line.split("=", 1)
        return {k.strip(): v.strip()}
    return {}


def get_bin_dir() -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).resolve().parent
    bin_dir = base_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    return bin_dir


def locate_binaries(custom_ffmpeg_path: Optional[str] = None) -> BinaryDetectionResult:
    bin_dir = get_bin_dir()
    is_win = os.name == "nt"
    ffmpeg_exe = "ffmpeg.exe" if is_win else "ffmpeg"
    ffprobe_exe = "ffprobe.exe" if is_win else "ffprobe"

    ffmpeg_found = None
    ffprobe_found = None
    creationflags = subprocess.CREATE_NO_WINDOW if is_win else 0

    def test_run(path: str) -> bool:
        try:
            res = subprocess.run(
                [path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                timeout=3,
            )
            return res.returncode == 0
        except Exception:
            return False

    # 1. Custom user path
    if custom_ffmpeg_path and os.path.isfile(custom_ffmpeg_path):
        if test_run(custom_ffmpeg_path):
            ffmpeg_found = custom_ffmpeg_path
            candidate_probe = os.path.join(os.path.dirname(custom_ffmpeg_path), ffprobe_exe)
            if os.path.isfile(candidate_probe) and test_run(candidate_probe):
                ffprobe_found = candidate_probe

    # 2. Local app bin/ directory (highest priority for portable zero-setup)
    if not ffmpeg_found:
        local_ffmpeg = bin_dir / ffmpeg_exe
        if local_ffmpeg.is_file() and test_run(str(local_ffmpeg)):
            ffmpeg_found = str(local_ffmpeg)

    if not ffprobe_found:
        local_ffprobe = bin_dir / ffprobe_exe
        if local_ffprobe.is_file() and test_run(str(local_ffprobe)):
            ffprobe_found = str(local_ffprobe)

    # 3. WinGet Packages fallback (*Gyan.FFmpeg*/**/bin)
    if is_win and (not ffmpeg_found or not ffprobe_found):
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            winget_packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
            if winget_packages.is_dir():
                for bin_cand in winget_packages.glob("*Gyan.FFmpeg*/**/bin"):
                    cand_ff = bin_cand / ffmpeg_exe
                    cand_probe = bin_cand / ffprobe_exe

                    if not ffmpeg_found and cand_ff.is_file() and test_run(str(cand_ff)):
                        ffmpeg_found = str(cand_ff)

                    if not ffprobe_found and cand_probe.is_file() and test_run(str(cand_probe)):
                        ffprobe_found = str(cand_probe)

                    if ffmpeg_found and ffprobe_found:
                        break

    # 4. System PATH fallback
    if not ffmpeg_found:
        sys_ffmpeg = shutil.which("ffmpeg")
        if sys_ffmpeg and test_run(sys_ffmpeg):
            ffmpeg_found = sys_ffmpeg

    if not ffprobe_found:
        sys_ffprobe = shutil.which("ffprobe")
        if sys_ffprobe and test_run(sys_ffprobe):
            ffprobe_found = sys_ffprobe

    return BinaryDetectionResult(ffmpeg_path=ffmpeg_found, ffprobe_path=ffprobe_found)


def probe_hardware_encoders(ffmpeg_path: str) -> Dict[str, bool]:
    """Tests if hardware acceleration works on this machine's GPU and driver."""
    results = {"qsv": False, "nvenc": False, "amf": False}
    if not ffmpeg_path or not os.path.isfile(ffmpeg_path):
        return results

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    test_cases = [("qsv", "h264_qsv"), ("nvenc", "h264_nvenc"), ("amf", "h264_amf")]

    for key, encoder in test_cases:
        try:
            cmd = [
                ffmpeg_path,
                "-y",
                "-f", "lavfi",
                "-i", "color=c=black:s=128x128:d=0.1",
                "-c:v", encoder,
                "-f", "null",
                "-",
            ]
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                timeout=4,
            )
            if res.returncode == 0:
                results[key] = True
        except Exception:
            results[key] = False

    return results


def download_and_extract_ffmpeg(
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    is_cancelled_func: Optional[Callable[[], bool]] = None,
) -> BinaryDetectionResult:
    bin_dir = get_bin_dir()
    zip_path = bin_dir / "ffmpeg_download_temp.zip"

    req = urllib.request.Request(
        FFMPEG_ESSENTIALS_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        block_size = 1024 * 512

        with open(zip_path, "wb") as f:
            while True:
                if is_cancelled_func and is_cancelled_func():
                    raise InterruptedError("Download cancelled by user.")
                chunk = response.read(block_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total_size, "Downloading FFmpeg...")

    if progress_callback:
        progress_callback(total_size, total_size, "Extracting binaries...")

    with zipfile.ZipFile(zip_path, "r") as z:
        for item in z.namelist():
            norm = item.replace("\\", "/")
            fname = os.path.basename(norm)
            if fname.lower() in ("ffmpeg.exe", "ffprobe.exe"):
                src = z.open(item)
                dest = bin_dir / fname
                with open(dest, "wb") as out_f:
                    shutil.copyfileobj(src, out_f)

    if zip_path.exists():
        try:
            zip_path.unlink()
        except Exception:
            pass

    return locate_binaries()


def probe_video(ffprobe_path: str, file_path: str) -> VideoMetadata:
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
        timeout=15,
    )
    if res.returncode != 0:
        raise RuntimeError("ffprobe could not inspect this file.")

    data = json.loads(res.stdout)
    vstream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if not vstream:
        raise ValueError("No video stream found in file.")

    dur = float(data.get("format", {}).get("duration", vstream.get("duration", 0)))
    w = int(vstream.get("width", 0))
    h = int(vstream.get("height", 0))
    size_b = int(data.get("format", {}).get("size", os.path.getsize(file_path)))
    br = int(data.get("format", {}).get("bit_rate", vstream.get("bit_rate", 0)))
    codec = vstream.get("codec_name", "unknown")

    # Extract accurate FPS
    r_fps = vstream.get("r_frame_rate", "30/1")
    try:
        if "/" in r_fps:
            num, den = r_fps.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 30.0
        else:
            fps = float(r_fps)
    except Exception:
        fps = 30.0

    return VideoMetadata(
        file_path=file_path,
        file_name=os.path.basename(file_path),
        file_size_bytes=size_b,
        formatted_size=format_bytes(size_b),
        duration_seconds=dur,
        formatted_duration=format_seconds(dur),
        width=w,
        height=h,
        resolution_str=f"{w}x{h}",
        codec_name=codec,
        bitrate_kbps=int(br / 1000) if br > 0 else 0,
        fps=round(fps, 2),
    )


def calculate_target_bitrate(
    target_mb: float,
    duration_seconds: float,
    width: int,
    height: int,
    fps: float = 30.0,
) -> TargetSizeCalculation:
    """Calculates bitrate using Bits Per Pixel (BPP): bpp = video_bps / (total_pixels * effective_fps)."""
    if duration_seconds <= 0:
        return TargetSizeCalculation(
            target_mb=target_mb,
            video_bitrate_kbps=1000,
            audio_bitrate_kbps=128,
            total_bitrate_kbps=1128,
            bpp=0.05,
            status="optimal",
            status_message="Valid duration required.",
            recommended_scale=None,
            is_feasible=True,
        )

    total_kbits = target_mb * 8192 * 0.95
    total_kbps = total_kbits / duration_seconds

    if total_kbps < 200:
        audio_kbps = 48
    elif total_kbps < 400:
        audio_kbps = 64
    elif total_kbps < 800:
        audio_kbps = 96
    else:
        audio_kbps = 128

    video_kbps = int(total_kbps - audio_kbps)
    if video_kbps < 64:
        video_kbps = 64

    # BPP Math calculation
    video_bps = video_kbps * 1000
    total_pixels = max(1, width * height)
    effective_fps = max(1.0, fps)
    bpp = video_bps / (total_pixels * effective_fps)

    is_vertical = height > width
    rec_scale = None

    if bpp < 0.012:
        status = "impractical"
        rec_scale = "360:-2" if is_vertical else "-2:360"
        msg = f"Extremely Low Quality (BPP: {bpp:.4f}, {video_kbps} kbps). Severe artifacts likely. Consider trimming or raising target MB."
    elif bpp < 0.025:
        status = "tight"
        rec_scale = "480:-2" if is_vertical else "-2:480"
        msg = f"Tight Quality (BPP: {bpp:.4f}, {video_kbps} kbps). Downscaling recommended to preserve text sharpness."
    elif bpp < 0.045:
        status = "optimal"
        if (width > 1280 or height > 1280) and bpp < 0.035:
            rec_scale = "720:-2" if is_vertical else "-2:720"
            msg = f"Good Quality (BPP: {bpp:.4f}, {video_kbps} kbps). Auto-downscaling to 720p recommended for crisp slides."
        else:
            rec_scale = None
            msg = f"Good Quality (BPP: {bpp:.4f}, {video_kbps} kbps). Suitable for meetings and screen recordings."
    else:
        status = "optimal"
        rec_scale = None
        msg = f"Optimal Quality (BPP: {bpp:.4f}, {video_kbps} kbps). Generous bitrate with sharp clarity."

    return TargetSizeCalculation(
        target_mb=target_mb,
        video_bitrate_kbps=video_kbps,
        audio_bitrate_kbps=audio_kbps,
        total_bitrate_kbps=int(total_kbps),
        bpp=round(bpp, 4),
        status=status,
        status_message=msg,
        recommended_scale=rec_scale,
        is_feasible=(status != "impractical"),
    )


def _resolve_encoder(codec_name: str, hw_accel: str, hw_caps: Optional[Dict[str, bool]]) -> Tuple[str, str]:
    hw_choice = "cpu"
    if hw_accel == "auto":
        if hw_caps and hw_caps.get("qsv"):
            hw_choice = "qsv"
        elif hw_caps and hw_caps.get("nvenc"):
            hw_choice = "nvenc"
        elif hw_caps and hw_caps.get("amf"):
            hw_choice = "amf"
        else:
            hw_choice = "cpu"
    else:
        hw_choice = hw_accel

    if codec_name == "hevc":
        if hw_choice == "qsv":
            return "hevc_qsv", "qsv"
        if hw_choice == "nvenc":
            return "hevc_nvenc", "nvenc"
        if hw_choice == "amf":
            return "hevc_amf", "amf"
        return "libx265", "cpu"
    else:
        if hw_choice == "qsv":
            return "h264_qsv", "qsv"
        if hw_choice == "nvenc":
            return "h264_nvenc", "nvenc"
        if hw_choice == "amf":
            return "h264_amf", "amf"
        return "libx264", "cpu"


def build_crf_args(
    input_path: str,
    output_path: str,
    crf_value: int = 28,
    codec_name: str = "h264",
    hw_accel: str = "auto",
    hw_caps: Optional[Dict[str, bool]] = None,
) -> List[str]:
    enc, hw = _resolve_encoder(codec_name, hw_accel, hw_caps)
    args = ["-y", "-i", input_path, "-c:v", enc]

    if hw == "cpu":
        args.extend(["-crf", str(crf_value), "-preset", "medium"])
    elif hw == "qsv":
        args.extend(["-global_quality", str(crf_value), "-preset", "medium"])
    elif hw == "nvenc":
        args.extend(["-cq", str(crf_value), "-preset", "p4"])
    elif hw == "amf":
        args.extend(["-rc", "cqp", "-qp_p", str(crf_value)])

    if hw != "qsv":
        args.extend(["-pix_fmt", "yuv420p"])

    args.extend([
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        "-nostats",
        output_path,
    ])
    return args


def build_target_size_args(
    input_path: str,
    output_path: str,
    video_kbps: int,
    audio_kbps: int = 128,
    scale: Optional[str] = None,
    codec_name: str = "h264",
    hw_accel: str = "auto",
    hw_caps: Optional[Dict[str, bool]] = None,
) -> List[str]:
    enc, hw = _resolve_encoder(codec_name, hw_accel, hw_caps)
    args = ["-y", "-i", input_path, "-c:v", enc]

    args.extend([
        "-b:v", f"{video_kbps}k",
        "-maxrate", f"{video_kbps}k",
        "-bufsize", f"{video_kbps * 2}k",
    ])

    if hw in ("cpu", "qsv"):
        args.extend(["-preset", "medium"])

    if scale:
        args.extend(["-vf", f"scale={scale}"])

    if hw != "qsv":
        args.extend(["-pix_fmt", "yuv420p"])

    args.extend([
        "-c:a", "aac",
        "-b:a", f"{audio_kbps}k",
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        "-nostats",
        output_path,
    ])
    return args