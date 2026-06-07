import math, random
from collections import deque
import pygame
from config import CHARACTERS, SHOP_ITEMS, CODE_BULLETS, WEAPON_BULLETS, MAP_W, MAP_H, GREEN, YELLOW, RED, ORANGE, PURPLE, GOLD, SEL, LIGHT_FLASH_DURATION, DOMAIN_RADIUS, ALLY_TYPES, BOMB_TYPES, MAX_BOMBS, MAX_PARTICLES

# Building interior zones where enemies should NOT spawn
# (player can walk through, but enemies won't appear inside)
BUILDING_ZONES = [
    (12, 26, 20, 34),     # Edificio A
    (12, 26, 56, 70),     # Edificio B
    (52, 64, 20, 34),     # Cafeteria
    (52, 64, 56, 70),     # Laboratorio
    (74, 90, 28, 66),     # Canchas
    (12, 30, 78, 105),    # Biblioteca
]


def in_building_zone(col, row):
    for r1, r2, c1, c2 in BUILDING_ZONES:
        if r1 <= row <= r2 and c1 <= col <= c2:
            return True
    return False

def move_with_collision(pos, nx, ny, grid):
    """Axis-separated wall collision: try full move, fallback to X-only, then Y-only."""
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

from src.tilemap import world_to_tile, is_wall, TILE, ROWS, COLS
from src.sprites import draw_player
from src.sound import SFX
from src.effects import Particle, Decal, DamageNum, CodeSnippet, Notif


class Bullet(pygame.sprite.Sprite):
    def __init__(self, pos, angle, text, damage, speed=14, spread=0.0, map_w=MAP_W, map_h=MAP_H, color=(0, 200, 255)):
        super().__init__()
        self.map_w = map_w; self.map_h = map_h
        self.damage = damage
        self.text = text
        self.font = pygame.font.Font(None, 15)
        self.image = self.font.render(self.text, True, color)
        self.rect = self.image.get_rect(center=(int(pos[0]), int(pos[1])))
        self.pos = pygame.Vector2(pos)
        self.radius = max(self.rect.width, self.rect.height) // 2
        self.color = color
        a = angle + random.uniform(-spread, spread)
        self.vel = pygame.Vector2(math.cos(a), math.sin(a)) * speed

    def update(self, grid=None):
        self.pos += self.vel
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if grid is not None:
            col, row = world_to_tile(self.pos.x, self.pos.y)
            if is_wall(grid, col, row):
                self.kill()
                return
        if (self.pos.x < -100 or self.pos.x > self.map_w + 100 or
            self.pos.y < -100 or self.pos.y > self.map_h + 100):
            self.kill()


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
        px = int(self.pos.x - cx)
        py = int(self.pos.y - cy)
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
        self.damage = info["dmg"]
        self.radius = info["radius"]
        self.speed = info["speed"]
        self.fuse = info["fuse"]
        self.color = info["color"]
        self.life = info["fuse"]
        self.stuck_to = None
        self.stuck_offset = pygame.Vector2(0, 0)
        self.bounces = 0
        self.max_bounces = 3
        self.detonated = False
        self.sub_bombs = []
        # Napalm pool
        self.pool_life = 0
        if btype == "napalm":
            self.pool_life = 240
        # Mine
        if btype == "mine":
            self.vel = pygame.Vector2(0, 0)
            self.life = -1  # stays until triggered
            self.trigger_radius = 40
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
        if self.detonated:
            return
        if self.btype == "mine":
            if enemies:
                for e in enemies:
                    if self.pos.distance_to(e.pos) < self.trigger_radius:
                        self._detonate_frame = 1
                        return
            return
        if self.stuck_to:
            if self.stuck_to.alive():
                self.pos = self.stuck_to.pos + self.stuck_offset
                self.rect.center = (int(self.pos.x), int(self.pos.y))
                self.life -= 1
                if self.life <= 0:
                    self._detonate_frame = 1
                return
            else:
                self._detonate_frame = 1
                return
        self.pos += self.vel
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if grid is not None:
            col, row = world_to_tile(self.pos.x, self.pos.y)
            if is_wall(grid, col, row):
                if self.btype == "bouncing":
                    self.bounces += 1
                    if self.bounces >= self.max_bounces:
                        self._detonate_frame = 1
                    else:
                        self.vel.x = -self.vel.x * 0.8
                        self.vel.y = -self.vel.y * 0.8
                else:
                    self._detonate_frame = 1
        self.life -= 1
        if self.life <= 0:
            self._detonate_frame = 1
        if (self.pos.x < -200 or self.pos.x > self.map_w + 200 or
            self.pos.y < -200 or self.pos.y > self.map_h + 200):
            self.kill()

    def draw(self, surf, cx, cy):
        px = int(self.pos.x - cx)
        py = int(self.pos.y - cy)
        if self.btype == "mine" and self.life < 0:
            pygame.draw.circle(surf, (0, 255, 0, 30), (px, py), self.radius, 1)
        if self.btype == "napalm" and self.pool_life > 0:
            alpha = int(180 * min(1, self.pool_life / 60))
            s = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
            c = (255, 100, 0, alpha)
            pygame.draw.circle(s, c, (self.radius, self.radius), self.radius)
            c2 = (255, 180, 50, int(alpha * 0.5))
            pygame.draw.circle(s, c2, (self.radius, self.radius), self.radius // 2)
            surf.blit(s, (px - self.radius, py - self.radius))
        if self.detonated:
            return
        s = pygame.transform.rotate(self.image, -math.degrees(math.atan2(self.vel.y, self.vel.x)) if self.vel.length() > 0.5 else 0)
        surf.blit(s, s.get_rect(center=(px, py)))


class Enemy(pygame.sprite.Sprite):
    TYPES = {
        "runner":  {"hp": 25,  "speed": 3.0, "r": 11, "color": ORANGE, "dmg": 5,  "score": 10},
        "walker":  {"hp": 60,  "speed": 1.6, "r": 14, "color": (45, 115, 45), "dmg": 8,  "score": 20},
        "tank":    {"hp": 180, "speed": 0.9, "r": 22, "color": PURPLE, "dmg": 15, "score": 40},
        "boss":    {"hp": 600, "speed": 0.6, "r": 32, "color": (200, 45, 45), "dmg": 25, "score": 200},
        "shooter": {"hp": 40,  "speed": 1.8, "r": 13, "color": (50, 200, 255), "dmg": 8,  "score": 25,
                    "shooter_cd": 90, "bullet_speed": 5, "bullet_dmg": 8},
        "healer":  {"hp": 50,  "speed": 1.5, "r": 14, "color": (50, 255, 100), "dmg": 5,  "score": 30,
                    "heal_cd": 120, "heal_amount": 15, "heal_range": 150},
        "swarm":   {"hp": 15,  "speed": 3.5, "r": 9,  "color": (255, 180, 50), "dmg": 4,  "score": 8},
        "shielded":{"hp": 50,  "speed": 1.4, "r": 16, "color": (100, 100, 255), "dmg": 10, "score": 35,
                    "shield_hp": 80},
        "bomber":  {"hp": 35,  "speed": 2.5, "r": 12, "color": (255, 100, 0),  "dmg": 12, "score": 18, "explode_r": 60, "explode_dmg": 30},
        "splitter":{"hp": 50,  "speed": 2.0, "r": 13, "color": (200, 50, 200), "dmg": 6,  "score": 15, "split_n": 3, "split_type": "swarm"},
        "worm":    {"hp": 40,  "speed": 2.2, "r": 14, "color": (150, 100, 50), "dmg": 10, "score": 22, "burrow_cd": 240, "burrow_dur": 120},
        "camouflage":{"hp": 20, "speed": 2.8, "r": 10, "color": (50, 150, 50), "dmg": 5,  "score": 12},
        "buffer":  {"hp": 40,  "speed": 0,   "r": 15, "color": (100, 200, 255), "dmg": 0,  "score": 25, "buff_r": 150, "buff_amt": 0.3},
        "elite":   {"hp": 250, "speed": 1.2, "r": 24, "color": (200, 50, 200), "dmg": 18, "score": 80},
    }

    def __init__(self, etype, map_w=MAP_W, map_h=MAP_H, wave=1, player_pos=None, grid=None):
        super().__init__()
        cfg = self.TYPES[etype]
        self.etype = etype
        self.hp = cfg["hp"]
        self.max_hp = cfg["hp"]
        self.speed = cfg["speed"]
        self.radius = cfg["r"]
        self.color = cfg["color"]
        self.damage = cfg["dmg"]
        self.score_val = cfg["score"]
        if wave > 1:
            s = 1.0 + (wave - 1) * 0.08
            self.hp = int(self.hp * s)
            self.max_hp = self.hp
            self.speed = cfg["speed"] * (1.0 + (wave - 1) * 0.04)
            self.damage = int(self.damage * s)

        self.kb = pygame.Vector2(0, 0)
        self.is_boss = etype == "boss"
        self.waifu_target = None
        self.waifu_timer = 0
        self.stun_timer = 0
        self.shooter_cd = cfg.get("shooter_cd", 0)
        self.shooter_timer = cfg.get("shooter_cd", 90)
        self.heal_cd = cfg.get("heal_cd", 0)
        self.heal_timer = cfg.get("heal_cd", 120)
        self.shield_hp = cfg.get("shield_hp", 0)
        self.boss_phase2 = False
        self.boss_charge_timer = 0
        self.boss_charging = False
        self.boss_summoned = False
        self.boss_shield_timer = 0
        self.boss_shield_active = False
        self.boss_shoot_timer = 0
        self.explode_r = cfg.get("explode_r", 0)
        self.explode_dmg = cfg.get("explode_dmg", 0)
        self.split_n = cfg.get("split_n", 0)
        self.split_type = cfg.get("split_type", "swarm")
        self.burrow_cd = cfg.get("burrow_cd", 0)
        self.burrow_dur = cfg.get("burrow_dur", 0)
        self.burrowed = False
        self.burrow_timer = random.randint(0, 60)
        self.buff_r = cfg.get("buff_r", 0)
        self.buff_amt = cfg.get("buff_amt", 0)
        self.dmg_mult = 1.0
        self.speed_mult = 1.0
        self.camo = etype == "camouflage"
        self.boss_shield_active = False
        self.boss_shoot_timer = 0
        self.hit_flash = 0
        self.map_w = map_w; self.map_h = map_h
        self.path = []
        self.path_timer = 0
        self.bob_phase = random.uniform(0, 6.28)
        self.dying = False
        self.death_timer = 0
        self._death_surf = None
        # Smart AI
        self.frozen = False
        self.frozen_timer = 0
        self.dodge_timer = 0
        self.dodge_angle = 0
        self.tactical_state = "chase"
        self.tactical_target = None

        if player_pos is not None:
            if grid is not None:
                for _ in range(30):
                    a = random.uniform(0, math.tau)
                    d = random.uniform(350, 600)
                    self.pos = pygame.Vector2(
                        player_pos.x + math.cos(a) * d,
                        player_pos.y + math.sin(a) * d,
                    )
                    self.pos.x = max(self.radius, min(self.pos.x, map_w - self.radius))
                    self.pos.y = max(self.radius, min(self.pos.y, map_h - self.radius))
                    col, row = world_to_tile(self.pos.x, self.pos.y)
                    if not is_wall(grid, col, row) and not in_building_zone(col, row):
                        break
                else:
                    # Fallback: scan outward in rings for nearest walkable tile that is NOT in a building zone
                    pc, pr = world_to_tile(player_pos.x, player_pos.y)
                    for radius in range(1, 30):
                        found = False
                        for dr in range(-radius, radius + 1):
                            for dc in range(-radius, radius + 1):
                                if abs(dr) == radius or abs(dc) == radius:
                                    nr, nc = pr + dr, pc + dc
                                    if 0 <= nr < ROWS and 0 <= nc < COLS and not is_wall(grid, nc, nr) and not in_building_zone(nc, nr):
                                        self.pos = pygame.Vector2(nc * TILE + TILE // 2, nr * TILE + TILE // 2)
                                        self.pos.x = max(self.radius, min(self.pos.x, map_w - self.radius))
                                        self.pos.y = max(self.radius, min(self.pos.y, map_h - self.radius))
                                        found = True
                                        break
                            if found: break
                        if found: break
            else:
                a = random.uniform(0, math.tau)
                d = random.uniform(350, 600)
                self.pos = pygame.Vector2(
                    player_pos.x + math.cos(a) * d,
                    player_pos.y + math.sin(a) * d,
                )
        else:
            side = random.choice(["t", "b", "l", "r"])
            m = 60
            if side == "t":    self.pos = pygame.Vector2(random.uniform(0, map_w), -m)
            elif side == "b":  self.pos = pygame.Vector2(random.uniform(0, map_w), map_h + m)
            elif side == "l":  self.pos = pygame.Vector2(-m, random.uniform(0, map_h))
            else:              self.pos = pygame.Vector2(map_w + m, random.uniform(0, map_h))

        self.image = pygame.Surface((self.radius * 2,) * 2, pygame.SRCALPHA)
        self._redraw()
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def _redraw(self):
        self.image.fill((0, 0, 0, 0))
        r = self.radius
        c = self.color[:3]
        if self.hit_flash > 0:
            c = tuple(min(255, x + 80) for x in c)
        if self.is_boss:
            pygame.draw.circle(self.image, (55, 18, 18), (r, r), r)
            pygame.draw.circle(self.image, (130, 30, 30), (r, r), r - 4)
            pygame.draw.circle(self.image, (200, 150, 50), (r, r), r, 3)
            pygame.draw.circle(self.image, RED, (r - 9, r - 6), 5)
            pygame.draw.circle(self.image, RED, (r + 9, r - 6), 5)
            pygame.draw.circle(self.image, YELLOW, (r - 9, r - 6), 2)
            pygame.draw.circle(self.image, YELLOW, (r + 9, r - 6), 2)
            if self.boss_phase2:
                pygame.draw.circle(self.image, (255, 50, 50), (r, r), r + 3, 2)
        elif self.etype == "shooter":
            pygame.draw.circle(self.image, (30, 60, 80), (r, r), r)
            pygame.draw.circle(self.image, c, (r, r), r - 2)
            pygame.draw.circle(self.image, RED, (r - 4, r - 4), 3)
            pygame.draw.circle(self.image, RED, (r + 4, r - 4), 3)
            pygame.draw.rect(self.image, (100, 100, 100), (r + 3, r - 2, 8, 3))
        elif self.etype == "healer":
            pygame.draw.circle(self.image, (20, 60, 30), (r, r), r)
            pygame.draw.circle(self.image, c, (r, r), r - 2)
            pygame.draw.circle(self.image, RED, (r - 4, r - 4), 2)
            pygame.draw.circle(self.image, RED, (r + 4, r - 4), 2)
            pygame.draw.line(self.image, (255, 255, 255), (r, r - 6), (r, r + 6), 2)
            pygame.draw.line(self.image, (255, 255, 255), (r - 6, r), (r + 6, r), 2)
        elif self.etype == "swarm":
            pygame.draw.circle(self.image, (80, 50, 10), (r, r), r)
            pygame.draw.circle(self.image, c, (r, r), r - 1)
            pygame.draw.circle(self.image, RED, (r - 3, r - 3), 2)
            pygame.draw.circle(self.image, RED, (r + 3, r - 3), 2)
        elif self.etype == "shielded":
            pygame.draw.circle(self.image, (30, 30, 80), (r, r), r)
            pygame.draw.circle(self.image, c, (r, r), r - 2)
            pygame.draw.circle(self.image, (100, 100, 255), (r, r), r, 3)
            pygame.draw.circle(self.image, RED, (r - 5, r - 4), 3)
            pygame.draw.circle(self.image, RED, (r + 5, r - 4), 3)
        elif self.etype == "bomber":
            pygame.draw.circle(self.image, (60, 30, 0), (r, r), r)
            pygame.draw.circle(self.image, c, (r, r), r - 2)
            pygame.draw.circle(self.image, RED, (r - 3, r - 4), 3)
            pygame.draw.circle(self.image, RED, (r + 3, r - 4), 3)
            pygame.draw.circle(self.image, (255, 80, 0), (r, r), r, 2)
            pygame.draw.rect(self.image, (255, 200, 50), (r - 4, r + 2, 8, 3))
        elif self.etype == "splitter":
            pygame.draw.circle(self.image, (60, 20, 60), (r, r), r)
            pygame.draw.circle(self.image, c, (r, r), r - 2)
            pygame.draw.circle(self.image, RED, (r - 4, r - 4), 2)
            pygame.draw.circle(self.image, RED, (r + 4, r - 4), 2)
            pygame.draw.circle(self.image, (255, 80, 255), (r, r), r, 2)
            for angle in [0, 2.09, 4.18]:
                cx = r + int(math.cos(angle) * r * 0.5)
                cy = r + int(math.sin(angle) * r * 0.5)
                pygame.draw.circle(self.image, (200, 80, 200), (cx, cy), 3)
        elif self.etype == "worm":
            pygame.draw.circle(self.image, (60, 40, 15), (r, r), r)
            if not self.burrowed:
                pygame.draw.circle(self.image, c, (r, r), r - 2)
                pygame.draw.circle(self.image, RED, (r - 4, r - 4), 2)
                pygame.draw.circle(self.image, RED, (r + 4, r - 4), 2)
                pygame.draw.circle(self.image, (100, 60, 30), (r, r), r, 2)
        elif self.etype == "camouflage":
            alpha = 60
            inner = tuple(max(0, x - 30) for x in c)
            pygame.draw.circle(self.image, (*c, alpha), (r, r), r)
            pygame.draw.circle(self.image, (*inner, alpha), (r, r), r - 2)
            pygame.draw.circle(self.image, (*c, 160), (r, r), r, 2)
            pygame.draw.circle(self.image, RED, (r - 3, r - 4), 2)
            pygame.draw.circle(self.image, RED, (r + 3, r - 4), 2)
        elif self.etype == "buffer":
            pygame.draw.circle(self.image, (30, 60, 80), (r, r), r)
            pygame.draw.circle(self.image, c, (r, r), r - 2)
            pygame.draw.circle(self.image, RED, (r - 4, r - 4), 2)
            pygame.draw.circle(self.image, RED, (r + 4, r - 4), 2)
            pygame.draw.circle(self.image, (200, 255, 255), (r, r), r, 2)
            pygame.draw.line(self.image, (200, 255, 255), (r - 5, r), (r + 5, r), 2)
            pygame.draw.line(self.image, (200, 255, 255), (r, r - 5), (r, r + 5), 2)
        elif self.etype == "elite":
            pygame.draw.circle(self.image, (60, 18, 60), (r, r), r)
            pygame.draw.circle(self.image, c, (r, r), r - 3)
            pygame.draw.circle(self.image, (255, 100, 0), (r, r), r, 3)
            pygame.draw.circle(self.image, RED, (r - 8, r - 6), 4)
            pygame.draw.circle(self.image, RED, (r + 8, r - 6), 4)
            pygame.draw.circle(self.image, YELLOW, (r - 8, r - 6), 2)
            pygame.draw.circle(self.image, YELLOW, (r + 8, r - 6), 2)
            pygame.draw.rect(self.image, (80, 40, 80), (r - r//2, r - 2, r, 4))
        else:
            inner = tuple(max(0, x - 35) for x in c)
            pygame.draw.circle(self.image, c, (r, r), r)
            pygame.draw.circle(self.image, inner, (r, r), r - 3)
            pygame.draw.circle(self.image, (*c, 160), (r, r), r, 2)
            pygame.draw.circle(self.image, RED, (r - 4 - r // 6, r - 4), max(2, r // 4))
            pygame.draw.circle(self.image, RED, (r + 4 + r // 6, r - 4), max(2, r // 4))
            if self.etype == "tank":
                pygame.draw.rect(self.image, (80, 40, 80), (r - r//2, r - 2, r, 4))

    def hit(self, dmg, kb_dir=None, kb_mult=1.0):
        if self.burrowed:
            return False
        if self.boss_shield_active:
            return False
        if self.shield_hp > 0:
            self.shield_hp -= dmg
            if self.shield_hp <= 0:
                self.shield_hp = 0
                self.stun_timer = 60
            return False
        self.hp -= dmg
        self.hit_flash = 6
        if kb_dir:
            k = (5 if not self.is_boss else 2) * kb_mult
            self.kb = pygame.Vector2(kb_dir).normalize() * k
        # Boss phase 2 at 50% HP
        if self.is_boss and not self.boss_phase2 and self.hp <= self.max_hp * 0.5:
            self.boss_phase2 = True
            self.speed *= 1.3
            self.damage = int(self.damage * 1.5)
        return self.hp <= 0

    def update(self, player_pos, dt=1, enemies=None, enemy_bullets=None, particles=None, grid=None):
        if self.frozen:
            self.frozen_timer -= 1
            if self.frozen_timer <= 0:
                self.frozen = False
            return
        if self.hit_flash > 0:
            self.hit_flash -= 1
        if self.stun_timer > 0:
            self.stun_timer -= 1
            return
        if self.waifu_timer > 0:
            self.waifu_timer -= 1
            if self.waifu_target is not None:
                dx = self.waifu_target[0] - self.pos.x
                dy = self.waifu_target[1] - self.pos.y
                dist = math.hypot(dx, dy)
                if dist > 10:
                    self.pos.x += (dx / dist) * self.speed * 1.5
                    self.pos.y += (dy / dist) * self.speed * 1.5
                    self.rect.center = (int(self.pos.x), int(self.pos.y))
                    return
                else:
                    self.waifu_timer = 0

        # Camouflage alpha (fade in when player close)
        if self.camo:
            dist_p = math.hypot(self.pos.x - player_pos[0], self.pos.y - player_pos[1])
            vis = max(30, min(255, int(255 * (1 - dist_p / 300))))
            self.image.set_alpha(vis)

        # Worm burrow
        if self.burrow_cd > 0:
            self.burrow_timer -= 1
            if self.burrowed:
                if self.burrow_timer <= 0:
                    self.burrowed = False
                    self.burrow_timer = self.burrow_cd
                    a = random.uniform(0, math.tau)
                    d = random.uniform(30, 80)
                    self.pos.x = player_pos[0] + math.cos(a) * d
                    self.pos.y = player_pos[1] + math.sin(a) * d
                    self._redraw()
                    if particles is not None:
                        for _ in range(8):
                            a2 = random.uniform(0, math.tau)
                            sp2 = random.uniform(2, 5)
                            particles.append(Particle(self.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2, (120, 80, 40), random.uniform(2, 4), random.randint(10, 20)))
                    self.image.set_alpha(255)
                return
            if self.burrow_timer <= 0 and random.random() < 0.015:
                self.burrowed = True
                self.burrow_timer = self.burrow_dur
                self.image.set_alpha(20)
                return

        # Boss shield timer
        if self.is_boss:
            if self.boss_shield_timer > 0:
                self.boss_shield_timer -= 1
                if self.boss_shield_timer <= 0:
                    self.boss_shield_active = False
            if not self.boss_shield_active and random.random() < 0.003:
                self.boss_shield_active = True
                self.boss_shield_timer = 300

        self.pos += self.kb
        self.kb *= 0.85
        if self.kb.length() < 0.1:
            self.kb = pygame.Vector2(0, 0)

        # Boss charge attack
        if self.is_boss and self.boss_phase2:
            if self.boss_charge_timer > 0:
                self.boss_charge_timer -= 1
                if self.boss_charging:
                    sp = self.speed * 4
                    dx2 = player_pos[0] - self.pos.x
                    dy2 = player_pos[1] - self.pos.y
                    d2 = math.hypot(dx2, dy2)
                    if d2 > 5:
                        self.pos.x += (dx2 / d2) * sp
                        self.pos.y += (dy2 / d2) * sp
                    if particles is not None:
                        for _ in range(2):
                            a2 = random.uniform(0, math.tau)
                            sp2 = random.uniform(1, 3)
                            particles.append(Particle(self.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2, (255, 50, 50), random.uniform(2, 3), random.randint(4, 10)))
                    if self.boss_charge_timer <= 0:
                        self.boss_charging = False
                        self.boss_charge_timer = 180
                    self.rect.center = (int(self.pos.x), int(self.pos.y))
                    return
                if self.boss_charge_timer <= 0:
                    if random.random() < 0.02:
                        self.boss_charging = True
                        self.boss_charge_timer = 30
            else:
                if random.random() < 0.005:
                    self.boss_charging = True
                    self.boss_charge_timer = 30

            # Boss shoots in phase 2
            self.boss_shoot_timer -= 1
            if self.boss_shoot_timer <= 0 and enemy_bullets is not None:
                self.boss_shoot_timer = 180
                for i in range(8):
                    a = math.tau * i / 8
                    nv = pygame.Vector2(math.cos(a), math.sin(a)) * 4
                    enemy_bullets.append(EnemyBullet(self.pos.copy(), nv, 10))

        # Shooter AI (burst fire)
        if self.etype == "shooter":
            self.shooter_timer -= 1
            if self.shooter_timer <= 0 and enemy_bullets is not None:
                self.shooter_timer = self.shooter_cd
                dx2 = player_pos[0] - self.pos.x
                dy2 = player_pos[1] - self.pos.y
                d2 = math.hypot(dx2, dy2)
                if d2 > 0:
                    base_angle = math.atan2(dy2, dx2)
                    for offset in [-0.15, 0, 0.15]:
                        nv = pygame.Vector2(math.cos(base_angle + offset), math.sin(base_angle + offset)) * self.TYPES[self.etype]["bullet_speed"]
                        enemy_bullets.append(EnemyBullet(self.pos.copy(), nv, self.TYPES[self.etype]["bullet_dmg"]))

        # Healer AI (also buffs damage)
        if self.etype == "healer" and enemies is not None:
            self.heal_timer -= 1
            if self.heal_timer <= 0:
                self.heal_timer = self.heal_cd
                for e in enemies:
                    if e is self: continue
                    if e.pos.distance_to(self.pos) < self.TYPES[self.etype]["heal_range"]:
                        e.hp = min(e.max_hp, e.hp + self.TYPES[self.etype]["heal_amount"])
                if particles is not None:
                    for _ in range(4):
                        a2 = random.uniform(0, math.tau)
                        sp2 = random.uniform(1, 3)
                        particles.append(Particle(self.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2, (50, 255, 100), random.uniform(2, 3), random.randint(8, 16)))
            # Damage buff to nearby enemies
            for e in enemies:
                if e is self: continue
                if e.pos.distance_to(self.pos) < self.TYPES[self.etype]["heal_range"]:
                    e.dmg_mult = max(e.dmg_mult, 1.25)

        # Tactical dodge
        if self.dodge_timer > 0:
            self.dodge_timer -= 1
            dodge_spd = self.speed * self.speed_mult * 2
            self.pos.x += math.cos(self.dodge_angle) * dodge_spd
            self.pos.y += math.sin(self.dodge_angle) * dodge_spd
            self.rect.center = (int(self.pos.x), int(self.pos.y))
            return

        # Tactical state: flank toward target
        if self.tactical_state == "flank" and self.tactical_target and not self.is_boss:
            tx, ty = self.tactical_target
            fdx = tx - self.pos.x
            fdy = ty - self.pos.y
            fdist = math.hypot(fdx, fdy)
            if fdist > 30:
                move_spd = self.speed * self.speed_mult
                nx = self.pos.x + (fdx / fdist) * move_spd
                ny = self.pos.y + (fdy / fdist) * move_spd
                if grid is not None:
                    move_with_collision(self.pos, nx, ny, grid)
                else:
                    self.pos.x = nx; self.pos.y = ny
        self.pos.x = max(self.radius, min(self.map_w - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(self.map_h - self.radius, self.pos.y))
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def draw_hp(self, surf, cx, cy):
        bw = self.radius * 2; bh = 4
        x = self.pos.x - bw // 2 - cx
        y = self.pos.y - self.radius - 8 - cy
        r = self.hp / self.max_hp
        pygame.draw.rect(surf, (40, 10, 40), (x, y, bw, bh))
        pygame.draw.rect(surf, (220, 80, 255) if r > 0.5 else (255, 50, 50), (x, y, int(bw * r), bh))


class AirdropCrate(pygame.sprite.Sprite):
    def __init__(self, pos, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        self.pos = pygame.Vector2(pos[0], -40)  # start above screen
        self.target_y = pos[1]
        self.map_w = map_w
        self.map_h = map_h
        self.radius = 16
        self.landed = False
        self.opened = False
        self.fall_speed = 2
        self.land_timer = 0
        self.image = pygame.Surface((self.radius * 2,) * 2, pygame.SRCALPHA)
        self._redraw()
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def _redraw(self):
        self.image.fill((0, 0, 0, 0))
        r = self.radius
        pygame.draw.rect(self.image, (80, 60, 30), (0, 0, r * 2, r * 2), border_radius=3)
        pygame.draw.rect(self.image, (120, 90, 50), (2, 2, r * 2 - 4, r * 2 - 4), border_radius=2)
        pygame.draw.line(self.image, (180, 150, 80), (r, 0), (r, r * 2), 2)
        pygame.draw.line(self.image, (180, 150, 80), (0, r), (r * 2, r), 2)
        # Parachute lines
        if not self.landed:
            pygame.draw.line(self.image, (200, 200, 200), (r, 0), (r - 10, -8), 2)
            pygame.draw.line(self.image, (200, 200, 200), (r, 0), (r + 10, -8), 2)
            # Chute (arc)
            pygame.draw.arc(self.image, (255, 200, 100), (r - 14, -16, 28, 16), math.pi, 2 * math.pi, 3)

    def update(self):
        if not self.landed:
            self.pos.y += self.fall_speed
            if self.pos.y >= self.target_y:
                self.pos.y = self.target_y
                self.landed = True
                self.land_timer = 600  # 10 seconds to collect
            self._redraw()
        else:
            self.land_timer -= 1
            if self.land_timer <= 0 and not self.opened:
                self.kill()
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def draw_glow(self, surf, cx, cy, player_pos):
        if self.landed and not self.opened:
            px = int(self.pos.x - cx)
            py = int(self.pos.y - cy)
            d = self.pos.distance_to(player_pos)
            if d < 120:
                glow_r = 30 + int(math.sin(pygame.time.get_ticks() * 0.005) * 5)
                gs = pygame.Surface((glow_r * 2,) * 2, pygame.SRCALPHA)
                a = int(max(20, 80 - d * 0.5))
                pygame.draw.circle(gs, (255, 210, 55, a), (glow_r, glow_r), glow_r)
                surf.blit(gs, (px - glow_r, py - glow_r))
                # Label
                from src.ui import _f
                lbl = _f(11).render("F=Recibir", True, (255, 210, 55))
                lbl.set_alpha(int(min(255, 500 - d * 3)))
                surf.blit(lbl, (px - lbl.get_width() // 2, py - 30))


class Ally(pygame.sprite.Sprite):
    def __init__(self, aid, pos, player, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        cfg = ALLY_TYPES[aid]
        self.aid = aid
        self.player = player
        self.map_w = map_w; self.map_h = map_h
        self.name = cfg["name"]
        self.max_hp = cfg["hp"]
        self.hp = cfg["hp"]
        self.damage = cfg["dmg"]
        self.speed = cfg["speed"]
        self.radius = cfg["radius"]
        self.color = cfg["color"]
        self.fr = cfg["fr"]
        self.attack_range = cfg["range"]
        self.shoot_timer = 0
        self.pos = pygame.Vector2(pos)
        self.image = pygame.Surface((self.radius * 2,) * 2, pygame.SRCALPHA)
        self._redraw()
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def _redraw(self):
        self.image.fill((0, 0, 0, 0))
        r = self.radius
        c = self.color
        pygame.draw.circle(self.image, tuple(max(0, x-40) for x in c), (r, r), r)
        pygame.draw.circle(self.image, c, (r, r), r - 2)
        pygame.draw.circle(self.image, RED, (r - 4, r - 4), 2)
        pygame.draw.circle(self.image, RED, (r + 4, r - 4), 2)
        # Shield/role mark
        if self.aid == "zaid":
            pygame.draw.circle(self.image, (200, 150, 50), (r, r), r, 3)
        elif self.aid == "irvin_sis":
            pygame.draw.line(self.image, (255, 255, 255), (r, r-5), (r, r+5), 2)
            pygame.draw.line(self.image, (255, 255, 255), (r-5, r), (r+5, r), 2)
        elif self.aid == "usiel_sis":
            pygame.draw.circle(self.image, (255, 255, 255), (r, r), 4)
            pygame.draw.line(self.image, (255, 255, 255), (r, r-4), (r, r+4), 2)

    def update(self, enemies, grid=None):
        if self.hp <= 0:
            self.kill()
            return
        ppos = self.player.pos
        dx = ppos.x - self.pos.x
        dy = ppos.y - self.pos.y
        dist = math.hypot(dx, dy)
        if dist > 80:
            move_spd = self.speed
            nx = self.pos.x + (dx / dist) * move_spd
            ny = self.pos.y + (dy / dist) * move_spd
            if grid is not None:
                col, row = world_to_tile(nx, ny)
                if not is_wall(grid, col, row):
                    self.pos.x = nx; self.pos.y = ny
                else:
                    col2, _ = world_to_tile(nx, self.pos.y)
                    if not is_wall(grid, col2, int(self.pos.y // TILE)): self.pos.x = nx
                    _, row2 = world_to_tile(self.pos.x, ny)
                    if not is_wall(grid, int(self.pos.x // TILE), row2): self.pos.y = ny
            else:
                self.pos.x = nx; self.pos.y = ny

        # Find target
        target = None
        target_dist = self.attack_range + 20
        for e in enemies:
            if not e.alive(): continue
            ed = self.pos.distance_to(e.pos)
            if ed < target_dist:
                target = e
                target_dist = ed
        # Attack
        self.shoot_timer += 1
        if target and self.shoot_timer >= self.fr:
            self.shoot_timer = 0
            edist = self.pos.distance_to(target.pos)
            if edist < self.attack_range:
                if self.aid == "zaid":
                    died = target.hit(self.damage, (target.pos - self.pos).normalize() * 8)
                    return died
                else:
                    from src.entities import Bullet
                    a = math.atan2(target.pos.y - self.pos.y, target.pos.x - self.pos.x)
                    b = Bullet(self.pos, a, "ally", self.damage, speed=10, spread=0.1, map_w=self.map_w, map_h=self.map_h, color=self.color)
                    return b

        self.pos.x = max(self.radius, min(self.map_w - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(self.map_h - self.radius, self.pos.y))
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def draw_hp(self, surf, cx, cy):
        bw = self.radius * 2; bh = 3
        x = self.pos.x - bw // 2 - cx
        y = self.pos.y - self.radius - 6 - cy
        r = self.hp / self.max_hp
        pygame.draw.rect(surf, (20, 20, 20), (x, y, bw, bh))
        pygame.draw.rect(surf, (0, 200, 100) if r > 0.5 else (255, 200, 50) if r > 0.25 else (255, 50, 50), (x, y, int(bw * r), bh))

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp < 0: self.hp = 0
