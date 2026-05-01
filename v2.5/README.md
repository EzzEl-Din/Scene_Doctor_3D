# 🩺 Maya Scene Doctor AI — v2.5

An AI assistant that lives inside Maya. It automatically scans your scene, explains what's wrong and why, suggests fixes with runnable code, and can even verify its own work — all without leaving Maya.

Built by **Ezz El-Din** | [LinkedIn](https://www.linkedin.com/in/ezzel-din-tarek-mostafa)

---

## ✨ Features

### Core
- **Auto-scan on open** — no manual button needed
- **Prioritized report** — 🔴 Critical / 🟡 Warning / 🟢 Info
- **Plain language** — explains WHY each issue matters
- **Chat per scene** — history saves and loads automatically per `.ma` / `.mb` file
- **Smart re-scan** — AI decides on its own when it needs fresh scene data
- **Real-time streaming** — responses appear token by token like ChatGPT
- **Any AI backend** — local (Ollama) or any OpenAI-compatible API

### Vision (v2.0+)
- **Viewport screenshots** — click 📷 to capture and send the viewport to the AI
- **Clipboard paste** — paste images directly with Ctrl+V
- **Vision compatibility** — warns if the selected model may not support images

### Code Execution (v2.0+)
- **Runnable code blocks** — AI suggests Maya Python fixes inside `▶ Run` / `✕ Dismiss` buttons
- **Editable before running** — review and tweak the code before executing
- **Safe execution** — code runs in a sandboxed namespace with `cmds`, `mel`, and `os`

### Agentic Auto-Check (v2.5)
- **Self-verifying fixes** — after running code, the AI automatically takes a viewport screenshot and evaluates the result
- **Iterative fixes** — if something looks wrong, the AI suggests another fix (up to 3 attempts)
- **Hands-free workflow** — run a fix and let the AI confirm it worked without manual checking

### Deep Scene Scanning
- **Meshes** — vertex/face/tri counts, non-manifold geometry, lamina faces, frozen transforms, construction history
- **Materials** — shading groups, missing textures with file paths
- **Lights** — type, intensity, color, position, visibility, and issues (zero intensity, hidden, black color, overexposure)
- **Cameras** — focal length, clipping planes, renderable flag, z-fighting detection
- **Rigs & Joints** — joint hierarchy, skin clusters, locked attributes
- **Render layers** — enabled state, empty layers, member counts
- **References** — loaded/unloaded status, missing files
- **Unknown nodes** — missing plugin detection
- **Animation** — anim curve count, infinity extrapolation issues
- **Render settings** — active renderer, resolution, render range

---

## 📁 Files

```
maya_scene_doctor/
├── main.py          ← UI + chat window (run this)
├── scanner.py       ← reads Maya scene data
├── ai_backend.py    ← handles AI communication
├── settings.json    ← auto-generated on first use
└── README.md
```

---

## ⚙️ Requirements

- Autodesk Maya 2020 or newer
- Python 3 (already included with Maya)
- One of the following:
  - **Ollama** (free, runs locally — no internet needed)
  - **Any OpenAI-compatible API** — OpenRouter, Groq, Mistral, OpenAI...

> **Note:** For vision features (screenshots & image paste), use a model that supports images — e.g. Llama 4 Maverick, GPT-4o, Gemini 2, or Claude.

---

## 🚀 Installation

1. Download all 3 `.py` files and place them in the same folder
2. Open Maya
3. Open the **Script Editor** (Windows → General Editors → Script Editor)
4. Make sure the tab is set to **Python**
5. Paste and run:

```python
import sys
sys.path.insert(0, "C:/path/to/maya_scene_doctor")  # change this to your folder
import main
main.show()
```

---

## 🔧 Setup — Choose Your AI

### Option A: Local (Ollama — free, offline)

1. Download Ollama from [ollama.com](https://ollama.com)
2. Run in terminal:
   ```
   ollama pull llama3
   ```
3. In the tool: click **⚙ Settings**
   - Backend: `ollama`
   - Base URL: `http://localhost:11434`
   - Model: `llama3`

### Option B: External API (OpenRouter, Groq, etc.)

1. Create a free account on [openrouter.ai](https://openrouter.ai) or [groq.com](https://groq.com)
2. Generate an API key
3. In the tool: click **⚙ Settings**
   - Backend: `openai`
   - Base URL: `https://openrouter.ai/api/v1`
   - API Key: paste your key
   - Model: `meta-llama/llama-4-maverick:free`

---

## 💬 How to Use

1. **Open any Maya scene** — the tool auto-scans and shows a report immediately
2. **Read the AI's analysis** — issues are prioritized by severity with a health score
3. **Ask follow-up questions** — chat naturally about your scene
4. **Send images** — click 📷 for a viewport screenshot, or Ctrl+V to paste from clipboard
5. **Run suggested fixes** — click `▶ Run` on code blocks the AI provides, or `✕ Dismiss` to skip
6. **Let the AI verify** — after running a fix, the AI automatically checks the viewport and confirms or suggests another fix
7. **Chat history persists** — reopen the scene and your conversation is still there

### Example questions:
- *"What's the most important thing to fix first?"*
- *"How do I fix the missing textures?"*
- *"Is my scene ready for rigging?"*
- *"Add a three-point lighting setup"*
- *"The shadows look too harsh, can you adjust the lights?"*

---

## ⚠️ Beta Notice

This is an early release. It works, but improvements are coming.
Feedback from TDs and artists is very welcome — DM me on LinkedIn.

---

## 📄 License

Free to use. Not for resale.
