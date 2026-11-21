"""MGM en düşük/en yüksek ölçüm servisini keşfeder."""
import json, re, urllib.request
H = {"Origin": "https://www.mgm.gov.tr", "Referer": "https://www.mgm.gov.tr/", "User-Agent": "Mozilla/5.0"}
def al(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return -1, str(e)
out = {}
k, t = al("https://www.mgm.gov.tr/sondurum/en-yuksek-en-dusuk-sicakliklar.aspx")
open("kesif/eyed.html", "w").write(t)
out["satirlar"] = [l.strip()[:300] for l in t.splitlines() if re.search(r"enDusuk|enYuksek|servis|ng-controller|\.js|ekstrem", l)][:80]
for js in re.findall(r'src="([^"]+\.js[^"]*)"', t):
    for taban in ["https://www.mgm.gov.tr/sondurum/", "https://www.mgm.gov.tr/"]:
        u = js if js.startswith("http") else taban + js.lstrip("./").lstrip("/")
        k2, t2 = al(u)
        if k2 == 200 and re.search(r"enDusuk|enYuksek", t2):
            out[u] = [t2[max(0, m.start() - 300):m.start() + 300] for m in re.finditer(r"enDusuk|enYuksek", t2)][:6]
for q in ["?sayi=10", "?adet=10", "?zaman=bugun", "?tarih=2026-11-21", "?gun=0", "?istno=17130", "?bolge=1", "?il=Sivas", "?tip=0", "?sure=24"]:
    for yol in ["sondurumlar/enDusuk", "sondurumlar/enYuksek"]:
        k3, t3 = al("https://servis.mgm.gov.tr/web/" + yol + q)
        out[yol + q] = [k3, t3[:300]]
json.dump(out, open("kesif/mgm_olcum.json", "w"), ensure_ascii=False, indent=1)
