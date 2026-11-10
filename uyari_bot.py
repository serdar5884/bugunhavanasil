#!/usr/bin/env python3
"""
Hava kaynaklı uyarılar ve kapalı yollar – Instagram hikâye/gönderi görseli üretici
Kaynaklar:
  - MGM MeteoUYARI (sarı / turuncu / kırmızı kodlu uyarılar)
  - KGM (Karayolları) trafiğe kapalı yollar – sadece hava kaynaklı olanlar (kar, heyelan, sel, çığ...)

Kullanım:
  python uyari_bot.py            -> yeni uyarı/kapanma varsa görsel üretir (daha önce paylaşılanları atlar)
  python uyari_bot.py --demo     -> örnek veriyle görsel üretir (tasarım testi)
  python uyari_bot.py --kesif    -> kaynaklardan gelen ham veriyi kesif/ klasörüne kaydeder (ilk kurulumda bana gönder)
"""
import argparse, datetime, hashlib, html, json, os, re, time, urllib.request
from PIL import Image, ImageDraw
from hava_bot import font, metni_sigdir, MGM, HEADERS, paylas_satiri, destek_bandi

W, H = 1080, 1920  # hikâye formatı
DURUM_DOSYA = "durum.json"
KGM_URL = "https://yol.kgm.gov.tr/KapaliYollar/api/workings/search"  # yol.kgm.gov.tr/kapaliyollar haritasının veri servisi

PLAKA = ["", "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya", "Artvin",
         "Aydın", "Balıkesir", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale",
         "Çankırı", "Çorum", "Denizli", "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum",
         "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane", "Hakkari", "Hatay", "Isparta", "Mersin",
         "İstanbul", "İzmir", "Kars", "Kastamonu", "Kayseri", "Kırklareli", "Kırşehir", "Kocaeli",
         "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş", "Nevşehir",
         "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Tekirdağ", "Tokat",
         "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt",
         "Karaman", "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova", "Karabük",
         "Kilis", "Osmaniye", "Düzce"]

SEVIYE = {  # renk, Türkçe ad, öncelik
    "red": ((200, 30, 35), "KIRMIZI", 3),
    "orange": ((235, 120, 20), "TURUNCU", 2),
    "yellow": ((240, 190, 20), "SARI", 1),
}
HADISE_TR = {
    "rain": "Kuvvetli Yağış", "thunderstorm": "Gök Gürültülü Sağanak", "snow": "Kar Yağışı",
    "wind": "Kuvvetli Rüzgar / Fırtına", "fog": "Yoğun Sis", "hot": "Aşırı Sıcak", "cold": "Aşırı Soğuk",
    "ice": "Buzlanma ve Don", "avalanche": "Çığ Tehlikesi", "dust": "Toz Taşınımı", "flood": "Sel",
}
HAVA_KELIME = ["kar", "tipi", "heyelan", "sel", "taşkın", "çığ", "buzlanma", "yağış", "fırtına",
               "su baskını", "kaya düşme", "toprak kayması", "olumsuz hava"]


# ---------------------------------------------------------------- VERİ ÇEKME
def http_get(url, headers=None, deneme=3):
    for i in range(deneme):
        try:
            req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            if i == deneme - 1:
                raise RuntimeError(f"{url} -> {e}")
            time.sleep(2)


def merkez_to_il(mid):
    """MGM merkez kodları 9 + plaka(2 hane) + ilçe şeklinde (ör. 93401 = İstanbul)."""
    s = str(mid)
    try:
        p = int(s[1:3]) if len(s) >= 5 and s[0] == "9" else int(s[:2])
        return PLAKA[p] if 0 < p < len(PLAKA) else None
    except ValueError:
        return None


def mgm_uyarilar():
    uyarilar = []
    for gun in ("today", "tomorrow"):
        try:
            veri = json.loads(http_get(f"{MGM}/meteoalarm/{gun}", HEADERS))
        except Exception as e:
            print("MGM uyarı alınamadı:", e)
            continue
        for u in veri if isinstance(veri, list) else [veri]:
            if not isinstance(u, dict):
                continue
            towns = u.get("towns") or {}
            weather = u.get("weather") or {}
            text = u.get("text") or {}
            for renk in ("red", "orange", "yellow"):
                ilceler = towns.get(renk) or []
                if not ilceler:
                    continue
                iller = sorted({merkez_to_il(t) for t in ilceler} - {None})
                hadiseler = [HADISE_TR.get(h, h) for h in (weather.get(renk) or [])]
                metin = text.get(renk) if isinstance(text, dict) else str(text)
                kimlik = hashlib.md5(f"{u.get('alarmId', '')}{u.get('begin')}{renk}{iller}".encode()).hexdigest()
                uyarilar.append({"id": "mgm-" + kimlik, "seviye": renk, "iller": iller,
                                 "hadise": hadiseler or ["Olumsuz Hava"],
                                 "metin": html.unescape(re.sub("<[^>]+>", " ", metin or "")).strip(),
                                 "baslangic": u.get("begin"), "bitis": u.get("end"), "gun": gun})
    return uyarilar


def kgm_kapali_yollar():
    try:
        veri = json.loads(http_get(KGM_URL))
    except Exception as e:
        print("KGM alınamadı:", e)
        return []
    yollar = []
    for k in veri.get("data") or []:
        sebep = (k.get("reason") or "").strip()
        if not any(w in sebep.lower() for w in HAVA_KELIME):
            continue  # yapım/bakım kaynaklı kapanmaları atla
        il = ""
        try:  # yol no "53-35" -> ilk kısım il plaka kodu
            p = int(str(k.get("roadNo") or "").split("-")[0])
            il = PLAKA[p] if 0 < p < len(PLAKA) else ""
        except ValueError:
            pass
        ad = re.sub(r"\s+", " ", k.get("shortDescription") or "").strip()
        acik = re.sub(r"\s+", " ", k.get("explanation") or "").strip()
        km = f" ({k['startKm']}-{k['endKm']}. km)" if k.get("endKm") else ""
        metin = f"{ad + ': ' if ad else ''}{acik}{km} – {sebep} nedeniyle kapalı"
        yollar.append({"id": f"kgm-{k.get('id')}-{sebep}", "il": il, "metin": metin[:220], "sebep": sebep})
    return yollar


# ---------------------------------------------------------------- GÖRSEL
def _zemin(ust, alt):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(ust[i] * (1 - k) + alt[i] * k) for i in range(3)))
    return img


def _uyari_ikon(d, x, y, s, renk):
    d.polygon([(x, y - s * .55), (x + s * .62, y + s * .5), (x - s * .62, y + s * .5)], fill=renk)
    d.rounded_rectangle([x - s * .06, y - s * .2, x + s * .06, y + s * .22], radius=s * .05, fill=(25, 20, 20))
    d.ellipse([x - s * .07, y + s * .3, x + s * .07, y + s * .44], fill=(25, 20, 20))


def _sar(d, metin, f, max_w):
    satirlar, s = [], ""
    for k in metin.split():
        if d.textlength((s + " " + k).strip(), font=f) <= max_w:
            s = (s + " " + k).strip()
        else:
            satirlar.append(s); s = k
    if s:
        satirlar.append(s)
    return satirlar


def _saat(iso):
    try:
        t = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        t = t.astimezone(datetime.timezone(datetime.timedelta(hours=3)))
        return t.strftime("%d.%m %H:%M")
    except Exception:
        return ""


def uyari_gorseli(u, yol):
    renk, ad, _ = SEVIYE[u["seviye"]]
    img = _zemin((22, 22, 30), tuple(int(c * .45) for c in renk))
    d = ImageDraw.Draw(img, "RGBA")
    M = 70
    d.rectangle([0, 0, W, 16], fill=renk)
    d.text((M, 90), "METEOROLOJİK UYARI", font=font("Bold", 36), fill=(255, 255, 255, 200))
    _uyari_ikon(d, W / 2, 470, 300, renk)
    rozet = f"{ad} KOD"
    f_r = font("ExtraBold", 64)
    rw = d.textlength(rozet, font=f_r)
    d.rounded_rectangle([W / 2 - rw / 2 - 40, 690, W / 2 + rw / 2 + 40, 790], radius=50, fill=renk)
    d.text((W / 2 - rw / 2, 700), rozet, font=f_r, fill=(20, 15, 15) if u["seviye"] == "yellow" else "white")

    y = 870
    baslik = " · ".join(u["hadise"])
    for s in _sar(d, baslik, font("ExtraBold", 70), W - 2 * M):
        d.text((W / 2 - d.textlength(s, font=font("ExtraBold", 70)) / 2, y), s, font=font("ExtraBold", 70), fill="white")
        y += 84
    zaman = " – ".join(z for z in (_saat(u.get("baslangic")), _saat(u.get("bitis"))) if z)
    if zaman:
        f_z = font("Medium", 38)
        d.text((W / 2 - d.textlength(zaman, font=f_z) / 2, y + 10), zaman, font=f_z, fill=(255, 255, 255, 210))
        y += 70

    y += 40
    iller = ", ".join(u["iller"]) or "-"
    f_il = font("SemiBold", 46 if len(u["iller"]) < 15 else 36)
    il_sat = _sar(d, iller, f_il, W - 2 * M - 80)[:9]
    f_m = font("Regular", 34)
    m_sat = _sar(d, u.get("metin") or "", f_m, W - 2 * M - 80)
    kutu_h = 110 + len(il_sat) * (f_il.size + 14) + (30 + len(m_sat) * 46 if m_sat else 0) + 30
    kutu_h = min(kutu_h, H - 420 - y)
    m_sat = m_sat[: max(0, int((kutu_h - 170 - len(il_sat) * (f_il.size + 14)) / 46))]
    d.rounded_rectangle([M, y, W - M, y + kutu_h], radius=36, fill=(255, 255, 255, 28), outline=(255, 255, 255, 60), width=2)
    d.text((M + 40, y + 34), f"Uyarı verilen iller ({len(u['iller'])})", font=font("Bold", 40), fill=renk)
    yy = y + 110
    for s_ in il_sat:
        d.text((M + 40, yy), s_, font=f_il, fill="white"); yy += f_il.size + 14
    yy += 30
    for s_ in m_sat:
        d.text((M + 40, yy), s_, font=f_m, fill=(255, 255, 255, 205)); yy += 46
    # alt bilgi: güvenlik notu
    not_ = "Tedbirli olun, resmi kurumların açıklamalarını takip edin."
    f_n = font("Medium", 34)
    d.text((W / 2 - d.textlength(not_, font=f_n) / 2, H - 370), not_, font=f_n, fill=(255, 255, 255, 220))
    d.text((M, H - 130), "Kaynak: Meteoroloji Genel Müdürlüğü (MeteoUYARI)", font=font("Regular", 30),
           fill=(255, 255, 255, 170))
    destek_bandi(d, M, H - 300, W - M, H - 170)
    img.save(yol, quality=93)


def yollar_gorseli(yollar, yol):
    img = _zemin((30, 34, 44), (90, 40, 20))
    d = ImageDraw.Draw(img, "RGBA")
    M = 70
    sari = (255, 196, 0)
    for i in range(0, W, 80):  # yol bariyeri şeridi
        d.polygon([(i, 0), (i + 40, 0), (i + 10, 40), (i - 30, 40)], fill=sari)
    d.text((M, 110), "YOL DURUMU", font=font("Bold", 36), fill=(255, 255, 255, 200))
    d.text((M, 160), "Ulaşıma Kapalı Yollar", font=font("ExtraBold", 80), fill="white")
    d.text((M, 265), "Kar, heyelan, sel ve çığ nedeniyle", font=font("Medium", 38), fill=(255, 255, 255, 210))
    y = 360
    for yolb in yollar[:7]:
        f_m = font("Regular", 33)
        sat = _sar(d, yolb["metin"], f_m, W - 2 * M - 70)[:4]
        h = 80 + len(sat) * 44
        if y + h > H - 340:
            break
        d.rounded_rectangle([M, y, W - M, y + h], radius=28, fill=(255, 255, 255, 30), outline=(255, 196, 0, 120), width=2)
        d.text((M + 35, y + 22), yolb["il"].replace("i", "İ").replace("ı", "I").upper() or "—", font=font("Bold", 36), fill=sari)
        yy = y + 72
        for s in sat:
            d.text((M + 35, yy), s, font=f_m, fill="white"); yy += 44
        y += h + 22
    if len(yollar) > 7:
        d.text((M, y), f"+ {len(yollar) - 7} yol daha", font=font("SemiBold", 36), fill=(255, 255, 255, 200))
    d.text((M, H - 130), "Kaynak: Karayolları Genel Müdürlüğü", font=font("Regular", 30), fill=(255, 255, 255, 170))
    destek_bandi(d, M, H - 300, W - M, H - 170)
    img.save(yol, quality=93)


def gonderi_surumu(hikaye_yolu):
    """9:16 hikâye görselinden Instagram gönderisine uygun 4:5 (1080x1350) sürüm üretir."""
    from PIL import ImageFilter, ImageEnhance
    src = Image.open(hikaye_yolu).convert("RGB")
    GW, GH = 1080, 1350
    arka = src.resize((GW, int(GW * src.height / src.width))).crop((0, 0, GW, GH))
    arka = ImageEnhance.Brightness(arka.filter(ImageFilter.GaussianBlur(30))).enhance(0.55)
    on = src.resize((int(GH * src.width / src.height), GH))
    arka.paste(on, ((GW - on.width) // 2, 0))
    yol = hikaye_yolu.replace(".jpg", "_gonderi.jpg")
    arka.save(yol, quality=93)
    return yol


def uyari_caption(u):
    _, ad, _ = SEVIYE[u["seviye"]]
    return (f"⚠️ {ad} KODLU UYARI: {', '.join(u['hadise'])}\n\n"
            f"📍 {', '.join(u['iller'])}\n\n"
            "Lütfen tedbirli olun, resmi kurumların açıklamalarını takip edin.\n"
            "Kaynak: Meteoroloji Genel Müdürlüğü\n\n"
            "📤 Uyarıdan haberi olmayan yakınlarınla paylaş.\n🔔 Sayfamızı takip edip bildirimleri açarak destek olun: @bugun.hava.nasil\n\n#meteorolojikuyarı #havadurumu #"
            + "".join(c for c in ad.lower() if c.isalpha()) + "kod")


# ---------------------------------------------------------------- ANA AKIŞ
def demo_veri():
    u = [{"id": "demo1", "seviye": "orange", "iller": ["Artvin", "Rize", "Trabzon", "Giresun"],
          "hadise": ["Kuvvetli Yağış", "Sel"], "baslangic": "2026-11-10T09:00:00Z", "bitis": "2026-11-11T06:00:00Z",
          "metin": "Doğu Karadeniz'de yer yer çok kuvvetli yağış bekleniyor. Sel, su baskını, heyelan ve yıldırım "
                   "gibi olumsuzluklara karşı dikkatli olunmalıdır."},
         {"id": "demo2", "seviye": "yellow", "iller": ["Erzurum", "Kars", "Ardahan", "Ağrı", "Bitlis", "Muş"],
          "hadise": ["Kar Yağışı", "Buzlanma ve Don"], "baslangic": "2026-11-10T15:00:00Z", "bitis": "",
          "metin": "Yüksek kesimlerde kuvvetli kar yağışı ve tipi beklenmektedir."},
         {"id": "demo3", "seviye": "red", "iller": ["Antalya", "Mersin"], "hadise": ["Gök Gürültülü Sağanak"],
          "baslangic": "", "bitis": "", "metin": ""}]
    y = [{"id": "dy1", "il": "Artvin", "metin": "Artvin-Şavşat yolunun 12-14. km'lerinde heyelan nedeniyle yol her iki yönde ulaşıma kapanmıştır."},
         {"id": "dy2", "il": "Erzurum", "metin": "Erzurum-Tortum yolu Kırık mevkiinde yoğun kar ve tipi nedeniyle tır ve çekici geçişlerine kapatılmıştır."},
         {"id": "dy3", "il": "Rize", "metin": "Rize-İkizdere-İspir yolu Ovit Tüneli girişinde çığ riski nedeniyle kontrollü olarak kapatılmıştır."}]
    return u, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--kesif", action="store_true")
    ap.add_argument("--min-seviye", default="yellow", choices=["yellow", "orange", "red"],
                    help="Bu seviyenin altındaki uyarılar paylaşılmaz")
    ap.add_argument("--cikti", default="cikti_uyari")
    a = ap.parse_args()

    if a.kesif:
        os.makedirs("kesif", exist_ok=True)
        for ad, url, h in (("mgm_today.json", f"{MGM}/meteoalarm/today", HEADERS),
                           ("mgm_tomorrow.json", f"{MGM}/meteoalarm/tomorrow", HEADERS),
                           ("kgm.html", KGM_URL, None)):
            try:
                open(os.path.join("kesif", ad), "w", encoding="utf-8").write(http_get(url, h))
                print("kaydedildi:", ad)
            except Exception as e:
                print("HATA", ad, e)
        return

    durum = {"gorulen": []}
    if os.path.exists(DURUM_DOSYA) and not a.demo:
        durum = json.load(open(DURUM_DOSYA, encoding="utf-8"))
    gorulen = set(durum["gorulen"])

    uyarilar, yollar = demo_veri() if a.demo else (mgm_uyarilar(), kgm_kapali_yollar())
    esik = SEVIYE[a.min_seviye][2]
    yeni_u = [u for u in uyarilar if u["id"] not in gorulen and SEVIYE[u["seviye"]][2] >= esik]
    yeni_u.sort(key=lambda u: -SEVIYE[u["seviye"]][2])
    yeni_y = [y for y in yollar if y["id"] not in gorulen]

    os.makedirs(a.cikti, exist_ok=True)
    zaman = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime("%Y%m%d_%H%M")
    paylasim = []
    for i, u in enumerate(yeni_u):
        p = os.path.join(a.cikti, f"{zaman}_uyari_{i + 1}_{u['seviye']}.jpg")
        uyari_gorseli(u, p)
        kayit = {"gorsel": p, "tur": "hikaye" if u["seviye"] == "yellow" else "hikaye+gonderi",
                 "caption": uyari_caption(u)}
        if "gonderi" in kayit["tur"]:
            kayit["gonderi_gorsel"] = gonderi_surumu(p)
        paylasim.append(kayit)
    if yeni_y:
        p = os.path.join(a.cikti, f"{zaman}_kapali_yollar.jpg")
        yollar_gorseli(yollar, p)  # yeni kapanma varsa güncel tam listeyi paylaş
        paylasim.append({"gorsel": p, "tur": "hikaye",
                         "caption": "🚧 Hava koşulları nedeniyle ulaşıma kapalı yollar\nKaynak: Karayolları Genel Müdürlüğü"})

    json.dump(paylasim, open(os.path.join(a.cikti, "paylasim.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(yeni_u)} yeni uyarı, {len(yeni_y)} yeni kapalı yol -> {len(paylasim)} görsel")
    if not a.demo:
        durum["gorulen"] = (list(gorulen) + [x["id"] for x in yeni_u + yeni_y])[-2000:]
        json.dump(durum, open(DURUM_DOSYA, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
