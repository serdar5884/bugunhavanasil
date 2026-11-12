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
    y = balon(d, 90, 560, 760, "sen", "Sivas yarın nasıl?", f, (255, 255, 255, 235), LACI)
    y = balon(d, 250, y + 26, 990, HESAP, "Sivas – yarın: Puslu, en yüksek 16°, en düşük 3° · Kaynak: MGM", f, (25, 45, 85, 230), (255, 255, 255))
    ortala(d, y + 36, "Örnekler:  \"İzmir bugün\"  ·  \"Erzurum yarın\"  ·  \"Antalya hafta sonu\"", font("SemiBold", 30), (255, 255, 255, 230))
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
        ("bulut", "Her Cuma 17:47", "Hafta sonu hava durumu"),
        ("firtina", "Anında", "MGM sarı, turuncu, kırmızı uyarılar"),
        ("kar", "Anında", "Kar, heyelan, sel nedeniyle kapalı yollar"),
        ("yagmur", "Son dakika", "Sel, çığ, fırtına gibi hava haberleri"),
    ]
    y = 270
    for tip, ust, alt in maddeler:
        d.rounded_rectangle([70, y, W - 70, y + 128], radius=28, fill=(15, 30, 55, 120), outline=(255, 255, 255, 70), width=2)
        ikon(d, tip, 150, y + 64, 92)
        d.text((225, y + 20), ust, font=font("ExtraBold", 40), fill=SARI)
        d.text((225, y + 72), alt, font=metni_sigdir(d, alt, "SemiBold", 34, W - 300), fill="white")
        y += 146
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


if __name__ == "__main__":
    k = sys.argv[1] if len(sys.argv) > 1 else "yayin/tanitim"
    os.makedirs(k, exist_ok=True)
    gorsel1(os.path.join(k, "01_yorum_yaz.jpg"))
    gorsel2(os.path.join(k, "02_neler_var.jpg"))
    gorsel3(os.path.join(k, "03_takip_et.jpg"))
    open(os.path.join(k, "caption.txt"), "w", encoding="utf-8").write(
        "🌤 Senin ilinde hava nasıl?\n\n"
        "İlinin adını yorumlara yaz, Meteoroloji Genel Müdürlüğü (MGM) verisiyle hemen cevaplayalım! 💬\n"
        "Örnek: \"Sivas yarın\", \"İzmir bugün\", \"Antalya hafta sonu\"\n\n"
        "📍 Bu sayfada:\n"
        "☀️ Her sabah 07:17 – Bugün hava nasıl? (7 bölge, 81 il)\n"
        "🌙 Her akşam 20:13 – Yarının hava durumu\n"
        "📅 Her Cuma 17:47 – Hafta sonu hava durumu\n"
        "⚠️ MGM sarı, turuncu ve kırmızı kodlu uyarılar\n"
        "🚧 Kar, heyelan, sel nedeniyle kapalı yollar\n"
        "🔴 Son dakika hava haberleri\n\n"
        "🔔 Takip edip bildirimleri açarak destek olun, hiçbir uyarıyı kaçırmayın!\n"
        "📤 Sevdiklerinle paylaş 👉 @bugun.hava.nasil\n\n"
        "#havadurumu #hava #meteoroloji #mgm #türkiye #havauyarısı #sondakika")
    print("Tanıtım gönderisi hazır:", k)
