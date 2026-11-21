"""
Yeni kart tasarımı yardımcıları:
- ikon3d: parlak, gölgeli, degradeli 3D hava ikonları (güneş, bulut, yağmur, kar, fırtına, sis)
- cam_kart: buzlu cam görünümlü kart (yarı saydam, üstte ışık, ince kenar)
- takvim_ikon: tarih satırı için küçük takvim simgesi
Gövdeler (güneş, bulut) önbelleğe alınır; animasyonda sadece damla/taneler her karede yeniden çizilir.
"""
import math
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter

OL = 3  # kenar yumuşatma için büyük çizip küçültme oranı


def _dikey_degrade(w, h, ust, alt):
    g = Image.new("RGBA", (1, h))
    for y in range(h):
        k = y / max(1, h - 1)
        g.putpixel((0, y), tuple(int(ust[i] * (1 - k) + alt[i] * k) for i in range(3)) + (255,))
    return g.resize((w, h))


def _radyal(w, h, ic, dis, merkez=(0.4, 0.38)):
    g = Image.new("RGBA", (w, h))
    px = g.load()
    cx, cy = w * merkez[0], h * merkez[1]
    R = math.hypot(max(cx, w - cx), max(cy, h - cy))
    for y in range(h):
        for x in range(w):
            k = min(1, math.hypot(x - cx, y - cy) / R)
            px[x, y] = tuple(int(ic[i] * (1 - k) + dis[i] * k) for i in range(3)) + (255,)
    return g


def _bulut_maske(w, h):
    """Bulut silueti (w×h kutusuna oturan yuvarlak hatlar)."""
    m = Image.new("L", (w * OL, h * OL), 0)
    d = ImageDraw.Draw(m)
    W_, H_ = w * OL, h * OL
    for cx, cy, r in [(.30, .62, .26), (.52, .42, .34), (.74, .60, .24), (.50, .66, .28)]:
        d.ellipse([W_ * (cx - r), H_ * (cy - r * 1.25), W_ * (cx + r), H_ * (cy + r * 1.25)], fill=255)
    d.rounded_rectangle([W_ * .08, H_ * .58, W_ * .94, H_ * .90], radius=H_ * .16, fill=255)
    return m.resize((w, h), Image.LANCZOS)


@lru_cache(maxsize=256)
def _bulut(w, h, koyu=False):
    m = _bulut_maske(w, h)
    ust, alt = ((150, 160, 182), (78, 86, 108)) if koyu else ((255, 255, 255), (190, 204, 226))
    govde = _dikey_degrade(w, h, ust, alt)
    katman = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    golge = Image.new("RGBA", (w, h), (10, 20, 40, 120))
    katman.paste(golge, (22, 30), m)
    katman = katman.filter(ImageFilter.GaussianBlur(max(3, w // 22)))
    katman.paste(govde, (20, 20), m)
    # üst-sol parlaklık
    pm = Image.new("L", (w, h), 0)
    ImageDraw.Draw(pm).ellipse([w * .22, h * .12, w * .62, h * .48], fill=110)
    pm = pm.filter(ImageFilter.GaussianBlur(max(2, w // 14)))
    from PIL import ImageChops
    pm = ImageChops.multiply(pm, m)
    katman.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (20, 20), pm)
    return katman


@lru_cache(maxsize=128)
def _gunes(r):
    s = int(r * 3.8)
    k = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    c = s / 2
    # parıltı
    p = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(p).ellipse([c - r * 1.35, c - r * 1.35, c + r * 1.35, c + r * 1.35], fill=(255, 170, 30, 120))
    k.alpha_composite(p.filter(ImageFilter.GaussianBlur(r * .3)))
    # ışınlar
    d = ImageDraw.Draw(k)
    for i in range(10):
        a = math.radians(i * 36)
        b1, b2 = a - .13, a + .13
        d.polygon([(c + math.cos(b1) * r * 1.08, c + math.sin(b1) * r * 1.08), (c + math.cos(a) * r * 1.42, c + math.sin(a) * r * 1.42),
                   (c + math.cos(b2) * r * 1.08, c + math.sin(b2) * r * 1.08)], fill=(255, 176, 30, 255))
    # gövde: radyal degrade
    D = int(r * 2)
    govde = _radyal(D, D, (255, 240, 140), (255, 150, 20))
    m = Image.new("L", (D * OL, D * OL), 0)
    ImageDraw.Draw(m).ellipse([0, 0, D * OL - 1, D * OL - 1], fill=255)
    m = m.resize((D, D), Image.LANCZOS)
    k.paste(govde, (int(c - r), int(c - r)), m)
    return k


def _damla(d, x, y, s, renk=((150, 215, 255), (40, 130, 235))):
    """Damla: üstü sivri, altı yuvarlak."""
    r = s * .055
    d.polygon([(x, y - r * 2.2), (x - r, y), (x + r, y)], fill=renk[1])
    d.ellipse([x - r, y - r, x + r, y + r], fill=renk[1])
    d.ellipse([x - r * .45, y - r * .6, x - r * .05, y - r * .15], fill=renk[0])


def _tane(d, x, y, s):
    """Kar tanesi (6 kollu)."""
    R = s * .06
    for k in range(3):
        a = math.radians(k * 60 + 90)
        d.line([(x - math.cos(a) * R, y - math.sin(a) * R), (x + math.cos(a) * R, y + math.sin(a) * R)],
               fill=(255, 255, 255, 255), width=max(2, int(s * .022)))
    d.ellipse([x - R * .3, y - R * .3, x + R * .3, y + R * .3], fill=(225, 238, 255, 255))


def ikon3d(img, tip, cx, cy, s, faz=None):
    """img (RGB ya da RGBA) üzerine (cx, cy) merkezli, s boyutunda 3D hava ikonu çizer."""
    katman = Image.new("RGBA", img.size, (0, 0, 0, 0))

    def yapistir(parca, x, y):
        katman.alpha_composite(parca, (int(x), int(y)))

    sal = math.sin(2 * math.pi * faz) * s * .025 if faz is not None else 0
    if tip in ("gunes", "az_bulut"):
        r = int(s * (.3 if tip == "gunes" else .22))
        g = _gunes(r)
        gx, gy = (cx, cy) if tip == "gunes" else (cx - s * .14, cy - s * .12)
        if faz is not None and tip == "gunes":  # ışınlar yavaşça döner
            g = g.rotate(-faz * 36, resample=Image.BICUBIC)
        yapistir(g, gx - g.width / 2, gy - g.height / 2)
        if tip == "az_bulut":
            b = _bulut(int(s * .68), int(s * .44))
            yapistir(b, cx - s * .26 + sal - 20, cy - s * .06 - 20)
    elif tip == "bulut":
        b2 = _bulut(int(s * .55), int(s * .36), True)
        yapistir(b2, cx - s * .40 - sal - 20, cy - s * .30 - 20)
        b = _bulut(int(s * .78), int(s * .50))
        yapistir(b, cx - s * .36 + sal - 20, cy - s * .18 - 20)
    elif tip in ("yagmur", "firtina", "kar", "karla_yagmur"):
        koyu = tip in ("firtina", "yagmur")
        b = _bulut(int(s * .80), int(s * .52), koyu)
        yapistir(b, cx - s * .40 + sal - 20, cy - s * .40 - 20)
        d = ImageDraw.Draw(katman)
        for i in range(3):
            x = cx - s * .2 + i * s * .2
            y = cy + s * .26
            if faz is not None:
                k = (faz * 4 + i * .37) % 1
                y = cy + s * .18 + k * s * .16
                x -= k * s * .03
            if tip == "kar" or (tip == "karla_yagmur" and i == 1):
                _tane(d, x, y + s * .04, s)
            elif tip == "firtina" and i == 1:
                continue
            else:
                _damla(d, x, y + s * .04, s)
        if tip == "firtina":
            x, y = cx + s * .02, cy + s * .06
            pts = [(x + s * .06, y), (x - s * .07, y + s * .2), (x + s * .01, y + s * .2), (x - s * .05, y + s * .38),
                   (x + s * .12, y + s * .14), (x + s * .03, y + s * .14), (x + s * .09, y)]
            p = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(p).polygon(pts, fill=(255, 170, 0, 200))
            katman.alpha_composite(p.filter(ImageFilter.GaussianBlur(s * .03)))
            ImageDraw.Draw(katman).polygon(pts, fill=(255, 214, 40, 255), outline=(255, 150, 0, 255))
    elif tip == "sis":
        b = _bulut(int(s * .66), int(s * .40), True)
        yapistir(b, cx - s * .33 - 20, cy - s * .38 - 20)
        d = ImageDraw.Draw(katman)
        for i in range(3):
            y = cy + s * .08 + i * s * .12
            off = (s * .06 if i % 2 else 0) + sal
            d.rounded_rectangle([cx - s * .36 + off, y, cx + s * .30 + off, y + s * .06], radius=s * .03,
                                fill=(220, 228, 240, 235))
    if img.mode == "RGBA":
        img.alpha_composite(katman)
    else:
        img.paste(katman, (0, 0), katman)


def cam_kart(img, box, r=26):
    """Buzlu cam kart: yarı saydam koyu dolgu, üstte ışık, ince parlak kenar, hafif gölge."""
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    k = Image.new("RGBA", img.size, (0, 0, 0, 0))
    g = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    ImageDraw.Draw(g).rounded_rectangle([20, 26, w + 20, h + 26], radius=r, fill=(0, 0, 0, 70))
    k.alpha_composite(g.filter(ImageFilter.GaussianBlur(10)), (x0 - 20, y0 - 20))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    dolgu = _dikey_degrade(w, h, (70, 86, 118), (34, 44, 68))
    dolgu.putalpha(m.point(lambda v: v * 150 // 255))
    k.alpha_composite(dolgu, (x0, y0))
    d = ImageDraw.Draw(k)
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, outline=(255, 255, 255, 70), width=2)
    d.line([(x0 + r, y0 + 2), (x1 - r, y0 + 2)], fill=(255, 255, 255, 90), width=2)  # üst ışık çizgisi
    if img.mode == "RGBA":
        img.alpha_composite(k)
    else:
        img.paste(k, (0, 0), k)


def takvim_ikon(d, x, y, s, renk=(255, 255, 255, 220)):
    w = max(2, int(s * .09))
    d.rounded_rectangle([x, y + s * .12, x + s, y + s], radius=s * .16, outline=renk, width=w)
    d.line([(x, y + s * .36), (x + s, y + s * .36)], fill=renk, width=w)
    for i in (.28, .72):
        d.line([(x + s * i, y), (x + s * i, y + s * .24)], fill=renk, width=w)
    for r_ in range(2):
        for c_ in range(3):
            cx, cy = x + s * (.25 + c_ * .25), y + s * (.56 + r_ * .2)
            d.ellipse([cx - s * .04, cy - s * .04, cx + s * .04, cy + s * .04], fill=renk)
