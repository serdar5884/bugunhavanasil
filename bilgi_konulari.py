"""
"10 saniyede" bilgi videosu konuları.
Her sahnede: ad (büyük başlık), metin (altyazı), ses (seslendirme metni; sayılar yazıyla), vurgu, gok, efekt, gorsel.
Pusula açıları ekran koordinatında rüzgarın GELDİĞİ yön: 135=güneybatı, 315=kuzeydoğu, 225=kuzeybatı, 45=güneydoğu, 270=kuzey, 90=güney.
"""

KONULAR = [
    {
        "id": "lodos_poyraz",
        "baslik": ["LODOS", "VE", "POYRAZ"], "soru": "FARKI NEDİR?",
        "soru_tam": "Lodos ve poyraz arasındaki fark nedir?",
        "ses_baslik": "On saniyede: Lodos ve poyraz arasındaki fark nedir?",
        "gok": "bulutlu",
        "sahneler": [
            {"ad": "LODOS", "metin": "Lodos güneybatıdan eser, ılık ve fırtınalıdır.",
             "ses": "Lodos, güneybatıdan eser. Ilık ve fırtınalıdır.", "vurgu": ["güneybatıdan", "ılık"],
             "gok": "ilik", "efekt": ["ruzgar"], "akis": "sag", "serit": [255, 200, 140],
             "gorsel": "pusula", "ok_aci": 135, "etiket": "GÜNEYBATIDAN ESER", "sure": 5.5},
            {"ad": "POYRAZ", "metin": "Poyraz kuzeydoğudan eser, soğuk ve serttir.",
             "ses": "Poyraz ise kuzeydoğudan eser. Soğuk ve serttir.", "vurgu": ["kuzeydoğudan", "soğuk"],
             "gok": "soguk", "efekt": ["ruzgar", "kar"], "akis": "sol", "serit": [220, 240, 255],
             "gorsel": "pusula", "ok_aci": 315, "etiket": "KUZEYDOĞUDAN ESER", "sure": 5.5},
        ],
        "ozet": [["LODOS", "Ilık · Fırtınalı", "Güneybatıdan eser", [225, 130, 70]],
                 ["POYRAZ", "Soğuk · Sert", "Kuzeydoğudan eser", [90, 150, 220]]],
        "ses_ozet": "Kısacası: lodos ılık, poyraz soğuk.",
        "aciklama": ["Lodos güneybatıdan esen ılık bir rüzgardır; özellikle Marmara'da fırtınaya dönüşebilir.",
                     "Poyraz kuzeydoğudan esen soğuk ve sert bir rüzgardır; kışın soğuk havayı getirir."],
        "etiket": "#lodos #poyraz #rüzgar",
    },
]
