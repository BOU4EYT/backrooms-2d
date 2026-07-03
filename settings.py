import os

import pygame as pg
import glpg as gl

WINDOW_PRESET = "720p"
WINDOW_TITLE = "2D Backrooms: Lost in the Infinite"
TARGET_FPS = 60
BACKGROUND_COLOR = "grey"
TILE_SIZE = 48
UI_FONT_SIZE = 20
AMBIENT_CHANNEL = 7
AMBIENT_VOLUME = 0.4

TEXTURE_DIR_CANDIDATES = [
    os.path.join("assets", "textures"),
    os.path.join("Python Testing", "assets", "textures"),
]
AUDIO_DIR_CANDIDATES = [
    os.path.join("assets", "audio"),
    os.path.join("Python Testing", "assets", "audio"),
]
AUDIO_EXTENSIONS = [".wav", ".mp3"]

# Asset names map game concepts to file names without extensions.
TEXTURE_ASSET_MAPPING = {
    "wall": ["wall"],
    "floor": ["floor"],
    "hazard": ["hazard", "lava"],
    "exit": ["finish", "exit"],
    "item_test": ["item_test"],
    "player": ["player"],
}
AUDIO_ASSET_NAMES = ["hurt", "pickup", "ambient_buzz", "player_walk", "exit_door"]

# Shared asset registries populated at import time.
TEXTURES = {}
SOUNDS = {}
TILE_COLORS = {
    "wall": (185, 170, 110),
    "floor": (215, 200, 140),
    "hazard": (130, 20, 20),
    "exit": (50, 50, 50),
}

ROOM_TYPES = {
    "office_bay": {
        "weight": 35,
        "min_size": (5, 5),
        "max_size": (10, 8),
        "hazard_density": 0.02,
        "wall_tint": (190, 175, 100),
        "floor_tint": (225, 210, 140),
    },
    "pillar_hall": {
        "weight": 15,
        "min_size": (8, 8),
        "max_size": (14, 10),
        "hazard_density": 0.01,
        "wall_tint": (185, 170, 110),
        "floor_tint": (215, 200, 140),
    },
    "moist_room": {
        "weight": 20,
        "min_size": (4, 4),
        "max_size": (7, 7),
        "hazard_density": 0.18,
        "wall_tint": (60, 70, 40),
        "floor_tint": (90, 100, 60),
    },
    "cramped_storage": {
        "weight": 20,
        "min_size": (3, 3),
        "max_size": (5, 5),
        "hazard_density": 0.05,
        "wall_tint": (80, 70, 55),
        "floor_tint": (130, 115, 90),
    },
    "flooded_sublevel": {
        "weight": 10,
        "min_size": (6, 6),
        "max_size": (10, 9),
        "hazard_density": 0.30,
        "wall_tint": (30, 40, 55),
        "floor_tint": (50, 65, 80),
    },
    "corridor": {
        "weight": 0,
        "min_size": (1, 1),
        "max_size": (1, 1),
        "hazard_density": 0.02,
        "wall_tint": (150, 140, 120),
        "floor_tint": (180, 170, 150),
    },
}


gl.window(WINDOW_PRESET, title=WINDOW_TITLE, fps=TARGET_FPS, bg_color=BACKGROUND_COLOR)
pg.font.init()
try:
    pg.mixer.init()
except pg.error:
    AUDIO_ENABLED = False
else:
    AUDIO_ENABLED = True
ui_font = pg.font.Font(None, UI_FONT_SIZE)


def first_existing_path(paths):
    return next((path for path in paths if os.path.exists(path)), None)


def load_all_assets():
    """Load optional textures and audio, falling back to shapes/colors if missing."""
    TEXTURES.clear()
    SOUNDS.clear()

    tex_dir = first_existing_path(TEXTURE_DIR_CANDIDATES)
    if tex_dir:
        for game_name, file_names in TEXTURE_ASSET_MAPPING.items():
            for file_name in file_names:
                path = os.path.join(tex_dir, f"{file_name}.png")
                if os.path.exists(path):
                    image = pg.image.load(path).convert_alpha()
                    if game_name == "player":
                        TEXTURES["player_sheet"] = image
                    else:
                        TEXTURES[game_name] = pg.transform.scale(
                            image, (TILE_SIZE, TILE_SIZE)
                        )
                    break

    if not AUDIO_ENABLED:
        return

    aud_dir = first_existing_path(AUDIO_DIR_CANDIDATES)
    if aud_dir:
        for audio_name in AUDIO_ASSET_NAMES:
            for ext in AUDIO_EXTENSIONS:
                path = os.path.join(aud_dir, f"{audio_name}{ext}")
                if os.path.exists(path):
                    SOUNDS[audio_name] = pg.mixer.Sound(path)
                    break


def start_ambient_buzz():
    if AUDIO_ENABLED and "ambient_buzz" in SOUNDS:
        channel = pg.mixer.Channel(AMBIENT_CHANNEL)
        channel.play(SOUNDS["ambient_buzz"], loops=-1)
        channel.set_volume(AMBIENT_VOLUME)


load_all_assets()
start_ambient_buzz()
