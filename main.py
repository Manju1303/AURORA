"""
AURORA — Main Entry Point
Boots AI Engine + Hologram Display in separate threads/processes.
"""
import os
import sys
import argparse
import threading
import time
from dotenv import load_dotenv

from core.engine import AuroraEngine
from core.avatar_manager import AvatarManager
from core.live_display import LiveDisplay


def start_ai_engine(engine: AuroraEngine):
    """Run the AURORA AI engine (voice pipeline) in a background thread."""
    try:
        engine.start()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[AI CORE ERROR] Engine thread stopped: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="AURORA Full System Launcher")
    parser.add_argument("--fullscreen", action="store_true", help="Launch in LED Fan full-screen mode")
    parser.add_argument("--test", action="store_true", help="Launch in GUI test mode")
    parser.add_argument("--image", default="gui/avatar.jpeg", help="Path to avatar image")
    parser.add_argument("--video", default="gui/avatar.mp4", help="Path to lip-sync video")
    parser.add_argument("--no-gui", action="store_true", help="Run voice-only mode without hologram window")
    args = parser.parse_args()

    load_dotenv()

    print("-" * 65)
    print("   AURORA — AI-Powered Smart Interactive Voice Assistant")
    print("   Live Conversation Mode: STT → LLM Stream → TTS")
    print("-" * 65)

    # ── Init Engine ───────────────────────────────────────────
    try:
        engine = AuroraEngine()
    except RuntimeError as e:
        print(f"\n[CRITICAL ERROR] {e}")
        sys.exit(1)

    if args.no_gui:
        # ── Voice-Only Mode ───────────────────────────────────
        print("[SYSTEM] Running in voice-only mode (no hologram window).")
        engine.start()
    else:
        # ── Full Mode: Voice + Hologram Display ───────────────

        # 1. Start AI Engine in background thread
        print("[SYSTEM] Booting AI Neural Engine in background thread...")
        ai_thread = threading.Thread(target=start_ai_engine, args=(engine,), daemon=True)
        ai_thread.start()

        # Give engine a moment to initialize
        time.sleep(1.0)

        # 2. Start Hologram Display in main GUI thread (required by Windows/OpenCV)
        print("[SYSTEM] Booting Hologram Window...")
        try:
            # Auto-detect idle vs speaking videos if standard filenames exist
            idle_vid = "gui/avatar.mp4" if os.path.exists("gui/avatar.mp4") else args.video
            speak_vid = "gui/avatar lip.mp4" if os.path.exists("gui/avatar lip.mp4") else args.video
            
            manager = AvatarManager(avatar_path=args.image, idle_video=idle_vid, speaking_video=speak_vid)
            display = LiveDisplay(manager=manager, fullscreen=args.fullscreen)
            manager.display = display

            # Start avatar sync thread (reads TTS state for lip-sync)
            manager.start_sync()

            print("[SYSTEM] ✅ All systems live — AURORA is ready!")
            print("[SYSTEM] Press Q in the hologram window to quit.")

            # Blocks here — runs the display loop
            display.run()

        except Exception as e:
            print(f"[DISPLAY ERROR] {e}")
            import traceback
            traceback.print_exc()

        # ── Shutdown ──────────────────────────────────────────
        print("\n[SYSTEM] Initiating safe shutdown...")
        engine.is_running = False
        time.sleep(0.5)
        sys.exit(0)


if __name__ == "__main__":
    main()
