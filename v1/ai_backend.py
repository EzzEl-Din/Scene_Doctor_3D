"""
ai_backend.py — Maya Scene Doctor AI
Handles AI communication for both:
  - Local  : Ollama  (http://localhost:11434)
  - External: Any OpenAI-compatible API (user provides base_url + api_key + model)

Built by Ezz El-Din | LinkedIn: https://www.linkedin.com/in/ezzel-din-tarek-mostafa

Streaming is done in a QThread so the UI never freezes.
"""

import json
import urllib.request
import urllib.error
from PySide2.QtCore import QThread, Signal


# ---------------------------------------------------------------------------
# Settings — stored as a simple dict, saved/loaded by main.py
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    "backend":   "ollama",          # "ollama" | "openai"
    "base_url":  "http://localhost:11434",
    "api_key":   "",
    "model":     "llama3",
    "system_prompt": (
        "You are Maya Scene Doctor — a friendly, experienced Technical Director "
        "who truly understands artists. You speak in plain, simple language that "
        "any 3D artist can follow, avoiding heavy technical jargon. "
        "When you must use a technical term, briefly explain what it means in "
        "everyday words.\n\n"
        "Your tone is warm, supportive, and encouraging — like a helpful colleague "
        "sitting next to the artist. Use short sentences, bullet points, and "
        "practical step-by-step instructions.\n\n"
        "When given a scene diagnostic report:\n"
        "• Summarise what's going on in the scene in plain language.\n"
        "• Flag problems using clear priorities: 🔴 Critical, 🟡 Warning, 🟢 Info.\n"
        "• Explain WHY each issue matters (e.g. 'this will make your render slow' "
        "instead of 'non-manifold geometry increases ray-tracing cost').\n"
        "Always be concise — respect the artist's time.\n\n"
        "IMPORTANT PERMISSION:\n"
        "If the user asks ANY question about the CURRENT state of their scene, or asks you to 'scan', "
        "you must check if they just provided the 'Latest scene data'. "
        "If they HAVE NOT provided the latest data yet, reply with exactly this text and nothing else:\n"
        "[SCAN_SCENE]\n"
        "I will intercept this phrase, generate a fresh Scene Diagnostic Report, and give it to you. "
        "Once I provide the new report, DO NOT output [SCAN_SCENE] again. Use the report to answer the user's question!"
    ),
}


# ---------------------------------------------------------------------------
# Streaming worker — lives in a background QThread
# ---------------------------------------------------------------------------

class StreamWorker(QThread):
    """
    Sends a message to the AI and emits tokens one by one.

    Signals:
        token(str)   — one streamed chunk of text
        done()       — streaming finished successfully
        error(str)   — something went wrong
    """

    token = Signal(str)
    done  = Signal()
    error = Signal(str)

    def __init__(self, messages, settings, parent=None):
        """
        Args:
            messages (list[dict]): Full conversation history
                                   [{"role": "user"|"assistant", "content": "..."}]
            settings (dict):       Backend settings (see DEFAULT_SETTINGS)
        """
        super().__init__(parent)
        self.messages = messages
        self.settings = settings
        self._running = True

    def stop(self):
        self._running = False

    # ------------------------------------------------------------------
    def run(self):
        backend = self.settings.get("backend", "ollama")
        try:
            if backend == "ollama":
                self._stream_ollama()
            else:
                self._stream_openai()
        except urllib.error.HTTPError as e:
            code = e.code
            # Try to read the error body for details
            detail = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
                err_json = json.loads(body)
                detail = err_json.get("error", {}).get("message", "")
            except Exception:
                detail = body[:300] if body else ""

            if detail:
                msg = "API Error {}: {}".format(code, detail)
            elif code == 401:
                msg = ("Authentication failed (401). "
                       "Please check your API key in Settings.")
            elif code == 403:
                msg = ("Forbidden (403). Possible causes:\n"
                       "• API key invalid or expired\n"
                       "• Model may be blocked in your account\n"
                       "• Check model permissions at console.groq.com/settings/limits")
            elif code == 404:
                msg = ("Not found (404). The API URL might be wrong. "
                       "Check Settings > Base URL.")
            elif code == 429:
                msg = ("Rate limited (429). Too many requests — "
                       "wait a moment and try again.")
            else:
                msg = "HTTP Error {}: {}".format(code, e.reason)
            self.error.emit(msg)
        except urllib.error.URLError as e:
            self.error.emit(
                "Cannot connect to {}. Is the server running?\n{}".format(
                    self.settings.get("base_url", "?"), str(e.reason)
                )
            )
        except Exception as e:
            self.error.emit("Error: {}".format(str(e)))

    # ------------------------------------------------------------------
    # Ollama  — POST /api/chat  (NDJSON stream)
    # ------------------------------------------------------------------
    def _stream_ollama(self):
        url   = self.settings.get("base_url", "http://localhost:11434").rstrip("/")
        url  += "/api/chat"
        model = self.settings.get("model", "llama3")

        # Prepend system message if set
        messages = self._with_system()

        payload = json.dumps({
            "model":    model,
            "messages": messages,
            "stream":   True,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "MayaSceneDoctor/1.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            for raw_line in response:
                if not self._running:
                    break
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    text  = chunk.get("message", {}).get("content", "")
                    if text:
                        self.token.emit(text)
                    if chunk.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue

        self.done.emit()

    # ------------------------------------------------------------------
    # OpenAI-compatible  — POST /chat/completions  (SSE stream)
    # ------------------------------------------------------------------
    def _stream_openai(self):
        base_url = self.settings.get("base_url", "").rstrip("/")
        api_key  = self.settings.get("api_key",  "").strip()
        model    = self.settings.get("model",    "gpt-4o")

        if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
            self.error.emit("Wait! Your API key is empty! Go to Settings and enter your key.")
            self.done.emit()
            return

        # Build correct endpoint regardless of what the user typed
        if base_url.endswith("/chat/completions"):
            pass  # already correct
        elif base_url.endswith("/v1"):
            base_url = base_url + "/chat/completions"
        else:
            base_url = base_url.rstrip("/") + "/v1/chat/completions"

        messages = self._with_system()

        payload = json.dumps({
            "model":    model,
            "messages": messages,
            "stream":   True,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MayaSceneDoctor/1.0",
        }
        if api_key:
            headers["Authorization"] = "Bearer {}".format(api_key)

        req = urllib.request.Request(
            base_url,
            data=payload,
            headers=headers,
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            for raw_line in response:
                if not self._running:
                    break
                line = raw_line.decode("utf-8").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk   = json.loads(data)
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        text  = delta.get("content", "")
                        if text:
                            self.token.emit(text)
                except json.JSONDecodeError:
                    continue

        self.done.emit()

    # ------------------------------------------------------------------
    def _with_system(self):
        """Prepend the system prompt to the message list."""
        system = self.settings.get("system_prompt", "").strip()
        if system:
            return [{"role": "system", "content": system}] + self.messages
        return self.messages
