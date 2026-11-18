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
SON_GONDERI = 10  # dakikada bir çalıştığı için API sınırını aşmamak adına son 6 gönderi        # son kaç gönderinin yorumlarına bakılsın
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
    # yorumda geçtiği sıraya göre
    sirali = sorted(bulunan, key=lambda il: min([m.start() for ad, x in SADE_IL.items() if x == il for m in re.finditer(ad, s)] or [999]))
    return sirali[:3]


ILCE_DOSYA = "ilceler.json"
HARIC = ("havaliman", "kayak", "merkezi", "baraj", "liman", "istasyon", "üniversite", "tesis", "dağı", "gölü", "geçidi")
# günlük dilde başka anlamı olan ilçe adları: ancak il adı da yazılmışsa ilçe sayılır
GENEL_KELIME = {"pazar", "cay", "kale", "bor", "saray", "kas", "merkez", "guney", "kemer", "bahce", "hani", "tut", "cal",
                "can", "sur", "kartal", "fatih", "selim", "selcuk", "ulas", "kiraz", "mut", "bayat", "cat", "bucak", "ulus",
                "of", "susuz", "hacilar", "karasu", "konak", "golbasi", "aksu", "ortakoy", "yenice", "kocaali", "esenler",
                "ova"}
EK = r"(?:'?(?:da|de|ta|te|ya|ye|a|e|in|un|ın|nin|nun|dan|den|tan|ten|li|lu|lar|ler|daki|deki|ilcesi|ilcesinde))?"
_ILCE = {}


def ilceleri_yukle():
    """{il: {ilçe: istasyon no}} – ilk çalışmada MGM'den çekilip ilceler.json'a kaydedilir."""
    if _ILCE:
        return _ILCE
    if os.path.exists(ILCE_DOSYA):
        _ILCE.update(json.load(open(ILCE_DOSYA, encoding="utf-8")))
        return _ILCE
    import urllib.parse
    from concurrent.futures import ThreadPoolExecutor

    def al(il):
        try:
            lst = mgm_get("/merkezler/ililcesi?il=" + urllib.parse.quote(il))
            return il, {x["ilce"]: x["gunlukTahminIstNo"] for x in lst if x.get("ilce") and x.get("gunlukTahminIstNo")
                        and x["ilce"] not in (il, "Merkez") and not any(h in x["ilce"].lower() for h in HARIC)}
        except Exception as e:
            print("İlçe listesi alınamadı:", il, e)
            return il, None
    with ThreadPoolExecutor(max_workers=8) as ex:
        sonuc = dict(ex.map(al, ILLER))
    _ILCE.update({k: v for k, v in sonuc.items() if v})
    if all(sonuc.values()):  # eksiksizse kalıcı kaydet
        json.dump(_ILCE, open(ILCE_DOSYA, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return _ILCE


def hedefleri_bul(metin):
    """Yorumdaki il/ilçeleri bulur: [(etiket, istasyon no), ...] (yorumdaki sıraya göre, en fazla 3)"""
    s = sade(metin)
    iller = illeri_bul(metin)
    merkez = merkezleri_yukle()
    bulunan = []  # (konum, etiket, istno, il)
    for il, ilceler in ilceleri_yukle().items():
        for ilce, istno in ilceler.items():
            ad = sade(ilce.replace("İ", "i").replace("I", "ı"))
            m = re.search(rf"(?<![a-z]){re.escape(ad)}{EK}(?![a-z])", s)
            if not m or (ad in GENEL_KELIME and il not in iller):
                continue
            bulunan.append((m.start(), f"{ilce} ({il})", istno, il))
    # aynı ilçe adı birden çok ilde varsa ve il yazılmışsa sadece o il
    if bulunan:
        ad_say = {}
        for b in bulunan:
            ad_say.setdefault(b[1].split(" (")[0], []).append(b)
        bulunan = []
        for adaylar in ad_say.values():
            secili = [b for b in adaylar if b[3] in iller] or adaylar[:2]
            bulunan += secili
    ilce_illeri = {b[3] for b in bulunan}
    for il in iller:
        if il not in ilce_illeri and il in merkez:  # ilçesi sorulan ilin merkezini ayrıca verme
            konum = min([m.start() for ad, x in SADE_IL.items() if x == il for m in re.finditer(ad, s)] or [999])
            bulunan.append((konum, il, merkez[il], il))
    return [(b[1], b[2]) for b in sorted(bulunan)][:3]


def tahmin(istno, tarih):
    t = mgm_get(f"/tahminler/gunluk?istno={istno}")
    t = t[0] if isinstance(t, list) else t
    for i in range(1, 6):
        if str(t.get(f"tarihGun{i}", ""))[:10] == tarih.isoformat():
            return (HADISE.get(t.get(f"hadiseGun{i}"), (t.get(f"hadiseGun{i}"), ""))[0],
                    t.get(f"enYuksekGun{i}"), t.get(f"enDusukGun{i}"), t.get(f"ruzgarHizGun{i}"))
    return None


GUN_KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
SIMGE = {"gunes": "☀️", "az_bulut": "🌤️", "bulut": "☁️", "yagmur": "🌧️", "firtina": "⛈️", "kar": "❄️", "karla_yagmur": "🌨️", "sis": "🌫️"}


def simge(hadise_metni):
    tip = next((v[1] for v in HADISE.values() if v[0] == hadise_metni), "bulut")
    return SIMGE.get(tip, "🌡️")
COK_GUN = r"(5|bes|7|yedi)\s*gun|haftalik|bir hafta|1 hafta|bu hafta|hafta boyu|onumuzdeki gunler|gunluk tahmin|uzun vade"


def tahmin_cok(istno):
    """MGM'nin 5 günlük tahmini: [(tarih, hadise metni, max, min, rüzgar), ...]"""
    t = mgm_get(f"/tahminler/gunluk?istno={istno}")
    t = t[0] if isinstance(t, list) else t
    bugun = datetime.datetime.now(TR).date()
    out = []
    for i in range(1, 6):
        ts = str(t.get(f"tarihGun{i}", ""))[:10]
        if not ts:
            continue
        tarih = datetime.date.fromisoformat(ts)
        if tarih < bugun:
            continue
        out.append((tarih, HADISE.get(t.get(f"hadiseGun{i}"), (t.get(f"hadiseGun{i}"), ""))[0],
                    t.get(f"enYuksekGun{i}"), t.get(f"enDusukGun{i}"), t.get(f"ruzgarHizGun{i}")))
    return out


def cevap_metni(yorum, kullanici):
    iller = hedefleri_bul(yorum)
    if not iller:
        return None
    s = sade(yorum)
    ruzgar_iste = "ruzgar" in s or "firtina" in s
    bugun = datetime.datetime.now(TR).date()
    if re.search(COK_GUN, s) and "hafta sonu" not in s and "haftasonu" not in s:
        bloklar = []
        for il, istno in iller[:2]:  # uzun cevap olmasın diye en fazla 2 yer
            gunler = tahmin_cok(istno)
            if gunler:
                satirlar = [f"{simge(h)} {GUN_KISA[t.weekday()]} {t.day} {AYLAR[t.month][:3]}  {mx}° / {mn}°  {h}"
                            + (f" · 💨{rz} km/sa" if ruzgar_iste and rz is not None else "") for t, h, mx, mn, rz in gunler]
                bloklar.append(f"📍 {il} – {len(gunler)} günlük\n" + "\n".join(satirlar))
        if not bloklar:
            return None
        return f"@{kullanici}\n" + "\n\n".join(bloklar) + "\n\nKaynak: MGM"
    if "yarin" in s:
        gunler = [(bugun + datetime.timedelta(days=1), "yarın")]
    elif "hafta sonu" in s or "haftasonu" in s:
        cmt = bugun + datetime.timedelta(days=(5 - bugun.weekday()) % 7)
        gunler = [(cmt, "Cumartesi"), (cmt + datetime.timedelta(days=1), "Pazar")]
    else:
        gunler = [(bugun, "bugün")]
    satirlar = []
    for il, istno in iller:
        parcalar = []
        for tarih, ad in gunler:
            v = tahmin(istno, tarih)
            if v is None and ad == "bugün":  # öğleden sonra MGM bugünü kaldırıyor -> yarını ver
                tarih, ad = bugun + datetime.timedelta(days=1), "yarın"
                v = tahmin(istno, tarih)
            if v:
                parcalar.append(f"{simge(v[0])} {ad.capitalize()} ({tarih.day} {AYLAR[tarih.month]}): {v[0]}\n🌡️ En yüksek {v[1]}° · En düşük {v[2]}°"
                                + (f"\n💨 Rüzgar {v[3]} km/sa" if v[3] is not None else ""))
        if parcalar:
            satirlar.append(f"📍 {il}\n" + "\n".join(parcalar))
    if not satirlar:
        return None
    return f"@{kullanici}\n" + "\n\n".join(satirlar) + "\n\nKaynak: MGM"


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
    sayilar = durum.get("yorum_sayilari", {})
    # 1 istek: son gönderiler + yorum sayıları. Sadece yorumu artan gönderilere bakılır (API sınırı için)
    medya = ig.istek(f"{ig.USER}/media", {"fields": "id,comments_count", "limit": SON_GONDERI}, "GET").get("data", [])
    # profilde sabitlenen gönderiler eskise de her zaman kontrol edilsin
    son_idler = {m["id"] for m in medya}
    for sid in durum.get("sabit_gonderiler", []):
        if sid not in son_idler:
            try:
                medya.append(ig.istek(sid, {"fields": "id,comments_count"}, "GET"))
            except Exception as e:
                print("Sabit gönderi okunamadı:", sid, e)
    tam_kontrol = datetime.datetime.now(TR).minute % 15 == 0  # 15 dakikada bir tüm yorumlara bak
    degisen = [m for m in medya if m.get("comments_count", 0) and
               (tam_kontrol or m.get("comments_count", 0) != sayilar.get(m["id"], -1))]
    for m in medya:
        sayilar[m["id"]] = m.get("comments_count", 0)
    if not degisen:
        return print("Yeni yorum yok")
    hesap = durum.get("hesap") or ig.istek(ig.USER, {"fields": "username"}, "GET").get("username", "")
    durum["hesap"] = hesap
    yeni = 0
    for m in degisen:
        sayilar[m["id"]] = m.get("comments_count", 0)
        ham = ig.istek(f"{m['id']}/comments", {"fields": "id,text,username,timestamp,replies{id,text,username,timestamp}",
                                              "limit": 50}, "GET").get("data", [])
        yorumlar = []
        sinir = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S")
        for y in ham:
            yorumlar.append(dict(y, ust=y["id"]))
            for r in (y.get("replies") or {}).get("data", []):
                if r.get("timestamp", "") >= sinir:  # eski yanıtlara toplu cevap yağmasın
                    yorumlar.append(dict(r, ust=y["id"]))  # yanıta cevap, ana yorumun altına yazılır
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
            ig.istek(f"{y['ust']}/replies", {"message": metin[:2000]})
            print("Cevaplandı:", y.get("username"), "|", y.get("text", "")[:60], "->", metin[:90])
            yeni += 1
            if yeni >= TUR_BASINA_EN_FAZLA:
                break
    durum["yorum_sayilari"] = {k: v for k, v in sayilar.items() if k in {m["id"] for m in medya}}
    durum["cevaplanan_yorumlar"] = list(cevaplanan)[-5000:]
    json.dump(durum, open(DURUM, "w", encoding="utf-8"), ensure_ascii=False)
    print(yeni, "yoruma cevap verildi")


if __name__ == "__main__":
    main()
