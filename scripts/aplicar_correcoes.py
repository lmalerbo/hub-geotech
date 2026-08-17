"""
Aplica correcoes manuais (exportadas da ferramenta interativa de
colheitabilidade) em cima da classificacao automatica, gerando o shapefile
final corrigido pra aquela fazenda/tipo.

Fluxo:
    1. Na ferramenta interativa, corrige a classificacao visualmente e clica
       "Exportar correcoes" -- baixa um JSON com os ajustes.
    2. python aplicar_correcoes.py <shapefile_bruto.shp> <correcoes.json> <saida.shp>

O shapefile de entrada precisa ser o MESMO (mesma ordem de linhas) que gerou
os dados carregados na ferramenta via prep_visualizacao_partes.py -- os
overrides referenciam indice de linha, entao ordem diferente = correcao
aplicada na linha errada.

O JSON de correcao e copiado pra linhas-vant/correcoes/ como log de auditoria
(serve tambem pra revisar padroes das correcoes mais tarde e refinar os
parametros do algoritimo).
"""

import json
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import warnings

from classificar_partes import (
    calcular_compacidade, calcular_custo_corte, calcular_cv,
    classificar_partes_bruto,
)

warnings.filterwarnings("ignore")

PASTA_CORRECOES = Path("linhas-vant/correcoes")


def aplicar(shp_bruto: str, correcoes_json: str, shp_saida: str):
    with open(correcoes_json, "r", encoding="utf-8") as f:
        corr = json.load(f)

    if corr.get("metodo") != "walk":
        raise ValueError(
            f"Metodo '{corr.get('metodo')}' nao suportado aqui -- so o metodo "
            f"'walk' (Prim/MST, o mesmo do pipeline de producao) tem equivalente "
            f"em Python. Reclassifique na ferramenta usando esse metodo."
        )

    print(f"Fazenda {corr['fazenda']}/{corr['tipo']}: {len(corr['overrides'])} correcao(oes) manual(is)")
    print(
        f"  Reproduzindo classificacao base (alvo={corr['alvoMB']}MB max={corr['maxMB']}MB "
        f"min={corr['minMB']}MB dist={corr['maxDist']}m)..."
    )

    gdf = gpd.read_file(shp_bruto)
    bruto = classificar_partes_bruto(
        gdf, alvo_mb=corr["alvoMB"], max_mb=corr["maxMB"],
        min_mb=corr["minMB"], max_dist_m=corr["maxDist"],
    )
    partes, geoms, vizinhos, bytes_, n = (
        bruto["partes"], bruto["geoms"], bruto["vizinhos"], bruto["bytes_"], bruto["n"]
    )

    if len(partes) != corr["nPartesBase"]:
        raise ValueError(
            f"Numero de partes-base nao bate: reproduzido={len(partes)} "
            f"esperado={corr['nPartesBase']}. O shapefile de entrada provavelmente "
            f"nao e o mesmo (ou esta em ordem diferente) do que gerou os dados na "
            f"ferramenta interativa -- as correcoes nao podem ser aplicadas com seguranca."
        )

    part_of = [None] * n
    for k, p in enumerate(partes):
        for i in p:
            part_of[i] = k

    aplicadas = 0
    for line_id, alvo in corr["overrides"]:
        if alvo is not None and 0 <= alvo < len(partes):
            part_of[line_id] = alvo
            aplicadas += 1
    print(f"  {aplicadas}/{len(corr['overrides'])} correcao(oes) aplicada(s)")

    partes_finais = [set() for _ in partes]
    for i, k in enumerate(part_of):
        if k is not None:
            partes_finais[k].add(i)

    tipo = corr["tipo"]
    partes_ordenadas = sorted(partes_finais, key=len, reverse=True)
    field_names = [None] * n
    tamanhos = []
    for idx, parte in enumerate(partes_ordenadas, start=1):
        nome = f"{tipo}-{idx}"
        for i in parte:
            field_names[i] = nome
        tamanhos.append((nome, len(parte), sum(bytes_[i] for i in parte)))

    print(f"\n{len(tamanhos)} parte(s) apos correcao:")
    for nome, n_linhas, tam in tamanhos:
        print(f"  {nome}: {n_linhas} linha(s), {tam/1_000_000:.3f}MB")

    compacidade = calcular_compacidade(partes_ordenadas, geoms, bytes_)
    desequilibrio = calcular_cv(partes_ordenadas, bytes_)
    custo_corte = calcular_custo_corte(partes_ordenadas, vizinhos, n)
    print(
        f"\nQualidade apos correcao: compacidade={compacidade:.2f}  "
        f"desequilibrio={desequilibrio:.1f}%  custo_corte={custo_corte/1000:.2f}km"
    )

    gdf_wgs84 = gdf.to_crs(4326) if gdf.crs and gdf.crs.to_epsg() != 4326 else gdf.copy()
    gdf_wgs84["FIELD_NAME"] = field_names
    gdf_wgs84.to_file(shp_saida)
    print(f"\nShapefile corrigido gerado: {shp_saida}")

    PASTA_CORRECOES.mkdir(parents=True, exist_ok=True)
    destino_log = PASTA_CORRECOES / Path(correcoes_json).name
    shutil.copy2(correcoes_json, destino_log)
    print(f"Log de correcao arquivado: {destino_log}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python aplicar_correcoes.py <shapefile_bruto.shp> <correcoes.json> <saida.shp>")
        sys.exit(1)
    aplicar(sys.argv[1], sys.argv[2], sys.argv[3])
