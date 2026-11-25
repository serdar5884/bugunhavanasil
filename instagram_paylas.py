#!/usr/bin/env python3
"""
Instagram'a otomatik paylaşım (Instagram API – Instagram ile giriş).
Gerekli GitHub Secrets:  IG_TOKEN (uzun ömürlü erişim anahtarı), IG_USER_ID (hesap kimliği)
Görseller herkese açık depodan (raw.githubusercontent.com) Instagram'a verilir.

Kullanım:
  python instagram_paylas.py karusel yayin/gunluk     -> klasördeki 7 bölge görselini tek gönderi (kaydırmalı) olarak paylaşır
  python instagram_paylas.py uyari yayin/uyari        -> paylasim.json'daki yeni uyarıları hikâye (+ önemliyse gönderi) olarak paylaşır
  python instagram_paylas.py reels yayin/gunluk        -> reels.mp4'i Reels olarak paylaşır
  python instagram_paylas.py kontrol                  -> anahtar çalışıyor mu, hesap adı ne
"""
import re, glob, json, os, subprocess, sys, time, urllib.parse, urllib.request

TOKEN = os.environ.get("IG_TOKEN", "").strip().strip('"').strip("'").strip()
USER = os.environ.get("IG_USER_ID", "").strip().strip('"').strip() or "me"
REPO = os.environ.get("GITHUB_REPOSITORY", "serdar5884/bugunhavanasil")
# "IGAA..." = Instagram girişli anahtar, "EAA..." = Facebook (sayfa/kullanıcı) anahtarı
API = "https://graph.facebook.com/v21.0" if TOKEN.startswith("EAA") else "https://graph.instagram.com/v21.0"


GENEL_ETIKET = {"#hava", "#meteoroloji", "#mgm", "#reels", "#havadurumureels", "#bugunhavanasil", "#türkiye"}
OLAY = re.compile(r"kar|yağ|yag|sel|çığ|fırtına|rüzgar|soğuk|sıcak|ayaz|don|sis|dolu|hortum|uyarı|sondakika|kapalı", re.I)


def etiket_sinirla(metin, n=5):
    """Instagram en fazla 5 hashtag'e izin veriyor: en ilgili 5'i kalır (havadurumu > olay > il > genel)."""
    etiketler = list(dict.fromkeys(re.findall(r"#[\wçğıöşüÇĞİÖŞÜ]+", metin)))
    if len(etiketler) <= n:
        return metin
    def puan(e):
        k = e.lower()
        return 0 if k == "#havadurumu" else 4 if k in GENEL_ETIKET else 2 if k.endswith("havadurumu") else 1 if OLAY.search(k) else 3
    kalan = set(sorted(etiketler, key=puan)[:n])
    metin = re.sub(r"#[\wçğıöşüÇĞİÖŞÜ]+", lambda m: m.group(0) if m.group(0) in kalan and not kalan.discard(m.group(0)) else "", metin)
    return re.sub(r"[ \t]{2,}", " ", re.sub(r"[ \t]+\n", "\n", metin))


def caption_duzenle(c, reels=False):
    """Tüm açıklamalar: paylaşma çağrısı en üstte (algoritmanın en güçlü sinyali), kısa takip satırı, en fazla 5 hashtag."""
    satirlar = c.split("\n")
    paylas = next((x for x in satirlar if x.startswith(("📤", "🔁"))), "")
    paylas = re.split(r",\s*takip", paylas)[0].rstrip(" .!") if paylas else ""
    if not paylas or "gönderiyi sevdiklerinle" in paylas:
        paylas = "📤 Ailene ve arkadaşlarına gönder, hazırlıklı olsunlar"
    paylas = "📤 " + paylas.lstrip("📤🔁 ").replace("Hemşehrilerinle paylaş", "Hemşehrilerine gönder") + "!"
    at = re.compile(r"^(📤|🔁)|bildirim|^👉 @bugun|^🔔")
    satirlar = [x for x in satirlar if not at.search(x) and not (reels and "kaydır" in x.lower())]
    takip = "🔔 Takipte kal 👉 @bugun.hava.nasil"
    k = next((i for i, x in enumerate(satirlar) if x.startswith(("Kaynak", "#"))), len(satirlar))
    satirlar[k:k] = ["", takip, ""]
    i = satirlar.index("", 1) if "" in satirlar[1:k] else 1
    satirlar[i:i] = ["", paylas, ""]
    c = re.sub(r"\n{3,}", "\n\n", "\n".join(satirlar)).strip()
    return etiket_sinirla(c)


def istek(yol, veri=None, yontem="POST"):
    if veri and veri.get("caption") and yontem == "POST":
        veri = dict(veri, caption=caption_duzenle(veri["caption"], reels=veri.get("media_type") == "REELS"))
    veri = dict(veri or {}, access_token=TOKEN)
    if yontem == "GET":
        req = urllib.request.Request(f"{API}/{yol}?{urllib.parse.urlencode(veri)}")
    else:
        req = urllib.request.Request(f"{API}/{yol}", data=urllib.parse.urlencode(veri).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Instagram hatası ({yol}): {e.read().decode(errors='replace')}")


_MEDYA_SHA = None


def medya_yukle():
    """Videolar ana dala girmesin (depo şişmesin): yayin/ altındaki tüm .mp4'ler tek commit'le 'medya' dalına
    zorla gönderilir; eski videolar geçmişte birikmez. Döner: commit kimliği."""
    global _MEDYA_SHA
    if _MEDYA_SHA:
        return _MEDYA_SHA
    import tempfile
    videolar = sorted(glob.glob("yayin/**/*.mp4", recursive=True))
    env = dict(os.environ, GIT_INDEX_FILE=os.path.join(tempfile.mkdtemp(), "index"))
    subprocess.run(["git", "add", "-f", *videolar], env=env, check=True)
    agac = subprocess.check_output(["git", "write-tree"], env=env, text=True).strip()
    sha = subprocess.check_output(["git", "-c", "user.name=hava-bot", "-c", "user.email=hava-bot@users.noreply.github.com",
                                   "commit-tree", agac, "-m", "medya"], text=True).strip()
    subprocess.run(["git", "push", "-q", "-f", "origin", f"{sha}:refs/heads/medya"], check=True)
    _MEDYA_SHA = sha
    print("Videolar medya dalına yüklendi:", len(videolar))
    return sha


def url(dosya):
    sha = medya_yukle() if dosya.endswith(".mp4") else subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    return f"https://raw.githubusercontent.com/{REPO}/{sha}/{urllib.parse.quote(dosya)}"


def hazir_bekle(cid, deneme=30):
    for _ in range(deneme):
        d = istek(cid, {"fields": "status_code"}, "GET")
        if d.get("status_code") == "FINISHED":
            return
        if d.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram görseli işleyemedi: {d}")
        time.sleep(4)
    raise RuntimeError("Instagram işleme zaman aşımı")


def yayinla(cid):
    hazir_bekle(cid)
    return istek(f"{USER}/media_publish", {"creation_id": cid})["id"]


def karusel(klasor):
    gorseller = sorted(g for g in glob.glob(os.path.join(klasor, "*.jpg")) if "kapak" not in os.path.basename(g))[:10]
    if len(gorseller) < 2:
        sys.exit("Paylaşılacak görsel yok")
    cocuklar = []
    for g in gorseller:
        mp4 = g[:-4] + ".mp4"
        cid = None
        if os.path.exists(mp4):  # hareketli kart (6 sn video)
            try:
                cid = istek(f"{USER}/media", {"media_type": "VIDEO", "video_url": url(mp4), "is_carousel_item": "true"})["id"]
                hazir_bekle(cid, deneme=60)
            except Exception as e:
                print("Hareketli kart yüklenemedi, sabit görsel kullanılıyor:", os.path.basename(g), e)
                cid = None
        if not cid:
            cid = istek(f"{USER}/media", {"image_url": url(g), "is_carousel_item": "true"})["id"]
        cocuklar.append(cid)
    for c in cocuklar:
        hazir_bekle(c, deneme=60)
    caption = open(os.path.join(klasor, "caption.txt"), encoding="utf-8").read()
    kap = istek(f"{USER}/media", {"media_type": "CAROUSEL", "children": ",".join(cocuklar), "caption": caption})["id"]
    mid = yayinla(kap)
    print("Gönderi paylaşıldı:", mid)
    return mid


def reels(klasor, yayinlama=True):
    video = os.path.join(klasor, "reels.mp4")
    if not os.path.exists(video):
        sys.exit("reels.mp4 yok")
    caption = open(os.path.join(klasor, "caption.txt"), encoding="utf-8").read()
    kc = os.path.join(klasor, "kanca.txt")
    if os.path.exists(kc) and open(kc, encoding="utf-8").read().strip():  # dikkat çeken ilk satır
        caption = open(kc, encoding="utf-8").read().strip() + "\n\n" + caption
    mz = os.path.join(klasor, "muzik.txt")
    if os.path.exists(mz):
        caption += f"\n\n🎵 Müzik: {open(mz, encoding='utf-8').read().strip()} (Pixabay)"
    veri = {"media_type": "REELS", "video_url": url(video), "caption": caption, "share_to_feed": "true"}
    kapak = os.path.join(klasor, "reels_kapak.jpg")
    if os.path.exists(kapak):
        veri["cover_url"] = url(kapak)
    cid = istek(f"{USER}/media", veri)["id"]
    hazir_bekle(cid, deneme=60)  # video işleme birkaç dakika sürebilir
    if not yayinlama:
        return print("Reels testi: Instagram videoyu kabul etti ve işledi (yayınlanmadı)")
    mid = istek(f"{USER}/media_publish", {"creation_id": cid})["id"]
    print("Reels paylaşıldı:", mid)
    return mid


AKIS_SINIRI = 3          # uyarı/haber/yurt geneli kartlarından günde en fazla bu kadarı akışa (Reels) düşer, gerisi sadece hikâye
SESSIZ = (23, 0), (6, 30)  # bu saatler arası paylaşım yok (kırmızı uyarı hikâyesi hariç); kartlar kuyrukta bekler
KUYRUK_OMRU = 14 * 3600    # saniye: bundan eski kartlar artık paylaşılmaz
UYARI_KLASORLERI = ("yayin/uyari", "yayin/ozel", "yayin/ulke")


def _simdi():
    import datetime
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))


def akis_sayisi():
    bugun = _simdi().date().isoformat()
    n = 0
    for k in UYARI_KLASORLERI:
        try:
            d = json.load(open(os.path.join(k, "akis.json"), encoding="utf-8"))
            n += d.get("n", 0) if d.get("tarih") == bugun else 0
        except Exception:
            pass
    return n


def akis_say(klasor):
    yol, bugun = os.path.join(klasor, "akis.json"), _simdi().date().isoformat()
    d = json.load(open(yol, encoding="utf-8")) if os.path.exists(yol) else {}
    d = d if d.get("tarih") == bugun else {"tarih": bugun, "n": 0}
    d["n"] += 1
    json.dump(d, open(yol, "w", encoding="utf-8"))


def uyari(klasor):
    """Uyarı / son dakika / yurt geneli kartları kuyruğa girer; her çalışmada kuyruk paylaşılır:
    hikâye hareketli müzikli video, akışa Reels (günde en fazla AKIS_SINIRI). Gece sessiz saatlerde beklenir,
    hata olursa sonraki çalışmada tekrar denenir (en fazla 3 kez)."""
    from hareket import hareketlendir, tur_bul, guvenli_alan
    kyol = os.path.join(klasor, "kuyruk.json")
    kuyruk = json.load(open(kyol, encoding="utf-8")) if os.path.exists(kyol) else []
    yol = os.path.join(klasor, "paylasim.json")
    simdi = _simdi()
    if os.path.exists(yol):
        mevcut = {p["gorsel"] for p in kuyruk}
        for p in json.load(open(yol, encoding="utf-8")):
            if p.get("paylasildi") or p["gorsel"] in mevcut:
                continue
            if "kapali_yollar" in p["gorsel"]:  # kapalı yollar: sadece en güncel liste beklesin
                kuyruk = [q for q in kuyruk if "kapali_yollar" not in q["gorsel"]]
            kuyruk.append(dict(p, eklendi=simdi.timestamp(), deneme=0))
    kuyruk = [p for p in kuyruk if simdi.timestamp() - p.get("eklendi", 0) < KUYRUK_OMRU and p.get("deneme", 0) < 3]

    def kaydet():
        json.dump(kuyruk, open(kyol, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    kaydet()
    if not kuyruk:
        return print("Bekleyen uyarı yok")
    sa = (simdi.hour, simdi.minute)
    gece = sa >= SESSIZ[0] or sa < SESSIZ[1]
    sayac = 0
    for p in list(kuyruk):
        kirmizi = "_red" in p["gorsel"] or "KIRMIZI" in p.get("caption", "").upper()
        if gece and not kirmizi:
            print("Sessiz saat, sabaha bekliyor:", os.path.basename(p["gorsel"]))
            continue
        reels_ister = p.get("tur") != "hikaye" and not p.get("reels_ok")
        if reels_ister and (gece or (akis_sayisi() >= AKIS_SINIRI and not kirmizi)):
            if gece:
                reels_ister = False  # kırmızı uyarı gece: şimdi hikâye, Reels sabah
            else:
                print("Günlük akış sınırı dolu, sadece hikâye:", os.path.basename(p["gorsel"]))
                p["reels_ok"] = "sinir"
                reels_ister = False
        if p.get("hikaye_ok") and not reels_ister:
            if not gece:
                kuyruk.remove(p)
            kaydet()
            continue
        p["deneme"] = p.get("deneme", 0) + 1
        kaydet()
        try:
            mp4 = None
            try:
                # efekt türü kaydın kendisinden (ör. KAR -> kar); yoksa başlık satırından tahmin
                tur = p["hareket"] if "hareket" in p else tur_bul(p.get("caption", "").split("\n")[0])
                mp4 = hareketlendir(p["gorsel"], tur)
                guvenli_alan(mp4)  # hikâye ve Reels tam ekranda kırpılmasın
            except Exception as e:
                print("Hareketli kart üretilemedi:", e)
                try:  # sade (yakınlaşan) video
                    mp4 = hareketlendir(p["gorsel"], None)
                    guvenli_alan(mp4)
                except Exception as e:
                    print("Video üretilemedi:", e)
                    mp4 = None
            caption = p["caption"]
            if mp4:  # sel, hortum, kapalı yol dahil tüm uyarı/haber videolarına müzik
                ilk = caption.split("\n")[0]
                ciddi = bool(re.search(r"SEL|HORTUM|FIRTINA|KAPAN|KAPALI|ÇIĞ|DOLU|TURUNCU|KIRMIZI|TAŞKIN|HEYELAN", ilk.upper()))
                yeni = muzik_degistir(mp4, sayac, ciddi)
                sayac += 1
                if yeni:
                    mp4 = yeni[0]
                    if "🎵" not in caption:
                        caption += f"\n\n🎵 Müzik: {yeni[1]} (Pixabay)"
            if not p.get("hikaye_ok"):
                hik = None
                if mp4:
                    try:
                        hik = istek(f"{USER}/media", {"video_url": url(mp4), "media_type": "STORIES"})["id"]
                        hazir_bekle(hik, deneme=60)
                    except Exception as e:
                        print("Hareketli hikâye yüklenemedi, sabit görsel:", e)
                        hik = None
                if not hik:
                    hik = istek(f"{USER}/media", {"image_url": url(p["gorsel"]), "media_type": "STORIES"})["id"]
                print("Hikâye:", yayinla(hik))
                p["hikaye_ok"] = True
                kaydet()
            if reels_ister:
                if not mp4:
                    raise RuntimeError("video yok, Reels sonra tekrar denenecek")
                g = istek(f"{USER}/media", {"media_type": "REELS", "video_url": url(mp4), "cover_url": url(p["gorsel"]),
                                            "caption": caption, "share_to_feed": "true"})["id"]
                hazir_bekle(g, deneme=60)
                print("Reels:", yayinla(g))
                p["reels_ok"] = True
                akis_say(klasor)
            if not (gece and p.get("tur") != "hikaye" and not p.get("reels_ok")):
                kuyruk.remove(p)
        except Exception as e:
            print("Paylaşılamadı, sonraki çalışmada tekrar denenecek:", os.path.basename(p["gorsel"]), e)
        kaydet()


def ozel(gorsel_yolu, il, sadece=None):
    """İle özel Reels'i ortak sayfalarla Collab olarak paylaşır. Her ortak sayfaya AYRI ve FARKLI içerik
    (bugün / yarın / sonraki günler; liste.txt) gider: ortaklar birbirini görmez, Instagram kopya saymaz.
    Bizim ızgarada yalnız 'bugün' Reels'i görünür; diğerleri sadece Reels sekmesinde. 10 dk arayla, farklı müzikle."""
    import datetime, time
    ortak = json.load(open("ortaklar.json", encoding="utf-8")).get(il, []) if os.path.exists("ortaklar.json") else []
    if sadece:  # elle tetiklemede sadece belirtilen sayfa(lar)a davet (ör. yeni ortak için ilk gönderi)
        ortak = [x.strip().lstrip("@") for x in sadece.split(",") if x.strip()]
    lst = os.path.join(os.path.dirname(gorsel_yolu), "liste.txt")
    varyantlar = [x for x in open(lst).read().split() if os.path.exists(x)] if os.path.exists(lst) else []
    if gorsel_yolu not in varyantlar:
        varyantlar = [gorsel_yolu] + varyantlar
    varyantlar = [v for v in varyantlar if os.path.exists(v[:-4] + ".mp4")]
    if not varyantlar:
        return print(f"{il}: video yok, paylaşılmadı")
    n = max(1, len(ortak))
    kay = 0  # her sayfanın tasarımı sabit: ortaklar.json'daki sırası = tasarım (1. sayfa klasik, 2. gökyüzü...)
    for k in range(n):
        grup = [ortak[(k + kay) % n]] if ortak else []
        g = varyantlar[k % len(varyantlar)]
        mp4 = g[:-4] + ".mp4"
        caption = open(g[:-4] + ".txt", encoding="utf-8").read()
        v = {"media_type": "REELS", "video_url": url(mp4), "cover_url": url(g[:-4] + "_kapak.jpg"), "caption": caption,
             "share_to_feed": "true" if k == 0 else "false"}
        if k:
            time.sleep(600)
            yeni = muzik_degistir(mp4, k)
            if yeni:
                v["video_url"], sanatci = url(yeni[0]), yeni[1]
                v["caption"] = re.sub(r"🎵 Müzik: .*\(Pixabay\)", f"🎵 Müzik: {sanatci} (Pixabay)", v["caption"])
        try:
            if grup:
                try:
                    cid = istek(f"{USER}/media", dict(v, collaborators=json.dumps(grup)))["id"]
                except RuntimeError as e:  # tek başına kopya paylaşmamak için bu sayfayı atla
                    print(f"Reels: @{grup[0]} için ortak gönderi kurulamadı, atlandı:", e)
                    continue
            else:
                cid = istek(f"{USER}/media", v)["id"]
            hazir_bekle(cid, deneme=60)
            print(f"{il} Reels ({os.path.basename(g)}) paylaşıldı" + (f" (ortak: @{grup[0]})" if grup else "") + ":", yayinla(cid))
        except Exception as e:
            print(f"{il} Reels paylaşılamadı" + (f" (@{grup[0]})" if grup else "") + ":", e)


def muzik_degistir(mp4, k, ciddi=False):
    """Aynı videonun farklı müzikli kopyası (k. ortak / k. uyarı için). Döner: (yol, sanatçı) ya da None.
    ciddi=True (sel, hortum, kapalı yol...): neşeli ("happy/cheerful") parçalar kullanılmaz."""
    parcalar = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "muzik", "*.mp3")))
    if ciddi:
        parcalar = [p for p in parcalar if not re.search(r"happy|cheerful", os.path.basename(p))] or parcalar
    if not parcalar:
        return None
    import datetime
    parca = parcalar[(datetime.date.today().toordinal() + 5 + k * 3) % len(parcalar)]
    out = mp4[:-4] + f"_m{k}.mp4"
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-ss", "8", "-i", parca, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-af", "afade=t=in:d=0.8", "-shortest",
                        "-movflags", "+faststart", out], check=True)
    except Exception as e:
        print("Müzik değiştirilemedi:", e)
        return None
    global _MEDYA_SHA
    _MEDYA_SHA = None  # yeni dosya medya dalına yüklensin
    ad = os.path.basename(parca)[3:-4].split("-")[0]
    return out, {"alex": "Alex Morgan", "atlasaudio": "AtlasAudio", "nastelbom": "Nastelbom",
                 "velariomusic": "VelarioMusic", "andriig": "AndriiG"}.get(ad, ad)


if __name__ == "__main__":
    if not TOKEN:
        sys.exit("IG_TOKEN tanımlı değil – Instagram paylaşımı atlandı")
    komut = sys.argv[1] if len(sys.argv) > 1 else "kontrol"
    if komut == "kontrol":
        print(f"Anahtar uzunluğu: {len(TOKEN)} karakter, başlangıcı: {TOKEN[:4]}… ; kullanıcı no uzunluğu: {len(USER)}")
        if API.startswith("https://graph.facebook"):
            print(istek(USER, {"fields": "id,username,followers_count"}, "GET"))
        else:
            print(istek("me", {"fields": "user_id,username,account_type"}, "GET"))
    elif komut == "karusel":
        karusel(sys.argv[2])
    elif komut == "reels":
        reels(sys.argv[2])
    elif komut == "reels-test":
        reels(sys.argv[2], yayinlama=False)
    elif komut == "hikaye":
        h = istek(f"{USER}/media", {"image_url": url(sys.argv[2]), "media_type": "STORIES"})["id"]
        hazir_bekle(h)
        print("Hikâye:", yayinla(h))
    elif komut == "ozel":
        ozel(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif komut == "uyari":
        uyari(sys.argv[2])
