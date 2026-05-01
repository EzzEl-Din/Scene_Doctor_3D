# 🩺 Maya Scene Doctor AI — V3 (Multi-Agent)

![Maya](https://img.shields.io/badge/Maya-2022%2B-blue)
![Python](https://img.shields.io/badge/Python-3.7%2B-yellow)
![License](https://img.shields.io/badge/License-MIT-green)

An AI assistant that lives inside Maya. It automatically scans your scene, explains what's wrong and why, suggests fixes with runnable code, and can even verify its own work — all without leaving Maya.

![Screenshot](images/screenshot.png)

**V3** introduces a **multi-agent architecture** — specialized AI agents for analysis, code writing, vision, and summarisation — plus a **single-agent mode** for quick setup.

Built by **Ezz El-Din** | [LinkedIn](https://www.linkedin.com/in/ezzel-din-tarek-mostafa)

---

## ✨ Features

### Core
- **Auto-scan on open** — no manual button needed.
- **Prioritized report** — 🔴 Critical / 🟡 Warning / 🟢 Info.
- **Plain language** — explains WHY each issue matters.
- **Chat per scene** — history saves and loads automatically per `.ma` / `.mb` file.
- **Smart re-scan** — AI decides on its own when it needs fresh scene data.
- **Real-time streaming** — responses appear token by token like ChatGPT.
- **Any AI backend** — local (Ollama) or any OpenAI-compatible API.
- **🚀 Zero-Dependency** — Built using native Maya libraries (`urllib`, `PySide`). No complex `pip` installations required.

### Multi-Agent Architecture (V3)
- **🔍 Analyzer** — reads scene data and describes issues in plain text.
- **🔧 Code Writer** — writes clean Maya Python fixes based on the analysis.
- **👁 Vision** — evaluates viewport screenshots to verify fixes.
- **💬 Summary** — auto-summarises long conversations to save context.
- **Single Agent mode** — use one model for everything (simpler setup).
- **Multi Agent mode** — assign different models per agent (advanced).

### Vision
- **Viewport screenshots** — click 📷 to capture and send the viewport to the AI.
- **Clipboard paste** — paste images directly with Ctrl+V.
- **Drag & drop** — drop image files onto the window.
- **Vision compatibility** — warns if the selected model may not support images.

### Code Execution
- **Runnable code blocks** — AI suggests Maya Python fixes inside `▶ Run` / `✕ Dismiss` buttons.
- **Editable before running** — review and tweak the code before executing.
- **Safe execution** — code runs in a sandboxed namespace with `cmds`, `mel`, and `os`.

### Agentic Auto-Check
- **Self-verifying fixes** — after running code, the Vision agent automatically takes a viewport screenshot and evaluates the result.
- **Iterative fixes** — if something looks wrong, the AI suggests another fix (up to 3 attempts).
- **Hands-free workflow** — run a fix and let the AI confirm it worked without manual checking.

### Search Mode
- **Web search** — toggle 🔍 search mode to find tools, plugins, and tutorials.
- **Searches Gumroad, GitHub, and 80 Level** for relevant resources.

---

## 🔍 Deep Scene Scanning Capabilities

The doctor analyzes every corner of your Maya scene:
- **Meshes**: Vertex/face/tri counts, non-manifold geometry, lamina faces, frozen transforms, construction history.
- **Materials**: Shading groups, missing textures with absolute file paths.
- **Lights**: Type, intensity, color, position, visibility, and issues (zero intensity, hidden, black color, overexposure).
- **Cameras**: Focal length, clipping planes, renderable flag, z-fighting detection.
- **Rigs & Joints**: Joint hierarchy, skin clusters, locked attributes.
- **Render layers**: Enabled state, empty layers, member counts.
- **References**: Loaded/unloaded status, missing files.
- **Unknown nodes**: Missing plugin detection.
- **Animation**: Anim curve count, infinity extrapolation issues.
- **Render settings**: Active renderer, resolution, render range.

---

## 📁 Repository Structure

```
Scene_Doctor_3D/
├── main.py          ← UI + chat window (run this)
├── scanner.py       ← reads Maya scene data
├── ai_backend.py    ← handles AI communication (multi-agent)
├── images/          ← UI screenshots and assets
├── LICENSE          ← MIT License
└── README.md
```

---

## ⚙️ Requirements

- Autodesk Maya 2020 or newer.
- Python 3 (already included with Maya).
- One of the following:
  - **Ollama** (free, runs locally — no internet needed).
  - **Any OpenAI-compatible API** — OpenRouter, Groq, Mistral, OpenAI...

> **Note:** For vision features (screenshots & image paste), use a model that supports images — e.g. Llama 4, GPT-4o, Gemini 2, or Claude.

---

## 🚀 Installation & Usage

1. **Download** all files and place them in your Maya scripts folder:
   - **Windows**: `Documents/maya/scripts/`
2. Open **Maya**.
3. Open the **Script Editor** (Windows → General Editors → Script Editor).
4. Make sure the tab is set to **Python**.
5. Paste and run:

```python
import main
main.show()
```

---

## 🔧 Setup — Choose Your AI

Click **⚙ Settings** in the tool to configure.

### Option A: Local (Ollama — free, offline)
1. Download Ollama from [ollama.com](https://ollama.com).
2. Run in terminal: `ollama pull llama3`.
3. In Settings: Set Backend to `Local (Ollama)`, Base URL to `http://localhost:11434`, and Model to `llama3`.

### Option B: External API (OpenRouter, Groq, etc.)
1. Create an account on [OpenRouter](https://openrouter.ai) or [Groq](https://groq.com).
2. Generate an API key.
3. In Settings: Set Backend to `External API`, paste your API Key, and enter the Model name (e.g., `gpt-4o`).

---

## 💬 How to Use

1. **Open any Maya scene** — the tool auto-scans and shows a report immediately.
2. **Read the AI's analysis** — issues are prioritized by severity with a health score.
3. **Ask follow-up questions** — chat naturally about your scene.
4. **Send images** — click 📷 for a viewport screenshot, or Ctrl+V to paste from clipboard.
5. **Run suggested fixes** — click `▶ Run` on code blocks the AI provides.
6. **Let the AI verify** — the AI automatically checks the viewport and confirms the fix worked.
7. **Search for tools** — toggle 🔍 search mode and ask about plugins or tutorials.

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

Built with ❤️ by **Ezz El-Din** | [LinkedIn](https://www.linkedin.com/in/ezzel-din-tarek-mostafa)
