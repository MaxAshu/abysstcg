# Abyss TCG · Sobres del Vacío

## Cómo añadir una carta nueva

1. Sube la ilustración a **`cartas/arte/`** (por ejemplo `cartas/arte/neri-pijama.png`).
2. Añade la carta a **`cartas/cartas-nuevas.json`**, dentro de `"cartas"`:

```json
{
  "name": "Neri, Pijama de Dragona",
  "r": 2,
  "type": "Alma - Dragona",
  "flavor": "Hasta las dragonas necesitan dormir.",
  "artist": "CarlPrix",
  "file": "neri-pijama.png",
  "pos": "50% 30%"
}
```

| Campo | Qué es |
|---|---|
| `name` | Nombre de la carta |
| `r` | Rareza: 0 Eco · 1 Recuerdo · 2 Reliquia · 3 Presagio · 4 Eterna (full art) |
| `type` | Línea de tipo |
| `flavor` | Texto de la caja (máx. 4 líneas, si no, se corta con …) |
| `artist` | Ilustrador (sale como "Ilus. …") |
| `file` | Nombre del archivo en `cartas/arte/` |
| `pos` | (opcional) Encuadre, como en el widget. Por defecto `50% 20%` (Eterna `50% 22%`) |
| `fit` | (opcional) `"contain"` para que se vea la imagen completa |
| `pixel` | (opcional) `true` para pixel art nítido |

3. Listo. La **Action "Generar cartas nuevas"** arma sola:
   - `cartas/<nombre-de-la-carta>.png` → la que se ve en Discord
   - `cartas/alt/<nombre-de-la-carta>-<acabado>.png` → las 5 versiones ALT

   El widget lee `cartas-nuevas.json` al cargar, así que la carta ya puede salir en los sobres (recarga la fuente del navegador en OBS).

> Las cartas viejas no se tocan: el script solo reescribe imágenes que hizo él mismo (lista en `cartas/bases/generadas.json`).

## Carpetas

- `cartas/bases/` → marcos, paneles, capas de brillo, fuentes y `config.json` (medidas y colores sacados del CSS del widget)
- `cartas/arte/` → ilustraciones de las cartas nuevas
- `herramientas/generar_cartas.py` → arma las cartas (lo corre la Action; también funciona en tu PC con `pip install pillow numpy`)
- `herramientas/hacer_bases.py` + `widget.css` → vuelve a sacar las bases si cambias el diseño de las cartas en el CSS

## Notas

- `numeroInicial` = número de la primera carta nueva (las 49 del widget van primero). El total del pie se recalcula solo con cada carta nueva.
- `brilloNormal: true` añade el brillo holo también a las cartas normales (las de ahora no lo llevan).
