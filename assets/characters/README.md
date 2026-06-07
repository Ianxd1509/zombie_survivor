# PERSONALIZAR PERSONAJES CON IMAGENES

## Personajes jugables

Cada personaje puede tener una imagen personalizada.

### Como poner imagen a un personaje

1. Crea o consigue una imagen PNG (fondo transparente recomendado)
2. Renombrala como: `char_{ID}.png`
3. Colocala en: `assets/characters/`

Ejemplo: para ponerle imagen a Irvin, crea `assets/characters/char_irvin.png`

### IDs de personajes

| Personaje | ID del archivo |
|-----------|---------------|
| Irvin     | `char_irvin.png` |
| Sebas     | `char_sebas.png` |
| Leo       | `char_leo.png` |
| Diego     | `char_diego.png` |
| Usiel     | `char_usiel.png` |
| Obed      | `char_obed.png` |
| Eder      | `char_eder.png` |
| Ian       | `char_ian.png` |
| Randy     | `char_randy.png` |
| Vicente   | `char_vicente.png` |

### Tamaño recomendado

- 34x34 pixeles (se escala automaticamente)
- PNG con canal alfa (fondo transparente)
- El personaje se ve de ~17px de radio en el juego

### Que pasa si no hay imagen

Si no existe el archivo `.png`, el juego dibuja el personaje como un circulo de color con ojos y la inicial (como siempre).