"""
Prepara os dados (linhas + grafo de vizinhanca real) pra visualizacao HTML
interativa de classificacao de partes (colheitabilidade).
"""

import json
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import box
from shapely.strtree import STRtree

warnings.filterwarnings("ignore")

BYTES_POR_PONTO = 45.3  # calibrado empiricamente (617755 bytes / 13633 pontos)
TOL_RENDER_M = 2.0  # simplificacao so pra visualizacao (nao afeta o pipeline real)
RAIO_VIZINHANCA_M = 20.0  # captura vizinhos nesse raio (cobre o slider ate 15m com folga)
MAX_VIZINHOS = 12  # teto por linha -- suficiente pra conectividade real, mantem o JSON leve


def preparar(shp_path: str, tipo: str, nome_display: str = "") -> dict:
    gdf = gpd.read_file(shp_path)
    utm = gdf.estimate_utm_crs()
    gdf_utm = gdf.to_crs(utm)

    geoms = list(gdf_utm.geometry)
    n = len(geoms)

    # geometria simplificada so pra render (mais leve)
    render_geoms = [g.simplify(TOL_RENDER_M, preserve_topology=False) for g in geoms]

    centroids = np.array([[g.centroid.x, g.centroid.y] for g in geoms])
    origin = centroids.min(axis=0)

    tree = STRtree(geoms)

    def bbox_expandida(g, r):
        minx, miny, maxx, maxy = g.bounds
        return box(minx - r, miny - r, maxx + r, maxy + r)

    vizinhos = []
    nn1_dists = []
    for i, g in enumerate(geoms):
        # bbox expandida da linha INTEIRA (nao so o centroide) -- senao linhas compridas
        # perdem vizinhos que estao pertos de uma ponta mas longe do centro
        idxs = tree.query(bbox_expandida(g, RAIO_VIZINHANCA_M))
        cands = [j for j in idxs if j != i]
        dists = sorted(((geoms[i].distance(geoms[j]), int(j)) for j in cands), key=lambda t: t[0])
        dists = [t for t in dists if t[0] <= RAIO_VIZINHANCA_M][:MAX_VIZINHOS]
        if not dists:
            # fallback: garante ao menos 1 vizinho (a mais proxima) mesmo fora do raio, p/ nunca isolar sozinha
            idxs2 = tree.query(bbox_expandida(g, 500))
            cands2 = [j for j in idxs2 if j != i]
            todas = sorted(((geoms[i].distance(geoms[j]), int(j)) for j in cands2), key=lambda t: t[0])[:5]
            dists = todas
        vizinhos.append([[j, round(d, 1)] for d, j in dists])
        if dists:
            nn1_dists.append(dists[0][0])

    lines_out = []
    for i, (g, rg) in enumerate(zip(geoms, render_geoms)):
        coords = [[round(x - origin[0], 2), round(y - origin[1], 2)] for x, y in rg.coords]
        n_pts_original = len(g.coords)
        lines_out.append({
            "id": i,
            "coords": coords,
            "len_m": round(g.length, 1),
            "n_pts": n_pts_original,
            "bytes": round(n_pts_original * BYTES_POR_PONTO),
            "cx": round(centroids[i][0] - origin[0], 2),
            "cy": round(centroids[i][1] - origin[1], 2),
        })

    xs = [pt[0] for l in lines_out for pt in l["coords"]]
    ys = [pt[1] for l in lines_out for pt in l["coords"]]

    return {
        "tipo": tipo,
        "nome": nome_display,
        "n_linhas": n,
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
        "mediana_nn1_m": round(float(np.median(nn1_dists)), 2) if nn1_dists else None,
        "lines": lines_out,
        "neighbors": vizinhos,
    }


OUT_PATH = Path("linhas-vant/dados_visualizacao_partes.json")


def main(entradas: list[str]):
    """entradas: cada item e '<shapefile>' ou '<shapefile>:<nome de exibicao>'.
    O shapefile precisa se chamar '<codigo_fazenda>_<tipo>.shp' (ex: 10471_1L.shp).
    Acumula no JSON existente (nao sobrescreve fazendas ja processadas antes),
    pra a ferramenta ir crescendo com os casos revisados ao longo do tempo."""
    out = {}
    if OUT_PATH.exists():
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            out = json.load(f)
        n_existentes = sum(len(v) for v in out.values())
        print(f"Carregado {OUT_PATH} existente ({n_existentes} fazenda/tipo ja presentes)")

    for entrada in entradas:
        shp_path, _, nome_display = entrada.partition(":")
        shp = Path(shp_path)
        if not shp.exists():
            print(f"Pulando (nao encontrado): {shp}")
            continue
        if "_" not in shp.stem:
            print(f"Pulando {shp} (nome precisa ser <codigo_fazenda>_<tipo>.shp)")
            continue
        fazenda, tipo = shp.stem.rsplit("_", 1)
        if not nome_display:
            nome_display = fazenda

        print(f"Processando {fazenda}/{tipo} ({shp})...")
        data = preparar(str(shp), tipo, nome_display)
        out.setdefault(fazenda, {})[tipo] = data
        print(f"  {data['n_linhas']} linhas, mediana NN1 = {data['mediana_nn1_m']}m")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"\nGerado: {OUT_PATH} ({OUT_PATH.stat().st_size / 1_000_000:.2f}MB)")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Uso: python prep_visualizacao_partes.py <shp1>[:nome exibicao] [<shp2> ...]\n"
            "  cada shp precisa se chamar <codigo_fazenda>_<tipo>.shp (ex: 10471_1L.shp)\n"
            "  acumula no dados_visualizacao_partes.json existente"
        )
        sys.exit(1)
    main(sys.argv[1:])
