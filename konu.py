"""Aynı konu (ör. 'yarın kar') gün içinde en fazla 2 formatta paylaşılsın: liste, akşam kancası, yurt geneli kartı."""
import datetime, json, os

DOSYA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "konu.json")
ESLE = {"KAR": "kar", "YAGIS": "yagmur", "YAGMUR": "yagmur", "firtina": "yagmur", "AYAZ": "soguk", "SOGUK": "soguk",
        "SICAK": "sicak", "RUZGAR": "ruzgar"}
SINIR = 2


def _bugun():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date().isoformat()


def _oku():
    try:
        d = json.load(open(DOSYA, encoding="utf-8"))
        return d if d.get("tarih") == _bugun() else {"tarih": _bugun(), "konular": {}}
    except Exception:
        return {"tarih": _bugun(), "konular": {}}


def _ad(k):
    if (k or "").startswith("ulke_"):
        return k
    return ESLE.get(k, (k or "").lower())


def dolu_mu(k, sinir=SINIR):
    return _oku()["konular"].get(_ad(k), 0) >= sinir


def kaydet(k):
    if not k:
        return
    d = _oku()
    d["konular"][_ad(k)] = d["konular"].get(_ad(k), 0) + 1
    json.dump(d, open(DOSYA, "w", encoding="utf-8"), ensure_ascii=False)
