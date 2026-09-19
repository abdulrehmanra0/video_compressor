"""
main.py
PySide6 application entry point and complete v0.1 UI with QProcess execution,
clean card layout without clipping, instant cancellation, and automatic partial file deletion.
"""

import sys
import os
from PySide6.QtCore import Qt, QProcess, QUrl, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QFileDialog,
    QRadioButton,
    QButtonGroup,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QScrollArea,
    QPlainTextEdit,
)

from ffmpeg_core import (
    locate_binaries,
    probe_video,
    build_ffmpeg_args,
    parse_progress_line,
    parse_time_str_to_seconds,
    format_bytes,
    format_seconds,
    BinaryDetectionResult,
    VideoMetadata,
)


DARK_THEME_QSS = """
QMainWindow {
    background-color: #121317;
}

QScrollArea {
    background-color: #121317;
    border: none;
}

QWidget#scrollContent {
    background-color: #121317;
}

QWidget {
    color: #E2E8F0;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13px;
}

/* Card frames styled without CSS padding to prevent label clipping */
QFrame#statusCard, QFrame#dropCard, QFrame#infoCard, QFrame#presetCard, QFrame#outputCard, QFrame#progressCard, QFrame#logCard {
    background-color: #1A1C23;
    border: 1px solid #2D3139;
    border-radius: 8px;
}

QFrame#dropCard {
    border: 2px dashed #3B4252;
    background-color: #15171E;
}

QFrame#dropCard:hover {
    border-color: #3B82F6;
    background-color: #181B24;
}

QLabel#titleLabel {
    font-size: 18px;
    font-weight: 600;
    color: #F8FAFC;
    min-height: 24px;
}

QLabel#subtitleLabel {
    font-size: 12px;
    color: #94A3B8;
    min-height: 18px;
}

QLabel#sectionHeader {
    font-weight: 600;
    font-size: 12px;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    min-height: 18px;
}

QLabel#statusBadgeSuccess {
    background-color: #064E3B;
    color: #6EE7B7;
    border: 1px solid #059669;
    border-radius: 4px;
    padding: 2px 8px;
    font-weight: 600;
    font-size: 11px;
    min-height: 16px;
}

QLabel#statusBadgeError {
    background-color: #7F1D1D;
    color: #FCA5A5;
    border: 1px solid #DC2626;
    border-radius: 4px;
    padding: 2px 8px;
    font-weight: 600;
    font-size: 11px;
    min-height: 16px;
}

QLabel#metaKeyLabel {
    color: #64748B;
    font-size: 12px;
    min-height: 20px;
}

QLabel#metaValueLabel {
    color: #F1F5F9;
    font-weight: 500;
    font-size: 12px;
    min-height: 20px;
}

QLineEdit {
    background-color: #0F1115;
    border: 1px solid #2D3139;
    border-radius: 6px;
    padding: 6px 10px;
    color: #F1F5F9;
    font-family: "Consolas", monospace;
    font-size: 12px;
    min-height: 22px;
}

QLineEdit:focus {
    border-color: #3B82F6;
}

QPushButton {
    background-color: #2563EB;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #1D4ED8;
}

QPushButton:pressed {
    background-color: #1E40AF;
}

QPushButton:disabled {
    background-color: #1E2330;
    color: #4B5563;
    border: 1px solid #282E3E;
}

QPushButton#secondaryBtn {
    background-color: #272A34;
    color: #E2E8F0;
    border: 1px solid #3B404D;
    font-weight: 500;
    padding: 6px 14px;
    min-height: 18px;
}

QPushButton#secondaryBtn:hover {
    background-color: #323744;
}

QPushButton#cancelBtn {
    background-color: #7F1D1D;
    color: #FCA5A5;
    border: 1px solid #991B1B;
    padding: 8px 18px;
    min-height: 18px;
}

QPushButton#cancelBtn:hover {
    background-color: #991B1B;
}

QRadioButton {
    spacing: 8px;
    color: #CBD5E1;
    font-weight: 500;
    min-height: 22px;
}

QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid #4B5563;
    background-color: #1A1C23;
}

QRadioButton::indicator:checked {
    border-color: #3B82F6;
    background-color: #3B82F6;
}

QProgressBar {
    background-color: #0F1115;
    border: 1px solid #2D3139;
    border-radius: 6px;
    text-align: center;
    color: #FFFFFF;
    font-weight: 600;
    font-size: 12px;
    height: 24px;
    min-height: 24px;
}

QProgressBar::chunk {
    background-color: #2563EB;
    border-radius: 5px;
}

QPlainTextEdit#logConsole {
    background-color: #0B0C0E;
    color: #94A3B8;
    border: 1px solid #242832;
    border-radius: 6px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11px;
    line-height: 1.4;
    padding: 8px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Compressor")
        self.resize(780, 820)
        self.setMinimumSize(640, 600)

        self.setAcceptDrops(True)

        self.detection: BinaryDetectionResult = BinaryDetectionResult(None, None)
        self.current_metadata: VideoMetadata | None = None

        self.process: QProcess | None = None
        self.is_compressing = False
        self.was_cancelled = False
        self.target_output_file = ""
        self._stdout_buffer = ""

        self._init_ui()
        self._check_binaries()

    def _init_ui(self):
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll_area)

        content_widget = QWidget()
        content_widget.setObjectName("scrollContent")
        scroll_area.setWidget(content_widget)

        root_layout = QVBoxLayout(content_widget)
        root_layout.setContentsMargins(24, 20, 24, 24)
        root_layout.setSpacing(14)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(3)
        title = QLabel("Video Compressor", self)
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)
        subtitle = QLabel("Desktop meeting & media compressor (v0.1)", self)
        subtitle.setObjectName("subtitleLabel")
        header_layout.addWidget(subtitle)
        root_layout.addLayout(header_layout)

        # 1. Environment status bar
        status_card = QFrame(self)
        status_card.setObjectName("statusCard")
        sc_layout = QHBoxLayout(status_card)
        sc_layout.setContentsMargins(14, 10, 14, 10)
        sc_layout.setSpacing(16)

        sc_title = QLabel("Environment:", self)
        sc_title.setObjectName("sectionHeader")
        sc_layout.addWidget(sc_title)

        ff_row = QHBoxLayout()
        ff_row.setSpacing(6)
        ff_row.addWidget(QLabel("FFmpeg:", self))
        self.badge_ffmpeg = QLabel(self)
        ff_row.addWidget(self.badge_ffmpeg)
        sc_layout.addLayout(ff_row)

        probe_row = QHBoxLayout()
        probe_row.setSpacing(6)
        probe_row.addWidget(QLabel("FFprobe:", self))
        self.badge_ffprobe = QLabel(self)
        probe_row.addWidget(self.badge_ffprobe)
        sc_layout.addLayout(probe_row)

        sc_layout.addStretch()

        self.btn_locate = QPushButton("Locate FFmpeg...", self)
        self.btn_locate.setObjectName("secondaryBtn")
        self.btn_locate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_locate.clicked.connect(self._on_locate_clicked)
        sc_layout.addWidget(self.btn_locate)

        root_layout.addWidget(status_card)

        # 2. Drop Zone
        self.drop_card = QFrame(self)
        self.drop_card.setObjectName("dropCard")
        drop_layout = QVBoxLayout(self.drop_card)
        drop_layout.setContentsMargins(20, 22, 20, 22)
        drop_layout.setSpacing(8)
        drop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.drop_label = QLabel("Drag and drop your video file here", self)
        self.drop_label.setStyleSheet("font-size: 14px; font-weight: 500; color: #CBD5E1;")
        drop_layout.addWidget(self.drop_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.drop_sublabel = QLabel("Supports MP4, MOV, MKV, WebM, AVI", self)
        self.drop_sublabel.setStyleSheet("font-size: 11px; color: #64748B;")
        drop_layout.addWidget(self.drop_sublabel, alignment=Qt.AlignmentFlag.AlignCenter)

        self.btn_browse = QPushButton("Select Video File...", self)
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.clicked.connect(self._on_browse_file)
        drop_layout.addWidget(self.btn_browse, alignment=Qt.AlignmentFlag.AlignCenter)

        root_layout.addWidget(self.drop_card)

        # 3. Video Metadata Details Card
        self.info_card = QFrame(self)
        self.info_card.setObjectName("infoCard")
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setContentsMargins(16, 14, 16, 14)
        info_layout.setSpacing(8)

        info_header = QLabel("Input Video Details", self)
        info_header.setObjectName("sectionHeader")
        info_layout.addWidget(info_header)

        meta_grid = QHBoxLayout()
        meta_grid.setSpacing(24)

        col1 = QVBoxLayout()
        col1.setSpacing(4)
        self.lbl_meta_name = self._make_meta_row(col1, "File Name:", "-")
        self.lbl_meta_size = self._make_meta_row(col1, "Original Size:", "-")
        meta_grid.addLayout(col1, stretch=2)

        col2 = QVBoxLayout()
        col2.setSpacing(4)
        self.lbl_meta_duration = self._make_meta_row(col2, "Duration:", "-")
        self.lbl_meta_res = self._make_meta_row(col2, "Resolution / Codec:", "-")
        meta_grid.addLayout(col2, stretch=1)

        info_layout.addLayout(meta_grid)
        self.info_card.setVisible(False)
        root_layout.addWidget(self.info_card)

        # 4. Quality Presets Card
        preset_card = QFrame(self)
        preset_card.setObjectName("presetCard")
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setContentsMargins(16, 14, 16, 14)
        preset_layout.setSpacing(10)

        preset_title = QLabel("Compression Quality Preset", self)
        preset_title.setObjectName("sectionHeader")
        preset_layout.addWidget(preset_title)

        radio_layout = QHBoxLayout()
        radio_layout.setSpacing(20)

        self.preset_group = QButtonGroup(self)
        self.rb_high = QRadioButton("High Quality (CRF 23 - sharpest, moderate savings)", self)
        self.rb_balanced = QRadioButton("Balanced (CRF 28 - ideal for meetings & slides)", self)
        self.rb_small = QRadioButton("Small Size (CRF 32 - maximum reduction)", self)
        self.rb_balanced.setChecked(True)

        self.preset_group.addButton(self.rb_high, 23)
        self.preset_group.addButton(self.rb_balanced, 28)
        self.preset_group.addButton(self.rb_small, 32)

        radio_layout.addWidget(self.rb_high)
        radio_layout.addWidget(self.rb_balanced)
        radio_layout.addWidget(self.rb_small)
        radio_layout.addStretch()

        preset_layout.addLayout(radio_layout)
        root_layout.addWidget(preset_card)

        # 5. Output Destination Card
        output_card = QFrame(self)
        output_card.setObjectName("outputCard")
        out_layout = QVBoxLayout(output_card)
        out_layout.setContentsMargins(16, 14, 16, 14)
        out_layout.setSpacing(8)

        out_title = QLabel("Output Destination", self)
        out_title.setObjectName("sectionHeader")
        out_layout.addWidget(out_title)

        dest_row = QHBoxLayout()
        dest_row.setSpacing(10)

        self.txt_output_path = QLineEdit(self)
        self.txt_output_path.setPlaceholderText("Output path will appear here once video is loaded")
        dest_row.addWidget(self.txt_output_path, stretch=1)

        self.btn_change_dest = QPushButton("Change...", self)
        self.btn_change_dest.setObjectName("secondaryBtn")
        self.btn_change_dest.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_change_dest.clicked.connect(self._on_change_output)
        dest_row.addWidget(self.btn_change_dest)

        out_layout.addLayout(dest_row)
        root_layout.addWidget(output_card)

        # 6. Action Buttons (Compress / Cancel)
        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        self.btn_compress = QPushButton("Compress Video", self)
        self.btn_compress.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_compress.setEnabled(False)
        self.btn_compress.clicked.connect(self._start_compression)
        action_row.addWidget(self.btn_compress)

        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.setObjectName("cancelBtn")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel_compression)
        action_row.addWidget(self.btn_cancel)

        action_row.addStretch()
        root_layout.addLayout(action_row)

        # 7. Progress & Results Card
        self.progress_card = QFrame(self)
        self.progress_card.setObjectName("progressCard")
        prog_layout = QVBoxLayout(self.progress_card)
        prog_layout.setContentsMargins(16, 14, 16, 14)
        prog_layout.setSpacing(10)

        self.lbl_progress_status = QLabel("Ready to compress", self)
        self.lbl_progress_status.setStyleSheet("font-weight: 500; color: #E2E8F0; min-height: 20px;")
        prog_layout.addWidget(self.lbl_progress_status)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.progress_bar)

        # Results area
        self.results_box = QWidget(self)
        res_layout = QVBoxLayout(self.results_box)
        res_layout.setContentsMargins(0, 4, 0, 0)
        res_layout.setSpacing(8)

        self.lbl_result_summary = QLabel(self)
        self.lbl_result_summary.setStyleSheet("color: #6EE7B7; font-weight: 600; font-size: 13px; min-height: 20px;")
        res_layout.addWidget(self.lbl_result_summary)

        self.btn_open_folder = QPushButton("Open Output Folder", self)
        self.btn_open_folder.setObjectName("secondaryBtn")
        self.btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self._open_output_folder)
        res_layout.addWidget(self.btn_open_folder, alignment=Qt.AlignmentFlag.AlignLeft)

        prog_layout.addWidget(self.results_box)
        self.results_box.setVisible(False)
        self.progress_card.setVisible(False)
        root_layout.addWidget(self.progress_card)

        # 8. Activity Log Card
        self.log_card = QFrame(self)
        self.log_card.setObjectName("logCard")
        log_layout = QVBoxLayout(self.log_card)
        log_layout.setContentsMargins(16, 14, 16, 14)
        log_layout.setSpacing(8)

        log_header_row = QHBoxLayout()
        log_title = QLabel("FFmpeg Activity Log", self)
        log_title.setObjectName("sectionHeader")
        log_header_row.addWidget(log_title)
        log_header_row.addStretch()

        self.btn_toggle_log = QPushButton("Hide Log", self)
        self.btn_toggle_log.setObjectName("secondaryBtn")
        self.btn_toggle_log.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_log.clicked.connect(self._toggle_log_view)
        log_header_row.addWidget(self.btn_toggle_log)
        log_layout.addLayout(log_header_row)

        self.log_console = QPlainTextEdit(self)
        self.log_console.setObjectName("logConsole")
        self.log_console.setReadOnly(True)
        self.log_console.setMinimumHeight(120)
        self.log_console.setMaximumHeight(180)
        log_layout.addWidget(self.log_console)

        self.log_card.setVisible(False)
        root_layout.addWidget(self.log_card)

        root_layout.addStretch()

    def _make_meta_row(self, parent_layout: QVBoxLayout, label: str, default_val: str) -> QLabel:
        row = QHBoxLayout()
        row.setSpacing(8)
        key_lbl = QLabel(label, self)
        key_lbl.setObjectName("metaKeyLabel")
        key_lbl.setFixedWidth(115)
        val_lbl = QLabel(default_val, self)
        val_lbl.setObjectName("metaValueLabel")
        val_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(key_lbl)
        row.addWidget(val_lbl, stretch=1)
        parent_layout.addLayout(row)
        return val_lbl

    def _check_binaries(self, custom_path: str | None = None):
        self.detection = locate_binaries(custom_path)
        self._update_status_display()

    def _update_status_display(self):
        if self.detection.ffmpeg_path:
            self.badge_ffmpeg.setText("FOUND")
            self.badge_ffmpeg.setObjectName("statusBadgeSuccess")
            self.badge_ffmpeg.setToolTip(self.detection.ffmpeg_path)
        else:
            self.badge_ffmpeg.setText("MISSING")
            self.badge_ffmpeg.setObjectName("statusBadgeError")

        if self.detection.ffprobe_path:
            self.badge_ffprobe.setText("FOUND")
            self.badge_ffprobe.setObjectName("statusBadgeSuccess")
            self.badge_ffprobe.setToolTip(self.detection.ffprobe_path)
        else:
            self.badge_ffprobe.setText("MISSING")
            self.badge_ffprobe.setObjectName("statusBadgeError")

        self.badge_ffmpeg.style().unpolish(self.badge_ffmpeg)
        self.badge_ffmpeg.style().polish(self.badge_ffmpeg)
        self.badge_ffprobe.style().unpolish(self.badge_ffprobe)
        self.badge_ffprobe.style().polish(self.badge_ffprobe)

        all_found = bool(self.detection.ffmpeg_path and self.detection.ffprobe_path)
        self.btn_locate.setVisible(not all_found)

    def _on_locate_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select ffmpeg.exe",
            os.environ.get("USERPROFILE", ""),
            "Executables (ffmpeg.exe);;All Files (*.*)",
        )
        if file_path:
            self._check_binaries(custom_path=file_path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if not self.is_compressing and event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        if not self.is_compressing:
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                file_path = urls[0].toLocalFile()
                self._process_selected_file(file_path)

    def _on_browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            os.environ.get("USERPROFILE", ""),
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm *.flv);;All Files (*.*)",
        )
        if file_path:
            self._process_selected_file(file_path)

    def _process_selected_file(self, file_path: str):
        if not self.detection.ffprobe_path:
            QMessageBox.critical(self, "Error", "Cannot inspect video: ffprobe.exe is missing.")
            return

        try:
            metadata = probe_video(self.detection.ffprobe_path, file_path)
            self.current_metadata = metadata

            self.lbl_meta_name.setText(metadata.file_name)
            self.lbl_meta_size.setText(metadata.formatted_size)
            self.lbl_meta_duration.setText(metadata.formatted_duration)
            self.lbl_meta_res.setText(f"{metadata.resolution_str} ({metadata.codec_name})")
            self.info_card.setVisible(True)

            folder = os.path.dirname(metadata.file_path)
            stem, _ = os.path.splitext(metadata.file_name)
            default_out = os.path.join(folder, f"{stem}_compressed.mp4")
            self.txt_output_path.setText(default_out)

            self.drop_label.setText(f"Loaded: {metadata.file_name}")
            self.btn_compress.setEnabled(bool(self.detection.ffmpeg_path))

            self.progress_card.setVisible(False)
            self.results_box.setVisible(False)
            self.log_card.setVisible(False)

        except Exception as err:
            QMessageBox.critical(self, "Inspection Error", f"Could not read video metadata:\n{str(err)}")

    def _on_change_output(self):
        current_val = self.txt_output_path.text().strip()
        start_dir = os.path.dirname(current_val) if current_val else os.environ.get("USERPROFILE", "")

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Choose Compressed Output Location",
            current_val or os.path.join(start_dir, "compressed_video.mp4"),
            "MP4 Video (*.mp4);;All Files (*.*)",
        )
        if save_path:
            self.txt_output_path.setText(save_path)

    # --- Compression via QProcess ---
    def _start_compression(self):
        if not self.current_metadata or not self.detection.ffmpeg_path:
            return

        output_path = self.txt_output_path.text().strip()
        if not output_path:
            QMessageBox.warning(self, "Warning", "Please specify a valid output destination path.")
            return

        if os.path.abspath(output_path) == os.path.abspath(self.current_metadata.file_path):
            QMessageBox.warning(self, "Warning", "Output destination cannot be identical to the input file.")
            return

        crf_value = self.preset_group.checkedId()
        if crf_value == -1:
            crf_value = 28

        args = build_ffmpeg_args(self.current_metadata.file_path, output_path, crf_value)

        self.target_output_file = output_path
        self.was_cancelled = False
        self.is_compressing = True
        self._stdout_buffer = ""

        self.btn_compress.setEnabled(False)
        self.btn_browse.setEnabled(False)
        self.btn_change_dest.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.btn_cancel.setEnabled(True)
        self.progress_card.setVisible(True)
        self.results_box.setVisible(False)
        self.progress_bar.setValue(0)
        self.lbl_progress_status.setText("Initializing FFmpeg encoder...")

        self.log_console.clear()
        full_command_str = f'"{self.detection.ffmpeg_path}" ' + " ".join(f'"{a}"' if " " in a else a for a in args)
        self.log_console.appendPlainText(f"$ {full_command_str}\n")
        self.log_card.setVisible(True)

        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._on_ffmpeg_stdout)
        self.process.readyReadStandardError.connect(self._on_ffmpeg_stderr)
        self.process.finished.connect(self._on_ffmpeg_finished)

        self.process.start(self.detection.ffmpeg_path, args)

    def _on_ffmpeg_stdout(self):
        if not self.process or not self.current_metadata:
            return

        raw_data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self._stdout_buffer += raw_data

        lines = self._stdout_buffer.split("\n")
        self._stdout_buffer = lines[-1]

        latest_time_sec = None
        latest_fps = None
        latest_speed = None

        for raw_line in lines[:-1]:
            line = raw_line.strip()
            if not line:
                continue

            parsed = parse_progress_line(line)

            if "out_time_us" in parsed:
                try:
                    val = int(parsed["out_time_us"])
                    if val >= 0:
                        latest_time_sec = val / 1_000_000.0
                except (ValueError, TypeError):
                    pass

            elif "out_time" in parsed and latest_time_sec is None:
                sec = parse_time_str_to_seconds(parsed["out_time"])
                if sec > 0:
                    latest_time_sec = sec

            if "fps" in parsed and parsed["fps"] != "0.0":
                latest_fps = parsed["fps"]
            if "speed" in parsed:
                latest_speed = parsed["speed"]

        if latest_time_sec is not None:
            total_sec = max(1.0, self.current_metadata.duration_seconds)
            percent = min(100, max(0, int((latest_time_sec / total_sec) * 100)))

            self.progress_bar.setValue(percent)
            curr_str = format_seconds(latest_time_sec)
            tot_str = format_seconds(total_sec)

            detail_parts = [f"{curr_str} / {tot_str}"]
            if latest_fps:
                detail_parts.append(f"{latest_fps} fps")
            if latest_speed:
                detail_parts.append(f"{latest_speed}")

            self.lbl_progress_status.setText(f"Compressing... {percent}% ({' • '.join(detail_parts)})")

    def _on_ffmpeg_stderr(self):
        if not self.process:
            return
        err_data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        if err_data:
            self.log_console.appendPlainText(err_data.rstrip())
            self.log_console.verticalScrollBar().setValue(
                self.log_console.verticalScrollBar().maximum()
            )

    def _cancel_compression(self):
        """Immediately terminates FFmpeg and triggers asynchronous file cleanup."""
        if not self.process:
            return

        self.was_cancelled = True
        self.btn_cancel.setEnabled(False)
        self.lbl_progress_status.setText("Cancelling...")
        self.log_console.appendPlainText("\n[USER CANCELLED] Terminating FFmpeg process immediately...")

        # Kill the process
        self.process.kill()

    def _cleanup_partial_output_file(self, attempt: int = 1):
        """
        Deletes the unplayable partial output file after FFmpeg has completely exited.
        Retries up to 5 times if Windows temporarily holds the file handle lock.
        """
        if not self.target_output_file:
            return

        if os.path.isfile(self.target_output_file):
            try:
                os.remove(self.target_output_file)
                self.log_console.appendPlainText(f"[CLEANUP] Successfully deleted corrupted partial file: {self.target_output_file}")
            except OSError as err:
                if attempt < 6:
                    # Windows kernel may hold the file lock for a split-second; retry after 200ms
                    QTimer.singleShot(200, lambda: self._cleanup_partial_output_file(attempt + 1))
                else:
                    self.log_console.appendPlainText(f"[CLEANUP ERROR] Could not delete file: {err}")

    def _on_ffmpeg_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        self.is_compressing = False
        self._reset_ui_after_run()

        # Handle user cancellation
        if self.was_cancelled:
            self.lbl_progress_status.setText("Compression cancelled.")
            self.progress_bar.setValue(0)
            self._cleanup_partial_output_file()
            return

        # Handle successful completion
        if exit_code == 0 and os.path.isfile(self.target_output_file):
            self.progress_bar.setValue(100)
            self.lbl_progress_status.setText("Compression complete!")

            orig_bytes = self.current_metadata.file_size_bytes if self.current_metadata else 0
            new_bytes = os.path.getsize(self.target_output_file)
            saved_bytes = max(0, orig_bytes - new_bytes)
            percent_saved = (saved_bytes / orig_bytes * 100) if orig_bytes > 0 else 0.0

            summary_text = (
                f"Original: {format_bytes(orig_bytes)}  ->  "
                f"Compressed: {format_bytes(new_bytes)}  "
                f"({percent_saved:.1f}% saved)"
            )
            self.lbl_result_summary.setText(summary_text)
            self.results_box.setVisible(True)
            self.log_console.appendPlainText(f"\n[FINISHED] Success! Output saved to: {self.target_output_file}")

        # Handle error
        else:
            self.lbl_progress_status.setText("Encoding failed.")
            self.log_console.appendPlainText(f"\n[ERROR] FFmpeg exited with code {exit_code}")
            self._cleanup_partial_output_file()
            QMessageBox.critical(
                self,
                "Compression Error",
                f"FFmpeg failed with exit code {exit_code}.\nCheck the Activity Log below for details."
            )

    def _reset_ui_after_run(self):
        self.btn_compress.setEnabled(True)
        self.btn_browse.setEnabled(True)
        self.btn_change_dest.setEnabled(True)
        self.btn_cancel.setVisible(False)

    def _open_output_folder(self):
        if self.target_output_file and os.path.isfile(self.target_output_file):
            folder = os.path.dirname(self.target_output_file)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _toggle_log_view(self):
        is_visible = self.log_console.isVisible()
        self.log_console.setVisible(not is_visible)
        self.btn_toggle_log.setText("Show Log" if is_visible else "Hide Log")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()