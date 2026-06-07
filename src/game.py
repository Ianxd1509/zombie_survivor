import json
import logging
import math
import os
import random

import pygame

from config import AIRDROP_CHANCE_PER_FRAME, AIRDROP_OPEN_RADIUS, BLACK, CHAOS_ITEMS, CODE_SNIPPETS, CYAN, EVOLUTION_ITEM_EMOJIS, EVOLUTION_ITEMS, GACHA_LOOT, GOLD, GREEN, HEIGHT, MAP_H, MAP_W, MAX_AIRDROPS, POWERUP_TYPES, PURPLE, RED, SAVE_FILE, SHOP_ITEMS, WHITE, WIDTH, YELLOW
from src.camera import Camera
from src.effects import CodeSnippet, DamageNum, Decal, Notif, Particle
from src.entities import AirdropCrate, Ally, BillieNPC, Bomb, BrainrotMinion, Bullet, Enemy, Hazard, ImportSnippet, Mimic, Pickup, Player, Powerup, ShopTerminal, Tornado, Wall
from src.sound import SFX, play_boss_music, stop_boss_music, stop_shop_music
from src.tactics import SquadManager
from src.tilemap import COLS, MAP_THEMES, ROWS, TILE, compute_reachable, generate_grid, is_wall


# Rejilla de hash espacial para optimizar detección de colisiones O(n²) → O(1)
class SpatialHash:
    """Spatial hash grid for optimizing collision detection O(n²) -> O(1)."""

    def __init__(self, cell_size=64):
        self.cell_size = cell_size
        self.grid = {}

    def clear(self):
        self.grid.clear()

    def add(self, obj, pos):
        cell_x = int(pos.x // self.cell_size)
        cell_y = int(pos.y // self.cell_size)
        cell_key = (cell_x, cell_y)
        if cell_key not in self.grid:
            self.grid[cell_key] = []
        self.grid[cell_key].append(obj)

    def get_nearby(self, pos, radius):
        cell_x = int(pos.x // self.cell_size)
        cell_y = int(pos.y // self.cell_size)
        nearby = []

        # Check surrounding cells
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                cell_key = (cell_x + dx, cell_y + dy)
                if cell_key in self.grid:
                    nearby.extend(self.grid[cell_key])

        return nearby
from config import ALLY_TYPES, BOMB_TYPES, DOMAIN_EXPANSION, DOMAIN_RADIUS, FOG_NEAR_ALPHA, LIGHT_FLASH_DURATION, MAX_BOMBS, MAX_PARTICLES, OSCAR_ITEMS


# Colisión circular entre dos entidades (proyectil, enemigo)
def _circle_hit(px, py, pr, ex, ey, er):
    dx, dy = ex - px, ey - py
    r = pr + er
    return dx * dx + dy * dy <= r * r


# Clase principal del juego: gestiona oleadas, enemigos, colisiones, power-ups y estado global
class Game:
    # Configuración inicial: personaje, estado, wave, tiendas, sistema de spawn, administrador
    def __init__(self):
        self.selected_char = "irvin"
        self.state = "menu"
        self.wave = 0
        self.wave_state = "idle"
        self.wave_cd = 0
        self.wave_spawned = 0
        self.wave_total = 0
        self.wave_has_boss = False
        self.wave_announce = 0
        self.grid = None  # will be set in reset()
        self.map_index = 0
        self.map_sel = 0
        self.map_theme = MAP_THEMES[0]
        self.prep_timer = 0
        self.vicente = None
        self.vicente_items = []
        self.vicente_near = False
        self.oscar = None
        self.oscar_near = False
        self.oscar_open = False
        self.shop_flash_timer = 0
        self.shop_flash_idx = -1
        self.shop_flash_id = None
        self.shop_tab = 0
        self.spatial_hash = SpatialHash()
        self.ally_bullets = pygame.sprite.Group()
        self.aliados = pygame.sprite.Group()
        self.shop_open = False
        self.shop_costs = {}
        self.enemy_bullets = []
        self.powerups = []
        self.hazards = []
        self.mimics = pygame.sprite.Group()
        self.brainrots = pygame.sprite.Group()
        self.wave_modifier = "normal"
        self.zone_name = ""
        self.zone_timer = 0
        self.vicente_unlocked = False
        self.admin_mode = False
        self.admin_inputting = False
        self.admin_input = ""
        self.admin_slowmo = False
        self.squad_manager = SquadManager()
        self.reset()

    # Guarda progreso del jugador (bytes, hp, stats, wave, items) en JSON
    def save_game(self):
        if not hasattr(self, "player") or self.player is None: return
        data = {
            "char_id": self.player.char_id,
            "bytes": self.player.bytes,
            "hp": self.player.hp,
            "max_hp": self.player.max_hp,
            "kills": self.player.kills,
            "score": self.player.score,
            "level": self.player.level,
            "xp": self.player.xp,
            "shop_levels": self.player.shop_levels,
            "ability_cd_remaining": max(0, self.player.ability_max_cd - (pygame.time.get_ticks() - self.player.ability_cd)),
            "bonus_damage": self.player.bonus_damage,
            "extra_shots": self.player.extra_shots,
            "bonus_firerate": self.player.bonus_firerate,
            "bonus_speed": self.player.bonus_speed,
            "bonus_mag": self.player.bonus_mag,
            "bonus_reload": self.player.bonus_reload,
            "bonus_hp": self.player.bonus_hp,
            "fr_mult": self.player.fr_mult,
            "reload_mult": self.player.reload_mult,
            "dmg_mult": self.player.dmg_mult,
            "vampire": self.player.vampire,
            "piercing": self.player.piercing,
            "lifesteal": self.player.lifesteal,
            "knockback": self.player.knockback,
            "mag": self.player.mag,
            "reserve": self.player.reserve,
            "stamina": self.player.stamina,
            "pos_x": self.player.pos.x,
            "pos_y": self.player.pos.y,
            "wave": self.wave,
            "wave_has_boss": self.wave_has_boss,
            "wave_modifier": self.wave_modifier,
            "wave_total": self.wave_total,
            "weapon_idx": self.player.weapon_idx,
            "weapon_mode": self.player.weapon_mode,
            "turbo_timer": self.player.turbo_timer,
            "shield_timer": self.player.shield_timer,
            "explosive_timer": self.player.explosive_timer,
            "shield": self.player.shield,
            "invulnerable": self.player.invulnerable,
            "invuln_timer": self.player.invuln_timer,
            "byte_multiplier": self.player.byte_multiplier,
            "byte_mult_timer": self.player.byte_mult_timer,
            "ability_speed": self.player.ability_speed,
            "ability_damage_mult": self.player.ability_damage_mult,
            "ability_damage_timer": self.player.ability_damage_timer,
            "ability_speed_timer": self.player.ability_speed_timer,
            "wave_state": self.wave_state,
            "vicente_unlocked": self.vicente_unlocked,
            "shop_costs": self.shop_costs,
            "evolution_items": getattr(self.player, "evolution_items", {}),
            "evolved": getattr(self.player, "evolved", False),
            "chaos_items": getattr(self.player, "chaos_items", []),
            "auras": getattr(self.player, "auras", []),
            "unique_items": getattr(self.player, "unique_items", []),
            "bomb_owned": list(getattr(self.player, "bomb_owned", set())),
            "bomb_queue": getattr(self.player, "bomb_queue", []),
            "bomb_count": getattr(self.player, "bomb_count", 0),
            "bomb_active_idx": getattr(self.player, "bomb_active_idx", 0),
            "ability_charge": getattr(self.player, "ability_charge", 0),
            "domain_charge": getattr(self.player, "domain_charge", 0),
            "domain_cd_timer": getattr(self.player, "domain_cd_timer", 0),
            "prep_timer": getattr(self, "prep_timer", 0),
            "wave_cd": getattr(self, "wave_cd", 0),
            "wave_spawned": getattr(self, "wave_spawned", 0),
            "combo_counter": getattr(self.player, "combo_counter", 0),
            "_last_combo_time": getattr(self.player, "_last_combo_time", 0),
            "map_index": self.map_index,
        }
        try:
            with open(SAVE_FILE, "w") as f:
                json.dump(data, f)
        except Exception as ex:
            logging.error(f"Save failed: {ex}")

    # Carga datos guardados desde archivo JSON
    def load_game(self):
        if not os.path.exists(SAVE_FILE): return None
        try:
            with open(SAVE_FILE) as f:
                return json.load(f)
        except Exception as ex:
            logging.error(f"Load failed: {ex}")
            return None

    # Coloca los NPCs de tienda Vicente y Oscar cerca del laboratorio
    def _spawn_shop_terminals(self):
        pp = self.player.pos
        # Fixed spawn near Laboratorio entrance (tile 49,61 → path leading to lab door)
        lab_pos = pygame.Vector2(2460, 1980)
        col, row = int(lab_pos.x // TILE), int(lab_pos.y // TILE)
        if not is_wall(self.grid, col, row):
            pos = lab_pos
        else:
            offset_variants = [(150, 0), (-150, 0), (0, 150), (0, -150), (150, 100), (-150, -100)]
            pos = None
            for ox, oy in offset_variants:
                candidate = pp + pygame.Vector2(ox, oy)
                candidate.x = max(100, min(MAP_W - 100, candidate.x))
                candidate.y = max(100, min(MAP_H - 100, candidate.y))
                col, row = int(candidate.x // TILE), int(candidate.y // TILE)
                if not is_wall(self.grid, col, row):
                    pos = candidate
                    break
            if pos is None:
                pos = pp + pygame.Vector2(150, 0)
                pos.x = max(100, min(MAP_W - 100, pos.x))
                pos.y = max(100, min(MAP_H - 100, pos.y))
        self.vicente = ShopTerminal(pos, SHOP_ITEMS, name="VICENTE")
        self.vicente_items = [dict(item) for item in SHOP_ITEMS]
        for vi in self.vicente_items:
            if vi["id"] in self.shop_costs:
                vi["cost"] = self.shop_costs[vi["id"]]
        self.vicente_near = False

        # Spawn Oscar nearby (slightly offset from Vicente)
        oscar_offset = pygame.Vector2(120, 80)
        oscar_pos = pos + oscar_offset
        oscar_pos.x = max(100, min(MAP_W - 100, oscar_pos.x))
        oscar_pos.y = max(100, min(MAP_H - 100, oscar_pos.y))
        col2, row2 = int(oscar_pos.x // TILE), int(oscar_pos.y // TILE)
        if is_wall(self.grid, col2, row2):
            oscar_pos = pos + pygame.Vector2(-120, -80)
            oscar_pos.x = max(100, min(MAP_W - 100, oscar_pos.x))
            oscar_pos.y = max(100, min(MAP_H - 100, oscar_pos.y))
        self.oscar = ShopTerminal(oscar_pos, OSCAR_ITEMS, name="OSCAR")
        self.oscar_near = False

    # Otorga recompensas al matar enemigo: bytes, XP, power-ups, partículas, sistema de combo
    def _reward_enemy_death(self, e, bullet_damage=None):
        p = self.player
        p.bytes += e.score_val
        p.score += e.score_val
        p.kills += 1
        p.ability_charge = min(p.ability_max_charge, p.ability_charge + 1)
        p.charge_kills = min(p.charge_max, p.charge_kills + 1)
        p.domain_charge = min(p.domain_kills_needed, p.domain_charge + 1)
        p.domain_kills = min(p.domain_kills_needed, p.domain_kills + 1)
        old_lv = p.level
        p.add_xp(e.score_val)
        if p.level > old_lv:
            self.gold_flash_alpha = 80
        if bullet_damage and p.lifesteal > 0:
            p.hp = min(p.max_hp, p.hp + int(bullet_damage * p.lifesteal))
        if random.random() < 0.08:
            if random.random() < 0.15:
                m = Mimic(e.pos)
                self.all_sprites.add(m); self.mimics.add(m)
            else:
                pu = Powerup(e.pos, random.choice(POWERUP_TYPES))
                self.powerups.append(pu)
        near_cap = len(self.particles) > 120
        if not near_cap:
            for _ in range(12):
                a = random.uniform(0, math.tau)
                sp = random.uniform(1.5, 5.5)
                self.particles.append(Particle(e.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                    e.color, random.uniform(2, 5), random.randint(12, 25)))
            for _ in range(3):
                a = random.uniform(0, math.tau)
                sp = random.uniform(1, 2.5)
                self.particles.append(Particle(e.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                    YELLOW, random.uniform(2, 3), random.randint(8, 15)))
        for _ in range(4):
            self.decals.append(Decal(e.pos + pygame.Vector2(random.uniform(-12, 12), random.uniform(-12, 12)), e.color))
        if random.random() < 0.22:
            pkup = Pickup(e.pos, random.choice(["health", "ammo"]))
            self.all_sprites.add(pkup); self.pickups.add(pkup)
        self.code_snippets.append(CodeSnippet(e.pos, random.choice(CODE_SNIPPETS), (100, 200, 255)))
        if e.explode_r > 0:
            if p.pos.distance_to(e.pos) < e.explode_r:
                p.take_damage(e.explode_dmg)
                self.flash_alpha = 100
            if not near_cap:
                for _ in range(15):
                    a = random.uniform(0, math.tau)
                    sp = random.uniform(3, 8)
                    self.particles.append(Particle(e.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                        (255, 80, 0), random.uniform(3, 6), random.randint(12, 25)))
        if e.split_n > 0:
            for _ in range(e.split_n):
                e2 = Enemy(e.split_type, MAP_W, MAP_H, self.wave, p.pos, grid=self.grid)
                e2.pos = e.pos + pygame.Vector2(random.uniform(-20, 20), random.uniform(-20, 20))
                e2.rect.center = (int(e2.pos.x), int(e2.pos.y))
                self.all_sprites.add(e2); self.enemies.add(e2)
        SFX["kill"].play()
        # Death animation
        e._death_surf = e.image.copy()
        e.dying = True
        e.death_timer = 15
        e.hit_flash = 0
        self.enemies.remove(e)
        self.dead_enemies.append(e)
        if e.explode_r > 0:
            self.shockwaves.append({"pos": pygame.Vector2(e.pos), "timer": 30, "max_r": 0, "color": e.color})

        # Kill combo system
        current_time = pygame.time.get_ticks()
        if hasattr(self.player, "_last_combo_time") and current_time - self.player._last_combo_time > 1000:
            self.player.combo_counter = 0
        self.player.combo_counter += 1
        self.player.combo_timer = 60
        self.player._last_combo_time = current_time

        if self.player.combo_counter >= 5 and self.player.combo_counter % 5 == 0:
            bonus_bytes = 15
            p.bytes += bonus_bytes
            p.score += bonus_bytes
            self.notifs.append(Notif(f"¡Combo x{self.player.combo_counter}! +{bonus_bytes} Bytes", GOLD, 90))
            self.player.combo_text = f"Combo x{self.player.combo_counter}"
            self.player.combo_text_timer = 120

    # Reinicia el estado del juego: sprites, wave, mapa, personaje y cámara
    def reset(self, char_id=None, map_index=None):
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.pickups = pygame.sprite.Group()
        self.particles = []
        self.decals = []
        self.dmg_nums = []
        self.code_snippets = []
        self.notifs = []
        self.decoys = []
        self.dead_enemies = []
        self.shockwaves = []
        self.tornado = None
        self.airdrops = []
        self.gacha_open = False
        self.gacha_result = None
        self._gacha_picked = None
        self.gacha_timer = 0
        self.gacha_spinning = False
        self.gacha_final_idx = 0
        self.enemy_bullets = []
        self.powerups = []
        self.hazards = []
        self.mimics = pygame.sprite.Group()
        self.brainrots = pygame.sprite.Group()
        self.wave_modifier = "normal"
        self.transition_alpha = 0
        self.prep_timer = 0
        self.vicente = None
        self.vicente_items = []
        self.vicente_near = False
        self.oscar = None
        self.oscar_near = False
        self.oscar_open = False
        self.shop_flash_timer = 0
        self.shop_flash_idx = -1
        self.shop_flash_id = None
        self.shop_tab = 0
        self.ally_bullets = pygame.sprite.Group()
        self.aliados = pygame.sprite.Group()
        self.shop_open = False
        stop_shop_music()
        self.shop_items = SHOP_ITEMS
        self.shop_costs = {}
        self.admin_mode = False
        self.admin_inputting = False
        self.admin_input = ""
        self.admin_slowmo = False
        self.wave_cd = 0
        self.wave_spawned = 0

        if map_index is not None:
            self.map_index = map_index
            self.map_theme = MAP_THEMES[map_index]
        else:
            map_index = self.map_index
        self.grid = generate_grid(map_index)
        if char_id:
            self.selected_char = char_id
        spawn_pos = pygame.Vector2(MAP_W // 2, MAP_H // 2)
        col, row = int(spawn_pos.x // TILE), int(spawn_pos.y // TILE)
        if is_wall(self.grid, col, row):
            for r in range(1, 30):
                for dr in range(-r, r + 1):
                    for dc in range(-r, r + 1):
                        if abs(dr) == r or abs(dc) == r:
                            nr, nc = row + dr, col + dc
                            if 0 <= nr < ROWS and 0 <= nc < COLS and not is_wall(self.grid, nc, nr):
                                spawn_pos = pygame.Vector2(nc * TILE + TILE // 2, nr * TILE + TILE // 2)
                                break
                    else:
                        continue
                    break
                else:
                    continue
                break
        sc, sr = int(spawn_pos.x // TILE), int(spawn_pos.y // TILE)
        import src.entities as _ent
        _ent.ENEMY_REACHABLE = compute_reachable(self.grid, sc, sr)
        self.player = Player(self.selected_char, spawn_pos, MAP_W, MAP_H)
        self.all_sprites.add(self.player)
        self._check_evolution()  # check on load in case save has all items
        self.cam = Camera(MAP_W, MAP_H)
        self.transition_alpha = 0
        self.flash_alpha = 0
        self.gold_flash_alpha = 0
        self.dmg_dir_x = 0; self.dmg_dir_y = 0; self.dmg_dir_alpha = 0
        self._start_wave(1)

    def _start_wave(self, n):
        self.hazards = []
        self.wave = n
        self.wave_state = "prep"
        self.wave_spawned = 0
        self.wave_has_boss = n % 5 == 0
        if self.wave_has_boss:
            self.wave_modifier = "normal"
        elif n % 3 == 0:
            self.wave_modifier = random.choice(["horda", "vampirica", "elite", "toxica", "veloz", "blindaje", "explosivo"])
        else:
            self.wave_modifier = random.choice(["normal", "normal", "horda", "vampirica", "elite", "toxica", "veloz", "blindaje", "explosivo"])
        base = 8 + n * 3
        if self.wave_modifier == "horda":
            self.wave_total = base * 2
        elif self.wave_modifier == "elite":
            self.wave_total = base // 2
        else:
            self.wave_total = base
        self.wave_total += 1 if self.wave_has_boss else 0
        self.prep_timer = 3600
        self.wave_announce = 180 if self.wave_has_boss else 120
        self.transition_alpha = 255
        self._spawn_shop_terminals()

        for _ in range(12):
            a = random.uniform(0, math.tau)
            sp = random.uniform(2, 6)
            pos = self.player.pos + pygame.Vector2(random.uniform(-150, 150), random.uniform(-150, 150))
            self.particles.append(Particle(pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                RED if self.wave_has_boss else GREEN, random.uniform(2, 5), random.randint(15, 30)))
        SFX["wave"].play()
        if self.wave_has_boss:
            SFX["boss_warn"].play()
        if self.wave_modifier != "normal" and not self.wave_has_boss:
            mod_names = {"horda":"MOD: HORDA - Enemigos mas debiles pero mas numerosos!",
                         "vampirica":"MOD: VAMPIRICA - Enemigos roban vida al golpear!",
                         "elite":"MOD: ELITE - Enemigos de elite!",
                         "toxica":"MOD: TOXICA - Zonas de peligro en el mapa!",
                         "veloz":"MOD: VELOZ - Enemigos +50% velocidad!",
                         "blindaje":"MOD: BLINDAJE - Enemigos con escudo extra!",
                         "explosivo":"MOD: EXPLOSIVO - Enemigos explotan al morir!"}
            self.notifs.append(Notif(mod_names.get(self.wave_modifier, ""), YELLOW, 180))

    # Crea zonas de peligro tóxico en el mapa si el modificador es "toxica"
    def _start_toxica_hazards(self):
        if self.wave_modifier == "toxica":
            for _ in range(6):
                hx = random.uniform(200, MAP_W - 200)
                hy = random.uniform(200, MAP_H - 200)
                self.hazards.append(Hazard((hx, hy), 5, 50, 600))

    # Funciones auxiliares de administrador (comandos debug)
    def _admin_kill_all(self):
        killed = 0
        for e in list(self.enemies):
            if hasattr(e, "hp") and e.hp > 0:
                e.hp = 0
                self._reward_enemy_death(e)
                killed += 1
        self.notifs.append(Notif(f"ADMIN: {killed} enemigos eliminados", (0, 255, 255), 60))

    # Spawnea un enemigo aleatorio en las coordenadas dadas
    def _admin_spawn_enemy(self, wx, wy):
        from src.entities import Enemy
        etypes = ["runner", "walker", "tank", "fast", "shielded", "splitter", "buffer", "elite"]
        e = Enemy(random.choice(etypes), MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
        e.pos = pygame.Vector2(wx, wy)
        self.all_sprites.add(e)
        self.enemies.add(e)
        self.notifs.append(Notif(f"ADMIN: spawned {e.etype}", (0, 255, 255), 60))

    # Spawnea al jefe Vicente (jefe final) en las coordenadas dadas
    def _admin_spawn_vicente_boss(self, wx, wy):
        for e in self.enemies:
            if getattr(e, "etype", None) == "vicente_boss" and e.hp > 0:
                self.notifs.append(Notif("ADMIN: Ya hay un jefe Vicente activo", (255, 100, 100), 60))
                return
        from src.entities import Enemy
        e = Enemy("vicente_boss", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
        e.pos = pygame.Vector2(wx, wy)
        e.all_sprites_ref = self.all_sprites
        e.enemies_ref = self.enemies
        self.all_sprites.add(e)
        self.enemies.add(e)
        play_boss_music()
        self.notifs.append(Notif("ADMIN: Vicente jefe final invocado!", (100, 200, 255), 120))

    # Spawnea un power-up aleatorio en las coordenadas dadas
    def _admin_spawn_powerup(self, wx, wy):
        import random
        ptypes = ["health", "ammo", "speed", "dmg", "firerate"]
        from src.entities import Pickup
        p = Pickup(pygame.Vector2(wx, wy), random.choice(ptypes), MAP_W, MAP_H)
        self.all_sprites.add(p)
        self.pickups.add(p)
        self.notifs.append(Notif(f"ADMIN: powerup {p.type}", (0, 255, 255), 60))

    # Salta a la siguiente oleada eliminando todos los enemigos
    def _admin_next_wave(self):
        self.wave_spawned = self.wave_total
        self.enemies.empty()
        stop_boss_music()
        self.notifs.append(Notif("ADMIN: Saltando a siguiente wave", (0, 255, 255), 60))

    # Spawnea un enemigo según wave, modificador y tipo: jefe, minijefe, runner, tank, etc.
    def _spawn_enemy(self):
        mod = self.wave_modifier
        if self.wave_has_boss and self.wave_spawned == self.wave_total - 1:
            if self.wave >= 30:
                e = Enemy("vicente_boss", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                e.all_sprites_ref = self.all_sprites
                e.enemies_ref = self.enemies
                self.notifs.append(Notif("VICENTE: Legado Python!", (100, 200, 255), 180))
                play_boss_music()  # Activa música de jefe final Vicente
            else:
                e = Enemy("boss", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                self.notifs.append(Notif("JEFE!", RED, 120))
        elif not self.wave_has_boss and self.wave % 3 == 0 and self.wave_spawned == 0 and random.random() < 0.5:
            e = Enemy("elite", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
            self.notifs.append(Notif("MINI-JEFE!", PURPLE, 90))
        else:
            p = random.random()
            if mod == "elite":
                etype = random.choice(["tank", "shielded", "splitter", "buffer"])
                e = Enemy(etype, MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
            else:
                if self.wave >= 4: p *= 0.7
                elif self.wave >= 2: p *= 0.85
                if p < 0.12:
                    e = Enemy("runner", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                elif p < 0.30:
                    e = Enemy("walker", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                elif p < 0.42:
                    e = Enemy("tank", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                elif p < 0.50:
                    e = Enemy("swarm", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                    extra = max(0, min(random.randint(2, 4), self.wave_total - self.wave_spawned - 1))
                    for _ in range(extra):
                        e2 = Enemy("swarm", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                        self.all_sprites.add(e2); self.enemies.add(e2)
                        self.wave_spawned += 1
                elif p < 0.60 and self.wave >= 2:
                    e = Enemy("shooter", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                elif p < 0.68 and self.wave >= 2:
                    e = Enemy("healer", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                elif p < 0.76 and self.wave >= 3:
                    e = Enemy("shielded", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                elif p < 0.83 and self.wave >= 3:
                    e = Enemy("bomber", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                elif p < 0.89 and self.wave >= 4:
                    e = Enemy("splitter", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                elif p < 0.94 and self.wave >= 5:
                    e = Enemy("worm", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                elif p < 0.98 and self.wave >= 5:
                    e = Enemy("buffer", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                else:
                    e = Enemy("camouflage", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
        if self.wave_modifier == "horda":
            e.max_hp = int(e.max_hp * 0.6)
            e.hp = e.max_hp
        elif self.wave_modifier == "veloz":
            e.speed *= 1.5
        elif self.wave_modifier == "blindaje":
            e.shield_hp = int(e.max_hp * 0.5)
        elif self.wave_modifier == "explosivo":
            e.explode_r = 60
            e.explode_dmg = 20
        self.all_sprites.add(e); self.enemies.add(e)

    # Abre la tienda del vendedor (Vicente u Oscar)
    def open_shop(self, vendor="vicente"):
        self.vendor = vendor
        if vendor == "oscar":
            self.shop_items = list(OSCAR_ITEMS)
        else:
            self.shop_items = [dict(item) for item in SHOP_ITEMS]
            for item in self.shop_items:
                if item["id"] in self.shop_costs:
                    item["cost"] = self.shop_costs[item["id"]]
        self.shop_open = True

    # Compra un item de la tienda: descuenta bytes y aplica la mejora
    def buy_shop_item(self, idx):
        items = self.shop_items
        if idx >= len(items): return
        item = items[idx]
        is_oscar = "id" not in item
        if is_oscar:
            cost = item["cost"]
            tid = item.get("type", "")
            # Oscar perm price scaling
            if tid.startswith("perm_"):
                tid2 = tid.replace("perm_", "")
                self.player.shop_levels[f"oscar_{tid2}"] = self.player.shop_levels.get(f"oscar_{tid2}", 0) + 1
                cost = int(item["cost"] * (1.35 ** (self.player.shop_levels[f"oscar_{tid2}"] - 1)))
            if self.player.bytes >= cost:
                self.player.bytes -= cost
                self._apply_oscar_item(item)
                self.shop_flash_timer = 20
                self.shop_flash_id = item.get("type", "")
                SFX["click"].play()
            return
        # Vicente item handling
        cost = item["base_cost"]
        if item["id"] in self.shop_costs:
            cost = self.shop_costs[item["id"]]
        if self.vendor == "vicente":
            cost = max(1, int(cost * 0.75))
        if self.player.bytes >= cost and self.player.shop_levels.get(item["id"], 0) < item["max"]:
            self.player.bytes -= cost
            self.player.shop_levels[item["id"]] = self.player.shop_levels.get(item["id"], 0) + 1
            self.player.apply_upgrade(item["id"])
            self.shop_costs[item["id"]] = int(cost * 1.35)
            self.shop_flash_timer = 20
            self.shop_flash_id = item["id"]
            SFX["click"].play()

    # Aplica efectos de items de Oscar: buffs, aliados, bombas, auras, fragmentos de evolución
    def _apply_oscar_item(self, item):
        tid = item["type"]
        p = self.player
        if tid.startswith("buff_"):
            btype = tid.replace("buff_", "")
            if btype == "turbo":
                p.turbo_timer = max(p.turbo_timer, 480)
            elif btype == "shield":
                p.shield_timer = max(p.shield_timer, 480)
                p.shield = 30
                p.invulnerable = True
                p.invuln_timer = max(p.invuln_timer, 480)
            elif btype == "dmg":
                p.ability_damage_mult = max(p.ability_damage_mult, 2.0)
                p.ability_damage_timer = max(p.ability_damage_timer, 480)
            elif btype == "speed":
                p.ability_speed = max(p.ability_speed, 0.3)
                p.ability_speed_timer = max(p.ability_speed_timer, 480)
            self.notifs.append(Notif(f"+{item['name']}", (100, 255, 100), 60))
        elif tid.startswith("ally_"):
            aid = tid.replace("ally_", "")
            if aid == "irvin": aid = "irvin_sis"
            elif aid == "usiel": aid = "usiel_sis"
            for a in self.aliados:
                if a.aid == aid:
                    self.notifs.append(Notif("Aliado ya activo!", RED, 60))
                    p.bytes += item["cost"]
                    return
            spawn_pos = p.pos + pygame.Vector2(random.uniform(-60, 60), random.uniform(-60, 60))
            ally = Ally(aid, spawn_pos, p, MAP_W, MAP_H)
            self.aliados.add(ally)
            self.all_sprites.add(ally)
            self.notifs.append(Notif(f"¡{ALLY_TYPES[aid]['name']} se une!", (100, 255, 100), 90))
        elif tid.startswith("bomb_"):
            btype = tid.replace("bomb_", "")
            if btype in p.bomb_owned:
                self.notifs.append(Notif("Bomba ya adquirida!", RED, 60))
                p.bytes += item["cost"]
                return
            if len(p.bomb_owned) >= len(BOMB_TYPES):
                self.notifs.append(Notif("Ya tienes todas las bombas!", RED, 60))
                p.bytes += item["cost"]
                return
            p.bomb_owned.add(btype)
            p.bomb_queue.append(btype)
            p.bomb_count = min(p.bomb_count + 1, MAX_BOMBS)
            p.bomb_active_idx = len(p.bomb_queue) - 1
            self.notifs.append(Notif(f"¡{BOMB_TYPES[btype]['name']} adquirida!", (255, 200, 100), 90))
        elif tid.startswith("perm_"):
            ptype = tid.replace("perm_", "")
            if ptype == "hp":
                p.max_hp += 10
                p.hp = min(p.hp + 10, p.max_hp)
                self.notifs.append(Notif("Vida +10 permanente!", (100, 255, 100), 90))
            elif ptype == "speed":
                p.bonus_speed += 0.05
                self.notifs.append(Notif("Velocidad +5% permanente!", (100, 255, 100), 90))
            elif ptype == "dmg":
                p.bonus_damage += 3
                self.notifs.append(Notif("Daño +3 permanente!", (100, 255, 100), 90))
            elif ptype == "firerate":
                p.fr_mult *= 0.9
                self.notifs.append(Notif("Cadencia +10% permanente!", (100, 255, 100), 90))
        elif tid.startswith("aura_"):
            atype = tid.replace("aura_", "")
            if atype in p.auras:
                self.notifs.append(Notif("Aura ya activa!", RED, 60))
                p.bytes += item["cost"]
                return
            p.auras.append(atype)
            self.notifs.append(Notif(f"Aura de {atype} activada!", (100, 200, 255), 90))
        elif tid == "evo_fragment":
            cid = self.selected_char
            needed = EVOLUTION_ITEMS.get(cid, [])
            missing = [it for it in needed if p.evolution_items.get(it, 0) < 1]
            if missing:
                gave = random.choice(missing)
                p.evolution_items[gave] = p.evolution_items.get(gave, 0) + 1
                emoji = EVOLUTION_ITEM_EMOJIS.get(gave, "📦")
                self.notifs.append(Notif(f"Fragmento Evo: {emoji} {gave} obtenido!", GOLD, 120))
                self._check_evolution()
            else:
                p.bytes += 200
                self.notifs.append(Notif("Ya tienes todos los items! +200 Bytes", GOLD, 90))
        elif tid.startswith("unique_"):
            uniq = tid.replace("unique_", "")
            if uniq in p.unique_items:
                self.notifs.append(Notif("Item unico ya adquirido!", RED, 60))
                p.bytes += item["cost"]
                return
            p.unique_items.append(uniq)
            self._apply_unique(uniq, p)
            self.notifs.append(Notif(f"Item unico: {item['name']} equipado!", GOLD, 90))

    # Aplica items únicos según personaje: efectos pasivos especiales (rebote, vampiro, etc.)
    def _apply_unique(self, uniq, p):
        if uniq == "irvin":
            p.bonus_mag += int(p.char_data["mag"] * 0.5)
            p.mag = min(p.mag + int(p.char_data["mag"] * 0.5), p.char_data["mag"] + p.bonus_mag)
        elif uniq == "sebas":
            p.rebotar_timer = 21600
            p.rebotar_bounces = 999
        elif uniq == "leo":
            p.byte_multiplier = max(p.byte_multiplier, 2.0)
            p.byte_mult_timer = max(p.byte_mult_timer, 600)
        elif uniq == "diego":
            p.vampire = max(p.vampire, 2)
        elif uniq == "usiel":
            p.ability_max_cd = max(1, int(p.ability_max_cd * 0.9))
            p.ability_cd = p.ability_max_cd
        elif uniq == "obed":
            pass  # Billie double duration handled in handle()
        elif uniq == "eder":
            p.ability_damage_mult = max(p.ability_damage_mult, 1.5)
        elif uniq == "ian":
            p.ability_max_charge = int(p.ability_max_charge * 1.5)
        elif uniq == "randy":
            p._wall_hp_mult = 2.0
            for w in p.walls:
                w.hp *= 2
                w.max_hp *= 2
                w._redraw()

    def open_airdrop(self):
        """Open the nearest landed airdrop crate (called when F pressed near one)."""
        for c in self.airdrops:
            if c.landed and not c.opened and self.player.pos.distance_to(c.pos) < AIRDROP_OPEN_RADIUS:
                c.opened = True
                self._start_gacha()
                return True
        return False

    # Inicia la ruleta gacha seleccionando un premio aleatorio con pesos
    def _start_gacha(self):
        total_w = sum(w for _, _, w in GACHA_LOOT)
        roll = random.uniform(0, total_w)
        cum = 0
        self._gacha_picked = None
        for name, typ, w in GACHA_LOOT:
            cum += w
            if roll <= cum:
                self._gacha_picked = (name, typ)
                break
        if self._gacha_picked is None:
            self._gacha_picked = ("Bytes +50", "bytes")
        self.gacha_spinning = True
        self.gacha_timer = 60
        self.gacha_open = True
        self.gacha_result = None

    # Aplica la recompensa del gacha: bytes, buffs temporal, item de evolución o caos
    def _apply_gacha_reward(self):
        name, typ = self._gacha_picked
        self.gacha_result = (name, typ)
        p = self.player
        if typ == "bytes":
            amounts = {"Bytes +50": 50, "Bytes +100": 100, "Bytes +200": 200}
            p.bytes += amounts.get(name, 50)
            self.notifs.append(Notif(f"Gacha: +{amounts.get(name, 50)} Bytes!", GOLD, 90))
        elif typ.startswith("buff_"):
            if typ == "buff_turbo":
                p.turbo_timer = max(p.turbo_timer, 300)
                self.notifs.append(Notif("Gacha: Turbo 5s!", (255, 100, 50), 90))
            elif typ == "buff_shield":
                p.shield_timer = max(p.shield_timer, 300)
                p.shield = 30
                p.invulnerable = True
                p.invuln_timer = 300
                self.notifs.append(Notif("Gacha: Escudo 5s!", (50, 150, 255), 90))
            elif typ == "buff_dmg":
                p.ability_damage_mult = 2.0
                p.ability_damage_timer = max(p.ability_damage_timer, 480)
                self.notifs.append(Notif("Gacha: Doble Daño 8s!", (255, 50, 50), 90))
            elif typ == "buff_speed":
                p.ability_speed = max(p.ability_speed, 0.2)
                p.ability_speed_timer = max(p.ability_speed_timer, 480)
                self.notifs.append(Notif("Gacha: Velocidad +20% 8s!", (50, 200, 100), 90))
        elif typ == "evo_item":
            cid = self.selected_char
            needed = EVOLUTION_ITEMS.get(cid, [])
            # Pick a random needed item the player doesn't have yet
            missing = [it for it in needed if p.evolution_items.get(it, 0) < 1]
            if missing:
                item = random.choice(missing)
                p.evolution_items[item] = p.evolution_items.get(item, 0) + 1
                emoji = EVOLUTION_ITEM_EMOJIS.get(item, "📦")
                self.notifs.append(Notif(f"Gacha: {emoji} {item} obtenido!", (255, 215, 0), 120))
                self._check_evolution()
            else:
                # Already have all items, give bytes instead
                p.bytes += 75
                self.notifs.append(Notif("Gacha: Ya tienes todos los items! +75 Bytes", GOLD, 90))
        elif typ == "chaos":
            item = random.choice(CHAOS_ITEMS)
            p.chaos_items.append(item)
            self.notifs.append(Notif(f"Gacha: Item Caos {item}!", PURPLE, 120))
        self.gacha_result = None

    # Verifica si el jugador tiene todos los items de evolución y evoluciona al personaje
    def _check_evolution(self):
        """Check if player has all evolution items for their character and evolve."""
        cid = self.selected_char
        needed = EVOLUTION_ITEMS.get(cid, [])
        p = self.player
        if p.evolved:
            return
        for it in needed:
            if p.evolution_items.get(it, 0) < 1:
                return
        # All items collected - evolve!
        p.evolved = True
        p.max_hp += 30
        p.hp = min(p.hp + 30, p.max_hp)
        p.bonus_damage += 5
        p.bonus_speed += 0.15
        self.notifs.append(Notif(f"{p.char_data['name']} HA EVOLUCIONADO! HP+30 DMG+5 SPD+15%", GOLD, 300))
        for _ in range(50):
            a = random.uniform(0, math.tau)
            sp = random.uniform(2, 8)
            self.particles.append(Particle(p.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                GOLD, random.uniform(3, 6), random.randint(20, 40)))

    # Detecta en qué zona del mapa está el jugador (edificios, cafetería, laboratorio, etc.)
    def _detect_zone(self):
        col, row = self.player.pos.x // TILE, self.player.pos.y // TILE
        new_zone = ""
        if 10 <= row <= 28 and 18 <= col <= 36:
            new_zone = "Edificio A (Aulas)"
        elif 10 <= row <= 28 and 54 <= col <= 72:
            new_zone = "Edificio B (Aulas)"
        elif 50 <= row <= 66 and 18 <= col <= 36:
            new_zone = "Cafeteria (Tienda)"
        elif 50 <= row <= 66 and 54 <= col <= 72:
            new_zone = "Lab. Computo (Jefe)"
        elif 72 <= row <= 92 and 26 <= col <= 68:
            new_zone = "Canchas (Arena)"
        elif 30 <= row <= 48 and 30 <= col <= 60:
            new_zone = "Plaza Civica"
        if new_zone != self.zone_name:
            self.zone_name = new_zone
            self.zone_timer = 180

    # Pobla el spatial hash con posiciones de enemigos para colisiones rápidas O(1)
    def _populate_spatial_hash(self):
        self.spatial_hash.clear()
        for e in self.enemies:
            self.spatial_hash.add(e, e.pos)

    # Detecta si una bala golpea a un enemigo usando spatial hash
    def _bullet_hit_enemy(self, b):
        nearby = self.spatial_hash.get_nearby(b.pos, b.radius + 32)
        bx, by, br = b.pos.x, b.pos.y, b.radius
        for e in nearby:
            if not hasattr(e, "hp") or e.hp <= 0 or getattr(e, "burrowed", False):
                continue
            if _circle_hit(bx, by, br, e.pos.x, e.pos.y, e.radius):
                return e
        return None

    # Actualiza aliados: movimiento, disparo, sincronización de sprites y balas aliadas
    def _update_allies(self):
        enemies_list = list(self.enemies)
        for a in list(self.aliados):
            if not a.alive():
                self.aliados.remove(a)
                continue
            result = a.update(enemies_list, grid=self.grid)
            if isinstance(result, Bullet):
                self.ally_bullets.add(result)
                self.all_sprites.add(result)
        self.ally_bullets.update(self.grid)

    # Sincroniza minions Brainrot entre el jugador y el grupo de sprites
    def _sync_brainrots(self):
        for br in list(self.player.active_brainrots):
            if br.hp > 0:
                if br not in self.brainrots:
                    self.all_sprites.add(br)
                    self.brainrots.add(br)
            else:
                self.player.active_brainrots.remove(br)
                if br in self.brainrots:
                    self.brainrots.remove(br)

    # Sincroniza NPC Billie con el grupo de sprites si está vivo
    def _sync_companions(self):
        if self.player.billie_npc is not None:
            try:
                alive = self.player.billie_npc.alive()
            except Exception:
                alive = True
            if alive and self.player.billie_npc not in self.all_sprites:
                self.all_sprites.add(self.player.billie_npc)

    # Bucle principal del juego: oleadas, enemigos, colisiones, power-ups, auras, dominio
    def update(self):
        if self.shop_flash_timer > 0:
            self.shop_flash_timer -= 1
        if self.state not in ("play", "shop_prep"):
            return
        if not self.player.alive():
            if self.state != "over":
                self.state = "over"
                SFX["death"].play()
                SFX["gameover"].play()
            return
        if self.admin_mode:
            self.player.invulnerable = True
            self.player.bytes += 5
            self.player.ability_charge = self.player.ability_max_charge
            self.player.domain_charge = 30
            self.player.domain_cd = 0
        self._detect_zone()

        # Fase de preparación: espera antes del ataque, tiendas activas
        if self.wave_state == "prep":
            self.prep_timer -= 1
            self.wave_announce -= 1
            if self.prep_timer <= 0:
                self.prep_timer = 0
                self.wave_state = "spawning"
                self.wave_announce = 120
                if self.state == "shop_prep":
                    self.state = "play"
                self.notifs.append(Notif("Iniciando ataque...", YELLOW, 90))
                self._start_toxica_hazards()
            if self.vicente:
                self.vicente.update()
                self.vicente_near = self.player.pos.distance_to(self.vicente.pos) < 60
            if self.oscar:
                self.oscar.update()
                self.oscar_near = self.player.pos.distance_to(self.oscar.pos) < 60
            self._sync_brainrots()
            self._sync_companions()
            self._update_allies()
            self.cam.follow(self.player.pos.x, self.player.pos.y, WIDTH, HEIGHT)
            self.particles = [p for p in self.particles if p.update()]
            self.notifs = [n for n in self.notifs if n.update()]
            return

        # Fase de spawn: genera enemigos progresivamente hasta completar la oleada
        if self.wave_state == "spawning":
            self.wave_cd += 1
            if self.wave_cd > max(2, 15 - self.wave * 2):
                self.wave_cd = 0
                if self.wave_spawned < self.wave_total and len(self.enemies) < 80:
                    self._spawn_enemy()
                    self.wave_spawned += 1
                elif self.wave_spawned >= self.wave_total:
                    self.wave_state = "clear"

        # Fase clear: todos los enemigos eliminados, avanza a la siguiente oleada
        if self.wave_state == "clear" and len(self.enemies) == 0:
            stop_boss_music()  # Detiene música de jefe al limpiar la wave
            SFX["wave_clear"].play()
            if self.wave >= 30:
                self.state = "win"
                self.vicente_unlocked = True
                SFX["victory"].play()
                self.notifs.append(Notif("VICTORIA! Has limpiado todos los servidores!", GOLD, 300))
                self.notifs.append(Notif("VICENTE desbloqueado! Nuevo personaje secreto!", (100, 200, 255), 300))
                return
            self._start_wave(self.wave + 1)
            self.state = "shop_prep"
            SFX["transition"].play()
            self.notifs.append(Notif("Fase de preparacion! 60s para el ataque!", GOLD, 150))

        if self.wave_announce > 0:
            self.wave_announce -= 1

        self.cam.follow(self.player.pos.x, self.player.pos.y, WIDTH, HEIGHT)
        pp = self.player.pos
        self._sync_brainrots()
        self._sync_companions()
        self._update_allies()

        # IA de enemigos: resetea buffs, aplica buffs de buffer, actualiza cada enemigo
        enemies_list = list(self.enemies)
        self.squad_manager.update(enemies_list, pp, self.grid)

        for e in enemies_list:
            e.dmg_mult = 1.0
            e.speed_mult = 1.0

        for e in enemies_list:
            if e.etype == "buffer":
                buff_r2 = e.buff_r * e.buff_r
                ex, ey = e.pos.x, e.pos.y
                for e2 in enemies_list:
                    if e2 is e:
                        continue
                    dx, dy = e2.pos.x - ex, e2.pos.y - ey
                    if dx * dx + dy * dy < buff_r2:
                        e2.dmg_mult = max(e2.dmg_mult, 1.0 + e.buff_amt)
                        e2.speed_mult = max(e2.speed_mult, 1.0 + e.buff_amt * 0.5)

        for e in enemies_list:
            e.update(pp, enemies=enemies_list, enemy_bullets=self.enemy_bullets, particles=self.particles, grid=self.grid)
            if e.hp <= 0:
                if getattr(e, "etype", None) == "vicente_boss":
                    stop_boss_music()  # Detiene música al morir el jefe Vicente
                self._reward_enemy_death(e)
        self.bullets.update(self.grid)

        # Partículas de estela de balas (densidad adaptativa según rendimiento)
        nbullets = len(self.bullets)
        nene = len(self.enemies)
        density_mult = 1.0
        if nene > 60: density_mult = 0.3
        elif nene > 30: density_mult = 0.5
        trail_chance = 1.0 * density_mult if nbullets < 30 else 0.5 * density_mult if nbullets < 60 else 0.2 * density_mult
        for b in list(self.bullets):
            if random.random() < trail_chance:
                self.particles.append(Particle(b.pos, pygame.Vector2(0, 0),
                    b.color, random.uniform(1.5, 3), random.randint(4, 8), gravity=0, shrink=True))
            if nbullets < 40 and random.random() < 0.5 * density_mult:
                self.particles.append(Particle(b.pos, pygame.Vector2(0, 0),
                    (255, 255, 255), random.uniform(1, 2), random.randint(2, 4), gravity=0, shrink=True))

        # Actualización del NPC Zapiens (mini-jefe neutral)

        # Actualización de minions Brainrot: atacan enemigos, sincronización
        enemies_list = list(self.enemies)
        for m in list(self.brainrots):
            if not m.alive():
                self.brainrots.remove(m)
                continue
            m.update(enemies_list, pp, grid=self.grid)
            # Minion death
            if m.hp <= 0:
                m.kill()
                self.brainrots.remove(m)
                if m in self.player.active_brainrots:
                    self.player.active_brainrots.remove(m)
                for _ in range(6):
                    a = random.uniform(0, math.tau)
                    sp = random.uniform(1.5, 4)
                    self.particles.append(Particle(m.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                        (180, 50, 255), random.uniform(2, 4), random.randint(8, 16)))

        # Daño por zonas de peligro (modificador tóxico)
        for h in list(self.hazards):
            dmg = h.update(self.player.pos)
            if dmg > 0:
                self.player.take_damage(dmg)
                self.flash_alpha = 60
            if not h.alive:
                self.hazards.remove(h)

        # Detección de Mimics: explotan al contacto con el jugador
        for m in list(self.mimics):
            m.update()
            if self.player.pos.distance_to(m.pos) < self.player.radius + m.radius + 4:
                m.explode(self.player, self.particles)
                self.mimics.remove(m)
                self.flash_alpha = 100
                vec = m.pos - self.player.pos
                if vec.length() > 0: vec.normalize_ip()
                self.dmg_dir_x, self.dmg_dir_y = vec.x, vec.y
                self.dmg_dir_alpha = 120

        # Enemigos atacan aliados, brainrots y walls cercanos
        for e in enemies_list:
            if e.hp <= 0: continue
            ed = int(e.damage * e.dmg_mult)
            # Atacar aliados
            for a in list(self.aliados):
                if a.pos.distance_to(e.pos) < e.radius + a.radius + 4:
                    a.hp -= max(1, ed // 2)
                    if a.hp <= 0:
                        a.kill()
                        self.aliados.remove(a)
                        self.all_sprites.remove(a)
                        self.notifs.append(Notif("Aliado eliminado!", RED, 60))
            # Atacar brainrots
            for m in list(self.brainrots):
                if m.pos.distance_to(e.pos) < e.radius + m.radius + 4:
                    m.hp -= max(1, ed // 3)
                    if m.hp <= 0:
                        m.kill()
                        self.brainrots.remove(m)
            # Atacar walls
            for w in list(self.player.walls):
                if w.pos.distance_to(e.pos) < e.radius + w.radius + 4:
                    w.hp -= max(1, ed // 2)
                    if w.hp <= 0:
                        self.player.walls.remove(w)

        self._populate_spatial_hash()

        # Colisión balas del jugador vs enemigos (spatial hash)
        for b in list(self.bullets):
            e = self._bullet_hit_enemy(b)
            if not e:
                continue

            kb_mult = 1 + self.player.knockback
            dir = (e.pos - b.pos).normalize() if e.pos.distance_to(b.pos) > 0.5 else pygame.Vector2(1, 0)

            is_critical = random.random() < 0.1
            final_damage = b.damage * 2 if is_critical else b.damage

            died = e.hit(final_damage, dir, kb_mult)
            self.dmg_nums.append(DamageNum(e.pos, str(final_damage), WHITE if final_damage >= 15 else YELLOW))
            self.code_snippets.append(CodeSnippet(e.pos, random.choice(CODE_SNIPPETS), (100, 200, 255)))

            if is_critical:
                self.dmg_nums.append(DamageNum(e.pos, "¡CRIT!", GOLD))
                for _ in range(5):
                    a = random.uniform(0, math.tau)
                    sp = random.uniform(2, 6)
                    self.particles.append(Particle(e.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                                                 GOLD, random.uniform(2, 4), random.randint(8, 15)))

            explosive_dmg = 0
            if self.player.explosive_timer > 0:
                explosive_dmg = int(b.damage * 0.5)
                for _ in range(10):
                    a = random.uniform(0, math.tau)
                    sp = random.uniform(2, 5)
                    self.particles.append(Particle(e.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                                                 (255, 80, 80), random.uniform(2, 4), random.randint(8, 18)))

            if died:
                self._reward_enemy_death(e, final_damage)
                if explosive_dmg:
                    for e2 in list(self.enemies):
                        if e2 is e:
                            continue
                        if e2.pos.distance_squared_to(e.pos) < 1600:
                            died2 = e2.hit(explosive_dmg)
                            self.dmg_nums.append(DamageNum(e2.pos, str(explosive_dmg), (255, 100, 100)))
                            if died2:
                                self._reward_enemy_death(e2, explosive_dmg)
            elif e.is_boss and not e.boss_summoned and e.hp <= e.max_hp * 0.3:
                e.boss_summoned = True
                self.notifs.append(Notif("JEFE invoca refuerzos!", RED, 120))
                for _ in range(4):
                    e2 = Enemy("runner", MAP_W, MAP_H, self.wave, self.player.pos, grid=self.grid)
                    self.all_sprites.add(e2)
                    self.enemies.add(e2)

            if self.player.rebotar_timer > 0 and self.player.rebotar_bounces > 0:
                neighbors = [e2 for e2 in self.enemies if e2 is not e and e2.pos.distance_squared_to(e.pos) < 22500]
                if neighbors:
                    target = random.choice(neighbors)
                    self.player.rebotar_bounces -= 1
                    bounce_dmg = int(b.damage * 0.6)
                    for e2 in list(self.enemies):
                        if not e2.alive(): continue
                        if e2 is e: continue
                        if e2.pos.distance_to(target.pos) < 100:
                            died2 = e2.hit(bounce_dmg)
                            if died2:
                                self._reward_enemy_death(e2, bounce_dmg)
                    self.dmg_nums.append(DamageNum(target.pos, str(bounce_dmg), (255, 100, 100)))
                    for _ in range(6):
                        a2 = random.uniform(0, math.tau)
                        sp2 = random.uniform(1, 5)
                        self.particles.append(Particle(target.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2,
                            (255, 100, 100), random.uniform(2, 4), random.randint(6, 16)))

            if hasattr(b, "pierce") and b.pierce > 0:
                b.pierce -= 1
            else:
                b.kill()

        # Colisión balas de aliados vs enemigos
        for b in list(self.ally_bullets):
            e = self._bullet_hit_enemy(b)
            if e:
                dir = (e.pos - b.pos).normalize() if e.pos.distance_to(b.pos) > 0.5 else pygame.Vector2(1, 0)
                died = e.hit(b.damage, dir)
                self.dmg_nums.append(DamageNum(e.pos, str(b.damage), CYAN))
                if died:
                    self._reward_enemy_death(e, b.damage)
                b.kill()

        # Colisión rayos láser del jugador vs enemigos
        for b in list(self.player.lasers):
            b.update(self.grid, self.particles)
            if not b.alive():
                self.player.lasers.remove(b)
                continue
            e = self._bullet_hit_enemy(b)
            if e:
                dir = (e.pos - b.pos).normalize() if e.pos.distance_to(b.pos) > 0.5 else pygame.Vector2(1, 0)
                died = e.hit(b.damage, dir)
                self.dmg_nums.append(DamageNum(e.pos, str(b.damage), (255, 50, 50)))
                if died:
                    self._reward_enemy_death(e, b.damage)

        # Daño de balas del jugador contra Zapiens (se le puede atacar)
                    b.kill()
                    for _ in range(4):
                        a2 = random.uniform(0, math.tau)
                        sp2 = random.uniform(1, 3)
                        self.particles.append(Particle(b.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2,
                            (100, 200, 255), random.uniform(2, 3), random.randint(4, 10)))
                    break

        # Colisión balas enemigas contra el jugador
        for eb in list(self.enemy_bullets):
            if not eb.update(grid=self.grid):
                self.enemy_bullets.remove(eb)
                continue
            if self.player.pos.distance_to(eb.pos) < self.player.radius + eb.radius:
                self.player.take_damage(eb.damage)
                self.flash_alpha = 80
                vec = eb.pos - self.player.pos
                if vec.length() > 0: vec.normalize_ip()
                self.dmg_dir_x, self.dmg_dir_y = vec.x, vec.y
                self.dmg_dir_alpha = 120
                self.enemy_bullets.remove(eb)
                for _ in range(6):
                    a = random.uniform(0, math.tau)
                    sp = random.uniform(1, 3)
                    self.particles.append(Particle(eb.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                        (255, 50, 50), random.uniform(2, 3), random.randint(5, 12)))

        # Actualización de bombas: napalm, flash, cluster, mina, fragmentación
        for b in list(self.player.bombs):
            if not b.alive():
                b.kill()
                self.player.bombs.remove(b)
                continue
            # Napalm pool per-frame
            if b.btype == "napalm" and b.pool_life > 0:
                b.pool_life -= 1
                for e in list(self.enemies):
                    if e.pos.distance_to(b.pos) < b.radius:
                        e.hp -= BOMB_TYPES["napalm"]["dmg"] // 2
                        if e.hp <= 0:
                            self._reward_enemy_death(e)
                if b.pool_life % 15 == 0:
                    self.shockwaves.append({"pos":b.pos,"timer":8,"max_r":b.radius,"color":(255,100,0)})
                if b.pool_life <= 0:
                    b.kill()
                    self.player.bombs.remove(b)
                continue
            b.update(grid=self.grid, enemies=self.enemies)
            if b.detonated or b._detonate_frame <= -1:
                b.kill()
                if b in self.player.bombs:
                    self.player.bombs.remove(b)
                continue
            if b._detonate_frame > 0:
                if b.btype != "napalm":
                    b.kill()
                b.detonated = True
                b._detonate_frame = -1
            else:
                continue
            btype = b.btype
            pos = b.pos
            if btype == "flash":
                SFX["explosion"].play()
                for e in list(self.enemies):
                    if e.pos.distance_to(pos) < b.radius:
                        e.stun_timer = max(e.stun_timer, 180)
                for _ in range(30):
                    a2 = random.uniform(0, math.tau)
                    sp2 = random.uniform(2, 8)
                    self.particles.append(Particle(pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2,
                        (255, 255, 255), random.uniform(3, 6), random.randint(10, 25)))
                self.shockwaves.append({"pos":pos,"timer":15,"max_r":b.radius,"color":(255,255,200)})
            elif btype == "napalm":
                SFX["explosion"].play()
                b.pool_life = 240
                b.image = pygame.Surface((1, 1), pygame.SRCALPHA)
                for _ in range(15):
                    a2 = random.uniform(0, math.tau)
                    sp2 = random.uniform(1, 4)
                    self.particles.append(Particle(pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2,
                        (255, 100, 0), random.uniform(3, 5), random.randint(15, 30)))
            elif btype == "cluster":
                SFX["explosion"].play()
                for _i in range(3):
                    a2 = random.uniform(0, math.tau)
                    sp2 = random.uniform(4, 8)
                    sb = Bomb(pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2, "frag", MAP_W, MAP_H)
                    sb.life = 30
                    self.all_sprites.add(sb)
                    self.player.bombs.append(sb)
                for _ in range(20):
                    a2 = random.uniform(0, math.tau)
                    sp2 = random.uniform(2, 6)
                    self.particles.append(Particle(pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2,
                        (255, 80, 200), random.uniform(2, 4), random.randint(8, 18)))
                self.shockwaves.append({"pos":pos,"timer":12,"max_r":b.radius,"color":(255,80,200)})
            elif btype == "mine":
                SFX["explosion"].play()
                for e in list(self.enemies):
                    if e.pos.distance_to(pos) < b.radius:
                        dir2 = (e.pos - pos).normalize() if e.pos.distance_to(pos) > 0.5 else pygame.Vector2(1, 0)
                        died = e.hit(b.damage, dir2 * 20)
                        self.dmg_nums.append(DamageNum(e.pos, str(b.damage), (100, 200, 100)))
                        if died:
                            self._reward_enemy_death(e)
                for _ in range(20):
                    a2 = random.uniform(0, math.tau)
                    sp2 = random.uniform(2, 6)
                    self.particles.append(Particle(pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2,
                        (80, 200, 80), random.uniform(2, 5), random.randint(10, 25)))
            else:
                SFX["explosion"].play()
                for e in list(self.enemies):
                    if e.pos.distance_to(pos) < b.radius:
                        dir2 = (e.pos - pos).normalize() if e.pos.distance_to(pos) > 0.5 else pygame.Vector2(1, 0)
                        died = e.hit(b.damage, dir2 * 15)
                        self.dmg_nums.append(DamageNum(e.pos, str(b.damage), WHITE if b.damage >= 15 else YELLOW))
                        if died:
                            self._reward_enemy_death(e)
                for _ in range(20):
                    a2 = random.uniform(0, math.tau)
                    sp2 = random.uniform(2, 7)
                    self.particles.append(Particle(pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2,
                        b.color, random.uniform(2, 5), random.randint(10, 25)))
                self.shockwaves.append({"pos":pos,"timer":15,"max_r":b.radius,"color":b.color})
            if b in self.player.bombs and b.btype != "napalm":
                self.player.bombs.remove(b)

        # Efectos de auras del jugador por frame (fuego, hielo, escudo)
        for aura in list(self.player.auras):
            if aura == "fire":
                for e in list(self.enemies):
                    if e.pos.distance_to(self.player.pos) < 100 and random.random() < 0.1:
                        e.hp -= 1
                        if e.hp <= 0:
                            self._reward_enemy_death(e)
            elif aura == "ice":
                for e in list(self.enemies):
                    if e.pos.distance_to(self.player.pos) < 80:
                        e.stun_timer = max(e.stun_timer, 5)
            elif aura == "shield":
                self.player.shield = max(self.player.shield, 20)

        # Power-ups flotantes: turbo, escudo, byte magnet, explosivo
        for pu in list(self.powerups):
            if pu.update():
                self.powerups.remove(pu)
                continue
            if self.player.pos.distance_to(pu.pos) < self.player.radius + pu.radius + 4:
                SFX["pickup"].play()
                if pu.ptype == "turbo":
                    self.player.turbo_timer = 480
                elif pu.ptype == "shield":
                    self.player.shield_timer = 480
                    self.player.shield = 30
                    self.player.invulnerable = True
                    self.player.invuln_timer = 480
                elif pu.ptype == "byte_magnet":
                    self.player.byte_multiplier = 2.0
                    self.player.byte_mult_timer = 600
                elif pu.ptype == "explosive":
                    self.player.explosive_timer = 360
                self.powerups.remove(pu)
                for _ in range(8):
                    a = random.uniform(0, math.tau)
                    sp = random.uniform(1, 3)
                    self.particles.append(Particle(pu.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                        pu.colors.get(pu.ptype, (255, 255, 255)), random.uniform(2, 3), random.randint(8, 16)))

        # Pickup lifetime update
        self.pickups.update()

        # Efectos de Domain Expansion por frame (efecto único por personaje)
        if self.player.alive() and self.player.domain_active:
            ppos = self.player.pos
            domain_effect = self.player.domain_effect or DOMAIN_EXPANSION.get(self.player.char_id, {}).get("effect", "")
            for e in list(self.enemies):
                if not e.alive(): continue
                if e.pos.distance_to(ppos) < DOMAIN_RADIUS:
                    if domain_effect == "lluvia":
                        if random.random() < 0.08:
                            dmg = random.randint(12, 18)
                            died = e.hit(dmg)
                            self.dmg_nums.append(DamageNum(e.pos, str(dmg), (100, 200, 255)))
                            for _ in range(5):
                                a = random.uniform(0, math.tau)
                                sp = random.uniform(1, 3)
                                self.particles.append(Particle(e.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                                    (100, 200, 255), random.uniform(1.5, 3), random.randint(5, 12)))
                            e.stun_timer = max(getattr(e, "stun_timer", 0), 10)
                            if died:
                                self._reward_enemy_death(e)
                    elif domain_effect == "congelar":
                        e.frozen = True
                        e.frozen_timer = 120
                        self.player.ability_damage_mult = 4.0
                        if random.random() < 0.04:
                            died = e.hit(20)
                            if died:
                                self._reward_enemy_death(e)
                    elif domain_effect == "rebote":
                        self.player.ability_speed = max(self.player.ability_speed, 1.5)
                        if random.random() < 0.06:
                            died = e.hit(15)
                            e.stun_timer = max(getattr(e, "stun_timer", 0), 15)
                            if died:
                                self._reward_enemy_death(e)
                    elif domain_effect == "admin":
                        self.player.hp = min(self.player.max_hp, self.player.hp + 3)
                        if random.random() < 0.06:
                            e.hp -= int(e.max_hp * 0.10)
                            if e.hp <= 0:
                                self._reward_enemy_death(e)
                    elif domain_effect == "tornado" and hasattr(self.player, "tornado"):
                        if self.player.tornado is None:
                            self.player.tornado = Tornado(self.player.pos, 0, MAP_W, MAP_H)
                        self.player.tornado.pull_radius = 150
                    elif domain_effect == "muro":
                        self.player.hp = min(self.player.max_hp, self.player.hp + 3)
                        if random.random() < 0.04:
                            died = e.hit(20)
                            if died:
                                self._reward_enemy_death(e)
                        if len(self.player.walls) < 3 and random.random() < 0.01:
                            wpos = self.player.pos + pygame.Vector2(random.uniform(-60, 60), random.uniform(-60, 60))
                            self.player.walls.append(Wall(wpos, self.player))
                    elif domain_effect == "bytes":
                        if random.random() < 0.10:
                            self.player.bytes += random.randint(3, 8)
                            for _ in range(3):
                                a2 = random.uniform(0, math.tau)
                                sp2 = random.uniform(1, 3)
                                self.particles.append(Particle(e.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2,
                                    (255, 210, 55), random.uniform(1.5, 3), random.randint(5, 10)))
                        if random.random() < 0.02:
                            died = e.hit(int(e.max_hp * 0.05))
                            if died:
                                self._reward_enemy_death(e)
                    elif domain_effect == "brainrot":
                        if random.random() < 0.03:
                            bm = BrainrotMinion(e.pos, self.player, MAP_W, MAP_H)
                            self.all_sprites.add(bm)
                            self.brainrots.add(bm)
                        if random.random() < 0.05:
                            died = e.hit(10)
                            if died:
                                self._reward_enemy_death(e)
                    elif domain_effect == "billie":
                        if random.random() < 0.02 and (self.player.billie_npc is None or self.player.billie_npc.hp <= 0):
                            bpos = e.pos + pygame.Vector2(random.uniform(-20, 20), random.uniform(-20, 20))
                            self.player.billie_npc = BillieNPC(bpos, MAP_W, MAP_H)
                            self.all_sprites.add(self.player.billie_npc)
                        if e.pos.distance_to(ppos) < DOMAIN_RADIUS:
                            kb = ppos - e.pos
                            if kb.length_squared() > 0.01:
                                kb.scale_to_length(2.0)
                                e.pos += kb
                    elif domain_effect == "python_import":
                        if random.random() < 0.04:
                            dmg = random.randint(40, 70)
                            died = e.hit(dmg)
                            self.dmg_nums.append(DamageNum(e.pos, str(dmg), (100, 200, 255)))
                            for _ in range(10):
                                a2 = random.uniform(0, math.tau)
                                sp2 = random.uniform(2, 5)
                                self.particles.append(Particle(e.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2,
                                    (100, 200, 255), random.uniform(2, 4), random.randint(8, 16)))
                            if died:
                                self._reward_enemy_death(e)
                        if random.random() < 0.005:
                            sn = ImportSnippet(e.pos, MAP_W, MAP_H)
                            self.all_sprites.add(sn)
                            if hasattr(self.player, "active_snippets"):
                                self.player.active_snippets.append(sn)
                    elif domain_effect == "python_compile":
                        if e.pos.distance_to(ppos) < DOMAIN_RADIUS * 0.7 and random.random() < 0.08:
                            died = e.hit(random.randint(60, 100))
                            self.dmg_nums.append(DamageNum(e.pos, "COMPILE", (255, 80, 80)))
                            for _ in range(8):
                                a2 = random.uniform(0, math.tau)
                                sp2 = random.uniform(2, 6)
                                self.particles.append(Particle(e.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2,
                                    (255, 80, 80), random.uniform(2, 5), random.randint(8, 18)))
                            e.stun_timer = max(getattr(e, "stun_timer", 0), 15)
                            if died:
                                self._reward_enemy_death(e)
                    elif domain_effect == "python_debug":
                        self.player.hp = min(self.player.max_hp, self.player.hp + 2)
                        if random.random() < 0.04:
                            died = e.hit(random.randint(20, 40))
                            self.dmg_nums.append(DamageNum(e.pos, "DEBUG", (100, 255, 100)))
                            for _ in range(5):
                                a2 = random.uniform(0, math.tau)
                                sp2 = random.uniform(1, 3)
                                self.particles.append(Particle(e.pos, pygame.Vector2(math.cos(a2), math.sin(a2)) * sp2,
                                    (100, 255, 100), random.uniform(2, 3), random.randint(5, 12)))
                            if died:
                                self._reward_enemy_death(e)
            # Domain ambient particles
            if len(self.particles) < 100 and random.random() < 0.3:
                a = random.uniform(0, math.tau)
                r = random.uniform(0, DOMAIN_RADIUS)
                p = self.player.pos + pygame.Vector2(math.cos(a), math.sin(a)) * r
                # Color del dominio según modo de Vicente (vicente/vicenta)
                if self.player.char_id == "vicente":
                    de_color = self.player.vicente_mode_colors[self.player.vicente_mode]
                else:
                    de_color = DOMAIN_EXPANSION.get(self.player.char_id, {}).get("color", (255, 255, 255))
                self.particles.append(Particle(p, pygame.Vector2(0, 0),
                    de_color, random.uniform(1, 3), random.randint(10, 20), gravity=0, shrink=False))

        # Temporizadores del jugador: turbo, escudo, explosivo, byte mult, rebote, daño, velocidad
        if self.player.turbo_timer > 0:
            self.player.turbo_timer -= 1
        if self.player.shield_timer > 0:
            self.player.shield_timer -= 1
            if self.player.shield_timer <= 0:
                self.player.shield = 0
        if self.player.explosive_timer > 0:
            self.player.explosive_timer -= 1
        if self.player.byte_mult_timer > 0:
            self.player.byte_mult_timer -= 1
            if self.player.byte_mult_timer <= 0:
                self.player.byte_multiplier = 1.0
        if self.player.rebotar_timer > 0:
            self.player.rebotar_timer -= 1
        if self.player.ability_damage_timer > 0:
            self.player.ability_damage_timer -= 1
            if self.player.ability_damage_timer <= 0:
                self.player.ability_damage_mult = 1.0
        if self.player.ability_speed_timer > 0:
            self.player.ability_speed_timer -= 1
            if self.player.ability_speed_timer <= 0:
                self.player.ability_speed = 1.0

        # Colisión jugador vs enemigos: daño, vampiric modifier, indicador de dirección
        col = pygame.sprite.spritecollide(self.player, self.enemies, False)
        if col:
            self.player.take_damage(int(max(e.damage * e.dmg_mult for e in col)))
            self.flash_alpha = 80
            # Vampiric modifier: enemies heal 10% on hit
            if self.wave_modifier == "vampirica":
                for e in col:
                    e.hp = min(e.max_hp, e.hp + int(e.damage * 0.1))
            nearest = min(col, key=lambda e2: self.player.pos.distance_squared_to(e2.pos))
            vec = nearest.pos - self.player.pos
            if vec.length() > 0: vec.normalize_ip()
            self.dmg_dir_x, self.dmg_dir_y = vec.x, vec.y
            self.dmg_dir_alpha = 120

        # Colisión jugador vs pickups: salud, munición
        for p in pygame.sprite.spritecollide(self.player, self.pickups, True):
            if p.type == "health":
                self.player.hp = min(self.player.max_hp, self.player.hp + 35)
            else:
                self.player.reserve = min(self.player.char_data["reserve"] * 2, self.player.reserve + 45)
            SFX["pickup"].play()

        alive = []
        nene = len(self.enemies)
        max_parts = min(MAX_PARTICLES, 120 if nene > 60 else 150)
        for p in self.particles:
            p.update()
            if p.alive: alive.append(p)
        self.particles = alive
        if len(self.particles) > max_parts:
            self.particles = self.particles[-max_parts:]
        self.decals = [d for d in self.decals if d.update()]
        decal_max = 30 if nene > 60 else 40
        if len(self.decals) > decal_max:
            self.decals[:] = self.decals[-decal_max:]
        self.dmg_nums = [d for d in self.dmg_nums if d.update()]
        dmg_max = 40 if nene > 60 else 60
        if len(self.dmg_nums) > dmg_max:
            self.dmg_nums[:] = self.dmg_nums[-dmg_max:]
        self.code_snippets = [s for s in self.code_snippets if s.update()]
        if len(self.code_snippets) > 40:
            self.code_snippets[:] = self.code_snippets[-40:]
        self.notifs = [n for n in self.notifs if n.update() is not False]

        # Animación de muerte de enemigos: escala progresiva y desvanecimiento
        for e in self.dead_enemies[:]:
            e.death_timer -= 1
            t = max(0, e.death_timer / 15)
            if e.death_timer == 5 and len(self.particles) < 180:
                for _ in range(20):
                    a = random.uniform(0, math.tau)
                    sp = random.uniform(2, 7)
                    self.particles.append(Particle(e.pos, pygame.Vector2(math.cos(a), math.sin(a)) * sp,
                        e.color, random.uniform(2, 5), random.randint(10, 22)))
                if e.explode_r > 0:
                    self.shockwaves.append({"pos": pygame.Vector2(e.pos), "timer": 25, "max_r": e.explode_r, "color": (255, 120, 0)})
            if e.death_timer > 0:
                stage = min(4, max(0, int(t * 5)))  # 0..4
                if not hasattr(e, '_death_cache'):
                    e._death_cache = {}
                cached = e._death_cache.get(stage)
                if cached is None:
                    scale = max(0.15, (stage + 1) * 0.2)
                    w = max(1, int(e.radius * 2 * scale))
                    h = max(1, int(e.radius * 2 * scale))
                    cached = pygame.transform.scale(e._death_surf, (w, h))
                    e._death_cache[stage] = cached
                e.image = cached
                e.image.set_alpha(int(t * 255))
                e.rect = e.image.get_rect(center=(int(e.pos.x), int(e.pos.y)))
            else:
                self.dead_enemies.remove(e)
                e.kill()
        if len(self.dead_enemies) > 30:
            for e in self.dead_enemies[:len(self.dead_enemies)-30]:
                e.kill()
            self.dead_enemies[:] = self.dead_enemies[-30:]

        # Actualización de anillos de onda expansiva (shockwave)
        for sw in self.shockwaves[:]:
            sw["timer"] -= 1
            if sw["timer"] <= 0:
                self.shockwaves.remove(sw)
        if len(self.shockwaves) > 20:
            self.shockwaves[:] = self.shockwaves[-20:]

        # Spawn de airdrops durante la oleada (contenedores con botín gacha)
        if self.wave_state in ("spawning", "clear") and len(self.airdrops) < MAX_AIRDROPS and random.random() < AIRDROP_CHANCE_PER_FRAME:
            for _ in range(10):
                ax = random.randint(200, MAP_W - 200)
                ay = random.randint(200, MAP_H - 200)
                col, row = int(ax // TILE), int(ay // TILE)
                if not is_wall(self.grid, col, row):
                    crate = AirdropCrate((ax, ay))
                    self.airdrops.append(crate)
                    break

        # Airdrop update
        for c in self.airdrops[:]:
            c.update()
            if not c.alive():
                self.airdrops.remove(c)

        # Temporizador de la ruleta gacha (animación de giro)
        if self.gacha_spinning:
            self.gacha_timer -= 1
            if self.gacha_timer <= 0:
                self.gacha_spinning = False
                self._apply_gacha_reward()

        # Transfer shake to camera + smooth HP
        if self.player.shake > 0:
            self.cam.add_shake(self.player.shake)
            self.player.shake = 0
        self.player._update_display_hp()

    def draw(self, surf):
        surf.fill(self.map_theme.get("bg", BLACK))
        cx, cy = self.cam.x + self.cam.shake_x, self.cam.y + self.cam.shake_y
        sc = max(0, int(cx // TILE))
        ec = min(COLS, int((cx + WIDTH) // TILE) + 1)
        sr = max(0, int(cy // TILE))
        er = min(ROWS, int((cy + HEIGHT) // TILE) + 1)

        # ── Pre-rendered tile cache (lazy init) ──
        if not hasattr(self, "_tile_cache"):
            self._tile_cache = {}
            self._floor_noise = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            for _ in range(30):
                self._floor_noise.set_at((random.randint(0, TILE - 1), random.randint(0, TILE - 1)), (0, 0, 0, 12))
            self._grid_line = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            pygame.draw.rect(self._grid_line, (0, 18, 3), (0, 0, TILE, TILE), 1)
        def _load_tile(vv):
            ts = pygame.Surface((TILE, TILE))
            if 10 <= vv <= 19:
                color = self.map_theme["floor"].get(vv, (15, 15, 15))
                ts.fill(color)
                ts.blit(self._floor_noise, (0, 0))
                ts.blit(self._grid_line, (0, 0))
            elif (1 <= vv <= 9) or (vv >= 20):
                color = self.map_theme["wall"].get(vv, (10, 35, 10))
                if vv == 9:
                    cy2 = TILE // 2
                    pygame.draw.circle(ts, (5, 35, 8), (cy2, cy2), TILE // 2 - 2)
                    pygame.draw.rect(ts, (40, 25, 10), (cy2 - 2, cy2 + 2, 4, TILE // 2 - 2))
                else:
                    ts.fill(color)
                    hl = (min(color[0]+35,255), min(color[1]+35,255), min(color[2]+35,255))
                    sh = (max(color[0]-40,0), max(color[1]-40,0), max(color[2]-40,0))
                    pygame.draw.line(ts, hl, (0, 0), (TILE-2, 0), 2)
                    pygame.draw.line(ts, hl, (0, 0), (0, TILE-2), 2)
                    pygame.draw.line(ts, sh, (1, TILE-1), (TILE-1, TILE-1), 2)
                    pygame.draw.line(ts, sh, (TILE-1, 1), (TILE-1, TILE-1), 2)
            self._tile_cache[vv] = ts
            return ts

        now_ticks = pygame.time.get_ticks()
        for r in range(sr, er):
            row_obj = self.grid[r]
            for c in range(sc, ec):
                v = row_obj[c]
                px = c * TILE - cx
                py = r * TILE - cy
                if v == 17:
                    color = self.map_theme["floor"].get(17, (15, 15, 15))
                    wave = int(math.sin(now_ticks * 0.003 + r + c) * 6)
                    color = (color[0] + wave, color[1] + wave // 2, color[2] - wave)
                    pygame.draw.rect(surf, color, (px, py, TILE, TILE))
                    surf.blit(self._floor_noise, (px, py))
                    surf.blit(self._grid_line, (px, py))
                elif 10 <= v <= 16 or 18 <= v <= 19:
                    tile_surf = self._tile_cache.get(v)
                    if tile_surf is None:
                        tile_surf = _load_tile(v)
                    surf.blit(tile_surf, (px, py))
                    if 10 <= v <= 15:
                        for dr, dc, side in [(-1,0,"t"),(1,0,"b"),(0,-1,"l"),(0,1,"r")]:
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < ROWS and 0 <= nc < COLS:
                                nv = row_obj[nc] if dr == 0 else self.grid[nr][c]
                                if nv == 16:
                                    if side in ("t", "b"):
                                        pygame.draw.line(surf, (8, 28, 10), (px, py + (0 if side=="t" else TILE-1)), (px+TILE-1, py + (0 if side=="t" else TILE-1)), 2)
                                    else:
                                        pygame.draw.line(surf, (8, 28, 10), (px + (0 if side=="l" else TILE-1), py), (px + (0 if side=="l" else TILE-1), py+TILE-1), 2)
                elif (1 <= v <= 9) or (v >= 20):
                    tile_surf = self._tile_cache.get(v)
                    if tile_surf is None:
                        tile_surf = _load_tile(v)
                    surf.blit(tile_surf, (px, py))

        # ── Light pools from lamp posts ──
        if not hasattr(self, "_light_pool_surf") or self._light_pool_surf.get_width() != WIDTH:
            self._light_pool_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self._light_pool_surf.fill((0, 0, 0, 0))
        for r in range(sr, er):
            row_obj = self.grid[r]
            for c in range(sc, ec):
                v = row_obj[c]
                if v in (23, 34):
                    lx = c * TILE + TILE // 2 - cx
                    ly = r * TILE + TILE // 2 - cy
                    pulse = int(math.sin(now_ticks * 0.004 + r + c) * 10 + 25)
                    pygame.draw.circle(self._light_pool_surf, (255, 220, 100, max(0, pulse)), (lx, ly), TILE * 2)
        surf.blit(self._light_pool_surf, (0, 0))

        # Entity shadows on floor (cached surface)
        if not hasattr(self, "_shadow_surf"):
            self._shadow_surf = pygame.Surface((64, 10), pygame.SRCALPHA)
            pygame.draw.ellipse(self._shadow_surf, (0, 0, 0, 50), self._shadow_surf.get_rect())
        shadow_s = self._shadow_surf
        for s in self.all_sprites:
            if abs(s.rect.centerx - cx) < WIDTH + 60:
                sw = min(s.rect.width, 64)
                sx = s.rect.x - cx + (s.rect.width - sw) // 2
                sy = s.rect.y - cy + s.rect.height - 5
                surf.blit(shadow_s, (sx, sy), (0, 0, sw, 10))
        for e in self.enemies:
            sw = min(e.radius * 2, 64)
            sx = e.pos.x - sw // 2 - cx
            sy = e.pos.y - cy + e.radius - 5
            surf.blit(shadow_s, (sx, sy), (0, 0, sw, 10))

        # Tornado drawing
        if hasattr(self.player, "tornado") and self.player.tornado is not None:
            self.player.tornado.draw(surf, cx, cy)

        for w in self.player.walls:
            w.draw(surf, cx, cy)

        # Laser beam drawing
        for b in self.player.lasers:
            if b.alive():
                b.draw(surf, cx, cy)

        # Ally drawing
        for a in self.aliados:
            if abs(a.pos.x - cx) < WIDTH + 60 and abs(a.pos.y - cy) < HEIGHT + 60:
                surf.blit(a.image, (int(a.pos.x - cx - a.radius), int(a.pos.y - cy - a.radius)))
                a.draw_hp(surf, cx, cy)
                # Name label
                from src.ui import _f
                ns = _f(10).render(a.name, True, a.color)
                ns.set_alpha(180)
                surf.blit(ns, (int(a.pos.x - cx - ns.get_width() // 2), int(a.pos.y - cy - a.radius - 12)))

        for d in self.decals:
            if abs(d.pos.x - cx) < WIDTH + 40 and abs(d.pos.y - cy) < HEIGHT + 40:
                d.draw(surf, cx, cy)
        # Bomb custom drawing (napalm pools, mine indicators)
        for b in self.player.bombs:
            if b.alive():
                b.draw(surf, cx, cy)
        for s in self.all_sprites:
            if abs(s.rect.centerx - cx) < WIDTH + 60 and abs(s.rect.centery - cy) < HEIGHT + 60:
                surf.blit(s.image, (s.rect.x - cx, s.rect.y - cy))
        for e in self.enemies:
            e.draw_hp(surf, cx, cy)
        for m in self.brainrots:
            m.draw_hp(surf, cx, cy)
        if self.player.billie_npc is not None:
            try:
                if self.player.billie_npc.alive():
                    self.player.billie_npc.draw(surf, cx, cy)
            except Exception:
                pass
        for p in self.particles:
            if abs(p.pos.x - cx) < WIDTH + 40 and abs(p.pos.y - cy) < HEIGHT + 40:
                p.draw(surf, cx, cy)
        for n in self.dmg_nums:
            if abs(n.pos.x - cx) < WIDTH + 50 and abs(n.pos.y - cy) < HEIGHT + 50:
                n.draw(surf, cx, cy)
        for s in self.code_snippets:
            if abs(s.pos.x - cx) < WIDTH + 50 and abs(s.pos.y - cy) < HEIGHT + 50:
                s.draw(surf, cx, cy)
        for eb in self.enemy_bullets:
            eb.draw(surf, cx, cy)
        for ab in self.ally_bullets:
            ab.draw(surf, cx, cy)
        for pu in self.powerups:
            pu.draw(surf, cx, cy)
        for h in self.hazards:
            h.draw(surf, cx, cy)
        if self.vicente:
            self.vicente.draw(surf, cx, cy, self.vicente_near)
        if self.oscar:
            self.oscar.draw(surf, cx, cy, self.oscar_near)

        # Airdrop crates
        for c in self.airdrops:
            if abs(c.pos.x - cx) < WIDTH + 60 and abs(c.pos.y - cy) < HEIGHT + 60:
                surf.blit(c.image, (int(c.pos.x - cx - c.radius), int(c.pos.y - cy - c.radius)))
                c.draw_glow(surf, cx, cy, self.player.pos)

        # Shockwave rings (cached per radius)
        if not hasattr(self, "_sw_cache"): self._sw_cache = {}
        for sw in self.shockwaves:
            t = max(0, sw["timer"] / 30)
            r = int(sw.get("max_r", 80) * (1 - t) + 10)
            if r < 2: continue
            px = int(sw["pos"].x - cx); py = int(sw["pos"].y - cy)
            if px + r < 0 or px - r > WIDTH or py + r < 0 or py - r > HEIGHT: continue
            a = int(t * 180)
            key = (r, sw["color"][0], sw["color"][1], sw["color"][2], a)
            cached = self._sw_cache.get(key)
            if cached is None:
                cached = pygame.Surface((r * 2,) * 2, pygame.SRCALPHA)
                pygame.draw.circle(cached, (*sw["color"][:3], a), (r, r), r, max(1, r // 10))
                if len(self._sw_cache) < 100:
                    self._sw_cache[key] = cached
            surf.blit(cached, (px - r, py - r))

        if not hasattr(self, "_waifu_glow"):
            self._waifu_glow = pygame.Surface((50, 50), pygame.SRCALPHA)
            pygame.draw.circle(self._waifu_glow, (255, 80, 200, 40), (25, 25), 25)
        if not hasattr(self, "_decoy_ring_cache"):
            self._decoy_ring_cache = {}
        for dec in self.decoys:
            t = max(0, dec["timer"] / 180)
            alpha = min(255, int(t * 200))
            r = int(dec["radius"])
            px = int(dec["pos"].x - cx)
            py = int(dec["pos"].y - cy)
            ring_key = (r, dec["color"][0], dec["color"][1], dec["color"][2], alpha)
            s = self._decoy_ring_cache.get(ring_key)
            if s is None:
                s = pygame.Surface((r * 2,) * 2, pygame.SRCALPHA)
                pygame.draw.circle(s, (*dec["color"][:3], alpha), (r, r), r, 2)
                if len(self._decoy_ring_cache) < 40:
                    self._decoy_ring_cache[ring_key] = s
            surf.blit(s, (px - r, py - r))
            # Waifu NPC character (glow pre-cached)
            surf.blit(self._waifu_glow, (px - 25, py - 25))
            # Body/dress
            pygame.draw.ellipse(surf, (255, 100, 200), (px - 7, py + 3, 14, 16))
            # Head
            pygame.draw.circle(surf, (255, 220, 220), (px, py - 5), 8)
            # Hair
            pygame.draw.arc(surf, (255, 50, 150), (px - 8, py - 13, 16, 12), math.pi, 2*math.pi, 3)
            # Eyes
            eye_y = py - 6
            pygame.draw.circle(surf, (0, 0, 0), (px - 3, eye_y), 2)
            pygame.draw.circle(surf, (0, 0, 0), (px + 3, eye_y), 2)
            pygame.draw.circle(surf, (255, 255, 255), (px - 2, eye_y - 1), 1)
            pygame.draw.circle(surf, (255, 255, 255), (px + 4, eye_y - 1), 1)
            # Smile
            pygame.draw.arc(surf, (255, 80, 150), (px - 3, py - 4, 6, 5), 0, math.pi, 1)

        # Eder ultimate laser (charged Z) — bounded surface
        if self.player.alive() and getattr(self.player, "ult_laser_active", False):
            bcx = int(self.cam.x); bcy = int(self.cam.y)
            sx = int(self.player.beam_start.x - bcx)
            sy = int(self.player.beam_start.y - bcy)
            ex = int(self.player.beam_end.x - bcx)
            ey = int(self.player.beam_end.y - bcy)
            bw = max(8, self.player.beam_w)
            max_glow = bw * 4
            min_x = max(0, min(sx, ex) - max_glow)
            min_y = max(0, min(sy, ey) - max_glow)
            max_x = min(WIDTH, max(sx, ex) + max_glow)
            max_y = min(HEIGHT, max(sy, ey) + max_glow)
            if max_x > min_x and max_y > min_y:
                bsurf = pygame.Surface((max_x - min_x, max_y - min_y), pygame.SRCALPHA)
                lsx, lsy = sx - min_x, sy - min_y
                lex, ley = ex - min_x, ey - min_y
                for i in range(6, 0, -1):
                    a = 70 - i * 10
                    w = int(bw * (1 + i * 0.35))
                    pygame.draw.line(bsurf, (255, 40, 40, max(0, a)), (lsx, lsy), (lex, ley), w)
                pygame.draw.line(bsurf, (255, 120, 120), (lsx, lsy), (lex, ley), bw)
                pygame.draw.line(bsurf, (255, 255, 200), (lsx, lsy), (lex, ley), max(2, bw // 3))
                surf.blit(bsurf, (min_x, min_y))

        # Character beam visuals (Ian buffer Q) — bounded surface
        elif (hasattr(self.player, "beam_start") and self.player.alive()
            and self.player.ability_active):
            ab = self.player.char_data["ability"]
            if ab == "buffer":
                bcx = int(self.cam.x); bcy = int(self.cam.y)
                sx = int(self.player.beam_start.x - bcx)
                sy = int(self.player.beam_start.y - bcy)
                ex = int(self.player.beam_end.x - bcx)
                ey = int(self.player.beam_end.y - bcy)
                bw = self.player.beam_w
                beam_clr = (255, 80, 180)
                beam_clr2 = (255, 180, 230)
                min_x = max(0, min(sx, ex) - bw * 3)
                min_y = max(0, min(sy, ey) - bw * 3)
                max_x = min(WIDTH, max(sx, ex) + bw * 3)
                max_y = min(HEIGHT, max(sy, ey) + bw * 3)
                if max_x > min_x and max_y > min_y:
                    bsurf = pygame.Surface((max_x - min_x, max_y - min_y), pygame.SRCALPHA)
                    lsx, lsy = sx - min_x, sy - min_y
                    lex, ley = ex - min_x, ey - min_y
                    for i in range(5, 0, -1):
                        a = 50 - i * 8
                        w = int(bw * (1 + i * 0.4))
                        pygame.draw.line(bsurf, (*beam_clr, max(0, a)), (lsx, lsy), (lex, ley), w)
                    pygame.draw.line(bsurf, beam_clr2, (lsx, lsy), (lex, ley), bw)
                    pygame.draw.line(bsurf, (255, 255, 255), (lsx, lsy), (lex, ley), max(1, bw // 4))
                    surf.blit(bsurf, (min_x, min_y))
        # Ian pink aura — bounded surface
        if (self.player.alive() and self.player.ability_active
            and self.player.char_data["ability"] == "buffer" and self.player.ian_phase == 1):
            bcx = int(self.cam.x); bcy = int(self.cam.y)
            px = int(self.player.pos.x - bcx); py = int(self.player.pos.y - bcy)
            pulse = int(math.sin(pygame.time.get_ticks() * 0.01) * 15 + 50)
            r = 125
            min_x = max(0, px - r); min_y = max(0, py - r)
            max_x = min(WIDTH, px + r); max_y = min(HEIGHT, py + r)
            if max_x > min_x and max_y > min_y:
                asurf = pygame.Surface((max_x - min_x, max_y - min_y), pygame.SRCALPHA)
                apx, apy = px - min_x, py - min_y
                pygame.draw.circle(asurf, (255, 80, 180, pulse), (apx, apy), 120, 3)
                pygame.draw.circle(asurf, (255, 80, 180, pulse // 2), (apx, apy), 120)
                surf.blit(asurf, (min_x, min_y))

        if self.transition_alpha > 0:
            self.transition_alpha = max(0, self.transition_alpha - 8)
            o = pygame.Surface((WIDTH, HEIGHT))
            o.set_alpha(min(200, self.transition_alpha))
            o.fill(GREEN)
            surf.blit(o, (0, 0))

        if self.flash_alpha > 0:
            self.flash_alpha = max(0, self.flash_alpha - 5)
            o = pygame.Surface((WIDTH, HEIGHT))
            o.set_alpha(self.flash_alpha)
            o.fill((255, 50, 50))
            surf.blit(o, (0, 0))

        if self.gold_flash_alpha > 0:
            self.gold_flash_alpha = max(0, self.gold_flash_alpha - 5)
            o = pygame.Surface((WIDTH, HEIGHT))
            o.set_alpha(self.gold_flash_alpha)
            o.fill(GOLD)
            surf.blit(o, (0, 0))

        # Directional damage indicator
        if self.dmg_dir_alpha > 0:
            self.dmg_dir_alpha = max(0, self.dmg_dir_alpha - 3)
            o = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            a = int(self.dmg_dir_alpha)
            ang = math.atan2(self.dmg_dir_y, self.dmg_dir_x)
            ca, sa = math.cos(ang), math.sin(ang)
            if abs(ca) > abs(sa):
                if ca > 0:
                    pygame.draw.rect(o, (255, 0, 0, a), (WIDTH - 16, 0, 16, HEIGHT))
                else:
                    pygame.draw.rect(o, (255, 0, 0, a), (0, 0, 16, HEIGHT))
            elif sa > 0:
                pygame.draw.rect(o, (255, 0, 0, a), (0, HEIGHT - 16, WIDTH, 16))
            else:
                pygame.draw.rect(o, (255, 0, 0, a), (0, 0, WIDTH, 16))
            surf.blit(o, (0, 0))

        # Zone label
        if self.zone_name and self.zone_timer > 0:
            from src.ui import _f
            zs = _f(18).render(self.zone_name, True, (0, 180, 50))
            zs.set_alpha(min(255, int(255 * self.zone_timer / 180)))
            surf.blit(zs, (WIDTH // 2 - zs.get_width() // 2, HEIGHT - 55))
            self.zone_timer -= 1

        # Power-up tooltips
        for pu in self.powerups:
            if self.player.pos.distance_to(pu.pos) < 80:
                tip_text = {"turbo":"Fire rate x2","shield":"Escudo 30s","byte_magnet":"Bytes x2 10s","explosive":"Balas explosivas 6s"}
                tip = tip_text.get(pu.ptype, "")
                if tip and not self.shop_open:
                    px = int(pu.pos.x - self.cam.x)
                    py = int(pu.pos.y - self.cam.y) - 20
                    ts = pygame.font.Font(None, 12).render(tip, True, (100, 255, 100))
                    ts.set_alpha(200)
                    surf.blit(ts, (px - ts.get_width() // 2, py))

        # ── Domain Expansion barrier (JJK style) ──
        if self.player.alive() and self.player.domain_active:
            de = DOMAIN_EXPANSION.get(self.player.char_id, {})
            de_color = de.get("color", (255, 255, 255))
            dom_name = de.get("name", "DOMINIO")
            px = int(self.player.pos.x - cx); py = int(self.player.pos.y - cy)
            now = pygame.time.get_ticks()

            # Pre-render static barrier wall once per color
            bsz = DOMAIN_RADIUS * 2 + 60
            bh = bsz // 2
            cache_key = de_color
            if not hasattr(self, "_domain_cache") or self._domain_cache.get("key") != cache_key:
                ds = pygame.Surface((bsz, bsz), pygame.SRCALPHA)
                # Dark/tinted overlay
                pygame.draw.circle(ds, (*de_color[:3], 25), (bh, bh), DOMAIN_RADIUS)
                pygame.draw.circle(ds, (0, 0, 0, 50), (bh, bh), DOMAIN_RADIUS)
                # Barrier outer thick ring
                pygame.draw.circle(ds, (*de_color[:3], 50), (bh, bh), DOMAIN_RADIUS, 14)
                pygame.draw.circle(ds, (*de_color[:3], 30), (bh, bh), DOMAIN_RADIUS + 8, 2)
                pygame.draw.circle(ds, (*de_color[:3], 18), (bh, bh), DOMAIN_RADIUS - 12, 1)
                # Inner glow rings
                for i in range(3):
                    r = DOMAIN_RADIUS - 30 - i * 25
                    if r > 0:
                        pygame.draw.circle(ds, (*de_color[:3], max(4, 12 - i * 4)), (bh, bh), r, 1)
                # Radial lines (like JJK inner markings)
                for i in range(16):
                    a = i * (2 * math.pi / 16)
                    sx = bh + int(math.cos(a) * 25)
                    sy = bh + int(math.sin(a) * 25)
                    ex = bh + int(math.cos(a) * (DOMAIN_RADIUS - 18))
                    ey = bh + int(math.sin(a) * (DOMAIN_RADIUS - 18))
                    pygame.draw.line(ds, (*de_color[:3], 12), (sx, sy), (ex, ey), 1)
                # Runes (static symbols on barrier edge)
                rune_chars = "✦✧⬡⬢◈◇◎●◆◉○◌◍◎◉"
                for i in range(10):
                    a = i * (2 * math.pi / 10) + 0.3
                    rx = bh + int(math.cos(a) * (DOMAIN_RADIUS - 8))
                    ry = bh + int(math.sin(a) * (DOMAIN_RADIUS - 8))
                    rf = pygame.font.Font(None, 14)
                    r_char = rune_chars[i % len(rune_chars)]
                    rs = rf.render(r_char, True, (*de_color[:3], 100))
                    ds.blit(rs, (rx - rs.get_width() // 2, ry - rs.get_height() // 2))
                self._domain_cache = {"surface": ds, "key": cache_key}

            # Clip domain to screen
            min_dx = max(0, px - bh); max_dx = min(WIDTH, px + bh)
            min_dy = max(0, py - bh); max_dy = min(HEIGHT, py + bh)
            if max_dx > min_dx and max_dy > min_dy:
                src_x = min_dx - (px - bh); src_y = min_dy - (py - bh)
                src_w = max_dx - min_dx; src_h = max_dy - min_dy
                surf.blit(self._domain_cache["surface"], (min_dx, min_dy), (src_x, src_y, src_w, src_h))

            # Animated pulse ring (bounded)
            pulse_r = int(math.sin(now * 0.005) * 6 + DOMAIN_RADIUS)
            ring_sz = (pulse_r + 20) * 2
            min_rx = max(0, px - ring_sz // 2); max_rx = min(WIDTH, px + ring_sz // 2)
            min_ry = max(0, py - ring_sz // 2); max_ry = min(HEIGHT, py + ring_sz // 2)
            if max_rx > min_rx and max_ry > min_ry:
                rs = pygame.Surface((ring_sz, ring_sz), pygame.SRCALPHA)
                rh = ring_sz // 2
                pygame.draw.circle(rs, (*de_color[:3], 55), (rh, rh), pulse_r, 3)
                pygame.draw.circle(rs, (*de_color[:3], 25), (rh, rh), pulse_r + 5, 1)
                surf.blit(rs, (px - rh, py - rh), (min_rx - (px - rh), min_ry - (py - rh), max_rx - min_rx, max_ry - min_ry))

            # Orbiting runes (animated)
            orbiting = getattr(self, "_domain_orbiting", [])
            if not orbiting:
                self._domain_orbiting = orbiting = [
                    {"a": i * (2 * math.pi / 8), "speed": 0.008 + 0.003 * (i % 3 - 1)}
                    for i in range(8)
                ]
            for orb in orbiting:
                orb["a"] += orb["speed"]
                ox = px + int(math.cos(orb["a"]) * (DOMAIN_RADIUS - 6))
                oy = py + int(math.sin(orb["a"]) * (DOMAIN_RADIUS - 6))
                if 0 <= ox < WIDTH and 0 <= oy < HEIGHT:
                    pygame.draw.circle(surf, (*de_color[:3], 80), (ox, oy), 3)
                    pygame.draw.circle(surf, (*de_color[:3], 30), (ox, oy), 5, 1)

            # Domain name with glow
            name_surf = pygame.font.Font(None, 30).render(f"DOMINIO: {dom_name}", True, (*de_color[:3], 255))
            nr = name_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 120))
            # Glow behind name
            for i in range(4, 0, -1):
                gs = pygame.Surface((nr.width + i * 12, nr.height + i * 6), pygame.SRCALPHA)
                pygame.draw.rect(gs, (*de_color[:3], 15 - i * 2), gs.get_rect(), border_radius=4)
                surf.blit(gs, (nr.x - i * 6, nr.y - i * 3))
            pygame.draw.rect(surf, (0, 0, 0, 120), nr.inflate(12, 6), border_radius=4)
            name_surf.set_alpha(200)
            surf.blit(name_surf, nr)

            # Python code for Vicente domain
            if de.get("effect") == "python":
                code_text = random.choice(["import this", "print('hello')", "while True:", "for x in y:", "class Vicente:", "self.lealtad()", "def dominio():"])
                code_surf = pygame.font.Font(None, 22).render(code_text, True, (150, 200, 255))
                code_surf.set_alpha(100)
                surf.blit(code_surf, (px - code_surf.get_width() // 2, py - code_surf.get_height() // 2))
                for e in list(self.enemies):
                    if e.pos.distance_to(self.player.pos) < DOMAIN_RADIUS and random.random() < 0.05:
                        ex = int(e.pos.x - cx); ey = int(e.pos.y - cy)
                        for j in range(5):
                            lx = px + (ex - px) * j / 5 + random.randint(-10, 10)
                            ly = py + (ey - py) * j / 5 + random.randint(-10, 10)
                            pygame.draw.circle(surf, (150, 200, 255, 150), (int(lx), int(ly)), 3)

        # ── Lighting system (half-res for performance) ──
        if self.state == "play" and self.player.alive():
            hw, hh = WIDTH // 2, HEIGHT // 2
            if not hasattr(self, "_fl_dark") or self._fl_dark.get_width() != hw:
                self._fl_dark = pygame.Surface((hw, hh), pygame.SRCALPHA)
                self._fl_cut = pygame.Surface((hw, hh), pygame.SRCALPHA)
            self._fl_dark.fill((0, 0, 0, FOG_NEAR_ALPHA))
            self._fl_cut.fill((0, 0, 0, 0))
            a = self.player.angle; cx2 = hw // 2; cy2 = hh // 2
            for dist, rad, alpha in [(135, 105, 255), (100, 90, 240), (70, 75, 220),
                                     (40, 60, 210), (15, 45, 200)]:
                lx = cx2 + int(math.cos(a) * dist)
                ly = cy2 + int(math.sin(a) * dist)
                pygame.draw.circle(self._fl_cut, (0, 0, 0, alpha), (lx, ly), rad)
            pygame.draw.circle(self._fl_cut, (0, 0, 0, 220), (cx2, cy2), 48)
            pygame.draw.circle(self._fl_cut, (0, 0, 0, 140), (cx2, cy2), 85)
            self._fl_dark.blit(self._fl_cut, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
            scaled = pygame.transform.smoothscale(self._fl_dark, (WIDTH, HEIGHT))
            surf.blit(scaled, (0, 0))

        # Light flash from shooting (half-res)
        if self.player.alive() and self.player.light_flash_timer > 0:
            hw, hh = WIDTH // 2, HEIGHT // 2
            if not hasattr(self, "_flash_surf") or self._flash_surf.get_width() != hw:
                self._flash_surf = pygame.Surface((hw, hh), pygame.SRCALPHA)
            self._flash_surf.fill((0, 0, 0, 0))
            fa = int(50 * self.player.light_flash_timer / LIGHT_FLASH_DURATION)
            pygame.draw.circle(self._flash_surf, (255, 255, 200, fa), (hw // 2, hh // 2), 50)
            scaled = pygame.transform.smoothscale(self._flash_surf, (WIDTH, HEIGHT))
            surf.blit(scaled, (0, 0))

        # Scanlines during gameplay (cached fullscreen)
        if not hasattr(self, "_scanline_surf") or self._scanline_surf.get_width() != WIDTH:
            self._scanline_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            for y in range(0, HEIGHT, 4):
                self._scanline_surf.fill((0, 255, 65, 18), (0, y, WIDTH, 2))
        surf.blit(self._scanline_surf, (0, 0))

        # CRT vignette
        if not hasattr(self, "_vignette_surf") or self._vignette_surf.get_width() != WIDTH:
            self._vignette_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            for i in range(6, 0, -1):
                r = int(math.hypot(WIDTH, HEIGHT) * 0.25 + i * 35)
                s = pygame.Surface((r * 2,) * 2, pygame.SRCALPHA)
                a = 8 + i * 6
                pygame.draw.circle(s, (0, 0, 0, min(60, a)), (r, r), r)
                self._vignette_surf.blit(s, (WIDTH // 2 - r, HEIGHT // 2 - r))
        surf.blit(self._vignette_surf, (0, 0))

        # Red border when HP < 25% (cached per pulse)
        if self.player.alive() and self.player.hp < self.player.max_hp * 0.25:
            pulse = int(math.sin(pygame.time.get_ticks() * 0.008) * 20 + 35)
            if not hasattr(self, "_lowhp_surf") or self._lowhp_a != pulse:
                self._lowhp_a = pulse
                self._lowhp_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                pygame.draw.rect(self._lowhp_surf, (255, 0, 0, pulse), (0, 0, WIDTH, 8))
                pygame.draw.rect(self._lowhp_surf, (255, 0, 0, pulse), (0, HEIGHT - 8, WIDTH, 8))
                pygame.draw.rect(self._lowhp_surf, (255, 0, 0, pulse), (0, 0, 8, HEIGHT))
                pygame.draw.rect(self._lowhp_surf, (255, 0, 0, pulse), (WIDTH - 8, 0, 8, HEIGHT))
            surf.blit(self._lowhp_surf, (0, 0))

        # Gacha roulette overlay
        if self.gacha_open:
            from src.ui import draw_gacha
            draw_gacha(surf, self)

        if self.state == "over":
            if not hasattr(self, "_overlay_surf"):
                self._overlay_surf = pygame.Surface((WIDTH, HEIGHT))
            oa = max(0, min(190, (600 - self.wave_announce) / 3))
            if oa != getattr(self, "_overlay_alpha", -1):
                self._overlay_alpha = oa
                self._overlay_surf.set_alpha(oa)
                self._overlay_surf.fill((40, 0, 0))
            surf.blit(self._overlay_surf, (0, 0))
