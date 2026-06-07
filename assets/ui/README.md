# UI

Actualmente toda la interfaz se dibuja con texto y rectangulos pygame (src/ui.py).
NO se cargan archivos de imagen. Los .png aqui son decorativos.

## Pantallas de UI (todas en src/ui.py)

MainMenu          - titulo "PYTHON COMPAS" con glow, 4 opciones con scanlines
CharSelector      - tarjetas 5 columnas, 10 personajes, stats, color, candado
ControlsScreen    - lista completa de teclas: WASD/mov, Q/Z/X hab, F/tienda, etc.
PauseScreen       - "PAUSA" + Continuar / Salir
ResultScreen      - "SERVER OVER" o "VICTORIA" con estadisticas finales
draw_hud()        - todos los elementos de HUD in-game
draw_shop()       - tienda Vicente (grid 4 col) y Oscar (lista vertical)
draw_gacha()      - animacion de gacha con nombres rotando
draw_inventory()  - powerups activos del jugador

## Paleta de colores

Fondo     (0,0,0) negro
Texto     (0,255,65) verde neon
Brillo    (180,150,55) dorado opaco
Oro       (255,200,50)
Rojo      (255,50,50) peligro
Azul      (50,150,255) info
Gris      (0,180,50) deshabilitado

## Archivos existentes (decorativos)

assets/ui/logo.png        - no usado
assets/ui/cursor.png      - no usado
assets/ui/sel_frame.png   - no usado
