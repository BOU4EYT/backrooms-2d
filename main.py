import math
import random

import pygame as pg
import glpg as gl

import generator
import settings
from player import Player, is_dead

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
MAX_FADE_ALPHA = 255
FADE_SPEED = 8
DARKNESS_COLOR = (255, 255, 255)  # Removed alpha channel from base color to avoid transparency leaks
FLASHLIGHT_FLICKER_SANITY_THRESHOLD = 40
FLASHLIGHT_CONE_WIDTH = 220
FLASHLIGHT_SOFTNESS_STEPS = 48
FLASHLIGHT_JITTER_LENGTH = 3
FLASHLIGHT_JITTER_WIDTH = 2
FLASHLIGHT_FALLOFF_POWER = 0.8
FLASHLIGHT_ALPHA_MULT = 35
FLASHLIGHT_CONE_LENGTH_SCALE = 0.6
FLASHLIGHT_CONE_LENGTH_VARIANCE = 0.4
FLASHLIGHT_BASE_WIDTH_SCALE = 0.15
PLAYER_AURA_MULTIPLIER = 1.5
PLAYER_AURA_STEP = 4
SHADOW_EXTENSION = 1500
SHADOW_CULL_PADDING = 100
AMBIENT_LIGHT_PEAK_ALPHA = 220
AMBIENT_LIGHT_STEP = 6
AMBIENT_LIGHT_REVEAL_MARGIN = 150
WALL_SHADOW_BRIGHTNESS_FLOOR = 0.15
WALL_SHADOW_DARKENING_ALPHA = 150
WALL_TINT_BRIGHTNESS_SCALE = 1
WALL_TINT_MIN_CHANNEL = 1
WALL_ADJACENT_OFFSETS = ((1, 0), (-1, 0), (0, 1), (0, -1))
SHADOW_SAMPLING = 1

cam_x, cam_y = 0, 0
current_level_index = 0
fade_alpha = 0
fade_state = "idle"
pending_level_id = None
HAZARD_VARIANT_CACHE = {}


def start_level_transition(next_level_id):
    """Begin a fade-to-black transition before generating the next level."""
    global fade_state, pending_level_id
    fade_state = "fading_out"
    pending_level_id = next_level_id


# Initialize the first level before creating the player so the spawn is valid.
generator.generate_backrooms_level(0)
player = Player(generator.spawn_x, generator.spawn_y)


def start_game():
    """Initialize the game state before the main loop begins."""
    global current_level_index, fade_alpha, fade_state, pending_level_id, player

    if not pg.mixer.get_init():
        pg.mixer.init()

    current_level_index = 0
    fade_alpha = 0
    fade_state = "idle"
    pending_level_id = None
    settings.start_ambient_buzz()
    generator.generate_backrooms_level(0)
    player = Player(generator.spawn_x, generator.spawn_y)

    # The game loop itself only starts here, once state (including ambient
    # audio) is fully set up. Previously gl.run() lived at module scope,
    # meaning the first Start Game click ran the loop using the module's
    # initial pre-start_game() state (no ambient audio), and only after
    # quitting did start_game() actually execute and reset things - with
    # no loop left to render/update (frozen window), and no way to run()
    # again on later Start Game clicks since "main" was already imported.
    gl.run()


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def hazard_connectivity_mask(tile_x, tile_y, hazard_positions):
    """Return a bitmask describing which neighboring hazard tiles are connected."""
    mask = 0
    directions = ((0, -1), (1, 0), (0, 1), (-1, 0), (1, -1), (1, 1), (-1, 1), (-1, -1))
    for bit, (dx, dy) in enumerate(directions):
        if (tile_x + dx, tile_y + dy) in hazard_positions:
            mask |= 1 << bit
    return mask


def _hazard_cell_name(mask):
    """Map a 4-directional neighbor mask (N=1, E=2, S=4, W=8) onto one of the
    10 atlas cells, using the standard 9-slice-plus-isolated scheme: corners
    win when two adjacent sides are both open, a single open side gives an
    edge piece, no open sides gives the full interior, and no neighbors at
    all gives the standalone variant tile."""
    n = bool(mask & 0b0001)
    e = bool(mask & 0b0010)
    s = bool(mask & 0b0100)
    w = bool(mask & 0b1000)

    if not (n or e or s or w):
        return "VR"
    if not n and not w:
        return "TL"
    if not n and not e:
        return "TR"
    if not s and not w:
        return "BL"
    if not s and not e:
        return "BR"
    if not n:
        return "TC"
    if not s:
        return "BC"
    if not w:
        return "CL"
    if not e:
        return "CR"
    return "CC"


def build_hazard_tile_surface(tile_x, tile_y, hazard_positions):
    """Look up the correctly-connected autotile cell for this hazard tile from
    the sliced atlas (settings.TEXTURES['hazard_tiles']), based on which of
    its 4 orthogonal neighbors are also hazard tiles."""
    mask = hazard_connectivity_mask(tile_x, tile_y, hazard_positions)
    cache_key = (mask, settings.TILE_SIZE)
    if cache_key in HAZARD_VARIANT_CACHE:
        return HAZARD_VARIANT_CACHE[cache_key]

    hazard_tiles = settings.TEXTURES.get("hazard_tiles")
    if not hazard_tiles:
        return None

    cell_name = _hazard_cell_name(mask)
    tile_surface = hazard_tiles.get(cell_name, hazard_tiles.get("VR"))
    HAZARD_VARIANT_CACHE[cache_key] = tile_surface
    return tile_surface


def apply_shadow_blur(surface, blur_radius=1):
    """Apply a simple blur to soften shadow edges by downscaling and upscaling."""
    w, h = surface.get_size()
    scale_factor = blur_radius + SHADOW_SAMPLING
    small_w = max(1, w // scale_factor)
    small_h = max(1, h // scale_factor)
    small = pg.transform.smoothscale(surface, (small_w, small_h))
    return pg.transform.scale(small, (w, h))


@gl.on_update
def update(dt):
    global cam_x, cam_y, current_level_index, fade_alpha, fade_state

    if gl.key("escape"):
        gl.quit()

    # FIX: Added 'dt' back as the first argument here
    hit_exit = player.update(
        dt,
        generator.walls,
        generator.hazard_tiles,
        generator.exit_tiles,
        generator.map_width,
        generator.map_height,
    )
    generator.update_room_lights(dt)
    
    if hit_exit and fade_state == "idle":
        current_level_index += 1
        start_level_transition(current_level_index)

    if fade_state == "fading_out":
        fade_alpha = min(MAX_FADE_ALPHA, fade_alpha + FADE_SPEED)
        if fade_alpha >= MAX_FADE_ALPHA:
            generator.generate_backrooms_level(pending_level_id, player)
            fade_state = "fading_in"
    elif fade_state == "fading_in":
        fade_alpha = max(0, fade_alpha - FADE_SPEED)
        if fade_alpha <= 0:
            fade_state = "idle"

    cam_x = clamp((player.x + player.size / 2) - SCREEN_WIDTH / 2, 0, generator.map_width - SCREEN_WIDTH)
    cam_y = clamp((player.y + player.size / 2) - SCREEN_HEIGHT / 2, 0, generator.map_height - SCREEN_HEIGHT)


@gl.on_draw
def draw():
    # Use glpg's own screen reference instead of pg.display.get_surface() —
    # on some platforms pygame's global "current display surface" can
    # momentarily desync from the surface glpg is actually filling/flipping
    # each frame, which was returning None here.
    surface = gl.get_screen()

    def room_tint_for(px, py, kind):
        tx, ty = int(px // settings.TILE_SIZE), int(py // settings.TILE_SIZE)
        if 0 <= ty < len(generator.room_type_grid) and 0 <= tx < len(generator.room_type_grid[0]):
            rtype = generator.room_type_grid[ty][tx]
            if rtype and rtype in settings.ROOM_TYPES:
                return settings.ROOM_TYPES[rtype][f"{kind}_tint"]
        return settings.TILE_COLORS[kind]

    for floor in generator.floors:
        if "floor" in settings.TEXTURES:
            surface.blit(settings.TEXTURES["floor"], (floor[0] - cam_x, floor[1] - cam_y))
        else:
            gl.draw.rect(floor[0] - cam_x, floor[1] - cam_y, floor[2], floor[3], room_tint_for(floor[0], floor[1], "floor"))

    hazard_positions = {(int(haz[0] // settings.TILE_SIZE), int(haz[1] // settings.TILE_SIZE)) for haz in generator.hazard_tiles}
    for haz in generator.hazard_tiles:
        tile_x = int(haz[0] // settings.TILE_SIZE)
        tile_y = int(haz[1] // settings.TILE_SIZE)
        if "hazard" in settings.TEXTURES:
            hazard_surface = build_hazard_tile_surface(tile_x, tile_y, hazard_positions)
            if hazard_surface is not None:
                surface.blit(hazard_surface, (haz[0] - cam_x, haz[1] - cam_y))
            else:
                gl.draw.rect(haz[0] - cam_x, haz[1] - cam_y, haz[2], haz[3], settings.TILE_COLORS["hazard"])
        else:
            gl.draw.rect(haz[0] - cam_x, haz[1] - cam_y, haz[2], haz[3], settings.TILE_COLORS["hazard"])

    for ex in generator.exit_tiles:
        if "exit" in settings.TEXTURES:
            surface.blit(settings.TEXTURES["exit"], (ex[0] - cam_x, ex[1] - cam_y))
        else:
            gl.draw.rect(ex[0] - cam_x, ex[1] - cam_y, ex[2], ex[3], settings.TILE_COLORS["exit"])

    player.draw(cam_x, cam_y)
    light_map = draw_fog_of_war(surface)

    # Draw exposed wall tiles after the fog pass, using the light map to soften shadows
    # instead of letting them flatten walls into pure black.
    wall_positions = {(int(wall[0] // settings.TILE_SIZE), int(wall[1] // settings.TILE_SIZE)) for wall in generator.walls}
    for wall in generator.walls:
        tx, ty = int(wall[0] // settings.TILE_SIZE), int(wall[1] // settings.TILE_SIZE)
        is_exposed = False
        for dx, dy in WALL_ADJACENT_OFFSETS:
            if (tx + dx, ty + dy) not in wall_positions:
                is_exposed = True
                break
        if not is_exposed:
            continue

        wall_x = wall[0] - cam_x
        wall_y = wall[1] - cam_y
        
        # Check if this wall is on the perimeter of the wall cluster
        edge_count = 0
        for dx, dy in WALL_ADJACENT_OFFSETS:
            if (tx + dx, ty + dy) not in wall_positions:
                edge_count += 1
        
        # Sample multiple points on the wall to avoid bright edge artifacts
        sample_points = [
            (int(wall_x + wall[2] / 3), int(wall_y + wall[3] / 3)),
            (int(wall_x + 2 * wall[2] / 3), int(wall_y + wall[3] / 3)),
            (int(wall_x + wall[2] / 3), int(wall_y + 2 * wall[3] / 3)),
            (int(wall_x + 2 * wall[2] / 3), int(wall_y + 2 * wall[3] / 3)),
            (int(wall_x + wall[2] / 2), int(wall_y + wall[3] / 2)),
        ]
        brightness = 1.0
        min_brightness = 1.0
        for sample_x, sample_y in sample_points:
            # Clamp into the screen instead of discarding out-of-bounds samples.
            # Previously, edge-row/column wall tiles could have every sample
            # point land off-screen, leaving min_brightness stuck at its 1.0
            # default and rendering that tile at full, undarkened brightness -
            # the bright streaks seen along screen edges.
            clamped_x = clamp(sample_x, 0, SCREEN_WIDTH - 1)
            clamped_y = clamp(sample_y, 0, SCREEN_HEIGHT - 1)
            sample_brightness = light_map.get_at((clamped_x, clamped_y))[0] / 255.0
            min_brightness = min(min_brightness, sample_brightness)
        
        # Apply extra darkening for edge-exposed walls
        if edge_count > 0:
            min_brightness *= 0.85
        
        brightness = max(WALL_SHADOW_BRIGHTNESS_FLOOR, min_brightness)

        if "wall" in settings.TEXTURES:
            wall_texture = settings.TEXTURES["wall"].copy()
            overlay = pg.Surface(wall_texture.get_size(), pg.SRCALPHA)
            overlay.fill((0, 0, 0, int((1.0 - brightness) * WALL_SHADOW_DARKENING_ALPHA)))
            wall_texture.blit(overlay, (0, 0))
            surface.blit(wall_texture, (wall_x, wall_y))
        else:
            base_color = room_tint_for(wall[0], wall[1], "wall")
            tint = tuple(max(WALL_TINT_MIN_CHANNEL, int(channel * brightness * WALL_TINT_BRIGHTNESS_SCALE)) for channel in base_color)
            gl.draw.rect(wall_x, wall_y, wall[2], wall[3], tint)

    player.draw_hud(current_level_index)

    if fade_alpha > 0:
        fade_surface = pg.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pg.SRCALPHA)
        fade_surface.fill((0, 0, 0, fade_alpha))
        surface.blit(fade_surface, (0, 0))


def draw_fog_of_war(surface):
    """Render player visibility, flashlight falloff, and wall-cast shadows by multiplying
    the rendered scene against a lightmap. Multiplying (rather than subtracting a flat
    darkness amount) keeps each color channel dimming proportionally, so textures keep
    their color balance instead of the low channels (e.g. blue) clipping to 0 first."""
    p_center_x = player.x + player.size / 2
    p_center_y = player.y + player.size / 2
    scr_px = int(p_center_x - cam_x)
    scr_py = int(p_center_y - cam_y)

    # Light map layer. This tracks where light is allowed to shine.
    light_map = pg.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    light_map.fill((0, 0, 0))  # Start completely unlit

    player_base_rad = int(player.size * PLAYER_AURA_MULTIPLIER)

    def merge_source(draw_fn):
        """Draw a light source to a temp surface and maximize it onto the light_map."""
        scratch = pg.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        scratch.fill((0, 0, 0))
        draw_fn(scratch)
        light_map.blit(scratch, (0, 0), special_flags=pg.BLEND_RGB_MAX)

    # Add the Flashlight Beam
    if player.flashlight_on and (player.smooth_dir_x != 0 or player.smooth_dir_y != 0):
        merge_source(lambda scratch: draw_flashlight_cone(scratch, scr_px, scr_py, player_base_rad))

    # Add the Player's personal small light aura
    merge_source(lambda scratch: draw_player_aura(scratch, scr_px, scr_py, player_base_rad))

    # Add any active Ambient Room Lights
    for light in generator.room_lights:
        if not light["lit"]:
            continue
        scr_lx = int(light["x"] - cam_x)
        scr_ly = int(light["y"] - cam_y)
        rad = light["radius"]
        if scr_lx + rad < 0 or scr_lx - rad > SCREEN_WIDTH or scr_ly + rad < 0 or scr_ly - rad > SCREEN_HEIGHT:
            continue

        dist_to_player = math.hypot(scr_lx - scr_px, scr_ly - scr_py)
        if dist_to_player > player.view_radius + rad + AMBIENT_LIGHT_REVEAL_MARGIN:
            continue
        merge_source(lambda scratch, lx=scr_lx, ly=scr_ly, r=rad: draw_single_ambient_light(scratch, lx, ly, r))

    # Cast shadows directly onto the light map by drawing solid black geometry.
    draw_wall_shadows(light_map, p_center_x, p_center_y)
    
    # Blur the light map to soften shadow edges
    light_map = apply_shadow_blur(light_map, blur_radius=2)

    # Multiply the scene by the light map: lit areas (light_val near 255) stay near their
    # original color, unlit areas (light_val near 0) go black, and everything in between
    # dims proportionally across channels instead of clipping.
    surface.blit(light_map, (0, 0), special_flags=pg.BLEND_RGB_MULT)
    return light_map


def draw_player_aura(light_surface, scr_px, scr_py, player_base_rad):
    for radius in range(player_base_rad, 0, -PLAYER_AURA_STEP):
        reveal_ratio = radius / player_base_rad
        val = int(255 * (1.0 - reveal_ratio))
        pg.draw.circle(light_surface, (val, val, val), (scr_px, scr_py), max(1, radius))


def draw_single_ambient_light(light_surface, scr_lx, scr_ly, rad):
    for radius in range(rad, 0, -AMBIENT_LIGHT_STEP):
        reveal_ratio = radius / rad
        val = int(AMBIENT_LIGHT_PEAK_ALPHA * (1.0 - reveal_ratio))
        pg.draw.circle(light_surface, (val, val, val), (scr_lx, scr_ly), max(1, radius))


def draw_flashlight_cone(light_surface, scr_px, scr_py, aura_radius):
    """Paint a soft flashlight cone into the light map."""
    forward_x, forward_y = player.smooth_dir_x, player.smooth_dir_y
    flicker_prob = 0.15 if player.sanity < FLASHLIGHT_FLICKER_SANITY_THRESHOLD else 0.0
    if random.random() <= flicker_prob:
        return

    cone_length = player.view_radius * (
        FLASHLIGHT_CONE_LENGTH_SCALE + FLASHLIGHT_CONE_LENGTH_VARIANCE * (player.sanity / player.max_sanity)
    )
    perp_x, perp_y = -forward_y, forward_x
    mag = math.hypot(perp_x, perp_y) or 1
    perp_x /= mag
    perp_y /= mag

    frame_length_jitter = random.randint(-FLASHLIGHT_JITTER_LENGTH, FLASHLIGHT_JITTER_LENGTH)
    frame_width_jitter = random.randint(-FLASHLIGHT_JITTER_WIDTH, FLASHLIGHT_JITTER_WIDTH)

    # Loop from the largest outer cone down to the smallest inner core, 
    # painting increasingly brighter solid values toward the center.
    softness_steps = int(FLASHLIGHT_SOFTNESS_STEPS)
    for step in reversed(range(1, softness_steps + 1)):
        ratio = step / softness_steps
        jitter_scale = ratio
        current_length = cone_length * ratio + frame_length_jitter * jitter_scale
        half_width = (FLASHLIGHT_CONE_WIDTH / 2) * ratio + frame_width_jitter * jitter_scale
        base_half_width = max(half_width * FLASHLIGHT_BASE_WIDTH_SCALE, aura_radius * ratio)
        
        # FIX: Removed the layer division so intensity scales cleanly up to 255
        reveal_val = int(255 * (1.0 - ratio) ** FLASHLIGHT_FALLOFF_POWER)
        reveal_val = clamp(reveal_val, 0, 255)

        tip = (scr_px, scr_py)
        base_left = (int(scr_px + perp_x * base_half_width), int(scr_py + perp_y * base_half_width))
        base_right = (int(scr_px - perp_x * base_half_width), int(scr_py - perp_y * base_half_width))
        end_left = (int(scr_px + forward_x * current_length + perp_x * half_width), int(scr_py + forward_y * current_length + perp_y * half_width))
        end_right = (int(scr_px + forward_x * current_length - perp_x * half_width), int(scr_py + forward_y * current_length - perp_y * half_width))
        
        pg.draw.polygon(light_surface, (reveal_val, reveal_val, reveal_val), [tip, base_left, end_left, end_right, base_right])


def draw_wall_shadows(light_surface, p_center_x, p_center_y):
    """Carve shadow geometry out of the light map by drawing solid black polygons that extend
    outward from each wall face, sealing corners so light can't leak between segments."""
    for x1, y1, x2, y2 in generator.wall_segments:
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        if math.hypot(mid_x - p_center_x, mid_y - p_center_y) > player.view_radius + SHADOW_CULL_PADDING:
            continue

        s_x1, s_y1 = x1 - cam_x, y1 - cam_y
        s_x2, s_y2 = x2 - cam_x, y2 - cam_y
        d1x, d1y = x1 - p_center_x, y1 - p_center_y
        d2x, d2y = x2 - p_center_x, y2 - p_center_y
        mag1 = math.hypot(d1x, d1y) or 1
        mag2 = math.hypot(d2x, d2y) or 1

        # Closed the wall geometry gap. Shadow bounds now anchor perfectly along 
        # tile segment faces to seal corners completely.
        p1x = s_x1 + (d1x / mag1) * SHADOW_EXTENSION
        p1y = s_y1 + (d1y / mag1) * SHADOW_EXTENSION
        p2x = s_x2 + (d2x / mag2) * SHADOW_EXTENSION
        p2y = s_y2 + (d2y / mag2) * SHADOW_EXTENSION
        
        # Draw pure black onto the light map layer to completely negate light in shadow zones
        pg.draw.polygon(light_surface, (0, 0, 0), [(s_x1, s_y1), (s_x2, s_y2), (p2x, p2y), (p1x, p1y)])