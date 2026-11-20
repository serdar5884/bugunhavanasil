#!/usr/bin/env python3
"""Profilde sabitlenecek tanıtım gönderisi (3 görsel, 1080x1350). Kullanım: python tanitim.py yayin/tanitim"""
import os, sys
from PIL import Image, ImageDraw
from hava_bot import sahne_ciz, font, destek_bandi, metni_sigdir, ikon, HESAP, W, H

SARI, LACI = (255, 205, 0), (18, 30, 55)


def ortala(d, y, metin, f, renk="white"):
    d.text((W / 2 - d.textlength(metin, font=f) / 2, y), metin, font=f, fill=renk)


def baslik_ust(d):
    f1, f2 = font("ExtraBold", 46), font("Bold", 30)
    gen = d.textlength("BUGÜN", font=f1) + 12 + d.textlength("HAVA NASIL?", font=f2)
    x = W / 2 - gen / 2
    d.text((x, 50), "BUGÜN", font=f1, fill=SARI)
    d.text((x + d.textlength("BUGÜN", font=f1) + 12, 64), "HAVA NASIL?", font=f2, fill="white")


def balon(d, x0, y0, x1, kullanici, metin, f, renk, yazi):
    satirlar, s = [], ""
    for k in metin.split():
        if d.textlength((s + " " + k).strip(), font=f) <= x1 - x0 - 60:
            s = (s + " " + k).strip()
        else:
            satirlar.append(s); s = k
    satirlar.append(s)
    h = 70 + len(satirlar) * (f.size + 10) + 20
    d.rounded_rectangle([x0, y0, x1, y0 + h], radius=34, fill=renk)
    d.text((x0 + 30, y0 + 22), kullanici, font=font("Bold", 28), fill=yazi)
    y = y0 + 66
    for s in satirlar:
        d.text((x0 + 30, y), s, font=f, fill=yazi); y += f.size + 10
    return y0 + h


def gorsel1(yol):
    img = sahne_ciz("parcali", "tanitim")
    d = ImageDraw.Draw(img, "RGBA")
    baslik_ust(d)
    ortala(d, 170, "Senin ilinde", font("ExtraBold", 92))
    ortala(d, 275, "hava nasıl?", font("ExtraBold", 92), SARI)
    ortala(d, 400, "İlini yorumlara yaz,", font("Bold", 46))
    ortala(d, 458, "MGM verisiyle hemen cevaplayalım!", font("Bold", 46))
    f = font("Medium", 36)
    y = balon(d, 90, 560, 760, "sen", "Zara yarın nasıl?", f, (255, 255, 255, 235), LACI)
    y = balon(d, 250, y + 26, 990, HESAP, "Zara (Sivas) – yarın: Parçalı bulutlu, en yüksek 9°, en düşük -2° · Rüzgar 15 km/sa · Kaynak: MGM", f, (25, 45, 85, 230), (255, 255, 255))
    ortala(d, y + 36, "İl, ilçe ya da gün yazabilirsin:", font("SemiBold", 32), (255, 255, 255, 235))
    ortala(d, y + 82, "\"İzmir 5 günlük\"  ·  \"Onikişubat bugün\"  ·  \"Sivas cumartesi\"", font("SemiBold", 30), SARI)
    destek_bandi(d, 56, H - 165, W - 56, H - 60)
    img.save(yol, quality=93)


def gorsel2(yol):
    img = sahne_ciz("bulutlu", "tanitim2")
    d = ImageDraw.Draw(img, "RGBA")
    baslik_ust(d)
    ortala(d, 150, "Bu sayfada neler var?", font("ExtraBold", 66))
    maddeler = [
        ("gunes", "Her sabah 07:17", "Bugün hava nasıl? 7 bölge, 81 il"),
        ("az_bulut", "Her akşam 20:13", "Yarının hava durumu"),
        ("kar", "Her gün 17:00", "Yarın kar ve yağmur yağacak iller listesi"),
        ("bulut", "Her Cuma 17:47", "Hafta sonu hava durumu"),
        ("firtina", "Anında", "MGM turuncu ve kırmızı kodlu uyarılar"),
        ("yagmur", "Son dakika", "Sel, kar, sis haberleri ve kapalı yollar"),
        ("az_bulut", "Yorumlarda", "İl, ilçe ya da gün yaz: 5 günlük tahmin"),
    ]
    y = 240
    for tip, ust, alt in maddeler:
        d.rounded_rectangle([70, y, W - 70, y + 116], radius=28, fill=(15, 30, 55, 120), outline=(255, 255, 255, 70), width=2)
        ikon(d, tip, 150, y + 58, 86)
        d.text((225, y + 14), ust, font=font("ExtraBold", 38), fill=SARI)
        d.text((225, y + 64), alt, font=metni_sigdir(d, alt, "SemiBold", 33, W - 300), fill="white")
        y += 130
    ortala(d, y + 8, "Veriler: Meteoroloji Genel Müdürlüğü (MGM) · Karayolları", font("Regular", 26), (255, 255, 255, 200))
    destek_bandi(d, 56, H - 150, W - 56, H - 50)
    img.save(yol, quality=93)


def gorsel3(yol):
    img = sahne_ciz("gunesli", "tanitim3")
    d = ImageDraw.Draw(img, "RGBA")
    baslik_ust(d)
    ortala(d, 190, "Hiçbir uyarıyı", font("ExtraBold", 84))
    ortala(d, 290, "kaçırma!", font("ExtraBold", 84), SARI)
    adimlar = [("1", "Takip et", HESAP), ("2", "Zil simgesine dokun", "Profilin sağ üstündeki zil"),
               ("3", "Gönderiler ve Hikâyeler'i aç", "Uyarılar anında telefonuna gelsin"),
               ("4", "Sevdiklerinle paylaş", "Hava durumunu kimse kaçırmasın")]
    y = 460
    for no, ust, alt in adimlar:
        d.rounded_rectangle([90, y, W - 90, y + 140], radius=30, fill=(15, 30, 55, 140))
        d.ellipse([120, y + 30, 200, y + 110], fill=SARI)
        f = font("ExtraBold", 50)
        d.text((160 - d.textlength(no, font=f) / 2, y + 38), no, font=f, fill=LACI)
        d.text((230, y + 26), ust, font=metni_sigdir(d, ust, "ExtraBold", 42, W - 340), fill="white")
        d.text((230, y + 82), alt, font=font("Medium", 32), fill=(255, 255, 255, 215))
        y += 162
    ortala(d, H - 110, HESAP, font("ExtraBold", 56), "white")
    img.save(yol, quality=93)


def reels(k, sure=3.5):
    """Sabitlenecek tanıtım Reels'i: 3 görsel 9:16, hafif hareketli, yumuşak geçişli, müzikli (~10 sn)."""
    import datetime, glob, subprocess
    from reels_bot import dikey
    from hareket import hareketlendir
    parcalar_v = []
    for i, g in enumerate(sorted(glob.glob(os.path.join(k, "0*.jpg")))):
        dk = os.path.join(k, f"r{i}.jpg")
        dikey(g, dk)
        parcalar_v.append(hareketlendir(dk, ["yagmur", None, "kar"][i % 3], dk[:-4] + ".mp4", sure=3))
    girdi, fc, son = [], [], None
    for i, v in enumerate(parcalar_v):
        girdi += ["-stream_loop", "-1", "-t", str(sure), "-i", v]
        fc.append(f"[{i}:v]fps=30,setsar=1,format=yuv420p[v{i}]")
    son, t = "v0", sure
    for i in range(1, len(parcalar_v)):
        fc.append(f"[{son}][v{i}]xfade=transition=fade:duration=0.4:offset={t - 0.4}[x{i}]")
        son, t = f"x{i}", t + sure - 0.4
    muzik = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "muzik", "*.mp3")))
    komut = ["ffmpeg", "-y", "-loglevel", "error", *girdi]
    if muzik:
        komut += ["-ss", "15", "-i", muzik[datetime.date.today().toordinal() % len(muzik)]]
    komut += ["-filter_complex", ";".join(fc), "-map", f"[{son}]"]
    if muzik:
        komut += ["-map", f"{len(parcalar_v)}:a", "-af", f"afade=t=in:d=0.5,afade=t=out:st={t - 1}:d=1", "-c:a", "aac", "-b:a", "128k"]
    out = os.path.join(k, "reels.mp4")
    komut += ["-t", str(t), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    subprocess.run(komut, check=True)
    import shutil
    shutil.copy(os.path.join(k, "r0.jpg"), os.path.join(k, "reels_kapak.jpg"))
    for f in glob.glob(os.path.join(k, "r[0-9].*")):
        os.remove(f)
    if muzik:
        ad = os.path.basename(muzik[datetime.date.today().toordinal() % len(muzik)])[3:-4].split("-")[0]
        open(os.path.join(k, "muzik.txt"), "w").write({"alex": "Alex Morgan", "atlasaudio": "AtlasAudio", "nastelbom": "Nastelbom",
                                                         "velariomusic": "VelarioMusic", "andriig": "AndriiG"}.get(ad, ad))
    return out


if __name__ == "__main__":
    k = next((a for a in sys.argv[1:] if not a.startswith("--")), "yayin/tanitim")
    os.makedirs(k, exist_ok=True)
    gorsel1(os.path.join(k, "01_yorum_yaz.jpg"))
    gorsel2(os.path.join(k, "02_neler_var.jpg"))
    gorsel3(os.path.join(k, "03_takip_et.jpg"))
    open(os.path.join(k, "caption.txt"), "w", encoding="utf-8").write(
        "🌤 Senin ilinde hava nasıl?\n\n"
        "İlinin adını yorumlara yaz, Meteoroloji Genel Müdürlüğü (MGM) verisiyle hemen cevaplayalım! 💬\n"
        "İl, ilçe ya da gün yazabilirsin: \"İzmir 5 günlük\", \"Zara yarın\", \"Sivas cumartesi\"\n\n"
        "📍 Bu sayfada:\n"
        "☀️ Her sabah 07:17 – Bugün hava nasıl? (7 bölge, 81 il)\n"
        "🌙 Her akşam 20:13 – Yarının hava durumu\n"
        "📋 Her gün 17:00 – Yarın kar ve yağmur yağacak iller listesi\n"
        "📅 Her Cuma 17:47 – Hafta sonu hava durumu\n"
        "⚠️ MGM turuncu ve kırmızı kodlu uyarılar\n"
        "🚧 Kar, heyelan, sel nedeniyle kapalı yollar\n"
        "🔴 Son dakika hava haberleri (sel, kar, sis, fırtına)\n\n"
        "🔔 Takip edip bildirimleri açarak destek olun, hiçbir uyarıyı kaçırmayın!\n"
        "📤 Sevdiklerinle paylaş 👉 @bugun.hava.nasil\n\n"
        "#havadurumu #hava #meteoroloji #mgm #türkiye #havauyarısı #sondakika")
    if "--reels" in sys.argv:
        print("Reels:", reels(k))
    print("Tanıtım gönderisi hazır:", k)
