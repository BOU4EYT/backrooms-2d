import os

import pygame as pg

TARGET_FPS = 60

# Shared values used by the menu before the game module is loaded.
MENU_SETTINGS = {
    "FLASHLIGHT_SOFTNESS_STEPS": 48,
    "SHADOW_SAMPLING": 1,
    "TARGET_FPS": TARGET_FPS,
}

pg.font.init()
pg.init()
pg.mixer.init()
pg.display.set_caption("2D Backrooms: Lost in the Infinite")
clock = pg.time.Clock()

# Tracks whether menu music has already been kicked off, so we don't
# re-check/reload every single frame.
_menu_music_started = False


def _reinit_after_game_loop():
    """glpg's gl.run() calls pg.quit() internally when its loop ends (e.g. on
    ESC), fully tearing down display/font/mixer/etc. That's fine for a
    program that's exiting, but we're returning to this menu's own loop
    afterward, so everything pygame needs has to be brought back up before
    we touch the screen, clock, or fonts again."""
    global clock, _menu_music_started
    pg.init()
    pg.font.init()
    pg.mixer.init()
    pg.display.set_mode((1280, 720))
    pg.display.set_caption("2D Backrooms: Lost in the Infinite")
    clock = pg.time.Clock()
    _menu_music_started = False


def get_screen():
    surface = pg.display.get_surface()
    if surface is None:
        surface = pg.display.set_mode((1280, 720))
    return surface


class MenuButton:
    def __init__(self, label, font, position, size, color, text_color=(255, 255, 255)):
        self.label = label
        self.font = font
        self.size = size
        self.color = color
        self.text_color = text_color
        self.rect = pg.Rect(position[0] - size[0] / 2, position[1] - size[1] / 2, size[0], size[1])
        self.text_surface = self.font.render(self.label, True, self.text_color)
        self.text_rect = self.text_surface.get_rect(center=self.rect.center)

    def is_hovered(self):
        return self.rect.collidepoint(pg.mouse.get_pos())

    def draw(self):
        surface = get_screen()
        pg.draw.rect(surface, self.color, self.rect, border_radius=8)
        pg.draw.rect(surface, (255, 255, 255), self.rect, 2, border_radius=8)
        surface.blit(self.text_surface, self.text_rect)


class MenuSlider:
    def __init__(self, label, font, position, size, value, minimum=0.0, maximum=1.0, integer=False):
        self.label = label
        self.font = font
        self.size = size
        self.minimum = minimum
        self.maximum = maximum
        self.integer = integer
        self.value = self._clamp(value)
        self.dragging = False
        self.rect = pg.Rect(position[0] - size[0] / 2, position[1] - size[1] / 2, size[0], size[1])

    def _clamp(self, value):
        return max(self.minimum, min(self.maximum, value))

    def _value_from_position(self, x):
        ratio = (x - self.rect.left) / self.rect.width if self.rect.width else 0.0
        ratio = max(0.0, min(1.0, ratio))
        value = self.minimum + ratio * (self.maximum - self.minimum)
        return int(round(value)) if self.integer else value

    def handle_event(self, event):
        if event.type == pg.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self.dragging = True
            self.value = self._clamp(self._value_from_position(event.pos[0]))
            return True
        if event.type == pg.MOUSEBUTTONUP:
            self.dragging = False
        if event.type == pg.MOUSEMOTION and self.dragging:
            self.value = self._clamp(self._value_from_position(event.pos[0]))
            return True
        return False

    def draw(self):
        surface = get_screen()
        label_surface = self.font.render(self.label, True, (255, 255, 255))
        label_rect = label_surface.get_rect(center=(self.rect.centerx, self.rect.top - 18))
        surface.blit(label_surface, label_rect)

        track_rect = pg.Rect(self.rect.left, self.rect.centery - 2, self.rect.width, 4)
        pg.draw.rect(surface, (70, 70, 80), track_rect)

        ratio = 0.0 if self.maximum == self.minimum else (self.value - self.minimum) / (self.maximum - self.minimum)
        ratio = max(0.0, min(1.0, ratio))
        knob_x = self.rect.left + ratio * self.rect.width
        knob_y = self.rect.centery
        pg.draw.circle(surface, (220, 220, 220), (int(knob_x), knob_y), 10)
        pg.draw.circle(surface, (255, 255, 255), (int(knob_x), knob_y), 6)


def load_menu_background(path, size):
    if os.path.exists(path):
        image = pg.image.load(path)
        return pg.transform.scale(image, size)

    surface = pg.Surface(size)
    surface.fill((20, 20, 30))
    for y in range(0, size[1], 40):
        pg.draw.rect(surface, (35, 35, 55), (0, y, size[0], 20))
    return surface


def load_menu_font(path, size):
    if not pg.font.get_init():
        pg.font.init()

    try:
        if os.path.exists(path):
            font = pg.font.Font(path, size)
            if font is not None:
                return font
    except Exception:
        pass

    return pg.font.SysFont("arial", size)


def _start_menu_music():
    """Kick off menu music once, instead of checking every frame."""
    global _menu_music_started
    if _menu_music_started:
        return
    try:
        pg.mixer.music.load("assets/audio/menu_music.mp3")
        pg.mixer.music.play(-1)
    except Exception:
        pass
    _menu_music_started = True


def main_menu():
    """Main menu of the game."""
    global _menu_music_started
    _menu_music_started = False  # allow music to restart if we return here

    # Load the background image or fall back to a generated surface
    background = load_menu_background("assets/images/main_menu_background.png", (1280, 720))

    # Load the font or fall back to a system font
    font = load_menu_font("assets/fonts/PressStart2P-Regular.ttf", 24)
    if font is None:
        font = pg.font.SysFont("arial", 24)

    # Create the buttons
    start_button = MenuButton("Start Game", font, (640, 300), (240, 56), "green")
    settings_button = MenuButton("Settings", font, (640, 400), (240, 56), "blue")
    quit_button = MenuButton("Quit", font, (640, 500), (240, 56), "red")

    # Main loop
    running = True
    while running:
        # handle events
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                return

            if event.type == pg.MOUSEBUTTONDOWN:
                if start_button.is_hovered():
                    main_module = __import__("main")
                    main_module.FLASHLIGHT_SOFTNESS_STEPS = int(MENU_SETTINGS["FLASHLIGHT_SOFTNESS_STEPS"])
                    main_module.SHADOW_SAMPLING = int(MENU_SETTINGS["SHADOW_SAMPLING"])
                    main_module.TARGET_FPS = MENU_SETTINGS["TARGET_FPS"]
                    main_module.start_game()
                    # start_game()'s gl.run() has now returned, which means
                    # pygame was fully torn down by glpg's internal pg.quit().
                    # Bring it back before this loop touches the screen again.
                    _reinit_after_game_loop()
                    background = load_menu_background("assets/images/main_menu_background.png", (1280, 720))
                elif settings_button.is_hovered():
                    settings_menu()
                elif quit_button.is_hovered():
                    pg.quit()
                    return

        # Draw the background
        get_screen().blit(background, (0, 0))

        # menu music (only attempts load/play once per menu entry)
        _start_menu_music()

        # draw buttons
        start_button.draw()
        settings_button.draw()
        quit_button.draw()

        pg.display.flip()
        clock.tick(TARGET_FPS)


def settings_menu():
    # pygame doesn't provide a global master volume; derive a simple master
    # from music and channel 0 (if available).
    try:
        music_volume = pg.mixer.music.get_volume()
    except Exception:
        music_volume = 1.0

    try:
        sfx_channel = pg.mixer.Channel(0)
        sfx_volume = sfx_channel.get_volume()
    except Exception:
        sfx_volume = 1.0

    # approximate master as average of music and sfx
    master_volume = (music_volume + sfx_volume) / 2

    ## Create the settings menu
    # Load the background image or fall back to a generated surface
    background = load_menu_background("assets/images/settings_menu_background.png", (1280, 720))

    # Load the font or fall back to a system font
    font = load_menu_font("assets/fonts/PressStart2P-Regular.ttf", 24)

    # create the sliders and buttons
    # Re-laid-out on a wider vertical grid so nothing overlaps the buttons.
    master_volume_slider = MenuSlider("Master Volume", font, (640, 140), (400, 26), master_volume, minimum=0.0, maximum=1.0)
    music_volume_slider = MenuSlider("Music Volume", font, (640, 220), (400, 26), music_volume, minimum=0.0, maximum=1.0)
    sfx_volume_slider = MenuSlider("SFX Volume", font, (640, 300), (400, 26), sfx_volume, minimum=0.0, maximum=1.0)

    flashlight_softness_slider = MenuSlider("Flashlight Softness", font, (640, 380), (400, 26), MENU_SETTINGS["FLASHLIGHT_SOFTNESS_STEPS"], minimum=1.0, maximum=64.0, integer=True)
    shadow_sampling_slider = MenuSlider("Shadow Sampling", font, (640, 460), (400, 26), MENU_SETTINGS["SHADOW_SAMPLING"], minimum=1.0, maximum=8.0, integer=True)
    fps_slider = MenuSlider("Target FPS", font, (640, 540), (400, 26), MENU_SETTINGS["TARGET_FPS"], minimum=30.0, maximum=144.0, integer=True)

    save_button = MenuButton("Save Settings", font, (640, 630), (260, 44), "green")
    cancel_button = MenuButton("Cancel", font, (640, 690), (220, 44), "red")

    sliders = [
        master_volume_slider,
        music_volume_slider,
        sfx_volume_slider,
        flashlight_softness_slider,
        shadow_sampling_slider,
        fps_slider,
    ]

    # Track whether the user has actually touched the master slider, so
    # saving doesn't silently overwrite independently-set music/sfx values
    # with a stale initial average.
    master_touched = False

    # Main loop
    while True:
        # handle events
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                return

            if event.type == pg.MOUSEBUTTONDOWN:
                handled = False
                for slider in sliders:
                    if slider.handle_event(event):
                        handled = True
                        if slider is master_volume_slider:
                            master_touched = True

                if handled:
                    pass
                elif save_button.is_hovered():
                    # Save the settings
                    try:
                        pg.mixer.music.set_volume(music_volume_slider.value)
                    except Exception:
                        pass

                    try:
                        pg.mixer.Channel(0).set_volume(sfx_volume_slider.value)
                    except Exception:
                        pass

                    # Only apply "master" as an override if the user actually
                    # dragged it; otherwise leave music/sfx as independently set.
                    if master_touched:
                        try:
                            pg.mixer.music.set_volume(master_volume_slider.value)
                            pg.mixer.Channel(0).set_volume(master_volume_slider.value)
                        except Exception:
                            pass

                    MENU_SETTINGS["FLASHLIGHT_SOFTNESS_STEPS"] = flashlight_softness_slider.value
                    MENU_SETTINGS["SHADOW_SAMPLING"] = shadow_sampling_slider.value
                    MENU_SETTINGS["TARGET_FPS"] = fps_slider.value

                    return  # Return to the main menu

                elif cancel_button.is_hovered():
                    return  # Return to the main menu
            elif event.type in (pg.MOUSEBUTTONUP, pg.MOUSEMOTION):
                for slider in sliders:
                    if slider.handle_event(event) and slider is master_volume_slider:
                        master_touched = True

        # Draw the background
        get_screen().blit(background, (0, 0))

        # draw sliders and buttons
        for slider in sliders:
            slider.draw()
        save_button.draw()
        cancel_button.draw()

        pg.display.flip()
        clock.tick(TARGET_FPS)


if __name__ == "__main__":
    main_menu()