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
import glob, json, os, subprocess, sys, time, urllib.parse, urllib.request

TOKEN = os.environ.get("IG_TOKEN", "").strip().strip('"').strip("'").strip()
USER = os.environ.get("IG_USER_ID", "").strip().strip('"').strip() or "me"
REPO = os.environ.get("GITHUB_REPOSITORY", "serdar5884/bugunhavanasil")
# "IGAA..." = Instagram girişli anahtar, "EAA..." = Facebook (sayfa/kullanıcı) anahtarı
API = "https://graph.facebook.com/v21.0" if TOKEN.startswith("EAA") else "https://graph.instagram.com/v21.0"


def istek(yol, veri=None, yontem="POST"):
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
    caption = open(os.path.join(klasor, "caption.txt"), encoding="utf-8").read() + " #reels #havadurumureels"
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


def uyari(klasor):
    """Uyarı / son dakika / yurt geneli kartları: hikâye hareketli video, gönderi hareketli Reels.
    Video hazırlanamaz ya da yüklenemezse eskisi gibi sabit görsel paylaşılır."""
    from hareket import hareketlendir, tur_bul
    yol = os.path.join(klasor, "paylasim.json")
    if not os.path.exists(yol):
        return print("Yeni uyarı yok")
    for p in json.load(open(yol, encoding="utf-8")):
        if p.get("paylasildi"):
            continue
        mp4 = None
        try:
            # efekt türü kaydın kendisinden (ör. KAR -> kar); yoksa başlık satırından tahmin
            tur = p["hareket"] if "hareket" in p else tur_bul(p.get("caption", "").split("\n")[0])
            mp4 = hareketlendir(p["gorsel"], tur)
        except Exception as e:
            print("Hareketli kart üretilemedi:", e)
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
        if "gonderi" in p["tur"]:
            g = None
            if mp4:
                try:
                    g = istek(f"{USER}/media", {"media_type": "REELS", "video_url": url(mp4), "cover_url": url(p["gorsel"]),
                                                "caption": p["caption"], "share_to_feed": "true"})["id"]
                    hazir_bekle(g, deneme=60)
                except Exception as e:
                    print("Hareketli gönderi yüklenemedi, sabit görsel:", e)
                    g = None
            if not g:
                g = istek(f"{USER}/media", {"image_url": url(p.get("gonderi_gorsel", p["gorsel"])), "caption": p["caption"]})["id"]
            print("Gönderi:", yayinla(g))


def ozel(gorsel_yolu, il, sadece=None):
    """İle özel görseli normal gönderi + (video varsa) Reels olarak paylaşır;
    ortaklar.json'da sayfa varsa ikisine de ortak gönderi (Collab) daveti gönderir."""
    caption = open(gorsel_yolu[:-4] + ".txt", encoding="utf-8").read()
    ortak = json.load(open("ortaklar.json", encoding="utf-8")).get(il, []) if os.path.exists("ortaklar.json") else []
    if sadece:  # elle tetiklemede sadece belirtilen sayfa(lar)a davet (ör. yeni ortak için ilk gönderi)
        ortak = [x.strip().lstrip("@") for x in sadece.split(",") if x.strip()]
    gonderi_cap = caption.split("\n\n🎵")[0]  # müzik satırı sadece Reels'te
    mp4 = gorsel_yolu[:-4] + ".mp4"
    if os.path.exists(mp4):  # ortak paylaşım sadece Reels (kaydırmalı gönderi yok)
        isler = [("Reels", {"media_type": "REELS", "video_url": url(mp4), "cover_url": url(gorsel_yolu[:-4] + "_kapak.jpg"),
                            "caption": caption + " #reels", "share_to_feed": "true"})]
    else:  # video üretilemediyse sabit görsel
        isler = [("Gönderi", {"image_url": url(gorsel_yolu), "caption": gonderi_cap})]
    for ad, veri in isler:
        try:
            if ortak:
                try:
                    cid = istek(f"{USER}/media", dict(veri, collaborators=json.dumps(ortak[:3])))["id"]
                    print(f"{ad}: ortak gönderi daveti ->", ", ".join(ortak))
                except RuntimeError as e:
                    print(f"{ad}: ortak gönderi kurulamadı, tek başına paylaşılıyor:", e)
                    cid = istek(f"{USER}/media", veri)["id"]
            else:
                cid = istek(f"{USER}/media", veri)["id"]
            hazir_bekle(cid, deneme=60)
            print(f"{il} {ad} paylaşıldı:", yayinla(cid))
        except Exception as e:
            print(f"{il} {ad} paylaşılamadı:", e)


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
