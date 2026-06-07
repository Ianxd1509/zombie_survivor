import math

import pygame

from src.tilemap import is_wall, world_to_tile


class SquadManager:
    """Agrupa enemigos cercanos en escuadrones tácticos con formaciones (surround, flank)."""
    def __init__(self):
        self.squads = []
        self.refresh_timer = 0

    def _tile_walkable(self, grid, wx, wy):
        if grid is None:
            return True
        col, row = world_to_tile(wx, wy)
        if row < 0 or row >= len(grid) or col < 0 or col >= len(grid[0]):
            return False
        return not is_wall(grid, col, row)

    def update(self, enemies, player_pos, grid=None):
        self.refresh_timer += 1
        if self.refresh_timer < 15:
            return
        self.refresh_timer = 0
        used = set()
        self.squads = []
        elist = [e for e in enemies if hasattr(e, "etype") and hasattr(e, "alive") and e.alive() and e.hp > 0]
        for i, e in enumerate(elist):
            if i in used:
                continue
            squad = [e]
            used.add(i)
            for j in range(i + 1, len(elist)):
                if j in used:
                    continue
                if e.pos.distance_to(elist[j].pos) < 220:
                    squad.append(elist[j])
                    used.add(j)
            if len(squad) >= 2:
                self.squads.append(squad)
                if len(player_pos) < 2:
                    continue
                leader = min(squad, key=lambda x: x.pos.distance_to(pygame.Vector2(player_pos[0], player_pos[1])))
                dx = player_pos[0] - leader.pos.x
                dy = player_pos[1] - leader.pos.y
                dist = math.hypot(dx, dy)
                dist = max(dist, 1)
                angle_to_player = math.atan2(dy, dx)
                # Decide formación según tamaño y composición del escuadrón
                tank_count = sum(1 for m in squad if m.etype in ("tank", "shielded"))
                formation = "wall" if tank_count >= 3 else "surround" if len(squad) >= 5 else "flank"
                for idx, member in enumerate(squad):
                    tx = player_pos[0]
                    ty = player_pos[1]
                    if formation == "wall":
                        m_idx = idx % 5
                        spacing = 100
                        wall_x = player_pos[0] + math.cos(angle_to_player) * 160
                        wall_y = player_pos[1] + math.sin(angle_to_player) * 160
                        perp_angle = angle_to_player + math.pi / 2
                        tx = wall_x + math.cos(perp_angle) * (m_idx - 2) * spacing
                        ty = wall_y + math.sin(perp_angle) * (m_idx - 2) * spacing
                    elif formation == "surround":
                        a = angle_to_player + math.tau * idx / len(squad)
                        tx += math.cos(a) * 130
                        ty += math.sin(a) * 130
                    elif formation == "flank":
                        side = -1 if idx % 2 == 0 else 1
                        perp_x = -dy / dist * side * 90
                        perp_y = dx / dist * side * 90
                        ahead_x = dx / dist * 110
                        ahead_y = dy / dist * 110
                        tx += ahead_x + perp_x
                        ty += ahead_y + perp_y
                    if grid is not None and not self._tile_walkable(grid, tx, ty):
                        tx, ty = player_pos[0], player_pos[1]
                    member.tactical_target = (tx, ty)
                    member.tactical_state = "flank" if formation != "swarm" else "chase"
                    if member.etype in ("shooter", "buffer"):
                        member.tactical_state = "hold"
                    # Healer escort: sigue al tank más cercano
                    if member.etype == "healer":
                        tanks = [m for m in squad if m.etype in ("tank", "shielded")]
                        if tanks:
                            nearest_tank = min(tanks, key=lambda t: t.pos.distance_to(member.pos))
                            member.tactical_target = (nearest_tank.pos.x - dx / dist * 60,
                                                      nearest_tank.pos.y - dy / dist * 60)
                            member.tactical_state = "flank"
                        else:
                            member.tactical_state = "hold"
            else:
                for m in squad:
                    m.tactical_target = None
                    if m.etype in ("shooter", "healer", "buffer"):
                        m.tactical_state = "hold"
                    else:
                        m.tactical_state = "chase"

    def clear(self):
        self.squads = []
        self.refresh_timer = 0
