"""Metas e rascunho da Apresentação semanal (spec D6)."""
import itertools

_n = itertools.count()


def usuario(banco, pessoa, modulo):
    uid = pessoa(f'apt{next(_n)}@x.com')
    banco.execute("insert into hub.usuario_modulos (usuario_id, modulo_id, nivel) values (%s, %s, 'editor')", (uid, modulo))
    return uid


def test_metas_iniciais(banco):
    m = dict(banco.execute('select chave, valor from hub.apresentacao_metas').fetchall())
    assert m == {'meta_ervas_ha': '20863', 'meta_fornecedor_ha': '3500', 'meta_ha_dia': '250',
                 'drone_pendente_ha': '2000', 'safra_atual': '26/27', 'inicio_safra': '2026-04-01'}


def test_sem_ferramenta_nao_le_nem_grava(banco, pessoa, como):
    sem = usuario(banco, pessoa, 'plantio')
    assert como(sem, 'select count(*) from hub.apresentacao_metas') == [(0,)]
    r = como(sem, "select hub.apresentacao_texto_salvar('S5M10', '2026-10-28', 'colheita', 'destaque', 'x')")
    assert r[0] == 'ERRO'


def test_dois_editores_nao_se_apagam(banco, pessoa, como):
    a, b = usuario(banco, pessoa, 'apresentacao'), usuario(banco, pessoa, 'apresentacao')
    como(a, "select hub.apresentacao_texto_salvar('S4M10', '2026-10-21', 'colheita', 'destaque', 'chuva na F3')")
    como(b, "select hub.apresentacao_texto_salvar('S4M10', '2026-10-21', 'plantio', 'notas', 'falar do atraso')")
    como(a, "select hub.apresentacao_texto_salvar('S4M10', '2026-10-21', 'colheita', 'notas', 'ok')")
    t = banco.execute("select textos from hub.apresentacao_semanas where semana = 'S4M10'").fetchone()[0]
    assert t == {'colheita': {'destaque': 'chuva na F3', 'notas': 'ok'}, 'plantio': {'notas': 'falar do atraso'}}


def test_campo_e_slide_validos(banco, pessoa, como):
    a = usuario(banco, pessoa, 'apresentacao')
    assert como(a, "select hub.apresentacao_texto_salvar('S5M10', '2026-10-28', 'xx', 'notas', 'a')")[0] == 'ERRO'
    assert como(a, "select hub.apresentacao_texto_salvar('S5M10', '2026-10-28', 'drone', 'cor', 'a')")[0] == 'ERRO'


def test_metas_editaveis_por_quem_tem_a_ferramenta(banco, pessoa, como):
    a = usuario(banco, pessoa, 'apresentacao')
    como(a, "update hub.apresentacao_metas set valor = '2500' where chave = 'drone_pendente_ha'")
    assert banco.execute("select valor, atualizado_por = %s from hub.apresentacao_metas "
                         "where chave = 'drone_pendente_ha'", (a,)).fetchone() == ('2500', True)
    banco.execute("update hub.apresentacao_metas set valor = '2000' where chave = 'drone_pendente_ha'")