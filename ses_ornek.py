import asyncio, os, edge_tts
METIN = "Lodos ve poyraz arasındaki fark nedir? Lodos, güneybatıdan eser. Ilık ve fırtınalıdır! Poyraz ise kuzeydoğudan eser. Soğuk ve serttir. Bizi takipte kalın!"
os.makedirs("yayin/ses_ornek2", exist_ok=True)
async def main():
    sesler = await edge_tts.list_voices()
    coklu = sorted(v["ShortName"] for v in sesler if "Multilingual" in v["ShortName"])
    print("Çok dilli sesler:", coklu)
    adaylar = [("tr-TR-AhmetNeural", "+20%", "+10Hz", "1_ahmet_daha_enerjik"),
               ("tr-TR-EmelNeural", "+15%", "+8Hz", "2_emel_enerjik")]
    for ad, dosya in (("en-US-AndrewMultilingualNeural", "3_andrew_cokdilli_erkek"), ("en-US-BrianMultilingualNeural", "4_brian_cokdilli_erkek"),
                      ("en-US-AvaMultilingualNeural", "5_ava_cokdilli_kadin"), ("en-US-EmmaMultilingualNeural", "6_emma_cokdilli_kadin"),
                      ("de-DE-FlorianMultilingualNeural", "7_florian_cokdilli_erkek")):
        if ad in coklu:
            adaylar.append((ad, "+10%", "+0Hz", dosya))
    for ses, hiz, ton, dosya in adaylar:
        try:
            await edge_tts.Communicate(METIN, ses, rate=hiz, pitch=ton).save(f"yayin/ses_ornek2/{dosya}.mp3")
            print("ok", dosya)
        except Exception as e:
            print("hata", dosya, e)
asyncio.run(main())
