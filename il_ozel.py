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


def gorsel(il, merkez, ilceler, tarih, yol, gun_no=1):
    t = tarih.isoformat()
    m = merkez.get(t)
    if not m:
        raise RuntimeError(f"{il} için {t} tahmini yok")
    ilce_v = [{"il": ad, **d[t]} for ad, d in sorted(ilceler.items(), key=lambda x: x[0].replace("Ş", "Sz").replace("İ", "Iz"))
              if t in d]
    sahne = baskin_sahne([{"hadise": m["hadise"]}] * 3 + [{"hadise": v["hadise"]} for v in ilce_v])
    img = sahne_ciz(sahne, il)
    d = ImageDraw.Draw(img, "RGBA")
    M = 50
    # --- başlık
    gun_k = {1: "BUGÜN", 2: "YARIN"}.get(gun_no, "")
    f1, f2 = font("ExtraBold", 40), font("Bold", 28)
    d.text((M, 36), gun_k, font=f1, fill=SARI)
    d.text((M + d.textlength(gun_k, font=f1) + 10, 48), "HAVA NASIL?", font=f2, fill="white")
    il_b = il.replace("i", "İ").replace("ı", "I").upper()
    d.text((M, 82), il_b, font=font("ExtraBold", 92), fill="white")
    d.text((M, 186), f"{tarih.day} {AYLAR[tarih.month]} {tarih.year}, {GUNLER[tarih.weekday()]}", font=font("Medium", 30),
           fill=(255, 255, 255, 220))
    # --- merkez: büyük ikon + sıcaklık
    metin, tip = HADISE.get(m["hadise"] or "", (m["hadise"] or "-", "bulut"))
    ikon(d, tip, W - 250, 140, 150)
    f_s = font("ExtraBold", 110)
    sic = f"{m['max']}°"
    d.text((W - M - d.textlength(sic, font=f_s), 200), sic, font=f_s, fill="white")
    alt = f"En düşük {m['min']}° · {metin}"
    f_a = metni_sigdir(d, alt, "SemiBold", 28, 420)
    d.text((W - M - d.textlength(alt, font=f_a), 320), alt, font=f_a, fill=(255, 255, 255, 230))
    # --- ilçeler (4 sütun)
    y0, sut = 380, 4
    satir_n = (min(len(ilce_v), 20) + sut - 1) // sut
    kh = min(112, (H - 225 - 225 - y0) / max(1, satir_n) - 12)  # alttan: 5 günlük (≈225) + bantlar (≈225)
    kw, gap = (W - 2 * M - gap_x(3)) / sut, 12
    for i, v in enumerate(ilce_v[:20]):
        c, r = i % sut, i // sut
        x, y = M + c * (kw + gap_x(1)), y0 + r * (kh + gap)
        d.rounded_rectangle([x, y, x + kw, y + kh], radius=18, fill=(15, 30, 55, 120), outline=(255, 255, 255, 60), width=2)
        mt, tp = HADISE.get(v["hadise"] or "", (v["hadise"] or "-", "bulut"))
        ikon(d, tp, x + 40, y + kh / 2, 58)
        fa = metni_sigdir(d, v["il"], "Bold", 27, kw - 84)
        d.text((x + 76, y + 16), v["il"], font=fa, fill="white")
        d.text((x + 76, y + 54), f"{v['max']}°", font=font("ExtraBold", 38), fill="white")
        d.text((x + 76 + d.textlength(f"{v['max']}°", font=font("ExtraBold", 38)) + 6, y + 68), f"/{v['min']}°",
               font=font("Medium", 22), fill=(255, 255, 255, 190))
    satir = (min(len(ilce_v), 20) + sut - 1) // sut
    # --- 5 günlük şerit
    y5 = y0 + satir * (kh + gap) + 14
    d.text((M, y5), f"{il} merkez · 5 günlük", font=font("Bold", 26), fill=SARI)
    y5 += 40
    gunler = sorted(k for k in merkez if k >= t)[:5]
    gw = (W - 2 * M - 4 * 10) / 5
    for i, k in enumerate(gunler):
        x = M + i * (gw + 10)
        v = merkez[k]
        dt = datetime.date.fromisoformat(k)
        d.rounded_rectangle([x, y5, x + gw, y5 + 165], radius=18, fill=(15, 30, 55, 130))
        ad = GUN_KISA[dt.weekday()] if i else ("Bugün" if gun_no == 1 else "Yarın")
        fg = font("Bold", 24)
        d.text((x + gw / 2 - d.textlength(ad, font=fg) / 2, y5 + 10), ad, font=fg, fill="white")
        ikon(d, HADISE.get(v["hadise"] or "", ("", "bulut"))[1], x + gw / 2, y5 + 78, 60)
        s = f"{v['max']}°/{v['min']}°"
        fs = font("ExtraBold", 26)
        d.text((x + gw / 2 - d.textlength(s, font=fs) / 2, y5 + 120), s, font=fs, fill="white")
    yorum_cagrisi(d, M + 40, H - 212, W - M - 40, H - 160)
    destek_bandi(d, M, H - 150, W - M, H - 50)
    d.text((M, H - 40), "Kaynak: Meteoroloji Genel Müdürlüğü (MGM) · ilçe tahminleri", font=font("Regular", 22),
           fill=(255, 255, 255, 170))
    img.save(yol, quality=93)


def gap_x(n):
    return 12 * n


def video(gorsel_yolu, sure=12):
    """Görseli 9:16 Reels videosuna çevirir (bulanık arka plan + Pixabay müziği). Döner: (video, kapak, sanatçı)"""
    import glob, subprocess
    from reels_bot import dikey
    kapak = gorsel_yolu[:-4] + "_kapak.jpg"
    mp4 = gorsel_yolu[:-4] + ".mp4"
    dikey(gorsel_yolu, kapak)
    parcalar = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "muzik", "*.mp3")))
    girdi = ["-loop", "1", "-t", str(sure), "-i", kapak]
    sanatci = None
    if parcalar:
        parca = parcalar[(datetime.date.today().toordinal() + 5) % len(parcalar)]  # sabah reels'inden farklı parça
        girdi += ["-i", parca]
        ad = os.path.basename(parca)[3:-4]
        sanatci = {"alex": "Alex Morgan", "atlasaudio": "AtlasAudio", "nastelbom": "Nastelbom",
                   "velariomusic": "VelarioMusic", "andriig": "AndriiG"}.get(ad.split("-")[0], ad.split("-")[0])
    komut = ["ffmpeg", "-y", "-loglevel", "error", *girdi,
             "-vf", f"fade=t=in:d=0.6,fade=t=out:st={sure - 0.8}:d=0.8,format=yuv420p", "-r", "30",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    if sanatci:
        komut += ["-af", f"afade=t=in:d=0.8,afade=t=out:st={sure - 2}:d=2", "-c:a", "aac", "-b:a", "128k", "-shortest"]
    subprocess.run(komut + ["-t", str(sure), mp4], check=True)
    return mp4, kapak, sanatci


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--il", default="Sivas")
    ap.add_argument("--gun", type=int, default=1)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--cikti", default="yayin/il_ozel")
    ap.add_argument("--video", action="store_true", help="Reels videosu da üret")
    a = ap.parse_args()
    os.makedirs(a.cikti, exist_ok=True)
    tarih = datetime.datetime.now(TR).date() + datetime.timedelta(days=a.gun - 1)
    merkez, ilceler = demo_veri() if a.demo else veri_cek(a.il)
    ascii_ad = a.il.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))
    yol = os.path.join(a.cikti, f"{ascii_ad}_{tarih:%Y%m%d}.jpg")
    gorsel(a.il, merkez, ilceler, tarih, yol, a.gun)
    gun_ad = "Bugün" if a.gun == 1 else "Yarın"
    etiket = ascii_ad.lower()
    cap = (f"📍 {a.il} – {gun_ad.lower()} hava nasıl? Merkez, tüm ilçeler ve 5 günlük tahmin 👇\n\n"
           f"💬 Yorumlara \"{a.il} 5 günlük\" yaz, tahmini hemen gönderelim!\n"
           f"🔁 Hemşehrilerinle paylaş, takip edip bildirimleri açarak destek ol!\n\n"
           f"Kaynak: Meteoroloji Genel Müdürlüğü (MGM)\n\n"
           f"#{etiket} #{etiket}havadurumu #{etiket}haber #havadurumu #bugunhavanasil #mgm")
    if a.video:
        mp4, kapak, sanatci = video(yol)
        if sanatci:
            cap += f"\n\n🎵 Müzik: {sanatci} (Pixabay)"
        print("Video:", mp4)
    open(yol[:-4] + ".txt", "w", encoding="utf-8").write(cap)
    open(os.path.join(a.cikti, "son.txt"), "w").write(yol)
    print("Hazır:", yol, len(ilceler), "ilçe")


if __name__ == "__main__":
    main()
