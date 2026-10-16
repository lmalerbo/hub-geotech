"""Migração dos Mapas de aplicação (spec 2026-10-16-mapas-aplicacao-aerea-design.md): cadastro de insumos,
mapa de aplicação aérea e aplicação de insumo com cópia de nome e unidade."""
import json


def _mapa(como, uid, operacao):
    return como(uid, 'insert into hub.corretivo_mapas (cod_faz, operacao) values (10001, %s) returning id', (operacao,))[0][0]


def _insumo(banco, nome):
    return banco.execute('select id from hub.insumos where nome = %s', (nome,)).fetchone()[0]


def _aplicar(como, uid, mapa, aplicacao, talhoes=(1,)):
    tal = [{'talhao_num': t, 'area_ha': 10 + t, 'area_editada': False} for t in talhoes]
    return como(uid, 'select hub.corretivo_aplicar(%s, %s::jsonb, %s::jsonb)', (mapa, json.dumps(aplicacao), json.dumps(tal)))


def test_insumos_iniciais_vem_do_arquivo_insumos_aviao(banco):
    linhas = banco.execute('select codigo, nome, unidade, dose_sugerida, ativo from hub.insumos order by nome').fetchall()
    assert len(linhas) == 34
    por_nome = {n: (c, u, float(d), a) for c, n, u, d, a in linhas}
    assert por_nome['INSETICIDA BOUVERIZ WP PR'] == (562297, 'KG', 0.1, True)
    assert por_nome['ADJUVANTE LIQUIDO OCHIMA'] == (500522, 'L', 0.25, True)      # sem o espaço do fim do arquivo
    assert por_nome['REGULADOR SUMITOMO PROGIB'][1:3] == ('KG', 0.008)
    assert all(n == n.strip() for n in por_nome)


def test_modulo_passa_a_se_chamar_mapas_de_aplicacao(banco):
    assert banco.execute("select nome from hub.modulos where id = 'corretivos'").fetchone()[0] == 'Mapas de aplicação'


def test_quem_usa_a_ferramenta_mantem_o_cadastro_e_quem_nao_usa_nao_ve(como, pessoa):
    sim, nao = pessoa(), pessoa(modulo=False)
    novo = como(sim, "insert into hub.insumos (nome, unidade, dose_sugerida) values ('INSETICIDA TESTE', 'L', 0.2) returning id")
    assert novo and novo[0] != 'ERRO'
    assert como(sim, "update hub.insumos set ativo = false where nome = 'INSETICIDA TESTE' returning ativo") == [(False,)]
    assert como(nao, 'select count(*) from hub.insumos') == [(0,)]
    assert como(nao, "insert into hub.insumos (nome, unidade) values ('X', 'L')")[0] == 'ERRO'


def test_unidade_so_L_ou_KG(como, pessoa):
    assert como(pessoa(), "insert into hub.insumos (nome, unidade) values ('INSUMO T', 'ml')")[0] == 'ERRO'


def test_aplicacao_aerea_copia_nome_e_unidade_e_aceita_dose_de_tres_casas(banco, como, pessoa):
    uid = pessoa()
    mapa = _mapa(como, uid, 'aerea')
    ins = _insumo(banco, 'REGULADOR SUMITOMO PROGIB')
    r = _aplicar(como, uid, mapa, {'tipo': 'insumo', 'insumo_id': ins, 'dose': 0.008, 'os': ' 9001 '})
    assert r and r[0] != 'ERRO', r
    linha = banco.execute('select tipo, insumo_id, insumo_nome, insumo_unidade, dose::float, os, calcario, dose_gesso '
                          'from hub.corretivo_aplicacoes where id = %s', (r[0][0],)).fetchone()
    assert linha == ('insumo', ins, 'REGULADOR SUMITOMO PROGIB', 'KG', 0.008, '9001', None, None)


def test_editar_o_cadastro_nao_muda_mapa_antigo(banco, como, pessoa):
    uid = pessoa()
    mapa = _mapa(como, uid, 'aerea')
    ins = _insumo(banco, 'INSETICIDA REVOLUX')
    apl = _aplicar(como, uid, mapa, {'tipo': 'insumo', 'insumo_id': ins, 'dose': 0.15, 'os': '9002'})[0][0]
    como(uid, "update hub.insumos set nome = 'INSETICIDA REVOLUX NOVO', unidade = 'KG' where id = %s", (ins,))
    assert banco.execute('select insumo_nome, insumo_unidade from hub.corretivo_aplicacoes where id = %s',
                         (apl,)).fetchone() == ('INSETICIDA REVOLUX', 'L')
    como(uid, "update hub.insumos set nome = 'INSETICIDA REVOLUX', unidade = 'L' where id = %s", (ins,))


def test_insumo_removido_nao_entra_em_mapa_novo(banco, como, pessoa):
    uid = pessoa()
    mapa = _mapa(como, uid, 'aerea')
    como(uid, "insert into hub.insumos (nome, unidade, ativo) values ('INSUMO REMOVIDO', 'L', false)")
    r = _aplicar(como, uid, mapa, {'tipo': 'insumo', 'insumo_id': _insumo(banco, 'INSUMO REMOVIDO'), 'dose': 1, 'os': '1'})
    assert r[0] == 'ERRO' and 'removido' in r[1]


def test_cada_tipo_de_mapa_so_aceita_o_seu_tipo_de_aplicacao(banco, como, pessoa):
    uid = pessoa()
    aereo, corretivo = _mapa(como, uid, 'aerea'), _mapa(como, uid, 'subsolagem')
    ins = _insumo(banco, 'FUNGICIDA PRIORI XTRA')
    r1 = _aplicar(como, uid, corretivo, {'tipo': 'insumo', 'insumo_id': ins, 'dose': 0.5, 'os': '1'})
    r2 = _aplicar(como, uid, aereo, {'tipo': 'calcario', 'calcario': 'dolomitico', 'dose': 2, 'os': '1'})
    assert r1[0] == 'ERRO' and r2[0] == 'ERRO'
    ok = _aplicar(como, uid, corretivo, {'tipo': 'calcario', 'calcario': 'dolomitico', 'dose': 2, 'os': '1'})
    assert ok[0] != 'ERRO', ok                                   # corretivo continua como antes


def test_duplicada_considera_o_insumo(banco, como, pessoa):
    uid = pessoa()
    mapa = _mapa(como, uid, 'aerea')
    a, b = _insumo(banco, 'INSETICIDA BOVETTUS'), _insumo(banco, 'FERTILIZANTE AMINOCORE BA')
    assert _aplicar(como, uid, mapa, {'tipo': 'insumo', 'insumo_id': a, 'dose': 0.15, 'os': '7'})[0] != 'ERRO'
    assert _aplicar(como, uid, mapa, {'tipo': 'insumo', 'insumo_id': b, 'dose': 0.15, 'os': '7'})[0] != 'ERRO'
    dup = _aplicar(como, uid, mapa, {'tipo': 'insumo', 'insumo_id': a, 'dose': 0.15, 'os': '7'})
    assert dup[0] == 'ERRO' and 'já tem esta aplicação' in dup[1]


def test_aplicacao_de_insumo_exige_insumo(como, pessoa):
    uid = pessoa()
    mapa = _mapa(como, uid, 'aerea')
    r = _aplicar(como, uid, mapa, {'tipo': 'insumo', 'dose': 1, 'os': '1'})
    assert r[0] == 'ERRO'
