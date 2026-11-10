#!/usr/bin/env python3
"""
Türkiye bölge bölge hava durumu – Instagram görsel üretici
Veri kaynağı: MGM (servis.mgm.gov.tr – www.mgm.gov.tr'nin kendi kullandığı servis)

Kullanım:
  python hava_bot.py            -> MGM'den gerçek veri çeker, cikti/ klasörüne 7 görsel + caption yazar
  python hava_bot.py --demo     -> internet olmadan örnek veriyle görsel üretir (tasarım testi)
  python hava_bot.py --gun 2    -> yarının tahmini (1 = bugün, 2 = yarın ... 5)
"""
import argparse, datetime, json, os, random, sys, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- BÖLGELER
BOLGELER = {
    "Marmara": ["Balıkesir", "Bilecik", "Bursa", "Çanakkale", "Edirne", "İstanbul",
                "Kırklareli", "Kocaeli", "Sakarya", "Tekirdağ", "Yalova"],
    "Ege": ["Afyonkarahisar", "Aydın", "Denizli", "İzmir", "Kütahya", "Manisa", "Muğla", "Uşak"],
    "Akdeniz": ["Adana", "Antalya", "Burdur", "Hatay", "Isparta", "Kahramanmaraş", "Mersin", "Osmaniye"],
    "İç Anadolu": ["Aksaray", "Ankara", "Çankırı", "Eskişehir", "Karaman", "Kayseri", "Kırıkkale",
                   "Kırşehir", "Konya", "Nevşehir", "Niğde", "Sivas", "Yozgat"],
    "Karadeniz": ["Amasya", "Artvin", "Bartın", "Bayburt", "Bolu", "Çorum", "Düzce", "Giresun",
                  "Gümüşhane", "Karabük", "Kastamonu", "Ordu", "Rize", "Samsun", "Sinop",
                  "Tokat", "Trabzon", "Zonguldak"],
    "Doğu Anadolu": ["Ağrı", "Ardahan", "Bingöl", "Bitlis", "Elazığ", "Erzincan", "Erzurum",
                     "Hakkari", "Iğdır", "Kars", "Malatya", "Muş", "Tunceli", "Van"],
    "Güneydoğu Anadolu": ["Adıyaman", "Batman", "Diyarbakır", "Gaziantep", "Kilis", "Mardin",
                          "Siirt", "Şanlıurfa", "Şırnak"],
}

# Bölge başlık renkleri (gradient üst, alt)
BOLGE_RENK = {
    "Marmara": ((24, 92, 168), (10, 40, 90)),
    "Ege": ((0, 128, 150), (6, 55, 80)),
    "Akdeniz": ((214, 104, 34), (110, 38, 30)),
    "İç Anadolu": ((176, 120, 40), (80, 52, 22)),
    "Karadeniz": ((24, 120, 80), (8, 52, 40)),
    "Doğu Anadolu": ((92, 80, 170), (34, 30, 80)),
    "Güneydoğu Anadolu": ((190, 70, 60), (85, 28, 30)),
}

# MGM hadise kodları -> (Türkçe metin, ikon tipi)
HADISE = {
    "A": ("Açık", "gunes"), "AB": ("Az Bulutlu", "az_bulut"), "PB": ("Parçalı Bulutlu", "az_bulut"),
    "CB": ("Çok Bulutlu", "bulut"), "HY": ("Hafif Yağmurlu", "yagmur"), "Y": ("Yağmurlu", "yagmur"),
    "KY": ("Kuvvetli Yağmurlu", "yagmur"), "KKY": ("Karla Karışık Yağmur", "karla_yagmur"),
    "HKY": ("Hafif Kar Yağışlı", "kar"), "K": ("Kar Yağışlı", "kar"), "YKY": ("Yoğun Kar Yağışlı", "kar"),
    "HSY": ("Hafif Sağanak", "yagmur"), "SY": ("Sağanak Yağışlı", "yagmur"),
    "KSY": ("Kuvvetli Sağanak", "yagmur"), "MSY": ("Mevzi Sağanak", "yagmur"),
    "DY": ("Dolu", "kar"), "GSY": ("Gök Gürültülü Sağanak", "firtina"),
    "KGY": ("Kuvvetli Gök Gürültülü", "firtina"), "SIS": ("Sisli", "sis"), "PUS": ("Puslu", "sis"),
    "DMN": ("Dumanlı", "sis"), "KF": ("Kum Fırtınası", "sis"), "R": ("Rüzgarlı", "bulut"),
    "GKR": ("Güneyli Kuvvetli Rüzgar", "bulut"), "KKR": ("Kuzeyli Kuvvetli Rüzgar", "bulut"),
    "SCK": ("Sıcak", "gunes"), "SGK": ("Soğuk", "az_bulut"), "HHY": ("Yağışlı", "yagmur"),
}

# ---------------------------------------------------------------- MGM VERİ
MGM = "https://servis.mgm.gov.tr/web"
HEADERS = {"Origin": "https://www.mgm.gov.tr", "Referer": "https://www.mgm.gov.tr/",
           "User-Agent": "Mozilla/5.0"}


def mgm_get(yol, deneme=3):
    url = MGM + yol
    for i in range(deneme):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == deneme - 1:
                raise RuntimeError(f"MGM isteği başarısız: {url} -> {e}")
            time.sleep(2)


_MERKEZ = {}


def merkezleri_yukle():
    """81 il merkezini tek istekte alır: {il adı: günlük tahmin istasyon no}."""
    if not _MERKEZ:
        for m in mgm_get("/merkezler/iller"):
            _MERKEZ[m["il"]] = m["gunlukTahminIstNo"]
    return _MERKEZ


def il_tahmin(il, gun):
    istno = merkezleri_yukle().get(il)
    if istno is None:
        m = mgm_get("/merkezler?il=" + urllib.parse.quote(il))
        istno = (m[0] if isinstance(m, list) else m)["gunlukTahminIstNo"]
    t = mgm_get(f"/tahminler/gunluk?istno={istno}")
    t = t[0] if isinstance(t, list) else t
    # MGM'de "Gün1" her zaman bugün değil (akşam saatlerinde yarın olabiliyor) -> tarihe göre seç
    hedef = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date() + datetime.timedelta(days=gun - 1)
    k = None
    for i in range(1, 6):
        if str(t.get(f"tarihGun{i}", ""))[:10] == hedef.isoformat():
            k = i
            break
    if k is None:
        raise RuntimeError(f"{il}: {hedef} tarihli tahmin yok")
    return {"il": il, "hadise": t.get(f"hadiseGun{k}"), "min": t.get(f"enDusukGun{k}"),
            "max": t.get(f"enYuksekGun{k}"), "ruzgar": t.get(f"ruzgarHizGun{k}")}


def demo_tahmin(il, gun):
    rnd = random.Random(il + str(gun))
    kod = rnd.choice(["A", "AB", "PB", "CB", "HY", "Y", "SY", "GSY", "SIS", "HKY"])
    mx = rnd.randint(4, 24)
    return {"il": il, "hadise": kod, "min": mx - rnd.randint(4, 11), "max": mx,
            "ruzgar": rnd.randint(5, 35)}


# ---------------------------------------------------------------- ÇİZİM
W, H = 1080, 1350
FONT_DIR = "/usr/share/fonts/opentype/inter/"


def font(stil, boyut):
    adaylar = [os.path.join(os.path.dirname(__file__), "fonts", f"Inter-{stil}.otf"),
               os.path.join(FONT_DIR, f"Inter-{stil}.otf"),
               os.path.join(FONT_DIR, f"Inter-{stil}.ttf"),
               f"/usr/share/fonts/truetype/inter/Inter-{stil}.ttf",
               "C:/Windows/Fonts/segoeuib.ttf" if stil in ("Bold", "ExtraBold") else "C:/Windows/Fonts/segoeui.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for a in adaylar:
        if os.path.exists(a):
            return ImageFont.truetype(a, boyut)
    return ImageFont.load_default()


def gradient(ust, alt):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(ust[i] * (1 - k) + alt[i] * k) for i in range(3)))
    return img


def ikon(d, tip, cx, cy, s):
    """Basit vektör hava ikonları (emoji fontu gerektirmez)."""
    sari, beyaz, gri, mavi = (255, 200, 40), (255, 255, 255), (200, 210, 225), (110, 190, 255)

    def gunes(x, y, r):
        for a in range(0, 360, 45):
            import math
            rx, ry = math.cos(math.radians(a)), math.sin(math.radians(a))
            d.line([(x + rx * r * 1.35, y + ry * r * 1.35), (x + rx * r * 1.75, y + ry * r * 1.75)],
                   fill=sari, width=max(2, s // 14))
        d.ellipse([x - r, y - r, x + r, y + r], fill=sari)

    def bulut(x, y, k, renk=beyaz):
        d.ellipse([x - k * .9, y - k * .35, x - k * .1, y + k * .45], fill=renk)
        d.ellipse([x - k * .45, y - k * .75, x + k * .4, y + k * .3], fill=renk)
        d.ellipse([x + k * .05, y - k * .45, x + k * .85, y + k * .45], fill=renk)
        d.rectangle([x - k * .5, y, x + k * .45, y + k * .45], fill=renk)

    if tip == "gunes":
        gunes(cx, cy, s * .32)
    elif tip == "az_bulut":
        gunes(cx - s * .15, cy - s * .12, s * .24)
        bulut(cx + s * .08, cy + s * .12, s * .42)
    elif tip == "bulut":
        bulut(cx - s * .12, cy - s * .08, s * .32, gri)
        bulut(cx + s * .06, cy + s * .08, s * .45)
    elif tip in ("yagmur", "firtina", "kar", "karla_yagmur"):
        bulut(cx, cy - s * .12, s * .45, gri if tip == "firtina" else beyaz)
        for i in range(3):
            x = cx - s * .22 + i * s * .22
            y = cy + s * .24
            if tip == "kar" or (tip == "karla_yagmur" and i == 1):
                r = s * .05
                d.ellipse([x - r, y - r + s * .06, x + r, y + r + s * .06], fill=beyaz)
            elif tip == "firtina" and i == 1:
                d.polygon([(x + s * .04, y - s * .02), (x - s * .07, y + s * .14), (x, y + s * .14),
                           (x - s * .05, y + s * .28), (x + s * .1, y + s * .1), (x + s * .02, y + s * .1)],
                          fill=sari)
            else:
                d.line([(x + s * .04, y), (x - s * .03, y + s * .14)], fill=mavi, width=max(3, s // 12))
    elif tip == "sis":
        for i in range(4):
            y = cy - s * .24 + i * s * .16
            off = s * .08 if i % 2 else 0
            d.rounded_rectangle([cx - s * .36 + off, y, cx + s * .36 - (s * .08 - off), y + s * .07],
                                radius=s * .035, fill=gri)


# ---------------------------------------------------------------- HAVAYA GÖRE ARKA PLAN
import math
SAHNE_GRUP = {"gunes": "gunesli", "az_bulut": "parcali", "bulut": "bulutlu", "yagmur": "yagmurlu",
              "firtina": "firtinali", "kar": "karli", "karla_yagmur": "karli", "sis": "sisli"}


def baskin_sahne(veriler):
    """Bölgedeki illerin çoğunluğuna göre sahne seçer. Yağış/kar az ilde olsa da öne çıkar."""
    say = {}
    for v in veriler:
        tip = HADISE.get(v["hadise"] or "", ("", "bulut"))[1]
        g = SAHNE_GRUP[tip]
        say[g] = say.get(g, 0) + 1
    n = max(1, len(veriler))
    if say.get("karli", 0) / n >= 0.3:
        return "karli"
    yagis = say.get("yagmurlu", 0) + say.get("firtinali", 0)
    if yagis / n >= 0.35:
        return "firtinali" if say.get("firtinali", 0) >= say.get("yagmurlu", 0) else "yagmurlu"
    if say.get("sisli", 0) / n >= 0.4:
        return "sisli"
    acik = say.get("gunesli", 0) + say.get("parcali", 0)
    if acik >= say.get("bulutlu", 0):
        return "gunesli" if say.get("gunesli", 0) >= say.get("parcali", 0) else "parcali"
    return "bulutlu"


SAHNE_RENK = {  # gökyüzü üst, alt
    "gunesli": ((30, 120, 220), (120, 195, 245)),
    "parcali": ((50, 120, 200), (140, 180, 220)),
    "bulutlu": ((80, 95, 115), (150, 160, 175)),
    "yagmurlu": ((35, 50, 70), (80, 95, 115)),
    "firtinali": ((18, 20, 38), (60, 55, 80)),
    "karli": ((120, 150, 185), (215, 228, 240)),
    "sisli": ((140, 150, 160), (200, 205, 210)),
}


def _bulut_katman(img, rnd, adet, renk, alfa, y_aralik, boyut, blur):
    from PIL import ImageFilter
    kat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(kat)
    for _ in range(adet):
        cx, cy = rnd.randint(-100, W + 100), rnd.randint(*y_aralik)
        k = rnd.randint(*boyut)
        for _ in range(7):
            ox, oy = rnd.randint(-k, k), rnd.randint(-k // 3, k // 4)
            r = rnd.randint(k // 2, k)
            d.ellipse([cx + ox - r, cy + oy - r * .7, cx + ox + r, cy + oy + r * .7], fill=renk + (alfa,))
    img.alpha_composite(kat.filter(ImageFilter.GaussianBlur(blur)))


def kar_ciz(img, rnd):
    """Belirgin kar: hafif gölgeli büyük taneler + kristal şekilleri, ön planda keskin."""
    from PIL import ImageFilter
    golge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    kar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd, d = ImageDraw.Draw(golge), ImageDraw.Draw(kar)
    for _ in range(380):  # yuvarlak taneler
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        r = rnd.choice([3, 4, 5, 5, 6, 7, 9, 11])
        gd.ellipse([x - r - 2, y - r - 2, x + r + 2, y + r + 2], fill=(20, 40, 70, 90))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rnd.randint(200, 255)))
    for _ in range(30):  # kristal kar taneleri
        x, y = rnd.randint(20, W - 20), rnd.randint(20, H - 20)
        R = rnd.randint(14, 30)
        w = max(2, R // 7)
        for k in range(6):
            a = math.radians(k * 60 + rnd.random() * 0)
            ux, uy = math.cos(a), math.sin(a)
            uc = (x + ux * R, y + uy * R)
            for hedef, kal in ((gd, w + 3), (d, w)):
                renk = (20, 40, 70, 90) if hedef is gd else (255, 255, 255, 245)
                hedef.line([(x, y), uc], fill=renk, width=kal)
                for t in (0.5, 0.75):  # dallar
                    px, py = x + ux * R * t, y + uy * R * t
                    for s_ in (-1, 1):
                        b = a + s_ * math.radians(45)
                        hedef.line([(px, py), (px + math.cos(b) * R * .3, py + math.sin(b) * R * .3)],
                                   fill=renk, width=max(1, kal - 1))
    img.alpha_composite(golge.filter(ImageFilter.GaussianBlur(4)))
    img.alpha_composite(kar)


def sahne_ciz(sahne, bolge):
    from PIL import ImageFilter
    rnd = random.Random(bolge + sahne)
    ust, alt = SAHNE_RENK[sahne]
    img = gradient(ust, alt).convert("RGBA")

    if sahne in ("gunesli", "parcali"):
        if sahne == "parcali":
            _bulut_katman(img, rnd, 6, (255, 255, 255), 200, (200, 700), (90, 170), 14)
        else:
            _bulut_katman(img, rnd, 2, (255, 255, 255), 150, (900, 1200), (80, 130), 18)
    elif sahne == "bulutlu":
        _bulut_katman(img, rnd, 10, (210, 215, 225), 170, (-50, 600), (120, 220), 22)
        _bulut_katman(img, rnd, 8, (240, 242, 246), 140, (300, 1100), (100, 200), 18)
    elif sahne in ("yagmurlu", "firtinali"):
        koyu = (55, 60, 75) if sahne == "yagmurlu" else (30, 30, 48)
        _bulut_katman(img, rnd, 14, koyu, 220, (-100, 450), (140, 240), 24)
        if sahne == "firtinali":
            sim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(sim)
            x, y = rnd.randint(650, 900), -20
            pts = [(x, y)]
            while y < 230:
                x += rnd.randint(-45, 45); y += rnd.randint(35, 60); pts.append((x, y))
            d.line(pts, fill=(255, 250, 220, 255), width=6)
            img.alpha_composite(sim.filter(ImageFilter.GaussianBlur(10)))
            img.alpha_composite(sim)
        yag = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(yag)
        for _ in range(700):
            x, y = rnd.randint(-200, W), rnd.randint(-50, H)
            l = rnd.randint(25, 60)
            d.line([(x, y), (x + l * .25, y + l)], fill=(200, 215, 235, rnd.randint(60, 140)), width=2)
        img.alpha_composite(yag)
    elif sahne == "karli":
        _bulut_katman(img, rnd, 10, (235, 240, 248), 160, (-80, 400), (130, 220), 22)
        d = ImageDraw.Draw(img)
        d.ellipse([-300, H - 140, W + 300, H + 300], fill=(245, 248, 252, 255))
    elif sahne == "sisli":
        for i in range(9):
            _bulut_katman(img, rnd, 3, (235, 238, 240), 120, (i * 150, i * 150 + 120), (150, 260), 40)

    # okunabilirlik için hafif koyu perde
    perde = Image.new("RGBA", (W, H), (10, 20, 35, {"gunesli": 35, "parcali": 55, "karli": 70, "sisli": 85}.get(sahne, 55)))
    img.alpha_composite(perde)
    if sahne == "karli":
        kar_ciz(img, rnd)
    if sahne in ("gunesli", "parcali"):
            isik = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(isik)
            gx, gy = W - 170, 150
            for r, a in [(520, 40), (360, 60), (230, 90), (150, 160)]:
                d.ellipse([gx - r, gy - r, gx + r, gy + r], fill=(255, 230, 150, a))
            for i in range(12):
                ang = math.radians(i * 30 + 8)
                d.polygon([(gx, gy), (gx + math.cos(ang - .05) * 1500, gy + math.sin(ang - .05) * 1500),
                           (gx + math.cos(ang + .05) * 1500, gy + math.sin(ang + .05) * 1500)],
                          fill=(255, 240, 190, 18))
            img.alpha_composite(isik.filter(ImageFilter.GaussianBlur(30)))
            d2 = ImageDraw.Draw(img)
            d2.ellipse([gx - 95, gy - 95, gx + 95, gy + 95], fill=(255, 245, 205, 255))

    return img.convert("RGB")


def metni_sigdir(d, metin, f_stil, boyut, max_w):
    while boyut > 14:
        f = font(f_stil, boyut)
        if d.textlength(metin, font=f) <= max_w:
            return f
        boyut -= 1
    return font(f_stil, boyut)


def bolge_gorseli(bolge, veriler, tarih, cikti, gun_no=1):
    sahne = baskin_sahne(veriler)
    kart_dolgu = {"yagmurlu": (255, 255, 255, 34), "firtinali": (255, 255, 255, 34),
                  "karli": (25, 45, 80, 175)}.get(sahne, (15, 30, 55, 85))
    img = sahne_ciz(sahne, bolge)
    d = ImageDraw.Draw(img, "RGBA")

    # Başlık
    M = 56
    d.text((M, 52), "BUGÜN HAVA NASIL?" if gun_no == 1 else "YARIN HAVA NASIL?" if gun_no == 2 else "HAVA NASIL?",
           font=font("Bold", 32), fill=(255, 255, 255, 215))
    baslik = bolge.replace("i", "İ").replace("ı", "I").upper() + " BÖLGESİ"
    bosluk = 250 if sahne in ("gunesli", "parcali") else 0  # güneşe yer bırak
    d.text((M, 90), baslik, font=metni_sigdir(d, baslik, "ExtraBold", 64, W - 2 * M - bosluk), fill="white")
    gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    aylar = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
             "Eylül", "Ekim", "Kasım", "Aralık"]
    tstr = f"{tarih.day} {aylar[tarih.month]} {tarih.year}, {gunler[tarih.weekday()]}"
    d.text((M, 172), tstr, font=font("Medium", 32), fill=(255, 255, 255, 220))

    # Kartlar: 2 sütun
    n = len(veriler)
    satir = (n + 1) // 2
    top, bottom = 240, H - 80
    gap = 14
    kart_h = min(150, (bottom - top - gap * (satir - 1)) / satir)
    kart_w = (W - 2 * M - gap) / 2
    blok_h = satir * kart_h + (satir - 1) * gap
    top = top + (bottom - top - blok_h) / 2

    for i, v in enumerate(veriler):
        c, r = i % 2, i // 2
        x0 = M + c * (kart_w + gap)
        y0 = top + r * (kart_h + gap)
        d.rounded_rectangle([x0, y0, x0 + kart_w, y0 + kart_h], radius=min(24, kart_h * .25),
                            fill=kart_dolgu, outline=(255, 255, 255, 70), width=2)
        metin, tip = HADISE.get(v["hadise"] or "", (v["hadise"] or "-", "bulut"))
        ik = kart_h * .62
        ikon(d, tip, x0 + 18 + ik / 2, y0 + kart_h / 2, int(ik))
        tx = x0 + 30 + ik
        sicak = f"{v['max']}°" if v["max"] is not None else "-"
        f_sic = font("ExtraBold", int(kart_h * .38))
        sw = d.textlength(sicak, font=f_sic)
        f_min = font("Medium", int(kart_h * .2))
        mn = f"/ {v['min']}°" if v["min"] is not None else ""
        mw = d.textlength(mn, font=f_min)
        sag = x0 + kart_w - 20
        isim_w = sag - mw - sw - 16 - tx
        f_il = metni_sigdir(d, v["il"], "Bold", int(kart_h * .27), isim_w)
        d.text((tx, y0 + kart_h * .17), v["il"], font=f_il, fill="white")
        f_dur = metni_sigdir(d, metin, "Regular", int(kart_h * .19), sag - tx)
        d.text((tx, y0 + kart_h * .56), metin, font=f_dur, fill=(255, 255, 255, 200))
        d.text((sag - mw - sw - 8, y0 + kart_h * .1), sicak, font=f_sic, fill="white")
        d.text((sag - mw, y0 + kart_h * .22), mn, font=f_min, fill=(255, 255, 255, 190))

    d.text((M, H - 56), "Kaynak: Meteoroloji Genel Müdürlüğü (mgm.gov.tr)",
           font=font("Regular", 24), fill=(255, 255, 255, 170))
    yol = os.path.join(cikti, f"{list(BOLGELER).index(bolge) + 1:02d}_{bolge.replace(' ', '_')}.jpg")
    img.save(yol, quality=93)
    return yol


def caption(tarih, tum, gun=1):
    bas = {1: "Bugün hava nasıl?", 2: "Yarın hava nasıl?"}.get(gun, "Hava nasıl?")
    sat = [f"🌤 {bas} Türkiye bölge bölge hava durumu – {tarih.strftime('%d.%m.%Y')}", ""]
    hepsi = [v for vs in tum.values() for v in vs if v["max"] is not None]
    if hepsi:
        sicak = max(hepsi, key=lambda v: v["max"])
        soguk = min(hepsi, key=lambda v: v["min"] if v["min"] is not None else 99)
        sat += [f"🔥 En sıcak: {sicak['il']} {sicak['max']}°C",
                f"❄️ En soğuk: {soguk['il']} {soguk['min']}°C", ""]
    sat += ["Kendi bölgeni bulmak için kaydır 👉", "",
            "Kaynak: Meteoroloji Genel Müdürlüğü (MGM)", "",
            "#havadurumu #hava #türkiye #meteoroloji #mgm #istanbul #ankara #izmir"]
    return "\n".join(sat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--gun", type=int, default=1, choices=range(1, 6))
    ap.add_argument("--cikti", default="cikti")
    a = ap.parse_args()

    os.makedirs(a.cikti, exist_ok=True)
    tarih = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date() + datetime.timedelta(days=a.gun - 1)
    getir = demo_tahmin if a.demo else il_tahmin
    if not a.demo:
        merkezleri_yukle()
    from concurrent.futures import ThreadPoolExecutor
    hatalar = []

    def guvenli(il):
        try:
            return getir(il, a.gun)
        except Exception as e:
            hatalar.append(f"{il}: {e}")
            return {"il": il, "hadise": None, "min": None, "max": None, "ruzgar": None}

    tum = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for bolge, iller in BOLGELER.items():
            tum[bolge] = list(ex.map(guvenli, iller))
    for bolge in BOLGELER:
        print(bolge, baskin_sahne(tum[bolge]), "->", bolge_gorseli(bolge, tum[bolge], tarih, a.cikti, a.gun), flush=True)

    with open(os.path.join(a.cikti, "caption.txt"), "w", encoding="utf-8") as f:
        f.write(caption(tarih, tum, a.gun))
    with open(os.path.join(a.cikti, "veri.json"), "w", encoding="utf-8") as f:
        json.dump(tum, f, ensure_ascii=False, indent=1)
    if hatalar:
        print("UYARI – veri alınamayan iller:\n  " + "\n  ".join(hatalar))
        if len(hatalar) > 10:
            sys.exit(1)


if __name__ == "__main__":
    main()
