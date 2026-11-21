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
   - `cartas/catalogo.json` → lo que lee el widget

   Cuando la Action termina (✅ en la pestaña Actions), espera ~5 minutos y recarga la fuente del widget en OBS.
   El widget solo ve las cartas que ya tienen sus imágenes hechas, así que nunca sale una carta "sin imagen" en Discord.

## Cómo crear una serie nueva

1. Crea la carpeta **`cartas/<nombre-de-la-serie>/`** (solo minúsculas, números y guiones, ej. `cartas/neon-city/`).
   En la web de GitHub: *Add file → Create new file* y escribe `cartas/neon-city/serie.json`.
2. Pega en ese `serie.json` el contenido de **`cartas/_plantilla-serie/serie.json`** y rellénalo:

| Campo | Qué es |
|---|---|
| `code` | Código corto y único (sale en las cartas y se usa en Discord: `/cartas serie:NEO`) |
| `name` | Nombre de la serie (arriba en el sobre) |
| `packTitle` / `packSub` | Título y subtítulo del sobre (`<br>` = salto de línea) |
| `redeem` | Nombre **exacto** del canje de la tienda que abre esta serie |
| `cartas` | Las cartas, con los mismos campos que arriba |

3. Sube las ilustraciones a **`cartas/<nombre-de-la-serie>/arte/`**.
4. Crea el canje en la tienda de StreamElements/Twitch con el mismo nombre que pusiste en `redeem`.

Y ya. La Action arma `<nombre>-carta.png` + sus ALT dentro de la carpeta de la serie, y el widget y Discord la reconocen solos
(inventario, `/album`, `/preview`, `/dar`… con la opción `serie`). Para probarla en el stream: `!testsobre NEO`.
Para añadir más cartas a la serie después, solo sumas cartas a su `serie.json` y su arte a su carpeta.

> Las cartas viejas no se tocan: el script solo reescribe imágenes que hizo él mismo (lista en `cartas/bases/generadas.json`).

## Carpetas

- `cartas/bases/` → marcos, paneles, capas de brillo, fuentes y `config.json` (medidas y colores sacados del CSS del widget)
- `cartas/arte/` → ilustraciones de las cartas nuevas de El Vacío
- `cartas/<serie>/` → cada serie nueva (`serie.json`, `arte/`, sus cartas y `alt/`)
- `cartas/_plantilla-serie/` → plantilla para copiar (se ignora)
- `cartas/catalogo.json` → lo escribe la Action; no lo edites a mano
- `herramientas/generar_cartas.py` → arma las cartas (lo corre la Action; también funciona en tu PC con `pip install pillow numpy`)
- `herramientas/hacer_bases.py` + `widget.css` → vuelve a sacar las bases si cambias el diseño de las cartas en el CSS

## Notas

- `numeroInicial` = número de la primera carta nueva (las 49 del widget van primero; en las series nuevas empieza en 1).
- Cada carta se arma **una sola vez** (como las de siempre, el total del pie queda el de ese momento). Se vuelve a armar solo si cambias sus datos o su arte.
- Si algo está mal (falta un arte, nombre repetido, JSON con error), la Action lo avisa con ⚠️ en su resumen y sigue con lo demás.
- `brilloNormal: true` añade el brillo holo también a las cartas normales (las de ahora no lo llevan).
