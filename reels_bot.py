#!/usr/bin/env python3
"""
Sabahki 7 bölge görselinden 9:16 Reels videosu üretir (ffmpeg).
- Açılış kartı + 7 bölge (her biri ~2.4 sn) + kapanış kartı, yumuşak geçişler
- Müzik: telif sorunu olmasın diye ffmpeg ile üretilen sakin bir ses (akor)

Kullanım: python reels_bot.py yayin/gunluk   -> yayin/gunluk/reels.mp4 + reels_kapak.jpg
"""
import glob, os, subprocess, sys, tempfile, datetime
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from hava_bot import font, destek_bandi, HESAP

W, H = 1080, 1920
SURE, GECIS = 2.6, 0.4


def dikey(src_yol, hedef):
    """1080x1350 görseli bulanık arka planlı 1080x1920 kareye yerleştirir."""
    src = Image.open(src_yol).convert("RGB")
    arka = src.resize((int(H * src.width / src.height), H)).crop((0, 0, W, H))
    arka = ImageEnhance.Brightness(arka.filter(ImageFilter.GaussianBlur(35))).enhance(0.5)
    arka.paste(src, (0, (H - src.height) // 2))
    d = ImageDraw.Draw(arka, "RGBA")
    d.text((W / 2 - d.textlength(HESAP, font=font("Bold", 40)) / 2, 180), HESAP, font=font("Bold", 40), fill=(255, 255, 255, 230))
    arka.save(hedef, quality=92)


def kart(hedef, ust, buyuk, alt, tarih, kapanis=False):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img, "RGBA")
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=(int(20 + 10 * k), int(70 - 30 * k), int(150 - 60 * k)))
    f_u, f_b, f_a = font("ExtraBold", 110), font("ExtraBold", 150), font("Bold", 56)
    y = 560
    for metin, f, renk in ((ust, f_u, (255, 205, 0)), (buyuk, f_b, (255, 255, 255)), (alt, f_a, (255, 255, 255))):
        for s in metin.split("\n"):
            d.text((W / 2 - d.textlength(s, font=f) / 2, y), s, font=f, fill=renk)
            y += f.size + 30
        y += 30
    f_t = font("Medium", 46)
    d.text((W / 2 - d.textlength(tarih, font=f_t) / 2, y + 20), tarih, font=f_t, fill=(255, 255, 255, 210))
    if kapanis:
        destek_bandi(d, 80, 1380, W - 80, 1560)
    d.text((W / 2 - d.textlength(HESAP, font=font("Bold", 44)) / 2, H - 200), HESAP, font=font("Bold", 44), fill="white")
    img.save(hedef, quality=92)


def main(klasor):
    bolgeler = sorted(g for g in glob.glob(os.path.join(klasor, "[0-9][0-9]_*.jpg")) if "_gonderi" not in g)
    if len(bolgeler) < 2:
        sys.exit("Bölge görseli yok")
    tmp = tempfile.mkdtemp()
    aylar = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    bugun = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date()
    tarih = f"{bugun.day} {aylar[bugun.month]} {bugun.year}"
    kareler = [os.path.join(tmp, "00.jpg")]
    kart(kareler[0], "BUGÜN", "HAVA\nNASIL?", "7 bölge · 81 il", tarih)
    for i, b in enumerate(bolgeler, 1):
        k = os.path.join(tmp, f"{i:02d}.jpg")
        dikey(b, k)
        kareler.append(k)
    son = os.path.join(tmp, "99.jpg")
    kart(son, "", "İYİ GÜNLER!", "Hava durumunu\nkaçırmamak için", "", kapanis=True)
    kareler.append(son)

    n = len(kareler)
    toplam = n * SURE - (n - 1) * GECIS
    girdiler, filtre = [], []
    for i, k in enumerate(kareler):
        girdiler += ["-loop", "1", "-t", str(SURE), "-i", k]
        # hafif yakınlaşma (Ken Burns)
        filtre.append(f"[{i}:v]scale=1188:2112,zoompan=z='min(zoom+0.0009,1.06)':d={int(SURE * 30)}:"
                      f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps=30,setsar=1,format=yuv420p[v{i}]")
    son_et = "v0"
    for i in range(1, n):
        ofset = i * (SURE - GECIS)
        filtre.append(f"[{son_et}][v{i}]xfade=transition=fade:duration={GECIS}:offset={ofset:.2f}[x{i}]")
        son_et = f"x{i}"
    # sakin akor müziği (C - Am - F - G), yumuşak giriş/çıkış
    akorlar = [(261.6, 329.6, 392.0), (220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7)]
    parca = toplam / 4
    ifade = "+".join(
        f"if(between(t,{j * parca:.2f},{(j + 1) * parca:.2f}),"
        + "+".join(f"0.06*sin(2*PI*{f}*t)+0.02*sin(2*PI*{f * 2}*t)" for f in a) + ",0)"
        for j, a in enumerate(akorlar))
    filtre.append(f"aevalsrc='{ifade}':s=44100:d={toplam:.2f},lowpass=f=1800,"
                  f"afade=t=in:d=1.2,afade=t=out:st={toplam - 1.8:.2f}:d=1.8,aformat=channel_layouts=stereo[a]")
    cikti = os.path.join(klasor, "reels.mp4")
    komut = ["ffmpeg", "-y", "-loglevel", "error", *girdiler, "-filter_complex", ";".join(filtre),
             "-map", f"[{son_et}]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
             "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart", "-t", f"{toplam:.2f}", cikti]
    subprocess.run(komut, check=True)
    Image.open(kareler[0]).save(os.path.join(klasor, "reels_kapak.jpg"), quality=90)
    print(f"Reels hazır: {cikti} ({toplam:.1f} sn, {os.path.getsize(cikti) // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "yayin/gunluk")
