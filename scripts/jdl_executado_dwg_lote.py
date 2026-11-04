"""
Gera, para cada subpasta (fazenda/revisao) de uma raiz de executados, um DWG
com a trajetoria tick a tick dos .jdl (mesmos pontos do GOIMP do AgroCAD):

    <raiz>/<F>/dwg_executado/executado_<F>.dxf
    <raiz>/<F>/dwg_executado/executado_<F>.dwg

O DXF e montado numa pasta local temporaria (o G: e rede, lento), convertido
pra DWG via ODA File Converter, verificado (contagem de POINTs e bbox lendo o
DXF de volta em streaming) e so entao copiado pro destino.

Uso:
    python jdl_executado_dwg_lote.py <raiz> [FAZENDA ...] [--relatorio saida.csv]
"""
import argparse
import csv
import os
import shutil
import sys
import tempfile
import time

from jdl_para_dxf import gerar_dxf_ticks
from converter_dwg import converter_dxf_para_dwg


def verificar_dxf(caminho_dxf: str):
    """Conta POINTs e calcula bbox lendo o DXF em streaming (sem carregar tudo)."""
    from ezdxf.addons import iterdxf
    n = 0
    xmin = ymin = float("inf")
    xmax = ymax = float("-inf")
    # obs: iterdxf.single_pass_modelspace perde a ultima entidade (ezdxf 1.4.4),
    # por isso opendxf
    doc = iterdxf.opendxf(caminho_dxf)
    try:
        for e in doc.modelspace(types=["POINT"]):
            x, y, _ = e.dxf.location
            n += 1
            if x < xmin: xmin = x
            if x > xmax: xmax = x
            if y < ymin: ymin = y
            if y > ymax: ymax = y
    finally:
        doc.close()
    return n, (xmin, ymin, xmax, ymax)


def processar(raiz: str, fazenda: str) -> dict:
    t0 = time.time()
    pasta = os.path.join(raiz, fazenda)
    destino = os.path.join(pasta, "dwg_executado")
    nome = f"executado_{fazenda}"
    with tempfile.TemporaryDirectory() as tmp:
        dxf_local = os.path.join(tmp, nome + ".dxf")
        n_ticks = gerar_dxf_ticks(pasta, dxf_local)
        dwg_local = converter_dxf_para_dwg(dxf_local, tmp)
        n_pts, bbox = verificar_dxf(dxf_local)
        os.makedirs(destino, exist_ok=True)
        shutil.copy2(dxf_local, os.path.join(destino, nome + ".dxf"))
        shutil.copy2(str(dwg_local), os.path.join(destino, nome + ".dwg"))
    dwg_final = os.path.join(destino, nome + ".dwg")
    xmin, ymin, xmax, ymax = bbox
    bbox_ok = (n_pts > 0 and 150_000 <= xmin and xmax <= 350_000
               and 7_550_000 <= ymin and ymax <= 7_750_000)
    return {
        "fazenda": fazenda, "ticks": n_ticks, "points_dxf": n_pts,
        "contagem_ok": n_ticks == n_pts, "bbox_ok": bbox_ok,
        "xmin": round(xmin, 1), "ymin": round(ymin, 1),
        "xmax": round(xmax, 1), "ymax": round(ymax, 1),
        "dwg_mb": round(os.path.getsize(dwg_final) / 1e6, 1),
        "dxf_mb": round(os.path.getsize(os.path.join(destino, nome + ".dxf")) / 1e6, 1),
        "tempo_s": round(time.time() - t0, 1), "dwg": dwg_final,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raiz")
    ap.add_argument("fazendas", nargs="*", help="subpastas a processar (padrao: todas)")
    ap.add_argument("--relatorio", default=None, help="CSV com o resumo por fazenda")
    args = ap.parse_args()

    fazendas = args.fazendas or sorted(
        d for d in os.listdir(args.raiz) if os.path.isdir(os.path.join(args.raiz, d)))

    linhas = []
    for f in fazendas:
        print(f"=== {f} ===", flush=True)
        try:
            r = processar(args.raiz, f)
        except Exception as e:
            print(f"  [ERRO] {f}: {e!r}", flush=True)
            r = {"fazenda": f, "erro": repr(e)}
        print(f"  {r}", flush=True)
        linhas.append(r)
        if args.relatorio:
            campos = sorted({k for l in linhas for k in l}, key=lambda k: (k != "fazenda", k))
            with open(args.relatorio, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=campos)
                w.writeheader()
                w.writerows(linhas)
    if any("erro" in l or not l.get("contagem_ok") or not l.get("bbox_ok") for l in linhas):
        sys.exit(1)


if __name__ == "__main__":
    main()
