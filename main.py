"""
main.py
PySide6 application entry point and main window for Step 2.
"""

import sys
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
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
)

from ffmpeg_core import locate_binaries, probe_video, BinaryDetectionResult, VideoMetadata


DARK_THEME_QSS = """
QMainWindow {
    background-color: #121317;
}

QWidget {
    color: #E2E8F0;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13px;
}

QFrame#statusCard, QFrame#dropCard, QFrame#infoCard, QFrame#presetCard, QFrame#outputCard {
    background-color: #1A1C23;
    border: 1px solid #2D3139;
    border-radius: 8px;
    padding: 14px;
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
}

QLabel#subtitleLabel {
    font-size: 12px;
    color: #94A3B8;
}

QLabel#sectionHeader {
    font-weight: 600;
    font-size: 12px;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

QLabel#statusBadgeSuccess {
    background-color: #064E3B;
    color: #6EE7B7;
    border: 1px solid #059669;
    border-radius: 4px;
    padding: 1px 7px;
    font-weight: 600;
    font-size: 11px;
}

QLabel#statusBadgeError {
    background-color: #7F1D1D;
    color: #FCA5A5;
    border: 1px solid #DC2626;
    border-radius: 4px;
    padding: 1px 7px;
    font-weight: 600;
    font-size: 11px;
}

QLabel#metaKeyLabel {
    color: #64748B;
    font-size: 12px;
}

QLabel#metaValueLabel {
    color: #F1F5F9;
    font-weight: 500;
    font-size: 12px;
}

QLineEdit {
    background-color: #0F1115;
    border: 1px solid #2D3139;
    border-radius: 6px;
    padding: 6px 10px;
    color: #F1F5F9;
    font-family: "Consolas", monospace;
    font-size: 12px;
}

QLineEdit:focus {
    border-color: #3B82F6;
}

QPushButton {
    background-color: #2563EB;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #1D4ED8;
}

QPushButton:pressed {
    background-color: #1E40AF;
}

QPushButton#secondaryBtn {
    background-color: #272A34;
    color: #E2E8F0;
    border: 1px solid #3B404D;
}

QPushButton#secondaryBtn:hover {
    background-color: #323744;
}

QRadioButton {
    spacing: 8px;
    color: #CBD5E1;
    font-weight: 500;
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
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Compressor")
        self.resize(720, 700)
        self.setMinimumSize(600, 620)

        # Enable drag-and-drop on the main window
        self.setAcceptDrops(True)

        self.detection: BinaryDetectionResult = BinaryDetectionResult(None, None)
        self.current_metadata: VideoMetadata | None = None

        self._init_ui()
        self._check_binaries()

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(14)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(2)
        title = QLabel("Video Compressor", self)
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)
        subtitle = QLabel("Desktop meeting & media compressor (v0.1)", self)
        subtitle.setObjectName("subtitleLabel")
        header_layout.addWidget(subtitle)
        root_layout.addLayout(header_layout)

        # 1. Environment status bar (compact)
        status_card = QFrame(self)
        status_card.setObjectName("statusCard")
        sc_layout = QHBoxLayout(status_card)
        sc_layout.setContentsMargins(12, 8, 12, 8)
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

        # 2. Input File Selection Drop Zone
        self.drop_card = QFrame(self)
        self.drop_card.setObjectName("dropCard")
        drop_layout = QVBoxLayout(self.drop_card)
        drop_layout.setContentsMargins(16, 20, 16, 20)
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

        # 3. Media Metadata Info Card (hidden until a file is selected)
        self.info_card = QFrame(self)
        self.info_card.setObjectName("infoCard")
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setSpacing(8)

        info_header = QLabel("Input Video Details", self)
        info_header.setObjectName("sectionHeader")
        info_layout.addWidget(info_header)

        # 2x2 grid for file details
        meta_grid = QHBoxLayout()
        meta_grid.setSpacing(20)

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
        preset_layout.setSpacing(10)

        preset_title = QLabel("Compression Quality Preset", self)
        preset_title.setObjectName("sectionHeader")
        preset_layout.addWidget(preset_title)

        radio_layout = QHBoxLayout()
        radio_layout.setSpacing(24)

        self.preset_group = QButtonGroup(self)

        self.rb_high = QRadioButton("High Quality (CRF 23 - sharpest, moderate savings)", self)
        self.rb_balanced = QRadioButton("Balanced (CRF 28 - ideal for meetings & slides)", self)
        self.rb_small = QRadioButton("Small Size (CRF 32 - maximum reduction)", self)

        self.rb_balanced.setChecked(True)  # Default recommendation for meeting recordings

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
        out_layout.setSpacing(8)

        out_title = QLabel("Output Destination", self)
        out_title.setObjectName("sectionHeader")
        out_layout.addWidget(out_title)

        dest_row = QHBoxLayout()
        dest_row.setSpacing(10)

        self.txt_output_path = QLineEdit(self)
        self.txt_output_path.setPlaceholderText("Output file path will be configured once video is selected")
        dest_row.addWidget(self.txt_output_path, stretch=1)

        self.btn_change_dest = QPushButton("Change...", self)
        self.btn_change_dest.setObjectName("secondaryBtn")
        self.btn_change_dest.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_change_dest.clicked.connect(self._on_change_output)
        dest_row.addWidget(self.btn_change_dest)

        out_layout.addLayout(dest_row)
        root_layout.addWidget(output_card)

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
        else:
            self.badge_ffmpeg.setText("MISSING")
            self.badge_ffmpeg.setObjectName("statusBadgeError")

        if self.detection.ffprobe_path:
            self.badge_ffprobe.setText("FOUND")
            self.badge_ffprobe.setObjectName("statusBadgeSuccess")
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

    # --- Drag and Drop Handlers ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
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

            # Update Metadata Display
            self.lbl_meta_name.setText(metadata.file_name)
            self.lbl_meta_size.setText(metadata.formatted_size)
            self.lbl_meta_duration.setText(metadata.formatted_duration)
            self.lbl_meta_res.setText(f"{metadata.resolution_str} ({metadata.codec_name})")
            self.info_card.setVisible(True)

            # Auto-suggest output path: same folder with "_compressed.mp4"
            folder = os.path.dirname(metadata.file_path)
            stem, _ = os.path.splitext(metadata.file_name)
            default_out = os.path.join(folder, f"{stem}_compressed.mp4")
            self.txt_output_path.setText(default_out)

            # Update drop label
            self.drop_label.setText(f"Loaded: {metadata.file_name}")

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


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()