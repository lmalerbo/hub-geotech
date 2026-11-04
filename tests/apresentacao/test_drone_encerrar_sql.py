"""hub.drone_encerrar_projeto: fazenda que saiu inteira da Base deixa de ter projeto vigente, com histórico guardado."""
import pytest


@pytest.fixture
def editor(pessoa):
    return pessoa(modulos=('drone',))


def projeto(banco, cod):
    pid = banco.execute("insert into hub.projetos (modulo_id, tipo, cod_faz, nome) values ('drone','individual',%s,'x') "
                        "returning id", (cod,)).fetchone()[0]
    for doc in ('normal', 'catacao'):
        banco.execute("insert into hub.projeto_revisoes (projeto_id, documento, numero, vigente) values (%s,%s,0,true)",
                      (pid, doc))
    return pid


def solicitacao(banco, cod, status='em_elaboracao', ger='erro'):
    sol = banco.execute("insert into hub.drone_solicitacoes (cod_faz, tipo, status) values (%s,'normal',%s) returning id",
                        (cod, status)).fetchone()[0]
    gid = banco.execute("insert into hub.drone_geracoes (solicitacao_id, status) values (%s,%s) returning id",
                        (sol, ger)).fetchone()[0]
    return sol, gid


def encerrar(como, uid, cod, motivo='saiu da Base'):
    return como(uid, 'select hub.drone_encerrar_projeto(%s, %s)', (cod, motivo))


def test_encerra_guarda_historico_e_cancela_o_que_esta_aberto(banco, como, fazenda, editor):
    cod = fazenda()
    pid = projeto(banco, cod)
    sol, gid = solicitacao(banco, cod)
    assert encerrar(como, editor, cod)[0] != 'ERRO'
    assert banco.execute('select count(*) from hub.projeto_revisoes where projeto_id = %s and vigente', (pid,)).fetchone()[0] == 0
    assert banco.execute('select count(*) from hub.projeto_revisoes where projeto_id = %s', (pid,)).fetchone()[0] == 2
    assert banco.execute('select encerrado_motivo, encerrado_por, encerrado_em is not null from hub.projetos where id = %s',
                         (pid,)).fetchone() == ('saiu da Base', editor, True)
    assert banco.execute('select status, cancelado_motivo from hub.drone_solicitacoes where id = %s',
                         (sol,)).fetchone() == ('cancelado', 'saiu da Base')
    assert banco.execute('select status from hub.drone_geracoes where id = %s', (gid,)).fetchone()[0] == 'descartada'


def test_recusa_fazenda_que_ainda_tem_talhao_na_base(banco, como, fazenda, editor):
    cod = fazenda()
    pid = projeto(banco, cod)
    banco.execute('insert into hub.talhao_geom values (%s, 1)', (cod,))
    assert 'ainda tem talhões na Base' in encerrar(como, editor, cod)[1]
    assert banco.execute('select count(*) from hub.projeto_revisoes where projeto_id = %s and vigente', (pid,)).fetchone()[0] == 2


def test_recusa_sem_permissao_sem_motivo_e_sem_projeto_vigente(banco, como, fazenda, pessoa, editor):
    cod = fazenda()
    projeto(banco, cod)
    assert 'Sem permissão' in encerrar(como, pessoa(modulos=()), cod)[1]
    assert 'motivo' in encerrar(como, editor, cod, '  ')[1]
    assert 'vigente' in encerrar(como, editor, fazenda())[1]


def test_recusa_com_o_agente_gerando_ou_publicando(banco, como, fazenda, editor):
    cod = fazenda()
    pid = projeto(banco, cod)
    solicitacao(banco, cod, ger='processando')
    assert 'agente' in encerrar(como, editor, cod)[1]
    assert banco.execute('select count(*) from hub.projeto_revisoes where projeto_id = %s and vigente', (pid,)).fetchone()[0] == 2
