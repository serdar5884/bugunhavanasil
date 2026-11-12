#!/usr/bin/env python3
"""
Kendi gönderilerimize gelen yorumlara MGM verisiyle otomatik cevap.
Örnek: "Sivas yarın kar var mı?" -> "@kullanici Sivas – yarın (13 Kasım): Hafif Kar Yağışlı, en yüksek 2°, en düşük -5°."

Sadece kendi hesabımızın gönderilerindeki yorumlara cevap verir (Instagram kurallarına uygun).
Bir yoruma bir kez cevap verilir; il adı geçmeyen yorumlar atlanır.

Kullanım: python yorum_bot.py           (IG_TOKEN, IG_USER_ID gerekli)
          python yorum_bot.py --dene "sivas yarın nasıl"   (cevap metnini test eder, paylaşmaz)
"""
import argparse, datetime, json, os, re, sys
from hava_bot import BOLGELER, HADISE, mgm_get, merkezleri_yukle
import instagram_paylas as ig

DURUM = "yorum_durum.json"  # uyarı botuyla çakışmasın diye ayrı dosya
SON_GONDERI = 6   # 5 dakikada bir çalıştığı için API sınırını aşmamak adına son 6 gönderi        # son kaç gönderinin yorumlarına bakılsın
TUR_BASINA_EN_FAZLA = 25
TR = datetime.timezone(datetime.timedelta(hours=3))
AYLAR = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
ILLER = [il for v in BOLGELER.values() for il in v]


def sade(m):
    return m.lower().translate(str.maketrans("çğıöşüâîû", "cgiosuaiu")).replace("i̇", "i")


SADE_IL = {sade(il.replace("İ", "i").replace("I", "ı")): il for il in ILLER}
SADE_IL.update({"antep": "Gaziantep", "urfa": "Şanlıurfa", "maras": "Kahramanmaraş", "afyon": "Afyonkarahisar",
                "izmit": "Kocaeli", "adapazari": "Sakarya", "icel": "Mersin", "istanbul": "İstanbul"})


def illeri_bul(metin):
    s = sade(metin)
    bulunan = []
    for ad, il in sorted(SADE_IL.items(), key=lambda x: -len(x[0])):
        ek = r"(?:'?(?:da|de|ta|te|ya|ye|a|e|in|un|nin|nun|dan|den|tan|ten|li|lu|lar|ler|daki|deki))?"
        if re.search(rf"(?<![a-z]){ad}{ek}(?![a-z])", s) and il not in bulunan:
            bulunan.append(il)
    return bulunan[:3]


def tahmin(il, tarih):
    t = mgm_get(f"/tahminler/gunluk?istno={merkezleri_yukle()[il]}")
    t = t[0] if isinstance(t, list) else t
    for i in range(1, 6):
        if str(t.get(f"tarihGun{i}", ""))[:10] == tarih.isoformat():
            return (HADISE.get(t.get(f"hadiseGun{i}"), (t.get(f"hadiseGun{i}"), ""))[0],
                    t.get(f"enYuksekGun{i}"), t.get(f"enDusukGun{i}"))
    return None


def cevap_metni(yorum, kullanici):
    iller = illeri_bul(yorum)
    if not iller:
        return None
    s = sade(yorum)
    bugun = datetime.datetime.now(TR).date()
    if "yarin" in s:
        gunler = [(bugun + datetime.timedelta(days=1), "yarın")]
    elif "hafta sonu" in s or "haftasonu" in s:
        cmt = bugun + datetime.timedelta(days=(5 - bugun.weekday()) % 7)
        gunler = [(cmt, "Cumartesi"), (cmt + datetime.timedelta(days=1), "Pazar")]
    else:
        gunler = [(bugun, "bugün")]
    satirlar = []
    for il in iller:
        parcalar = []
        for tarih, ad in gunler:
            v = tahmin(il, tarih)
            if v is None and ad == "bugün":  # öğleden sonra MGM bugünü kaldırıyor -> yarını ver
                tarih, ad = bugun + datetime.timedelta(days=1), "yarın"
                v = tahmin(il, tarih)
            if v:
                parcalar.append(f"{ad} ({tarih.day} {AYLAR[tarih.month]}): {v[0]}, en yüksek {v[1]}°, en düşük {v[2]}°")
        if parcalar:
            satirlar.append(f"{il} – " + " | ".join(parcalar))
    if not satirlar:
        return None
    return f"@{kullanici} " + " / ".join(satirlar) + " 🌤 Kaynak: MGM"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dene")
    a = ap.parse_args()
    if a.dene:
        print(cevap_metni(a.dene, "deneme"))
        return
    if not ig.TOKEN:
        sys.exit("IG_TOKEN yok – yorum cevaplama atlandı")
    durum = json.load(open(DURUM, encoding="utf-8")) if os.path.exists(DURUM) else {}
    cevaplanan = set(durum.get("cevaplanan_yorumlar", []))
    hesap = ig.istek(ig.USER, {"fields": "username"}, "GET").get("username", "")
    medya = ig.istek(f"{ig.USER}/media", {"fields": "id", "limit": SON_GONDERI}, "GET").get("data", [])
    yeni = 0
    for m in medya:
        yorumlar = ig.istek(f"{m['id']}/comments", {"fields": "id,text,username,timestamp", "limit": 50}, "GET").get("data", [])
        for y in yorumlar:
            if y["id"] in cevaplanan or y.get("username") == hesap:
                continue
            cevaplanan.add(y["id"])
            try:
                metin = cevap_metni(y.get("text", ""), y.get("username", ""))
            except Exception as e:
                print("Tahmin alınamadı:", e)
                continue
            if not metin:
                continue
            ig.istek(f"{y['id']}/replies", {"message": metin[:2000]})
            print("Cevaplandı:", y.get("username"), "|", y.get("text", "")[:60], "->", metin[:90])
            yeni += 1
            if yeni >= TUR_BASINA_EN_FAZLA:
                break
    durum["cevaplanan_yorumlar"] = list(cevaplanan)[-5000:]
    json.dump(durum, open(DURUM, "w", encoding="utf-8"), ensure_ascii=False)
    print(yeni, "yoruma cevap verildi")


if __name__ == "__main__":
    main()
