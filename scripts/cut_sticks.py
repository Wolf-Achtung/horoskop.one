"""Schneidet die vier Wurfstäbe aus den beiden Gruppenfotos frei.

    python3 scripts/cut_sticks.py

Ergebnis in public/assets/material/:
  stab-1 … stab-4          aus staebe-liegend.png (ruhende Stäbe)
  stab-fall-1 … stab-fall-4 aus staebe-fallend.png (im Flug)

Die Vorlagen zeigen alle vier Stäbe nebeneinander auf hellem Grund. Nach
der Hintergrundmaske wird das Bild in Zusammenhangskomponenten zerlegt und
je Stab nur die größte behalten — sonst schleppt ein Freisteller Splitter
vom Nachbarstab mit. Die fliegenden Stäbe werden zusätzlich über ihre
Hauptachse senkrecht gestellt, damit sie in dieselbe Box passen wie die
ruhenden; das Taumeln macht die CSS-Animation.
"""
from collections import deque

import numpy as np
from PIL import Image, ImageFilter

SRC = "assets-src/material"
OUT = "public/assets/material"


def hintergrund_maske(im: Image.Image) -> Image.Image:
    """Heller, unbunter Studiogrund fällt weg; der Stab bleibt."""
    a = np.asarray(im).astype(np.float32) / 255.0
    mx, mn = a.max(2), a.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    bg = ((mx >= 200 / 255.0) & (sat <= 0.12)) | (mn >= 245 / 255.0)

    alpha = Image.fromarray(((~bg) * 255).astype(np.uint8))
    alpha = alpha.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
    alpha = alpha.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
    return alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))


def komponenten(solid: np.ndarray):
    """Zusammenhängende Flächen per Breitensuche, größte zuerst."""
    h, w = solid.shape
    lab = np.zeros((h, w), np.int32)
    found = []
    for sy in range(h):
        for sx in range(w):
            if not solid[sy, sx] or lab[sy, sx]:
                continue
            cid = len(found) + 1
            q = deque([(sy, sx)])
            lab[sy, sx] = cid
            px = 0
            while q:
                y, x = q.popleft()
                px += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and solid[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = cid
                        q.append((ny, nx))
            found.append((px, cid))
    found.sort(reverse=True)
    return lab, found


def schneide(quelle: str, praefix: str, *, aufrichten: bool, box: tuple[int, int]):
    im = Image.open(f"{SRC}/{quelle}").convert("RGB")
    alpha = hintergrund_maske(im)
    lab, found = komponenten(np.asarray(alpha) > 128)
    print(f"{quelle}: {len(found)} Flächen, größte {[p for p, _ in found[:6]]}")

    rgba = np.dstack([np.asarray(im), np.asarray(alpha)])
    # Nur die vier größten Flächen sind Stäbe; alles andere sind Splitter.
    staebe = found[:4]
    # Von links nach rechts, damit die Nummerierung stabil bleibt.
    mitten = []
    for px, cid in staebe:
        xs = np.where(lab == cid)[1]
        mitten.append((xs.mean(), cid))
    mitten.sort()

    for i, (_, cid) in enumerate(mitten, start=1):
        m = lab == cid
        part = rgba.copy()
        part[..., 3] = np.where(m, part[..., 3], 0)
        img = Image.fromarray(part, "RGBA")

        if aufrichten:
            ys, xs = np.where(m)
            pts = np.stack([xs - xs.mean(), ys - ys.mean()])
            evals, evecs = np.linalg.eigh(np.cov(pts))
            vx, vy = evecs[:, np.argmax(evals)]
            img = img.rotate(np.degrees(np.arctan2(vy, vx)) - 90,
                             resample=Image.BICUBIC, expand=True)

        crop = img.crop(img.split()[-1].getbbox())
        crop.thumbnail(box, Image.LANCZOS)
        crop.save(f"{OUT}/{praefix}{i}.webp", "WEBP", quality=88, method=6)
        print(f"  {praefix}{i}.webp  {crop.size}")


schneide("staebe-liegend.png", "stab-", aufrichten=False, box=(120, 300))
schneide("staebe-fallend.png", "stab-fall-", aufrichten=True, box=(120, 320))
