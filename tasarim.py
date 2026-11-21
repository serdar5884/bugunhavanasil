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


def _bulut_maske(w, h, puflar=None):
    """Kabarık bulut silueti: farklı boyutta 6 küre + düz taban."""
    m = Image.new("L", (w * OL, h * OL), 0)
    d = ImageDraw.Draw(m)
    W_, H_ = w * OL, h * OL
    for cx, cy, r in puflar or [(.22, .66, .20), (.38, .50, .24), (.60, .42, .28), (.80, .60, .20), (.50, .66, .26), (.70, .70, .22)]:
        rr = r * H_ * 1.45
        d.ellipse([W_ * cx - rr, H_ * cy - rr * .95, W_ * cx + rr, H_ * cy + rr * .95], fill=255)
    d.rounded_rectangle([W_ * .06, H_ * .60, W_ * .96, H_ * .92], radius=H_ * .16, fill=255)
    return m.resize((w, h), Image.LANCZOS)


@lru_cache(maxsize=256)
def _bulut(w, h, koyu=False):
    """3D bulut: üst-solda parlak, altta koyu; yumuşak gölge, iç gölge ve kenar parıltısı."""
    from PIL import ImageChops
    m = _bulut_maske(w, h)
    if koyu:
        govde = _radyal(w, h, (205, 214, 232), (92, 102, 128), merkez=(.42, .18))
    else:
        govde = _radyal(w, h, (255, 255, 255), (178, 194, 222), merkez=(.40, .20))
    # alt kısımda iç gölge
    alt = Image.new("L", (w, h), 0)
    ImageDraw.Draw(alt).ellipse([-w * .1, h * .62, w * 1.1, h * 1.4], fill=120 if koyu else 80)
    alt = ImageChops.multiply(alt.filter(ImageFilter.GaussianBlur(h * .12)), m)
    govde.paste(Image.new("RGBA", (w, h), (40, 50, 80, 255) if koyu else (120, 140, 185, 255)), (0, 0), alt)
    # üst parlaklık (iki küçük parıltı)
    pm = Image.new("L", (w, h), 0)
    pd = ImageDraw.Draw(pm)
    pd.ellipse([w * .30, h * .14, w * .56, h * .36], fill=150)
    pd.ellipse([w * .52, h * .06, w * .78, h * .26], fill=120)
    pm = ImageChops.multiply(pm.filter(ImageFilter.GaussianBlur(max(2, w // 16))), m)
    govde.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), pm)
    katman = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    golge = Image.new("RGBA", (w, h), (5, 12, 30, 150))
    katman.paste(golge, (24, 34), m)
    katman = katman.filter(ImageFilter.GaussianBlur(max(3, w // 18)))
    katman.paste(govde, (20, 20), m)
    return katman


@lru_cache(maxsize=128)
def _gunes(r):
    """3D güneş: geniş sıcak parıltı, degradeli yuvarlak ışınlar, parlak merkez ve parıltı lekesi."""
    s = int(r * 3.8)
    k = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    c = s / 2
    p = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    pd = ImageDraw.Draw(p)
    pd.ellipse([c - r * 1.6, c - r * 1.6, c + r * 1.6, c + r * 1.6], fill=(255, 150, 20, 90))
    pd.ellipse([c - r * 1.25, c - r * 1.25, c + r * 1.25, c + r * 1.25], fill=(255, 190, 40, 140))
    k.alpha_composite(p.filter(ImageFilter.GaussianBlur(r * .35)))
    # ışınlar (süper örnekleme ile yumuşak)
    S = s * OL
    im = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(im)
    C, R = S / 2, r * OL
    for i in range(12):
        a = math.radians(i * 30 + 15)
        b1, b2 = a - .11, a + .11
        d.polygon([(C + math.cos(b1) * R * 1.12, C + math.sin(b1) * R * 1.12), (C + math.cos(a) * R * 1.52, C + math.sin(a) * R * 1.52),
                   (C + math.cos(b2) * R * 1.12, C + math.sin(b2) * R * 1.12)], fill=255)
        tx, ty = C + math.cos(a) * R * 1.52, C + math.sin(a) * R * 1.52
        d.ellipse([tx - R * .05, ty - R * .05, tx + R * .05, ty + R * .05], fill=255)
    im = im.resize((s, s), Image.LANCZOS)
    isin = _radyal(s, s, (255, 215, 60), (245, 120, 10), merkez=(.5, .5))
    k.paste(isin, (0, 0), im)
    # gövde
    D = int(r * 2.1)
    govde = _radyal(D, D, (255, 252, 200), (248, 150, 15), merkez=(.38, .34))
    m = Image.new("L", (D * OL, D * OL), 0)
    ImageDraw.Draw(m).ellipse([0, 0, D * OL - 1, D * OL - 1], fill=255)
    m = m.resize((D, D), Image.LANCZOS)
    hl = Image.new("L", (D, D), 0)
    ImageDraw.Draw(hl).ellipse([D * .18, D * .12, D * .52, D * .40], fill=170)
    from PIL import ImageChops
    hl = ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(D * .06)), m)
    govde.paste(Image.new("RGBA", (D, D), (255, 255, 240, 255)), (0, 0), hl)
    k.paste(govde, (int(c - D / 2), int(c - D / 2)), m)
    return k


@lru_cache(maxsize=64)
def _damla_res(boy):
    """Parlak mavi damla (süper örneklemeli)."""
    w, h = int(boy * .62), boy
    S = OL
    m = Image.new("L", (w * S, h * S), 0)
    d = ImageDraw.Draw(m)
    r = w * S / 2
    d.ellipse([0, h * S - 2 * r, 2 * r, h * S], fill=255)
    d.polygon([(r, 0), (0.12 * r, h * S - r * 1.1), (1.88 * r, h * S - r * 1.1)], fill=255)
    m = m.resize((w, h), Image.LANCZOS)
    g = _radyal(w, h, (170, 225, 255), (25, 110, 225), merkez=(.35, .55))
    hl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(hl).ellipse([w * .22, h * .50, w * .46, h * .74], fill=230)
    from PIL import ImageChops
    g.paste(Image.new("RGBA", (w, h), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(hl, m))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(g, (0, 0), m)
    return out


@lru_cache(maxsize=64)
def _tane_res(boy):
    """Kar kristali: 6 kol, dallı, hafif mavi parıltılı."""
    S = boy * OL
    im = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(im)
    c, R = S / 2, S * .42
    w = max(2, int(S * .07))
    for k in range(6):
        a = math.radians(k * 60 + 90)
        ux, uy = math.cos(a), math.sin(a)
        d.line([(c, c), (c + ux * R, c + uy * R)], fill=255, width=w)
        for t in (.5, .75):
            px, py = c + ux * R * t, c + uy * R * t
            for s_ in (-1, 1):
                b = a + s_ * math.radians(45)
                d.line([(px, py), (px + math.cos(b) * R * .28, py + math.sin(b) * R * .28)], fill=255, width=max(1, w - 1))
    im = im.resize((boy, boy), Image.LANCZOS)
    out = Image.new("RGBA", (boy + 10, boy + 10), (0, 0, 0, 0))
    glow = Image.new("RGBA", (boy, boy), (150, 200, 255, 200))
    t = Image.new("RGBA", (boy + 10, boy + 10), (0, 0, 0, 0))
    t.paste(glow, (5, 5), im)
    out.alpha_composite(t.filter(ImageFilter.GaussianBlur(2)))
    out.paste(Image.new("RGBA", (boy, boy), (255, 255, 255, 255)), (5, 5), im)
    return out


def _damla(katman, x, y, s):
    dm = _damla_res(max(10, int(s * (.19 if s >= 100 else .26))))  # küçük ikonlarda daha iri
    katman.alpha_composite(dm, (int(x - dm.width / 2), int(y - dm.height / 2)))


def _tane(katman, x, y, s):
    t = _tane_res(max(10, int(s * (.2 if s >= 100 else .28))))
    katman.alpha_composite(t, (int(x - t.width / 2), int(y - t.height / 2)))


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
        b = _bulut(int(s * .84), int(s * .56), koyu)
        yapistir(b, cx - s * .40 + sal - 20, cy - s * .40 - 20)
        for i in range(3):
            x = cx - s * .2 + i * s * .2
            y = cy + s * .26
            if faz is not None:
                k = (faz * 4 + i * .37) % 1
                y = cy + s * .18 + k * s * .16
                x -= k * s * .03
            if tip == "kar" or (tip == "karla_yagmur" and i == 1):
                _tane(katman, x, y + s * .04, s)
            elif tip == "firtina" and i == 1:
                continue
            else:
                _damla(katman, x, y + s * .04, s)
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
