import pygame as pg
import glpg as gl
import math
import random

# Import from your separated modules
import settings
from player import Player
import generator

cam_x, cam_y = 0, 0
current_level_index = 0
fade_alpha = 0          
fade_state = "idle"     
fade_speed = 8           
pending_level_id = None  

def start_level_transition(next_level_id):
    global fade_state, pending_level_id
    fade_state = "fading_out"
    pending_level_id = next_level_id

# Initialize the first level using your generator module
generator.generate_backrooms_level(0)
player = Player(generator.spawn_x, generator.spawn_y)

@gl.on_update
def update(dt):
    global cam_x, cam_y, current_level_index, fade_alpha, fade_state, pending_level_id
    if gl.key("escape"): gl.quit()

    # Update player using the walls list from generator
    hit_exit = player.update(generator.walls, generator.hazard_tiles, generator.exit_tiles, generator.map_width, generator.map_height)
    if hit_exit and fade_state == "idle":
        current_level_index += 1
        start_level_transition(current_level_index)

    if fade_state == "fading_out":
        fade_alpha = min(255, fade_alpha + fade_speed)
        if fade_alpha >= 255:
            generator.generate_backrooms_level(pending_level_id, player)   
            fade_state = "fading_in"
    elif fade_state == "fading_in":
        fade_alpha = max(0, fade_alpha - fade_speed)
        if fade_alpha <= 0:
            fade_state = "idle"

    cam_x = max(0, min((player.x + player.size / 2) - 1280 / 2, generator.map_width - 1280))
    cam_y = max(0, min((player.y + player.size / 2) - 720 / 2, generator.map_height - 720))

@gl.on_draw
def draw():
    surface = pg.display.get_surface()
    
    def room_tint_for(px, py, kind):
        tx, ty = int(px // settings.TILE_SIZE), int(py // settings.TILE_SIZE)
        if 0 <= ty < len(generator.room_type_grid) and 0 <= tx < len(generator.room_type_grid[0]):
            rtype = generator.room_type_grid[ty][tx]
            if rtype and rtype in settings.ROOM_TYPES:
                return settings.ROOM_TYPES[rtype][f"{kind}_tint"]
        return settings.TILE_COLORS[kind]

    # 1. Render World Elements from generator module
    for floor in generator.floors:
        if "floor" in settings.TEXTURES: surface.blit(settings.TEXTURES["floor"], (floor[0] - cam_x, floor[1] - cam_y))
        else: gl.draw.rect(floor[0] - cam_x, floor[1] - cam_y, floor[2], floor[3], room_tint_for(floor[0], floor[1], "floor"))
        
    for haz in generator.hazard_tiles:
        if "hazard" in settings.TEXTURES: surface.blit(settings.TEXTURES["hazard"], (haz[0] - cam_x, haz[1] - cam_y))
        else: gl.draw.rect(haz[0] - cam_x, haz[1] - cam_y, haz[2], haz[3], settings.TILE_COLORS["hazard"])
        
    for ex in generator.exit_tiles:
        if "exit" in settings.TEXTURES: surface.blit(settings.TEXTURES["exit"], (ex[0] - cam_x, ex[1] - cam_y))
        else: gl.draw.rect(ex[0] - cam_x, ex[1] - cam_y, ex[2], ex[3], settings.TILE_COLORS["exit"])
        
    for wall in generator.walls:
        if "wall" in settings.TEXTURES: surface.blit(settings.TEXTURES["wall"], (wall[0] - cam_x, wall[1] - cam_y))
        else: gl.draw.rect(wall[0] - cam_x, wall[1] - cam_y, wall[2], wall[3], room_tint_for(wall[0], wall[1], "wall"))
    
    player.draw(cam_x, cam_y)

    # 2. Advanced Raycasted Fog of War (Line of Sight Shadows)
    # 1. Darkness overlay: opaque everywhere by default, per-pixel alpha controls
    #    how much of it shows. This is the layer we actually blit to the screen.
    darkness = pg.Surface((1280, 720), pg.SRCALPHA)
    darkness.fill((10, 10, 12, 255))  # near-total darkness, fully opaque

    # 2. Get the screen coordinates of your player center point
    p_center_x = player.x + player.size / 2
    p_center_y = player.y + player.size / 2
    scr_px = int(p_center_x - cam_x)
    scr_py = int(p_center_y - cam_y)

    # 3. Visibility layer: WHITE shapes whose alpha says how much to reveal.
    #    (Kept separate from `darkness` because pygame.draw overwrites pixels
    #    directly rather than blending, so we need one clean surface to later
    #    subtract from the darkness alpha in a single blit.)
    visibility = pg.Surface((1280, 720), pg.SRCALPHA)
    visibility.fill((0, 0, 0, 0))

    # --- A: CARVE THE LIGHT FIELDS (Flashlight & Proximity) ---
    if player.flashlight_on and (player.smooth_dir_x != 0 or player.smooth_dir_y != 0):
        forward_x, forward_y = player.smooth_dir_x, player.smooth_dir_y
        flicker_prob = 0.15 if player.sanity < 40 else 0.0
        
        if random.random() > flicker_prob:
            cone_length = player.view_radius * (0.6 + 0.4 * (player.sanity / 100.0))
            cone_width = 220
            perp_x, perp_y = -forward_y, forward_x
            mag = math.hypot(perp_x, perp_y) or 1
            perp_x /= mag; perp_y /= mag

            # Gradual alpha steps for a realistic, soft beam drop-off
            for step in reversed(range(1, 11)):
                ratio = step / 10.0
                current_length = cone_length * ratio + random.randint(-3, 3)
                half_width = (cone_width / 2) * ratio + random.randint(-2, 2)
                reveal_alpha = int(255 * (1.0 - ratio))

                tip = (scr_px, scr_py)
                base_left = (int(scr_px + perp_x * half_width * 0.15), int(scr_py + perp_y * half_width * 0.15))
                base_right = (int(scr_px - perp_x * half_width * 0.15), int(scr_py - perp_y * half_width * 0.15))
                end_left = (int(scr_px + forward_x * current_length + perp_x * half_width), int(scr_py + forward_y * current_length + perp_y * half_width))
                end_right = (int(scr_px + forward_x * current_length - perp_x * half_width), int(scr_py + forward_y * current_length - perp_y * half_width))

                # Paint the reveal amount for this ring of the cone
                pg.draw.polygon(visibility, (255, 255, 255, reveal_alpha), [tip, base_left, end_left, end_right, base_right])

    # Player baseline physical circle proximity aura glow
    player_base_rad = int(player.size * 1.5)
    for r in range(player_base_rad, 0, -4):
        c_ratio = r / player_base_rad
        reveal_alpha = int(255 * (1.0 - c_ratio))
        pg.draw.circle(visibility, (255, 255, 255, reveal_alpha), (scr_px, scr_py), max(1, r))

    # Subtract the visibility alpha out of the darkness alpha -> lit areas become transparent
    darkness.blit(visibility, (0, 0), special_flags=pg.BLEND_RGBA_SUB)

    # --- B: PROJECT SHADOW OCCLUSION POLYGONS BEHIND WALL GEOMETRY ---
    shadow_extension = 2000.0  # Length to cast shadow projection beyond screen borders
    
    # Iterate over the walls list exposed by your generator module
    for wall in generator.walls:  # Update this reference if your generator names it differently (e.g., generator.walls)
        wx, wy, ww, wh = wall
        w_center_x = wx + ww / 2
        w_center_y = wy + wh / 2
        
        # Performance Guard: Skip processing wall units outside active player rendering boundaries
        if math.hypot(w_center_x - p_center_x, w_center_y - p_center_y) > player.view_radius + 100:
            continue

        # Map out the 4 static vertex coordinates of the wall tile
        vertices = [(wx, wy), (wx + ww, wy), (wx + ww, wy + wh), (wx, wy + wh)]

        for i in range(4):
            v1 = vertices[i]
            v2 = vertices[(i + 1) % 4]

            # Convert map-space corner boundaries to active screen spaces
            s_v1x, s_v1y = v1[0] - cam_x, v1[1] - cam_y
            s_v2x, s_v2y = v2[0] - cam_x, v2[1] - cam_y

            # Trace mathematical projection rays from player light origin position
            d1x, d1y = v1[0] - p_center_x, v1[1] - p_center_y
            d2x, d2y = v2[0] - p_center_x, v2[1] - p_center_y

            mag1 = math.hypot(d1x, d1y) or 1
            mag2 = math.hypot(d2x, d2y) or 1

            # Cast endpoints out past view frustum bounds using directional vectors
            p1x = s_v1x + (d1x / mag1) * shadow_extension
            p1y = s_v1y + (d1y / mag1) * shadow_extension
            p2x = s_v2x + (d2x / mag2) * shadow_extension
            p2y = s_v2y + (d2y / mag2) * shadow_extension

            # Fill back in absolute solid darkness behind the geometry edge, re-occluding
            # anything the flashlight/proximity glow revealed through a wall
            pg.draw.polygon(darkness, (10, 10, 12, 255), [(s_v1x, s_v1y), (s_v2x, s_v2y), (p2x, p2y), (p1x, p1y)])

    # 4. Composite the darkness overlay onto the screen with a normal alpha blit
    #    (same technique as the fade-to-black transition below)
    surface.blit(darkness, (0, 0))

    # 3. HUD Layer
    player.draw_hud(current_level_index)

    if fade_alpha > 0:
        fade_surface = pg.Surface((1280, 720), pg.SRCALPHA)
        fade_surface.fill((0, 0, 0, fade_alpha))
        surface.blit(fade_surface, (0, 0))

gl.run()