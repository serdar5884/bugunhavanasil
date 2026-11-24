#!/usr/bin/env python3
"""
Günlük istatistik raporu: son 24 saatte paylaşılan tüm gönderilerin (özellikle ortak Sivas Reels'leri)
izlenme, erişim, beğeni, yorum, paylaşım ve kaydetme sayıları; ortak sayfa bazında özet.
Çıktı: rapor/istatistik_<tarih>.md ve rapor/son.md
"""
import datetime, json, os, sys
import instagram_paylas as ig

TR = datetime.timezone(datetime.timedelta(hours=3))
METRIKLER = ["views", "reach", "likes", "comments", "shares", "saved"]


def insights(mid):
    try:
        d = ig.istek(f"{mid}/insights", {"metric": ",".join(METRIKLER)}, "GET").get("data", [])
        return {x["name"]: (x.get("values") or [{}])[0].get("value", x.get("total_value", {}).get("value")) for x in d}
    except Exception as e:  # eski videolarda "views" yoksa tek tek dene
        out = {}
        for m in METRIKLER:
            try:
                d = ig.istek(f"{mid}/insights", {"metric": m}, "GET").get("data", [])
                if d:
                    out[m] = (d[0].get("values") or [{}])[0].get("value")
            except Exception:
                pass
        if not out:
            print("İstatistik alınamadı:", mid, e)
        return out


def ortaklar(mid):
    try:
        d = ig.istek(f"{mid}/collaborators", {}, "GET").get("data", [])
        return [x.get("username") for x in d if x.get("username")]
    except Exception:
        return []


def main():
    simdi = datetime.datetime.now(TR)
    sinir = simdi - datetime.timedelta(hours=26)
    medya = ig.istek(f"{ig.USER}/media", {"fields": "id,caption,timestamp,media_product_type,permalink,comments_count,like_count",
                                         "limit": 50}, "GET").get("data", [])
    satirlar, ortak_ozet = [], {}
    for m in medya:
        t = datetime.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(TR)
        if t < sinir:
            continue
        i = insights(m["id"])
        o = ortaklar(m["id"])
        baslik = (m.get("caption") or "").split("\n")[0][:55]
        satirlar.append((t, m, i, o, baslik))
        for u in o:
            oz = ortak_ozet.setdefault(u, {"adet": 0, "views": 0, "likes": 0, "shares": 0, "saved": 0})
            oz["adet"] += 1
            for k in ("views", "likes", "shares", "saved"):
                oz[k] += i.get(k) or 0
    satirlar.sort(key=lambda x: -(x[2].get("views") or 0))
    toplam = sum(x[2].get("views") or 0 for x in satirlar)
    md = [f"# Günlük istatistik – {simdi:%d.%m.%Y %H:%M}", "",
          f"Son 24 saatte {len(satirlar)} paylaşım, toplam {toplam:,} izlenme.".replace(",", "."), ""]
    if ortak_ozet:
        md += ["## Ortak sayfalar (Sivas)", "", "| Sayfa | Reels | İzlenme | Beğeni | Paylaşım | Kaydetme |", "|---|---|---|---|---|---|"]
        for u, oz in sorted(ortak_ozet.items(), key=lambda x: -x[1]["views"]):
            md.append(f"| @{u} | {oz['adet']} | {oz['views']} | {oz['likes']} | {oz['shares']} | {oz['saved']} |")
        md.append("")
    md += ["## Tüm paylaşımlar (izlenmeye göre)", "", "| Saat | Paylaşım | Ortak | İzlenme | Erişim | Beğeni | Yorum | Paylaşım | Kaydetme |",
           "|---|---|---|---|---|---|---|---|---|"]
    for t, m, i, o, b in satirlar:
        md.append(f"| {t:%H:%M} | [{b or m.get('media_product_type', '')}]({m.get('permalink', '')}) | {', '.join('@' + u for u in o) or '-'} | "
                  f"{i.get('views', '-')} | {i.get('reach', '-')} | {i.get('likes', m.get('like_count', '-'))} | "
                  f"{i.get('comments', m.get('comments_count', '-'))} | {i.get('shares', '-')} | {i.get('saved', '-')} |")
    os.makedirs("rapor", exist_ok=True)
    metin = "\n".join(md) + "\n"
    open(f"rapor/istatistik_{simdi:%Y%m%d}.md", "w", encoding="utf-8").write(metin)
    open("rapor/son.md", "w", encoding="utf-8").write(metin)
    print(metin)


if __name__ == "__main__":
    main()
