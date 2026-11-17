#!/usr/bin/env python3
"""
"10 saniyede" bilgi videosu (1080x1920, 30 fps) – animasyonlar Pillow ile çizilir, müzik muzik/ klasöründen.
Deneme konusu: Lodos ile poyraz farkı.
Kullanım: python bilgi_video.py cikti.mp4
"""
import math, os, random, subprocess, sys, glob
from PIL import Image, ImageDraw, ImageFilter
from hava_bot import font, HESAP

W, H, FPS = 1080, 1920, 30
SARI, LACI = (255, 205, 0), (14, 24, 46)
rnd = random.Random(7)

# ---------------------------------------------------------------- SAHNE PLANI
SAHNELER = [  # (süre sn, tür, veri)
    (2.6, "baslik", {"ust": "10 SANİYEDE", "b1": "LODOS", "ve": "VE", "b2": "POYRAZ", "alt": "FARKI NEDİR?"}),
    (3.6, "ruzgar", {"ad": "LODOS", "yon": "GÜNEYBATIDAN", "aci": -35, "renk": ((70, 40, 60), (215, 120, 70)),
                     "seritr": (255, 200, 140), "metin": "Lodos güneybatıdan eser, ılık ve fırtınalıdır.", "vurgu": ["güneybatıdan", "ılık"],
                     "ok_aci": 135, "kar": False}),
    (3.6, "ruzgar", {"ad": "POYRAZ", "yon": "KUZEYDOĞUDAN", "aci": 145, "renk": ((20, 35, 70), (110, 150, 200)),
                     "seritr": (220, 240, 255), "metin": "Poyraz kuzeydoğudan eser, soğuk ve serttir.", "vurgu": ["kuzeydoğudan", "soğuk"],
                     "ok_aci": 315, "kar": True}),
    (2.2, "ozet", {}),
    (2.0, "takip", {}),
]
GECIS = 0.3


def gradient(ust, alt):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(ust[i] * (1 - k) + alt[i] * k) for i in range(3)))
    return img


def bulut(d, cx, cy, s, ton=225, golge=150):
    """Çizgi film tarzı kabarık bulut (gölgeli)."""
    toplar = [(-.9, .1, .55), (-.45, -.25, .7), (.1, -.38, .8), (.65, -.15, .65), (1.05, .15, .5), (.1, .15, .75)]
    for dx, dy, r in toplar:
        d.ellipse([cx + (dx - r) * s, cy + (dy - r) * s + s * .12, cx + (dx + r) * s, cy + (dy + r) * s + s * .12], fill=(golge,) * 3 + (255,))
    for dx, dy, r in toplar:
        d.ellipse([cx + (dx - r) * s, cy + (dy - r) * s, cx + (dx + r) * s, cy + (dy + r) * s], fill=(ton,) * 3 + (255,))
    for dx, dy, r in toplar[:4]:
        d.ellipse([cx + (dx - r * .55) * s, cy + (dy - r * .7) * s, cx + (dx + r * .25) * s, cy + (dy - r * .1) * s], fill=(min(255, ton + 25),) * 3 + (255,))


def bulut_katmani(ton, golge, kayma):
    kat = Image.new("RGBA", (W + 600, 700), (0, 0, 0, 0))
    d = ImageDraw.Draw(kat)
    for i in range(7):
        bulut(d, 120 + i * 260 + (i % 2) * 60, 380 + (i % 3) * 70, 150 + (i % 2) * 40, ton, golge)
    return kat


def ust_bant(d):
    d.rounded_rectangle([40, 120, 120, 200], radius=22, fill=(40, 160, 220))
    d.ellipse([58, 140, 102, 184], fill=SARI)
    d.text((140, 122), "BUGÜN HAVA NASIL?", font=font("ExtraBold", 38), fill="white")
    d.text((140, 168), "Meteoroloji bilgi", font=font("Medium", 28), fill=(255, 255, 255, 200))


def sayac(d, kalan):
    cx, cy, r = W - 110, 160, 46
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 120))
    d.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * kalan / 10, fill=SARI, width=8)
    t = str(max(0, math.ceil(kalan)))
    f = font("ExtraBold", 44)
    d.text((cx - d.textlength(t, font=f) / 2, cy - 28), t, font=f, fill="white")


def altyazi(d, metin, vurgu, ilerleme, y=1420):
    """Kelime kelime beliren altyazı; vurgulu kelimeler sarı."""
    f = font("ExtraBold", 54)
    kelimeler = metin.split()
    goster = kelimeler[:max(1, int(len(kelimeler) * min(1, ilerleme * 1.6)))]
    satirlar, s = [], []
    for k in kelimeler:
        if d.textlength(" ".join(s + [k]), font=f) > W - 180:
            satirlar.append(s); s = []
        s.append(k)
    satirlar.append(s)
    h = len(satirlar) * 72 + 40
    d.rounded_rectangle([60, y, W - 60, y + h], radius=30, fill=(10, 16, 30, 190))
    sayac_k = 0
    for i, sat in enumerate(satirlar):
        gen = d.textlength(" ".join(sat), font=f)
        x = W / 2 - gen / 2
        for k in sat:
            if sayac_k < len(goster):
                temiz = k.strip(".,").lower()
                vur = any(temiz == v.lower() for v in vurgu)
                kw = d.textlength(k, font=f)
                if vur:
                    d.rounded_rectangle([x - 8, y + 24 + i * 72, x + kw + 8, y + 24 + i * 72 + 64], radius=12, fill=SARI)
                d.text((x, y + 22 + i * 72), k, font=f, fill=LACI if vur else "white")
            sayac_k += 1
            x += d.textlength(k + " ", font=f)


def pusula(d, cx, cy, r, ok_aci, etiket, t):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(10, 16, 30, 150), outline=(255, 255, 255, 180), width=4)
    f = font("ExtraBold", 40)
    for harf, a in (("K", 270), ("D", 0), ("G", 90), ("B", 180)):
        x, y = cx + math.cos(math.radians(a)) * (r - 40), cy + math.sin(math.radians(a)) * (r - 40)
        d.text((x - d.textlength(harf, font=f) / 2, y - 24), harf, font=f, fill=(255, 255, 255, 220))
    # ok: rüzgarın geldiği yönden merkeze doğru (titreşimli)
    a = math.radians(ok_aci)
    titre = math.sin(t * 8) * 6
    bx, by = cx + math.cos(a) * (r * .75 + titre), cy + math.sin(a) * (r * .75 + titre)
    ux, uy = cx - math.cos(a) * r * .35, cy - math.sin(a) * r * .35
    d.line([(bx, by), (ux, uy)], fill=SARI, width=16)
    pa = math.atan2(uy - by, ux - bx)
    uc = [(ux + math.cos(pa) * 34, uy + math.sin(pa) * 34),
          (ux + math.cos(pa + 2.5) * 34, uy + math.sin(pa + 2.5) * 34),
          (ux + math.cos(pa - 2.5) * 34, uy + math.sin(pa - 2.5) * 34)]
    d.polygon(uc, fill=SARI)
    fe = font("Bold", 34)
    d.text((cx - d.textlength(etiket, font=fe) / 2, cy + r + 22), etiket, font=fe, fill=SARI)


# ---------------------------------------------------------------- KARE ÇİZİCİLER
_onbellek = {}


def zemin(anahtar, ust, alt):
    if anahtar not in _onbellek:
        _onbellek[anahtar] = gradient(ust, alt)
    return _onbellek[anahtar].copy()


SERITLER = [(rnd.random(), rnd.random(), rnd.uniform(.6, 1.4), rnd.randint(120, 320)) for _ in range(46)]
KARLAR = [(rnd.random(), rnd.random(), rnd.uniform(.5, 1.5), rnd.choice([4, 5, 6, 8])) for _ in range(140)]


def kare_baslik(v, t, toplam_t):
    img = zemin("baslik", (25, 40, 80), (60, 90, 150)).convert("RGBA")
    kat = bulut_katmani(205, 150, 0)
    img.alpha_composite(kat, (int(-200 - t * 40), 650))
    d = ImageDraw.Draw(img, "RGBA")
    ust_bant(d)
    sayac(d, 10)
    giris = min(1, t / .5)
    olcek = .7 + .3 * giris
    f_ust = font("ExtraBold", 46)
    gen = d.textlength(v["ust"], font=f_ust) + 60
    d.rounded_rectangle([W / 2 - gen / 2, 520, W / 2 + gen / 2, 600], radius=40, fill=SARI)
    d.text((W / 2 - d.textlength(v["ust"], font=f_ust) / 2, 532), v["ust"], font=f_ust, fill=LACI)
    for metin, y, boy, renk in ((v["b1"], 640, 170, SARI), (v["ve"], 820, 70, "white"), (v["b2"], 890, 170, SARI), (v["alt"], 1080, 84, "white")):
        f = font("ExtraBold", int(boy * olcek))
        x = W / 2 - d.textlength(metin, font=f) / 2
        d.text((x + 6, y + 8), metin, font=f, fill=(0, 0, 0, 120))
        d.text((x, y), metin, font=f, fill=renk)
    return img


def kare_ruzgar(v, t, kalan):
    img = zemin(v["ad"], *v["renk"]).convert("RGBA")
    ton, golge = (200, 130) if v["kar"] else (235, 175)
    img.alpha_composite(bulut_katmani(ton, golge, 0), (int(-300 + (t * 120 if v["ok_aci"] == 135 else -t * 120)), -120))
    d = ImageDraw.Draw(img, "RGBA")
    # rüzgar şeritleri: lodos sağ-yukarı, poyraz sol-aşağı akar
    dx, dy = (1, -.45) if v["ok_aci"] == 135 else (-1, .45)
    for x0, y0, hiz, uz in SERITLER:
        p = (x0 + t * hiz * .55) % 1.3 - .15
        x = (p if dx > 0 else 1 - p) * W
        y = 380 + y0 * 1000 + (p * dy * 500 if dx > 0 else -p * dy * -500)
        d.line([(x, y), (x - dx * uz, y - dy * uz)], fill=v["seritr"] + (150,), width=6)
    if v["kar"]:
        for x0, y0, hiz, r in KARLAR:
            x = (x0 * W - t * 260 * hiz) % W
            y = (y0 * H + t * 300 * hiz) % H
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 220))
    ust_bant(d)
    sayac(d, kalan)
    f = font("ExtraBold", 150)
    d.text((W / 2 - d.textlength(v["ad"], font=f) / 2 + 6, 300), v["ad"], font=f, fill=(0, 0, 0, 110))
    d.text((W / 2 - d.textlength(v["ad"], font=f) / 2, 294), v["ad"], font=f, fill="white")
    pusula(d, W / 2, 960, 230, v["ok_aci"], v["yon"] + " ESER", t)
    altyazi(d, v["metin"], v["vurgu"], t / 2.4)
    return img


def kare_ozet(t, kalan):
    img = zemin("ozet", (30, 40, 70), (70, 80, 120)).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    ust_bant(d)
    sayac(d, kalan)
    f_b, f_k = font("ExtraBold", 92), font("Bold", 46)
    for i, (ad, ozellik, renk, yon) in enumerate((("LODOS", "Ilık · Fırtınalı", (225, 130, 70), "Güneybatı ↗"),
                                                  ("POYRAZ", "Soğuk · Sert", (90, 150, 220), "Kuzeydoğu ↙"))):
        y = 520 + i * 470
        giris = min(1, max(0, (t - i * .3) / .4))
        x0 = 80 - (1 - giris) * 900
        d.rounded_rectangle([x0, y, x0 + W - 160, y + 400], radius=40, fill=renk + (230,))
        d.text((x0 + 60, y + 50), ad, font=f_b, fill="white")
        d.text((x0 + 60, y + 170), ozellik, font=f_k, fill="white")
        d.text((x0 + 60, y + 250), yon.replace(" ↗", "").replace(" ↙", "") + "dan eser", font=font("SemiBold", 40), fill=(255, 255, 255, 230))
    return img


def kare_takip(t):
    img = zemin("takip", (40, 170, 230), (20, 110, 190)).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    s = 1 + .04 * math.sin(t * 6)
    r = 150 * s
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


def kare(sahne_i, t):
    sure, tur, v = SAHNELER[sahne_i]
    gecen = sum(s[0] for s in SAHNELER[:sahne_i]) + t
    bilgi_bas = SAHNELER[0][0]
    kalan = max(0, 10 - (gecen - bilgi_bas) * 10 / (sum(s[0] for s in SAHNELER[1:4])))
    if tur == "baslik":
        return kare_baslik(v, t, sure)
    if tur == "ruzgar":
        return kare_ruzgar(v, t, kalan)
    if tur == "ozet":
        return kare_ozet(t, kalan)
    return kare_takip(t)


def main(cikti):
    toplam = sum(s[0] for s in SAHNELER)
    n = int(toplam * FPS)
    parcalar = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "muzik", "*.mp3")))
    ses = ["-stream_loop", "-1", "-i", parcalar[2]] if parcalar else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", *ses, "-filter_complex",
                          f"[1:a]atrim=0:{toplam},volume=0.7,afade=t=in:d=0.5,afade=t=out:st={toplam - 1.5}:d=1.5[a]",
                          "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-t", str(toplam), cikti], stdin=subprocess.PIPE)
    sinirlar = []
    acc = 0
    for s in SAHNELER:
        sinirlar.append(acc); acc += s[0]
    onceki = None
    for f in range(n):
        tt = f / FPS
        i = max(j for j, b in enumerate(sinirlar) if tt >= b)
        img = kare(i, tt - sinirlar[i]).convert("RGB")
        if i > 0 and tt - sinirlar[i] < GECIS:  # geçiş: önceki sahnenin son karesiyle karıştır
            k = (tt - sinirlar[i]) / GECIS
            img = Image.blend(kare(i - 1, SAHNELER[i - 1][0] - 0.01).convert("RGB"), img, k)
        p.stdin.write(img.tobytes())
    p.stdin.close()
    p.wait()
    print("Hazır:", cikti, f"{toplam:.1f} sn")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "bilgi.mp4")
