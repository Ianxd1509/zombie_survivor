# Changelog — zombie_survivor

## [v1.4] — 2026-06-08

### HUD & UI Fixes
- HUD de bombas ahora usa `len(bomb_queue)` real — muestra cuenta correcta
- Muestra la bomba del frente de la cola (FIFO) en vez de la última comprada
- Oscar ya no dice `[F]` — ahora muestra `[T]` correctamente
- NPC Vicente/Oscar muestran `[F]`/`[T]` sobre sus cabezas (antes `[E]`)
- Pantalla de controles: "Ultimate (carga 40 bajas)" — coincide con `ULT_CHARGE_MAX`
- Pantalla de controles: agregadas `F` (Vicente) y `T` (Oscar)
- Eliminado `bomb_count` y `bomb_active_idx` del código de compra/uso (ya no se desincronizan)

### Habilidades con daño directo
- **Sebas Q** (`rebotar`): ahora también hace 80 de daño AOE (250px) + shake 4
- **Sebas Z** (`rebote caótico`): ahora también hace 150 de daño AOE (300px) + stun 30f + shake 6
- **Obed Q** (`billie`): ahora también hace 60 de daño AOE (250px) + shake 4
- **Obed Z** (`billie ultimate`): ahora también hace 100 de daño AOE (350px) + stun 20f + shake 6

### Correcciones
- Colisión con muros de Randy — `Wall` ahora tiene `rect` sincronizado
- Crash Bomb `e.r` → `e.radius`
- Enemigos atascados se eliminan tras 60s sin dañar al jugador
- `NameError: MatrixRain` en UI reset (import local)
- Eder Z laser ahora suena (loop continuo + chord)
- Sonidos de armas: shoot, sniper, pierce, shotgun asignados correctamente
- Audio recarga.wav normalizado al 98% y volumen al 100%

### Optimización
- Separación de enemigos usa `SpatialHash` — O(N²) → O(N)

### Sonido
- Todos los WAV convertidos a PCM WAV 44100Hz estéreo
- `make_sound()` ahora aplica `vol` a archivos WAV personalizados

---

## [v1.3] — 2026-06-06

### Eder — Guitarra Eléctrica
- **Q** (`guitar_riff`): power chord de 0.35s + AOE 120 de daño + stun
- **Z** (laser cargable): mantén Z para cargar, suelta para disparar rayo
- **Dominio** (X): loop de guitarra durante expansión, soporte para `eder_domain.wav`
- Sonido de dominio ya no crashea (fix `NameError 'enemies'`)

### Correcciones
- Dominio se desactiva correctamente con X (fix `_prev_x_key`)
- Admin mode: dominio ahora carga con 30 bajas (no 40), más bytes por kill
- Boss Vicente: bombas explotan con partículas, `domain_pulse` corregido
- `CreditsScreen.reset()` ya no tira `AttributeError`
- `ChochoxMinion` crash, `bomb_queue IndexError`, `MAP_THEMES` out of range
- `ResultScreen` — `update()` vs `draw()` separados correctamente
