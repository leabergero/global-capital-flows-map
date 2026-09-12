#!/usr/bin/env python3
"""
Self-check del dodge de etiquetas del RRG.

No re-implementa el algoritmo (eso solo verificaría una copia que se desactualiza):
pide el DOM ya renderizado por el navegador y mide las cajas de texto que
realmente se pintaron. Falla si dos etiquetas de sector vuelven a encimarse.

Uso (con el server levantado):
    python check_rrg_labels.py [url]
Necesita chromium en el PATH.
"""
import re
import subprocess
import sys

CHW, LBH = 5.42, 9      # ancho de char y alto de línea a font-size 9, monospace
LABEL = re.compile(
    r'<text x="([\d.-]+)" y="([\d.-]+)" text-anchor="(\w+)"[^>]*'
    r'class="rrg-sector-label"[^>]*>([^<]+)</text>'
)


def main(url):
    dom = subprocess.run(
        ["chromium", "--headless", "--disable-gpu", "--no-sandbox",
         "--virtual-time-budget=20000", "--dump-dom", url],
        capture_output=True, text=True, timeout=120,
    ).stdout
    svg = dom.partition('<svg id="rrg"')[2].partition("</svg>")[0]

    cajas = []
    for x, y, anchor, texto in LABEL.findall(svg):
        x, y = float(x), float(y)
        ancho = len(texto) * CHW
        x0 = x - ancho if anchor == "end" else x
        cajas.append((texto, x0, x0 + ancho, y))

    assert len(cajas) >= 8, f"el RRG pintó solo {len(cajas)} etiquetas"
    choques = [
        (a[0], b[0])
        for i, a in enumerate(cajas) for b in cajas[i + 1:]
        if a[1] < b[2] and b[1] < a[2] and abs(a[3] - b[3]) < LBH
    ]
    assert not choques, f"etiquetas encimadas: {choques}"
    print(f"RRG dodge OK — {len(cajas)} etiquetas, sin solapes")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5055/")
