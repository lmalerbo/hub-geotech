"""Agregação do paralelismo por fazenda, talhão e frota (parâmetros fixos, iguais ao validado no base-op)."""
import collections
import io
import zipfile

import pyproj
import shapefile
from shapely.geometry import LineString, Point, shape
from shapely.strtree import STRtree

from paralelismo.pipeline import cle, limpar, lsfp, pll_amostras, qbd

LSFP_M, QBD_GRAUS, CLE_M, PASSO_PLL = 10.0, 160.0, 10.0, 10.0
IDEAL_MIN, IDEAL_MAX = 2.90, 3.10
IGNORA_MIN, IGNORA_MAX = 2.60, 3.40
MIN_AMOSTRAS_TALHAO = 25
SEM_TRABALHO_MIN_S, SEM_TRABALHO_FRACAO = 3600, 0.10

_PARA_UTM = pyproj.Transformer.from_crs(4326, 31983, always_xy=True)

PRJ_31983 = ('PROJCS["SIRGAS_2000_UTM_Zone_23S",GEOGCS["GCS_SIRGAS_2000",DATUM["D_SIRGAS_2000",'
             'SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],'
             'UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
             'PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",10000000.0],'
             'PARAMETER["Central_Meridian",-45.0],PARAMETER["Scale_Factor",0.9996],'
             'PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]')


def para_utm(pontos_latlon):
    if not pontos_latlon:
        return []
    xs, ys = _PARA_UTM.transform([lo for _, lo in pontos_latlon], [la for la, _ in pontos_latlon])
    return list(zip(xs, ys))


def linhas_do_grupo(pontos_xy):
    """LSFP -> QBD -> CLE dos pontos de uma frota numa fazenda, em ordem de gravação."""
    return cle(qbd(lsfp({'g': pontos_xy}, max_dist=LSFP_M), min_angle_deg=QBD_GRAUS), min_length=CLE_M)


def talhoes_de_geojson(fc):
    saida = {}
    for f in fc.get('features', []):
        g = shape(f['geometry'])
        g = _transformar(g)
        saida[int(f['properties']['talhao'])] = g if g.is_valid else g.buffer(0)
    return saida


def _transformar(g):
    from shapely.ops import transform
    return transform(lambda x, y, z=None: _PARA_UTM.transform(x, y), g)


def classe(espacamento):
    if espacamento < IDEAL_MIN:
        return 'abaixo'
    if espacamento > IDEAL_MAX:
        return 'acima'
    return 'aderente'


def mes_execucao(contagem):
    if not contagem:
        return None
    por_mes = collections.Counter()
    for data, n in contagem.items():
        por_mes[data[:7]] += n
    return por_mes.most_common(1)[0][0] + '-01'


def sem_trabalho(duracao_total_s, duracao_trabalho_s):
    return duracao_total_s >= SEM_TRABALHO_MIN_S and duracao_trabalho_s < SEM_TRABALHO_FRACAO * duracao_total_s


def analisar_fazenda(linhas, talhoes):
    geoms = [LineString(l['coords']) for l in linhas]
    limpas = {id(g) for g in limpar(geoms)}
    usadas = [(g, l) for g, l in zip(geoms, linhas) if id(g) in limpas]
    amostras = pll_amostras([g for g, _ in usadas], IGNORA_MIN, IGNORA_MAX, PASSO_PLL)

    nums = list(talhoes)
    polis = [talhoes[n] for n in nums]
    arvore = STRtree(polis) if polis else None

    def talhao_em(x, y):
        if arvore is None:
            return None
        p = Point(x, y)
        for i in arvore.query(p):
            if polis[i].contains(p):
                return nums[i]
        return None

    vazio = lambda: {'amostras': 0, 'aderentes': 0, 'acima': 0, 'abaixo': 0, 'soma': 0.0, 'frotas': set()}
    por_talhao = collections.defaultdict(vazio)
    por_frota = collections.defaultdict(lambda: {'amostras': 0, 'aderentes': 0})
    datas = collections.Counter()
    pontos, pll_aderentes, fora = [], 0, 0
    for a in amostras:
        linha = usadas[a.linha][1]
        cl = classe(a.espacamento)
        pll_aderentes += cl == 'aderente'
        num = talhao_em(a.x, a.y)
        pontos.append([a.x, a.y, a.x_vizinha, a.y_vizinha, round(a.espacamento, 3), cl, num, linha['frota']])
        if num is None:
            fora += 1
            continue
        t = por_talhao[num]
        t['amostras'] += 1
        t[cl + 's' if cl == 'aderente' else cl] += 1
        t['soma'] += a.espacamento
        t['frotas'].add(linha['frota'])
        f = por_frota[linha['frota']]
        f['amostras'] += 1
        f['aderentes'] += cl == 'aderente'
        datas[linha['data']] += 1

    talhoes_saida = [{'talhao_num': n, 'amostras': t['amostras'], 'aderentes': t['aderentes'],
                      'acima': t['acima'], 'abaixo': t['abaixo'],
                      'media_m': round(t['soma'] / t['amostras'], 3), 'frotas': sorted(t['frotas']),
                      'insuficiente': t['amostras'] < MIN_AMOSTRAS_TALHAO}
                     for n, t in sorted(por_talhao.items())]
    soma = lambda k: sum(t[k] for t in talhoes_saida)
    return {
        'pll_total': len(amostras), 'pll_aderentes': pll_aderentes,
        'amostras': soma('amostras'), 'aderentes': soma('aderentes'), 'acima': soma('acima'),
        'abaixo': soma('abaixo'), 'fora_talhao': fora, 'mes': mes_execucao(datas),
        'talhoes': talhoes_saida,
        'frotas': [{'frota': k, **v} for k, v in sorted(por_frota.items())],
        'linhas_usadas': len(usadas), 'pontos': pontos,
    }


def exportar_shapefiles(resultado, linhas, prefixo):
    """Zip com <prefixo>_Amostras (segmento amostra -> vizinha) e <prefixo>_Linhas (linhas antes do limpar)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        def gravar(nome, campos, linhas_geo, registros):
            shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
            w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYLINE, encoding='utf-8')
            for nome_campo, tipo, tam, dec in campos:
                w.field(nome_campo, tipo, size=tam, decimal=dec)
            for coords, reg in zip(linhas_geo, registros):
                w.line([coords])
                w.record(*reg)
            w.close()
            for ext, b in (('shp', shp), ('shx', shx), ('dbf', dbf)):
                z.writestr(f'{nome}.{ext}', b.getvalue())
            z.writestr(f'{nome}.prj', PRJ_31983)
            z.writestr(f'{nome}.cpg', 'UTF-8')

        pts = resultado['pontos']
        gravar(f'{prefixo}_Amostras', [('Talhao', 'N', 4, 0), ('Aderencia', 'C', 10, 0),
                                       ('Frota', 'C', 40, 0), ('Espac', 'N', 8, 3)],
               [[(p[0], p[1]), (p[2], p[3])] for p in pts],
               [(p[6] if p[6] is not None else -1, p[5], p[7], p[4]) for p in pts])
        gravar(f'{prefixo}_Linhas', [('Frota', 'C', 40, 0), ('Data', 'C', 10, 0)],
               [l['coords'] for l in linhas], [(l['frota'], l['data']) for l in linhas])
    return buf.getvalue()
