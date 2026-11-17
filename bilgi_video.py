#!/usr/bin/env python3
"""
"10 saniyede" meteoroloji bilgi videoları (1080x1920, 30 fps) + aynı konudan kaydırmalı gönderi görselleri (4:5).
Konular bilgi_konulari.py içinde; animasyonlar Pillow ile çizilir, müzik muzik/ klasöründen.

Kullanım:
  python bilgi_video.py --konu lodos_poyraz --cikti yayin/bilgi     -> reels.mp4 + 01..N.jpg + caption.txt
  python bilgi_video.py --siradaki --cikti yayin/bilgi              -> bilgi_durum.json'daki sıradaki konu
"""
import argparse, glob, json, math, os, random, subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from hava_bot import font, HESAP
from bilgi_konulari import KONULAR

W, H, FPS = 1080, 1920, 30
SARI, LACI = (255, 205, 0), (14, 24, 46)
GECIS = 0.35
YAZI_HIZI = 0.5  # altyazının tamamı sahne süresinin ilk yarısında belirir, kalan yarıda okunur
DURUM = "bilgi_durum.json"

GOK = {
    "ilik": ((70, 40, 60), (215, 120, 70)), "soguk": ((20, 35, 70), (110, 150, 200)), "gece": ((10, 14, 35), (40, 45, 80)),
    "firtina": ((18, 20, 38), (60, 60, 90)), "gunes": ((30, 120, 220), (130, 200, 250)), "bulutlu": ((70, 85, 110), (150, 160, 180)),
    "sis": ((140, 150, 160), (200, 205, 210)), "yagmur": ((35, 50, 75), (90, 105, 130)), "kar": ((110, 140, 180), (200, 215, 235)),
}


def gradient(ust, alt):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(ust[i] * (1 - k) + alt[i] * k) for i in range(3)))
    return img


_zeminler = {}


def zemin(gok):
    if gok not in _zeminler:
        _zeminler[gok] = gradient(*GOK[gok])
    return _zeminler[gok].copy().convert("RGBA")


def bulut(d, cx, cy, s, ton=225, golge=150):
    toplar = [(-.9, .1, .55), (-.45, -.25, .7), (.1, -.38, .8), (.65, -.15, .65), (1.05, .15, .5), (.1, .15, .75)]
    for dx, dy, r in toplar:
        d.ellipse([cx + (dx - r) * s, cy + (dy - r) * s + s * .12, cx + (dx + r) * s, cy + (dy + r) * s + s * .12], fill=(golge,) * 3 + (255,))
    for dx, dy, r in toplar:
        d.ellipse([cx + (dx - r) * s, cy + (dy - r) * s, cx + (dx + r) * s, cy + (dy + r) * s], fill=(ton,) * 3 + (255,))
    for dx, dy, r in toplar[:4]:
        d.ellipse([cx + (dx - r * .55) * s, cy + (dy - r * .7) * s, cx + (dx + r * .25) * s, cy + (dy - r * .1) * s], fill=(min(255, ton + 25),) * 3 + (255,))


_bulutlar = {}


def bulut_katmani(ton, golge):
    if (ton, golge) not in _bulutlar:
        kat = Image.new("RGBA", (W + 700, 720), (0, 0, 0, 0))
        d = ImageDraw.Draw(kat)
        for i in range(8):
            bulut(d, 120 + i * 250 + (i % 2) * 60, 380 + (i % 3) * 70, 150 + (i % 2) * 40, ton, golge)
        _bulutlar[(ton, golge)] = kat
    return _bulutlar[(ton, golge)]


rnd = random.Random(7)
SERIT = [(rnd.random(), rnd.random(), rnd.uniform(.6, 1.4), rnd.randint(120, 320)) for _ in range(46)]
DAMLA = [(rnd.random(), rnd.random(), rnd.uniform(.8, 1.3)) for _ in range(160)]
KARL = [(rnd.random(), rnd.random(), rnd.uniform(.5, 1.5), rnd.choice([4, 5, 6, 8])) for _ in range(140)]
DOLU = [(rnd.random(), rnd.random(), rnd.uniform(.9, 1.4), rnd.choice([7, 9, 11])) for _ in range(60)]


# ---------------------------------------------------------------- EFEKTLER
def efekt(img, ad, t, v):
    d = ImageDraw.Draw(img, "RGBA")
    if ad == "ruzgar":
        sag = v.get("akis", "sag") == "sag"
        dx, dy = (1, -.45) if sag else (-1, .45)
        for x0, y0, hiz, uz in SERIT:
            p = (x0 + t * hiz * .45) % 1.3 - .15
            x = (p if sag else 1 - p) * W
            y = 380 + y0 * 1000 + p * dy * 500
            d.line([(x, y), (x - dx * uz, y - dy * uz)], fill=tuple(v.get("serit", (240, 240, 255))) + (150,), width=6)
    if ad == "yagmur":
        for x0, y0, hiz in DAMLA:
            x = (x0 * W - t * 120) % W
            y = (y0 * H + t * 1400 * hiz) % H
            d.line([(x, y), (x - 8, y + 38)], fill=(190, 210, 240, 160), width=4)
    if ad == "kar":
        for x0, y0, hiz, r in KARL:
            x = (x0 * W + math.sin(t * 2 + y0 * 9) * 30 - t * 60) % W
            y = (y0 * H + t * 220 * hiz) % H
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 225))
    if ad == "dolu":
        for x0, y0, hiz, r in DOLU:
            y = (y0 * H + t * 1100 * hiz) % H
            d.ellipse([x0 * W - r, y - r, x0 * W + r, y + r], fill=(235, 245, 255, 240), outline=(170, 190, 220, 255), width=2)
    if ad == "sis":
        for i in range(6):
            ofs = math.sin(t * .8 + i) * 80
            sis = Image.new("RGBA", (W, 220), (0, 0, 0, 0))
            ImageDraw.Draw(sis).rounded_rectangle([-100 + ofs, 60, W + 100 + ofs, 160], radius=50, fill=(240, 242, 245, 95))
            img.alpha_composite(sis.filter(ImageFilter.GaussianBlur(25)), (0, 500 + i * 190))
    if ad in ("simsek", "yildirim"):
        faz = t % 1.6
        if faz < .25:
            rr = random.Random(int(t / 1.6) + (0 if ad == "simsek" else 99))
            if ad == "simsek":  # buluttan buluta (yatay)
                x, y = 150, 460
                pts = [(x, y)]
                while x < W - 150:
                    x += rr.randint(60, 110); y += rr.randint(-40, 40); pts.append((x, y))
            else:  # buluttan yere (dikey)
                x, y = rr.randint(380, 700), 520
                pts = [(x, y)]
                while y < 1380:
                    y += rr.randint(70, 130); x += rr.randint(-70, 70); pts.append((x, y))
            parla = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(parla).line(pts, fill=(255, 250, 210, 255), width=10)
            img.alpha_composite(parla.filter(ImageFilter.GaussianBlur(14)))
            img.alpha_composite(parla)
            if faz < .08:
                img.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 50)))
    if ad in ("gunes", "gokkusagi"):
        gx, gy = W - 200, 440
        isik = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        idr = ImageDraw.Draw(isik)
        for r, a in ((380, 40), (260, 70), (170, 120)):
            idr.ellipse([gx - r, gy - r, gx + r, gy + r], fill=(255, 230, 150, a))
        img.alpha_composite(isik.filter(ImageFilter.GaussianBlur(30)))
        d = ImageDraw.Draw(img, "RGBA")
        for i in range(12):
            a = math.radians(i * 30 + t * 20)
            d.line([(gx + math.cos(a) * 130, gy + math.sin(a) * 130), (gx + math.cos(a) * 190, gy + math.sin(a) * 190)], fill=(255, 220, 90, 230), width=12)
        d.ellipse([gx - 105, gy - 105, gx + 105, gy + 105], fill=(255, 215, 60, 255))
    if ad == "gokkusagi":
        renkler = [(230, 60, 60), (245, 140, 40), (250, 210, 50), (80, 190, 90), (60, 140, 230), (90, 80, 200), (150, 80, 190)]
        acilma = min(1, t / 1.5)
        kat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        kd = ImageDraw.Draw(kat)
        for i, r in enumerate(renkler):
            R = 620 - i * 34
            kd.arc([W / 2 - R, 1250 - R, W / 2 + R, 1250 + R], 180, 180 + 180 * acilma, fill=r + (200,), width=34)
        img.alpha_composite(kat.filter(ImageFilter.GaussianBlur(2)))


# ---------------------------------------------------------------- ORTA GÖRSELLER
def pusula(d, cx, cy, r, ok_aci, etiket, t):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(10, 16, 30, 160), outline=(255, 255, 255, 180), width=4)
    f = font("ExtraBold", 40)
    for harf, a in (("K", 270), ("D", 0), ("G", 90), ("B", 180)):
        x, y = cx + math.cos(math.radians(a)) * (r - 40), cy + math.sin(math.radians(a)) * (r - 40)
        d.text((x - d.textlength(harf, font=f) / 2, y - 24), harf, font=f, fill=(255, 255, 255, 220))
    if ok_aci is not None:
        a = math.radians(ok_aci)
        titre = math.sin(t * 6) * 6
        bx, by = cx + math.cos(a) * (r * .75 + titre), cy + math.sin(a) * (r * .75 + titre)
        ux, uy = cx - math.cos(a) * r * .35, cy - math.sin(a) * r * .35
        d.line([(bx, by), (ux, uy)], fill=SARI, width=16)
        pa = math.atan2(uy - by, ux - bx)
        d.polygon([(ux + math.cos(pa) * 34, uy + math.sin(pa) * 34), (ux + math.cos(pa + 2.5) * 34, uy + math.sin(pa + 2.5) * 34),
                   (ux + math.cos(pa - 2.5) * 34, uy + math.sin(pa - 2.5) * 34)], fill=SARI)
    if etiket:
        fe = font("Bold", 34)
        d.text((cx - d.textlength(etiket, font=fe) / 2, cy + r + 22), etiket, font=fe, fill=SARI)


def termometre(d, cx, cy, deger, t, etiket=""):
    h = 420
    d.rounded_rectangle([cx - 38, cy - h / 2, cx + 38, cy + h / 2], radius=38, fill=(255, 255, 255, 230))
    d.ellipse([cx - 70, cy + h / 2 - 40, cx + 70, cy + h / 2 + 100], fill=(255, 255, 255, 230))
    renk = (230, 70, 50) if deger >= 15 else (60, 140, 230)
    oran = min(1, t / 1.2) * max(.08, min(1, (deger + 20) / 60))
    d.rounded_rectangle([cx - 20, cy + h / 2 - (h - 40) * oran, cx + 20, cy + h / 2 + 20], radius=20, fill=renk)
    d.ellipse([cx - 52, cy + h / 2 - 22, cx + 52, cy + h / 2 + 82], fill=renk)
    d.text((cx + 110, cy - 50), f"{deger}°C", font=font("ExtraBold", 90), fill="white")
    if etiket:
        d.text((cx + 115, cy + 55), etiket, font=font("Bold", 36), fill=SARI)


def kristal(d, cx, cy, R, t):
    a0 = t * 15
    for k in range(6):
        a = math.radians(a0 + k * 60)
        ux, uy = math.cos(a), math.sin(a)
        d.line([(cx, cy), (cx + ux * R, cy + uy * R)], fill=(255, 255, 255, 245), width=14)
        for s in (.45, .72):
            px, py = cx + ux * R * s, cy + uy * R * s
            for y in (-1, 1):
                b = a + y * math.radians(45)
                d.line([(px, py), (px + math.cos(b) * R * .28, py + math.sin(b) * R * .28)], fill=(255, 255, 255, 235), width=10)
    d.regular_polygon((cx, cy, R * .22), 6, rotation=a0, fill=(200, 230, 255, 255))


def buyuk_metin(d, metin, alt, t):
    s = min(1, t / .4)
    satirlar = metin.split("\n")
    y = 980 - len(satirlar) * 85
    for sat in satirlar:
        f = font("ExtraBold", int(150 * (.8 + .2 * s)))
        while d.textlength(sat, font=f) > W - 100:
            f = font("ExtraBold", f.size - 6)
        x = W / 2 - d.textlength(sat, font=f) / 2
        d.text((x + 6, y + 8), sat, font=f, fill=(0, 0, 0, 120))
        d.text((x, y), sat, font=f, fill=SARI)
        y += 170
    if alt:
        fa = font("Bold", 48)
        d.text((W / 2 - d.textlength(alt, font=fa) / 2, y + 10), alt, font=fa, fill="white")


def renk_kodlari(d, t):
    for i, (ad, renk, metin) in enumerate((("SARI", (240, 190, 20), "Dikkatli olun"), ("TURUNCU", (235, 120, 20), "Hazırlıklı olun"),
                                          ("KIRMIZI", (200, 30, 35), "Çok tehlikeli, önlem alın"))):
        giris = min(1, max(0, (t - i * .5) / .4))
        x0 = 90 - (1 - giris) * 1000
        y = 600 + i * 230
        d.rounded_rectangle([x0, y, x0 + W - 180, y + 190], radius=34, fill=renk + (235,))
        d.text((x0 + 40, y + 28), ad, font=font("ExtraBold", 64), fill="white" if i else LACI)
        d.text((x0 + 40, y + 112), metin, font=font("Bold", 40), fill="white" if i else LACI)


# ---------------------------------------------------------------- ORTAK ÖĞELER
def ust_bant(d):
    d.rounded_rectangle([40, 120, 120, 200], radius=22, fill=(40, 160, 220))
    d.ellipse([58, 140, 102, 184], fill=SARI)
    d.text((140, 122), "BUGÜN HAVA NASIL?", font=font("ExtraBold", 38), fill="white")
    d.text((140, 168), "Meteoroloji bilgi", font=font("Medium", 28), fill=(255, 255, 255, 200))


def sayac(d, kalan):
    cx, cy, r = W - 110, 160, 46
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 120))
    d.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * kalan / 10, fill=SARI, width=8)
    tx = str(max(0, math.ceil(kalan)))
    f = font("ExtraBold", 44)
    d.text((cx - d.textlength(tx, font=f) / 2, cy - 28), tx, font=f, fill="white")


def altyazi(d, metin, vurgu, ilerleme, y=1420):
    f = font("ExtraBold", 54)
    kelimeler = metin.split()
    adet = len(kelimeler) if ilerleme >= YAZI_HIZI else max(1, int(len(kelimeler) * ilerleme / YAZI_HIZI))
    satirlar, s = [], []
    for k in kelimeler:
        if d.textlength(" ".join(s + [k]), font=f) > W - 180:
            satirlar.append(s); s = []
        s.append(k)
    satirlar.append(s)
    d.rounded_rectangle([60, y, W - 60, y + len(satirlar) * 72 + 40], radius=30, fill=(10, 16, 30, 195))
    vset = [v.lower() for v in vurgu]
    n = 0
    for i, sat in enumerate(satirlar):
        x = W / 2 - d.textlength(" ".join(sat), font=f) / 2
        for k in sat:
            if n < adet:
                vur = k.strip(".,!?:;").lower() in vset
                kw = d.textlength(k, font=f)
                if vur:
                    d.rounded_rectangle([x - 8, y + 24 + i * 72, x + kw + 8, y + 88 + i * 72], radius=12, fill=SARI)
                d.text((x, y + 22 + i * 72), k, font=f, fill=LACI if vur else "white")
            n += 1
            x += d.textlength(k + " ", font=f)


# ---------------------------------------------------------------- SAHNELER
def sahne_baslik(k, t, kalan):
    img = zemin(k.get("gok", "bulutlu"))
    img.alpha_composite(bulut_katmani(205, 150), (int(-200 - t * 40), 650))
    d = ImageDraw.Draw(img, "RGBA")
    ust_bant(d)
    sayac(d, 10)
    s = .7 + .3 * min(1, t / .5)
    f_u = font("ExtraBold", 46)
    gen = d.textlength("10 SANİYEDE", font=f_u) + 60
    d.rounded_rectangle([W / 2 - gen / 2, 520, W / 2 + gen / 2, 600], radius=40, fill=SARI)
    d.text((W / 2 - d.textlength("10 SANİYEDE", font=f_u) / 2, 532), "10 SANİYEDE", font=f_u, fill=LACI)
    y = 640
    satirlar = [(x, 150, SARI) if i % 2 == 0 else (x, 70, "white") for i, x in enumerate(k["baslik"])] + [(k["soru"], 80, "white")]
    for metin, boy, renk in satirlar:
        f = font("ExtraBold", int(boy * s))
        while d.textlength(metin, font=f) > W - 100:
            f = font("ExtraBold", f.size - 4)
        x = W / 2 - d.textlength(metin, font=f) / 2
        d.text((x + 6, y + 8), metin, font=f, fill=(0, 0, 0, 120))
        d.text((x, y), metin, font=f, fill=renk)
        y += f.size + 30
    return img


def sahne_konu(v, t, kalan):
    img = zemin(v.get("gok", "bulutlu"))
    karanlik = v.get("gok") in ("firtina", "gece", "yagmur")
    img.alpha_composite(bulut_katmani(*((150, 100) if karanlik else (230, 175))), (int(-300 + t * 50), -130))
    for e in v.get("efekt", []):
        efekt(img, e, t, v)
    d = ImageDraw.Draw(img, "RGBA")
    ust_bant(d)
    sayac(d, kalan)
    f = font("ExtraBold", 140)
    while d.textlength(v["ad"], font=f) > W - 80:
        f = font("ExtraBold", f.size - 6)
    x = W / 2 - d.textlength(v["ad"], font=f) / 2
    d.text((x + 6, 306), v["ad"], font=f, fill=(0, 0, 0, 110))
    d.text((x, 300), v["ad"], font=f, fill="white")
    g = v.get("gorsel")
    if g == "pusula":
        pusula(d, W / 2, 960, 230, v.get("ok_aci"), v.get("etiket", ""), t)
    elif g == "termometre":
        termometre(d, W / 2 - 160, 950, v["deger"], t, v.get("etiket", ""))
    elif g == "kristal":
        kristal(d, W / 2, 950, 220, t)
    elif g == "buyuk":
        buyuk_metin(d, v["buyuk"], v.get("alt", ""), t)
    elif g == "renkkod":
        renk_kodlari(d, t)
    if v.get("_ses_sure"):
        altyazi(d, v["metin"], v.get("vurgu", []), min(1, (t - 0.3) / v["_ses_sure"]) * YAZI_HIZI)
    else:
        altyazi(d, v["metin"], v.get("vurgu", []), t / v["sure"])
    return img


def sahne_ozet(k, t, kalan):
    img = zemin("gece")
    d = ImageDraw.Draw(img, "RGBA")
    ust_bant(d)
    sayac(d, kalan)
    kartlar = k["ozet"]
    yuk = 400 if len(kartlar) <= 2 else 300
    y0 = 1000 - (len(kartlar) * (yuk + 60) - 60) / 2
    for i, (ad, s1, s2, renk) in enumerate(kartlar):
        y = y0 + i * (yuk + 60)
        giris = min(1, max(0, (t - i * .4) / .5))
        x0 = 80 - (1 - giris) * 1000
        d.rounded_rectangle([x0, y, x0 + W - 160, y + yuk], radius=40, fill=tuple(renk) + (235,))
        fa = font("ExtraBold", 86 if yuk == 400 else 70)
        while d.textlength(ad, font=fa) > W - 280:
            fa = font("ExtraBold", fa.size - 4)
        d.text((x0 + 60, y + 40), ad, font=fa, fill="white")
        d.text((x0 + 60, y + 50 + fa.size + 20), s1, font=font("Bold", 44), fill="white")
        if s2:
            d.text((x0 + 60, y + 50 + fa.size + 86), s2, font=font("SemiBold", 38), fill=(255, 255, 255, 230))
    return img


def sahne_takip(k, t, kalan):
    img = gradient((40, 170, 230), (20, 110, 190)).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    r = 150 * (1 + .04 * math.sin(t * 5))
    d.rounded_rectangle([W / 2 - r, 620 - r, W / 2 + r, 620 + r], radius=60, fill=(255, 255, 255, 60))
    d.ellipse([W / 2 - 70, 560, W / 2 + 50, 680], fill=SARI)
    bulut(d, W / 2 + 20, 690, 70, 250, 210)
    for metin, y, boy in (("Bizi Takipte Kalın", 900, 84), (HESAP, 1010, 56)):
        f = font("ExtraBold", boy)
        d.text((W / 2 - d.textlength(metin, font=f) / 2, y), metin, font=f, fill="white")
    f = font("Bold", 40)
    m = "Bildirimleri aç, hiçbir uyarıyı kaçırma!"
    d.rounded_rectangle([110, 1150, W - 110, 1250], radius=50, fill=SARI)
    d.text((W / 2 - d.textlength(m, font=f) / 2, 1175), m, font=f, fill=LACI)
    return img


SES_MODEL = os.environ.get("PIPER_MODEL", "")  # yedek: Türkçe Piper ses modeli (.onnx)
EDGE_SES, EDGE_HIZ, EDGE_TON = "tr-TR-AhmetNeural", "+12%", "+6Hz"  # ana ses: Microsoft Ahmet, canlı ton
CANLI_FILTRE = "atempo=1.06,asetrate=22050*1.04,aresample=44100,equalizer=f=3000:t=q:w=1:g=3"


def _sure(yol):
    import wave
    with wave.open(yol, "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def _edge(metin, yol):
    import asyncio, edge_tts
    mp3 = yol.replace(".wav", ".mp3")
    asyncio.run(edge_tts.Communicate(metin, EDGE_SES, rate=EDGE_HIZ, pitch=EDGE_TON).save(mp3))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ar", "44100", "-ac", "1", yol], check=True)


def _piper(metin, yol):
    import wave
    from piper import PiperVoice
    if not hasattr(_piper, "ses"):
        _piper.ses = PiperVoice.load(SES_MODEL)
    ham = yol.replace(".wav", "_ham.wav")
    with wave.open(ham, "wb") as wf:
        try:
            _piper.ses.synthesize_wav(metin, wf)
        except AttributeError:
            _piper.ses.synthesize(metin, wf)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", ham, "-af", CANLI_FILTRE, "-ac", "1", yol], check=True)


def seslendir(metin, yol):
    """Önce Microsoft Ahmet (edge-tts); çalışmazsa açık kaynak Piper (dfki, canlı ayar). Döner: süre (sn)."""
    if not getattr(seslendir, "edge_bozuk", False):
        try:
            _edge(metin, yol)
            return _sure(yol)
        except Exception as e:
            print("Microsoft sesi çalışmadı, Piper'a geçiliyor:", e)
            seslendir.edge_bozuk = True
    if SES_MODEL and os.path.exists(SES_MODEL):
        _piper(metin, yol)
        return _sure(yol)
    raise RuntimeError("Seslendirme yapılamadı")


def plan(k, sesler=None):
    sesler = sesler or {}

    def sure(anahtar, taban):
        return max(taban, sesler[anahtar][1] + 1.0) if anahtar in sesler else taban
    p = [(sure("baslik", 3.2), sahne_baslik, k)]
    for i, s in enumerate(k["sahneler"]):
        s = dict(s)
        if f"s{i}" in sesler:
            s["_ses_sure"] = sesler[f"s{i}"][1]
        s["sure"] = sure(f"s{i}", s["sure"])
        p.append((s["sure"], sahne_konu, s))
    p.append((sure("ozet", 4.5), sahne_ozet, k))
    p.append((sure("takip", 2.6), sahne_takip, k))
    return p


def kare(p, i, t):
    if i == 0:
        return p[0][1](p[0][2], t, 10)
    bilgi = sum(s[0] for s in p[1:-1])
    gecen = sum(s[0] for s in p[1:i]) + t
    return p[i][1](p[i][2], t, max(0, 10 - gecen * 10 / bilgi))


def video(k, cikti):
    import tempfile
    sesler = {}
    if os.environ.get("SESLENDIRME", "1") == "1":
        tmp = tempfile.mkdtemp()
        metinler = {"baslik": k.get("ses_baslik"), "ozet": k.get("ses_ozet"), "takip": "Bizi takipte kalın!"}
        metinler.update({f"s{i}": s.get("ses") for i, s in enumerate(k["sahneler"])})
        for ad, m in metinler.items():
            if m:
                yol = os.path.join(tmp, ad + ".wav")
                try:
                    sesler[ad] = (yol, seslendir(m, yol))
                except Exception as e:
                    print("Seslendirme atlandı:", e)
                    sesler = {}
                    break
    p = plan(k, sesler)
    toplam = sum(s[0] for s in p)
    sinir, acc = [], 0
    for s in p:
        sinir.append(acc); acc += s[0]
    sira = ["baslik"] + [f"s{i}" for i in range(len(k["sahneler"]))] + ["ozet", "takip"]
    ses_girdi, ses_filtre, ses_etiket = [], [], []
    for j, ad in enumerate(sira):
        if ad in sesler:
            n = 2 + len(ses_girdi) // 2
            ses_girdi += ["-i", sesler[ad][0]]
            gecik = int((sinir[j] + 0.3) * 1000)
            ses_filtre.append(f"[{n}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={gecik}|{gecik},volume=1.6[v{n}]")
            ses_etiket.append(f"[v{n}]")
    parcalar = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "muzik", "*.mp3")))
    parca = parcalar[sum(map(ord, k["id"])) % len(parcalar)] if parcalar else None
    ses = ["-stream_loop", "-1", "-i", parca] if parca else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    muzik_ses = 0.18 if sesler else 0.7  # seslendirme varsa müzik arka planda kalsın
    filtre = f"[1:a]atrim=0:{toplam},asetpts=PTS-STARTPTS,volume={muzik_ses},afade=t=in:d=0.6,afade=t=out:st={toplam - 1.8}:d=1.8[m]"
    if ses_etiket:
        filtre += ";" + ";".join(ses_filtre) + f";[m]{''.join(ses_etiket)}amix=inputs={1 + len(ses_etiket)}:normalize=0:duration=first[a]"
    else:
        filtre = filtre.replace("[m]", "[a]")
    pr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", *ses, *ses_girdi, "-filter_complex", filtre,
                           "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "25", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-t", str(toplam), cikti], stdin=subprocess.PIPE)
    for f in range(int(toplam * FPS)):
        tt = f / FPS
        i = max(j for j, b in enumerate(sinir) if tt >= b)
        img = kare(p, i, tt - sinir[i]).convert("RGB")
        if i > 0 and tt - sinir[i] < GECIS:
            img = Image.blend(kare(p, i - 1, p[i - 1][0] - 0.01).convert("RGB"), img, (tt - sinir[i]) / GECIS)
        pr.stdin.write(img.tobytes())
    pr.stdin.close()
    pr.wait()
    if not parca:
        return None
    ad = os.path.basename(parca)[3:-4]
    return next((n for o, n in (("alex-morgan", "Alex Morgan"), ("atlasaudio", "AtlasAudio"), ("nastelbom", "Nastelbom"),
                                ("velariomusic", "VelarioMusic"), ("andriig", "AndriiG")) if ad.startswith(o)), ad.split("-")[0])


def gonderi_gorselleri(k, klasor):
    """Her sahnenin son halinden 4:5 kaydırmalı gönderi görselleri (takip sahnesi hariç)."""
    p = plan(k)
    for i in range(len(p) - 1):
        img = kare(p, i, p[i][0] - 0.05).convert("RGB")
        on = img.resize((int(1350 * W / H), 1350))
        bg = ImageEnhance.Brightness(img.crop((0, 285, 1080, 1635)).filter(ImageFilter.GaussianBlur(30))).enhance(.5)
        bg.paste(on, ((1080 - on.width) // 2, 0))
        bg.save(os.path.join(klasor, f"{i + 1:02d}_{k['id']}.jpg"), quality=92)


def caption(k):
    s = [f"⚡ 10 saniyede: {k['soru_tam']}", ""] + [f"• {x}" for x in k["aciklama"]]
    s += ["", "💬 Başka hangi hava olayını merak ediyorsun? Yorumlara yaz!",
          "🔔 Takip edip bildirimleri açarak destek olun · 📤 Sevdiklerinle paylaş",
          f"👉 {HESAP}", "", "#havadurumu #meteoroloji #bilgi #biliyormuydunuz " + k.get("etiket", "")]
    return "\n".join(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--konu")
    ap.add_argument("--siradaki", action="store_true")
    ap.add_argument("--cikti", default="yayin/bilgi")
    a = ap.parse_args()
    ids = [k["id"] for k in KONULAR]
    durum = json.load(open(DURUM, encoding="utf-8")) if os.path.exists(DURUM) else {"sira": 0}
    paylasilan = durum.setdefault("paylasilan", [])
    if a.siradaki:
        # elle paylaşılmış konuları atla (tur tamamlanınca liste sıfırlanır)
        if len(set(paylasilan) & set(ids)) >= len(ids):
            paylasilan.clear()
        while True:
            k = KONULAR[durum["sira"] % len(KONULAR)]
            durum["sira"] += 1
            if k["id"] not in paylasilan:
                break
        import datetime
        durum["son"] = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date().isoformat()
        durum["son_konu"] = k["id"]
    else:
        k = KONULAR[ids.index(a.konu)] if a.konu else KONULAR[0]
    paylasilan.append(k["id"])
    json.dump(durum, open(DURUM, "w", encoding="utf-8"), ensure_ascii=False)
    os.makedirs(a.cikti, exist_ok=True)
    for f in glob.glob(os.path.join(a.cikti, "*")):
        os.remove(f)
    muzik = video(k, os.path.join(a.cikti, "reels.mp4"))
    gonderi_gorselleri(k, a.cikti)
    open(os.path.join(a.cikti, "caption.txt"), "w", encoding="utf-8").write(caption(k))
    if muzik:
        open(os.path.join(a.cikti, "muzik.txt"), "w", encoding="utf-8").write(muzik)
    Image.open(sorted(glob.glob(os.path.join(a.cikti, "01_*.jpg")))[0]).save(os.path.join(a.cikti, "reels_kapak.jpg"))
    print("Hazır:", k["id"])


if __name__ == "__main__":
    main()
