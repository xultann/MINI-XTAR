import os
import sys
import pygame
import ctypes
import threading
import time
import shutil
from datetime import datetime
from pathlib import Path
from interface.chat_bridge import ask_ai
from core.chatbot import ChatBot
from core.voice import VoiceSystem
from core.speech import SpeechRecognition
from core.tools.image_gen import ImageGenerator
from interface.settings_window import SettingsWindow
from PIL import Image, ImageSequence


class MiniAvatar:
    def __init__(self, sprite_folder=None, button_folder=None, chatbot=None,
                 shutdown_event=None):
        """Initialize avatar with optional shared chatbot instance"""
        self.chatbot = chatbot
        self.shutdown_event = shutdown_event

        base_dir = Path(__file__).resolve().parent
        self.sprite_folder = Path(sprite_folder) if sprite_folder else base_dir / "sprite"
        self.button_folder = Path(button_folder) if button_folder else base_dir / "buttons"

        # --- Voice System ---
        self.voice_system = VoiceSystem()
        print("✅ Voice system (pyttsx3) initialized and ready.")

        # --- Speech Recognition System ---
        self.speech_system = SpeechRecognition()
        self.detected_language = "en"  # Track detected language

        # --- Image Generation System ---
        self.image_generator = ImageGenerator()

        # --- Pygame Initialization ---
        pygame.init()
        pygame.display.set_caption("MINI-XTAR")

        # TTS is now always on - volume controlled via settings
        self.voice_enabled = True  # Always ON now

        # --- Transparent Window Setup ---
        # EDITABLE: Window size - increased to fit all buttons without going off-screen
        # Avatar is centered, buttons positioned relative to avatar center
        # Window must be large enough: avatar (350px) + buttons + padding
        self.width, self.height = 800, 1000  # EDIT THIS if buttons still go off-screen
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.NOFRAME)
        hwnd = pygame.display.get_wm_info()["window"]
        self.hwnd = hwnd
        self.user32 = ctypes.windll.user32

        # CRITICAL: Set window style for layered window
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        LWA_COLORKEY = 0x00000001
        LWA_ALPHA = 0x00000002

        # Get current style and add layered flag
        style = self.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        self.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)

        # GREY (128, 128, 128) as transparent color - shows gradients better
        self.TRANSPARENT_COLOR = (128, 128, 128)
        self.user32.SetLayeredWindowAttributes(
            hwnd,
            self._rgb_to_colorref(self.TRANSPARENT_COLOR),
            255,
            LWA_COLORKEY
        )

        # --- Settings Window ---
        # Initialize settings window (after window setup, before everything else)
        # SettingsWindow only takes voice_system as parameter (based on error message)
        self.settings_window = SettingsWindow(self)

        self.clock = pygame.time.Clock()

        # --- Smooth Dragging (FIXED) ---
        self.dragging = False
        self.drag_start_window_x = 0
        self.drag_start_window_y = 0
        self.drag_start_mouse_x = 0
        self.drag_start_mouse_y = 0

        self.selected_image_path = None
        self.last_generated_image = None

        # --- Animated GIFs ---
        self.sprites = self._load_gif_sprites(str(self.sprite_folder))
        self.state = "idle"
        self.frame_index = 0
        self.frame_timer = 0
        self.frame_delay = 200  # ms between frames

        # --- UI / Fonts ---
        self.font = pygame.font.SysFont("Segoe UI", 16)
        self.text = ""
        self.show_text = False

        # --- Chat / Buttons (FIXED SIZES) ---
        self.chat_box_open = False
        self.chat_mode = "normal"  # "normal" or "web" - determines chat behavior
        self.chat_input = ""
        self.cursor_position = 0  # NEW: Cursor position for text editing
        self.cursor_visible = True  # NEW: Cursor blink state
        self.cursor_timer = 0  # NEW: Timer for cursor blinking
        self.backspace_held = False  # NEW: Track if backspace is held
        self.backspace_timer = 0  # NEW: Timer for backspace repeat
        self.backspace_initial_delay = 500  # ms before repeat starts
        self.backspace_repeat_delay = 10  # ms between repeats

        self.voice_enabled = True  # Start with voice ON
        self.muted = True  # Start with mic OFF

        # --- Button State Variables ---
        # EDITABLE: Toggle states for new buttons (can be implemented later)
        self.web_enabled = False
        self.image_enabled = False
        self.display_enabled = False
        self.game_enabled = False
        self.settings_enabled = False

        # Load button images
        self.buttons = self._load_buttons(str(self.button_folder))

        # --- BUTTON LAYOUT CONFIGURATION ---
        # EDITABLE: All button positioning is relative to avatar center
        # Avatar is centered at (width//2, height//2)
        # This ensures buttons stay on screen even if window size changes

        # Avatar center coordinates (used as reference point)
        avatar_center_x = self.width // 2  # EDIT THIS if avatar position changes
        avatar_center_y = self.height // 2  # EDIT THIS if avatar position changes

        # Main button size (for X, chat, web, image, display, game)
        # EDITABLE: Change button_size to resize all main buttons
        button_size = 67

        # Smaller button size (for settings, mic - positioned next to chat)
        # EDITABLE: Change small_button_size to resize settings/mic buttons
        small_button_size = 45  # Smaller than main buttons

        # Button spacing between main buttons (vertical spacing)
        # EDITABLE: Change button_spacing to adjust vertical gap between buttons
        button_spacing = 70

        # Horizontal offset from avatar center to button column
        # EDITABLE: Change button_offset_x to move buttons left/right
        button_offset_x = 130  # Buttons appear to the right of avatar center

        # Starting Y position for main button column (relative to avatar center)
        # EDITABLE: Change start_y_offset to move entire button column up/down
        start_y_offset = -235  # Negative = above avatar center

        # Calculate button X position (right side of window)
        button_x = avatar_center_x + button_offset_x

        # Calculate starting Y position
        start_y = avatar_center_y + start_y_offset

        # --- MAIN BUTTON RECTANGLES (Top to Bottom) ---
        # Order: X button, chat, web, image, display, game
        # EDITABLE: Adjust positions by changing start_y_offset or button_spacing above

        # X button (main size, at top)
        self.exit_button_rect = pygame.Rect(button_x, start_y, button_size, button_size)

        # Chat button (main size, below X)
        self.chat_button_rect = pygame.Rect(button_x, start_y + button_spacing, button_size, button_size)

        # Web button (main size, below chat)
        self.web_button_rect = pygame.Rect(button_x, start_y + button_spacing * 2, button_size, button_size)

        # Image button (main size, below web)
        self.image_button_rect = pygame.Rect(button_x, start_y + button_spacing * 3, button_size, button_size)

        # Display button (main size, below image)
        self.display_button_rect = pygame.Rect(button_x, start_y + button_spacing * 4, button_size, button_size)

        # Game button (main size, below display)
        self.game_button_rect = pygame.Rect(button_x, start_y + button_spacing * 5, button_size, button_size)

        # --- SMALLER BUTTONS (Next to chat button, to the right) ---
        # Settings and mic buttons positioned to the right of chat button
        # EDITABLE: Change small_button_spacing to adjust gap between settings and mic
        small_button_spacing = 35
        small_button_x = button_x + button_size + 10  # To the right of main buttons

        # Settings button (smaller, next to chat)
        self.settings_button_rect = pygame.Rect(small_button_x, (start_y-14) + button_spacing, small_button_size, small_button_size)

        # Mic button (smaller, below settings)
        self.mic_button_rect = pygame.Rect(small_button_x, start_y + button_spacing + small_button_spacing, small_button_size, small_button_size)

        # Chat input - FIXED: Positioned relative to avatar X-axis, lower Y
        avatar_center_x = self.width // 2
        chat_box_width = 250
        chat_box_height = 32
        send_button_width = 80

        # Center chat box horizontally with avatar, near bottom
        chat_box_x = avatar_center_x - (chat_box_width + send_button_width + 10) // 2
        chat_box_y = self.height - 300  # 300px from bottom

        self.chat_field_rect = pygame.Rect(chat_box_x, chat_box_y, chat_box_width, chat_box_height)
        self.send_button_rect = pygame.Rect(chat_box_x + chat_box_width + 10, chat_box_y, send_button_width,
                                            chat_box_height)
        self.photo_button_rect = pygame.Rect(self.send_button_rect.right + 10, chat_box_y, send_button_width,
                                             chat_box_height)

        # Misc UI config
        self.chat_box_height = -30
        self.max_input_length = 200
        self.wrap_width = 30
        self.max_bubble_width = 350

        # Bubble close button
        self.bubble_close_button_size = 20
        self.bubble_close_button_rect = None

    # ---------------------------------------------------
    # Helper for Windows Transparency
    # ---------------------------------------------------
    def _rgb_to_colorref(self, rgb):
        """Convert RGB tuple to Windows COLORREF (BGR format)"""
        return rgb[0] | (rgb[1] << 8) | (rgb[2] << 16)

    # ---------------------------------------------------
    # Asset Loading (FIXED: Keep gradients, only remove magenta)
    # ---------------------------------------------------
    def _load_gif_sprites(self, folder):
        """Load animated GIFs - only replace pure magenta, keep gradients"""
        states = ["idle", "listening", "thinking", "talking", "dragged", "drawing", "jamming"]
        sprites = {}
        for state in states:
            path = os.path.join(folder, f"mini_{state}.gif")
            if not os.path.exists(path):
                print(f"⚠️ Missing sprite for {state}: {path}")
                continue
            try:
                img = Image.open(path)
                frames = []
                for frame in ImageSequence.Iterator(img):
                    frame = frame.convert("RGBA")
                    size_ratio = frame.width / frame.height
                    target_height = 350
                    target_width = int(target_height * size_ratio)
                    frame = frame.resize((target_width, target_height), Image.Resampling.LANCZOS)

                    # FIXED: Only replace PURE magenta (255, 0, 255) with grey
                    pixels = frame.load()
                    for y in range(frame.height):
                        for x in range(frame.width):
                            r, g, b, a = pixels[x, y]
                            # Only detect PURE magenta/pink (exact or very close)
                            if r >= 250 and g <= 10 and b >= 250:  # Pure magenta only
                                pixels[x, y] = (128, 128, 128, 255)  # Grey (transparent)

                    # Convert PIL image to pygame surface
                    surf = pygame.image.fromstring(frame.tobytes(), frame.size, "RGBA")
                    frames.append(surf)
                sprites[state] = frames
            except Exception as e:
                print(f"⚠️ Failed to load {path}: {e}")
        return sprites

    def _load_buttons(self, folder):
        """Load button PNGs - only remove pure magenta"""

        def load_img(name):
            path = os.path.join(folder, f"{name}.png")
            if not os.path.exists(path):
                print(f"⚠️ Missing button: {path}")
                return None

            # Load with PIL first
            pil_img = Image.open(path).convert("RGBA")
            pixels = pil_img.load()

            # Replace ONLY pure magenta with grey
            for y in range(pil_img.height):
                for x in range(pil_img.width):
                    r, g, b, a = pixels[x, y]
                    # Pure magenta only
                    if r >= 250 and g <= 10 and b >= 250:
                        pixels[x, y] = (128, 128, 128, 255)

            # Convert to pygame surface
            img_str = pil_img.tobytes()
            surf = pygame.image.fromstring(img_str, pil_img.size, "RGBA")
            return surf

        # EDITABLE: Load all new button images
        # If button files are missing, they will return None and be skipped
        return {
            "chat_on": load_img("chat_on"),
            "chat_off": load_img("chat_off"),
            "web_on": load_img("web_on"),
            "web_off": load_img("web_off"),
            "image_on": load_img("image_on"),
            "image_off": load_img("image_off"),
            "display_on": load_img("display_on"),
            "display_off": load_img("display_off"),
            "game_on": load_img("game_on"),
            "game_off": load_img("game_off"),
            "settings_on": load_img("settings_on"),
            "settings_off": load_img("settings_off"),
            "mic_on": load_img("mic_on"),
            "mic_off": load_img("mic_off"),
            "x_button": load_img("X_button"),
        }

    def _move_window(self, x, y):
        """Move window smoothly without shaking"""
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        flags = SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
        self.user32.SetWindowPos(self.hwnd, None, int(x), int(y), 0, 0, flags)

    # ---------------------------------------------------
    # States / Voice
    # ---------------------------------------------------
    def set_state(self, new_state):
        if new_state in self.sprites:
            self.state = new_state
            self.frame_index = 0
            self.frame_timer = 0

    def speak(self, text):
        self.text = text
        self.show_text = True

    def hide_text(self):
        self.show_text = False

    def handle_voice_button_click(self):
        """Toggle AI voice output"""
        self.voice_enabled = not self.voice_enabled
        state = "ON" if self.voice_enabled else "OFF"
        msg = f"Voice mode {state}."
        self.speak(msg)
        if self.voice_enabled:
            self.speak_with_voice(msg)

    def handle_mute_button_click(self):
        """Toggle microphone (speech input)"""
        self.muted = not self.muted

        if not self.muted:
            # Mic turned ON - start listening
            self.set_state("listening")
            self.speak("Listening...")

            def start_speech():
                try:
                    # Start recording
                    success = self.speech_system.start_recording()
                    if not success:
                        self.speak("Speech recognition failed to start.")
                        self.muted = True
                        self.set_state("idle")
                except Exception as e:
                    print(f"❌ Speech recognition error: {e}")
                    self.speak("Speech recognition error.")
                    self.muted = True
                    self.set_state("idle")

            threading.Thread(target=start_speech, daemon=True).start()
        else:
            # Mic turned OFF - stop listening and process
            self.set_state("thinking")

            def stop_and_process():
                try:
                    # Stop recording and get transcription
                    transcription = self.speech_system.stop_recording()

                    if transcription:
                        self.speak(f"You said: {transcription}")
                        # Send to AI
                        time.sleep(1.0)  # Brief pause to show "You said..."
                        self.send_to_ai(transcription)
                    else:
                        self.speak("I didn't hear anything.")
                        self.set_state("idle")
                except Exception as e:
                    print(f"❌ Speech processing error: {e}")
                    self.speak("Speech processing error.")
                    self.set_state("idle")

            threading.Thread(target=stop_and_process, daemon=True).start()

    def speak_with_voice(self, text):
        """Make AI speak using pyttsx3 - ALWAYS ON"""
        if not self.voice_system or not self.voice_system.is_running:
            return

        if self.voice_system.is_speaking:
            return

        def worker():
            try:
                self.set_state("talking")
                success = self.voice_system.text_to_speech(text, blocking=False)

                if not success:
                    return

                time.sleep(0.2)
                timeout = 3.0
                elapsed = 0
                check_interval = 0.05

                while not self.voice_system.is_speaking and elapsed < timeout:
                    time.sleep(check_interval)
                    elapsed += check_interval

                if not self.voice_system.is_speaking:
                    time.sleep(0.5)
                    if not self.voice_system.is_speaking:
                        return

                elapsed = 0
                max_wait = 30.0
                while self.voice_system.is_speaking and elapsed < max_wait:
                    time.sleep(check_interval)
                    elapsed += check_interval

            except Exception as e:
                print(f"❌ TTS error: {e}")
            finally:
                if self.state == "talking":
                    self.set_state("idle")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    # ---------------------------------------------------
    # Drawing
    # ---------------------------------------------------
    def draw_buttons(self):
        """Draw all image buttons with proper sizing"""
        # EDITABLE: Button drawing - all buttons are scaled to their rect sizes
        # Main buttons use button_size, smaller buttons use small_button_size

        # X button (main size, always visible)
        img = self.buttons.get("x_button")
        if img:
            scaled = pygame.transform.scale(img, (self.exit_button_rect.width, self.exit_button_rect.height))
            self.screen.blit(scaled, self.exit_button_rect)

        # Chat button (main size, only ON when in normal chat mode)
        # FIXED: Show OFF when in web or image mode
        is_chat_on = self.chat_box_open and self.chat_mode == "normal"
        img = self.buttons.get("chat_on" if is_chat_on else "chat_off")
        if img:
            scaled = pygame.transform.scale(img, (self.chat_button_rect.width, self.chat_button_rect.height))
            self.screen.blit(scaled, self.chat_button_rect)

        # Web button (main size, only ON when in web mode)
        is_web_on = self.chat_box_open and self.chat_mode == "web"
        img = self.buttons.get("web_on" if is_web_on else "web_off")
        if img:
            scaled = pygame.transform.scale(img, (self.web_button_rect.width, self.web_button_rect.height))
            self.screen.blit(scaled, self.web_button_rect)

        # Image button (main size, only ON when in image mode)
        is_image_on = self.chat_box_open and self.chat_mode == "image"
        img = self.buttons.get("image_on" if is_image_on else "image_off")
        if img:
            scaled = pygame.transform.scale(img, (self.image_button_rect.width, self.image_button_rect.height))
            self.screen.blit(scaled, self.image_button_rect)

        # Display button (main size, toggles on/off)
        img = self.buttons.get("display_on" if self.display_enabled else "display_off")
        if img:
            scaled = pygame.transform.scale(img, (self.display_button_rect.width, self.display_button_rect.height))
            self.screen.blit(scaled, self.display_button_rect)

        # Game button (main size, toggles on/off)
        img = self.buttons.get("game_on" if self.game_enabled else "game_off")
        if img:
            scaled = pygame.transform.scale(img, (self.game_button_rect.width, self.game_button_rect.height))
            self.screen.blit(scaled, self.game_button_rect)

        # Settings button (smaller, next to chat, toggles on/off)
        img = self.buttons.get("settings_on" if self.settings_enabled else "settings_off")
        if img:
            scaled = pygame.transform.scale(img, (self.settings_button_rect.width, self.settings_button_rect.height))
            self.screen.blit(scaled, self.settings_button_rect)

        # Mic button (smaller, below settings, toggles on/off based on muted state)
        img = self.buttons.get("mic_on" if not self.muted else "mic_off")
        if img:
            scaled = pygame.transform.scale(img, (self.mic_button_rect.width, self.mic_button_rect.height))
            self.screen.blit(scaled, self.mic_button_rect)

    def draw_bubble(self, text):
        """Draw speech bubble on LEFT SIDE of avatar"""
        if not text:
            return

        # Word wrap
        wrapped = []
        words = text.split()
        line = ""
        max_width = self.max_bubble_width - 60

        for word in words:
            test = line + (" " if line else "") + word
            if self.font.size(test)[0] <= max_width:
                line = test
            else:
                if line:
                    wrapped.append(line)
                line = word
        if line:
            wrapped.append(line)

        # Calculate bubble size
        padding = 15
        line_height = 22
        text_widths = [self.font.size(l)[0] for l in wrapped] if wrapped else [200]
        bubble_width = min(self.max_bubble_width, max(200, max(text_widths) + 60))
        bubble_height = len(wrapped) * line_height + padding * 2 + 30

        # FIXED: Position on LEFT side, vertically centered with avatar
        x = 44  # Left margin
        y = (self.height - bubble_height) // 2  # Vertically centered
        rect = pygame.Rect(x, y, bubble_width, bubble_height)

        # Draw bubble
        pygame.draw.rect(self.screen, (40, 40, 50), rect, border_radius=12)
        pygame.draw.rect(self.screen, (150, 100, 200), rect, 2, border_radius=12)

        # Draw text
        ty = y + padding + 5
        for l in wrapped:
            txt = self.font.render(l, True, (255, 255, 255))
            self.screen.blit(txt, (x + 20, ty))
            ty += line_height

        # Draw close button
        close_x = x + bubble_width - self.bubble_close_button_size - 8
        close_y = y + 8
        self.bubble_close_button_rect = pygame.Rect(close_x, close_y,
                                                    self.bubble_close_button_size,
                                                    self.bubble_close_button_size)

        pygame.draw.rect(self.screen, (200, 60, 60), self.bubble_close_button_rect, border_radius=4)
        pygame.draw.rect(self.screen, (255, 255, 255), self.bubble_close_button_rect, width=1, border_radius=4)

        x_font = pygame.font.SysFont("Arial", 14, bold=True)
        x_text = x_font.render("×", True, (255, 255, 255))
        x_rect = x_text.get_rect(center=self.bubble_close_button_rect.center)
        self.screen.blit(x_text, x_rect)

    # ---------------------------------------------------
    # AI + Events
    # ---------------------------------------------------
    def _handle_send_message(self):
        msg = self.chat_input.strip()
        if self.chat_mode == "image":
            if not msg and not self.selected_image_path:
                self.speak("Add a prompt or drop a photo first.")
                return
            self.send_to_ai_image(msg)
        elif self.chat_mode == "web":
            if msg:
                self.send_to_ai_web(msg)
            else:
                self.speak("Type something for me to search.")
                return
        else:
            if msg:
                self.send_to_ai(msg)
            else:
                return

        self.chat_input = ""
        self.cursor_position = 0

    def open_image_picker(self):
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as e:
            print(f"⚠️ Photo picker unavailable: {e}")
            self.speak("Photo picker unavailable.")
            return

        def picker():
            root = tk.Tk()
            root.withdraw()
            file_path = filedialog.askopenfilename(
                title="Select image",
                filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("All files", "*.*")]
            )
            root.destroy()
            if file_path:
                self.selected_image_path = file_path
                self.speak("Photo attached for the next render.")

        threading.Thread(target=picker, daemon=True).start()

    def send_to_ai(self, message):
        """Send message to AI - Route based on chat mode"""
        # Route to appropriate handler based on chat mode
        if self.chat_mode == "web":
            self.send_to_ai_web(message)
        elif self.chat_mode == "image":
            # Image mode is handled separately via send_to_ai_image()
            # This shouldn't be called directly in image mode
            pass
        else:
            self.send_to_ai_normal(message)

    # def send_to_ai_with_language(self, message, language="en"):
    #     """
    #     Send message to AI with language context
    #     AI will respond in the same language as detected
    #     """
    #
    #     def worker():
    #         self.set_state("thinking")
    #         try:
    #             # Add language instruction to the message
    #             if language == "ar":
    #                 # User spoke Arabic - instruct AI to respond in Arabic
    #                 language_instruction = (
    #                     "The user spoke to you in Arabic. "
    #                     "Please respond in Arabic (العربية). "
    #                     f"User's message: {message}"
    #                 )
    #             else:
    #                 # User spoke English - respond in English
    #                 language_instruction = message
    #
    #             # Send to AI without tools (normal conversation)
    #             reply = ask_ai(language_instruction, source="avatar", use_tools=False)
    #
    #         except RuntimeError:
    #             reply = self.chatbot.ask(message) if self.chatbot else "Error: Chatbot not available"
    #
    #         self.speak(reply)
    #
    #         # Always speak the response
    #         def speak_after_delay():
    #             self.speak_with_voice(reply)
    #
    #         threading.Timer(0.3, speak_after_delay).start()
    #
    #     threading.Thread(target=worker, daemon=True).start()

    def send_to_ai_normal(self, message):
        """Send message to AI in normal chat mode - NO WEB SEARCH"""

        def worker():
            self.set_state("thinking")
            try:
                # FIXED: Explicitly disable tools for normal chat mode
                # This prevents keyword-based web search triggers
                reply = ask_ai(message, source="avatar", use_tools=False)
            except RuntimeError:
                reply = self.chatbot.ask(message) if self.chatbot else "Error: Chatbot not available"

            self.speak(reply)

            # FIXED: ALWAYS speak - removed the "if not self.muted:" check
            def speak_after_delay():
                self.speak_with_voice(reply)

            threading.Timer(0.3, speak_after_delay).start()

        threading.Thread(target=worker, daemon=True).start()

    def send_to_ai_web(self, message):
        """Send message to AI in web search mode - ALWAYS search the web and summarize"""

        def worker():
            self.set_state("thinking")

            try:
                # FIXED: Force web search by directly calling the web search tool
                from core.tools.web_search import web_search

                # Clean the message - remove "search for" prefix if present
                query = message.strip()
                if query.lower().startswith("search for "):
                    query = query[11:]  # Remove "search for " prefix

                print(f"🔍 Web search query: {query}")

                # Perform the search with the ORIGINAL user query
                search_result = web_search(query=query, max_results=5)

                if search_result["success"] and search_result["results"]:
                    # Format search results for AI to summarize
                    search_context = f"I searched the web for: '{query}'\n\n"
                    search_context += "Here's what I found:\n\n"

                    for i, result in enumerate(search_result["results"], 1):
                        search_context += f"{i}. {result['title']}\n"
                        search_context += f"   {result['snippet']}\n"
                        search_context += f"   Source: {result['url']}\n\n"

                    # CRITICAL FIX: Send to AI with EXPLICIT instruction to NOT trigger more searches
                    summary_prompt = (
                        f"{search_context}\n\n"
                        f"Based on the search results above, please provide a helpful answer to: {query}\n\n"
                        f"Important: Just answer based on these results. Do not search again."
                    )

                    # IMPORTANT: use_tools=False prevents recursive searches
                    reply = ask_ai(summary_prompt, source="avatar", use_tools=False)
                else:
                    reply = f"Sorry, I couldn't find any results for '{query}'. Error: {search_result.get('error', 'Unknown error')}"

            except Exception as e:
                print(f"❌ Web search error: {e}")
                import traceback
                traceback.print_exc()
                reply = f"Web search failed: {str(e)}"

            self.speak(reply)

            # FIXED: ALWAYS speak - removed the "if not self.muted:" check
            def speak_after_delay():
                self.speak_with_voice(reply)

            threading.Timer(0.3, speak_after_delay).start()

        threading.Thread(target=worker, daemon=True).start()

    def send_to_ai_image(self, prompt):
        """Generate image from prompt - handles both text-to-image and img2img"""

        def worker():
            self.set_state("drawing")

            # Validate and process prompt
            final_prompt = prompt
            if not final_prompt or not final_prompt.strip():
                if not self.selected_image_path:
                    self.speak("Please provide a prompt for image generation.")
                    self.set_state("idle")
                    return
                else:
                    # If only image provided, use a default prompt
                    final_prompt = "enhance this image with artistic style"

            self.speak("Generating your image...")

            try:
                # Check if we're doing img2img or text2img
                if self.selected_image_path:
                    # Image-to-image generation
                    print(f"[AVATAR] Generating image from: {self.selected_image_path}")
                    output_path = self.image_generator.generate_from_image(
                        prompt=final_prompt.strip(),
                        image_path=self.selected_image_path,
                        strength=0.90,  # How much to change the image (0.0-1.0)
                        num_inference_steps=30,
                        guidance_scale=10
                    )
                else:
                    # Text-to-image generation
                    print(f"[AVATAR] Generating image from prompt: {final_prompt}")
                    output_path = self.image_generator.generate(
                        prompt=final_prompt.strip(),
                        width=600,  # SD 1.5 optimal size
                        height=600,  # SD 1.5 optimal size
                        num_inference_steps=30,
                        guidance_scale=10
                    )

                # Store the generated image path
                self.last_generated_image = output_path

                # Save to desktop
                desktop_path = self.save_image_to_desktop(output_path)

                # Show preview
                self.show_generated_image(output_path)

                # Success message
                self.speak(f"Image ready! Saved to {desktop_path.name}.")

                # FIXED: ALWAYS speak - removed the "if not self.muted:" check
                def speak_after_delay():
                    self.speak_with_voice(f"Image ready! Saved to desktop.")

                threading.Timer(0.3, speak_after_delay).start()

            except Exception as e:
                print(f"❌ Image generation error: {e}")
                import traceback
                traceback.print_exc()
                self.speak(f"Image generation failed: {str(e)}")

                # FIXED: ALWAYS speak error - removed the "if not self.muted:" check
                def speak_error():
                    self.speak_with_voice("Image generation failed. Check the console for details.")

                threading.Timer(0.3, speak_error).start()

            finally:
                # Clean up: reset selected image and return to idle
                self.selected_image_path = None
                if self.state == "drawing":
                    self.set_state("idle")

        threading.Thread(target=worker, daemon=True).start()

    def show_generated_image(self, image_path):
        """Show generated image in a preview window"""
        try:
            import tkinter as tk
            from PIL import Image, ImageTk
        except Exception as e:
            print(f"⚠️ Unable to preview image: {e}")
            return

        def viewer():
            try:
                root = tk.Tk()
                root.title("MINI-XTAR Image Preview")

                # Load and resize image
                img = Image.open(image_path)
                img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)

                # Create label with image
                label = tk.Label(root, image=photo)
                label.image = photo  # Keep reference
                label.pack(padx=10, pady=10)

                # Add close button
                close_btn = tk.Button(root, text="Close", command=root.destroy,
                                      font=("Arial", 12), padx=20, pady=5)
                close_btn.pack(pady=10)

                root.mainloop()
            except Exception as e:
                print(f"❌ Image viewer error: {e}")

        threading.Thread(target=viewer, daemon=True).start()

    def save_image_to_desktop(self, image_path):
        """Save generated image to desktop with timestamp"""
        try:
            desktop = Path.home() / "\OneDrive\Desktop"
            desktop.mkdir(parents=True, exist_ok=True)

            # Create filename with timestamp
            filename = f"MINI_XTAR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            dest = desktop / filename

            # Copy or convert image to desktop
            try:
                img = Image.open(image_path)
                img.save(dest, format="PNG")
                print(f"[AVATAR] Image saved to: {dest}")
            except Exception as e:
                # Fallback: direct file copy
                print(f"[AVATAR] Using fallback copy method: {e}")
                shutil.copyfile(image_path, dest)

            return dest

        except Exception as e:
            print(f"❌ Failed to save image to desktop: {e}")
            # Return original path if desktop save fails
            return Path(image_path)

    def handle_buttons(self, pos):
        """Handle button clicks for all buttons"""

        # X button - FIXED: Shutdown entire application
        if self.exit_button_rect.collidepoint(pos):
            if self.shutdown_event:
                self.shutdown_event.set()  # Signal main to shutdown
            return False  # Close avatar window

        # Speech bubble close button
        if self.show_text and self.bubble_close_button_rect and self.bubble_close_button_rect.collidepoint(pos):
            self.hide_text()
            return True

        # Main buttons
        if self.chat_button_rect.collidepoint(pos):
            # Chat button: Open normal chat mode
            if self.chat_box_open and self.chat_mode == "normal":
                # If already in normal chat, close it
                self.chat_box_open = False
            else:
                # Open normal chat, close web chat if open
                self.chat_box_open = True
                self.chat_mode = "normal"
                self.web_enabled = False
                self.image_enabled = False  # ADDED: Turn off image mode
                self.speak("Chat mode enabled.")

        elif self.web_button_rect.collidepoint(pos):
            # Web button: Turn off chat button and open web-focused chatbox
            if self.chat_box_open and self.chat_mode == "web":
                # If already in web chat, close it
                self.chat_box_open = False
                self.web_enabled = False
            else:
                # Open web chat, close normal chat
                self.chat_box_open = True
                self.chat_mode = "web"
                self.web_enabled = True
                self.image_enabled = False  # ADDED: Turn off image mode
                self.speak("Web search mode enabled.")

        elif self.image_button_rect.collidepoint(pos):
            # FIXED: Toggle image mode properly
            if self.chat_box_open and self.chat_mode == "image":
                # Close image mode
                self.chat_box_open = False
                self.image_enabled = False
                self.selected_image_path = None
            else:
                # Open image mode
                self.chat_box_open = True
                self.chat_mode = "image"
                self.image_enabled = True
                self.web_enabled = False
                self.speak("Image generation mode enabled.")

        elif self.display_button_rect.collidepoint(pos):
            self.display_enabled = not self.display_enabled
            self.speak(f"Display mode {'ON' if self.display_enabled else 'OFF'}")

        elif self.game_button_rect.collidepoint(pos):
            self.game_enabled = not self.game_enabled
            self.speak(f"Game mode {'ON' if self.game_enabled else 'OFF'}")

        # Settings button - Opens settings window
        elif self.settings_button_rect.collidepoint(pos):
            self.settings_window.open()
            self.settings_enabled = True

        # Mic button - Toggle speech recognition
        elif self.mic_button_rect.collidepoint(pos):
            self.handle_mute_button_click()

        return True

    # ---------------------------------------------------
    # Update & Draw Loop
    # ---------------------------------------------------
    def update(self):
        """Main update and draw loop"""
        # Fill with transparent color (grey)
        self.screen.fill(self.TRANSPARENT_COLOR)

        # Animate sprite
        sprite_frames = self.sprites.get(self.state)
        if sprite_frames:
            self.frame_timer += self.clock.get_time()
            if self.frame_timer >= self.frame_delay:
                self.frame_index = (self.frame_index + 1) % len(sprite_frames)
                self.frame_timer = 0
            # FIXED: Get the current frame first
            frame = sprite_frames[self.frame_index]
            # EDITABLE: Avatar sprite positioning - centered in window
            # Avatar center is at (width//2, height//2)
            frame_rect = frame.get_rect(center=(self.width // 2, self.height // 2))
            self.screen.blit(frame, frame_rect)

        # Buttons (X button is now drawn as image, not a drawn rectangle)
        # All buttons are drawn using their image files
        self.draw_buttons()

        # Speech bubble (left side)
        if self.show_text:
            self.draw_bubble(self.text)

        # Chat UI
        if self.chat_box_open:
            # Show mode indicator above chat box
            if self.chat_mode == "web":
                mode_text = "Web Search Mode"
                mode_color = (100, 200, 255)
            elif self.chat_mode == "image":
                mode_text = "Image Mode"
                mode_color = (200, 150, 255)
            else:
                mode_text = "Chat Mode"
                mode_color = (150, 150, 200)
            mode_surface = self.font.render(mode_text, True, mode_color)
            mode_x = self.chat_field_rect.x
            mode_y = self.chat_field_rect.y - 25
            self.screen.blit(mode_surface, (mode_x, mode_y))

            # Chat input field
            # Different border color for web mode
            if self.chat_mode == "web":
                border_color = (100, 200, 255)
            elif self.chat_mode == "image":
                border_color = (200, 150, 255)
            else:
                border_color = (150, 150, 200)
            pygame.draw.rect(self.screen, (40, 40, 60), self.chat_field_rect, border_radius=8)
            pygame.draw.rect(self.screen, border_color, self.chat_field_rect, width=2, border_radius=8)

            # FIXED: Render text with proper clipping and cursor
            # Get visible portion of text that fits in the box
            max_visible_width = self.chat_field_rect.width - 10

            # Calculate what part of text to show (scroll if needed)
            full_text = self.chat_input
            cursor_pos = self.cursor_position

            # Measure text before cursor
            text_before_cursor = full_text[:cursor_pos]
            cursor_pixel_pos = self.font.size(text_before_cursor)[0]

            # If cursor is off-screen to the right, scroll left
            scroll_offset = 0
            if cursor_pixel_pos > max_visible_width:
                scroll_offset = cursor_pixel_pos - max_visible_width + 20

            # Render text
            txt_surface = self.font.render(full_text, True, (255, 255, 255))

            # Clip to text box
            clip_rect = pygame.Rect(self.chat_field_rect.x + 5, self.chat_field_rect.y + 5,
                                    max_visible_width, self.chat_field_rect.height - 10)
            self.screen.set_clip(clip_rect)
            self.screen.blit(txt_surface, (self.chat_field_rect.x + 5 - scroll_offset,
                                           self.chat_field_rect.y + 5))
            self.screen.set_clip(None)

            # Draw blinking cursor
            self.cursor_timer += self.clock.get_time()
            if self.cursor_timer >= 500:  # Blink every 500ms
                self.cursor_visible = not self.cursor_visible
                self.cursor_timer = 0

            if self.cursor_visible:
                cursor_x = self.chat_field_rect.x + 5 + cursor_pixel_pos - scroll_offset
                cursor_y = self.chat_field_rect.y + 5
                pygame.draw.line(self.screen, (255, 255, 255),
                                 (cursor_x, cursor_y),
                                 (cursor_x, cursor_y + 18), 2)

            # Send button
            pygame.draw.rect(self.screen, (100, 180, 255), self.send_button_rect, border_radius=8)
            pygame.draw.rect(self.screen, (255, 255, 255), self.send_button_rect, width=2, border_radius=8)
            send_txt = self.font.render("Send", True, (10, 10, 10))
            send_rect = send_txt.get_rect(center=self.send_button_rect.center)
            self.screen.blit(send_txt, send_rect)

            if self.chat_mode == "image":
                pygame.draw.rect(self.screen, (120, 150, 255), self.photo_button_rect, border_radius=8)
                pygame.draw.rect(self.screen, (255, 255, 255), self.photo_button_rect, width=2, border_radius=8)
                drop_label = "Photo ✓" if self.selected_image_path else "Drop Photo"
                drop_txt = self.font.render(drop_label, True, (10, 10, 10))
                drop_rect = drop_txt.get_rect(center=self.photo_button_rect.center)
                self.screen.blit(drop_txt, drop_rect)

        # Draw settings window (if open) - MUST be drawn last (on top)
        if self.settings_window.active:
            self.settings_window.draw(self.screen)

        pygame.display.flip()
        self.clock.tick(60)  # Increased to 60 FPS for smoother cursor

    # ---------------------------------------------------
    # Main Loop (FIXED: Perfect dragging)
    # ---------------------------------------------------
    def run(self):
        running = True
        while running and (not self.shutdown_event or not self.shutdown_event.is_set()):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        pos = pygame.mouse.get_pos()

                        # Handle buttons first
                        if not self.handle_buttons(pos):
                            running = False
                            break

                        # EDITABLE: Dragging area - avatar is centered, so adjust drag area accordingly
                        # Drag area should be on the avatar (left side of window, avoiding buttons)
                        # Avatar center is at width//2, so drag area is roughly left half
                        avatar_center_x = self.width // 2
                        if pos[0] < avatar_center_x and pos[1] > 50:
                            if not (self.show_text and self.bubble_close_button_rect
                                    and self.bubble_close_button_rect.collidepoint(pos)):
                                self.dragging = True

                                # Get current window position on screen
                                rect = ctypes.wintypes.RECT()
                                self.user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
                                self.drag_start_window_x = rect.left
                                self.drag_start_window_y = rect.top

                                # Get mouse position on screen
                                cursor_pos = ctypes.wintypes.POINT()
                                ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor_pos))
                                self.drag_start_mouse_x = cursor_pos.x
                                self.drag_start_mouse_y = cursor_pos.y

                                self.set_state("dragged")

                        # Chat buttons
                        if self.chat_box_open:
                            if self.send_button_rect.collidepoint(pos):
                                self._handle_send_message()
                            elif self.chat_mode == "image" and self.photo_button_rect.collidepoint(pos):
                                self.open_image_picker()
                # Handle settings window events (if open)
                if self.settings_window.active:
                    if self.settings_window.handle_event(event):
                        continue  # Event was handled by settings window

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.dragging = False
                        if self.state == "dragged":
                            self.set_state("idle")

                elif event.type == pygame.MOUSEMOTION:
                    if self.dragging:
                        # FIXED: Calculate new position based on screen coordinates
                        cursor_pos = ctypes.wintypes.POINT()
                        ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor_pos))

                        delta_x = cursor_pos.x - self.drag_start_mouse_x
                        delta_y = cursor_pos.y - self.drag_start_mouse_y

                        new_x = self.drag_start_window_x + delta_x
                        new_y = self.drag_start_window_y + delta_y

                        self._move_window(new_x, new_y)

                elif event.type == pygame.KEYDOWN and self.chat_box_open:
                    if event.key == pygame.K_RETURN:
                        self._handle_send_message()

                    elif event.key == pygame.K_BACKSPACE:
                        self.backspace_held = True
                        self.backspace_timer = 0
                        if self.cursor_position > 0:
                            self.chat_input = (self.chat_input[:self.cursor_position - 1] +
                                               self.chat_input[self.cursor_position:])
                            self.cursor_position -= 1

                    elif event.key == pygame.K_DELETE:
                        if self.cursor_position < len(self.chat_input):
                            self.chat_input = (self.chat_input[:self.cursor_position] +
                                               self.chat_input[self.cursor_position + 1:])

                    elif event.key == pygame.K_LEFT:
                        self.cursor_position = max(0, self.cursor_position - 1)

                    elif event.key == pygame.K_RIGHT:
                        self.cursor_position = min(len(self.chat_input), self.cursor_position + 1)

                    elif event.key == pygame.K_HOME:
                        self.cursor_position = 0

                    elif event.key == pygame.K_END:
                        self.cursor_position = len(self.chat_input)

                    else:
                        # Regular character input
                        if len(self.chat_input) < self.max_input_length and event.unicode.isprintable():
                            self.chat_input = (self.chat_input[:self.cursor_position] +
                                               event.unicode +
                                               self.chat_input[self.cursor_position:])
                            self.cursor_position += 1

                elif event.type == pygame.KEYUP and self.chat_box_open:
                    if event.key == pygame.K_BACKSPACE:
                        self.backspace_held = False

            # Handle held backspace (fast delete)
            if self.backspace_held and self.chat_box_open:
                self.backspace_timer += self.clock.get_time()
                if self.backspace_timer >= self.backspace_initial_delay:
                    # Start repeating
                    if self.backspace_timer % self.backspace_repeat_delay < self.clock.get_time():
                        if self.cursor_position > 0:
                            self.chat_input = (self.chat_input[:self.cursor_position - 1] +
                                               self.chat_input[self.cursor_position:])
                            self.cursor_position -= 1

            self.update()

        # Cleanup
        if self.voice_system:
            self.voice_system.stop_audio()

        pygame.quit()


if __name__ == "__main__":
    avatar = MiniAvatar()
    avatar.run()