import io
import zipfile

import pytest
import shapefile
from shapely.geometry import box, mapping

from paralelismo.analise import (analisar_fazenda, classe, exportar_shapefiles, mes_execucao, para_utm,
                                 sem_trabalho, talhoes_de_geojson)


def linhas(n, espacamento, frota='64086', data='2026-10-03', y0=0.0, comprimento=200.0):
    return [{'frota': frota, 'data': data,
             'coords': [[d / 2, y0 + k * espacamento] for d in range(int(comprimento * 2) + 1)]}
            for k in range(n)]


TALHOES = {
    1: box(0, -5, 15, 30),        # só a amostra de x = 10 → 14 amostras → insuficiente
    2: box(15, -5, 250, 30),      # x = 20..190 → 18 × 14 = 252
    3: box(0, 95, 250, 130),      # passadas a 3,20 m em y0 = 100 → 266, todas acima
}


def test_classe_nos_limites():
    assert [classe(e) for e in (2.89, 2.90, 3.10, 3.11)] == ['abaixo', 'aderente', 'aderente', 'acima']


def test_para_utm_31983():
    (x, y), = para_utm([(-22.0, -48.0)])
    assert x == pytest.approx(190234.95, abs=0.01) and y == pytest.approx(7564133.21, abs=0.01)


def test_talhoes_de_geojson_converte_para_31983():
    fc = {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {'talhao': 7},
         'geometry': mapping(box(-48.001, -22.001, -47.999, -21.999))}]}
    t = talhoes_de_geojson(fc)
    assert list(t) == [7] and t[7].bounds[0] > 100000 and t[7].area == pytest.approx(45809, rel=0.01)


def test_analisar_fazenda_por_talhao():
    r = analisar_fazenda(linhas(8, 3.00) + linhas(8, 3.20, frota='PLANT CANA', y0=100.0), TALHOES)
    assert (r['pll_total'], r['pll_aderentes']) == (532, 266)
    assert (r['amostras'], r['aderentes'], r['acima'], r['abaixo'], r['fora_talhao']) == (532, 266, 266, 0, 0)
    t = {x['talhao_num']: x for x in r['talhoes']}
    assert (t[1]['amostras'], t[1]['insuficiente']) == (14, True)
    assert (t[2]['amostras'], t[2]['aderentes'], t[2]['insuficiente'], t[2]['frotas']) == (252, 252, False, ['64086'])
    assert (t[3]['acima'], t[3]['media_m'], t[3]['frotas']) == (266, 3.2, ['PLANT CANA'])
    assert {f['frota']: f['aderentes'] for f in r['frotas']} == {'64086': 266, 'PLANT CANA': 0}
    assert r['linhas_usadas'] == 16 and len(r['pontos']) == 532


def test_amostra_fora_de_talhao():
    r = analisar_fazenda(linhas(8, 3.00), {2: box(15, -5, 250, 30)})
    assert (r['pll_total'], r['amostras'], r['fora_talhao']) == (266, 252, 14)


def test_mes_de_execucao_pelas_amostras():
    ls = linhas(8, 3.00)
    for l in ls[6:]:
        l['data'] = '2026-09-20'      # 57 amostras em set, 209 em out
    assert analisar_fazenda(ls, TALHOES)['mes'] == '2026-10-01'
    assert mes_execucao({'2026-09-20': 300, '2026-10-01': 100, '2026-10-02': 250}) == '2026-10-01'
    assert mes_execucao({}) is None


def test_sem_trabalho():
    assert sem_trabalho(7200, 300) is True       # 2 h de trilha, 4% trabalhando
    assert sem_trabalho(7200, 3000) is False
    assert sem_trabalho(1800, 0) is False        # trilha curta não avisa


def test_fazenda_vazia():
    r = analisar_fazenda([], TALHOES)
    assert (r['pll_total'], r['amostras'], r['mes'], r['talhoes']) == (0, 0, None, [])


def test_exportar_shapefiles(tmp_path):
    ls = linhas(8, 3.00)
    r = analisar_fazenda(ls, TALHOES)
    z = zipfile.ZipFile(io.BytesIO(exportar_shapefiles(r, ls, '10233_torta')))
    nomes = set(z.namelist())
    for base in ('10233_torta_Amostras', '10233_torta_Linhas'):
        assert {f'{base}.{e}' for e in ('shp', 'shx', 'dbf', 'prj', 'cpg')} <= nomes
    z.extractall(tmp_path)
    am = shapefile.Reader(str(tmp_path / '10233_torta_Amostras'))
    assert len(am) == 266
    assert [f[0] for f in am.fields[1:]] == ['Talhao', 'Aderencia', 'Frota', 'Espac']
    assert am.record(0)['Aderencia'] == 'aderente'
    li = shapefile.Reader(str(tmp_path / '10233_torta_Linhas'))
    assert len(li) == 8 and [f[0] for f in li.fields[1:]] == ['Frota', 'Data']
    assert 'SIRGAS_2000_UTM_Zone_23S' in z.read('10233_torta_Amostras.prj').decode()
