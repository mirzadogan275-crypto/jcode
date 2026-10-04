#!/usr/bin/env python3
"""Baş ve Boyun Cerrahisi sınav kitabı — Markdown → HTML → PDF (WeasyPrint).

Kullanım:  python3 build.py [--html-only] [--only 05,06]
Çıktı:     ../Bas-ve-Boyun-Cerrahisi-Sinav-Kitabi.pdf
"""
import hashlib
import html
import math
import os
import re
import subprocess
import sys

import markdown

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHAPTERS = os.path.join(ROOT, "chapters")
CACHE = os.path.join(HERE, ".diagram-cache")
OUT_PDF = os.path.join(ROOT, "Bas-ve-Boyun-Cerrahisi-Sinav-Kitabi.pdf")
OUT_HTML = os.path.join(HERE, "book.html")

BOOK_TITLE = "Baş ve Boyun Cerrahisi"
BOOK_SUBTITLE = "KBB uzmanlık ve yeterlik sınavlarına yönelik ileri düzey, kılavuz destekli kapsamlı rehber"
EDITION = "1. baskı · Ekim 2026"

# (kısım başlığı, [bölüm dosyaları]) — dosya adları chapters/ altında, uzantısız
PARTS = [
    ("Temeller", ["01-embriyoloji", "02-boyun-anatomisi"]),
    ("Boyun", ["03-boyun-kitlesi", "04-konjenital-kitleler", "05-boyun-enfeksiyonlari",
               "06-boyun-diseksiyonu", "07-boyun-travmasi", "08-parafarengeal-paragangliom"]),
    ("Baş-Boyun Onkolojisinin İlkeleri", ["09-onkoloji-temel", "10-radyoterapi-sistemik", "11-rekonstruksiyon"]),
    ("Ağız Boşluğu ve Farenks", ["12-agiz-mukoza", "13-agiz-kanseri", "14-farenks-tonsil",
                                "15-orofarenks-kanseri", "16-nazofarenks", "17-hipofarenks-yutma"]),
    ("Larenks, Trakea ve Havayolu", ["18-larenks-benign", "19-larenks-noroloji-pediatrik",
                                    "20-larenks-kanseri", "21-havayolu-trakea"]),
    ("Tükürük Bezleri", ["22-tukuruk-nonneoplastik", "23-tukuruk-tumorleri"]),
    ("Tiroid ve Paratiroid", ["24-tiroid-benign-nodul", "25-tiroid-kanseri", "26-tiroidektomi", "27-paratiroid"]),
    ("Diğer Baş-Boyun Tümörleri", ["28-cilt-lenfoma-sarkom", "29-sinonazal-kafatabani"]),
    ("Sınav Hazırlık", ["30-yuksek-verimli-tablolar", "31-soru-bankasi"]),
]
FRONT = ["front-kullanim", "front-kaynaklar", "front-kisaltmalar"]
BACK = ["back-kaynakca"]

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def tr_upper(s: str) -> str:
    """Türkçe büyük harf dönüşümü (i→İ, ı→I)."""
    return s.replace("i", "İ").replace("ı", "I").upper()


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


# ---------------------------------------------------------------------------
# Diyagramlar (Graphviz)
# ---------------------------------------------------------------------------
DOT_DEFAULTS = (
    'graph [fontname="Source Sans 3", fontsize=12, bgcolor="transparent", pad=0.15, nodesep=0.25, ranksep=0.32];\n'
    'node [fontname="Source Sans 3", fontsize=12, shape=box, style="rounded,filled", fillcolor="#eef6f8", '
    'color="#16697a", penwidth=1.1, margin="0.12,0.06"];\n'
    'edge [fontname="Source Sans 3", fontsize=11, color="#5b6770", arrowsize=0.7, penwidth=1.0];\n'
)


def render_dot(src: str) -> str:
    os.makedirs(CACHE, exist_ok=True)
    # varsayılan stilleri ilk süslü paranteze enjekte et
    src2 = re.sub(r"(digraph|graph)\s*([\w\"]*)\s*\{", lambda m: m.group(0) + "\n" + DOT_DEFAULTS, src, count=1)
    key = hashlib.sha1(src2.encode()).hexdigest()[:16]
    path = os.path.join(CACHE, key + ".svg")
    if not os.path.exists(path):
        res = subprocess.run(["dot", "-Tsvg:cairo"], input=src2.encode(), capture_output=True)
        if res.returncode != 0:
            raise RuntimeError("Graphviz hatası:\n" + res.stderr.decode() + "\n" + src2)
        open(path, "wb").write(res.stdout)
    svg = open(path, encoding="utf-8").read()
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg).strip()
    # pt → genişlik sınırı: çok geniş diyagramları sayfaya sığdır
    m = re.search(r'width="([\d.]+)pt"', svg)
    if m:
        w = float(m.group(1))
        maxw = 470.0
        if w > maxw:
            scale = maxw / w
            hm = re.search(r'height="([\d.]+)pt"', svg)
            h = float(hm.group(1)) if hm else 0
            svg = svg.replace(m.group(0), f'width="{maxw:.1f}pt"', 1)
            if hm:
                svg = svg.replace(hm.group(0), f'height="{h*scale:.1f}pt"', 1)
    return svg


# ---------------------------------------------------------------------------
# Markdown ön işleme
# ---------------------------------------------------------------------------
def preprocess(md_text: str, chnum, counters: dict) -> str:
    # ```dot ... ``` blokları → figür
    def dot_repl(m):
        body = m.group(1)
        cap = ""
        cm = re.search(r"^\s*//\s*caption:\s*(.+)$", body, flags=re.M)
        if cm:
            cap = cm.group(1).strip()
            body = body.replace(cm.group(0), "")
        svg = render_dot(body)
        counters["fig"] += 1
        label = f"Şekil {chnum}.{counters['fig']}" if chnum else f"Şekil {counters['fig']}"
        capt = f'<figcaption><span class="fnum">{label}</span>{html.escape(cap)}</figcaption>' if cap else ""
        return f'\n<figure class="diagram">{svg}{capt}</figure>\n'

    md_text = re.sub(r"^```dot\s*\n(.*?)^```\s*$", dot_repl, md_text, flags=re.S | re.M)

    # "Tablo: başlık" satırları → numaralı tablo başlığı
    def tab_repl(m):
        counters["tab"] += 1
        label = f"Tablo {chnum}.{counters['tab']}" if chnum else f"Tablo {counters['tab']}"
        return f'\n<p class="tablecap"><span class="tnum">{label}</span>{m.group(2).strip()}</p>\n'

    md_text = re.sub(r"^([ \t]*)Tablo:\s*(.+)$", lambda m: "\n" + m.group(1) + tab_repl(m).strip("\n") + "\n",
                     md_text, flags=re.M)
    return md_text


def make_md():
    return markdown.Markdown(
        extensions=["tables", "attr_list", "def_list", "footnotes", "admonition", "md_in_html",
                    "sane_lists", "pymdownx.mark", "pymdownx.caret", "pymdownx.betterem"],
        extension_configs={"footnotes": {"UNIQUE_IDS": True}},
    )


def postprocess(htm: str, chnum, toc: list) -> str:
    # admonition başlıklarını Türkçe büyük harfe çevir
    htm = re.sub(r'<p class="admonition-title">(.*?)</p>',
                 lambda m: f'<p class="admonition-title">{tr_upper(m.group(1))}</p>', htm, flags=re.S)
    # h2 numaralandırma + TOC
    sec = [0]

    def h2_repl(m):
        sec[0] += 1
        inner = m.group(2)
        hid = f"c{chnum}-s{sec[0]}" if chnum else f"x{abs(hash(inner)) % 10**8}-s{sec[0]}"
        num = f"{chnum}.{sec[0]}" if chnum else ""
        toc.append(("sec", num, strip_tags(inner), hid))
        numspan = f'<span class="hnum">{num}</span>&#8194;' if num else ""
        return f'<h2 id="{hid}">{numspan}{inner}</h2>'

    htm = re.sub(r"<h2( [^>]*)?>(.*?)</h2>", h2_repl, htm, flags=re.S)
    # tablolar: çok sütunlu ise kompakt
    def table_repl(m):
        t = m.group(0)
        first_row = re.search(r"<tr>(.*?)</tr>", t, flags=re.S)
        ncols = len(re.findall(r"<t[hd]", first_row.group(1))) if first_row else 0
        if ncols >= 5:
            t = t.replace("<table>", '<table class="compact">', 1)
        return t

    htm = re.sub(r"<table>.*?</table>", table_repl, htm, flags=re.S)
    return htm


def read_chapter(stem):
    path = os.path.join(CHAPTERS, stem + ".md")
    if not os.path.exists(path):
        return None, None
    txt = open(path, encoding="utf-8").read()
    m = re.match(r"\s*#\s+(.+?)\s*\n", txt)
    if not m:
        raise ValueError(f"{stem}: ilk satır '# Başlık' olmalı")
    title = m.group(1).strip()
    body = txt[m.end():]
    return title, body


# ---------------------------------------------------------------------------
# Kapak sanatı (soyut kontur çizgileri)
# ---------------------------------------------------------------------------
def cover_art_svg():
    paths = []
    for i in range(34):
        y0 = 40 + i * 14
        amp = 18 + 10 * math.sin(i / 3.0)
        d = f"M -20 {y0:.1f} "
        for k in range(1, 9):
            x = k * 75 - 20
            y = y0 + amp * math.sin(k * 0.9 + i * 0.33) + 6 * math.cos(i * 0.7 + k)
            cx = x - 37
            cy = y0 + amp * math.sin((k - 0.5) * 0.9 + i * 0.33)
            d += f"Q {cx:.1f} {cy:.1f} {x:.1f} {y:.1f} "
        width = 1.6 if i % 5 == 0 else 0.8
        paths.append(f'<path d="{d}" fill="none" stroke="#ffffff" stroke-width="{width}"/>')
    circles = "".join(
        f'<circle cx="{420 + 60*math.cos(a):.1f}" cy="{260 + 60*math.sin(a):.1f}" r="{3 + (j % 3)}" fill="#ffd6dc"/>'
        for j, a in enumerate([x * 0.7 for x in range(9)]))
    return (f'<svg class="art" viewBox="0 0 560 560" xmlns="http://www.w3.org/2000/svg">{"".join(paths)}'
            f'<circle cx="420" cy="260" r="92" fill="none" stroke="#ffd6dc" stroke-width="2.2"/>{circles}</svg>')


# ---------------------------------------------------------------------------
# Kitap derleme
# ---------------------------------------------------------------------------
def build(only=None, html_only=False):
    toc = []  # (kind, num, title, id)
    body_parts = []
    stats = {"words": 0, "chapters": 0}

    # Kapak
    tags = ["NCCN 2026", "AJCC 8 / Versiyon 9", "ATA 2025", "Bethesda 2023", "Milan 2. baskı",
            "WHO 2022–2024", "CAP HPV 2025", "ISSVA 2025", "KEYNOTE-689", "NIVOPOSTOP"]
    body_parts.append(f'''
<section class="cover">
  <div class="band"></div>
  {cover_art_svg()}
  <div class="kicker">{tr_upper("Kulak Burun Boğaz · Baş ve Boyun Cerrahisi")}</div>
  <h1 class="title">Baş ve Boyun<br/>Cerrahisi</h1>
  <div class="rule"></div>
  <div class="subtitle">{BOOK_SUBTITLE}</div>
  <div class="tags">{"".join(f"<span>{t}</span>" for t in tags)}</div>
  <div class="edition"><b>{EDITION}</b><br/>Otoloji ve rinoloji kapsam dışıdır · Sınav odaklı sentez</div>
</section>''')

    # İç kapak
    body_parts.append(f'''
<section class="front titlepage">
  <div class="t1">Baş ve Boyun Cerrahisi</div>
  <div class="t2">{BOOK_SUBTITLE}</div>
  <div class="t3">Embriyoloji ve cerrahi anatomiden onkolojiye, tükürük bezlerinden tiroid–paratiroide<br/>
  güncel kılavuzlar, evreleme sistemleri, dönüm noktası çalışmalar ve soru bankası</div>
  <div class="colophon">
  <b>{EDITION}</b><br/>
  Bu metin kişisel sınav hazırlığı amacıyla hazırlanmış bir çalışma kitabıdır. Standart KBB–baş-boyun cerrahisi
  ders kitaplarındaki temel bilgiler ile 2024–2026 dönemine ait kılavuz ve evreleme güncellemeleri sentezlenmiştir.
  Klinik karar verirken hasta özelinde güncel kılavuzlara, ürün bilgilerine ve kurumsal protokollere başvurulmalıdır.
  İlaç dozları ve tedavi şemaları yalnızca bilgilendirme amaçlıdır.
  </div>
</section>''')

    # Ön kısım dosyaları
    for stem in FRONT:
        title, body = read_chapter(stem)
        if title is None:
            continue
        md = make_md()
        htm = md.convert(preprocess(body, None, {"fig": 0, "tab": 0}))
        htm = re.sub(r'<p class="admonition-title">(.*?)</p>',
                     lambda m: f'<p class="admonition-title">{tr_upper(m.group(1))}</p>', htm, flags=re.S)
        fid = "front-" + stem
        body_parts.append(f'<section class="front" id="{fid}"><h1>{title}</h1>{htm}</section>')
        toc.append(("front", "", title, fid))

    toc_index = len(body_parts)
    body_parts.append("")  # İçindekiler yer tutucu

    chnum = 0
    for pi, (ptitle, stems) in enumerate(PARTS):
        part_id = f"part-{pi+1}"
        ch_list = []
        part_html_index = len(body_parts)
        body_parts.append("")
        toc.append(("part", ROMAN[pi], ptitle, part_id))
        for stem in stems:
            chnum += 1
            if only and stem[:2] not in only:
                continue
            title, body = read_chapter(stem)
            if title is None:
                ch_list.append((chnum, f"{title or stem} (hazırlanıyor)"))
                continue
            stats["chapters"] += 1
            stats["words"] += len(re.findall(r"\w+", body))
            counters = {"fig": 0, "tab": 0}
            md = make_md()
            htm = md.convert(preprocess(body, chnum, counters))
            cid = f"ch-{chnum}"
            toc.append(("ch", str(chnum), title, cid))
            htm = postprocess(htm, chnum, toc)
            ch_list.append((chnum, title))
            body_parts.append(f'''
<section class="chapter" id="{cid}">
  <header class="chopen">
    <div class="chnum">{tr_upper("Bölüm")} <b>{chnum}</b></div>
    <h1 data-bm="{chnum}. {html.escape(title)}">{title}</h1>
    <div class="chbar"></div>
  </header>
  {htm}
</section>''')
        lis = "".join(f"<li><span>{n}</span>{html.escape(t)}</li>" for n, t in ch_list)
        body_parts[part_html_index] = f'''
<section class="part" id="{part_id}">
  <div class="pbig">{ROMAN[pi]}</div>
  <div class="pnum">{tr_upper("Kısım")} {ROMAN[pi]}</div>
  <h1 class="ptitle" data-bm="Kısım {ROMAN[pi]} — {html.escape(ptitle)}">{ptitle}</h1>
  <div class="prule"></div>
  <ul class="pch">{lis}</ul>
</section>'''

    # Arka kısım
    for stem in BACK:
        title, body = read_chapter(stem)
        if title is None:
            continue
        md = make_md()
        htm = md.convert(preprocess(body, None, {"fig": 0, "tab": 0}))
        bid = "back-" + stem
        toc.append(("ch", "", title, bid))
        body_parts.append(f'''
<section class="chapter backmatter" id="{bid}">
  <header class="chopen"><div class="chnum">{tr_upper("Ek")}</div><h1 data-bm="{html.escape(title)}">{title}</h1><div class="chbar"></div></header>
  {htm}
</section>''')

    # İçindekiler
    items = []
    for kind, num, title, tid in toc:
        if kind == "front":
            items.append(f'<li class="toc-ch"><a href="#{tid}">{html.escape(title)}</a></li>')
        elif kind == "part":
            items.append(f'<li class="toc-part"><a href="#{tid}">{tr_upper("Kısım")} {num} · {tr_upper(title)}</a></li>')
        elif kind == "ch":
            numspan = f'<span class="num">{num}</span>' if num else ""
            items.append(f'<li class="toc-ch"><a href="#{tid}">{numspan}{html.escape(title)}</a></li>')
        else:
            items.append(f'<li class="toc-sec"><a href="#{tid}"><span class="num">{num}</span>{html.escape(title)}</a></li>')
    body_parts[toc_index] = f'<nav class="toc"><h1>İçindekiler</h1><ul>{"".join(items)}</ul></nav>'

    doc = f'''<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8"/><title>{BOOK_TITLE}</title>
<meta name="author" content="Sınav çalışma kitabı"/>
<meta name="description" content="{BOOK_SUBTITLE}"/>
<link rel="stylesheet" href="style.css"/></head>
<body>{"".join(body_parts)}</body></html>'''
    open(OUT_HTML, "w", encoding="utf-8").write(doc)
    print(f"HTML yazıldı: {OUT_HTML}  | bölüm: {stats['chapters']}  | kelime (bölümler): {stats['words']:,}")
    if html_only:
        return
    from weasyprint import HTML
    document = HTML(filename=OUT_HTML, base_url=HERE).render()
    print(f"Sayfa sayısı: {len(document.pages)}")
    document.write_pdf(OUT_PDF)
    print(f"PDF yazıldı: {OUT_PDF}")


if __name__ == "__main__":
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    build(only=only, html_only="--html-only" in sys.argv)
