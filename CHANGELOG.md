# Changelog — zombie_survivor

## [v1.7] — 2026-06-09

### Bugs críticos corregidos
- Láser de Vicente Boss ya no se mata a sí mismo al eliminar un enemigo (game.py)
- BillieNPC ahora retorna `True` en update() — ya no se congela tras 1 frame
- `dmg_mult` de "rebotar" (Sebas Q) ahora se resetea al terminar la duración
- Timer de dominio de Vicente ya no se decrementa doble por frame
- `SFX["click"]` envuelto en guard condicional (game.py)

### Bugs altos corregidos
- **Passive stats**: ahora se parsean correctamente (`"piercing+1"` → +1 piercing). 9/10 personajes ahora reciben su stat pasivo real
- `eder_laser_loop` ahora se reproduce al disparar el láser (antes nunca sonaba)
- Reembolsos de tienda devuelven el costo real pagado (no el costo del siguiente nivel)
- Cámara ya no se traba si el mundo es más chico que la pantalla

### Bugs medios corregidos
- Animaciones agregadas a: rebotar Z, billie Q+Z, guitar_riff Q, buffer Q+Z
- Volumen SFX global ×1.8 aplicado (ahora +80% real)
- Música de tienda con fallback sintético (antes silencio si faltaba .wav)
- Muros de Randy usan colisiones circulares en vez de rect-based
- Healer de tactics empuja en dirección correcta (hacia el tank más cercano, no el leader)
- Squad members con spread aleatorio al converger en pared
- Vicente Boss excluido de la fase 2 genérica de jefe
- `EVOLUTION_ITEMS["vicente"]` agregado (Termo)

### Bugs bajos corregidos
- Ternario sin efecto en main.py eliminado
- `pygame.quit()` en `finally` al crashear
- Código muerto `random.Random(7)` en tilemap.py eliminado
- `sebas_ult` renombrado a `sebas_z` para consistencia
- Sombra del personaje usa `base_color` en vez de verde fijo
- Import de `draw_player` movido fuera de `CharSelector.draw()`

### UI
- Texto "SERVER {wave}" reposicionado arriba del minimapa

---

## [v1.6] — 2026-06-09

### Animaciones en habilidades
- **Irvin Q/Z**: spin (gira el sprite)
- **Vicente Q**: spin (gira el sprite)
- **Leo Q/Z**: pulse (escala pulsante)
- **Diego Q/Z**: pulse
- **Uziel Q/Z**: pulse
- **Randy Q/Z**: pulse
- **Vicente Z**: pulse

### Tienda de Vicente
- Nuevo item "Municion": +50 balas de reserva, 80 bytes, max 10 compras

---

## [v1.5] — 2026-06-09

### Sonidos personalizados para todas las habilidades
- **Q abilities**: cada personaje tiene su propio sonido (irvin_q, sebas_q, leo_q, diego_q, usiel_q, obed_q, ian_q, randy_q, vicente_q)
- **Z ultimates**: cada personaje tiene su propio sonido (irvin_z, leo_z, diego_z, usiel_z, obed_z, ian_z, randy_z, vicente_z + sebas_ult existente)
- **Dominios X**: cada personaje tiene su propio sonido al activar dominio (irvin_domain, sebas_domain, leo_domain, diego_domain, usiel_domain, obed_domain, eder_domain, ian_domain, randy_domain, vicente_domain)
- Sonidos definidos en `sound.py` con fallback procedural. Nombres de archivo documentados en `assets/sounds/_list.txt`.

### Ian Z = láser cargable (como Eder)
- Ian ahora usa el mismo sistema de carga que Eder: mantener Z para cargar, soltar para disparar
- Láser, partículas y notificación en **blanco** (vs rojo/púrpura de Eder)

### Imágenes de personaje mejoradas
- `load_image()` ahora usa `pygame.transform.smoothscale()` en vez de `scale()` — imágenes PNG se ven más suaves
- La pantalla de selección de personajes (`CharSelector`) muestra la imagen personalizada en vez de un círculo genérico

### Fixes de SFX
- Agregados guards `if SFX and hasattr(SFX, "get")` a todas las llamadas `SFX[...].play()` que faltaban (18 en game.py, 2 en entities.py)

### Calidad de vida
- Nuevo archivo `assets/sounds/_list.txt` con todos los nombres de archivo .wav por sección (SFX, Q, Z, X, Música)

---

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
