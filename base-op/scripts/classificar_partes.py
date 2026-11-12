"""
Classificador de partes (colheitabilidade): agrupa linhas de guia em blocos
espacialmente contiguos, respeitando tamanho-alvo/minimo/maximo por bloco e
ilhas fisicamente desconectadas (lago, estrada, morro, divisa de talhao).

Algoritmo validado interativamente em colheitabilidade_partes.html (fazendas
10738, 10072, 10003) -- porte 1:1 da logica JS pra producao:
  1. Grafo de vizinhanca real (distancia linha-a-linha, nao centroide).
  2. Deteccao de ilhas (uniao-busca) pela distancia maxima de conexao.
  3. Dentro de cada ilha: crescimento tipo Prim/MST (sempre gruda o
     nao-visitado mais proximo de QUALQUER linha ja pega), cortado em partes
     de tamanho equilibrado (poucas partes, usando a folga ate o maximo).
  4. Fusao de partes pequenas (dentro da ilha) e de fragmentos minusculos
     (ilhas isoladas de poucas linhas, cruzando fronteira de ilha).
  5. Suavizacao de fronteira: linha migra se a maioria das vizinhas reais
     pertence a outra parte (limpa ruido, ameniza desequilibrio de borda).

Uso:
    python classificar_partes.py <shapefile_linhas.shp> <shapefile_saida.shp> [tipo] [alvo_mb] [max_mb] [min_mb] [max_dist_m]

O shapefile de entrada precisa ter CLIENT_NAM / FARM_NAME (FIELD_NAME e
sobrescrito com o resultado da classificacao).
"""

import heapq
import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import MultiPoint, box
from shapely.strtree import STRtree

warnings.filterwarnings("ignore")

# limiares pra sinalizar "precisa revisao manual" no relatorio de qualidade --
# provisorios, calibrados so pela faixa observada nas 4 fazendas validadas
# visualmente na ferramenta interativa (10738/10072/10003/10471); ajustar
# conforme mais fazendas forem revisadas e o padrao real ficar mais claro.
COMPACIDADE_LIMIAR = 3.0
DESEQUILIBRIO_CV_LIMIAR = 40.0

BYTES_POR_PONTO = 45.3  # calibrado empiricamente (ver prep_visualizacao_partes.py)
RAIO_VIZINHANCA_M = 20.0  # mesmo raio validado na ferramenta interativa
MAX_VIZINHOS = 12

ALVO_MB_DEFAULT = 1.3
MAX_MB_DEFAULT = 2.0
MIN_MB_DEFAULT = 0.7
MAX_DIST_DEFAULT = 4.0

# limiar pra fundir fragmento ATRAVESSANDO fronteira de ilha (residuo bem pequeno mesmo) --
# deliberadamente bem menor que MIN_MB_DEFAULT, que so vale pra fusao DENTRO da mesma ilha
# (fundir entre ilhas quebra contiguidade/colheitabilidade, entao so faz sentido pra sobra
# realmente residual, nao pra ilhas de verdade que so nao bateram o minimo configurado).
MIN_MB_ENTRE_ILHAS_DEFAULT = 0.1

# pra ilhas pequenas-mas-nao-minusculas (entre o limiar acima e o alvo): so funde na
# vizinha mais proxima se a queda no desequilibrio (em pontos de CV%) for pelo menos
# esse fator vezes o aumento percentual no custo de corte -- mesma logica que o usuario
# validou manualmente no painel de qualidade da ferramenta interativa.
FATOR_DESEQUILIBRIO_CORTE_DEFAULT = 5.0


def _bbox_expandida(g, r):
    minx, miny, maxx, maxy = g.bounds
    return box(minx - r, miny - r, maxx + r, maxy + r)


def construir_vizinhanca(geoms) -> list:
    tree = STRtree(geoms)
    vizinhos = []
    for i, g in enumerate(geoms):
        idxs = tree.query(_bbox_expandida(g, RAIO_VIZINHANCA_M))
        cands = [j for j in idxs if j != i]
        dists = sorted(((geoms[i].distance(geoms[j]), int(j)) for j in cands), key=lambda t: t[0])
        dists = [t for t in dists if t[0] <= RAIO_VIZINHANCA_M][:MAX_VIZINHOS]
        if not dists:
            idxs2 = tree.query(_bbox_expandida(g, 500))
            cands2 = [j for j in idxs2 if j != i]
            dists = sorted(((geoms[i].distance(geoms[j]), int(j)) for j in cands2), key=lambda t: t[0])[:5]
        vizinhos.append([(j, round(d, 2)) for d, j in dists])
    return vizinhos


def detectar_ilhas(n: int, vizinhos: list, max_dist: float) -> list:
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[a] = b

    for i in range(n):
        for j, d in vizinhos[i]:
            if d <= max_dist:
                union(i, j)

    grupos = {}
    for i in range(n):
        grupos.setdefault(find(i), []).append(i)
    return list(grupos.values())


def _ponto_de_partida(ilha: list, cx: list, cy: list) -> int:
    """Extremo do eixo principal da ilha -- ponto de partida deterministico."""
    pts = np.array([[cx[i], cy[i]] for i in ilha])
    mean = pts.mean(axis=0)
    if len(ilha) < 2:
        return ilha[0]
    cov = np.cov((pts - mean).T)
    if cov.shape == () or np.isnan(cov).any():
        return ilha[0]
    autovals, autovecs = np.linalg.eigh(cov)
    eixo = autovecs[:, np.argmax(autovals)]
    proj = (pts - mean) @ eixo
    return ilha[int(np.argmin(proj))]


def mesclar_partes_pequenas(partes: list, vizinhos: list, bytes_: list, min_bytes: float) -> list:
    """Funde partes pequenas na vizinha mais proxima DENTRO da mesma ilha
    (usa o grafo de vizinhanca real, nao cruza pra outras ilhas)."""
    partes = [set(p) for p in partes]
    mudou = True
    while mudou and len(partes) > 1:
        mudou = False
        part_of = {}
        for k, p in enumerate(partes):
            for i in p:
                part_of[i] = k
        for k in range(len(partes)):
            tam = sum(bytes_[i] for i in partes[k])
            if tam >= min_bytes:
                continue
            melhor_j, melhor_d = None, float("inf")
            for i in partes[k]:
                for j, d in vizinhos[i]:
                    jp = part_of.get(j)
                    if jp is not None and jp != k and d < melhor_d:
                        melhor_d, melhor_j = d, jp
            if melhor_j is None:
                candidatos = [(j, len(p)) for j, p in enumerate(partes) if j != k]
                if candidatos:
                    melhor_j = max(candidatos, key=lambda x: x[1])[0]
            if melhor_j is not None:
                partes[melhor_j] |= partes[k]
                del partes[k]
                mudou = True
                break
    return partes


def crescer_partes_isoladas(ilha: list, vizinhos: list, bytes_: list, cx: list, cy: list,
                             alvo_bytes: float, max_bytes: float, min_bytes: float) -> list:
    total_ilha = sum(bytes_[i] for i in ilha)
    n_partes = max(1, int(np.ceil(total_ilha / max_bytes)))
    target_por_parte = total_ilha / n_partes

    nao_atribuido = set(ilha)
    partes = []
    semente = _ponto_de_partida(ilha, cx, cy)

    while nao_atribuido:
        eh_ultima = len(partes) == n_partes - 1

        parte = {semente}
        nao_atribuido.discard(semente)
        bytes_atual = bytes_[semente]

        melhor_dist = {}
        heap = []

        def atualiza_fronteira(no):
            for j, d in vizinhos[no]:
                if j not in nao_atribuido:
                    continue
                if j not in melhor_dist or d < melhor_dist[j]:
                    melhor_dist[j] = d
                    heapq.heappush(heap, (d, j))

        atualiza_fronteira(semente)

        limite = max_bytes if eh_ultima else target_por_parte
        while nao_atribuido and bytes_atual < limite:
            melhor = None
            while heap:
                d, j = heapq.heappop(heap)
                if j not in nao_atribuido:
                    continue
                if d != melhor_dist.get(j):
                    continue
                melhor = j
                break
            if melhor is None:
                break
            del melhor_dist[melhor]
            parte.add(melhor)
            nao_atribuido.discard(melhor)
            bytes_atual += bytes_[melhor]
            atualiza_fronteira(melhor)

        partes.append(parte)
        if not nao_atribuido:
            break

        prox = None
        while heap:
            d, j = heapq.heappop(heap)
            if j not in nao_atribuido:
                continue
            if d != melhor_dist.get(j):
                continue
            prox = j
            break
        semente = prox if prox is not None else next(iter(nao_atribuido))

    return mesclar_partes_pequenas(partes, vizinhos, bytes_, min_bytes)


def calcular_cv(partes: list, bytes_: list) -> float:
    """Coeficiente de variacao (%) dos tamanhos das partes -- 0% = todas do mesmo tamanho."""
    tamanhos = [sum(bytes_[i] for i in p) for p in partes if len(p) > 0]
    if not tamanhos:
        return 0.0
    media = sum(tamanhos) / len(tamanhos)
    if media == 0:
        return 0.0
    variancia = sum((t - media) ** 2 for t in tamanhos) / len(tamanhos)
    return (variancia ** 0.5) / media * 100


def calcular_custo_corte(partes: list, vizinhos: list, n: int) -> float:
    """Soma das distancias reais entre linhas vizinhas que cairam em partes diferentes."""
    part_of = [None] * n
    for k, p in enumerate(partes):
        for i in p:
            part_of[i] = k
    custo = 0.0
    for i in range(n):
        for j, d in vizinhos[i]:
            if part_of[j] is not None and part_of[j] != part_of[i]:
                custo += d
    return custo / 2


def calcular_compacidade(partes: list, geoms: list, bytes_: list) -> float:
    """Indice isoperimetrico (perimetro^2 / 4*pi*area) do feixo convexo de cada
    parte -- 1.0 = formato arredondado ideal, quanto maior mais esparramada/
    irregular. Media ponderada pelo tamanho (bytes) de cada parte."""
    soma, peso_total = 0.0, 0.0
    for p in partes:
        if not p:
            continue
        pts = [pt for i in p for pt in geoms[i].coords]
        hull = MultiPoint(pts).convex_hull
        area, perimetro = hull.area, hull.length
        indice = (perimetro ** 2) / (4 * np.pi * area) if area > 1e-6 else 1.0
        peso = sum(bytes_[i] for i in p)
        soma += indice * peso
        peso_total += peso
    return soma / peso_total if peso_total > 0 else 0.0


def considerar_fusao_ilhas_pequenas(partes: list, eh_ilha_inteira: list, vizinhos: list, bytes_: list,
                                     cx: list, cy: list, n: int, alvo_bytes: float,
                                     fator_minimo: float = FATOR_DESEQUILIBRIO_CORTE_DEFAULT) -> list:
    """Ilha pequena-mas-nao-minuscula (inteira, nao fragmento de ilha maior), abaixo do
    alvo: testa fundir na parte vizinha mais proxima e so aceita se a queda no
    desequilibrio (CV%) for pelo menos `fator_minimo` vezes o aumento % no custo de
    corte -- avaliador objetivo em vez de limiar fixo de tamanho."""
    partes_dict = {i: set(p) for i, p in enumerate(partes)}
    tags = {i: eh_ilha_inteira[i] for i in range(len(partes))}

    candidatos = sorted(
        (k for k in partes_dict if tags[k] and sum(bytes_[i] for i in partes_dict[k]) < alvo_bytes),
        key=lambda k: sum(bytes_[i] for i in partes_dict[k]),
    )

    for k in candidatos:
        if k not in partes_dict:
            continue  # ja foi fundida numa iteracao anterior

        p_k = partes_dict[k]
        cxm = sum(cx[i] for i in p_k) / len(p_k)
        cym = sum(cy[i] for i in p_k) / len(p_k)
        melhor_j, melhor_d = None, float("inf")
        for j, p in partes_dict.items():
            if j == k:
                continue
            for i in p:
                d = ((cx[i] - cxm) ** 2 + (cy[i] - cym) ** 2) ** 0.5
                if d < melhor_d:
                    melhor_d, melhor_j = d, j
        if melhor_j is None:
            continue

        lista_atual = list(partes_dict.values())
        cv_antes = calcular_cv(lista_atual, bytes_)
        custo_antes = calcular_custo_corte(lista_atual, vizinhos, n)

        nova_j = partes_dict[melhor_j] | p_k
        lista_teste = [nova_j if idx == melhor_j else pp for idx, pp in partes_dict.items() if idx != k]
        cv_depois = calcular_cv(lista_teste, bytes_)
        custo_depois = calcular_custo_corte(lista_teste, vizinhos, n)

        queda_cv = cv_antes - cv_depois
        aumento_custo_pct = ((custo_depois - custo_antes) / custo_antes * 100) if custo_antes > 0 else 0.0

        aceita = queda_cv > 0 and (aumento_custo_pct <= 0 or queda_cv >= fator_minimo * aumento_custo_pct)
        if aceita:
            partes_dict[melhor_j] = nova_j
            del partes_dict[k]

    return list(partes_dict.values())


def mesclar_fragmentos_minusculos(partes: list, bytes_: list, cx: list, cy: list, min_bytes: float) -> list:
    """Funde fragmentos MUITO pequenos (ilhas isoladas de poucas linhas) na
    parte mais proxima por distancia real de centroide, mesmo cruzando
    fronteira de ilha -- pra residuo tao pequeno que nao vale isolar."""
    partes = [set(p) for p in partes]
    mudou = True
    while mudou and len(partes) > 1:
        mudou = False
        for k in range(len(partes)):
            tam = sum(bytes_[i] for i in partes[k])
            if tam >= min_bytes:
                continue
            cxm = sum(cx[i] for i in partes[k]) / len(partes[k])
            cym = sum(cy[i] for i in partes[k]) / len(partes[k])
            melhor_j, melhor_d = None, float("inf")
            for j, p in enumerate(partes):
                if j == k:
                    continue
                for i in p:
                    d = ((cx[i] - cxm) ** 2 + (cy[i] - cym) ** 2) ** 0.5
                    if d < melhor_d:
                        melhor_d, melhor_j = d, j
            if melhor_j is not None:
                partes[melhor_j] |= partes[k]
                del partes[k]
                mudou = True
                break
    return partes


def suavizar_fronteiras(partes: list, vizinhos: list, n: int, rounds: int = 2) -> list:
    """Cada linha migra pra parte da maioria das suas vizinhas reais --
    limpa ruido de fronteira e ameniza desequilibrio nas bordas."""
    part_of = [None] * n
    for k, p in enumerate(partes):
        for i in p:
            part_of[i] = k

    for _ in range(rounds):
        mudancas = 0
        for i in range(n):
            viz = vizinhos[i]
            if len(viz) < 3:
                continue
            contagem = {}
            for j, d in viz:
                contagem[part_of[j]] = contagem.get(part_of[j], 0) + 1
            melhor_parte, melhor_contagem = part_of[i], contagem.get(part_of[i], 0)
            for p, c in contagem.items():
                if c > melhor_contagem:
                    melhor_contagem, melhor_parte = c, p
            if melhor_parte != part_of[i] and melhor_contagem >= len(viz) * 0.6:
                part_of[i] = melhor_parte
                mudancas += 1
        if mudancas == 0:
            break

    novas = [set() for _ in partes]
    for i, p in enumerate(part_of):
        if p is not None:
            novas[p].add(i)
    return novas


def classificar_partes_bruto(gdf, alvo_mb: float = ALVO_MB_DEFAULT,
                              max_mb: float = MAX_MB_DEFAULT, min_mb: float = MIN_MB_DEFAULT,
                              max_dist_m: float = MAX_DIST_DEFAULT,
                              min_mb_entre_ilhas: float = MIN_MB_ENTRE_ILHAS_DEFAULT,
                              fator_desequilibrio_corte: float = FATOR_DESEQUILIBRIO_CORTE_DEFAULT,
                              verboso: bool = True) -> dict:
    """Roda o algoritmo e devolve as partes SEM o sort-por-tamanho final --
    mesma ordem que a ferramenta interativa (JS) usa, entao os indices batem
    1:1 com o que o usuario ve/edita la (necessario pra aplicar_correcoes.py
    conseguir reaplicar os overrides exportados de la corretamente).
    Quem so quer o resultado pronto pra salvar deve usar classificar_partes()."""
    utm = gdf.estimate_utm_crs()
    gdf_utm = gdf.to_crs(utm)
    geoms = list(gdf_utm.geometry)
    n = len(geoms)

    cx = [g.centroid.x for g in geoms]
    cy = [g.centroid.y for g in geoms]
    bytes_ = [len(g.coords) * BYTES_POR_PONTO for g in geoms]

    if verboso:
        print(f"  Calculando vizinhanca real ({n} linhas)...")
    vizinhos = construir_vizinhanca(geoms)

    ilhas = detectar_ilhas(n, vizinhos, max_dist_m)
    ilhas.sort(key=len, reverse=True)
    if verboso:
        print(f"  {len(ilhas)} ilha(s) detectada(s)")

    alvo_bytes, max_bytes, min_bytes = alvo_mb * 1_000_000, max_mb * 1_000_000, min_mb * 1_000_000

    partes = []
    eh_ilha_inteira = []
    for ilha in ilhas:
        sub_partes = crescer_partes_isoladas(ilha, vizinhos, bytes_, cx, cy, alvo_bytes, max_bytes, min_bytes)
        inteira = len(sub_partes) == 1  # a ilha nao precisou ser dividida em mais de 1 parte
        for sp in sub_partes:
            partes.append(sp)
            eh_ilha_inteira.append(inteira)

    n_antes = len(partes)
    partes = considerar_fusao_ilhas_pequenas(partes, eh_ilha_inteira, vizinhos, bytes_, cx, cy, n,
                                              alvo_bytes, fator_desequilibrio_corte)
    if len(partes) < n_antes and verboso:
        print(f"  Fusao por avaliador (desequilibrio vs. corte): {n_antes} -> {len(partes)} parte(s)")

    partes = mesclar_fragmentos_minusculos(partes, bytes_, cx, cy, min_mb_entre_ilhas * 1_000_000)
    partes = suavizar_fronteiras(partes, vizinhos, n)

    return {
        "partes": partes, "geoms": geoms, "vizinhos": vizinhos,
        "bytes_": bytes_, "cx": cx, "cy": cy, "n": n,
    }


def classificar_partes(gdf, tipo: str = "1L", alvo_mb: float = ALVO_MB_DEFAULT,
                        max_mb: float = MAX_MB_DEFAULT, min_mb: float = MIN_MB_DEFAULT,
                        max_dist_m: float = MAX_DIST_DEFAULT,
                        min_mb_entre_ilhas: float = MIN_MB_ENTRE_ILHAS_DEFAULT,
                        fator_desequilibrio_corte: float = FATOR_DESEQUILIBRIO_CORTE_DEFAULT):
    bruto = classificar_partes_bruto(gdf, alvo_mb, max_mb, min_mb, max_dist_m,
                                      min_mb_entre_ilhas, fator_desequilibrio_corte)
    partes, geoms, vizinhos, bytes_, n = (
        bruto["partes"], bruto["geoms"], bruto["vizinhos"], bruto["bytes_"], bruto["n"]
    )

    field_names = [None] * n
    tamanhos_finais = []
    partes_ordenadas = sorted(partes, key=len, reverse=True)
    for idx, parte in enumerate(partes_ordenadas, start=1):
        nome = f"{tipo}-{idx}"
        for i in parte:
            field_names[i] = nome
        tamanhos_finais.append((nome, len(parte), sum(bytes_[i] for i in parte)))

    compacidade = calcular_compacidade(partes_ordenadas, geoms, bytes_)
    desequilibrio_cv = calcular_cv(partes_ordenadas, bytes_)
    custo_corte = calcular_custo_corte(partes_ordenadas, vizinhos, n)

    relatorio = {
        "tipo": tipo,
        "n_linhas": n,
        "n_partes": len(partes_ordenadas),
        "total_mb": round(sum(bytes_) / 1_000_000, 3),
        "compacidade_media": round(compacidade, 3),
        "desequilibrio_cv_pct": round(desequilibrio_cv, 1),
        "custo_corte_km": round(custo_corte / 1000, 3),
        "precisa_revisao": bool(
            compacidade > COMPACIDADE_LIMIAR or desequilibrio_cv > DESEQUILIBRIO_CV_LIMIAR
        ),
        "limiares": {
            "compacidade_max": COMPACIDADE_LIMIAR,
            "desequilibrio_cv_max_pct": DESEQUILIBRIO_CV_LIMIAR,
        },
        "partes": [
            {"nome": nome, "n_linhas": n_linhas, "tamanho_mb": round(tam / 1_000_000, 3)}
            for nome, n_linhas, tam in tamanhos_finais
        ],
    }
    return field_names, tamanhos_finais, relatorio


def main(shp_in: str, shp_out: str, tipo: str = "1L", alvo_mb: float = ALVO_MB_DEFAULT,
         max_mb: float = MAX_MB_DEFAULT, min_mb: float = MIN_MB_DEFAULT, max_dist_m: float = MAX_DIST_DEFAULT):
    gdf = gpd.read_file(shp_in)

    field_names, tamanhos, relatorio = classificar_partes(gdf, tipo=tipo, alvo_mb=alvo_mb, max_mb=max_mb,
                                                min_mb=min_mb, max_dist_m=max_dist_m)

    gdf_wgs84 = gdf.to_crs(4326) if gdf.crs and gdf.crs.to_epsg() != 4326 else gdf.copy()
    gdf_wgs84["FIELD_NAME"] = field_names

    print(f"\n{len(tamanhos)} parte(s) geradas (alvo {alvo_mb}MB, max {max_mb}MB, min {min_mb}MB, distancia {max_dist_m}m):")
    for nome, n_linhas, tamanho in tamanhos:
        print(f"  {nome}: {n_linhas} linha(s), {tamanho/1_000_000:.3f}MB")

    print(
        f"\nQualidade: compacidade={relatorio['compacidade_media']}  "
        f"desequilibrio={relatorio['desequilibrio_cv_pct']}%  "
        f"custo_corte={relatorio['custo_corte_km']}km"
    )
    if relatorio["precisa_revisao"]:
        print("  ATENCAO: fora dos limiares -- recomenda revisao manual na ferramenta interativa.")

    gdf_wgs84.to_file(shp_out)
    print(f"\nShapefile classificado gerado: {shp_out}")

    relatorio_path = Path(shp_out).with_name(Path(shp_out).stem + "_qualidade.json")
    relatorio_path.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Relatorio de qualidade gerado: {relatorio_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python classificar_partes.py <shapefile_linhas.shp> <shapefile_saida.shp> "
              "[tipo] [alvo_mb] [max_mb] [min_mb] [max_dist_m]")
        sys.exit(1)
    tipo = sys.argv[3] if len(sys.argv) > 3 else "1L"
    alvo_mb = float(sys.argv[4]) if len(sys.argv) > 4 else ALVO_MB_DEFAULT
    max_mb = float(sys.argv[5]) if len(sys.argv) > 5 else MAX_MB_DEFAULT
    min_mb = float(sys.argv[6]) if len(sys.argv) > 6 else MIN_MB_DEFAULT
    max_dist_m = float(sys.argv[7]) if len(sys.argv) > 7 else MAX_DIST_DEFAULT
    main(sys.argv[1], sys.argv[2], tipo, alvo_mb, max_mb, min_mb, max_dist_m)
