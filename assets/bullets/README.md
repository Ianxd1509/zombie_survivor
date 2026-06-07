# Balas

Actualmente las balas se renderizan como texto de codigo (Bullet class en src/entities.py).
Ejemplos: "print", "for", "while", "import", etc. segun el arma.

## Tipos de bala

Bala normal       - texto "(x+y)", color celeste (IRVIN)
Bala escopeta     - texto "{}", color segun personaje, 3-5 por disparo
Bala sniper       - texto "lambda", color celeste, 3x dano
Bala perforante   - texto "while", color rojo, perfora 2 enemigos
Balas enemigas    - texto "0x1F", color rojo (EnemyBullet)
Balas de aliados  - texto segun color del aliado (Ally class)
LaserBeam (Eder)  - rayo rojo con glow, 40 dmg, clase LaserBeam

## Armas por personaje

1=auto:   "print" / "var" / "int" (default)
2=shotgun:"{}" / "[]" (disperso, color personaje)
3=sniper: "lambda" (lento, 3x dmg, preciso)
4=pierce: "while" / "for" (perfora pared/enemigos)

## Archivo existente (decorativo)

assets/bullets/code_bullet.png  - no usado
