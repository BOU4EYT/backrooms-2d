import pygame as pg
import glpg as gl
import random
import settings

PLAYER_SIZE = 40
MAX_STAT = 100
BASE_SPEED = 150.0  # Converted to pixels-per-second instead of per-frame
SPRINT_SPEED = 300.0
EXHAUSTION_SPEED = 75.0  # Exhaustion penalty speed (half of base)
EXHAUSTION_DURATION = 2.0  # How long exhaustion lasts in seconds
HOTBAR_SLOTS = 5
VIEW_RADIUS = 240
STAMINA_SPRINT_DRAIN = 42.0  # Scaled for delta-time
STAMINA_RECOVERY = 18.0
FLASHLIGHT_DEBOUNCE_TIME = 0.25  # Debounce tracked via real seconds instead of frame ticks
HAZARD_HEALTH_DAMAGE = 24.0
HAZARD_SANITY_DAMAGE = 12.0
SANITY_DRAIN_FLASHLIGHT_ON = 1.2
SANITY_DRAIN_FLASHLIGHT_OFF_BONUS = 4.8
DIRECTION_SMOOTHING = 0.1
DIRECTION_THRESHOLD = 0.5
SHIVER_SANITY_THRESHOLD = 30
SPRITE_SIZE = 64
SPRITE_ROW_UP = 8
SPRITE_ROW_LEFT = 9
SPRITE_ROW_DOWN = 10
SPRITE_ROW_RIGHT = 11
SPRITE_ANIM_FRAMES = 9
WALK_ANIM_INTERVAL = 0.15
SPRINT_ANIM_INTERVAL = 0.08
WALK_STEP_INTERVAL = 0.45
SPRINT_STEP_INTERVAL = 0.25
HUD_X = 20
HEALTH_Y = 20
STAMINA_Y = 40
SANITY_Y = 55
LEVEL_TEXT_Y = 75
HUD_WIDTH = 200
HEALTH_HEIGHT = 15
STAT_HEIGHT = 10
is_dead = False

class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.size = PLAYER_SIZE
        self.max_health, self.health = MAX_STAT, MAX_STAT
        self.max_stamina, self.stamina = MAX_STAT, MAX_STAT
        self.max_sanity, self.sanity = MAX_STAT, MAX_STAT

        self.base_speed, self.sprint_speed, self.current_speed = BASE_SPEED, SPRINT_SPEED, BASE_SPEED
        self.hotbar_slots = HOTBAR_SLOTS
        self.inventory = [None] * self.hotbar_slots
        self.selected_slot = 0
        self.view_radius = VIEW_RADIUS
        self.dir_x, self.dir_y = 0, 1
        self.smooth_dir_x, self.smooth_dir_y = 0.0, 1.0

        self.flashlight_on = True
        self.flashlight_debounce = 0.0

        self.sprite_w, self.sprite_h = SPRITE_SIZE, SPRITE_SIZE
        self.anim_frame = 0
        self.anim_timer = 0.0
        self.anim_speed = WALK_ANIM_INTERVAL
        self.is_moving = False
        self.on_exit = False

        self.footstep_timer = 0.0
        self.walk_step_interval = WALK_STEP_INTERVAL
        self.sprint_step_interval = SPRINT_STEP_INTERVAL
        self.was_sprinting = False
        self.exhaustion_timer = 0.0

    def handle_input(self, dt, walls_list, map_width, map_height):
        self.is_moving = False
        dx, dy = 0, 0
        is_moving_keys = gl.key("a") or gl.key("d") or gl.key("w") or gl.key("s")

        if gl.key("shift") and self.stamina > 0 and is_moving_keys:
            self.current_speed = self.sprint_speed
            self.stamina = max(0, self.stamina - STAMINA_SPRINT_DRAIN * dt)
            # If stamina just depleted, trigger exhaustion
            if self.stamina == 0:
                self.exhaustion_timer = EXHAUSTION_DURATION
        elif self.exhaustion_timer > 0:
            # Exhaustion penalty: reduced speed
            self.current_speed = EXHAUSTION_SPEED
            self.exhaustion_timer -= dt
        else:
            self.current_speed = self.base_speed
            # Only recover stamina when NOT actively sprinting and not exhausted
            self.stamina = min(self.max_stamina, self.stamina + STAMINA_RECOVERY * dt)

        if gl.key("a"): dx -= self.current_speed * dt; self.dir_x, self.dir_y = -1, 0; self.is_moving = True
        if gl.key("d"): dx += self.current_speed * dt; self.dir_x, self.dir_y = 1, 0; self.is_moving = True
        if gl.key("w"): dy -= self.current_speed * dt; self.dir_x, self.dir_y = 0, -1; self.is_moving = True
        if gl.key("s"): dy += self.current_speed * dt; self.dir_x, self.dir_y = 0, 1; self.is_moving = True

        if self.is_moving and "player_walk" in settings.SOUNDS:
            is_sprinting = self.current_speed > self.base_speed
            current_interval = self.sprint_step_interval if is_sprinting else self.walk_step_interval
            
            # Reset timer when switching between sprint/walk to sync sound immediately
            if is_sprinting != self.was_sprinting:
                self.footstep_timer = 0.0
            self.was_sprinting = is_sprinting
            
            self.footstep_timer += dt
            if self.footstep_timer >= current_interval:
                pg.mixer.Channel(1).play(settings.SOUNDS["player_walk"])
                self.footstep_timer = 0.0
        else:
            self.footstep_timer = 0.0
            self.was_sprinting = False

        if self.flashlight_debounce > 0: 
            self.flashlight_debounce -= dt
        if gl.key("f") and self.flashlight_debounce <= 0:
            self.flashlight_on = not self.flashlight_on
            self.flashlight_debounce = FLASHLIGHT_DEBOUNCE_TIME

        future_rect_x = (self.x + dx, self.y, self.size, self.size)
        if not self.check_wall_collisions(future_rect_x, walls_list):
            self.x = max(0, min(self.x + dx, map_width - self.size))

        future_rect_y = (self.x, self.y + dy, self.size, self.size)
        if not self.check_wall_collisions(future_rect_y, walls_list):
            self.y = max(0, min(self.y + dy, map_height - self.size))

        for i in range(self.hotbar_slots):
            if gl.key(str(i+1)): 
                self.selected_slot = i

    def check_wall_collisions(self, future_rect, walls_list):
        future = pg.Rect(future_rect)
        for wall in walls_list:
            if future.colliderect(pg.Rect(wall)):
                return True
        return False

    def check_environmental_interactions(self, dt, hazard_tiles, exit_tiles):
        player_rect = (self.x, self.y, self.size, self.size)

        for haz in hazard_tiles:
            if pg.Rect(player_rect).colliderect(pg.Rect(haz)):
                self.health = max(0, self.health - HAZARD_HEALTH_DAMAGE * dt)
                self.sanity = max(0, self.sanity - HAZARD_SANITY_DAMAGE * dt)
                if "hurt" in settings.SOUNDS and not pg.mixer.Channel(0).get_busy():
                    settings.SOUNDS["hurt"].play()
                if self.health <= 0:
                    self.die()
                break

        touching_exit = False
        for exit_t in exit_tiles:
            if pg.Rect(player_rect).colliderect(pg.Rect(exit_t)):
                touching_exit = True
                break

        if touching_exit and not self.on_exit:
            if "exit_door" in settings.SOUNDS: 
                settings.SOUNDS["exit_door"].play()
            self.on_exit = True
            return True

        if not touching_exit: 
            self.on_exit = False
        return False

    def die(self):
        if "death" in settings.SOUNDS:
            settings.SOUNDS["death"].play()
        self.health = 0
        self.stamina = 0
        self.sanity = 0

        if self.health <= 0:
            global is_dead
            is_dead = True

        if is_dead:
            from game_menu import death_screen
            death_screen()

    def update(self, dt, walls_list, hazard_tiles, exit_tiles, map_width, map_height):
        self.handle_input(dt, walls_list, map_width, map_height)
        hit_exit = self.check_environmental_interactions(dt, hazard_tiles, exit_tiles)

        drain_rate = SANITY_DRAIN_FLASHLIGHT_ON
        if not self.flashlight_on: 
            drain_rate += SANITY_DRAIN_FLASHLIGHT_OFF_BONUS
        self.sanity = max(0, self.sanity - drain_rate * dt)

        turn_speed = DIRECTION_SMOOTHING
        self.smooth_dir_x += (self.dir_x - self.smooth_dir_x) * turn_speed
        self.smooth_dir_y += (self.dir_y - self.smooth_dir_y) * turn_speed

        if self.is_moving:
            anim_speed = SPRINT_ANIM_INTERVAL if self.current_speed > self.base_speed else self.anim_speed
            self.anim_timer += dt
            if self.anim_timer >= anim_speed:
                self.anim_timer = 0
                self.anim_frame += 1
        else:
            self.anim_frame = 0

        return hit_exit

    def draw(self, cam_x, cam_y):
        shiver_x, shiver_y = 0, 0
        if self.sanity < SHIVER_SANITY_THRESHOLD:
            shiver_x = random.randint(-1, 1)
            shiver_y = random.randint(-1, 1)

        if "player_sheet" in settings.TEXTURES:
            row = SPRITE_ROW_DOWN
            if self.smooth_dir_y < -DIRECTION_THRESHOLD: 
                row = SPRITE_ROW_UP
            elif self.smooth_dir_x < -DIRECTION_THRESHOLD: 
                row = SPRITE_ROW_LEFT
            elif self.smooth_dir_x > DIRECTION_THRESHOLD: 
                row = SPRITE_ROW_RIGHT

            col = self.anim_frame % SPRITE_ANIM_FRAMES if self.is_moving else 0
            sheet_rect = pg.Rect(col * self.sprite_w, row * self.sprite_h, self.sprite_w, self.sprite_h)
            frame_surf = pg.Surface((self.sprite_w, self.sprite_h), pg.SRCALPHA)
            frame_surf.blit(settings.TEXTURES["player_sheet"], (0, 0), sheet_rect)
            scaled_player = pg.transform.scale(frame_surf, (self.size, self.size))
            gl.get_screen().blit(scaled_player, (self.x - cam_x + shiver_x, self.y - cam_y + shiver_y))
        else:
            gl.draw.rect(self.x - cam_x + shiver_x, self.y - cam_y + shiver_y, self.size, self.size, "green")

    def draw_hud(self, level_index):
        self.draw_meter(HUD_X, HEALTH_Y, HUD_WIDTH, HEALTH_HEIGHT, self.health, self.max_health, (60, 10, 10), (200, 30, 30))
        self.draw_meter(HUD_X, STAMINA_Y, HUD_WIDTH, STAT_HEIGHT, self.stamina, self.max_stamina, (10, 10, 60), (40, 160, 220))
        self.draw_meter(HUD_X, SANITY_Y, HUD_WIDTH, STAT_HEIGHT, self.sanity, self.max_sanity, (40, 10, 40), (160, 40, 180))

        lvl_text = settings.ui_font.render(f"LEVEL: {level_index}", True, "white")
        gl.get_screen().blit(lvl_text, (HUD_X, LEVEL_TEXT_Y))

    def draw_meter(self, x, y, width, height, value, maximum, background, foreground):
        gl.draw.rect(x, y, width, height, background)
        fill_width = int(width * (value / maximum))
        if fill_width > 0:
            gl.draw.rect(x, y, fill_width, height, foreground)