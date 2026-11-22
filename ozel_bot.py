#!/usr/bin/env python3
"""
Özel kartlar (yurt geneli kart formatında: fotoğraf zemin, il çipleri, hareketli Reels + hikâye):

  olcum     Kış (Kasım–Mart) sabahları: MGM'nin ölçtüğü en düşük sıcaklıklar ("Bu sabah en soğuk yer ...")
  haftalik  Pazartesi sabahı: "Bu hafta hava nasıl?" (Pzt–Cuma gidişatı)
  tatil     Bayram / uzun tatil başlamadan 2 gün önce: yolculuk öncesi hava ve kapalı yollar

`zamanlayici` uyarı kontrolünde (30 dk'da bir) çağrılır; zamanı gelen kartı üretir, her biri günde/haftada bir.
Çıktı: yayin/ozel/paylasim.json (instagram_paylas.py uyari ile paylaşılır)
"""
import argparse, datetime, json, os, sys
from collections import Counter

from hava_bot import mgm_get, HADISE
import ulke_bot as ub

TR = datetime.timezone(datetime.timedelta(hours=3))
DURUM = "ozel_durum.json"
AYLAR = ub.AYLAR
GUNLER = ub.GUNLER
HARIC = ("KAYAK", "ZİRVE", "ZIRVE", "GEÇİDİ", "GECIDI", "DAĞI", "DAGI", "TEPE", "MERKEZİ", "RADAR", "BARAJ")

# Diyanet takvimine göre bayramlar ve uzun tatiller: (ad, ilk tatil günü, son gün)
TATILLER = [
    ("Yılbaşı", "2027-01-01", "2027-01-03"),
    ("Ramazan Bayramı", "2027-03-08", "2027-03-11"),
    ("23 Nisan", "2027-04-23", "2027-04-25"),
    ("Kurban Bayramı", "2027-05-15", "2027-05-19"),
    ("30 Ağustos", "2027-08-28", "2027-08-30"),
    ("Cumhuriyet Bayramı", "2027-10-29", "2027-10-31"),
    ("Yılbaşı", "2028-01-01", "2028-01-02"),
]

RISK = {  # tatil yolculuğu için riskli hadiseler
    "KAR": ub.KAR, "YAGIS": ub.KUVVETLI_YAGIS, "SIS": {"SIS", "PUS"}, "RUZGAR": ub.RUZGAR, "FIRTINA": {"GSY", "GKR", "KGY"},
}


def fmt(x):
    return f"{x:.1f}".replace(".", ",").replace("-", "−")


def kayit(o, klasor, ad):
    os.makedirs(klasor, exist_ok=True)
    g = os.path.join(klasor, f"{ad}.jpg")
    ub.kart(o, g)
    h = g.replace(".jpg", "_hikaye.jpg")
    ub.dikey(g, h)
    return {"gorsel": h, "gonderi_gorsel": g, "tur": "hikaye+gonderi", "caption": o["caption"],
            "hareket": {"karli": "kar", "yagmurlu": "yagmur", "firtinali": "firtina", "ruzgarli": "ruzgar", "sisli": "sis"}.get(o["sahne"])}


# ---------------- 1) Ölçülen en düşük sıcaklıklar (kış sabahları) ----------------
def olcum(demo=False):
    bugun = datetime.datetime.now(TR).date()
    if demo:
        veri = [{"il": il, "ilce": il, "istAd": il.upper(), "deger": d} for il, d in
                [("Ardahan", -18.4), ("Kars", -15.2), ("Erzurum", -14.8), ("Ağrı", -12.1), ("Sivas", -9.6), ("Van", -8.3),
                 ("Muş", -7.9), ("Bayburt", -7.4), ("Erzincan", -6.2), ("Kayseri", -5.5), ("Yozgat", -4.1), ("Ankara", -2.3)]]
    else:
        veri = mgm_get(f"/sondurumlar/enDusuk?tarih={bugun.isoformat()}") or []
    en = {}
    for x in veri:
        d, il = x.get("deger"), x.get("il")
        if d is None or il not in ub.IL_BOLGE or d < -50 or d > 50:
            continue
        if any(h in str(x.get("istAd", "")).upper() for h in HARIC):  # dağ/kayak istasyonları il genelini yansıtmaz
            continue
        if il not in en or d < en[il]["deger"]:
            en[il] = x
    sirali = sorted(en.values(), key=lambda x: x["deger"])
    if not sirali or sirali[0]["deger"] > -3:
        print("Ölçüm: belirgin soğuk yok", sirali[:1])
        return None
    eksi = [x for x in sirali if x["deger"] < 0]
    ilk = sirali[0]
    yer = lambda x: f"{x['ilce']} ({x['il']})" if x.get("ilce") and x["ilce"] != x["il"] else x["il"]
    ilk5 = ", ".join(f"{yer(x)} {fmt(x['deger'])}°C" for x in sirali[:5])
    cip = [f"{x['il']} {round(x['deger'])}°" for x in sirali[:16]]
    o = {"tur": "AYAZ", "baslik": f"{fmt(ilk['deger'])}°C ÖLÇÜLDÜ!", "sahne": "bulutlu", "foto": "soguk", "iller": cip,
         "tarih": bugun, "alt_baslik": f"Bu sabah en soğuk yer: {yer(ilk)}",
         "kaynak": "Kaynak: MGM istasyon ölçümleri",
         "paragraf": (f"MGM ölçümlerine göre bu sabah Türkiye'nin en soğuk yeri {fmt(ilk['deger'])}°C ile {yer(ilk)} oldu. "
                      f"En soğuk 5 yer: {ilk5}. {len(eksi)} ilde sıcaklık sıfırın altına düştü; buzlanma ve don olaylarına dikkat.")}
    o["caption"] = (f"🥶 Bu sabah {yer(ilk)} {fmt(ilk['deger'])}°C'yi gördü!\n\n{o['paragraf']}\n\n"
                    f"📍 En soğuk iller: {', '.join(c for c in cip)}\n\n"
                    "💬 Senin ilinde bu sabah kaç derece? Yorumlara yaz!\n"
                    "🔔 Takip edip bildirimleri açarak destek olun · 📤 Sevdiklerinle paylaş\n"
                    "👉 @bugun.hava.nasil\n\nKaynak: Meteoroloji Genel Müdürlüğü (MGM) ölçümleri\n\n"
                    "#havadurumu #soğukhava #ayaz #don #enSoğuk #mgm")
    return o


# ---------------- 2) Bu hafta hava nasıl? (Pazartesi) ----------------
def gun_ozeti(g):
    """Bir günün tüm illerdeki tahmininden kısa özet."""
    tip = Counter(HADISE.get(x.get("hadise"), ("", ""))[1] for x in g)
    kar = tip["kar"] + tip["karla_yagmur"]
    yag = tip["yagmur"] + tip["firtina"]
    acik = tip["gunes"] + tip["az_bulut"]
    maks = [x["max"] for x in g if x.get("max") is not None]
    ort = round(sum(maks) / len(maks)) if maks else None
    if kar >= 5:
        etiket, metin = "Karlı", f"{kar} ilde kar" + (f", {yag} ilde yağmur" if yag >= 5 else "")
    elif yag >= 25:
        etiket, metin = "Yağmurlu", f"{yag} ilde yağmur"
    elif yag >= 8:
        etiket, metin = "Yer yer yağışlı", f"{yag} ilde yağış"
    elif acik >= 45:
        etiket, metin = "Güneşli", f"{acik} ilde açık hava"
    else:
        etiket, metin = "Parçalı bulutlu", "genelde parçalı bulutlu"
    return etiket, metin, ort, kar, yag


def haftalik(veri):
    bugun = datetime.datetime.now(TR).date()
    pzt = bugun - datetime.timedelta(days=bugun.weekday())
    gunler = []
    for k in range(5):
        t = pzt + datetime.timedelta(days=k)
        g = [v[t.isoformat()] for v in veri.values() if t.isoformat() in v]
        if len(g) >= 60:
            gunler.append((t, *gun_ozeti(g)))
    if len(gunler) < 3:
        return None
    parca = [f"{GUNLER[t.weekday()]} {metin}" + (f" (ort. {ort}°C)" if ort is not None else "") for t, et, metin, ort, k, y in gunler]
    sicak = max(gunler, key=lambda x: x[3] if x[3] is not None else -99)
    soguk = min(gunler, key=lambda x: x[3] if x[3] is not None else 99)
    en_kar = max(gunler, key=lambda x: x[4])
    en_yag = max(gunler, key=lambda x: x[5])
    if en_kar[4] >= 5:
        baslik, foto, sahne = "BU HAFTA KAR VAR!", "karli", "karli"
    elif en_yag[5] >= 25:
        baslik, foto, sahne = "BU HAFTA YAĞMURLU!", "yagmurlu", "yagmurlu"
    else:
        baslik, foto, sahne = "BU HAFTA HAVA NASIL?", "gunesli", "gunesli"
    ozet = f"Haftanın en sıcak günü {GUNLER[sicak[0].weekday()]}, en serin günü {GUNLER[soguk[0].weekday()]}."
    o = {"tur": "HAFTA", "baslik": baslik, "sahne": sahne, "foto": foto, "tarih": pzt,
         "alt_baslik": f"{pzt.day}-{(pzt + datetime.timedelta(days=4)).day} {AYLAR[pzt.month]} haftası",
         "iller": [f"{GUNLER[t.weekday()][:3]}: {et}" for t, et, *_ in gunler],
         "paragraf": "MGM tahminlerine göre bu hafta: " + "; ".join(parca) + ". " + ozet}
    o["caption"] = (f"📅 {baslik} {o['alt_baslik']}\n\n{o['paragraf']}\n\n"
                    "📌 Kaydet, haftanı buna göre planla!\n"
                    "💬 Kendi ilinin 5 günlük tahmini için yorumlara il ya da ilçe yaz, hemen cevaplayalım.\n"
                    "🔔 Takip edip bildirimleri açarak destek olun 👉 @bugun.hava.nasil\n\n"
                    "Kaynak: Meteoroloji Genel Müdürlüğü (MGM)\n\n#havadurumu #buhafta #haftalıkhava #mgm")
    return o


# ---------------- 3) Bayram / tatil yolculuğu ----------------
def tatil(veri, ad, bas, son):
    gunler = [bas + datetime.timedelta(days=k) for k in range((son - bas).days + 1)]
    gunler = [t for t in gunler if any(t.isoformat() in v for v in veri.values())]
    if not gunler:
        return None
    riskli = {}
    for il, v in veri.items():
        for t in gunler:
            h = v.get(t.isoformat(), {}).get("hadise")
            for tur, kodlar in RISK.items():
                if h in kodlar:
                    riskli.setdefault(il, set()).add(tur)
    adlar = {"KAR": "kar", "YAGIS": "kuvvetli yağış", "SIS": "sis", "RUZGAR": "kuvvetli rüzgar", "FIRTINA": "gök gürültülü sağanak"}
    say = Counter(t for s in riskli.values() for t in s)
    try:
        from uyari_bot import kgm_kapali_yollar
        yollar = kgm_kapali_yollar()
    except Exception:
        yollar = []
    aralik = f"{bas.day}-{son.day} {AYLAR[son.month]}" if bas.month == son.month else f"{bas.day} {AYLAR[bas.month]} - {son.day} {AYLAR[son.month]}"
    if riskli:
        risk_metin = ", ".join(f"{n} ilde {adlar[t]}" for t, n in say.most_common())
        baslik, foto, sahne = "YOLA ÇIKMADAN ÖNCE OKU!", ("karli" if say["KAR"] else "yagmurlu"), ("karli" if say["KAR"] else "yagmurlu")
        metin = (f"MGM tahminlerine göre {ad} tatilinde ({aralik}) {risk_metin} bekleniyor. "
                 + (f"Şu an {len(yollar)} yol hava koşulları nedeniyle ulaşıma kapalı. " if yollar else "")
                 + "Yola çıkmadan önce güzergâhınızdaki hava ve yol durumunu kontrol edin; kış lastiği, zincir ve battaniyenizi unutmayın.")
        cip = sorted(riskli, key=lambda il: -len(riskli[il]))
    else:
        baslik, foto, sahne = "YOLCULUĞA UYGUN HAVA!", "gunesli", "gunesli"
        metin = (f"MGM tahminlerine göre {ad} tatilinde ({aralik}) yurt genelinde yolculuğu zorlaştıracak bir hava olayı beklenmiyor. "
                 "Yine de dinlenerek, emniyet kemerinizi takarak yolculuk yapın. İyi bayramlar!")
        cip = []
    o = {"tur": "TATIL", "baslik": baslik, "sahne": sahne, "foto": foto, "tarih": bas, "iller": cip,
         "alt_baslik": f"{ad} yolculuğu", "paragraf": metin}
    o["caption"] = (f"🚗 {ad} yolculuğu öncesi hava durumu ({aralik})\n\n{metin}\n\n"
                    + (f"📍 Dikkat edilmesi gereken iller: {', '.join(cip)}\n\n" if cip else "")
                    + "📌 Kaydet, yola çıkacak sevdiklerine gönder!\n"
                    "💬 Gideceğin il ya da ilçeyi yorumlara yaz, tahminini hemen gönderelim.\n"
                    "🔔 Takip edip bildirimleri açarak destek olun 👉 @bugun.hava.nasil\n\n"
                    "Kaynak: Meteoroloji Genel Müdürlüğü (MGM) · Karayolları Genel Müdürlüğü\n\n"
                    "#havadurumu #bayram #yolculuk #trafik #kapalıyollar #mgm")
    return o


def zamanlayici(demo=False, zorla=None, klasor="yayin/ozel"):
    simdi = datetime.datetime.now(TR)
    bugun = simdi.date()
    durum = json.load(open(DURUM)) if os.path.exists(DURUM) and not demo else {}
    paylasim, veri = [], None

    def tahmin():
        nonlocal veri
        if veri is None:
            veri = ub.demo_tahminler() if demo else ub.tum_tahminler()
        return veri

    # 1) Kış sabahı ölçüm: Kasım–Mart, 08:00-11:59, günde bir
    if zorla == "olcum" or (bugun.month in (11, 12, 1, 2, 3) and 8 <= simdi.hour < 12 and durum.get("olcum") != bugun.isoformat()):
        o = olcum(demo)
        durum["olcum"] = bugun.isoformat()
        if o:
            paylasim.append(kayit(o, klasor, f"olcum_{bugun:%Y%m%d}"))
    # 2) Pazartesi 08:30-11:59 haftalık
    if zorla == "haftalik" or (bugun.weekday() == 0 and (simdi.hour, simdi.minute) >= (8, 30) and simdi.hour < 12
                               and durum.get("haftalik") != bugun.isoformat()):
        o = haftalik(tahmin())
        durum["haftalik"] = bugun.isoformat()
        if o:
            paylasim.append(kayit(o, klasor, f"hafta_{bugun:%Y%m%d}"))
    # 3) Tatil: ilk tatil gününden 2 gün önce, 12:00-17:59
    for ad, b, s in TATILLER:
        bas, son = datetime.date.fromisoformat(b), datetime.date.fromisoformat(s)
        anahtar = f"tatil|{b}"
        if zorla == "tatil" or ((bas - bugun).days == 2 and 12 <= simdi.hour < 18 and anahtar not in durum.get("tatil", [])):
            if zorla == "tatil" and (bas - bugun).days not in (0, 1, 2, 3, 4):
                bas = bugun + datetime.timedelta(days=2)
                son = bas + datetime.timedelta(days=2)
            o = tatil(tahmin(), ad, bas, son)
            durum.setdefault("tatil", []).append(anahtar)
            if o:
                paylasim.append(kayit(o, klasor, f"tatil_{b.replace('-', '')}"))
            break
    os.makedirs(klasor, exist_ok=True)
    json.dump(paylasim, open(os.path.join(klasor, "paylasim.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not demo:
        json.dump(durum, open(DURUM, "w"), ensure_ascii=False)
    print(len(paylasim), "özel kart hazır")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("komut", nargs="?", default="zamanlayici")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--cikti", default="yayin/ozel")
    a = ap.parse_args()
    zamanlayici(a.demo, None if a.komut == "zamanlayici" else a.komut, a.cikti)
