import math
import random

import pygame as pg
import glpg as gl

import generator
import settings
from player import Player

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
MAX_FADE_ALPHA = 255
FADE_SPEED = 8
DARKNESS_COLOR = (10, 10, 12, MAX_FADE_ALPHA)
FLASHLIGHT_FLICKER_SANITY_THRESHOLD = 40
FLASHLIGHT_CONE_WIDTH = 220
FLASHLIGHT_SOFTNESS_STEPS = 48
FLASHLIGHT_JITTER_LENGTH = 3
FLASHLIGHT_JITTER_WIDTH = 2
FLASHLIGHT_FALLOFF_POWER = 0.8
FLASHLIGHT_ALPHA_MULT = 35
PLAYER_AURA_MULTIPLIER = 1.5
PLAYER_AURA_STEP = 4
SHADOW_EXTENSION = 2000.0
SHADOW_CULL_PADDING = 100
AMBIENT_LIGHT_PEAK_ALPHA = 220
AMBIENT_LIGHT_STEP = 6
AMBIENT_LIGHT_REVEAL_MARGIN = 150

cam_x, cam_y = 0, 0
current_level_index = 0
fade_alpha = 0
fade_state = "idle"
pending_level_id = None


def start_level_transition(next_level_id):
    """Begin a fade-to-black transition before generating the next level."""
    global fade_state, pending_level_id
    fade_state = "fading_out"
    pending_level_id = next_level_id


# Initialize the first level before creating the player so the spawn is valid.
generator.generate_backrooms_level(0)
player = Player(generator.spawn_x, generator.spawn_y)


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


@gl.on_update
def update(dt):
    global cam_x, cam_y, current_level_index, fade_alpha, fade_state

    if gl.key("escape"):
        gl.quit()

    hit_exit = player.update(
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
    surface = pg.display.get_surface()

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

    for haz in generator.hazard_tiles:
        if "hazard" in settings.TEXTURES:
            surface.blit(settings.TEXTURES["hazard"], (haz[0] - cam_x, haz[1] - cam_y))
        else:
            gl.draw.rect(haz[0] - cam_x, haz[1] - cam_y, haz[2], haz[3], settings.TILE_COLORS["hazard"])

    for ex in generator.exit_tiles:
        if "exit" in settings.TEXTURES:
            surface.blit(settings.TEXTURES["exit"], (ex[0] - cam_x, ex[1] - cam_y))
        else:
            gl.draw.rect(ex[0] - cam_x, ex[1] - cam_y, ex[2], ex[3], settings.TILE_COLORS["exit"])

    for wall in generator.walls:
        if "wall" in settings.TEXTURES:
            surface.blit(settings.TEXTURES["wall"], (wall[0] - cam_x, wall[1] - cam_y))
        else:
            gl.draw.rect(wall[0] - cam_x, wall[1] - cam_y, wall[2], wall[3], room_tint_for(wall[0], wall[1], "wall"))

    player.draw(cam_x, cam_y)
    draw_fog_of_war(surface)
    player.draw_hud(current_level_index)

    if fade_alpha > 0:
        fade_surface = pg.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pg.SRCALPHA)
        fade_surface.fill((0, 0, 0, fade_alpha))
        surface.blit(fade_surface, (0, 0))


def draw_fog_of_war(surface):
    """Render player visibility, flashlight falloff, and wall-cast shadows."""
    darkness = pg.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pg.SRCALPHA)
    darkness.fill(DARKNESS_COLOR)

    p_center_x = player.x + player.size / 2
    p_center_y = player.y + player.size / 2
    scr_px = int(p_center_x - cam_x)
    scr_py = int(p_center_y - cam_y)

    visibility = pg.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pg.SRCALPHA)
    visibility.fill((0, 0, 0, 0))

    player_base_rad = int(player.size * PLAYER_AURA_MULTIPLIER)

    def merge_source(draw_fn):
        """Draw one light source on its own scratch layer, then merge it into `visibility`
        by taking the MAX alpha per-pixel rather than normal alpha compositing. Normal
        compositing of two overlapping partial-alpha shapes can produce a result *darker*
        than either shape alone -- that's what caused the seam/bite where lights met.
        MAX blending means overlapping lights always take the brighter contribution."""
        scratch = pg.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pg.SRCALPHA)
        scratch.fill((0, 0, 0, 0))
        draw_fn(scratch)
        visibility.blit(scratch, (0, 0), special_flags=pg.BLEND_RGBA_MAX)

    if player.flashlight_on and (player.smooth_dir_x != 0 or player.smooth_dir_y != 0):
        merge_source(lambda scratch: draw_flashlight_cone(scratch, scr_px, scr_py, player_base_rad))

    merge_source(lambda scratch: draw_player_aura(scratch, scr_px, scr_py, player_base_rad))

    for light in generator.room_lights:
        if not light["lit"]:
            continue
        scr_lx = int(light["x"] - cam_x)
        scr_ly = int(light["y"] - cam_y)
        rad = light["radius"]
        if scr_lx + rad < 0 or scr_lx - rad > SCREEN_WIDTH or scr_ly + rad < 0 or scr_ly - rad > SCREEN_HEIGHT:
            continue
        # The camera window is much larger than the player's actual sight range, so a lit
        # room could sit fully inside the camera frame while still being far from the player
        # -- visible on screen despite never having been explored. Gate by proximity to the
        # player as well so distant rooms stay dark until you're actually near them.
        dist_to_player = math.hypot(scr_lx - scr_px, scr_ly - scr_py)
        if dist_to_player > player.view_radius + rad + AMBIENT_LIGHT_REVEAL_MARGIN:
            continue
        merge_source(lambda scratch, lx=scr_lx, ly=scr_ly, r=rad: draw_single_ambient_light(scratch, lx, ly, r))

    darkness.blit(visibility, (0, 0), special_flags=pg.BLEND_RGBA_SUB)
    draw_wall_shadows(darkness, p_center_x, p_center_y)
    surface.blit(darkness, (0, 0))


def draw_player_aura(visibility, scr_px, scr_py, player_base_rad):
    for radius in range(player_base_rad, 0, -PLAYER_AURA_STEP):
        reveal_ratio = radius / player_base_rad
        reveal_alpha = int(MAX_FADE_ALPHA * (1.0 - reveal_ratio))
        pg.draw.circle(visibility, (255, 255, 255, reveal_alpha), (scr_px, scr_py), max(1, radius))


def draw_single_ambient_light(visibility, scr_lx, scr_ly, rad):
    for radius in range(rad, 0, -AMBIENT_LIGHT_STEP):
        reveal_ratio = radius / rad
        reveal_alpha = int(AMBIENT_LIGHT_PEAK_ALPHA * (1.0 - reveal_ratio))
        pg.draw.circle(visibility, (255, 255, 255, reveal_alpha), (scr_lx, scr_ly), max(1, radius))


def draw_flashlight_cone(visibility, scr_px, scr_py, aura_radius):
    """Paint a soft flashlight cone into the visibility mask."""
    forward_x, forward_y = player.smooth_dir_x, player.smooth_dir_y
    flicker_prob = 0.15 if player.sanity < FLASHLIGHT_FLICKER_SANITY_THRESHOLD else 0.0
    if random.random() <= flicker_prob:
        return

    cone_length = player.view_radius * (0.6 + 0.4 * (player.sanity / player.max_sanity))
    perp_x, perp_y = -forward_y, forward_x
    mag = math.hypot(perp_x, perp_y) or 1
    perp_x /= mag
    perp_y /= mag

    # Roll jitter once per frame (not per softness step) so every layer of the cone shifts
    # together as one flickering beam, instead of each layer jittering independently and
    # creating a corrugated/ribbed edge where the misaligned layers stack.
    frame_length_jitter = random.randint(-FLASHLIGHT_JITTER_LENGTH, FLASHLIGHT_JITTER_LENGTH)
    frame_width_jitter = random.randint(-FLASHLIGHT_JITTER_WIDTH, FLASHLIGHT_JITTER_WIDTH)

    for step in reversed(range(1, FLASHLIGHT_SOFTNESS_STEPS + 1)):
        ratio = step / FLASHLIGHT_SOFTNESS_STEPS
        jitter_scale = ratio  # keep jitter subtle near the player, fuller at the tip
        current_length = cone_length * ratio + frame_length_jitter * jitter_scale
        half_width = (FLASHLIGHT_CONE_WIDTH / 2) * ratio + frame_width_jitter * jitter_scale
        # Base width tracks the aura circle's radius (not a fraction of the tip width) so the
        # cone flares out of the aura smoothly instead of pinching to a point at the seam.
        base_half_width = max(half_width * 0.15, aura_radius * ratio)
        # Eased falloff (steeper near the tip, gentler near the player) avoids visible banding.
        reveal_alpha = int(MAX_FADE_ALPHA * (1.0 - ratio) ** FLASHLIGHT_FALLOFF_POWER / FLASHLIGHT_SOFTNESS_STEPS * FLASHLIGHT_ALPHA_MULT)
        reveal_alpha = min(MAX_FADE_ALPHA, reveal_alpha)

        tip = (scr_px, scr_py)
        base_left = (int(scr_px + perp_x * base_half_width), int(scr_py + perp_y * base_half_width))
        base_right = (int(scr_px - perp_x * base_half_width), int(scr_py - perp_y * base_half_width))
        end_left = (int(scr_px + forward_x * current_length + perp_x * half_width), int(scr_py + forward_y * current_length + perp_y * half_width))
        end_right = (int(scr_px + forward_x * current_length - perp_x * half_width), int(scr_py + forward_y * current_length - perp_y * half_width))
        pg.draw.polygon(visibility, (255, 255, 255, reveal_alpha), [tip, base_left, end_left, end_right, base_right])


def draw_wall_shadows(darkness, p_center_x, p_center_y):
    """Re-occlude light that would otherwise leak through merged wall edges."""
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
        # Push the shadow's near edge one tile further along the light direction so it starts
        # at the *back* of the wall, not its lit front face -- otherwise the wall's own body
        # gets re-darkened the instant light hits it.
        near_x1 = s_x1 + (d1x / mag1) * settings.TILE_SIZE
        near_y1 = s_y1 + (d1y / mag1) * settings.TILE_SIZE
        near_x2 = s_x2 + (d2x / mag2) * settings.TILE_SIZE
        near_y2 = s_y2 + (d2y / mag2) * settings.TILE_SIZE
        p1x = s_x1 + (d1x / mag1) * SHADOW_EXTENSION
        p1y = s_y1 + (d1y / mag1) * SHADOW_EXTENSION
        p2x = s_x2 + (d2x / mag2) * SHADOW_EXTENSION
        p2y = s_y2 + (d2y / mag2) * SHADOW_EXTENSION
        pg.draw.polygon(darkness, DARKNESS_COLOR, [(near_x1, near_y1), (near_x2, near_y2), (p2x, p2y), (p1x, p1y)])


gl.run()