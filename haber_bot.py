#!/usr/bin/env python3
"""
Son dakika hava haberleri: sel, heyelan, çığ, kar, fırtına, hortum, su baskını...
Kaynaklar: AA, TRT Haber, NTV, Habertürk haber akışları (RSS).

Telif için: haber metni ve fotoğrafı KOPYALANMAZ. Kart bizim tasarımımız; üzerinde sadece
olay türü + il + kendi kısa cümlemiz + kaynak adı yer alır.

Kullanım:
  python haber_bot.py --cikti yayin/uyari     -> yeni hava haberleri için hikâye görseli üretir, paylasim.json'a ekler
  python haber_bot.py --demo                  -> örnek veriyle görsel
  python haber_bot.py --liste                 -> görsel üretmeden, filtreye takılan haberleri listeler (test)
"""
import argparse, datetime, hashlib, html, json, os, re
from PIL import Image, ImageDraw
from hava_bot import font
from uyari_bot import PLAKA, http_get, _sar, _zemin, DURUM_DOSYA, W, H

KAYNAKLAR = [
    ("AA", "https://www.aa.com.tr/tr/rss/default?cat=guncel"),
    ("TRT Haber", "https://www.trthaber.com/xml_mobile.php?tur=xml_genel&kategori=gundem&adet=50"),
    ("NTV", "https://www.ntv.com.tr/turkiye.rss"),
    ("Habertürk", "https://www.haberturk.com/rss/kategori/gundem.xml"),
]

# (olay adı, kart rengi, desen) – kelime sınırlı, "Selin", "Selçuk" gibi isimlere takılmasın
OLAYLAR = [
    ("ÇIĞ", (90, 170, 230), r"\bçığ(\b|a\b|da\b|ın\b|ı\b| altında)"),
    ("HEYELAN", (170, 110, 60), r"\bheyelan"),
    ("SEL", (40, 120, 200), r"\bsel(\b|e\b|de\b|den\b|i\b| felaketi| suları)|\btaşkın|\bsu baskını|\bsu bastı|\bsağanak.{0,30}(bastı|bodrum|su bastı)"),
    ("HORTUM", (110, 110, 130), r"\bhortum(\b|u\b|un\b)"),
    ("FIRTINA", (80, 90, 140), r"\bfırtına(\b|da\b|nın\b)|\bkuvvetli rüzgar|\bçatı(sı|ları)? uçtu"),
    ("KAR", (150, 180, 220), r"\bkar (yağışı|nedeniyle|esareti|kalınlığı)|\btipi\b|\bkardan kapan|\bkar.{0,25}kapandı"),
    ("DOLU", (120, 150, 170), r"\bdolu (yağışı|yağdı|vurdu)"),
    ("YILDIRIM", (200, 170, 40), r"\byıldırım (düştü|isabet)"),
]
HARIC = r"uyarı|uyarısı|hava durumu|tahmin|meteoroloji|bugün hava|yarın hava|hafta sonu hava|maç|lig\b|derbi|fırtına gibi|siyasi"
GUNLUK_SINIR = 8  # bir günde en fazla bu kadar haber hikâyesi


def bulunma(il):
    """İl adına Türkçe bulunma eki: Rize'de, Artvin'de, Muş'ta, Ankara'da"""
    son_unlu = next((c for c in reversed(il.lower()) if c in "aeıioöuü"), "e")
    unlu = "a" if son_unlu in "aıou" else "e"
    sert = il.lower()[-1] in "fstkçşhp"
    return f"{il}'{'t' if sert else 'd'}{unlu}"


CUMLE = {
    "ÇIĞ": "çığ düştü", "HEYELAN": "heyelan meydana geldi", "SEL": "sel ve su baskını yaşandı",
    "HORTUM": "hortum etkili oldu", "FIRTINA": "fırtına hayatı olumsuz etkiledi", "KAR": "kar yağışı ulaşımı etkiliyor",
    "DOLU": "dolu yağışı etkili oldu", "YILDIRIM": "yıldırım düştü",
}


def _etiket(xml, adlar):
    for ad in adlar:
        m = re.search(rf"<{ad}[^>]*>(.*?)</{ad}>", xml, re.S | re.I)
        if m:
            t = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", m.group(1), flags=re.S)
            return html.unescape(re.sub(r"<[^>]+>", " ", t)).strip()
        m = re.search(rf"<{ad}[^>]*href=\"([^\"]+)\"", xml, re.I)
        if m:
            return m.group(1)
    return ""


def haberleri_cek():
    haberler = []
    for kaynak, url in KAYNAKLAR:
        try:
            xml = http_get(url)
        except Exception as e:
            print(f"{kaynak} alınamadı: {e}")
            continue
        ogeler = re.findall(r"<(item|entry|haber)\b[^>]*>(.*?)</\1>", xml, re.S | re.I)
        for _, o in ogeler:
            baslik = _etiket(o, ["title", "haber_manset", "baslik"])
            ozet = _etiket(o, ["description", "summary", "haber_aciklama", "spot"])
            link = _etiket(o, ["link", "haber_link", "guid"])
            if baslik:
                haberler.append({"kaynak": kaynak, "baslik": re.sub(r"\s+", " ", baslik),
                                 "ozet": re.sub(r"\s+", " ", ozet)[:300], "link": link})
    return haberler


def hava_haberi_mi(h):
    metin = (h["baslik"] + " " + h["ozet"][:150]).lower()
    if re.search(HARIC, h["baslik"].lower()):
        return None
    olay = next(((ad, renk) for ad, renk, desen in OLAYLAR if re.search(desen, metin)), None)
    if not olay:
        return None
    # Türkiye'de bir il geçmeli (yurt dışı haberlerini ele)
    tum = h["baslik"] + " " + h["ozet"]
    il = next((p for p in PLAKA[1:] if re.search(rf"\b{p}\b", tum)), None)
    if not il:
        return None
    return {"olay": olay[0], "renk": olay[1], "il": il}


def haber_gorseli(x, yol):
    renk = x["renk"]
    img = _zemin((20, 22, 30), tuple(int(c * .5) for c in renk))
    d = ImageDraw.Draw(img, "RGBA")
    M = 70
    kirmizi = (215, 30, 40)
    # SON DAKİKA bandı
    d.rectangle([0, 150, W, 270], fill=kirmizi)
    f = font("ExtraBold", 72)
    d.text((M, 165), "SON DAKİKA", font=f, fill="white")
    d.text((M + d.textlength("SON DAKİKA", font=f) + 24, 190), "HAVA HABER", font=font("Bold", 42), fill=(255, 220, 220))
    d.text((M, 80), "BUGÜN HAVA NASIL?", font=font("Bold", 34), fill=(255, 205, 0))
    # olay türü – büyük
    f_o = font("ExtraBold", 190 if len(x["olay"]) <= 5 else 150)
    ow = d.textlength(x["olay"], font=f_o)
    d.text((W / 2 - ow / 2 + 5, 505), x["olay"], font=f_o, fill=(0, 0, 0, 120))
    d.text((W / 2 - ow / 2, 500), x["olay"], font=f_o, fill="white")
    # il
    il = x["il"].replace("i", "İ").replace("ı", "I").upper()
    f_il = font("ExtraBold", 96)
    iw = d.textlength(il, font=f_il)
    d.rounded_rectangle([W / 2 - iw / 2 - 40, 790, W / 2 + iw / 2 + 40, 920], radius=30, fill=renk)
    d.text((W / 2 - iw / 2, 800), il, font=f_il, fill="white")
    # kendi cümlemiz
    cumle = f"{bulunma(x['il'])} {CUMLE[x['olay']]}."
    f_c = font("SemiBold", 52)
    y = 1010
    for s in _sar(d, cumle, f_c, W - 2 * M):
        d.text((W / 2 - d.textlength(s, font=f_c) / 2, y), s, font=f_c, fill="white"); y += 68
    zaman = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%d.%m.%Y  %H:%M")
    f_z = font("Medium", 38)
    d.text((W / 2 - d.textlength(zaman, font=f_z) / 2, y + 30), zaman, font=f_z, fill=(255, 255, 255, 200))
    not_ = "Bölgedeyseniz resmi kurumların uyarılarını takip edin."
    f_n = font("Medium", 34)
    d.text((W / 2 - d.textlength(not_, font=f_n) / 2, H - 260), not_, font=f_n, fill=(255, 255, 255, 210))
    d.text((M, H - 140), f"Haber kaynağı: {x['kaynak']}", font=font("SemiBold", 34), fill=(255, 255, 255, 190))
    img.save(yol, quality=93)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--liste", action="store_true")
    ap.add_argument("--cikti", default="cikti_uyari")
    a = ap.parse_args()

    if a.demo:
        adaylar = [{"kaynak": "AA", "baslik": "Rize'de sel", "ozet": "", "link": "x", "olay": "SEL", "renk": OLAYLAR[2][1], "il": "Rize"},
                   {"kaynak": "TRT Haber", "baslik": "x", "ozet": "", "link": "y", "olay": "ÇIĞ", "renk": OLAYLAR[0][1], "il": "Hakkari"}]
    else:
        adaylar = []
        for h in haberleri_cek():
            x = hava_haberi_mi(h)
            if x:
                adaylar.append({**h, **x})
    if a.liste:
        for x in adaylar:
            print(f"[{x['olay']}] {x['il']} | {x['kaynak']} | {x['baslik']}")
        print(len(adaylar), "hava haberi bulundu")
        return

    durum = json.load(open(DURUM_DOSYA, encoding="utf-8")) if os.path.exists(DURUM_DOSYA) and not a.demo else {}
    gorulen = set(durum.get("haber_gorulen", []))
    bugun = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%d")
    bugun_sayi = sum(1 for g in gorulen if g.startswith(bugun))

    os.makedirs(a.cikti, exist_ok=True)
    pj = os.path.join(a.cikti, "paylasim.json")
    paylasim = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else []
    yeni = []
    for x in adaylar:
        # aynı gün aynı ilde aynı olay = tek haber (farklı sitelerden gelse de)
        anahtar = f"{bugun}|{x['il']}|{x['olay']}"
        if anahtar in gorulen or anahtar in yeni:
            continue
        if bugun_sayi + len(yeni) >= GUNLUK_SINIR:
            break
        yeni.append(anahtar)
        dosya = os.path.join(a.cikti, f"haber_{bugun.replace('-', '')}_{len(yeni)}_{hashlib.md5(anahtar.encode()).hexdigest()[:6]}.jpg")
        haber_gorseli(x, dosya)
        paylasim.append({"gorsel": dosya, "tur": "hikaye",
                         "caption": f"🔴 SON DAKİKA | {x['il']}: {x['olay'].capitalize()}\nHaber kaynağı: {x['kaynak']}"})
        print("Yeni hava haberi:", anahtar, "|", x["kaynak"], "|", x["baslik"])
    json.dump(paylasim, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not a.demo:
        durum["haber_gorulen"] = (list(gorulen) + yeni)[-1000:]
        json.dump(durum, open(DURUM_DOSYA, "w", encoding="utf-8"), ensure_ascii=False)
    print(len(yeni), "yeni hava haberi görseli")


if __name__ == "__main__":
    main()
