"""
Speech Recognition using Vosk for MINI-XTAR
English-only with good accuracy
"""
import json
import queue
import sys
import threading
from pathlib import Path
from typing import Optional, Tuple

try:
    import sounddevice as sd
    import vosk
    VOSK_AVAILABLE = True
except ImportError:
    print("⚠️ Vosk not installed. Run: pip install vosk sounddevice")
    VOSK_AVAILABLE = False


class SpeechRecognition:
    """
    Vosk-based speech recognition system
    Records audio and transcribes in real-time
    """

    def __init__(self, model_path="models/vosk-model-en-us-0.42-gigaspeech"):
        """
        Initialize speech recognition

        Args:
            model_path: Path to Vosk model directory
                Download from: https://alphacephei.com/vosk/models
                Recommended: vosk-model-en-us-0.42-gigaspeech (2.3 GB, high quality)
        """
        self.model_path = Path(model_path)
        self.model = None
        self.recognizer = None

        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.sample_rate = 16000  # Vosk works best at 16kHz

        self.transcription = ""
        self.partial_transcription = ""

        if not VOSK_AVAILABLE:
            print("⚠️ Speech recognition not available")
            return

        # Load Vosk model
        self._load_model()

    def _load_model(self):
        """Load Vosk speech recognition model"""
        if not self.model_path.exists():
            print(f"⚠️ Vosk model not found at: {self.model_path}")
            print("   Download from: https://alphacephei.com/vosk/models")
            print("   Place in: models/vosk-model-en-us-0.42-gigaspeech/")
            return False

        try:
            print(f"🔄 Loading Vosk model from {self.model_path}...")
            self.model = vosk.Model(str(self.model_path))
            print("✅ Vosk model loaded successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to load Vosk model: {e}")
            return False

    def start_recording(self, callback=None):
        """
        Start recording and transcribing audio

        Args:
            callback: Optional function to call with partial transcriptions
                      callback(partial_text, is_final)
        """
        if not VOSK_AVAILABLE or not self.model:
            print("⚠️ Speech recognition not available")
            return False

        if self.is_recording:
            print("⚠️ Already recording")
            return False

        self.is_recording = True
        self.transcription = ""
        self.partial_transcription = ""
        self.audio_queue = queue.Queue()

        # Create new recognizer for this session
        self.recognizer = vosk.KaldiRecognizer(self.model, self.sample_rate)
        self.recognizer.SetWords(True)  # Get word-level timestamps

        print("🎤 Recording started...")

        # Audio callback
        def audio_callback(indata, frames, time, status):
            if status:
                print(f"Audio status: {status}")
            if self.is_recording:
                self.audio_queue.put(bytes(indata))

        # Start audio stream
        try:
            self.stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=8000,
                dtype='int16',
                channels=1,
                callback=audio_callback
            )
            self.stream.start()
        except Exception as e:
            print(f"❌ Failed to start recording: {e}")
            self.is_recording = False
            return False

        # Start transcription thread
        self.transcription_thread = threading.Thread(
            target=self._transcription_worker,
            args=(callback,),
            daemon=True
        )
        self.transcription_thread.start()

        return True

    def _transcription_worker(self, callback):
        """Worker thread that processes audio and generates transcription"""
        while self.is_recording:
            try:
                data = self.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if self.recognizer.AcceptWaveform(data):
                # Final result for this segment
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "")

                if text:
                    self.transcription += " " + text
                    if callback:
                        callback(text, is_final=True)
            else:
                # Partial result (what's being said right now)
                partial_result = json.loads(self.recognizer.PartialResult())
                partial_text = partial_result.get("partial", "")

                if partial_text != self.partial_transcription:
                    self.partial_transcription = partial_text
                    if callback:
                        callback(partial_text, is_final=False)

    def stop_recording(self):
        """Stop recording and return final transcription"""
        if not self.is_recording:
            return ""

        self.is_recording = False

        # Stop audio stream
        try:
            if hasattr(self, 'stream'):
                self.stream.stop()
                self.stream.close()
        except Exception as e:
            print(f"⚠️ Error stopping stream: {e}")

        # Wait for transcription thread to finish
        if hasattr(self, 'transcription_thread'):
            self.transcription_thread.join(timeout=1.0)

        # Get final result
        if self.recognizer:
            try:
                final_result = json.loads(self.recognizer.FinalResult())
                final_text = final_result.get("text", "")
                if final_text:
                    self.transcription += " " + final_text
            except Exception as e:
                print(f"⚠️ Error getting final result: {e}")

        final_transcription = self.transcription.strip()
        print(f"✅ Recording stopped. Transcription: '{final_transcription}'")

        return final_transcription

    def get_current_transcription(self):
        """Get current transcription (including partial)"""
        if self.partial_transcription:
            return (self.transcription + " " + self.partial_transcription).strip()
        return self.transcription.strip()


# Test script
if __name__ == "__main__":
    print("=== Vosk Speech Recognition Test ===\n")

    speech = SpeechRecognition()

    if not speech.model:
        print("\n❌ Model not loaded. Cannot test.")
        print("Download a model from: https://alphacephei.com/vosk/models")
        print("Extract to: models/vosk-model-en-us-0.42-gigaspeech/")
        sys.exit(1)


    def print_callback(text, is_final):
        """Print partial and final transcriptions"""
        if is_final:
            print(f"\n✅ Final: {text}")
        else:
            print(f"\r🔄 Partial: {text}", end="", flush=True)


    print("Speak for 5 seconds...")
    speech.start_recording(callback=print_callback)

    # Record for 5 seconds
    import time

    time.sleep(5)

    final_text = speech.stop_recording()
    print(f"\n\n📝 Complete transcription: '{final_text}'")