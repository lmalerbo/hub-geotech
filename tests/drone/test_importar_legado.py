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
