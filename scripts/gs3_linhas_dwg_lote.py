"""
Mesmo fluxo do jdl_linhas_dwg_lote.py, mas para executados gravados pelo
monitor GS3_2630 (.fdl/.fdd, ver gs3_documentacao.py): acha todos os .fdl
abaixo da raiz, agrupa as sessoes pela fazenda gravada no proprio .fdl
(funciona tambem com o que o copiador mandou pra SEM_FAZENDA_IDENTIFICADA),
roda LSFP -> QBD -> CLE -> limpar e grava <fazenda>_linhas.dwg. Tambem
calcula o PLL de cada fazenda e o geral.

Uso:
    python gs3_linhas_dwg_lote.py <raiz> <pasta_saida> [--lsfp 10 --qbd 160 --cle 10] [--csv saida.csv]
"""
import argparse
import collections
import csv
import glob
import os
import re

import pyproj

from gs3_documentacao import ler_sessao, pontos_plantio
from jdl_linhas_dwg_lote import linhas_ate_cle, salvar_linhas_dwg
from paralelismo_pipeline import pll

UTM_23S_SIRGAS2000 = "EPSG:31983"


def nome_arquivo(fazenda: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", fazenda).strip() or "SEM_NOME"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raiz")
    ap.add_argument("pasta_saida")
    ap.add_argument("--lsfp", type=float, default=10.0)
    ap.add_argument("--qbd", type=float, default=160.0)
    ap.add_argument("--cle", type=float, default=10.0)
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()

    os.makedirs(args.pasta_saida, exist_ok=True)
    transformer = pyproj.Transformer.from_crs("EPSG:4326", UTM_23S_SIRGAS2000, always_xy=True)
    por_fazenda = collections.defaultdict(list)
    for fdl in sorted(glob.glob(os.path.join(args.raiz, "**", "*.fdl"), recursive=True)):
        sessao = ler_sessao(fdl)
        if sessao["registros"]:
            por_fazenda[sessao["fazenda"]].append(sessao)

    linhas_csv = []
    tot = collections.Counter()
    soma_media = 0.0
    for fazenda, sessoes in sorted(por_fazenda.items()):
        pontos = []
        for s in sessoes:
            lats_lons = pontos_plantio(s)
            if lats_lons:
                xs, ys = transformer.transform([lo for _, lo in lats_lons], [la for la, _ in lats_lons])
                pontos.extend(zip(xs, ys))
        nome = nome_arquivo(fazenda)
        linhas = linhas_ate_cle(pontos, nome, args.lsfp, args.qbd, args.cle)
        salvar_linhas_dwg(linhas, nome, args.pasta_saida)
        r = pll(linhas)
        km = sum(l.length for l in linhas) / 1000
        print(f"{fazenda}: sessoes={len(sessoes)} pontos={len(pontos)} linhas={len(linhas)} km={km:.1f} "
              f"amostras={r.total_amostras} inf={r.pct_abaixo:.2f}% ideal={r.pct_ideal:.2f}% "
              f"sup={r.pct_acima:.2f}%", flush=True)
        linhas_csv.append([fazenda, len(sessoes), len(pontos), len(linhas), f"{km:.1f}", r.total_amostras,
                           r.abaixo, f"{r.pct_abaixo:.2f}", r.ideais, f"{r.pct_ideal:.2f}",
                           r.acima, f"{r.pct_acima:.2f}", f"{r.espacamento_medio:.2f}"])
        tot.update(amostras=r.total_amostras, inf=r.abaixo, ide=r.ideais, sup=r.acima)
        soma_media += r.espacamento_medio * r.total_amostras

    n = tot["amostras"] or 1
    geral = ["GERAL", "", "", "", "", tot["amostras"], tot["inf"], f"{100 * tot['inf'] / n:.2f}",
             tot["ide"], f"{100 * tot['ide'] / n:.2f}", tot["sup"], f"{100 * tot['sup'] / n:.2f}",
             f"{soma_media / n:.2f}"]
    print(f"GERAL: amostras={tot['amostras']} inf={geral[7]}% ideal={geral[9]}% sup={geral[11]}%")
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["fazenda", "sessoes", "pontos", "linhas", "km", "amostras", "inferiores", "pct_inferiores",
                        "ideais", "pct_ideais", "superiores", "pct_superiores", "espacamento_medio"])
            w.writerows(linhas_csv + [geral])


if __name__ == "__main__":
    main()
