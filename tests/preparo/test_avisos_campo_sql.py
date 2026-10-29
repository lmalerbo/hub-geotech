"""Aviso por fazenda: data de campo do PLANAGRI no ciclo atual e talhão sem lançamento no Hub."""
from tests.fluxo.test_fluxo_projetos_sql import por


def avisos(banco, cod):
    return banco.execute('select tipo, texto from hub.avisos where cod_faz = %s and resolvido_em is null order by tipo',
                         (cod,)).fetchall()


def rodar(banco):
    banco.execute('select hub.avisos_campo_planagri()')


def test_preparo_e_plantio_abrem_aviso_so_no_ciclo_atual(banco, fazenda):
    cod = fazenda(3)
    banco.execute("update hub.talhao_preparo set conservacao_em = '2026-09-10' where layer in (%s, %s)", (cod*1000+1, cod*1000+2))
    banco.execute("update hub.talhao_preparo set conservacao_em = '2025-09-10' where layer = %s", (cod*1000+3,))
    banco.execute("update hub.talhao_plantio set plantio_realizado_em = '2026-10-01' where layer = %s", (cod*1000+1,))
    rodar(banco)
    assert avisos(banco, cod) == [
        ('plantio_campo_sem_lancamento', '1 talhão(ões) com plantio realizado no PLANAGRI, falta lançar no Hub.'),
        ('preparo_campo_sem_lancamento', '2 talhão(ões) usados em campo (conservação no PLANAGRI), falta lançar no Hub.')]


def test_aviso_resolve_quando_lanca(banco, fazenda):
    cod = fazenda(1)
    banco.execute("update hub.talhao_preparo set conservacao_em = '2026-09-10' where layer = %s", (cod*1000+1,))
    rodar(banco)
    por(banco, 'preparo', cod, 'Ok')
    rodar(banco)
    assert avisos(banco, cod) == []


def test_aviso_igual_nao_volta_a_ficar_nao_lido(banco, fazenda, pessoa):
    cod, uid = fazenda(2), pessoa()
    banco.execute("update hub.talhao_preparo set conservacao_em = '2026-09-10' where layer = %s", (cod*1000+1,))
    rodar(banco)
    aid = banco.execute('select id from hub.avisos where cod_faz = %s and resolvido_em is null', (cod,)).fetchone()[0]
    banco.execute('insert into hub.avisos_lidos (aviso_id, usuario_id) values (%s, %s)', (aid, uid))
    rodar(banco)
    assert banco.execute('select count(*) from hub.avisos_lidos where aviso_id = %s', (aid,)).fetchone()[0] == 1
    banco.execute("update hub.talhao_preparo set conservacao_em = '2026-09-11' where layer = %s", (cod*1000+2,))
    rodar(banco)                                            # mudou a contagem → não lido de novo
    assert banco.execute('select count(*) from hub.avisos_lidos where aviso_id = %s', (aid,)).fetchone()[0] == 0


def test_chamar_duas_vezes_na_mesma_transacao(banco, fazenda):
    cod = fazenda(1)
    banco.execute("update hub.talhao_preparo set conservacao_em = '2026-09-10' where layer = %s", (cod*1000+1,))
    rodar(banco)
    rodar(banco)
    assert len(avisos(banco, cod)) == 1
