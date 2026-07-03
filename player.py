import pygame as pg
import glpg as gl
import random
import math
import settings

class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.size = 40
        self.max_health, self.health = 100, 100
        self.max_stamina, self.stamina = 100, 100
        self.max_sanity, self.sanity = 100, 100
        
        self.base_speed, self.sprint_speed, self.current_speed = 2.5, 5.0, 2.5
        self.hotbar_slots = 5
        self.inventory = [None] * self.hotbar_slots
        self.selected_slot = 0
        self.view_radius = 240  # Slightly increased radius to enjoy the shadow depth!
        self.dir_x, self.dir_y = 0, 1
        self.smooth_dir_x, self.smooth_dir_y = 0.0, 1.0
        
        self.flashlight_on = True
        self.flashlight_debounce = 0
        
        self.sprite_w, self.sprite_h = 64, 64  
        self.anim_frame = 0
        self.anim_timer = 0.0
        self.anim_speed = 0.15 
        self.is_moving = False
        self.on_exit = False

        self.footstep_timer = 0.0
        self.walk_step_interval = 0.45   
        self.sprint_step_interval = 0.25 

    def handle_input(self, walls_list, map_width, map_height):
        self.is_moving = False
        dx, dy = 0, 0
        is_moving_keys = gl.key("a") or gl.key("d") or gl.key("w") or gl.key("s")
        
        if gl.key("shift") and self.stamina > 0 and is_moving_keys:
            self.current_speed = self.sprint_speed
            self.stamina = max(0, self.stamina - 0.7)
        else:
            self.current_speed = self.base_speed
            if not gl.key("shift") or not is_moving_keys:
                self.stamina = min(self.max_stamina, self.stamina + 0.3)

        if gl.key("a"): dx -= self.current_speed; self.dir_x, self.dir_y = -1, 0; self.is_moving = True
        if gl.key("d"): dx += self.current_speed; self.dir_x, self.dir_y = 1, 0; self.is_moving = True
        if gl.key("w"): dy -= self.current_speed; self.dir_x, self.dir_y = 0, -1; self.is_moving = True
        if gl.key("s"): dy += self.current_speed; self.dir_x, self.dir_y = 0, 1; self.is_moving = True

        if self.is_moving and "player_walk" in settings.SOUNDS:
            current_interval = self.sprint_step_interval if self.current_speed > self.base_speed else self.walk_step_interval
            self.footstep_timer += 0.016
            if self.footstep_timer >= current_interval:
                pg.mixer.Channel(1).play(settings.SOUNDS["player_walk"])
                self.footstep_timer = 0.0
        else:
            self.footstep_timer = self.walk_step_interval

        if self.flashlight_debounce > 0: self.flashlight_debounce -= 1
        if gl.key("f") and self.flashlight_debounce == 0:
            self.flashlight_on = not self.flashlight_on
            self.flashlight_debounce = 15 

        future_rect_x = (self.x + dx, self.y, self.size, self.size)
        if not self.check_wall_collisions(future_rect_x, walls_list):
            self.x = max(0, min(self.x + dx, map_width - self.size))

        future_rect_y = (self.x, self.y + dy, self.size, self.size)
        if not self.check_wall_collisions(future_rect_y, walls_list):
            self.y = max(0, min(self.y + dy, map_height - self.size))

        for i in range(5):
            if gl.key(str(i+1)): self.selected_slot = i

    def check_wall_collisions(self, future_rect, walls_list):
        for wall in walls_list:
            x1, y1, w1, h1 = future_rect
            x2, y2, w2, h2 = wall
            if not (x1 + w1 <= x2 or x1 >= x2 + w2 or y1 + h1 <= y2 or y1 >= y2 + h2): return True
        return False

    def check_environmental_interactions(self, hazard_tiles, exit_tiles):
        player_rect = (self.x, self.y, self.size, self.size)
        
        for haz in hazard_tiles:
            x1, y1, w1, h1 = player_rect
            x2, y2, w2, h2 = haz
            if not (x1 + w1 <= x2 or x1 >= x2 + w2 or y1 + h1 <= y2 or y1 >= y2 + h2):
                self.health = max(0, self.health - 0.4)
                self.sanity = max(0, self.sanity - 0.2) 
                if "hurt" in settings.SOUNDS and not pg.mixer.Channel(0).get_busy():
                    settings.SOUNDS["hurt"].play()
                break

        touching_exit = False
        for exit_t in exit_tiles:
            x1, y1, w1, h1 = player_rect
            x2, y2, w2, h2 = exit_t
            if not (x1 + w1 <= x2 or x1 >= x2 + w2 or y1 + h1 <= y2 or y1 >= y2 + h2):
                touching_exit = True
                break

        if touching_exit and not self.on_exit:
            if "exit_door" in settings.SOUNDS: settings.SOUNDS["exit_door"].play()
            self.on_exit = True
            return True  

        if not touching_exit: self.on_exit = False
        return False

    def update(self, walls_list, hazard_tiles, exit_tiles, map_width, map_height):
        self.handle_input(walls_list, map_width, map_height)
        hit_exit = self.check_environmental_interactions(hazard_tiles, exit_tiles)

        drain_rate = 0.02
        if not self.flashlight_on: drain_rate += 0.08
        self.sanity = max(0, self.sanity - drain_rate)

        turn_speed = 0.1 
        self.smooth_dir_x += (self.dir_x - self.smooth_dir_x) * turn_speed
        self.smooth_dir_y += (self.dir_y - self.smooth_dir_y) * turn_speed
        
        if self.is_moving:
            anim_speed = 0.08 if self.current_speed > self.base_speed else self.anim_speed
            self.anim_timer += 0.016
            if self.anim_timer >= anim_speed:
                self.anim_timer = 0
                self.anim_frame += 1
        else:
            self.anim_frame = 0

        return hit_exit

    def draw(self, cam_x, cam_y):
        shiver_x, shiver_y = 0, 0
        if self.sanity < 30:
            shiver_x = random.randint(-1, 1)
            shiver_y = random.randint(-1, 1)

        if "player_sheet" in settings.TEXTURES:
            row = 10  
            if self.smooth_dir_y < -0.5: row = 8   
            elif self.smooth_dir_x < -0.5: row = 9   
            elif self.smooth_dir_x > 0.5: row = 11  
            
            col = self.anim_frame % 9 if self.is_moving else 0
            sheet_rect = pg.Rect(col * self.sprite_w, row * self.sprite_h, self.sprite_w, self.sprite_h)
            frame_surf = pg.Surface((self.sprite_w, self.sprite_h), pg.SRCALPHA)
            frame_surf.blit(settings.TEXTURES["player_sheet"], (0, 0), sheet_rect)
            scaled_player = pg.transform.scale(frame_surf, (self.size, self.size))
            pg.display.get_surface().blit(scaled_player, (self.x - cam_x + shiver_x, self.y - cam_y + shiver_y))
        else:
            gl.draw.rect(self.x - cam_x + shiver_x, self.y - cam_y + shiver_y, self.size, self.size, "green")

    def draw_hud(self, level_index):
        gl.draw.rect(20, 20, 200, 15, (60, 10, 10))
        h_w = int(200 * (self.health / self.max_health))
        if h_w > 0: gl.draw.rect(20, 20, h_w, 15, (200, 30, 30))

        gl.draw.rect(20, 40, 200, 10, (10, 10, 60))
        s_w = int(200 * (self.stamina / self.max_stamina))
        if s_w > 0: gl.draw.rect(20, 40, s_w, 10, (40, 160, 220))

        gl.draw.rect(20, 55, 200, 10, (40, 10, 40))
        san_w = int(200 * (self.sanity / self.max_sanity))
        if san_w > 0: gl.draw.rect(20, 55, san_w, 10, (160, 40, 180))
        
        lvl_text = settings.ui_font.render(f"LEVEL: {level_index}", True, "white")
        pg.display.get_surface().blit(lvl_text, (20, 75))