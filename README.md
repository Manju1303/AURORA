# AURORA — Holographic AI Voice Assistant v3.0 🌌

AURORA is a high-performance, 3D holographic assistant designed for advanced exhibitions. She features **hands-free interaction**, **"Live RAG" (Fact-checking)**, and a **ultra-low latency voice-to-voice pipeline**.

---

## 🚀 Key Features

### 1. 🧠 "Live RAG" (Retrieval-Augmented Generation)
AURORA does not just "guess" answers. When asked a factual question (e.g., *"Who is the current PM of UK?"*), she:
- **Background Searches**: Silently fetches live snippets from the web (via custom DuckDuckGo scraper).
- **Fact-Checks**: Analyzes the snippets to ground her answer in recent truth.
- **Zero Hallucination**: Delivers accurate, real-world data instantly without a browser popping up.

### 2. ⚡ Ultra-Low Latency Pipeline
- **Ollama-Ooptimized**: Primary brain runs locally on **Phi-3 Mini** for millisecond responses.
- **15s Cloud Fallback**: If local inference lags, she instantly fails over to **Groq (Llama 3.1 70B)** or **SambaNova** to keep the conversation seamless.
- **Instant Triggers**: Common queries (Time, Weather, System Stats, Math) are handled via dedicated **Skills** to bypass LLM latency entirely.

### 3. 🛡️ Silent & Respectful Mode
- **No Unwanted Browsers**: Factual RAG happens 100% in the background. The browser only opens if you explicitly say *"Open browser"*.
- **Professional Persona**: AURORA is strictly respectful and avoids all informal fillers or "da/ga" colloquialisms.

### 4. 📊 3D Neural HUD
- **Real-time Telemetry**: The GUI displays live **CPU and RAM** usage.
- **Spectrum Visualization**: Real-time audio waveform feedback.
- **Conversation Log**: A premium, glass-morphism chat history panel that auto-scrolls.

---

## 🛠️ Architecture

- **Core Engine**: `core/engine.py` (Main loop, voice handling, skill routing)
- **Brain**: `core/llm_manager.py` (Ollama, Groq, SambaNova backends)
- **STT/TTS**: `core/stt_manager.py` (Faster-Whisper), `core/tts_bridge.py` (`Edge-TTS`).
- **Memory**: `core/memory_manager.py` (SQLite-based persistent long-term memory).
- **Skills**:
  - `skills/web_ops.py`: Scrapers for Google/DuckDuckGo/Weather.
  - `skills/math_ops.py`: Instant math processor.
  - `skills/system_ops.py`: OS-level controls (Apps, Volume, Screenshots).
  - `skills/fun_ops.py`: Local joke bank and facts.
- **GUI**: `gui/aurora3d.html` (Three.js 3D Hologram, Telemetry HUD).

---

## 🆕 Recent Updates

### 🎙️ Enhanced Audio Pipeline
Switched to **Edge-TTS** and **Pygame** for high-fidelity, studio-quality voice output. This update resolves previous audio clipping issues and provides full support for Bluetooth speakers and Windows audio drivers.

### 🌌 Holographic LED Fan Optimization
The interface has been specifically refined for **1024x1024 holographic LED fans**. Removed HUD borders, base rings, and background grids to achieve a clean "floating" 3D effect.

### 🧠 Persistent Brain Evolution
AURORA now learns from every conversation. Using `MemoryManager`, she extracts facts and preferences, storing them in a local **SQLite database** (`aurora_memory.db`) to provide personalized experiences over time.

### ⚡ One-Click Ecosystem
Added optimized launch scripts (`start.bat` and `start_aurora.ps1`) that automatically initialize the STT/TTS engines, the WebSocket bridge, and the holographic GUI in one go.

---

## 🏃 Quick Start

1. **Start Ollama**:
   ```powershell
   ollama pull phi3:mini
   ollama serve
   ```
2. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```
3. **Configure Environment**:
   Update `.env` with your API keys (optional for fallback) and set `LLM_BACKEND=ollama`.
4. **Launch**:
   ```powershell
   python main.py
   ```

---

## 🛑 Requirements
- **Python**: 3.11+
- **Voice**: PyAudio, SpeechRecognition, edge-tts, pygame.
- **Local AI**: Ollama (phi3:mini).

---

## 🏛️ Project Evolution

### **v1.0: Foundations 🏗️**
- Core engine for voice-to-voice interaction.
- Basic AI brain using local **Ollama (Phi-3 Mini)**.
- Integrated **pyttsx3** for simple text-to-speech.

### **v2.0: The Hologram 🌌**
- Added **Three.js-based 3D interface** with neural waveform visualization.
- Implemented **Glass-morphism Telemetry HUD** (CPU/RAM/Logs).
- Added WebSocket bridge to sync voice engine with GUI display.

### **v2.5: Intelligence Boost 🧠**
- **Live RAG Integration**: Added silent background web searches for real-time facts.
- **Skill Engine**: Implemented native command handlers (Weather, Time, System Controls).
- **Multimodal**: Support for avatar image/video background processing.

### **v3.0: Studio Fidelity 🎙️**
- Switched to **Edge-TTS (Azure-based)** for studio-quality voices.
- Replaced standard audio drivers with **Pygame Mixer** for seamless Bluetooth output.
- **1024x1024 Optimization**: Refined UI specifically for 3D LED Fan exhibition devices.

### **v4.0: Autonomous Personality (Latest) ✨**
- **Long-Term Memory**: AURORA now stores facts in SQLite to "remember" users over time.
- **Interface Minimalism**: Removed HUD borders, rings, and grids for a true "floating" hologram effect.
- **Unified Startup**: Integrated `start_aurora.ps1` to launch the entire ecosystem in one click.

---

**AURORA — Optimized for Reality, Designed for Tomorrow.**
