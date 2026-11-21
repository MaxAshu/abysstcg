"""Arma las imágenes de las cartas NUEVAS (para Discord) usando las bases.

  cartas/cartas-nuevas.json      -> cartas nuevas de El Vacío (nombre, rareza, tipo, texto, artista, archivo de arte)
  cartas/arte/<archivo>          -> la ilustración de cada carta nueva de El Vacío
  cartas/<serie>/serie.json      -> una serie nueva completa (datos del sobre + sus cartas)
  cartas/<serie>/arte/<archivo>  -> las ilustraciones de esa serie
  cartas/bases/                  -> marcos, paneles, capas de brillo y fuentes (los hace hacer_bases.py)

Salida (los mismos nombres que ya buscan el widget y el Worker):
  cartas/<nombre-de-la-carta>.png               carta normal
  cartas/alt/<nombre-de-la-carta>-<acabado>.png versiones ALT (shiny, cosmic, chrome, antique, neon)
  cartas/<serie>/<nombre>-carta.png  y  cartas/<serie>/alt/<nombre>-carta-<acabado>.png
  cartas/catalogo.json                          lo que lee el widget (solo cartas con sus imágenes ya hechas)
Cada carta se arma una sola vez; se vuelve a armar solo si cambias sus datos o su arte.

Nunca pisa una imagen que no haya hecho este script (las cartas viejas quedan intactas).
Uso:  pip install pillow numpy  &&  python herramientas/generar_cartas.py
"""
import json, os, re, sys, unicodedata
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
CARTAS = RAIZ / 'cartas'
BASES = CARTAS / 'bases'
ARTE = CARTAS / 'arte'
DATOS = CARTAS / 'cartas-nuevas.json'
REGISTRO = BASES / 'generadas.json'            # lista de imágenes hechas por este script (las únicas que puede reescribir)
RAREZAS = ['eco', 'recuerdo', 'reliquia', 'presagio', 'eterna']
ACABADOS = ['shiny', 'cosmic', 'chrome', 'antique', 'neon']
CFG = json.loads((BASES / 'config.json').read_text(encoding='utf-8'))
S = CFG['escala']
W, H = CFG['tam']


def slug(n):
    n = unicodedata.normalize('NFD', str(n))
    n = ''.join(ch for ch in n if unicodedata.category(ch) != 'Mn').lower()
    return re.sub(r'^-+|-+$', '', re.sub(r'[^a-z0-9]+', '-', n))


def cinzel(peso):
    return 'Cinzel-Bold.ttf' if int(peso or 700) > 600 else 'Cinzel-Medium.ttf'


def fuente(nombre, px):
    return ImageFont.truetype(str(BASES / 'fuentes' / nombre), max(1, round(px)))


# ---------------- colores y efectos CSS ----------------
def color(c):
    c = c.strip()
    m = re.match(r'rgba?\(([^)]*)\)', c)
    if m:
        v = [float(x) for x in re.split(r'[,\s/]+', m.group(1).strip()) if x]
        return (int(v[0]), int(v[1]), int(v[2]), int(round((v[3] if len(v) > 3 else 1) * 255)))
    m = re.match(r'color\(srgb ([^)]*)\)', c)
    if m:
        v = [float(x) for x in re.split(r'[\s/]+', m.group(1).strip()) if x]
        return tuple(int(round(x * 255)) for x in v[:3]) + (int(round((v[3] if len(v) > 3 else 1) * 255)),)
    if c.startswith('#'):
        h = c[1:]
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    return (0, 0, 0, 0)


COLOR_RE = r'(rgba?\([^)]*\)|color\([^)]*\)|#[0-9a-fA-F]{6})'


def sombras(css):
    """'rgb(0,0,0) 0px 1px 2px, ...' -> [(color, dx, dy, blur)]"""
    if not css or css == 'none':
        return []
    out = []
    for m in re.finditer(COLOR_RE + r'\s+(-?[\d.]+)px\s+(-?[\d.]+)px(?:\s+([\d.]+)px)?', css):
        out.append((color(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4) or 0)))
    return out


def filtro_css(im, f):
    """sepia / contrast / saturate / brightness, como el filter: de CSS"""
    if not f or f == 'none':
        return im
    a = np.asarray(im.convert('RGBA')).astype(np.float32) / 255
    rgb, al = a[..., :3], a[..., 3:]
    for fn, val in re.findall(r'(\w+)\(([\d.]+)\)', f):
        v = float(val)
        if fn == 'sepia':
            M = np.array([[.393 + .607 * (1 - v), .769 - .769 * (1 - v), .189 - .189 * (1 - v)],
                          [.349 - .349 * (1 - v), .686 + .314 * (1 - v), .168 - .168 * (1 - v)],
                          [.272 - .272 * (1 - v), .534 - .534 * (1 - v), .131 + .869 * (1 - v)]])
            rgb = rgb @ M.T
        elif fn == 'saturate':
            M = np.array([[.213 + .787 * v, .715 - .715 * v, .072 - .072 * v],
                          [.213 - .213 * v, .715 + .285 * v, .072 - .072 * v],
                          [.213 - .213 * v, .715 - .715 * v, .072 + .928 * v]])
            rgb = rgb @ M.T
        elif fn == 'contrast':
            rgb = (rgb - .5) * v + .5
        elif fn == 'brightness':
            rgb = rgb * v
        rgb = np.clip(rgb, 0, 1)
    return Image.fromarray((np.concatenate([rgb, al], -1) * 255).round().astype(np.uint8), 'RGBA')


def _soft(b, s):
    d = np.where(b <= .25, ((16 * b - 12) * b + 4) * b, np.sqrt(b))
    return np.where(s <= .5, b - (1 - 2 * s) * b * (1 - b), b + (2 * s - 1) * (d - b))


MODOS = {
    'normal': lambda b, s: s,
    'screen': lambda b, s: b + s - b * s,
    'multiply': lambda b, s: b * s,
    'overlay': lambda b, s: np.where(b <= .5, 2 * b * s, 1 - 2 * (1 - b) * (1 - s)),
    'hard-light': lambda b, s: np.where(s <= .5, 2 * b * s, 1 - 2 * (1 - b) * (1 - s)),
    'soft-light': _soft,
}


def fundir(lienzo, capa, modo, opacidad):
    """Aplica una capa con su modo de fusión (como mix-blend-mode) sobre el lienzo."""
    b = np.asarray(lienzo).astype(np.float32) / 255
    s = np.asarray(capa.convert('RGBA')).astype(np.float32) / 255
    a = s[..., 3:] * opacidad
    rgb = b[..., :3] * (1 - a) + MODOS.get(modo, MODOS['normal'])(b[..., :3], s[..., :3]) * a
    alfa = b[..., 3:] + a * (1 - b[..., 3:]) if modo == 'normal' else b[..., 3:]
    return Image.fromarray((np.clip(np.concatenate([rgb, alfa], -1), 0, 1) * 255).round().astype(np.uint8), 'RGBA')


def mascara_redonda(w, h, r):
    k = 4
    m = Image.new('L', (w * k, h * k), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=r * k, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def posicion(pos, defecto):
    p = re.findall(r'(-?[\d.]+)%', pos or defecto) or re.findall(r'(-?[\d.]+)%', defecto)
    return (float(p[0]) / 100, float(p[1] if len(p) > 1 else 50) / 100)


def encajar(arte, w, h, fit, pos, pixel):
    """object-fit (cover / contain) + object-position"""
    aw, ah = arte.size
    k = max(w / aw, h / ah) if fit != 'contain' else min(w / aw, h / ah)
    nw, nh = max(1, round(aw * k)), max(1, round(ah * k))
    im = arte.resize((nw, nh), Image.NEAREST if pixel else Image.LANCZOS)
    ox, oy = round((w - nw) * pos[0]), round((h - nh) * pos[1])
    capa = im.crop((-ox, -oy, -ox + w, -oy + h))             # fuera de la imagen queda transparente
    return capa


def caja(r):
    x, y, w, h = r
    return round(x * S), round(y * S), round(w * S), round(h * S)


# ---------------- texto ----------------
def ancho(txt, f, esp):
    return f.getlength(txt) + esp * max(0, len(txt) - 1) if txt else 0


def recortar(txt, f, esp, maxw):
    if ancho(txt, f, esp) <= maxw:
        return txt
    while txt and ancho(txt + '…', f, esp) > maxw:
        txt = txt[:-1]
    return txt.rstrip() + '…'


def escribir(lienzo, x, y, txt, f, col, esp=0, sombra='none'):
    """Texto con espaciado entre letras y sombras/brillos (text-shadow). (x, y) = esquina superior de la línea."""
    if not txt:
        return
    capa = Image.new('RGBA', lienzo.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    def pintar(dd, ox, oy, c):
        if esp:
            for i, ch in enumerate(txt):
                dd.text((x + ox + f.getlength(txt[:i]) + esp * i, y + oy), ch, font=f, fill=c)
        else:
            dd.text((x + ox, y + oy), txt, font=f, fill=c)
    for c, dx, dy, blur in reversed(sombras(sombra)):
        sc = Image.new('RGBA', lienzo.size, (0, 0, 0, 0))
        pintar(ImageDraw.Draw(sc), dx * S, dy * S, c)
        if blur:
            sc = sc.filter(ImageFilter.GaussianBlur(blur * S / 2))
        capa.alpha_composite(sc)
    pintar(d, 0, 0, col)
    lienzo.alpha_composite(capa)


def linea_y(f, cy):
    asc, desc = f.getmetrics()
    return cy - (asc + desc) / 2


def px(v, base):
    return float(re.sub('px', '', v)) * S if v and v.endswith('px') else 0


def fondo_set(w, h, css):
    m = re.match(r'linear-gradient\(90deg,\s*(.*)\)$', css.strip())
    if not m:
        return Image.new('RGBA', (w, h), color(css))
    cols = [color(c) for c in re.findall(COLOR_RE, m.group(1))]
    g = np.zeros((h, w, 4), np.float32)
    xs = np.linspace(0, 1, w)
    for ch in range(4):
        g[..., ch] = np.interp(xs, np.linspace(0, 1, len(cols)), [c[ch] for c in cols])[None, :]
    return Image.fromarray(g.round().astype(np.uint8), 'RGBA')


def textos(lienzo, v, c, num, total, codigo, estudio, alt):
    # nombre
    t = v['titulo']
    largo = len(c['name']) > 22
    f = fuente(cinzel(t.get('peso')), t['size'] * (14 / 17 if largo else 1) * S)
    esp = px(t['espaciado'], 0) * (14 / 17 if largo else 1)
    x0, x1 = t['x0'] * S, t['x1'] * S
    nombre = recortar(c['name'], f, esp, x1 - x0)
    escribir(lienzo, x0, linea_y(f, t['cy'] * S), nombre, f, color(t['color']), esp, t['sombra'])
    # tipo
    t = v['tipo']
    f = fuente(cinzel(t.get('peso')), t['size'] * S)
    esp = px(t['espaciado'], 0)
    tipo = recortar(c.get('type') or RAREZAS[c['r']].capitalize(), f, esp, (t['x1'] - t['x0']) * S)
    escribir(lienzo, t['x0'] * S, linea_y(f, t['cy'] * S), tipo, f, color(t['color']), esp, t['sombra'])
    # texto de ambientación (máx. 4 líneas, como -webkit-line-clamp)
    t = v['texto']
    f = fuente('CormorantGaramond-SemiBold.ttf', t['size'] * S)
    maxw, alto = (t['x1'] - t['x0']) * S, t['alto'] * S
    lineas, cur = [], ''
    for pal in str(c.get('flavor') or '').split():
        prueba = (cur + ' ' + pal).strip()
        if f.getlength(prueba) <= maxw or not cur:
            cur = prueba
        else:
            lineas.append(cur); cur = pal
    if cur:
        lineas.append(cur)
    if len(lineas) > t['lineas']:
        lineas = lineas[:t['lineas']]
        lineas[-1] = recortar(lineas[-1] + ' …', f, 0, maxw - f.getlength('…'))
    asc, desc = f.getmetrics()
    for i, ln in enumerate(lineas):
        escribir(lienzo, t['x0'] * S, t['y0'] * S + i * alto + (alto - asc - desc) / 2, ln, f, color(t['color']), 0, t['sombra'])
    # pie: artista · recuadro de set · estudio
    p = v['pie']
    f = fuente('Inter-Regular.ttf', p['size'] * S)
    esp = p['size'] * S * .03
    y = linea_y(f, p['cy'] * S)
    if c.get('artist'):
        escribir(lienzo, p['x0'] * S, y, 'Ilus. ' + c['artist'], f, color(p['color']), esp, p['sombra'])
    if estudio:
        txt = '© 2026 ' + estudio
        escribir(lienzo, p['x1'] * S - ancho(txt, f, esp), y, txt, f, color(p['color']), esp, p['sombra'])
    st = v['set']
    fb = fuente('Inter-Bold.ttf', p['size'] * S)
    a = f'{codigo} {num}/{total} '
    b = '★'
    cola = ' ALT' if alt else ''
    tw = ancho(a, fb, esp) + ancho(b, fb, esp) + ancho(cola, fb, esp) + esp
    bw, bh = round(tw + 2 * 6 * S + 2 * S), round((p['size'] * 1.21 + 2 + 2) * S)
    bx, by = round((p['x0'] + p['x1']) / 2 * S - bw / 2), round(p['cy'] * S - bh / 2)
    m = mascara_redonda(bw, bh, st['radio'] * S)
    borde = Image.new('RGBA', (bw, bh), color(st['borde']))
    lienzo.paste(borde, (bx, by), Image.fromarray((np.asarray(m).astype(np.float32) * color(st['borde'])[3] / 255).astype(np.uint8)))
    interior = mascara_redonda(bw - 2 * S, bh - 2 * S, max(0, st['radio'] - 1) * S)
    fondo = fondo_set(bw - 2 * S, bh - 2 * S, st['fondo'])
    al = (np.asarray(interior).astype(np.float32) / 255 * np.asarray(fondo)[..., 3]).astype(np.uint8)
    fondo.putalpha(Image.fromarray(al))
    lienzo.alpha_composite(fondo, (bx + S, by + S))
    ty = linea_y(fb, p['cy'] * S)
    x = bx + 7 * S
    escribir(lienzo, x, ty, a, fb, color(st['color']), esp); x += ancho(a, fb, esp) + esp
    escribir(lienzo, x, ty, b, fb, color(st['estrella'])); x += ancho(b, fb, esp) + esp
    escribir(lienzo, x, ty, cola, fb, color(st['color']), esp)


# ---------------- armado ----------------
_cache = {}


def img(ruta):
    if ruta not in _cache:
        _cache[ruta] = Image.open(BASES / ruta).convert('RGBA')
    return _cache[ruta]


def armar(c, arte, fin, num, total, codigo, estudio, brillo=False):
    v = CFG['variantes'][f'alt/{fin}/{RAREZAS[c["r"]]}' if fin else f'normal/{RAREZAS[c["r"]]}']
    arte = filtro_css(arte, v['filtroArte'])
    lienzo = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    lienzo.alpha_composite(img(v['marco']))
    if v['full']:                                              # Eterna: full art en todo el interior
        x, y, w, h = caja(v['inner'])
        capa = Image.new('RGBA', (w, h), (0, 0, 0, 255))
        capa.alpha_composite(encajar(arte, w, h, 'cover', posicion(c.get('pos'), '50% 22%'), c.get('pixel')))
        r = v['innerRadio']
    else:                                                      # resto: ilustración dentro del recuadro
        x, y, w, h = caja(v['artwin'])
        capa = encajar(arte, w, h, c.get('fit'), posicion(c.get('pos'), '50% 20%'), c.get('pixel'))
        r = v['artwinRadio']
    m = np.asarray(mascara_redonda(w, h, round(r * S))).astype(np.float32) / 255
    capa.putalpha(Image.fromarray((np.asarray(capa)[..., 3] * m).astype(np.uint8)))
    lienzo.alpha_composite(capa, (x, y))
    def capas():
        nonlocal lienzo
        for k in v['capas']:
            if not fin and not brillo:             # cartas normales: sin holo, igual que las que ya existen
                continue
            lienzo = fundir(lienzo, img(k['archivo']), k['modo'], k['opacidad'])
    if fin:          # ALT: los efectos van debajo de los paneles
        capas(); lienzo.alpha_composite(img(v['paneles']))
    else:            # normal: el brillo holo pasa por encima de los paneles
        lienzo.alpha_composite(img(v['paneles'])); capas()
    textos(lienzo, v, c, num, total, codigo, estudio, bool(fin))
    return lienzo


def aviso(msg):
    """Advertencia visible en la pestaña Actions de GitHub (no detiene el resto)."""
    print(f'::warning::{msg}' if os.environ.get('GITHUB_ACTIONS') else f'  ! {msg}')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(f'- ⚠️ {msg}\n')


def huella(*partes):
    import hashlib
    h = hashlib.sha1()
    for x in partes:
        h.update(x if isinstance(x, bytes) else json.dumps(x, ensure_ascii=False, sort_keys=True).encode())
    return h.hexdigest()[:16]


CAMPOS = ('name', 'r', 'type', 'flavor', 'artist', 'file', 'pos', 'fit', 'pixel', 'dfile')
HUELLA_BASES = huella((BASES / 'config.json').read_bytes())


def procesar(lista, carpeta, arte_dir, sufijo, codigo, inicio, estudio, brillo, registro, etiqueta):
    """Arma las cartas de una serie. Devuelve (cartas listas para el widget, errores)."""
    total = inicio - 1 + len(lista)
    listas, errores, usados = [], 0, set()
    for i, c in enumerate(lista):
        c = dict(c)
        nombre = c.get('name')
        try:
            c['r'] = max(0, min(4, int(c.get('r', 0))))
        except (TypeError, ValueError):
            c['r'] = 0
        if not nombre or not c.get('file'):
            aviso(f'[{etiqueta}] carta {i + 1}: falta "name" o "file"'); errores += 1; continue
        ruta_arte = arte_dir / c['file']
        if not ruta_arte.exists():
            aviso(f'[{etiqueta}] {nombre}: falta el arte {ruta_arte.relative_to(RAIZ).as_posix()} (súbelo y se generará)'); continue
        s = c.get('dfile', '').rsplit('.', 1)[0] or (slug(nombre) + sufijo)
        if s in usados:
            aviso(f'[{etiqueta}] {nombre}: hay dos cartas con el mismo nombre'); errores += 1; continue
        usados.add(s)
        num = str(inicio + i).zfill(2)
        firma = huella({k: c.get(k) for k in CAMPOS}, ruta_arte.read_bytes(), HUELLA_BASES, codigo, num, estudio, brillo)
        principal = carpeta / f'{s}.png'
        if principal.exists() and principal.relative_to(CARTAS).as_posix() not in registro:
            aviso(f'[{etiqueta}] {nombre}: ya existe {principal.relative_to(CARTAS).as_posix()} (una carta vieja). Cámbiale el nombre o usa "dfile".')
            errores += 1; continue
        salidas = [(None, principal)] + [(f, carpeta / 'alt' / f'{s}-{f}.png') for f in ACABADOS]
        arte, hechos = None, 0
        for fin, out in salidas:
            rel = out.relative_to(CARTAS).as_posix()
            if out.exists() and rel not in registro:
                aviso(f'[{etiqueta}] {rel} ya existe y no lo hizo este script: no lo toco'); continue
            if out.exists() and registro.get(rel) == firma:
                continue                                         # ya está hecha y no cambió nada
            if arte is None:
                arte = Image.open(ruta_arte).convert('RGBA')
            out.parent.mkdir(parents=True, exist_ok=True)
            armar(c, arte, fin, num, str(total).zfill(2), codigo, estudio, brillo).save(out, optimize=True)
            registro[rel] = firma; hechos += 1
        if hechos:
            print(f'  ✓ [{etiqueta}] {nombre} ({RAREZAS[c["r"]]}) -> {hechos} imágenes')
        rel_carpeta = carpeta.relative_to(CARTAS).as_posix()
        pre = '' if rel_carpeta == '.' else rel_carpeta + '/'
        lista_widget = {k: v for k, v in c.items() if k not in ('file', 'dfile')}
        listas.append({**lista_widget, 'num': int(num), 'img': f'{pre}arte/{c["file"]}', 'dimg': f'{pre}{s}.png'})
    return listas, errores


def leer(ruta):
    try:
        return json.loads(ruta.read_text(encoding='utf-8'))
    except Exception as e:
        aviso(f'{ruta.relative_to(RAIZ).as_posix()} no es JSON válido: {e}')
        return None


def main():
    reg = json.loads(REGISTRO.read_text(encoding='utf-8')) if REGISTRO.exists() else {}
    registro = {k: '' for k in reg} if isinstance(reg, list) else reg
    errores = 0
    catalogo = {'actualizado': None, 'vac': [], 'series': []}

    # 1) Cartas nuevas de El Vacío
    d = leer(DATOS) if DATOS.exists() else None
    if d:
        listas, e = procesar(d.get('cartas', []), CARTAS, ARTE, '', d.get('serie', 'VAC'), int(d.get('numeroInicial', 1)),
                             d.get('estudio', 'MYTH Studio'), bool(d.get('brilloNormal')), registro, d.get('serie', 'VAC'))
        catalogo['vac'], errores = listas, errores + e

    # 2) Series nuevas: cada carpeta cartas/<carpeta>/ con un serie.json (las que empiezan por _ se ignoran)
    codigos = {str((d or {}).get('serie', 'VAC')).upper()}
    for sj in sorted(CARTAS.glob('*/serie.json')):
        carpeta = sj.parent
        if carpeta.name.startswith(('_', '.')) or carpeta.name in ('arte', 'alt', 'bases'):
            continue
        if carpeta.name != slug(carpeta.name):
            aviso(f'carpeta "{carpeta.name}": usa solo minúsculas, números y guiones (ej. "{slug(carpeta.name)}")'); errores += 1; continue
        s = leer(sj)
        if not s:
            errores += 1; continue
        codigo = str(s.get('code') or carpeta.name[:6]).upper()
        if codigo in codigos:
            aviso(f'serie "{carpeta.name}": el código {codigo} ya lo usa otra serie'); errores += 1; continue
        codigos.add(codigo)
        listas, e = procesar(s.get('cartas', []), carpeta, carpeta / 'arte', '-carta', codigo, int(s.get('numeroInicial', 1)),
                             s.get('estudio', 'MYTH Studio'), bool(s.get('brilloNormal')), registro, codigo)
        errores += e
        catalogo['series'].append({'folder': carpeta.name, 'code': codigo, 'name': s.get('name') or carpeta.name.upper(),
                                   'packTitle': s.get('packTitle') or 'SOBRE', 'packSub': s.get('packSub') or '',
                                   'redeem': s.get('redeem') or None, 'total': int(s.get('numeroInicial', 1)) - 1 + len(s.get('cartas', [])), 'cards': listas})
        print(f'  · serie {codigo} ({carpeta.name}): {len(listas)} cartas listas')

    # 3) Catálogo que lee el widget: solo cartas que ya tienen sus imágenes hechas
    ruta = CARTAS / 'catalogo.json'
    viejo = leer(ruta) if ruta.exists() else None
    if not viejo or {k: v for k, v in viejo.items() if k != 'actualizado'} != {k: v for k, v in catalogo.items() if k != 'actualizado'}:
        import datetime
        catalogo['actualizado'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
        ruta.write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding='utf-8')
    REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    print('Listo.')


if __name__ == '__main__':
    main()
