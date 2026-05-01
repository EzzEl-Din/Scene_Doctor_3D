"""
ai_backend.py — Maya Scene Doctor AI  (V3 — Multi-Agent)

Handles AI communication for 4 specialized agents:
  - Analyzer     : scene analysis and issue identification
  - Code Writer  : Maya Python fix generation
  - Vision       : viewport screenshot evaluation
  - Summary      : conversation summarisation

Supports:
  - Local  : Ollama  (http://localhost:11434)
  - External: Any OpenAI-compatible API (user provides base_url + api_key + model)

Built by Ezz El-Din | LinkedIn: https://www.linkedin.com/in/ezzel-din-tarek-mostafa

Streaming is done in a QThread so the UI never freezes.
"""

import json
import urllib.request
import urllib.error

try:
    from PySide2.QtCore import QThread, Signal
except ImportError:
    from PySide6.QtCore import QThread, Signal


# ---------------------------------------------------------------------------
# Agent system prompts — hardcoded defaults (editable in Settings > Advanced)
# ---------------------------------------------------------------------------

AGENT_PROMPTS = {
    "analyzer": (
        "You are a Maya scene analysis expert.\n"
        "Your ONLY job is to analyze scene data and describe issues in plain text.\n\n"
        "STRICT RULES:\n"
        "- NEVER suggest searching the web or provide YouTube/tutorial links\n"
        "- NEVER write code or code blocks of any kind\n"
        "- NEVER use ```maya-run, ```python, or any code tags\n"
        "- Your ONLY job is to analyze and describe issues in plain text\n"
        "- If you don't know the answer, say so simply — don't search\n"
        "- The search button exists for the user to trigger manually\n"
        "- Be concise — 3-5 lines maximum\n"
        "- Use 🔴 Critical / 🟡 Warning / 🟢 Info only when issues exist\n"
        "- If scene is clean, say so in one natural sentence\n"
        "- End with one short question or suggested next action\n\n"
        "Your analysis will be passed to a Code Writer agent \n"
        "who will handle ALL code. You just describe the problem.\n\n"
        "SEARCH MODE:\n"
        "Only activated when user message starts with [SEARCH_MODE].\n"
        "Search ONLY for external resources — tools, plugins, tutorials.\n"
        "NEVER activate search for scene edits, light changes, \n"
        "camera adjustments, or any Maya operation.\n"
        "- Always check: Gumroad (paid/free tools), GitHub (open source), 80 Level (tutorials)\n"
        "- Return results with: title, brief description, and link\n"
        "- Format results clearly — one result per bullet point\n"
        "- If nothing relevant found, say so honestly\n\n"
        "IMPORTANT PERMISSION:\n"
        "If the user asks ANY question about the CURRENT state of their scene, "
        "or asks you to 'scan', you must check if they just provided the "
        "'Latest scene data'. If they HAVE NOT provided the latest data yet, "
        "reply with exactly this text and nothing else:\n"
        "[SCAN_SCENE]\n"
        "I will intercept this phrase, generate a fresh Scene Diagnostic Report, "
        "and give it to you. Once I provide the new report, DO NOT output "
        "[SCAN_SCENE] again. Use the report to answer the user's question!"
    ),
    "codewriter": (
        "You are a Maya Python expert.\n"
        "You receive a scene analysis and write clean Python fixes.\n"
        "Add a one-line comment explaining what each block does.\n"
        "Never use MEL — Python only.\n"
        "Keep code simple and safe.\n\n"
        "CRITICAL RULES — CODE BLOCKS:\n\n"
        "1. ALWAYS write ONE single complete maya-run block per task.\n"
        "   Never split code into multiple blocks.\n"
        "   Never write a \"verify\" block after the main block.\n"
        "   All logic must be in ONE block.\n\n"
        "2. Every block must be fully self-contained:\n"
        "   - Import maya.cmds at the top\n"
        "   - Define all variables inside the block\n"
        "   - Never reference variables from previous blocks\n\n"
        "3. NODE NAMES — CRITICAL:\n"
        "   - NEVER use full path names like |transform3 or |directLightShape\n"
        "   - ALWAYS strip the pipe character from node names:\n"
        "     safe_name = node_name.split('|')[-1]\n"
        "   - For directional lights: the transform node handles position/rotation\n"
        "     NOT the shape node. Get the transform like this:\n\n"
        "     ```maya-run\n"
        "     import maya.cmds as cmds\n"
        "     \n"
        "     # Create directional light — returns transform node directly\n"
        "     light = cmds.directionalLight(name='myLight')\n"
        "     # light is already the transform — use it directly\n"
        "     cmds.setAttr(light + '.translateX', 5)\n"
        "     cmds.setAttr(light + '.translateY', 10)\n"
        "     cmds.setAttr(light + '.rotateX', -45)\n"
        "     ```\n\n"
        "4. NEVER use ```python or ```maya-python — ONLY ```maya-run\n\n"
        "LIGHTS RULES:\n"
        "- ALWAYS check existing lights from the scan data before doing anything\n"
        "- If lights exist in scan data → ALWAYS modify them with cmds.setAttr()\n"
        "- NEVER create new lights if lights already exist in the scene\n"
        "- Only create new lights if scan data shows NO lights at all\n\n"
        "ARNOLD LIGHTS — CRITICAL:\n"
        "Arnold area lights have a transform node AND a shape node.\n"
        "ALWAYS use the transform node for position/rotation.\n"
        "ALWAYS use the shape node for color/intensity.\n\n"
        "Correct way to get both:\n"
        "```maya-run\n"
        "import maya.cmds as cmds\n"
        "# Get all Arnold area lights (shape nodes)\n"
        "shapes = cmds.ls(type='aiAreaLight')\n"
        "if shapes:\n"
        "    # Get transform from shape\n"
        "    transform = cmds.listRelatives(shapes[0], parent=True, fullPath=True)[0]\n"
        "    # Modify color on shape\n"
        "    cmds.setAttr(shapes[0] + '.color', 0, 0, 1, type='double3')\n"
        "    # Modify position on transform\n"
        "    cmds.setAttr(transform + '.translateX', -5)\n"
        "```\n\n"
        "NEVER do this (causes NoneType error):\n"
        "```\n"
        "node = cmds.listConnections(light + '.message', d=False)[0]\n"
        "```"
    ),
    "vision": (
        "You are a visual quality inspector for 3D scenes.\n"
        "Look at the viewport screenshot carefully.\n"
        "Describe what you see in 2-3 lines.\n"
        "If a fix was applied, confirm if it worked or suggest adjustment.\n"
        "Talk naturally — not like a report."
    ),
    "summary": (
        "You are a conversation summariser.\n"
        "Summarise the conversation in 3-4 lines focusing on:\n"
        "- What was analysed\n"
        "- What was fixed\n"
        "- What is still pending\n"
        "Be concise and factual."
    ),
}


# ---------------------------------------------------------------------------
# Tooltip hints — shown on the model field in the Settings dialog
# ---------------------------------------------------------------------------

AGENT_TOOLTIPS = {
    "analyzer":   "Understands your scene. Use a smart model \u2014 gpt-4o, claude-3-5-sonnet",
    "codewriter": "Writes Maya Python. Use a code-focused model \u2014 gpt-4o, deepseek-coder",
    "vision":     "Reads images. Must support vision \u2014 gpt-4o, gemini-2.0-flash",
    "summary":    "Summarises chat. Any fast model works \u2014 llama3, mistral-small",
}

# Human-readable labels for the UI
AGENT_LABELS = {
    "analyzer":   "🔍 Analyzer",
    "codewriter": "🔧 Code Writer",
    "vision":     "👁 Vision",
    "summary":    "💬 Summary",
}


# ---------------------------------------------------------------------------
# Default settings — per-agent backend configuration
# ---------------------------------------------------------------------------

_BASE_AGENT_SETTINGS = {
    "backend":  "ollama",
    "base_url": "http://localhost:11434",
    "api_key":  "",
    "model":    "llama3",
}


def _build_agent_defaults(agent_key):
    """Build default settings for one agent, including its system prompt."""
    settings = dict(_BASE_AGENT_SETTINGS)
    settings["system_prompt"] = AGENT_PROMPTS.get(agent_key, "")
    return settings


DEFAULT_SETTINGS = {
    "mode": "single",
    "single": dict(_BASE_AGENT_SETTINGS),
    "analyzer":   _build_agent_defaults("analyzer"),
    "codewriter": _build_agent_defaults("codewriter"),
    "vision":     _build_agent_defaults("vision"),
    "summary":    _build_agent_defaults("summary"),
}


# ---------------------------------------------------------------------------
# Settings migration  (V2.5 flat → V3 per-agent)
# ---------------------------------------------------------------------------

def migrate_settings(data):
    """
    Migrate V2.5 flat settings to V3 per-agent format.

    V2.5 format:
        {"backend": "...", "base_url": "...", "api_key": "...",
         "model": "...", "system_prompt": "..."}

    V3 format:
        {"mode": "single"|"multi",
         "single": {"backend": ..., "base_url": ..., "api_key": ..., "model": ...},
         "analyzer": {...}, "codewriter": {...},
         "vision": {...}, "summary": {...}}

    Returns the (possibly migrated) settings dict.
    """
    # Already V3 format — just ensure all agent keys exist
    if "analyzer" in data and isinstance(data.get("analyzer"), dict):
        for agent_key in ("analyzer", "codewriter", "vision", "summary"):
            if agent_key not in data:
                data[agent_key] = _build_agent_defaults(agent_key)
            else:
                # Ensure system_prompt key exists (fill from defaults if missing)
                if "system_prompt" not in data[agent_key]:
                    data[agent_key]["system_prompt"] = AGENT_PROMPTS.get(agent_key, "")
        # Default mode to "multi" for existing V3 configs, "single" for new
        if "mode" not in data:
            data["mode"] = "multi"
        if "single" not in data:
            # Seed single config from analyzer
            a = data.get("analyzer", {})
            data["single"] = {
                "backend":  a.get("backend", "ollama"),
                "base_url": a.get("base_url", ""),
                "api_key":  a.get("api_key", ""),
                "model":    a.get("model", "llama3"),
            }
        return data

    # V2.5 flat format → migrate to single mode
    base = {
        "backend":  data.get("backend",  "ollama"),
        "base_url": data.get("base_url", "http://localhost:11434"),
        "api_key":  data.get("api_key",  ""),
        "model":    data.get("model",    "llama3"),
    }

    migrated = {"mode": "single", "single": dict(base)}
    for agent_key in ("analyzer", "codewriter", "vision", "summary"):
        agent = dict(base)
        agent["system_prompt"] = AGENT_PROMPTS[agent_key]
        migrated[agent_key] = agent

    # Preserve the old system prompt so the user can reference it
    old_prompt = data.get("system_prompt", "")
    if old_prompt:
        migrated["legacy_system_prompt"] = old_prompt

    return migrated


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

    def __init__(self, messages, settings, parent=None, search_mode=False):
        """
        Args:
            messages (list[dict]): Full conversation history
                                   [{"role": "user"|"assistant", "content": "..."}]
            settings (dict):       **Per-agent** settings dict
                                   (must include backend, base_url, api_key, model,
                                    and optionally system_prompt)
        """
        super().__init__(parent)
        self.messages = messages
        self.settings = settings
        self.search_mode = search_mode
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
                       "• Check model permissions at your provider's console")
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
        if self.search_mode:
            self.error.emit("⚠ Search mode requires an external API — not available with Ollama")
            self.done.emit()
            return

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
                "User-Agent": "MayaSceneDoctor/3.0",
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

        payload_dict = {
            "model":    model,
            "messages": messages,
            "stream":   True,
        }
        
        if self.search_mode:
            payload_dict["tools"] = [{
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for Maya tools, tutorials, and resources",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }]

        payload = json.dumps(payload_dict).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MayaSceneDoctor/3.0",
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
        """Prepend the system prompt to the message list and format images."""
        backend = self.settings.get("backend", "ollama")
        processed_msgs = []

        system = self.settings.get("system_prompt", "").strip()
        if system:
            processed_msgs.append({"role": "system", "content": system})

        for msg in self.messages:
            new_msg = {"role": msg.get("role", "user")}
            text = msg.get("content", "")
            img_b64 = msg.get("image_b64")

            if img_b64:
                if backend == "ollama":
                    new_msg["content"] = text
                    new_msg["images"] = [img_b64]
                else:
                    new_msg["content"] = [
                        {"type": "text", "text": text},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + img_b64}}
                    ]
            else:
                new_msg["content"] = text

            processed_msgs.append(new_msg)

        return processed_msgs


# ---------------------------------------------------------------------------
# Summary worker — non-streaming, returns a single response
# ---------------------------------------------------------------------------

class SummaryWorker(QThread):
    """
    Non-streaming worker that sends messages to the AI and returns
    a single complete response.  Used for conversation summarisation.

    Signals:
        result(str)  — the full summary text
        error(str)   — something went wrong
    """

    result = Signal(str)
    error  = Signal(str)

    def __init__(self, messages, settings, parent=None):
        """
        Args:
            messages (list[dict]): Messages to summarise
            settings (dict):       Summary agent's settings dict
        """
        super().__init__(parent)
        self.messages = messages
        self.settings = settings

    # ------------------------------------------------------------------
    def run(self):
        backend = self.settings.get("backend", "ollama")
        try:
            if backend == "ollama":
                self._call_ollama()
            else:
                self._call_openai()
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
                detail = body[:300]
            except Exception:
                pass
            self.error.emit("Summary API Error {}: {}".format(e.code, detail))
        except urllib.error.URLError as e:
            self.error.emit(
                "Summary: Cannot connect to {}. {}".format(
                    self.settings.get("base_url", "?"), str(e.reason)
                )
            )
        except Exception as e:
            self.error.emit("Summary error: {}".format(str(e)))

    # ------------------------------------------------------------------
    def _build_messages(self):
        """Prepend the system prompt to the message list."""
        processed = []
        system = self.settings.get("system_prompt", "").strip()
        if system:
            processed.append({"role": "system", "content": system})

        for msg in self.messages:
            processed.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })
        return processed

    # ------------------------------------------------------------------
    # Ollama  — POST /api/chat  (non-streaming)
    # ------------------------------------------------------------------
    def _call_ollama(self):
        url   = self.settings.get("base_url", "http://localhost:11434").rstrip("/")
        url  += "/api/chat"
        model = self.settings.get("model", "llama3")

        payload = json.dumps({
            "model":    model,
            "messages": self._build_messages(),
            "stream":   False,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "MayaSceneDoctor/3.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body)
            text = data.get("message", {}).get("content", "")
            self.result.emit(text.strip())

    # ------------------------------------------------------------------
    # OpenAI-compatible  — POST /chat/completions  (non-streaming)
    # ------------------------------------------------------------------
    def _call_openai(self):
        base_url = self.settings.get("base_url", "").rstrip("/")
        api_key  = self.settings.get("api_key",  "").strip()
        model    = self.settings.get("model",    "gpt-4o")

        if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
            self.error.emit("Summary agent: API key is empty. Check Settings.")
            return

        # Build correct endpoint
        if base_url.endswith("/chat/completions"):
            pass
        elif base_url.endswith("/v1"):
            base_url = base_url + "/chat/completions"
        else:
            base_url = base_url.rstrip("/") + "/v1/chat/completions"

        payload = json.dumps({
            "model":    model,
            "messages": self._build_messages(),
            "stream":   False,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MayaSceneDoctor/3.0",
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
            body = response.read().decode("utf-8")
            data = json.loads(body)
            choices = data.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "")
                self.result.emit(text.strip())
            else:
                self.result.emit("")
