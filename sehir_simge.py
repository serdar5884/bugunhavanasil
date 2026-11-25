"""İllere özel sade simge silüetleri (kodla çizilir, telif sorunu yok). Şimdilik Sivas:
Kongre Binası, Çifte Minareli Medrese, Kangal köpeği."""
from PIL import Image, ImageDraw, ImageFilter

_ONBELLEK = {}
K = 4  # yüksek çözünürlükte çizip küçült (yumuşak kenar)


def _kongre(d, x, y, s):
    """Sivas Kongre Binası: iki katlı, kırma çatılı, sıra pencereli taş bina + bayrak direği."""
    w, h = 230 * s, 120 * s
    zx, zy = x, y - h
    d.polygon([(zx - 8 * s, zy), (zx + w / 2, zy - 42 * s), (zx + w + 8 * s, zy)], fill=255)  # çatı
    d.rectangle([zx, zy, zx + w, y], fill=255)
    d.rectangle([zx - 6 * s, zy + h * .48, zx + w + 6 * s, zy + h * .54], fill=255)  # kat silmesi
    for kat in range(2):
        for i in range(7):
            px = zx + 14 * s + i * (w - 28 * s) / 6.6
            py = zy + 12 * s + kat * h * .5
            d.rounded_rectangle([px, py, px + 18 * s, py + 34 * s], radius=8 * s, fill=0)  # kemerli pencere
    d.rectangle([zx + w / 2 - 15 * s, y - 42 * s, zx + w / 2 + 15 * s, y], fill=0)  # kapı
    d.rectangle([zx + w / 2 - 2 * s, zy - 110 * s, zx + w / 2 + 2 * s, zy - 38 * s], fill=255)  # direk
    return (zx + w / 2 + 2 * s, zy - 110 * s)


def _medrese(d, x, y, s):
    """Çifte Minareli Medrese: yüksek taç kapı + üstünde iki yivli minare, yanlarda alçak duvar."""
    import math
    w, h = 130 * s, 150 * s
    d.rectangle([x - 30 * s, y - 62 * s, x + w + 30 * s, y], fill=255)  # yan duvarlar
    d.rectangle([x, y - h, x + w, y], fill=255)                          # taç kapı bloğu
    cx, kg, ust = x + w / 2, 28 * s, y - 92 * s
    d.rectangle([cx - kg, ust, cx + kg, y], fill=0)                      # kapı nişi
    nok = []  # sivri kemer: iki yay
    for i in range(21):
        t = math.radians(180 - i * 60 / 20)
        nok.append((cx + kg + 2 * kg * math.cos(t), ust - 2 * kg * math.sin(t) * .62))
    for i in range(21):
        t = math.radians(i * 60 / 20)
        nok.append((cx - kg + 2 * kg * math.cos(math.radians(60) - t + math.radians(0)) , ust - 2 * kg * math.sin(math.radians(60) - t) * .62))
    d.polygon(nok, fill=0)
    d.rectangle([x + 8 * s, y - h + 8 * s, x + w - 8 * s, y - h + 14 * s], fill=0)  # yazı kuşağı çizgisi
    for mx in (x + 16 * s, x + w - 16 * s):  # minareler
        d.rectangle([mx - 10 * s, y - h - 125 * s, mx + 10 * s, y - h], fill=255)
        d.rectangle([mx - 15 * s, y - h - 78 * s, mx + 15 * s, y - h - 70 * s], fill=255)  # şerefe
        d.polygon([(mx - 10 * s, y - h - 125 * s), (mx, y - h - 155 * s), (mx + 10 * s, y - h - 125 * s)], fill=255)
        for j in (-5, 0, 5):  # yivler
            d.line([(mx + j * s, y - h - 120 * s), (mx + j * s, y - h - 84 * s)], fill=0, width=max(1, int(1.5 * s)))
            d.line([(mx + j * s, y - h - 64 * s), (mx + j * s, y - h - 8 * s)], fill=0, width=max(1, int(1.5 * s)))


KANGAL = [(20, 60), (35, 52), (70, 50), (110, 52), (130, 46), (140, 33), (150, 22), (165, 17), (179, 21), (190, 31),
          (201, 37), (204, 47), (196, 55), (179, 57), (166, 63), (161, 79), (159, 96), (158, 148), (146, 150), (144, 110),
          (137, 108), (135, 148), (124, 150), (123, 108), (82, 110), (52, 106), (49, 125), (52, 148), (41, 150), (37, 128),
          (34, 110), (30, 120), (32, 148), (21, 150), (18, 122), (12, 95), (11, 76), (14, 66)]


def _kangal(d, x, y, s):
    """Kangal köpeği (yandan, ayakta): iri gövde, kalın boyun, sırtına kıvrık kuyruk."""
    d.polygon([(x + px * s, y - (150 - py) * s) for px, py in KANGAL], fill=255)
    d.arc([x - 6 * s, y - 150 * s + 16 * s, x + 40 * s, y - 150 * s + 64 * s], start=150, end=400, fill=255, width=int(12 * s))  # kuyruk
    d.polygon([(x + 151 * s, y - 124 * s), (x + 163 * s, y - 126 * s), (x + 162 * s, y - 100 * s), (x + 153 * s, y - 104 * s)],
              outline=0, width=max(1, int(2 * s)))  # sarkık kulak
    d.ellipse([x + 172 * s, y - 126 * s, x + 178 * s, y - 120 * s], fill=0)  # göz


def sivas(gen=720, yuk=330):
    """Beyaz silüet (RGBA). Saydam arka plan; alpha ile soluk basılır."""
    if ("Sivas", gen, yuk) in _ONBELLEK:
        return _ONBELLEK[("Sivas", gen, yuk)]
    W, H = gen * K, yuk * K
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    s = K
    zemin = H - 6 * K
    direk = _kongre(d, 12 * K, zemin, s)
    _medrese(d, 300 * K, zemin, s)
    _kangal(d, 500 * K, zemin, s)
    d.rectangle([0, zemin, W, H], fill=255)  # zemin çizgisi
    m = m.resize((gen, yuk), Image.LANCZOS)
    img = Image.new("RGBA", (gen, yuk), (255, 255, 255, 0))
    img.putalpha(m)
    # küçük Türk bayrağı (direkte)
    bx, by = direk[0] / K, direk[1] / K
    b = Image.new("RGBA", (gen, yuk), (0, 0, 0, 0))
    bd = ImageDraw.Draw(b)
    bd.rectangle([bx, by, bx + 34, by + 22], fill=(227, 10, 23, 255))
    bd.ellipse([bx + 6, by + 4, bx + 20, by + 18], fill=(255, 255, 255, 255))
    bd.ellipse([bx + 9, by + 5.5, bx + 21, by + 16.5], fill=(227, 10, 23, 255))
    bd.regular_polygon((bx + 25, by + 11, 4), 5, rotation=-18, fill=(255, 255, 255, 255))
    img.alpha_composite(b)
    _ONBELLEK[("Sivas", gen, yuk)] = img
    return img


SIMGELER = {"Sivas": sivas}
