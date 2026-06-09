import math
import random

import pygame


class Camera:
    """Cámara que sigue al jugador con interpolación suave, look-ahead hacia el mouse y efecto de shake."""
    def __init__(self, w, h):
        self.x = 0; self.y = 0
        self.target_x = 0; self.target_y = 0
        self.w = w; self.h = h
        self.shake_x = 0; self.shake_y = 0
        self.shake_intensity = 0
        self.zoom = 1.0
        self.look_ahead = pygame.Vector2(0, 0)

    def follow(self, target_x, target_y, sw=800, sh=600, mouse_target=None):
        # Calcula la posición objetivo de la cámara centrada en el jugador
        max_x = max(0, self.w - sw)
        max_y = max(0, self.h - sh)
        self.target_x = max(0, min(max_x, target_x - sw // 2))
        self.target_y = max(0, min(max_y, target_y - sh // 2))

        # Look-ahead: la cámara se adelanta hacia donde apunta el mouse
        if mouse_target:
            dx = mouse_target[0] - sw // 2
            dy = mouse_target[1] - sh // 2
            d = math.hypot(dx, dy)
            if d > 20:
                look = min(1.0, d / 300) * 0.15
                self.look_ahead += (pygame.Vector2(dx / d * look * sw, dy / d * look * sh) - self.look_ahead) * 0.05
            else:
                self.look_ahead *= 0.9
        else:
            self.look_ahead *= 0.9

        # Interpolación suave hacia la posición objetivo con look-ahead
        tx = self.target_x + self.look_ahead.x
        ty = self.target_y + self.look_ahead.y

        self.x += (tx - self.x) * 0.08
        self.y += (ty - self.y) * 0.08
        self.x = max(0, min(max_x, self.x))
        self.y = max(0, min(max_y, self.y))

        # Efecto de shake que se desvanece progresivamente
        if self.shake_intensity > 0.3:
            self.shake_x = random.uniform(-self.shake_intensity, self.shake_intensity)
            self.shake_y = random.uniform(-self.shake_intensity, self.shake_intensity)
            self.shake_intensity *= 0.88
        else:
            self.shake_x = 0; self.shake_y = 0; self.shake_intensity = 0

    def add_shake(self, intensity):
        self.shake_intensity = max(self.shake_intensity, intensity)
