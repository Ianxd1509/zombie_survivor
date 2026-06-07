import math
import random

import pygame

from config import ALLY_TYPES, BLUE, BOMB_TYPES, CHARACTERS, DOMAIN_CHARGE_KILLS, EVOLUTION_ITEM_EMOJIS, FONT_SCALE, GACHA_LOOT, GOLD, GRAY, GREEN, HEIGHT, MAP_W, MAPS, PURPLE, RED, SEL, WEAPON_BULLETS, WHITE, WIDTH, YELLOW
from src.tilemap import TILE

# Caché de fuentes para evitar recrearlas constantemente
_FONTS = {}
def _f(sz):
    sz = int(sz * FONT_SCALE + 0.5)
    if sz not in _FONTS:
        _FONTS[sz] = pygame.font.Font(None, sz)
    return _FONTS[sz]

# Dibuja un rectángulo con bordes redondeados
def draw_rrect(surf, color, rect, r=6):
    s = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
    pygame.draw.rect(s, color, (0, 0, rect[2], rect[3]), border_radius=r)
    surf.blit(s, (rect[0], rect[1]))

# Dibuja un efecto de brillo circular alrededor de una posición
def draw_glow(surf, color, pos, radius, alpha=180):
    for i in range(4, 0, -1):
        r = radius + i * 6; a = alpha // (i + 1)
        s = pygame.Surface((r * 2,) * 2, pygame.SRCALPHA)
        pygame.draw.circle(s, (*color[:3], a), (r, r), r)
        surf.blit(s, (pos[0] - r, pos[1] - r))

# Superficie reutilizable para el efecto de líneas de barrido (scanlines)
_scanline_surf = None

def draw_scanlines(surf, alpha=25):
    global _scanline_surf
    if _scanline_surf is None or _scanline_surf.get_size()[0] != WIDTH:
        _scanline_surf = pygame.Surface((WIDTH, 2), pygame.SRCALPHA)
        _scanline_surf.fill((0, 255, 65, 20))
    for y in range(0, HEIGHT, 4):
        surf.blit(_scanline_surf, (0, y))

# Dibuja un marco tipo terminal (bordes con esquinas)
def draw_terminal_frame(surf, color=GREEN, alpha=60):
    s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.line(s, (*color[:3], alpha), (15, 10), (WIDTH - 15, 10), 1)
    pygame.draw.line(s, (*color[:3], alpha), (15, HEIGHT - 10), (WIDTH - 15, HEIGHT - 10), 1)
    pygame.draw.line(s, (*color[:3], alpha), (10, 15), (10, HEIGHT - 15), 1)
    pygame.draw.line(s, (*color[:3], alpha), (WIDTH - 10, 15), (WIDTH - 10, HEIGHT - 15), 1)
    corners = [(10, 10), (WIDTH - 10, 10), (10, HEIGHT - 10), (WIDTH - 10, HEIGHT - 10)]
    for cx, cy in corners:
        pygame.draw.circle(s, (*color[:3], alpha), (cx, cy), 2)
    surf.blit(s, (0, 0))


# Caché del fondo del minimapa para redibujar solo cuando cambia
_MINIMAP_BG = None
_MINIMAP_KEY = None

def _draw_minimap(surf, game):
    global _MINIMAP_BG, _MINIMAP_KEY
    if game is None or not hasattr(game, "grid"):
        return
    MS = int(130 * FONT_SCALE)
    mm_x = WIDTH - MS - 10
    mm_y = 10
    scale = MS / MAP_W

    key = (MAP_W, MS)
    if key != _MINIMAP_KEY:
        _MINIMAP_KEY = key
        _MINIMAP_BG = pygame.Surface((MS, MS))
        grid = game.grid
        for r in range(len(grid)):
            row = grid[r]
            for c in range(len(row)):
                v = row[c]
                if (1 <= v <= 9) or (v >= 20):
                    color = (8, 18, 8)
                elif 10 <= v <= 19:
                    color = (14, 16, 14)
                else:
                    color = (10, 12, 10)
                _MINIMAP_BG.set_at((int(c * TILE * scale), int(r * TILE * scale)), color)
        pygame.draw.rect(_MINIMAP_BG, (0, 50, 15), (0, 0, MS, MS), 1)

    surf.blit(_MINIMAP_BG, (mm_x, mm_y))

    pp = game.player.pos
    px = mm_x + int(pp.x * scale)
    py = mm_y + int(pp.y * scale)
    pygame.draw.circle(surf, (0, 255, 65), (px, py), 3)

    for e in game.enemies:
        ex = mm_x + int(e.pos.x * scale)
        ey = mm_y + int(e.pos.y * scale)
        is_boss = getattr(e, "is_boss", False)
        c2 = (255, 50, 50) if is_boss else (180, 30, 30)
        r2 = 2 if is_boss else 1
        pygame.draw.circle(surf, c2, (ex, ey), r2)

    for br in game.brainrots:
        bx = mm_x + int(br.pos.x * scale)
        by = mm_y + int(br.pos.y * scale)
        pygame.draw.circle(surf, (180, 50, 255), (bx, by), 1)

    if hasattr(game, "vicente") and game.vicente:
        vx = mm_x + int(game.vicente.pos.x * scale)
        vy = mm_y + int(game.vicente.pos.y * scale)
        pygame.draw.circle(surf, (100, 200, 255), (vx, vy), 3)
        vs = _f(10).render("$", True, (100, 200, 255))
        surf.blit(vs, (vx - vs.get_width() // 2, vy - vs.get_height() // 2 - 4))

    if hasattr(game, "oscar") and game.oscar:
        ox = mm_x + int(game.oscar.pos.x * scale)
        oy = mm_y + int(game.oscar.pos.y * scale)
        pygame.draw.circle(surf, (255, 200, 50), (ox, oy), 3)
        os_ = _f(10).render("$", True, (255, 200, 50))
        surf.blit(os_, (ox - os_.get_width() // 2, oy - os_.get_height() // 2 - 4))

    if hasattr(game, "aliados"):
        for a in game.aliados:
            ax = mm_x + int(a.pos.x * scale)
            ay = mm_y + int(a.pos.y * scale)
            pygame.draw.circle(surf, a.color, (ax, ay), 2)

    # Camera viewport rectangle
    cam_w = int(WIDTH * scale)
    cam_h = int(HEIGHT * scale)
    cam_x = int(game.cam.x * scale)
    cam_y = int(game.cam.y * scale)
    pygame.draw.rect(surf, (0, 100, 40), (mm_x + cam_x, mm_y + cam_y, cam_w, cam_h), 1)


# Dibuja todo el HUD en pantalla: stats, barras, minimapa, notificaciones, crosshair, etc
def draw_hud(surf, player, wave, wave_state, wave_has_boss, wave_announce, enemies_count, notifs, prep_timer=0, vicente_near=False, shop_open=False, game=None, oscar_near=False, fps=0):
    char = player.char_data
    c = tuple(char["color"])
    bx, bw = 10, 220

    # ═══ FILA SUPERIOR ═══
    y = 6
    surf.blit(_f(20).render(f"BYTES: {player.bytes}", True, GOLD), (10, y))
    surf.blit(_f(20).render(f"BAJAS: {player.kills}", True, GREEN), (155, y))
    surf.blit(_f(20).render(f"LV {player.level}", True, GREEN), (300, y))
    surf.blit(_f(20).render(f"SERVER {wave}", True, GREEN), (WIDTH - 165, y))
    surf.blit(_f(16).render(f"[{char['name']}]", True, c), (10, y + 22))
    if player.char_id == "vicente":
        vm = player.vicente_mode_names[player.vicente_mode]
        vc = player.vicente_mode_colors[player.vicente_mode]
        surf.blit(_f(14).render(f"[C] {vm}", True, vc), (95, y + 22))
    # Timer de Barrera Infinita (solo Vicente)
    if getattr(player, "invuln_timer", 0) > 0 and player.char_id == "vicente":
        bt_secs = player.invuln_timer // 60
        surf.blit(_f(18).render(f"BARRERA: {bt_secs}s", True, (100, 255, 100)), (10, y + 44))

    # ═══ ANUNCIO DE SERVIDOR (centro de pantalla) ═══
    if wave_announce > 40:
        fade = min(255, max(0, int(255 * (wave_announce - 40) / 80)))
        pulse2 = math.sin(pygame.time.get_ticks() * 0.008) * 8 + 8
        ts = int(54 + pulse2)
        t = _f(ts).render(f"SERVIDOR {wave}", True, GREEN if not wave_has_boss else RED)
        t.set_alpha(fade)
        for i in range(3):
            g = _f(ts + i * 3).render(f"SERVIDOR {wave}", True, (0, 25 - i * 6, 0))
            g.set_alpha(fade // 2)
            surf.blit(g, g.get_rect(center=(WIDTH // 2 + i + 1, HEIGHT // 2 - 72 + i + 1 + math.sin(pygame.time.get_ticks() * 0.005) * 3)))
        surf.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 70 + math.sin(pygame.time.get_ticks() * 0.005) * 3)))
        txt = "!! JEFE DEL SERVIDOR !!" if wave_has_boss else "Cargando..."
        sc = RED if wave_has_boss else (0, 200, 50)
        s = _f(26 if wave_has_boss else 22).render(txt, True, sc); s.set_alpha(fade)
        glow_rect = s.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20))
        if wave_has_boss:
            for i in range(4):
                gs = pygame.Surface((glow_rect.width + i * 20, glow_rect.height + i * 10), pygame.SRCALPHA)
                pygame.draw.rect(gs, (255, 50, 50, 15 - i * 3), gs.get_rect(), border_radius=4)
                surf.blit(gs, (glow_rect.x - i * 10, glow_rect.y - i * 5))
        surf.blit(s, glow_rect)

    # ═══ PANEL IZQUIERDO: BARRAS ═══
    # Barra de RAM (HP)
    y_hp = 44
    bar_h = 18
    hr = player.display_hp / player.max_hp
    hc = GREEN if hr > 0.5 else YELLOW if hr > 0.25 else RED
    pygame.draw.rect(surf, (0, 8, 0), (bx, y_hp, bw, bar_h))
    if hr > 0:
        fill_w = max(2, int(bw * hr))
        for i in range(bar_h):
            alpha = 80 - i * 4 if i < bar_h // 2 else 80 - (bar_h - i) * 4
            strip = pygame.Surface((fill_w, 1), pygame.SRCALPHA)
            strip.fill((*hc[:3], max(10, alpha)))
            surf.blit(strip, (bx, y_hp + i))
    pygame.draw.rect(surf, GREEN, (bx, y_hp, bw, bar_h), 1)
    surf.blit(_f(16).render(f"RAM {int(player.hp)}/{player.max_hp}", True, WHITE), (bx + 4, y_hp + 1))

    # Barra de resistencia (stamina)
    y_stam = y_hp + bar_h + 2  # 64
    sr = player.stamina / player.max_stamina
    pygame.draw.rect(surf, (0, 10, 10), (bx, y_stam, bw, 10))
    pygame.draw.rect(surf, BLUE, (bx, y_stam, int(bw * sr), 10))
    pygame.draw.rect(surf, GREEN, (bx, y_stam, bw, 10), 1)

    # Barra de experiencia (XP)
    y_xp = y_stam + 12  # 76
    xr = player.xp / max(1, player.xp_next)
    pygame.draw.rect(surf, (10, 10, 0), (bx, y_xp, bw, 8))
    pygame.draw.rect(surf, GOLD, (bx, y_xp, int(bw * xr), 8))
    pygame.draw.rect(surf, GREEN, (bx, y_xp, bw, 8), 1)

    # Munición / recarga
    y_ammo = y_xp + 10  # 86
    wp = player.char_data
    if player.reloading:
        reload_total = max(1, int(wp["reload"] / 16.67 * player.reload_mult))
        prog = max(0, min(1, 1 - player.reload_timer / reload_total))
        pygame.draw.rect(surf, (0, 30, 0), (bx, y_ammo, bw, 12))
        pygame.draw.rect(surf, GREEN, (bx, y_ammo, int(bw * prog), 12))
        surf.blit(_f(13).render("RECARGANDO...", True, WHITE), (bx + 4, y_ammo + 1))
    else:
        surf.blit(_f(13).render(f"Buffer: {player.mag}/{wp['mag'] + player.bonus_mag}  Heap: {player.reserve}", True, WHITE), (bx, y_ammo))

    # Barra de habilidad [Q]
    y_q = y_ammo + 14  # 100
    now = pygame.time.get_ticks()
    cd_remaining = max(0, player.ability_max_cd - (now - player.ability_cd))
    cd_secs = cd_remaining // 1000
    cd_ready = cd_remaining <= 0
    if player.char_id == "vicente":
        q_ability_names = {0: "IMPORT", 1: "COMPILE", 2: "BREAK"}
        ab_name = f"IMPORT({q_ability_names.get(player.vicente_mode, '?')})"
        q_color = player.vicente_mode_colors[player.vicente_mode]
    else:
        ab_name = wp["ability"].upper()
        q_color = c
    ab_bar_h = 14
    pygame.draw.rect(surf, (0, 15, 0), (bx, y_q, bw, ab_bar_h))
    if not cd_ready:
        fill_w = max(2, int(bw * (1 - cd_remaining / player.ability_max_cd)))
        pygame.draw.rect(surf, (0, 60, 20), (bx, y_q, bw, ab_bar_h))
        pygame.draw.rect(surf, q_color, (bx, y_q, fill_w, ab_bar_h))
    pygame.draw.rect(surf, GREEN, (bx, y_q, bw, ab_bar_h), 1)
    cd_text = "LISTO" if cd_ready else f"{cd_secs}s"
    surf.blit(_f(14).render(f"[Q] {ab_name}: {cd_text}", True, GREEN if cd_ready else GRAY), (bx + 4, y_q + 1))

    # Barra de ultimate [Z]
    y_z = y_q + 16  # 116
    chg = player.ability_charge
    chg_max = player.ability_max_charge
    if player.char_id == "vicente":
        z_ult_names = {0: "LIMPIADOR", 1: "RUNTIME", 2: "BARRERA"}
        ult_hint = z_ult_names.get(player.vicente_mode, "ULT")
        z_color = player.vicente_mode_colors[player.vicente_mode]
    else:
        ult_hint = "RIFF" if player.char_id == "eder" else "ULT"
        z_color = c
    pygame.draw.rect(surf, (0, 8, 0), (bx, y_z, bw, 10))
    if getattr(player, "ult_laser_active", False):
        from config import ULT_LASER_DURATION
        ult_ratio = player.ult_laser_timer / ULT_LASER_DURATION
        fill_w = max(2, int(bw * ult_ratio))
        pygame.draw.rect(surf, (200, 80, 255), (bx, y_z, fill_w, 10))
        secs_left = max(0.1, player.ult_laser_timer / max(1, ULT_LASER_DURATION))
        ult_lbl = f"[Z] RIFF {secs_left:.1f}s"
        surf.blit(_f(12).render(ult_lbl, True, (200, 100, 255)), (bx + 4, y_z + 1))
    elif getattr(player, "ult_charging", False) and player.char_id == "eder":
        from config import ULT_CHARGE_MAX
        fill_w = max(2, int(bw * player.ult_charge / ULT_CHARGE_MAX))
        pygame.draw.rect(surf, (200, 80, 255), (bx, y_z, fill_w, 10))
        surf.blit(_f(12).render("[Z] CARGANDO RIFF...", True, (200, 100, 255)), (bx + 4, y_z + 1))
    else:
        ready = "LISTO" if chg >= chg_max else f"{chg}/{chg_max}"
        if chg > 0:
            fill_w = max(2, int(bw * chg / chg_max))
            chg_color = z_color if chg < chg_max else GOLD
            pygame.draw.rect(surf, chg_color, (bx, y_z, fill_w, 10))
        surf.blit(_f(12).render(f"[Z] {ult_hint}: {ready}", True, GREEN if chg >= chg_max else GRAY), (bx + 4, y_z + 1))
    pygame.draw.rect(surf, GREEN, (bx, y_z, bw, 10), 1)

    # Barra de dominio [X]
    y_x = y_z + 12  # 128
    dchg = player.domain_charge
    dchg_max = DOMAIN_CHARGE_KILLS
    dc_ready = dchg >= dchg_max and player.domain_cd_timer <= 0 and not player.domain_active
    if player.char_id == "vicente":
        dc_color_base = player.vicente_mode_colors[player.vicente_mode]
    else:
        dc_color_base = (100, 200, 255)
    pygame.draw.rect(surf, (0, 5, 10), (bx, y_x, bw, 8))
    if dchg > 0:
        fill_w = max(2, int(bw * dchg / dchg_max))
        dc_color = dc_color_base if dchg < dchg_max else GOLD
        pygame.draw.rect(surf, dc_color, (bx, y_x, fill_w, 8))
    pygame.draw.rect(surf, dc_color_base, (bx, y_x, bw, 8), 1)
    dc_text = "LISTO" if dc_ready else f"{dchg}/{dchg_max}"
    surf.blit(_f(10).render(f"[X] DOM: {dc_text}", True, dc_color_base if dc_ready else (50, 100, 120)), (bx + 2, y_x + 1))

    # Texto de dominio activo (nombre + timer)
    y_dom = y_x + 10  # 138
    if player.domain_active:
        from config import DOMAIN_DURATION
        if player.char_id == "vicente":
            dom_name = player.vicente_domain_names[player.vicente_mode]
            dom_color = player.vicente_mode_colors[player.vicente_mode]
        else:
            from config import DOMAIN_EXPANSION
            de = DOMAIN_EXPANSION.get(player.char_id, {})
            dom_name = de.get("name", "DOMINIO")
            dom_color = de.get("color", (255, 255, 255))
        dom_ratio = player.domain_timer / max(1, DOMAIN_DURATION)
        dom_secs = max(0, player.domain_timer // 60)
        # Colored timer bar
        pygame.draw.rect(surf, (0, 8, 10), (bx, y_dom, bw, 4))
        pygame.draw.rect(surf, dom_color, (bx, y_dom, int(bw * dom_ratio), 4))
        # Domain name + time
        ds = _f(14).render(f"[DOM] {dom_name} {dom_secs}s", True, dom_color)
        ds.set_alpha(200)
        surf.blit(ds, (bx, y_dom + 6))
        y_dom += 22

    # Lista de armas equipadas
    y_weap = y_dom  # 138 or 156
    wx = bx
    for i, wname in enumerate(player.weapon_list):
        if i > 0:
            wx += _f(11).render(" | ", True, (0, 60, 20)).get_width()
        is_active = wname == player.weapon_mode
        wbinfo = WEAPON_BULLETS.get(wname, {"color": (0, 200, 255), "name": wname})
        wc = wbinfo["color"] if is_active else (0, 80, 30)
        tag = f"[{i+1}]{wbinfo['name']}"
        tag_s = _f(11).render(tag, True, wc)
        surf.blit(tag_s, (wx, y_weap))
        wx += tag_s.get_width()

    # Contador de enemigos
    y_ene = y_weap + 14  # 152 or 170
    if wave_state != "idle":
        surf.blit(_f(15).render(f"Procesos: {enemies_count}", True, GREEN), (bx, y_ene))

    # Bombas equipadas
    y_bomb = y_ene + 18  # 170 or 188
    if player.bomb_queue:
        b_idx = max(0, min(player.bomb_active_idx, len(player.bomb_queue) - 1))
        btype = player.bomb_queue[b_idx]
        binfo = BOMB_TYPES.get(btype, {})
        bcolor = binfo.get("color", (255, 200, 100))
        surf.blit(_f(13).render(f"[G] BOMBA x{player.bomb_count}", True, bcolor), (bx, y_bomb))
        surf.blit(_f(11).render(f"{binfo.get('name', '?')} - {binfo.get('desc', '')}", True, bcolor), (bx + 2, y_bomb + 14))
        y_bomb += 30

    # Auras activas
    y_aura = y_bomb + 4
    for aura in (player.auras if hasattr(player, "auras") else []):
        ac = {"fire":(255,100,50),"ice":(100,200,255),"shield":(50,150,255)}.get(aura, (200,200,200))
        surf.blit(_f(12).render(f"AURA: {aura.upper()}", True, ac), (bx + 2, y_aura))
        y_aura += 14

    # ═══ LADO DERECHO ═══
    # Minimap (top-right)
    _draw_minimap(surf, game)

    # FPS debajo del minimapa
    y_right = 148
    surf.blit(_f(14).render(f"FPS: {fps}", True, (0, 120, 0)), (WIDTH - 170, y_right))
    y_right += 18

    # Barras de power-ups activos
    pw_x = WIDTH - 155
    pw_items = []
    if player.turbo_timer > 0:
        pw_items.append(("TURBO", player.turbo_timer, 480, (255, 100, 50)))
    if player.shield_timer > 0:
        pw_items.append(("ESCUDO", player.shield_timer, 480, (50, 150, 255)))
    if player.explosive_timer > 0:
        pw_items.append(("EXPLOSIVO", player.explosive_timer, 360, (255, 80, 80)))
    if player.byte_mult_timer > 0:
        pw_items.append(("BYTE x2", player.byte_mult_timer, 600, (255, 210, 55)))
    for label, timer, max_t, color in pw_items:
        r = timer / max_t
        surf.blit(_f(12).render(label, True, color), (pw_x, y_right))
        pygame.draw.rect(surf, (0, 0, 0), (pw_x, y_right + 14, 140, 8))
        pygame.draw.rect(surf, color, (pw_x, y_right + 14, int(140 * r), 8))
        pygame.draw.rect(surf, (0, 255, 65), (pw_x, y_right + 14, 140, 8), 1)
        y_right += 26

    # Inventario de ítems de evolución (abajo a la derecha)
    if game and hasattr(game.player, "evolution_items"):
        draw_inventory(surf, game.player)

    # ═══ PARTE INFERIOR ═══
    # Barra de HP del jefe Vicente (fases)
    y_boss = HEIGHT - 90
    vb = None
    for e in list(game.enemies):
        if getattr(e, "etype", None) == "vicente_boss":
            vb = e
            break
    if vb is not None:
        seg_w = 72
        gap = 4
        total_w = seg_w * 4 + gap * 3
        bx2 = WIDTH // 2 - total_w // 2
        ph = vb._vb_phase
        phase_colors = {1: (100, 200, 255), 2: (80, 180, 240), 3: (150, 100, 255), 4: (255, 100, 100)}
        seg_hp = vb.max_hp / 4
        for i in range(4):
            sx = bx2 + i * (seg_w + gap)
            fill = max(0, min(1, (vb.hp - i * seg_hp) / seg_hp))
            c = (60, 60, 80) if i + 1 > ph else phase_colors.get(i + 1, (100, 200, 255))
            pygame.draw.rect(surf, (20, 20, 30), (sx, y_boss, seg_w, 14))
            pygame.draw.rect(surf, c, (sx, y_boss, int(seg_w * fill), 14))
            pygame.draw.rect(surf, (150, 220, 255) if i + 1 == ph else (60, 60, 80), (sx, y_boss, seg_w, 14), 1)
        nm = _f(14).render(f"VICENTE — Legado Python  Fase {ph}/4", True, (100, 200, 255))
        surf.blit(nm, (WIDTH // 2 - nm.get_width() // 2, y_boss - 18))
    else:
        boss_hp_total = 0
        boss_hp_max = 0
        for e in list(game.enemies):
            if hasattr(e, "is_boss") and e.is_boss:
                boss_hp_total += e.hp
                boss_hp_max += e.max_hp
        if boss_hp_max > 0:
            bw2 = 300
            bx2 = WIDTH // 2 - bw2 // 2
            br = boss_hp_total / boss_hp_max
            bc = GREEN if br > 0.5 else YELLOW if br > 0.25 else RED
            pygame.draw.rect(surf, (0, 0, 0), (bx2, y_boss, bw2, 16))
            pygame.draw.rect(surf, bc, (bx2, y_boss, int(bw2 * br), 16))
            pygame.draw.rect(surf, (0, 255, 65), (bx2, y_boss, bw2, 16), 1)
            surf.blit(_f(14).render(f"JEFE  {int(br * 100)}%", True, WHITE), (bx2 + 4, y_boss + 1))

    # Notificaciones temporales
    ny = HEIGHT - 30
    for n in reversed(notifs):
        s = _f(16).render(n.text, True, n.color)
        s.set_alpha(int(255 * n.life / n.max_life))
        nx = WIDTH // 2 - s.get_width() // 2
        surf.blit(s, (max(5, min(WIDTH - s.get_width() - 5, nx)), ny))
        ny -= 22
        if ny < y_boss - 24:
            break

    # ═══ MIRA (CROSSHAIR) ═══
    mx, my = pygame.mouse.get_pos()
    c2 = GREEN
    pygame.draw.line(surf, c2, (mx - 10, my), (mx - 4, my), 2)
    pygame.draw.line(surf, c2, (mx + 4, my), (mx + 10, my), 2)
    pygame.draw.line(surf, c2, (mx, my - 10), (mx, my - 4), 2)
    pygame.draw.line(surf, c2, (mx, my + 4), (mx, my + 10), 2)
    pygame.draw.circle(surf, GREEN, (mx, my), 2)

    # ═══ TIEMPO DE PREPARACIÓN / TEXTO CENTRAL ═══
    if wave_state == "prep":
        secs = max(0, prep_timer // 60)
        mins = secs // 60
        sec = secs % 60
        pcolor = RED if secs < 10 else YELLOW if secs < 20 else GREEN
        timer_s = _f(28).render(f"PREPARACION  {mins}:{sec:02d}", True, pcolor)
        surf.blit(timer_s, timer_s.get_rect(center=(WIDTH // 2, 50)))
        s = _f(14).render("Vicente esta en el mapa! Buscalo [$] para comprar mejoras", True, (0, 140, 40))
        surf.blit(s, s.get_rect(center=(WIDTH // 2, 80)))

        # NPC near prompt (single unified box)
        if not shop_open:
            box_w, box_h = 280, 40
            bx3 = WIDTH // 2 - box_w // 2
            by3 = HEIGHT - 80
            if vicente_near:
                draw_rrect(surf, (40, 30, 5), (bx3, by3, box_w, box_h))
                draw_rrect(surf, SEL, (bx3, by3, box_w, box_h), r=2)
                surf.blit(_f(16).render("VICENTE  [F] comprar  [ESP] saltar", True, SEL), (bx3 + 8, by3 + 10))
            elif oscar_near:
                draw_rrect(surf, (40, 30, 5), (bx3, by3, box_w, box_h))
                draw_rrect(surf, (200, 180, 50), (bx3, by3, box_w, box_h), r=2)
                surf.blit(_f(16).render("OSCAR  [F] comprar  [ESP] saltar", True, (200, 180, 50)), (bx3 + 8, by3 + 10))

    # Entrada de comandos del administrador
    if game and getattr(game, "admin_inputting", False):
        box_w, box_h = 400, 60
        bx3, by3 = WIDTH // 2 - box_w // 2, HEIGHT // 2 - box_h // 2
        draw_rrect(surf, (10, 10, 30), (bx3, by3, box_w, box_h))
        draw_rrect(surf, (0, 200, 255), (bx3, by3, box_w, box_h), r=2)
        inp = _f(22).render("ADMIN: " + game.admin_input + "_", True, (0, 255, 255))
        surf.blit(inp, (bx3 + 10, by3 + 10))
        lbl = _f(14).render(",=Abrir  Enter=Confirmar  Esc=Cancelar", True, (100, 200, 255))
        surf.blit(lbl, (bx3 + 10, by3 + 35))

    # Indicador de modo administrador activo
    if game and getattr(game, "admin_mode", False):
        t = _f(24).render("ADMIN MODE", True, (0, 255, 255))
        pygame.draw.rect(surf, (0, 0, 0), (WIDTH // 2 - t.get_width() // 2 - 6, 32, t.get_width() + 12, 30))
        surf.blit(t, (WIDTH // 2 - t.get_width() // 2, 35))


# Dibuja la tienda (Vicente u Oscar) con rejilla de objetos
# Tooltip helper: renders effect comparison text for a shop item
def _shop_tooltip(surf, player, item, is_oscar, x, y, game=None):
    tw = 220
    pygame.draw.rect(surf, (0, 15, 0), (x, y, tw, HEIGHT - y - 10), border_radius=4)
    pygame.draw.rect(surf, (0, 50, 15), (x, y, tw, HEIGHT - y - 10), 1, border_radius=4)
    tx = x + 10
    ty = y + 10
    surf.blit(_f(15).render(item["name"], True, GREEN), (tx, ty))
    ty += 22
    surf.blit(_f(11).render(item["desc"], True, WHITE), (tx, ty))
    ty += 18
    if not is_oscar:
        iid = item["id"]
        lvl = player.shop_levels.get(iid, 0)
        mx = item["max"]
        surf.blit(_f(11).render(f"Nivel: {lvl}/{mx}", True, GOLD), (tx, ty))
        ty += 16
        if iid == "firerate":
            before = int(player.fire_rate * player.fr_mult)
            after = int(player.fire_rate * player.fr_mult * 0.9)
            surf.blit(_f(11).render(f"FR: {before}ms -> {after}ms", True, WHITE), (tx, ty))
        elif iid == "dmg":
            surf.blit(_f(11).render(f"Daño: {player.damage} -> {player.damage+3}", True, WHITE), (tx, ty))
        elif iid == "hp":
            surf.blit(_f(11).render(f"HP: {player.max_hp} -> {player.max_hp+20}", True, WHITE), (tx, ty))
        elif iid == "multishot":
            surf.blit(_f(11).render(f"Balas: {player.shots} -> {player.shots+1}", True, WHITE), (tx, ty))
        elif iid == "speed":
            spd = player.base_speed + player.bonus_speed
            surf.blit(_f(11).render(f"Vel: {spd:.1f} -> {spd+0.1:.1f}", True, WHITE), (tx, ty))
        elif iid == "mag":
            surf.blit(_f(11).render(f"Mag: {player.max_mag} -> {player.max_mag+5}", True, WHITE), (tx, ty))
        elif iid == "reload":
            surf.blit(_f(11).render(f"Recarga: {player.reload_time}ms -> {int(player.reload_time*0.85)}ms", True, WHITE), (tx, ty))
        elif iid == "piercing":
            surf.blit(_f(11).render(f"Perforar: {player.piercing} -> {player.piercing+1}", True, WHITE), (tx, ty))
        elif iid == "lifesteal":
            surf.blit(_f(11).render(f"Vamp: {player.vampirism*100:.0f}% -> {(player.vampirism+0.05)*100:.0f}%", True, WHITE), (tx, ty))
        elif iid == "knockback":
            surf.blit(_f(11).render(f"Retroceso: {player.knockback:.1f} -> {player.knockback+0.2:.1f}", True, WHITE), (tx, ty))
    else:
        tid = item.get("type", "")
        # Ally preview card
        if tid.startswith("ally_"):
            aid = tid.replace("ally_", "")
            if aid == "irvin": aid = "irvin_sis"
            elif aid == "usiel": aid = "usiel_sis"
            ad = ALLY_TYPES.get(aid, {})
            if ad:
                for k, v in ad.items():
                    if k == "name":
                        surf.blit(_f(12).render(f"Nombre: {v}", True, ad.get("color", WHITE)), (tx, ty))
                    elif k in ("hp", "dmg", "speed", "fr", "range"):
                        surf.blit(_f(11).render(f"{k}: {v}", True, WHITE), (tx, ty+14))
                    ty += 14
        elif tid.startswith("bomb_"):
            btype = tid.replace("bomb_", "")
            bd = BOMB_TYPES.get(btype, {})
            if bd:
                surf.blit(_f(11).render(f"Daño: {bd.get('dmg','?')}", True, WHITE), (tx, ty))
                surf.blit(_f(11).render(f"Radio: {bd.get('radius','?')}px", True, WHITE), (tx, ty+14))
                surf.blit(_f(11).render(f"{bd.get('desc','')}", True, GRAY), (tx, ty+28))
        elif tid.startswith("buff_"):
            btype = tid.replace("buff_", "")
            dur = item.get("desc", "")
            surf.blit(_f(11).render(f"Duración: 8s", True, WHITE), (tx, ty))
        elif tid.startswith("aura_"):
            atype = tid.replace("aura_", "")
            if atype in player.auras:
                surf.blit(_f(11).render("YA ACTIVA", True, GOLD), (tx, ty))
        elif tid.startswith("perm_"):
            ptype = tid.replace("perm_", "")
            lvl = player.shop_levels.get(f"oscar_{ptype}", 0) if hasattr(player, "shop_levels") else 0
            surf.blit(_f(11).render(f"Comprado: {lvl} vez/ces", True, WHITE), (tx, ty))
            if ptype == "hp":
                surf.blit(_f(11).render(f"HP: {player.max_hp} -> {player.max_hp+10}", True, WHITE), (tx, ty+14))
            elif ptype == "speed":
                spd = player.base_speed + player.bonus_speed
                surf.blit(_f(11).render(f"Vel: {spd:.1f} -> {spd+0.05:.1f}", True, WHITE), (tx, ty+14))
            elif ptype == "dmg":
                surf.blit(_f(11).render(f"Daño: {player.damage} -> {player.damage+3}", True, WHITE), (tx, ty+14))
            elif ptype == "firerate":
                before = int(player.fire_rate * player.fr_mult)
                after = int(player.fire_rate * player.fr_mult * 0.9)
                surf.blit(_f(11).render(f"FR: {before}ms -> {after}ms", True, WHITE), (tx, ty+14))
        elif tid.startswith("unique_"):
            surf.blit(_f(11).render("Item único permanente", True, GOLD), (tx, ty))
        else:
            surf.blit(_f(11).render(f"Costo: {item.get('cost','?')} bytes", True, WHITE), (tx, ty))

# Draws the shop overlay with grid, tabs for Oscar, tooltip panel, and purchase flash
def draw_shop(surf, player, sel, items, game=None):
    is_oscar = len(items) > 0 and "id" not in items[0]
    o = pygame.Surface((WIDTH, HEIGHT))
    o.set_alpha(210); o.fill((0, 0, 0))
    surf.blit(o, (0, 0))
    draw_terminal_frame(surf, SEL, 40)
    draw_scanlines(surf, 15)

    glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    title_color = (200, 180, 50) if is_oscar else SEL
    pygame.draw.circle(glow, (*title_color[:3], 8), (WIDTH // 2, 40), 180)
    surf.blit(glow, (0, 0))

    vendor_name = "Oscar" if is_oscar else "Vicente"
    title = f"import {vendor_name.lower()}_shop"
    t = _f(36).render(title, True, title_color)
    for i in range(3):
        g = _f(36 + i * 2).render(title, True, (max(0,40-i*10), max(0,30-i*8), 5 - i*2) if not is_oscar else (max(0,40-i*10), max(0,35-i*8), 5 - i*2))
        surf.blit(g, (WIDTH // 2 - g.get_width() // 2 + i, 41 + i))
    surf.blit(t, t.get_rect(center=(WIDTH // 2, 40)))
    surf.blit(_f(16).render(f"BYTES: {player.bytes}", True, GOLD), (150, 55))

    vendor_lines = {
        "Vicente": ["Vicente: 'Que modulo quieres?'", "Vicente: 'Mejora tu sistema!'", "Vicente: 'Paga en bytes!'"],
        "Oscar":   ["Oscar: 'Power-ups frescos!'", "Oscar: 'Aliados de confianza!'", "Oscar: 'Solo los mejores bytes!'"],
    }[vendor_name]
    vline = vendor_lines[int(pygame.time.get_ticks() / 3000) % len(vendor_lines)]
    surf.blit(_f(14).render(vline, True, title_color), (150, 75))

    # Category tabs for Oscar
    tab_names = ["TODOS", "BUFFS", "ALIADOS", "BOMBAS", "PERMS", "AURAS", "UNIQUE"]
    tab_types = ["", "buff_", "ally_", "bomb_", "perm_", "aura_", "unique_"]
    current_tab = getattr(game, "shop_tab", 0) if game else 0
    if is_oscar:
        tab_x = 150
        for ti, tn in enumerate(tab_names):
            tc = title_color if ti == current_tab else GRAY
            ts = _f(13).render(tn, True, tc)
            surf.blit(ts, (tab_x, 95))
            if ti == current_tab:
                surf.blit(_f(13).render("_", True, title_color), (tab_x, 105))
            tab_x += ts.get_width() + 14

    # Filter items for Oscar tabs
    filtered = list(items)
    if is_oscar and current_tab > 0:
        filtered = [it for it in items if it.get("type", "").startswith(tab_types[current_tab])]
    if not filtered:
        surf.blit(_f(18).render("(vacio)", True, GRAY), (WIDTH // 2 - 50, HEIGHT // 2))
        hint = _f(15).render("<-  ->  A/D  W/S Navegar  ENTER=Comprar  F=Cerrar", True, (180, 140, 35))
        surf.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 27)))
        return

    # Adjust sel to stay within filtered bounds
    sel_in_filtered = sel if not is_oscar else min(sel, len(filtered) - 1)

    # Unified grid with scroll to keep selected item visible
    cols = 5
    card_w, card_h = 130, 90
    gap = 10
    start_x = 30
    start_y = 120
    # Compute scroll offset to keep selected item visible
    sel_row = sel_in_filtered // cols
    visible_rows = (HEIGHT - start_y - 50) // (card_h + gap)
    scroll_offset = max(0, sel_row - visible_rows + 2) * (card_h + gap)

    # Purchase flash
    flash_timer = getattr(game, "shop_flash_timer", 0) if game else 0
    flash_id = getattr(game, "shop_flash_id", None) if game else None

    for i, item in enumerate(filtered):
        bx = start_x + (i % cols) * (card_w + gap)
        by = start_y + (i // cols) * (card_h + gap) - scroll_offset
        bw, bh = card_w, card_h
        # Skip items above or below screen
        if by + bh < start_y - 10 or by > HEIGHT - 30:
            continue

        cost = item.get("cost", 0)
        can_buy = player.bytes >= cost
        if not is_oscar:
            can_buy = can_buy and player.shop_levels.get(item["id"], 0) < item["max"]
        else:
            # Oscar perm items can be purchased multiple times (scaled price)
            tid = item.get("type", "")
            if tid.startswith("perm_"):
                ptype = tid.replace("perm_", "")
                oscar_lvl = player.shop_levels.get(f"oscar_{ptype}", 0) if hasattr(player, "shop_levels") else 0
                can_buy = can_buy  # always can buy if enough bytes

        is_sel = i == sel_in_filtered

        # Grab indicador compra
        item_flash_id = item.get("id", item.get("type", ""))
        if flash_timer > 0 and flash_id is not None and flash_id == item_flash_id:
            bg = (20, 60, 10) if (flash_timer // 4) % 2 == 0 else (0, 40, 5)
            draw_rrect(surf, bg, (bx, by, bw, bh))
            draw_glow(surf, GREEN, (bx + bw // 2, by + bh // 2), 60, 20)
        else:
            bg = (40, 30, 5) if is_sel else (0, 25, 5)
            draw_rrect(surf, bg, (bx, by, bw, bh))

        if is_sel:
            sel_color = title_color if can_buy else RED
            draw_glow(surf, sel_color, (bx + bw // 2, by + bh // 2), 55, 25)
            pygame.draw.rect(surf, sel_color, (bx - 2, by - 2, bw + 4, bh + 4), 1, border_radius=6)

        txt_color = GREEN if can_buy else GRAY
        name_s = _f(13).render(item["name"], True, txt_color)
        surf.blit(name_s, (bx + 6, by + 6))
        surf.blit(_f(10).render(item["desc"], True, WHITE if can_buy else (80, 80, 80)), (bx + 6, by + 22))

        if not is_oscar:
            lvl = player.shop_levels.get(item["id"], 0)
            lvl_color = GREEN if lvl < item["max"] else GOLD
            surf.blit(_f(10).render(f"Niv {lvl}/{item['max']}", True, lvl_color), (bx + 6, by + 38))
        cost_c = GOLD if can_buy else RED
        surf.blit(_f(12).render(f"{cost} B", True, cost_c), (bx + 6, by + 52))

        if is_oscar:
            status = "" if can_buy else "No tienes"
        elif lvl >= item["max"]:
            status = "MAX"
        elif not can_buy:
            status = "No tienes"
        else:
            status = ""
        if status:
            surf.blit(_f(10).render(status, True, GOLD if status == "MAX" else RED), (bx + 6, by + 68))
        elif can_buy:
            surf.blit(_f(10).render("ENTER=Comprar", True, title_color), (bx + 6, by + 68))

    # Tooltip panel on the right side
    if filtered:
        tt_item = filtered[sel_in_filtered]
        _shop_tooltip(surf, player, tt_item, is_oscar, WIDTH - 240, start_y - 10, game)

    hint = _f(15).render("<-  ->  A/D  W/S Navegar  TAB=Categoria  ENTER=Comprar  F=Cerrar", True, (180, 140, 35))
    surf.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 27)))


# Pantalla principal del menú con lluvia de matrices y logo ASCII
class MainMenu:
    def __init__(self):
        self.sel = 0
        self.opts = ["JUGAR", "CARGAR PARTIDA", "CONTROLES", "CREDITOS", "SALIR"]
        from src.effects import MatrixRain
        self.rain = MatrixRain(WIDTH, HEIGHT)
        self.timer = 0
        self.cursor_vis = True
        self.cursor_timer = 0
        self.glitch_timer = 400
        self.glitch = 0
        self.glitch_active = False
        self.scan_y = 0
        self.scan_dir = 1
        self.logs = []
        self._init_logs()

    # Inicializa los logs del sistema que flotan hacia arriba
    def _init_logs(self):
        lines = [
            "SYS:: INICIANDO SECUENCIA DE CORRUPCION...",
            "SYS:: BYPASSANDO CORTEFUEGOS...",
            "SYS:: INYECTANDO CARGA UTIL...",
            "SYS:: SISTEMA COMPROMETIDO",
            "SYS:: ACCESO A SHELL DE RAICES",
            "SYS:: DESPLEGANDO MALWARE...",
            "SYS:: CIFRANDO FLUJOS DE DATOS...",
            "SYS:: TERMINAL VIRUS v1.0 ACTIVA",
        ]
        for i, line in enumerate(lines):
            self.logs.append({"text": line, "alpha": 20 + i * 10, "y": HEIGHT - 90 + i * 14})

    # Anima los logs del sistema (movimiento vertical)
    def _update_logs(self):
        for log in self.logs:
            if log["y"] > HEIGHT + 10:
                log["y"] = HEIGHT - 100
                log["alpha"] = 20
            log["y"] -= 0.15
            if log["alpha"] < 200:
                log["alpha"] += 0.3

    # Actualiza animaciones, cursor, lluvia y efecto glitch
    # Actualiza animaciones y efecto glitch
    def update(self):
        self.timer += 1
        self.rain.update()
        self._update_logs()

        self.glitch_timer -= 1
        if self.glitch_timer <= 0:
            self.glitch_active = not self.glitch_active
            self.glitch = random.randint(-6, 6)
            self.glitch_timer = random.randint(200, 800) if self.glitch_active else random.randint(10, 40)

        self.scan_y += self.scan_dir * 0.8
        if self.scan_y > HEIGHT - 100 or self.scan_y < 100:
            self.scan_dir *= -1

    # Dibuja el menú principal completo con logo, opciones y efectos
    def draw(self, surf):
        surf.fill((0, 3, 0))
        self.rain.draw(surf)
        draw_scanlines(surf)
        draw_terminal_frame(surf, GREEN, 50)

        now = pygame.time.get_ticks()

        glow_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (0, 255, 65, 6), (WIDTH // 2, 120), 200)
        surf.blit(glow_surf, (0, 0))

        logo_lines = [
            "██╗   ██╗██╗██████╗ ██╗   ██╗███████╗",
            "██║   ██║██║██╔══██╗██║   ██║██╔════╝",
            "██║   ██║██║██████╔╝██║   ██║███████╗",
            "╚██╗ ██╔╝██║██╔══██╗██║   ██║╚════██║",
            " ╚████╔╝ ██║██║  ██║╚██████╔╝███████║",
            "  ╚═══╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝",
        ]

        glitch_off = self.glitch if self.glitch_active else 0
        pulse = math.sin(now * 0.002) * 0.08 + 1
        logo_fs = int(13 * pulse)
        logo_y_start = 30

        for li, line in enumerate(logo_lines):
            render_line = "".join(random.choice("01█▓▒░") if random.random() < 0.3 else ch for ch in line) if self.glitch_active and random.random() < 0.3 else line
            lg = _f(logo_fs).render(render_line, True, (0, 40, 10))
            lg.set_alpha(60)
            surf.blit(lg, (WIDTH // 2 - lg.get_width() // 2 + 2, logo_y_start + li * 14 + 2))
            lt = _f(logo_fs).render(render_line, True, GREEN)
            lx = WIDTH // 2 - lt.get_width() // 2
            if self.glitch_active and li == random.randint(0, 5):
                lx += glitch_off
            surf.blit(lt, (lx, logo_y_start + li * 14))

        title_y = logo_y_start + 6 * 14 + 10
        pulse2 = math.sin(now * 0.003) * 0.06 + 1
        title_fs = int(28 * pulse2)
        title = "VIRUS"
        for i in range(4):
            off = (i + 1) * 2
            g = _f(title_fs + off).render(title, True, (0, 25 - i * 6, 0))
            gx = WIDTH // 2 - g.get_width() // 2 + i + 1
            gy = title_y - g.get_height() // 2 + i + 1
            surf.blit(g, (gx, gy))
        title_surf = _f(title_fs).render(title, True, GREEN)
        tx = WIDTH // 2 - title_surf.get_width() // 2
        if self.glitch_active:
            tx += glitch_off
        surf.blit(title_surf, (tx, title_y - title_surf.get_height() // 2))

        if self.scan_y > title_y - 30 and self.scan_y < title_y + 30:
            scan_surf = pygame.Surface((WIDTH, 2), pygame.SRCALPHA)
            scan_surf.fill((0, 255, 65, 60))
            surf.blit(scan_surf, (0, self.scan_y))

        sub = _f(18).render(">> SISTEMA CORROMPIDO <<", True, (0, 130, 40))
        sub.set_alpha(160)
        surf.blit(sub, sub.get_rect(center=(WIDTH // 2, title_y + 22)))

        for log in self.logs:
            if 0 < log["y"] < HEIGHT:
                s = _f(12).render(log["text"], True, (0, 80, 20))
                s.set_alpha(min(180, int(log["alpha"])))
                surf.blit(s, (50, log["y"]))

        for i, opt in enumerate(self.opts):
            is_sel = i == self.sel
            by = HEIGHT // 2 - 10 + i * 55
            bw, bh = 280, 44
            bx = WIDTH // 2 - bw // 2
            c = SEL if is_sel else (0, 100, 30)

            if is_sel:
                draw_glow(surf, SEL, (bx + bw // 2, by + bh // 2), 50, 120)
                draw_rrect(surf, (40, 30, 5), (bx, by, bw, bh))
                draw_rrect(surf, (60, 50, 10), (bx + 2, by + 2, bw - 4, bh - 4))
                pygame.draw.rect(surf, SEL, (bx - 2, by - 2, bw + 4, bh + 4), 1, border_radius=6)
                prefix = "> "
            else:
                draw_rrect(surf, (0, 15, 4), (bx, by, bw, bh))
                draw_rrect(surf, (0, 22, 6), (bx + 2, by + 2, bw - 4, bh - 4))
                prefix = "  "

            txt = prefix + opt
            t = _f(24).render(txt, True, c)
            surf.blit(t, (bx + bw // 2 - t.get_width() // 2, by + bh // 2 - 12))

            if is_sel:
                bar = pygame.Surface((bw, 2), pygame.SRCALPHA)
                bar.fill((0, 255, 65, 40))
                surf.blit(bar, (bx, by + bh + 4))

        if self.glitch_active and random.random() < 0.4:
            for _ in range(2):
                gy = random.randint(0, HEIGHT)
                gh = random.randint(1, 4)
                gl = pygame.Surface((WIDTH, gh))
                gl.set_alpha(random.randint(30, 80))
                gl.fill((0, 255, 65))
                surf.blit(gl, (random.randint(-10, 10), gy))

        prompt = "root@virus:~$ "
        prompt_surf = _f(16).render(prompt, True, (0, 150, 50))
        prompt_x = 30
        prompt_y = HEIGHT - 55
        surf.blit(prompt_surf, (prompt_x, prompt_y))
        if self.cursor_vis:
            cursor = _f(16).render("_", True, GREEN)
            surf.blit(cursor, (prompt_x + prompt_surf.get_width(), prompt_y))

        hint = _f(15).render("\u2191 \u2193 Navegar  ENTER=Seleccionar  ESC=Salir  RATON=Click", True, (0, 70, 25))
        surf.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 26)))


# Pantalla de selección de mapa con tarjetas descriptivas
class MapSelector:
    def __init__(self):
        self.sel = 0
        self.timer = 0
        self.entries = {}
        self.card_w, self.card_h = 300, 320
        self.gap = 30
        self.total_w = len(MAPS) * self.card_w + (len(MAPS) - 1) * self.gap
        self.start_x = (WIDTH - self.total_w) // 2
        self.start_y = 150
        self.particles = []
        from src.effects import MatrixRain
        self.rain = MatrixRain(WIDTH, HEIGHT)

    def reset_animation(self):
        self.entries = {}
        self.particles = []

    # Actualiza animaciones de las tarjetas y partículas
    def update(self, mouse_pos=None):
        self.timer += 1
        self.rain.update()
        for i in range(len(MAPS)):
            if i not in self.entries:
                self.entries[i] = HEIGHT + 100
            if self.entries[i] > 0:
                self.entries[i] -= max(1, (self.entries[i] - 0) * 0.08)
                if abs(self.entries[i]) < 1:
                    self.entries[i] = 0
        if self.timer % 3 == 0:
            bx = self.start_x + self.sel * (self.card_w + self.gap)
            by = self.start_y
            cx = bx + self.card_w // 2
            cy = by + self.card_h // 2
            for _ in range(2):
                a = random.uniform(0, math.tau)
                r = random.uniform(5, 14)
                self.particles.append({
                    "x": cx + math.cos(a) * r, "y": cy + math.sin(a) * r,
                    "vx": math.cos(a) * random.uniform(-0.3, 0.3),
                    "vy": math.sin(a) * random.uniform(-0.3, 0.3),
                    "life": random.randint(15, 30), "max_life": 30,
                    "color": GREEN, "radius": random.uniform(1.5, 3),
                })
        for p in self.particles[:]:
            p["x"] += p["vx"]; p["y"] += p["vy"]; p["life"] -= 1
            if p["life"] <= 0:
                self.particles.remove(p)

    def get_card_rects(self):
        rects = []
        for i in range(len(MAPS)):
            bx = self.start_x + i * (self.card_w + self.gap)
            rects.append((i, pygame.Rect(bx, self.start_y, self.card_w, self.card_h)))
        return rects

    # Dibuja un ícono pixel-art para cada mapa (edificio, árbol, playa)
    def _draw_map_icon(self, s, i, size):
        cx, cy = size // 2, size // 2
        if i == 0:  # Campus - building
            w, h = size * 0.6, size * 0.7
            rx, ry = int(cx - w / 2), int(cy - h / 2 + 4)
            rw, rh = int(w), int(h)
            pygame.draw.rect(s, (100, 100, 120), (rx, ry, rw, rh))
            pygame.draw.rect(s, (60, 60, 80), (rx, ry, rw, rh), 2)
            for wx in range(rx + 4, rx + rw - 3, 8):
                pygame.draw.rect(s, (80, 200, 255), (wx, ry + 4, 4, 5))
                pygame.draw.rect(s, (80, 200, 255), (wx, ry + 13, 4, 5))
            # door
            pygame.draw.rect(s, (40, 30, 20), (cx - 4, ry + rh - 10, 8, 10))
        elif i == 1:  # Forest - tree
            trunk_w, trunk_h = 6, size * 0.35
            tx, ty = cx - trunk_w // 2, cy + 2
            pygame.draw.rect(s, (80, 50, 20), (tx, ty - trunk_h, trunk_w, trunk_h))
            # canopy layers
            for layer in range(3):
                ly = cy - 8 - layer * 12
                lw = size * 0.5 - layer * 6
                lh = 14
                pts = [(cx, ly - lh), (cx - lw / 2, ly), (cx + lw / 2, ly)]
                pygame.draw.polygon(s, (20, 100 + layer * 20, 10), pts)
        else:  # Beach - sun + wave
            # sun
            pygame.draw.circle(s, (255, 220, 50), (cx, cy - 8), 10)
            for a in range(0, 360, 45):
                ra = math.radians(a)
                sx = cx + math.cos(ra) * 14
                sy = cy - 8 + math.sin(ra) * 14
                pygame.draw.line(s, (255, 200, 50), (cx + math.cos(ra) * 10, cy - 8 + math.sin(ra) * 10), (sx, sy), 2)
            # wave
            for wx in range(cx - 18, cx + 18, 4):
                wy = cy + 10 + int(math.sin(wx * 0.4) * 4)
                pygame.draw.circle(s, (50, 150, 220), (wx, wy), 3)

    def draw(self, surf):
        surf.fill((0, 3, 0))
        self.rain.draw(surf)
        draw_scanlines(surf)
        draw_terminal_frame(surf, GREEN, 40)

        title = _f(32).render("SELECCIONA EL MAPA", True, GREEN)
        surf.blit(title, title.get_rect(center=(WIDTH // 2, 60)))

        now = pygame.time.get_ticks()
        for i, m in enumerate(MAPS):
            bx = self.start_x + i * (self.card_w + self.gap)
            by = self.start_y + self.entries[i]
            selected = i == self.sel
            pulse = math.sin(now * 0.003 + i) * 0.06 + 1
            cw = int(self.card_w * pulse)

            # Card background
            card_alpha = 200 if selected else 140
            card_surf = pygame.Surface((cw, self.card_h), pygame.SRCALPHA)
            border_col = GREEN if selected else (0, 60, 20)
            card_surf.fill((0, 20, 5, card_alpha))
            pygame.draw.rect(card_surf, border_col, card_surf.get_rect(), 2, border_radius=8)
            surf.blit(card_surf, (bx - (cw - self.card_w) // 2, by))

            # Map name
            cx = bx + self.card_w // 2
            name_color = (0, 255, 100) if selected else (0, 200, 80)
            name = _f(24).render(m["name"], True, name_color)
            surf.blit(name, (cx - name.get_width() // 2, by + 20))

            # Map description
            desc_lines = self._wrap_text(m["desc"], _f(16), self.card_w - 30)
            for li, line in enumerate(desc_lines):
                dc = _f(16).render(line, True, (0, 180, 80))
                surf.blit(dc, (bx + 15, by + 70 + li * 22))

            # Map icon
            icon_size = 80
            icon_y = by + 70 + len(desc_lines) * 22 + 10
            icon_x = bx + (self.card_w - icon_size) // 2
            icon_surf = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
            icon_surf.fill((0, 0, 0, 0))
            pygame.draw.rect(icon_surf, (0, 40, 10), (0, 0, icon_size, icon_size), 1, border_radius=4)
            self._draw_map_icon(icon_surf, i, icon_size)
            surf.blit(icon_surf, (icon_x, icon_y))

            # Selection indicator
            if selected:
                gf = _f(42)
                check = gf.render("\u2714", True, GREEN)
                pulse_a = int(200 + math.sin(now * 0.005 + i) * 55)
                check.set_alpha(pulse_a)
                surf.blit(check, (bx + cw - 90, by + 10))
                # Pulse glow ring
                gr = 8 + int(math.sin(now * 0.004 + i) * 3)
                for r in range(gr, 0, -1):
                    a = 60 // (gr - r + 1) if gr - r + 1 > 0 else 60
                    glow_surf = pygame.Surface((cw + r * 2, self.card_h + r * 2), pygame.SRCALPHA)
                    pygame.draw.rect(glow_surf, (*GREEN[:3], a), glow_surf.get_rect(), 2, border_radius=10)
                    surf.blit(glow_surf, (bx - (cw - self.card_w) // 2 - r, by - r))

        # Particles
        for p in self.particles:
            a = int(255 * p["life"] / p["max_life"])
            s = pygame.Surface((int(p["radius"] * 2),) * 2, pygame.SRCALPHA)
            pygame.draw.circle(s, (*p["color"][:3], a), (p["radius"], p["radius"]), p["radius"])
            surf.blit(s, (int(p["x"] - p["radius"]), int(p["y"] - p["radius"])))

        hint = _f(15).render("\u2190 \u2192 Navegar  ENTER=Seleccionar  ESC=Volver", True, (0, 70, 25))
        surf.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 26)))

    def _wrap_text(self, text, font, max_width):
        words = text.split()
        lines = []
        cur = ""
        for w in words:
            test = cur + (" " if cur else "") + w
            if font.size(test)[0] <= max_width:
                cur = test
            else:
                if cur: lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        return lines


# Pantalla de selección de personaje con tarjetas de estadísticas
class CharSelector:
    def __init__(self):
        from src.effects import MatrixRain
        self.rain = MatrixRain(WIDTH, HEIGHT)
        self.sel = 0
        self.timer = 0
        self.glitch = 0
        self.glitch_active = False
        self.glitch_timer = 300
        self.entries = {}
        self.particles = []
        self.cursor_vis = True
        self.cursor_timer = 0
        self.card_w, self.card_h = 200, 270
        self.gap_x, self.gap_y = 20, 12
        self.cols = 5
        self.start_x = (WIDTH - self.cols * self.card_w - (self.cols - 1) * self.gap_x) // 2
        self.vicente_unlocked = False

    # Obtiene la lista de personajes, incluyendo a Vicente si está desbloqueado
    def _get_items(self):
        base = [i for i in list(CHARACTERS.items()) if i[0] != "vicente"]
        if self.vicente_unlocked:
            base.append(("vicente", CHARACTERS["vicente"]))
        else:
            base.append(("??", {"name":"???","desc":"BLOQUEADO - Gana la partida","color":(100,100,100),"max_hp":0,"dmg":0,"speed":0,"fr":0,"mag":0,"reload":2000,"ability":"???","cd":0}))
        return base

    # Actualiza animaciones, partículas y efecto glitch
    def update(self, mouse_pos=None, vicente_unlocked=False):
        self.vicente_unlocked = vicente_unlocked
        self.timer += 1
        self.rain.update()
        self.cursor_timer += 1
        if self.cursor_timer > 30:
            self.cursor_vis = not self.cursor_vis
            self.cursor_timer = 0

        self.glitch_timer -= 1
        if self.glitch_timer <= 0:
            self.glitch_active = not self.glitch_active
            self.glitch = random.randint(-4, 4)
            self.glitch_timer = random.randint(200, 600) if self.glitch_active else random.randint(10, 30)

        items = self._get_items()
        for i in range(len(items)):
            if i not in self.entries:
                self.entries[i] = HEIGHT + 100
            if self.entries[i] > 0:
                self.entries[i] -= max(1, (self.entries[i] - 0) * 0.08)
                if abs(self.entries[i]) < 1:
                    self.entries[i] = 0

        if self.timer % 3 == 0 and items:
            ci = min(self.sel, len(items) - 1)
            c = items[ci][1]
            bx = self.start_x + (ci % self.cols) * (self.card_w + self.gap_x)
            by = 95 + (ci // self.cols) * (self.card_h + self.gap_y) + self.entries.get(ci, 0)
            cx = bx + self.card_w // 2
            cy = by + self.card_h // 2
            for _ in range(2):
                a = random.uniform(0, math.tau)
                r = random.uniform(5, 14)
                self.particles.append({
                    "x": cx + math.cos(a) * r, "y": cy + math.sin(a) * r,
                    "vx": math.cos(a) * random.uniform(-0.3, 0.3),
                    "vy": math.sin(a) * random.uniform(-0.3, 0.3),
                    "life": random.randint(15, 30), "max_life": 30,
                    "color": c["color"], "radius": random.uniform(1.5, 3),
                })

        for p in self.particles[:]:
            p["x"] += p["vx"]; p["y"] += p["vy"]; p["life"] -= 1
            if p["life"] <= 0:
                self.particles.remove(p)

    # Devuelve rectángulos de tarjetas para detección de clics
    def get_card_rects(self):
        rects = []
        items = self._get_items()
        for i in range(len(items)):
            bx = self.start_x + (i % self.cols) * (self.card_w + self.gap_x)
            by = 95 + (i // self.cols) * (self.card_h + self.gap_y)
            rects.append((i, pygame.Rect(bx, by, self.card_w, self.card_h)))
        return rects

    # Reinicia animación de entrada de tarjetas
    def reset_animation(self):
        self.entries = {}
        self.particles = []

    def draw(self, surf, vicente_unlocked=False):
        self.vicente_unlocked = vicente_unlocked
        surf.fill((0, 3, 0))
        self.rain.draw(surf)
        draw_scanlines(surf)
        draw_terminal_frame(surf, GREEN, 40)

        now = pygame.time.get_ticks()
        items = self._get_items()
        card_w, card_h = self.card_w, self.card_h

        glow_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (0, 255, 65, 6), (WIDTH // 2, 40), 150)
        surf.blit(glow_surf, (0, 0))

        t = _f(32).render("SELECCIONA TU COMPA", True, GREEN)
        for i in range(3):
            g = _f(32 + i * 2).render("SELECCIONA TU COMPA", True, (0, 30 - i * 8, 0))
            surf.blit(g, (WIDTH // 2 - g.get_width() // 2 + i, 27 + i))
        surf.blit(t, t.get_rect(center=(WIDTH // 2, 27)))

        sub = _f(14).render("root@virus:~$ ./seleccionar_personaje.sh", True, (0, 100, 30))
        sub.set_alpha(140)
        surf.blit(sub, sub.get_rect(center=(WIDTH // 2, 52)))

        for i, (cid, c) in enumerate(items):
            entry_y = self.entries.get(i, 0)
            bx = self.start_x + (i % self.cols) * (card_w + self.gap_x)
            by = 95 + (i // self.cols) * (card_h + self.gap_y) + entry_y
            is_sel = i == self.sel

            bg = (20, 18, 8) if is_sel else (5, 10, 5)

            if is_sel:
                draw_glow(surf, c["color"], (bx + card_w // 2, by + card_h // 2), 80, 40)

            draw_rrect(surf, bg, (bx, by, card_w, card_h))

            if is_sel:
                pulse_a = int(math.sin(now * 0.004) * 30 + 70)
                pygame.draw.rect(surf, (*SEL[:3], pulse_a), (bx - 2, by - 2, card_w + 4, card_h + 4), 2, border_radius=8)
            else:
                pygame.draw.rect(surf, (0, 35, 10), (bx, by, card_w, card_h), 1, border_radius=6)

            if cid == "??":
                # Locked character card
                cx = bx + card_w // 2
                lock_s = _f(40).render("?", True, (60, 60, 60))
                surf.blit(lock_s, (cx - lock_s.get_width() // 2, by + 25))
                pygame.draw.circle(surf, (60, 60, 60), (cx, by + 35), 20, 2)
                name_s = _f(16).render("???", True, (80, 80, 80))
                surf.blit(name_s, (cx - name_s.get_width() // 2, by + 60))
                ds = _f(10).render("BLOQUEADO", True, (80, 50, 50))
                surf.blit(ds, (bx + 10, by + 80))
                st = _f(10).render("Gana la partida", True, (60, 60, 60))
                surf.blit(st, (bx + 10, by + 95))
                if is_sel:
                    st2 = _f(12).render("F=", True, (120, 80, 80))
                    surf.blit(st2, (cx - st2.get_width() // 2, by + card_h - 22))
                continue

            col = list(c["color"])
            cx = bx + card_w // 2
            if is_sel:
                draw_glow(surf, col, (cx, by + 38), 30, 60)

            ring_r = 24 + int(math.sin(now * 0.003 + i) * 3)
            if is_sel:
                pygame.draw.circle(surf, (*col, 60), (cx, by + 38), ring_r, 2)

            pygame.draw.circle(surf, col, (cx, by + 38), 20)
            pygame.draw.circle(surf, SEL if is_sel else (0, 50, 15), (cx, by + 38), 20, 2)

            name_s = _f(18).render(c["name"], True, SEL if is_sel else (0, 120, 40))
            surf.blit(name_s, (cx - name_s.get_width() // 2, by + 65))

            ds = _f(12).render(c["desc"], True, WHITE if is_sel else (0, 100, 35))
            surf.blit(ds, (bx + 12, by + 85))

            stats = [
                ("HP", c["max_hp"], 150, (0, 200, 50)),
                ("DMG", c["dmg"], 30, (200, 50, 50)),
                ("SPD", c["speed"], 5.0, (50, 120, 200)),
                ("FR", c["fr"], 200, (200, 180, 50)),
                ("MAG", c["mag"], 40, (100, 200, 200)),
                ("RLD", 2000 - c["reload"], 2000, (200, 100, 200)),
            ]
            bar_start_y = by + 102
            for si, (lbl, val, maxv, clr) in enumerate(stats):
                bar_y = bar_start_y + si * 11
                bar_w, bar_h = 88, 7
                pygame.draw.rect(surf, (5, 8, 3), (bx + 12, bar_y, bar_w, bar_h))
                ratio = min(1.0, val / maxv)
                fill_w = max(1, int(bar_w * ratio))
                pygame.draw.rect(surf, clr, (bx + 12, bar_y, fill_w, bar_h))
                lbl_c = (0, 120, 40) if is_sel else (0, 60, 20)
                surf.blit(_f(9).render(lbl, True, lbl_c), (bx + 104, bar_y - 1))

            ab_y = bar_start_y + 6 * 11 + 6
            ab_clr = SEL if is_sel else (0, 80, 30)
            surf.blit(_f(12).render(c["ability"].upper(), True, ab_clr), (bx + 12, ab_y))
            surf.blit(_f(10).render(f"CD: {c['cd']}ms", True, ab_clr), (bx + 12, ab_y + 14))

            if is_sel:
                st = _f(13).render("ENTER = Elegir", True, SEL)
                surf.blit(st, (cx - st.get_width() // 2, by + card_h - 22))
                deco = _f(14).render("<", True, (0, 60, 20))
                deco2 = _f(14).render(">", True, (0, 60, 20))
                surf.blit(deco, (bx - 20, by + card_h // 2))
                surf.blit(deco2, (bx + card_w + 8, by + card_h // 2))

        for p in self.particles:
            t = p["life"] / p["max_life"]
            a = int(t * 200)
            r = max(0.5, p["radius"] * t)
            s = pygame.Surface((int(r * 2),) * 2, pygame.SRCALPHA)
            pygame.draw.circle(s, (*p["color"][:3], a), (r, r), r)
            surf.blit(s, (p["x"] - r, p["y"] - r))

        if self.glitch_active and random.random() < 0.3:
            for _ in range(2):
                gy = random.randint(0, HEIGHT)
                gh = random.randint(1, 3)
                gl = pygame.Surface((WIDTH, gh))
                gl.set_alpha(random.randint(20, 60))
                gl.fill((0, 255, 65))
                surf.blit(gl, (random.randint(-5, 5), gy))

        prompt = "root@virus:~$ select_character "
        prompt_surf = _f(15).render(prompt, True, (0, 130, 40))
        surf.blit(prompt_surf, (25, HEIGHT - 50))
        if self.cursor_vis:
            cursor = _f(15).render("_", True, GREEN)
            surf.blit(cursor, (25 + prompt_surf.get_width(), HEIGHT - 50))

        hint = _f(14).render("<-  -> Navegar  ENTER=Seleccionar  ESC=Menu  RATON=Click", True, (0, 70, 22))
        surf.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 22)))


# Pantalla de controles con lista de teclas
class ControlsScreen:
    def __init__(self):
        from src.effects import MatrixRain
        self.rain = MatrixRain(WIDTH, HEIGHT)
        self.timer = 0
        self.glitch_timer = 400
        self.glitch_active = False
        self.glitch = 0

    def update(self):
        self.timer += 1
        self.rain.update()
        self.glitch_timer -= 1
        if self.glitch_timer <= 0:
            self.glitch_active = not self.glitch_active
            self.glitch = random.randint(-3, 3)
            self.glitch_timer = random.randint(200, 500) if self.glitch_active else random.randint(10, 40)

    # Dibuja la pantalla de controles con grupos de teclas
    def draw(self, surf):
        surf.fill((0, 5, 0))
        self.rain.draw(surf)
        draw_scanlines(surf, 15)
        draw_terminal_frame(surf, GREEN, 35)

        glow_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (0, 255, 65, 8), (WIDTH // 2, 50), 200)
        surf.blit(glow_surf, (0, 0))

        t = _f(40).render("CONTROLES", True, GREEN)
        for i in range(3):
            g = _f(40 + i * 3).render("CONTROLES", True, (0, 28 - i * 8, 0))
            surf.blit(g, (WIDTH // 2 - g.get_width() // 2 + i, 42 + i))
        surf.blit(t, t.get_rect(center=(WIDTH // 2, 42)))

        sub = _f(15).render("Manual de operacion del sistema", True, (0, 120, 40))
        sub.set_alpha(150)
        surf.blit(sub, sub.get_rect(center=(WIDTH // 2, 72)))

        groups = [
            ("MOVIMIENTO", [
                ("W A S D", "Movimiento del cursor"),
                ("SHIFT", "Acelerar desplazamiento"),
            ]),
            ("COMBATE", [
                ("CLICK IZQ", "Ejecutar codigo enemigo"),
                ("R", "Recargar buffer"),
                ("Q", "Habilidad (cooldown)"),
                ("Z", "Ultimate (carga 20 bajas)"),
                ("X", "Expansion de Dominio"),
                ("F", "Abrir suministros/Gacha"),
            ]),
            ("SISTEMA", [
                ("ESC", "Pausar / Retroceder"),
                ("F11", "Pantalla completa"),
                ("1-4", "Cambiar arma"),
            ]),
        ]

        y = 105
        for gname, items in groups:
            gs = _f(14).render(f"[ {gname} ]", True, (0, 150, 40))
            surf.blit(gs, (WIDTH // 2 - 250, y))
            y += 22
            for k, v in items:
                c = GREEN if k else (0, 150, 50)
                ks = _f(20).render(k, True, c)
                vs = _f(17).render(v, True, WHITE if k else (0, 120, 40))
                if self.glitch_active and random.random() < 0.2:
                    off = random.randint(-2, 2)
                    surf.blit(ks, (WIDTH // 2 - 240 + off, y))
                    surf.blit(vs, (WIDTH // 2 + 20 + off, y))
                else:
                    surf.blit(ks, (WIDTH // 2 - 240, y))
                    surf.blit(vs, (WIDTH // 2 + 20, y))
                if k:
                    dot = _f(16).render("$", True, (0, 100, 30))
                    surf.blit(dot, (WIDTH // 2 - 265, y))
                y += 32
            y += 8

        # Objetivo
        obj = _f(15).render("OBJETIVO: Limpia todos los servidores!", True, (0, 150, 50))
        surf.blit(obj, (WIDTH // 2 - obj.get_width() // 2, y + 10))

        if self.glitch_active and random.random() < 0.3:
            for _ in range(2):
                gy = random.randint(0, HEIGHT); gh = random.randint(1, 3)
                gl = pygame.Surface((WIDTH, gh)); gl.set_alpha(random.randint(20, 60))
                gl.fill((0, 255, 65)); surf.blit(gl, (random.randint(-5, 5), gy))

        prompt = "root@virus:~$ ./ayuda --manual"
        ps = _f(15).render(prompt, True, (0, 130, 40))
        surf.blit(ps, (25, HEIGHT - 50))
        cursor = _f(15).render("_", True, GREEN) if self.timer % 60 < 30 else _f(15).render("", True, GREEN)
        surf.blit(cursor, (25 + ps.get_width(), HEIGHT - 50))

        h = _f(16).render("ESC para volver al menu", True, (0, 80, 25))
        surf.blit(h, h.get_rect(center=(WIDTH // 2, HEIGHT - 24)))


# Pantalla de créditos con desplazamiento vertical
class CreditsScreen:
    CREDITS = ["GEMINI", "OPEN CODE", "IRVING", "IAN", "SEBASTIAN", "DIEGO", "EDER"]

    def __init__(self):
        from src.effects import MatrixRain
        self.rain = MatrixRain(WIDTH, HEIGHT)
        self.timer = 0
        self.done = False
        self.scroll_y = HEIGHT + 50
        self.glitch_timer = 400
        self.glitch_active = False
        self.glitch = 0
        self.finished_timer = 0

    # Actualiza desplazamiento de créditos y efecto glitch
    def update(self):
        self.timer += 1
        self.rain.update()
        self.glitch_timer -= 1
        if self.glitch_timer <= 0:
            self.glitch_active = not self.glitch_active
            self.glitch = random.randint(-3, 3)
            self.glitch_timer = random.randint(200, 500) if self.glitch_active else random.randint(10, 40)

        if self.done:
            self.finished_timer += 1
            return

        self.scroll_y -= 1.2

        total_h = len(self.CREDITS) * 60 + 100
        if self.scroll_y < -total_h:
            self.done = True

    # Dibuja los créditos desplazándose hacia arriba
    def draw(self, surf):
        surf.fill((0, 5, 0))
        self.rain.draw(surf)
        draw_scanlines(surf, 15)
        draw_terminal_frame(surf, GREEN, 35)

        glow_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (0, 255, 65, 8), (WIDTH // 2, 50), 200)
        surf.blit(glow_surf, (0, 0))

        t = _f(40).render("CREDITOS", True, GREEN)
        for i in range(3):
            g = _f(40 + i * 3).render("CREDITOS", True, (0, 28 - i * 8, 0))
            surf.blit(g, (WIDTH // 2 - g.get_width() // 2 + i, 42 + i))
        surf.blit(t, t.get_rect(center=(WIDTH // 2, 42)))

        for i, name in enumerate(self.CREDITS):
            y = int(self.scroll_y + i * 60)
            if y < -50 or y > HEIGHT + 50:
                continue

            pulse = math.sin(self.timer * 0.03 + i * 0.8) * 0.06 + 1
            fs = int(32 * pulse)

            for j in range(3):
                off = (j + 1) * 2
                g = _f(fs + off).render(name, True, (0, 25 - j * 6, 0))
                gx = WIDTH // 2 - g.get_width() // 2 + j + 1
                surf.blit(g, (gx, y + j + 1))

            c = GREEN
            if self.glitch_active and random.random() < 0.3:
                c = (100, 255, 100)
            txt = _f(fs).render(name, True, c)
            tx = WIDTH // 2 - txt.get_width() // 2
            if self.glitch_active and random.random() < 0.3:
                tx += self.glitch
            surf.blit(txt, (tx, y))

            if self.glitch_active and random.random() < 0.2:
                off2 = random.randint(-2, 2)
                dot = _f(fs).render(name, True, (0, 200, 50))
                dot.set_alpha(80)
                surf.blit(dot, (tx + off2 + 4, y))

        if self.glitch_active and random.random() < 0.3:
            for _ in range(2):
                gy = random.randint(0, HEIGHT)
                gh = random.randint(1, 3)
                gl = pygame.Surface((WIDTH, gh))
                gl.set_alpha(random.randint(20, 60))
                gl.fill((0, 255, 65))
                surf.blit(gl, (random.randint(-5, 5), gy))

        if self.done:
            fade = min(255, self.finished_timer * 5)
            if fade < 255:
                d = _f(18).render("Presiona ENTER o ESC para volver", True, (0, 150, 50))
                d.set_alpha(fade)
                surf.blit(d, d.get_rect(center=(WIDTH // 2, HEIGHT - 80)))
        else:
            h = _f(15).render("ESC para volver al menu", True, (0, 80, 25))
            surf.blit(h, h.get_rect(center=(WIDTH // 2, HEIGHT - 24)))

    # Reinicia el estado de los créditos
        self.scroll_y = HEIGHT + 50
        self.finished_timer = 0
        self.timer = 0


# Pantalla de pausa con estadísticas y opciones
class PauseScreen:
    def __init__(self):
        from src.effects import MatrixRain
        self.rain = MatrixRain(WIDTH, HEIGHT)
        self.sel = 0
        self.timer = 0

    # Actualiza animación de lluvia en pausa
    def update(self):
        self.timer += 1
        self.rain.update()

    # Dibuja la pantalla de pausa con estadísticas y opciones
    def draw(self, surf, game):
        o = pygame.Surface((WIDTH, HEIGHT))
        o.set_alpha(160); o.fill((0, 0, 0))
        surf.blit(o, (0, 0))
        self.rain.draw(surf)
        draw_scanlines(surf, 30)
        draw_terminal_frame(surf, GREEN, 30)

        for i in range(4):
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            r2 = 100 + i * 25; a = 8 - i * 2
            pygame.draw.circle(s, (0, 255, 65, a), (WIDTH // 2, HEIGHT // 2 - 50), r2)
            surf.blit(s, (0, 0))

        t = _f(44).render("PAUSA", True, (0, 200, 50))
        for i in range(3):
            g = _f(44 + i * 4).render("PAUSA", True, (0, 25 - i * 7, 0))
            surf.blit(g, g.get_rect(center=(WIDTH // 2 + i, HEIGHT // 2 - 52 + i)))
        surf.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 50)))

        # Stats panel
        if game and hasattr(game, "player") and game.player:
            p = game.player
            stats_x = WIDTH // 2 - 200
            stats_y = HEIGHT // 2 - 10
            stats_data = [
                ("SERVER", str(game.wave), GREEN),
                ("BAJAS", str(p.kills), GREEN),
                ("NIVEL", str(p.level), GREEN),
                ("BYTES", str(p.bytes), GOLD),
                ("RAM", f"{p.hp}/{p.max_hp}", WHITE),
                ("DANO", str(p.bonus_damage + p.char_data["dmg"]), GREEN),
            ]
            for si, (label, val, clr) in enumerate(stats_data):
                col = si % 3; row = si // 3
                sx = stats_x + col * 135
                sy = stats_y + row * 28
                surf.blit(_f(13).render(label, True, (0, 100, 30)), (sx, sy))
                surf.blit(_f(16).render(val, True, clr), (sx + 60, sy))

        opts = ["CONTINUAR", "SALIR AL MENU"]
        for i, opt in enumerate(opts):
            is_sel = i == self.sel
            by = HEIGHT // 2 + 70 + i * 45
            bx = WIDTH // 2 - 100
            bw, bh = 200, 36
            if is_sel:
                draw_glow(surf, SEL, (bx + bw // 2, by + bh // 2), 50, 80)
                draw_rrect(surf, (40, 30, 5), (bx, by, bw, bh))
                draw_rrect(surf, (60, 50, 10), (bx + 2, by + 2, bw - 4, bh - 4))
                pygame.draw.rect(surf, SEL, (bx - 1, by - 1, bw + 2, bh + 2), 1, border_radius=5)
                prefix = "> "
            else:
                draw_rrect(surf, (0, 15, 4), (bx, by, bw, bh))
                prefix = "  "
            c = SEL if is_sel else (0, 120, 40)
            st = _f(20).render(prefix + opt, True, c)
            surf.blit(st, (bx + bw // 2 - st.get_width() // 2, by + bh // 2 - 10))

        hint = _f(14).render("W/S Navegar  ENTER=Seleccionar  ESC=Volver  RATON=Click", True, (0, 60, 18))
        surf.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 175)))

    # Devuelve rectángulos de las opciones para detectar clics
    def get_sel_rects(self):
        rects = []
        for i in range(2):
            by = HEIGHT // 2 + 70 + i * 45
            rects.append((i, pygame.Rect(WIDTH // 2 - 100, by, 200, 36)))
        return rects


# Dibuja la máquina tragamonedas de suministros (Gacha)
_GACHA_NAMES = [name for name, _, _ in GACHA_LOOT]
def draw_gacha(surf, game):
    o = pygame.Surface((WIDTH, HEIGHT))
    o.set_alpha(200); o.fill((0, 0, 0))
    surf.blit(o, (0, 0))
    draw_terminal_frame(surf, GOLD, 50)
    draw_scanlines(surf, 20)

    # Title
    t = _f(30).render("CAIDA DE SUMINISTROS - GACHA", True, GOLD)
    surf.blit(t, t.get_rect(center=(WIDTH // 2, 50)))

    # Roulette slot machine
    slot_w, slot_h = 300, 80
    slot_x = WIDTH // 2 - slot_w // 2
    slot_y = HEIGHT // 2 - slot_h // 2

    # Slot background
    draw_rrect(surf, (20, 15, 5), (slot_x, slot_y, slot_w, slot_h))
    pygame.draw.rect(surf, GOLD, (slot_x, slot_y, slot_w, slot_h), 2, border_radius=6)

    # Spinning names
    spinning = game.gacha_spinning
    result = game.gacha_result
    now = pygame.time.get_ticks()
    if spinning:
        idx = (now // 80) % len(_GACHA_NAMES)
        display = _GACHA_NAMES[idx]
        color = GOLD
    elif result:
        name, typ = result
        display = name
        color_map = {"bytes": GOLD, "buff_turbo": (255, 100, 50), "buff_shield": (50, 150, 255),
                     "buff_dmg": (255, 50, 50), "buff_speed": (50, 200, 100), "evo_item": (255, 215, 0), "chaos": PURPLE}
        color = color_map.get(typ, WHITE)
    else:
        display = "?"
        color = GRAY
    ds = _f(32).render(display, True, color)
    surf.blit(ds, ds.get_rect(center=(WIDTH // 2, slot_y + slot_h // 2)))

    # Glow while spinning
    if spinning:
        glow_r = 100 + int(math.sin(now * 0.01) * 20)
        gs = pygame.Surface((glow_r * 2,) * 2, pygame.SRCALPHA)
        a = int(math.sin(now * 0.01) * 30 + 50)
        pygame.draw.circle(gs, (*GOLD[:3], a), (glow_r, glow_r), glow_r)
        surf.blit(gs, (WIDTH // 2 - glow_r, slot_y + slot_h // 2 - glow_r))

    if not spinning and result:
        # Show hint to close
        h = _f(16).render("PRESIONA F PARA CERRAR", True, GREEN)
        surf.blit(h, h.get_rect(center=(WIDTH // 2, slot_y + slot_h + 30)))

    # Arrows on sides
    for side, dx in [("◀", -20), ("▶", slot_w + 4)]:
        s = _f(24).render(side, True, GOLD)
        surf.blit(s, (slot_x + dx, slot_y + slot_h // 2 - 12))


# Dibuja el inventario de ítems de evolución (abajo a la derecha)
def draw_inventory(surf, player):
    x = WIDTH - 220
    y = HEIGHT - 130
    draw_rrect(surf, (10, 10, 5), (x, y, 210, 120))
    pygame.draw.rect(surf, GREEN, (x, y, 210, 120), 1, border_radius=4)
    surf.blit(_f(13).render("INVENTARIO", True, GREEN), (x + 4, y + 2))
    if player.evolution_items:
        iy = y + 18
        for item, count in player.evolution_items.items():
            emoji = EVOLUTION_ITEM_EMOJIS.get(item, "📦")
            txt = f"{emoji} {item}" + (" ✓" if count >= 1 else "")
            surf.blit(_f(11).render(txt, True, GOLD if count >= 1 else GRAY), (x + 4, iy))
            iy += 15
    if player.chaos_items:
        iy = y + 18 + len(player.evolution_items) * 15 + 4
        for item in player.chaos_items[-3:]:
            surf.blit(_f(11).render(f"Caos: {item}", True, PURPLE), (x + 4, iy))
            iy += 15
    if player.evolved:
        surf.blit(_f(14).render("EVOLUCIONADO!", True, GOLD), (x + 4, y + 100))


# Pantalla de resultado: victoria o derrota
class ResultScreen:
    def __init__(self, kind="over"):
        self.kind = kind
        from src.effects import MatrixRain
        self.rain = MatrixRain(WIDTH, HEIGHT)
        self.timer = 0
        self.glitch_timer = 300
        self.glitch_active = False
        self.glitch = 0
        self.entries = {}  # stat index -> current alpha
        self.particles = []
        self.player = None
        self.wave = 0

    # Reinicia el estado con datos de la partida
    def reset(self, kind, player, wave):
        self.kind = kind
        self.rain = MatrixRain(WIDTH, HEIGHT)
        self.timer = 0
        self.entries = {}
        self.particles = []
        self.player = player
        self.wave = wave

    # Actualiza animaciones, partículas y entrada de estadísticas
    def update(self):
        self.timer += 1
        self.rain.update()

        self.glitch_timer -= 1
        if self.glitch_timer <= 0:
            self.glitch_active = not self.glitch_active
            self.glitch = random.randint(-5, 5)
            self.glitch_timer = random.randint(150, 500) if self.glitch_active else random.randint(10, 40)

        n_stats = 4
        for i in range(n_stats):
            if i not in self.entries:
                self.entries[i] = 0
            if self.entries[i] < 255:
                self.entries[i] = min(255, self.entries[i] + 4)

        # Particles
        if self.kind == "win":
            for _ in range(3):
                self.particles.append({
                    "x": random.uniform(0, WIDTH), "y": -10,
                    "vx": random.uniform(-1, 1), "vy": random.uniform(0.5, 2.5),
                    "life": random.randint(40, 80), "max_life": 80,
                    "color": random.choice([(0, 255, 65), (255, 210, 55), (0, 200, 100)]),
                    "radius": random.uniform(2, 5),
                })
        elif random.random() < 0.4:
            self.particles.append({
                "x": random.uniform(0, WIDTH), "y": random.uniform(0, HEIGHT),
                "vx": random.uniform(-0.3, 0.3), "vy": random.uniform(-0.5, 0.2),
                "life": random.randint(20, 50), "max_life": 50,
                "color": (255, 50, 50),
                "radius": random.uniform(1.5, 3),
            })

        for p in self.particles[:]:
            p["x"] += p["vx"]; p["y"] += p["vy"]; p["life"] -= 1
            if p["life"] <= 0:
                self.particles.remove(p)

    # Dibuja la pantalla de resultado con estadísticas y arte ASCII
            player = self.player
        if wave is None:
            wave = self.wave

        is_win = self.kind == "win"
        main_color = GOLD if is_win else RED
        border_color = GOLD if is_win else RED

        o = pygame.Surface((WIDTH, HEIGHT))
        o.set_alpha(190); o.fill((0, 0, 0))
        surf.blit(o, (0, 0))
        self.rain.draw(surf)
        draw_scanlines(surf, 25)
        draw_terminal_frame(surf, border_color, 50)

        for i in range(6):
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            r2 = 80 + i * 20; a = 10 - i * 1
            pygame.draw.circle(s, (*border_color[:3], a), (WIDTH // 2, HEIGHT // 2 - 70), r2)
            surf.blit(s, (0, 0))

        # ASCII art
        if is_win:
            art = [
                "    ╔═══╗╦╔═╗╔═╗╔╦╗╔═╗╔╗╔╔╦╗",
                "    ║╔═╗║║║╣ ║ ║ ║║║║╣ ║║║ ║ ",
                "    ║╚═╝║╚╝╚═╝╚═╝═╩╝╚═╝╝╚╝ ╩ ",
                "    ╚═══╝╚╝              ╚═╝  ",
            ]
            title_str = "VICTORIA"
            prompt_txt = "root@virus:~$ ./system_secured.sh"
        else:
            art = [
                "     ╔═╗╔═╗╔╗╔╔═╗     ╔═╗╔═╗╔╦╗",
                "     ║ ╦║╣ ║║║║ ║     ║ ║║ ║ ║ ",
                "     ╚═╝╚═╝╝╚╝╚═╝     ╚═╝╚═╝ ╩ ",
            ]
            title_str = "GAME OVER"
            prompt_txt = "root@virus:~$ ./analizar_logs.sh"

        # Draw ASCII art
        art_fs = 14
        art_y = 30
        for li, line in enumerate(art):
            if self.glitch_active and random.random() < 0.25:
                line = "".join(random.choice("01█▓▒░") if random.random() < 0.3 else ch for ch in line)
            lx = WIDTH // 2 - _f(art_fs).render(line, True, main_color).get_width() // 2
            if self.glitch_active:
                lx += self.glitch
            lt = _f(art_fs).render(line, True, main_color)
            surf.blit(lt, (lx, art_y + li * 14))

        title_y = art_y + len(art) * 14 + 5
        go = _f(50 if is_win else 56).render(title_str, True, main_color)
        for i in range(4):
            g = _f((50 if is_win else 56) + i * 3).render(title_str, True, (max(0, 30 - i * 8), max(0, 25 - i * 7), max(0, 5 - i * 2)) if is_win else (max(0, 40 - i * 10), 0, 0))
            surf.blit(g, g.get_rect(center=(WIDTH // 2 + i, title_y - 22 + i)))
        surf.blit(go, go.get_rect(center=(WIDTH // 2, title_y - 20)))

        prompt_line = _f(14).render(prompt_txt, True, (0, 120, 40))
        surf.blit(prompt_line, (WIDTH // 2 - 180, title_y + 8))

        stats = [
            (f"BYTES: {player.bytes if player else 0}", (0, 200, 50)),
            (f"BAJAS: {player.kills if player else 0}", (0, 200, 50)),
            (f"NIVEL: {player.level if player else 0}", (0, 200, 50)),
            (f"SERVIDOR: {wave}", (0, 200, 50)),
        ]

        y = title_y + 36
        for si, (text, clr) in enumerate(stats):
            alpha = self.entries.get(si, 0)
            st = _f(20).render(text, True, clr)
            st.set_alpha(alpha)
            surf.blit(st, (WIDTH // 2 - 150, y))
            y += 30

        sep = _f(16).render("-" * 40 if not is_win else "=" * 40, True, (0, 80, 25) if not is_win else GOLD)
        surf.blit(sep, (WIDTH // 2 - sep.get_width() // 2, y + 5))

        h = _f(18).render("R = Reintentar    ESC = Menu", True, WHITE)
        surf.blit(h, (WIDTH // 2 - h.get_width() // 2, y + 35))

        # Particles
        for p in self.particles:
            t = p["life"] / p["max_life"]
            a = int(t * 200)
            r = max(0.5, p["radius"] * t)
            s = pygame.Surface((int(r * 2),) * 2, pygame.SRCALPHA)
            pygame.draw.circle(s, (*p["color"][:3], a), (r, r), r)
            surf.blit(s, (p["x"] - r, p["y"] - r))

        # Glitch
        if self.glitch_active and random.random() < 0.3:
            for _ in range(2):
                gy = random.randint(0, HEIGHT); gh = random.randint(1, 4)
                gl = pygame.Surface((WIDTH, gh)); gl.set_alpha(random.randint(20, 60))
                gl.fill(border_color[:3]); surf.blit(gl, (random.randint(-5, 5), gy))

        prompt = "root@virus:~$ "
        ps = _f(14).render(prompt, True, (0, 130, 40))
        surf.blit(ps, (25, HEIGHT - 50))
        if self.timer % 60 < 30:
            cursor = _f(14).render("_", True, GREEN)
            surf.blit(cursor, (25 + ps.get_width(), HEIGHT - 50))
