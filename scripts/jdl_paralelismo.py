"""
Liga a extracao de pontos GPS do .jdl (jdl_gps_extract.py) com a analise de
paralelismo (paralelismo_pipeline.py: LSFP -> QBD -> CLE -> PLL).

Usa a trajetoria tick a tick (0,2s, ~30cm entre pontos) decodificada do item
rico -- ou, por padrao, os pontos de (PLANTIO) do GOIMP (--modo, ver
extrair_pontos_utm). Os pontos de todos os .jdl da
pasta, em ordem cronologica pelo nome do arquivo, viram um unico grupo do
LSFP, que ja quebra as linhas nos saltos (troca de talhao, sessao nova).

Uso:
    python jdl_paralelismo.py <pasta_com_jdl> [--farm CODIGO] [--lsfp 12 --qbd 160 --cle 15 --pll 10]
"""
import argparse
import glob
import os

import numpy as np
import pyproj

from filtro_produtivo import dilatar_estado, mascara_produtiva
from jdl_documentacao import pontos_plantio
from jdl_gps_extract import extrair_ticks_de_arquivo, extrair_ticks_por_registro
from paralelismo_pipeline import analisar

UTM_23S_SIRGAS2000 = "EPSG:31983"


MODOS = ("plantio", "heuristico", "todos")


def extrair_pontos_utm(pasta_jdl: str, modo: str = "plantio") -> tuple[list[tuple[float, float]], int]:
    """modo:
      plantio    -- documentacao do implemento com estado de trabalho ligado,
                    igual ao (PLANTIO) do GOIMP (jdl_documentacao.py);
      heuristico -- trilha da maquina filtrada por velocidade/curva/estado
                    (filtro_produtivo.py), pra arquivo sem documentacao;
      todos      -- trilha da maquina inteira (inclui manobra e estrada)."""
    if modo not in MODOS:
        raise ValueError(f"modo invalido: {modo} (use {MODOS})")
    arquivos = sorted(glob.glob(os.path.join(pasta_jdl, "**", "*.jdl"), recursive=True))
    transformer = pyproj.Transformer.from_crs("EPSG:4326", UTM_23S_SIRGAS2000, always_xy=True)

    pontos = []
    for caminho in arquivos:
        if modo == "plantio":
            for lat, lon in pontos_plantio(caminho):
                pontos.append(transformer.transform(lon, lat))
            continue
        if modo == "todos":
            for lat, lon in extrair_ticks_de_arquivo(caminho):
                pontos.append(transformer.transform(lon, lat))
            continue
        registros = extrair_ticks_por_registro(caminho)
        if not registros:
            continue
        lats = [la for ticks, _ in registros for la, _ in ticks]
        lons = [lo for ticks, _ in registros for _, lo in ticks]
        xs, ys = transformer.transform(lons, lats)
        xy = np.column_stack([xs, ys])
        estado = np.concatenate([np.full(len(ticks), e) for (ticks, _), e in
                                 zip(registros, dilatar_estado([e for _, e in registros]))])
        pontos.extend(map(tuple, xy[mascara_produtiva(xy, estado)]))
    return pontos, len(arquivos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta_jdl")
    ap.add_argument("--farm", default="")
    ap.add_argument("--lsfp", type=float, default=12.0, help="distancia maxima de conexao (m)")
    ap.add_argument("--qbd", type=float, default=160.0, help="angulo minimo aceitavel (graus)")
    ap.add_argument("--cle", type=float, default=15.0, help="comprimento minimo de linha (m)")
    ap.add_argument("--pll", type=float, default=10.0, help="intervalo de amostragem (m)")
    ap.add_argument("--modo", choices=MODOS, default="plantio",
                    help="plantio = igual ao GOIMP (padrao); heuristico; todos")
    args = ap.parse_args()

    pontos, n_arquivos = extrair_pontos_utm(args.pasta_jdl, modo=args.modo)
    print(f"arquivos .jdl encontrados: {n_arquivos}")
    print(f"pontos ({args.modo}): {len(pontos)}")

    if len(pontos) < 2:
        print("pontos insuficientes para analise.")
        return

    resultado = analisar(
        {args.farm or "fazenda": pontos},
        lsfp_max_dist=args.lsfp,
        qbd_min_angle=args.qbd,
        cle_min_length=args.cle,
        pll_sample_interval=args.pll,
    )
    print()
    print(resultado.resumo())


if __name__ == "__main__":
    main()
