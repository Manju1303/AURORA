"""
TTS Bridge — High-Fidelity Audio output for AURORA.
Uses Edge-TTS for premium voice + Pygame Mixer for low-latency playback.
Automatic offline fallback to pyttsx3.
"""
import asyncio
import threading
import queue
import time
import os
import pygame
import edge_tts
import pyttsx3

# ── Shared State ─────────────────────────────────────────────
tts_state = {"speaking": False, "text": ""}
tts_queue = queue.Queue()
_state_lock = threading.Lock()

TEMP_DIR = os.path.join(os.getcwd(), "temp_audio")
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

def clear_temp_audio():
    """Wipe the temp_audio folder on startup."""
    try:
        for f in os.listdir(TEMP_DIR):
            if f.endswith(".mp3"):
                os.remove(os.path.join(TEMP_DIR, f))
        print(f"[TTS] 🧹 Cleaned {TEMP_DIR}")
    except Exception as e:
        print(f"[TTS] Cleanup skip: {e}")


def _set_speaking(val: bool, text: str = ""):
    with _state_lock:
        tts_state["speaking"] = val
        tts_state["text"] = text


def tts_worker():
    """Background thread that converts text to high-quality audio and plays it."""
    # Cleanup old chunks before starting
    clear_temp_audio()
    
    # Initialize Pygame Mixer if not done
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
    except:
        pass

    # Backup offline engine
    backup_engine = None
    try:
        backup_engine = pyttsx3.init()
        # Natural rate
        backup_engine.setProperty('rate', 165)
    except:
        pass

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            text = tts_queue.get(block=True)
            if text is None: break  # Shutdown
            
            _set_speaking(True, text)
            print(f"[TTS] 🔉 Processing: {text[:40]}...")
            
            # 1. Attempt Edge-TTS (Premium Online Voice)
            filename = os.path.join(TEMP_DIR, f"chunk_{int(time.time() * 1000)}.mp3")
            success = False
            try:
                # Optimized for speed: aria voice
                communicate = edge_tts.Communicate(text, "en-US-AriaNeural", rate="+15%")
                loop.run_until_complete(communicate.save(filename))
                
                # Play via pygame
                pygame.mixer.music.load(filename)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
                
                success = True
            except Exception as e:
                # If Edge-TTS fails (internet down), use backup SAPI5
                print(f"[TTS] Edge-TTS fail/offline, using backup: {e}")
                if backup_engine:
                    try:
                        backup_engine.say(text)
                        backup_engine.runAndWait()
                        success = True
                    except:
                        pass
            
            # Clean up temp files
            if os.path.exists(filename):
                try: os.remove(filename)
                except: pass

            tts_queue.task_done()
            if tts_queue.empty():
                _set_speaking(False)

        except Exception as e:
            print(f"[TTS Worker Critical] {e}")
            time.sleep(0.5)


# ── Start the dedicated worker immediately ────────────────────
_worker = threading.Thread(target=tts_worker, daemon=True)
_worker.start()


# ── Public API ───────────────────────────────────────────────

def speak(text: str):
    """Synchronous call — queues text for immediate playback."""
    if text and text.strip():
        # Remove markdown/formatting before speaking
        clean_text = text.replace("**", "").replace("__", "").replace("*", "").replace("`", "")
        tts_queue.put(clean_text.strip())


async def speak_chunk(text: str, voice: str = "en-US-AriaNeural"):
    """Async-compatible wrapper — delegates to the thread worker."""
    speak(text)


def is_speaking() -> bool:
    """Returns True while TTS is actively outputting sound."""
    with _state_lock:
        try:
            # Check pygame state as well
            playing = pygame.mixer.music.get_busy() if pygame.mixer.get_init() else False
            return tts_state["speaking"] or playing or not tts_queue.empty()
        except:
            return tts_state["speaking"] or not tts_queue.empty()


def get_current_text() -> str:
    """Returns the text currently being spoken."""
    with _state_lock:
        return tts_state["text"]


def stop():
    """Interrupt current speech and clear the queue."""
    while not tts_queue.empty():
        try:
            tts_queue.get_nowait()
            tts_queue.task_done()
        except queue.Empty:
            break
            
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except:
        pass
        
    _set_speaking(False)
    print("[TTS] Speech interrupted and queue cleared.")
