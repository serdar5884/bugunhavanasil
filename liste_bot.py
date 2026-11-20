#!/usr/bin/env python3
"""
17:00 liste Reels'i (Kabul Kapısı'ndaki formatın hava durumu uyarlaması):
- Video doğrudan listeyle açılır (9 sn, solma yok); liste bu sürede okunamaz, video başa döner -> tekrar izlenme
- Merak kapağı ("YARIN KAR YAĞACAK İLLER – Senin ilin var mı?") sadece Reels/profil kapağı olarak gider
- açıklama: "Kaydet, sevdiklerine gönder" (kaydetme/gönderme Instagram'da en güçlü sinyal)

Konu MGM'nin yarınki tahminine göre seçilir: kar > yağmur > en soğuk / en sıcak iller.
Kullanım: python liste_bot.py --cikti yayin/liste [--demo]
"""
import argparse, datetime, glob, json, os, random, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

import hava_bot as hb
from hava_bot import font, metni_sigdir, destek_bandi, yorum_cagrisi, ikon, HADISE, HESAP, BOLGELER

W, H = 1080, 1920
TR = datetime.timezone(datetime.timedelta(hours=3))
AYLAR = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
SARI = (255, 205, 0)
LAC = (18, 30, 55)


def veri_al(demo=False):
    iller = [il for v in BOLGELER.values() for il in v]
    if demo:
        rnd = random.Random(3)
        kod = ["K", "HKY", "Y", "PB", "A", "SY", "CB", "KKY"]
        return [{"il": il, "hadise": rnd.choice(kod), "max": rnd.randint(-2, 18), "min": rnd.randint(-12, 8)} for il in iller]

    def al(il):
        try:
            return hb.il_tahmin(il, 2)
        except Exception as e:
            print("Veri alınamadı:", il, e)
            return None
    with ThreadPoolExecutor(max_workers=6) as ex:
        return [v for v in ex.map(al, iller) if v and v.get("max") is not None]


def konu_sec(veri, tarih):
    """Döner: dict(tur, kapak, baslik, satirlar=[(il, hadise, max, min)], acilis, hareket)"""
    tip = lambda v: HADISE.get(v["hadise"], ("", ""))[1]
    kar = [v for v in veri if tip(v) in ("kar", "karla_yagmur")]
    yagis = [v for v in veri if tip(v) in ("yagmur", "firtina")]
    if len(kar) >= 3:
        s = sorted(kar, key=lambda v: (v["min"], v["max"]))[:14]
        return dict(tur="kar", kapak="KAR YAĞACAK\nİLLER", baslik=f"Kar yağışı beklenen {len(kar)} il",
                    satirlar=s, hareket="kar", fazla=len(kar) - len(s),
                    acilis=f"❄️ Yarın {len(kar)} ilde kar yağışı bekleniyor! Senin ilin listede mi?")
    if len(yagis) >= 6:
        oncelik = {"KGY": 0, "GSY": 1, "KSY": 2, "KY": 3, "SY": 4, "Y": 5, "MSY": 6, "HSY": 7, "HY": 8}
        s = sorted(yagis, key=lambda v: oncelik.get(v["hadise"], 9))[:14]
        return dict(tur="yagmur", kapak="YAĞMUR YAĞACAK\nİLLER", baslik=f"Yağış beklenen {len(yagis)} il",
                    satirlar=s, hareket="yagmur", fazla=len(yagis) - len(s),
                    acilis=f"☔ Yarın {len(yagis)} ilde yağış bekleniyor! Şemsiyeni almayı unutma, senin ilin listede mi?")
    if tarih.month in (11, 12, 1, 2, 3):
        s = sorted(veri, key=lambda v: v["min"])[:10]
        return dict(tur="soguk", kapak="EN SOĞUK\n10 İL", baslik="Gece en soğuk olacak 10 il", satirlar=s,
                    hareket=None, fazla=0, acilis="🥶 Yarın Türkiye'nin en soğuk 10 ili! Senin ilin kaçıncı sırada?")
    s = sorted(veri, key=lambda v: -v["max"])[:10]
    return dict(tur="sicak", kapak="EN SICAK\n10 İL", baslik="Gündüz en sıcak olacak 10 il", satirlar=s,
                hareket=None, fazla=0, acilis="🔥 Yarın Türkiye'nin en sıcak 10 ili! Senin ilin kaçıncı sırada?")


def zemin(tur):
    renk = {"kar": ((70, 100, 140), (20, 35, 60)), "yagmur": ((55, 70, 95), (18, 24, 38)),
            "soguk": ((40, 90, 150), (12, 25, 55)), "sicak": ((230, 120, 40), (120, 30, 20))}[tur]
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(renk[0][i] * (1 - k) + renk[1][i] * k) for i in range(3)))
    # yumuşak bulut lekeleri
    kat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    kd = ImageDraw.Draw(kat)
    rnd = random.Random(tur)
    for _ in range(12):
        cx, cy, r = rnd.randint(-100, W + 100), rnd.randint(0, H // 2), rnd.randint(140, 300)
        kd.ellipse([cx - r, cy - r * .5, cx + r, cy + r * .5], fill=(255, 255, 255, 28))
    img = img.convert("RGBA")
    img.alpha_composite(kat.filter(ImageFilter.GaussianBlur(50)))
    return img


def kapak(k, tarih, yol):
    img = zemin(k["tur"]).convert("RGB")  # RGB üzerine RGBA çizim -> saydamlık karışır
    d = ImageDraw.Draw(img, "RGBA")
    gun = f"{GUNLER[tarih.weekday()]}, {tarih.day} {AYLAR[tarih.month]}"
    d.text((W / 2 - d.textlength(HESAP, font=font("Bold", 42)) / 2, 170), HESAP, font=font("Bold", 42), fill=(255, 255, 255, 220))
    y = 560
    f = font("ExtraBold", 130)
    d.text((W / 2 - d.textlength("YARIN", font=f) / 2, y), "YARIN", font=f, fill=SARI)
    y += 175
    for s in k["kapak"].split("\n"):
        fb = metni_sigdir(d, s, "ExtraBold", 150, W - 100)
        d.text((W / 2 - d.textlength(s, font=fb) / 2, y), s, font=fb, fill="white")
        y += fb.size + 25
    y += 40
    soru = "Senin ilin var mı?" if k["tur"] in ("kar", "yagmur") else "Senin ilin kaçıncı?"
    fs = font("Bold", 64)
    sw = d.textlength(soru, font=fs)
    d.rounded_rectangle([W / 2 - sw / 2 - 40, y, W / 2 + sw / 2 + 40, y + 110], radius=55, fill=SARI)
    d.text((W / 2 - sw / 2, y + 14), soru, font=fs, fill=LAC)
    ft = font("Medium", 46)
    d.text((W / 2 - d.textlength(gun, font=ft) / 2, y + 170), gun, font=ft, fill=(255, 255, 255, 220))
    img.convert("RGB").save(yol, quality=93)
    return yol


def liste(k, tarih, yol):
    img = zemin(k["tur"]).convert("RGB")  # RGB üzerine RGBA çizim -> saydamlık karışır
    d = ImageDraw.Draw(img, "RGBA")
    gun = f"YARIN · {GUNLER[tarih.weekday()]}, {tarih.day} {AYLAR[tarih.month]}"
    d.text((70, 150), gun, font=font("Bold", 44), fill=SARI)
    fb = metni_sigdir(d, k["baslik"], "ExtraBold", 74, W - 140)
    d.text((70, 215), k["baslik"], font=fb, fill="white")
    n = len(k["satirlar"])
    top, alt = 340, H - 330
    sh = min(110, (alt - top) / n)
    for i, v in enumerate(k["satirlar"]):
        y0 = top + i * sh
        box = [60, y0 + 6, W - 60, y0 + sh - 6]
        d.rounded_rectangle(box, radius=22, fill=(255, 255, 255, 38), outline=(255, 255, 255, 60), width=2)
        orta = (box[1] + box[3]) / 2
        h = box[3] - box[1]
        fn = font("ExtraBold", int(h * .42))
        no = str(i + 1)
        d.ellipse([90, orta - h * .32, 90 + h * .64, orta + h * .32], fill=SARI)
        d.text((90 + h * .32 - d.textlength(no, font=fn) / 2, orta - fn.size * .62), no, font=fn, fill=LAC)
        ikon(d, HADISE.get(v["hadise"], ("", "bulut"))[1], 90 + h * .64 + h * .55, orta, int(h * .7))
        tx = 90 + h * .64 + h * 1.05
        fi = font("ExtraBold", int(h * .44))
        d.text((tx, orta - h * .42), v["il"], font=fi, fill="white")
        fd = font("Medium", int(h * .27))
        d.text((tx, orta + h * .06), HADISE.get(v["hadise"], (v["hadise"] or "", ""))[0], font=fd, fill=(255, 255, 255, 215))
        sic = f"{v['max']}°" if k["tur"] != "soguk" else f"{v['min']}°"
        ek = f" / {v['min']}°" if k["tur"] != "soguk" else f" / {v['max']}°"
        ft, fe = font("ExtraBold", int(h * .48)), font("Medium", int(h * .3))
        x = box[2] - 30 - d.textlength(ek, font=fe)
        d.text((x, orta - h * .08), ek, font=fe, fill=(255, 255, 255, 200))
        d.text((x - d.textlength(sic, font=ft), orta - h * .4), sic, font=ft, fill="white")
    if k["fazla"] > 0:
        f = font("Bold", 36)
        s = f"+ {k['fazla']} il daha · Yoruma ilini yaz, sorgulayalım"
        d.text((W / 2 - d.textlength(s, font=f) / 2, alt + 5), s, font=f, fill=(255, 255, 255, 220))
    yorum_cagrisi(d, 70, H - 270, W - 70, H - 205)
    destek_bandi(d, 60, H - 190, W - 60, H - 80)
    f = font("Medium", 30)
    d.text((70, H - 62), "Kaynak: MGM il merkezi tahminleri", font=f, fill=(255, 255, 255, 190))
    img.convert("RGB").save(yol, quality=93)
    return yol


def video(kapak_jpg, liste_jpg, hareket, out, sure=9):
    """Döngü için kısa Reels (Kabul Kapısı ile aynı): doğrudan listeyle açılır, solma yok; kapak sadece
    profil/Reels kapağı olarak gider. Liste 9 sn'de okunamaz -> durdurma ve başa dönme = tekrar izlenme."""
    from hareket import hareketlendir
    hare = hareketlendir(liste_jpg, hareket, liste_jpg[:-4] + "_hareketli.mp4", sure=3)  # 3 sn kesintisiz döngü
    parcalar = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "muzik", "*.mp3")))
    girdi = ["-stream_loop", "-1", "-t", str(sure), "-i", hare]
    sanatci = None
    if parcalar:
        parca = parcalar[(datetime.date.today().toordinal() + 3) % len(parcalar)]
        girdi += ["-ss", "20", "-t", str(sure), "-i", parca]
        ad = os.path.basename(parca)[3:-4].split("-")[0]
        sanatci = {"alex": "Alex Morgan", "atlasaudio": "AtlasAudio", "nastelbom": "Nastelbom",
                   "velariomusic": "VelarioMusic", "andriig": "AndriiG"}.get(ad, ad)
    komut = ["ffmpeg", "-y", "-loglevel", "error", *girdi, "-map", "0:v"]
    if sanatci:
        komut += ["-map", "1:a", "-c:a", "aac", "-b:a", "160k"]
    komut += ["-t", str(sure), "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
              "-movflags", "+faststart", out]
    subprocess.run(komut, check=True)
    return out, sanatci


def caption(k):
    iller = ", ".join(v["il"] for v in k["satirlar"])
    tag = {"kar": "#kar #karyağışı", "yagmur": "#yağmur #sağanak", "soguk": "#soğuk #ayaz", "sicak": "#sıcak #sıcakhava"}[k["tur"]]
    return "\n\n".join([
        k["acilis"],
        f"📍 {iller}" + (f" ve {k['fazla']} il daha" if k["fazla"] else ""),
        "📌 Kaydet, bu illerde yaşayan sevdiklerine gönder!",
        "💬 Listede olmayan ilin mi var? Yorumlara yaz, MGM verisiyle hemen cevaplayalım.\n🔔 Takip edip bildirimleri açarak destek ol 👉 @bugun.hava.nasil",
        "Kaynak: Meteoroloji Genel Müdürlüğü (MGM)",
        f"#havadurumu {tag} #yarınhavanasıl #mgm"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cikti", default="yayin/liste")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.cikti, exist_ok=True)
    for f in glob.glob(os.path.join(a.cikti, "*")):
        os.remove(f)
    tarih = datetime.datetime.now(TR).date() + datetime.timedelta(days=1)
    veri = veri_al(a.demo)
    if len(veri) < 60:
        sys.exit(f"Yeterli veri yok ({len(veri)} il)")
    k = konu_sec(veri, tarih)
    kap = kapak(k, tarih, os.path.join(a.cikti, "reels_kapak.jpg"))
    lst = liste(k, tarih, os.path.join(a.cikti, "liste.jpg"))
    mp4, sanatci = video(kap, lst, k["hareket"], os.path.join(a.cikti, "reels.mp4"))
    cap = caption(k) + (f"\n\n🎵 Müzik: {sanatci} (Pixabay)" if sanatci else "")
    open(os.path.join(a.cikti, "caption.txt"), "w", encoding="utf-8").write(cap)
    if not a.demo:
        json.dump({"son": datetime.datetime.now(TR).date().isoformat(), "konu": k["tur"]}, open("liste_durum.json", "w"))
    print("Konu:", k["tur"], "|", mp4)


if __name__ == "__main__":
    main()
