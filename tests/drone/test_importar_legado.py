import pytest
import pandas as pd

from drone.importar_legado import classe_do_legado, selecionar_obstaculos, selecionar_projetos


def _cat(linhas):
    colunas = ['cod_fazenda', 'categoria', 'subtipo', 'safra', 'revisao', 'arquivo', 'modificado_em', 'caminho']
    return pd.DataFrame(linhas, columns=colunas)


def test_projeto_mais_recente_por_fazenda_e_tipo():
    c = _cat([
        ['10156', 'Aplicação', 'Normal', '2024-2025', 'Rev0', 'a.shp', '2024-05-01', 'A'],
        ['10156', 'Aplicação', 'Normal', '2026-2027', 'Rev0', 'b.shp', '2026-01-01', 'B'],
        ['10156', 'Aplicação', 'Normal', '2026-2027', 'Rev1', 'c.shp', '2025-12-01', 'C'],
        ['10156', 'Aplicação', 'Catação', '2023-2024', 'Rev2', 'd.shp', '2023-06-01', 'D'],
        ['10156', 'Aplicação', 'Experimento', '2026-2027', 'Rev5', 'e.shp', '2026-06-01', 'E'],
        ['10156', 'Aplicação', 'Não identificado', '2026-2027', 'Rev9', 'f.shp', '2026-06-01', 'F'],
    ])
    s = selecionar_projetos(c)
    assert sorted(zip(s['subtipo'], s['caminho'])) == [('Catação', 'D'), ('Normal', 'C')]


def test_classe_do_legado():
    base = {'categoria': 'Restrição', 'subtipo': 'Buffer 15 m', 'arquivo': 'restricoes15m.shp'}
    assert classe_do_legado(pd.Series(base)) == 15
    assert classe_do_legado(pd.Series({**base, 'subtipo': 'Buffer 200 m', 'arquivo': 'x.shp'})) is None
    assert classe_do_legado(pd.Series({'categoria': 'Obstáculo', 'subtipo': 'Árvores', 'arquivo': 'Arvores.shp'})) == 15
    assert classe_do_legado(pd.Series({'categoria': 'Obstáculo', 'subtipo': 'Rede elétrica', 'arquivo': 'Rede.shp'})) == 25
    assert classe_do_legado(pd.Series({'categoria': 'Obstáculo', 'subtipo': 'Rede elétrica', 'arquivo': 'Alta tensão.shp'})) == 50
    assert classe_do_legado(pd.Series({'categoria': 'Obstáculo', 'subtipo': 'Sede', 'arquivo': 'Sede.shp'})) == 50
    assert classe_do_legado(pd.Series({'categoria': 'Obstáculo', 'subtipo': 'Obstáculos', 'arquivo': 'obstaculos.shp'})) is None


def test_obstaculos_do_grupo_mais_recente_por_classe():
    c = _cat([
        ['10008', 'Restrição', 'Buffer 15 m', '2024-2025', 'Rev1', 'restricoes15m.shp', '2024-08-09', 'VELHO15'],
        ['10008', 'Restrição', 'Buffer 15 m', '2024-2025', 'Rev3', 'restricoes15m.shp', '2024-08-09', 'NOVO15'],
        ['10008', 'Obstáculo', 'Árvores', '2024-2025', 'Rev3', 'Arvores.shp', '2024-08-09', 'ARV'],
        ['10008', 'Restrição', 'Buffer 50 m', '2024-2025', 'Rev1', 'restricoes50m.shp', '2024-08-09', 'SO50'],
    ])
    s = selecionar_obstaculos(c)
    assert sorted(s[(10008, 15)]) == ['ARV', 'NOVO15']
    assert s[(10008, 50)] == ['SO50']


def test_safra_ou_revisao_vazias_contam_como_mais_antigas():
    c = _cat([
        ['10156', 'Aplicação', 'Normal', None, None, 'a.shp', '2026-09-01', 'SEM_SAFRA'],
        ['10156', 'Aplicação', 'Normal', '2024-2025', 'Rev0', 'b.shp', '2024-01-01', 'COM_SAFRA'],
    ])
    c = c.astype(object).where(c.notna(), float('nan'))
    assert selecionar_projetos(c)['caminho'].tolist() == ['COM_SAFRA']


def test_area_antiga_pelo_nome_do_campo():
    from drone.importar_legado import area_antiga
    assert area_antiga({'SECAO': 10624, 'Taxa l/ha': 10, 'Área Apli': 18.91}) == 18.91
    assert area_antiga({'COD': 10624, 'aplicavel': 5.5}) == 5.5
    assert area_antiga({'id': 1, 'SECAO': 10624}) is None


def test_crs_do_legado_sem_prj_pela_faixa_das_coordenadas():
    from drone.importar_legado import crs_pela_faixa
    assert crs_pela_faixa((-47.7, -21.3, -47.6, -21.2)) == 4326
    assert crs_pela_faixa((200000, 7550000, 210000, 7560000)) == 31983
    assert crs_pela_faixa((0, 0, 10, 10)) is None   # nem graus do Brasil, nem UTM 23S: não adivinha
    assert crs_pela_faixa((5_000_000, 0, 5_000_100, 10)) is None


def test_safra_curta():
    from drone.importar_legado import safra_curta
    assert safra_curta('2024-2025') == '24/25'
    assert safra_curta(None) is None


def _base_dois_talhoes():
    import geopandas as gpd
    from shapely.geometry import box
    return gpd.GeoDataFrame({'TALHAO': [1, 2], 'AREA_PROD': [1.0, 1.0]},
                            geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100)], crs=31983)


def test_recorte_legado_mantem_a_geometria_antiga_e_reparte_por_talhao():
    from shapely.geometry import MultiPolygon, box
    from drone.importar_legado import recorte_legado
    area = MultiPolygon([box(50, 0, 150, 100)])            # meio talhão 1 + meio talhão 2
    r = recorte_legado(_base_dois_talhoes(), area)
    assert r.aplicacao_ha == pytest.approx(1.0)
    assert [t['aplicavel_ha'] for t in r.por_talhao] == pytest.approx([0.5, 0.5])
    assert r.area_total_ha == pytest.approx(2.0)


def test_divergencia_com_a_base_atual():
    from shapely.geometry import MultiPolygon, box
    from drone.importar_legado import divergencia
    # 1/4 da área antiga caiu fora dos talhões de hoje; cobre 3/4 de 1 dos 2 ha
    d = divergencia(_base_dois_talhoes(), MultiPolygon([box(-25, 0, 75, 100)]))
    assert d['fora_da_base_pct'] == pytest.approx(25.0)
    assert d['cobertura_base_pct'] == pytest.approx(50.0)     # talhão 1 coberto (75%), talhão 2 não


def test_normal_com_muitos_obstaculos_ainda_cobre_a_fazenda():
    from shapely.geometry import MultiPolygon, box
    from drone.importar_legado import divergencia
    # Normal da fazenda inteira com 40% de cada talhão tirado por obstáculos
    area = MultiPolygon([box(0, 0, 100, 60), box(100, 0, 200, 60)])
    assert divergencia(_base_dois_talhoes(), area)['cobertura_base_pct'] == pytest.approx(100.0)


def _base_tres_talhoes():
    import geopandas as gpd
    from shapely.geometry import box
    return gpd.GeoDataFrame({'TALHAO': [1, 2, 3], 'AREA_PROD': [1.0, 1.0, 1.0]},
                            geometry=[box(0, 0, 100, 100), box(100, 0, 200, 100), box(200, 0, 300, 100)], crs=31983)


def test_consolidar_pega_o_projeto_mais_recente_de_cada_talhao():
    from shapely.geometry import box
    from drone.importar_legado import consolidar
    antigo = box(0, 0, 200, 100)                 # Rev0: talhões 1 e 2 inteiros
    novo = box(100, 0, 300, 50)                  # Rev1: metade de baixo dos talhões 2 e 3
    area, usados = consolidar(_base_tres_talhoes(), [antigo, novo], limiar=0.3)
    assert area.area == pytest.approx(100 * 100 + 100 * 50 + 100 * 50)   # t1 do antigo; t2 e t3 do novo
    assert usados == {0, 1}


def test_consolidar_descarta_o_que_ficou_fora_dos_talhoes_de_hoje():
    from shapely.geometry import box
    from drone.importar_legado import consolidar
    area, _ = consolidar(_base_tres_talhoes(), [box(-50, 0, 100, 100)], limiar=0.3)
    assert area.area == pytest.approx(100 * 100)


def test_consolidar_catacao_usa_o_levantamento_mais_recente_que_tem_mancha_no_talhao():
    from shapely.geometry import box
    from drone.importar_legado import consolidar
    antigo = box(10, 10, 20, 20).union(box(210, 10, 220, 20))   # manchas nos talhões 1 e 3
    novo = box(110, 10, 115, 15)                                 # só no talhão 2
    area, usados = consolidar(_base_tres_talhoes(), [antigo, novo], limiar=0)
    assert area.area == pytest.approx(100 + 25 + 100)
    assert usados == {0, 1}


def test_consolidar_normal_ignora_projeto_que_so_encosta_no_talhao():
    from shapely.geometry import box
    from drone.importar_legado import consolidar
    antigo = box(0, 0, 100, 100)                 # talhão 1 inteiro
    novo = box(95, 0, 200, 100)                  # talhão 2 + 5% do talhão 1
    area, _ = consolidar(_base_tres_talhoes(), [antigo, novo], limiar=0.3)
    assert area.area == pytest.approx(100 * 100 + 100 * 100)     # talhão 1 continua vindo do antigo


def test_projetos_por_fazenda_ordena_do_mais_antigo_ao_mais_novo():
    from drone.importar_legado import projetos_por_fazenda
    c = _cat([
        ['10156', 'Aplicação', 'Normal', '2025-2026', 'Rev1', 'b.shp', '2025-06-01', 'B'],
        ['10156', 'Aplicação', 'Normal', '2024-2025', 'Rev3', 'a.shp', '2024-09-01', 'A'],
        ['10156', 'Aplicação', 'Catação', '2024-2025', 'Rev0', 'c.shp', '2024-03-01', 'C'],
        ['10156', 'Aplicação', 'Experimento', '2026-2027', 'Rev0', 'e.shp', '2026-06-01', 'E'],
    ])
    g = projetos_por_fazenda(c)
    assert [l['caminho'] for l in g[(10156, 'normal')]] == ['A', 'B']
    assert [l['caminho'] for l in g[(10156, 'catacao')]] == ['C']
    assert (10156, 'experimento') not in g
