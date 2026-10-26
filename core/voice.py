# core/voice.py
"""
Clean and optimized pyttsx3 voice system for MINI-XTAR
- Engine runs in dedicated worker thread
- Non-blocking speech synthesis
- Queue-based message processing
- Volume and rate control via settings
"""

import threading
import queue
import time
from pathlib import Path

try:
    import pyttsx3

    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    pyttsx3 = None
    print("⚠️ pyttsx3 not installed. Run: pip install pyttsx3")


class VoiceSystem:
    """
    Reliable pyttsx3 TTS system with thread-safe operation.
    All engine operations happen in a dedicated worker thread.
    """

    def __init__(self, rate=180, volume=1.0, voice_preference=None):
        """
        Initialize voice system.

        Args:
            rate: Speech rate (words per minute, default 180)
            volume: Volume level (0.0 to 1.0, default 1.0)
            voice_preference: Preferred voice name substring (optional)
        """
        # Message queue for text-to-speech requests
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._engine_ready_event = threading.Event()
        self._worker_thread = None

        # Configuration
        self.rate = rate
        self.volume = volume
        self.voice_preference = voice_preference

        # State tracking
        self.is_running = False
        self.is_speaking = False
        self.engine = None

        if not PYTTSX3_AVAILABLE:
            print("⚠️ TTS unavailable: pyttsx3 not installed")
            return

        # Start worker thread
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        # Wait for engine initialization (with timeout)
        if not self._engine_ready_event.wait(timeout=5):
            print("⚠️ TTS engine initialization timeout")

    def _worker_loop(self):
        """
        Main worker loop - runs in dedicated thread.
        All pyttsx3 engine operations happen here.
        """
        try:
            # Initialize engine in worker thread
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)

            # Set preferred voice if specified
            if self.voice_preference:
                voices = engine.getProperty("voices")
                pref = self.voice_preference.lower()
                for v in voices:
                    if pref in v.name.lower():
                        engine.setProperty("voice", v.id)
                        print(f"✅ Selected voice: {v.name}")
                        break

            self.engine = engine
            self.is_running = True
            self._engine_ready_event.set()
            print("✅ TTS engine ready")

        except Exception as e:
            print(f"❌ Failed to initialize TTS engine: {e}")
            self._engine_ready_event.set()
            self.is_running = False
            return

        # Main processing loop
        while not self._stop_event.is_set():
            try:
                # Wait for next message (short timeout for clean shutdown)
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Handle stop signal
            if item is None:
                try:
                    engine.stop()
                except Exception:
                    pass
                continue

            # Process text-to-speech request
            text = item
            try:
                self.is_speaking = True
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"❌ TTS playback error: {e}")
            finally:
                self.is_speaking = False

        # Cleanup
        try:
            engine.stop()
        except Exception:
            pass
        self.is_running = False
        print("🔇 TTS engine stopped")

    def text_to_speech(self, text, blocking=False):
        """
        Convert text to speech.

        Args:
            text: Text to speak
            blocking: If True, wait until speech completes

        Returns:
            True if queued successfully, False otherwise
        """
        if not PYTTSX3_AVAILABLE or not self.is_running:
            return False

        # Queue the text
        self._queue.put(text)

        # Wait for completion if blocking
        if blocking:
            while self.is_speaking or not self._queue.empty():
                time.sleep(0.05)

        return True

    def stop_audio(self):
        """Stop current speech and clear queue."""
        if not PYTTSX3_AVAILABLE or not self.is_running:
            return

        try:
            # Clear pending messages
            with self._queue.mutex:
                self._queue.queue.clear()

            # Send stop signal
            self._queue.put(None)

            # Brief wait for stop to take effect
            time.sleep(0.1)

        except Exception as e:
            print(f"⚠️ Error stopping audio: {e}")

    def update_rate(self, new_rate):
        """Update speech rate (must be done in worker thread)."""
        if self.engine and self.is_running:
            self.rate = new_rate
            try:
                self.engine.setProperty("rate", new_rate)
            except Exception as e:
                print(f"⚠️ Failed to update rate: {e}")

    def update_volume(self, new_volume):
        """Update volume level (0.0 to 1.0)."""
        if self.engine and self.is_running:
            self.volume = max(0.0, min(1.0, new_volume))
            try:
                self.engine.setProperty("volume", self.volume)
            except Exception as e:
                print(f"⚠️ Failed to update volume: {e}")

    def shutdown(self):
        """Gracefully shutdown the voice system."""
        if not PYTTSX3_AVAILABLE:
            return

        print("🔇 Shutting down TTS...")
        self._stop_event.set()
        self._queue.put(None)  # Wake up worker thread

        if self._worker_thread:
            self._worker_thread.join(timeout=2)


# Quick test
if __name__ == "__main__":
    print("=== Voice System Test ===\n")

    voice = VoiceSystem(rate=180, volume=1.0)

    if voice.is_running:
        print("Testing TTS...")
        voice.text_to_speech("Hello! I am Mini-Xtar. Voice system is working correctly.", blocking=True)
        print("✅ Test complete")
    else:
        print("❌ Voice system failed to initialize")

    voice.shutdown()