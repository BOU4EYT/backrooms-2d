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

TEXTURE_DIR_CANDIDATES = [os.path.join("assets", "textures"), os.path.join("Python Testing", "assets", "textures")]
AUDIO_DIR_CANDIDATES = [os.path.join("assets", "audio"), os.path.join("Python Testing", "assets", "audio")]
AUDIO_EXTENSIONS = [".wav", ".mp3"]

# Asset names map game concepts to file names without extensions.
TEXTURE_ASSET_MAPPING = {
    "wall": "wall",
    "floor": "floor",
    "hazard": "lava",
    "exit": "finish",
    "item_test": "item_test",
    "player": "player",
}
AUDIO_ASSET_NAMES = ["hurt", "pickup", "ambient_buzz", "player_walk", "exit_door"]

# lava.png/hazard.png ship as a 10-cell autotile atlas, not a single tile.
# Pixel rects measured directly from the sheet (1134x928): 3 columns for the
# top/middle rows (split at x=378/758), 4 columns for the bottom row (split
# at x=378/628/869), rows split at y=281 and y=622-652. Naively scaling the
# whole sheet down to one TILE_SIZE square (the old generic loader path)
# squashed all 10 pieces together, which is why hazard clusters never
# tiled/connected correctly.
HAZARD_SHEET_RECTS = {
    "TL": (0, 0, 378, 281),
    "TC": (379, 0, 757, 281),
    "TR": (759, 0, 1133, 281),
    "CL": (0, 282, 378, 621),
    "CC": (379, 282, 757, 621),
    "CR": (759, 282, 1133, 621),
    "BL": (0, 653, 378, 899),
    "BC": (379, 653, 628, 899),
    "BR": (630, 653, 869, 899),
    "VR": (870, 653, 1133, 899),
}

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
    "office_bay": {"weight": 35, "min_size": (5, 5), "max_size": (10, 8), "hazard_density": 0.02, "wall_tint": (190, 175, 100), "floor_tint": (225, 210, 140), "light_weights": (90, 5, 5)},
    "pillar_hall": {"weight": 15, "min_size": (8, 8), "max_size": (14, 10), "hazard_density": 0.01, "wall_tint": (185, 170, 110), "floor_tint": (215, 200, 140), "light_weights": (80, 15, 5)},
    "moist_room": {"weight": 20, "min_size": (4, 4), "max_size": (7, 7), "hazard_density": 0.18, "wall_tint": (60, 70, 40), "floor_tint": (90, 100, 60), "light_weights": (55, 35, 10)},
    "cramped_storage": {"weight": 20, "min_size": (3, 3), "max_size": (5, 5), "hazard_density": 0.05, "wall_tint": (80, 70, 55), "floor_tint": (130, 115, 90), "light_weights": (60, 30, 10)},
    "flooded_sublevel": {"weight": 10, "min_size": (6, 6), "max_size": (10, 9), "hazard_density": 0.30, "wall_tint": (30, 40, 55), "floor_tint": (50, 65, 80), "light_weights": (45, 35, 20)},
    "corridor": {"weight": 0, "min_size": (1, 1), "max_size": (1, 1), "hazard_density": 0.02, "wall_tint": (150, 140, 120), "floor_tint": (180, 170, 150), "light_weights": (65, 25, 10)},
}


gl.window(WINDOW_PRESET, title=WINDOW_TITLE, fps=TARGET_FPS, bg_color=BACKGROUND_COLOR)
pg.font.init()
pg.mixer.init()
ui_font = pg.font.Font(None, UI_FONT_SIZE)


def first_existing_path(paths):
    return next((path for path in paths if os.path.exists(path)), None)


def load_all_assets():
    """Load optional textures and audio, falling back to shapes/colors if missing."""
    TEXTURES.clear()
    SOUNDS.clear()

    tex_dir = first_existing_path(TEXTURE_DIR_CANDIDATES)
    if tex_dir:
        for game_name, file_name in TEXTURE_ASSET_MAPPING.items():
            path = os.path.join(tex_dir, f"{file_name}.png")
            if os.path.exists(path):
                image = pg.image.load(path).convert_alpha()
                if game_name == "player":
                    TEXTURES["player_sheet"] = image
                elif game_name == "hazard":
                    # Check if this is a full autotile atlas or a simple single-tile image
                    img_width, img_height = image.get_size()
                    hazard_tiles = {}
                    
                    # If the image is large enough for the autotile atlas, slice it
                    if img_width >= 1134 and img_height >= 928:
                        # This is an autotile atlas (see HAZARD_SHEET_RECTS), not a
                        # single tile - slice each named cell out and scale it
                        # individually so the connected-tile art survives.
                        for cell_name, (x0, y0, x1, y1) in HAZARD_SHEET_RECTS.items():
                            cell = image.subsurface(pg.Rect(x0, y0, x1 - x0, y1 - y0)).copy()
                            hazard_tiles[cell_name] = pg.transform.smoothscale(cell, (TILE_SIZE, TILE_SIZE))
                    else:
                        # Simple single-tile image - use it for all variants
                        scaled = pg.transform.scale(image, (TILE_SIZE, TILE_SIZE))
                        for cell_name in HAZARD_SHEET_RECTS.keys():
                            hazard_tiles[cell_name] = scaled
                    
                    TEXTURES["hazard_tiles"] = hazard_tiles
                    # Keep a plain "hazard" entry (the fully-surrounded/interior
                    # piece) so existing "if 'hazard' in TEXTURES" checks elsewhere
                    # still work as a simple presence flag / fallback.
                    TEXTURES["hazard"] = hazard_tiles["CC"]
                else:
                    TEXTURES[game_name] = pg.transform.scale(image, (TILE_SIZE, TILE_SIZE))

    aud_dir = first_existing_path(AUDIO_DIR_CANDIDATES)
    if aud_dir:
        for audio_name in AUDIO_ASSET_NAMES:
            for ext in AUDIO_EXTENSIONS:
                path = os.path.join(aud_dir, f"{audio_name}{ext}")
                if os.path.exists(path):
                    SOUNDS[audio_name] = pg.mixer.Sound(path)
                    break


def start_ambient_buzz():
    if "ambient_buzz" in SOUNDS:
        channel = pg.mixer.Channel(AMBIENT_CHANNEL)
        channel.play(SOUNDS["ambient_buzz"], loops=-1)
        channel.set_volume(AMBIENT_VOLUME)


load_all_assets()