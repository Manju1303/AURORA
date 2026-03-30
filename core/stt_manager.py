"""
AURORA STT Manager — Faster-Whisper + WebRTC VAD
Anti-Hallucination, Ultra-Low Latency Speech Recognition
"""
import threading
import time
import queue
import numpy as np
import pyaudio
from faster_whisper import WhisperModel
import webrtcvad
import speech_recognition as sr
import os

# === TUNABLE CONSTANTS ===
NOISE_FLOOR       = 250    # RMS threshold — lowered to easily pick up normal speech
MIN_AUDIO_SECS    = 0.5    # Allowed to pick up very short sentences like "Hello"
SILENCE_FRAMES    = 12     # ~360ms of silence to trigger a FAST response
MAX_FRAMES        = 33 * 7 # 7-second hard cap per turn
MIN_WORD_COUNT    = 1      # Accept single-word commands
LOG_PROB_FLOOR    = -0.8   # Forgiving transcription rating
NO_SPEECH_THRESH  = 0.85   # Accept up to 85% silence in short clips


class STTManager:
    def __init__(self, model_size="base.en", compute_type="int8"):
        # Auto-detect Nvidia GPU for Maximum Performance
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except:
            device = "cpu"

        print(f"[STT] Initializing Faster-Whisper ({model_size}) on [{device.upper()}] — Anti-Hallucination Mode...")
        try:
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        except Exception as e:
            print(f"[STT] Offline Mode Detected. Optimized model '{model_size}' not cached locally.")
            print(f"[STT] Falling back to pre-downloaded 'base' model to maintain 100% offline uptime...")
            self.model = WhisperModel("base", device=device, compute_type=compute_type)

        self.p = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(3)
        self.is_listening = False
        self.is_paused = False
        self.listen_thread = None
        self.current_callback = None
        
        # Backend selection from .env
        self.backend = os.getenv("RECOGNITION_BACKEND", "google").lower()
        self.recognizer = sr.Recognizer() if self.backend == "google" else None
        
        # Processing queue for transcription to avoid blocking the mic
        self.process_queue = queue.Queue()
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()

    def start_listening(self, callback):
        self.current_callback = callback
        if self.listen_thread and self.listen_thread.is_alive():
            self.is_paused = False  # Instant resume
            return

        self.is_listening = True
        self.is_paused = False
        self.listen_thread = threading.Thread(
            target=self._listen_loop, daemon=True
        )
        self.listen_thread.start()

    def pause_listening(self):
        self.is_paused = True

    def resume_listening(self):
        self.is_paused = False

    def stop_listening(self):
        self.is_listening = False
        if self.listen_thread:
            self.listen_thread.join(timeout=2)

    def _listen_loop(self):
        rate = 16000
        chunk_size = 480  # 30ms VAD frames

        while self.is_listening:
            stream = None
            try:
                stream = self.p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=rate,
                    input=True,
                    frames_per_buffer=chunk_size
                )

                audio_buffer = []
                silent_frames = 0
                speaking = False

                print("[STT] 🎤 Listening... (LIVE Mode active)")

                while self.is_listening:
                    try:
                        data = stream.read(chunk_size, exception_on_overflow=False)
                    except Exception:
                        break

                    if self.is_paused:
                        audio_buffer = []
                        speaking = False
                        silent_frames = 0
                        continue

                    frame = np.frombuffer(data, dtype=np.int16)
                    audio_level = np.abs(frame).mean()

                    # Hard noise floor gate
                    if audio_level < NOISE_FLOOR:
                        is_speech = False
                    else:
                        try:
                            is_speech = self.vad.is_speech(data, rate)
                        except Exception:
                            is_speech = False

                    if is_speech:
                        speaking = True
                        audio_buffer.append(frame)
                        silent_frames = 0
                        if len(audio_buffer) >= MAX_FRAMES:
                            self.process_queue.put((list(audio_buffer), rate))
                            audio_buffer = []
                            speaking = False
                    else:
                        if speaking:
                            audio_buffer.append(frame)
                            silent_frames += 1
                            if silent_frames > SILENCE_FRAMES:
                                # Push to queue instead of processing synchronously
                                self.process_queue.put((list(audio_buffer), rate))
                                audio_buffer = []
                                speaking = False
                                silent_frames = 0

            except Exception as e:
                print(f"[STT Error] Stream died. Auto-recovering in 1s... ({e})")
                time.sleep(1)
            finally:
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except:
                        pass

    def _processing_loop(self):
        """Background thread that handles transcription without stopping the mic."""
        while True:
            try:
                buffer_frames, rate = self.process_queue.get()
                if buffer_frames is None: break
                
                audio_np = np.concatenate(buffer_frames)
                duration = len(audio_np) / rate
                
                if duration < MIN_AUDIO_SECS:
                    self.process_queue.task_done()
                    continue

                if self.backend == "google":
                    text = self._transcribe_google(audio_np, rate)
                else:
                    text = self._transcribe_whisper(audio_np)
                
                if text and self.current_callback:
                    self.current_callback(text)
                
                self.process_queue.task_done()
            except Exception as e:
                print(f"[STT Processing Error] {e}")

    def _transcribe_google(self, audio_np, rate):
        """Ultra-fast online recognition fallback."""
        try:
            import io
            import wave
            byte_io = io.BytesIO()
            with wave.open(byte_io, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2) # 16-bit
                wav_file.setframerate(rate)
                wav_file.writeframes(audio_np.tobytes())
            
            byte_io.seek(0)
            with sr.AudioFile(byte_io) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data)
                if text:
                    print(f"[STT] 🗣️  Transcribed (Google): {text}")
                return text
        except Exception:
            return None

    def _transcribe_whisper(self, audio_np):
        """Local high-accuracy recognition using Faster-Whisper."""
        audio_fp32 = audio_np.astype(np.float32) / 32768.0

        segments, info = self.model.transcribe(
            audio_fp32,
            beam_size=5,
            language="en",
            condition_on_previous_text=False,
            no_speech_threshold=NO_SPEECH_THRESH,
            log_prob_threshold=LOG_PROB_FLOOR,
            compression_ratio_threshold=2.0,
        )

        segments = list(segments)
        if not segments: return None

        low_confidence = all(s.avg_logprob < LOG_PROB_FLOOR for s in segments)
        if low_confidence: return None

        text = " ".join(s.text.strip() for s in segments).strip()
        if len(text.split()) < MIN_WORD_COUNT: return None

        # Non-English character rejection
        ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
        if ascii_ratio < 0.75: return None

        print(f"[STT] 🗣️  Transcribed (Whisper): {text}")
        return text
