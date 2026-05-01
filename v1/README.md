# 🩺 Maya Scene Doctor AI — Beta v1

An AI assistant that lives inside Maya. It automatically scans your scene, explains what's wrong and why, and lets you chat to fix things — all without leaving Maya.

Built by **Ezz El-Din** | [LinkedIn](https://www.linkedin.com/in/ezzel-din-tarek-mostafa)

---

## ✨ Features

- **Auto-scan on open** — no manual button needed
- **Prioritized report** — 🔴 Critical / 🟡 Warning / 🟢 Info
- **Plain language** — explains WHY each issue matters
- **Chat per scene** — history saves and loads automatically per `.ma` / `.mb` file
- **Smart re-scan** — AI decides on its own when it needs fresh scene data
- **Real-time streaming** — responses appear token by token like ChatGPT
- **Any AI backend** — local (Ollama) or any OpenAI-compatible API

---

## 📁 Files

```
maya_scene_doctor/
├── main.py          ← UI + chat window (run this)
├── scanner.py       ← reads Maya scene data
├── ai_backend.py    ← handles AI communication
└── README.md
```

---

## ⚙️ Requirements

- Autodesk Maya 2020 or newer
- Python 3 (already included with Maya)
- One of the following:
  - **Ollama** (free, runs locally — no internet needed)
  - **Any OpenAI-compatible API** — OpenRouter, Groq, Mistral, OpenAI...

---

## 🚀 Installation

1. Download all 3 files and place them in the same folder
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

1. Open any Maya scene
2. The tool auto-scans and shows a report immediately
3. Read the AI's analysis and ask follow-up questions
4. Chat history is saved automatically — reopen the scene and your chat is still there
5. Ask things like:
   - *"What's the most important thing to fix first?"*
   - *"How do I fix the missing textures?"*
   - *"Is my scene ready for rigging?"*

---

## ⚠️ Beta Notice

This is an early release. It works, but improvements are coming.
Feedback from TDs and artists is very welcome — DM me on LinkedIn.

---

## 📄 License

Free to use. Not for resale.
