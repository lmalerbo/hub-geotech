"""
Roda a analise de paralelismo (jdl_paralelismo.py) em cada subpasta de uma
pasta-raiz (uma subpasta por fazenda/revisao, cada uma com seus .jdl) e grava
uma linha por fazenda num CSV, logo que cada uma termina.

Uso:
    python jdl_paralelismo_lote.py <pasta_raiz> <saida.csv> [--lsfp 12 --qbd 160 --cle 15 --pll 10]
"""
import argparse
import csv
import glob
import os
import time

from jdl_paralelismo import extrair_pontos_utm
from paralelismo_pipeline import analisar

COLUNAS = ["fazenda", "arquivos_jdl", "pontos", "amostras", "inferiores", "pct_inferiores",
           "ideais", "pct_ideais", "superiores", "pct_superiores", "espacamento_medio", "segundos"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta_raiz")
    ap.add_argument("saida_csv")
    ap.add_argument("--lsfp", type=float, default=12.0)
    ap.add_argument("--qbd", type=float, default=160.0)
    ap.add_argument("--cle", type=float, default=15.0)
    ap.add_argument("--pll", type=float, default=10.0)
    args = ap.parse_args()

    pastas = sorted(p for p in glob.glob(os.path.join(args.pasta_raiz, "*")) if os.path.isdir(p))
    with open(args.saida_csv, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter=";").writerow(COLUNAS)

    for pasta in pastas:
        nome = os.path.basename(pasta)
        t0 = time.time()
        pontos, n_arq = extrair_pontos_utm(pasta)
        if len(pontos) < 2:
            linha = [nome, n_arq, len(pontos)] + [""] * 8 + [round(time.time() - t0)]
        else:
            r = analisar({nome: pontos}, lsfp_max_dist=args.lsfp, qbd_min_angle=args.qbd,
                         cle_min_length=args.cle, pll_sample_interval=args.pll)
            linha = [nome, n_arq, len(pontos), r.total_amostras,
                     r.abaixo, f"{r.pct_abaixo:.2f}", r.ideais, f"{r.pct_ideal:.2f}",
                     r.acima, f"{r.pct_acima:.2f}", f"{r.espacamento_medio:.2f}", round(time.time() - t0)]
        with open(args.saida_csv, "a", newline="", encoding="utf-8") as f:
            csv.writer(f, delimiter=";").writerow(linha)
        print(f"{nome}: " + " | ".join(f"{c}={v}" for c, v in zip(COLUNAS[1:], linha[1:])), flush=True)


if __name__ == "__main__":
    main()
