"""
AURORA Engine — Live Conversation Core
Ultra-Low Latency Voice Pipeline with Real-Time STT → LLM → TTS
"""
import asyncio
import json
import threading
import queue
import time
import os
import pygame
import sqlite3
import websockets
import logging
import psutil
import pyttsx3
import platform
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("AURORA")

load_dotenv()

# ── Voice Input Detection ─────────────────────────────────────
try:
    import speech_recognition as sr
    VOICE_ENABLED = True
except ImportError:
    VOICE_ENABLED = False
    print("[INFO] SpeechRecognition not found. Basic voice fallback disabled.")

from skills.system_ops import SystemSkill
from skills.web_ops import WebSkill
from skills.fun_ops import FunSkill
from skills.math_ops import MathSkill
from core.llm_manager import LLMManager
from core.stt_manager import STTManager
from core import tts_bridge

LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")


class AuroraEngine:
    def __init__(self, api_key=None):
        self.db_path = "aurora_memory.db"
        self._init_db()

        print(f"\n[LLM] Initializing {LLM_BACKEND.upper()} backend...")
        self.llm_manager = LLMManager(preferred_backend=LLM_BACKEND)

        if not self.llm_manager.active_backend:
            print("[⚠️ CRITICAL] No LLM available!")
            print("[SOLUTION] Install Ollama: https://ollama.ai")
            print("[COMMAND] ollama pull phi3:mini && ollama serve")
            raise RuntimeError("No LLM backend available")

        # ── Skills ───────────────────────────────────────────
        self.skills = [SystemSkill(), WebSkill(), FunSkill(), MathSkill()]
        self.tools = []
        self.functions = {}
        for skill in self.skills:
            skill_tools = skill.get_tools()
            for tool in skill_tools:
                if isinstance(tool, dict):
                    if "function_declarations" in tool:
                        for fd in tool["function_declarations"]:
                            self.tools.append(fd)
                    elif "function" in tool:
                        self.tools.append(tool["function"])
                    else:
                        self.tools.append(tool)
            self.functions.update(skill.get_functions())

        self.chat_session = None

        # ── State ────────────────────────────────────────────
        self.current_stage = 0
        self.visitor_count = 0
        self.global_visitors = self._get_global_visitors()
        self.is_running = True
        self.connected_display = None
        self.ws_loop = None       # WS server event loop
        self.main_loop = None     # Main pipeline event loop
        self.db_lock = threading.Lock()
        self.manual_trigger = False
        self.reset_requested = False

        # ── STT ──────────────────────────────────────────────
        print("[INIT] Initializing Faster-Whisper STT engine...")
        try:
            self.stt_manager = STTManager()
        except Exception as e:
            print(f"[WARN] STT failed to init: {e}")
            self.stt_manager = None

        # ── Audio ────────────────────────────────────────────
        try:
            pygame.mixer.init()
            print("[INIT] Audio: OK")
        except Exception as e:
            print(f"[WARN] Pygame audio init failed: {e}")

        # ── Memory ───────────────────────────────────────────
        from core.memory_manager import MemoryManager
        self.memory_mgr = MemoryManager()

        # ── System Prompt ────────────────────────────────────
        self.system_prompt = f"""You are AURORA, a premium holographic AI assistant.
        Today's date is {datetime.now().strftime('%B %d, %Y')}.
        RULES:
        1. Be strictly professional, polite, and efficient.
        2. Responses MUST be maximum 2 sentences.
        3. Avoid all informal fillers like "da", "ga", "buddy", or "bro".
        4. Focus on accuracy and millisecond-latency.
        5. Use provided context to personalize your response if available."""
        print("\n" + "="*50)
        print("  ✅ AURORA ENGINE READY — Live Conversation Mode")
        print("="*50)

    # ─────────────────────────────────────────────────────────
    #  DATABASE
    # ─────────────────────────────────────────────────────────

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)")
            conn.execute("INSERT OR IGNORE INTO stats VALUES ('total_visitors', 0)")
            conn.execute("CREATE TABLE IF NOT EXISTS logs (timestamp TEXT, role TEXT, content TEXT)")
            conn.commit()

    def _get_global_visitors(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT value FROM stats WHERE key='total_visitors'")
                val = cursor.fetchone()
                return val[0] if val else 0
        except:
            return 0

    def _increment_visitors(self):
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("UPDATE stats SET value = value + 1 WHERE key='total_visitors'")
                    conn.commit()
                self.global_visitors += 1
            except:
                pass

    # ─────────────────────────────────────────────────────────
    #  WEBSOCKET BROADCAST (GUI HUD)
    # ─────────────────────────────────────────────────────────

    async def broadcast(self, data):
        if self.connected_display:
            try:
                await self.connected_display.send(json.dumps(data))
            except:
                self.connected_display = None

    def update_hud(self, **kwargs):
        """Update GUI HUD with telemetry and AI state."""
        try:
            kwargs["cpu"] = f"{psutil.cpu_percent()}%"
            kwargs["ram"] = f"{psutil.virtual_memory().percent}%"
        except:
            pass

        payload = {"visitors": self.visitor_count, "global_visitors": self.global_visitors}
        payload.update(kwargs)

        if "stage" in kwargs:
            self.current_stage = kwargs["stage"]

        # Send to WS server loop (not main loop)
        if self.ws_loop and self.ws_loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self.ws_loop)

    # ─────────────────────────────────────────────────────────
    #  TTS SPEAK
    # ─────────────────────────────────────────────────────────

    def stop_speaking(self):
        """Stop current speech output immediately."""
        tts_bridge.stop()
        self.update_hud(speaking=False)
        print("[AURORA] (Interrupted)")

    def speak(self, text):
        """Speak text via tts_bridge."""
        if not text:
            return
        print(f"[AURORA] 🔊 {text}")
        logger.info(f"AURORA: {text}")
        self.update_hud(speech=text, speaking=True)
        try:
            tts_bridge.speak(text)
        except Exception as e:
            logger.error(f"[TTS Error] {e}")
            try:
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except:
                pass

    # ─────────────────────────────────────────────────────────
    #  LIVE PIPELINE (Main Conversation Loop)
    # ─────────────────────────────────────────────────────────

    async def run_live_pipeline(self):
        """
        AURORA Live Pipeline — Continuous real-time voice conversation.
        Flow: Listen → Transcribe → Think (RAG+LLM Stream) → Speak → Repeat
        """
        print("\n" + "=" * 55)
        print("  🤖 AURORA LIVE — Real-Time Voice Conversation")
        print("=" * 55)

        if not self.stt_manager:
            print("[ERROR] No STT engine available. Cannot start live pipeline.")
            return

        # Introduce and greet user
        greet_text = "I am AURORA, your universal holographic assistant. Greetings! How can I assist you today?"
        self.update_hud(stage=4, speech=greet_text, action="wave")
        tts_bridge.speak(greet_text)

        # Wait for greeting to finish
        await asyncio.sleep(0.5)
        while tts_bridge.is_speaking():
            await asyncio.sleep(0.1)

        while self.is_running:
            try:
                # ── 1. LISTEN ────────────────────────────────
                self.update_hud(stage=5, speech="🎤 Listening...")
                print("\n[AURORA] 🎤 Listening...")

                user_text = await self._listen_async()

                if not user_text:
                    continue

                print(f"[USER] 🗣️  {user_text}")
                self.update_hud(stage=6, user_text=user_text, speech="Thinking...")

                # ── 2. INSTANT TASK CHECK ────────────────────
                handled = await self._handle_instant_tasks(user_text)
                if handled:
                    # Wait for TTS to finish then go back to listening
                    await self._wait_for_tts()
                    continue

                # ── 3. RAG CONTEXT FETCH ─────────────────────
                rag_context = await self._fetch_rag_context(user_text)

                # ── 4. BUILD CONTEXT PROMPT ──────────────────
                current_context = self.system_prompt + self.memory_mgr.get_context_prompt()
                if rag_context:
                    current_context += f"\n\nVERIFIED REAL-TIME FACTS (use these to answer):\n{rag_context}"
                    print(f"[RAG] 📡 Context: {rag_context[:120]}...")

                # ── 5. STREAM LLM RESPONSE → TTS ─────────────
                self.update_hud(stage=7, speech="Speaking...")
                full_response = ""
                display_response = ""

                async for chunk in self.llm_manager.chat_stream(user_text, current_context):
                    if not chunk or not chunk.strip():
                        continue
                    
                    full_response += chunk + " "
                    display_response += chunk + " "
                    
                    print(f"[AURORA] 🤖 {chunk}")
                    # Push cumulative text to HUD so it doesn't flicker/reset
                    self.update_hud(stage=8, speech=display_response.strip(), speaking=True)
                    tts_bridge.speak(chunk)

                self.update_hud(speaking=False)

                # ── 6. LEARN / EVOLVE ────────────────────────
                if full_response.strip():
                    fact = self.memory_mgr.learn_fact(user_text, full_response)
                    if fact:
                        print(f"[MEMORY] 🧠 {fact}")
                        self.memory_mgr.save()

                # ── 7. WAIT FOR TTS TO FINISH ────────────────
                await self._wait_for_tts()

            except asyncio.CancelledError:
                print("[AURORA] Pipeline cancelled.")
                break
            except Exception as e:
                print(f"[ERROR] Live pipeline error: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(1)

    async def _listen_async(self) -> str:
        """
        Non-blocking async listen: starts STT in background,
        waits for the first transcription result.
        """
        result_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def on_transcription(text: str):
            if text and text.strip():
                loop.call_soon_threadsafe(result_queue.put_nowait, text)

        # Don't listen while AURORA is speaking
        while tts_bridge.is_speaking():
            await asyncio.sleep(0.1)

        self.stt_manager.is_paused = False
        self.stt_manager.current_callback = on_transcription
        self.stt_manager.start_listening(on_transcription)

        # Wait for result (no timeout — just keep listening)
        try:
            user_text = await asyncio.wait_for(result_queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            print("[STT] Timeout waiting for speech. Still listening...")
            return ""

        self.stt_manager.pause_listening()
        return user_text

    async def _wait_for_tts(self, max_wait: float = 30.0):
        """Wait for all TTS audio to finish playing."""
        waited = 0.0
        await asyncio.sleep(0.3)  # Small buffer to let queue fill
        while tts_bridge.is_speaking() and waited < max_wait:
            await asyncio.sleep(0.1)
            waited += 0.1

    # ─────────────────────────────────────────────────────────
    #  INSTANT TASK HANDLING
    # ─────────────────────────────────────────────────────────

    async def _handle_instant_tasks(self, user_text: str) -> bool:
        """Detect and execute real-time tasks instantly without LLM."""
        text = user_text.lower().strip()
        import re

        # ── TIME / DATE ───────────────────────────────────────
        if any(w in text for w in ["time", "date", "clock", "today"]):
            resp = json.loads(self.functions["get_time"]())
            msg = f"It is {resp['time']} on {resp['date']}."
            self._speak_task(msg)
            return True

        # ── OPEN APPS ─────────────────────────────────────────
        if "open " in text or "launch " in text:
            app = text.replace("open ", "").replace("launch ", "").strip()
            app = app.replace("chrome browser", "chrome").replace("visual studio code", "vscode")
            resp = json.loads(self.functions["open_app"](app_name=app))
            if resp.get("status") in ("success", "attempted"):
                msg = f"Launching {app} for you."
            else:
                msg = f"I couldn't find {app} to launch."
            self._speak_task(msg)
            return True

        # ── VOLUME ────────────────────────────────────────────
        if "volume" in text and ("set" in text or "to" in text):
            match = re.search(r'\d+', text)
            if match:
                level = int(match.group())
                self.functions["set_volume"](level=level)
                msg = f"System volume set to {level} percent."
                self._speak_task(msg)
                return True

        # ── SCREENSHOT ────────────────────────────────────────
        if any(w in text for w in ["screenshot", "screen shot", "capture screen"]):
            msg = "Capturing your screen now."
            self._speak_task(msg)
            self.functions["take_screenshot"]()
            return True

        # ── WEATHER ───────────────────────────────────────────
        if any(k in text for k in ["weather", "temperature", "climate", "raining", "sunny"]):
            clean = text
            for filler in ["what is the", "how is the", "tell me the", "weather in", "weather at",
                           "temperature in", "weather", "now", "today", "current"]:
                clean = clean.replace(filler, "")
            location = clean.strip().title()
            if len(location) < 2:
                location = "Coimbatore"
            weather_res = json.loads(self.functions["get_weather"](city=location))
            if "weather" in weather_res:
                msg = f"The current weather in {location} is {weather_res['weather']}."
            else:
                msg = f"I could not reach the weather service for {location} right now."
            self._speak_task(msg)
            return True

        # ── MATH ──────────────────────────────────────────────
        math_kw = ["+", "-", "*", "/", "plus", "minus", "divided by", "times", "percent of", "square root"]
        if any(k in text for k in math_kw) and any(c.isdigit() for c in text):
            res = json.loads(self.functions["calculate"](text))
            if res.get("status") == "success":
                msg = f"The result is {res['result']}."
                self._speak_task(msg)
                return True

        return False

    def _speak_task(self, msg: str):
        print(f"[TASK] 🤖 {msg}")
        self.update_hud(stage=7, speech=msg, speaking=True)
        tts_bridge.speak(msg)

    # ─────────────────────────────────────────────────────────
    #  RAG CONTEXT FETCH
    # ─────────────────────────────────────────────────────────

    async def _fetch_rag_context(self, user_text: str) -> str:
        """
        RAG Layer: Fetch real-time web context for factual questions.
        Times out after 4s to keep conversation flowing.
        """
        text = user_text.lower().strip()
        FACTUAL_TRIGGERS = [
            "who is", "what is", "what are", "tell me about", "explain",
            "where is", "when did", "how does", "news", "weather", "latest",
            "define", "meaning of", "history of", "capital of", "population",
            "score", "price", "cost", "cricket", "match", "movie", "song",
        ]
        is_factual = any(trigger in text for trigger in FACTUAL_TRIGGERS)
        word_count = len(user_text.split())

        if not is_factual and word_count < 4:
            return ""

        loop = asyncio.get_event_loop()
        try:
            raw = await asyncio.wait_for(
                loop.run_in_executor(None, self.functions["web_rag"], user_text),
                timeout=4.0
            )
            result = json.loads(raw)
            if result.get("status") == "success":
                snippets = result.get("snippets", [])
                return " ".join(snippets)[:400]
        except asyncio.TimeoutError:
            print("[RAG] ⏱️  Timeout — proceeding without context.")
        except Exception as e:
            print(f"[RAG] Error: {e}")

        return ""

    # ─────────────────────────────────────────────────────────
    #  WEBSOCKET SERVER (GUI Bridge)
    # ─────────────────────────────────────────────────────────

    async def ws_handler(self, websocket, path=None):
        self.connected_display = websocket
        print("[WS] 🔌 GUI display connected.")
        try:
            async for message in websocket:
                data = json.loads(message)
                if data.get("action") == "WAKE":
                    self.manual_trigger = True
                elif data.get("action") == "RESET":
                    self.reset_requested = True
        except:
            pass
        finally:
            self.connected_display = None
            print("[WS] GUI display disconnected.")

    # ─────────────────────────────────────────────────────────
    #  START
    # ─────────────────────────────────────────────────────────

    def start(self):
        """
        Start AURORA:
        1. WebSocket server in a background thread (for GUI HUD)
        2. Live voice pipeline in the main thread (async event loop)
        """
        # Start WS server in a background thread with its own event loop
        def start_ws_server():
            async def run_server():
                async with websockets.serve(self.ws_handler, "localhost", 8765):
                    await asyncio.Future()  # Run forever

            self.ws_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.ws_loop)
            try:
                self.ws_loop.run_until_complete(run_server())
            except Exception as e:
                print(f"[WS Server Error] {e}")

        ws_thread = threading.Thread(target=start_ws_server, daemon=True)
        ws_thread.start()
        time.sleep(0.5)  # Let WS server boot up
        print("[WS] WebSocket server started on ws://localhost:8765")

        # Run live pipeline in the main thread's event loop
        self.main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.main_loop)
        try:
            self.main_loop.run_until_complete(self.run_live_pipeline())
        except KeyboardInterrupt:
            print("\n[AURORA] Shutting down...")
        finally:
            self.is_running = False
            if self.stt_manager:
                self.stt_manager.stop_listening()
            self.main_loop.close()
            print("[AURORA] Goodbye.")
