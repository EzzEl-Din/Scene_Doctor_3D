"""
main.py — Maya Scene Doctor AI  (V3 — Multi-Agent)
PySide2/PySide6 UI that wires scanner.py + ai_backend.py into a Maya panel.

Built by Ezz El-Din | LinkedIn: https://www.linkedin.com/in/ezzel-din-tarek-mostafa

Usage (Maya Script Editor):
    import main
    main.show()
"""

import os
import json
import base64
import tempfile
import re

import maya.cmds as cmds
import maya.mel as mel

try:
    from PySide2.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit,
        QDialog, QFormLayout, QComboBox, QDialogButtonBox,
        QScrollArea, QSizePolicy, QFrame, QTextEdit, QApplication,
        QTabWidget, QRadioButton, QButtonGroup, QGroupBox,
    )
    from PySide2.QtCore import Qt, QTimer, QBuffer, QIODevice, Signal
    from PySide2.QtGui  import QFont, QColor, QPalette, QTextCursor, QImage, QPixmap
except ImportError:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit,
        QDialog, QFormLayout, QComboBox, QDialogButtonBox,
        QScrollArea, QSizePolicy, QFrame, QTextEdit, QApplication,
        QTabWidget, QRadioButton, QButtonGroup, QGroupBox,
    )
    from PySide6.QtCore import Qt, QTimer, QBuffer, QIODevice, Signal
    from PySide6.QtGui  import QFont, QColor, QPalette, QTextCursor, QImage, QPixmap

# Local modules — must be in the same folder / on sys.path
from scanner    import scan_to_prompt, run_scan
from ai_backend import (
    StreamWorker, SummaryWorker, DEFAULT_SETTINGS,
    migrate_settings, AGENT_PROMPTS, AGENT_TOOLTIPS, AGENT_LABELS,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _chat_dir():
    """Folder where chat JSON files are saved (same folder as the scene)."""
    scene = cmds.file(q=True, sceneName=True)
    if scene:
        return os.path.dirname(scene)
    # Fallback: Maya's projects folder
    return cmds.workspace(q=True, rootDirectory=True)


def _chat_path(scene_path=None):
    """Return the JSON path for the current (or given) scene."""
    scene = scene_path or cmds.file(q=True, sceneName=True)
    if not scene:
        return None
    base = os.path.splitext(scene)[0]
    return base + "_chat.json"


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------

class ChatLineEdit(QLineEdit):
    pasted_image = Signal(QImage)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_V and (event.modifiers() & Qt.ControlModifier):
            clipboard = QApplication.clipboard()
            mime = clipboard.mimeData()
            if mime.hasImage():
                image = clipboard.image()
                if not image.isNull():
                    self.pasted_image.emit(image)
                    return
        super().keyPressEvent(event)


class SettingsDialog(QDialog):
    """Settings dialog with Single / Multi agent mode selector."""

    _AGENTS = ("analyzer", "codewriter", "vision", "summary")

    _DIALOG_STYLE = """
        QDialog {
            background-color: #1e1e1e;
            color: #d4d4d4;
            font-family: "Segoe UI", Arial, sans-serif;
            font-size: 13px;
        }
        QGroupBox {
            font-weight: bold;
            font-size: 12px;
            color: #aaa;
            border: 1px solid #3a3a3a;
            border-radius: 6px;
            margin-top: 8px;
            padding: 12px 10px 8px 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: #ccc;
        }
        QRadioButton {
            color: #d4d4d4;
            spacing: 6px;
            font-size: 13px;
            font-weight: normal;
        }
        QRadioButton::indicator {
            width: 14px;
            height: 14px;
        }
        QLineEdit {
            background-color: #2d2d2d;
            border: 1px solid #444;
            border-radius: 4px;
            padding: 5px 8px;
            color: #d4d4d4;
            font-size: 13px;
        }
        QLineEdit:focus {
            border-color: #1a73e8;
        }
        QTabWidget::pane {
            border: 1px solid #3a3a3a;
            border-radius: 4px;
            background: #252526;
        }
        QTabBar::tab {
            background: #2a2a2a;
            color: #999;
            padding: 6px 12px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            font-size: 12px;
        }
        QTabBar::tab:selected {
            background: #252526;
            color: #d4d4d4;
        }
        QTabBar::tab:hover {
            color: #fff;
        }
        QPushButton {
            background-color: #3a3a3a;
            color: #ccc;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 6px 14px;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QDialogButtonBox QPushButton {
            min-width: 70px;
        }
        QTextEdit {
            background-color: #2d2d2d;
            border: 1px solid #444;
            border-radius: 4px;
            color: #d4d4d4;
        }
        QLabel {
            color: #d4d4d4;
            font-weight: normal;
        }
    """

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Agent Settings")
        self.setMinimumWidth(480)
        self.setStyleSheet(self._DIALOG_STYLE)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        self._settings = {}
        for key in self._AGENTS:
            self._settings[key] = dict(settings.get(key, {}))
        self._mode = settings.get("mode", "single")
        self._single_cfg = dict(settings.get("single", {}))

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── AI Mode toggle ------------------------------------------------
        mode_group = QGroupBox("AI Mode")
        mode_row = QHBoxLayout(mode_group)
        mode_row.setContentsMargins(10, 4, 10, 6)
        self._mode_single = QRadioButton("Single Agent")
        self._mode_multi  = QRadioButton("Multi Agent")
        mode_btn_group = QButtonGroup(self)
        mode_btn_group.addButton(self._mode_single)
        mode_btn_group.addButton(self._mode_multi)
        if self._mode == "multi":
            self._mode_multi.setChecked(True)
        else:
            self._mode_single.setChecked(True)
        mode_row.addWidget(self._mode_single)
        mode_row.addWidget(self._mode_multi)
        mode_row.addStretch()
        layout.addWidget(mode_group)

        # ── Backend toggle (shared by both modes) -------------------------
        backend_group = QGroupBox("Backend")
        backend_row = QHBoxLayout(backend_group)
        backend_row.setContentsMargins(10, 4, 10, 6)
        self._backend_ollama = QRadioButton("Local (Ollama)")
        self._backend_api    = QRadioButton("External API")
        backend_btn_group = QButtonGroup(self)
        backend_btn_group.addButton(self._backend_ollama)
        backend_btn_group.addButton(self._backend_api)
        init_backend = self._single_cfg.get("backend", "")
        if not init_backend:
            init_backend = self._settings.get("analyzer", {}).get("backend", "ollama")
        if init_backend == "openai":
            self._backend_api.setChecked(True)
        else:
            self._backend_ollama.setChecked(True)
        backend_row.addWidget(self._backend_ollama)
        backend_row.addWidget(self._backend_api)
        backend_row.addStretch()
        layout.addWidget(backend_group)

        # ── Single Agent fields -------------------------------------------
        self._single_widget = QGroupBox("Single Agent")
        single_form = QFormLayout(self._single_widget)
        single_form.setSpacing(8)
        single_form.setContentsMargins(10, 8, 10, 8)

        s = self._single_cfg if self._single_cfg else self._settings.get("analyzer", {})
        self._s_url = QLineEdit(s.get("base_url", ""))
        self._s_url.setPlaceholderText("http://localhost:11434")
        single_form.addRow("Base URL:", self._s_url)

        self._s_key = QLineEdit(s.get("api_key", ""))
        self._s_key.setPlaceholderText("sk-... (leave blank for Ollama)")
        self._s_key.setEchoMode(QLineEdit.Password)
        single_form.addRow("API Key:", self._s_key)

        self._s_model = QLineEdit(s.get("model", "llama3"))
        self._s_model.setPlaceholderText("llama3 / gpt-4o / mistral ...")
        single_form.addRow("Model:", self._s_model)

        layout.addWidget(self._single_widget)

        # ── Multi Agent section -------------------------------------------
        self._multi_widget = QGroupBox("Multi Agent")
        multi_layout = QVBoxLayout(self._multi_widget)
        multi_layout.setContentsMargins(6, 8, 6, 8)
        multi_layout.setSpacing(6)

        self._tabs = QTabWidget()
        self._agent_widgets = {}

        for agent_key in self._AGENTS:
            tab, widgets = self._build_agent_tab(agent_key)
            label = AGENT_LABELS.get(agent_key, agent_key)
            self._tabs.addTab(tab, label)
            self._agent_widgets[agent_key] = widgets

        # Advanced tab (system prompts)
        adv_tab, self._prompt_edits = self._build_advanced_tab()
        self._tabs.addTab(adv_tab, "⚙ Advanced")

        multi_layout.addWidget(self._tabs)

        # Copy-to-all button
        copy_btn = QPushButton("📋 Copy to all agents")
        copy_btn.setToolTip("Copy current tab's URL / key / model to every agent")
        copy_btn.clicked.connect(self._copy_to_all)
        multi_layout.addWidget(copy_btn)

        layout.addWidget(self._multi_widget)

        # ── OK / Cancel ---------------------------------------------------
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Wire mode toggle
        self._mode_single.toggled.connect(self._on_mode_changed)
        self._on_mode_changed()

    # ---- mode switch -----------------------------------------------------
    def _on_mode_changed(self):
        is_single = self._mode_single.isChecked()
        self._single_widget.setVisible(is_single)
        self._multi_widget.setVisible(not is_single)
        # Resize dialog to fit the visible content
        self.layout().activate()
        self.setFixedHeight(self.sizeHint().height())
        # Allow horizontal resize but lock height to content
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)  # reset max after a brief moment
        from functools import partial
        try:
            QTimer.singleShot(50, partial(self.setFixedHeight, self.sizeHint().height()))
        except Exception:
            pass

    # ---- build one agent tab ---------------------------------------------
    def _build_agent_tab(self, agent_key):
        widget = QWidget()
        form = QFormLayout(widget)
        form.setSpacing(10)
        s = self._settings[agent_key]

        url_input = QLineEdit(s.get("base_url", ""))
        url_input.setPlaceholderText("http://localhost:11434")
        form.addRow("Base URL:", url_input)

        key_input = QLineEdit(s.get("api_key", ""))
        key_input.setPlaceholderText("sk-... (leave blank for Ollama)")
        key_input.setEchoMode(QLineEdit.Password)
        form.addRow("API Key:", key_input)

        model_input = QLineEdit(s.get("model", "llama3"))
        model_input.setPlaceholderText("llama3 / gpt-4o / mistral ...")
        model_input.setToolTip(AGENT_TOOLTIPS.get(agent_key, ""))
        form.addRow("Model:", model_input)

        # Tooltip hint label
        hint = QLabel(AGENT_TOOLTIPS.get(agent_key, ""))
        hint.setStyleSheet("color: #888; font-size: 11px; font-style: italic;")
        hint.setWordWrap(True)
        form.addRow("", hint)

        return widget, {
            "url": url_input,
            "key": key_input,
            "model": model_input,
        }

    # ---- Advanced tab (system prompts) -----------------------------------
    def _build_advanced_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        note = QLabel("Edit system prompts for each agent. Leave blank to use defaults.")
        note.setStyleSheet("color: #aaa; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        prompt_edits = {}
        for agent_key in self._AGENTS:
            label = QLabel(AGENT_LABELS.get(agent_key, agent_key))
            label.setStyleSheet("font-weight: bold; margin-top: 6px;")
            layout.addWidget(label)

            edit = QTextEdit()
            current = self._settings[agent_key].get("system_prompt", "")
            default = AGENT_PROMPTS.get(agent_key, "")
            edit.setPlainText(current if current else default)
            edit.setFixedHeight(70)
            edit.setStyleSheet("font-size: 11px;")
            layout.addWidget(edit)
            prompt_edits[agent_key] = edit

        reset_btn = QPushButton("↻ Reset All Prompts to Defaults")
        reset_btn.clicked.connect(lambda: self._reset_prompts(prompt_edits))
        layout.addWidget(reset_btn)
        layout.addStretch()
        return widget, prompt_edits

    def _reset_prompts(self, edits):
        for key, edit in edits.items():
            edit.setPlainText(AGENT_PROMPTS.get(key, ""))

    # ---- Copy current tab settings to all agents -------------------------
    def _copy_to_all(self):
        current_idx = self._tabs.currentIndex()
        agent_keys = list(self._AGENTS)
        if current_idx >= len(agent_keys):
            return  # Advanced tab selected, nothing to copy
        src_key = agent_keys[current_idx]
        src = self._agent_widgets[src_key]
        for agent_key in self._AGENTS:
            if agent_key == src_key:
                continue
            dst = self._agent_widgets[agent_key]
            dst["url"].setText(src["url"].text())
            dst["key"].setText(src["key"].text())
            dst["model"].setText(src["model"].text())

    # ---- get current backend string --------------------------------------
    def _current_backend(self):
        return "ollama" if self._backend_ollama.isChecked() else "openai"

    # ---- Save ------------------------------------------------------------
    def _save(self):
        is_single = self._mode_single.isChecked()
        backend = self._current_backend()

        if is_single:
            # Save single-agent fields
            self._settings["mode"] = "single"
            self._settings["single"] = {
                "backend":  backend,
                "base_url": self._s_url.text().strip(),
                "api_key":  self._s_key.text().strip(),
                "model":    self._s_model.text().strip(),
            }
            # Propagate single settings to all agents internally
            for agent_key in self._AGENTS:
                self._settings[agent_key] = {
                    "backend":  backend,
                    "base_url": self._s_url.text().strip(),
                    "api_key":  self._s_key.text().strip(),
                    "model":    self._s_model.text().strip(),
                    "system_prompt": self._prompt_edits[agent_key].toPlainText().strip(),
                }
        else:
            # Save per-agent settings
            self._settings["mode"] = "multi"
            for agent_key in self._AGENTS:
                w = self._agent_widgets[agent_key]
                self._settings[agent_key] = {
                    "backend":  backend,
                    "base_url": w["url"].text().strip(),
                    "api_key":  w["key"].text().strip(),
                    "model":    w["model"].text().strip(),
                    "system_prompt": self._prompt_edits[agent_key].toPlainText().strip(),
                }
        self.accept()

    def get_settings(self):
        return self._settings

# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class SceneDoctorWindow(QWidget):

    # Accent colours per agent
    _AGENT_COLORS = {
        "analyzer":   "#4ec9b0",
        "codewriter": "#e8a838",
        "vision":     "#c586c0",
        "user":       "#1a73e8",
        "system":     "#666666",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Maya Scene Doctor AI  (V3)")
        self.setMinimumSize(520, 640)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAcceptDrops(True)

        # State
        self._settings         = self._load_global_settings()
        self._messages         = []       # unified chat (saved to disk)
        self._display_items    = []
        self._stream_worker    = None
        self._stream_label     = None
        self._search_mode      = False
        self._current_scene    = ""
        self._assistant_buffer = ""
        self._agentic_iter     = 0
        self._current_agent    = None     # which agent is currently streaming
        self._pending_chain    = None     # callback after current agent finishes
        self._last_scan_data   = {}

        # Per-agent message histories (not saved to disk)
        self._analyzer_history   = []
        self._codewriter_history = []
        self._vision_history     = []

        # Context management
        self._msg_count_since_summary = 0
        self._summary_worker = None

        self._build_ui()
        self._apply_stylesheet()
        self._register_scene_callbacks()

        # Load chat for the currently open scene
        self._on_scene_changed()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Top bar ───────────────────────────────────────────────────
        top = QHBoxLayout()

        self._scene_label = QLabel("Scene: (untitled)")
        self._scene_label.setObjectName("sceneLabel")
        top.addWidget(self._scene_label, stretch=1)

        settings_btn = QPushButton("⚙  Settings")
        settings_btn.setObjectName("smallBtn")
        settings_btn.setFixedWidth(100)
        settings_btn.clicked.connect(self._open_settings)
        top.addWidget(settings_btn)

        root.addLayout(top)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("divider")
        root.addWidget(line)

        # ── Chat display ──────────────────────────────────────────────
        # QScrollArea containing a vertical list of message rows
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setObjectName("chatScroll")

        self._chat_container = QWidget()
        self._chat_container.setObjectName("chatContainer")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setSpacing(4)
        self._chat_layout.setContentsMargins(8, 8, 8, 8)
        self._chat_layout.addStretch()          # pushes messages to top

        self._scroll.setWidget(self._chat_container)
        root.addWidget(self._scroll, stretch=1)

        # ── Input row & Preview ───────────────────────────────────────
        input_vbox = QVBoxLayout()
        input_vbox.setSpacing(4)
        
        self._preview_container = QWidget()
        self._preview_container.setVisible(False)
        prev_layout = QHBoxLayout(self._preview_container)
        prev_layout.setContentsMargins(0, 0, 0, 0)
        
        self._preview_lbl = QLabel()
        self._preview_lbl.setFixedSize(64, 64)
        self._preview_lbl.setStyleSheet("background-color: #333; border: 1px solid #555; border-radius: 4px;")
        self._preview_lbl.setAlignment(Qt.AlignCenter)
        prev_layout.addWidget(self._preview_lbl)
        
        self._preview_warning = QLabel("")
        self._preview_warning.setStyleSheet("color: #d97706; font-size: 11px;")
        prev_layout.addWidget(self._preview_warning)
        
        prev_layout.addStretch()
        
        clear_img_btn = QPushButton("✕")
        clear_img_btn.setFixedSize(24, 24)
        clear_img_btn.setStyleSheet("background-color: transparent; color: #888; border: none; font-weight: bold;")
        clear_img_btn.clicked.connect(self._clear_pending_image)
        prev_layout.addWidget(clear_img_btn)
        
        input_vbox.addWidget(self._preview_container)

        self._search_lbl = QLabel("🔍 Search mode active")
        self._search_lbl.setStyleSheet("color: #4ec9b0; font-size: 11px; font-weight: bold;")
        self._search_lbl.setVisible(False)
        input_vbox.addWidget(self._search_lbl)

        BOTTOM_HEIGHT = 36

        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        input_row.setContentsMargins(8, 8, 8, 8)

        self._input = ChatLineEdit()
        self._input.setPlaceholderText("Ask a follow-up question...")
        self._input.setObjectName("inputField")
        self._input.setFixedHeight(BOTTOM_HEIGHT)
        self._input.returnPressed.connect(self._send_message)
        self._input.pasted_image.connect(self._on_image_pasted)
        input_row.addWidget(self._input, stretch=1)

        self._search_btn = QPushButton("🔍")
        self._search_btn.setObjectName("smallBtn")
        self._search_btn.setFixedHeight(BOTTOM_HEIGHT)
        self._search_btn.setFixedWidth(BOTTOM_HEIGHT)
        self._search_btn.setCheckable(True)
        self._search_btn.setToolTip("Search mode — AI will search Gumroad, GitHub, and 80 Level")
        self._search_btn.clicked.connect(self._toggle_search_mode)
        input_row.addWidget(self._search_btn)

        self._screenshot_btn = QPushButton("📷")
        self._screenshot_btn.setObjectName("smallBtn")
        self._screenshot_btn.setFixedHeight(BOTTOM_HEIGHT)
        self._screenshot_btn.setFixedWidth(BOTTOM_HEIGHT)
        self._screenshot_btn.setToolTip("Take Viewport Screenshot")
        self._screenshot_btn.clicked.connect(self._take_viewport_screenshot)
        input_row.addWidget(self._screenshot_btn)

        self._send_btn = QPushButton("Send")
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.setFixedHeight(BOTTOM_HEIGHT)
        self._send_btn.setFixedWidth(72)
        self._send_btn.clicked.connect(self._send_message)
        input_row.addWidget(self._send_btn)

        input_vbox.addLayout(input_row)
        root.addLayout(input_vbox)

        # ── Action buttons ────────────────────────────────────────────
        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        self._scan_btn = QPushButton("🔍  Scan Scene")
        self._scan_btn.setObjectName("scanBtn")
        self._scan_btn.clicked.connect(self._scan_scene)
        action_row.addWidget(self._scan_btn)

        clear_btn = QPushButton("Clear Chat")
        clear_btn.setObjectName("smallBtn")
        clear_btn.setFixedWidth(90)
        clear_btn.clicked.connect(self._clear_chat)
        action_row.addWidget(clear_btn)

        credit_label = QLabel('Built by <b>Ezz El-Din</b> | <a href="https://www.linkedin.com/in/ezzel-din-tarek-mostafa" style="color: #4ec9b0; text-decoration: none;">LinkedIn</a>')
        credit_label.setOpenExternalLinks(True)
        credit_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        action_row.addWidget(credit_label, stretch=1)

        root.addLayout(action_row)

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }
            #sceneLabel {
                color: #888;
                font-size: 12px;
            }
            #divider {
                color: #333;
            }
            #chatScroll {
                background-color: #252526;
                border: 1px solid #333;
                border-radius: 6px;
            }
            #chatContainer {
                background-color: #252526;
            }
            #msgBubble {
                background-color: #2a2a2a;
                border-radius: 6px;
            }
            #inputField {
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 10px;
                color: #d4d4d4;
            }
            #inputField:focus {
                border-color: #1a73e8;
            }
            #sendBtn {
                background-color: #1a73e8;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 0 8px;
                font-size: 13px;
                font-weight: bold;
            }
            #sendBtn:hover    { background-color: #1558b0; }
            #sendBtn:disabled { background-color: #555; color: #888; }
            #scanBtn {
                background-color: #2d6a4f;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            #scanBtn:hover    { background-color: #1e4d37; }
            #scanBtn:disabled { background-color: #555; color: #888; }
            #smallBtn {
                background-color: #3a3a3a;
                color: #ccc;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 0 8px;
                font-size: 13px;
                min-width: 36px;
            }
            #smallBtn:hover { background-color: #4a4a4a; }
        """)

    # ------------------------------------------------------------------
    # Maya scene callbacks
    # ------------------------------------------------------------------

    def _register_scene_callbacks(self):
        """Register Maya scriptJobs to detect scene changes."""
        self._job_ids = []
        for event in ("SceneOpened", "NewSceneOpened", "SceneSaved"):
            jid = cmds.scriptJob(event=[event, self._on_scene_changed])
            self._job_ids.append(jid)

    def _unregister_scene_callbacks(self):
        for jid in getattr(self, "_job_ids", []):
            try:
                cmds.scriptJob(kill=jid, force=True)
            except Exception:
                pass

    def closeEvent(self, event):
        self._unregister_scene_callbacks()
        if self._stream_worker and self._stream_worker.isRunning():
            self._stream_worker.stop()
            self._stream_worker.wait(1000)
        if self._summary_worker and self._summary_worker.isRunning():
            self._summary_worker.wait(1000)
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Drag & Drop images
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event):
        if event.mimeData().hasImage() or event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            path = event.mimeData().urls()[0].toLocalFile()
            if path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tga')):
                image = QImage(path)
                if not image.isNull():
                    self._set_pending_image(image)
                    return
        if event.mimeData().hasImage():
            image = QImage(event.mimeData().imageData())
            if not image.isNull():
                self._set_pending_image(image)

    def _on_scene_changed(self):
        """Called whenever Maya opens or saves a scene."""
        scene = cmds.file(q=True, sceneName=True) or "untitled"
        scene_name = os.path.basename(scene) or "untitled"

        if scene == self._current_scene:
            return

        # Save current chat before switching
        if self._current_scene:
            self._save_chat()

        self._current_scene = scene
        self._scene_label.setText("Scene: {}".format(scene_name))

        # Load chat for the new scene
        self._messages      = []
        self._display_items = []
        self._analyzer_history   = []
        self._codewriter_history = []
        self._vision_history     = []
        self._msg_count_since_summary = 0
        self._clear_chat_display()
        self._load_chat()

        # Auto-scan if this is a fresh conversation
        if not self._messages:
            QTimer.singleShot(100, self._scan_scene)

    # ------------------------------------------------------------------
    # Chat persistence
    # ------------------------------------------------------------------

    def _save_chat(self):
        path = _chat_path(self._current_scene)
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._messages, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print("[Scene Doctor] Could not save chat: {}".format(e))

    def _load_chat(self):
        path = _chat_path(self._current_scene)
        if not path or not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._messages = json.load(f)
            # Replay messages into the chat display
            for msg in self._messages:
                role    = msg.get("role", "user")
                content = msg.get("content", "")
                img_b64 = msg.get("image_b64")
                self._append_to_chat(role, content, save=False, image_b64=img_b64)
            self._append_system("Chat history loaded for this scene.")
        except Exception as e:
            print("[Scene Doctor] Could not load chat: {}".format(e))

    def _clear_chat(self):
        self._messages      = []
        self._display_items = []
        self._clear_chat_display()
        path = _chat_path(self._current_scene)
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except Exception:
                pass
        self._append_system("Chat cleared.")

    # ------------------------------------------------------------------
    # Chat display helpers
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Chat display — one QHBoxLayout row per message, pure widgets
    # ------------------------------------------------------------------

    def _add_row(self, label_text, label_color, content, italic=False):
        """
        Add one message bubble:
            Name
            Message text...
        With a colored left-border accent.
        """
        # Outer wrapper with colored left border
        wrapper = QWidget()
        wrapper.setObjectName("msgBubble")
        wrapper.setStyleSheet(
            "#msgBubble {{ background-color: #2a2a2a; "
            "border-left: 3px solid {}; "
            "border-radius: 6px; "
            "padding: 0px; }}".format(label_color)
        )

        col = QVBoxLayout(wrapper)
        col.setSpacing(2)
        col.setContentsMargins(12, 8, 12, 8)

        # Name label (top)
        if label_text:
            lbl = QLabel(label_text)
            lbl.setTextFormat(Qt.PlainText)
            lbl.setAlignment(Qt.AlignLeft)
            lbl.setStyleSheet(
                "color:{}; font-weight:bold; font-size:12px; "
                "background: transparent; padding: 0px;".format(label_color)
            )
            col.addWidget(lbl)

        # Content label (below)
        txt = QLabel(content)
        txt.setTextFormat(Qt.PlainText)
        txt.setWordWrap(True)
        txt.setTextInteractionFlags(Qt.TextSelectableByMouse)
        txt.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        txt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        style = ("color:#d4d4d4; font-size:13px; "
                 "background: transparent; padding: 0px;")
        if italic:
            style = ("color:#888888; font-size:12px; font-style:italic; "
                     "background: transparent; padding: 0px;")
        txt.setStyleSheet(style)
        col.addWidget(txt)

        # Insert before the trailing stretch
        count = self._chat_layout.count()
        self._chat_layout.insertWidget(count - 1, wrapper)

        # Scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)

        return txt    # return label so streaming can update it

    def _scroll_to_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_chat_display(self):
        """Remove all message widgets from the layout."""
        while self._chat_layout.count() > 1:   # keep the trailing stretch
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ------------------------------------------------------------------
    # Vision Handlers
    # ------------------------------------------------------------------
    
    def _on_image_pasted(self, image):
        self._set_pending_image(image)

    def _take_viewport_screenshot(self):
        self._set_ui_busy(True)
        try:
            tmp_dir = tempfile.gettempdir()
            path = os.path.join(tmp_dir, "maya_doctor_capture.jpg")
            # Enforce 16:9 approx 800x450
            cmds.playblast(completeFilename=path, forceOverwrite=True, format="image", compression="jpg", percent=100, widthHeight=(800, 450), viewer=False, frame=cmds.currentTime(q=True))
            if os.path.exists(path):
                self._set_pending_image(QImage(path))
        except Exception as e:
            self._append_system("Screenshot failed: " + str(e))
        self._set_ui_busy(False)
        
    def _set_pending_image(self, image):
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "JPG", 80)
        self._pending_image_b64 = base64.b64encode(buffer.data().data()).decode('utf-8')
        
        thumb = image.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._preview_lbl.setPixmap(QPixmap.fromImage(thumb))
        
        vision_model = self._settings.get("vision", {}).get("model", "").lower()
        known_vision = ["maverick", "scout", "gemini-2", "gpt-4o", "claude", "llava"]
        if not any(v in vision_model for v in known_vision):
            self._preview_warning.setText("⚠ Vision model may not support images")
        else:
            self._preview_warning.setText("")
            
        self._preview_container.setVisible(True)

    def _clear_pending_image(self):
        self._pending_image_b64 = None
        self._preview_container.setVisible(False)

    # ------------------------------------------------------------------

    def _append_to_chat(self, role, content, save=True, image_b64=None,
                        agent_key=None):
        if role == "user":
            label, color = "You", "#1a73e8"
        elif role == "assistant":
            if agent_key:
                label = AGENT_LABELS.get(agent_key, "Scene Doctor")
                color = self._AGENT_COLORS.get(agent_key, "#4ec9b0")
            else:
                label, color = "Scene Doctor", "#4ec9b0"
        else:
            label, color = "System", "#888888"

        disp_text = content
        if image_b64:
            disp_text = (content + "\n[Image attached]") if content else "[Image attached]"

        has_code_block = any(tag in content for tag in ("```maya-run", "```python", "```maya-python"))
        if role == "assistant" and has_code_block:
            self._render_assistant_code_message(content, agent_key=agent_key)
        else:
            self._add_row(label, color, disp_text, italic=(role == "system"))

        if save and role in ("user", "assistant"):
            msg = {"role": role, "content": content}
            if image_b64:
                msg["image_b64"] = image_b64
            self._messages.append(msg)
            self._save_chat()

    def _render_assistant_code_message(self, content, agent_key=None):
        """Parse text for ```maya-run ... ``` blocks and render them with buttons."""
        color = self._AGENT_COLORS.get(agent_key, "#4ec9b0") if agent_key else "#e8a838"
        label_text = AGENT_LABELS.get(agent_key, "🔧 Code Writer") if agent_key else "🔧 Code Writer"
        wrapper = QWidget()
        wrapper.setObjectName("msgBubble")
        wrapper.setStyleSheet(
            "#msgBubble {{ background-color: #2a2a2a; "
            "border-left: 3px solid {}; "
            "border-radius: 6px; padding: 0px; }}".format(color)
        )

        col = QVBoxLayout(wrapper)
        col.setSpacing(6)
        col.setContentsMargins(12, 8, 12, 8)

        lbl = QLabel(label_text)
        lbl.setStyleSheet("color:{}; font-weight:bold; font-size:12px; background: transparent; padding: 0px;".format(color))
        col.addWidget(lbl)

        # Apply primary and fallback patterns to catch common model mistakes
        parts = re.split(r"```(?:maya-run|python|maya-python)\n(.*?)\n```", content, flags=re.DOTALL)
        
        for i, part in enumerate(parts):
            if not part.strip():
                continue
            if i % 2 == 0:
                txt = QLabel(part.strip())
                txt.setWordWrap(True)
                txt.setTextInteractionFlags(Qt.TextSelectableByMouse)
                txt.setStyleSheet("color:#d4d4d4; font-size:13px; background: transparent; padding: 0px;")
                col.addWidget(txt)
            else:
                code_box = QWidget()
                code_box.setStyleSheet("background-color: #1a1a1a; border: 1px solid #444; border-radius: 4px;")
                code_layout = QVBoxLayout(code_box)
                code_layout.setContentsMargins(8, 8, 8, 8)
                
                code_text = QTextEdit()
                code_text.setPlainText(part.strip())
                code_text.setReadOnly(False)
                code_text.setStyleSheet("color:#9cdcfe; font-family:'Consolas','Courier New',monospace; font-size:12px; background: transparent; border: none;")
                lines = part.strip().count('\n') + 1
                code_text.setFixedHeight(min(200, max(40, lines * 16 + 20)))
                code_layout.addWidget(code_text)
                
                btn_row = QHBoxLayout()
                btn_row.addStretch()
                btn_run = QPushButton("▶ Run")
                btn_run.setCursor(Qt.PointingHandCursor)
                btn_run.setStyleSheet("background-color: #2d6a4f; color: white; border: none; border-radius: 2px; padding: 4px 12px; font-weight: bold;")
                
                btn_dismiss = QPushButton("✕ Dismiss")
                btn_dismiss.setCursor(Qt.PointingHandCursor)
                btn_dismiss.setStyleSheet("background-color: #662222; color: white; border: none; border-radius: 2px; padding: 4px 12px; font-weight: bold;")
                
                btn_row.addWidget(btn_run)
                btn_row.addWidget(btn_dismiss)
                code_layout.addLayout(btn_row)
                btn_run.clicked.connect(lambda checked=False, cb=code_box, cr=btn_row, ct=code_text: self._run_maya_code(ct.toPlainText(), cb, cr, ct))
                btn_dismiss.clicked.connect(lambda checked=False, cb=code_box, cr=btn_row, ct=code_text: self._dismiss_maya_code(cb, cr, ct))
                
                col.addWidget(code_box)

        count = self._chat_layout.count()
        self._chat_layout.insertWidget(count - 1, wrapper)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _sanitize_node_names(self, code):
        """Fix full path node names like |transform3 to transform3"""
        import re
        # Find patterns like '|nodeName' and strip the leading pipe
        # but keep internal pipes in paths like |group1|transform3
        # Only strip leading pipe at start of a name in string context
        code = re.sub(r"'(\|+)([^'|]+)'", lambda m: f"'{m.group(2)}'", code)
        code = re.sub(r'"(\|+)([^"|]+)"', lambda m: f'"{m.group(2)}"', code)
        return code

    def _run_maya_code(self, code, code_box, btn_row, code_text):
        self._dismiss_maya_code(code_box, btn_row, code_text)
        try:
            code = self._sanitize_node_names(code)
            exec(code, {"cmds": cmds, "mel": mel, "os": os})
            self._append_system("✅ Done (Code Executed)")
        except Exception as e:
            self._append_system("⚠ Error: " + str(e))
            return   # don't trigger agentic loop on error

        # ── V2.5 Agentic Loop ─────────────────────────────────────────
        self._agentic_iter += 1
        if self._agentic_iter > 3:
            self._append_system(
                "🔁 Max auto-check iterations reached (3). "
                "Send a message if you'd like to continue."
            )
            self._agentic_iter = 0
            return

        self._append_system(
            "🔄 Auto-checking result... (attempt {}/3)".format(self._agentic_iter)
        )
        # Take a viewport screenshot and send it to the AI
        QTimer.singleShot(200, self._agentic_check)

    def _dismiss_maya_code(self, code_box, btn_row, code_text):
        code_box.setStyleSheet("background-color: #2d2d2d; border: 1px solid #444; border-radius: 4px;")
        code_text.setStyleSheet("color:#666666; font-family:'Consolas','Courier New',monospace; font-size:12px; background: transparent; border: none;")
        code_text.setReadOnly(True)
        while btn_row.count():
            item = btn_row.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _agentic_check(self):
        """V3 — Take a viewport screenshot and send to Vision agent for evaluation."""
        try:
            tmp_dir = tempfile.gettempdir()
            path = os.path.join(tmp_dir, "maya_doctor_capture.jpg")
            cmds.playblast(
                completeFilename=path, forceOverwrite=True,
                format="image", compression="jpg", percent=100,
                widthHeight=(800, 450), viewer=False,
                frame=cmds.currentTime(q=True),
            )
            if not os.path.exists(path):
                self._append_system("⚠ Could not capture viewport for auto-check.")
                return

            img = QImage(path)
            buffer = QBuffer()
            buffer.open(QIODevice.WriteOnly)
            img.save(buffer, "JPG", 80)
            img_b64 = base64.b64encode(buffer.data().data()).decode("utf-8")

            check_msg = (
                "Here is the viewport after running the fix. "
                "Does it look correct? If yes, confirm to the user. "
                "If not, suggest another fix."
            )

            # Add to unified history
            self._messages.append({
                "role": "user",
                "content": check_msg,
                "image_b64": img_b64,
            })
            self._save_chat()

            # Send to Vision agent
            self._vision_history.append({
                "role": "user",
                "content": check_msg,
                "image_b64": img_b64,
            })
            self._run_agent("vision", self._vision_history)

        except Exception as e:
            self._append_system("⚠ Auto-check failed: " + str(e))

    def _append_system(self, text):
        self._add_row("", "#666666", text, italic=True)




    def _append_token(self, token):
        """Update the live streaming label in-place."""
        self._assistant_buffer += token
        if self._stream_label:
            self._stream_label.setText(self._assistant_buffer + "▌")
        self._scroll_to_bottom()

    def _strip_code_blocks(self, text):
        """Remove any code blocks from Analyzer output."""
        # Remove ```maya-run blocks
        text = re.sub(r'```maya-run\n.*?```', '', text, flags=re.DOTALL)
        # Remove ```python blocks  
        text = re.sub(r'```python\n.*?```', '', text, flags=re.DOTALL)
        # Remove any other ``` blocks
        text = re.sub(r'```[\w-]*\n.*?```', '', text, flags=re.DOTALL)
        return text.strip()

    def _end_assistant_bubble(self):
        """Finalise the current agent's streaming bubble."""
        content = self._assistant_buffer.strip()
        self._assistant_buffer = ""
        agent_key = self._current_agent or "analyzer"

        # Intercept [SCAN_SCENE] (only from Analyzer)
        if agent_key == "analyzer" and content.strip() == "[SCAN_SCENE]":
            if self._stream_label:
                self._stream_label.setText("...scanning scene...")
                self._stream_label.setStyleSheet(
                    "color:#888888; font-style:italic; font-size:12px;"
                )
            self._stream_label = None
            self._set_ui_busy(False)

            try:
                self._last_scan_data = run_scan()
                prompt = scan_to_prompt(self._last_scan_data)
            except Exception as e:
                prompt = "Scan failed: {}".format(e)

            scan_msg = (
                "Here is the 'Latest scene data' you requested. "
                "DO NOT output [SCAN_SCENE] again. "
                "Use this data to answer my previous question immediately:\n\n"
                + prompt
            )
            self._messages.append({"role": "user", "content": scan_msg})
            self._analyzer_history.append({"role": "user", "content": scan_msg})
            QTimer.singleShot(100, self._run_ai)
            return

        # Remove the streaming bubble (will be re-added properly)
        if self._stream_label:
            stream_bubble = self._stream_label.parentWidget()
            stream_bubble.setParent(None)
            stream_bubble.deleteLater()
        self._stream_label = None

        if not content:
            self._set_ui_busy(False)
            return

        if agent_key == "analyzer":
            content = self._strip_code_blocks(content)

        # Save to unified history
        self._append_to_chat("assistant", content, save=True,
                             agent_key=agent_key)

        # Save to per-agent history
        if agent_key == "analyzer":
            self._analyzer_history.append(
                {"role": "assistant", "content": content})
        elif agent_key == "codewriter":
            self._codewriter_history.append(
                {"role": "assistant", "content": content})
        elif agent_key == "vision":
            self._vision_history.append(
                {"role": "assistant", "content": content})

        # Chain to next agent if pending
        callback = self._pending_chain
        self._pending_chain = None

        if callback:
            callback(content)
        else:
            self._set_ui_busy(False)

    # ------------------------------------------------------------------
    # Orchestrator — decides which agents to run
    # ------------------------------------------------------------------

    def _classify_intent(self, content, has_image):
        """Return 'vision', 'analyze_and_fix', or 'general'."""
        if has_image:
            return "vision"
        lower = content.lower()
        if "## Maya Scene Diagnostic Report" in content:
            return "analyze_and_fix"
        fix_kw = [
            "fix", "clean", "delete", "remove", "freeze", "repair",
            "optimise", "optimize", "reduce", "merge", "combine",
            "rename", "set up", "setup", "create", "add", "change",
            "modify", "lighting", "light", "camera", "move", "rotate",
            "scale", "apply", "bake", "transfer", "mirror",
        ]
        if any(k in lower for k in fix_kw):
            return "analyze_and_fix"
        return "general"

    def _run_agent(self, agent_key, messages, on_complete=None, search_mode=False):
        """Run a single agent. Streams into the chat with agent-specific label."""
        settings = self._settings.get(agent_key, {})
        self._current_agent = agent_key
        self._pending_chain = on_complete

        self._set_ui_busy(True)
        self._start_agent_bubble(agent_key)

        self._stream_worker = StreamWorker(
            messages=list(messages),
            settings=settings,
            search_mode=search_mode
        )
        self._stream_worker.token.connect(self._append_token)
        self._stream_worker.done.connect(self._end_assistant_bubble)
        self._stream_worker.error.connect(self._on_stream_error)
        self._stream_worker.start()

    def _start_agent_bubble(self, agent_key):
        """Start a streaming bubble labelled for the given agent."""
        self._assistant_buffer = ""
        label = AGENT_LABELS.get(agent_key, "AI")
        color = self._AGENT_COLORS.get(agent_key, "#4ec9b0")
        self._stream_label = self._add_row(label, color, "▌")

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def _scan_scene(self):
        self._append_system("Scanning scene...")
        try:
            self._last_scan_data = run_scan()
            prompt = scan_to_prompt(self._last_scan_data)
        except Exception as e:
            self._append_system("Scan failed: {}".format(e))
            return

        user_msg = "Please analyse this scene:\n\n" + prompt
        self._append_to_chat("user", user_msg)
        self._analyzer_history.append({"role": "user", "content": user_msg})

        # Analyzer → Code Writer chain
        self._run_agent("analyzer", self._analyzer_history,
                        on_complete=self._on_scan_analyzer_done)

    def _on_scan_analyzer_done(self, analysis):
        """After Analyzer finishes a scan, feed to Code Writer."""
        user_message = "Please analyse this scene"
        if len(self._analyzer_history) >= 2:
            user_message = self._analyzer_history[-2].get("content", user_message)
            
        codewriter_context = f"""
Scene Scan Data (lights):
{json.dumps(self._last_scan_data.get('lights', {}), indent=2)}

Analyzer Summary:
{analysis}

User Request:
{user_message}
"""
        self._codewriter_history.append({"role": "user", "content": codewriter_context})
        self._run_agent("codewriter", self._codewriter_history)

    # ------------------------------------------------------------------
    # Send message
    # ------------------------------------------------------------------

    def _toggle_search_mode(self):
        self._search_mode = not self._search_mode
        if self._search_mode:
            self._search_btn.setStyleSheet("background-color: #4ec9b0; color: #1e1e1e; font-weight: bold; border-radius: 4px;")
            self._search_lbl.setVisible(True)
        else:
            self._search_btn.setStyleSheet("")
            self._search_lbl.setVisible(False)

    def _send_message(self):
        text = self._input.text().strip()
        img_b64 = getattr(self, "_pending_image_b64", None)

        if not text and not img_b64:
            return

        self._input.clear()
        self._agentic_iter = 0

        if img_b64:
            self._clear_pending_image()

        if self._search_mode and text:
            text = f"[SEARCH_MODE] Please search for: {text}\nSearch Gumroad, GitHub, and 80 Level for relevant results."
            self._toggle_search_mode()  # One-shot: disable after use

        self._append_to_chat("user", text, image_b64=img_b64)
        self._run_ai()

    # ------------------------------------------------------------------
    # AI streaming — main entry point
    # ------------------------------------------------------------------

    def _run_ai(self):
        if not self._messages:
            return

        last_msg = self._messages[-1]
        has_image = bool(last_msg.get("image_b64"))
        content = last_msg.get("content", "")
        
        search_mode = content.startswith("[SEARCH_MODE]")
        
        intent = self._classify_intent(content, has_image)

        # Context management check
        self._msg_count_since_summary += 1
        if self._msg_count_since_summary >= 10:
            self._summarise_context()

        if intent == "vision":
            self._vision_history.append({
                "role": "user",
                "content": content,
                "image_b64": last_msg.get("image_b64"),
            })
            self._run_agent("vision", self._vision_history)

        elif intent == "analyze_and_fix":
            self._analyzer_history.append(
                {"role": "user", "content": content})
            self._run_agent("analyzer", self._analyzer_history,
                            on_complete=self._on_fix_analyzer_done, search_mode=search_mode)
        else:
            # General question — Analyzer only
            self._analyzer_history.append(
                {"role": "user", "content": content})
            self._run_agent("analyzer", self._analyzer_history, search_mode=search_mode)

    def _on_fix_analyzer_done(self, analysis):
        """After Analyzer identifies issues, run Code Writer."""
        user_message = ""
        if len(self._analyzer_history) >= 2:
            user_message = self._analyzer_history[-2].get("content", "")
            
        codewriter_context = f"""
Scene Scan Data (lights):
{json.dumps(self._last_scan_data.get('lights', {}), indent=2)}

Analyzer Summary:
{analysis}

User Request:
{user_message}
"""
        self._codewriter_history.append({"role": "user", "content": codewriter_context})
        self._run_agent("codewriter", self._codewriter_history)

    def _on_stream_error(self, msg):
        self._append_system("⚠  {}".format(msg))
        self._pending_chain = None
        self._set_ui_busy(False)

    # ------------------------------------------------------------------
    # Context management — auto-summarise every 10 messages
    # ------------------------------------------------------------------

    def _summarise_context(self):
        """Summarise the conversation to save context window."""
        summary_settings = self._settings.get("summary", {})
        if not summary_settings.get("model"):
            # No summary agent configured — just reset counter
            self._msg_count_since_summary = 0
            return

        # Build a transcript of the last 10 messages
        recent = self._messages[-10:]
        transcript = "\n".join(
            "{}: {}".format(m.get("role", "?"), m.get("content", "")[:300])
            for m in recent
        )
        summary_msgs = [{
            "role": "user",
            "content": (
                "Summarise this conversation in 3-4 lines focusing on "
                "what was fixed and what is still pending:\n\n" + transcript
            ),
        }]

        self._summary_worker = SummaryWorker(summary_msgs, summary_settings)
        self._summary_worker.result.connect(self._on_summary_done)
        self._summary_worker.error.connect(self._on_summary_error)
        self._summary_worker.start()

    def _on_summary_done(self, summary_text):
        if not summary_text:
            self._msg_count_since_summary = 0
            return

        # Keep only [summary] + last 3 messages
        last_3 = self._messages[-3:]
        self._messages = [
            {"role": "assistant",
             "content": "📋 Previous conversation summary:\n" + summary_text}
        ] + last_3

        # Also trim per-agent histories
        for hist in (self._analyzer_history,
                     self._codewriter_history,
                     self._vision_history):
            if len(hist) > 6:
                hist[:] = hist[-4:]

        self._msg_count_since_summary = 0
        self._save_chat()
        self._append_system("💬 Chat summarised to save context")

    def _on_summary_error(self, msg):
        print("[Scene Doctor] Summary failed: {}".format(msg))
        self._msg_count_since_summary = 0

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self):
        dlg = SettingsDialog(self._settings, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._settings = dlg.get_settings()
            self._save_global_settings()
            mode = self._settings.get("mode", "single")
            if mode == "single":
                model = self._settings.get("single", {}).get("model", "?")
                self._append_system(
                    "Settings updated — Single Agent mode, model: " + model)
            else:
                models = ", ".join(
                    "{}: {}".format(AGENT_LABELS.get(k, k),
                                    self._settings.get(k, {}).get("model", "?"))
                    for k in ("analyzer", "codewriter", "vision", "summary")
                )
                self._append_system("Settings updated — Multi Agent — " + models)

    def _settings_path(self):
        return os.path.join(os.path.dirname(__file__), "settings.json")

    def _load_global_settings(self):
        path = self._settings_path()
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return migrate_settings(data)
            except Exception as e:
                print("[Scene Doctor] Could not load settings: {}".format(e))
        # Return fresh defaults
        import copy
        return copy.deepcopy(DEFAULT_SETTINGS)

    def _save_global_settings(self):
        path = self._settings_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            print("[Scene Doctor] Could not save settings: {}".format(e))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_ui_busy(self, busy):
        self._send_btn.setEnabled(not busy)
        self._scan_btn.setEnabled(not busy)
        self._input.setEnabled(not busy)
        if busy:
            self._send_btn.setText("...")
        else:
            self._send_btn.setText("Send")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_window = None

def show():
    """Call this from Maya's Script Editor to open the tool."""
    global _window
    if _window is not None:
        try:
            _window.close()
        except Exception:
            pass
    _window = SceneDoctorWindow()
    _window.show()
    return _window

