"""Datas de campo do PLANAGRI, ciclo e data de entrega do Preparo (spec 2026-10-28-preparo-mes-ciclo-design.md)."""
from tests.fluxo.test_fluxo_projetos_sql import por


def log_ok(banco, layer, quando, origem='usuario', de='Preparo', para='Ok'):
    banco.execute("insert into hub.log_auditoria (modulo_id, entidade_tipo, entidade_id, campo, valor_anterior, "
                  "valor_novo, origem, criado_em) values ('preparo','talhao',%s,'etapa',%s,%s,%s,%s)",
                  (layer, de, para, origem, quando))


def etapa_preparo_ok(banco, cod, quando):
    banco.execute("insert into hub.etapa_status (etapa_id, entidade_id, ok, concluido_em) "
                  "select id, %s, true, %s from hub.etapas where modulo_id='preparo' and nome='Preparo'", (cod, quando))


def entregas(banco, cod):
    return {r[0] % 1000: (r[1], r[2]) for r in banco.execute(
        "select layer, (entregue_em at time zone 'America/Sao_Paulo')::date::text, origem "
        "from hub.preparo_entregas where cod_faz = %s", (cod,))}


def test_ciclo_inicio_vem_da_safra(banco):
    assert banco.execute('select hub.ciclo_inicio()::text').fetchone()[0] == '2026-04-01'


def test_entrega_pelo_log_vale_a_ultima_passagem(banco, fazenda):
    cod = fazenda(2)
    por(banco, 'preparo', cod, 'Ok', [1])
    log_ok(banco, cod * 1000 + 1, '2026-08-10 12:00-03')
    log_ok(banco, cod * 1000 + 1, '2026-09-05 12:00-03', de='Ok', para='Preparo')
    log_ok(banco, cod * 1000 + 1, '2026-10-02 12:00-03')
    assert entregas(banco, cod) == {1: ('2026-10-02', 'hub')}   # talhão 2 não está Ok


def test_talhao_que_voltou_de_ok_nao_e_entregue(banco, fazenda):
    cod = fazenda(1)
    log_ok(banco, cod * 1000 + 1, '2026-08-10 12:00-03')        # foi Ok, mas hoje está em Identificação
    assert entregas(banco, cod) == {}


def test_sem_log_usa_etapa_preparo_e_marca_lote_de_junho(banco, fazenda):
    a, b = fazenda(1), fazenda(1)
    por(banco, 'preparo', a, 'Ok'); por(banco, 'preparo', b, 'Ok')
    etapa_preparo_ok(banco, a, '2026-06-18 15:00-03')
    etapa_preparo_ok(banco, b, '2026-07-20 15:00-03')
    assert entregas(banco, a) == {1: ('2026-06-18', 'lancamento_inicial')}
    assert entregas(banco, b) == {1: ('2026-07-20', 'hub')}


def test_lancamento_25_26_usa_data_de_conservacao(banco, fazenda):
    cod = fazenda(1)
    por(banco, 'preparo', cod, 'Ok')
    banco.execute("update hub.talhao_preparo set conservacao_em = '2025-09-15' where layer = %s", (cod * 1000 + 1,))
    log_ok(banco, cod * 1000 + 1, '2026-10-28 12:00-03', origem='planagri_ciclo_25_26')
    assert entregas(banco, cod) == {1: ('2025-09-15', 'ciclo_25_26')}


def test_conservacao_dia_1_nao_cai_no_mes_anterior_com_sessao_em_utc(banco, fazenda):
    cod = fazenda(1)
    por(banco, 'preparo', cod, 'Ok')
    banco.execute("update hub.talhao_preparo set conservacao_em = '2025-09-01' where layer = %s", (cod * 1000 + 1,))
    log_ok(banco, cod * 1000 + 1, '2026-10-28 12:00-03', origem='planagri_ciclo_25_26')
    banco.execute("set time zone 'UTC'")
    try:
        assert entregas(banco, cod) == {1: ('2025-09-01', 'ciclo_25_26')}
    finally:
        banco.execute("reset time zone")
