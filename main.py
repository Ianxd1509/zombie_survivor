import sys
import traceback
from datetime import datetime

import pygame

# Ruta del archivo donde se guardan los registros de fallos
CRASH_LOG = "docs/crash_log.txt"


# Guarda trazas de errores graves en un archivo de texto
def _log_crash(exc_type, exc_value, exc_tb):
    import os
    d = os.path.dirname(CRASH_LOG)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(CRASH_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"CRASH: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        f.write(f"{'='*60}\n")


# Registra cualquier excepción no capturada automáticamente
sys.excepthook = _log_crash

from config import ADMIN_PASSWORD, CHARACTERS, FPS, HEIGHT, MAPS, RED, WIDTH
from src.effects import Notif
from src.game import Game
from src.sound import SFX
from src.ui import CharSelector, ControlsScreen, CreditsScreen, MapSelector, PauseScreen, ResultScreen, TutorialScreen, draw_hud, draw_shop


# Restaura todos los atributos de una partida guardada
def _do_load_game(game, data):
    """Shared load logic for keyboard and mouse paths."""
    cid = data.get("char_id", "irvin")
    game.selected_char = cid
    mi = data.get("map_index", 0)
    game.map_sel = mi
    game.map_index = mi
    game.reset(cid)
    for k2, v2 in data.items():
        if k2 == "shop_costs":
            game.shop_costs.update(v2)
        elif k2 == "ability_cd_remaining":
            if hasattr(game.player, "ability_max_cd"):
                if v2 > 0:
                    game.player.ability_cd = pygame.time.get_ticks() - (game.player.ability_max_cd - v2)
                else:
                    game.player.ability_cd = pygame.time.get_ticks() - game.player.ability_max_cd
        elif k2 == "pos_x":
            game.player.pos.x = v2
        elif k2 == "pos_y":
            game.player.pos.y = v2
        elif k2 in ("wave", "wave_state", "wave_has_boss", "wave_modifier", "wave_total", "vicente_unlocked"):
            setattr(game, k2, v2)
        elif k2 in ("turbo_timer", "shield_timer", "explosive_timer", "weapon_idx", "weapon_mode",
                     "shield", "invulnerable", "invuln_timer", "byte_multiplier", "byte_mult_timer",
                     "ability_speed", "ability_damage_mult", "ability_damage_timer", "ability_speed_timer"):
            setattr(game.player, k2, v2)
        elif k2 == "bomb_owned" and hasattr(game.player, "bomb_owned"):
            game.player.bomb_owned = set(v2)
        elif k2 == "bomb_queue" and hasattr(game.player, "bomb_queue"):
            game.player.bomb_queue = v2
        elif k2 == "bomb_count" and hasattr(game.player, "bomb_count"):
            game.player.bomb_count = v2
        elif k2 == "bomb_active_idx" and hasattr(game.player, "bomb_active_idx"):
            game.player.bomb_active_idx = v2
        elif k2 == "_last_combo_time" and hasattr(game.player, "_last_combo_time"):
            game.player._last_combo_time = v2
        elif k2 == "ability_charge" and hasattr(game.player, "ability_charge"):
            game.player.ability_charge = v2
        elif k2 == "ability_max_charge" and hasattr(game.player, "ability_max_charge"):
            game.player.ability_max_charge = v2
        elif k2 == "domain_charge" and hasattr(game.player, "domain_charge"):
            game.player.domain_charge = v2
        elif k2 == "domain_cd_timer" and hasattr(game.player, "domain_cd_timer"):
            game.player.domain_cd_timer = v2
        elif k2 == "prep_timer":
            game.prep_timer = v2
        elif k2 == "wave_cd":
            game.wave_cd = v2
        elif k2 == "wave_spawned":
            game.wave_spawned = v2
        elif k2 in _SAVE_ALLOWLIST and hasattr(game.player, k2):
            setattr(game.player, k2, v2)
        # bonus_damage already restored via setattr in the loop above
        pass
    if data.get("wave_state") in ("spawning", "clear"):
        game.wave_state = "prep"
    game.state = "play"

# Lista blanca de atributos del jugador que se guardan/cargan
_SAVE_ALLOWLIST = {
    "hp", "max_hp", "bytes", "score", "kills", "level", "xp", "stamina",
    "shop_levels", "extra_shots", "bonus_firerate", "bonus_speed", "bonus_mag",
    "bonus_reload", "bonus_hp", "vampire", "lifesteal", "knockback", "mag", "reserve",
    "piercing", "bounce", "bonus_damage",
    "fr_mult", "reload_mult", "dmg_mult",
    "evolution_items", "evolved", "chaos_items", "auras", "unique_items",
    "combo_counter",
    "turbo_timer", "shield_timer", "explosive_timer",
    "weapon_idx", "weapon_mode", "shield", "invulnerable", "invuln_timer",
    "byte_multiplier", "byte_mult_timer",
    "ability_speed", "ability_damage_mult", "ability_damage_timer", "ability_speed_timer",
}

def main():
    # Inicializa Pygame en pantalla completa y oculta el cursor
    pygame.init()
    pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.SCALED)
    pygame.display.set_caption("VIRUS")
    pygame.mouse.set_visible(False)
    screen = pygame.display.get_surface()
    clock = pygame.time.Clock()

    # Crea instancia del juego, menús y pantallas de UI
    game = Game()
    from src.sound import SFX, stop_bg_music, update_bg_music, play_menu_music, stop_menu_music, play_shop_music, stop_shop_music
    from src.ui import MainMenu
    menu = MainMenu()
    mapsel = MapSelector()
    charsel = CharSelector()
    controls = ControlsScreen()
    tutorial = TutorialScreen()
    credits = CreditsScreen()
    pause_screen = PauseScreen()
    result_screen = ResultScreen("over")
    game.map_sel = 0
    shop_sel = 0
    _prev_state = None  # Para detectar transiciones de estado y gestionar música
    running = True

    # Bucle principal del juego
    while running:
        # Control de FPS (modo lento si admin activó slowmo) y estado del ratón
        clock.tick(FPS if not getattr(game, 'admin_slowmo', False) else max(15, FPS // 2))
        mouse_pos = pygame.mouse.get_pos()
        mouse_btn = pygame.mouse.get_pressed()[0]
        pygame.mouse.set_visible(game.state in ("menu", "mapsel", "credits"))

        # --- Bucle de eventos ---
        for event in pygame.event.get():
            # Cierra el juego y guarda si hay partida activa
            if event.type == pygame.QUIT:
                if game.state in ("play", "shop_prep", "pause"):
                    game.save_game()
                running = False

            if event.type == pygame.KEYDOWN:
                k = event.key
                # ESC: retrocede entre estados (juego->pausa->juego, menús->menú principal, etc.)
                if k == pygame.K_ESCAPE:
                    if game.state in ("play", "shop_prep") and game.shop_open:
                        game.shop_open = False
                        stop_shop_music()
                    elif game.state in ("play", "shop_prep"):
                        game.state = "pause"; pause_screen.sel = 0
                    elif game.state == "pause": game.state = "play"
                    elif game.state in {"controls", "tutorial", "credits"} or game.state in {"mapsel", "charsel"}: game.state = "menu"
                    elif game.state in ("over", "win"):
                        game.state = "menu"
                    elif game.state == "menu":
                        running = False

                # SPACE: inicia la siguiente oleada durante la preparación
                if k == pygame.K_SPACE and game.wave_state == "prep" and not game.shop_open:
                    game.vicente = None
                    game.prep_timer = 0
                    game.wave_state = "spawning"
                    game.wave_announce = 120
                    if game.state == "shop_prep":
                        game.state = "play"

                # Navegación del menú de pausa (continuar / salir)
                if game.state == "pause":
                    if k in (pygame.K_UP, pygame.K_w):
                        pause_screen.sel = (pause_screen.sel - 1) % 2
                        if SFX: SFX["hover"].play()
                    elif k in (pygame.K_DOWN, pygame.K_s):
                        pause_screen.sel = (pause_screen.sel + 1) % 2
                        if SFX: SFX["hover"].play()
                    elif k == pygame.K_RETURN:
                        if SFX: SFX["click"].play()
                        if pause_screen.sel == 0: game.state = "play"
                        else:
                            game.save_game()
                            game.state = "menu"

                # Navegación y compra en la tienda (Vicente u Oscar)
                if game.shop_open:
                    shop_items = game.shop_items
                    cols = 5
                    if k in (pygame.K_LEFT, pygame.K_a):
                        shop_sel = max(0, shop_sel-1)
                        if SFX: SFX["hover"].play()
                    elif k in (pygame.K_RIGHT, pygame.K_d):
                        shop_sel = min(len(shop_items)-1, shop_sel+1)
                        if SFX: SFX["hover"].play()
                    elif k in (pygame.K_UP, pygame.K_w):
                        shop_sel = max(0, shop_sel-cols)
                        if SFX: SFX["hover"].play()
                    elif k in (pygame.K_DOWN, pygame.K_s):
                        shop_sel = min(len(shop_items)-1, shop_sel+cols)
                        if SFX: SFX["hover"].play()
                    elif k == pygame.K_TAB:
                        if len(shop_items) > 0 and "id" not in shop_items[0]:
                            game.shop_tab = (game.shop_tab + 1) % 7
                            shop_sel = 0
                            if SFX: SFX["hover"].play()
                    elif k == pygame.K_RETURN:
                        game.buy_shop_item(shop_sel)
                    elif k == pygame.K_f:
                        game.shop_open = False
                        stop_shop_music()
                        if SFX: SFX["click"].play()
                elif game.state in ("shop_prep", "play"):
                    # F abre tienda de Vicente, T abre tienda de Oscar
                    if k == pygame.K_f and game.vicente_near:
                        game.open_shop("vicente")
                        shop_sel = 0
                        play_shop_music("vicente")
                        if SFX: SFX["shop_open"].play()
                    if k == pygame.K_t and game.oscar_near:
                        game.open_shop("oscar")
                        shop_sel = 0
                        play_shop_music("oscar")
                        if SFX: SFX["shop_open"].play()

                # Selección de mapa
                elif game.state == "mapsel":
                    maps_total = len(MAPS)
                    if k in (pygame.K_LEFT, pygame.K_a):
                        mapsel.sel = (mapsel.sel - 1) % maps_total
                        if SFX: SFX["hover"].play()
                    elif k in (pygame.K_RIGHT, pygame.K_d):
                        mapsel.sel = (mapsel.sel + 1) % maps_total
                        if SFX: SFX["hover"].play()
                    elif k == pygame.K_RETURN:
                        if SFX: SFX["click"].play()
                        charsel.reset_animation()
                        game.map_sel = mapsel.sel
                        game.state = "charsel"

                # Selección de personaje
                elif game.state == "charsel":
                    chars_list = [k for k in CHARACTERS if k != "vicente"]
                    if game.vicente_unlocked:
                        chars_list.append("vicente")
                    else:
                        chars_list.append("??")
                    total = len(chars_list)
                    if k in (pygame.K_LEFT, pygame.K_a):
                        charsel.sel = (charsel.sel - 1) % total
                        if SFX: SFX["hover"].play()
                    elif k in (pygame.K_RIGHT, pygame.K_d):
                        charsel.sel = (charsel.sel + 1) % total
                        if SFX: SFX["hover"].play()
                    elif k in (pygame.K_UP, pygame.K_w):
                        charsel.sel = (charsel.sel - charsel.cols) % total
                        if SFX: SFX["hover"].play()
                    elif k in (pygame.K_DOWN, pygame.K_s):
                        charsel.sel = (charsel.sel + charsel.cols) % total
                        if SFX: SFX["hover"].play()
                    elif k == pygame.K_RETURN:
                        cid = chars_list[charsel.sel]
                        if cid == "??":
                            game.notifs.append(Notif("VICENTE BLOQUEADO - Gana la partida para desbloquear!", (100, 100, 100), 120))
                            if SFX: SFX["empty"].play()
                        else:
                            if SFX: SFX["click"].play()
                            game.selected_char = cid
                            game.reset(cid, map_index=game.map_sel)
                            game.state = "play"

                # Menú principal (nueva partida, cargar, controles, créditos, salir)
                elif game.state == "menu":
                    if k in (pygame.K_UP, pygame.K_w):
                        menu.sel = (menu.sel - 1) % len(menu.opts)
                        if SFX: SFX["hover"].play()
                    elif k in (pygame.K_DOWN, pygame.K_s):
                        menu.sel = (menu.sel + 1) % len(menu.opts)
                        if SFX: SFX["hover"].play()
                    elif k == pygame.K_RETURN:
                        if SFX: SFX["click"].play()
                        if menu.sel == 0:
                            mapsel.reset_animation()
                            game.state = "mapsel"
                        elif menu.sel == 1:
                            data = game.load_game()
                            if data:
                                _do_load_game(game, data)
                            else:
                                game.notifs.append(Notif("No hay partida guardada", RED, 60))
                        elif menu.sel == 2: game.state = "controls"
                        elif menu.sel == 3: game.state = "tutorial"; tutorial.page = 0
                        elif menu.sel == 4: game.state = "credits"; credits.reset()
                        else:
                            game.save_game()
                            running = False

                # Navegación del tutorial (páginas)
                elif game.state == "tutorial":
                    if k in (pygame.K_RIGHT, pygame.K_d):
                        tutorial.page = min(tutorial.page + 1, len(tutorial.pages) - 1)
                        if SFX: SFX["hover"].play()
                    elif k in (pygame.K_LEFT, pygame.K_a):
                        tutorial.page = max(tutorial.page - 1, 0)
                        if SFX: SFX["hover"].play()

                # Abrir/cerrar airdrop (gacha) con F
                if k == pygame.K_f and game.state == "play" and game.gacha_open:
                    game.gacha_open = False
                elif k == pygame.K_f and game.state == "play" and not game.gacha_open and game.open_airdrop():
                    if SFX: SFX["click"].play()

                # R para reiniciar desde personaje tras game over / victoria
                if game.state in ("over", "win") and k == pygame.K_r:
                    charsel.reset_animation()
                    game.state = "charsel"

                # F11: alternar pantalla completa
                if k == pygame.K_F11:
                    pygame.display.toggle_fullscreen()

                # Admin: tecla "," abre campo de contraseña
                if k == pygame.K_COMMA and game.state in ("play", "shop_prep"):
                    game.admin_inputting = not game.admin_inputting

                if game.admin_inputting:
                    if k == pygame.K_RETURN:
                        if game.admin_input.strip() == ADMIN_PASSWORD:
                            game.admin_mode = not game.admin_mode
                            if game.admin_mode:
                                game.notifs.append(Notif("MODO ADMIN ACTIVADO", (0, 255, 255), 180))
                            else:
                                game.notifs.append(Notif("MODO ADMIN DESACTIVADO", (255, 100, 100), 180))
                        else:
                            game.notifs.append(Notif("CONTRASENA INCORRECTA", RED, 120))
                        game.admin_inputting = False
                        game.admin_input = ""
                    elif k == pygame.K_ESCAPE:
                        game.admin_inputting = False
                        game.admin_input = ""
                    elif k == pygame.K_BACKSPACE:
                        game.admin_input = game.admin_input[:-1]
                    elif event.unicode and event.unicode.isprintable():
                        game.admin_input += event.unicode

                # Admin: atajos (requieren SHIFT) para teletransporte, spawn, etc.
                if (game.admin_mode and game.state in ("play", "shop_prep") and not game.admin_inputting
                        and (pygame.key.get_mods() & pygame.KMOD_SHIFT)):
                    if k == pygame.K_t:
                        wx = mouse_pos[0] + game.cam.x
                        wy = mouse_pos[1] + game.cam.y
                        game.player.pos = pygame.Vector2(wx, wy)
                        game.notifs.append(Notif("ADMIN: Teletransporte", (0, 255, 255), 60))
                    elif k == pygame.K_k:
                        game._admin_kill_all()
                    elif k == pygame.K_n:
                        game._admin_next_wave()
                    elif k == pygame.K_b:
                        game.player.bytes += 1000
                        game.notifs.append(Notif("ADMIN: +1000 bytes", (0, 255, 255), 60))
                    elif k == pygame.K_l:
                        if game.player.add_xp(game.player.xp_next):
                            game.notifs.append(Notif("ADMIN: +1 nivel", (0, 255, 255), 60))
                    elif k == pygame.K_h:
                        game.player.hp = game.player.max_hp
                        game.notifs.append(Notif("ADMIN: Vida maxima", (0, 255, 255), 60))
                    elif k == pygame.K_w:
                        all_weps = ["auto", "shotgun", "sniper", "pierce"]
                        for w in all_weps:
                            if w not in game.player.weapon_list:
                                game.player.weapon_list.append(w)
                        game.notifs.append(Notif("ADMIN: Armas desbloqueadas", (0, 255, 255), 60))
                    elif k == pygame.K_e:
                        wx = mouse_pos[0] + game.cam.x
                        wy = mouse_pos[1] + game.cam.y
                        game._admin_spawn_enemy(wx, wy)
                    elif k == pygame.K_o:
                        wx = mouse_pos[0] + game.cam.x
                        wy = mouse_pos[1] + game.cam.y
                        game._admin_spawn_vicente_boss(wx, wy)
                    elif k == pygame.K_p:
                        wx = mouse_pos[0] + game.cam.x
                        wy = mouse_pos[1] + game.cam.y
                        game._admin_spawn_powerup(wx, wy)
                    elif k == pygame.K_s:
                        if game.wave_state == "spawning":
                            game.wave_state = "idle"
                            game.notifs.append(Notif("ADMIN: Spawn pausado", (0, 255, 255), 60))
                        elif game.wave_state in ("idle", "prep"):
                            game.wave_state = "spawning"
                            game.notifs.append(Notif("ADMIN: Spawn reanudado", (0, 255, 255), 60))
                # F9: modo cámara lenta (admin, sin SHIFT)
                if game.admin_mode and game.state in ("play", "shop_prep") and k == pygame.K_F9:
                    game.admin_slowmo = not game.admin_slowmo
                    game.notifs.append(Notif(f"ADMIN: Slowmo {'ON' if game.admin_slowmo else 'OFF'}", (0, 255, 255), 60))

            # Eventos de ratón en pausa
            if game.state == "pause" and event.type == pygame.MOUSEMOTION:
                for i, rect in pause_screen.get_sel_rects():
                    if rect.collidepoint(mouse_pos) and pause_screen.sel != i:
                        pause_screen.sel = i
                        if SFX: SFX["hover"].play()

            if game.state == "pause" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rect in pause_screen.get_sel_rects():
                    if rect.collidepoint(mouse_pos):
                        if SFX: SFX["click"].play()
                        if i == 0: game.state = "play"
                        else:
                            game.save_game()
                            game.state = "menu"

            # Eventos de ratón en selección de mapa
            if game.state == "mapsel" and event.type == pygame.MOUSEMOTION:
                for i, rect in mapsel.get_card_rects():
                    if rect.collidepoint(mouse_pos) and mapsel.sel != i:
                        mapsel.sel = i
                        if SFX: SFX["hover"].play()
            if game.state == "mapsel" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rect in mapsel.get_card_rects():
                    if rect.collidepoint(mouse_pos):
                        if SFX: SFX["click"].play()
                        charsel.reset_animation()
                        game.map_sel = i
                        game.state = "charsel"

            # Eventos de ratón en selección de personaje
            if game.state == "charsel" and event.type == pygame.MOUSEMOTION:
                for i, rect in charsel.get_card_rects():
                    if rect.collidepoint(mouse_pos) and charsel.sel != i:
                        charsel.sel = i
                        if SFX: SFX["hover"].play()

            if game.state == "charsel" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rect in charsel.get_card_rects():
                    if rect.collidepoint(mouse_pos):
                        clist = [k for k in CHARACTERS if k != "vicente"]
                        if game.vicente_unlocked:
                            clist.append("vicente")
                        else:
                            clist.append("??")
                        cid = clist[i]
                        if cid == "??":
                            if SFX: SFX["empty"].play()
                            game.notifs.append(Notif("VICENTE BLOQUEADO - Gana la partida!", (100, 100, 100), 120))
                        else:
                            if SFX: SFX["click"].play()
                            game.selected_char = cid
                            game.reset(cid, map_index=game.map_sel)
                            game.state = "play"

            # Eventos de ratón en menú principal
            if game.state == "menu" and event.type == pygame.MOUSEMOTION:
                for i in range(len(menu.opts)):
                    rect = pygame.Rect(WIDTH // 2 - 120, HEIGHT // 2 - 15 + i * 55, 240, 44)
                    if rect.collidepoint(mouse_pos) and menu.sel != i:
                        menu.sel = i
                        if SFX: SFX["hover"].play()

            if game.state == "menu" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i in range(len(menu.opts)):
                    rect = pygame.Rect(WIDTH // 2 - 120, HEIGHT // 2 - 15 + i * 55, 240, 44)
                    if rect.collidepoint(mouse_pos):
                        if SFX: SFX["click"].play()
                        if i == 0:
                            mapsel.reset_animation()
                            game.state = "mapsel"
                        elif i == 1:
                            data = game.load_game()
                            if data:
                                _do_load_game(game, data)
                            else:
                                game.notifs.append(Notif("No hay partida guardada", RED, 60))
                        elif i == 2: game.state = "controls"
                        elif i == 3: game.state = "credits"; credits.reset()
                        else:
                            game.save_game()
                            running = False

        # Entrada del jugador (teclado + ratón)
        keys = pygame.key.get_pressed()
        if game.state in ("play", "shop_prep") and not game.admin_inputting:
            mouse_active = mouse_btn and game.state == "play"
            game.player.handle(keys, mouse_active, mouse_pos, game.grid, game.all_sprites, game.bullets, game.particles, game.cam.x, game.cam.y, game.notifs, enemy_bullets=game.enemy_bullets, enemies=list(game.enemies), brainrots=game.brainrots)

        # Actualización del juego y gestión de música de fondo
        if game.state in ("play", "shop_prep"):
            game.update()
            if _prev_state not in ("play", "shop_prep"):
                stop_menu_music()
                update_bg_music(1, 0.1)
        elif game.state in ("menu", "mapsel", "charsel", "controls", "credits", "pause", "over", "win"):
            if _prev_state in ("play", "shop_prep"):
                stop_bg_music()
        _menu_states = ("menu", "mapsel", "charsel", "controls", "credits")
        if game.state in _menu_states and _prev_state not in _menu_states:
            play_menu_music()
        elif game.state not in _menu_states:
            stop_menu_music()

        # Actualizaciones específicas según el estado
        if game.state == "menu":
            menu.update()

        if game.state == "mapsel":
            mapsel.update(mouse_pos)

        if game.state == "charsel":
            charsel.update(mouse_pos, vicente_unlocked=game.vicente_unlocked)

        if game.state == "controls":
            controls.update()

        if game.state == "tutorial":
            tutorial.update()

        if game.state == "credits":
            credits.update()
            if credits.done:
                # Espera entrada del usuario para continuar
                if keys[pygame.K_RETURN] or keys[pygame.K_ESCAPE]:
                    credits.reset()
                    game.state = "menu"

        if game.state == "pause":
            pause_screen.update()

        if game.state in ("over", "win"):
            result_screen.update()

        # --- Renderizado ---
        screen.fill((0, 5, 0))

        if game.state == "menu":
            menu.draw(screen)
        elif game.state == "mapsel":
            mapsel.draw(screen)
        elif game.state == "charsel":
            charsel.draw(screen, vicente_unlocked=game.vicente_unlocked)
        elif game.state == "controls":
            controls.draw(screen)
        elif game.state == "tutorial":
            tutorial.draw(screen)
        elif game.state == "credits":
            credits.draw(screen)
        elif game.state in ("play", "pause", "over", "win", "shop_prep"):
            game.draw(screen)
            draw_hud(screen, game.player, game.wave, game.wave_state, game.wave_has_boss,
                     game.wave_announce, len(game.enemies), game.notifs, game.prep_timer,
                     game.vicente_near, game.shop_open, game=game, oscar_near=game.oscar_near,
                     fps=int(clock.get_fps()))
            if game.state == "pause":
                pause_screen.draw(screen, game)
            if game.state == "over":
                if result_screen.kind != "over" or result_screen.player != game.player:
                    result_screen.reset("over", game.player, game.wave)
                result_screen.draw(screen)
            if game.state == "win":
                if result_screen.kind != "win" or result_screen.player != game.player:
                    result_screen.reset("win", game.player, game.wave)
                result_screen.draw(screen)
            if game.shop_open and game.state in ("shop_prep", "play"):
                draw_shop(screen, game.player, shop_sel, game.shop_items, game=game)

        _prev_state = game.state
        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__":
    try:
        main()
    except Exception:
        _log_crash(*sys.exc_info())
        raise
    finally:
        pygame.quit()
