"""
Settings Window for MINI-XTAR
Manages TTS volume and SFX volume
"""
import pygame
import json
import ctypes
from pathlib import Path


class SettingsWindow:
    """
    Settings window with volume sliders for TTS and SFX
    """

    def __init__(self, parent_avatar):
        """
        Initialize settings window

        Args:
            parent_avatar: Reference to main MiniAvatar instance
        """
        self.parent = parent_avatar
        self.active = False

        # Window dimensions
        self.width = 400
        self.height = 300
        
        # Dragging support
        self.dragging = False
        self.drag_start_window_x = 0
        self.drag_start_window_y = 0
        self.drag_start_mouse_x = 0
        self.drag_start_mouse_y = 0
        
        # Window position (centered by default, but can be dragged)
        self.window_x = 0  # Will be set when opened
        self.window_y = 0  # Will be set when opened

        # Settings file
        self.settings_file = Path("config/settings.json")
        self.settings_file.parent.mkdir(exist_ok=True)

        # Load or create default settings
        self.settings = self._load_settings()

        # Apply loaded settings to voice system
        self._apply_settings()

        # UI elements
        self.font = pygame.font.SysFont("Segoe UI", 18)
        self.title_font = pygame.font.SysFont("Segoe UI", 24, bold=True)

        # Slider properties
        self.slider_height = 20
        self.slider_width = 250
        self.slider_handle_radius = 12

        # TTS Volume slider
        self.tts_slider_rect = pygame.Rect(100, 100, self.slider_width, self.slider_height)
        self.tts_handle_x = self._volume_to_x(self.settings["tts_volume"], self.tts_slider_rect)
        self.tts_dragging = False

        # SFX Volume slider
        self.sfx_slider_rect = pygame.Rect(100, 170, self.slider_width, self.slider_height)
        self.sfx_handle_x = self._volume_to_x(self.settings["sfx_volume"], self.sfx_slider_rect)
        self.sfx_dragging = False

        # OK button
        self.ok_button_rect = pygame.Rect(150, 230, 100, 40)

    def _load_settings(self):
        """Load settings from file or return defaults"""
        default_settings = {
            "tts_volume": 1.0,  # 0.0 to 1.0
            "sfx_volume": 0.5  # 0.0 to 1.0
        }

        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults in case new settings added
                    return {**default_settings, **loaded}
            except Exception as e:
                print(f"⚠️ Failed to load settings: {e}")

        return default_settings

    def _save_settings(self):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            print("✅ Settings saved")
        except Exception as e:
            print(f"❌ Failed to save settings: {e}")

    def _apply_settings(self):
        """Apply current settings to voice system"""
        # Apply TTS volume
        if self.parent.voice_system and self.parent.voice_system.engine:
            try:
                self.parent.voice_system.engine.setProperty("volume", self.settings["tts_volume"])
            except Exception as e:
                print(f"⚠️ Failed to apply TTS volume: {e}")

        # Apply SFX volume (when sound effects are added)
        # TODO: Uncomment when sound effects are implemented
        # if hasattr(self.parent, 'sfx_system'):
        #     self.parent.sfx_system.set_volume(self.settings["sfx_volume"])

    def _volume_to_x(self, volume, slider_rect):
        """Convert volume (0.0-1.0) to slider handle X position"""
        return slider_rect.x + int(volume * slider_rect.width)

    def _x_to_volume(self, x, slider_rect):
        """Convert slider handle X position to volume (0.0-1.0)"""
        relative_x = x - slider_rect.x
        volume = relative_x / slider_rect.width
        return max(0.0, min(1.0, volume))  # Clamp to 0-1

    def open(self):
        """Open the settings window"""
        self.active = True
        # Center window on first open
        if self.window_x == 0 and self.window_y == 0:
            self.window_x = (self.parent.width - self.width) // 2
            self.window_y = (self.parent.height - self.height) // 2
        # Reload settings in case they changed
        self.settings = self._load_settings()
        self.tts_handle_x = self._volume_to_x(self.settings["tts_volume"], self.tts_slider_rect)
        self.sfx_handle_x = self._volume_to_x(self.settings["sfx_volume"], self.sfx_slider_rect)

    def close(self):
        """Close the settings window"""
        self.active = False
        # Turn off settings button state when window closes
        if self.parent:
            self.parent.settings_enabled = False

    def handle_event(self, event):
        """
        Handle mouse events for sliders and buttons

        Args:
            event: Pygame event

        Returns:
            True if event was handled, False otherwise
        """
        if not self.active:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                pos = event.pos
                
                # Adjust position relative to settings window
                relative_pos = (pos[0] - self.window_x, pos[1] - self.window_y)
                
                # Check if clicking on title bar area (for dragging)
                title_bar_rect = pygame.Rect(self.window_x, self.window_y, self.width, 50)
                if title_bar_rect.collidepoint(pos):
                    # Check if not clicking on a button or slider
                    if not self.ok_button_rect.collidepoint(relative_pos):
                        # Check if not clicking on slider handles
                        tts_handle_rect = pygame.Rect(
                            self.tts_handle_x - self.slider_handle_radius,
                            self.tts_slider_rect.y + self.tts_slider_rect.height // 2 - self.slider_handle_radius,
                            self.slider_handle_radius * 2,
                            self.slider_handle_radius * 2
                        )
                        sfx_handle_rect = pygame.Rect(
                            self.sfx_handle_x - self.slider_handle_radius,
                            self.sfx_slider_rect.y + self.sfx_slider_rect.height // 2 - self.slider_handle_radius,
                            self.slider_handle_radius * 2,
                            self.slider_handle_radius * 2
                        )
                        if not tts_handle_rect.collidepoint(relative_pos) and not sfx_handle_rect.collidepoint(relative_pos):
                            # Start dragging
                            self.dragging = True
                            # Get current window position
                            self.drag_start_window_x = self.window_x
                            self.drag_start_window_y = self.window_y
                            # Get mouse position on screen
                            cursor_pos = ctypes.wintypes.POINT()
                            ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor_pos))
                            self.drag_start_mouse_x = cursor_pos.x
                            self.drag_start_mouse_y = cursor_pos.y
                            return True

                # Check OK button

                if self.ok_button_rect.collidepoint(relative_pos):
                    self._save_settings()
                    self._apply_settings()
                    self.close()
                    return True

                # Check TTS slider handle
                tts_handle_rect = pygame.Rect(
                    self.tts_handle_x - self.slider_handle_radius,
                    self.tts_slider_rect.y + self.tts_slider_rect.height // 2 - self.slider_handle_radius,
                    self.slider_handle_radius * 2,
                    self.slider_handle_radius * 2
                )
                if tts_handle_rect.collidepoint(relative_pos):
                    self.tts_dragging = True
                    return True

                # Check SFX slider handle
                sfx_handle_rect = pygame.Rect(
                    self.sfx_handle_x - self.slider_handle_radius,
                    self.sfx_slider_rect.y + self.sfx_slider_rect.height // 2 - self.slider_handle_radius,
                    self.slider_handle_radius * 2,
                    self.slider_handle_radius * 2
                )
                if sfx_handle_rect.collidepoint(relative_pos):
                    self.sfx_dragging = True
                    return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.tts_dragging = False
                self.sfx_dragging = False
                self.dragging = False

        elif event.type == pygame.MOUSEMOTION:
            pos = event.pos
            
            # Handle window dragging
            if self.dragging:
                cursor_pos = ctypes.wintypes.POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor_pos))
                
                delta_x = cursor_pos.x - self.drag_start_mouse_x
                delta_y = cursor_pos.y - self.drag_start_mouse_y
                
                self.window_x = self.drag_start_window_x + delta_x
                self.window_y = self.drag_start_window_y + delta_y
                
                # Keep window within screen bounds (optional, can be removed if you want it to go off-screen)
                self.window_x = max(0, min(self.window_x, self.parent.width - self.width))
                self.window_y = max(0, min(self.window_y, self.parent.height - self.height))
                
                return True
            
            if self.tts_dragging or self.sfx_dragging:
                relative_pos = (pos[0] - self.window_x, pos[1] - self.window_y)

                if self.tts_dragging:
                    # Update TTS slider
                    self.tts_handle_x = max(
                        self.tts_slider_rect.x,
                        min(relative_pos[0], self.tts_slider_rect.x + self.tts_slider_rect.width)
                    )
                    self.settings["tts_volume"] = self._x_to_volume(self.tts_handle_x, self.tts_slider_rect)
                    # Apply immediately for real-time feedback
                    self._apply_settings()

                if self.sfx_dragging:
                    # Update SFX slider
                    self.sfx_handle_x = max(
                        self.sfx_slider_rect.x,
                        min(relative_pos[0], self.sfx_slider_rect.x + self.sfx_slider_rect.width)
                    )
                    self.settings["sfx_volume"] = self._x_to_volume(self.sfx_handle_x, self.sfx_slider_rect)
                    # TODO: Apply SFX volume when sound effects are added
                    # self._apply_settings()

                return True

        return False

    def draw(self, screen):
        """Draw the settings window on the screen"""
        if not self.active:
            return

        # Use stored window position (can be dragged)
        window_x = self.window_x
        window_y = self.window_y

        # Draw semi-transparent background overlay (transparent like chat bubble)
        overlay = pygame.Surface((self.parent.width, self.parent.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))  # Reduced alpha for more transparency
        screen.blit(overlay, (0, 0))

        # Draw settings window background with transparency (like chat bubble)
        window_rect = pygame.Rect(window_x, window_y, self.width, self.height)
        # Create a surface with per-pixel alpha for transparency
        window_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        # Draw background with transparency (matching chat bubble style)
        pygame.draw.rect(window_surface, (40, 40, 50, 250), (0, 0, self.width, self.height), border_radius=15)
        pygame.draw.rect(window_surface, (150, 100, 200, 255), (0, 0, self.width, self.height), 3, border_radius=15)
        screen.blit(window_surface, (window_x, window_y))

        # Draw title (with drag indicator)
        title_text = self.title_font.render("Settings", True, (255, 255, 255))
        title_rect = title_text.get_rect(center=(window_x + self.width // 2, window_y + 40))
        screen.blit(title_text, title_rect)
        
        # Draw subtle drag hint (optional - can be removed)
        hint_font = pygame.font.SysFont("Segoe UI", 10)
        hint_text = hint_font.render("(Drag to move)", True, (150, 150, 150))
        hint_rect = hint_text.get_rect(center=(window_x + self.width // 2, window_y + 60))
        screen.blit(hint_text, hint_rect)

        # Draw TTS Volume label
        tts_label = self.font.render("TTS Volume:", True, (255, 255, 255))
        screen.blit(tts_label, (window_x + 20, window_y + 85))

        # Draw TTS slider track
        slider_rect_abs = self.tts_slider_rect.move(window_x, window_y)
        pygame.draw.rect(screen, (100, 100, 100), slider_rect_abs, border_radius=10)

        # Draw TTS slider fill
        fill_width = int((self.tts_handle_x - self.tts_slider_rect.x) * 1)
        fill_rect = pygame.Rect(
            slider_rect_abs.x,
            slider_rect_abs.y,
            fill_width,
            slider_rect_abs.height
        )
        pygame.draw.rect(screen, (100, 180, 255), fill_rect, border_radius=10)

        # Draw TTS slider handle
        handle_pos = (
            window_x + self.tts_handle_x,
            window_y + self.tts_slider_rect.y + self.tts_slider_rect.height // 2
        )
        pygame.draw.circle(screen, (255, 255, 255), handle_pos, self.slider_handle_radius)
        pygame.draw.circle(screen, (100, 180, 255), handle_pos, self.slider_handle_radius - 2)

        # Draw TTS volume percentage
        tts_percent = int(self.settings["tts_volume"] * 100)
        tts_percent_text = self.font.render(f"{tts_percent}%", True, (255, 255, 255))
        screen.blit(tts_percent_text, (window_x + 360, window_y + 95))

        # Draw SFX Volume label
        sfx_label = self.font.render("SFX Volume:", True, (255, 255, 255))
        screen.blit(sfx_label, (window_x + 20, window_y + 155))

        # Draw SFX slider track
        slider_rect_abs = self.sfx_slider_rect.move(window_x, window_y)
        pygame.draw.rect(screen, (100, 100, 100), slider_rect_abs, border_radius=10)

        # Draw SFX slider fill
        fill_width = int((self.sfx_handle_x - self.sfx_slider_rect.x) * 1)
        fill_rect = pygame.Rect(
            slider_rect_abs.x,
            slider_rect_abs.y,
            fill_width,
            slider_rect_abs.height
        )
        pygame.draw.rect(screen, (255, 150, 100), fill_rect, border_radius=10)

        # Draw SFX slider handle
        handle_pos = (
            window_x + self.sfx_handle_x,
            window_y + self.sfx_slider_rect.y + self.sfx_slider_rect.height // 2
        )
        pygame.draw.circle(screen, (255, 255, 255), handle_pos, self.slider_handle_radius)
        pygame.draw.circle(screen, (255, 150, 100), handle_pos, self.slider_handle_radius - 2)

        # Draw SFX volume percentage
        sfx_percent = int(self.settings["sfx_volume"] * 100)
        sfx_percent_text = self.font.render(f"{sfx_percent}%", True, (255, 255, 255))
        screen.blit(sfx_percent_text, (window_x + 360, window_y + 165))

        # Draw OK button
        ok_rect_abs = self.ok_button_rect.move(window_x, window_y)
        pygame.draw.rect(screen, (100, 180, 255), ok_rect_abs, border_radius=10)
        pygame.draw.rect(screen, (255, 255, 255), ok_rect_abs, 2, border_radius=10)
        ok_text = self.font.render("OK", True, (255, 255, 255))
        ok_text_rect = ok_text.get_rect(center=ok_rect_abs.center)
        screen.blit(ok_text, ok_text_rect)