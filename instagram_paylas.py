#!/usr/bin/env python3
"""
Instagram'a otomatik paylaşım (Instagram API – Instagram ile giriş).
Gerekli GitHub Secrets:  IG_TOKEN (uzun ömürlü erişim anahtarı), IG_USER_ID (hesap kimliği)
Görseller herkese açık depodan (raw.githubusercontent.com) Instagram'a verilir.

Kullanım:
  python instagram_paylas.py karusel yayin/gunluk     -> klasördeki 7 bölge görselini tek gönderi (kaydırmalı) olarak paylaşır
  python instagram_paylas.py uyari yayin/uyari        -> paylasim.json'daki yeni uyarıları hikâye (+ önemliyse gönderi) olarak paylaşır
  python instagram_paylas.py kontrol                  -> anahtar çalışıyor mu, hesap adı ne
"""
import glob, json, os, subprocess, sys, time, urllib.parse, urllib.request

API = "https://graph.instagram.com/v21.0"
TOKEN = os.environ.get("IG_TOKEN", "")
USER = os.environ.get("IG_USER_ID", "me")
REPO = os.environ.get("GITHUB_REPOSITORY", "serdar5884/bugunhavanasil")


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


def hazir_bekle(cid):
    for _ in range(30):
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
    print("Gönderi paylaşıldı:", yayinla(kap))


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
            g = istek(f"{USER}/media", {"image_url": url(p["gorsel"]), "caption": p["caption"]})["id"]
            print("Gönderi:", yayinla(g))


if __name__ == "__main__":
    if not TOKEN:
        sys.exit("IG_TOKEN tanımlı değil – Instagram paylaşımı atlandı")
    komut = sys.argv[1] if len(sys.argv) > 1 else "kontrol"
    if komut == "kontrol":
        print(istek("me", {"fields": "user_id,username,account_type"}, "GET"))
    elif komut == "karusel":
        karusel(sys.argv[2])
    elif komut == "uyari":
        uyari(sys.argv[2])
