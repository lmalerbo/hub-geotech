"""hub.drone_projetos_v: ha de aplicação e safra por projeto vigente (spec D4)."""


def revisao(banco, cod, documento='normal', criado='2026-06-10 12:00-03', area=None, safra=None, vigente=True):
    pid = banco.execute("insert into hub.projetos (modulo_id, tipo, cod_faz, nome) values ('drone','individual',%s,'P') "
                        "returning id", (cod,)).fetchone()[0]
    return banco.execute("insert into hub.projeto_revisoes (projeto_id, documento, numero, vigente, criado_em, "
                         "area_aplicacao_ha, safra) values (%s,%s,0,%s,%s,%s,%s) returning id",
                         (pid, documento, vigente, criado, area, safra)).fetchone()[0]


def publicada(banco, rev, ha):
    sol = banco.execute("insert into hub.drone_solicitacoes (status, revisao_id) values ('ok', %s) returning id", (rev,)).fetchone()[0]
    banco.execute("insert into hub.drone_geracoes (solicitacao_id, status, resumo) values (%s, 'publicada', %s)",
                  (sol, f'{{"aplicacao_ha": {ha}}}'))


def linha(banco, rev):
    return banco.execute('select area_aplicacao_ha::float, safra, origem from hub.drone_projetos_v where revisao_id = %s',
                         (rev,)).fetchone()


def test_safra_vira_em_abril(banco):
    assert banco.execute("select hub.safra_de('2026-04-01'), hub.safra_de('2026-03-31')").fetchone() == ('26/27', '25/26')


def test_projeto_do_hub_usa_resumo_da_geracao(banco, fazenda):
    rev = revisao(banco, fazenda(1), criado='2026-09-02 10:00-03')
    publicada(banco, rev, 37.4)
    assert linha(banco, rev) == (37.4, '26/27', 'hub')


def test_projeto_do_legado_usa_colunas(banco, fazenda):
    rev = revisao(banco, fazenda(1), area=120.5, safra='24/25')
    assert linha(banco, rev) == (120.5, '24/25', 'legado')


def test_sem_dado_aparece_com_nulos(banco, fazenda):
    rev = revisao(banco, fazenda(1))
    assert linha(banco, rev) == (None, None, 'sem_dado')


def test_revisao_nao_vigente_fica_fora(banco, fazenda):
    rev = revisao(banco, fazenda(1), area=10, safra='26/27', vigente=False)
    assert linha(banco, rev) is None


def test_geracao_descartada_nao_conta(banco, fazenda):
    rev = revisao(banco, fazenda(1))
    sol = banco.execute("insert into hub.drone_solicitacoes (status, revisao_id) values ('ok', %s) returning id", (rev,)).fetchone()[0]
    banco.execute("insert into hub.drone_geracoes (solicitacao_id, status, resumo) values (%s,'descartada','{\"aplicacao_ha\": 5}')", (sol,))
    assert linha(banco, rev) == (None, None, 'sem_dado')
