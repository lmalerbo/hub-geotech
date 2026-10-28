"""Lançamento único do ciclo 25-26: talhão a talhão, conservação antes de 01/04/2026."""
from tests.fluxo.test_fluxo_projetos_sql import etapas, por

SELO = 'ciclo 25-26 · pelo PLANAGRI'


def conservacao(banco, cod, datas):
    for n, d in datas.items():
        banco.execute('update hub.talhao_preparo set conservacao_em = %s where layer = %s', (d, cod * 1000 + n))


def status(banco, cod):
    return banco.execute("select e.nome, s.ok, s.observacao, (s.concluido_em at time zone 'America/Sao_Paulo')::date::text "
                         "from hub.etapa_status s join hub.etapas e on e.id = s.etapa_id "
                         "where e.modulo_id='preparo' and s.entidade_id = %s order by e.ordem", (cod,)).fetchall()


def test_lanca_so_talhoes_com_conservacao_antes_do_corte(banco, fazenda):
    cod = fazenda(3)
    conservacao(banco, cod, {1: '2025-08-01', 2: '2026-04-01', 3: None})
    cand = banco.execute('select talhao_num from hub.preparo_ciclo_25_26_candidatos() where cod_faz = %s', (cod,)).fetchall()
    assert cand == [(1,)]
    lote = banco.execute('select hub.preparo_lancar_ciclo_25_26()').fetchone()[0]
    assert etapas(banco, 'preparo', cod) == {1: 'Ok', 2: 'Identificação', 3: 'Identificação'}
    assert banco.execute("select count(*) from hub.log_auditoria where lote_id = %s and entidade_id = %s "
                         "and origem = 'planagri_ciclo_25_26' and justificativa = %s", (lote, cod * 1000 + 1, SELO)).fetchone()[0] == 1
    assert status(banco, cod) == []          # fazenda não ficou inteira Ok: etapa_status não muda


def test_fazenda_inteira_ganha_etapas_sem_trocar_observacao(banco, fazenda):
    cod = fazenda(2)
    conservacao(banco, cod, {1: '2025-06-10', 2: '2025-11-20'})
    banco.execute("insert into hub.etapa_status (etapa_id, entidade_id, ok, observacao) select id, %s, false, 'obs antiga' "
                  "from hub.etapas where modulo_id='preparo' and nome='Observações'", (cod,))
    banco.execute('select hub.preparo_lancar_ciclo_25_26()')
    assert status(banco, cod) == [('Identificação', True, SELO, '2025-11-20'), ('Escoamento', True, SELO, '2025-11-20'),
                                  ('Observações', True, 'obs antiga', '2025-11-20'), ('Preparo', True, SELO, '2025-11-20')]


def test_rodar_de_novo_nao_lanca_nada(banco, fazenda):
    cod = fazenda(1)
    conservacao(banco, cod, {1: '2025-07-01'})
    banco.execute('select hub.preparo_lancar_ciclo_25_26()')
    assert banco.execute('select hub.preparo_lancar_ciclo_25_26()').fetchone()[0] is None


def test_talhao_ja_ok_nao_entra(banco, fazenda):
    cod = fazenda(1)
    conservacao(banco, cod, {1: '2025-07-01'})
    por(banco, 'preparo', cod, 'Ok')
    assert banco.execute('select count(*) from hub.preparo_ciclo_25_26_candidatos() where cod_faz = %s', (cod,)).fetchone()[0] == 0


def test_volta_restaura_etapa_status_e_log(banco, fazenda):
    cod = fazenda(1)
    conservacao(banco, cod, {1: '2025-07-01'})
    por(banco, 'preparo', cod, 'Observações')
    banco.execute("insert into hub.etapa_status (etapa_id, entidade_id, ok, observacao) select id, %s, true, 'x' "
                  "from hub.etapas where modulo_id='preparo' and nome='Identificação'", (cod,))
    antes = status(banco, cod)
    lote = banco.execute('select hub.preparo_lancar_ciclo_25_26()').fetchone()[0]
    assert banco.execute('select hub.preparo_voltar_ciclo_25_26(%s)', (lote,)).fetchone()[0] == 1
    assert etapas(banco, 'preparo', cod) == {1: 'Observações'}
    assert status(banco, cod) == antes
    assert banco.execute('select count(*) from hub.log_auditoria where lote_id = %s', (lote,)).fetchone()[0] == 0
