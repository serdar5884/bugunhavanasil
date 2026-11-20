#!/usr/bin/env python3
"""
Sabahki 7 bölge görselinden 9:16 Reels videosu üretir (ffmpeg).
- Açılış kartı + 7 bölge (her biri ~2.4 sn) + kapanış kartı, yumuşak geçişler
- Müzik: telif sorunu olmasın diye ffmpeg ile üretilen sakin bir ses (akor)

Kullanım: python reels_bot.py yayin/gunluk   -> yayin/gunluk/reels.mp4 + reels_kapak.jpg
"""
import glob, json, os, subprocess, sys, tempfile, datetime
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from hava_bot import font, destek_bandi, HESAP, HADISE

W, H = 1080, 1920
ACILIS, BOLGE, KAPANIS, GECIS = 2.5, 6.0, 3.5, 0.5  # saniye: bölge görselleri okunabilsin diye uzun


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
            while d.textlength(s, font=f) > W - 90 and f.size > 60:  # uzun satır taşmasın
                f = font("ExtraBold", f.size - 6)
            d.text((W / 2 - d.textlength(s, font=f) / 2, y), s, font=f, fill=renk)
            y += f.size + 30
        y += 30
    f_t = font("Medium", 46)
    d.text((W / 2 - d.textlength(tarih, font=f_t) / 2, y + 20), tarih, font=f_t, fill=(255, 255, 255, 210))
    if kapanis:
        destek_bandi(d, 80, 1380, W - 80, 1560)
    d.text((W / 2 - d.textlength(HESAP, font=font("Bold", 44)) / 2, H - 200), HESAP, font=font("Bold", 44), fill="white")
    img.save(hedef, quality=92)


def kanca(klasor):
    """Reels açılışı için dikkat çeken başlık: ('YARIN', '12 İLDE\nKAR VAR!', alt yazı, caption satırı, tarih)"""
    aylar = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    oz_yol, veri_yol = os.path.join(klasor, "ozet.json"), os.path.join(klasor, "veri.json")
    oz = json.load(open(oz_yol)) if os.path.exists(oz_yol) else {}
    gun = oz.get("gun", 1)
    t = datetime.date.fromisoformat(oz["tarih"]) if oz.get("tarih") else \
        datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date()
    ust = {1: "BUGÜN", 2: "YARIN", "hs": "HAFTA SONU"}.get(gun, "BUGÜN")
    if gun == "hs":
        p = t + datetime.timedelta(days=1)
        tarih = f"{t.day}-{p.day} {aylar[p.month]} {p.year}" if t.month == p.month else f"{t.day} {aylar[t.month]} - {p.day} {aylar[p.month]}"
    else:
        tarih = f"{t.day} {aylar[t.month]} {t.year}"
    tipler = {"kar": set(), "firtina": set(), "yagmur": set()}
    sicak, soguk = [], []
    if os.path.exists(veri_yol):
        for vs in json.load(open(veri_yol, encoding="utf-8")).values():
            for v in vs:
                for x in (v, v.get("paz")):
                    if not x or not x.get("hadise"):
                        continue
                    tip = HADISE.get(x["hadise"], ("", ""))[1]
                    tip = "kar" if tip == "karla_yagmur" else tip
                    if tip in tipler:
                        tipler[tip].add(v["il"])
                    if x.get("max") is not None:
                        sicak.append((x["max"], v["il"]))
                    if x.get("min") is not None:
                        soguk.append((x["min"], v["il"]))
    kim = {1: "Bugün", 2: "Yarın", "hs": "Hafta sonu"}.get(gun, "Bugün")
    n_kar, n_fir, n_yag = len(tipler["kar"]), len(tipler["firtina"]), len(tipler["yagmur"])
    if n_kar >= 3:
        return ust, f"{n_kar} İLDE\nKAR VAR!", "Senin ilin\nlistede mi?", f"❄️ {kim} {n_kar} ilde kar yağışı var! Senin ilin listede mi?", tarih
    if n_fir >= 3:
        return ust, f"{n_fir} İLDE\nFIRTINA!", "Gök gürültülü sağanak\nbekleniyor", f"⛈️ {kim} {n_fir} ilde gök gürültülü sağanak bekleniyor!", tarih
    if n_yag + n_fir >= 10:
        n = n_yag + n_fir
        return ust, f"{n} İLDE\nYAĞMUR VAR!", "Şemsiyeni\nunutma!", f"☔ {kim} {n} ilde yağmur var! Şemsiyeni unutma.", tarih
    if soguk and min(soguk)[0] <= -5:
        d, il = min(soguk)
        return ust, f"{il.upper()}\n{d}°C!", "Türkiye'nin\nen soğuk ili", f"🥶 {kim} en soğuk il {il}: {d}°C! Senin ilinde hava nasıl?", tarih
    if sicak and max(sicak)[0] >= 33:
        d, il = max(sicak)
        return ust, f"{il.upper()}\n{d}°C!", "Türkiye'nin\nen sıcak ili", f"🔥 {kim} en sıcak il {il}: {d}°C! Senin ilinde hava nasıl?", tarih
    return ust, "HAVA\nNASIL?", "7 bölge · 81 il", None, tarih


def main(klasor):
    bolgeler = sorted(g for g in glob.glob(os.path.join(klasor, "[0-9][0-9]_*.jpg")) if "_gonderi" not in g)
    if len(bolgeler) < 2:
        sys.exit("Bölge görseli yok")
    tmp = tempfile.mkdtemp()
    aylar = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    bugun = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date()
    tarih = f"{bugun.day} {aylar[bugun.month]} {bugun.year}"
    kareler = [os.path.join(tmp, "00.jpg")]
    ust, buyuk, alt, satir, tarih = kanca(klasor)
    kart(kareler[0], ust, buyuk, alt, tarih)
    open(os.path.join(klasor, "kanca.txt"), "w", encoding="utf-8").write(satir or "")
    for i, b in enumerate(bolgeler, 1):
        k = os.path.join(tmp, f"{i:02d}.jpg")
        dikey(b, k)
        kareler.append(k)
    son = os.path.join(tmp, "99.jpg")
    kart(son, "", "İYİ GÜNLER!", "Hava durumunu\nkaçırmamak için", "", kapanis=True)
    kareler.append(son)

    n = len(kareler)
    sureler = [ACILIS] + [BOLGE] * (n - 2) + [KAPANIS]
    toplam = sum(sureler) - (n - 1) * GECIS
    girdiler, filtre = [], []
    gi = 0  # ffmpeg girdi sırası
    for i, k in enumerate(kareler):
        SURE = sureler[i]
        girdiler += ["-loop", "1", "-t", str(SURE), "-i", k]
        hareketli = bolgeler[i - 1][:-4] + ".mp4" if 0 < i <= len(bolgeler) else None
        if hareketli and os.path.exists(hareketli):
            # hareketli bölge kartı (yağmur/kar/bulut akar), bulanık arka planın ortasına
            girdiler += ["-stream_loop", "-1", "-t", str(SURE), "-i", hareketli]
            filtre.append(f"[{gi}:v]fps=30,setsar=1[a{i}];[{gi + 1}:v]fps=30,setsar=1[h{i}];"
                          f"[a{i}][h{i}]overlay=0:{(H - 1350) // 2}:shortest=1,trim=duration={SURE},setpts=PTS-STARTPTS,"
                          f"format=yuv420p[v{i}]")
            gi += 2
            continue
        # çok hafif yakınlaşma (bölgelerde daha yavaş, yazı rahat okunsun)
        hiz = 0.0009 if i == 0 else 0.0003
        filtre.append(f"[{gi}:v]scale=1188:2112,zoompan=z='min(zoom+{hiz},1.06)':d={int(SURE * 30)}:"
                      f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps=30,setsar=1,format=yuv420p[v{i}]")
        gi += 1
    son_et = "v0"
    ofset = 0.0
    for i in range(1, n):
        ofset += sureler[i - 1] - GECIS
        filtre.append(f"[{son_et}][v{i}]xfade=transition=fade:duration={GECIS}:offset={ofset:.2f}[x{i}]")
        son_et = f"x{i}"
    # Müzik: muzik/ klasöründeki parçalar her gün sırayla kullanılır (Pixabay lisansı); yoksa üretilen sakin akor
    parcalar = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "muzik", "*.mp3")))
    if parcalar:
        parca = parcalar[bugun.toordinal() % len(parcalar)]
        girdiler += ["-stream_loop", "-1", "-i", parca]
        filtre.append(f"[{gi}:a]atrim=0:{toplam:.2f},asetpts=PTS-STARTPTS,volume=0.85,afade=t=in:d=0.8,"
                      f"afade=t=out:st={toplam - 2.5:.2f}:d=2.5,aformat=channel_layouts=stereo[a]")
        dosya = os.path.basename(parca)[3:-4]
        sanatci = next((ad for on, ad in (("alex-morgan", "Alex Morgan"), ("atlasaudio", "AtlasAudio"), ("nastelbom", "Nastelbom"),
                                          ("velariomusic", "VelarioMusic"), ("andriig", "AndriiG")) if dosya.startswith(on)),
                       dosya.split("-")[0])
        open(os.path.join(klasor, "muzik.txt"), "w", encoding="utf-8").write(sanatci)
        print("Müzik:", os.path.basename(parca))
    else:
        akorlar = [(261.6, 329.6, 392.0), (220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7)]
        parca_s = toplam / 4
        ifade = "+".join(
            f"if(between(t,{j * parca_s:.2f},{(j + 1) * parca_s:.2f}),"
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
