from shapely.geometry import LineString

from paralelismo.pipeline import cle, limpar, lsfp, pll_amostras, qbd


def passadas(n, espacamento, comprimento=200.0, x0=0.0, y0=0.0):
    """n passadas retas paralelas, com um ponto a cada 0,5 m."""
    return [LineString([(x0 + d / 2, y0 + k * espacamento) for d in range(int(comprimento * 2) + 1)])
            for k in range(n)]


def contagem(linhas):
    a = pll_amostras(linhas)
    aderentes = sum(1 for x in a if 2.90 <= x.espacamento <= 3.10)
    acima = sum(1 for x in a if x.espacamento > 3.10)
    return len(a), aderentes, acima, len(a) - aderentes - acima


def test_espacamento_ideal_tudo_aderente():
    # 8 passadas de 200 m: 19 amostras por lado, 14 lados com vizinha
    assert contagem(passadas(8, 3.00)) == (266, 266, 0, 0)


def test_espacamento_largo_e_estreito():
    assert contagem(passadas(8, 3.20)) == (266, 0, 266, 0)
    assert contagem(passadas(8, 2.80)) == (266, 0, 0, 266)


def test_limpar_mantem_passadas_boas():
    assert len(limpar(passadas(8, 3.00))) == 8


def test_limpar_tira_empilhada():
    linhas = passadas(8, 3.00) + [LineString([(20, 3.3), (150, 3.3)])]
    limpas = limpar(linhas)
    assert len(limpas) == 8 and all(l.length == 200.0 for l in limpas)


def test_limpar_tira_cruzamento():
    limpas = limpar(passadas(8, 3.00) + [LineString([(100, -10), (100, 40)])])
    assert len(limpas) == 8 and not any(l.length == 50 for l in limpas)


def test_limpar_tira_isolada():
    assert len(limpar(passadas(8, 3.00) + [LineString([(500, 500), (600, 500)])])) == 8


def test_lsfp_quebra_no_salto_e_qbd_corta_manobra():
    assert [round(l.length) for l in lsfp({'f': [(0, 0), (5, 0), (30, 0), (35, 0)]}, max_dist=10.0)] == [5, 5]
    ida = [(d / 2, 0.0) for d in range(401)]
    volta = [(200 - d / 2, 3.0) for d in range(401)]
    linhas = cle(qbd(lsfp({'f': ida + [(201.5, 1.5)] + volta}, max_dist=10.0), min_angle_deg=160.0),
                 min_length=10.0)
    assert [round(l.length) for l in linhas] == [200, 200]
