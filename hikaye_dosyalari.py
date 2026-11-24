#!/usr/bin/env python3
"""
Sadece hikâye olarak paylaşmak isteyen ortak sayfalar için (hikaye_ortaklar.json):
günün il videosu ve görseli 'hikaye' dalına sabit adlarla konur. Adresler her gün aynıdır:
  https://raw.githubusercontent.com/serdar5884/bugunhavanasil/hikaye/<İl>_hikaye.mp4
  https://raw.githubusercontent.com/serdar5884/bugunhavanasil/hikaye/<İl>_hikaye.jpg
"""
import json, os, shutil, subprocess, tempfile

iller = json.load(open("hikaye_ortaklar.json", encoding="utf-8"))
tmp = tempfile.mkdtemp()
var = []
for il in iller:
    son = f"yayin/il_ozel/{il}/son.txt"
    if not os.path.exists(son):
        il_yolu = None
        continue
    jpg = open(son).read().strip()
    mp4, kapak = jpg[:-4] + ".mp4", jpg[:-4] + "_kapak.jpg"
    if os.path.exists(mp4):
        shutil.copy(mp4, os.path.join(tmp, f"{il}_hikaye.mp4")); var.append(f"{il}_hikaye.mp4")
    if os.path.exists(kapak):
        shutil.copy(kapak, os.path.join(tmp, f"{il}_hikaye.jpg")); var.append(f"{il}_hikaye.jpg")
if not var:
    raise SystemExit("Hikâye dosyası yok")
env = dict(os.environ, GIT_INDEX_FILE=os.path.join(tmp, "index"), GIT_WORK_TREE=tmp)
subprocess.run(["git", "add", "-f", *var], env=env, check=True)
agac = subprocess.check_output(["git", "write-tree"], env=env, text=True).strip()
c = subprocess.check_output(["git", "-c", "user.name=hava-bot", "-c", "user.email=hava-bot@users.noreply.github.com",
                             "commit-tree", agac, "-m", "hikaye"], text=True).strip()
subprocess.run(["git", "push", "-q", "-f", "origin", f"{c}:refs/heads/hikaye"], check=True)
print("Hikâye dosyaları güncellendi:", ", ".join(var))
