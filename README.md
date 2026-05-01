# 🩺 Maya Scene Doctor AI — Multi-Agent

![Maya](https://img.shields.io/badge/Maya-2022%2B-blue)
![Python](https://img.shields.io/badge/Python-3.7%2B-yellow)
![License](https://img.shields.io/badge/License-MIT-green)

An intelligent, multi-agent AI assistant designed to live directly inside Autodesk Maya. It automatically scans your scene, identifies technical issues, and provides one-click Python fixes—all without you ever leaving the viewport.

![Screenshot](images/screenshot.png)

---

## ✨ Features

- **🔍 Automated Scene Scanning**: Instantly identifies missing lights, orphaned nodes, broken shaders, and unoptimized scene settings.
- **🔧 Multi-Agent Architecture**: 
  - **Analyzer**: Diagnoses the scene in plain language.
  - **Code Writer**: Generates safe, self-contained Maya Python fixes.
  - **Vision**: Analyzes viewport screenshots for visual quality checks.
- **🌍 Search Mode**: Manually trigger searches across Gumroad, GitHub, and 80 Level for relevant tools and tutorials.
- **🚀 Zero-Dependency**: Built using native Maya libraries (`urllib`, `PySide`). No complex `pip` installations or environment setup required.
- **🔗 Flexible Backends**: Supports local LLMs via **Ollama** or any OpenAI-compatible API (Groq, OpenRouter, GPT-4o, etc.).

---

## 🚀 Installation & Usage

1. **Download** this repository.
2. Place the folder `Scene_Doctor_3D` into your Maya scripts directory:
   - **Windows**: `Documents/maya/scripts/`
3. Open the **Maya Script Editor** and switch to a **Python** tab.
4. Paste and run the following code:

```python
import main
main.show()
```

---

## ⚙️ Configuration

1. Click the **Settings (⚙️)** button in the UI.
2. **Local Mode**: Use `http://localhost:11434` for Ollama.
3. **Cloud Mode**: Enter your API Key and Base URL for services like Groq or OpenAI.
4. Choose between **Single Agent** (fast/simple) or **Multi-Agent** (detailed/powerful) modes.

---

## 🤝 Contributing

Contributions are welcome! If you have suggestions for new agents or better scanning logic, feel free to open an issue or a pull request.

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

Built with ❤️ by **Ezz El-Din** | [LinkedIn](https://www.linkedin.com/in/ezzel-din-tarek-mostafa)
