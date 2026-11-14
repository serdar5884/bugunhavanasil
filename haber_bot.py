#!/usr/bin/env python3
"""
Son dakika hava haberleri: sel, heyelan, çığ, kar, fırtına, hortum, su baskını...
Kaynaklar: AA, NTV, Habertürk haber akışları (RSS) – sadece son 3 saatte yayımlananlar.

Telif için: haber metni ve fotoğrafı KOPYALANMAZ. Kart bizim tasarımımız; üzerinde sadece
olay türü + il + kendi kısa cümlemiz + kaynak adı yer alır.

Kullanım:
  python haber_bot.py --cikti yayin/uyari     -> yeni hava haberleri için hikâye görseli üretir, paylasim.json'a ekler
  python haber_bot.py --demo                  -> örnek veriyle görsel
  python haber_bot.py --liste                 -> görsel üretmeden, filtreye takılan haberleri listeler (test)
"""
import argparse, datetime, hashlib, html, json, os, re
from PIL import Image, ImageDraw
from hava_bot import font, paylas_satiri, destek_bandi
from uyari_bot import PLAKA, http_get, _sar, _zemin, DURUM_DOSYA, W, H, gonderi_surumu

KAYNAKLAR = [
    ("AA", "https://www.aa.com.tr/tr/rss/default?cat=guncel"),
    # TRT Haber çıkarıldı: akışında yayın tarihi yok, eski haberler güncelmiş gibi görünüyordu
    ("NTV", "https://www.ntv.com.tr/turkiye.rss"),
    ("Habertürk", "https://www.haberturk.com/rss/kategori/gundem.xml"),
]

# (olay adı, kart rengi, desen) – kelime sınırlı, "Selin", "Selçuk" gibi isimlere takılmasın
OLAYLAR = [
    ("ÇIĞ", (90, 170, 230), r"\bçığ(\b|a\b|da\b|ın\b|ı\b| altında)"),
    ("HEYELAN", (170, 110, 60), r"\bheyelan"),
    ("SEL", (40, 120, 200), r"\bsel(\b|e\b|de\b|den\b|i\b| felaketi| suları)|\btaşkın|\bsu baskını|\bsu bastı|\bsağanak.{0,30}(bastı|bodrum|su bastı)"),
    ("HORTUM", (110, 110, 130), r"\bhortum(\b|u\b|un\b)"),
    ("FIRTINA", (80, 90, 140), r"\bfırtına(\b|da\b|nın\b|sı\b|sında\b)|\blodos\b|\bkuvvetli rüzgar|\bçatı(sı|ları)? uçtu"),
    ("KAR", (150, 180, 220), r"\b(yoğun |kuvvetli )?kar (yağışı|nedeniyle|esareti|kalınlığı|geliyor|uyarısı|bekleniyor|alarmı|yağacak)|\bkar yağacak|\btipi\b|\bkardan kapan|\bkar.{0,25}kapandı"),
    ("YAĞIŞ", (60, 110, 170), r"\bkuvvetli (yağış|sağanak)|\bsağanak yağış|\bşiddetli yağış|\byoğun yağış"),
    ("DOLU", (120, 150, 170), r"\bdolu (yağışı|yağdı|vurdu)"),
    ("YILDIRIM", (200, 170, 40), r"\byıldırım (düştü|isabet)"),
]
HARIC = (r"hava durumu|bugün hava|yarın hava|hafta sonu hava|hava nasıl olacak|"
         r"maç|lig\b|derbi|fırtına gibi|fırtına kopardı|siyasi|şehit|helikopter|kaza kırım|hikaye|hikayesi")
# Olay henüz olmamışsa (bekleniyor, uyarı, risk, -acak/-ecek) "HAVA UYARISI" olarak paylaşılır
TAHMIN = r"bekleniyor|beklenen|uyarı|alarm|risk|tehlike|geliyor|kapıda|\b\w+(acak|ecek|acağı|eceği)\b"
GUNLUK_SINIR = 8
# Can kaybı varsa hikâyeye ek olarak gönderi de paylaşılır (sadece bu olaylarda)
CAN_KAYBI_OLAYLAR = {"SEL", "ÇIĞ"}
CAN_KAYBI = r"şehit|hayatını kaybetti|hayatını kaybeden|hayatını yitir|can verdi|can kaybı|cansız beden|öldü\b|ölü sayısı|ölen\b|ölümüne|cenaze"  # bir günde en fazla bu kadar haber hikâyesi


def bulunma(il):
    """İl adına Türkçe bulunma eki: Rize'de, Artvin'de, Muş'ta, Ankara'da"""
    son_unlu = next((c for c in reversed(il.lower()) if c in "aeıioöuü"), "e")
    unlu = "a" if son_unlu in "aıou" else "e"
    sert = il.lower()[-1] in "fstkçşhp"
    return f"{il}'{'t' if sert else 'd'}{unlu}"


CUMLE = {
    "ÇIĞ": "çığ düştü", "HEYELAN": "heyelan meydana geldi", "SEL": "sel meydana geldi",
    "HORTUM": "hortum etkili oldu", "FIRTINA": "fırtına etkili oldu", "KAR": "kar yağışı etkili oluyor",
    "DOLU": "dolu yağışı etkili oldu", "YILDIRIM": "yıldırım düştü", "YAĞIŞ": "kuvvetli yağış etkili oluyor",
}
CUMLE_TAHMIN = {
    "ÇIĞ": "çığ tehlikesi var", "HEYELAN": "heyelan riski var", "SEL": "sel ve su baskını riski var",
    "HORTUM": "hortum riski var", "FIRTINA": "fırtına bekleniyor", "KAR": "yoğun kar yağışı bekleniyor",
    "DOLU": "dolu yağışı bekleniyor", "YILDIRIM": "gök gürültülü sağanak bekleniyor", "YAĞIŞ": "kuvvetli yağış bekleniyor",
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


TR = datetime.timezone(datetime.timedelta(hours=3))
EN_ESKI_SAAT = 3  # sadece son 3 saatte yayımlanan haberler


def tarih_coz(metin):
    """RSS (RFC822), Atom (ISO) ve TRT biçimlerini dener; çözülemezse None."""
    import email.utils
    metin = (metin or "").strip()
    if not metin:
        return None
    try:
        t = email.utils.parsedate_to_datetime(metin)
        return t if t.tzinfo else t.replace(tzinfo=TR)
    except Exception:
        pass
    for f in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            t = datetime.datetime.strptime(metin.replace("Z", "+00:00"), f)
            return t if t.tzinfo else t.replace(tzinfo=TR)
        except ValueError:
            continue
    return None


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
            tarih = tarih_coz(_etiket(o, ["pubDate", "published", "updated", "dc:date", "haber_tarihi", "tarih", "haber_yayin_tarihi"]))
            if baslik:
                haberler.append({"kaynak": kaynak, "baslik": re.sub(r"\s+", " ", baslik),
                                 "ozet": re.sub(r"\s+", " ", ozet)[:300], "link": link, "tarih": tarih})
    return haberler


def hava_haberi_mi(h):
    # Olay ve il BAŞLIKTA geçmeli (özetteki tesadüfi kelimeler yanıltmasın)
    metin = h["baslik"].lower()
    if re.search(HARIC, metin):
        return None
    simdi = datetime.datetime.now(TR)
    if not h.get("tarih") or not (simdi - datetime.timedelta(hours=EN_ESKI_SAAT) <= h["tarih"] <= simdi + datetime.timedelta(minutes=30)):
        return None  # tarihi olmayan ya da eski haber paylaşılmaz
    olay = next(((ad, renk) for ad, renk, desen in OLAYLAR if re.search(desen, metin)), None)
    if not olay:
        return None
    # Türkiye'de bir il geçmeli (yurt dışı haberlerini ele)
    il = next((p for p in PLAKA[1:] if re.search(rf"\b{p}\b", h["baslik"])), None)
    if not il:
        return None
    tahmin = bool(re.search(TAHMIN, metin))
    can = not tahmin and olay[0] in CAN_KAYBI_OLAYLAR and bool(re.search(CAN_KAYBI, metin))
    return {"olay": olay[0], "renk": olay[1], "il": il, "can_kaybi": can, "tahmin": tahmin}


def haber_gorseli(x, yol):
    renk = x["renk"]
    img = _zemin((20, 22, 30), tuple(int(c * .5) for c in renk))
    d = ImageDraw.Draw(img, "RGBA")
    M = 70
    tahmin = x.get("tahmin")
    band_renk = (235, 120, 20) if tahmin else (215, 30, 40)
    ust, alt = ("HAVA UYARISI", "BEKLENİYOR") if tahmin else ("SON DAKİKA", "HAVA HABER")
    d.rectangle([0, 150, W, 270], fill=band_renk)
    f = font("ExtraBold", 72)
    d.text((M, 165), ust, font=f, fill="white")
    d.text((M + d.textlength(ust, font=f) + 24, 190), alt, font=font("Bold", 42), fill=(255, 235, 220))
    d.text((M, 80), "BUGÜN HAVA NASIL?", font=font("Bold", 34), fill=(255, 205, 0))
    # olay türü – büyük
    f_o = font("ExtraBold", 190 if len(x["olay"]) <= 5 else 150)
    if tahmin:
        etiket = "DİKKAT"
        fe = font("ExtraBold", 54)
        d.text((W / 2 - d.textlength(etiket, font=fe) / 2, 410), etiket, font=fe, fill=(255, 190, 90))
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
    if x.get("can_kaybi"):
        cumle = f"{bulunma(x['il'])} {'sel' if x['olay'] == 'SEL' else 'çığ'} felaketi: can kaybı yaşandı."
    elif tahmin:
        cumle = f"{bulunma(x['il'])} {CUMLE_TAHMIN[x['olay']]}."
    else:
        cumle = f"{bulunma(x['il'])} {CUMLE[x['olay']]}."
    f_c = font("SemiBold", 52)
    y = 1010
    for s in _sar(d, cumle, f_c, W - 2 * M):
        d.text((W / 2 - d.textlength(s, font=f_c) / 2, y), s, font=f_c, fill="white"); y += 68
    t = x.get("tarih") or datetime.datetime.now(TR)
    zaman = "Haber saati: " + t.astimezone(TR).strftime("%d.%m.%Y  %H:%M")
    f_z = font("Medium", 38)
    d.text((W / 2 - d.textlength(zaman, font=f_z) / 2, y + 30), zaman, font=f_z, fill=(255, 255, 255, 200))
    not_ = "Bölgedeyseniz resmi kurumların uyarılarını takip edin."
    f_n = font("Medium", 34)
    d.text((W / 2 - d.textlength(not_, font=f_n) / 2, H - 370), not_, font=f_n, fill=(255, 255, 255, 210))
    d.text((M, H - 130), f"Haber kaynağı: {x['kaynak']}", font=font("SemiBold", 32), fill=(255, 255, 255, 190))
    destek_bandi(d, M, H - 300, W - M, H - 170)
    img.save(yol, quality=93)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--liste", action="store_true")
    ap.add_argument("--cikti", default="cikti_uyari")
    a = ap.parse_args()

    if a.demo:
        adaylar = [{"kaynak": "AA", "baslik": "Rize'de sel", "ozet": "", "link": "x", "olay": "SEL", "renk": OLAYLAR[2][1], "il": "Rize", "can_kaybi": True, "tarih": datetime.datetime.now(TR)},
                   {"kaynak": "NTV", "baslik": "x", "ozet": "", "link": "y", "olay": "KAR", "renk": (150, 180, 220), "il": "Erzurum", "tahmin": True, "tarih": datetime.datetime.now(TR)}]
    else:
        adaylar = []
        for h in haberleri_cek():
            x = hava_haberi_mi(h)
            if x:
                adaylar.append({**h, **x})
    if a.liste:
        for x in adaylar:
            print(f"[{x['olay']}] {x['il']} | {x['kaynak']} | {x.get('tarih')} | {x['baslik']}")
        print(len(adaylar), "hava haberi bulundu")
        return

    durum = json.load(open(DURUM_DOSYA, encoding="utf-8")) if os.path.exists(DURUM_DOSYA) and not a.demo else {}
    gorulen = set(durum.get("haber_gorulen", []))
    bugun = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y-%m-%d")
    bugun_sayi = sum(1 for g in gorulen if g.startswith(bugun))
    # ilk çalıştırmada akıştaki tüm haberleri "görüldü" say (eski haber birikmesin) – listede değilse


    os.makedirs(a.cikti, exist_ok=True)
    pj = os.path.join(a.cikti, "paylasim.json")
    paylasim = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else []
    yeni, yeni_idler = [], []
    for x in adaylar:
        # aynı gün aynı ilde aynı olay = tek haber (farklı sitelerden gelse de)
        anahtar = f"{bugun}|{x['il']}|{x['olay']}" + ("|tahmin" if x.get("tahmin") else "")
        haber_id = "h:" + hashlib.md5(re.sub(r"\W", "", x["baslik"].lower()).encode()).hexdigest()[:12]
        if anahtar in gorulen or anahtar in yeni or haber_id in gorulen:
            continue
        yeni_idler.append(haber_id)
        if bugun_sayi + len(yeni) >= GUNLUK_SINIR:
            break
        yeni.append(anahtar)
        dosya = os.path.join(a.cikti, f"haber_{bugun.replace('-', '')}_{len(yeni)}_{hashlib.md5(anahtar.encode()).hexdigest()[:6]}.jpg")
        haber_gorseli(x, dosya)
        kayit = {"gorsel": dosya, "tur": "hikaye",
                 "caption": (f"⚠️ HAVA UYARISI | {bulunma(x['il'])} {CUMLE_TAHMIN[x['olay']]}.\nHaber kaynağı: {x['kaynak']}"
                             if x.get("tahmin") else
                             f"🔴 SON DAKİKA | {x['il']}: {x['olay'].capitalize()}\nHaber kaynağı: {x['kaynak']}")}
        if x.get("can_kaybi"):
            kayit["tur"] = "hikaye+gonderi"
            kayit["gonderi_gorsel"] = gonderi_surumu(dosya)
            olay = "sel" if x["olay"] == "SEL" else "çığ"
            kayit["caption"] = (f"🔴 SON DAKİKA | {bulunma(x['il'])} {olay} felaketi: can kaybı yaşandı.\n\n"
                                f"Hayatını kaybedenlerin yakınlarına başsağlığı diliyoruz. Bölgedeyseniz lütfen "
                                f"resmi kurumların uyarılarını takip edin.\n\nHaber kaynağı: {x['kaynak']}\n\n"
                                f"📤 Bölgede yakını olanlarla paylaş.\n🔔 Gelişmelerden haberdar olmak için takip edip bildirimleri açın: @bugun.hava.nasil\n\n"
                                f"#sondakika #{'sel' if x['olay'] == 'SEL' else 'çığ'} #{x['il'].lower()} #havadurumu")
        paylasim.append(kayit)
        print("Yeni hava haberi:", anahtar, "|", x["kaynak"], "|", x["baslik"])
    json.dump(paylasim, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not a.demo:
        durum["haber_gorulen"] = (list(gorulen) + yeni + yeni_idler)[-2000:]
        json.dump(durum, open(DURUM_DOSYA, "w", encoding="utf-8"), ensure_ascii=False)
    print(len(yeni), "yeni hava haberi görseli")


if __name__ == "__main__":
    main()
