import math
import os

import pygame

# Caché de sprites de jugador (player procedural), armas renderizadas e imágenes cargadas desde disco
_PLAYER_CACHE = {}
_GUN_CACHE = {}
# Última rotación de arma para evitar re-calcular en cada frame si el ángulo no cambió
_LAST_ANGLE_KEY = None
_LAST_ROT_GUN = None
_LAST_GX = None
_LAST_GY = None
_IMG_CACHE = {}

# Directorio raíz de assets del juego (relativo a este archivo)
_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")

def _img_path(*parts):
    return os.path.join(_ASSETS_DIR, *parts)

# Carga una imagen desde disco, la escala opcionalmente y la guarda en _IMG_CACHE.
# Si el archivo no existe o falla, guarda None para no reintentar.
def load_image(path, size=None, cache_key=None):
    key = cache_key or path
    cached = _IMG_CACHE.get(key)
    if cached is not None:
        return cached
    full = _img_path(path)
    if not os.path.isfile(full):
        _IMG_CACHE[key] = None
        return None
    try:
        img = pygame.image.load(full).convert_alpha()
        if size:
            img = pygame.transform.scale(img, size)
        _IMG_CACHE[key] = img
        return img
    except Exception:
        _IMG_CACHE[key] = None
        return None


# Dibuja el jugador en una superficie cuadrada (2*radius x 2*radius).
# Usa imagen personalizada (char_{cid}.png) con máscara circular si existe; si no, genera un círculo procedural.
# El arma se rota según el ángulo y se dibuja encima del cuerpo.
def draw_player(surf, angle, flash=False, radius=17, char_data=None, char_id="", no_weapon=False):
    r = radius
    if char_data and "color" in char_data:
        col_val = char_data["color"]
        base_color = tuple(col_val[:3]) if hasattr(col_val, "__iter__") else (0, 255, 65)
    else:
        base_color = (0, 255, 65)
    name_char = char_data["name"][0] if char_data and char_data.get("name") else "?"

    # Try loading a custom character image
    cid = char_id or (char_data.get("id", "") if char_data else "")
    char_img = load_image(f"characters/char_{cid}.png", (r * 2, r * 2), f"char_{cid}_{r}")
    use_custom = char_img is not None

    if use_custom:
        surf.fill((0, 0, 0, 0))
        # Máscara circular para la imagen personalizada (el jugador se ve como un círculo)
        mask = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        pygame.draw.circle(mask, (255, 255, 255, 255), (r, r), r)
        masked = char_img.copy()
        masked.blit(mask, (0, 0), None, pygame.BLEND_RGBA_MULT)
        surf.blit(masked, (0, 0))
    else:
        # Fallback: círculo procedural con color, sombra, borde e inicial del nombre
        flash_key = bool(flash)
        cache_key = (base_color, flash_key, name_char, radius)
        cached = _PLAYER_CACHE.get(cache_key)
        if cached is None:
            cached = pygame.Surface((r * 2,) * 2, pygame.SRCALPHA)
            if flash:
                c = [min(255, x + 100) for x in base_color]
            else:
                c = list(base_color)
            pygame.draw.circle(cached, (0, 255, 65, 30), (r + 2, r + 2), r)
            pygame.draw.circle(cached, (*c, 200), (r, r), r)
            pygame.draw.circle(cached, (max(0, c[0]-30), max(0, c[1]-30), max(0, c[2]-30)), (r, r), r-4)
            pygame.draw.circle(cached, (0, 255, 65), (r, r), r, 2)
            font = pygame.font.Font(None, 18)
            s = font.render(name_char, True, (0, 0, 0))
            cached.blit(s, (r - s.get_width()//2, r - s.get_height()//2))
            _PLAYER_CACHE[cache_key] = cached

        surf.fill((0, 0, 0, 0))
        surf.blit(cached, (0, 0))

    # Arma: se dibuja como un rectángulo con rejilla y se rota según el ángulo del jugador
    if not no_weapon:
        gun_key = base_color
        gun_base = _GUN_CACHE.get(gun_key)
        if gun_base is None:
            gun_base = pygame.Surface((30, 16), pygame.SRCALPHA)
            pygame.draw.rect(gun_base, (0, 60, 15), (2, 0, 26, 16), border_radius=3)
            pygame.draw.rect(gun_base, base_color, (2, 0, 26, 16), 1, border_radius=3)
            for i in range(3):
                for j in range(5):
                    px = 2 + j * 5
                    py = 2 + i * 5
                    pygame.draw.rect(gun_base, (*base_color[:3], 80), (px, py, 3, 3), 1)
            _GUN_CACHE[gun_key] = gun_base

        # Solo rota el arma cuando el ángulo cambia para ahorrar rendimiento
        deg = math.degrees(angle)
        global _LAST_ANGLE_KEY, _LAST_ROT_GUN, _LAST_GX, _LAST_GY
        angle_key = (radius, round(deg))
        if angle_key != _LAST_ANGLE_KEY:
            rot_gun = pygame.transform.rotate(gun_base, -deg)
            gx = r + math.cos(angle) * (r * 1.0) - rot_gun.get_width() // 2
            gy = r + math.sin(angle) * (r * 1.0) - rot_gun.get_height() // 2
            _LAST_ANGLE_KEY = angle_key
            _LAST_ROT_GUN = rot_gun
            _LAST_GX = gx
            _LAST_GY = gy
        else:
            rot_gun = _LAST_ROT_GUN
            gx = _LAST_GX
            gy = _LAST_GY
        surf.blit(rot_gun, (gx, gy))
