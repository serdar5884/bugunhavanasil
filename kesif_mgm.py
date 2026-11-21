"""MGM ölçüm (son durum / en düşük-en yüksek) servislerini keşfeder; sonuçları kesif/ altına yazar."""
import json, re, requests
H = {"Origin": "https://www.mgm.gov.tr", "Referer": "https://www.mgm.gov.tr/", "User-Agent": "Mozilla/5.0"}
out = {}
def al(u):
    try:
        r = requests.get(u, headers=H, timeout=25)
        return r.status_code, r.text
    except Exception as e:
        return -1, str(e)
# 1) sayfa + JS'lerden servis adreslerini topla
for sayfa in ["https://www.mgm.gov.tr/sondurum/en-yuksek-en-dusuk-sicakliklar.aspx", "https://www.mgm.gov.tr/sondurum/en-yuksek-en-dusuk.aspx",
              "https://www.mgm.gov.tr/sondurum/turkiye-icin-son-durumlar.aspx", "https://www.mgm.gov.tr/sondurum/"]:
    k, t = al(sayfa)
    out[sayfa] = {"kod": k, "js": re.findall(r'src="([^"]+\.js[^"]*)"', t)[:40], "servis": sorted(set(re.findall(r"servis\.mgm\.gov\.tr/[^\"'\s]+", t)))}
    for js in out[sayfa]["js"]:
        ju = js if js.startswith("http") else "https://www.mgm.gov.tr/" + js.lstrip("/")
        k2, t2 = al(ju)
        bul = sorted(set(re.findall(r"""['"]/?(?:web/)?(sondurumlar[^'"]*|enDusuk[^'"]*|enYuksek[^'"]*|[a-zA-Z]*[Ss]icaklik[^'"]*)['"]""", t2)))
        if bul:
            out[ju] = bul
# 2) tahmini adresler
for yol in ["sondurumlar/enDusukSicakliklar", "sondurumlar/enYuksekSicakliklar", "sondurumlar/enDusuk", "sondurumlar/enYuksek",
            "sondurumlar/ekstremler", "sondurumlar?merkezid=90601", "sondurumlar/il?il=Sivas", "sondurumlar/il81", "ekstremler",
            "sondurumlar/maxmin", "sondurumlar/enSicakEnSoguk", "sondurumlar/enDusukEnYuksek"]:
    k, t = al("https://servis.mgm.gov.tr/web/" + yol)
    out["/web/" + yol] = {"kod": k, "ornek": t[:600]}
json.dump(out, open("kesif/mgm_olcum.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False)[:3000])
