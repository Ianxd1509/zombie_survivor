import random

import pygame

from config import WHITE, YELLOW


# Caché de superficies circulares para partículas (evita crear texturas repetidas)
_PARTICLE_RADII_CACHE = {}

def _get_circle_surf(r, color):
    key = (r, color[0], color[1], color[2])
    cached = _PARTICLE_RADII_CACHE.get(key)
    if cached is None:
        cached = pygame.Surface((r * 2,) * 2, pygame.SRCALPHA)
        pygame.draw.circle(cached, (*color[:3], 255), (r, r), r)
        if len(_PARTICLE_RADII_CACHE) < 2000:
            _PARTICLE_RADII_CACHE[key] = cached
    return cached


class Particle:
    """Partícula simple con velocidad, gravedad, desvanecimiento y encogimiento."""
    __slots__ = ("alive", "color", "gravity", "life", "max_life", "pos", "radius", "shrink", "vel")
    _surf_cache = {}

    def __init__(self, pos, vel, color, radius, lifetime, gravity=0.0, shrink=True):
        self.pos = pygame.Vector2(pos) if pos is not None else pygame.Vector2(0, 0)
        self.vel = pygame.Vector2(vel) if vel is not None else pygame.Vector2(0, 0)
        self.color = color if color and len(color) >= 3 else (255, 255, 255)
        self.radius = radius
        self.life = lifetime
        self.max_life = lifetime
        self.gravity = gravity
        self.shrink = shrink
        self.alive = True

    def update(self):
        self.pos += self.vel
        self.vel.y += self.gravity
        self.life -= 1
        if self.life <= 0 or self.max_life <= 0:
            self.alive = False
        elif self.shrink:
            self.radius *= 0.97
        return self.alive

    def draw(self, surf, cx=0, cy=0):
        if self.max_life <= 0: return
        a = int(max(0.0, self.life / self.max_life) * 220)
        r = int(max(1, self.radius))
        s = _get_circle_surf(r, self.color)
        s.set_alpha(a)
        surf.blit(s, (self.pos.x - r - cx, self.pos.y - r - cy))


class Decal:
    """Marca/rastro en el suelo que se desvanece lentamente (sangre, quemaduras)."""
    def __init__(self, pos, color, radius=None):
        self.pos = pygame.Vector2(pos)
        self.color = color
        self.radius = radius if radius is not None else random.uniform(4, 10)
        self.life = 600
        self.max_life = 600

    def update(self):
        self.life -= 1
        return self.life > 0

    def draw(self, surf, cx=0, cy=0):
        if self.max_life <= 0: return
        a = int(self.life / self.max_life * 180)
        if a <= 0: return
        r = int(max(1, self.radius))
        s = _get_circle_surf(r, self.color)
        s.set_alpha(a)
        surf.blit(s, (self.pos.x - r - cx, self.pos.y - r - cy))


class DamageNum:
    """Número flotante de daño que sube y se desvanece."""
    __slots__ = ("alive", "color", "image", "life", "max_life", "pos", "size", "text")
    def __init__(self, pos, text, color=YELLOW, size=20):
        self.pos = pygame.Vector2(pos)
        self.text = text
        self.color = color
        self.life = 50
        self.max_life = 50
        self.size = size
        self.alive = True
        from src.ui import _f
        f = _f(size)
        self.image = f.render(text, True, color) if f else pygame.Surface((0, 0))

    def update(self):
        self.pos.y -= 1.5
        self.life -= 1
        if self.life <= 0:
            self.alive = False
        return self.alive

    def draw(self, surf, cx=0, cy=0):
        if self.max_life <= 0: return
        a = int(self.life / self.max_life * 255)
        self.image.set_alpha(a)
        surf.blit(self.image, (self.pos.x - self.image.get_width() // 2 - cx, self.pos.y - cy))


class CodeSnippet:
    """Fragmento de código flotante (efecto visual del dominio Python)."""
    __slots__ = ("alive", "color", "image", "life", "max_life", "pos", "text", "vel")
    def __init__(self, pos, text, color):
        self.pos = pygame.Vector2(pos)
        self.text = text
        self.color = color
        self.life = 45
        self.max_life = 45
        self.alive = True
        self.vel = pygame.Vector2(random.uniform(-0.5, 0.5), -2.0)
        from src.ui import _f
        f = _f(14)
        self.image = f.render(text, True, color) if f else pygame.Surface((0, 0))

    def update(self):
        self.pos += self.vel
        self.vel.y += 0.05
        self.life -= 1
        if self.life <= 0:
            self.alive = False
        return self.alive

    def draw(self, surf, cx=0, cy=0):
        if self.max_life <= 0: return
        a = int(self.life / self.max_life * 255)
        self.image.set_alpha(a)
        surf.blit(self.image, (self.pos.x - self.image.get_width() // 2 - cx, self.pos.y - cy))


class Notif:
    """Notificación temporal en texto (ej. "Modo IMPORT activado", "+1000 bytes")."""
    __slots__ = ("alive", "color", "life", "max_life", "text")
    def __init__(self, text, color=WHITE, duration=120):
        self.text = text
        self.color = color
        self.life = duration
        self.max_life = duration
        self.alive = True

    def update(self):
        self.life -= 1
        if self.life <= 0:
            self.alive = False
        return self.alive

class MatrixRain:
    """Column-based matrix rain for the main menu background."""

    CHARS = "01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.font = pygame.font.Font(None, 14)
        self.col_w = 18
        self.n_cols = w // self.col_w + 1
        self.columns = []
        for i in range(self.n_cols):
            self.columns.append(self._make_col(i))

    def _make_col(self, i):
        length = random.randint(10, 30)
        offset = random.randint(-self.h, 0)
        return {
            "x": i * self.col_w + random.randint(0, 3),
            "y": offset,
            "speed": random.uniform(1.5, 6.0),
            "length": length,
            "chars": [random.choice(self.CHARS) for _ in range(length + 10)],
            "head": 0,
        }

    def update(self):
        for i, c in enumerate(self.columns):
            c["y"] += c["speed"]
            c["head"] = (c["head"] + 1) % len(c["chars"])
            if random.random() < 0.04:
                c["chars"][c["head"]] = random.choice(self.CHARS)
            if c["y"] > self.h + c["length"] * 18:
                self.columns[i] = self._make_col(random.randint(0, self.n_cols - 1))

    def draw(self, surf):
        for c in self.columns:
            head = c["head"]
            for i in range(c["length"]):
                idx = (head - i) % len(c["chars"])
                ch = c["chars"][idx]
                y = c["y"] - i * 18
                if y < -20 or y > self.h + 20:
                    continue
                if i == 0:
                    s = self.font.render(ch, True, (210, 255, 210))
                elif i < 4:
                    fade = 1.0 - (i - 1) * 0.2
                    g = int(255 * fade)
                    s = self.font.render(ch, True, (0, g, 0))
                else:
                    fade = 1.0 - (i / c["length"]) ** 0.6
                    g = int(200 * fade)
                    if g < 8:
                        continue
                    raw = self.font.render(ch, True, (0, g, 0))
                    s = raw.copy()
                    s.set_alpha(max(5, g))
                surf.blit(s, (c["x"], y))
