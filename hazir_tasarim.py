"""Hazır (tasarımcı/yapay zekâ) arka planlı il kartları: tasarimlar/<İl>/<n>.png + kutular.json.
Görseldeki örnek tarih ve kart içerikleri, kart rengiyle boyanıp gerçek MGM verisiyle yeniden yazılır."""
import datetime, json, os
from PIL import Image, ImageDraw, ImageFilter
from hava_bot import HADISE, font, metni_sigdir
import tasarim

KLASOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasarimlar")
AYLAR = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
GUN_KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def var_mi(il):
    return os.path.exists(os.path.join(KLASOR, il, "kutular.json"))


def ayar(il, n):
    if not var_mi(il):
        return {}
    c = json.load(open(os.path.join(KLASOR, il, "kutular.json"), encoding="utf-8"))
    return c[n % len(c)]


def sayi(il):
    return len(json.load(open(os.path.join(KLASOR, il, "kutular.json"), encoding="utf-8"))) if var_mi(il) else 0


def _kart_boya(img, b, ic=7):
    """Kartın içini kendi rengiyle (üst/alt kenardan örneklenen dikey geçiş) boya; kenar ve gölge kalır."""
    x0, y0, x1, y1 = b
    ust = img.crop((x1 - 26, y0 + 8, x1 - 10, y0 + 16)).resize((1, 1), Image.BOX).getpixel((0, 0))
    alt = img.crop((x1 - 26, y1 - 16, x1 - 10, y1 - 8)).resize((1, 1), Image.BOX).getpixel((0, 0))
    w, h = x1 - x0 - 2 * ic, y1 - y0 - 2 * ic
    g = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        g.putpixel((0, y), tuple(int(ust[k] + (alt[k] - ust[k]) * t) for k in range(3)))
    g = g.resize((w, h))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=max(8, h // 7), fill=255)
    img.paste(g, (x0 + ic, y0 + ic), m.filter(ImageFilter.GaussianBlur(1.2)))
    return ust


def _zemin_boya(img, b):
    """Kutuyu (arka plan üstündeki yazı) soldan-sağdan örneklenen zeminle doldur."""
    x0, y0, x1, y1 = b
    sol = img.crop((x0 - 8, y0, x0 - 2, y1)).resize((1, y1 - y0), Image.BOX)
    sag = img.crop((x1 + 2, y0, x1 + 8, y1)).resize((1, y1 - y0), Image.BOX)
    w = x1 - x0
    yama = Image.new("RGB", (w, y1 - y0))
    for y in range(y1 - y0):
        a, c = sol.getpixel((0, y)), sag.getpixel((0, y))
        for x in range(0, w, 4):
            t = x / max(1, w - 1)
            renk = tuple(int(a[k] + (c[k] - a[k]) * t) for k in range(3))
            for dx in range(4):
                if x + dx < w:
                    yama.putpixel((x + dx, y), renk)
    img.paste(yama.filter(ImageFilter.GaussianBlur(3)), (x0, y0))


def hava_turu(v):
    """Merkezin günlük tahmininden arka plan havası: gunes / az_bulut / bulut / yagmur / firtina / kar / sis (+ruzgar)."""
    tp = HADISE.get((v or {}).get("hadise") or "", ("", "bulut"))[1]
    tp = {"karla_yagmur": "kar"}.get(tp, tp)
    if tp in ("bulut", "az_bulut", "gunes") and ((v or {}).get("ruzgar") or 0) >= 40 or (v or {}).get("hadise") in ("R", "GKR", "KKR"):
        return "ruzgar"
    return tp


DERECE = {  # arka plan düzeltmesi: (renk doygunluğu, parlaklık, ton rengi, ton oranı)
    "gunes": None, "az_bulut": None,
    "bulut": (.55, .9, (150, 160, 175), .18), "ruzgar": (.6, .92, (150, 160, 175), .15),
    "yagmur": (.5, .8, (80, 98, 125), .22), "firtina": (.38, .66, (50, 60, 90), .3),
    "kar": (.45, 1.0, (215, 228, 245), .3), "sis": (.4, 1.02, (215, 218, 222), .36),
}


def kart_maskesi(cfg, size, dy=0, koru=False):
    """Kartların olduğu yerler 0, arka plan 255."""
    m = Image.new("L", size, 255)
    d = ImageDraw.Draw(m)
    for b in cfg["mk"] + cfg["ilce"] + (cfg.get("koru", []) if not dy and koru else []):
        d.rounded_rectangle([b[0], b[1] + dy, b[2], b[3] + dy], radius=18, fill=0)
    return m


def hava_uygula(img, cfg, tur):
    """Güneşli arka planı yağmurlu/karlı/sisli güne çevirir: renk soldurma, karartma/ağartma, güneşi bulutla örtme.
    Kartlara dokunmaz. Resmi çok değiştirmez."""
    from PIL import ImageEnhance
    ayar = DERECE.get(tur)
    if not ayar:
        return img
    doy, par, ton, oran = ayar
    yeni = ImageEnhance.Brightness(ImageEnhance.Color(img).enhance(doy)).enhance(par)
    yeni = Image.blend(yeni, Image.new("RGB", img.size, ton), oran)
    if cfg.get("gunes"):  # güneşi yumuşak bulut kütlesiyle ört
        gx, gy, r = cfg["gunes"]
        k = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(k)
        ort = yeni.crop((max(0, gx - 8 * r), max(0, gy - 4 * r), min(img.width, gx + 8 * r), gy + 6 * r)).resize((1, 1), Image.BOX).getpixel((0, 0))
        bulut = tuple(min(255, int(c * 1.06 + 8)) for c in ort)  # çevresiyle uyumlu, hafif açık bulut
        for dx, dy, rr in ((0, 0, 5), (-4, 1.5, 3.6), (4, 1, 3.8), (-1.5, -2.5, 3.4), (2.5, -2, 3.2)):
            d.ellipse([gx + dx * r - rr * r, gy + dy * r - rr * r * .7, gx + dx * r + rr * r, gy + dy * r + rr * r * .7],
                      fill=bulut + (225,))
        k = k.filter(ImageFilter.GaussianBlur(r * 1.3))
        yeni.paste(k, (0, 0), k)
    from PIL import ImageChops
    m = kart_maskesi(cfg, img.size).filter(ImageFilter.GaussianBlur(3))
    k = Image.new("L", img.size, 255)
    kd = ImageDraw.Draw(k)
    for b in cfg.get("koru", []):  # başlık ve bantlar: yumuşak kenarla korunur (dikdörtgen izi kalmaz)
        kd.rounded_rectangle(b, radius=30, fill=0)
    m = ImageChops.darker(m, k.filter(ImageFilter.GaussianBlur(22)))
    img.paste(yeni, (0, 0), m)
    return img


def kart(il, n, merkez, ilce_v, tarih, yol, faz=None, _ikonlar=None):
    """n. hazır tasarımla kart üretir (1080 genişlik). _ikonlar listesi verilirse ikonlar çizilmez, listeye eklenir."""
    def ikon_ciz(tp, cx, cy, s):
        if _ikonlar is not None:
            _ikonlar.append((tp, cx, cy, s))
        else:
            tasarim.ikon3d(img, tp, cx, cy, s, faz)
    cfg = json.load(open(os.path.join(KLASOR, il, "kutular.json"), encoding="utf-8"))[n]
    img = Image.open(os.path.join(KLASOR, il, f"{n}.png")).convert("RGB")
    bugun = merkez.get(tarih.isoformat()) or {}
    if cfg.get("canli") or cfg.get("kontras"):  # daha canlı renkler
        from PIL import ImageEnhance
        img = ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(cfg.get("canli", 1))).enhance(cfg.get("kontras", 1))
    img = hava_uygula(img, cfg, hava_turu(bugun))  # arka plan o günün havasına göre (kartlar hariç)
    yazi = tuple(cfg["yazi"])
    # tarih (takvim ikonu kalır, yanındaki yazı yenilenir)
    tx0, ty0, tx1, ty1 = cfg["tarih"]
    ix = tx0 + int((ty1 - ty0) * 1.15)
    _zemin_boya(img, [ix, ty0, tx1 + 30, ty1])
    d = ImageDraw.Draw(img, "RGBA")
    d.text((ix + 4, (ty0 + ty1) / 2), f"{tarih.day} {AYLAR[tarih.month]} {tarih.year}, {GUNLER[tarih.weekday()]}",
           font=font("SemiBold", int((ty1 - ty0) * .72)), fill=tuple(cfg["tarih_renk"]), anchor="lm")
    # merkez: bugün / yarın
    for i, b in enumerate(cfg["mk"]):
        dt = tarih + datetime.timedelta(days=i)
        v = merkez.get(dt.isoformat())
        if not v:
            continue
        _kart_boya(img, b)
        d = ImageDraw.Draw(img, "RGBA")
        x0, y0, x1, y1 = b
        w, h = x1 - x0, y1 - y0
        renk = tuple(cfg.get("mk_yazi", [yazi, yazi])[i])
        mt, tp = HADISE.get(v["hadise"] or "", (v["hadise"] or "-", "bulut"))
        ikon_ciz(tp, x0 + w * .2, y0 + h * .5, int(h * .62))
        d = ImageDraw.Draw(img, "RGBA")
        tx = x0 + w * .39
        d.text((tx, y0 + h * .2), f"{'BUGÜN' if i == 0 else 'YARIN'} • {GUN_KISA[dt.weekday()]}", font=font("Bold", int(h * .16)),
               fill=renk, anchor="lm")
        fb = font("ExtraBold", int(h * .4))
        d.text((tx, y0 + h * .52), f"{v['max']}°", font=fb, fill=renk, anchor="lm")
        d.text((tx + d.textlength(f"{v['max']}°", font=fb) + 6, y0 + h * .56), f"/ {v['min']}°",
               font=font("SemiBold", int(h * .17)), fill=renk, anchor="lm")
        d.text((tx, y0 + h * .83), mt, font=metni_sigdir(d, mt, "SemiBold", int(h * .15), x1 - tx - 14), fill=renk, anchor="lm")
    # ilçeler (veri gelmeyen kutular boş kalır; tasarımdaki örnek yazı görünmesin)
    for b in cfg["ilce"][len(ilce_v):]:
        _kart_boya(img, b, ic=6)
    for b, v in zip(cfg["ilce"], ilce_v):
        _kart_boya(img, b, ic=6)
        x0, y0, x1, y1 = b
        w, h = x1 - x0, y1 - y0
        mt, tp = HADISE.get(v["hadise"] or "", (v["hadise"] or "-", "bulut"))
        ikon_ciz(tp, x0 + w * .2, y0 + h * .52, int(h * .55))
        d = ImageDraw.Draw(img, "RGBA")
        tx = x0 + w * .375
        d.text((tx, y0 + h * .3), v["il"], font=metni_sigdir(d, v["il"], "Bold", int(h * .25), x1 - tx - 6), fill=yazi, anchor="lm")
        fb = font("ExtraBold", int(h * .34))
        d.text((tx, y0 + h * .68), f"{v['max']}°", font=fb, fill=yazi, anchor="lm")
        d.text((tx + d.textlength(f"{v['max']}°", font=fb) + 4, y0 + h * .71), f"/ {v['min']}°",
               font=font("SemiBold", int(h * .17)), fill=yazi, anchor="lm")
    if cfg.get("kontur"):  # kart çevrelerine belirgin çizgi
        d = ImageDraw.Draw(img, "RGBA")
        for b in cfg["mk"] + cfg["ilce"]:
            d.rounded_rectangle([b[0] + 2, b[1] + 2, b[2] - 2, b[3] - 2], radius=max(10, (b[3] - b[1]) // 7),
                                outline=tuple(cfg["kontur"]), width=3)
    img.save(yol, quality=93)
    return yol


def _gunes_parilti(img, gunes, faz):
    """Arka plandaki güneş: nabız gibi parlayan ışık + yavaş dönen ışınlar (döngü kesintisiz)."""
    import math
    gx, gy, r = gunes
    k = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(k)
    a = .5 + .5 * math.sin(2 * math.pi * faz)
    for j in range(12):  # ışınlar (döngü başına 2 ışın aralığı döner)
        t = 2 * math.pi * (j / 12 + faz / 6)
        uz = r * (3.6 if j % 2 else 2.8)
        uc = (gx + math.cos(t) * uz, gy + math.sin(t) * uz)
        y1 = (gx + math.cos(t + .07) * r * .9, gy + math.sin(t + .07) * r * .9)
        y2 = (gx + math.cos(t - .07) * r * .9, gy + math.sin(t - .07) * r * .9)
        d.polygon([y1, uc, y2], fill=(255, 250, 215, int(95 + 60 * a)))
    k = k.filter(ImageFilter.GaussianBlur(4))
    d = ImageDraw.Draw(k)
    for i in range(10, 0, -1):  # parıltı
        rr = r * (1 + i * .22 * (1 + .12 * a))
        d.ellipse([gx - rr, gy - rr, gx + rr, gy + rr], fill=(255, 245, 200, int((10 + 9 * a) * (11 - i) / 3)))
    k = k.filter(ImageFilter.GaussianBlur(4))
    img.paste(k, (0, 0), k)


def dikey(img, H=1920):
    """Kartı 9:16 tam ekrana yayar: üst/alt boşluk kartın kendi kenar renkleriyle (gerilip yumuşatılmış) dolar."""
    w, h = img.size
    if h >= H:
        return img.resize((w, H))
    ust = (H - h) // 2
    alt = H - h - ust
    tuval = Image.new("RGB", (w, H))
    bant = 24
    from PIL import ImageOps
    # kenardaki bölgenin ayna yansıması, yumuşatılmış (çizgi/şerit oluşmaz)
    u = img.crop((0, 0, w, 40)).resize((5, 2), Image.BOX).resize((w, ust + bant), Image.BICUBIC).filter(ImageFilter.GaussianBlur(40))
    a = img.crop((0, h - 20, w, h)).resize((5, 2), Image.BOX).resize((w, alt + bant), Image.BICUBIC).filter(ImageFilter.GaussianBlur(40))
    tuval.paste(u, (0, 0))
    tuval.paste(a, (0, ust + h - bant))
    m = Image.new("L", (w, h), 255)
    md = ImageDraw.Draw(m)
    for i in range(bant):  # ek yerleri yumuşak geçiş
        md.line([(0, i), (w, i)], fill=int(255 * i / bant))
        md.line([(0, h - 1 - i), (w, h - 1 - i)], fill=int(255 * i / bant))
    tuval.paste(img, (0, ust), m)
    return tuval


def guvenli(kare, zemin=None, oran=0.8):
    """Telefonda tam ekranda (20:9) Instagram 9:16 videonun yanlarını kırpar: içerik %80'e küçültülüp ortalanır,
    kenarlar aynı karenin bulanık hali ile dolar (yakınlaşma yok). zemin: önceden hazırlanmış bulanık arka plan."""
    W, H = kare.size
    if zemin is None:
        zemin = guvenli_zemin(kare)
    w, h = int(W * oran), int(H * oran)
    out = zemin.copy()
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=28, fill=255)
    out.paste(kare.resize((w, h), Image.LANCZOS), ((W - w) // 2, (H - h) // 2), m.filter(ImageFilter.GaussianBlur(1.5)))
    return out


def guvenli_zemin(kare):
    from PIL import ImageEnhance
    W, H = kare.size
    z = kare.resize((W // 8, H // 8)).filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BICUBIC)
    return ImageEnhance.Brightness(z).enhance(.85)


def animasyon(il, n, merkez, ilce_v, tarih, yol, sure=6, fps=20, tam_ekran=True):
    """Hareketli kart: ikonlardaki güneş/bulut/yağmur/kar/rüzgar hareket eder; arka plan o günün havasına göre:
    güneşli gün parlayan güneş, yağmurlu gün yağmur, karlı gün kar, sisli gün sis, rüzgarlı gün rüzgar çizgileri
    (yalnız arka planda, kartların üstüne binmez). Yakınlaşma yok. Döner: mp4 yolu."""
    import random, shutil, subprocess, tempfile
    import hareket
    ikonlar = []
    kart(il, n, merkez, ilce_v, tarih, yol, _ikonlar=ikonlar)  # ikonsuz taban
    taban = Image.open(yol).convert("RGB")
    cfg = json.load(open(os.path.join(KLASOR, il, "kutular.json"), encoding="utf-8"))[n]
    tur = hava_turu(merkez.get(tarih.isoformat()))
    dy = (1920 - taban.height) // 2 if tam_ekran else 0
    if tam_ekran:
        taban = dikey(taban)
    W, H = taban.size
    maske = kart_maskesi(cfg, (W, H), dy).filter(ImageFilter.GaussianBlur(2))
    sis = None
    if tur == "sis":
        rnd = random.Random(1)
        sis = Image.new("RGBA", (W * 2, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sis)
        for _ in range(30):
            cx, cy, r = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(150, 320)
            for k in (0, W):
                sd.ellipse([cx + k - r, cy - r * .4, cx + k + r, cy + r * .4], fill=(240, 242, 245, 70))
        sis = sis.filter(ImageFilter.GaussianBlur(40))
    tmp = tempfile.mkdtemp()
    N = int(sure * fps)
    for i in range(N):
        f = i / N
        im = taban.copy()
        if tur in ("gunes", "az_bulut") and cfg.get("gunes"):
            gx, gy, r = cfg["gunes"]
            _gunes_parilti(im, [gx, gy + dy, r], f)
        kat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(kat)
        rnd = random.Random(7)
        if tur in ("yagmur", "firtina"):
            hareket._yagmur(d, W, H, f, rnd)
        elif tur == "kar":
            hareket._kar(d, W, H, f, rnd)
        elif tur == "ruzgar":
            hareket._ruzgar(d, W, H, f, rnd)
        elif tur == "sis":
            x = int(f * W)
            kat.alpha_composite(sis.crop((x, 0, x + W, H)))
        if tur not in ("gunes", "az_bulut", "bulut"):
            kat.putalpha(Image.composite(kat.getchannel("A"), Image.new("L", (W, H), 0), maske))
            im.paste(kat, (0, 0), kat)
        if tur == "firtina" and (0.40 <= f < 0.44 or 0.48 <= f < 0.50):  # şimşek
            im.paste(Image.new("RGB", (W, H), (235, 235, 255)), (0, 0), maske.point(lambda v: v * 60 // 255))
        for tp, cx, cy, s in ikonlar:
            tasarim.ikon3d(im, tp, cx, cy + dy, s, f)
        if i == 0:
            im.crop((0, dy, W, dy + Image.open(yol).height)).save(yol, quality=93)
        if tam_ekran:
            if i == 0:
                zemin = guvenli_zemin(im)
            im = guvenli(im, zemin)
            if i == 0:
                im.save(yol[:-4] + "_kapak.jpg", quality=93)
        im.save(os.path.join(tmp, f"k{i:03d}.jpg"), quality=90)
    mp4 = yol[:-4] + "_hareketli.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(tmp, "k%03d.jpg"),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", mp4], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return mp4


def video(yol, sure=12):
    """Tam ekran 9:16 Reels: hareketli kart döngüsü + Pixabay müziği; yakınlaşma ve çerçeve yok. Döner: (mp4, kapak, sanatçı)"""
    import glob, subprocess
    hareketli, mp4, kapak = yol[:-4] + "_hareketli.mp4", yol[:-4] + ".mp4", yol[:-4] + "_kapak.jpg"
    parcalar = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "muzik", "*.mp3")))
    komut = ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-t", str(sure), "-i", hareketli]
    sanatci = None
    if parcalar:
        parca = parcalar[(datetime.date.today().toordinal() + 5) % len(parcalar)]
        komut += ["-i", parca]
        ad = os.path.basename(parca)[3:-4]
        sanatci = {"alex": "Alex Morgan", "atlasaudio": "AtlasAudio", "nastelbom": "Nastelbom",
                   "velariomusic": "VelarioMusic", "andriig": "AndriiG"}.get(ad.split("-")[0], ad.split("-")[0])
    komut += ["-map", "0:v", "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
              "-movflags", "+faststart"]
    if sanatci:
        komut += ["-map", "1:a", "-af", f"afade=t=in:d=0.8,afade=t=out:st={sure - 2}:d=2", "-c:a", "aac", "-b:a", "128k"]
    subprocess.run(komut + ["-t", str(sure), mp4], check=True)
    return mp4, kapak, sanatci
