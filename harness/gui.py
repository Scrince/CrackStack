from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from threading import Event

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from harness.backends import GenerateConfig, create_backend
from harness.config import HarnessConfig, ModelConfig, SafetyConfig, load_config, save_config
from harness.config_commands import select_model, show_config
from harness.core.agent import Conversation
from harness.core.context import ContextManager
from harness.doctor import format_checks, run_checks
from harness.models import discover_gguf_models, display_model_path
from harness.paths import ensure_base_dirs, harness_root, plugins_dir, workspace_dir
from harness.storage.sessions import ConversationStore, list_sessions, read_session
from harness.storage.tool_log import log_tool_event
from harness.tools import (
    ToolRegistry,
    register_filesystem_tools,
    register_packaging_tools,
    register_self_modify_tools,
)
from harness.tools.plugin_loader import load_generated_tools


CONTEXT_PRESETS = (
    ("4K", 4096),
    ("8K", 8192),
    ("16K", 16384),
    ("32K", 32768),
    ("64K", 65536),
    ("128K", 131072),
    ("Custom", 0),
)

CONTEXT_SLIDER_STEP = 512
CONTEXT_SLIDER_MIN_TOKENS = 2048
CONTEXT_SLIDER_MAX_TOKENS = 131072

TEXT_ATTACHMENT_SUFFIXES = {
    ".py", ".pyi", ".pyw", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".json", ".jsonl", ".toml", ".yaml", ".yml", ".md", ".rst", ".txt",
    ".csv", ".tsv", ".html", ".htm", ".css", ".scss", ".less", ".xml", ".svg",
    ".ini", ".cfg", ".conf", ".env", ".sh", ".bash", ".zsh", ".ps1", ".bat",
    ".cmd", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".cs", ".go", ".rs",
    ".java", ".kt", ".rb", ".php", ".swift", ".sql", ".r", ".lua", ".vim",
    ".dockerfile", ".makefile", ".cmake", ".gradle", ".properties",
    ".gitignore", ".gitattributes", ".editorconfig",
}

DEFAULT_ATTACHMENT_BYTES = 200_000

WELCOME_CAPABILITIES = (
    ("Read & edit files", "Inspect and patch files in the local workspace"),
    ("Run tools", "Search, list dirs, package archives, call agent tools"),
    ("Attach context", "Drag files into the composer like Codex / Claude Code"),
    ("Local only", "GGUF model on this machine — no cloud API"),
)


APP_QSS = """
* {
    outline: none;
}
QMainWindow, QWidget {
    background: #0a0a0b;
        pass
    color: #ececef;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 10pt;
}
QFrame#Sidebar {
    background: #111113;
        pass
    border-right: 1px solid #1e1e22;
}
QFrame#BrandMark {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #3b82f6, stop:1 #8b5cf6);
    border-radius: 8px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
}
QFrame#Panel, QFrame#SettingsDrawer {
    background: #141416;
        pass
    border: 1px solid #232329;
    border-radius: 12px;
}
QFrame#TopBar {
    background: #0a0a0b;
        pass
    border-bottom: 1px solid #1a1a1e;
}
QFrame#ComposerShell {
    background: #121214;
        pass
    border: 1px solid #2a2a30;
    border-radius: 16px;
}
QFrame#ComposerShell[dragActive="true"] {
    border: 1px dashed #60a5fa;
    background: #0c1526;
        pass
}
QFrame#AttachmentChip {
    background: #1a1a1f;
        pass
    border: 1px solid #2f2f38;
    border-radius: 10px;
}
QFrame#CapabilityCard {
    background: #121214;
        pass
    border: 1px solid #232329;
    border-radius: 14px;
}
QFrame#CapabilityCard:hover {
    border-color: #3b3b48;
        pass
    background: #16161a;
        pass
}
QFrame#StatusDot[state="ready"] {
    background: #22c55e;
        pass
    border-radius: 5px;
    min-width: 10px;
    max-width: 10px;
    min-height: 10px;
    max-height: 10px;
}
QFrame#StatusDot[state="busy"] {
    background: #3b82f6;
        pass
    border-radius: 5px;
    min-width: 10px;
    max-width: 10px;
    min-height: 10px;
    max-height: 10px;
}
QFrame#StatusDot[state="warn"] {
    background: #f59e0b;
        pass
    border-radius: 5px;
    min-width: 10px;
    max-width: 10px;
    min-height: 10px;
    max-height: 10px;
}
QFrame#StatusDot[state="error"] {
    background: #ef4444;
        pass
    border-radius: 5px;
    min-width: 10px;
    max-width: 10px;
    min-height: 10px;
    max-height: 10px;
}
QLabel#Brand {
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.2px;
}
QLabel#Title {
    font-size: 15px;
    font-weight: 650;
}
QLabel#HeroTitle {
    font-size: 26px;
    font-weight: 700;
    color: #fafafa;
        pass
}
QLabel#HeroSub {
    font-size: 12pt;
    color: #9b9ba7;
        pass
}
QLabel#Subtitle, QLabel#Muted, QLabel#DropHint {
    color: #8b8b96;
        pass
}
QLabel#SectionTitle {
    font-size: 10px;
    font-weight: 700;
    color: #6b6b78;
        pass
    letter-spacing: 0.8px;
}
QLabel#Pill, QLabel#ModePill {
    background: #18181c;
        pass
    color: #d4d4d8;
        pass
    border: 1px solid #2a2a32;
    border-radius: 999px;
    padding: 5px 11px;
    font-size: 9pt;
}
QLabel#ModePill[tone="agent"] {
    background: #12201a;
        pass
    border-color: #1f3d2f;
        pass
    color: #86efac;
        pass
}
QLabel#ModePill[tone="local"] {
    background: #121826;
        pass
    border-color: #1e3a5f;
        pass
    color: #93c5fd;
        pass
}
QLabel#ModePill[tone="ctx"] {
    background: #1a1625;
        pass
    border-color: #3b2f55;
        pass
    color: #c4b5fd;
        pass
}
QLabel#CapTitle {
    font-weight: 650;
    color: #f4f4f5;
        pass
}
QLabel#CapBody {
    color: #8b8b96;
    font-size: 9pt;
}
QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QListWidget {
    background: #0e0e10;
        pass
    color: #ececef;
        pass
    border: 1px solid #2a2a32;
    border-radius: 10px;
    padding: 6px 10px;
    selection-background-color: #2563eb;
        pass
}
QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 32px;
}
QComboBox QAbstractItemView {
    background: #121214;
        pass
    color: #ececef;
        pass
    border: 1px solid #2a2a32;
    selection-background-color: #2563eb;
        pass
}
QComboBox::drop-down {
    border: 0;
    width: 26px;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    width: 16px;
    border: 0;
}
QListWidget#SessionList {
    background: transparent;
    border: 0;
    padding: 0;
    outline: 0;
}
QListWidget#SessionList::item {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 10px 10px;
    margin: 2px 0;
    color: #b4b4be;
        pass
}
QListWidget#SessionList::item:hover {
    background: #18181c;
        pass
    color: #f4f4f5;
        pass
}
QListWidget#SessionList::item:selected {
    background: #1a1f2e;
        pass
    border-color: #2a3a55;
        pass
    color: #f8fafc;
        pass
}
QTextEdit#Transcript {
    background: #0a0a0b;
        pass
    border: 0;
    padding: 8px 8px;
    font-size: 10.5pt;
}
QTextEdit#Prompt {
    background: transparent;
    border: 0;
    padding: 2px 4px;
    font-size: 11pt;
}
QPushButton {
    background: #1a1a1f;
        pass
    color: #ececef;
        pass
    border: 1px solid #2a2a32;
    border-radius: 10px;
    padding: 8px 12px;
    min-height: 30px;
    font-weight: 550;
}
QPushButton:hover {
    background: #222228;
        pass
}
QPushButton:disabled {
    color: #5c5c66;
        pass
    background: #141416;
        pass
}
QPushButton#PrimaryButton {
    background: #f4f4f5;
        pass
    color: #0a0a0b;
        pass
    border-color: #f4f4f5;
    font-weight: 700;
}
QPushButton#PrimaryButton:hover {
    background: #ffffff;
        pass
}
QPushButton#PrimaryButton:disabled {
    background: #3f3f46;
        pass
    border-color: #3f3f46;
        pass
    color: #a1a1aa;
        pass
}
QPushButton#AccentButton {
    background: #2563eb;
        pass
    color: #ffffff;
        pass
    border-color: #2563eb;
    font-weight: 700;
}
QPushButton#AccentButton:hover {
    background: #3b82f6;
        pass
}
QPushButton#GhostButton, QPushButton#IconButton {
    background: transparent;
    border-color: #2a2a32;
        pass
    color: #c4c4cc;
        pass
}
QPushButton#IconButton {
    min-width: 36px;
    max-width: 42px;
    padding: 6px;
}
QPushButton#DangerButton {
    background: #1f1214;
        pass
    border-color: #4a2228;
        pass
    color: #fca5a5;
        pass
}
QPushButton#DangerButton:hover {
    background: #2a1619;
        pass
}
QToolButton#ChipClose {
    background: transparent;
    border: 0;
    color: #8b8b96;
        pass
    padding: 0 4px;
    min-height: 18px;
}
QToolButton#ChipClose:hover {
    color: #f4f4f5;
        pass
}
QCheckBox {
    spacing: 8px;
    color: #c4c4cc;
        pass
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid #3f3f46;
    background: #0e0e10;
        pass
}
QCheckBox::indicator:checked {
    background: #2563eb;
        pass
    border-color: #2563eb;
        pass
}
QSlider#ContextSlider::groove:horizontal {
    border: 0;
    height: 6px;
    background: #1e1e24;
        pass
    border-radius: 3px;
}
QSlider#ContextSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3b82f6, stop:1 #8b5cf6);
    height: 6px;
    border-radius: 3px;
}
QSlider#ContextSlider::add-page:horizontal {
    background: #1e1e24;
        pass
    height: 6px;
    border-radius: 3px;
}
QSlider#ContextSlider::handle:horizontal {
    background: #ffffff;
        pass
    border: 0;
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QScrollArea#AttachmentScroll, QScrollArea#SideScroll {
    background: transparent;
    border: 0;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2a2a32;
        pass
    border-radius: 5px;
    min-height: 28px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
}
QScrollBar::handle:horizontal {
    background: #2a2a32;
        pass
    border-radius: 4px;
}
"""


@dataclass(frozen=True)
class FileAttachment:
    path: Path
    size_bytes: int

    @property
    def label(self) -> str:
        return self.path.name

    @property
    def display_path(self) -> str:
        return str(self.path)


def is_likely_text_file(path: Path) -> bool:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix in TEXT_ATTACHMENT_SUFFIXES:
        return True
    if name in {"dockerfile", "makefile", "cmakelists.txt", "license", "readme"}:
        return True
    if not suffix and name.startswith("."):
        return True
    return False


def read_attachment_excerpt(path: Path, max_bytes: int = DEFAULT_ATTACHMENT_BYTES) -> tuple[str, str]:
    resolved = path.expanduser()
    if not resolved.exists():
        return "missing", f"File not found: {resolved}"
    if not resolved.is_file():
        return "error", f"Not a file: {resolved}"
    size = resolved.stat().st_size
    if not is_likely_text_file(resolved):
        return "binary", f"Binary file attached by path only ({size} bytes)."
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        return "error", f"Could not read file: {exc}"
    truncated = False
    if max_bytes > 0 and len(raw) > max_bytes:
        raw = raw[:max_bytes]
        truncated = True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-8", errors="replace")
            if "\x00" in text:
                return "binary", f"Binary file attached by path only ({size} bytes)."
        except Exception as exc:  
            return "error", f"Could not decode file: {exc}"
    if truncated:
        return (
            "truncated",
            text + f"\n\n...[truncated: showing first {max_bytes} of {size} bytes]...",
        )
    return "text", text


def build_prompt_with_attachments(
    user_text: str,
    attachments: list[FileAttachment],
    *,
    max_file_bytes: int = DEFAULT_ATTACHMENT_BYTES,
) -> str:
    text = user_text.strip()
    if not attachments:
        return text

    blocks: list[str] = []
    if text:
        blocks.append(text)
        blocks.append("")

    blocks.append("Attached files (use these as authoritative context):")
    for attachment in attachments:
        kind, body = read_attachment_excerpt(attachment.path, max_bytes=max_file_bytes)
        header = f"### File: {attachment.display_path}"
        if kind in {"binary", "missing", "error"}:
            blocks.append(header)
            blocks.append(body)
        else:
            blocks.append(header)
            blocks.append("```")
            blocks.append(body.rstrip("\n"))
            blocks.append("```")
        blocks.append("")
    return "\n".join(blocks).rstrip() + "\n"


def paths_from_mime_urls(urls) -> list[Path]:
    paths: list[Path] = []
    for url in urls:
        if hasattr(url, "isLocalFile") and not url.isLocalFile():
            continue
        local = url.toLocalFile() if hasattr(url, "toLocalFile") else str(url)
        if not local:
            continue
        path = Path(local)
        if path.exists():
            paths.append(path.resolve())
    return paths


def short_session_label(session_id: str) -> str:
    
    try:
        stamp = session_id.split("-", 1)[0]
        month = int(stamp[4:6])
        day = int(stamp[6:8])
        hour = stamp[9:11]
        minute = stamp[11:13]
        months = (
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        )
        return f"{months[month - 1]} {day} · {hour}:{minute}"
    except Exception:
        return session_id[:18]


class WorkerSignals(QObject):
    chunk = Signal(str)
    error = Signal(str)
    tool = Signal(str)
    finished = Signal()


class ModelLoadSignals(QObject):
    loaded = Signal(object, str)
    error = Signal(str)
    finished = Signal()


class PromptTextEdit(QTextEdit):
    submitted = Signal()
    files_dropped = Signal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                event.accept()
                self.submitted.emit()
                return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            paths = paths_from_mime_urls(event.mimeData().urls())
            if paths:
                self.files_dropped.emit(paths)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class ModelLoadWorker(QRunnable):
    def __init__(self, config: HarnessConfig):
        super().__init__()
        self.config = config
        self.signals = ModelLoadSignals()

    @Slot()
    def run(self) -> None:
        try:
            backend = create_backend(self.config.model)
            backend.load()
            model_path = getattr(backend, "model_path", None)
            model_name = str(model_path.name if model_path is not None else self.config.model.backend)
            self.signals.loaded.emit(backend, model_name)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class PromptWorker(QRunnable):
    def __init__(self, window: "HarnessWindow", prompt: str, config: HarnessConfig):
        super().__init__()
        self.window = window
        self.prompt = prompt
        self.config = config
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            convo = self.window.conversation(self.signals.tool, self.config)
            for chunk in convo.stream_ask(self.prompt):
                self.signals.chunk.emit(chunk)
        except Exception as exc:
            self.signals.error.emit(f"Cannot start model backend: {exc}")
        finally:
            self.signals.finished.emit()


class HarnessWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CrackStack Codex")
        self.resize(1320, 860)
        self.setMinimumSize(1040, 700)
        self.setAcceptDrops(True)
        self.thread_pool = QThreadPool.globalInstance()
        self._conversation: Conversation | None = None
        self._conversation_config: HarnessConfig | None = None
        self._preloaded_backend = None
        self._preloaded_config: HarnessConfig | None = None
        self._loading_model = False
        self._assistant_turn_open = False
        self._cancel_event = Event()
        self._busy = False
        self._attachments: list[FileAttachment] = []
        self._syncing_context = False
        self._settings_dirty = False
        self._has_transcript_content = False
        self._loaded_model_name = ""

        self._build()
        self.load_settings()
        self.refresh_models()
        self.refresh_sessions()
        self.run_doctor(append=False)
        self._show_welcome()
        self.preload_model()

    def _build(self) -> None:
        shell = QWidget()
        layout = QHBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setCentralWidget(shell)

        
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(300)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 16, 14, 14)
        side.setSpacing(12)
        layout.addWidget(sidebar)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        mark = QFrame()
        mark.setObjectName("BrandMark")
        brand_row.addWidget(mark)
        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        brand = QLabel("CrackStack")
        brand.setObjectName("Brand")
        brand_sub = QLabel("Local coding agent")
        brand_sub.setObjectName("Muted")
        brand_col.addWidget(brand)
        brand_col.addWidget(brand_sub)
        brand_row.addLayout(brand_col, 1)
        side.addLayout(brand_row)

        new_task = QPushButton("+  New chat")
        new_task.setObjectName("PrimaryButton")
        new_task.clicked.connect(self.new_task)
        side.addWidget(new_task)

        sessions_label = QLabel("CHATS")
        sessions_label.setObjectName("SectionTitle")
        side.addWidget(sessions_label)
        self.session_list = QListWidget()
        self.session_list.setObjectName("SessionList")
        self.session_list.setSpacing(1)
        self.session_list.itemClicked.connect(self._session_item_clicked)
        side.addWidget(self.session_list, 1)

        
        model_card = self._panel()
        model_layout = QVBoxLayout(model_card)
        model_layout.setContentsMargins(12, 12, 12, 12)
        model_layout.setSpacing(8)
        model_title = QLabel("MODEL")
        model_title.setObjectName("SectionTitle")
        model_layout.addWidget(model_title)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumHeight(34)
        model_layout.addWidget(self.model_combo)
        model_btns = self._button_row(
            self._ghost("Refresh", self.refresh_models),
            self._primary("Use model", self.select_current_model),
        )
        model_layout.addLayout(model_btns)
        self.workspace_path_label = QLabel()
        self.workspace_path_label.setObjectName("Muted")
        self.workspace_path_label.setWordWrap(True)
        model_layout.addWidget(self.workspace_path_label)
        side.addWidget(model_card)

        
        settings_card = QFrame()
        settings_card.setObjectName("SettingsDrawer")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(12, 12, 12, 12)
        settings_layout.setSpacing(8)
        settings_header = QHBoxLayout()
        settings_title = QLabel("AGENT SETTINGS")
        settings_title.setObjectName("SectionTitle")
        settings_header.addWidget(settings_title)
        settings_header.addStretch(1)
        self.settings_toggle = QToolButton()
        self.settings_toggle.setText("Hide")
        self.settings_toggle.setObjectName("ChipClose")
        self.settings_toggle.clicked.connect(self._toggle_settings_body)
        settings_header.addWidget(self.settings_toggle)
        settings_layout.addLayout(settings_header)

        self.settings_body = QWidget()
        body = QGridLayout(self.settings_body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setHorizontalSpacing(8)
        body.setVerticalSpacing(8)

        self.context_preset = QComboBox()
        for label, _value in CONTEXT_PRESETS:
            self.context_preset.addItem(label)
        self.context_spin = self._spin(512, 262144, 512)
        self.context_slider = QSlider(Qt.Orientation.Horizontal)
        self.context_slider.setObjectName("ContextSlider")
        self.context_slider.setRange(
            CONTEXT_SLIDER_MIN_TOKENS // CONTEXT_SLIDER_STEP,
            CONTEXT_SLIDER_MAX_TOKENS // CONTEXT_SLIDER_STEP,
        )
        self.context_slider.setSingleStep(1)
        self.context_slider.setPageStep(8)
        self.context_slider.setToolTip(
            f"Context window ({CONTEXT_SLIDER_MIN_TOKENS}–{CONTEXT_SLIDER_MAX_TOKENS} tokens)"
        )
        self.context_value_label = QLabel("4096 tokens")
        self.context_value_label.setObjectName("Muted")
        self.gpu_spin = self._spin(-1, 999, 1)
        self.max_tokens_spin = self._spin(1, 32768, 32)
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.05)
        self.temperature_spin.setDecimals(2)

        body.addWidget(QLabel("Preset"), 0, 0)
        body.addWidget(self.context_preset, 0, 1)
        body.addWidget(QLabel("Context"), 1, 0, 1, 2)
        body.addWidget(self.context_slider, 2, 0, 1, 2)
        body.addWidget(self.context_value_label, 3, 0, 1, 2)
        body.addWidget(QLabel("Exact"), 4, 0)
        body.addWidget(self.context_spin, 4, 1)
        body.addWidget(QLabel("GPU layers"), 5, 0)
        body.addWidget(self.gpu_spin, 5, 1)
        body.addWidget(QLabel("Max tokens"), 6, 0)
        body.addWidget(self.max_tokens_spin, 6, 1)
        body.addWidget(QLabel("Temp"), 7, 0)
        body.addWidget(self.temperature_spin, 7, 1)

        self.dry_run_check = QCheckBox("Dry run (no writes)")
        self.dry_run_check.setToolTip(
            "Preview write/delete/zip/build/self-mod tool actions without applying them. "
            "Saved to config.toml as safety.dry_run when you Save & reload model."
        )
        self.self_modify_check = QCheckBox("Self-modify tools")
        body.addWidget(self.dry_run_check, 8, 0, 1, 2)
        body.addWidget(self.self_modify_check, 9, 0, 1, 2)
        settings_layout.addWidget(self.settings_body)

        for widget in (self.context_spin, self.gpu_spin, self.max_tokens_spin, self.temperature_spin):
            widget.valueChanged.connect(self._settings_changed)
        self.context_preset.currentIndexChanged.connect(self._context_preset_changed)
        self.context_spin.valueChanged.connect(self._context_spin_changed)
        self.context_slider.valueChanged.connect(self._context_slider_changed)
        self.dry_run_check.toggled.connect(self._settings_changed)
        self.self_modify_check.toggled.connect(self._settings_changed)

        save_settings = QPushButton("Save & reload model")
        save_settings.setObjectName("AccentButton")
        save_settings.clicked.connect(self.save_settings)
        settings_layout.addWidget(save_settings)
        side.addWidget(settings_card)

        
        util = QGridLayout()
        util.setSpacing(6)
        for i, (label, slot) in enumerate(
            (
                ("Tools", self.show_tools),
                ("Doctor", self.run_doctor),
                ("Config", self.show_config),
                ("Workspace", self.open_workspace),
            )
        ):
            btn = QPushButton(label)
            btn.setObjectName("GhostButton")
            btn.clicked.connect(slot)
            util.addWidget(btn, i // 2, i % 2)
        side.addLayout(util)

        self.status_label = QLabel()
        self.status_label.setObjectName("Muted")
        self.status_label.setWordWrap(True)
        side.addWidget(self.status_label)

        
        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        layout.addWidget(main, 1)

        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(24, 12, 24, 12)
        top_layout.setSpacing(10)

        self.mode_pill = QLabel("Agent")
        self.mode_pill.setObjectName("ModePill")
        self.mode_pill.setProperty("tone", "agent")
        top_layout.addWidget(self.mode_pill)

        self.backend_pill = QLabel("Local GGUF")
        self.backend_pill.setObjectName("ModePill")
        self.backend_pill.setProperty("tone", "local")
        top_layout.addWidget(self.backend_pill)

        self.context_pill = QLabel("ctx 4096")
        self.context_pill.setObjectName("ModePill")
        self.context_pill.setProperty("tone", "ctx")
        top_layout.addWidget(self.context_pill)

        self.sandbox_pill = QLabel("sandbox on")
        self.sandbox_pill.setObjectName("Pill")
        top_layout.addWidget(self.sandbox_pill)

        top_layout.addStretch(1)

        self.status_dot = QFrame()
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setProperty("state", "warn")
        top_layout.addWidget(self.status_dot)
        self.task_status = QLabel("Starting…")
        self.task_status.setObjectName("Muted")
        top_layout.addWidget(self.task_status)
        main_layout.addWidget(top_bar)

        
        self.chat_stack = QStackedWidget()
        main_layout.addWidget(self.chat_stack, 1)

        welcome = QWidget()
        welcome_layout = QVBoxLayout(welcome)
        welcome_layout.setContentsMargins(48, 40, 48, 24)
        welcome_layout.addStretch(1)
        hero = QLabel("What should we build?")
        hero.setObjectName("HeroTitle")
        hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(hero)
        hero_sub = QLabel(
            "Codex-style agent loop on your local model — edit the workspace, "
            "run tools, attach files, raise context when you need it."
        )
        hero_sub.setObjectName("HeroSub")
        hero_sub.setWordWrap(True)
        hero_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(hero_sub)
        welcome_layout.addSpacing(20)

        caps = QGridLayout()
        caps.setHorizontalSpacing(12)
        caps.setVerticalSpacing(12)
        for i, (title, body_text) in enumerate(WELCOME_CAPABILITIES):
            card = QFrame()
            card.setObjectName("CapabilityCard")
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(4)
            t = QLabel(title)
            t.setObjectName("CapTitle")
            b = QLabel(body_text)
            b.setObjectName("CapBody")
            b.setWordWrap(True)
            cl.addWidget(t)
            cl.addWidget(b)
            caps.addWidget(card, i // 2, i % 2)
            card.mousePressEvent = (  
                lambda _e, prompt=title: self._welcome_prompt(prompt)
            )
        welcome_layout.addLayout(caps)
        welcome_layout.addStretch(2)
        self.chat_stack.addWidget(welcome)

        self.transcript = QTextEdit()
        self.transcript.setObjectName("Transcript")
        self.transcript.setReadOnly(True)
        self.transcript.setAcceptDrops(True)
        self.transcript.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.transcript.dragEnterEvent = self._transcript_drag_enter  
        self.transcript.dragMoveEvent = self._transcript_drag_move  
        self.transcript.dropEvent = self._transcript_drop  
        self.chat_stack.addWidget(self.transcript)

        
        composer_wrap = QWidget()
        composer_outer = QVBoxLayout(composer_wrap)
        composer_outer.setContentsMargins(28, 4, 28, 18)
        composer_outer.setSpacing(8)

        self.composer_shell = QFrame()
        self.composer_shell.setObjectName("ComposerShell")
        self.composer_shell.setProperty("dragActive", False)
        composer_inner = QVBoxLayout(self.composer_shell)
        composer_inner.setContentsMargins(14, 12, 14, 12)
        composer_inner.setSpacing(8)

        self.attachment_scroll = QScrollArea()
        self.attachment_scroll.setObjectName("AttachmentScroll")
        self.attachment_scroll.setWidgetResizable(True)
        self.attachment_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.attachment_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.attachment_scroll.setFixedHeight(0)
        self.attachment_host = QWidget()
        self.attachment_row = QHBoxLayout(self.attachment_host)
        self.attachment_row.setContentsMargins(0, 0, 0, 0)
        self.attachment_row.setSpacing(8)
        self.attachment_row.addStretch(1)
        self.attachment_scroll.setWidget(self.attachment_host)
        composer_inner.addWidget(self.attachment_scroll)

        self.prompt = PromptTextEdit()
        self.prompt.setObjectName("Prompt")
        self.prompt.setFixedHeight(88)
        self.prompt.setPlaceholderText(
            "Ask the agent to inspect, edit, or build…  @ files via Attach or drop.  Enter to send · Shift+Enter newline"
        )
        self.prompt.submitted.connect(self.send_prompt)
        self.prompt.files_dropped.connect(self.add_attachments)
        composer_inner.addWidget(self.prompt)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.attach_button = QPushButton("+")
        self.attach_button.setObjectName("IconButton")
        self.attach_button.setToolTip("Attach files")
        self.attach_button.clicked.connect(self.browse_attachments)
        footer.addWidget(self.attach_button)
        self.clear_attach_button = QPushButton("Clear")
        self.clear_attach_button.setObjectName("GhostButton")
        self.clear_attach_button.clicked.connect(self.clear_attachments)
        self.clear_attach_button.setEnabled(False)
        footer.addWidget(self.clear_attach_button)
        self.drop_hint = QLabel("Agent · tools · local model · drag files to attach")
        self.drop_hint.setObjectName("DropHint")
        footer.addWidget(self.drop_hint, 1)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("DangerButton")
        self.stop_button.setFixedWidth(84)
        self.stop_button.setMinimumHeight(38)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.cancel_prompt)
        footer.addWidget(self.stop_button)
        self.send_button = QPushButton("Send ↵")
        self.send_button.setObjectName("PrimaryButton")
        self.send_button.setFixedWidth(108)
        self.send_button.setMinimumHeight(38)
        self.send_button.clicked.connect(self.send_prompt)
        footer.addWidget(self.send_button)
        composer_inner.addLayout(footer)
        composer_outer.addWidget(self.composer_shell)
        main_layout.addWidget(composer_wrap)

        self._polish_pills()

    def _panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        return panel

    def _ghost(self, label: str, slot) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("GhostButton")
        btn.clicked.connect(slot)
        return btn

    def _primary(self, label: str, slot) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName("PrimaryButton")
        btn.clicked.connect(slot)
        return btn

    def _button_row(self, *buttons: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        for button in buttons:
            row.addWidget(button)
        return row

    def _spin(self, minimum: int, maximum: int, step: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        return spin

    def _polish_pills(self) -> None:
        for pill in (self.mode_pill, self.backend_pill, self.context_pill, self.sandbox_pill, self.status_dot):
            pill.style().unpolish(pill)
            pill.style().polish(pill)
            pill.update()

    def _set_status(self, text: str, state: str = "ready") -> None:
        self.task_status.setText(text)
        self.status_dot.setProperty("state", state)
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        self.status_dot.update()

    def _toggle_settings_body(self) -> None:
        visible = not self.settings_body.isVisible()
        self.settings_body.setVisible(visible)
        self.settings_toggle.setText("Hide" if visible else "Show")

    def _show_welcome(self) -> None:
        self.chat_stack.setCurrentIndex(0)
        self._has_transcript_content = False

    def _show_transcript(self) -> None:
        self.chat_stack.setCurrentIndex(1)
        self._has_transcript_content = True

    def _welcome_prompt(self, capability: str) -> None:
        prompts = {
            "Read & edit files": "List the workspace and summarize the important files.",
            "Run tools": "What tools do you have available? Show a short summary of each.",
            "Attach context": "Tell me how to attach files for you to review, then wait for my files.",
            "Local only": "Confirm you are running as a local agent and describe the workspace root.",
        }
        self.prompt.setPlainText(prompts.get(capability, capability))
        self.prompt.setFocus()

    
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_composer_drag_active(True)
            return
        super().dragEnterEvent(event)

    def dragLeaveEvent(self, event) -> None:
        self._set_composer_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_composer_drag_active(False)
        if event.mimeData().hasUrls():
            paths = paths_from_mime_urls(event.mimeData().urls())
            if paths:
                self.add_attachments(paths)
                event.acceptProposedAction()
                return
        super().dropEvent(event)

    def _transcript_drag_enter(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_composer_drag_active(True)
        else:
            event.ignore()

    def _transcript_drag_move(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def _transcript_drop(self, event: QDropEvent) -> None:
        self._set_composer_drag_active(False)
        if event.mimeData().hasUrls():
            paths = paths_from_mime_urls(event.mimeData().urls())
            if paths:
                self.add_attachments(paths)
                event.acceptProposedAction()
                return
        event.ignore()

    def _set_composer_drag_active(self, active: bool) -> None:
        self.composer_shell.setProperty("dragActive", active)
        self.composer_shell.style().unpolish(self.composer_shell)
        self.composer_shell.style().polish(self.composer_shell)
        self.composer_shell.update()

    
    def add_attachments(self, paths) -> None:
        added = 0
        existing = {item.path for item in self._attachments}
        for raw in paths:
            path = Path(raw).expanduser().resolve()
            if not path.exists() or not path.is_file() or path in existing:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            self._attachments.append(FileAttachment(path=path, size_bytes=size))
            existing.add(path)
            added += 1
        if added:
            self._render_attachments()
            self._set_status(f"Attached {added} file(s)", "ready")

    def browse_attachments(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Attach files",
            str(workspace_dir()),
            "All files (*.*)",
        )
        if paths:
            self.add_attachments(paths)

    def clear_attachments(self) -> None:
        if not self._attachments:
            return
        self._attachments.clear()
        self._render_attachments()
        self._set_status("Attachments cleared", "ready")

    def remove_attachment(self, path: Path) -> None:
        self._attachments = [item for item in self._attachments if item.path != path]
        self._render_attachments()

    def _render_attachments(self) -> None:
        while self.attachment_row.count():
            item = self.attachment_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for attachment in self._attachments:
            chip = QFrame()
            chip.setObjectName("AttachmentChip")
            chip_layout = QHBoxLayout(chip)
            chip_layout.setContentsMargins(10, 5, 6, 5)
            chip_layout.setSpacing(4)
            size_kb = max(1, attachment.size_bytes // 1024)
            label = QLabel(f"{attachment.label}  ·  {size_kb} KB")
            label.setToolTip(attachment.display_path)
            chip_layout.addWidget(label)
            close = QToolButton()
            close.setObjectName("ChipClose")
            close.setText("×")
            close.clicked.connect(lambda _c=False, p=attachment.path: self.remove_attachment(p))
            chip_layout.addWidget(close)
            self.attachment_row.addWidget(chip)

        self.attachment_row.addStretch(1)
        has_files = bool(self._attachments)
        self.attachment_scroll.setFixedHeight(44 if has_files else 0)
        self.clear_attach_button.setEnabled(has_files)
        self.drop_hint.setText(
            f"{len(self._attachments)} file(s) ready · content inlined on send"
            if has_files
            else "Agent · tools · local model · drag files to attach"
        )

    
    def refresh_models(self) -> None:
        current = self.model_combo.currentText()
        self.model_combo.clear()
        models = [display_model_path(path) for path in discover_gguf_models()]
        self.model_combo.addItems(models)
        if current:
            index = self.model_combo.findText(current)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
        selected = self.model_combo.currentText() or "none"
        selected_name = selected.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        config = load_config()
        self.backend_pill.setText(f"{config.model.backend.upper()} local")
        self._update_mode_pills(config)
        self._update_context_pill()
        self.workspace_path_label.setText(f"Workspace\n{workspace_dir()}")
        self.status_label.setText(
            f"{len(models)} model(s) · selected {selected_name or '—'}\n"
            f"Root {harness_root()}"
        )
        self._polish_pills()

    def _update_mode_pills(self, config: HarnessConfig | None = None) -> None:
        config = config or self._live_config()
        if self.dry_run_check.isChecked():
            self.mode_pill.setText("Dry-run agent")
        else:
            self.mode_pill.setText("Agent")
        self.sandbox_pill.setText("sandbox on" if config.safety.sandbox else "sandbox off")
        if self.self_modify_check.isChecked():
            self.sandbox_pill.setText(self.sandbox_pill.text() + " · self-mod")

    def refresh_sessions(self) -> None:
        current = None
        item = self.session_list.currentItem()
        if item is not None:
            current = item.data(Qt.ItemDataRole.UserRole)
        self.session_list.clear()
        for session in list_sessions()[:40]:
            label = short_session_label(session.session_id)
            row = QListWidgetItem(f"{label}\n{session.session_id[-8:]}")
            row.setData(Qt.ItemDataRole.UserRole, session.session_id)
            row.setToolTip(session.session_id)
            self.session_list.addItem(row)
        if current:
            for i in range(self.session_list.count()):
                if self.session_list.item(i).data(Qt.ItemDataRole.UserRole) == current:
                    self.session_list.setCurrentRow(i)
                    break

    def _session_item_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id:
            self.load_session(session_id)

    def load_session(self, session_id: str) -> None:
        try:
            records = read_session(session_id)
        except Exception as exc:
            QMessageBox.critical(self, "Sessions", str(exc))
            return
        self.clear_output(show_welcome=False)
        self.clear_attachments()
        self._show_transcript()
        for record in records:
            payload = record.get("payload", {})
            if record.get("type") != "message":
                continue
            role = payload.get("role", "event")
            content = payload.get("content", "")
            if role == "user":
                self._append_user(content)
            elif role == "assistant":
                self._append_assistant_header()
                self._append_raw(content + "\n")
                self._close_assistant_turn()
            elif role == "tool":
                self._append_tool(content)
            elif role != "system":
                self._append_system(content)
        self._conversation = None
        self._conversation_config = None
        self._set_status(f"Loaded chat {short_session_label(session_id)}", "ready")

    def load_selected_session(self) -> None:
        item = self.session_list.currentItem()
        if not item:
            QMessageBox.information(self, "CrackStack", "No saved chats found.")
            return
        self.load_session(item.data(Qt.ItemDataRole.UserRole))

    def new_task(self) -> None:
        self._cancel_event.set()
        self._conversation = None
        self._conversation_config = None
        self._cancel_event.clear()
        self._busy = False
        self.send_button.setEnabled(self._preloaded_backend is not None and not self._loading_model)
        self.stop_button.setEnabled(False)
        self.clear_output(show_welcome=True)
        self.clear_attachments()
        self.prompt.clear()
        self._set_status("New chat", "ready" if self._preloaded_backend else "warn")

    def load_settings(self) -> None:
        config = load_config()
        self._syncing_context = True
        self.context_spin.setValue(config.model.context_size)
        self._sync_context_controls(config.model.context_size)
        self.gpu_spin.setValue(config.model.gpu_layers)
        self.max_tokens_spin.setValue(config.model.max_tokens)
        self.temperature_spin.setValue(config.model.temperature)
        self.dry_run_check.setChecked(config.safety.dry_run)
        self.self_modify_check.setChecked(config.safety.self_modify)
        self._syncing_context = False
        self._settings_dirty = False
        self._update_mode_pills(config)
        self._update_context_pill()

    def _tokens_to_slider(self, tokens: int) -> int:
        stepped = max(CONTEXT_SLIDER_MIN_TOKENS, min(CONTEXT_SLIDER_MAX_TOKENS, tokens))
        return max(
            self.context_slider.minimum(),
            min(self.context_slider.maximum(), stepped // CONTEXT_SLIDER_STEP),
        )

    def _slider_to_tokens(self, slider_value: int) -> int:
        return max(CONTEXT_SLIDER_MIN_TOKENS, slider_value * CONTEXT_SLIDER_STEP)

    def _format_context_tokens(self, tokens: int) -> str:
        if tokens >= 1024 and tokens % 1024 == 0:
            return f"{tokens // 1024}K tokens ({tokens})"
        if tokens >= 1024:
            return f"{tokens / 1024:.1f}K tokens ({tokens})"
        return f"{tokens} tokens"

    def _sync_context_controls(self, tokens: int) -> None:
        for index, (_label, preset) in enumerate(CONTEXT_PRESETS):
            if preset == tokens:
                self.context_preset.setCurrentIndex(index)
                break
        else:
            custom_index = next(i for i, (_label, preset) in enumerate(CONTEXT_PRESETS) if preset == 0)
            self.context_preset.setCurrentIndex(custom_index)
        self.context_slider.setValue(self._tokens_to_slider(tokens))
        self.context_value_label.setText(self._format_context_tokens(tokens))

    def _context_preset_changed(self, _index: int = 0) -> None:
        if self._syncing_context:
            return
        label = self.context_preset.currentText()
        for preset_label, value in CONTEXT_PRESETS:
            if preset_label == label and value > 0:
                self._syncing_context = True
                self.context_spin.setValue(value)
                self._sync_context_controls(value)
                self._syncing_context = False
                self._settings_changed()
                return

    def _context_slider_changed(self, value: int = 0) -> None:
        if self._syncing_context:
            return
        tokens = self._slider_to_tokens(value)
        self._syncing_context = True
        self.context_spin.setValue(tokens)
        self._sync_context_controls(tokens)
        self._syncing_context = False
        self._settings_changed()

    def _context_spin_changed(self, _value: int = 0) -> None:
        if self._syncing_context:
            return
        tokens = self.context_spin.value()
        self._syncing_context = True
        self._sync_context_controls(tokens)
        self._syncing_context = False
        self._update_context_pill()

    def _settings_changed(self, *_args) -> None:
        self._settings_dirty = True
        self._conversation = None
        self._conversation_config = None
        self._preloaded_backend = None
        self._preloaded_config = None
        self._update_mode_pills()
        self._update_context_pill()
        if not self._loading_model and not self._busy:
            self.send_button.setEnabled(False)
            self._set_status("Settings changed — save & reload", "warn")

    def _update_context_pill(self) -> None:
        value = self.context_spin.value()
        dirty = " ·" if self._settings_dirty else ""
        if value >= 1024 and value % 1024 == 0:
            self.context_pill.setText(f"{value // 1024}K ctx{dirty}")
        else:
            self.context_pill.setText(f"ctx {value}{dirty}")
        if hasattr(self, "context_value_label"):
            self.context_value_label.setText(self._format_context_tokens(value))
        self._polish_pills()

    def _live_config(self) -> HarnessConfig:
        config = load_config()
        return HarnessConfig(
            model=ModelConfig(
                backend=config.model.backend,
                path=config.model.path,
                context_size=self.context_spin.value(),
                gpu_layers=self.gpu_spin.value(),
                temperature=self.temperature_spin.value(),
                max_tokens=self.max_tokens_spin.value(),
            ),
            workspace=config.workspace,
            safety=SafetyConfig(
                self_modify=self.self_modify_check.isChecked(),
                sandbox=config.safety.sandbox,
                allow_outside_workspace=config.safety.allow_outside_workspace,
                dry_run=self.dry_run_check.isChecked(),
                max_file_bytes=config.safety.max_file_bytes,
                max_search_matches=config.safety.max_search_matches,
            ),
        )

    def save_settings(self) -> None:
        config = self._live_config()
        save_config(config)
        self._settings_dirty = False
        self._conversation = None
        self._conversation_config = None
        self._preloaded_backend = None
        self._preloaded_config = None
        self._update_context_pill()
        self._append_system(
            f"Settings saved — reloading local model (context={config.model.context_size})"
        )
        self.refresh_models()
        self.preload_model()

    def select_current_model(self) -> None:
        value = self.model_combo.currentText()
        if not value:
            QMessageBox.information(self, "CrackStack", "Put a .gguf file in models/ first.")
            return
        try:
            result = select_model(value)
        except Exception as exc:
            QMessageBox.critical(self, "Config", str(exc))
            return
        self._append_system(result)
        self._conversation = None
        self._conversation_config = None
        self._preloaded_backend = None
        self._preloaded_config = None
        self.run_doctor()
        self.preload_model()

    def preload_model(self) -> None:
        if self._loading_model:
            return
        config = self._live_config()
        self._loading_model = True
        self._set_status("Loading local model…", "busy")
        self.send_button.setEnabled(False)
        worker = ModelLoadWorker(config)
        worker.signals.loaded.connect(lambda backend, name, cfg=config: self._model_loaded(backend, name, cfg))
        worker.signals.error.connect(self._model_load_error)
        worker.signals.finished.connect(self._model_load_finished)
        self.thread_pool.start(worker)

    def _model_loaded(self, backend, model_name: str, config: HarnessConfig) -> None:
        if config != self._live_config():
            return
        self._preloaded_backend = backend
        self._preloaded_config = config
        self._conversation = None
        self._conversation_config = config
        self._settings_dirty = False
        self._loaded_model_name = model_name
        self._update_context_pill()
        short = model_name if len(model_name) < 36 else model_name[:33] + "…"
        self.backend_pill.setText(short)
        self._set_status("Ready · local agent", "ready")
        self._polish_pills()

    def _model_load_error(self, text: str) -> None:
        self._preloaded_backend = None
        self._preloaded_config = None
        self._set_status("Model not loaded", "error")
        hint = ""
        lowered = text.lower()
        if "llama_context" in lowered or "context_size" in lowered or "vram" in lowered:
            hint = (
                "\n\nQuick fix: set Context preset to 4K or 8K (this 14B model rarely fits "
                "32K–128K with GPU offload on laptop VRAM), then click Save & reload model. "
                "If it still fails, lower GPU layers (try 16 or 0)."
            )
        self._append_error(f"Could not load local model: {text}{hint}")

    def _model_load_finished(self) -> None:
        self._loading_model = False
        if not self._busy:
            self.send_button.setEnabled(self._preloaded_backend is not None)

    def run_doctor(self, _checked: bool = False, append: bool = True) -> None:
        try:
            text = format_checks(run_checks(load_config()))
        except Exception as exc:
            text = f"doctor failed: {exc}"
        if append:
            self._append_system("[doctor]\n" + text)
        if "missing" in text.lower() or "failed" in text.lower():
            self._set_status("Check local setup", "warn")

    def show_tools(self) -> None:
        registry = self._registry(load_config())
        lines = [f"• {spec['name']} — {spec['description']}" for spec in registry.specs()]
        self._append_tool("Available tools\n" + "\n".join(lines))

    def show_config(self) -> None:
        try:
            text = show_config()
        except Exception as exc:
            text = f"config failed: {exc}"
        self._append_system("[config]\n" + text)

    def open_workspace(self) -> None:
        path = workspace_dir()
        path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                __import__("os").startfile(str(path))  
            elif sys.platform == "darwin":
                import subprocess

                subprocess.Popen(["open", str(path)])
            else:
                import subprocess

                subprocess.Popen(["xdg-open", str(path)])
            self._append_system(f"Opened workspace: {path}")
        except Exception as exc:
            self._append_error(f"Could not open workspace: {exc}")

    def send_prompt(self) -> None:
        text = self.prompt.toPlainText().strip()
        if not text and not self._attachments:
            return
        if not text and self._attachments:
            text = "Please review the attached files and help with the coding task."
        if self._loading_model:
            self._append_system("Model is still loading — wait until status is Ready.")
            return
        if self._settings_dirty or self._preloaded_backend is None:
            self._append_system("Settings changed or model not loaded — click Save & reload model.")
            return

        config = self._conversation_config or self._live_config()
        max_bytes = min(config.safety.max_file_bytes or DEFAULT_ATTACHMENT_BYTES, DEFAULT_ATTACHMENT_BYTES)
        composed = build_prompt_with_attachments(
            text,
            list(self._attachments),
            max_file_bytes=max_bytes,
        )
        display_text = text
        if self._attachments:
            names = ", ".join(item.label for item in self._attachments)
            display_text = f"{text}\n\n📎 {names}"

        self.prompt.clear()
        self.clear_attachments()
        self._cancel_event.clear()
        self._busy = True
        self.send_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._set_status("Agent running…", "busy")
        self._append_user(display_text)
        self._append_assistant_header()
        self._conversation_config = config
        worker = PromptWorker(self, composed, config)
        worker.signals.chunk.connect(self._append_raw)
        worker.signals.error.connect(self._append_error)
        worker.signals.tool.connect(self._append_tool)
        worker.signals.finished.connect(self._prompt_finished)
        self.thread_pool.start(worker)

    def cancel_prompt(self) -> None:
        if self._busy:
            self._cancel_event.set()
            self.stop_button.setEnabled(False)
            self._append_system("Stop requested — waiting for the current step to yield.")
            self._set_status("Stopping…", "warn")

    def _prompt_finished(self) -> None:
        self._busy = False
        self.send_button.setEnabled(self._preloaded_backend is not None and not self._settings_dirty)
        self.stop_button.setEnabled(False)
        if self._preloaded_backend is not None:
            self._set_status("Ready · local agent", "ready")
        else:
            self._set_status("Ready", "warn")
        self._close_assistant_turn()
        self.refresh_sessions()

    def clear_output(self, show_welcome: bool = False) -> None:
        self.transcript.clear()
        self._assistant_turn_open = False
        if show_welcome:
            self._show_welcome()
        else:
            self._show_transcript()

    def conversation(
        self,
        tool_signal: Signal | None = None,
        config: HarnessConfig | None = None,
    ) -> Conversation:
        if self._conversation is not None:
            return self._conversation
        config = config or self._conversation_config or self._live_config()
        self._conversation_config = config
        if self._preloaded_backend is not None and self._preloaded_config == config:
            backend = self._preloaded_backend
        else:
            backend = create_backend(config.model)
        registry = self._registry(config)
        store = ConversationStore()

        def tool_log(kind: str, message: str) -> None:
            log_tool_event(store.session_id, kind, message)
            text = f"[tool:{kind}] {message}"
            if tool_signal is not None:
                tool_signal.emit(text)
            else:
                self._append_tool(text)

        self._conversation = Conversation(
            backend=backend,
            generate_config=GenerateConfig(
                max_tokens=config.model.max_tokens,
                temperature=config.model.temperature,
            ),
            tools=registry,
            tool_observer=tool_log,
            cancel_checker=self._cancel_event.is_set,
            context_manager=ContextManager(context_window=config.model.context_size),
            store=store,
        )
        return self._conversation

    def _registry(self, config) -> ToolRegistry:
        registry = ToolRegistry()
        register_filesystem_tools(registry, config)
        register_packaging_tools(registry, config)
        load_generated_tools(
            plugins_dir() / "generated_tools",
            registry,
            sandbox=config.safety.sandbox,
        )
        register_self_modify_tools(registry, config)
        return registry

    
    def _ensure_transcript_visible(self) -> None:
        if not self._has_transcript_content:
            self._show_transcript()

    def _append_html(self, html: str, trailing_blocks: int = 0) -> None:
        self._ensure_transcript_visible()
        self.transcript.moveCursor(QTextCursor.MoveOperation.End)
        cursor = self.transcript.textCursor()
        cursor.insertHtml(html)
        for _ in range(trailing_blocks):
            cursor.insertBlock()
        self.transcript.setTextCursor(cursor)
        self.transcript.ensureCursorVisible()

    def _append_plain(self, text: str, trailing_blocks: int = 0) -> None:
        self._ensure_transcript_visible()
        self.transcript.moveCursor(QTextCursor.MoveOperation.End)
        cursor = self.transcript.textCursor()
        cursor.insertText(text)
        for _ in range(trailing_blocks):
            cursor.insertBlock()
        self.transcript.setTextCursor(cursor)
        self.transcript.ensureCursorVisible()

    def _close_assistant_turn(self) -> None:
        if self._assistant_turn_open:
            self._append_plain("", trailing_blocks=2)
            self._assistant_turn_open = False

    def _append_user(self, text: str) -> None:
        self._close_assistant_turn()
        self._append_html(
            "<table width='100%' cellspacing='0' cellpadding='0' style='margin:0 0 14px 0;'>"
            "<tr><td align='right'>"
            "<div style='display:inline-block;max-width:82%;text-align:left;'>"
            "<div style='color:#8b8b96;font-size:11px;font-weight:650;margin:0 0 6px 4px;'>You</div>"
            f"<div style='background:#1a1f2e;border:1px solid #2a3a55;border-radius:14px 14px 4px 14px;"
            f"padding:12px 14px;color:#f1f5f9;white-space:pre-wrap;line-height:1.45;'>{self._escape(text)}</div>"
            "</div></td></tr></table>",
            trailing_blocks=1,
        )

    def _append_assistant_header(self) -> None:
        self._close_assistant_turn()
        self._append_html(
            "<div style='margin:8px 0 6px 0;'>"
            "<span style='color:#86efac;font-size:11px;font-weight:700;letter-spacing:0.4px;'>AGENT</span>"
            "<span style='color:#5b5b66;font-size:11px;'> · local</span>"
            "</div>",
            trailing_blocks=0,
        )
        self._assistant_turn_open = True

    def _append_system(self, text: str) -> None:
        self._close_assistant_turn()
        self._append_html(
            f"<div style='margin:8px 0 12px 0;padding:10px 12px;border-radius:10px;"
            f"background:#121214;border:1px solid #232329;color:#8b8b96;"
            f"font-family:Consolas,monospace;font-size:11px;white-space:pre-wrap;'>"
            f"{self._escape(text)}</div>",
            trailing_blocks=1,
        )

    def _append_tool(self, text: str) -> None:
        self._close_assistant_turn()
        
        title = "Tool"
        body = text
        if text.startswith("[tool:"):
            end = text.find("]")
            if end > 0:
                title = text[1:end]
                body = text[end + 1 :].lstrip()
        self._append_html(
            f"<div style='margin:8px 0 12px 0;border-radius:12px;overflow:hidden;"
            f"border:1px solid #2a3320;background:#10140e;'>"
            f"<div style='padding:7px 12px;background:#162014;color:#a3e635;"
            f"font-size:11px;font-weight:700;letter-spacing:0.3px;'>{self._escape(title)}</div>"
            f"<pre style='margin:0;padding:10px 12px;color:#d9f99d;white-space:pre-wrap;"
            f"font-family:Consolas,monospace;font-size:11px;'>"
            f"{self._escape(body)}</pre></div>",
            trailing_blocks=1,
        )

    def _append_error(self, text: str) -> None:
        self._set_status("Error", "error")
        self._close_assistant_turn()
        self._append_html(
            f"<div style='margin:8px 0 12px 0;padding:12px 14px;border-radius:12px;"
            f"background:#1a1012;border:1px solid #4a2228;color:#fca5a5;"
            f"white-space:pre-wrap;font-family:Consolas,monospace;font-size:11px;'>"
            f"{self._escape(text)}</div>",
            trailing_blocks=1,
        )

    def _append_raw(self, text: str) -> None:
        
        if not self._assistant_turn_open:
            self._append_assistant_header()
        self._append_plain(text)

    def _escape(self, text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )


def main() -> int:
    ensure_base_dirs()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)
    window = HarnessWindow()
    window.show()
    return app.exec()
