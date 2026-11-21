"""Genera las BASES de las cartas (marcos, paneles y capas de brillo) a partir del CSS real del widget.

Solo hace falta volver a correrlo si cambias el diseño de las cartas en widget.css.
Necesita Chrome/Chromium y Playwright:   pip install playwright pillow  &&  playwright install chromium
Uso:   python herramientas/hacer_bases.py            (escribe en cartas/bases/)

Por cada variante (5 rarezas normales + 5 acabados ALT x 5 rarezas) guarda:
  marco    -> todo lo que no es texto ni panel (en Eterna el centro queda transparente para el full art)
  paneles  -> barra de título, franja de tipo, caja de texto, insignia y etiqueta del acabado
  capas    -> brillo holo, destello y efectos ALT, cada uno con su modo de fusión (se aplican sobre el arte)
y escribe cartas/bases/config.json con las medidas y colores que usa generar_cartas.py.
"""
import hashlib, io, json, os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / 'cartas' / 'bases'
CSS = (Path(__file__).parent / 'widget.css').read_text(encoding='utf-8')
CSS = CSS.split('\n', 1)[1] if CSS.startswith('@import') else CSS          # sin Google Fonts: usamos las fuentes locales
FUENTES = (OUT / 'fuentes').as_uri()

RAREZAS = ['eco', 'recuerdo', 'reliquia', 'presagio', 'eterna']
RAR_COLOR = ['#9a917e', '#d3ccbb', '#e6ad2e', '#ffc933', '#fff0b8']
RAR_HOLO = [0, 0.3, 0.6, 0.85, 1]
ACABADOS = {'shiny': ('Shiny', '#ffd24a'), 'cosmic': ('Cósmico', '#8a7bff'), 'chrome': ('Cromada', '#c9d3df'),
            'antique': ('Archivo Antiguo', '#c9a468'), 'neon': ('Neón', '#39ffe0')}
ESCALA = 2                                                   # 320x448 -> 640x896 (igual que las cartas actuales)
TILT = {'--bx': '70%', '--by': '56%', '--gx': '68%', '--gy': '48%'}   # inclinación "congelada" del brillo

PAGINA = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:'Cinzel';src:url('%(f)s/Cinzel-Medium.ttf');font-weight:100 600}
@font-face{font-family:'Cinzel';src:url('%(f)s/Cinzel-Bold.ttf');font-weight:601 900}
@font-face{font-family:'Cormorant Garamond';src:url('%(f)s/CormorantGaramond-SemiBold.ttf');font-weight:100 900}
%(css)s
html,body{margin:0;background:transparent!important}
#host{position:absolute;left:0;top:0}
.slot{opacity:1!important;position:absolute;left:0;top:0}
.back{display:none!important}
.front,.card,.tilt{transform:none!important}
/* modos de captura */
body.m-marco .tbar,body.m-marco .tline,body.m-marco .tbox,body.m-marco .foot,body.m-marco .holo,body.m-marco .glare,body.m-marco .fx,body.m-marco .finb{display:none!important}
body.m-marco .artwin img,body.m-marco .fullart .artbg img{display:none!important}
body.m-marco .fullart,body.m-marco .fullart .artbg{background:transparent!important}
body.m-paneles .front,body.m-paneles .inner{background:transparent!important;box-shadow:none!important;animation:none!important;filter:none!important}
body.m-paneles .artbg,body.m-paneles .holo,body.m-paneles .glare,body.m-paneles .fx,body.m-paneles .foot{display:none!important}
body.m-capa .front,body.m-capa .inner{background:transparent!important;box-shadow:none!important;animation:none!important;filter:none!important}
body.m-capa .inner>*{visibility:hidden!important}
body.m-capa .capa,body.m-capa .capa *{visibility:visible!important;mix-blend-mode:normal!important}
body.m-capa .fx.capa::before,body.m-capa .fx.capa::after,body.m-capa .fx.capa i{visibility:hidden!important}
body.m-capa.p-before .fx.capa::before,body.m-capa.p-after .fx.capa::after{visibility:visible!important;mix-blend-mode:normal!important}
body.m-capa.p-stars .fx.capa i{visibility:visible!important}
body.m-capa .holo.capa,body.m-capa .glare.capa{opacity:1!important}
.m-paneles .tbar b,.m-paneles .tline span,.m-paneles .tbox p{visibility:hidden!important}
</style></head><body><div id="host"></div></body></html>"""

JS_HALO = """
const PETAL='M0 -100 Q5 -55 30 -31 A43 43 0 0 0 -30 -31 Q-5 -55 0 -100Z', OFF='rgba(255,255,255,.13)';
function haloSVG(lit=4,core=true,ring=false,cls=''){let s=`<svg class="${cls}" viewBox="-108 -108 216 216"><defs><radialGradient id="gHalo" cx="50%" cy="50%" r="60%"><stop offset="0" stop-color="#fffbe6"/><stop offset=".45" stop-color="#ffd24a"/><stop offset="1" stop-color="#b8891a"/></radialGradient></defs>`;
 for(let i=0;i<4;i++) s+=`<path d="${PETAL}" transform="rotate(${i*90})" fill="${i<lit?'url(#gHalo)':OFF}"/>`;
 s+=`<circle r="16" fill="${core?'url(#gHalo)':OFF}"/>`; if(ring) s+=`<circle r="43" fill="none" stroke="#fff3c4" stroke-width="3" opacity=".9"/>`; return s+'</svg>';}
const FXP=[[10,18,13],[80,12,9],[64,40,16],[20,56,8],[88,60,12],[38,30,7],[52,10,10],[8,74,9],[72,72,7],[30,82,11],[92,30,7],[46,64,8],[16,40,6],[58,86,9]];
window.build=(r,fin,finName,accent,holo,tilt)=>{
  const full=r===4, el=document.createElement('div');
  el.className=`slot rar-${r}${fin?' alt fin-'+fin:''}`;
  el.style.setProperty('--accent',accent); el.style.setProperty('--holo',holo); el.style.setProperty('--rn',r);
  for(const k in tilt) el.style.setProperty(k,tilt[k]);
  const art=full?'<img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" alt="">':'<div class="artwin"><img alt="" src="data:image/gif;base64,R0lGODlhAQABAAAAACw="></div>';
  const fx=fin?`<div class="fx">${FXP.map(([x,y,z],k)=>`<i style="--x:${x}%;--y:${y}%;--z:${z}px;--d:${((k*0.37)%2.6).toFixed(2)}s"></i>`).join('')}</div><div class="finb">${finName}</div>`:'';
  el.innerHTML=`<div class="tilt"><div class="card"><div class="face back"></div><div class="face front"><div class="inner ${full?'fullart':''}">
   <div class="artbg">${art}</div>
   <div class="tbar"><b>Nombre de prueba</b><span class="badge">${haloSVG(Math.min(4,r+1),r>=3,r===4)}</span></div>
   <div class="tline"><span>Tipo</span></div><div class="tbox"><p>Texto</p></div>
   <div class="foot"><span>Ilus.</span><span class="setb">VAC 01/01 <i>★</i></span><span>©</span></div>
   <div class="holo"></div><div class="glare"></div>${fx}</div></div></div></div>`;
  const h=document.getElementById('host'); h.innerHTML=''; h.appendChild(el);
  /* congela las animaciones: estrellas a mitad de su parpadeo, sin giro de color ni parpadeo neón */
  document.getAnimations().forEach(a=>{const n=a.animationName||''; if(n==='twk'){a.pause();a.currentTime=1300;} else a.cancel();});
};
window.medir=()=>{
  const q=s=>document.querySelector(s), R=e=>{const b=e.getBoundingClientRect();return [b.left,b.top,b.width,b.height];};
  const cs=(s,p)=>getComputedStyle(q(s),p||null);
  const tbar=q('.tbar'), tb=cs('.tbar'), badge=q('.badge');
  const tl=q('.tline'), tlc=cs('.tline'), tbx=q('.tbox'), tbc=cs('.tbox'), pp=cs('.tbox p'), ft=q('.foot'), fc=cs('.foot');
  const cap=(sel,p)=>{const c=cs(sel,p);return {display:c.display,visibility:c.visibility,mode:c.mixBlendMode,opacity:+c.opacity,content:c.content};};
  const fx=q('.fx');
  return {
    inner:R(q('.inner')), innerRadio:parseFloat(cs('.inner').borderTopLeftRadius),
    artwin:q('.artwin')?R(q('.artwin')):null, artwinRadio:q('.artwin')?parseFloat(cs('.artwin').borderTopLeftRadius):0,
    filtroArte:cs(q('.artwin')?'.artwin img':'.artbg img').filter,
    titulo:{x0:R(tbar)[0]+parseFloat(tb.borderLeftWidth)+parseFloat(tb.paddingLeft), x1:R(badge)[0]-parseFloat(getComputedStyle(badge).marginLeft),
            cy:R(tbar)[1]+(R(tbar)[3]-parseFloat(tb.borderBottomWidth))/2, size:parseFloat(cs('.tbar b').fontSize), peso:cs('.tbar b').fontWeight, color:cs('.tbar b').color,
            sombra:cs('.tbar b').textShadow, espaciado:cs('.tbar b').letterSpacing},
    tipo:{x0:R(tl)[0]+parseFloat(tlc.paddingLeft), x1:R(tl)[0]+R(tl)[2]-parseFloat(tlc.paddingRight), cy:R(tl)[1]+R(tl)[3]/2,
          size:parseFloat(tlc.fontSize), peso:tlc.fontWeight, color:tlc.color, sombra:tlc.textShadow, espaciado:tlc.letterSpacing},
    texto:{x0:R(tbx)[0]+parseFloat(tbc.paddingLeft), x1:R(tbx)[0]+R(tbx)[2]-parseFloat(tbc.paddingRight), y0:R(tbx)[1]+parseFloat(tbc.paddingTop),
           size:parseFloat(pp.fontSize), alto:parseFloat(pp.lineHeight), color:pp.color, sombra:pp.textShadow, lineas:4},
    pie:{x0:R(ft)[0], x1:R(ft)[0]+R(ft)[2], cy:R(ft)[1]+R(ft)[3]/2, size:parseFloat(fc.fontSize), color:fc.color, sombra:fc.textShadow},
    capas:{holo:cap('.holo'), glare:cap('.glare'), fxBefore:fx?cap('.fx','::before'):null, fxAfter:fx?cap('.fx','::after'):null}
  };
};
"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for d in ('normal', 'alt', 'capas'):
        (OUT / d).mkdir(exist_ok=True)
    variantes = [(f'normal/{RAREZAS[r]}', r, None) for r in range(5)]
    variantes += [(f'alt/{fin}/{RAREZAS[r]}', r, fin) for fin in ACABADOS for r in range(5)]
    hechas, vistos, config = {}, {}, {'escala': ESCALA, 'tam': [320 * ESCALA, 448 * ESCALA], 'variantes': {}}

    def guardar(img_bytes, nombre):
        im = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
        if im.getbbox() is None or im.getchannel('A').getextrema()[1] == 0:
            return None
        h = hashlib.md5(im.tobytes()).hexdigest()
        if h in vistos:
            return vistos[h]
        ruta = OUT / f'{nombre}.png'
        ruta.parent.mkdir(parents=True, exist_ok=True)
        im.save(ruta, optimize=True)
        vistos[h] = f'{nombre}.png'
        return vistos[h]

    exe = os.environ.get('CHROME') or None
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        page = b.new_page(viewport={'width': 320, 'height': 448}, device_scale_factor=ESCALA)
        tmp = OUT / '_pagina.html'
        tmp.write_text(PAGINA % {'f': FUENTES, 'css': CSS}, encoding='utf-8')
        page.goto(tmp.as_uri())
        page.add_script_tag(content=JS_HALO)
        page.evaluate('document.fonts.ready')
        for nombre, r, fin in variantes:
            finName, finColor = ACABADOS.get(fin, (None, None))
            page.evaluate('([r,f,n,a,h,t])=>build(r,f,n,a,h,t)', [r, fin, finName, finColor or RAR_COLOR[r], RAR_HOLO[r], TILT])
            page.evaluate("document.body.className=''")
            page.evaluate('document.fonts.ready')
            m = page.evaluate('medir()')
            m['set'] = page.evaluate("""()=>{const s=document.querySelector('.setb'),c=getComputedStyle(s),ci=getComputedStyle(s.querySelector('i'));
              return {fondo:c.backgroundImage!=='none'?c.backgroundImage:c.backgroundColor,borde:c.borderTopColor,color:c.color,estrella:ci.color,radio:parseFloat(c.borderTopLeftRadius)}}""")
            v = {'rareza': r, 'acabado': fin, 'full': r == 4, **m}
            page.evaluate("document.body.className='m-marco'")
            v['marco'] = guardar(page.screenshot(omit_background=True), f'{nombre}-marco')
            page.evaluate("document.body.className='m-paneles'")
            v['paneles'] = guardar(page.screenshot(omit_background=True), f'{nombre}-paneles')
            capas = []
            orden = [('fxBefore', '.fx', 'p-before'), ('fxAfter', '.fx', 'p-after'), ('stars', '.fx', 'p-stars'), ('holo', '.holo', ''), ('glare', '.glare', '')]
            for clave, sel, extra in orden:
                info = m['capas'].get(clave) if clave != 'stars' else ({'display': 'block', 'visibility': 'visible', 'mode': 'normal', 'opacity': 1} if fin in ('shiny', 'cosmic') else None)
                if not info or info['display'] == 'none' or info.get('content') == 'none' and clave.startswith('fx'):
                    continue
                if clave == 'holo' and info['opacity'] == 0:
                    continue
                tipo = clave.replace('fxBefore', 'fx').replace('fxAfter', 'fx2').replace('stars', 'estrellas')
                nom_capa = f'capas/{tipo}-{fin or "normal"}'          # las capas solo dependen del acabado
                if nom_capa in hechas:
                    ruta = hechas[nom_capa]
                    if ruta:
                        capas.append({'capa': clave, 'archivo': ruta, 'modo': info['mode'], 'opacidad': 1 if clave in ('fxBefore', 'fxAfter', 'stars') else info['opacity']})
                    continue
                page.evaluate(f"""()=>{{document.querySelectorAll('.capa').forEach(e=>e.classList.remove('capa'));
                  const e=document.querySelector('{sel}'); e && e.classList.add('capa'); document.body.className='m-capa {extra}';}}""")
                ruta = hechas[nom_capa] = guardar(page.screenshot(omit_background=True), nom_capa)
                if ruta:
                    capas.append({'capa': clave, 'archivo': ruta, 'modo': info['mode'], 'opacidad': 1 if clave in ('fxBefore', 'fxAfter', 'stars') else info['opacity']})
            v['capas'] = capas
            config['variantes'][nombre] = v
            print('ok', nombre, len(capas), 'capas')
        tmp.unlink()
        b.close()
    (OUT / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding='utf-8')
    print('Listo:', len(vistos), 'imágenes en', OUT)


if __name__ == '__main__':
    main()
