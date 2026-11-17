import asyncio, os, subprocess, sys, wave
METIN = "On saniyede: Lodos ve poyraz arasındaki fark nedir? Lodos, güneybatıdan eser. Ilık ve fırtınalıdır! Poyraz ise kuzeydoğudan eser. Soğuk ve serttir. Bizi takipte kalın!"
os.makedirs("yayin/ses_ornek", exist_ok=True)
CANLI = "atempo=1.12,asetrate=22050*1.05,aresample=44100,equalizer=f=3000:t=q:w=1:g=3"

def piper(model, ad, canli):
    from piper import PiperVoice
    v = PiperVoice.load(model)
    with wave.open("/tmp/p.wav", "wb") as wf:
        try:
            from piper import SynthesisConfig
            v.synthesize_wav(METIN, wf, syn_config=SynthesisConfig(length_scale=0.9, noise_scale=0.8, noise_w_scale=0.9))
        except Exception:
            v.synthesize_wav(METIN, wf)
    af = CANLI if canli else "anull"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "/tmp/p.wav", "-af", af, "-b:a", "128k", f"yayin/ses_ornek/{ad}.mp3"], check=True)

for m, ad in (("ses_model/dfki.onnx", "1_piper_dfki_canli"), ("ses_model/fettah.onnx", "2_piper_fettah_canli")):
    if os.path.exists(m):
        try: piper(m, ad, True)
        except Exception as e: print("hata", ad, e)

async def edge():
    import edge_tts
    for ses, ad in (("tr-TR-EmelNeural", "3_microsoft_emel_kadin"), ("tr-TR-AhmetNeural", "4_microsoft_ahmet_erkek")):
        try:
            await edge_tts.Communicate(METIN, ses, rate="+12%", pitch="+6Hz").save(f"yayin/ses_ornek/{ad}.mp3")
        except Exception as e:
            print("hata", ad, e)
asyncio.run(edge())
print(os.listdir("yayin/ses_ornek"))
