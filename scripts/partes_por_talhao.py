"""
Calcula a classificacao de partes UMA VEZ usando os poligonos de talhao como
referencia espacial estavel, e aplica o mesmo resultado tanto pro 1L quanto
pro 2L (em vez de rodar o crescimento em cima de cada conjunto de linha
separadamente, o que gerava contornos levemente diferentes entre os dois).

Uso:
    python partes_por_talhao.py <farm_secao> <shp_talhoes> <shp_1L> <shp_2L> <saida_dir>
"""

import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import box

warnings.filterwarnings("ignore")

BYTES_POR_PONTO = 45.3
ALVO_MB = 1.0
MAX_MB = 1.5
DIST_MAX_TALHAO_M = 50.0  # dois talhoes sao "vizinhos" se estiverem a ate essa distancia


def carregar_talhoes(shp_talhoes: str, secao: float) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(shp_talhoes)
    sub = gdf[gdf["SECAO"] == secao].copy()
    utm = sub.estimate_utm_crs()
    sub = sub.to_crs(utm)
    sub = sub.dissolve(by="TALHAO", as_index=False)[["TALHAO", "geometry"]]
    sub["TALHAO"] = sub["TALHAO"].astype(str)
    return sub.reset_index(drop=True)


def atribuir_linhas_a_talhoes(shp_linhas: str, talhoes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(shp_linhas).to_crs(talhoes.crs)
    centroides = gdf.geometry.centroid
    juncao = gpd.sjoin(
        gpd.GeoDataFrame(geometry=centroides, crs=talhoes.crs),
        talhoes[["TALHAO", "geometry"]],
        how="left",
        predicate="within",
    )
    gdf["TALHAO"] = juncao["TALHAO"].values

    faltando = gdf["TALHAO"].isna()
    if faltando.any():
        # fallback: talhao mais proximo pra linhas cujo centroide caiu fora de qualquer poligono
        talhoes_sindex = talhoes.sindex
        for idx in gdf[faltando].index:
            c = centroides.loc[idx]
            dists = talhoes.geometry.distance(c)
            gdf.loc[idx, "TALHAO"] = talhoes.loc[dists.idxmin(), "TALHAO"]
    return gdf


def bytes_por_talhao(gdf_linhas: gpd.GeoDataFrame) -> dict:
    pontos = gdf_linhas.geometry.apply(lambda g: len(g.coords))
    tmp = gdf_linhas.assign(pontos=pontos)
    soma = tmp.groupby("TALHAO")["pontos"].sum() * BYTES_POR_PONTO
    return soma.to_dict()


def vizinhanca_talhoes(talhoes: gpd.GeoDataFrame, dist_max: float) -> dict:
    adj = {t: [] for t in talhoes["TALHAO"]}
    for i in range(len(talhoes)):
        for j in range(i + 1, len(talhoes)):
            d = talhoes.geometry.iloc[i].distance(talhoes.geometry.iloc[j])
            if d <= dist_max:
                ti, tj = talhoes["TALHAO"].iloc[i], talhoes["TALHAO"].iloc[j]
                adj[ti].append((tj, d))
                adj[tj].append((ti, d))
    for t in adj:
        adj[t].sort(key=lambda x: x[1])
    return adj


def detectar_ilhas(talhoes_ids: list, adj: dict) -> list:
    parent = {t: t for t in talhoes_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[a] = b

    for t in talhoes_ids:
        for viz, _ in adj[t]:
            union(t, viz)

    grupos = {}
    for t in talhoes_ids:
        grupos.setdefault(find(t), []).append(t)
    return list(grupos.values())


def ponto_de_partida(ilha: list, centroides: dict) -> str:
    pts = np.array([centroides[t] for t in ilha])
    mean = pts.mean(axis=0)
    cov = np.cov((pts - mean).T)
    if cov.shape == ():
        return ilha[0]
    autovals, autovecs = np.linalg.eigh(cov)
    eixo = autovecs[:, np.argmax(autovals)]
    proj = [(centroides[t] - mean) @ eixo for t in ilha]
    return ilha[int(np.argmin(proj))]


def crescer_partes_isoladas(ilha: list, adj: dict, pesos: dict, centroides: dict, alvo_bytes: float, max_bytes: float) -> list:
    total = sum(pesos.get(t, 0) for t in ilha)
    n_partes = max(1, int(np.ceil(total / max_bytes)))
    target_por_parte = total / n_partes

    nao_atribuido = set(ilha)
    partes = []
    semente = ponto_de_partida(ilha, centroides)

    while nao_atribuido:
        eh_ultima = len(partes) == n_partes - 1
        parte = {semente}
        nao_atribuido.discard(semente)
        bytes_atual = pesos.get(semente, 0)

        fronteira = {}
        def atualiza_fronteira(no):
            for viz, d in adj[no]:
                if viz in nao_atribuido:
                    if viz not in fronteira or d < fronteira[viz]:
                        fronteira[viz] = d
        atualiza_fronteira(semente)

        limite = max_bytes if eh_ultima else target_por_parte
        while nao_atribuido and bytes_atual < limite:
            if not fronteira:
                break
            melhor = min(fronteira, key=fronteira.get)
            del fronteira[melhor]
            parte.add(melhor)
            nao_atribuido.discard(melhor)
            bytes_atual += pesos.get(melhor, 0)
            atualiza_fronteira(melhor)

        partes.append(parte)
        if not nao_atribuido:
            break

        if fronteira:
            semente = min(fronteira, key=fronteira.get)
        else:
            semente = next(iter(nao_atribuido))

    # funde partes pequenas na vizinha mais proxima
    min_bytes = target_por_parte * 0.3
    mudou = True
    while mudou and len(partes) > 1:
        mudou = False
        for k, p in enumerate(partes):
            if sum(pesos.get(t, 0) for t in p) >= min_bytes:
                continue
            melhor_j, melhor_d = None, float("inf")
            for t in p:
                for viz, d in adj[t]:
                    for j, outra in enumerate(partes):
                        if j != k and viz in outra and d < melhor_d:
                            melhor_d, melhor_j = d, j
            if melhor_j is None:
                tam = [(j, len(pp)) for j, pp in enumerate(partes) if j != k]
                if tam:
                    melhor_j = max(tam, key=lambda x: x[1])[0]
            if melhor_j is not None:
                partes[melhor_j] |= partes[k]
                del partes[k]
                mudou = True
                break
    return partes


def classificar(talhoes: gpd.GeoDataFrame, pesos: dict) -> dict:
    talhoes_ids = list(talhoes["TALHAO"])
    centroides = {row.TALHAO: np.array([row.geometry.centroid.x, row.geometry.centroid.y]) for row in talhoes.itertuples()}
    adj = vizinhanca_talhoes(talhoes, DIST_MAX_TALHAO_M)
    ilhas = detectar_ilhas(talhoes_ids, adj)
    ilhas.sort(key=len, reverse=True)

    talhao_para_parte = {}
    partes_final = []
    for ilha in ilhas:
        partes = crescer_partes_isoladas(ilha, adj, pesos, centroides, ALVO_MB * 1_000_000, MAX_MB * 1_000_000)
        for p in partes:
            idx_parte = len(partes_final)
            partes_final.append(p)
            for t in p:
                talhao_para_parte[t] = idx_parte
    return {"talhao_para_parte": talhao_para_parte, "n_ilhas": len(ilhas), "n_partes": len(partes_final)}


def main(secao: str, shp_talhoes: str, shp_1l: str, shp_2l: str, saida_dir: str):
    talhoes = carregar_talhoes(shp_talhoes, float(secao))
    print(f"{len(talhoes)} talhoes encontrados pra secao {secao}: {sorted(talhoes['TALHAO'].tolist(), key=int)}")

    gdf_1l = atribuir_linhas_a_talhoes(shp_1l, talhoes)
    gdf_2l = atribuir_linhas_a_talhoes(shp_2l, talhoes)

    pesos_1l = bytes_por_talhao(gdf_1l)
    pesos_2l = bytes_por_talhao(gdf_2l)
    pesos_media = {t: (pesos_1l.get(t, 0) + pesos_2l.get(t, 0)) / 2 for t in talhoes["TALHAO"]}

    resultado = classificar(talhoes, pesos_media)
    print(f"\n{resultado['n_ilhas']} ilha(s) de talhoes, {resultado['n_partes']} parte(s) geradas:")
    partes_agrupadas = {}
    for t, p in resultado["talhao_para_parte"].items():
        partes_agrupadas.setdefault(p, []).append(t)
    for p in sorted(partes_agrupadas):
        talhoes_p = sorted(partes_agrupadas[p], key=int)
        mb = sum(pesos_media.get(t, 0) for t in talhoes_p) / 1_000_000
        print(f"  Parte {p+1}: talhoes {talhoes_p} -- {mb:.2f}MB (media 1L/2L)")

    out_dir = Path(saida_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    gdf_1l["PARTE"] = gdf_1l["TALHAO"].map(resultado["talhao_para_parte"])
    gdf_2l["PARTE"] = gdf_2l["TALHAO"].map(resultado["talhao_para_parte"])
    gdf_1l.to_file(out_dir / f"{secao}_1L_partes.shp")
    gdf_2l.to_file(out_dir / f"{secao}_2L_partes.shp")

    with open(out_dir / f"{secao}_talhao_para_parte.json", "w", encoding="utf-8") as f:
        json.dump(resultado["talhao_para_parte"], f, indent=2)

    print(f"\nSalvo em {out_dir}/")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Uso: python partes_por_talhao.py <farm_secao> <shp_talhoes> <shp_1L> <shp_2L> <saida_dir>")
        sys.exit(1)
    main(*sys.argv[1:])
