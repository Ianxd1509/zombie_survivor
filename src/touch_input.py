import pygame
from config import WIDTH, HEIGHT

# D-Pad layout
_DPAD_CENTER = (130, HEIGHT - 170)
_DPAD_SIZE = 64
_DPAD_GAP = 72

_DPAD_BTNS = {
    "up":    pygame.Rect(_DPAD_CENTER[0] - _DPAD_SIZE//2, _DPAD_CENTER[1] - _DPAD_GAP - _DPAD_SIZE//2, _DPAD_SIZE, _DPAD_SIZE),
    "down":  pygame.Rect(_DPAD_CENTER[0] - _DPAD_SIZE//2, _DPAD_CENTER[1] + _DPAD_GAP - _DPAD_SIZE//2, _DPAD_SIZE, _DPAD_SIZE),
    "left":  pygame.Rect(_DPAD_CENTER[0] - _DPAD_GAP - _DPAD_SIZE//2, _DPAD_CENTER[1] - _DPAD_SIZE//2, _DPAD_SIZE, _DPAD_SIZE),
    "right": pygame.Rect(_DPAD_CENTER[0] + _DPAD_GAP - _DPAD_SIZE//2, _DPAD_CENTER[1] - _DPAD_SIZE//2, _DPAD_SIZE, _DPAD_SIZE),
}

# Action buttons
_ACTION_BTNS = {
    "q": pygame.Rect(680, HEIGHT - 110, 56, 56),
    "z": pygame.Rect(746, HEIGHT - 110, 56, 56),
    "x": pygame.Rect(812, HEIGHT - 110, 56, 56),
    "r": pygame.Rect(878, HEIGHT - 110, 56, 56),
    "g": pygame.Rect(944, HEIGHT - 110, 56, 56),
}

# Weapon buttons (2x2 grid)
_WEAPON_BTNS = {
    1: pygame.Rect(WIDTH - 160, HEIGHT - 175, 50, 50),
    2: pygame.Rect(WIDTH - 100, HEIGHT - 175, 50, 50),
    3: pygame.Rect(WIDTH - 160, HEIGHT - 115, 50, 50),
    4: pygame.Rect(WIDTH - 100, HEIGHT - 115, 50, 50),
}

# Utility buttons
_ESC_BTN = pygame.Rect(WIDTH - 46, 8, 40, 40)
_SPACE_BTN = pygame.Rect(WIDTH//2 - 100, HEIGHT - 65, 200, 50)

# Shoot zone (right side, above action buttons)
_SHOOT_ZONE = pygame.Rect(480, 0, WIDTH - 480, HEIGHT - 130)

GREEN = (0, 255, 65)
DARK = (0, 30, 0)
WHITE = (200, 220, 200)

def _draw_dpad_arrow(surf, rect, direction):
    cx, cy = rect.center
    pygame.draw.rect(surf, (0, 60, 0, 180), rect, border_radius=8)
    pygame.draw.rect(surf, (0, 200, 50, 220), rect, 2, border_radius=8)
    clr = (100, 255, 120)
    if direction == "up":
        pts = [(cx, cy-12), (cx-12, cy+8), (cx+12, cy+8)]
    elif direction == "down":
        pts = [(cx, cy+12), (cx-12, cy-8), (cx+12, cy-8)]
    elif direction == "left":
        pts = [(cx-12, cy), (cx+8, cy-12), (cx+8, cy+12)]
    else:
        pts = [(cx+12, cy), (cx-8, cy-12), (cx-8, cy+12)]
    pygame.draw.polygon(surf, clr, pts)

def _draw_icon_btn(surf, rect, icon_lines, pressed):
    bg = (0, 80, 0, 200) if pressed else (0, 50, 0, 160)
    brd = (0, 255, 65) if pressed else (0, 150, 40)
    pygame.draw.rect(surf, bg, rect, border_radius=6)
    pygame.draw.rect(surf, brd, rect, 2, border_radius=6)
    for pts, clr in icon_lines:
        pygame.draw.lines(surf, clr, False, [(rect.x + p[0], rect.y + p[1]) for p in pts], 2)

def _make_bolt_icon():
    return [([(24,6),(30,18),(22,18),(18,30),(28,18),(20,18),(26,6)], (255,220,80))]

def _make_burst_icon():
    return [([(15,28),(20,18),(28,14),(24,22),(28,28),(20,24)], (255,100,100)),
            ([(28,14),(32,6),(34,14)], (255,100,100))]

def _make_crystal_icon():
    return [([(10,28),(16,8),(28,8),(34,28)], (150,200,255)),
            ([(16,8),(22,18),(28,8)], (200,230,255))]

def _make_reload_icon():
    return [([(20,10),(28,10),(28,18)], (200,255,200)),
            ([(18,12),(28,14),(24,18)], (150,255,150))]

def _make_bomb_icon():
    return [([(14,28),(20,12),(28,12),(34,28)], (255,180,80)),
            ([(24,20)], (255,60,60))]

def _make_pause_icon():
    return [([(12,8),(12,30)], (255,255,200)),
            ([(24,8),(24,30)], (255,255,200))]

def _make_play_icon():
    return [([(16,8),(32,18),(16,28)], (100,255,100))]

def _make_gun_icon():
    return [([(8,18),(30,14),(38,14),(38,22),(30,22),(8,18)], (180,180,180)),
            ([(8,14),(20,14),(18,18),(8,18)], (200,200,200))]

_ICONS = {
    "q": _make_bolt_icon(),
    "z": _make_burst_icon(),
    "x": _make_crystal_icon(),
    "r": _make_reload_icon(),
    "g": _make_bomb_icon(),
    "esc": _make_pause_icon(),
    "space": _make_play_icon(),
    "gun": _make_gun_icon(),
}

class TouchControls:
    def __init__(self):
        self.fingers = {}
        self.buttons = set()
        self.shooting = False
        self.aim_pos = [WIDTH//2, HEIGHT//2]
        self.move_x = 0.0
        self.move_y = 0.0

    def handle_event(self, event):
        if event.type == pygame.FINGERDOWN:
            fx = int(event.x * WIDTH)
            fy = int(event.y * HEIGHT)
            self.fingers[event.finger_id] = (fx, fy)
            self._update_state(event.finger_id, fx, fy)
        elif event.type == pygame.FINGERUP:
            fid = event.finger_id
            if fid in self.fingers:
                fx, fy = self.fingers[fid]
                self._clear_finger(fid, fx, fy)
                del self.fingers[fid]
            self.shooting = False
            self._recalc_move()
        elif event.type == pygame.FINGERMOTION:
            fid = event.finger_id
            fx = int(event.x * WIDTH)
            fy = int(event.y * HEIGHT)
            if fid in self.fingers:
                old_x, old_y = self.fingers[fid]
                self.fingers[fid] = (fx, fy)
                self._update_move_from_dpad(fid, old_x, old_y, fx, fy)
            self._update_aim(fx, fy)

    def _update_state(self, fid, fx, fy):
        for name, rect in _DPAD_BTNS.items():
            if rect.collidepoint(fx, fy):
                self.buttons.add(name)
                self._recalc_move()
                return
        for name, rect in _ACTION_BTNS.items():
            if rect.collidepoint(fx, fy):
                self.buttons.add(name)
                return
        for idx, rect in _WEAPON_BTNS.items():
            if rect.collidepoint(fx, fy):
                self.buttons.add(f"weapon_{idx}")
                return
        if _ESC_BTN.collidepoint(fx, fy):
            self.buttons.add("esc")
            return
        if _SPACE_BTN.collidepoint(fx, fy):
            self.buttons.add("space")
            return
        if _SHOOT_ZONE.collidepoint(fx, fy):
            self.shooting = True
            self.aim_pos = [fx, fy]

    def _clear_finger(self, fid, fx, fy):
        for name, rect in _DPAD_BTNS.items():
            if rect.collidepoint(fx, fy):
                self.buttons.discard(name)
                self._recalc_move()
                return
        for name, rect in _ACTION_BTNS.items():
            if rect.collidepoint(fx, fy):
                self.buttons.discard(name)
                return
        for idx, rect in _WEAPON_BTNS.items():
            if rect.collidepoint(fx, fy):
                self.buttons.discard(f"weapon_{idx}")
                return
        if _ESC_BTN.collidepoint(fx, fy):
            self.buttons.discard("esc")
            return
        if _SPACE_BTN.collidepoint(fx, fy):
            self.buttons.discard("space")
            return
        self.shooting = False

    def _update_move_from_dpad(self, fid, old_x, old_y, new_x, new_y):
        was_in = False
        for rect in _DPAD_BTNS.values():
            if rect.collidepoint(old_x, old_y):
                was_in = True
                break
        if not was_in:
            return
        in_now = False
        for name, rect in _DPAD_BTNS.items():
            if rect.collidepoint(new_x, new_y):
                self.buttons.add(name)
                in_now = True
            else:
                self.buttons.discard(name)
        if not in_now:
            self.buttons.discard("up")
            self.buttons.discard("down")
            self.buttons.discard("left")
            self.buttons.discard("right")
        self._recalc_move()

    def _recalc_move(self):
        self.move_x = 0.0
        self.move_y = 0.0
        if "left" in self.buttons: self.move_x -= 1.0
        if "right" in self.buttons: self.move_x += 1.0
        if "up" in self.buttons: self.move_y -= 1.0
        if "down" in self.buttons: self.move_y += 1.0

    def _update_aim(self, fx, fy):
        for name, rect in _DPAD_BTNS.items():
            if rect.collidepoint(fx, fy):
                return
        for name, rect in _ACTION_BTNS.items():
            if rect.collidepoint(fx, fy):
                return
        for idx, rect in _WEAPON_BTNS.items():
            if rect.collidepoint(fx, fy):
                return
        if _ESC_BTN.collidepoint(fx, fy) or _SPACE_BTN.collidepoint(fx, fy):
            return
        self.shooting = True
        self.aim_pos = [fx, fy]

    def get_state(self):
        keys = {pygame.K_w: "up" in self.buttons,
                pygame.K_s: "down" in self.buttons,
                pygame.K_a: "left" in self.buttons,
                pygame.K_d: "right" in self.buttons,
                pygame.K_q: "q" in self.buttons,
                pygame.K_z: "z" in self.buttons,
                pygame.K_x: "x" in self.buttons,
                pygame.K_r: "r" in self.buttons,
                pygame.K_g: "g" in self.buttons,
                pygame.K_ESCAPE: "esc" in self.buttons,
                pygame.K_SPACE: "space" in self.buttons,
                pygame.K_LSHIFT: "shift" in self.buttons,
                pygame.K_1: "weapon_1" in self.buttons,
                pygame.K_2: "weapon_2" in self.buttons,
                pygame.K_3: "weapon_3" in self.buttons,
                pygame.K_4: "weapon_4" in self.buttons}
        touch_btn = self.shooting
        touch_pos = tuple(self.aim_pos)
        return keys, touch_btn, touch_pos

    def consume_event(self, name):
        if name in self.buttons:
            self.buttons.discard(name)
            return True
        return False

    def draw(self, surf):
        for name, rect in _DPAD_BTNS.items():
            _draw_dpad_arrow(surf, rect, name)
        for name, rect in _ACTION_BTNS.items():
            pressed = name in self.buttons
            _draw_icon_btn(surf, rect, _ICONS[name], pressed)
        for idx, rect in _WEAPON_BTNS.items():
            pressed = f"weapon_{idx}" in self.buttons
            _draw_icon_btn(surf, rect, _ICONS["gun"], pressed)
        _draw_icon_btn(surf, _ESC_BTN, _ICONS["esc"], "esc" in self.buttons)
        _draw_icon_btn(surf, _SPACE_BTN, _ICONS["space"], "space" in self.buttons)
