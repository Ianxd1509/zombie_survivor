# Efectos Visuales

Actualmente todos los efectos se dibujan con circulos pygame (src/effects.py).
NO se cargan archivos de imagen. Los .png en esta carpeta son decorativos.

Para usar imagenes personalizadas:
1. Colocar .png aqui
2. Modificar Particle.draw() en src/effects.py para blitear la imagen

## Efectos generados por codigo

Particula generica      - pygame.draw.circle(), color segun contexto
Particula fuego         - colores naranja/rojo (explosiones, habilidades)
Particula dorada        - bytes recolectados, levelup
Chispa                  - circulos pequenos 1-3px, colores claros
Decal/mancha            - circulos semitransparentes en el suelo
Escudo                  - circulo pulsante alrededor del player (shield_timer)
Brillo curacion         - particulas verdes de brainrot/heal
LaserBeam               - rayo rojo con glow (src/entities.py, clase LaserBeam)
Particulas de dominio   - circulos de color segun personaje, borde del dominio
Lluvia de dominio       - lineas verticales azules (Irvin: Ciclo For)
Particulas de congelar  - cristales azules (Ian: Deadlock)
