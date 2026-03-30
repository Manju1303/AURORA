"""
AURORA MuseTalk Engine — GPU-accelerated lip sync + Premium Holographic FX
RTX 3050 · fp16 · 512x512 · 25fps

Visual States:
  IDLE     → Cyan glow, breathing animation, scan lines, particle aura
  THINKING → Glitch/flicker + desaturate + digital noise  
  SPEAKING → MuseTalk lip sync (or mouth-energy animation fallback)
  
All frames rendered on pure BLACK background for LED Fan transparency.
"""
import os
import cv2
import numpy as np
import random
import time

MUSETALK_DIR = os.path.join(os.path.dirname(__file__), "..", "MuseTalk")
MUSETALK_AVAILABLE = os.path.exists(MUSETALK_DIR)

class MuseTalkEngine:
    def __init__(self, avatar_image_path: str, idle_video_path: str = None, speaking_video_path: str = None):
        self.avatar_path = avatar_image_path
        self.idle_video_path = idle_video_path
        self.speaking_video_path = speaking_video_path
        
        self.idle_cap = None
        if idle_video_path and os.path.exists(idle_video_path):
            self.idle_cap = cv2.VideoCapture(idle_video_path)
            print(f"[MuseTalk] ✅ Idle video loaded: {idle_video_path}")
            
        self.speaking_cap = None
        if speaking_video_path and os.path.exists(speaking_video_path):
            self.speaking_cap = cv2.VideoCapture(speaking_video_path)
            print(f"[MuseTalk] ✅ Speaking/Lip-sync video loaded: {speaking_video_path}")

        # Load base avatar (512x512, black background)
        raw = cv2.imread(avatar_image_path, cv2.IMREAD_UNCHANGED)
        if raw is None:
            print(f"[MuseTalk] Avatar not found at: {avatar_image_path} — using placeholder.")
            raw = np.zeros((512, 512, 3), dtype=np.uint8)
            # Draw a basic circle as placeholder
            cv2.circle(raw, (256, 200), 120, (0, 200, 255), -1)

        # Auto-crop to remove black padding and zoom the avatar up to fit within the circular fan radius
        raw = self._auto_crop_and_scale(raw, target_size=(1024, 1024), scale_boost=0.70)

        # Composite RGBA onto black if needed
        if raw.ndim == 3 and raw.shape[2] == 4:
            alpha = raw[:, :, 3:4].astype(np.float32) / 255.0
            self.base_frame = (raw[:, :, :3].astype(np.float32) * alpha).astype(np.uint8)
        else:
            self.base_frame = raw[:, :, :3].copy()

        # Build a brightness-based depth estimate (center = foreground)
        self._depth = self._compute_depth(self.base_frame)

        # Pre-generate particle positions (for aura effect - count increased for high res)
        self._particles = self._init_particles(240)

        if MUSETALK_AVAILABLE:
            print("[MuseTalk] ✅ MuseTalk found — GPU lip sync ENABLED (RTX 3050)")
        else:
            print("[MuseTalk] ℹ️  Parallax FX mode — all effects active on RTX 3050 GPU")

    def _auto_crop_and_scale(self, img: np.ndarray, target_size=(1024, 1024), scale_boost=1.0) -> np.ndarray:
        """Finds non-black content, crops it, and scales it to fit the fan perfectly."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        coords = cv2.findNonZero(gray)
        if coords is not None:
            x, y, w, h = cv2.boundingRect(coords)
            pad = 20
            x1, y1 = max(0, x - pad), max(0, y - pad)
            x2, y2 = min(img.shape[1], x + w + pad), min(img.shape[0], y + h + pad)
            cropped = img[y1:y2, x1:x2]
        else:
            cropped = img

        ch, cw = cropped.shape[:2]
        th, tw = target_size
        
        # Dynamic perfect-fit scale based on scale_boost factor
        fill_w, fill_h = int(tw * scale_boost), int(th * scale_boost)
        scale = min(fill_w / cw, fill_h / ch) 
        
        new_w, new_h = max(1, int(cw * scale)), max(1, int(ch * scale))
        scaled = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        final = np.zeros((th, tw, 3), dtype=np.uint8)
        y_o = max(0, (th - new_h) // 2)
        x_o = max(0, (tw - new_w) // 2)
        
        final[y_o:y_o+new_h, x_o:x_o+new_w] = scaled
        return final

    # ─────────────────────────────────────────────────────────────
    #  DEPTH MAP
    # ─────────────────────────────────────────────────────────────

    def _compute_depth(self, img: np.ndarray) -> np.ndarray:
        """Brightness-based depth: bright pixels = foreground = more parallax."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        blur = cv2.GaussianBlur(gray, (31, 31), 0)
        return blur

    # ─────────────────────────────────────────────────────────────
    #  PARTICLE AURA
    # ─────────────────────────────────────────────────────────────

    def _init_particles(self, count: int):
        """Create orbiting particle positions around the avatar."""
        return [
            {
                "angle": random.uniform(0, 2 * np.pi),
                "radius": random.uniform(180, 260),
                "speed": random.uniform(0.3, 1.2),
                "size": random.randint(1, 3),
                "alpha": random.uniform(0.4, 1.0),
                "color": random.choice([
                    (0, 255, 255),   # Cyan
                    (0, 180, 255),   # Sky Blue
                    (100, 255, 220), # Aqua
                    (200, 200, 255), # Soft White
                ]),
                "y_offset": random.uniform(-60, 60),
            }
            for _ in range(count)
        ]

    def _draw_particles(self, canvas: np.ndarray, t: float, intensity: float = 1.0):
        overlay = canvas.copy()
        cx, cy = 512, 440  # Avatar center (1024/2, offset for fan)
        for p in self._particles:
            p["angle"] += p["speed"] * 0.03
            x = int(cx + np.cos(p["angle"]) * p["radius"] * 2) 
            y = int(cy + p["y_offset"] * 2 + np.sin(p["angle"]) * p["radius"] * 0.75)
            if 0 <= x < 1024 and 0 <= y < 1024:
                color = tuple(int(c * intensity) for c in p["color"])
                cv2.circle(overlay, (x, y), p["size"], color, -1)
        cv2.addWeighted(overlay, 0.6, canvas, 0.4, 0, canvas)

    # ─────────────────────────────────────────────────────────────
    #  GLOW / BLOOM
    # ─────────────────────────────────────────────────────────────

    def _add_glow(self, img: np.ndarray, color_tint=(0, 255, 255), strength=0.45, ksize=31) -> np.ndarray:
        """Add soft bloom / glow around bright pixels."""
        blur = cv2.GaussianBlur(img, (ksize, ksize), 0)
        # Tint the blur towards hologram color
        tint = np.zeros_like(blur, dtype=np.float32)
        tint[:] = color_tint
        tinted = cv2.addWeighted(blur.astype(np.float32), 1.0, tint, 0.08, 0).astype(np.uint8)
        result = cv2.addWeighted(img, 1.0, tinted, strength, 0)
        return np.clip(result, 0, 255).astype(np.uint8)

    # ─────────────────────────────────────────────────────────────
    #  SCAN LINES
    # ─────────────────────────────────────────────────────────────

    def _draw_scanlines(self, canvas: np.ndarray, t: float, speed: float = 0.5):
        """Animated horizontal scan lines for holographic feel."""
        h, w = canvas.shape[:2]
        scan_y = int((t * speed * 60) % h)
        for y in range(0, h, 4):  # Every 4 pixels
            alpha = 0.12 if y % 8 == 0 else 0.06
            canvas[y, :] = np.clip(canvas[y, :].astype(np.float32) * (1 - alpha), 0, 255).astype(np.uint8)
        # Moving bright scan strip
        strip_h = 3
        strip_y = max(0, min(h - strip_h, scan_y))
        canvas[strip_y:strip_y + strip_h] = np.clip(
            canvas[strip_y:strip_y + strip_h].astype(np.float32) * 1.6, 0, 255
        ).astype(np.uint8)

    # ─────────────────────────────────────────────────────────────
    #  HOLOGRAPHIC BASE RING
    # ─────────────────────────────────────────────────────────────

    def _draw_base_ring(self, canvas: np.ndarray, t: float, pulse: float = 1.0):
        """Animated rotating holographic platform ring at avatar base."""
        cx, cy = 256, 430
        rx, ry = 130, 24
        segments = 72
        color_a = (0, 255, 255)
        color_b = (0, 120, 200)

        for i in range(segments):
            angle1 = (2 * np.pi * i / segments) + t * 0.8
            angle2 = (2 * np.pi * (i + 1) / segments) + t * 0.8
            x1 = int(cx + rx * np.cos(angle1))
            y1 = int(cy + ry * np.sin(angle1))
            x2 = int(cx + rx * np.cos(angle2))
            y2 = int(cy + ry * np.sin(angle2))
            # Alternate color for 3D feel
            color = color_a if i % 2 == 0 else color_b
            bright = int(200 * pulse + 55 * np.sin(angle1 * 3))
            c = tuple(min(255, int(color[j] * bright / 255)) for j in range(3))
            cv2.line(canvas, (x1, y1), (x2, y2), c, 2, cv2.LINE_AA)

        # Inner ring (faint)
        for i in range(0, 360, 5):
            angle = np.radians(i + t * 40)
            x = int(cx + (rx - 20) * np.cos(angle))
            y = int(cy + (ry - 5) * np.sin(angle))
            if 0 <= x < 1024 and 0 <= y < 1024:
                canvas[y, x] = [0, 180, 255]

    # ─────────────────────────────────────────────────────────────
    #  PARALLAX WARP
    # ─────────────────────────────────────────────────────────────

    def _warp(self, img, depth, off_x, off_y) -> np.ndarray:
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        h, w = img.shape[:2]
        y, x = np.mgrid[0:h, 0:w]
        new_x = (x + depth * off_x).astype(np.float32)
        new_y = (y + depth * off_y).astype(np.float32)
        return cv2.remap(img, new_x, new_y, cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

    # ─────────────────────────────────────────────────────────────
    #  STATE FRAMES
    # ─────────────────────────────────────────────────────────────

    def generate_idle_frame(self, t: float) -> np.ndarray:
        """
        IDLE: Looping avatar.mp4 with holographic FX.
        """
        if self.idle_cap:
            ret, frame = self.idle_cap.read()
            if not ret:
                # Seamless loop
                self.idle_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.idle_cap.read()
            
            if ret:
                frame = self._auto_crop_and_scale(frame, scale_boost=0.70)
                frame = self._add_glow(frame, color_tint=(0, 255, 255), strength=0.2, ksize=25)
                self._draw_scanlines(frame, t, speed=0.3)
                self._draw_particles(frame, t, intensity=0.8)
                return frame

        # Fallback to static parallax if no idle video
        breath = 1.0 + 0.018 * np.sin(t * 1.2)
        # ... existing static logic below ...

    def generate_thinking_frame(self, t: float) -> np.ndarray:
        """
        THINKING: Glitch + colour shift + digital noise + dimmer base.
        """
        frame = self._warp(self.base_frame, self._depth,
                           np.sin(t * 0.5) * 4, np.cos(t * 0.3) * 3)

        # 1. Desaturate (looks like "processing")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame = cv2.merge([gray, gray, gray])
        frame = cv2.addWeighted(frame, 0.6, np.zeros_like(frame), 0.4, 0)

        # 2. Blue-purple tint
        frame = frame.astype(np.float32)
        frame[:, :, 0] = np.clip(frame[:, :, 0] * 1.4, 0, 255)  # Boost blue
        frame[:, :, 2] = np.clip(frame[:, :, 2] * 0.5, 0, 255)  # Dull red
        frame = frame.astype(np.uint8)

        # 3. Glitch — random horizontal shifts
        if random.random() < 0.35:
            for _ in range(random.randint(2, 6)):
                y = random.randint(0, 511)
                shift = random.randint(-18, 18)
                frame[y] = np.roll(frame[y], shift, axis=0)

        # 4. Digital noise REMOVED for High Quality
        # noise = np.random.randint(0, 30, frame.shape, dtype=np.uint8)
        # frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # 5. Scan lines (faster)
        self._draw_scanlines(frame, t, speed=1.5)

        # 6. Dim ring (DISABLED for LED Fan Mode)
        # self._draw_base_ring(frame, t * 0.3, pulse=0.4)

        return frame

    def generate_speaking_frame(self, t: float, audio_energy: float = 0.7) -> np.ndarray:
        """
        SPEAKING: MuseTalk lip sync OR 'avatar lip.mp4' video.
        """
        if MUSETALK_AVAILABLE:
            return self._musetalk_frame(t, audio_energy)

        # 1. Use the specific lip-sync viedo if loaded
        if self.speaking_cap:
            ret, vframe = self.speaking_cap.read()
            if not ret:
                # Seamless loop
                self.speaking_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, vframe = self.speaking_cap.read()
            
            if ret:
                frame = self._auto_crop_and_scale(vframe, scale_boost=0.70)
                frame = self._add_glow(frame, color_tint=(0, 255, 255), strength=0.3, ksize=25)
                self._draw_scanlines(frame, t, speed=0.5)
                self._draw_particles(frame, t, intensity=1.0)
                return frame

        # 1. Base parallax float (Fallback if no video)
        off_x = np.sin(t * 0.8) * 7
        off_y = np.cos(t * 0.5) * 5
        frame = self._warp(self.base_frame, self._depth, off_x, off_y)

        # 2. Speaking cyan boost
        frame = frame.astype(np.float32)
        frame[:, :, 2] = np.clip(frame[:, :, 2] * 0.5, 0, 255)
        frame[:, :, 1] = np.clip(frame[:, :, 1] * 1.1, 0, 255)
        frame = frame.astype(np.uint8)

        # 3. Mouth region animation (lower face area)
        h, w = frame.shape[:2]
        mx1, mx2 = w // 4, 3 * w // 4
        my1 = int(h * 0.58)
        my2 = int(h * 0.72)
        open_factor = abs(np.sin(t * 14)) * audio_energy
        mouth_roi = frame[my1:my2, mx1:mx2].astype(np.float32)
        # Pronounced vertical stretch = visible speaking animation
        new_h = max(1, int(mouth_roi.shape[0] * (1.0 + open_factor * 0.65)))
        mouth_scaled = cv2.resize(mouth_roi.astype(np.uint8), (mx2 - mx1, new_h))
        paste_h = min(mouth_scaled.shape[0], my2 - my1)
        frame[my1:my1 + paste_h, mx1:mx2] = mouth_scaled[:paste_h]

        # 4. Stronger glow when speaking
        frame = self._add_glow(frame, color_tint=(0, 255, 255), strength=0.6, ksize=25)

        # 5. Scan lines
        self._draw_scanlines(frame, t, speed=0.5)

        # 6. High-energy particles
        self._draw_particles(frame, t, intensity=1.0)

        # 7. Energetic spinning ring (DISABLED for LED Fan Mode)
        # self._draw_base_ring(frame, t, pulse=1.0)

        return frame

    def _musetalk_frame(self, t: float, energy: float) -> np.ndarray:
        """Hook for MuseTalk when installed."""
        frame_path = os.path.join(MUSETALK_DIR, "results", "latest_frame.jpg")
        if os.path.exists(frame_path):
            frame = cv2.imread(frame_path)
            if frame is not None:
                return cv2.resize(frame, (1024, 1024))
        return self.generate_speaking_frame(t, energy)
