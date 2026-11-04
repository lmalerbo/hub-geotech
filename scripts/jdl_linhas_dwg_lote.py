"""
Roda o pipeline ate o CLE (LSFP -> QBD -> CLE -> limpar) para cada subpasta (fazenda/
revisao) de uma raiz de executados e grava as linhas limpas em DWG, prontas
para a analise de paralelismo (PLL) no AgroCAD:

    <saida>/<F>_linhas.dwg   (LWPOLYLINE na camada LINHAS_EXECUTADO, SIRGAS2000 UTM 23S)

O DXF e montado numa pasta local temporaria (destino costuma ser rede) e so o
DWG convertido e copiado.

Uso:
    python jdl_linhas_dwg_lote.py <raiz> <pasta_saida> [--lsfp 10 --qbd 160 --cle 10] [--relatorio csv]
"""
import argparse
import csv
import glob
import os
import shutil
import tempfile
import time

import ezdxf

from converter_dwg import converter_dxf_para_dwg
from jdl_paralelismo import extrair_pontos_utm
from paralelismo_pipeline import cle, limpar, lsfp, qbd

CAMADA = "LINHAS_EXECUTADO"


def gerar_linhas_dwg(pasta: str, nome: str, pasta_saida: str, lsfp_m: float, qbd_graus: float,
                     cle_m: float) -> tuple[int, int, float]:
    """Retorna (pontos, linhas, km de linhas)."""
    pontos, _ = extrair_pontos_utm(pasta)
    linhas = linhas_ate_cle(pontos, nome, lsfp_m, qbd_graus, cle_m)
    salvar_linhas_dwg(linhas, nome, pasta_saida)
    return len(pontos), len(linhas), sum(l.length for l in linhas) / 1000


def linhas_ate_cle(pontos, nome: str, lsfp_m: float, qbd_graus: float, cle_m: float):
    """LSFP -> QBD -> CLE -> limpar."""
    linhas = cle(qbd(lsfp({nome: pontos}, max_dist=lsfp_m), min_angle_deg=qbd_graus), min_length=cle_m)
    return limpar(linhas)


def salvar_linhas_dwg(linhas, nome: str, pasta_saida: str) -> None:
    """Grava <pasta_saida>/<nome>_linhas.dwg (LWPOLYLINE em LINHAS_EXECUTADO)."""
    doc = ezdxf.new("R2018")
    doc.layers.add(CAMADA)
    msp = doc.modelspace()
    for linha in linhas:
        msp.add_lwpolyline(list(linha.coords), dxfattribs={"layer": CAMADA})

    with tempfile.TemporaryDirectory() as tmp:
        dxf = os.path.join(tmp, f"{nome}_linhas.dxf")
        doc.saveas(dxf)
        dwg = converter_dxf_para_dwg(dxf, tmp)
        shutil.copy2(dwg, os.path.join(pasta_saida, os.path.basename(dwg)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raiz")
    ap.add_argument("pasta_saida")
    ap.add_argument("--lsfp", type=float, default=12.0)
    ap.add_argument("--qbd", type=float, default=160.0)
    ap.add_argument("--cle", type=float, default=15.0)
    ap.add_argument("--relatorio", default=None)
    args = ap.parse_args()

    os.makedirs(args.pasta_saida, exist_ok=True)
    pastas = sorted(p for p in glob.glob(os.path.join(args.raiz, "*")) if os.path.isdir(p))
    if args.relatorio:
        with open(args.relatorio, "w", newline="", encoding="utf-8") as f:
            csv.writer(f, delimiter=";").writerow(["fazenda", "pontos", "linhas", "km_linhas", "segundos"])

    for pasta in pastas:
        nome = os.path.basename(pasta)
        t0 = time.time()
        n_pts, n_lin, km = gerar_linhas_dwg(pasta, nome, args.pasta_saida, args.lsfp, args.qbd, args.cle)
        seg = round(time.time() - t0)
        print(f"{nome}: pontos={n_pts} linhas={n_lin} km={km:.1f} tempo={seg}s", flush=True)
        if args.relatorio:
            with open(args.relatorio, "a", newline="", encoding="utf-8") as f:
                csv.writer(f, delimiter=";").writerow([nome, n_pts, n_lin, f"{km:.1f}", seg])


if __name__ == "__main__":
    main()
