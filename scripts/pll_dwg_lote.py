"""
PLL (analise vetorial de paralelismo) direto sobre DWGs de linhas ja
prontas -- ex.: os <F>_linhas.dwg gerados por jdl_linhas_dwg_lote.py, ou os
mesmos depois de limpos a mao no AutoCAD. Nao refaz LSFP/QBD/CLE/limpar: mede
as linhas como estao no arquivo, igual ao comando PLL do AgroCAD.

Le as polilinhas da camada LINHAS_EXECUTADO (ou de todas as camadas, se ela
nao existir). Resultado por arquivo e geral (soma das amostras de todos).

Uso:
    python pll_dwg_lote.py <pasta_com_dwg> [--csv saida.csv] [--intervalo 10]
"""
import argparse
import csv
import glob
import os
import tempfile

import ezdxf
from shapely.geometry import LineString

from converter_dwg import converter_arquivo
from paralelismo_pipeline import pll

CAMADA = "LINHAS_EXECUTADO"


def ler_linhas(dwg: str) -> list[LineString]:
    with tempfile.TemporaryDirectory() as tmp:
        doc = ezdxf.readfile(converter_arquivo(dwg, tmp))
    msp = doc.modelspace()
    polis = list(msp.query("LWPOLYLINE POLYLINE"))
    if any(p.dxf.layer == CAMADA for p in polis):
        polis = [p for p in polis if p.dxf.layer == CAMADA]
    linhas = []
    for p in polis:
        pts = [(v[0], v[1]) for v in (p.get_points("xy") if p.dxftype() == "LWPOLYLINE" else p.points())]
        if len(pts) >= 2:
            linhas.append(LineString(pts))
    return linhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--intervalo", type=float, default=10.0)
    args = ap.parse_args()

    linhas_csv = []
    tot = {"amostras": 0, "inferiores": 0, "ideais": 0, "superiores": 0, "soma": 0.0, "km": 0.0}
    for dwg in sorted(glob.glob(os.path.join(args.pasta, "*.dwg"))):
        linhas = ler_linhas(dwg)
        r = pll(linhas, sample_interval=args.intervalo)
        km = sum(l.length for l in linhas) / 1000
        nome = os.path.basename(dwg).removesuffix(".dwg")
        print(f"{nome}: linhas={len(linhas)} km={km:.1f} amostras={r.total_amostras} "
              f"inf={r.pct_abaixo:.2f}% ideal={r.pct_ideal:.2f}% sup={r.pct_acima:.2f}% "
              f"media={r.espacamento_medio:.2f}", flush=True)
        linhas_csv.append([nome, len(linhas), f"{km:.1f}", r.total_amostras, r.abaixo, f"{r.pct_abaixo:.2f}",
                           r.ideais, f"{r.pct_ideal:.2f}", r.acima, f"{r.pct_acima:.2f}", f"{r.espacamento_medio:.2f}"])
        tot["amostras"] += r.total_amostras
        tot["inferiores"] += r.abaixo
        tot["ideais"] += r.ideais
        tot["superiores"] += r.acima
        tot["soma"] += r.espacamento_medio * r.total_amostras
        tot["km"] += km

    n = tot["amostras"] or 1
    geral = ["GERAL", "", f"{tot['km']:.1f}", tot["amostras"],
             tot["inferiores"], f"{100 * tot['inferiores'] / n:.2f}",
             tot["ideais"], f"{100 * tot['ideais'] / n:.2f}",
             tot["superiores"], f"{100 * tot['superiores'] / n:.2f}", f"{tot['soma'] / n:.2f}"]
    print(f"GERAL: km={tot['km']:.1f} amostras={tot['amostras']} inf={geral[5]}% ideal={geral[7]}% "
          f"sup={geral[9]}% media={geral[10]}")
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["arquivo", "linhas", "km", "amostras", "inferiores", "pct_inferiores", "ideais",
                        "pct_ideais", "superiores", "pct_superiores", "espacamento_medio"])
            w.writerows(linhas_csv + [geral])


if __name__ == "__main__":
    main()
