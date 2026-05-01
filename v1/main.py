"""
main.py — Maya Scene Doctor AI
PySide2 UI that wires scanner.py + ai_backend.py into a Maya panel.

Built by Ezz El-Din | LinkedIn: https://www.linkedin.com/in/ezzel-din-tarek-mostafa

Usage (Maya Script Editor):
    import main
    main.show()
"""

import os
import json

import maya.cmds as cmds
from PySide2.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit,
    QDialog, QFormLayout, QComboBox, QDialogButtonBox,
    QScrollArea, QSizePolicy, QFrame, QTextEdit,
)
from PySide2.QtCore    import Qt, QTimer
from PySide2.QtGui     import QFont, QColor, QPalette, QTextCursor

# Local modules — must be in the same folder / on sys.path
from scanner    import scan_to_prompt, run_scan
from ai_backend import StreamWorker, DEFAULT_SETTINGS

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

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Backend Settings")
        self.setMinimumWidth(420)
        self._settings = dict(settings)   # work on a copy

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(10)

        # Backend selector
        self._backend_combo = QComboBox()
        self._backend_combo.addItems(["ollama", "openai"])
        self._backend_combo.setCurrentText(self._settings.get("backend", "ollama"))
        form.addRow("Backend:", self._backend_combo)

        # Base URL
        self._url_input = QLineEdit(self._settings.get("base_url", ""))
        self._url_input.setPlaceholderText("http://localhost:11434")
        form.addRow("Base URL:", self._url_input)

        # API Key
        self._key_input = QLineEdit(self._settings.get("api_key", ""))
        self._key_input.setPlaceholderText("sk-... (leave blank for Ollama)")
        self._key_input.setEchoMode(QLineEdit.Password)
        form.addRow("API Key:", self._key_input)

        # Model
        self._model_input = QLineEdit(self._settings.get("model", "llama3"))
        self._model_input.setPlaceholderText("llama3 / gpt-4o / mistral ...")
        form.addRow("Model:", self._model_input)

        # System prompt
        self._sys_input = QTextEdit()
        self._sys_input.setPlainText(self._settings.get("system_prompt", ""))
        self._sys_input.setFixedHeight(90)
        form.addRow("System Prompt:", self._sys_input)

        layout.addLayout(form)

        # OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Update placeholder when backend changes
        self._backend_combo.currentTextChanged.connect(self._on_backend_change)
        self._on_backend_change(self._backend_combo.currentText())

    def _on_backend_change(self, backend):
        if backend == "ollama":
            self._url_input.setPlaceholderText("http://localhost:11434")
        else:
            self._url_input.setPlaceholderText("https://api.openai.com")

    def _save(self):
        self._settings["backend"]       = self._backend_combo.currentText()
        self._settings["base_url"]      = self._url_input.text().strip()
        self._settings["api_key"]       = self._key_input.text().strip()
        self._settings["model"]         = self._model_input.text().strip()
        self._settings["system_prompt"] = self._sys_input.toPlainText().strip()
        self.accept()

    def get_settings(self):
        return self._settings


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class SceneDoctorWindow(QWidget):

    # Colours for chat bubbles
    _COLOR_USER      = "#1a73e8"
    _COLOR_ASSISTANT = "#2d2d2d"
    _COLOR_SYSTEM    = "#5a5a5a"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Maya Scene Doctor AI")
        self.setMinimumSize(520, 640)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # State
        self._settings         = self._load_global_settings()
        self._messages         = []
        self._display_items    = []
        self._stream_worker    = None
        self._stream_label     = None
        self._current_scene    = ""
        self._assistant_buffer = ""

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

        # ── Input row ─────────────────────────────────────────────────
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask a follow-up question...")
        self._input.setObjectName("inputField")
        self._input.returnPressed.connect(self._send_message)
        input_row.addWidget(self._input, stretch=1)

        self._send_btn = QPushButton("Send")
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.setFixedWidth(70)
        self._send_btn.clicked.connect(self._send_message)
        input_row.addWidget(self._send_btn)

        root.addLayout(input_row)

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
                border-radius: 4px;
                padding: 6px;
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
                border-radius: 4px;
                padding: 4px 8px;
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
        super().closeEvent(event)

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
                self._append_to_chat(role, content, save=False)
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

    def _append_to_chat(self, role, content, save=True):
        if role == "user":
            label, color = "You", "#1a73e8"
        elif role == "assistant":
            label, color = "Scene Doctor", "#4ec9b0"
        else:
            label, color = "System", "#888888"

        self._add_row(label, color, content, italic=(role == "system"))

        if save and role in ("user", "assistant"):
            self._messages.append({"role": role, "content": content})
            self._save_chat()

    def _append_system(self, text):
        self._add_row("", "#666666", text, italic=True)

    def _start_assistant_bubble(self):
        """Add a streaming row and keep a reference to its content QLabel."""
        self._assistant_buffer = ""
        self._stream_label = self._add_row("Scene Doctor", "#4ec9b0", "▌")

    def _append_token(self, token):
        """Update the live streaming label in-place."""
        self._assistant_buffer += token
        if self._stream_label:
            self._stream_label.setText(self._assistant_buffer + "▌")
        self._scroll_to_bottom()

    def _end_assistant_bubble(self):
        """Finalise — remove the cursor, save message."""
        content = self._assistant_buffer.strip()
        self._assistant_buffer = ""
        
        # Intercept the AI requesting a scene scan
        if "[SCAN_SCENE]" in content:
            # Revert the UI since we don't want to show the magic word
            if self._stream_label:
                # We hide the label, we can't easily pop the layout row right now
                # but we can set it to a system message indicating scanning
                self._stream_label.setText("...scanning scene...")
                self._stream_label.setStyleSheet("color:#888888; font-style:italic; font-size:12px;")
            
            self._stream_label = None
            self._set_ui_busy(False)
            
            # Run scan and push back
            try:
                prompt = scan_to_prompt()
            except Exception as e:
                prompt = "Scan failed: {}".format(e)
                
            self._messages.append({
                "role": "user", 
                "content": "Here is the 'Latest scene data' you requested. DO NOT output [SCAN_SCENE] again. Use this data to answer my previous question immediately:\n\n" + prompt
            })
            # Re-run AI automatically
            QTimer.singleShot(100, self._run_ai)
            return

        # Normal message save
        if self._stream_label:
            self._stream_label.setText(content)
        if content:
            self._messages.append({"role": "assistant", "content": content})
            self._save_chat()
            
        self._stream_label = None
        self._set_ui_busy(False)

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def _scan_scene(self):
        self._append_system("Scanning scene...")
        try:
            prompt = scan_to_prompt()
        except Exception as e:
            self._append_system("Scan failed: {}".format(e))
            return

        self._append_to_chat("user", "Please analyse this scene:\n\n" + prompt)
        self._run_ai()

    # ------------------------------------------------------------------
    # Send message
    # ------------------------------------------------------------------

    def _send_message(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._append_to_chat("user", text)
        self._run_ai()

    # ------------------------------------------------------------------
    # AI streaming
    # ------------------------------------------------------------------

    def _run_ai(self):
        if not self._messages:
            return

        self._set_ui_busy(True)
        self._start_assistant_bubble()

        self._stream_worker = StreamWorker(
            messages=list(self._messages),   # snapshot
            settings=self._settings,
        )
        self._stream_worker.token.connect(self._append_token)
        self._stream_worker.done.connect(self._end_assistant_bubble)
        self._stream_worker.error.connect(self._on_stream_error)
        self._stream_worker.start()

    def _on_stream_error(self, msg):
        self._append_system("⚠  {}".format(msg))
        self._set_ui_busy(False)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self):
        dlg = SettingsDialog(self._settings, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._settings = dlg.get_settings()
            self._save_global_settings()
            self._append_system("Settings updated — model: {} [{}]".format(
                self._settings.get("model"), self._settings.get("backend")
            ))

    def _settings_path(self):
        # Save settings in the same directory as the script
        return os.path.join(os.path.dirname(__file__), "settings.json")

    def _load_global_settings(self):
        path = self._settings_path()
        out = dict(DEFAULT_SETTINGS)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    out.update(data)
            except Exception as e:
                print("[Scene Doctor] Could not load settings: {}".format(e))
        return out

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

_window = None   # keep a reference so it isn't garbage-collected

def show():
    """Call this from Maya's Script Editor to open the tool."""
    global _window
    # Close existing window if open
    if _window is not None:
        try:
            _window.close()
        except Exception:
            pass
    _window = SceneDoctorWindow()
    _window.show()
    return _window
