"""Banco do Paralelismo: níveis, RLS e o ciclo enviar → publicar/recusar → excluir (spec §5 e decisões 2, 3 e 4)."""
import json
from pathlib import Path

import psycopg
import pytest

JA = 'select hub.paralelismo_ja_analisados(%s)'
PUBLICAR = 'select hub.paralelismo_publicar(%s)'
RECALCULAR = 'select hub.paralelismo_publicar(%s, %s::jsonb)'
RECUSAR = 'select hub.paralelismo_recusar(%s, %s)'
EXCLUIR = 'select hub.paralelismo_excluir(%s)'
LINHAS = 'select hub.paralelismo_linhas_vigentes(%s, %s, %s)'


def erro(r, trecho=''):
    assert r[0] == 'ERRO' and trecho in r[1], r


def vigente(banco, cod):
    r = banco.execute('select rodada_id, amostras from hub.paralelismo_analises where cod_faz=%s and vigente', (cod,)).fetchone()
    return r


def analise_id(banco, rid):
    return banco.execute('select id from hub.paralelismo_analises where rodada_id=%s', (rid,)).fetchone()[0]


def conta_linhas(banco, tabela, rid):
    return banco.execute(f'select count(*) from hub.{tabela} where rodada_id=%s', (rid,)).fetchone()[0]


def test_nivel_de_cada_conta(conta, como):
    for nivel in ('leitura', 'solicitante', 'editor', 'admin'):
        assert como(conta(nivel), 'select hub.paralelismo_nivel()') == [(nivel,)]
    assert como(conta(None), 'select hub.paralelismo_nivel()') == [(None,)]


def test_preparar_parte_reserva_id_sem_criar_rodada(banco, conta, como, enviar, cod_novo):
    sol = conta('solicitante')
    rid = como(sol, 'select hub.paralelismo_preparar_parte()')[0][0]
    assert banco.execute('select count(*) from hub.paralelismo_rodadas where id=%s', (rid,)).fetchone() == (0,)
    assert como(sol, 'select hub.paralelismo_preparar_parte(%s)', (rid,)) == [(rid,)]
    erro(como(sol, 'select hub.paralelismo_preparar_parte(%s)', (rid + 1000,)), 'rodada_invalida')
    erro(como(conta('leitura'), 'select hub.paralelismo_preparar_parte()'), 'Sem permissão')
    enviada = enviar(sol, cod_novo())
    erro(como(sol, 'select hub.paralelismo_preparar_parte(%s)', (enviada,)), 'rodada_ja_enviada')


def test_enviar_grava_tudo_como_pendente(banco, conta, enviar, cod_novo):
    cod = cod_novo()
    rid = enviar(conta('solicitante'), cod)
    assert banco.execute('select status, release_tag from hub.paralelismo_rodadas where id=%s', (rid,)).fetchone() == (
        'pendente', f'paralelismo-r{rid}')
    assert conta_linhas(banco, 'paralelismo_arquivos', rid) == 1 and conta_linhas(banco, 'paralelismo_linhas', rid) == 1
    assert banco.execute('select vigente, pll_total, fora_talhao from hub.paralelismo_analises where rodada_id=%s',
                         (rid,)).fetchone() == (False, 102, 2)
    assert banco.execute('select frotas from hub.paralelismo_talhoes where analise_id=%s',
                         (analise_id(banco, rid),)).fetchone() == (['64086'],)


def test_leitura_nao_envia(conta, como):
    erro(como(conta('leitura'), 'select hub.paralelismo_enviar(%s::jsonb)', ('{"rodada_id": 1, "analises": [{}]}',)),
         'Sem permissão')


def test_solicitante_nao_publica_nem_recusa(conta, como, enviar, cod_novo):
    sol = conta('solicitante')
    rid = enviar(sol, cod_novo())
    erro(como(sol, PUBLICAR, (rid,)), 'Só o editor')
    erro(como(sol, RECUSAR, (rid, 'motivo')), 'Só o editor')


def test_quem_ve_o_que(banco, conta, como, enviar, cod_novo):
    sol, outro, ed, lei = conta('solicitante'), conta('solicitante'), conta('editor'), conta('leitura')
    cod = cod_novo()
    rid = enviar(sol, cod)
    ver = 'select count(*) from hub.paralelismo_rodadas where id=%s'
    assert como(sol, ver, (rid,)) == [(1,)] and como(ed, ver, (rid,)) == [(1,)]
    assert como(outro, ver, (rid,)) == [(0,)] and como(lei, ver, (rid,)) == [(0,)]
    ana = 'select count(*) from hub.paralelismo_analises where rodada_id=%s'
    assert como(lei, ana, (rid,)) == [(0,)] and como(outro, ana, (rid,)) == [(0,)]

    como(ed, PUBLICAR, (rid,))
    assert como(lei, ver, (rid,)) == [(1,)] and como(lei, ana, (rid,)) == [(1,)]
    assert como(lei, 'select count(*) from hub.paralelismo_talhoes where analise_id=%s', (analise_id(banco, rid),)) == [(1,)]
    assert como(conta(None), ana, (rid,)) == [(0,)]
    # leitura vê o resultado, não as linhas nem os registros de arquivo
    assert como(lei, 'select count(*) from hub.paralelismo_linhas where rodada_id=%s', (rid,)) == [(0,)]
    assert como(lei, 'select count(*) from hub.paralelismo_arquivos where rodada_id=%s', (rid,)) == [(0,)]
    erro(como(lei, LINHAS, ('torta', cod, None)), 'Sem permissão')


def test_ninguem_escreve_direto_nas_tabelas(conta, como, enviar, cod_novo):
    ed = conta('editor')
    rid = enviar(ed, cod_novo())
    erro(como(ed, "update hub.paralelismo_rodadas set status='publicada' where id=%s", (rid,)))
    erro(como(ed, 'update hub.paralelismo_analises set vigente=true where rodada_id=%s', (rid,)))
    erro(como(ed, 'select hub.paralelismo_gravar_talhoes(1, %s::jsonb)', ('[]',)))


def test_ja_analisados_conta_pendente_e_publicada_nao_recusada(conta, como, enviar, cod_novo):
    ed = conta('editor')
    rid = enviar(ed, cod_novo(), shas=['pen1', 'pen2'])
    assert sorted(como(ed, JA, (['pen1', 'pen2', 'novo'],))[0][0]) == ['pen1', 'pen2']
    como(ed, PUBLICAR, (rid,))
    assert sorted(como(ed, JA, (['pen1', 'novo'],))[0][0]) == ['pen1']
    rec = enviar(ed, cod_novo(), shas=['rec1'])
    como(ed, RECUSAR, (rec, 'pasta errada'))
    assert como(ed, JA, (['rec1'],)) == [([],)]
    assert isinstance(enviar(ed, cod_novo(), shas=['rec1']), int)   # recusado pode voltar


def test_sha_repetido_falha_sem_gravar_nada(banco, conta, enviar, cod_novo):
    sol = conta('solicitante')
    enviar(sol, cod_novo(), shas=['rep1'])
    cod = cod_novo()
    erro(enviar(sol, cod, shas=['rep1', 'rep2']), 'arquivo_ja_analisado:rep1')
    assert banco.execute('select count(*) from hub.paralelismo_analises where cod_faz=%s', (cod,)).fetchone() == (0,)
    assert banco.execute("select count(*) from hub.paralelismo_arquivos where sha256='rep2'").fetchone() == (0,)


def test_publicar_troca_a_vigente(banco, conta, como, enviar, cod_novo):
    ed, cod = conta('editor'), cod_novo()
    r1 = enviar(ed, cod)
    assert vigente(banco, cod) is None
    assert como(ed, PUBLICAR, (r1,))[0][0]['fazendas'] == [{'operacao': 'torta', 'cod_faz': cod}]
    assert vigente(banco, cod) == (r1, 100)
    r2 = enviar(ed, cod, base=analise_id(banco, r1), amostras=200)
    como(ed, PUBLICAR, (r2,))
    assert vigente(banco, cod) == (r2, 200)
    erro(como(ed, PUBLICAR, (r2,)), 'rodada_nao_pendente')


def test_fora_de_ordem_exige_recalculo(banco, conta, como, enviar, cod_novo):
    ed, cod = conta('editor'), cod_novo()
    r1, r2 = enviar(ed, cod), enviar(ed, cod, amostras=150)   # as duas prévias sem vigente na fazenda
    como(ed, PUBLICAR, (r1,))
    erro(como(ed, PUBLICAR, (r2,)), f'recalculo_necessario:torta/{cod}')
    assert vigente(banco, cod) == (r1, 100)

    recalculo = [{'operacao': 'torta', 'cod_faz': cod, 'base_analise_id': analise_id(banco, r1), 'mes': '2026-10-01',
                  'amostras': 240, 'aderentes': 230, 'acima': 6, 'abaixo': 4, 'fora_talhao': 0, 'pll_total': 240,
                  'pll_aderentes': 230, 'amostras_url': 'https://x/nova',
                  'talhoes': [{'talhao_num': 2, 'amostras': 240, 'aderentes': 230, 'acima': 6, 'abaixo': 4,
                               'media_m': 3.0, 'frotas': ['64086', 'PLANT CANA']}]}]
    como(ed, RECALCULAR, (r2, json.dumps(recalculo)))
    assert vigente(banco, cod) == (r2, 240)
    assert banco.execute('select talhao_num, frotas from hub.paralelismo_talhoes where analise_id=%s',
                         (analise_id(banco, r2),)).fetchall() == [(2, ['64086', 'PLANT CANA'])]


def test_recalculo_de_fazenda_de_fora_recusa(conta, como, enviar, cod_novo):
    ed = conta('editor')
    rid = enviar(ed, cod_novo())
    erro(como(ed, RECALCULAR, (rid, json.dumps([{'operacao': 'torta', 'cod_faz': 11111}]))), 'recalculo_sem_analise')


def test_recusar_exige_motivo_e_nao_mexe_na_vigente(banco, conta, como, enviar, cod_novo):
    ed, cod = conta('editor'), cod_novo()
    rid = enviar(ed, cod)
    erro(como(ed, RECUSAR, (rid, '  ')), 'motivo')
    como(ed, RECUSAR, (rid, 'pen-drive errado'))
    assert banco.execute('select status, motivo_recusa from hub.paralelismo_rodadas where id=%s', (rid,)).fetchone() == (
        'recusada', 'pen-drive errado')
    assert vigente(banco, cod) is None
    erro(como(ed, PUBLICAR, (rid,)), 'rodada_nao_pendente')


def test_linhas_vigentes_so_publicadas_e_a_rodada_pedida(banco, conta, como, enviar, cod_novo):
    ed, sol, outro, cod = conta('editor'), conta('solicitante'), conta('solicitante'), cod_novo()
    r1 = enviar(ed, cod)
    como(ed, PUBLICAR, (r1,))
    a1 = analise_id(banco, r1)
    r2 = enviar(sol, cod, base=a1)
    v = como(sol, LINHAS, ('torta', cod, None))[0][0]
    assert v['analise_id'] == a1 and v['linhas'] == [{'frota': '64086', 'data': '2026-10-03', 'coords': [[0, r1], [100, r1]]}]
    assert len(como(ed, LINHAS, ('torta', cod, r2))[0][0]['linhas']) == 2
    assert len(como(sol, LINHAS, ('torta', cod, r2))[0][0]['linhas']) == 2
    erro(como(outro, LINHAS, ('torta', cod, r2)), 'Sem permissão')
    assert como(sol, LINHAS, ('cana', cod, None))[0][0] == {'analise_id': None, 'linhas': []}


def test_excluir_devolve_a_anterior(banco, conta, como, enviar, cod_novo):
    ed, adm, cod = conta('editor'), conta('admin'), cod_novo()
    r1 = enviar(ed, cod, shas=['exc1'])
    como(ed, PUBLICAR, (r1,))
    r2 = enviar(ed, cod, base=analise_id(banco, r1), shas=['exc2'], amostras=200)
    como(ed, PUBLICAR, (r2,))
    erro(como(ed, EXCLUIR, (r2,)), 'Só administradores')
    assert como(adm, EXCLUIR, (r2,)) == [(f'paralelismo-r{r2}',)]
    assert vigente(banco, cod) == (r1, 100)
    assert conta_linhas(banco, 'paralelismo_linhas', r2) == 0 and conta_linhas(banco, 'paralelismo_analises', r2) == 0
    assert como(ed, JA, (['exc1', 'exc2'],)) == [(['exc1'],)]
    assert banco.execute("select valor_anterior from hub.log_auditoria where entidade_id=%s and campo='rodada_paralelismo_excluida'",
                         (cod,)).fetchone() == (f'paralelismo-r{r2}',)


def test_excluir_a_unica_deixa_a_fazenda_sem_vigente(banco, conta, como, enviar, cod_novo):
    ed, adm, cod = conta('editor'), conta('admin'), cod_novo()
    rid = enviar(ed, cod)
    como(ed, PUBLICAR, (rid,))
    como(adm, EXCLUIR, (rid,))
    assert vigente(banco, cod) is None


def test_excluir_recusa_com_rodada_mais_nova_ou_previa_dependente(banco, conta, como, enviar, cod_novo):
    ed, adm, cod = conta('editor'), conta('admin'), cod_novo()
    r1 = enviar(ed, cod)
    como(ed, PUBLICAR, (r1,))
    r2 = enviar(ed, cod, base=analise_id(banco, r1))
    erro(como(adm, EXCLUIR, (r1,)), f'rodada_pendente_depende:{r2}')
    como(ed, PUBLICAR, (r2,))
    erro(como(adm, EXCLUIR, (r1,)), f'exclua_antes_rodada_mais_nova:{cod}')
    erro(como(adm, EXCLUIR, (999999,)), 'rodada_nao_publicada')
    assert vigente(banco, cod) == (r2, 100)


def test_frotas_so_o_editor_escreve(conta, como):
    ed, lei, sol = conta('editor'), conta('leitura'), conta('solicitante')
    grava = "insert into hub.paralelismo_frotas (serie, frota, operacao, tipo) values (%s, '1', 'torta', 'propria')"
    assert como(ed, grava, ('TESTE1',)) is None
    erro(como(lei, grava, ('TESTE2',)))
    erro(como(sol, grava, ('TESTE3',)))
    assert como(lei, "select count(*) from hub.paralelismo_frotas where serie='TESTE1'") == [(1,)]
    assert como(conta(None), "select count(*) from hub.paralelismo_frotas where serie='TESTE1'") == [(0,)]


def test_talhoes_da_fazenda_em_geojson(banco, conta, como, cod_novo):
    cod = cod_novo()
    banco.execute('insert into hub.fazendas (cod_faz, nome) values (%s, %s)', (cod, 'TESTE'))
    banco.execute('insert into hub.talhoes (cod_faz, talhao_num, declividade) values (%s, 3, 7.5)', (cod,))
    banco.execute("insert into hub.talhao_geom values (%s, 3, %s, 12.5)", (cod, '{"type":"MultiPolygon","coordinates":[]}'))
    fc = como(conta('editor'), 'select hub.paralelismo_talhoes_fazenda(%s)', (cod,))[0][0]
    assert fc['type'] == 'FeatureCollection'
    assert fc['features'][0]['properties'] == {'talhao': 3, 'area_ha': 12.5, 'declividade': 7.5}
    erro(como(conta('leitura'), 'select hub.paralelismo_talhoes_fazenda(%s)', (cod,)), 'Sem permissão')


def test_solicitante_vale_no_paralelismo_e_continua_barrado_nos_outros(banco, conta, como):
    adm = conta('admin')
    salvar = 'select hub.acesso_salvar(%s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb)'
    ok = ('par-sol@x.com', 'Fulano', False, json.dumps({'paralelismo': 'solicitante'}),
          False, False, [], '[]')
    r = como(adm, salvar, ok)
    assert not r or r[0] != 'ERRO', r
    ruim = ('par-sol2@x.com', 'Fulano', False, json.dumps({'plantio': 'solicitante'}), False, False, [], '[]')
    erro(como(adm, salvar, ruim), 'Nível inválido')
    uid = conta(None)
    banco.execute("insert into hub.usuario_modulos (usuario_id, modulo_id, nivel) values (%s, 'paralelismo', 'solicitante')", (uid,))
    with pytest.raises(psycopg.errors.CheckViolation):
        banco.execute("insert into hub.usuario_modulos (usuario_id, modulo_id, nivel) values (%s, 'plantio', 'solicitante')", (uid,))


def test_reserva_tem_dono(conta, como, enviar, cod_novo):
    a, b = conta('solicitante'), conta('solicitante')
    rid = como(a, 'select hub.paralelismo_preparar_parte()')[0][0]
    erro(como(b, 'select hub.paralelismo_preparar_parte(%s)', (rid,)), 'rodada_invalida')
    erro(enviar(b, cod_novo(), rid=rid), 'rodada_invalida')
    assert enviar(a, cod_novo(), rid=rid) == rid


def test_enviar_de_novo_avisa_que_ja_foi(banco, conta, enviar, cod_novo):
    sol = conta('solicitante')
    rid = enviar(sol, cod_novo())
    erro(enviar(sol, cod_novo(), rid=rid), f'rodada_ja_enviada:{rid}')


def test_id_de_rodada_excluida_nao_volta(conta, como, enviar, cod_novo):
    ed, adm = conta('editor'), conta('admin')
    rid = enviar(ed, cod_novo())
    como(ed, PUBLICAR, (rid,))
    como(adm, EXCLUIR, (rid,))
    erro(como(ed, 'select hub.paralelismo_preparar_parte(%s)', (rid,)), 'rodada_ja_enviada')
    erro(enviar(ed, cod_novo(), rid=rid), 'rodada_ja_enviada')


def test_payload_incoerente_recusa_sem_gravar(banco, conta, enviar, cod_novo):
    sol, cod = conta('solicitante'), cod_novo()
    erro(enviar(sol, cod, shas=['dup1', 'dup1']), 'arquivo_repetido_no_envio:dup1')
    erro(enviar(sol, cod, linhas=[{'operacao': 'cana', 'cod_faz': 11111, 'coords': [[0, 0], [1, 1]]}]),
         'linha_sem_analise:cana/11111')
    erro(enviar(sol, cod, partes=[{'url': 'javascript:alert(1)'}]), 'url_invalida')
    erro(enviar(sol, cod, analises=[{'operacao': 'torta', 'cod_faz': cod, 'amostras': 1, 'aderentes': 999, 'acima': 0,
                                     'abaixo': 0, 'fora_talhao': 0, 'pll_total': 1}]))
    assert banco.execute('select count(*) from hub.paralelismo_analises where cod_faz=%s', (cod,)).fetchone() == (0,)


def test_recalculo_com_url_invalida_recusa(banco, conta, como, enviar, cod_novo):
    ed = conta('editor')
    cod = cod_novo()
    rid = enviar(ed, cod)
    erro(como(ed, RECALCULAR, (rid, json.dumps([{'operacao': 'torta', 'cod_faz': cod, 'amostras_url': 'javascript:x'}]))),
         'url_invalida')


def test_rodada_com_varias_fazendas(banco, conta, como, enviar, cod_novo):
    ed, adm, c1, c2 = conta('editor'), conta('admin'), cod_novo(), cod_novo()
    r1 = enviar(ed, c1)
    como(ed, PUBLICAR, (r1,))
    r2 = enviar(ed, [c1, c2])
    erro(como(ed, PUBLICAR, (r2,)), f'recalculo_necessario:torta/{c1}')
    assert vigente(banco, c2) is None
    banco.execute('update hub.paralelismo_analises set base_analise_id = %s where rodada_id = %s and cod_faz = %s',
                  (analise_id(banco, r1), r2, c1))
    como(ed, PUBLICAR, (r2,))
    assert vigente(banco, c1)[0] == r2 and vigente(banco, c2)[0] == r2
    como(adm, EXCLUIR, (r2,))
    assert vigente(banco, c1)[0] == r1 and vigente(banco, c2) is None


def test_matriz_de_permissoes(banco):
    def funcoes():
        return banco.execute("""select p.oid::regprocedure::text from pg_proc p join pg_namespace n on n.oid = p.pronamespace
                                 where n.nspname = 'hub' and p.proname like 'paralelismo%'""").fetchall()
    internas = ('paralelismo_gravar_talhoes', 'paralelismo_url_ok')
    nomes = [f[0] for f in funcoes()]
    assert len(nomes) == 12
    for f in nomes:
        interna = any(i in f for i in internas)
        assert banco.execute('select has_function_privilege(%s, %s, %s)', ('anon', f, 'execute')).fetchone() == (False,), f
        assert banco.execute('select has_function_privilege(%s, %s, %s)',
                             ('authenticated', f, 'execute')).fetchone() == (not interna,), f
    for t in ('frotas', 'rodadas', 'reservas', 'arquivos', 'linhas', 'analises', 'talhoes'):
        tab = f'hub.paralelismo_{t}'
        assert banco.execute('select relrowsecurity from pg_class where oid = %s::regclass', (tab,)).fetchone() == (True,), t
        for priv in ('select', 'insert', 'update', 'delete'):
            esperado = t == 'frotas' or (priv == 'select' and t != 'reservas')
            assert banco.execute('select has_table_privilege(%s, %s, %s)',
                                 ('authenticated', tab, priv)).fetchone() == (esperado,), (t, priv)
            assert banco.execute('select has_table_privilege(%s, %s, %s)', ('anon', tab, priv)).fetchone() == (False,), (t, priv)


def test_script_de_volta_desfaz_com_dados(banco_descartavel):
    b = banco_descartavel
    uid = b.execute("insert into auth.users (email) values ('v@x.com') returning id").fetchone()[0]
    b.execute("insert into hub.usuarios (id, nome) values (%s, 'V')", (uid,))
    b.execute("insert into hub.usuario_modulos (usuario_id, modulo_id, nivel) values (%s, 'paralelismo', 'solicitante')", (uid,))
    b.execute("""insert into hub.acessos (email, nome, niveis, modulos)
                 values ('v@x.com', 'V', '{"paralelismo": "solicitante", "plantio": "leitura"}', '{paralelismo,plantio}')""")
    b.execute("""insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo)
                 values ('paralelismo', 'fazenda', 1, 'rodada_paralelismo_excluida')""")
    raiz = Path(__file__).resolve().parents[2]
    b.execute((raiz / 'supabase/migrations/volta/20261104090000_paralelismo_volta.sql').read_text(encoding='utf-8'))
    assert b.execute("select to_regclass('hub.paralelismo_rodadas'), to_regproc('hub.paralelismo_nivel')").fetchone() == (None, None)
    assert b.execute("select count(*) from hub.modulos where id = 'paralelismo'").fetchone() == (0,)
    assert b.execute("select niveis, modulos from hub.acessos where email = 'v@x.com'").fetchone() == ({'plantio': 'leitura'}, ['plantio'])
    assert b.execute("select modulo_id from hub.log_auditoria where campo = 'rodada_paralelismo_excluida'").fetchone() == (None,)


def test_cartao_em_ferramentas_entra_uma_vez_e_preserva_os_outros(banco):
    import json
    from tests.paralelismo.conftest import RAIZ
    lista = json.loads(banco.execute("select valor from hub.parametros where chave = 'ferramentas'").fetchone()[0])
    ids = [f['id'] for f in lista]
    assert ids.count('paralelismo') == 1 and 'geomap' in ids
    assert lista[ids.index('paralelismo')]['url'].endswith('/paralelismo.html')
    sql = (RAIZ / 'supabase' / 'migrations' / '20261105090000_paralelismo_cartao.sql').read_text(encoding='utf-8')
    banco.execute(sql)
    depois = json.loads(banco.execute("select valor from hub.parametros where chave = 'ferramentas'").fetchone()[0])
    assert depois == lista
    volta = (RAIZ / 'supabase' / 'migrations' / 'volta' / '20261105090000_paralelismo_cartao_volta.sql').read_text(encoding='utf-8')
    banco.execute(volta)
    sem = json.loads(banco.execute("select valor from hub.parametros where chave = 'ferramentas'").fetchone()[0])
    assert [f['id'] for f in sem] == [i for i in ids if i != 'paralelismo']
    banco.execute(sql)   # deixa o cartão de volta para os outros testes
