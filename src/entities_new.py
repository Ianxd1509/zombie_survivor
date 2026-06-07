import math, random
from collections import deque
import pygame
from config import CHARACTERS, SHOP_ITEMS, CODE_BULLETS, WEAPON_BULLETS, MAP_W, MAP_H, GREEN, YELLOW, RED, ORANGE, PURPLE, GOLD, SEL, LIGHT_FLASH_DURATION, DOMAIN_RADIUS, ALLY_TYPES, BOMB_TYPES, MAX_BOMBS, MAX_PARTICLES
from src.tilemap import world_to_tile, is_wall, TILE, ROWS, COLS
from src.sprites import draw_player
from src.sound import SFX
from src.effects import Particle, Decal, DamageNum, CodeSnippet, Notif

BUILDING_ZONES = [
    (12, 26, 20, 34),
    (12, 26, 56, 70),
    (52, 64, 20, 34),
    (52, 64, 56, 70),
    (74, 90, 28, 66),
    (12, 30, 78, 105),
]


def in_building_zone(col, row):
    for r1, r2, c1, c2 in BUILDING_ZONES:
        if r1 <= row <= r2 and c1 <= col <= c2:
            return True
    return False


def move_with_collision(pos, nx, ny, grid):
    col, row = world_to_tile(nx, ny)
    if not is_wall(grid, col, row):
        pos.x = nx; pos.y = ny
    else:
        col2, _ = world_to_tile(nx, pos.y)
        if not is_wall(grid, col2, int(pos.y // TILE)):
            pos.x = nx
        _, row2 = world_to_tile(pos.x, ny)
        if not is_wall(grid, int(pos.x // TILE), row2):
            pos.y = ny

# === Classes ===

class LaserBeam(pygame.sprite.Sprite):
    def __init__(self, pos, angle, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        self.map_w = map_w; self.map_h = map_h
        self.pos = pygame.Vector2(pos)
        self.angle = angle
        self.speed = 20
        self.vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * self.speed
        self.damage = 40
        self.life = 30
        self.len = 40
        self.image = pygame.Surface((self.len, 6), pygame.SRCALPHA)
        self._redraw()
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def _redraw(self):
        self.image.fill((0, 0, 0, 0))
        for i in range(3):
            alpha = 60 + i * 60
            w = 2 + i * 2
            pygame.draw.line(self.image, (255, 0 + i * 20, 0 + i * 10, alpha), (0, 3 - i), (self.len, 3 - i), w)

    def update(self, grid=None):
        self.pos += self.vel
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        self.life -= 1
        if self.life <= 0:
            self.kill()
        if grid is not None:
            col, row = world_to_tile(self.pos.x, self.pos.y)
            if is_wall(grid, col, row):
                self.kill()
        if (self.pos.x < -100 or self.pos.x > self.map_w + 100 or
            self.pos.y < -100 or self.pos.y > self.map_h + 100):
            self.kill()

    def draw(self, surf, cx, cy):
        px = int(self.pos.x - cx); py = int(self.pos.y - cy)
        for i in range(4):
            alpha = max(0, 80 - i * 20)
            w = 8 - i * 2
            if w <= 0: break
            c = (255, max(0, 100 - i * 30), max(0, 50 - i * 15), alpha)
            s = pygame.Surface((self.len + i * 8, w), pygame.SRCALPHA)
            s.fill(c)
            rot = pygame.transform.rotate(s, -math.degrees(self.angle))
            r = rot.get_rect(center=(px, py))
            surf.blit(rot, r)

class Bomb(pygame.sprite.Sprite):
    TYPES = BOMB_TYPES
    def __init__(self, pos, vel, btype, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        self.map_w = map_w; self.map_h = map_h
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)
        self.btype = btype
        info = self.TYPES[btype]
        self.damage = info["dmg"]; self.radius = info["radius"]
        self.speed = info["speed"]; self.fuse = info["fuse"]
        self.color = info["color"]; self.life = info["fuse"]
        self.stuck_to = None; self.stuck_offset = pygame.Vector2(0, 0)
        self.bounces = 0; self.max_bounces = 3; self.detonated = False
        self.sub_bombs = []; self.pool_life = 0
        if btype == "napalm": self.pool_life = 240
        if btype == "mine":
            self.vel = pygame.Vector2(0, 0); self.life = -1; self.trigger_radius = 40
        self.image = pygame.Surface((12, 12), pygame.SRCALPHA)
        self._redraw()
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        self._detonate_frame = 0

    def _redraw(self):
        self.image.fill((0, 0, 0, 0))
        if self.btype == "flash":
            pygame.draw.circle(self.image, (255, 255, 220, 200), (6, 6), 5)
            pygame.draw.circle(self.image, (255, 255, 255, 150), (6, 6), 3)
        elif self.btype == "mine":
            pygame.draw.ellipse(self.image, (80, 180, 80, 200), (1, 4, 10, 4))
            pygame.draw.circle(self.image, (60, 140, 60, 255), (6, 3), 3)
        elif self.btype == "napalm":
            pygame.draw.circle(self.image, (255, 100, 0, 200), (6, 6), 5)
            pygame.draw.circle(self.image, (255, 180, 50, 150), (6, 6), 3)
        elif self.btype == "sticky":
            pygame.draw.circle(self.image, (255, 50, 50, 220), (6, 6), 5)
            pygame.draw.circle(self.image, (200, 20, 20, 150), (6, 6), 3)
        elif self.btype == "cluster":
            pygame.draw.circle(self.image, (255, 80, 200, 220), (6, 6), 6)
            pygame.draw.circle(self.image, (200, 40, 150, 150), (6, 6), 3)
        elif self.btype == "bouncing":
            pygame.draw.circle(self.image, (200, 200, 50, 220), (6, 6), 5)
            pygame.draw.circle(self.image, (255, 255, 100, 150), (6, 6), 3)
        else:
            pygame.draw.circle(self.image, (255, 120, 50, 220), (6, 6), 6)
            pygame.draw.circle(self.image, (200, 80, 20, 150), (6, 6), 3)

    def update(self, grid=None, enemies=None):
        if self.detonated: return
        if self.btype == "mine":
            if enemies:
                for e in enemies:
                    if self.pos.distance_to(e.pos) < self.trigger_radius:
                        self._detonate_frame = 1; return
            return
        if self.stuck_to:
            if self.stuck_to.alive():
                self.pos = self.stuck_to.pos + self.stuck_offset
                self.rect.center = (int(self.pos.x), int(self.pos.y))
                self.life -= 1
                if self.life <= 0: self._detonate_frame = 1
                return
            else: self._detonate_frame = 1; return
        self.pos += self.vel; self.rect.center = (int(self.pos.x), int(self.pos.y))
        if grid is not None:
            col, row = world_to_tile(self.pos.x, self.pos.y)
            if is_wall(grid, col, row):
                if self.btype == "bouncing":
                    self.bounces += 1
                    if self.bounces >= self.max_bounces: self._detonate_frame = 1
                    else: self.vel.x = -self.vel.x * 0.8; self.vel.y = -self.vel.y * 0.8
                else: self._detonate_frame = 1
        self.life -= 1
        if self.life <= 0: self._detonate_frame = 1
        if (self.pos.x < -200 or self.pos.x > self.map_w + 200 or
            self.pos.y < -200 or self.pos.y > self.map_h + 200): self.kill()

    def draw(self, surf, cx, cy):
        px = int(self.pos.x - cx); py = int(self.pos.y - cy)
        if self.btype == "mine" and self.life < 0:
            pygame.draw.circle(surf, (0, 255, 0, 30), (px, py), self.radius, 1)
        if self.btype == "napalm" and self.pool_life > 0:
            alpha = int(180 * min(1, self.pool_life / 60))
            s = pygame.Surface((self.radius * 2,) * 2, pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 100, 0, alpha), (self.radius, self.radius), self.radius)
            pygame.draw.circle(s, (255, 180, 50, int(alpha*0.5)), (self.radius, self.radius), self.radius//2)
            surf.blit(s, (px - self.radius, py - self.radius))
        if self.detonated: return
        s = pygame.transform.rotate(self.image, -math.degrees(math.atan2(self.vel.y, self.vel.x)) if self.vel.length() > 0.5 else 0)
        surf.blit(s, s.get_rect(center=(px, py)))

class AirdropCrate(pygame.sprite.Sprite):
    def __init__(self, pos, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        self.pos = pygame.Vector2(pos[0], -40)
        self.target_y = pos[1]; self.map_w = map_w; self.map_h = map_h
        self.radius = 16; self.landed = False; self.opened = False
        self.fall_speed = 2; self.land_timer = 0
        self.image = pygame.Surface((self.radius * 2,) * 2, pygame.SRCALPHA)
        self._redraw(); self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def _redraw(self):
        self.image.fill((0, 0, 0, 0)); r = self.radius
        pygame.draw.rect(self.image, (80, 60, 30), (0, 0, r*2, r*2), border_radius=3)
        pygame.draw.rect(self.image, (120, 90, 50), (2, 2, r*2-4, r*2-4), border_radius=2)
        pygame.draw.line(self.image, (180, 150, 80), (r, 0), (r, r*2), 2)
        pygame.draw.line(self.image, (180, 150, 80), (0, r), (r*2, r), 2)
        if not self.landed:
            pygame.draw.line(self.image, (200, 200, 200), (r, 0), (r-10, -8), 2)
            pygame.draw.line(self.image, (200, 200, 200), (r, 0), (r+10, -8), 2)
            pygame.draw.arc(self.image, (255, 200, 100), (r-14, -16, 28, 16), math.pi, 2*math.pi, 3)

    def update(self):
        if not self.landed:
            self.pos.y += self.fall_speed
            if self.pos.y >= self.target_y:
                self.pos.y = self.target_y; self.landed = True; self.land_timer = 600
            self._redraw()
        else:
            self.land_timer -= 1
            if self.land_timer <= 0 and not self.opened: self.kill()
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def draw_glow(self, surf, cx, cy, player_pos):
        if self.landed and not self.opened:
            px = int(self.pos.x - cx); py = int(self.pos.y - cy)
            d = self.pos.distance_to(player_pos)
            if d < 120:
                glow_r = 30 + int(math.sin(pygame.time.get_ticks() * 0.005) * 5)
                gs = pygame.Surface((glow_r*2,)*2, pygame.SRCALPHA)
                a = int(max(20, 80 - d * 0.5))
                pygame.draw.circle(gs, (255, 210, 55, a), (glow_r, glow_r), glow_r)
                surf.blit(gs, (px-glow_r, py-glow_r))

class Ally(pygame.sprite.Sprite):
    def __init__(self, aid, pos, player, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        cfg = ALLY_TYPES[aid]
        self.aid = aid; self.player = player; self.map_w = map_w; self.map_h = map_h
        self.name = cfg["name"]; self.max_hp = cfg["hp"]; self.hp = cfg["hp"]
        self.damage = cfg["dmg"]; self.speed = cfg["speed"]; self.radius = cfg["radius"]
        self.color = cfg["color"]; self.fr = cfg["fr"]; self.attack_range = cfg["range"]
        self.shoot_timer = 0; self.pos = pygame.Vector2(pos)
        self.image = pygame.Surface((self.radius*2,)*2, pygame.SRCALPHA)
        self._redraw(); self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def _redraw(self):
        self.image.fill((0,0,0,0)); r = self.radius; c = self.color
        pygame.draw.circle(self.image, tuple(max(0,x-40) for x in c), (r,r), r)
        pygame.draw.circle(self.image, c, (r,r), r-2)
        pygame.draw.circle(self.image, RED, (r-4,r-4), 2); pygame.draw.circle(self.image, RED, (r+4,r-4), 2)
        if self.aid == "zaid": pygame.draw.circle(self.image, (200,150,50), (r,r), r, 3)
        elif self.aid == "irvin_sis":
            pygame.draw.line(self.image, (255,255,255), (r,r-5), (r,r+5), 2)
            pygame.draw.line(self.image, (255,255,255), (r-5,r), (r+5,r), 2)
        elif self.aid == "usiel_sis":
            pygame.draw.circle(self.image, (255,255,255), (r,r), 4)
            pygame.draw.line(self.image, (255,255,255), (r,r-4), (r,r+4), 2)

    def update(self, enemies, grid=None):
        if self.hp <= 0: self.kill(); return
        ppos = self.player.pos
        dx = ppos.x - self.pos.x; dy = ppos.y - self.pos.y; dist = math.hypot(dx, dy)
        if dist > 80:
            nx = self.pos.x + (dx/dist) * self.speed; ny = self.pos.y + (dy/dist) * self.speed
            if grid is not None: move_with_collision(self.pos, nx, ny, grid)
            else: self.pos.x = nx; self.pos.y = ny
        target = None; target_dist = self.attack_range + 20
        for e in enemies:
            if not e.alive(): continue
            ed = self.pos.distance_to(e.pos)
            if ed < target_dist: target = e; target_dist = ed
        self.shoot_timer += 1
        if target and self.shoot_timer >= self.fr:
            self.shoot_timer = 0
            if self.pos.distance_to(target.pos) < self.attack_range:
                if self.aid == "zaid":
                    return target.hit(self.damage, (target.pos-self.pos).normalize()*8)
                else:
                    a = math.atan2(target.pos.y-self.pos.y, target.pos.x-self.pos.x)
                    return Bullet(self.pos, a, "ally", self.damage, speed=10, spread=0.1, map_w=self.map_w, map_h=self.map_h, color=self.color)
        self.pos.x = max(self.radius, min(self.map_w-self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(self.map_h-self.radius, self.pos.y))
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def draw_hp(self, surf, cx, cy):
        bw = self.radius*2; bh = 3
        x = self.pos.x - bw//2 - cx; y = self.pos.y - self.radius - 6 - cy
        r = self.hp / self.max_hp
        pygame.draw.rect(surf, (20,20,20), (x,y,bw,bh))
        pygame.draw.rect(surf, (0,200,100) if r>0.5 else (255,200,50) if r>0.25 else (255,50,50), (x,y,int(bw*r),bh))

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp < 0: self.hp = 0

class Wall:
    def __init__(self, pos, hp=500, player=None):
        self.pos = pygame.Vector2(pos)
        self.hp = hp; self.max_hp = hp; self.radius = 40
        self.player = player; self.timer = 600
        self.image = pygame.Surface((self.radius*2,)*2, pygame.SRCALPHA)
        self._redraw()

    def _redraw(self):
        self.image.fill((0,0,0,0)); r = self.radius
        t = self.hp / self.max_hp
        c = (80,180,255) if t>0.5 else (255,180,80) if t>0.25 else (255,80,80)
        pygame.draw.rect(self.image, (30,30,30), (0,0,r*2,r*2), border_radius=4)
        pygame.draw.rect(self.image, c, (2,2,r*2-4,r*2-4), border_radius=3)
        for i in range(3):
            pygame.draw.line(self.image, (60,60,60), (0,(r//3)*(i+1)), (r*2,(r//3)*(i+1)), 1)
            pygame.draw.line(self.image, (60,60,60), ((r//3)*(i+1),0), ((r//3)*(i+1),r*2), 1)

    def hit(self, dmg):
        self.hp -= dmg
        if self.hp <= 0: return True
        self._redraw(); return False

    def update(self):
        self.timer -= 1
        return self.timer > 0

class BillieNPC:
    def __init__(self, pos, map_w=MAP_W, map_h=MAP_H):
        self.pos = pygame.Vector2(pos)
        self.map_w = map_w; self.map_h = map_h
        self.max_hp = 800 + random.randint(0,200)
        self.hp = self.max_hp; self.speed = 1.8; self.radius = 18
        self.color = (255,80,200); self.attack_range = 250
        self.attract_range = 300; self.sing_timer = 0; self.hp_regen = 0.5
        self.image = pygame.Surface((self.radius*2,)*2, pygame.SRCALPHA)
        self.rect = self.image.get_rect()

    def update(self, enemies, grid=None):
        self.hp = min(self.max_hp, self.hp + self.hp_regen)
        nearest = None; nearest_d = self.attract_range
        for e in enemies:
            d = self.pos.distance_to(e.pos)
            if d < nearest_d: nearest = e; nearest_d = d
        if nearest:
            dx = nearest.pos.x - self.pos.x; dy = nearest.pos.y - self.pos.y; d = math.hypot(dx, dy)
            if d > 30:
                if grid is not None:
                    nx = self.pos.x + (dx/d)*self.speed; ny = self.pos.y + (dy/d)*self.speed
                    move_with_collision(self.pos, nx, ny, grid)
                else:
                    self.pos.x += (dx/d)*self.speed; self.pos.y += (dy/d)*self.speed
        for e in enemies:
            if e.pos.distance_to(self.pos) < self.attract_range:
                pull = (self.pos - e.pos).normalize() * 0.8; e.pos += pull
        if self.sing_timer % 30 == 0:
            for e in enemies:
                if e.pos.distance_to(self.pos) < 200:
                    e.hp = min(e.max_hp, e.hp + 2)

class Tornado:
    def __init__(self, pos, angle, speed=8):
        self.pos = pygame.Vector2(pos); self.angle = angle
        self.vel = pygame.Vector2(math.cos(angle), math.sin(angle))*speed
        self.lifetime = 90; self.radius = 30; self.damage = 15
        self.pull_radius = 80; self.max_radius = 30; self.grabbed = []

    def update(self, grid=None):
        self.pos += self.vel; self.lifetime -= 1
        if grid is not None:
            col, row = world_to_tile(self.pos.x, self.pos.y)
            if is_wall(grid, col, row):
                self.vel.x *= -0.5; self.vel.y *= -0.5
        return self.lifetime > 0

    def draw(self, surf, cx, cy):
        px = int(self.pos.x-cx); py = int(self.pos.y-cy)
        t = max(0, self.lifetime/90)
        for i in range(6):
            a = pygame.time.get_ticks()*0.01 + i*1.05
            r = 10 + i*4 + int(math.sin(a)*5)
            alpha = int(80*t)
            pygame.draw.circle(surf, (200,200,255,alpha), (px+int(math.cos(a)*r), py+int(math.sin(a)*r)-i*4), max(2,8-i))

class ChochoxMinion(pygame.sprite.Sprite):
    def __init__(self, pos, player, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        self.pos = pygame.Vector2(pos); self.player = player
        self.map_w = map_w; self.map_h = map_h
        self.hp = 150; self.max_hp = 150; self.speed = 2.2; self.radius = 18
        self.color = (200,50,150); self.damage = 20; self.attack_cooldown = 0
        self.image = pygame.Surface((self.radius*2,)*2, pygame.SRCALPHA)
        self._redraw(); self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def _redraw(self):
        self.image.fill((0,0,0,0)); r = self.radius
        pygame.draw.circle(self.image, (80,10,60), (r,r), r)
        pygame.draw.circle(self.image, self.color, (r,r), r-3)
        pygame.draw.circle(self.image, (255,80,200), (r-6,r-5), 4)
        pygame.draw.circle(self.image, (255,80,200), (r+6,r-5), 4)
        pygame.draw.circle(self.image, (0,0,0), (r-6,r-5), 2)
        pygame.draw.circle(self.image, (0,0,0), (r+6,r-5), 2)
        pygame.draw.arc(self.image, (255,50,150), (r-7,r,14,8), 0, math.pi, 2)
        pygame.draw.circle(self.image, (255,100,200), (r,r), r, 2)

    def update(self, enemies, player_pos, grid=None):
        if self.hp <= 0: self.kill(); return
        self.attack_cooldown -= 1
        target = None; target_d = 200
        for e in enemies:
            d = self.pos.distance_to(e.pos)
            if d < target_d: target = e; target_d = d
        if target:
            dx = target.pos.x - self.pos.x; dy = target.pos.y - self.pos.y; d = math.hypot(dx, dy)
            if d > 25:
                nx = self.pos.x + (dx/d)*self.speed; ny = self.pos.y + (dy/d)*self.speed
                move_with_collision(self.pos, nx, ny, grid)
            if d < 35 and self.attack_cooldown <= 0:
                self.attack_cooldown = 30
                target.hit(self.damage, (target.pos-self.pos).normalize()*5)
        else:
            dx = player_pos[0] - self.pos.x; dy = player_pos[1] - self.pos.y; d = math.hypot(dx, dy)
            if d > 50:
                nx = self.pos.x + (dx/d)*self.speed; ny = self.pos.y + (dy/d)*self.speed
                move_with_collision(self.pos, nx, ny, grid)
        self.pos.x = max(self.radius, min(self.map_w-self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(self.map_h-self.radius, self.pos.y))
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def draw_hp(self, surf, cx, cy):
        bw = self.radius*2; bh = 3
        x = self.pos.x - bw//2 - cx; y = self.pos.y - self.radius - 6 - cy
        r = self.hp / self.max_hp
        pygame.draw.rect(surf, (20,20,20), (x,y,bw,bh))
        pygame.draw.rect(surf, (200,50,150) if r>0.5 else (255,50,50), (x,y,int(bw*r),bh))

class ZapiensNPC:
    def __init__(self, pos, map_w=MAP_W, map_h=MAP_H):
        self.pos = pygame.Vector2(pos); self.map_w = map_w; self.map_h = map_h
        self.max_hp = 200; self.hp = 200; self.radius = 14
        self.color = (50,200,255); self.is_miniboss = False; self.angle = 0
        self.image = pygame.Surface((self.radius*2,)*2, pygame.SRCALPHA)
        self._redraw(); self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def _redraw(self):
        self.image.fill((0,0,0,0)); r = self.radius; c = self.color
        pygame.draw.circle(self.image, (20,60,80), (r,r), r)
        pygame.draw.circle(self.image, c, (r,r), r-2)
        pygame.draw.circle(self.image, RED, (r-4,r-4), 3)
        pygame.draw.circle(self.image, RED, (r+4,r-4), 3)
        pygame.draw.arc(self.image, (100,200,255), (r-5,r,10,6), 0, math.pi, 2)
        if self.is_miniboss:
            pygame.draw.circle(self.image, (255,50,50), (r,r), r+3, 2)

    def turn_hostile(self):
        self.is_miniboss = True; self.max_hp = 1000; self.hp = 1000; self.radius = 22
        self._redraw()

    def update(self, player_pos, grid, notifs, particles, enemy_bullets):
        self.angle += 0.02
        if self.is_miniboss:
            dx = player_pos[0] - self.pos.x; dy = player_pos[1] - self.pos.y; d = math.hypot(dx, dy)
            if d > 200:
                nx = self.pos.x + (dx/d)*2.5; ny = self.pos.y + (dy/d)*2.5
                move_with_collision(self.pos, nx, ny, grid)
            if random.random() < 0.03 and enemy_bullets is not None:
                a = math.atan2(dy, dx)
                for offset in [-0.2, 0, 0.2]:
                    nv = pygame.Vector2(math.cos(a+offset), math.sin(a+offset))*4
                    enemy_bullets.append(EnemyBullet(self.pos.copy(), nv, 12))
