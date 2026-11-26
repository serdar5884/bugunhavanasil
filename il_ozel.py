#!/usr/bin/env python3
"""
Tek bir ile özel günlük hava durumu görseli (1080x1350): il merkezi + tüm ilçeler + 5 günlük tahmin.
Yerel sayfalarla ortak gönderi (Collab) veya hikâye için.

Kullanım: python il_ozel.py --il Sivas --cikti yayin/il_ozel      (--demo: örnek veri, --gun 2: yarın)
"""
import argparse, datetime, os, random, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw
from hava_bot import (HADISE, mgm_get, merkezleri_yukle, sahne_ciz, baskin_sahne, font, ikon, metni_sigdir,
                      destek_bandi, yorum_cagrisi, W, H, HESAP)

TR = datetime.timezone(datetime.timedelta(hours=3))
SARI = (255, 205, 0)
# Ortak sayfalara aynı içerik farklı görünümle gitsin (Instagram kopya saymasın): renk tonu, kart rengi, düzen
TEMALAR = [
    dict(ad="klasik"),
    dict(ad="gokyuzu", ton=((135, 205, 255), (45, 135, 225)), oran=.6, vurgu=(255, 236, 110),
         kart=((80, 160, 235), (45, 115, 205))),
    dict(ad="gunbatimi", ton=((250, 130, 60), (130, 25, 85)), vurgu=(255, 240, 160), kart=((170, 60, 80), (95, 20, 65)),
         duzen="liste"),
    dict(ad="acik", ton=((236, 241, 248), (205, 214, 228)), oran=.2, kart=((104, 122, 156), (66, 82, 114)), simge="alt"),
    dict(ad="zumrut", ton=((20, 160, 135), (10, 45, 80)), vurgu=(170, 255, 205), kart=((25, 120, 115), (10, 60, 85)),
         baslik="orta"),
]
AYLAR = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
GUN_KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
SIVAS_ILCELER = ["Akıncılar", "Altınyayla", "Divriği", "Doğanşar", "Gemerek", "Gölova", "Gürün", "Hafik", "İmranlı",
                 "Kangal", "Koyulhisar", "Suşehri", "Şarkışla", "Ulaş", "Yıldızeli", "Zara"]


def gunluk(istno):
    t = mgm_get(f"/tahminler/gunluk?istno={istno}")
    t = t[0] if isinstance(t, list) else t
    out = {}
    for i in range(1, 6):
        ts = str(t.get(f"tarihGun{i}", ""))[:10]
        if ts:
            out[ts] = {"hadise": t.get(f"hadiseGun{i}"), "max": t.get(f"enYuksekGun{i}"), "min": t.get(f"enDusukGun{i}"),
                       "ruzgar": t.get(f"ruzgarHizGun{i}")}
    return out


def veri_cek(il):
    merkez = gunluk(merkezleri_yukle()[il])
    ilceler = mgm_get("/merkezler/ililcesi?il=" + urllib.parse.quote(il))
    haric = ("havaliman", "kayak", "merkezi", "baraj", "liman", "istasyon", "üniversite", "tesis", "dağı", "gölü", "geçidi")
    ilceler = [x for x in ilceler if x.get("ilce") and x.get("ilce") not in (il, "Merkez")
               and not any(h in x["ilce"].lower() for h in haric)]

    def al(x):
        try:
            return x["ilce"], gunluk(x["gunlukTahminIstNo"])
        except Exception:
            return x["ilce"], {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        return merkez, dict(ex.map(al, ilceler))


def demo_veri():
    rnd = random.Random(5)
    bugun = datetime.datetime.now(TR).date()
    def g():
        out = {}
        for k in range(5):
            mx = rnd.randint(6, 16)
            out[(bugun + datetime.timedelta(days=k)).isoformat()] = {"hadise": rnd.choice(["PB", "CB", "Y", "A", "HKY", "SIS"]),
                                                                    "max": mx, "min": mx - rnd.randint(5, 10), "ruzgar": rnd.randint(5, 30)}
        return out
    return g(), {ilce: g() for ilce in SIVAS_ILCELER}


def gorsel(il, merkez, ilceler, tarih, yol, gun_no=1, tema=0):
    t = tarih.isoformat()
    m = merkez.get(t)
    if not m:
        raise RuntimeError(f"{il} için {t} tahmini yok")
    ilce_v = [{"il": ad, **d[t]} for ad, d in sorted(ilceler.items(), key=lambda x: x[0].replace("Ş", "Sz").replace("İ", "Iz"))
              if t in d]
    sahne = baskin_sahne([{"hadise": m["hadise"]}] * 3 + [{"hadise": v["hadise"]} for v in ilce_v])
    img = sahne_ciz(sahne, il)
    T = TEMALAR[tema % len(TEMALAR)]
    SARI = T.get("vurgu", (255, 205, 0))
    if T.get("ton"):  # sahne (yağmur/kar efekti) korunur, üstüne renk tonu
        from tasarim import _dikey_degrade
        ton = _dikey_degrade(img.width, img.height, *T["ton"]).convert(img.mode)
        img = Image.blend(img, ton, T.get("oran", .5))
    kr = T.get("kart")
    from tasarim import cam_kart as _ck
    cam_kart = lambda im, box, r=26: _ck(im, box, r, renk=kr, opak=175 if kr else 150)
    d = ImageDraw.Draw(img, "RGBA")
    M = 50
    orta = T.get("baslik") == "orta"
    # --- ile özel simgeler (sade beyaz silüet, sağ üstte, soluk)
    from sehir_simge import SIMGELER
    renkli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simgeler", f"{il}_renkli.png")
    if T.get("simge") == "alt" and os.path.exists(renkli):  # altta renkli bina şeridi (hazır tasarımlardaki gibi)
        sm = Image.open(renkli).convert("RGBA")
        sm = sm.resize((W, int(sm.height * W / sm.width)), Image.LANCZOS)
        katman = Image.new("RGBA", img.size, (0, 0, 0, 0))
        katman.alpha_composite(sm, (0, H - 312))  # ilçe kartlarının altı ile yorum bandı arası
        if img.mode == "RGBA":
            img.alpha_composite(katman)
        else:
            img.paste(katman, (0, 0), katman)
        d = ImageDraw.Draw(img, "RGBA")
    elif il in SIMGELER and T.get("simge", True):
        sm = SIMGELER[il]()
        alt = T.get("simge") == "alt"  # altta, bantların arkasında geniş silüet
        sg = W - 2 * M if alt else 760 if orta else 520  # ortalı başlıkta: başlığın arkasında, geniş ve daha soluk
        sm = sm.resize((sg, int(sm.height * sg / sm.width)), Image.LANCZOS)
        sm.putalpha(sm.getchannel("A").point(lambda v: v * (150 if alt else 60 if orta else 185) // 255))
        katman = Image.new("RGBA", img.size, (0, 0, 0, 0))
        katman.alpha_composite(sm, (M if alt else (W - sg) // 2 if orta else W - M - sm.width,
                                    H - 120 - sm.height if alt else 272 - sm.height))
        if img.mode == "RGBA":
            img.alpha_composite(katman)
        else:
            img.paste(katman, (0, 0), katman)
        d = ImageDraw.Draw(img, "RGBA")
    # --- başlık
    from tasarim import takvim_ikon
    gun_k = {1: "BUGÜN", 2: "YARIN"}.get(gun_no) or GUNLER[tarih.weekday()].replace("i", "İ").upper()
    f1 = font("ExtraBold", 40)
    orta = T.get("baslik") == "orta"
    def X(metin, f, x=M):  # ortalı başlık temasında yatay konum
        return (W - d.textlength(metin, font=f)) / 2 if orta else x
    d.text((X(f"{gun_k} HAVA NASIL?", f1) + 2, 38), f"{gun_k} HAVA NASIL?", font=f1, fill=(0, 0, 0, 100))
    d.text((X(f"{gun_k} HAVA NASIL?", f1), 36), f"{gun_k} HAVA NASIL?", font=f1, fill=SARI)
    il_b = il.replace("i", "İ").replace("ı", "I").upper()
    f_il = metni_sigdir(d, il_b, "ExtraBold", 120, W - 2 * M)
    d.text((X(il_b, f_il) + 4, 84), il_b, font=f_il, fill=(0, 0, 0, 120))
    d.text((X(il_b, f_il), 80), il_b, font=f_il, fill="white")
    tr = f"{tarih.day} {AYLAR[tarih.month]} {tarih.year}, {GUNLER[tarih.weekday()]}"
    tx = X(tr, font("Medium", 30)) + (22 if orta else 0)
    takvim_ikon(d, tx - 44 if orta else M, 232, 30)
    d.text((tx if orta else M + 44, 228), tr, font=font("Medium", 30), fill=(255, 255, 255, 220))
    # --- merkez: bugün ve yarın (yan yana iki cam kart)
    yarin = (tarih + datetime.timedelta(days=1)).isoformat()
    gunler2 = [(t, {1: "BUGÜN", 2: "YARIN"}.get(gun_no, "BUGÜN"), tarih)]
    if merkez.get(yarin):
        gunler2.append((yarin, {1: "YARIN", 2: "ÖBÜR GÜN"}.get(gun_no, "YARIN"), tarih + datetime.timedelta(days=1)))
    yk, kh2, gap2 = 285, 170, 20
    kw2 = (W - 2 * M - gap2 * (len(gunler2) - 1)) / len(gunler2)
    for i, (k, etk, dt) in enumerate(gunler2):
        v = merkez[k]
        x = M + i * (kw2 + gap2)
        cam_kart(img, [x, yk, x + kw2, yk + kh2], r=24)
        mt, tp = HADISE.get(v["hadise"] or "", (v["hadise"] or "-", "bulut"))
        ikon(d, tp, x + 85, yk + kh2 / 2 + 6, 120)
        d.text((x + 170, yk + 16), f"{il.upper().replace('I', 'I')} · {etk}" if False else f"{etk} · {GUN_KISA[dt.weekday()]}",
               font=font("ExtraBold", 28), fill=SARI)
        fs = font("ExtraBold", 72)
        d.text((x + 168, yk + 48), f"{v['max']}°", font=fs, fill="white")
        d.text((x + 172 + d.textlength(f"{v['max']}°", font=fs), yk + 80), f"/ {v['min']}°", font=font("Medium", 32),
               fill=(255, 255, 255, 200))
        fm = metni_sigdir(d, mt, "SemiBold", 26, kw2 - 185)
        d.text((x + 170, yk + 128), mt, font=fm, fill=(255, 255, 255, 230))
    # --- ilçeler (bugün, 4 sütun)
    y0 = yk + kh2 + 62
    sut = 4 if len(ilce_v) > 9 else 3 if len(ilce_v) > 4 else 2  # az ilçeli illerde kartlar büyür, boşluk kalmaz
    etk = {"BUGÜN": "Bugün", "YARIN": "Yarın", "ÖBÜR GÜN": "Öbür gün"}.get(gunler2[0][1], gunler2[0][1].title())
    d.text((M, y0 - 44), f"İlçeler · {etk}", font=font("Bold", 28), fill=SARI)
    alt_sinir = H - 230  # yorum çağrısı + destek bandı
    if T.get("duzen") == "liste":  # 2 sütunlu satır listesi: ikon · ilçe · sıcaklık (sağa yaslı)
        sut = 2
    satir_n = (min(len(ilce_v), 24) + sut - 1) // sut
    gap = 12
    kh = min(118 if sut == 4 else 150, (alt_sinir - y0) / max(1, satir_n) - gap)
    kw = (W - 2 * M - gap_x(sut - 1)) / sut
    for i, v in enumerate(ilce_v[:24]):
        c, r = i % sut, i // sut
        x, y = M + c * (kw + gap_x(1)), y0 + r * (kh + gap)
        cam_kart(img, [x, y, x + kw, y + kh], r=18)
        mt, tp = HADISE.get(v["hadise"] or "", (v["hadise"] or "-", "bulut"))
        if sut == 2:
            ikon(d, tp, x + 44, y + kh / 2, min(70, kh * .9))
            d.text((x + 90, y + kh / 2), v["il"], font=metni_sigdir(d, v["il"], "Bold", 30, kw - 250), fill="white", anchor="lm")
            fb, fk = font("ExtraBold", 36), font("Medium", 24)
            mn = f" / {v['min']}°"
            sx = x + kw - 20 - d.textlength(mn, font=fk)
            d.text((sx, y + kh / 2 + 4), mn, font=fk, fill=(255, 255, 255, 190), anchor="lm")
            d.text((sx, y + kh / 2), f"{v['max']}°", font=fb, fill="white", anchor="rm")
            continue
        k = max(1.0, min(1.35, kh / 112))  # büyük kartlarda içerik de büyür
        ikon(d, tp, x + 40 * k, y + kh / 2, int(66 * k))
        fa = metni_sigdir(d, v["il"], "Bold", int(27 * k), kw - 84 * k)
        d.text((x + 76 * k, y + kh / 2 - 40 * k), v["il"], font=fa, fill="white")
        fb = font("ExtraBold", int(38 * k))
        d.text((x + 76 * k, y + kh / 2 - 2 * k), f"{v['max']}°", font=fb, fill="white")
        d.text((x + 76 * k + d.textlength(f"{v['max']}°", font=fb) + 6, y + kh / 2 + 12 * k), f"/{v['min']}°",
               font=font("Medium", int(22 * k)), fill=(255, 255, 255, 190))
    yorum_cagrisi(d, M + 40, H - 212, W - M - 40, H - 160)
    destek_bandi(d, M, H - 150, W - M, H - 50)
    d.text((M, H - 40), "Kaynak: Meteoroloji Genel Müdürlüğü (MGM) · ilçe tahminleri", font=font("Regular", 22),
           fill=(255, 255, 255, 170))
    img.save(yol, quality=93)


def gap_x(n):
    return 12 * n


def animasyon(il, merkez, ilceler, tarih, yol, gun_no=1, sure=6, fps=20, tema=0, tam_ekran=False):
    """Görselin hareketli hali (kar/yağmur/bulut akar): <ad>_hareketli.mp4, 6 sn kesintisiz döngü.
    tam_ekran: 9:16 (üst/alt kenar sahnenin renkleriyle uzatılır, yağmur/kar oraya da yağar), yakınlaşma yok."""
    import random, shutil, subprocess, tempfile
    import hava_bot, hareket
    from hazir_tasarim import dikey
    tmp = tempfile.mkdtemp()
    n = sure * fps
    t = tarih.isoformat()
    ilce_v = [dict(v[t]) for v in ilceler.values() if t in v]
    m = merkez.get(t) or {}
    sahne = baskin_sahne([{"hadise": m.get("hadise")}] * 3 + [{"hadise": v["hadise"]} for v in ilce_v])
    efekt = {"karli": "kar", "yagmurlu": "yagmur", "firtina": "yagmur", "saganak": "yagmur", "sisli": None}.get(sahne)
    try:
        for i in range(n):
            hava_bot.FAZ = i / n
            k_yol = os.path.join(tmp, f"k{i:03d}.jpg")
            gorsel(il, merkez, ilceler, tarih, k_yol, gun_no, tema)
            if tam_ekran:
                kare = Image.open(k_yol).convert("RGB")
                h0 = kare.height
                kare = dikey(kare)
                dy = (kare.height - h0) // 2
                if efekt:  # uzatılan şeritlere de aynı efekt
                    kat = Image.new("RGBA", kare.size, (0, 0, 0, 0))
                    fn = {"kar": hareket._kar, "yagmur": hareket._yagmur}[efekt]
                    fn(ImageDraw.Draw(kat), kare.width, kare.height, i / n, random.Random(7))
                    mk = Image.new("L", kare.size, 255)
                    ImageDraw.Draw(mk).rectangle([0, dy + 20, kare.width, dy + h0 - 20], fill=0)
                    kat.putalpha(Image.composite(kat.getchannel("A"), Image.new("L", kare.size, 0), mk))
                    kare.paste(kat, (0, 0), kat)
                from hazir_tasarim import guvenli, guvenli_zemin
                if i == 0:
                    zemin_g = guvenli_zemin(kare)
                kare = guvenli(kare, zemin_g)
                if i == 0:
                    kare.save(yol[:-4] + "_kapak.jpg", quality=93)
                kare.save(k_yol, quality=90)
    finally:
        hava_bot.FAZ = None
    mp4 = yol[:-4] + "_hareketli.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(tmp, "k%03d.jpg"),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", mp4], check=True)
    shutil.rmtree(tmp)
    return mp4


def video(gorsel_yolu, sure=12):
    """9:16 Reels: bulanık arka plan ortasında hareketli kart + Pixabay müziği. Döner: (video, kapak, sanatçı)"""
    import glob, subprocess
    from reels_bot import dikey
    kapak = gorsel_yolu[:-4] + "_kapak.jpg"
    mp4 = gorsel_yolu[:-4] + ".mp4"
    hareketli = gorsel_yolu[:-4] + "_hareketli.mp4"
    dikey(gorsel_yolu, kapak)
    parcalar = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "muzik", "*.mp3")))
    girdi = ["-loop", "1", "-t", str(sure), "-i", kapak]
    if os.path.exists(hareketli):
        girdi += ["-stream_loop", "-1", "-t", str(sure), "-i", hareketli]
        vf = (f"[0:v]fps=30,setsar=1[a];[1:v]fps=30,setsar=1[h];[a][h]overlay=0:(H-h)/2:shortest=1,"
              f"fade=t=in:d=0.6,fade=t=out:st={sure - 0.8}:d=0.8,format=yuv420p[v]")
    else:
        vf = f"[0:v]fade=t=in:d=0.6,fade=t=out:st={sure - 0.8}:d=0.8,format=yuv420p[v]"
    ses = 2 if os.path.exists(hareketli) else 1  # müzik girdisinin sırası
    sanatci = None
    if parcalar:
        parca = parcalar[(datetime.date.today().toordinal() + 5) % len(parcalar)]  # sabah reels'inden farklı parça
        girdi += ["-i", parca]
        ad = os.path.basename(parca)[3:-4]
        sanatci = {"alex": "Alex Morgan", "atlasaudio": "AtlasAudio", "nastelbom": "Nastelbom",
                   "velariomusic": "VelarioMusic", "andriig": "AndriiG"}.get(ad.split("-")[0], ad.split("-")[0])
    komut = ["ffmpeg", "-y", "-loglevel", "error", *girdi, "-filter_complex", vf, "-map", "[v]", "-r", "30",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-movflags", "+faststart"]
    if sanatci:
        komut += ["-map", f"{ses}:a", "-af", f"afade=t=in:d=0.8,afade=t=out:st={sure - 2}:d=2",
                  "-c:a", "aac", "-b:a", "128k"]
    subprocess.run(komut + ["-t", str(sure), mp4], check=True)
    from hareket import guvenli_alan
    guvenli_alan(mp4)  # tam ekranda kırpılmasın
    return mp4, kapak, sanatci


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--il", default="Sivas")
    ap.add_argument("--gun", type=int, default=1)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--cikti", default="yayin/il_ozel")
    ap.add_argument("--video", action="store_true", help="Reels videosu da üret")
    ap.add_argument("--varyant", type=int, default=1, help="Kaç farklı gün (her ortak sayfaya ayrı içerik)")
    a = ap.parse_args()
    os.makedirs(a.cikti, exist_ok=True)
    merkez, ilceler = demo_veri() if a.demo else veri_cek(a.il)
    ascii_ad = a.il.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))
    etiket = ascii_ad.lower()
    yollar = []
    # Her ortak sayfaya aynı içerik, farklı renk/tasarım (kopya Reels sayılmasın)
    gun = a.gun
    tarih = datetime.datetime.now(TR).date() + datetime.timedelta(days=gun - 1)
    for k in range(max(1, min(a.varyant, 8))):
        yol = os.path.join(a.cikti, f"{ascii_ad}_{tarih:%Y%m%d}" + (f"_t{k}" if k else "") + ".jpg")
        import hazir_tasarim
        hazir = hazir_tasarim.var_mi(a.il)  # ile özel hazır tasarımlar (tasarimlar/<İl>/) varsa onlar
        try:
            kod = hazir and hazir_tasarim.ayar(a.il, k).get("kod")  # bu sayfa için kodla çizilen tema (ör. "acik")
            tema_k = next((i for i, x in enumerate(TEMALAR) if x["ad"] == kod), k) if kod else k
            if kod:
                gorsel(a.il, merkez, ilceler, tarih, yol, gun, tema_k)
            elif hazir:
                t_ = tarih.isoformat()
                iv = [{"il": ad, **d[t_]} for ad, d in sorted(ilceler.items(), key=lambda x: x[0].replace("Ş", "Sz").replace("İ", "Iz"))
                      if t_ in d]
                hazir_tasarim.kart(a.il, k % hazir_tasarim.sayi(a.il), merkez, iv, tarih, yol)
            else:
                gorsel(a.il, merkez, ilceler, tarih, yol, gun, k)
        except Exception as e:
            print(f"{tarih} görseli üretilemedi:", e)
            continue
        gun_ad = {1: "bugün", 2: "yarın"}.get(gun, f"{GUNLER[tarih.weekday()]} ({tarih.day} {AYLAR[tarih.month]})")
        cap = (f"📍 {a.il} – {gun_ad} hava nasıl? Merkezde bugün ve yarın, tüm ilçelerde bugün 👇\n\n"
               f"💬 Yorumlara \"{a.il} 5 günlük\" yaz, tahmini hemen gönderelim!\n"
               f"📤 Hemşehrilerine gönder, hazırlıklı olsunlar!\n\n"
               f"Kaynak: Meteoroloji Genel Müdürlüğü (MGM)\n\n"
               f"#{etiket} #{etiket}havadurumu #{etiket}haber #havadurumu #bugunhavanasil #mgm")
        if a.video:
            try:
                if kod:  # kodla çizilen tema, tam ekran
                    print("Hareketli:", animasyon(a.il, merkez, ilceler, tarih, yol, gun, tema=tema_k, tam_ekran=True))
                elif hazir:  # hazır tasarım: ikonlar ve arka plandaki güneş hareketli
                    print("Hareketli:", hazir_tasarim.animasyon(a.il, k % hazir_tasarim.sayi(a.il), merkez, iv, tarih, yol))
                else:
                    print("Hareketli:", animasyon(a.il, merkez, ilceler, tarih, yol, gun, tema=k))
            except Exception as e:
                print("Hareketli görsel üretilemedi:", e)
            mp4, kapak, sanatci = hazir_tasarim.video(yol) if hazir else video(yol)
            if sanatci:
                cap += f"\n\n🎵 Müzik: {sanatci} (Pixabay)"
            print("Video:", mp4)
        open(yol[:-4] + ".txt", "w", encoding="utf-8").write(cap)
        yollar.append(yol)
        print("Hazır:", yol, len(ilceler), "ilçe")
    if not yollar:
        raise SystemExit("Görsel üretilemedi")
    open(os.path.join(a.cikti, "son.txt"), "w").write(yollar[0])
    open(os.path.join(a.cikti, "liste.txt"), "w").write("\n".join(yollar))


if __name__ == "__main__":
    main()
