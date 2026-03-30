"""
AURORA Avatar Manager — State machine for IDLE / THINKING / SPEAKING.
Reads tts_bridge state and drives the MuseTalk/Parallax engine.
"""
import threading
import time
from enum import Enum

from core import tts_bridge
from core.musetalk_engine import MuseTalkEngine


class AvatarState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    SPEAKING = "speaking"


class AvatarManager:
    def __init__(self, avatar_path: str, idle_video: str = None, speaking_video: str = None):
        self.engine = MuseTalkEngine(avatar_path, idle_video, speaking_video)
        self.idle_video = idle_video
        self.speaking_video = speaking_video
        self.state = AvatarState.IDLE
        self.speech_count = 0  # To track intro vs live conversation
        self.t = 0.0
        self._lock = threading.Lock()
        self._running = True
        self.display = None   # Set by avatar_main.py after LiveDisplay is created
        print(f"[AvatarManager] Initialized — State: {self.state.value}")

    def set_state(self, state: AvatarState):
        with self._lock:
            if self.state != state:
                print(f"[AvatarManager] {self.state.value.upper()} → {state.value.upper()}")
                self.state = state

    def get_current_frame(self):
        """Returns the correct frame based on current avatar state."""
        with self._lock:
            state = self.state
        
        self.t += 0.04  # ~25fps time step
        
        if state == AvatarState.SPEAKING:
            # Special request: use idle_video for the VERY FIRST speech (Introduction)
            # then use speaking_video for all future conversation chunks.
            if self.speech_count <= 1:
                return self.engine.generate_idle_frame(self.t)
            else:
                return self.engine.generate_speaking_frame(self.t, audio_energy=0.7)
        elif state == AvatarState.THINKING:
            return self.engine.generate_thinking_frame(self.t)
        else:
            return self.engine.generate_idle_frame(self.t)

    def sync_with_tts(self):
        """Background thread: sync avatar state + captions with tts_bridge."""
        while self._running:
            speaking = tts_bridge.is_speaking()
            if speaking:
                if self.state != AvatarState.SPEAKING:
                    self.speech_count += 1  # Increment on start of speaking
                self.set_state(AvatarState.SPEAKING)
                # Push current speech text to display typewriter
                current_text = tts_bridge.get_current_text()
                if self.display and current_text:
                    self.display.set_speech(current_text)
            else:
                self.set_state(AvatarState.IDLE)
            time.sleep(0.05)

    def start_sync(self):
        """Start the background state-sync thread."""
        t = threading.Thread(target=self.sync_with_tts, daemon=True)
        t.start()
        return t

    def stop(self):
        self._running = False
