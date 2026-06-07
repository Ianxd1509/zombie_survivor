import math
import random
import re
from collections import deque

import pygame

from config import ALLY_TYPES, BOMB_TYPES, CHARACTERS, CODE_SNIPPETS, DOMAIN_COOLDOWN, DOMAIN_DURATION, DOMAIN_EXPANSION, LIGHT_FLASH_DURATION, MAP_H, MAP_W, MIN_ULT_CHARGE, ORANGE, PURPLE, RED, SHOP_ITEMS, ULT_CHARGE_MAX, ULT_LASER_DURATION, WEAPON_BULLETS, YELLOW
from src.effects import Notif, Particle
from src.sound import SFX, play_eder_domain_music, stop_eder_domain_music
from src.sprites import draw_player
from src.tilemap import COLS, ROWS, TILE, is_wall, world_to_tile

# Zonas de edificios donde los enemigos NO deben aparecer
ENEMY_REACHABLE = None
BUILDING_ZONES = [
    (12, 26, 20, 34),
    (12, 26, 56, 70),
    (52, 64, 20, 34),
    (52, 64, 56, 70),
    (74, 90, 28, 66),
    (12, 30, 78, 105),
]


# Verifica si una coordenada está dentro de una zona de edificio (sin spawn)
def in_building_zone(col, row):
    return any(r1 <= row <= r2 and c1 <= col <= c2 for r1, r2, c1, c2 in BUILDING_ZONES)

# Verifica si una posición está bloqueada por paredes
def _position_blocked(grid, x, y, radius=0):
    if radius <= 0:
        col, row = world_to_tile(x, y)
        return is_wall(grid, col, row)
    r = max(4, int(radius))
    for ox, oy in ((0, 0), (-r, 0), (r, 0), (0, -r), (0, r), (-r, -r), (r, r)):
        col, row = world_to_tile(x + ox, y + oy)
        if is_wall(grid, col, row):
            return True
    return False


# Mueve con colisión contra paredes (intenta X, luego Y por separado)
def move_with_collision(pos, nx, ny, grid, radius=0):
    if not _position_blocked(grid, nx, ny, radius):
        pos.x = nx
        pos.y = ny
        return True
    moved = False
    if not _position_blocked(grid, nx, pos.y, radius):
        pos.x = nx
        moved = True
    if not _position_blocked(grid, pos.x, ny, radius):
        pos.y = ny
        moved = True
    return moved


# Raycast: calcula el punto final de un láser (se detiene en primera pared)
def laser_ray_end(grid, start, angle, max_len, map_w=MAP_W, map_h=MAP_H):
    step = max(8, TILE // 4)
    traveled = 0
    pos = pygame.Vector2(start)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    while traveled < max_len:
        pos.x += cos_a * step
        pos.y += sin_a * step
        traveled += step
        if pos.x < 0 or pos.y < 0 or pos.x > map_w or pos.y > map_h:
            break
        if _position_blocked(grid, pos.x, pos.y, 4):
            break
    return pos


# Distancia al cuadrado de un punto a un segmento (para beam colisión)
def point_seg_dist_sq(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return (px - x1) ** 2 + (py - y1) ** 2
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    lx = x1 + t * dx
    ly = y1 + t * dy
    return (px - lx) ** 2 + (py - ly) ** 2


PASSIVE_APPLY = {
    "piercing": "piercing",
    "bounce": "bounce",
    "speed": "bonus_speed",
    "vampire": "vampire",
    "lifesteal": "lifesteal",
    "dmg": "bonus_damage",
    "firerate": "fr_mult",
    "reload": "reload_mult",
    "hp": "bonus_max_hp",
    "bytes": "passive_bytes",
}

PASSIVE_SCALE = {
    "piercing": 0,
    "bounce": 0,
    "speed": 0.02,
    "vampire": 1,
    "lifesteal": 0.01,
    "dmg": 1,
    "firerate": 0.98,
    "reload": 0.95,
    "hp": 10,
    "bytes": 5,
}


_BULLET_FONT = None
_BULLET_TEXT_CACHE = {}

# Bala del jugador con texto y daño configurable
class Bullet(pygame.sprite.Sprite):
    def __init__(self, pos, angle, text, damage, speed=14, spread=0.0, map_w=MAP_W, map_h=MAP_H, color=(0, 200, 255), life=0):
        super().__init__()
        global _BULLET_FONT
        if _BULLET_FONT is None:
            _BULLET_FONT = pygame.font.Font(None, 15)
        self.map_w = map_w; self.map_h = map_h
        self.damage = damage
        self.text = text
        self.life = life
        key = (text, color)
        cached = _BULLET_TEXT_CACHE.get(key)
        if cached is None:
            cached = _BULLET_FONT.render(text, True, color)
            _BULLET_TEXT_CACHE[key] = cached
        self.image = cached
        self.rect = self.image.get_rect(center=(int(pos[0]), int(pos[1])))
        self.pos = pygame.Vector2(pos)
        self.radius = max(self.rect.width, self.rect.height) // 2
        self.color = color
        a = angle + random.uniform(-spread, spread)
        self.vel = pygame.Vector2(math.cos(a), math.sin(a)) * speed

    # Mueve la bala, mata si choca con pared o sale del mapa
    def update(self, grid=None):
        self.pos += self.vel
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if self.life > 0:
            self.life -= 1
            if self.life <= 0:
                self.kill()
                return
        if grid is not None:
            col, row = world_to_tile(self.pos.x, self.pos.y)
            if is_wall(grid, col, row):
                self.kill()
                return
        if (self.pos.x < -100 or self.pos.x > self.map_w + 100 or
            self.pos.y < -100 or self.pos.y > self.map_h + 100):
            self.kill()

    # Dibuja la bala en pantalla con offset de cámara
    def draw(self, surf, cx, cy):
        surf.blit(self.image, (int(self.pos.x - cx), int(self.pos.y - cy)))


# Láser del jugador con estela de partículas
class LaserBeam(pygame.sprite.Sprite):
    def __init__(self, pos, angle, map_w=MAP_W, map_h=MAP_H):
        # Inicializa rayo láser: daño 40, vida 30 frames
        super().__init__()
        self.map_w = map_w; self.map_h = map_h
        self.pos = pygame.Vector2(pos)
        self.angle = angle
        self.speed = 20
        self.vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * self.speed
        self.damage = 40
        self.life = 30
        self.len = 60
        self.radius = 14
        self.image = pygame.Surface((self.len + 20, 20), pygame.SRCALPHA)
        self._redraw()
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        self._trail_timer = 0

    def _redraw(self):
        self.image.fill((0, 0, 0, 0))
        colors = [(255, 255, 200, 40), (255, 200, 100, 60), (255, 150, 50, 80),
                  (255, 80, 20, 120), (255, 40, 0, 160)]
        for i in range(5):
            a = 60 - i * 10
            w = 3 + i * 3
            c = (colors[i][0], colors[i][1], colors[i][2], a)
            pygame.draw.line(self.image, c, (10, 10 - 2 + i), (self.len + 10, 10 - 2 + i), w)
        pygame.draw.line(self.image, (255, 255, 255, 200), (10, 9), (self.len + 10, 9), 2)

    # Mueve el láser, genera partículas de estela
    def update(self, grid=None, particles=None):
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
        self._trail_timer += 1
        if particles is not None and self._trail_timer % 2 == 0:
            a = random.uniform(0, math.tau)
            sp = random.uniform(0.5, 1.5)
            particles.append(Particle(
                self.pos - self.vel * 0.5,
                pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                (255, random.randint(80, 150), 0), random.uniform(2, 4),                 random.randint(6, 14)))

    # Dibuja el láser con rotación y múltiples capas de color
    def draw(self, surf, cx, cy):
        px = int(self.pos.x - cx)
        py = int(self.pos.y - cy)
        for i in range(6):
            alpha = max(0, 90 - i * 14)
            w = 12 - i * 2
            if w <= 0: break
            c = (255, max(0, 120 - i * 25), max(0, 60 - i * 12), alpha)
            s = pygame.Surface((self.len + i * 10, w), pygame.SRCALPHA)
            s.fill(c)
            rot = pygame.transform.rotate(s, -math.degrees(self.angle))
            r = rot.get_rect(center=(px, py))
            surf.blit(rot, r)


# Granada con múltiples tipos: flash, mine, napalm, sticky, cluster, bouncing
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
        self.pool_life = 0
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

    # Actualiza física, detonación, colisión con enemigos y paredes
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
        # Sticky bomb logic: check for enemy collision
        if self.btype == "sticky" and enemies is not None:
            for e in enemies:
                if self.pos.distance_to(e.pos) < self.radius + e.r:
                    self.stuck_to = e
                    self.stuck_offset = self.pos - e.pos
                    break
        self.life -= 1
        if self.life <= 0:
            self._detonate_frame = 1
        if (self.pos.x < -200 or self.pos.x > self.map_w + 200 or
            self.pos.y < -200 or self.pos.y > self.map_h + 200):
            self.kill()

    # Dibuja la bomba con rotación y efectos de napalm/mine
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


# Enemigo base con 14 variantes (runner, walker, tank, boss, shooter, etc.)
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
        "vicente_boss":{"hp": 8000, "speed": 1.8, "r": 42, "color": (100, 200, 255), "dmg": 35, "score": 500},
    }

    def __init__(self, etype, map_w=MAP_W, map_h=MAP_H, wave=1, player_pos=None, grid=None):
        super().__init__()
        # Inicializa stats, IA, estado de Vicente boss y pathfinding
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
        self.is_boss = etype == "boss" or etype == "vicente_boss"
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
        # Vicente boss state
        self._vb_phase = 1
        self._vb_shield_active = False
        self._vb_shield_timer = 0
        self._vb_shield_cooldown = 0
        self._vb_attack_timer = 0
        self._vb_special_timer = 120
        self._vb_summon_timer = 240
        self._vb_teleport_timer = 0
        self._vb_charge_timer = 0
        self._vb_charging = False
        self._vb_domain_active = False
        self._vb_domain_timer = 0
        self._vb_domain_cooldown = 0
        self._vb_last_stand = False
        self._vb_rar_shield = False
        self._vb_rar_timer = 0
        self._vb_compress_timer = 0
        self._vb_bomb_timer = 0
        self._vb_extract_timer = 0
        self._vb_syntax_timer = 0
        self._vb_domain_pulse = 0
        self._vb_snippets = []
        self.all_sprites_ref = None
        self.enemies_ref = None
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
        self.stuck_timer = 0
        self.ai_think_timer = random.randint(0, 15)
        self.last_damage_time = pygame.time.get_ticks()

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
                    if not is_wall(grid, col, row) and not in_building_zone(col, row) and (ENEMY_REACHABLE is None or (col, row) in ENEMY_REACHABLE):
                        break
                else:
                    pc, pr = world_to_tile(player_pos.x, player_pos.y)
                    for radius in range(1, 30):
                        found = False
                        for dr in range(-radius, radius + 1):
                            for dc in range(-radius, radius + 1):
                                if abs(dr) == radius or abs(dc) == radius:
                                    nr, nc = pr + dr, pc + dc
                                    if 0 <= nr < ROWS and 0 <= nc < COLS and not is_wall(grid, nc, nr) and not in_building_zone(nc, nr) and (ENEMY_REACHABLE is None or (nc, nr) in ENEMY_REACHABLE):
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
        self._last_pos = pygame.Vector2(self.pos)

    # Redibuja el sprite visual del enemigo según su tipo
    def _redraw(self):
        self.image.fill((0, 0, 0, 0))
        r = self.radius
        c = self.color[:3]
        if self.hit_flash > 0:
            c = tuple(min(255, x + 80) for x in c)
        if self.etype == "vicente_boss":
            pygame.draw.circle(self.image, (20, 50, 80), (r, r), r)
            pygame.draw.circle(self.image, (60, 140, 200), (r, r), r - 4)
            pygame.draw.circle(self.image, (150, 220, 255), (r, r), r, 3)
            pygame.draw.circle(self.image, (100, 200, 255), (r - 10, r - 7), 6)
            pygame.draw.circle(self.image, (100, 200, 255), (r + 10, r - 7), 6)
            pygame.draw.circle(self.image, (200, 240, 255), (r - 10, r - 7), 3)
            pygame.draw.circle(self.image, (200, 240, 255), (r + 10, r - 7), 3)
            if self._vb_domain_active:
                pygame.draw.circle(self.image, (100, 200, 255), (r, r), r + 5, 2)
                pygame.draw.circle(self.image, (150, 220, 255, 80), (r, r), r + 10, 1)
            if self._vb_rar_shield:
                pygame.draw.rect(self.image, (200, 180, 50), (4, 4, r * 2 - 8, r * 2 - 8), 3, border_radius=4)
                pygame.draw.rect(self.image, (100, 80, 20), (6, 6, r * 2 - 12, r * 2 - 12), 1, border_radius=3)
        elif self.is_boss:
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

    # Aplica daño, knockback y cambia a fase 2 al 50% HP (boss)
    def hit(self, dmg, kb_dir=None, kb_mult=1.0):
        if self.burrowed:
            return False
        if self.etype == "vicente_boss":
            if self._vb_shield_active or self._vb_rar_shield:
                return False
        elif self.boss_shield_active:
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

    def _step_move(self, nx, ny, grid):
        old_x, old_y = self.pos.x, self.pos.y
        if grid is not None:
            move_with_collision(self.pos, nx, ny, grid, self.radius)
        else:
            self.pos.x = nx
            self.pos.y = ny
        if abs(self.pos.x - old_x) < 0.5 and abs(self.pos.y - old_y) < 0.5:
            self.stuck_timer += 1
            if self.stuck_timer > 8:
                self.path = []
                self.path_timer = 0
        else:
            self.stuck_timer = 0
        self._last_pos.update(self.pos)

    def _warp_to_clear(self, grid, x, y, radius=None):
        r = radius or self.radius
        col, row = world_to_tile(x, y)
        if not is_wall(grid, col, row) and not _position_blocked(grid, x, y, r):
            self.pos.x = x
            self.pos.y = y
            return True
        for ring in range(1, 6):
            for dr in range(-ring, ring + 1):
                for dc in range(-ring, ring + 1):
                    if abs(dr) != ring and abs(dc) != ring:
                        continue
                    nr, nc = int(y // TILE) + dr, int(x // TILE) + dc
                    if 0 <= nr < ROWS and 0 <= nc < COLS and not is_wall(grid, nc, nr):
                        self.pos.x = nc * TILE + TILE // 2
                        self.pos.y = nr * TILE + TILE // 2
                        return True
        return False

    def _ai_dodge_bullets(self, enemy_bullets):
        if not enemy_bullets or self.dodge_timer > 0:
            return False
        for b in enemy_bullets:
            if not hasattr(b, "pos") or not hasattr(b, "vel"):
                continue
            to_me = self.pos - b.pos
            dist = to_me.length()
            if dist > 140 or dist < 8:
                continue
            if b.vel.length_squared() < 0.1:
                continue
            vel_n = b.vel.normalize()
            to_me_n = to_me.normalize() if dist > 0 else pygame.Vector2(1, 0)
            if vel_n.dot(to_me_n) > 0.35:
                self.trigger_dodge(math.atan2(b.vel.y, b.vel.x))
                return True
        return False

    def _ai_separation(self, enemies, strength=0.35):
        if not enemies:
            return pygame.Vector2(0, 0)
        sep = pygame.Vector2(0, 0)
        for e in enemies:
            if e is self or not hasattr(e, "pos"):
                continue
            d = self.pos.distance_to(e.pos)
            if d < 1 or d > self.radius * 5:
                continue
            away = self.pos - e.pos
            away.scale_to_length(strength * (1 - d / (self.radius * 5)))
            sep += away
        return sep

    # Actualiza IA, movimiento, ataques, fases del boss Vicente
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
                    sp = self.speed * 1.5
                    self._step_move(self.pos.x + (dx / dist) * sp, self.pos.y + (dy / dist) * sp, grid)
                    self.rect.center = (int(self.pos.x), int(self.pos.y))
                    return
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
                    nx = player_pos[0] + math.cos(a) * d
                    ny = player_pos[1] + math.sin(a) * d
                    if grid is not None:
                        self._warp_to_clear(grid, nx, ny)
                    else:
                        self.pos.x = nx
                        self.pos.y = ny
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

        # Vicente boss: complete custom update
        if self.etype == "vicente_boss":
            self._update_vicente_boss(player_pos, enemies, enemy_bullets, particles, grid)
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

        if self.kb.length() > 0.1:
            kb_pos = self.pos + self.kb
            if grid is not None:
                move_with_collision(self.pos, kb_pos.x, kb_pos.y, grid, self.radius)
            else:
                self.pos = kb_pos
            self.kb *= 0.85
            if self.kb.length() < 0.1:
                self.kb = pygame.Vector2(0, 0)
        else:
            self.kb = pygame.Vector2(0, 0)

        self._ai_dodge_bullets(enemy_bullets)

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
                        self._step_move(self.pos.x + (dx2 / d2) * sp, self.pos.y + (dy2 / d2) * sp, grid)
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
                if self.boss_charge_timer <= 0 and random.random() < 0.02:
                    self.boss_charging = True
                    self.boss_charge_timer = 30
            elif random.random() < 0.005:
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

        # Shooter AI (burst fire) con línea de visión
        if self.etype == "shooter":
            self.shooter_timer -= 1
            sd2x = player_pos[0] - self.pos.x
            sd2y = player_pos[1] - self.pos.y
            sdist = math.hypot(sd2x, sd2y)
            can_see_player = True
            if grid is not None:
                ang_to_player = math.atan2(sd2y, sd2x)
                end_hit = laser_ray_end(grid, self.pos, ang_to_player, sdist + 10, self.map_w, self.map_h)
                can_see_player = end_hit.distance_to(self.pos) >= sdist - 10
            if self.shooter_timer <= 0 and enemy_bullets is not None and can_see_player:
                self.shooter_timer = self.shooter_cd
                dx2 = player_pos[0] - self.pos.x
                dy2 = player_pos[1] - self.pos.y
                d2 = math.hypot(dx2, dy2)
                if d2 > 0:
                    base_angle = math.atan2(dy2, dx2)
                    for offset in [-0.15, 0, 0.15]:
                        nv = pygame.Vector2(math.cos(base_angle + offset), math.sin(base_angle + offset)) * self.TYPES[self.etype]["bullet_speed"]
                        enemy_bullets.append(EnemyBullet(self.pos.copy(), nv, self.TYPES[self.etype]["bullet_dmg"]))
                    self.last_damage_time = pygame.time.get_ticks()
            elif not can_see_player:
                # Move to a position where we can see the player
                perp_angle = math.atan2(player_pos[1] - self.pos.y, player_pos[0] - self.pos.x) + random.uniform(-1.0, 1.0)
                self.tactical_target = self.pos + pygame.Vector2(math.cos(perp_angle), math.sin(perp_angle)) * 80
                self.tactical_state = "flank"

        # Healer AI (also buffs damage) - prioriza boss o enemigo con más HP
        if self.etype == "healer" and enemies is not None:
            self.heal_timer -= 1
            if self.heal_timer <= 0:
                self.heal_timer = self.heal_cd
                # Find best target: prioritize boss, then highest missing HP
                best_target = None
                best_missing = 0
                for e in enemies:
                    if e is self: continue
                    if e.pos.distance_to(self.pos) < self.TYPES[self.etype]["heal_range"]:
                        missing = e.max_hp - e.hp
                        priority = 2 if e.etype in ("vicente_boss", "boss") else 1
                        if priority * missing > best_missing:
                            best_missing = priority * missing
                            best_target = e
                if best_target and best_missing > 0:
                    best_target.hp = min(best_target.max_hp, best_target.hp + self.TYPES[self.etype]["heal_amount"])
                    self.last_damage_time = pygame.time.get_ticks()
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
            self._step_move(
                self.pos.x + math.cos(self.dodge_angle) * dodge_spd,
                self.pos.y + math.sin(self.dodge_angle) * dodge_spd,
                grid,
            )
            self.rect.center = (int(self.pos.x), int(self.pos.y))
            return

        # Hold position (ranged / support roles)
        if self.tactical_state == "hold" and not self.is_boss:
            dx = player_pos[0] - self.pos.x
            dy = player_pos[1] - self.pos.y
            dist = math.hypot(dx, dy)
            hold_dist = 220 if self.etype == "shooter" else 160
            if dist < hold_dist - 40 and dist > 0.5:
                nx = self.pos.x - (dx / dist) * self.speed
                ny = self.pos.y - (dy / dist) * self.speed
                self._step_move(nx, ny, grid)
            elif dist > hold_dist + 40 and dist > 0.5:
                nx = self.pos.x + (dx / dist) * self.speed * 0.7
                ny = self.pos.y + (dy / dist) * self.speed * 0.7
                self._step_move(nx, ny, grid)
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
                self._step_move(nx, ny, grid)
                self.rect.center = (int(self.pos.x), int(self.pos.y))
                self.bob_phase += 0.06
                self.rect.centery = int(self.pos.y + math.sin(self.bob_phase) * 2)
                return

        # Movement toward player (skip if burrowed, stationary buffer)
        if self.burrowed or self.etype == "buffer":
            self.rect.center = (int(self.pos.x), int(self.pos.y))
            return

        dx = player_pos[0] - self.pos.x
        dy = player_pos[1] - self.pos.y
        dist = math.hypot(dx, dy)
        stop_dist = 200 if self.etype == "shooter" else 0
        # Aggro system: patrol when far, rush when close
        aggro_speed = 1.0
        if dist > 800:
            aggro_speed = 0.3  # patrol speed far away
        elif dist > 400:
            aggro_speed = 0.6  # jog when mid-range
        # Retreat when low HP
        retreating = False
        if self.hp < self.max_hp * 0.3 and self.etype not in ("vicente_boss", "boss", "shooter", "buffer"):
            retreating = True
        if dist > stop_dist and dist > 0.5:
            move_spd = self.speed * self.speed_mult * aggro_speed * (1.3 if self.is_boss and self.boss_phase2 else 1.0)
            sep = self._ai_separation(enemies, 0.4)
            if grid is not None and dist < 1400 and not retreating:
                # Basic enemies use direct chase when far; advanced ones BFS closer
                use_direct = (self.etype in ("walker", "runner", "swarm", "bomber") and dist > 400)
                self.ai_think_timer -= 1
                path_interval = 18 if self.stuck_timer > 0 else (30 if dist > 800 else 20 if dist > 400 else 12)
                self.path_timer -= 1
                needs_pathfind = (self.path_timer <= 0 or not self.path or self.ai_think_timer <= 0)
                if use_direct or dist < 400:
                    if needs_pathfind:
                        self.path_timer = path_interval
                        self.ai_think_timer = path_interval
                        if not use_direct:
                            self.path = self._find_path(grid, int(player_pos[0] // TILE), int(player_pos[1] // TILE))
                        else:
                            self.path = []
                if self.path:
                    nw = self.path[0]
                    wx = nw[1] * TILE + TILE // 2
                    wy = nw[0] * TILE + TILE // 2
                    wdx = wx - self.pos.x
                    wdy = wy - self.pos.y
                    wd = math.hypot(wdx, wdy)
                    if wd < TILE * 0.4:
                        self.path.pop(0)
                        if self.path:
                            nw = self.path[0]
                            wx = nw[1] * TILE + TILE // 2
                            wy = nw[0] * TILE + TILE // 2
                            wdx = wx - self.pos.x
                            wdy = wy - self.pos.y
                            wd = math.hypot(wdx, wdy)
                    if wd > 1:
                        nx = self.pos.x + (wdx / wd) * move_spd + sep.x
                        ny = self.pos.y + (wdy / wd) * move_spd + sep.y
                        self._step_move(nx, ny, grid)
                else:
                    nx = self.pos.x + (dx / dist) * move_spd + sep.x
                    ny = self.pos.y + (dy / dist) * move_spd + sep.y
                    self._step_move(nx, ny, grid)
            else:
                # Direct movement (away from player if retreating)
                dir_x = (-dx / dist) if retreating else (dx / dist)
                dir_y = (-dy / dist) if retreating else (dy / dist)
                nx = self.pos.x + dir_x * move_spd + sep.x
                ny = self.pos.y + dir_y * move_spd + sep.y
                self._step_move(nx, ny, grid)
            if self.etype == "shooter" and dist < 280 and enemy_bullets is not None:
                self.shooter_timer = min(self.shooter_timer, 5)

        self.pos.x = max(self.radius, min(self.map_w - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(self.map_h - self.radius, self.pos.y))
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        self.bob_phase += 0.06
        self.rect.centery = int(self.pos.y + math.sin(self.bob_phase) * 2)

    def trigger_dodge(self, bullet_angle):
        self.dodge_timer = 12
        self.dodge_angle = bullet_angle + math.pi / 2 + random.uniform(-0.5, 0.5)

    # IA completa del jefe Vicente: 4 fases con patrones crecientes
    def _update_vicente_boss(self, player_pos, enemies, enemy_bullets, particles, grid):
        hp_r = self.hp / self.max_hp
        # Phase
        new_ph = 4 if hp_r <= 0.25 else 3 if hp_r <= 0.50 else 2 if hp_r <= 0.75 else 1
        if new_ph > self._vb_phase:
            self._vb_phase = new_ph
        ph = self._vb_phase
        # Shield blue (phase 1-2)
        if ph <= 2:
            self._vb_shield_cooldown -= 1
            if self._vb_shield_active:
                self._vb_shield_timer -= 1
                if self._vb_shield_timer <= 0:
                    self._vb_shield_active = False
            elif self._vb_shield_cooldown <= 0:
                self._vb_shield_active = True
                self._vb_shield_timer = 120
                self._vb_shield_cooldown = 480
        # Knockback
        if self.kb.length() > 0.1:
            kp = self.pos + self.kb
            if grid is not None:
                move_with_collision(self.pos, kp.x, kp.y, grid, self.radius)
            else:
                self.pos = kp
            self.kb *= 0.85
            if self.kb.length() < 0.1:
                self.kb = pygame.Vector2(0, 0)
        else:
            self.kb = pygame.Vector2(0, 0)
        # Timers
        self._vb_attack_timer -= 1
        self._vb_special_timer -= 1
        self._vb_summon_timer -= 1
        self._vb_teleport_timer -= 1
        self._vb_charge_timer -= 1
        self._vb_domain_timer -= 1
        self._vb_domain_cooldown -= 1
        self._vb_rar_timer -= 1
        self._vb_compress_timer -= 1
        self._vb_bomb_timer -= 1
        self._vb_extract_timer -= 1
        self._vb_syntax_timer -= 1
        self._vb_domain_pulse += 1
        # Direction to player for bullet patterns
        ang_to_player = math.atan2(player_pos.y - self.pos.y, player_pos.x - self.pos.x)
        # ── Phase 1: Dispara snippets de código (patrón circular creciente) ──
        if self._vb_attack_timer <= 0 and enemy_bullets is not None:
            if ph == 1:
                n = 4
                spread = 0.3
                cd = 72
                spd = 5
            elif ph == 2:
                n = 6
                spread = math.tau / n
                cd = 60
                spd = 5.5
            elif ph == 3:
                n = 10
                spread = math.tau / n
                cd = 36
                spd = 6
            else:
                n = 12
                spread = math.tau / n
                cd = 30
                spd = 6.5
            for i in range(n):
                a = self._vb_domain_pulse * 0.02 + (math.tau * i / n if spread >= 0.5 else (ang_to_player if i == 0 else ang_to_player + spread * (i - n/2)))
                nv = pygame.Vector2(math.cos(a), math.sin(a)) * spd
                enemy_bullets.append(EnemyBullet(self.pos.copy(), nv, 10 + ph * 2))
            self._vb_attack_timer = cd
        # ── Phase 2+: Invoca ImportSnippets (snakes de código) ──
        if ph >= 2 and self._vb_summon_timer <= 0:
            n_snippets = {2: 2, 3: 3, 4: 6}.get(ph, 2)
            for _ in range(n_snippets):
                off = pygame.Vector2(random.uniform(-30, 30), random.uniform(-30, 30))
                sn = ImportSnippet(self.pos + off, self.map_w, self.map_h)
                self._vb_snippets.append(sn)
                if self.all_sprites_ref is not None:
                    self.all_sprites_ref.add(sn)
            self._vb_summon_timer = {2: 480, 3: 360, 4: 120}.get(ph, 480)
        # ── Phase 2+: Teletransportación con partículas ──
        if ph >= 2 and self._vb_teleport_timer <= 0:
            a = random.uniform(0, math.tau)
            d = random.uniform(100, 250)
            nx = player_pos[0] + math.cos(a) * d
            ny = player_pos[1] + math.sin(a) * d
            nx = max(self.radius, min(self.map_w - self.radius, nx))
            ny = max(self.radius, min(self.map_h - self.radius, ny))
            if grid is None or not is_wall(grid, int(nx // TILE), int(ny // TILE)):
                if particles:
                    for _ in range(15):
                        a2 = random.uniform(0, math.tau)
                        sp2 = random.uniform(2, 5)
                        particles.append(Particle(self.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2, (100, 200, 255), random.uniform(3, 5), random.randint(10, 20)))
                self.pos = pygame.Vector2(nx, ny)
                if particles:
                    for _ in range(15):
                        a2 = random.uniform(0, math.tau)
                        sp2 = random.uniform(2, 5)
                        particles.append(Particle(self.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2, (150, 220, 255), random.uniform(3, 5), random.randint(10, 20)))
            self._vb_teleport_timer = {2: 300, 3: 240, 4: 180}.get(ph, 300)
        # ── Phase 3+: Expansión de dominio (ráfagas circulares) ──
        if ph >= 3:
            if self._vb_domain_cooldown <= 0 and not self._vb_domain_active:
                self._vb_domain_active = True
                self._vb_domain_timer = 600
                if particles:
                    for _ in range(30):
                        a2 = random.uniform(0, math.tau)
                        sp2 = random.uniform(3, 8)
                        particles.append(Particle(self.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2, (100, 200, 255), random.uniform(4, 7), random.randint(20, 40)))
            if self._vb_domain_active:
                self._vb_domain_timer -= 1
                if self._vb_domain_timer <= 0:
                    self._vb_domain_active = False
                    self._vb_domain_cooldown = 300
                if self._vb_domain_timer % 30 == 0 and enemy_bullets is not None:
                    n = 8 if ph == 3 else 12
                    for i in range(n):
                        a = math.tau * i / n + self._vb_domain_pulse * 0.05
                        nv = pygame.Vector2(math.cos(a), math.sin(a)) * 4.5
                        enemy_bullets.append(EnemyBullet(self.pos.copy(), nv, 8 + ph))
            if ph == 4:
                if not self._vb_domain_active:
                    self._vb_domain_active = True
        # ── Phase 3+: Muro de sintaxis (lluvia de balas horizontal/vertical) ──
        if ph >= 3 and self._vb_syntax_timer <= 0 and enemy_bullets is not None:
            horiz = random.random() < 0.5
            n = 10
            for i in range(n):
                if horiz:
                    frac = i / n
                    bx = 50 + frac * (self.map_w - 100)
                    by = player_pos[1] + random.uniform(-30, 30)
                    nv = pygame.Vector2(0, 5)
                else:
                    frac = i / n
                    bx = player_pos[0] + random.uniform(-30, 30)
                    by = 50 + frac * (self.map_h - 100)
                    nv = pygame.Vector2(5, 0)
                enemy_bullets.append(EnemyBullet(pygame.Vector2(bx, by), nv, 15 + ph * 3))
            self._vb_syntax_timer = 600
        # ── Phase 4: Ataques WinRAR (compress, bomb, shield, extract, last stand) ──
        if ph == 4:
            if self._vb_compress_timer <= 0 and enemy_bullets is not None:
                dx = player_pos[0] - self.pos.x
                dy = player_pos[1] - self.pos.y
                d = math.hypot(dx, dy)
                if d > 5:
                    nv = pygame.Vector2(dx / d, dy / d) * 5
                    enemy_bullets.append(EnemyBullet(self.pos.copy(), nv, 25))
                    self._vb_compress_timer = 300
            if self._vb_bomb_timer <= 0 and enemy_bullets is not None:
                a = math.atan2(player_pos[1] - self.pos.y, player_pos[0] - self.pos.x)
                nv = pygame.Vector2(math.cos(a), math.sin(a)) * 3
                eb = EnemyBullet(self.pos.copy(), nv, 40)
                eb.radius = 8
                eb._vb_bomb = True
                enemy_bullets.append(eb)
                self._vb_bomb_timer = 480
            if self._vb_rar_shield:
                self._vb_rar_timer -= 1
                if self._vb_rar_timer <= 0:
                    self._vb_rar_shield = False
            elif self._vb_shield_cooldown <= 0:
                self._vb_rar_shield = True
                self._vb_rar_timer = 240
                self._vb_shield_cooldown = 600
            if self._vb_extract_timer <= 0 and self.all_sprites_ref is not None:
                for _ in range(3):
                    a2 = random.uniform(0, math.tau)
                    d2 = random.uniform(40, 80)
                    epos = self.pos + pygame.Vector2(math.cos(a2), math.sin(a2)) * d2
                    e2 = Enemy("runner", self.map_w, self.map_h, 30, player_pos, grid)
                    e2.pos = epos
                    e2.rect.center = (int(epos.x), int(epos.y))
                    self.all_sprites_ref.add(e2)
                    if self.enemies_ref is not None:
                        self.enemies_ref.add(e2)
                self._vb_extract_timer = 480
            # Last stand: se cura ~8% y lanza ataque final al 5% HP
            if not self._vb_last_stand and hp_r <= 0.05:
                self._vb_last_stand = True
                self.hp = min(self.max_hp, self.hp + int(self.max_hp * 0.08))
                self.pos = pygame.Vector2(self.map_w // 2, self.map_h // 2)
                if particles:
                    for _ in range(60):
                        a2 = random.uniform(0, math.tau)
                        sp2 = random.uniform(3, 10)
                        particles.append(Particle(self.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2, (100, 200, 255), random.uniform(4, 8), random.randint(20, 50)))
                if enemy_bullets is not None:
                    for i in range(40):
                        a = math.tau * i / 40
                        nv = pygame.Vector2(math.cos(a), math.sin(a)) * 6
                        enemy_bullets.append(EnemyBullet(self.pos.copy(), nv, 20))
                for _ in range(6):
                    off = pygame.Vector2(random.uniform(-60, 60), random.uniform(-60, 60))
                    sn = ImportSnippet(self.pos + off, self.map_w, self.map_h)
                    self._vb_snippets.append(sn)
                    if self.all_sprites_ref is not None:
                        self.all_sprites_ref.add(sn)
        # ── Movement toward player ──
        dx = player_pos[0] - self.pos.x
        dy = player_pos[1] - self.pos.y
        dist = math.hypot(dx, dy)
        move_spd = self.speed * self.speed_mult
        if ph == 2: move_spd *= 1.25
        elif ph == 3: move_spd *= 1.3
        elif ph == 4: move_spd *= 1.6
        # Charge
        if ph >= 3 and self._vb_charge_timer <= 0:
            if dist > 5:
                self._vb_charging = True
                self._vb_charge_timer = 30
        if self._vb_charging:
            if dist > 5:
                ch_spd = move_spd * (5 if ph == 4 else 3)
                nx = self.pos.x + (dx / dist) * ch_spd
                ny = self.pos.y + (dy / dist) * ch_spd
                if grid is not None:
                    move_with_collision(self.pos, nx, ny, grid, self.radius)
                else:
                    self.pos.x = nx; self.pos.y = ny
            self._vb_charge_timer -= 1
            if self._vb_charge_timer <= 0:
                self._vb_charging = False
                self._vb_charge_timer = {3: 120, 4: 60}.get(ph, 90)
            self.rect.center = (int(self.pos.x), int(self.pos.y))
            return
        # Normal movement
        if dist > 5:
            sep = pygame.Vector2(0, 0)
            if enemies:
                for e in enemies:
                    if e is self: continue
                    dd = self.pos.distance_to(e.pos)
                    if dd < self.radius + getattr(e, "radius", 0) + 5 and dd > 0.5:
                        sep += (self.pos - e.pos) / dd * 0.3
            if grid is not None:
                nx = self.pos.x + (dx / dist) * move_spd + sep.x
                ny = self.pos.y + (dy / dist) * move_spd + sep.y
                move_with_collision(self.pos, nx, ny, grid, self.radius)
            else:
                self.pos.x += (dx / dist) * move_spd + sep.x
                self.pos.y += (dy / dist) * move_spd + sep.y
        self.pos.x = max(self.radius, min(self.map_w - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(self.map_h - self.radius, self.pos.y))
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    # BFS básico para pathfinding hacia el jugador
    def _find_path(self, grid, target_col, target_row, max_steps=120):
        sc = int(self.pos.x // TILE); sr = int(self.pos.y // TILE)
        if (sr, sc) == (target_row, target_col):
            return []
        import heapq
        # A* with 8-directional movement and Manhattan heuristic
        start = (sr, sc)
        goal = (target_row, target_col)
        heap = [(0, 0, start)]
        g_cost = {start: 0}
        prev = {start: None}
        steps = 0
        # 8 directions: cardinal + diagonal
        dirs = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
        while heap:
            steps += 1
            if steps > max_steps:
                return []
            _, _, cur = heapq.heappop(heap)
            if cur == goal:
                path = []
                while cur != start:
                    path.append(cur)
                    cur = prev[cur]
                path.reverse()
                return path
            r, c = cur
            for dr, dc in dirs:
                nr, nc = r+dr, c+dc
                if not (0 <= nr < ROWS and 0 <= nc < COLS):
                    continue
                if is_wall(grid, nc, nr):
                    continue
                # Diagonal movement check: both adjacent cells must be walkable
                if dr != 0 and dc != 0:
                    if is_wall(grid, nc-dr, nr) and is_wall(grid, nc, nr-dc):
                        continue
                move_cost = 14 if dr != 0 and dc != 0 else 10  # diagonal cost ~1.4x
                ng = g_cost[cur] + move_cost
                if (nr, nc) not in g_cost or ng < g_cost[(nr, nc)]:
                    g_cost[(nr, nc)] = ng
                    f = ng + abs(nr - target_row) * 10 + abs(nc - target_col) * 10
                    heapq.heappush(heap, (f, steps, (nr, nc)))
                    prev[(nr, nc)] = cur
        return []

    # Dibuja la barra de vida coloreada (verde/amarillo/rojo)
    def draw_hp(self, surf, cx, cy):
        bw = self.radius * 2; bh = 3
        x = self.pos.x - bw // 2 - cx
        y = self.pos.y - self.radius - 6 - cy
        r = self.hp / self.max_hp
        pygame.draw.rect(surf, (20, 20, 20), (x, y, bw, bh))
        pygame.draw.rect(surf, (0, 200, 100) if r > 0.5 else (255, 200, 50) if r > 0.25 else (255, 50, 50), (x, y, int(bw * r), bh))

    # Daño directo (sin knockback)
    def take_damage(self, amount):
        self.hp -= amount
        self.hp = max(self.hp, 0)


# Muro desplegable del jugador (ability "muro")
# Muro desplegable del jugador (ability "muro")
class Wall:
    def __init__(self, pos, player, radius=60):
        # Inicializa muro con HP basado en el personaje
        self.pos = pygame.Vector2(pos)
        self.radius = radius
        self.player = player
        hp_mult = getattr(player, "_wall_hp_mult", 1.0)
        self.hp = int(300 * hp_mult)
        self.max_hp = int(300 * hp_mult)
        self.timer = 900
        self._redraw()

    def _redraw(self):
        r = self.radius
        ratio = self.hp / self.max_hp
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        br = (80, 60, 40) if ratio > 0.5 else (120, 40, 30) if ratio > 0.25 else (60, 20, 15)
        pygame.draw.rect(s, br, (2, 2, r * 2 - 4, r * 2 - 4), border_radius=4)
        for row in range(3):
            for col in range(4):
                ox = 4 + col * (r * 2 - 8) // 4
                oy = 4 + row * (r * 2 - 8) // 3
                pygame.draw.rect(s, tuple(min(255, x + 30) for x in br), (ox, oy, (r * 2 - 8) // 4 - 2, (r * 2 - 8) // 3 - 2), border_radius=2)
        edges = int(ratio * 255)
        pygame.draw.rect(s, (edges, max(0, edges - 80), 0, 180), (0, 0, r * 2, r * 2), 2, border_radius=4)
        self.image = s

    # Recibe daño, redibuja si sigue vivo
    def hit(self, dmg):
        self.hp -= dmg
        if self.hp <= 0:
            return True
        self._redraw()
        return False

    # Reduce timer, decae si expira
    def update(self):
        self.timer -= 1
        if self.timer <= 0 and self.hp > 0:
            self.hp -= 1
            self._redraw()
        return self.timer > 0 and self.hp > 0

    # Dibuja el muro con textura de ladrillos
    def draw(self, surf, cx, cy):
        px = int(self.pos.x - cx)
        py = int(self.pos.y - cy)
        surf.blit(self.image, (px - self.radius, py - self.radius))


# NPC aliado Billie Eilish (atrapa y daña enemigos)
class BillieNPC(pygame.sprite.Sprite):
    def __init__(self, pos, map_w=MAP_W, map_h=MAP_H):
        # Inicializa NPC cantante con atracción y daño cuerpo a cuerpo
        super().__init__()
        self.pos = pygame.Vector2(pos)
        self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        self.map_w = map_w
        self.map_h = map_h
        self.hp = 500
        self.max_hp = 500
        self.speed = 1.8
        self.radius = 18
        self.color = (255, 80, 200)
        self.attract_range = 300
        self.sing_timer = 0
        self.hp_regen = 0.2
        self.target = None
        self.damage = 25
        self.attack_cd = 0

    # Persigue al enemigo más cercano, lo atrae y ataca
    def update(self, enemies, grid=None):
        if self.hp <= 0:
            return False
        self.attack_cd = max(0, self.attack_cd - 1)
        self.sing_timer += 1
        self.hp = min(self.max_hp, self.hp + self.hp_regen)
        nearest = None
        nd = self.attract_range
        for e in enemies:
            if not hasattr(e, "hp") or e.hp <= 0: continue
            d = self.pos.distance_to(e.pos)
            if d < nd:
                nd = d
                nearest = e
        if nearest:
            dx = nearest.pos.x - self.pos.x
            dy = nearest.pos.y - self.pos.y
            dist = math.hypot(dx, dy)
            if dist > self.radius + nearest.radius + 5:
                nx = self.pos.x + (dx / dist) * self.speed
                ny = self.pos.y + (dy / dist) * self.speed
                if grid is not None:
                    move_with_collision(self.pos, nx, ny, grid)
                else:
                    self.pos.x = nx; self.pos.y = ny
            if dist < self.attract_range:
                e_dir = pygame.Vector2(nearest.pos - self.pos)
                if e_dir.length() > 0:
                    e_dir.scale_to_length(0.5)
                    nearest.pos += e_dir
            if self.attack_cd <= 0 and dist < self.radius + nearest.radius + 20:
                nearest.hit(self.damage)
                self.attack_cd = 20
        if self.sing_timer >= 180:
            self.sing_timer = 0
        self.pos.x = max(self.radius, min(self.map_w - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(self.map_h - self.radius, self.pos.y))
        return None

    # Dibuja a Billie con barra de vida
    def draw(self, surf, cx, cy):
        px = int(self.pos.x - cx)
        py = int(self.pos.y - cy)
        r = self.radius
        pygame.draw.circle(surf, (100, 30, 80), (px, py), r + 2)
        pygame.draw.circle(surf, self.color, (px, py), r)
        pygame.draw.circle(surf, (200, 60, 160), (px, py), r - 4)
        f = pygame.font.Font(None, 20)
        s = f.render("B", True, (255, 255, 255))
        surf.blit(s, (px - s.get_width() // 2, py - s.get_height() // 2))
        bw = r * 2; bh = 3
        hx = px - bw // 2
        hy = py - r - 6
        r_ratio = self.hp / self.max_hp
        pygame.draw.rect(surf, (20, 20, 20), (hx, hy, bw, bh))
        pygame.draw.rect(surf, (255, 80, 200), (hx, hy, int(bw * r_ratio), bh))


# Guitar Wave que daña enemigos (ability guitar_riff)
class Tornado:
    def __init__(self, pos, angle, map_w=MAP_W, map_h=MAP_H):
        self.pos = pygame.Vector2(pos)
        self.angle = angle
        self.vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * 4
        self.lifetime = 90
        self.radius = 45
        self.damage = 15
        self.pull_radius = 100
        self.grabbed = []
        self.map_w = map_w
        self.map_h = map_h

    # Mueve el tornado, rebota en paredes, reduce vida
    def update(self, grid=None):
        self.pos += self.vel
        self.lifetime -= 1
        if grid is not None:
            col, row = world_to_tile(self.pos.x, self.pos.y)
            if is_wall(grid, col, row):
                self.vel.x = -self.vel.x * 0.8
                self.vel.y = -self.vel.y * 0.8
                self.pos += self.vel
        if self.pos.x < self.radius or self.pos.x > self.map_w - self.radius:
            self.vel.x = -self.vel.x * 0.8
            self.pos.x = max(self.radius, min(self.map_w - self.radius, self.pos.x))
        if self.pos.y < self.radius or self.pos.y > self.map_h - self.radius:
            self.vel.y = -self.vel.y * 0.8
            self.pos.y = max(self.radius, min(self.map_h - self.radius, self.pos.y))
        self.grabbed = [e for e in self.grabbed if hasattr(e, "hp") and e.hp > 0]

    # Dibuja el tornado con partículas giratorias y anillos
    def draw(self, surf, cx, cy):
        px = int(self.pos.x - cx)
        py = int(self.pos.y - cy)
        t = pygame.time.get_ticks() * 0.008
        for i in range(10):
            a = t + i * 0.628
            r_offset = self.radius * (0.3 + 0.7 * (1 - i * 0.08))
            ox = int(math.cos(a) * r_offset)
            oy = int(math.sin(a) * r_offset) - i * 3
            r_ball = max(2, int(self.radius * 0.35 - i * 1.2))
            alpha = max(30, 180 - i * 16)
            clr = (100 + i * 12, 100 + i * 12, 255 - i * 10, alpha)
            s = pygame.Surface((r_ball * 2,) * 2, pygame.SRCALPHA)
            pygame.draw.circle(s, clr, (r_ball, r_ball), r_ball)
            surf.blit(s, (px + ox - r_ball, py + oy - r_ball))
        for i in range(5):
            a2 = t * 0.7 + i * 1.257
            r2 = self.pull_radius * 0.3 + i * 12
            ox2 = int(math.cos(a2) * r2)
            oy2 = int(math.sin(a2) * r2)
            pygame.draw.circle(surf, (180, 180, 255, 20 + i * 8), (px + ox2, py + oy2), max(2, 6 - i))


# Esbirro cerebral que persigue y daña enemigos (ability brainrot)
# Esbirro cerebral que persigue y daña enemigos (ability brainrot)
class BrainrotMinion(pygame.sprite.Sprite):
    _brainrot_imgs = []

    @classmethod
    def _load_brainrot_imgs(cls):
        if cls._brainrot_imgs:
            return
        from src.sprites import load_image
        for i in range(3):
            img = load_image(f"enemies/brainrot_{i}.png", cache_key=f"brainrot_{i}_raw")
            cls._brainrot_imgs.append(img)

    def __init__(self, pos, player, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        self.pos = pygame.Vector2(pos)
        self.player = player
        self.hp = 60
        self.max_hp = 60
        self.speed = 2.5
        self.radius = 12
        self.color = (180, 50, 255)
        self.damage = 8
        self.attack_cooldown = 0
        self.map_w = map_w
        self.map_h = map_h
        self.image = pygame.Surface((self.radius * 2,) * 2, pygame.SRCALPHA)
        self._img_idx = random.randint(0, 2)
        self._redraw()
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def _redraw(self):
        self.image.fill((0, 0, 0, 0))
        self._load_brainrot_imgs()
        custom = self._brainrot_imgs[self._img_idx]
        if custom is not None:
            r = self.radius
            target = r * 2 - 2
            scale = min(target / custom.get_width(), target / custom.get_height(), 1)
            nw = max(1, int(custom.get_width() * scale))
            nh = max(1, int(custom.get_height() * scale))
            scaled = pygame.transform.smoothscale(custom, (nw, nh))
            mask = pygame.Surface((nw, nh), pygame.SRCALPHA)
            cx, cy = nw // 2, nh // 2
            cr = min(cx, cy)
            pygame.draw.circle(mask, (255, 255, 255, 255), (cx, cy), cr)
            mask.blit(scaled, (0, 0), None, pygame.BLEND_RGBA_MULT)
            dx = r - mask.get_width() // 2
            dy = r - mask.get_height() // 2
            self.image.blit(mask, (dx, dy))
            return
        # Fallback procedural
        r = self.radius
        pygame.draw.circle(self.image, (60, 20, 80), (r, r), r)
        pygame.draw.circle(self.image, self.color, (r, r), r - 2)
        pygame.draw.circle(self.image, (100, 30, 150), (r, r), r - 4)
        pygame.draw.circle(self.image, RED, (r - 3, r - 3), 2)
        pygame.draw.circle(self.image, RED, (r + 3, r - 3), 2)
        pygame.draw.circle(self.image, (255, 255, 255), (r - 3, r - 3), 1)
        pygame.draw.circle(self.image, (255, 255, 255), (r + 3, r - 3), 1)

    # Busca al enemigo más cercano, lo persigue y ataca
    def update(self, enemies, player_pos, grid=None):
        target = None
        td = 300
        for e in enemies:
            if not hasattr(e, "hp") or e.hp <= 0: continue
            d = self.pos.distance_to(e.pos)
            if d < td:
                td = d
                target = e
        if target:
            dx = target.pos.x - self.pos.x
            dy = target.pos.y - self.pos.y
            dist = math.hypot(dx, dy)
            if dist > self.radius + target.radius + 2:
                nx = self.pos.x + (dx / dist) * self.speed
                ny = self.pos.y + (dy / dist) * self.speed
                if grid is not None:
                    move_with_collision(self.pos, nx, ny, grid)
                else:
                    self.pos.x = nx; self.pos.y = ny
            elif self.attack_cooldown <= 0:
                target.hp -= self.damage
                self.attack_cooldown = 30
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
        self.pos.x = max(self.radius, min(self.map_w - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(self.map_h - self.radius, self.pos.y))
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    # Dibuja barra de vida morada
    def draw_hp(self, surf, cx, cy):
        bw = self.radius * 2; bh = 3
        x = self.pos.x - bw // 2 - cx
        y = self.pos.y - self.radius - 6 - cy
        r = self.hp / self.max_hp
        pygame.draw.rect(surf, (20, 20, 20), (x, y, bw, bh))
        pygame.draw.rect(surf, (180, 50, 255) if r > 0.5 else (255, 100, 50), (x, y, int(bw * r), bh))


# Esbirro de chochox con mayor HP y daño
class ChochoxMinion(pygame.sprite.Sprite):
    def __init__(self, pos, player, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        # Inicializa minion chochox: HP 150, daño 20, radio 18
        self.pos = pygame.Vector2(pos)
        self.player = player
        self.hp = 150
        self.max_hp = 150
        self.speed = 2.2
        self.radius = 18
        self.color = (200, 50, 150)
        self.damage = 20
        self.attack_cooldown = 0
        self.map_w = map_w
        self.map_h = map_h
        self.image = pygame.Surface((self.radius * 2,) * 2, pygame.SRCALPHA)
        self._redraw()
        self.invuln_timer = 0
        self.shield = 0
        self.hit_flash = 0
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def _redraw(self):
        self.image.fill((0, 0, 0, 0))
        r = self.radius
        pygame.draw.circle(self.image, (80, 20, 60), (r, r), r)
        pygame.draw.circle(self.image, self.color, (r, r), r - 2)
        pygame.draw.circle(self.image, (150, 30, 110), (r, r), r - 4)
        pygame.draw.circle(self.image, RED, (r - 6, r - 5), 4)
        pygame.draw.circle(self.image, RED, (r + 6, r - 5), 4)
        pygame.draw.circle(self.image, (255, 255, 255), (r - 6, r - 5), 2)
        pygame.draw.circle(self.image, (255, 255, 255), (r + 6, r - 5), 2)
        pygame.draw.arc(self.image, (255, 100, 200), (r - 5, r + 1, 10, 6), 0, math.pi, 2)

    # Persigue al enemigo más cercano y ataca cuerpo a cuerpo
    def update(self, enemies, player_pos, grid=None):
        target = None
        td = 350
        for e in enemies:
            if not hasattr(e, "hp") or e.hp <= 0: continue
            d = self.pos.distance_to(e.pos)
            if d < td:
                td = d
                target = e
        if target:
            dx = target.pos.x - self.pos.x
            dy = target.pos.y - self.pos.y
            dist = math.hypot(dx, dy)
            if dist > self.radius + target.radius + 2:
                nx = self.pos.x + (dx / dist) * self.speed
                ny = self.pos.y + (dy / dist) * self.speed
                if grid is not None:
                    move_with_collision(self.pos, nx, ny, grid)
                else:
                    self.pos.x = nx; self.pos.y = ny
            elif self.attack_cooldown <= 0:
                target.hp -= self.damage
                self.attack_cooldown = 20
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
        self.pos.x = max(self.radius, min(self.map_w - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(self.map_h - self.radius, self.pos.y))
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    # Dibuja la barra de vida sobre el enemigo
    def draw_hp(self, surf, cx, cy):
        bw = self.radius * 2; bh = 3
        x = self.pos.x - bw // 2 - cx
        y = self.pos.y - self.radius - 6 - cy
        r = self.hp / self.max_hp
        pygame.draw.rect(surf, (20, 20, 20), (x, y, bw, bh))
        pygame.draw.rect(surf, (0, 200, 100) if r > 0.5 else (255, 200, 50) if r > 0.25 else (255, 50, 50), (x, y, int(bw * r), bh))

    # Daño directo (sin knockback)
    def take_damage(self, amount):
        if self.invuln_timer > 0:
            return
        if self.shield > 0:
            absorbed = min(self.shield, amount)
            self.shield -= absorbed
            amount -= absorbed
        self.hp -= amount
        self.hp = max(self.hp, 0)
        self.hit_flash = LIGHT_FLASH_DURATION
        self.invuln_timer = 10

class Player(pygame.sprite.Sprite):
    """Clase principal del jugador. Maneja movimiento, disparo, habilidades, dominio y 3 modos Vicente."""
    def __init__(self, char_id, pos, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        self.pos = pygame.Vector2(pos) if not isinstance(pos, pygame.Vector2) else pygame.Vector2(pos)
        self.map_w = map_w
        self.map_h = map_h
        self.char_id = char_id
        cd = CHARACTERS.get(char_id, CHARACTERS["irvin"])
        self.char_data = cd
        self.radius = 17
        self.hp = cd["hp"]
        self.max_hp = cd["max_hp"]
        self.bonus_max_hp = 0
        self.base_speed = cd["speed"]
        self.bonus_speed = 0.0
        self.stamina = cd["stamina"]
        self.max_stamina = cd["stamina"]
        self.angle = 0.0
        self.lerp_angle = 0.0
        self.damage = cd["dmg"]
        self.bonus_damage = 0
        self.dmg_mult = 1.0
        self.fire_rate = cd["fr"]
        self.fr_mult = 1.0
        self.spread = cd.get("spr", 0.04)
        self.shots = cd["shots"]
        self.extra_shots = 0
        self.bonus_firerate = 0
        self.bonus_mag = 0
        self.bonus_reload = 0
        self.bonus_hp = 0
        self.mag = cd["mag"]
        self.max_mag = cd["mag"]
        self.bonus_mag = 0
        self.reserve = cd["reserve"]
        self.reload_time = cd["reload"]
        self.reload_mult = 1.0
        self.reloading = False
        self.reload_timer = 0
        self.piercing = 0
        self.lifesteal = 0.0
        self.knockback = 0.0
        self.vampirism = 0.0
        self.vampire = 0
        self.display_hp = self.hp
        self.ability_name = cd.get("ability", "aplastar")
        self.ability_max_cd = cd.get("cd", 25000)
        self.ability_cd = 0
        self.ability_active = False
        self.ability_duration = 0
        self.ability_charge = 0
        self.ability_max_charge = ULT_CHARGE_MAX
        self.ability_damage_mult = 1.0
        self.ability_damage_timer = 0
        self.ability_speed = 1.0
        self.ability_speed_timer = 0
        self.passive_bytes = 0
        self.bytes = 0
        self.byte_multiplier = 1.0
        self.byte_mult_timer = 0
        self.level = 0
        self.xp = 0
        self.xp_next = 30
        self.kills = 0
        self.score = 0
        self._passive_stat = cd.get("passive")
        self.shoot_timer = 0
        self.turbo_timer = 0
        self.shield_timer = 0
        self.shield = 0
        self.explosive_timer = 0
        self.light_flash_timer = 0
        self.hit_flash = 0
        self.invuln_timer = 0
        self.shake = 0
        self.weapon_idx = 0
        self.weapon_mode = "auto"
        self.weapon_list = list(WEAPON_BULLETS.keys())
        self._prev_weapon_keys = [False] * 4
        self._prev_q_key = False
        self._prev_z_key = False
        self._prev_x_key = False
        self._prev_c_key = False
        self._prev_bomb_key = False
        self.inventory = []
        self.evolution_items = {}
        self.evolved = False
        self.chaos_items = []
        self.auras = []
        self.unique_items = []
        self.shop_levels = {}
        self.bomb_queue = []
        self.bomb_owned = set()
        self.bomb_count = 0
        self.bomb_active_idx = 0
        self.lasers = []
        self.bombs = []
        self.walls = []
        self.tornado = None
        self.billie_npc = None
        self.active_brainrots = []
        self.active_snippets = []
        self.domain_active = False
        self.domain_timer = 0
        self.domain_effect = None
        self.domain_kills_needed = 40
        self.domain_kills = 0
        self.domain_cd = 0
        self.domain_cd_timer = 0
        self.domain_charge = 0
        self.ult_charging = False
        self.ult_charge = 0
        self.charge_kills = 0
        self.charge_max = 40
        self.ult_ready = False
        self.ult_laser_active = False
        self.ult_laser_timer = 0
        self.ult_laser_angle = 0.0
        self.combo_counter = 0
        self._last_combo_time = 0
        self.combo_timer = 0
        self.combo_text = ""
        self.combo_text_timer = 0
        self.rebotar_timer = 0
        self.rebotar_bounces = 0
        self.bounce = 0
        self.ian_phase = 0
        self.beam_start = None
        self.beam_end = None
        self.beam_w = 0
        self._robar_buff = False
        self._ult_buff = False
        self._bolillo_buff = False
        self._wall_hp_mult = 1.0
        self.vicente_mode = 0
        self.vicente_mode_names = ["IMPORT", "COMPILE", "DEBUG"]
        self.vicente_mode_colors = [(100, 200, 255), (255, 80, 80), (80, 255, 120)]
        self.vicente_domain_names = ["LEALTAD A PYTHON", "COMPILE TIME ERROR", "DEBUG ZONE"]
        self.invulnerable = False
        self.image = pygame.Surface((self.radius * 2,) * 2, pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def add_xp(self, amount):

        self.xp += amount

        if self.xp >= self.xp_next:

            self.xp -= self.xp_next

            self.level += 1

            self.xp_next = int(self.xp_next * 1.3) + 20

            self.max_hp += 10

            self.hp = min(self.hp + 10, self.max_hp)

            self.damage += 1

            s = self._passive_stat

            if s is not None:

                scale = PASSIVE_SCALE.get(s)

                if scale is not None and scale != 0:

                    attr = PASSIVE_APPLY.get(s)

                    if attr is not None:

                        current = getattr(self, attr, 0)

                        if s in ("firerate", "reload"):

                            setattr(self, attr, current * scale)

                        elif attr == "bonus_max_hp":

                            self.bonus_max_hp += int(scale)

                            self.max_hp += int(scale)

                            self.hp = min(self.hp + int(scale), self.max_hp)

                        elif isinstance(current, int):

                            setattr(self, attr, current + int(scale))

                        else:

                            setattr(self, attr, current + scale)

            return True

        return False



    def apply_upgrade(self, upgrade_id):

        if upgrade_id == "firerate":

            self.fr_mult *= 0.9

        elif upgrade_id == "dmg":

            self.bonus_damage += 3

        elif upgrade_id == "hp":

            self.bonus_max_hp += 20

            self.max_hp += 20

            self.hp += 20

        elif upgrade_id == "multishot":

            self.shots += 1

        elif upgrade_id == "speed":

            self.bonus_speed += 0.1

        elif upgrade_id == "mag":

            self.max_mag += 5

            self.mag += 5

        elif upgrade_id == "reload":

            self.reload_mult *= 0.85

        elif upgrade_id == "piercing":

            self.piercing += 1

        elif upgrade_id == "lifesteal":

            self.lifesteal += 0.05

        elif upgrade_id == "knockback":

            self.knockback += 0.2



    def _ability_ready(self):

        if self.ability_name == "ninguno":

            return False

        return pygame.time.get_ticks() - self.ability_cd >= self.ability_max_cd



    def _start_ability_cd(self):

        self.ability_cd = pygame.time.get_ticks()



    def _ability_cd_remaining(self):

        return max(0, self.ability_max_cd - (pygame.time.get_ticks() - self.ability_cd))



    def _tick_ability_buffs(self, enemies=None, particles=None):

        if self.ability_active and self.ability_duration > 0:

            if self.ability_name == "buffer" and self.ian_phase == 1:

                beam_len = 420

                self.beam_start = self.pos.copy()

                self.beam_end = self.pos + pygame.Vector2(math.cos(self.angle), math.sin(self.angle)) * beam_len

                self.beam_w = 14

                self._tick_buffer_beam(enemies, particles)

            return

        if self.ability_active and self.ability_duration <= 0:

            self.ability_active = False

            if self.ability_name == "buffer":

                self.ian_phase = 0

            if self._robar_buff:

                self._robar_buff = False

                if self.byte_mult_timer <= 0:

                    self.byte_multiplier = 1.0

                if not self._ult_buff and not self._bolillo_buff:

                    self.dmg_mult = 1.0

            if self._bolillo_buff:

                self._bolillo_buff = False

                if not self._ult_buff:

                    self.dmg_mult = 1.0

            if self._ult_buff:

                self._ult_buff = False

                self.dmg_mult = 1.0



    def handle(self, keys, mouse_btn, mouse_pos, grid, all_sprites, bullets, particles, cam_x=0, cam_y=0, notifs=None, enemy_bullets=None, enemies=None, brainrots=None):

        if self.hp <= 0:

            return



        # Aiming (mouse_pos in screen coords, converted to world via cam_x, cam_y)

        self.angle = math.atan2(mouse_pos[1] - (self.pos.y - cam_y), mouse_pos[0] - (self.pos.x - cam_x))

        self.lerp_angle = self.angle



        # Movement

        move_x = 0.0

        move_y = 0.0

        if keys[pygame.K_w] or keys[pygame.K_UP]:

            move_y = -1

        if keys[pygame.K_s] or keys[pygame.K_DOWN]:

            move_y = 1

        if keys[pygame.K_a] or keys[pygame.K_LEFT]:

            move_x = -1

        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:

            move_x = 1



        sprint = keys[pygame.K_LSHIFT] and self.stamina > 0

        speed = (self.base_speed + self.bonus_speed) * self.ability_speed



        if move_x != 0 and move_y != 0:

            move_x *= 0.7071

            move_y *= 0.7071

            speed *= 0.85



        if sprint:

            speed *= 1.4

            self.stamina = max(0, self.stamina - 0.5)



        if move_x != 0 or move_y != 0:

            nx = self.pos.x + move_x * speed

            ny = self.pos.y + move_y * speed

            if grid is not None:

                move_with_collision(self.pos, nx, ny, grid, self.radius)

            else:

                self.pos.x = nx

                self.pos.y = ny

            if particles is not None and random.random() < 0.1:

                a = random.uniform(0, math.tau)

                particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * 0.5, (100, 255, 100, 80), random.uniform(1, 2), random.randint(8, 16)))

        else:

            self.stamina = min(self.max_stamina, self.stamina + 0.3)



        # Stamina regen

        self.stamina = min(self.max_stamina, self.stamina + 0.1)

        self.shoot_timer = max(0, self.shoot_timer - 1)



        # Reloading

        if self.reloading:

            self.reload_timer -= 1

            if self.reload_timer <= 0:

                needed = self.max_mag - self.mag

                available = min(needed, self.reserve)

                self.mag += available

                self.reserve -= available

                self.reloading = False

                if SFX and hasattr(SFX, "get"):

                    SFX["reload"].play()



        if keys[pygame.K_r] and not self.reloading and self.mag < self.max_mag and self.reserve > 0:

            self.reloading = True

            self.reload_timer = max(1, int(self.reload_time / 16.67 * self.reload_mult))



        # Weapon switching (edge-triggered)

        for i, wk in enumerate([pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]):

            pressed = keys[wk]

            if pressed and not self._prev_weapon_keys[i] and self.weapon_idx != i:

                self.weapon_idx = i

                self.weapon_mode = self.weapon_list[i]

                if SFX and hasattr(SFX, "get"):

                    SFX["click"].play()

            self._prev_weapon_keys[i] = pressed



        # Shooting (fr values are in milliseconds, convert to frames: / 16.67)

        wcfg = WEAPON_BULLETS[self.weapon_mode]

        current_fr = max(1, int(self.fire_rate / 16.67 * wcfg["fr_mult"] * self.fr_mult))

        if self.turbo_timer > 0:

            current_fr = max(1, current_fr // 2)



        if mouse_btn and self.shoot_timer <= 0 and not self.reloading:

            if self.mag <= 0:

                if self.reserve > 0:

                    self.reloading = True

                    self.reload_timer = max(1, int(self.reload_time / 16.67 * self.reload_mult * 0.5))

                    if SFX and hasattr(SFX, "get"):

                        SFX["empty"].play()

                self.shoot_timer = 10

            else:

                self.shoot_timer = current_fr

                self.mag -= 1

                bullet_dmg = int((self.damage + self.bonus_damage) * wcfg["dmg_mult"] * self.dmg_mult)

                bullet_spread = wcfg["spread"] if self.spread is None else (self.spread + wcfg["spread"])

                n_shots = self.shots

                if self.weapon_mode == "shotgun":

                    n_shots = wcfg["shots"]



                for i in range(n_shots):

                    a = self.angle + random.uniform(-bullet_spread, bullet_spread)

                    if self.weapon_mode == "sniper":

                        b = Bullet(self.pos, a, ">>", bullet_dmg, speed=24, spread=0, map_w=self.map_w, map_h=self.map_h, color=wcfg["color"])

                    elif self.weapon_mode == "pierce":

                        b = Bullet(self.pos, a, "->", bullet_dmg, speed=16, spread=0.02, map_w=self.map_w, map_h=self.map_h, color=wcfg["color"])

                    elif self.weapon_mode == "shotgun":

                        idx = random.randrange(len(wcfg["bullets"]))

                        txt, _ = wcfg["bullets"][idx]

                        b = Bullet(self.pos, a, txt, bullet_dmg, speed=14, spread=bullet_spread, map_w=self.map_w, map_h=self.map_h, color=wcfg["color"], life=10)

                    else:

                        idx = random.randrange(len(wcfg["bullets"]))

                        txt, _ = wcfg["bullets"][idx]

                        b = Bullet(self.pos, a, txt, bullet_dmg, speed=14, spread=bullet_spread, map_w=self.map_w, map_h=self.map_h, color=wcfg["color"])

                    b.pierce = self.piercing

                    if bullets is not None:

                        bullets.add(b)

                    if all_sprites is not None:

                        all_sprites.add(b)

                    # Set light flash timer for shooting effect

                    self.light_flash_timer = LIGHT_FLASH_DURATION



                if SFX and hasattr(SFX, "get"):

                     sname = self.weapon_mode if self.weapon_mode in ("sniper", "pierce", "shotgun") else "shoot"

                     SFX[sname].play()



        # Q Ability (cooldown in ms via pygame ticks)

        q_key = keys[pygame.K_q]

        if q_key and not self._prev_q_key and self._ability_ready():

            self._start_ability_cd()

            self._use_ability(particles, notifs, enemies, enemy_bullets, grid, all_sprites)

        elif q_key and not self._prev_q_key and self.ability_name == "ninguno" and notifs:

            notifs.append(Notif("Vicente no tiene Q - Usa [X] Dominio", (100, 200, 255), 90))

        self._prev_q_key = q_key



        # Z Ultimate

        self.charge_kills = self.ability_charge

        self.ult_ready = self.ability_charge >= self.ability_max_charge

        z_key = keys[pygame.K_z]

        if self.char_id == "eder":

            if self.ult_laser_active:

                self._tick_eder_laser(enemies, particles, grid)

                self.ult_laser_timer -= 1

                if self.ult_laser_timer <= 0:

                    self.ult_laser_active = False

                    self.ability_active = False

                    if SFX and hasattr(SFX, "get"):
                        SFX["guitar_riff"].stop()
                        SFX["eder_laser_loop"].stop()

            elif self.ability_charge >= self.ability_max_charge:

                if z_key:

                    if not self.ult_charging:

                        self.ult_charging = True

                        self.ult_charge = 0

                        if SFX and hasattr(SFX, "get"):
                            SFX["eder_charge"].play(loops=-1)

                    self.ult_charge = min(ULT_CHARGE_MAX, self.ult_charge + 1)

                    self.ult_laser_angle = self.angle

                elif self._prev_z_key and self.ult_charging:

                    if self.ult_charge >= MIN_ULT_CHARGE:

                        if SFX and hasattr(SFX, "get"):
                            SFX["eder_charge"].stop()

                        self._fire_eder_laser(particles, notifs, grid)
                    else:
                        if SFX and hasattr(SFX, "get"):
                            SFX["eder_charge"].stop()

                    self.ult_charging = False

                    self.ult_charge = 0

                elif self.ult_charging and self.ult_charge >= ULT_CHARGE_MAX:

                    if SFX and hasattr(SFX, "get"):
                        SFX["eder_charge"].stop()

                    self._fire_eder_laser(particles, notifs, grid)

                    self.ult_charging = False

                    self.ult_charge = 0

        elif z_key and not self._prev_z_key and self.ability_charge >= self.ability_max_charge:

            self.ability_charge = 0

            self.charge_kills = 0

            self.ult_ready = False

            self._use_ultimate(particles, notifs, enemies, all_sprites, grid)

        self._prev_z_key = z_key



        # C: Vicente mode switch (edge-triggered)

        c_key = keys[pygame.K_c]

        if c_key and not self._prev_c_key and self.char_id == "vicente":

            self._cycle_vicente_mode()

            if notifs is not None:

                mode_name = self.vicente_mode_names[self.vicente_mode]

                mode_col = self.vicente_mode_colors[self.vicente_mode]

                notifs.append(Notif(f"MODO: {mode_name}", mode_col, 60))

        self._prev_c_key = c_key



        # X Domain Expansion

        if self.domain_cd_timer > 0:

            self.domain_cd_timer -= 1

        self.domain_kills = self.domain_charge

        x_key = keys[pygame.K_x]

        domain_ready = (self.domain_charge >= self.domain_kills_needed

                        and not self.domain_active and self.domain_cd_timer <= 0)

        if x_key and not self._prev_x_key and domain_ready:

            self.domain_active = True

            self.domain_timer = DOMAIN_DURATION

            self.domain_charge = 0

            self.domain_kills = 0

            self.domain_cd_timer = DOMAIN_COOLDOWN

            if self.char_id == "vicente":

                self.domain_effect = ["python_import", "python_compile", "python_debug"][self.vicente_mode]

            else:

                self.domain_effect = DOMAIN_EXPANSION.get(self.char_id, {}).get("effect", "")

            if notifs is not None:

                if self.char_id == "vicente":

                    dom_name = self.vicente_domain_names[self.vicente_mode]

                    dom_col = self.vicente_mode_colors[self.vicente_mode]

                else:

                    domain_info = DOMAIN_EXPANSION.get(self.char_id, {})

                    dom_name = domain_info.get('name', 'EXPANSION')

                    dom_col = (255, 200, 50)

                notifs.append(Notif(f"DOMINIO: {dom_name}", dom_col, 90))

            if particles is not None:

                for _ in range(30):

                    a = random.uniform(0, math.tau)

                    sp = random.uniform(3, 6)

                    if self.char_id == "vicente":

                        dcol = self.vicente_mode_colors[self.vicente_mode]

                    else:

                        domain_info = DOMAIN_EXPANSION.get(self.char_id, {})

                        dcol = domain_info.get("color", (255, 200, 50))

                    particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                        dcol, random.uniform(3, 6), random.randint(15, 30)))

            SFX["transition"].play()
            if self.char_id == "eder":
                play_eder_domain_music()


        # Domain update

        if self.domain_active:

            self.domain_timer -= 1

            # Manual deactivation with X key press (edge-triggered, skip same-frame activation)
            if x_key and not self._prev_x_key and self.domain_timer < DOMAIN_DURATION - 1:

                self.domain_active = False

                self._on_domain_end()

                if notifs is not None:

                    notifs.append(Notif("Dominio desactivado!", (255, 255, 255), 60))

            elif self.domain_timer <= 0:

                self.domain_active = False

                self._on_domain_end()

        self._prev_x_key = x_key


        # Ability duration & temporary buffs

        if self.ability_active:

            self.ability_duration -= 1

        self._tick_ability_buffs(enemies, particles)



        # Buff timers

        if self.rebotar_timer > 0:

            self.rebotar_timer -= 1

        if self.turbo_timer > 0:

            self.turbo_timer -= 1

        if self.shield_timer > 0:

            self.shield_timer -= 1

            self.shield = 30

        else:

            self.shield = 0

        if self.explosive_timer > 0:

            self.explosive_timer -= 1

        if self.light_flash_timer > 0:

            self.light_flash_timer -= 1

        if self.hit_flash > 0:

            self.hit_flash -= 1

        if self.invuln_timer > 0:

            self.invuln_timer -= 1



        # Passive income (Vicente)

        if self.passive_bytes > 0 and random.random() < 0.01:

            self.bytes += max(1, self.passive_bytes // 10)



        # Bomb usage (edge-triggered)

        bomb_key = keys[pygame.K_g]

        if bomb_key and not self._prev_bomb_key and len(self.bomb_queue) > 0:

            btype = self.bomb_queue.pop(0)

            self.bomb_count = max(0, self.bomb_count - 1)

            self.bomb_active_idx = max(0, min(self.bomb_active_idx, len(self.bomb_queue) - 1)) if self.bomb_queue else 0

            angle = self.angle

            if btype == "mine":

                b = Bomb(self.pos.copy(), pygame.Vector2(0, 0), "mine", self.map_w, self.map_h)

            elif btype == "sticky":

                b = Bomb(self.pos.copy(), pygame.Vector2(math.cos(angle), math.sin(angle)) * 8, "sticky", self.map_w, self.map_h)

            else:

                b = Bomb(self.pos.copy(), pygame.Vector2(math.cos(angle), math.sin(angle)) * 12, btype, self.map_w, self.map_h)

            if all_sprites is not None:

                all_sprites.add(b)

            self.bombs.append(b)

        self._prev_bomb_key = bomb_key



        # Update minions

        for br in self.active_brainrots[:]:

            if not br.alive():

                self.active_brainrots.remove(br)

            elif enemies is not None:

                br.update(enemies, (self.pos.x, self.pos.y), grid)



        # Update import snippets

        for s in self.active_snippets[:]:

            if not s.update(enemies, grid):

                self.active_snippets.remove(s)



        # Update Billie

        if self.billie_npc is not None and enemies is not None and not self.billie_npc.update(enemies, grid):

            self.billie_npc = None



        # Update walls

        for w in self.walls[:]:

            if not w.update():

                self.walls.remove(w)



        # Update tornado

        if self.tornado is not None:

            self.tornado.update(grid)

            if self.tornado.lifetime <= 0:

                self.tornado = None



        # Update display HP

        self._update_display_hp()



        # Clamp position

        self.pos.x = max(self.radius, min(self.map_w - self.radius, self.pos.x))

        self.pos.y = max(self.radius, min(self.map_h - self.radius, self.pos.y))



        # Update sprite
        cd = self.char_data
        if self.char_id == "vicente":
            cd = {**cd, "color": self.vicente_mode_colors[self.vicente_mode]}
        draw_player(self.image, self.angle, self.hit_flash > 0, self.radius, cd, self.char_id)

        self.rect.center = (int(self.pos.x), int(self.pos.y))



    def _fire_eder_laser(self, particles, notifs, grid):

        charge_ratio = self.ult_charge / max(1, ULT_CHARGE_MAX)

        self.ult_laser_active = True

        self.ult_laser_timer = ULT_LASER_DURATION

        self.ult_laser_angle = self.angle

        self.ability_charge = 0

        self.charge_kills = 0

        self.ult_ready = False

        self.ult_charging = False

        self.beam_start = self.pos.copy()

        self.beam_end = self.beam_start

        self.beam_w = int(14 + 16 * charge_ratio)

        self.ability_active = True

        self.ability_duration = ULT_LASER_DURATION

        self.shake = 8

        if SFX and hasattr(SFX, "get"):
            SFX["guitar_riff"].play()
            SFX["eder_laser_loop"].play(loops=-1)

        if notifs:

            notifs.append(Notif("SOLO MORTAL!", (200, 80, 255), 45))

        if particles:

            for _ in range(12):

                a = random.uniform(-0.2, 0.2) + self.ult_laser_angle

                sp = random.uniform(4, 9)

                particles.append(Particle(

                        self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                    (200, 80, 255), random.uniform(2, 5), random.randint(8, 18)))



    def _tick_eder_laser(self, enemies, particles, grid):

        if not self.ult_laser_active:

            return

        self.beam_start = self.pos.copy()

        # Follow mouse direction while beam is active (no aimbot)
        self.ult_laser_angle = self.angle

        self.beam_end = laser_ray_end(

            grid, self.beam_start, self.ult_laser_angle, 950, self.map_w, self.map_h)

        charge_ratio = max(0.5, self.beam_w / 30.0)

        frame_dmg = int(35 * charge_ratio)

        hit_r = (self.beam_w + 12) ** 2

        x1, y1 = self.beam_start.x, self.beam_start.y

        x2, y2 = self.beam_end.x, self.beam_end.y

        if enemies:

            for e in enemies:

                if not hasattr(e, "pos") or not hasattr(e, "hp") or e.hp <= 0:

                    continue

                if point_seg_dist_sq(e.pos.x, e.pos.y, x1, y1, x2, y2) <= hit_r:

                    kb = e.pos - self.pos

                    kb = kb.normalize() if kb.length_squared() > 0.25 else pygame.Vector2(math.cos(self.ult_laser_angle), math.sin(self.ult_laser_angle))

                    e.hit(frame_dmg, kb)

                    if particles and random.random() < 0.35:

                        particles.append(Particle(

                            e.pos, pygame.Vector2(0, 0),

                            (255, 60, 60), random.uniform(2, 4), random.randint(4, 10), gravity=0))

        # Sparks along beam

        if particles and random.random() < 0.15:

            t = random.uniform(0, 1)

            sx = x1 + (x2 - x1) * t

            sy = y1 + (y2 - y1) * t

            a = random.uniform(-0.3, 0.3) + self.ult_laser_angle

            sp = random.uniform(1, 3)

            particles.append(Particle(

                pygame.Vector2(sx, sy),

                pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                (255, random.randint(200, 255), random.randint(100, 200)),

                random.uniform(1, 2), random.randint(4, 8)))



    def _tick_buffer_beam(self, enemies, particles):

        if not hasattr(self, "beam_start") or not hasattr(self, "beam_end"):

            return

        hit_r = (self.beam_w + 12) ** 2

        x1, y1 = self.beam_start.x, self.beam_start.y

        x2, y2 = self.beam_end.x, self.beam_end.y

        if not enemies:

            return

        for e in enemies:

            if not hasattr(e, "pos") or not hasattr(e, "hp") or e.hp <= 0:

                continue

            if point_seg_dist_sq(e.pos.x, e.pos.y, x1, y1, x2, y2) <= hit_r:

                kb = e.pos - self.pos

                kb = kb.normalize() if kb.length_squared() > 0.25 else pygame.Vector2(math.cos(self.angle), math.sin(self.angle))

                e.hit(10, kb)

                if particles is not None and random.random() < 0.3:

                    a = random.uniform(0, math.tau)

                    sp = random.uniform(1, 3)

                    particles.append(Particle(

                        e.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                        (255, 80, 180), random.uniform(2, 3), random.randint(4, 10)))



    def _ability_hit_enemies(self, enemies, radius, damage, particles=None, color=(255, 255, 255), stun=0):

        if not enemies:

            return

        for e in enemies:

            if not hasattr(e, "pos") or not hasattr(e, "hp") or e.hp <= 0:

                continue

            if self.pos.distance_to(e.pos) > radius:

                continue

            kb = e.pos - self.pos

            kb = kb.normalize() if kb.length_squared() > 0.25 else pygame.Vector2(1, 0)

            if getattr(e, "is_boss", False):

                e.hit(int(e.max_hp * 0.35 * self.ability_damage_mult), kb)

            else:

                e.hit(int(damage * self.ability_damage_mult), kb)

            if stun > 0:

                e.stun_timer = max(e.stun_timer, stun)

            if particles:

                for _ in range(3):

                    a = random.uniform(0, math.tau)

                    sp = random.uniform(1, 4)

                    particles.append(Particle(e.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                        color, random.uniform(2, 4), random.randint(6, 14)))



    def _use_ability(self, particles, notifs, enemies, enemy_bullets, grid, all_sprites=None):

        ab = self.ability_name



        if ab == "aplastar":

            self._ability_hit_enemies(enemies, 250, 150, particles, (0, 200, 255))

            if particles:

                for _ in range(8):

                    a = random.uniform(0, math.tau)

                    sp = random.uniform(2, 5)

                    particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp, (0, 200, 255), random.uniform(2, 4), random.randint(8, 16)))

            if notifs:

                notifs.append(Notif("APLASTAR!", (0, 200, 255), 40))



        elif ab == "rebotar":

            self.ability_active = True

            self.ability_duration = 420

            self.rebotar_timer = 420

            self.rebotar_bounces = 5 + max(0, self.bounce)

            self.dmg_mult = max(self.dmg_mult or 1.0, 1.5)

            if notifs:

                notifs.append(Notif("REBOTAR ACTIVO 7s", (255, 100, 100), 40))



        elif ab == "robar":

            self._robar_buff = True

            self.byte_multiplier = max(self.byte_multiplier, 4.0)

            self.dmg_mult = 2.0

            self.ability_active = True

            self.ability_duration = 300

            bytes_stolen = 0

            if enemies:

                for e in enemies:

                    if hasattr(e, "pos") and hasattr(e, "hp") and e.hp > 0 and self.pos.distance_to(e.pos) < 300:

                        bytes_stolen += 8

            self.bytes += int(bytes_stolen * 4)

            if notifs:

                notifs.append(Notif(f"ROBAR: +{bytes_stolen * 4} bytes", (255, 210, 55), 40))



        elif ab == "brainrot":

            self._ability_hit_enemies(enemies, 180, 50, particles, (180, 50, 255))

            for _ in range(2):

                br = BrainrotMinion(self.pos.copy(), self, self.map_w, self.map_h)

                self.active_brainrots.append(br)

                if all_sprites is not None:

                    all_sprites.add(br)

            if notifs:

                notifs.append(Notif("BRAINROT x2!", (180, 50, 255), 40))



        elif ab == "bolillo":

            self.hp = self.max_hp

            self._bolillo_buff = True

            self.dmg_mult = 2.0

            self.invuln_timer = 180

            self.ability_active = True

            self.ability_duration = 300

            if particles:

                for _ in range(30):

                    a = random.uniform(0, math.tau)

                    sp = random.uniform(2, 6)

                    particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp, (255, 200, 50), random.uniform(3, 5), random.randint(10, 20)))

            self._ability_hit_enemies(enemies, 200, 50, particles, (255, 200, 50))

            if notifs:

                notifs.append(Notif("BOLILLO: FULL HEAL + DMG!", (255, 200, 50), 40))



        elif ab == "billie":

            if self.billie_npc is None or (hasattr(self.billie_npc, "hp") and self.billie_npc.hp <= 0):

                self.billie_npc = BillieNPC(self.pos.copy(), self.map_w, self.map_h)

                if all_sprites is not None:

                    all_sprites.add(self.billie_npc)

                if notifs:

                    notifs.append(Notif("BILLIE EILISH!", (255, 80, 200), 40))

            elif notifs:

                notifs.append(Notif("Billie ya en escena!", (255, 80, 200), 40))



        elif ab == "import_snippet":

            if self.char_id == "vicente" and self.vicente_mode == 1:

                # COMPILE: Compile Error wave

                self._ability_hit_enemies(enemies, 250, 150, particles, (255, 80, 80))

                if particles:

                    for _ in range(15):

                        a = random.uniform(0, math.tau)

                        sp = random.uniform(3, 7)

                        particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                            (255, 80, 80), random.uniform(3, 5), random.randint(10, 20)))

                if notifs:

                    notifs.append(Notif("COMPILE ERROR!", (255, 80, 80), 40))

            elif self.char_id == "vicente" and self.vicente_mode == 2:

                # DEBUG: Breakpoint — slow enemies in radius

                if enemies:

                    for e in enemies:

                        if hasattr(e, "pos") and hasattr(e, "hp") and e.hp > 0 and self.pos.distance_to(e.pos) < 250:

                            e.stun_timer = max(getattr(e, "stun_timer", 0), 180)

                            if hasattr(e, "speed"):

                                e.speed = max(0.3, e.speed * 0.3)

                if particles:

                    for _ in range(20):

                        a = random.uniform(0, math.tau)

                        sp = random.uniform(1, 4)

                        particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                            (100, 255, 100), random.uniform(2, 4), random.randint(10, 25)))

                if notifs:

                    notifs.append(Notif("BREAKPOINT! 3s SLOW", (100, 255, 100), 40))

            else:

                # IMPORT: 3 ImportSnippets (default)

                for _ in range(3):

                    off = pygame.Vector2(random.uniform(-30, 30), random.uniform(-30, 30))

                    snippet = ImportSnippet(self.pos.copy() + off, self.map_w, self.map_h)

                    self.active_snippets.append(snippet)

                    if all_sprites is not None:

                        all_sprites.add(snippet)

                if notifs:

                    notifs.append(Notif("IMPORT THIS!", (100, 200, 255), 40))



        elif ab == "guitar_riff":

            self.shake = 6

            self.ability_active = True

            self.ability_duration = 20

            self._ability_hit_enemies(enemies, 300, 120, particles, (255, 200, 50), stun=25)

            if particles:

                for _ in range(25):

                    a = random.uniform(0, math.tau)

                    sp = random.uniform(5, 12)

                    particles.append(Particle(

                        self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                        (200, random.randint(80, 200), 255),

                        random.uniform(2, 5), random.randint(10, 22)))

            if SFX and hasattr(SFX, "get"):

                SFX["guitar_riff"].play()

            if notifs:

                notifs.append(Notif("RIFF ELÉCTRICO!", (200, 80, 255), 45))



        elif ab == "buffer":

            self.ability_active = True

            self.ability_duration = 120

            self.ian_phase = 1

            self.beam_w = 14

            beam_len = 500

            self.beam_start = self.pos.copy()

            self.beam_end = self.pos + pygame.Vector2(math.cos(self.angle), math.sin(self.angle)) * beam_len

            if particles:

                for _ in range(20):

                    a = random.uniform(0, math.tau)

                    sp = random.uniform(2, 5)

                    particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp, (255, 80, 180), random.uniform(3, 5), random.randint(10, 20)))

            self._ability_hit_enemies(enemies, 250, 120, particles, (255, 80, 180), stun=45)

            if notifs:

                notifs.append(Notif("BUFFER OVERFLOW!", (255, 80, 180), 40))



        elif ab == "muro":

            if len(self.walls) < 3:

                wall_pos = self.pos + pygame.Vector2(math.cos(self.angle), math.sin(self.angle)) * 50

                self.walls.append(Wall(wall_pos, self))

                if notifs:

                    notifs.append(Notif("MURO DESPLEGADO!", (80, 180, 255), 40))

            elif notifs:

                notifs.append(Notif("Maximo de muros alcanzado!", (80, 180, 255), 40))



    def _use_ultimate(self, particles, notifs, enemies, all_sprites=None, grid=None):

        ab = self.ability_name



        if ab == "aplastar":

            n_angles = 10

            for i in range(n_angles):

                a = self.angle + math.tau * i / n_angles

                end_pos = self.pos + pygame.Vector2(math.cos(a), math.sin(a)) * 250

                for e in enemies:

                    if not hasattr(e, "pos") or not hasattr(e, "hp") or e.hp <= 0: continue

                    d = point_seg_dist_sq(e.pos.x, e.pos.y, self.pos.x, self.pos.y, end_pos.x, end_pos.y)

                    if d <= (self.radius + 20) ** 2:

                        kb = e.pos - self.pos

                        kb = kb.normalize() if kb.length_squared() > 0.25 else pygame.Vector2(math.cos(a), math.sin(a))

                        e.hit(30, kb)

                if particles:

                    for _ in range(3):

                        sp = random.uniform(2, 5)

                        particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                            (0, 200, 255), random.uniform(2, 4), random.randint(8, 16)))

            self.ability_active = True

            self.ability_duration = 60

            if notifs:

                notifs.append(Notif("CICLO INFINITO!", (0, 200, 255), 60))



        elif ab == "rebotar":

            self.ability_active = True

            self.ability_duration = 300

            self.dmg_mult = 2.0

            self._ult_buff = True

            self.rebotar_bounces = 10 + max(0, self.bounce)

            self.rebotar_timer = 300

            if notifs:

                notifs.append(Notif("REBOTE CAÓTICO!", (255, 100, 100), 60))



        elif ab == "robar":

            self._robar_buff = True

            self.byte_multiplier = max(self.byte_multiplier, 5.0)

            self.dmg_mult = 3.0

            self._ult_buff = True

            self.ability_active = True

            self.ability_duration = 300

            bytes_stolen = 0

            if enemies:

                for e in enemies:

                    if hasattr(e, "pos") and hasattr(e, "hp") and e.hp > 0 and self.pos.distance_to(e.pos) < 350:

                        bytes_stolen += 20

            self.bytes += bytes_stolen

            if particles:

                for _ in range(30):

                    a = random.uniform(0, math.tau)

                    sp = random.uniform(2, 5)

                    particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                        (255, 210, 55), random.uniform(3, 5), random.randint(10, 20)))

            if notifs:

                notifs.append(Notif(f"BYTE OVERFLOW: +{bytes_stolen} bytes!", (255, 210, 55), 60))



        elif ab == "brainrot":

            for _ in range(6):

                offset = pygame.Vector2(random.uniform(-30, 30), random.uniform(-30, 30))

                br = BrainrotMinion(self.pos + offset, self, self.map_w, self.map_h)

                self.active_brainrots.append(br)

                if all_sprites is not None:

                    all_sprites.add(br)

            self.dmg_mult = 2.0

            self._ult_buff = True

            self.ability_active = True

            self.ability_duration = 300

            if notifs:

                notifs.append(Notif("HORDA CEREBRAL!", (180, 50, 255), 60))



        elif ab == "bolillo":

            self.hp = self.max_hp

            self.invuln_timer = 180

            self.dmg_mult = 3.0

            self._ult_buff = True

            self.ability_active = True

            self.ability_duration = 300

            if particles:

                for _ in range(30):

                    a = random.uniform(0, math.tau)

                    sp = random.uniform(3, 7)

                    particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                        (255, 200, 50), random.uniform(3, 6), random.randint(15, 25)))

            if notifs:

                notifs.append(Notif("ADMIN GODMODE!", (255, 200, 50), 60))



        elif ab == "billie":

            if self.billie_npc is None or (hasattr(self.billie_npc, "hp") and self.billie_npc.hp <= 0):

                self.billie_npc = BillieNPC(self.pos.copy(), self.map_w, self.map_h)

                if all_sprites is not None:

                    all_sprites.add(self.billie_npc)

            self.dmg_mult = 3.0

            self._ult_buff = True

            self.ability_active = True

            self.ability_duration = 300

            if enemies:

                for e in enemies:

                    if hasattr(e, "pos") and e.hp > 0 and self.pos.distance_to(e.pos) < 400:

                        kb = self.pos - e.pos

                        if kb.length_squared() > 0.01:

                            kb.scale_to_length(3.0)

                            e.pos += kb

            if notifs:

                notifs.append(Notif("BILLIE MUNDIAL!", (255, 80, 200), 60))



        elif ab == "import_snippet":

            if self.char_id == "vicente" and self.vicente_mode == 1:

                # COMPILE: Runtime Error — massive damage + stun all enemies near

                self._ability_hit_enemies(enemies, 350, 200, particles, (255, 80, 80), stun=120)

                if particles:

                    for _ in range(30):

                        a = random.uniform(0, math.tau)

                        sp = random.uniform(3, 8)

                        particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                            (255, 80, 80), random.uniform(3, 6), random.randint(15, 30)))

                if notifs:

                    notifs.append(Notif("RUNTIME ERROR!", (255, 80, 80), 60))

            elif self.char_id == "vicente" and self.vicente_mode == 2:

                # DEBUG: Barrera Infinita — invulnerable 60s

                self.invuln_timer = 3600

                self.shield_timer = 3600

                self.shield = 9999

                self.hp = self.max_hp

                if particles:

                    for _ in range(30):

                        a = random.uniform(0, math.tau)

                        sp = random.uniform(3, 8)

                        particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                            (100, 255, 100), random.uniform(3, 6), random.randint(15, 30)))

                if notifs:

                    notifs.append(Notif("BARRERA INFINITA! 60s INMORTAL", (100, 255, 100), 80))

            else:

                # IMPORT: LIMPIADOR (default)

                killed = 0

                for e in enemies:

                    if hasattr(e, "hp") and e.hp > 0:

                        e.hp = 0

                        killed += 1

                if particles:

                    for _ in range(min(killed * 5, 300)):

                        a = random.uniform(0, math.tau)

                        sp = random.uniform(2, 10)

                        particles.append(Particle(self.pos + pygame.Vector2(random.uniform(-300, 300), random.uniform(-300, 300)),

                            pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                            (100, 200, 255), random.uniform(3, 7), random.randint(15, 40)))

                if notifs:
                    notifs.append(Notif(f"LIMPIADOR! {killed} enemigos eliminados!", (100, 200, 255), 80))





        elif ab == "buffer":

            self.ability_active = True

            self.ability_duration = 60

            self.ian_phase = 1

            self.beam_w = 30

            beam_len = 600

            self.beam_start = self.pos.copy()

            self.beam_end = self.pos + pygame.Vector2(math.cos(self.angle), math.sin(self.angle)) * beam_len

            self._ability_hit_enemies(enemies, 300, 200, particles, (255, 80, 180), stun=60)

            if particles:

                for _ in range(25):

                    a = random.uniform(0, math.tau)

                    sp = random.uniform(3, 6)

                    particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,

                        (255, 80, 180), random.uniform(3, 5), random.randint(12, 22)))

            if notifs:

                notifs.append(Notif("BUFFER CRASH!", (255, 80, 180), 60))



        elif ab == "muro":

            self.walls.clear()

            for i in range(3):

                a = self.angle + math.radians((i - 1) * 30)

                wall_pos = self.pos + pygame.Vector2(math.cos(a), math.sin(a)) * 60

                self.walls.append(Wall(wall_pos, self, radius=50))

            self._ability_hit_enemies(enemies, 200, 50, particles, (80, 180, 255))

            if notifs:

                notifs.append(Notif("FIREWALL TOTAL!", (80, 180, 255), 60))



        SFX["levelup"].play()



    def _on_domain_end(self):

        if self.domain_effect == "congelar" and self.ability_damage_mult >= 4.0:

            self.ability_damage_mult = 1.0

        if self.char_id == "eder":
            stop_eder_domain_music()

    def _update_display_hp(self):
        self.display_hp = self.hp

    def _cycle_vicente_mode(self):
        self.vicente_mode = (self.vicente_mode + 1) % 3
        self._apply_vicente_mode()

    def _apply_vicente_mode(self):
        mode = self.vicente_mode
        if mode == 0:
            self.dmg_mult = 1.0
            self.fr_mult = 1.0
            self.base_speed = self.char_data["speed"]
        elif mode == 1:
            self.dmg_mult = 1.5
            self.fr_mult = 0.85
            self.base_speed = self.char_data["speed"] * 0.85
        elif mode == 2:
            self.dmg_mult = 0.7
            self.fr_mult = 1.3
            self.base_speed = self.char_data["speed"] * 1.2

    def take_damage(self, amount):
        if self.invuln_timer > 0:
            return
        if self.shield > 0:
            absorbed = min(self.shield, amount)
            self.shield -= absorbed
            amount -= absorbed
        self.hp -= amount
        self.hp = max(self.hp, 0)
        if self.hp <= 0 and self.domain_active:
            self.domain_active = False
            self._on_domain_end()
        self.hit_flash = LIGHT_FLASH_DURATION
        self.invuln_timer = 10


class ImportSnippet(pygame.sprite.Sprite):
    """Fragmento de código flotante del dominio Python (modo IMPORT de Vicente)."""
    def __init__(self, pos, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        self.pos = pygame.Vector2(pos)
        self.map_w = map_w
        self.map_h = map_h
        self.radius = 10
        self.life = 90
        self.max_life = 90
        self.alive = True
        self.vel = pygame.Vector2(random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5))
        self.text = random.choice(CODE_SNIPPETS)
        from src.ui import _f
        f = _f(12)
        self.image = f.render(self.text, True, (100, 200, 255)) if f else pygame.Surface((0, 0))
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))

    def update(self, enemies=None, grid=None):
        self.pos += self.vel
        self.life -= 1
        if self.life <= 0:
            self.alive = False
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        return self.alive

    def draw(self, surf, cx=0, cy=0):
        if not self.alive or self.max_life <= 0:
            return
        a = int((self.life / self.max_life) * 200)
        self.image.set_alpha(a)
        surf.blit(self.image, (self.pos.x - self.image.get_width() // 2 - cx, self.pos.y - cy))


class Mimic(pygame.sprite.Sprite):
    """Enemigo que se disfraza de pickup. Explota al contacto con el jugador."""
    def __init__(self, pos, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        self.pos = pygame.Vector2(pos)
        self.radius = 12
        self.hp = 1
        self._alive = True
        self.map_w = map_w
        self.map_h = map_h
        self.exploded = False
        self.image = pygame.Surface((self.radius * 2,) * 2, pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        self._redraw()

    def _redraw(self):
        r = self.radius
        self.image.fill((0, 0, 0, 0))
        color = (200, 50, 50)
        pygame.draw.circle(self.image, (100, 20, 20), (r, r), r)
        pygame.draw.circle(self.image, color, (r, r), r)
        pygame.draw.circle(self.image, (255, 100, 100), (r, r), r - 2)

    def update(self):
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def explode(self, player, particles):
        if self.exploded:
            return
        self.exploded = True
        player.take_damage(30)
        for _ in range(12):
            a = random.uniform(0, math.tau)
            sp = random.uniform(2, 6)
            particles.append(Particle(self.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp, (255, 50, 50), random.uniform(3, 6), random.randint(10, 20)))

    def draw(self, surf, cx=0, cy=0):
        color = (200, 50, 50)
        pygame.draw.circle(surf, (100, 20, 20), (self.pos.x - cx + 1, self.pos.y - cy + 1), self.radius)
        pygame.draw.circle(surf, color, (self.pos.x - cx, self.pos.y - cy), self.radius)
        pygame.draw.circle(surf, (255, 100, 100), (self.pos.x - cx, self.pos.y - cy), self.radius - 2)


class Pickup(pygame.sprite.Sprite):
    """Objeto recogible (salud, munición) que aparece al matar enemigos."""
    def __init__(self, pos, ptype, map_w=MAP_W, map_h=MAP_H):
        super().__init__()
        self.pos = pygame.Vector2(pos) if not isinstance(pos, pygame.Vector2) else pygame.Vector2(pos)
        self.type = ptype
        self.radius = 8
        self.map_w = map_w
        self.map_h = map_h
        self.life = 600
        self.max_life = 600
        self.alive = True
        self.image = pygame.Surface((self.radius * 2,) * 2, pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(int(self.pos.x), int(self.pos.y)))
        self._redraw()

    def _redraw(self):
        r = self.radius
        self.image.fill((0, 0, 0, 0))
        if self.type == "health":
            color = (50, 200, 50)
            icon = "+"
        elif self.type == "ammo":
            color = (200, 200, 50)
            icon = "a"
        else:
            color = (200, 200, 200)
            icon = "?"
        pygame.draw.circle(self.image, color, (r, r), r)
        pygame.draw.circle(self.image, (255, 255, 255), (r, r), r - 2)
        font = pygame.font.Font(None, 16)
        s = font.render(icon, True, color)
        self.image.blit(s, (r - s.get_width() // 2, r - s.get_height() // 2))

    def update(self):
        self.life -= 1
        if self.life <= 0:
            self.alive = False
        return self.alive

    def draw(self, surf, cx=0, cy=0):
        if not self.alive:
            return
        alpha = min(255, int(self.life / self.max_life * 255))
        self.image.set_alpha(alpha)
        surf.blit(self.image, (self.pos.x - self.radius - cx, self.pos.y - self.radius - cy))


class Powerup:
    """Power-up temporal que flota en el mapa (turbo, escudo, etc.)."""
    def __init__(self, pos, ptype, map_w=MAP_W, map_h=MAP_H):
        self.pos = pygame.Vector2(pos) if not isinstance(pos, pygame.Vector2) else pygame.Vector2(pos)
        self.ptype = ptype
        self.radius = 14
        self.map_w = map_w
        self.map_h = map_h
        self.life = 900
        self.max_life = 900
        self.alive = True
        self.float_offset = random.uniform(0, math.tau)
        self.colors = {
            "turbo": (255, 200, 50),
            "shield": (50, 150, 255),
            "byte_magnet": (100, 255, 100),
            "explosive": (255, 80, 80),
        }

    def update(self):
        self.life -= 1
        self.float_offset += 0.03
        if self.life <= 0:
            self.alive = False
        return self.alive

    def draw(self, surf, cx=0, cy=0):
        if not self.alive:
            return
        color = self.colors.get(self.ptype, (200, 200, 200))
        alpha = min(255, int(self.life / self.max_life * 255))
        fy = math.sin(self.float_offset) * 3
        x = self.pos.x - cx
        y = self.pos.y - cy + fy
        pygame.draw.circle(surf, (*color[:3], alpha), (x, y), self.radius, 3)
        pygame.draw.circle(surf, (*color[:3], alpha // 2), (x, y), self.radius + 2, 1)
        font = pygame.font.Font(None, 16)
        s = font.render(self.ptype[0].upper(), True, color)
        surf.blit(s, (x - s.get_width() // 2, y - s.get_height() // 2))


class ShopTerminal:
    """Terminal de compra (Vicente/Oscar) con skin de personaje."""
    def __init__(self, pos, items, name="VICENTE", map_w=MAP_W, map_h=MAP_H):
        self.pos = pygame.Vector2(pos) if not isinstance(pos, pygame.Vector2) else pygame.Vector2(pos)
        self.items = items
        self.name = name
        self.radius = 20
        self.map_w = map_w
        self.map_h = map_h
        self.angle = 0
        self.surf = pygame.Surface((self.radius * 2,) * 2, pygame.SRCALPHA)
        if name == "VICENTE":
            self.char_id = "vicente"
            self.char_data = CHARACTERS.get("vicente", {"name":"Vicente","color":(100,200,255)})
        else:
            self.char_id = "oscar"
            self.char_data = {"name":"Oscar","color":(255,200,50)}

    def update(self):
        self.angle += 0.02

    def draw(self, surf, cx=0, cy=0, near=False):
        x = self.pos.x - cx
        y = self.pos.y - cy
        draw_player(self.surf, self.angle, False, self.radius, self.char_data, self.char_id)
        surf.blit(self.surf, (x - self.radius, y - self.radius))
        if near:
            font2 = pygame.font.Font(None, 14)
            s2 = font2.render(f"[E] {self.name}", True, (255, 255, 255))
            surf.blit(s2, (x - s2.get_width() // 2, y - self.radius - 18))



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
            return None
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
                    diff = target.pos - self.pos
                    if diff.length_squared() > 0:
                        target.hit(self.damage, diff.normalize() * 8)
                    return None
                from src.entities import Bullet
                a = math.atan2(target.pos.y - self.pos.y, target.pos.x - self.pos.x)
                return Bullet(self.pos, a, "ally", self.damage, speed=10, spread=0.1, map_w=self.map_w, map_h=self.map_h, color=self.color)

        self.pos.x = max(self.radius, min(self.map_w - self.radius, self.pos.x))
        self.pos.y = max(self.radius, min(self.map_h - self.radius, self.pos.y))
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        return None

    def draw_hp(self, surf, cx, cy):
        bw = self.radius * 2; bh = 3
        x = self.pos.x - bw // 2 - cx
        y = self.pos.y - self.radius - 6 - cy
        r = self.hp / self.max_hp
        pygame.draw.rect(surf, (20, 20, 20), (x, y, bw, bh))
        pygame.draw.rect(surf, (0, 200, 100) if r > 0.5 else (255, 200, 50) if r > 0.25 else (255, 50, 50), (x, y, int(bw * r), bh))

    def take_damage(self, amount):
        self.hp -= amount
        self.hp = max(self.hp, 0)


class EnemyBullet:
    """Bala disparada por enemigos (Zapiens hostil, etc.)."""
    def __init__(self, pos, vel, damage):
        self.pos = pygame.Vector2(pos) if not isinstance(pos, pygame.Vector2) else pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel) if not isinstance(vel, pygame.Vector2) else pygame.Vector2(vel)
        self.damage = damage
        self.radius = 5
        self.alive = True

    def update(self, map_w=MAP_W, map_h=MAP_H, grid=None):
        self.pos += self.vel
        if grid is not None:
            col, row = int(self.pos.x // TILE), int(self.pos.y // TILE)
            if 0 <= row < ROWS and 0 <= col < COLS and is_wall(grid, col, row):
                self.alive = False
        if self.pos.x < -50 or self.pos.x > map_w + 50 or self.pos.y < -50 or self.pos.y > map_h + 50:
            self.alive = False
        return self.alive

    def draw(self, surf, cx=0, cy=0):
        x = self.pos.x - cx
        y = self.pos.y - cy
        pygame.draw.circle(surf, (255, 50, 50), (x, y), self.radius)
        pygame.draw.circle(surf, (255, 150, 150), (x, y), self.radius - 2)


class Hazard:
    """Zona de peligro en el suelo (modificador tóxico). Daña al jugador si está dentro del radio."""
    def __init__(self, pos, damage, radius, lifetime):
        self.pos = pygame.Vector2(pos) if not isinstance(pos, pygame.Vector2) else pygame.Vector2(pos)
        self.damage = damage
        self.radius = radius
        self.life = lifetime
        self.max_life = lifetime
        self.alive = True

    def update(self, player_pos):
        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return 0
        pp = player_pos if hasattr(player_pos, "distance_to") else pygame.Vector2(player_pos)
        dist = pp.distance_to(self.pos)
        if dist < self.radius + 17:
            return self.damage
        return 0

    def draw(self, surf, cx=0, cy=0):
        alpha = int((self.life / self.max_life) * 120)
        s = pygame.Surface((self.radius * 2,) * 2, pygame.SRCALPHA)
        pygame.draw.circle(s, (0, 200, 0, alpha), (self.radius, self.radius), self.radius)
        surf.blit(s, (self.pos.x - self.radius - cx, self.pos.y - self.radius - cy))

