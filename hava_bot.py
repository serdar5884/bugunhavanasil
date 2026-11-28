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
    "İç Anadolu": ["Sivas", "Aksaray", "Ankara", "Çankırı", "Eskişehir", "Karaman", "Kayseri",
                   "Kırıkkale", "Kırşehir", "Konya", "Nevşehir", "Niğde", "Yozgat"],
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
FAZ = None  # animasyon karesi (0..1); None = sabit görsel
FONT_DIR = "/usr/share/fonts/opentype/inter/"


NUNITO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Nunito.ttf")
# NeHaberÖzet ile aynı yuvarlak yazı tipi; başlıklar çok kalın, açıklamalar ince (belirgin kontrast)
NUNITO_AGIRLIK = {"Black": "Black", "ExtraBold": "Black", "Bold": "ExtraBold", "SemiBold": "Bold",
                  "Medium": "Regular", "Regular": "Regular", "Light": "Light"}


def font(stil, boyut):
    if os.path.exists(NUNITO):
        try:
            f = ImageFont.truetype(NUNITO, boyut)
            f.set_variation_by_name(NUNITO_AGIRLIK.get(stil, "Regular"))
            return f
        except Exception:
            pass
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
    """Parlak 3D hava ikonları (tasarim.py). d: çizilen görselin ImageDraw nesnesi."""
    from tasarim import ikon3d
    ikon3d(d._image, tip, cx, cy, int(s), FAZ)


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
        if FAZ is not None:  # bulutlar yavaşça sağa sola süzülür
            cx += math.sin(2 * math.pi * (FAZ + cy / 900)) * (25 + boyut[0] * .15)
        k = rnd.randint(*boyut)
        for _ in range(7):
            ox, oy = rnd.randint(-k, k), rnd.randint(-k // 3, k // 4)
            r = rnd.randint(k // 2, k)
            d.ellipse([cx + ox - r, cy + oy - r * .7, cx + ox + r, cy + oy + r * .7], fill=renk + (alfa,))
    img.alpha_composite(kat.filter(ImageFilter.GaussianBlur(blur)))


def kar_ciz(img, rnd):
    """Belirgin kar: hafif gölgeli büyük taneler + kristal şekilleri, ön planda keskin.
    Animasyonda desen dikeyde P periyotlu tekrar eder; döngü başına P kadar iner (yavaş ve kesintisiz)."""
    from PIL import ImageFilter
    golge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    kar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd, d = ImageDraw.Draw(golge), ImageDraw.Draw(kar)
    P = (H + 60) / 2

    def konumlar(x, y, r):
        if FAZ is None:
            return [(x, y)]
        yy = (y % P + FAZ * P) % P - 30
        sal = math.sin(2 * math.pi * (FAZ + x / 300)) * (6 + r * .8)
        return [(x + sal, yy), (x + sal, yy + P)]
    adet = 380 if FAZ is None else 200
    for _ in range(adet):  # yuvarlak taneler
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        r = rnd.choice([3, 4, 5, 5, 6, 7, 9, 11])
        alfa = rnd.randint(200, 255)
        for x_, y_ in konumlar(x, y, r):
            gd.ellipse([x_ - r - 2, y_ - r - 2, x_ + r + 2, y_ + r + 2], fill=(20, 40, 70, 90))
            d.ellipse([x_ - r, y_ - r, x_ + r, y_ + r], fill=(255, 255, 255, alfa))
    for _ in range(30 if FAZ is None else 16):  # kristal kar taneleri
        x0, y0 = rnd.randint(20, W - 20), rnd.randint(20, H - 20)
        R = rnd.randint(14, 30)
        w = max(2, R // 7)
        don = (FAZ or 0) * 60  # kristaller yavaşça döner (60° simetri -> kesintisiz)
        for x, y in konumlar(x0, y0, 9):
            for k in range(6):
                a = math.radians(k * 60 + don)
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
        if sahne == "firtinali" and (FAZ is None or 0.42 <= FAZ < 0.5 or 0.55 <= FAZ < 0.58):
            if FAZ is not None:  # şimşek çakınca gökyüzü aydınlanır
                img.alpha_composite(Image.new("RGBA", (W, H), (230, 230, 255, 45)))
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
            if FAZ is not None:  # 3 tam tur aşağı akış (yağmur hızlı)
                dy = FAZ * 3 * (H + 50)
                y = (y + 50 + dy) % (H + 50) - 50
                x = (x + 200 + dy * .25) % (W + 200) - 200
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
            nabiz = .5 + .5 * math.sin(2 * math.pi * (FAZ or 0))
            for r, a in [(520, 45), (360, 70), (230, 105), (150, 180)]:
                d.ellipse([gx - r, gy - r, gx + r, gy + r], fill=(255, 230, 150, int(a * (.85 + .3 * nabiz))))
            for i in range(12):  # ışınlar: döngü başına 60° (iki ışın aralığı) döner, kesintisiz
                ang = math.radians(i * 30 + 8 + (FAZ or 0) * 60)
                gen = .07 if i % 2 else .045
                d.polygon([(gx, gy), (gx + math.cos(ang - gen) * 1500, gy + math.sin(ang - gen) * 1500),
                           (gx + math.cos(ang + gen) * 1500, gy + math.sin(ang + gen) * 1500)],
                          fill=(255, 240, 190, int(28 + 20 * nabiz)))
            img.alpha_composite(isik.filter(ImageFilter.GaussianBlur(18)))
            d2 = ImageDraw.Draw(img)
            d2.ellipse([gx - 95, gy - 95, gx + 95, gy + 95], fill=(255, 245, 205, 255))

    return img.convert("RGB")


HESAP = "@bugun.hava.nasil"
PAYLAS_METIN = "Sevdiklerinle paylaş"


def paylas_ikon(d, x, y, s, renk=(255, 205, 0)):
    """Basit 'paylaş' (kağıt uçak) ikonu."""
    d.polygon([(x, y + s * .45), (x + s, y), (x + s * .62, y + s), (x + s * .45, y + s * .58)], fill=renk)
    d.polygon([(x + s * .45, y + s * .58), (x + s, y), (x + s * .52, y + s * .82)], fill=tuple(int(c * .75) for c in renk))


def paylas_satiri(d, x, y, boyut=30, sag_hizali_W=None):
    """'[ikon] Sevdiklerinle paylaş · @bugun.hava.nasil' satırı. sag_hizali_W verilirse sağa yaslar."""
    f1, f2 = font("Bold", boyut), font("SemiBold", boyut)
    m1, m2 = PAYLAS_METIN + "  ·  ", HESAP
    gen = boyut * 1.2 + d.textlength(m1, font=f1) + d.textlength(m2, font=f2)
    if sag_hizali_W:
        x = sag_hizali_W - gen
    paylas_ikon(d, x, y + boyut * .12, boyut * .85)
    x += boyut * 1.2
    d.text((x, y), m1, font=f1, fill=(255, 205, 0))
    d.text((x + d.textlength(m1, font=f1), y), m2, font=f2, fill="white")


def zil_ikon(d, x, y, s, renk):
    d.pieslice([x, y, x + s, y + s * 1.3], 180, 360, fill=renk)
    d.rectangle([x, y + s * .62, x + s, y + s * .85], fill=renk)
    d.polygon([(x - s * .12, y + s * .85), (x + s * 1.12, y + s * .85), (x + s, y + s * .7), (x, y + s * .7)], fill=renk)
    d.ellipse([x + s * .38, y + s * .86, x + s * .62, y + s * 1.08], fill=renk)


def destek_bandi(d, x0, y0, x1, y1):
    """Büyük sarı bant: takip + bildirim + paylaş çağrısı."""
    lacivert = (18, 30, 55)
    h = y1 - y0
    d.rounded_rectangle([x0, y0, x1, y1], radius=h * .22, fill=(255, 205, 0))
    s = h * .42
    zil_ikon(d, x0 + h * .3, y0 + h * .22, s, lacivert)
    tx = x0 + h * .3 + s + h * .28
    maxw = x1 - tx - h * .25
    f1 = metni_sigdir(d, "Takip edip bildirimleri açarak destek ol!", "ExtraBold", int(h * .32), maxw)
    d.text((tx, y0 + h * .13), "Takip edip bildirimleri açarak destek ol!", font=f1, fill=lacivert)
    alt = f"{PAYLAS_METIN}  ·  {HESAP}"
    f2 = metni_sigdir(d, alt, "Bold", int(h * .27), maxw)
    d.text((tx, y0 + h * .56), alt, font=f2, fill=(60, 50, 0))


YORUM_METIN = "Yoruma il ya da ilçe yaz, tahmini hemen al!"


def yorum_cagrisi(d, x0, y0, x1, y1):
    """Beyaz şerit: konuşma balonu + YORUM_METIN"""
    h = y1 - y0
    d.rounded_rectangle([x0, y0, x1, y1], radius=h / 2, fill=(255, 255, 255, 235))
    lac = (18, 30, 55)
    bx, by, bs = x0 + h * .45, y0 + h * .2, h * .6
    d.rounded_rectangle([bx, by, bx + bs * 1.25, by + bs * .8], radius=bs * .22, fill=lac)
    d.polygon([(bx + bs * .25, by + bs * .75), (bx + bs * .2, by + bs * 1.05), (bx + bs * .55, by + bs * .78)], fill=lac)
    for i in range(3):
        cx = bx + bs * (.32 + i * .3)
        d.ellipse([cx - bs * .07, by + bs * .33, cx + bs * .07, by + bs * .47], fill=(255, 205, 0))
    tx = bx + bs * 1.25 + h * .3
    f = metni_sigdir(d, YORUM_METIN, "ExtraBold", int(h * .5), x1 - tx - h * .4)
    d.text((tx, y0 + (h - f.size) / 2 - h * .05), YORUM_METIN, font=f, fill=lac)


def metni_sigdir(d, metin, f_stil, boyut, max_w):
    while boyut > 14:
        f = font(f_stil, boyut)
        if d.textlength(metin, font=f) <= max_w:
            return f
        boyut -= 1
    return font(f_stil, boyut)


# TÜİK 2024 yaklaşık nüfusları (bin): 14'ten fazla ili olan bölgede en az nüfuslu iller karta alınmaz
NUFUS = {"Samsun": 1377, "Trabzon": 823, "Ordu": 763, "Tokat": 596, "Zonguldak": 585, "Çorum": 527, "Giresun": 450,
         "Düzce": 411, "Kastamonu": 388, "Rize": 345, "Amasya": 337, "Bolu": 323, "Karabük": 252, "Sinop": 221,
         "Bartın": 204, "Artvin": 169, "Gümüşhane": 144, "Bayburt": 86}
EN_FAZLA_IL = 14


def kart_illeri(veriler):
    """Kartta en fazla 14 il: fazlaysa nüfusu en az olanlar çıkar, sıralama (ör. Sivas en üstte) korunur."""
    if len(veriler) <= EN_FAZLA_IL:
        return veriler
    kalan = sorted(veriler, key=lambda v: -NUFUS.get(v["il"], 10 ** 6))[:EN_FAZLA_IL]
    return [v for v in veriler if v in kalan]


def bolge_gorseli(bolge, veriler, tarih, cikti, gun_no=1):
    veriler = kart_illeri(veriler)
    sahne = baskin_sahne(veriler)
    kart_dolgu = {"yagmurlu": (255, 255, 255, 34), "firtinali": (255, 255, 255, 34),
                  "karli": (25, 45, 80, 175)}.get(sahne, (15, 30, 55, 85))
    img = sahne_ciz(sahne, bolge)
    d = ImageDraw.Draw(img, "RGBA")

    # Başlık (yeni tasarım): sarı "BUGÜN HAVA NASIL?", dev bölge adı, takvimli tarih
    from tasarim import cam_kart, takvim_ikon
    M = 56
    gun_kelime = {1: "BUGÜN", 2: "YARIN", "hs": "HAFTA SONU"}.get(gun_no, "BUGÜN")
    f_ust = font("ExtraBold", 46)
    d.text((M + 2, 42), f"{gun_kelime} HAVA NASIL?", font=f_ust, fill=(0, 0, 0, 100))
    d.text((M, 40), f"{gun_kelime} HAVA NASIL?", font=f_ust, fill=(255, 205, 0))
    baslik = bolge.replace("i", "İ").replace("ı", "I").upper() + " BÖLGESİ"
    f_b = metni_sigdir(d, baslik, "ExtraBold", 96, W - 2 * M - (230 if sahne in ("gunesli", "parcali") else 0))  # güneşe yer
    d.text((M + 4, 100), baslik, font=f_b, fill=(0, 0, 0, 120))
    d.text((M, 96), baslik, font=f_b, fill="white")
    gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    aylar = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
             "Eylül", "Ekim", "Kasım", "Aralık"]
    if gun_no == "hs":
        paz = tarih + datetime.timedelta(days=1)
        tstr = (f"{tarih.day}–{paz.day} {aylar[paz.month]} {paz.year}, Cumartesi–Pazar" if tarih.month == paz.month
                else f"{tarih.day} {aylar[tarih.month]} – {paz.day} {aylar[paz.month]}, Cumartesi–Pazar")
    else:
        tstr = f"{tarih.day} {aylar[tarih.month]} {tarih.year}, {gunler[tarih.weekday()]}"
    ty = 96 + f_b.size + 22
    takvim_ikon(d, M, ty + 4, 34)
    d.text((M + 50, ty), tstr, font=font("Medium", 34), fill=(255, 255, 255, 225))

    # Kartlar: 2 sütun
    n = len(veriler)
    satir = (n + 1) // 2
    top, bottom = 300, H - 225
    gap = 16
    kart_h = min(150, (bottom - top - gap * (satir - 1)) / satir)
    kart_w = (W - 2 * M - gap) / 2
    blok_h = satir * kart_h + (satir - 1) * gap
    top = top + (bottom - top - blok_h) / 2

    for i, v in enumerate(veriler):
        c, r = i % 2, i // 2
        x0 = M + c * (kart_w + gap)
        y0 = top + r * (kart_h + gap)
        cam_kart(img, [x0, y0, x0 + kart_w, y0 + kart_h], r=int(min(24, kart_h * .22)))
        metin, tip = HADISE.get(v["hadise"] or "", (v["hadise"] or "-", "bulut"))
        ik = kart_h * .74
        ikon(d, tip, x0 + 18 + ik / 2, y0 + kart_h / 2, int(ik))
        tx = x0 + 30 + ik
        if "paz" in v:  # hafta sonu kartı
            f_g = font("ExtraBold", int(kart_h * .24))
            f_k = font("SemiBold", int(kart_h * .17))
            sag = x0 + kart_w - 20
            satirlar = [("Cmt", v["max"], v["min"]), ("Paz", v["paz"]["max"], v["paz"]["min"])]
            gen = max(d.textlength(f"{a}  {mx}°/{mn}°", font=f_g) for a, mx, mn in satirlar)
            for j, (a, mx, mn) in enumerate(satirlar):
                yy = y0 + kart_h * (.14 + j * .40)
                d.text((sag - gen, yy + kart_h * .05), a, font=f_k, fill=(255, 205, 0))
                t = f"{mx}°" if mx is not None else "-"
                t2 = f"/{mn}°" if mn is not None else ""
                d.text((sag - d.textlength(t + t2, font=f_g), yy), t, font=f_g, fill="white")
                d.text((sag - d.textlength(t2, font=f_g), yy), t2, font=f_g, fill=(255, 255, 255, 170))
            f_il = metni_sigdir(d, v["il"], "Bold", int(kart_h * .34), sag - gen - 12 - tx)
            d.text((tx, y0 + kart_h * .1), v["il"], font=f_il, fill="white")
            f_dur = metni_sigdir(d, metin, "Regular", int(kart_h * .19), sag - gen - 12 - tx)
            d.text((tx, y0 + kart_h * .58), metin, font=f_dur, fill=(255, 255, 255, 200))
            continue
        sicak = f"{v['max']}°" if v["max"] is not None else "-"
        f_sic = font("ExtraBold", int(kart_h * .38))
        sw = d.textlength(sicak, font=f_sic)
        f_min = font("Medium", int(kart_h * .2))
        mn = f"/ {v['min']}°" if v["min"] is not None else ""
        mw = d.textlength(mn, font=f_min)
        sag = x0 + kart_w - 20
        isim_w = sag - mw - sw - 16 - tx
        if d.textlength(v["il"], font=font("Bold", int(kart_h * .34))) > isim_w * 1.12:  # belirgin küçülecekse iki satır
            # Uzun isim (Kahramanmaraş, Afyonkarahisar...): küçültmek yerine üstte isim, altta derece + hava durumu
            f_il = metni_sigdir(d, v["il"], "Bold", int(kart_h * .34), sag - tx)
            d.text((tx, y0 + kart_h * .08), v["il"], font=f_il, fill="white")
            f_s2, f_m2 = font("ExtraBold", int(kart_h * .32)), font("Medium", int(kart_h * .19))
            yy = y0 + kart_h * .5
            s2w, m2w = d.textlength(sicak, font=f_s2), d.textlength(mn, font=f_m2)
            d.text((sag - m2w - s2w - 6, yy), sicak, font=f_s2, fill="white")  # derece sağa yaslı
            d.text((sag - m2w, yy + kart_h * .1), mn, font=f_m2, fill=(255, 255, 255, 190))
            f_d2 = metni_sigdir(d, metin, "Regular", int(kart_h * .19), sag - m2w - s2w - 20 - tx)
            d.text((tx, yy + kart_h * .1), metin, font=f_d2, fill=(255, 255, 255, 200))
            continue
        f_il = metni_sigdir(d, v["il"], "Bold", int(kart_h * .34), isim_w)
        d.text((tx, y0 + kart_h * .1), v["il"], font=f_il, fill="white")
        f_dur = metni_sigdir(d, metin, "Regular", int(kart_h * .19), sag - tx)
        d.text((tx, y0 + kart_h * .58), metin, font=f_dur, fill=(255, 255, 255, 200))
        d.text((sag - mw - sw - 8, y0 + kart_h * .1), sicak, font=f_sic, fill="white")
        d.text((sag - mw, y0 + kart_h * .22), mn, font=f_min, fill=(255, 255, 255, 190))

    yorum_cagrisi(d, M + 40, H - 212, W - M - 40, H - 160)
    destek_bandi(d, M, H - 150, W - M, H - 50)
    d.text((M, H - 40), "Kaynak: Meteoroloji Genel Müdürlüğü (mgm.gov.tr)", font=font("Regular", 22), fill=(255, 255, 255, 170))
    ascii_ad = bolge.translate(str.maketrans("çğıöşüÇĞİÖŞÜ ", "cgiosuCGIOSU_"))
    yol = os.path.join(cikti, f"{list(BOLGELER).index(bolge) + 1:02d}_{ascii_ad}.jpg")
    img.save(yol, quality=93)
    return yol


def bolge_animasyon(bolge, veriler, tarih, cikti, gun_no=1, sure=6, fps=20):
    """Kartın hareketli hali: bulut, yağmur, kar, şimşek, güneş ışınları akar. MP4 (6 sn, kesintisiz döngü)."""
    global FAZ
    import shutil, subprocess, tempfile
    tmp = tempfile.mkdtemp()
    n = sure * fps
    try:
        for i in range(n):
            FAZ = i / n
            yol = bolge_gorseli(bolge, veriler, tarih, tmp, gun_no)
            os.replace(yol, os.path.join(tmp, f"k{i:03d}.jpg"))
    finally:
        FAZ = None
    ascii_ad = bolge.translate(str.maketrans("çğıöşüÇĞİÖŞÜ ", "cgiosuCGIOSU_"))
    mp4 = os.path.join(cikti, f"{list(BOLGELER).index(bolge) + 1:02d}_{ascii_ad}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
                    "-i", os.path.join(tmp, "k%03d.jpg"), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4], check=True)
    shutil.rmtree(tmp)
    return mp4


def _kucuk(il):
    return il.replace("İ", "i").replace("I", "ı").lower().replace(" ", "")


def etiketler(tum):
    """O günün öne çıkan illerine göre hashtag: en sıcak, en soğuk, kar/yağış alan iller + büyük şehirler."""
    hepsi = [v for vs in tum.values() for v in vs if v["max"] is not None]
    iller = []
    if hepsi:
        iller.append(max(hepsi, key=lambda v: v["max"])["il"])
        iller.append(min(hepsi, key=lambda v: v["min"] if v["min"] is not None else 99)["il"])
    tipler = {v["il"]: HADISE.get(v["hadise"] or "", ("", ""))[1] for v in hepsi}
    karli = [il for il, t in tipler.items() if t in ("kar", "karla_yagmur")]
    yagisli = [il for il, t in tipler.items() if t in ("yagmur", "firtina")]
    iller += karli[:3] + yagisli[:2]
    iller += ["İstanbul", "Ankara", "İzmir"]
    tekil = list(dict.fromkeys(iller))[:8]
    et = ["#havadurumu", "#hava", "#meteoroloji"] + [f"#{_kucuk(il)}havadurumu" for il in tekil]
    if karli:
        et += ["#kar", "#karyağışı"]
    if yagisli:
        et += ["#yağmur"]
    return " ".join(et)


def caption(tarih, tum, gun=1):
    bas = {1: "Bugün hava nasıl?", 2: "Yarın hava nasıl?", "hs": "Hafta sonu hava nasıl?"}.get(gun, "Hava nasıl?")
    sat = [f"🌤 {bas} Türkiye bölge bölge hava durumu – {tarih.strftime('%d.%m.%Y')}", ""]
    hepsi = [v for vs in tum.values() for v in vs if v["max"] is not None]
    if hepsi:
        sicak = max(hepsi, key=lambda v: v["max"])
        soguk = min(hepsi, key=lambda v: v["min"] if v["min"] is not None else 99)
        sat += [f"🔥 En sıcak: {sicak['il']} {sicak['max']}°C",
                f"❄️ En soğuk: {soguk['il']} {soguk['min']}°C", ""]
    sat += ["Kendi bölgeni bulmak için kaydır 👉", "",
            "💬 Senin ilinde hava nasıl? İlini yorumlara yaz, MGM verisiyle hemen cevaplayalım!",
            "(Örnek: \"Sivas yarın\", \"İzmir hafta sonu\" ya da \"Ankara 5 günlük\")", "",
            "🔔 Sayfamızı takip edip bildirimleri açarak bize destek olun!",
            "📤 Bu gönderiyi sevdiklerinle paylaş, hava durumunu kimse kaçırmasın.",
            "👉 @bugun.hava.nasil", "",
            "Kaynak: Meteoroloji Genel Müdürlüğü (MGM)", "",
            etiketler(tum)]
    return "\n".join(sat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--gun", type=int, default=1, choices=range(1, 6))
    ap.add_argument("--hafta-sonu", action="store_true", help="Cumartesi + Pazar tahmini (Cuma akşamı)")
    ap.add_argument("--cikti", default="cikti")
    ap.add_argument("--animasyon", action="store_true", help="Her bölge için hareketli 6 sn video da üret")
    a = ap.parse_args()
    gun_no = a.gun
    if a.hafta_sonu:
        bugun = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date()
        a.gun = (5 - bugun.weekday()) % 7 + 1  # Cumartesi'nin "gün" numarası
        gun_no = "hs"

    os.makedirs(a.cikti, exist_ok=True)
    tarih = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date() + datetime.timedelta(days=a.gun - 1)
    getir = demo_tahmin if a.demo else il_tahmin
    if not a.demo:
        merkezleri_yukle()
    from concurrent.futures import ThreadPoolExecutor
    hatalar = []

    def guvenli(il):
        try:
            if gun_no == "hs":
                v = getir(il, a.gun)
                v["paz"] = getir(il, a.gun + 1)
                return v
            return getir(il, a.gun)
        except Exception as e:
            hatalar.append(f"{il}: {e}")
            return {"il": il, "hadise": None, "min": None, "max": None, "ruzgar": None}

    tum = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for bolge, iller in BOLGELER.items():
            tum[bolge] = list(ex.map(guvenli, iller))
    for bolge in BOLGELER:
        print(bolge, baskin_sahne(tum[bolge]), "->", bolge_gorseli(bolge, tum[bolge], tarih, a.cikti, gun_no), flush=True)
    if a.animasyon:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=os.cpu_count() or 2) as ex:
            isler = [ex.submit(bolge_animasyon, b, tum[b], tarih, a.cikti, gun_no) for b in BOLGELER]
            for i in isler:
                try:
                    print("Hareketli:", i.result(), flush=True)
                except Exception as e:
                    print("Hareketli kart üretilemedi:", e, flush=True)

    with open(os.path.join(a.cikti, "caption.txt"), "w", encoding="utf-8") as f:
        f.write(caption(tarih, tum, gun_no))
    with open(os.path.join(a.cikti, "veri.json"), "w", encoding="utf-8") as f:
        json.dump(tum, f, ensure_ascii=False, indent=1)
    json.dump({"gun": gun_no, "tarih": tarih.isoformat()}, open(os.path.join(a.cikti, "ozet.json"), "w"))
    if hatalar:
        print("UYARI – veri alınamayan iller:\n  " + "\n  ".join(hatalar))
        if len(hatalar) > 10:
            sys.exit(1)


if __name__ == "__main__":
    main()
