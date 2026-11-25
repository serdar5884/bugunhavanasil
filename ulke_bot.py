#!/usr/bin/env python3
"""
Yurt geneli önemli hava gelişmeleri – MGM'nin 81 il tahmininden otomatik tespit:
  KAR GELİYOR!            yarın/öbür gün en az 8 ilde kar
  KUVVETLİ YAĞIŞ GELİYOR! en az 8 ilde MGM "kuvvetli" yağış kodu
  YAĞMURLU HAVA GELİYOR!  bir önceki gün ≤20 ilde yağış varken en az 40 ilde yağış
  SOĞUK HAVA DALGASI!     en az 30 ilde en yüksek sıcaklık bir önceki güne göre 6°C+ düşüyor
  SICAKLIKLAR X DERECE YÜKSELİYOR/DÜŞÜYOR!  20+ ilde 5°C ya da 8+ ilde 8°C değişim (bir önceki güne göre)
  KUVVETLİ RÜZGAR!        en az 8 ilde kuvvetli rüzgar
Her gelişme (tür + tarih) bir kez paylaşılır: 4:5 gönderi + hikâye.

Kullanım: python ulke_bot.py --cikti yayin/ulke      (--demo: örnek veri)
"""
import argparse, datetime, json, os, random
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageEnhance
from hava_bot import (BOLGELER, HADISE, mgm_get, merkezleri_yukle, sahne_ciz, font, destek_bandi, yorum_cagrisi,
                      metni_sigdir, W, H, HESAP)
from haber_bot import bulunma
from reels_bot import dikey

TR = datetime.timezone(datetime.timedelta(hours=3))
DURUM = "ulke_durum.json"
SARI = (255, 205, 0)
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
AYLAR = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
IL_BOLGE = {il: b for b, iller in BOLGELER.items() for il in iller}
KAR = {"K", "HKY", "YKY", "KKY"}
KUVVETLI_YAGIS = {"KY", "KSY", "KGY"}  # sadece MGM'nin "kuvvetli" kodları
YAGISLI = {"HY", "Y", "KY", "HSY", "SY", "KSY", "MSY", "GSY", "KGY", "KKY", "HHY"}
RUZGAR = {"GKR", "KKR", "R"}


def tum_tahminler():
    merkez = merkezleri_yukle()

    def al(il):
        t = mgm_get(f"/tahminler/gunluk?istno={merkez[il]}")
        t = t[0] if isinstance(t, list) else t
        g = {}
        for i in range(1, 6):
            tarih = str(t.get(f"tarihGun{i}", ""))[:10]
            if tarih:
                g[tarih] = {"hadise": t.get(f"hadiseGun{i}"), "max": t.get(f"enYuksekGun{i}"), "min": t.get(f"enDusukGun{i}")}
        return il, g

    with ThreadPoolExecutor(max_workers=6) as ex:
        return dict(ex.map(al, IL_BOLGE))


def demo_tahminler():
    rnd = random.Random(3)
    bugun = datetime.datetime.now(TR).date()
    v = {}
    for il, b in IL_BOLGE.items():
        g = {}
        for k in range(4):
            tr = (bugun + datetime.timedelta(days=k)).isoformat()
            soguk = b in ("Doğu Anadolu", "Karadeniz", "İç Anadolu") and k >= 1
            h = rnd.choice(["K", "HKY", "YKY"]) if soguk and rnd.random() < .6 else rnd.choice(["PB", "CB", "Y", "A"])
            mx = rnd.randint(14, 20) - (9 if k >= 1 else 0)
            g[tr] = {"hadise": h, "max": mx, "min": mx - rnd.randint(5, 9)}
        v[il] = g
    return v


def gun_adi(tarih):
    bugun = datetime.datetime.now(TR).date()
    return "Yarın" if tarih == bugun + datetime.timedelta(days=1) else GUNLER[tarih.weekday()]


def tespit(veri):
    bugun = datetime.datetime.now(TR).date()
    olaylar = []
    for k in (1, 2):  # yarın ve öbür gün
        tarih = bugun + datetime.timedelta(days=k)
        t, onceki = tarih.isoformat(), (tarih - datetime.timedelta(days=1)).isoformat()
        g = {il: d[t] for il, d in veri.items() if t in d}
        if len(g) < 60:
            continue

        def say(kodlar):
            return sorted([il for il, x in g.items() if x["hadise"] in kodlar], key=lambda il: list(IL_BOLGE).index(il))

        kar = say(KAR)
        if len(kar) >= 5:
            en_soguk = min(kar, key=lambda il: g[il]["min"] if g[il]["min"] is not None else 99)
            olaylar.append({"tur": "KAR", "baslik": "KAR GELİYOR!", "sahne": "karli", "iller": kar, "tarih": tarih,
                            "ek": f"En düşük sıcaklık {bulunma(en_soguk)} {g[en_soguk]['min']}°C olacak."})
        yagis = say(KUVVETLI_YAGIS)
        if len(yagis) >= 8:
            olaylar.append({"tur": "YAGIS", "baslik": "KUVVETLİ YAĞIŞ GELİYOR!", "sahne": "firtinali", "iller": yagis, "tarih": tarih,
                            "ek": "Sel ve su baskınlarına karşı dikkatli olun."})
        # Yağışlı havaya geçiş: bir önceki gün az ilde yağış varken bu gün çok ilde
        yagisli, onceki_yagisli = say(YAGISLI), [il for il, d in veri.items() if onceki in d and d[onceki]["hadise"] in YAGISLI]
        if len(yagisli) >= 40 and len(onceki_yagisli) <= 20:
            olaylar.append({"tur": "YAGMUR", "baslik": "YAĞMURLU HAVA GELİYOR!", "sahne": "yagmurlu", "iller": yagisli, "tarih": tarih,
                            "ek": "Şemsiyenizi yanınıza almayı unutmayın."})
        elif len(yagisli) >= 25:  # yağışlı hava sürüyor: yine de çok ili ilgilendiren gün
            olaylar.append({"tur": "YAGMUR", "baslik": "YAĞMUR DEVAM EDİYOR!", "sahne": "yagmurlu", "iller": yagisli, "tarih": tarih,
                            "ek": "Şemsiyenizi yanınıza almayı unutmayın."})
        # Güneşli havaya dönüş: önceki gün çok ilde yağış, bu gün çok ilde açık/az bulutlu
        acik = say({"A", "AB"})
        if len(acik) >= 40 and len(onceki_yagisli) >= 20:
            olaylar.append({"tur": "GUNES", "baslik": "GÜNEŞ GERİ DÖNÜYOR!", "sahne": "gunesli", "iller": acik, "tarih": tarih,
                            "fiil": "yağışlı havanın ardından açık ve az bulutlu hava bekleniyor",
                            "ek": "Çamaşır ve dışarıdaki işler için güzel bir gün."})
        # Ayaz / don: gece sıcaklığı -3°C ve altına inen il sayısı
        ayaz = sorted([il for il, x in g.items() if x["min"] is not None and x["min"] <= -3], key=lambda il: g[il]["min"])
        if len(ayaz) >= 12:
            e = ayaz[0]
            olaylar.append({"tur": "AYAZ", "baslik": "AYAZ VE DON GELİYOR!", "sahne": "bulutlu", "foto": "soguk", "iller": ayaz,
                            "tarih": tarih, "fiil": "gece sıcaklıkların sıfırın altına düşmesi bekleniyor",
                            "ek": f"En soğuk il {e}: {g[e]['min']}°C. Buzlanma ve don olaylarına karşı dikkatli olun."})
        sis = say({"SIS", "PUS"})
        if len(sis) >= 8:
            olaylar.append({"tur": "SIS", "baslik": "SİS UYARISI!", "sahne": "sisli", "iller": sis, "tarih": tarih,
                            "fiil": "sis ve pus bekleniyor",
                            "ek": "Sürücüler görüş mesafesine karşı dikkatli olmalı, takip mesafesini artırın."})
        ruzgar = say(RUZGAR)
        if len(ruzgar) >= 8:
            olaylar.append({"tur": "RUZGAR", "baslik": "KUVVETLİ RÜZGAR!", "sahne": "bulutlu", "foto": "ruzgarli", "iller": ruzgar, "tarih": tarih,
                            "ek": "Çatı uçması ve devrilmelere karşı tedbirli olun."})
        farklar = {il: g[il]["max"] - veri[il][onceki]["max"] for il in g
                   if onceki in veri[il] and g[il]["max"] is not None and veri[il][onceki]["max"] is not None}
        def ilk3(iller, isaret):
            sec = sorted(iller, key=lambda il: farklar[il] * isaret, reverse=True)[:3]
            return ", ".join(f"{il} {abs(farklar[il])} derece ({veri[il][onceki]['max']}°C'den {g[il]['max']}°C'ye)" for il in sec[:2]) + \
                (f", {sec[2]} {abs(farklar[sec[2]])} derece" if len(sec) > 2 else "")
        # Ani sıcaklık değişimi: geniş alanda (20+ il 5°C) ya da sert (8+ il 8°C) düşüş/artış
        dusen = sorted([il for il, f in farklar.items() if f <= -5], key=lambda il: farklar[il])
        sert_d = [il for il in dusen if farklar[il] <= -8]
        if len(dusen) >= 20 or len(sert_d) >= 8:
            en = -farklar[dusen[0]]
            soguk_dalga = len(dusen) >= 30
            olaylar.append({"tur": "SOGUK", "baslik": f"SICAKLIKLAR {en} DERECE DÜŞÜYOR!",
                            "sahne": "bulutlu", "foto": "soguk", "iller": dusen, "tarih": tarih,
                            "fiil": f"sıcaklıkların {en} dereceye kadar düşmesi bekleniyor" + (", soğuk hava dalgası geliyor" if soguk_dalga else ""),
                            "ek": f"En büyük düşüşler: {ilk3(dusen, -1)}. Kalın giyinmeyi unutmayın."})
        artan = sorted([il for il, f in farklar.items() if f >= 5], key=lambda il: -farklar[il])
        sert_a = [il for il in artan if farklar[il] >= 8]
        if len(artan) >= 20 or len(sert_a) >= 8:
            en = farklar[artan[0]]
            olaylar.append({"tur": "SICAK", "baslik": f"SICAKLIKLAR {en} DERECE YÜKSELİYOR!", "sahne": "gunesli",
                            "iller": artan, "tarih": tarih,
                            "fiil": f"sıcaklıkların {en} dereceye kadar yükselmesi bekleniyor",
                            "ek": f"En büyük artışlar: {ilk3(artan, 1)}."})
    # Aynı gün hem "yağmurlu hava" hem "kuvvetli yağış" varsa tek gönderide birleştir
    birlesik = []
    for o in olaylar:
        if o["tur"] == "YAGIS":
            ym = next((x for x in olaylar if x["tur"] == "YAGMUR" and x["tarih"] == o["tarih"]), None)
            if ym:
                bolge = {}
                for il in o["iller"]:
                    bolge[IL_BOLGE[il]] = bolge.get(IL_BOLGE[il], 0) + 1
                b = max(bolge, key=bolge.get)
                ym["ek"] = (f"{len(o['iller'])} ilde kuvvetli yağış bekleniyor ({', '.join(o['iller'][:6])}"
                            f"{'...' if len(o['iller']) > 6 else ''}); sel ve su baskınlarına dikkat.")
                continue
        birlesik.append(o)
    return birlesik


FIIL = {"KAR": "kar yağışı bekleniyor", "YAGIS": "kuvvetli yağış bekleniyor", "YAGMUR": "yağmur ve sağanak bekleniyor", "RUZGAR": "kuvvetli rüzgar bekleniyor"}


def paragraf(o):
    if o.get("paragraf"):  # özel kartlar (ölçüm, haftalık, tatil) kendi metnini getirir
        return o["paragraf"]
    t = o["tarih"]
    bolge = {}
    for il in o["iller"]:
        bolge[IL_BOLGE[il]] = bolge.get(IL_BOLGE[il], 0) + 1
    ilk = sorted(bolge.items(), key=lambda x: -x[1])[:2]
    bolge_metin = " ve ".join(f"{b} ({n} il)" for b, n in ilk)
    fiil = o.get("fiil") or FIIL[o["tur"]]
    return (f"MGM tahminlerine göre {gun_adi(t).lower() if gun_adi(t) == 'Yarın' else gun_adi(t)} ({t.day} {AYLAR[t.month]}) "
            f"{len(o['iller'])} il merkezinde {fiil}. En çok etkilenecek bölgeler: {bolge_metin}. {o['ek']}").strip()


def fotograf(sahne, tarih):
    """arka_plan/<sahne>/ klasöründe fotoğraf varsa sıradakini 1080x1350 kırparak döndürür."""
    import glob
    klasor = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arka_plan", sahne)
    fotolar = sorted(glob.glob(os.path.join(klasor, "*.jpg")) + glob.glob(os.path.join(klasor, "*.jpeg")) +
                     glob.glob(os.path.join(klasor, "*.png")) + glob.glob(os.path.join(klasor, "*.webp")))
    if not fotolar:
        return None
    src = Image.open(fotolar[tarih.toordinal() % len(fotolar)]).convert("RGB")
    oran = max(W / src.width, H / src.height)
    src = src.resize((int(src.width * oran + 1), int(src.height * oran + 1)))
    x, y = (src.width - W) // 2, (src.height - H) // 2
    return src.crop((x, y, x + W, y + H))


def kart(o, yol):
    img = fotograf(o.get("foto", o["sahne"]), o["tarih"]) or sahne_ciz(o["sahne"], o["tur"]).convert("RGB")
    img = ImageEnhance.Brightness(img).enhance(0.8)  # RGB kalmalı: RGBA çizim üstüne karışsın
    d = ImageDraw.Draw(img, "RGBA")
    # alttan koyulaşan perde (yazı okunsun)
    for y in range(H // 3, H):
        a = int(235 * ((y - H / 3) / (H * 2 / 3)) ** 0.6)
        d.line([(0, y), (W, y)], fill=(8, 14, 28, a))
    M = 64
    f1, f2 = font("ExtraBold", 40), font("Bold", 26)
    d.text((M, 46), "BUGÜN", font=f1, fill=SARI)
    d.text((M + d.textlength("BUGÜN", font=f1) + 10, 58), "HAVA NASIL?", font=f2, fill="white")
    rozet = "YURT GENELİ"
    fr = font("ExtraBold", 28)
    rw = d.textlength(rozet, font=fr)
    d.rounded_rectangle([W - M - rw - 36, 46, W - M, 96], radius=25, fill=(215, 30, 40))
    d.text((W - M - rw - 18, 55), rozet, font=fr, fill="white")

    # iller (alt kısım, çipler) – önce yerleşimi hesapla
    f_c = font("SemiBold", 26)
    satirlar, x, sat = [], 0, []
    for il in o["iller"]:
        w = d.textlength(il, font=f_c) + 28
        if x + w > W - 2 * M - 30:
            satirlar.append(sat); sat, x = [], 0
        sat.append((il, w)); x += w + 10
    if sat:
        satirlar.append(sat)
    fazla = 0
    if len(satirlar) > 4:
        fazla = sum(len(s) for s in satirlar[4:])
        satirlar = satirlar[:4]
    cip_h = len(satirlar) * 50
    alt = H - 245
    cip_y = alt - cip_h
    # paragraf
    f_p = font("SemiBold", 33)
    metin = paragraf(o)
    sat_p, s = [], ""
    for k in metin.split():
        if d.textlength((s + " " + k).strip(), font=f_p) <= W - 2 * M - 40:
            s = (s + " " + k).strip()
        else:
            sat_p.append(s); s = k
    sat_p.append(s)
    p_h = len(sat_p) * 46
    f_b = metni_sigdir(d, o["baslik"], "ExtraBold", 108, W - 2 * M - 40)
    alt_baslik = o.get("alt_baslik") or f"{gun_adi(o['tarih'])} {len(o['iller'])} ilde"
    f_ab = font("ExtraBold", 46)
    y0 = cip_y - 40 - p_h - 30 - f_b.size - 20 - f_ab.size - 10
    d.rectangle([M, y0 + 8, M + 10, cip_y - 40], fill=SARI)
    tx = M + 34
    d.text((tx, y0), alt_baslik, font=f_ab, fill=SARI)
    y = y0 + f_ab.size + 18
    d.text((tx + 4, y + 4), o["baslik"], font=f_b, fill=(0, 0, 0, 140))
    d.text((tx, y), o["baslik"], font=f_b, fill="white")
    y += f_b.size + 30
    for s in sat_p:
        d.text((tx, y), s, font=f_p, fill=(255, 255, 255, 235)); y += 46
    y = cip_y
    for sat in satirlar:
        x = M
        for il, w in sat:
            d.rounded_rectangle([x, y, x + w, y + 40], radius=20, fill=(255, 255, 255, 40), outline=(255, 255, 255, 90))
            d.text((x + 14, y + 6), il, font=f_c, fill="white")
            x += w + 10
        y += 50
    if fazla:
        d.text((M, y - 4), f"+ {fazla} il daha (tamamı açıklamada)", font=font("Medium", 26), fill=(255, 255, 255, 210))
    yorum_cagrisi(d, M + 40, H - 212, W - M - 40, H - 160)
    destek_bandi(d, M, H - 150, W - M, H - 55)
    d.text((M, H - 44), o.get("kaynak", "Kaynak: MGM il merkezi tahminleri"), font=font("Regular", 22), fill=(255, 255, 255, 170))
    img.convert("RGB").save(yol, quality=93)


def caption(o):
    if o.get("caption"):
        return o["caption"]
    t = o["tarih"]
    et = {"KAR": "#kar #karyağışı #kargeliyor", "YAGIS": "#sağanak #yağmur #kuvvetliyağış", "YAGMUR": "#yağmur #sağanak", "RUZGAR": "#fırtına #rüzgar",
          "SOGUK": "#soğukhava #soğukhavadalgası", "SICAK": "#sıcakhava #havaısınıyor",
          "GUNES": "#güneşlihava #havaaçıyor", "AYAZ": "#ayaz #don #buzlanma", "SIS": "#sis #trafik"}[o["tur"]]
    return (f"⚠️ {o['baslik']}\n\n{paragraf(o)}\n\n"
            f"📍 {len(o['iller'])} il: {', '.join(o['iller'])}\n\n"
            "💬 Kendi ilinin tahmini için yorumlara ilini yaz, hemen cevaplayalım!\n"
            "🔔 Takip edip bildirimleri açarak destek olun · 📤 Sevdiklerinle paylaş\n"
            f"👉 {HESAP}\n\nKaynak: Meteoroloji Genel Müdürlüğü (MGM)\n\n#havadurumu #meteoroloji #mgm {et}")


def sezon(t):
    return f"{t.year}-{t.year + 1}" if t.month >= 7 else f"{t.year - 1}-{t.year}"


def ilk_kar(veri, durum):
    """Bu kış ilk kez kar yağışı tahmin edilen iller (yarın/öbür gün). Kar görmüş iller durum["kar_gordu"][sezon]."""
    bugun = datetime.datetime.now(TR).date()
    sz = sezon(bugun)
    kg = durum.setdefault("kar_gordu", {})
    if sz not in kg:
        # İlk çalışma (sezon ortası): geçmişi bilemediğimiz için şu an kar beklenen iller ve kışı erken başlayan
        # Doğu Anadolu "görmüş" sayılır; yanlışlıkla "ilk kar" denmesin. Yeni sezonda (Temmuz) liste sıfırlanır.
        # Takip sezon başında (Temmuz–Ekim) başlamadıysa geçmiş kar bilinmez: o sezon "ilk kar" kartı hiç yapılmaz
        kg[sz] = sorted(IL_BOLGE) if bugun.month not in (7, 8, 9, 10) else []
        return []
    gordu = set(kg[sz])
    olaylar = []
    for k in (1, 2):
        tarih = bugun + datetime.timedelta(days=k)
        yeni = sorted(il for il, g in veri.items() if g.get(tarih.isoformat(), {}).get("hadise") in KAR and il not in gordu)
        if yeni:
            gordu |= set(yeni)
            ad = ", ".join(yeni[:3]) + (f" ve {len(yeni) - 3} il daha" if len(yeni) > 3 else "")
            olaylar.append({"tur": "KAR", "anahtar": f"ILKKAR|{tarih.isoformat()}", "baslik": "BU KIŞIN İLK KARI!", "sahne": "karli",
                            "iller": yeni, "tarih": tarih,
                            "fiil": "bu kışın ilk kar yağışı bekleniyor",
                            "ek": f"Kış lastiği ve zincirinizi hazırlayın. {ad} için beyaz manzara kapıda!",
                            "caption": None})
    kg[sz] = sorted(gordu)
    return olaylar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--cikti", default="yayin/ulke")
    a = ap.parse_args()
    os.makedirs(a.cikti, exist_ok=True)
    durum = json.load(open(DURUM, encoding="utf-8")) if os.path.exists(DURUM) and not a.demo else {}
    gorulen = set(durum.get("paylasilan", []))
    veri = demo_tahminler() if a.demo else tum_tahminler()
    olaylar = ilk_kar(veri, durum) + tespit(veri)
    paylasim = []
    for o in olaylar:
        anahtar = o.get("anahtar") or f"{o['tur']}|{o['tarih'].isoformat()}"
        print("Tespit:", anahtar, len(o["iller"]), "il")
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        import konu
        if konu.dolu_mu(o["tur"]):  # liste/akşam kancasında zaten 2 kez işlendi
            print("Konu bugün yeterince paylaşıldı, atlandı:", anahtar)
            continue
        konu.kaydet(o["tur"])
        g = os.path.join(a.cikti, f"{o['tarih']:%Y%m%d}_{o['tur'].lower()}.jpg")
        kart(o, g)
        h = g.replace(".jpg", "_hikaye.jpg")
        dikey(g, h)
        paylasim.append({"gorsel": h, "gonderi_gorsel": g, "tur": "hikaye+gonderi", "caption": caption(o),
                         "hareket": {"karli": "kar", "yagmurlu": "yagmur", "firtinali": "firtina", "ruzgarli": "ruzgar", "sisli": "sis"}.get(o["sahne"])})
        if len(paylasim) >= 3:  # bir seferde en fazla 3 gelişme
            break
    json.dump(paylasim, open(os.path.join(a.cikti, "paylasim.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not a.demo:
        durum["paylasilan"] = sorted(gorulen)[-200:]
        json.dump(durum, open(DURUM, "w", encoding="utf-8"), ensure_ascii=False)
    print(len(paylasim), "yurt geneli paylaşım hazır")


if __name__ == "__main__":
    main()
