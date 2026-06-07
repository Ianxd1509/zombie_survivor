# HUD

Actualmente todo el HUD se dibuja con texto y rectangulos (src/ui.py).
NO se cargan archivos de imagen. Los .png aqui son decorativos.

## Elementos del HUD por ubicacion en pantalla

Barra superior        - BYTES, BAJAS, LV, SERVER (texto), FPS (esquina der)
Nombre personaje      - abajo de la barra superior
Barra HP              - rectangulo verde->rojo con texto "RAM X/Y"
Barra stamina         - rectangulo azul delgado
Municion              - texto MAG / RESERVE
Barra habilidad Q     - naranja con CD
Barra habilidad Z     - morado con carga (20 kills)
Barra dominio X       - cyan con carga (30 kills) y CD
Minimapa              - 130x130px esq sup der, grid + entidades
Notificaciones        - texto deslizante en la parte superior
Numeros de dano       - texto flotante de colores
Codigos Python        - snippets flotantes (efecto visual)
Ventana habilidades   - overlay de powerups (draw_inventory)
Tienda Vicente/Oscar  - overlay con items, costos, barras
Selector personajes   - tarjetas 5 columnas con stats y color
Menu principal        - opciones con glow y scanlines
Pausa                 - Continuar / Salir
Resultado             - OVER / WIN con estadisticas
Controles             - lista completa de teclas
Input admin           - campo de texto (tecla ,)
Gacha                 - animacion tipo slot machine
Indicador ADMIN MODE  - texto cyan en centro superior

## Archivo existente (decorativo)

assets/hud/hp_icon.png   - icono de vida (no usado en codigo)
assets/hp_icon.png       - copia en raiz de assets/ por compatibilidad
