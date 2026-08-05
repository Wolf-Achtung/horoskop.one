"""Erzeugt das Teilbild der Mondlese als Stillleben aus den echten Material-Fotos.

    python3 scripts/make_og_image.py

Ergebnis: public/assets/og-mondlese.png (1200x630) — die Wortmarke auf
weißer Galeriewand, darum herum Feder, Orakelknochen, Wurzel und Rinde
angeschnitten am Rand, darunter Wurfstäbe, Astragal und die fünf
Pigmentsteine wie nach einem Wurf auf dem Tisch.

Die Schriften (IM Fell English, Cormorant Garamond) liegen nicht im Repo.
Wer das Bild neu bauen will, legt sie als TTF unter scripts/fonts/ ab
oder setzt MONDLESE_FONT_DIR; ohne sie bricht das Skript mit einem
Hinweis ab, statt eine falsche Schrift zu setzen.
"""
import math
import os
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1200, 630
MAT = "public/assets/material"
SRC = "assets-src/material"
OUT = "public/assets/og-mondlese.jpg"
FONT_DIR = os.environ.get("MONDLESE_FONT_DIR", "scripts/fonts")

WALL = (251, 250, 247)
INK = (43, 36, 26)
SUB = (74, 62, 44)

def freisteller(name: str, l_min=0.58, sat_max=0.18) -> Image.Image:
    """Stein aus dem Studiofoto lösen.

    Die Studiofotos der Steine haben einen sauberen hellen Grund mit weichem
    Schlagschatten — hier trägt ein Flutfüllen vom Bildrand am weitesten: der
    Schatten ist mit dem Rand verbunden und wird mitgenommen, während die
    Steinkante als harte Stufe stehen bleibt. (Bei den Motiven mit Papierbogen
    im Bild ginge das schief; die sind deshalb bereits freigestellt abgelegt.)
    """
    im = Image.open(f"{SRC}/{name}.png").convert("RGB")
    im.thumbnail((500, 500), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32) / 255.0
    mx, mn = a.max(2), a.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    hell = (a.mean(2) >= l_min) & (sat <= sat_max)

    h, w = hell.shape
    bg = np.zeros((h, w), bool)
    q = deque()
    rand = ([(0, x) for x in range(w)] + [(h - 1, x) for x in range(w)]
            + [(y, 0) for y in range(h)] + [(y, w - 1) for y in range(h)])
    for y, x in rand:
        if hell[y, x] and not bg[y, x]:
            bg[y, x] = True
            q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and hell[ny, nx] and not bg[ny, nx]:
                bg[ny, nx] = True
                q.append((ny, nx))

    alpha = Image.fromarray(((~bg) * 255).astype(np.uint8))
    alpha = alpha.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.0))

    rgba = Image.merge("RGBA", (*im.split(), alpha))
    return rgba.crop(alpha.getbbox())


def ground() -> Image.Image:
    """Weiße Galeriewand mit einer Ahnung von Kalkstruktur."""
    base = Image.new("RGB", (W, H), WALL)
    kalk = Image.open(f"{MAT}/grund-kalk.webp").convert("RGB")
    s = max(W / kalk.width, H / kalk.height)
    kalk = kalk.resize((int(kalk.width * s) + 1, int(kalk.height * s) + 1),
                       Image.LANCZOS).crop((0, 0, W, H))
    kalk = ImageEnhance.Color(ImageEnhance.Brightness(kalk).enhance(1.3)).enhance(0.45)
    return Image.blend(base, kalk, 0.17)


def place(canvas, img, *, height=None, angle=0.0, center=None, topleft=None,
          shadow=(7, 12, 14, 0.32)):
    """Legt ein Freisteller-Objekt mit weichem Schlagschatten auf die Wand.

    Licht kommt in der ganzen Fotostrecke von links oben, der Schatten also
    immer nach rechts unten.
    """
    im = img if isinstance(img, Image.Image) else Image.open(f"{MAT}/{img}").convert("RGBA")
    if height:
        im = im.resize((max(1, round(im.width * height / im.height)), height), Image.LANCZOS)
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)

    x, y = ((center[0] - im.width // 2, center[1] - im.height // 2)
            if center else topleft)

    dx, dy, blur, opacity = shadow
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    tint = Image.new("RGBA", im.size, (38, 30, 20, 255))
    tint.putalpha(im.split()[-1])
    sh.paste(tint, (x + dx, y + dy), tint)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    sh.putalpha(sh.split()[-1].point(lambda v: int(v * opacity)))
    canvas.alpha_composite(sh)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.paste(im, (x, y), im)
    canvas.alpha_composite(layer)


def tracked(draw, xy, text, font, fill, tracking=0.0):
    """Gesperrter, zentrierter Text — PIL kennt kein letter-spacing."""
    widths = [draw.textlength(c, font=font) for c in text]
    x = xy[0] - (sum(widths) + tracking * (len(text) - 1)) / 2
    for c, w in zip(text, widths):
        draw.text((x, xy[1]), c, font=font, fill=fill)
        x += w + tracking


def font(name, size):
    path = os.path.join(FONT_DIR, name)
    if not os.path.exists(path):
        sys.exit(f"Schrift fehlt: {path}\n"
                 f"IM Fell English und Cormorant Garamond als TTF nach "
                 f"{FONT_DIR}/ legen (oder MONDLESE_FONT_DIR setzen).")
    return ImageFont.truetype(path, size)


f_mark = font("IMFellEnglish-Italic.ttf", 96)
f_sub = font("CormorantGaramond-MediumItalic.ttf", 37)

canvas = ground().convert("RGBA")

# --- Rand: angeschnittene Objekte rahmen die freie Mitte -------------
place(canvas, "objekt-feder.webp", height=178, angle=-31, topleft=(46, -34),
      shadow=(5, 9, 10, 0.26))
place(canvas, "orakelknochen.webp", height=408, angle=10, topleft=(1002, -92),
      shadow=(8, 14, 16, 0.30))
place(canvas, "objekt-wurzel.webp", height=392, angle=-5, topleft=(-142, 302),
      shadow=(9, 15, 18, 0.28))
place(canvas, "objekt-rinde.webp", height=178, angle=16, topleft=(1078, 486),
      shadow=(7, 12, 14, 0.28))

# --- Unten: die Partie liegt auf dem Tisch ---------------------------
for i, (ang, cx, cy) in enumerate(
        [(-72, 372, 494), (-84, 430, 524), (-67, 500, 498), (-79, 556, 530)], start=1):
    place(canvas, f"stab-{i}.webp", height=188, angle=ang, center=(cx, cy),
          shadow=(6, 11, 12, 0.30))
place(canvas, "astragal.webp", height=70, angle=-16, center=(632, 552),
      shadow=(5, 9, 10, 0.30))

stones = ["stein-ocker", "stein-graphit", "stein-rost", "stein-moos", "stein-umbra"]
for i, s in enumerate(stones):
    t = i / (len(stones) - 1)
    place(canvas, freisteller(s), height=80, angle=-22 + i * 14,
          center=(722 + int(t * 300), 512 + int(math.sin(t * math.pi) * -30)),
          shadow=(5, 10, 11, 0.32))

# --- Wortmarke in der freien Mitte -----------------------------------
draw = ImageDraw.Draw(canvas)
tracked(draw, (W // 2, 176), "DIE MONDLESE", f_mark, INK, tracking=7)
draw.line([(W // 2 - 216, 314), (W // 2 + 216, 314)], fill=(43, 36, 26, 80), width=2)
tracked(draw, (W // 2, 330), "Ein Zug pro Tag · ein Brett pro Mondmonat", f_sub,
        SUB, tracking=1.1)

canvas.convert("RGB").save(OUT, "JPEG", quality=88, optimize=True, progressive=True)
print(f"{OUT} · {W}×{H} · {os.path.getsize(OUT) // 1024} KB")
