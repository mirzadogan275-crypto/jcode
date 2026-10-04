#!/usr/bin/env python3
"""qbank-parts/*.md dosyalarından chapters/31-soru-bankasi.md üretir.

Her parça yalnızca soru bloklarını içerir (biçim: build.render_qbank). Parçalar sırayla
kısımlara bölünür; sorular kitap boyunca 1'den başlayarak numaralanır.
"""
import os
import re
import sys

import build

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS_DIR = os.path.join(HERE, "qbank-parts")
OUT = os.path.join(build.CHAPTERS, "31-soru-bankasi.md")

SECTIONS = [
    ("qbank-1.md", "Temeller ve boyun (Bölüm 1–8)"),
    ("qbank-2.md", "Onkolojinin ilkeleri, ağız boşluğu ve orofarenks (Bölüm 9–15)"),
    ("qbank-3.md", "Nazofarenks, hipofarenks, larenks, havayolu ve tükürük bezleri (Bölüm 16–23)"),
    ("qbank-4.md", "Tiroid ve paratiroid (Bölüm 24–27)"),
    ("qbank-5.md", "Cilt kanserleri, lenfoma, sarkom ve sinonazal tümörler (Bölüm 28–29)"),
]

INTRO = """# Soru Bankası

Bu bölümde kitabın tüm konularını kapsayan **150 adet beş seçenekli, tek doğru yanıtlı soru** yer alır. Soruların yaklaşık yarısı klinik vaka, diğer yarısı doğrudan bilgi sorusudur ve dağılım bölümlerin sınavdaki ağırlığını yansıtır. Her kısmın sonunda **yanıtlar ve açıklamalar** verilmiştir; açıklamalar doğru seçeneğin gerekçesini, çeldiricilerin neden yanlış olduğunu ve konunun ayrıntılı anlatıldığı bölümü içerir.

!!! klinik "Nasıl çalışılmalı?"
    Soruları önce yanıt anahtarına bakmadan çözün ve yanıtlarınızı not edin. Ardından açıklamaları okuyun; yanlış yaptığınız soruların konularını parantez içinde belirtilen bölümden tekrar edin. Yedi günlük plandaki soru aralıkları "Bu Kitap Nasıl Kullanılır?" bölümünde verilmiştir.
"""


def main():
    out = [INTRO]
    total = 0
    letters = {}
    for fname, title in SECTIONS:
        path = os.path.join(PARTS_DIR, fname)
        if not os.path.exists(path):
            print(f"UYARI: {fname} yok — atlandı", file=sys.stderr)
            continue
        body = open(path, encoding="utf-8").read().strip()
        counters = {}
        build.render_qbank(body, counters)  # biçim doğrulaması
        n = counters["q"]
        for k in re.findall(r"^Yanıt:\s*([A-E])", body, flags=re.M):
            letters[k] = letters.get(k, 0) + 1
        out.append(f"## {title}\n\n```qbank\n{body}\n```\n")
        print(f"{fname}: {n} soru ({total + 1}–{total + n})")
        total += n
    open(OUT, "w", encoding="utf-8").write("\n".join(out))
    dist = " ".join(f"{k}:{letters.get(k, 0)}" for k in "ABCDE")
    print(f"Toplam {total} soru → {OUT}  | yanıt dağılımı {dist}")


if __name__ == "__main__":
    main()
