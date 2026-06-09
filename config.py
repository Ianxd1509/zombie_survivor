# Configuración global del juego: define constantes de pantalla, colores,
# personajes, armas, objetos, mapas, y parámetros de gameplay.
import pygame

pygame.init()
pygame.mixer.init(frequency=22050, size=-16, channels=2)

WIDTH, HEIGHT = 1280, 720
FONT_SCALE = HEIGHT / 600  # ~1.2 for 720p
FPS = 60
MAP_W, MAP_H = 5120, 5120

BLACK = (0, 0, 0)
WHITE = (220, 230, 220)
RED = (255, 50, 50)
GREEN = (0, 255, 65)
BLUE = (50, 150, 255)
YELLOW = (255, 210, 55)
ORANGE = (255, 140, 50)
PURPLE = (180, 50, 255)
GOLD = (255, 200, 50)
GRAY = (100, 120, 100)
SEL = (180, 150, 55)  # Muted gold for selection highlights

CHARACTERS = {
    "irvin": {"name":"Irvin","desc":"Bucle For - Limpieza","color":(0,200,255),"hp":120,"max_hp":120,"stamina":100,"speed":3.0,"ability":"aplastar","cd":25000,"dmg":12,"fr":140,"mag":35,"shots":2,"reserve":200,"reload":800,"spr":0.04,"passive":"piercing+1"},
    "sebas": {"name":"Sebas","desc":"Rebota - Area","color":(255,100,100),"hp":100,"max_hp":100,"stamina":80,"speed":3.5,"ability":"rebotar","cd":25000,"dmg":20,"fr":200,"mag":20,"shots":1,"reserve":150,"reload":1400,"spr":0.02,"passive":"bounce+1"},
    "leo": {"name":"Leo","desc":"Scraper - Bytes+","color":(255,210,55),"hp":90,"max_hp":90,"stamina":120,"speed":3.2,"ability":"robar","cd":24000,"dmg":10,"fr":170,"mag":30,"shots":1,"reserve":250,"reload":1000,"spr":0.05,"passive":"speed+0.05"},
    "diego": {"name":"Diego","desc":"Brainrot - Chochox","color":(180,50,255),"hp":110,"max_hp":110,"stamina":90,"speed":2.8,"ability":"brainrot","cd":25000,"dmg":15,"fr":180,"mag":25,"shots":1,"reserve":180,"reload":1200,"spr":0.03,"passive":"vampire+1"},
    "usiel": {"name":"Uziel","desc":"Admin Recursos - Regen","color":(255,200,50),"hp":150,"max_hp":150,"stamina":140,"speed":2.8,"ability":"bolillo","cd":30000,"dmg":10,"fr":160,"mag":30,"shots":1,"reserve":250,"reload":1000,"spr":0.04,"passive":"lifesteal+0.03"},
    "obed": {"name":"Obed","desc":"Billie Eilish - Concierto","color":(255,80,200),"hp":90,"max_hp":90,"stamina":100,"speed":3.4,"ability":"billie","cd":40000,"dmg":14,"fr":150,"mag":25,"shots":1,"reserve":200,"reload":900,"spr":0.03,"passive":"dmg+2"},
    "eder": {"name":"Eder","desc":"Guitarra Eléctrica - Riff","color":(200,80,255),"hp":100,"max_hp":100,"stamina":90,"speed":3.0,"ability":"guitar_riff","cd":25000,"dmg":18,"fr":180,"mag":25,"shots":1,"reserve":180,"reload":1200,"spr":0.03,"passive":"firerate"},
    "ian": {"name":"Ian","desc":"Sobrecarga Buffer - Vacío","color":(255,80,180),"hp":100,"max_hp":100,"stamina":100,"speed":3.0,"ability":"buffer","cd":28000,"dmg":15,"fr":160,"mag":30,"shots":1,"reserve":250,"reload":1000,"spr":0.03,"passive":"reload*0.9"},
    "randy": {"name":"Randy","desc":"Firewall Humano - Muro","color":(80,180,255),"hp":180,"max_hp":180,"stamina":80,"speed":2.5,"ability":"muro","cd":35000,"dmg":10,"fr":200,"mag":20,"shots":1,"reserve":200,"reload":1500,"spr":0.03,"passive":"hp+20"},
    "vicente": {"name":"Vicente","desc":"Legado Python - Desbloqueado","color":(100,200,255),"hp":300,"max_hp":300,"stamina":150,"speed":5.0,"ability":"import_snippet","cd":12000,"dmg":35,"fr":60,"mag":70,"shots":3,"reserve":400,"reload":450,"spr":0.01,"passive":"bytes+30"},
}

# Domain Expansion settings
ULT_CHARGE_MAX = 40
ULT_LASER_DURATION = 120
MIN_ULT_CHARGE = 8

DOMAIN_DURATION = 900  # frames (15s)
DOMAIN_RADIUS = 400
DOMAIN_COOLDOWN = 2700  # frames (45s)
DOMAIN_CHARGE_KILLS = 40

MAPS = [
    {"name":"CBTIS 222","desc":"Edificios, calles y jardin botanico","color":(50,150,255)},
    {"name":"Bosque","desc":"Arboles, rio y claros en la naturaleza","color":(50,200,50)},
    {"name":"Playa","desc":"Arena, mar, palmeras y muelle tropical","color":(255,200,50)},
]

DOMAIN_EXPANSION = {
    "irvin":  {"name":"Ciclo For",   "color":(0,200,255), "effect":"lluvia"},
    "sebas":  {"name":"Lluvia de Meteoros",   "color":(255,100,100), "effect":"rebote"},
    "leo":    {"name":"Desbordamiento de Bytes","color":(255,210,55), "effect":"bytes"},
    "diego":  {"name":"Cerebro Colectivo",    "color":(180,50,255), "effect":"brainrot"},
    "usiel":  {"name":"Administrador Total",  "color":(255,200,50), "effect":"admin"},
    "obed":   {"name":"Escenario de Billie",  "color":(255,80,200), "effect":"billie"},
    "eder":   {"name":"Solo del Apocalipsis", "color":(200,80,255), "effect":"guitar_wave"},
    "ian":    {"name":"Deadlock",             "color":(255,80,180), "effect":"congelar"},
    "randy":  {"name":"Fortaleza Firewall",   "color":(80,180,255), "effect":"muro"},
    "vicente":{"name":"LEALTAD A PYTHON",     "color":(100,200,255), "effect":"python"},
}

# Lighting settings
PLAYER_LIGHT_RADIUS = 250
FOG_NEAR_ALPHA = 170
FOG_FAR_ALPHA = 120
LIGHT_FLASH_DURATION = 8

SHOP_ITEMS = [
    {"name":"Fire Rate","desc":"+10% cadencia","cost":100,"base_cost":100,"id":"firerate","max":10},
    {"name":"Daño +","desc":"+3 daño","cost":80,"base_cost":80,"id":"dmg","max":15},
    {"name":"Vida +","desc":"+20 vida max","cost":120,"base_cost":120,"id":"hp","max":8},
    {"name":"Multi-balas","desc":"+1 bala","cost":150,"base_cost":150,"id":"multishot","max":4},
    {"name":"Velocidad","desc":"+10% mov","cost":90,"base_cost":90,"id":"speed","max":8},
    {"name":"Cargador","desc":"+5 balas","cost":60,"base_cost":60,"id":"mag","max":12},
    {"name":"Recarga","desc":"-15% recarga","cost":110,"base_cost":110,"id":"reload","max":8},
    {"name":"Perforar","desc":"Balas penetrantes","cost":200,"base_cost":200,"id":"piercing","max":5},
    {"name":"Vampirismo","desc":"+5% robo de vida","cost":180,"base_cost":180,"id":"lifesteal","max":8},
    {"name":"Impacto","desc":"+20% retroceso","cost":100,"base_cost":100,"id":"knockback","max":5},
    {"name":"Municion","desc":"+50 balas de reserva","cost":80,"base_cost":80,"id":"ammo","max":10},
]

CODE_BULLETS = [
    ("print('hello')", 8),   ("import pygame", 6),    ("x += 1", 4),
    ("self.hp -= dmg", 12),  ("while True:", 16),     ("for i in range(10):", 10),
    ("return None", 5),      ("def update():", 9),     ("class Player:", 14),
    ("if __name__:", 7),     ("break", 6),             ("continue", 6),
    ("raise Error", 18),     ("yield x", 10),          ("map(lambda x:x)", 8),
    ("filter(None, lst)", 7),("sorted(arr)", 5),       ("any(iterable)", 6),
    ("all(predicate)", 6),   ("sum(values)", 5),       ("with open(f):", 8),
    ("del items[i]", 10),    ("global var", 4),        ("assert cond", 12),
    ("pass", 3),             ("[x for x in y]", 9),    ("{k:v for k,v}", 11),
    ("len(arr)", 4),         ("range(100)", 5),        ("enumerate(lst)", 7),
    ("zip(a,b)", 5),         ("reversed(l)", 5),       ("dict.keys()", 6),
    ("list.append(x)", 7),   ("str.join(lst)", 6),    ("int(val)", 5),
    ("float(x)", 5),         ("bool(val)", 5),         ("type(obj)", 6),
]

WEAPON_BULLETS = {
    "auto": {
        "color": (0, 200, 255),
        "name": "Auto",
        "shots": 1,
        "spread": 0.04,
        "dmg_mult": 1.0,
        "fr_mult": 2.5,
        "bullets": CODE_BULLETS,
    },
    "shotgun": {
        "color": (255, 80, 80),
        "name": "Shotgun",
        "shots": 5,
        "spread": 0.35,
        "dmg_mult": 0.9,
        "fr_mult": 3.5,
        "bullets": [
            ("boom()", 10), ("bang()", 8), ("pow()", 6),
            ("blast(r)", 15), ("shotgun()", 12), ("spread()", 7),
            ("pellet()", 5), ("shrapnel()", 9), ("explode()", 14),
        ],
    },
    "sniper": {
        "color": (255, 255, 80),
        "name": "Sniper",
        "shots": 1,
        "spread": 0.0,
        "dmg_mult": 5.0,
        "fr_mult": 10.0,
        "bullets": [
            ("precision()", 22), ("critical()", 28), ("headshot()", 25),
            ("snipe()", 18), ("oneshot()", 30), ("focus()", 20),
        ],
    },
    "pierce": {
        "color": (130, 255, 130),
        "name": "Pierce",
        "shots": 1,
        "spread": 0.02,
        "dmg_mult": 1.2,
        "fr_mult": 3.0,
        "bullets": [
            ("pierce()", 14), ("penetrate()", 16), ("through()", 12),
            ("break()", 10), ("piercing()", 11), ("drill()", 15),
        ],
    },
}

CODE_SNIPPETS = [
    "def foo():", "import os", "print('hi')", "class Foo:", "return True",
    "lambda x: x", "for i in x:", "while True:", "try/except", "if __name__",
    "yield val", "map(f, xs)", "filter(None, x)", "zip(a, b)", "enumerate(x)",
    "sorted(x)", "reversed(x)", "any(x)", "all(x)", "sum(x)",
    "self.attr", "super().__init__", "@decorator", "raise Error", "assert x",
    "break", "continue", "pass", "del x", "global x",
    "with open():", "async def", "await resp", "@staticmethod",
]

POWERUP_TYPES = ["turbo", "shield", "byte_magnet", "explosive"]
WAVE_MODIFIERS = ["normal", "normal", "horda", "vampirica", "elite", "toxica", "veloz", "blindaje", "explosivo"]
SAVE_FILE = "save_data.json"

# Character evolution: items needed to evolve each character
CHAOS_ITEMS = ["🖥️", "💿", "🔌", "📡", "⚡", "🧠", "🔥", "💎"]
EVOLUTION_ITEMS = {
    "irvin": ["Telefono", "Memoria USB", "Cable USB-C"],
    "sebas": ["Zapatos", "Banda Muscular", "Reloj GPS"],
    "leo": ["Botella Agua", "Termo", "Sobre Hidratacion"],
    "diego": ["Audifonos", "Microfono", "Cancion MP3"],
    "usiel": ["Libreta", "Pluma", "Folder Manila"],
    "obed": ["Lentes Sol", "Gorra", "Collar"],
    "eder": ["Pelota", "Red", "Silbato"],
    "ian": ["Laptop", "Mouse", "Cargador"],
    "randy": ["Chamarra", "Mochila", "Termo Metal"],
}
EVOLUTION_ITEM_EMOJIS = {
    "Telefono": "📱", "Memoria USB": "💾", "Cable USB-C": "🔌",
    "Zapatos": "👟", "Banda Muscular": "💪", "Reloj GPS": "⌚",
    "Botella Agua": "🧴", "Termo": "🫗", "Sobre Hidratacion": "💧",
    "Audifonos": "🎧", "Microfono": "🎤", "Cancion MP3": "🎵",
    "Libreta": "📓", "Pluma": "🖊️", "Folder Manila": "📁",
    "Lentes Sol": "🕶️", "Gorra": "🧢", "Collar": "📿",
    "Pelota": "⚽", "Red": "🥅", "Silbato": "🔊",
    "Laptop": "💻", "Mouse": "🖱️", "Cargador": "🔋",
    "Chamarra": "🧥", "Mochila": "🎒", "Termo Metal": "🫗",
}

# Airdrop settings
AIRDROP_CHANCE_PER_FRAME = 0.001  # ~1/1000 per frame during wave
MAX_AIRDROPS = 2  # max active crates on map
AIRDROP_FALL_SPEED = 2
AIRDROP_OPEN_RADIUS = 40  # how close player must be to open

# Gacha loot table: (name, type, weight)
# type: "bytes", "buff", "evo_item"
GACHA_LOOT = [
    ("Bytes +50", "bytes", 50),
    ("Bytes +100", "bytes", 20),
    ("Bytes +200", "bytes", 10),
    ("Turbo 5s", "buff_turbo", 20),
    ("Escudo 5s", "buff_shield", 15),
    ("Doble Daño 8s", "buff_dmg", 10),
    ("Velocidad +20% 8s", "buff_speed", 12),
    ("Item Evolucion", "evo_item", 15),
    ("Chaos Item", "chaos", 3),
]

# Oscar shop items
OSCAR_ITEMS = [
    # Buffs temporales
    {"name":"Turbo 8s",  "desc":"Cadencia x2 por 8s",  "cost":300,  "type":"buff_turbo"},
    {"name":"Escudo 8s", "desc":"Escudo + inmune 8s", "cost":350,  "type":"buff_shield"},
    {"name":"Doble Dano 8s","desc":"+100% dmg 8s",     "cost":400,  "type":"buff_dmg"},
    {"name":"Velocidad 8s","desc":"+30% vel 8s",       "cost":200,  "type":"buff_speed"},
    # Aliados
    {"name":"Aliado: Hna Irving","desc":"Hermana de Irving - Ataca a distancia", "cost":1000, "type":"ally_irvin"},
    {"name":"Aliado: Zaid","desc":"Zaid - Tanque cuerpo a cuerpo", "cost":1500, "type":"ally_zaid"},
    {"name":"Aliado: Hna Uziel","desc":"Hermana de Uziel - Curacion", "cost":1200, "type":"ally_usiel"},
    # Bombas
    {"name":"Bomba Frag","desc":"Explosion estandar 120px", "cost":500, "type":"bomb_frag"},
    {"name":"Bomba Cluster","desc":"Se divide en 3 submuniciones", "cost":800, "type":"bomb_cluster"},
    {"name":"Bomba Sticky","desc":"Se pega al enemigo, alto dano", "cost":700, "type":"bomb_sticky"},
    {"name":"Mina terrestre","desc":"Explota al pisarla", "cost":600, "type":"bomb_mine"},
    {"name":"Bomba Napalm","desc":"Charco de fuego 4s", "cost":750, "type":"bomb_napalm"},
    {"name":"Bomba Flash","desc":"Ciega enemigos 3s, sin dano", "cost":400, "type":"bomb_flash"},
    {"name":"Bomba Rebotadora","desc":"Rebota 3 veces en paredes", "cost":650, "type":"bomb_bouncing"},
    # Permanentes
    {"name":"Vida +10","desc":"+10 HP max permanente", "cost":800, "type":"perm_hp"},
    {"name":"Velocidad +5%","desc":"+5% velocidad permanente", "cost":600, "type":"perm_speed"},
    {"name":"Dano +3","desc":"+3 dano permanente", "cost":700, "type":"perm_dmg"},
    {"name":"Cadencia +10%","desc":"+10% cadencia permanente", "cost":650, "type":"perm_firerate"},
    # Auras
    {"name":"Aura de Fuego","desc":"5 dmg/s a enemigos <=100px", "cost":1000, "type":"aura_fire"},
    {"name":"Aura de Hielo","desc":"Ralentiza enemigos <=80px", "cost":800, "type":"aura_ice"},
    {"name":"Aura de Escudo","desc":"-20% dano recibido", "cost":1200, "type":"aura_shield"},
    # Fragmento evolucion
    {"name":"Fragmento Evo","desc":"1 item de evolucion aleatorio", "cost":2000, "type":"evo_fragment"},
    # Items unicos por personaje
    {"name":"Overflow (Irvin)","desc":"+50% cargador", "cost":1500, "type":"unique_irvin"},
    {"name":"Rebote Infinito (Sebas)","desc":"Rebotes por 1 wave", "cost":1500, "type":"unique_sebas"},
    {"name":"Miner (Leo)","desc":"+2 bytes por kill", "cost":1500, "type":"unique_leo"},
    {"name":"Plaga (Diego)","desc":"Brainrot al matar enemigo", "cost":1500, "type":"unique_diego"},
    {"name":"Admin Persistente (Uziel)","desc":"-10% CD habilidades", "cost":1500, "type":"unique_usiel"},
    {"name":"Fan (Obed)","desc":"Billie dura el doble", "cost":1500, "type":"unique_obed"},
    {"name":"Amplificador Marshall","desc":"+50% daño Riff Eléctrico", "cost":1500, "type":"unique_eder"},
    {"name":"Overflow Buffer (Ian)","desc":"Buffer +50% carga", "cost":1500, "type":"unique_ian"},
    {"name":"Muro Reforzado (Randy)","desc":"x2 HP del muro", "cost":1500, "type":"unique_randy"},
]

# Ally definitions
ALLY_TYPES = {
    "irvin_sis": {"name":"Hna Irving","color":(180,200,255),"hp":200,"dmg":8,"speed":2.5,"radius":12,"fr":45,"range":250},
    "zaid":      {"name":"Zaid",      "color":(255,180,80),"hp":400,"dmg":15,"speed":2.0,"radius":18,"fr":30,"range":50},
    "usiel_sis": {"name":"Hna Uziel", "color":(200,255,180),"hp":150,"dmg":3,"speed":2.8,"radius":11,"fr":60,"range":180},
}

# Bomb types
MAX_BOMBS = 3
BOMB_TYPES = {
    "frag":    {"name":"Frag",    "dmg":80,  "radius":120, "speed":12, "fuse":30,  "color":(255,120,50),  "desc":"Explosion estandar"},
    "cluster": {"name":"Cluster", "dmg":50,  "radius":80,  "speed":11, "fuse":25,  "color":(255,80,200),  "desc":"Se divide en 3"},
    "sticky":  {"name":"Sticky",  "dmg":150, "radius":40,  "speed":8,  "fuse":120, "color":(255,50,50),   "desc":"Se pega al enemigo"},
    "mine":    {"name":"Mina",    "dmg":60,  "radius":100, "speed":0,  "fuse":0,   "color":(100,200,100),"desc":"Trampa de piso"},
    "napalm":  {"name":"Napalm",  "dmg":20,  "radius":100, "speed":8,  "fuse":20,  "color":(255,100,0),  "desc":"Charco de fuego 4s"},
    "flash":   {"name":"Flash",   "dmg":0,   "radius":180, "speed":14, "fuse":25,  "color":(255,255,200),"desc":"Ciega 3s"},
    "bouncing":{"name":"Rebotadora","dmg":70,"radius":90,  "speed":15, "fuse":60,  "color":(200,200,50), "desc":"Rebota 3 veces"},
}

MAX_PARTICLES = 600
CYAN = (0, 255, 255)
ADMIN_PASSWORD = "ianesmipastor"
