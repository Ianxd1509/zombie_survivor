import random
from collections import deque

from config import MAP_H, MAP_W

# Tamaño en píxeles de cada tile y número de columnas/filas del grid
TILE = 40
COLS = MAP_W // TILE
ROWS = MAP_H // TILE


def _rect(g, r1, r2, c1, c2, v=1):
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            if 0 <= r < ROWS and 0 <= c < COLS:
                g[r][c] = v


def _hwall(g, r, c1, c2, v=1):
    for c in range(c1, c2 + 1):
        if 0 <= r < ROWS and 0 <= c < COLS:
            g[r][c] = v


def _vwall(g, c, r1, r2, v=1):
    for r in range(r1, r2 + 1):
        if 0 <= r < ROWS and 0 <= c < COLS:
            g[r][c] = v


def _door(g, r, c, horiz=True, w=3):
    if horiz:
        _hwall(g, r, c, c + w - 1, 0)
    else:
        _vwall(g, c, r, r + w - 1, 0)


def _cross(g, r, c, v=1):
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                g[nr][nc] = v


# ── Rangos de valores de tiles ──
# 0        = empty (black, walkable)
# 1-9      = structural walls (block movement)
# 10-19    = floors (walkable, colored ground)
# 20-35    = decorative walls / furniture (block movement)


# Colores de paredes/obstáculos según el valor del tile
WALL_COLORS = {
    # Structural walls (block)
    1: (8, 30, 8),       # outer border - very dark green
    2: (20, 55, 15),     # Edificio A exterior - dark teal/green
    3: (20, 55, 15),     # Edificio B exterior
    4: (45, 35, 18),     # Cafeteria exterior - brown brick
    5: (12, 42, 25),     # Lab exterior - dark blue/green
    6: (18, 50, 12),     # Canchas exterior - dark olive
    7: (45, 45, 40),     # Plaza pillars - stone gray
    8: (25, 48, 18),     # interior walls - medium green
    9: (10, 35, 8),      # trees / bushes
    # Decorative walls (block)
    20: (50, 60, 65),    # fountain rim - blue-gray stone
    21: (65, 48, 28),    # bench - brown wood
    22: (35, 55, 20),    # planter / flower bed
    23: (40, 40, 42),    # lamp post - dark gray
    24: (65, 25, 20),    # car - red
    25: (60, 60, 55),    # goal post - off-white
    26: (55, 50, 35),    # locker - metallic tan
    27: (25, 45, 30),    # server rack extra - tech dark
    28: (30, 45, 25),    # classroom desk
    29: (50, 35, 20),    # cafeteria table / counter
    # New for v2 expansion
    30: (55, 55, 58),    # parking barrier - concrete gray
    31: (12, 30, 14),    # hedge wall - dark green
    32: (35, 28, 20),    # library wall - brown brick
    33: (22, 18, 12),    # bookshelf - dark wood
    34: (40, 42, 45),    # parking lamp - light pole
    35: (45, 25, 20),    # car 2 - dark red
}

# Colores de pisos/suelos transitables según el valor del tile
FLOOR_COLORS = {
    10: (30, 30, 28),    # plaza paved - warm gray
    11: (25, 28, 22),    # path / sidewalk - light gray-brown
    12: (20, 22, 20),    # building interior floor - dark gray
    13: (40, 35, 25),    # cafeteria floor - tan / beige
    14: (15, 20, 28),    # lab floor - dark blue-gray
    15: (45, 30, 18),    # canchas court - orange / terracotta
    16: (6, 22, 8),      # grass - dark green
    17: (25, 45, 50),    # fountain water - blue
    18: (18, 18, 20),    # asphalt - parking lot
    19: (30, 25, 18),    # wood floor - library
}


# Temas visuales para cada mapa (colores de pared, piso, fondo y luz ambiental)
MAP_THEMES = [
    {
        "wall": WALL_COLORS,
        "floor": FLOOR_COLORS,
        "bg": (2, 8, 2),
        "ambient": (0, 200, 255),
        "name": "Campus",
    },
    {
        "wall": {
            1: (10, 40, 10), 2: (25, 55, 15), 3: (15, 45, 10),
            4: (35, 25, 12), 5: (20, 50, 20), 6: (30, 50, 15),
            7: (40, 35, 30), 8: (20, 40, 12), 9: (8, 25, 6),
            20: (12, 45, 8), 21: (60, 40, 20), 22: (25, 60, 18),
            23: (35, 35, 38), 24: (60, 20, 15), 25: (55, 55, 50),
            30: (50, 45, 40), 31: (15, 40, 12), 32: (30, 25, 18),
            33: (20, 15, 10), 34: (35, 40, 42), 35: (40, 20, 15),
        },
        "floor": {
            10: (25, 30, 22), 11: (22, 28, 18), 12: (18, 22, 15),
            13: (35, 30, 20), 14: (12, 20, 24), 15: (40, 28, 12),
            16: (6, 18, 6), 17: (18, 40, 42), 18: (15, 18, 15),
            19: (25, 22, 14),
        },
        "bg": (4, 12, 4),
        "ambient": (100, 255, 100),
        "name": "Bosque",
    },
    {
        "wall": {
            1: (10, 15, 10), 2: (40, 35, 15), 3: (38, 32, 12),
            4: (45, 40, 20), 5: (35, 30, 10), 6: (42, 38, 18),
            7: (50, 45, 35), 8: (38, 33, 15), 9: (20, 50, 10),
            20: (60, 55, 40), 21: (55, 40, 25), 22: (50, 60, 30),
            23: (40, 38, 35), 24: (55, 25, 20), 25: (58, 55, 48),
            30: (52, 48, 42), 31: (25, 55, 20), 32: (35, 30, 22),
            33: (22, 18, 12), 34: (38, 42, 40), 35: (40, 22, 18),
        },
        "floor": {
            10: (55, 50, 35), 11: (50, 45, 30), 12: (45, 40, 28),
            13: (58, 50, 35), 14: (40, 45, 50), 15: (55, 42, 25),
            16: (35, 30, 15), 17: (20, 60, 70), 18: (50, 48, 40),
            19: (55, 45, 30),
        },
        "bg": (25, 20, 10),
        "ambient": (255, 200, 100),
        "name": "Playa",
    },
]


# Genera el grid del mapa según el índice (0=Campus, 1=Bosque, 2=Playa)
def generate_grid(map_index=0):
    if map_index == 1:
        return _generate_forest()
    if map_index == 2:
        return _generate_beach()
    return _generate_campus()


def _generate_forest():
    g = [[0] * COLS for _ in range(ROWS)]
    _rect(g, 0, 0, 0, COLS - 1, 1)
    _rect(g, ROWS - 1, ROWS - 1, 0, COLS - 1, 1)
    _rect(g, 0, ROWS - 1, 0, 0, 1)
    _rect(g, 0, ROWS - 1, COLS - 1, COLS - 1, 1)
    _rect(g, 1, ROWS - 2, 1, COLS - 2, 16)

    # River winding from top-left to bottom-right
    river_cells = [(5, 20), (6, 22), (7, 24), (8, 26), (10, 28), (12, 30),
                   (15, 32), (18, 33), (22, 34), (26, 35), (30, 34), (34, 33),
                   (38, 32), (42, 33), (46, 35), (50, 38), (54, 42), (58, 46),
                   (62, 51), (66, 56), (70, 60), (74, 64), (78, 68), (82, 72),
                   (86, 76), (90, 80), (94, 84), (98, 88), (102, 92), (106, 96),
                   (110, 100), (114, 104), (118, 108), (122, 112), (126, 116)]
    for i in range(len(river_cells)):
        r, c = river_cells[i]
        for dr in range(-1, 2):
            for dc in range(-2, 3):
                nr, nc = r + dr, c + dc
                if 1 < nr < ROWS - 1 and 1 < nc < COLS - 1:
                    g[nr][nc] = 17

    # Clearings (large open areas)
    clearings = [(20, 50, 30, 65), (35, 18, 50, 35), (55, 70, 55, 75),
                 (80, 100, 30, 50), (90, 110, 80, 100)]
    for r1, r2, c1, c2 in clearings:
        _rect(g, r1, r2, c1, c2, 10)

    # Paths connecting clearings
    path_routes = [(25, 50, 35, 50), (40, 65, 40, 65), (60, 80, 50, 55),
                   (75, 100, 30, 35), (90, 110, 30, 80)]
    for r1, r2, c1, c2 in path_routes:
        _rect(g, r1, r2, c1, c2, 11)

    # Cabañas (small cabins)
    cabins = [(22, 28, 65, 72, 4), (65, 71, 20, 27, 4), (100, 106, 100, 107, 5)]
    for r1, r2, c1, c2, wv in cabins:
        _rect(g, r1, r1 + 1, c1, c2, wv)
        _rect(g, r2 - 1, r2, c1, c2, wv)
        _rect(g, r1 + 2, r2 - 2, c1, c1 + 1, wv)
        _rect(g, r1 + 2, r2 - 2, c2 - 1, c2, wv)
        _rect(g, r1 + 2, r2 - 2, c1 + 1, c2 - 1, 12)
        _door(g, r2 - 1, c1 + 2, horiz=True, w=2)

    # Dense trees
    rng = random.Random(42)
    for _ in range(400):
        r = rng.randint(2, ROWS - 3)
        c = rng.randint(2, COLS - 3)
        if g[r][c] == 16:
            g[r][c] = 9

    # Rocks and bushes along river
    rng2 = random.Random(17)
    for _ in range(60):
        r = rng2.randint(5, 125)
        c = rng2.randint(5, 125)
        if g[r][c] == 16:
            g[r][c] = 20

    return g


def _generate_beach():
    g = [[0] * COLS for _ in range(ROWS)]
    _rect(g, 0, 0, 0, COLS - 1, 1)
    _rect(g, ROWS - 1, ROWS - 1, 0, COLS - 1, 1)
    _rect(g, 0, ROWS - 1, 0, 0, 1)
    _rect(g, 0, ROWS - 1, COLS - 1, COLS - 1, 1)

    # Ocean (left 40%)
    _rect(g, 1, ROWS - 2, 1, 50, 17)

    # Sand (right 60%)
    _rect(g, 1, ROWS - 2, 51, COLS - 2, 10)

    # Shoreline transition (sand path between ocean and sand)
    _rect(g, 1, ROWS - 2, 48, 52, 11)

    # Boardwalk (wood path along back of beach)
    _rect(g, 10, 14, 52, COLS - 2, 19)
    _rect(g, ROWS - 16, ROWS - 12, 52, COLS - 2, 19)

    # Palm trees scattered on sand
    rng = random.Random(42)
    for _ in range(100):
        r = rng.randint(2, ROWS - 3)
        c = rng.randint(53, COLS - 3)
        if g[r][c] == 10:
            g[r][c] = 9

    # Pier (muelle) sticking into ocean
    pier_row = ROWS // 2
    _rect(g, pier_row - 1, pier_row + 1, 25, 48, 19)
    # Pier railings
    _hwall(g, pier_row - 2, 25, 48, 21)
    _hwall(g, pier_row + 2, 25, 48, 21)
    # Boat at end of pier
    g[pier_row][22] = 24
    g[pier_row - 1][23] = 24
    g[pier_row + 1][23] = 24

    # Palapas (round structures)
    palapas = [(20, 80), (60, 100), (110, 70)]
    for pr, pc in palapas:
        for dr in range(-3, 4):
            for dc in range(-3, 4):
                if abs(dr) <= 1 and abs(dc) <= 1:
                    g[pr + dr][pc + dc] = 13
                elif max(abs(dr), abs(dc)) == 3 and 0 < pr + dr < ROWS - 1 and 0 < pc + dc < COLS - 1:
                    g[pr + dr][pc + dc] = 4

    # Rocks at water edge
    for _ in range(20):
        r = rng.randint(2, ROWS - 3)
        c = rng.randint(45, 55)
        if g[r][c] != 1:
            g[r][c] = 20

    return g


def _generate_campus():
    g = [[0] * COLS for _ in range(ROWS)]
    _rect(g, 0, 0, 0, COLS - 1, 1)
    _rect(g, ROWS - 1, ROWS - 1, 0, COLS - 1, 1)
    _rect(g, 0, ROWS - 1, 0, 0, 1)
    _rect(g, 0, ROWS - 1, COLS - 1, COLS - 1, 1)
    _rect(g, 1, ROWS - 2, 1, COLS - 2, 16)

    _rect(g, 30, 48, 30, 60, 10)
    _rect(g, 12, 26, 20, 34, 12)
    _rect(g, 12, 26, 56, 70, 12)
    _rect(g, 52, 64, 20, 34, 13)
    _rect(g, 52, 64, 56, 70, 14)
    _rect(g, 74, 90, 28, 66, 15)

    _rect(g, 39, 41, 12, 83, 11)
    _rect(g, 29, 50, 43, 47, 11)
    _rect(g, 29, 29, 24, 26, 11)
    _rect(g, 29, 29, 60, 62, 11)
    _rect(g, 49, 49, 24, 26, 11)
    _rect(g, 49, 49, 60, 62, 11)
    _rect(g, 49, 71, 44, 50, 11)
    _rect(g, 10, 66, 15, 17, 11)
    _rect(g, 10, 66, 73, 75, 11)

    _rect(g, 10, 11, 18, 36, 2)
    _rect(g, 27, 28, 18, 36, 2)
    _rect(g, 10, 28, 18, 19, 2)
    _rect(g, 10, 28, 35, 36, 2)
    _door(g, 28, 24)
    _hwall(g, 27, 24, 26, 0)
    _rect(g, 10, 11, 54, 72, 3)
    _rect(g, 27, 28, 54, 72, 3)
    _rect(g, 10, 28, 54, 55, 3)
    _rect(g, 10, 28, 71, 72, 3)
    _door(g, 28, 60)
    _hwall(g, 27, 60, 62, 0)
    _rect(g, 50, 51, 18, 36, 4)
    _rect(g, 65, 66, 18, 36, 4)
    _rect(g, 50, 66, 18, 19, 4)
    _rect(g, 50, 66, 35, 36, 4)
    _door(g, 66, 24)
    _hwall(g, 65, 24, 26, 0)
    _rect(g, 50, 51, 54, 72, 5)
    _rect(g, 65, 66, 54, 72, 5)
    _rect(g, 50, 66, 54, 55, 5)
    _rect(g, 50, 66, 71, 72, 5)
    _door(g, 66, 60)
    _hwall(g, 65, 60, 62, 0)

    for r in range(12, 27, 3):
        _hwall(g, r, 21, 33, 8)
    _vwall(g, 24, 12, 26, 8)
    for r in range(12, 27, 3):
        _hwall(g, r, 57, 69, 8)
    _vwall(g, 60, 12, 26, 8)

    rng = random.Random(42)
    for _ in range(12):
        dr = rng.randint(13, 25)
        dc = rng.randint(21, 32)
        if g[dr][dc] == 12: g[dr][dc] = 28
    for _ in range(4):
        dr = rng.randint(13, 25)
        if g[dr][20] == 12: g[dr][20] = 26
    rng2 = random.Random(99)
    for _ in range(12):
        dr = rng2.randint(13, 25)
        dc = rng2.randint(57, 68)
        if g[dr][dc] == 12: g[dr][dc] = 28
    rng3 = random.Random(33)
    for _ in range(8):
        dr = rng3.randint(53, 63)
        dc = rng3.randint(21, 33)
        if g[dr][dc] == 13: g[dr][dc] = 29
    for r in range(53, 64, 3):
        for c in (58, 64, 70):
            if g[r][c] == 14: g[r][c] = 27

    random.Random(7)
    for dr in range(-1, 2):
        for dc in range(-1, 2): g[39 + dr][45 + dc] = 20
    for dr in range(-1, 2): g[39 + dr][44] = 0; g[39 + dr][46] = 0
    g[38][45] = 0; g[40][45] = 0; g[39][45] = 17
    g[29][28] = 21; g[29][60] = 21; g[49][28] = 21; g[49][60] = 21
    lamp_positions = [(30, 18), (30, 72), (10, 16), (10, 74), (26, 42), (44, 42), (28, 50), (42, 38), (50, 18), (50, 72)]
    for lr, lc in lamp_positions: _cross(g, lr, lc, 23)

    lib_wall = 32
    _rect(g, 76, 77, 78, 106, lib_wall)
    _rect(g, 106, 107, 78, 106, lib_wall)
    _rect(g, 76, 107, 78, 79, lib_wall)
    _rect(g, 76, 107, 105, 106, lib_wall)
    _rect(g, 78, 106, 80, 104, 19)
    for r in range(80, 106, 4):
        for c in range(80, 104, 6): g[r][c] = 33
    _rect(g, 75, 99, 4, 14, 31)
    _rect(g, 100, 101, 4, 14, 4)
    _rect(g, 75, 101, 4, 5, 4)
    _rect(g, 75, 101, 13, 14, 4)
    _door(g, 101, 7)
    for r in range(77, 99, 3): g[r][6] = 16; g[r][12] = 16
    for c in range(6, 13, 3): g[77][c] = 16; g[99][c] = 16
    g[88][9] = 16
    for _ in range(10):
        fr = random.randint(77, 98)
        fc = random.randint(6, 12)
        if g[fr][fc] == 31: g[fr][fc] = 22
    _rect(g, 3, 8, 2, 14, 18)
    _hwall(g, 3, 2, 14, 8)
    _hwall(g, 8, 2, 14, 8)
    _vwall(g, 2, 3, 7, 8)
    _vwall(g, 14, 3, 7, 8)
    _door(g, 8, 6, horiz=True, w=3)
    _hwall(g, 5, 4, 6, 30)
    _hwall(g, 7, 4, 6, 30)
    g[4][8] = 24; g[4][10] = 24; g[4][12] = 24
    g[6][5] = 35; g[6][9] = 24; g[6][13] = 35
    g[8][4] = 24; g[8][8] = 35; g[8][12] = 24
    for gc in (32, 62):
        _vwall(g, gc, 76, 78, 25)
        _vwall(g, gc, 86, 88, 25)
    _rect(g, 51, 70, 44, 50, 11)
    _rect(g, 71, 74, 44, 50, 16)
    _rect(g, 74, 75, 44, 50, 11)
    _rect(g, 76, 76, 48, 78, 11)
    _rect(g, 51, 70, 44, 50, 11)
    _rect(g, 71, 74, 44, 50, 16)
    _rect(g, 74, 75, 30, 44, 11)
    _rect(g, 75, 75, 14, 30, 11)
    _rect(g, 2, 2, 16, 74, 11)
    _rect(g, 78, 83, 75, 77, 11)
    _rect(g, 84, 106, 75, 77, 16)

    rng5 = random.Random(42)
    for _ in range(80):
        r = rng5.randint(2, 8) if rng5.random() < 0.5 else rng5.randint(ROWS - 7, ROWS - 3)
        c = rng5.randint(2, 14) if rng5.random() < 0.5 else rng5.randint(COLS - 14, COLS - 3)
        if g[r][c] == 16: g[r][c] = 9
    rng6 = random.Random(77)
    for _ in range(40):
        r = rng6.randint(1, ROWS - 2)
        c = rng6.randint(1, COLS - 2)
        if g[r][c] == 16: g[r][c] = 9

    return g


# Convierte coordenadas del mundo a coordenadas de tile (col, row)
def world_to_tile(x, y):
    return int(x // TILE), int(y // TILE)


# Verifica si una celda del grid es una pared (obstáculo)
def is_wall(grid, col, row):
    if row < 0 or row >= len(grid) or col < 0 or col >= len(grid[0]):
        return True
    v = grid[row][col]
    # 1-9 and 20+ = wall; 0 and 10-19 = walkable
    return (1 <= v <= 9) or (v >= 20)


# Calcula todas las celdas alcanzables desde un origen (BFS) — usado para pathfinding
def compute_reachable(grid, start_col, start_row):
    if not (0 <= start_row < len(grid) and 0 <= start_col < len(grid[0])):
        return set()
    if is_wall(grid, start_col, start_row):
        return set()
    reachable = set()
    q = deque([(start_col, start_row)])
    reachable.add((start_col, start_row))
    while q:
        c, r = q.popleft()
        for dc, dr in ((1,0), (-1,0), (0,1), (0,-1)):
            nc, nr = c + dc, r + dr
            if 0 <= nr < len(grid) and 0 <= nc < len(grid[0]) and (nc, nr) not in reachable and not is_wall(grid, nc, nr):
                reachable.add((nc, nr))
                q.append((nc, nr))
    return reachable
