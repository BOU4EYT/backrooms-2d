import pygame as pg
import glpg as gl
import os

gl.window("720p", title="2D Backrooms: Lost in the Infinite", fps=60, bg_color="grey")

pg.font.init()
pg.mixer.init() 
ui_font = pg.font.Font(None, 20)

TILE_SIZE = 48

# --- GLOBAL ASSETS REGISTRY ---
TEXTURES = {}
SOUNDS = {}
TILE_COLORS = {"wall": (185, 170, 110), "floor": (215, 200, 140), "hazard": (130, 20, 20), "exit": (50, 50, 50)}

ROOM_TYPES = {
    "office_bay": {"weight": 35, "min_size": (5, 5), "max_size": (10, 8), "hazard_density": 0.02, "wall_tint": (190, 175, 100), "floor_tint": (225, 210, 140)},
    "pillar_hall": {"weight": 15, "min_size": (8, 8), "max_size": (14, 10), "hazard_density": 0.01, "wall_tint": (185, 170, 110), "floor_tint": (215, 200, 140)},
    "moist_room": {"weight": 20, "min_size": (4, 4), "max_size": (7, 7), "hazard_density": 0.18, "wall_tint": (60, 70, 40), "floor_tint": (90, 100, 60)},
    "cramped_storage": {"weight": 20, "min_size": (3, 3), "max_size": (5, 5), "hazard_density": 0.05, "wall_tint": (80, 70, 55), "floor_tint": (130, 115, 90)},
    "flooded_sublevel": {"weight": 10, "min_size": (6, 6), "max_size": (10, 9), "hazard_density": 0.30, "wall_tint": (30, 40, 55), "floor_tint": (50, 65, 80)},
    "corridor": {"weight": 0, "min_size": (1, 1), "max_size": (1, 1), "hazard_density": 0.02, "wall_tint": (150, 140, 120), "floor_tint": (180, 170, 150)},
}

def load_all_assets():
    global TEXTURES, SOUNDS
    possible_dirs = [os.path.join("assets", "textures"), os.path.join("Python Testing", "assets", "textures")]
    tex_dir = next((d for d in possible_dirs if os.path.exists(d)), None)

    if tex_dir:
        asset_mapping = {"wall": "wall", "floor": "floor", "hazard": "lava", "exit": "finish", "item_test": "item_test", "player": "player"}
        for game_name, file_name in asset_mapping.items():
            p = os.path.join(tex_dir, f"{file_name}.png")
            if os.path.exists(p):
                img = pg.image.load(p).convert_alpha()
                if game_name == "player":
                    TEXTURES["player_sheet"] = img
                else:
                    TEXTURES[game_name] = pg.transform.scale(img, (TILE_SIZE, TILE_SIZE))
    
    aud_dirs = [os.path.join("assets", "audio"), os.path.join("Python Testing", "assets", "audio")]
    aud_dir = next((d for d in aud_dirs if os.path.exists(d)), None)
    if aud_dir:
        for audio_name in ["hurt", "pickup", "ambient_buzz", "player_walk", "exit_door"]:
            for ext in [".wav", ".mp3"]:
                p = os.path.join(aud_dir, f"{audio_name}{ext}")
                if os.path.exists(p):
                    SOUNDS[audio_name] = pg.mixer.Sound(p)
                    break

load_all_assets()

def start_ambient_buzz():
    if "ambient_buzz" in SOUNDS:
        pg.mixer.Channel(7).play(SOUNDS["ambient_buzz"], loops=-1)
        pg.mixer.Channel(7).set_volume(0.4)

start_ambient_buzz()