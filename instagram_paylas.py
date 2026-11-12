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


def url(dosya):
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
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
    gorseller = sorted(glob.glob(os.path.join(klasor, "*.jpg")))[:10]
    if len(gorseller) < 2:
        sys.exit("Paylaşılacak görsel yok")
    cocuklar = [istek(f"{USER}/media", {"image_url": url(g), "is_carousel_item": "true"})["id"] for g in gorseller]
    for c in cocuklar:
        hazir_bekle(c)
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
    veri = {"media_type": "REELS", "video_url": url(video), "caption": caption, "share_to_feed": "true"}
    kapak = os.path.join(klasor, "reels_kapak.jpg")
    if os.path.exists(kapak):
        veri["cover_url"] = url(kapak)
    cid = istek(f"{USER}/media", veri)["id"]
    hazir_bekle(cid, deneme=60)  # video işleme birkaç dakika sürebilir
    if not yayinlama:
        return print("Reels testi: Instagram videoyu kabul etti ve işledi (yayınlanmadı)")
    print("Reels paylaşıldı:", istek(f"{USER}/media_publish", {"creation_id": cid})["id"])


def uyari(klasor):
    yol = os.path.join(klasor, "paylasim.json")
    if not os.path.exists(yol):
        return print("Yeni uyarı yok")
    for p in json.load(open(yol, encoding="utf-8")):
        if p.get("paylasildi"):
            continue
        hik = istek(f"{USER}/media", {"image_url": url(p["gorsel"]), "media_type": "STORIES"})["id"]
        print("Hikâye:", yayinla(hik))
        if "gonderi" in p["tur"]:
            g = istek(f"{USER}/media", {"image_url": url(p.get("gonderi_gorsel", p["gorsel"])), "caption": p["caption"]})["id"]
            print("Gönderi:", yayinla(g))


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
    elif komut == "uyari":
        uyari(sys.argv[2])
