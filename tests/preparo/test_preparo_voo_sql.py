"""Fase de voo do Preparo (spec 2026-10-29-preparo-fase-voo-design.md)."""
import json
import uuid

from tests.fluxo.test_fluxo_projetos_sql import por


def reg(cod, num, status, projeto='Sistematização', criado='2026-10-27T12:00:00Z', id_=None, land=None):
    return {'id': str(id_ or uuid.uuid4()), 'section': str(cod), 'landPlot': land or str(num), 'projeto': projeto,
            'controlStatus': status, 'verifyFlightSize': 5, 'createdUtc': criado,
            'scheduledDate': criado, 'startDateFlight': None, 'modifiedUtc': criado}


def gravar(banco, secoes, registros):
    return banco.execute('select hub.preparo_voos_gravar(%s, %s::jsonb)',
                         (secoes, json.dumps(registros))).fetchone()[0]


def situacoes(banco, cod):
    return {r[0] % 1000: r[1] for r in banco.execute(
        'select layer, situacao from hub.preparo_voo_talhao where layer / 1000 = %s order by layer', (cod,))}


def test_sem_leitura_ate_o_agente_ler_a_fazenda(banco, fazenda):
    cod = fazenda(2)
    assert situacoes(banco, cod) == {1: 'sem_leitura', 2: 'sem_leitura'}


def test_situacao_pelo_status_mais_avancado(banco, fazenda):
    cod = fazenda(5)
    gravar(banco, [cod], [reg(cod, 1, 2), reg(cod, 2, 4), reg(cod, 3, 9), reg(cod, 3, 2), reg(cod, 4, 10)])
    assert situacoes(banco, cod) == {1: 'solicitado', 2: 'processando', 3: 'liberado', 4: 'liberado',
                                     5: 'nao_solicitado'}


def test_expansao_conta_levantamento_nao(banco, fazenda):
    cod = fazenda(2)
    gravar(banco, [cod], [reg(cod, 1, 9, projeto='Expansão'), reg(cod, 2, 9, projeto='Levantamento Topográfico')])
    assert situacoes(banco, cod) == {1: 'liberado', 2: 'nao_solicitado'}


def test_voo_antigo_ou_cancelado_nao_conta(banco, fazenda):
    cod = fazenda(2)
    gravar(banco, [cod], [reg(cod, 1, 9, criado='2026-03-31T12:00:00Z'), reg(cod, 2, 11)])
    assert situacoes(banco, cod) == {1: 'nao_solicitado', 2: 'nao_solicitado'}


def test_so_talhoes_em_identificacao(banco, fazenda):
    cod = fazenda(2)
    por(banco, 'preparo', cod, 'Escoamento', [2])
    assert set(situacoes(banco, cod)) == {1}


def test_gravar_atualiza_o_mesmo_registro(banco, fazenda):
    cod, id_ = fazenda(1), uuid.uuid4()
    gravar(banco, [cod], [reg(cod, 1, 2, id_=id_)])
    gravar(banco, [cod], [reg(cod, 1, 9, id_=id_)])
    assert situacoes(banco, cod) == {1: 'liberado'}
    assert banco.execute('select count(*) from hub.voo_dronemgmt where dronemgmt_id = %s', (id_,)).fetchone()[0] == 1


def test_gravar_remove_o_que_sumiu(banco, fazenda):
    cod = fazenda(1)
    gravar(banco, [cod], [reg(cod, 1, 9)])
    gravar(banco, [cod], [])
    assert situacoes(banco, cod) == {1: 'nao_solicitado'}


def test_gravar_nao_mexe_em_outra_fazenda_nem_em_outro_projeto(banco, fazenda):
    a, b = fazenda(1), fazenda(1)
    gravar(banco, [b], [reg(b, 1, 9)])
    banco.execute("insert into hub.voo_dronemgmt (dronemgmt_id, layer, projeto_voo, control_status) "
                  "values (%s, %s, 'Falhas Soca', 4)", (uuid.uuid4(), a * 1000 + 1))
    gravar(banco, [a], [])
    assert situacoes(banco, b) == {1: 'liberado'}
    assert banco.execute("select count(*) from hub.voo_dronemgmt where layer = %s and projeto_voo = 'Falhas Soca'",
                         (a * 1000 + 1,)).fetchone()[0] == 1


def test_gravar_ignora_talhao_nao_numerico(banco, fazenda):
    cod = fazenda(1)
    assert gravar(banco, [cod], [reg(cod, 1, 9), reg(cod, 0, 9, land='1A')]) == 1
    assert situacoes(banco, cod) == {1: 'liberado'}


def test_gravar_so_service_role(banco, pessoa, como, fazenda):
    cod = fazenda(1)
    r = como(pessoa(), 'select hub.preparo_voos_gravar(%s, %s::jsonb)', ([cod], '[]'))
    assert r[0] == 'ERRO'


def test_aviso_sem_voo_foi_removido(banco):
    # sem uso desde 04/11 (etapa Voo calculada na tela); removido em 20261109090000
    assert banco.execute("select count(*) from pg_proc where proname = 'preparo_aviso_sem_voo'").fetchone()[0] == 0


def test_execucoes_aceitam_voos_preparo(banco):
    id_ = banco.execute("insert into hub.execucoes_ingestao (fonte) values ('voos_preparo') returning id").fetchone()[0]
    banco.execute("delete from hub.execucoes_ingestao where id = %s", (id_,))