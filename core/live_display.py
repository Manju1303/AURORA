"""
AURORA Live Display — Premium 25fps Holographic HUD
OpenCV · Pure Black BG · LED Fan Ready

HUD Elements:
  TOP-LEFT    → Real-time CPU / RAM / MIC stats
  TOP-RIGHT   → State badge (SPEAKING / THINKING / IDLE)
  CENTER      → Avatar with glow (from musetalk_engine)
  BOTTOM      → Glass caption bar:
                  • Typewriter speech text (AURORA)
                  • Audio waveform bars
                  • Previous user query (purple)
"""
import cv2
import numpy as np
import psutil
import time
import threading
import math

from core.avatar_manager import AvatarManager, AvatarState

TARGET_FPS = 25
FRAME_TIME = 1.0 / TARGET_FPS
DISPLAY_W, DISPLAY_H = 1024, 1024   # Optimized for 45cm Circular LED Fan
AVATAR_SIZE = 1024

# ── Colour Palette ─────────────────────────────────────────
C_CYAN   = (255, 230, 0)    # BGR: Cyan
C_PURPLE = (220, 80, 180)   # BGR: Purple
C_WHITE  = (240, 240, 240)
C_DIM    = (100, 100, 100)
C_GREEN  = (80, 220, 100)
C_RED    = (80, 80, 240)
C_ORANGE = (30, 160, 255)

STATE_COLOR = {
    AvatarState.IDLE:     (200, 200, 0),     # Cyan
    AvatarState.THINKING: (200, 80, 200),    # Purple
    AvatarState.SPEAKING: (80, 220, 80),     # Green
}
STATE_LABEL = {
    AvatarState.IDLE:     "● IDLE",
    AvatarState.THINKING: "◈ THINKING",
    AvatarState.SPEAKING: "◉ SPEAKING",
}


class LiveDisplay:
    def __init__(self, manager: AvatarManager, fullscreen: bool = False):
        self.manager = manager
        self.fullscreen = fullscreen
        self._running = True
        self.window_name = "AURORA_HOLOGRAM"

        # ── Speech / Caption state ──────────────────────────
        self.aurora_speech   = ""        # Full text
        self._typed_chars    = 0         # Typewriter progress
        self._type_timer     = 0.0
        self._type_speed     = 0.04      # Seconds per character
        self.user_query      = ""        # Previous user query
        self._speech_lock    = threading.Lock()

        # ── Waveform ────────────────────────────────────────
        self._wave_bars      = [0.0] * 24
        self._wave_lock      = threading.Lock()

        # ── Shared flags ────────────────────────────────────
        self._t = 0.0

    # ─────────────────────────────────────────────────────────
    #  PUBLIC API — called from avatar_manager / engine
    # ─────────────────────────────────────────────────────────

    def set_speech(self, text: str):
        with self._speech_lock:
            if text != self.aurora_speech:
                if not text.startswith(self.aurora_speech):
                    self._typed_chars = 0
                    self._type_timer = 0.0
                self.aurora_speech = text


    def set_user_query(self, text: str):
        with self._speech_lock:
            self.user_query = text

    def push_audio_energy(self, energy: float):
        """Call with RMS audio level (0‒1) for waveform bars."""
        with self._wave_lock:
            self._wave_bars.pop(0)
            self._wave_bars.append(min(1.0, max(0.0, energy)))

    # ─────────────────────────────────────────────────────────
    #  GLASS PANEL
    # ─────────────────────────────────────────────────────────

    def _glass_rect(self, canvas, x, y, w, h,
                    alpha=0.45, border_color=C_CYAN, radius=8):
        """Semi-transparent rounded-corner glass panel."""
        overlay = canvas.copy()
        cv2.rectangle(overlay, (x, y), (x + w, y + h), (20, 20, 30), -1)
        cv2.addWeighted(overlay, alpha, canvas, 1 - alpha, 0, canvas)
        # Border
        cv2.rectangle(canvas, (x, y), (x + w, y + h), border_color, 1, cv2.LINE_AA)
        # Top highlight line
        cv2.line(canvas, (x + radius, y), (x + w - radius, y),
                 tuple(min(255, c + 80) for c in border_color), 1, cv2.LINE_AA)

    # ─────────────────────────────────────────────────────────
    #  TEXT HELPERS
    # ─────────────────────────────────────────────────────────

    def _put_text(self, canvas, text, pos, color=C_WHITE,
                  scale=0.55, thickness=1, font=cv2.FONT_HERSHEY_SIMPLEX):
        x, y = pos
        # Shadow
        cv2.putText(canvas, text, (x + 1, y + 1), font, scale, (0, 0, 0), thickness + 1, cv2.LINE_AA)
        cv2.putText(canvas, text, pos, font, scale, color, thickness, cv2.LINE_AA)

    # ─────────────────────────────────────────────────────────
    #  TOP-LEFT: SYSTEM STATS
    # ─────────────────────────────────────────────────────────

    def _draw_stats(self, canvas):
        cpu  = psutil.cpu_percent()
        ram  = psutil.virtual_memory().percent

        panel_x, panel_y = 14, 14
        panel_w, panel_h = 200, 90
        self._glass_rect(canvas, panel_x, panel_y, panel_w, panel_h,
                         alpha=0.5, border_color=C_CYAN)

        self._put_text(canvas, "⬡ SYSTEM", (panel_x + 8, panel_y + 20),
                       C_CYAN, scale=0.5)

        # CPU bar
        self._draw_meter(canvas, "CPU", cpu,
                         panel_x + 8, panel_y + 38,
                         180, C_GREEN if cpu < 70 else C_ORANGE)
        # RAM bar
        self._draw_meter(canvas, "RAM", ram,
                         panel_x + 8, panel_y + 62,
                         180, C_PURPLE if ram < 75 else C_RED)
        # State pulse dot
        state = self.manager.state
        sc = STATE_COLOR[state]
        pulse = int(180 + 75 * math.sin(self._t * 4))
        dot_color = tuple(min(255, int(c * pulse / 255)) for c in sc)
        cv2.circle(canvas, (panel_x + panel_w - 14, panel_y + 14), 5, dot_color, -1, cv2.LINE_AA)

    def _draw_meter(self, canvas, label, value, x, y, bar_w, color):
        """Labelled percentage bar."""
        self._put_text(canvas, f"{label}", (x, y), C_DIM, scale=0.38)
        # Background track
        cv2.rectangle(canvas, (x + 28, y - 9), (x + 28 + bar_w, y - 1), (40, 40, 50), -1)
        # Fill
        fill = max(2, int(bar_w * value / 100))
        cv2.rectangle(canvas, (x + 28, y - 9), (x + 28 + fill, y - 1), color, -1)
        # Percentage text
        self._put_text(canvas, f"{value:.0f}%", (x + 28 + bar_w + 5, y - 1),
                       C_WHITE, scale=0.38)

    # ─────────────────────────────────────────────────────────
    #  TOP-RIGHT: STATE BADGE
    # ─────────────────────────────────────────────────────────

    def _draw_state_badge(self, canvas):
        state = self.manager.state
        label = STATE_LABEL[state]
        color = STATE_COLOR[state]

        # Pulsing glow
        pulse = 0.7 + 0.3 * math.sin(self._t * 5)
        bc = tuple(min(255, int(c * pulse)) for c in color)

        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        px = DISPLAY_W - tw - 30
        py = 14
        self._glass_rect(canvas, px - 8, py, tw + 16, 30, alpha=0.5, border_color=bc)
        self._put_text(canvas, label, (px, py + 20), bc, scale=0.6, thickness=1)

    # ─────────────────────────────────────────────────────────
    #  BOTTOM: CAPTION BAR
    # ─────────────────────────────────────────────────────────

    def _draw_caption_bar(self, canvas, dt: float):
        # ── Typewriter text ─────────────────────────────────
        with self._speech_lock:
            full_text   = self.aurora_speech
            user_query  = self.user_query

            # Advance typewriter
            if self._typed_chars < len(full_text):
                self._type_timer += dt
                while self._type_timer >= self._type_speed and self._typed_chars < len(full_text):
                    self._typed_chars  += 1
                    self._type_timer   -= self._type_speed

            display_text = full_text[:self._typed_chars]

        # Float safely above the bottom curve of the circular fan
        bar_y  = DISPLAY_H - 240
        tx = 150
        max_w = DISPLAY_W - 300

        # Word-wrap speech
        words = display_text.split()
        line, lines = "", []
        for w in words:
            test = (line + " " + w).strip()
            (tw, _), _ = cv2.getTextSize(test, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            if tw > max_w:
                lines.append(line)
                line = w
            else:
                line = test
        if line:
            lines.append(line)

        # Draw User Query (floating purple text) above the speech
        if user_query:
            q_text = f"You: {user_query}"
            if len(q_text) > 80:
                q_text = q_text[:77] + "..."
            self._put_text(canvas, q_text, (tx, bar_y - 25), C_PURPLE, scale=0.55, thickness=2)

        # Draw AURORA Speech (floating white text)
        if len(lines) > 0:
            self._put_text(canvas, "AURORA ›", (tx - 120, bar_y + 10), C_CYAN, scale=0.6, thickness=2)
            for i, l in enumerate(lines[:3]):
                self._put_text(canvas, l, (tx, bar_y + 10 + i * 30), C_WHITE, scale=0.7, thickness=2)

        # Cursor blink
        if self._typed_chars < len(full_text) and len(lines) > 0:
            blink = int(self._t * 6) % 2 == 0
            if blink:
                last_line = display_text.split('\n')[-1] if lines else ""
                (tw, _), _ = cv2.getTextSize(last_line, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                y_offset = (len(min(lines, key=len) and lines[:3]) - 1) * 30 if len(lines) <= 3 else 60
                cv2.rectangle(canvas, (tx + tw + 10, bar_y - 10 + y_offset), (tx + tw + 20, bar_y + 15 + y_offset), C_CYAN, -1)

    # ─────────────────────────────────────────────────────────
    #  COMPOSITE
    # ─────────────────────────────────────────────────────────

    def _composite(self, avatar_frame: np.ndarray) -> np.ndarray:
        canvas = np.zeros((DISPLAY_H, DISPLAY_W, 3), dtype=np.uint8)

        # Center the 512x512 avatar
        aw, ah = AVATAR_SIZE, AVATAR_SIZE
        ax = (DISPLAY_W - aw) // 2
        ay = (DISPLAY_H - ah) // 2   # Centered for square Fan

        frame = cv2.resize(avatar_frame, (aw, ah))
        
        # JPEG Visibility Fix: Place directly without aggressive dark-masking
        canvas[ay:ay + ah, ax:ax + aw] = frame
        return canvas

    # ─────────────────────────────────────────────────────────
    #  MAIN LOOP
    # ─────────────────────────────────────────────────────────

    def run(self):
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        if self.fullscreen:
            cv2.setWindowProperty(self.window_name,
                                  cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN)
        else:
            cv2.resizeWindow(self.window_name, DISPLAY_W, DISPLAY_H)

        print(f"[LiveDisplay] {DISPLAY_W}x{DISPLAY_H} @ {TARGET_FPS}fps — "
              f"{'FULLSCREEN' if self.fullscreen else 'WINDOWED'}")
        print("[LiveDisplay] Press Q to quit.")

        prev_t = time.time()

        while self._running:
            now = time.time()
            dt  = now - prev_t
            prev_t = now
            self._t += dt

            # 1. Get avatar frame
            frame  = self.manager.get_current_frame()
            canvas = self._composite(frame)

            # 2. Overlay HUD elements (DISABLED for LED Fan Mode)
            # self._draw_stats(canvas)
            # self._draw_state_badge(canvas)
            
            # Re-enabled: Floating Holographic Captions
            self._draw_caption_bar(canvas, dt)

            cv2.imshow(self.window_name, canvas)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                self._running = False
                break

            # Maintain FPS
            elapsed = time.time() - now
            sleep_t = FRAME_TIME - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

        cv2.destroyAllWindows()

    def stop(self):
        self._running = False
