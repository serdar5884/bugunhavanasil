#!/usr/bin/env python3
"""
Hazır bir kartı (uyarı, son dakika, yurt geneli) hareketli videoya çevirir:
- Olaya göre üstte akan katman: yağmur, kar, fırtına (yağmur + şimşek), rüzgar çizgileri, sis
- Arka planda çok hafif yakınlaşma; 6 sn kesintisiz döngü

Kullanım: python hareket.py kart.jpg [tur]   -> kart.mp4
"""
import math, os, random, re, shutil, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter

KELIMELER = [  # sıra önemli: ilk eşleşen
    ("firtina", r"fırtına|firtina|hortum|gök gürültü|gok gurultu|yıldırım|şimşek|\bdolu\b"),
    ("kar", r"\bkar\b|kar yağ|kar yag|karla|çığ|cig|buzlanma|tipi|kırağı|don\b"),
    ("yagmur", r"yağış|yagis|yağmur|yagmur|sağanak|saganak|\bsel\b|sel |su baskın|taşkın"),
    ("ruzgar", r"rüzgar|ruzgar|lodos|poyraz|kuvvetli rüzgar"),
    ("sis", r"\bsis\b|\bsis |sisli|\bpus\b|görüş mesafesi"),
]


def tur_bul(metin):
    m = (metin or "").lower()
    for tur, desen in KELIMELER:
        if re.search(desen, m):
            return tur
    return None


def _yagmur(d, W, H, faz, rnd, adet=260, alfa=(70, 130)):
    for _ in range(adet):
        x, y = rnd.randint(-300, W), rnd.randint(0, H)
        l = rnd.randint(30, 70)
        dy = faz * 3 * (H + 80)
        yy = (y + dy) % (H + 80) - 80
        xx = (x + 300 + dy * .25) % (W + 300) - 300
        d.line([(xx, yy), (xx + l * .25, yy + l)], fill=(220, 230, 245, rnd.randint(*alfa)), width=3)


def _kar(d, W, H, faz, rnd, adet=110):
    P = (H + 60) / 2
    for _ in range(adet):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        r = rnd.choice([3, 4, 5, 6, 8, 10])
        a = rnd.randint(150, 230)
        yy = (y % P + faz * P) % P - 30
        sal = math.sin(2 * math.pi * (faz + x / 300)) * (6 + r)
        for k in (0, P):
            d.ellipse([x + sal - r, yy + k - r, x + sal + r, yy + k + r], fill=(255, 255, 255, a))


def _ruzgar(d, W, H, faz, rnd, adet=26):
    for _ in range(adet):
        y0 = rnd.randint(0, H)
        x0 = rnd.randint(0, W)
        L = rnd.randint(160, 380)
        hiz = rnd.choice([1, 2])
        x = (x0 + faz * hiz * (W + L)) % (W + L) - L
        pts = [(x + t * L, y0 + math.sin(t * math.pi * 2 + x0) * 10) for t in [i / 12 for i in range(13)]]
        d.line(pts, fill=(255, 255, 255, rnd.randint(70, 130)), width=rnd.choice([2, 3]))


def hareketlendir(jpg, tur=None, mp4=None, sure=6, fps=20):
    """Kartı hareketli MP4'e çevirir. Döner: mp4 yolu."""
    mp4 = mp4 or jpg[:-4] + ".mp4"
    taban = Image.open(jpg).convert("RGB")
    W, H = taban.size
    sis = None
    if tur == "sis":  # yatayda periyodik sis katmanı
        rnd = random.Random(1)
        sis = Image.new("RGBA", (W * 2, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sis)
        for _ in range(26):
            cx, cy, r = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(150, 320)
            for k in (0, W):
                sd.ellipse([cx + k - r, cy - r * .4, cx + k + r, cy + r * .4], fill=(235, 238, 242, 55))
        sis = sis.filter(ImageFilter.GaussianBlur(40))
    tmp = tempfile.mkdtemp()
    n = sure * fps
    try:
        for i in range(n):
            faz = i / n
            z = 1 + 0.025 * (1 - math.cos(2 * math.pi * faz)) / 2  # hafif nefes alan yakınlaşma
            bw, bh = int(W * z), int(H * z)
            kare = taban.resize((bw, bh), Image.BILINEAR).crop(((bw - W) // 2, (bh - H) // 2, (bw - W) // 2 + W, (bh - H) // 2 + H))
            kare = kare.convert("RGBA")
            kat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(kat)
            rnd = random.Random(7)  # her karede aynı parçacıklar, sadece konum değişir
            if tur in ("yagmur", "firtina"):
                _yagmur(d, W, H, faz, rnd)
            elif tur == "kar":
                _kar(d, W, H, faz, rnd)
            elif tur == "ruzgar":
                _ruzgar(d, W, H, faz, rnd)
            elif tur == "sis":
                x = int(faz * W)
                kat.alpha_composite(sis.crop((x, 0, x + W, H)))
            kare.alpha_composite(kat)
            if tur == "firtina" and (0.40 <= faz < 0.44 or 0.48 <= faz < 0.50):  # şimşek çakması
                kare.alpha_composite(Image.new("RGBA", (W, H), (235, 235, 255, 70)))
            kare.convert("RGB").save(os.path.join(tmp, f"k{i:03d}.jpg"), quality=90)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(tmp, "k%03d.jpg"),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-movflags", "+faststart", mp4], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return mp4


if __name__ == "__main__":
    print(hareketlendir(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))


def guvenli_alan(mp4, oran=0.82, ust=50):
    """Reels/hikâye tam ekranda uzun telefonlarda iki yandan kırpılır ve altta yazılar/düğmeler içeriği örter.
    İçeriği %82'ye küçültüp yatayda ortalar, biraz yukarı alır; boşluğa aynı videonun bulanık hali gelir."""
    import json as _j
    bilgi = _j.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                              "stream=width,height", "-of", "json", mp4]))["streams"][0]
    W, H = bilgi["width"], bilgi["height"]
    w, h = int(W * oran) // 2 * 2, int(H * oran) // 2 * 2
    x = (W - w) // 2
    y = min(ust, H - h)
    gecici = mp4[:-4] + "_g.mp4"
    fc = (f"[0:v]split[a][b];[a]scale={W}:{H},boxblur=28:2,eq=brightness=-0.12[z];"
          f"[b]scale={w}:{h}[o];[z][o]overlay={x}:{y},format=yuv420p[v]")
    komut = ["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-c:a", "copy", "-movflags", "+faststart", gecici]
    subprocess.run(komut, check=True)
    os.replace(gecici, mp4)
    return mp4
