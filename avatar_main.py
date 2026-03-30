"""
AURORA Avatar Main — One-click launcher for the live hologram pipeline.

Usage:
  python avatar_main.py                          # Normal laptop preview
  python avatar_main.py --fullscreen             # HDMI → LED Fan (tomorrow)
  python avatar_main.py --test                   # Test all states (no mic)

Args:
  --image     Path to avatar photo (default: gui/avatar.png)
  --video     Path to action video (default: gui/avatar.mp4)
  --fullscreen  Run fullscreen for HDMI fan output
  --test      Run IDLE → THINKING → SPEAKING cycle and exit
"""
import argparse
import threading
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.avatar_manager import AvatarManager, AvatarState
from core.live_display import LiveDisplay
from core import tts_bridge


def run_test(manager: AvatarManager, display: LiveDisplay):
    """
    Test cycle: IDLE → THINKING → SPEAKING → IDLE
    Verifies the entire visual pipeline without needing a microphone.
    """
    def _cycle():
        print("\n[TEST] ── Starting Avatar Pipeline Test ──")
        time.sleep(2)
        
        print("[TEST] State: IDLE (5 seconds)")
        manager.set_state(AvatarState.IDLE)
        display.set_user_query("(waiting for your voice...)")
        display.set_speech("")
        time.sleep(5)

        print("[TEST] State: THINKING (3 seconds)")
        manager.set_state(AvatarState.THINKING)
        display.set_speech("Processing your request...")
        time.sleep(3)

        print("[TEST] State: SPEAKING (5 seconds — simulating voice)")
        manager.set_state(AvatarState.SPEAKING)
        display.set_user_query("Tell me about yourself")
        display.set_speech("Hello! I am AURORA, your holographic AI assistant. I am ready to assist you with anything you need.")
        tts_bridge.tts_state["speaking"] = True
        tts_bridge.speak("Hello! I am AURORA, your holographic AI assistant. I am ready to assist you.")
        tts_bridge.tts_state["speaking"] = False
        time.sleep(1)

        print("[TEST] State: IDLE — Test complete!")
        manager.set_state(AvatarState.IDLE)
        time.sleep(3)

        print("[TEST] ✅ All states verified. Closing display.")
        display.stop()

    t = threading.Thread(target=_cycle, daemon=True)
    t.start()


def main():
    parser = argparse.ArgumentParser(description="AURORA Live Avatar Hologram")
    parser.add_argument("--image", default="gui/avatar.jpeg", help="Avatar image path")
    parser.add_argument("--video", default="gui/avatar.mp4", help="Action video path")
    parser.add_argument("--fullscreen", action="store_true", help="Fullscreen for LED Fan (HDMI)")
    parser.add_argument("--test", action="store_true", help="Run state test cycle")
    args = parser.parse_args()

    print("\n" + "=" * 55)
    print("  AURORA v3.0 — Live Hologram Avatar System")
    print("  Mode:", "TEST" if args.test else ("FULLSCREEN (LED Fan)" if args.fullscreen else "WINDOWED (Laptop Preview)"))
    print("=" * 55)

    # 1. Avatar Manager
    manager = AvatarManager(avatar_path=args.image, video_path=args.video)

    # 2. Live Display
    display = LiveDisplay(manager=manager, fullscreen=args.fullscreen)

    # 3. Link display ↔ manager (enables live caption sync)
    manager.display = display

    if args.test:
        run_test(manager, display)
    else:
        manager.start_sync()
        print("[Avatar] TTS sync ACTIVE — AURORA's voice will drive avatar & captions automatically.")
        print("[Avatar] Now run: python main.py (in another terminal)")
        print("[Avatar] Press Q in the window to stop.\n")

    # 4. Start display loop (blocks)
    display.run()
    print("[Avatar] Hologram stopped. Goodbye!")


if __name__ == "__main__":
    main()
