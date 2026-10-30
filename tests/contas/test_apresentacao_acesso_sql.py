"""Ferramenta Apresentação semanal: módulo próprio, nível único editor, não muda o papel."""
import json

SALVAR = 'select hub.acesso_salvar(%s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb)'


def salvar(como, uid, email, nome='Fulano', admin=False, niveis=None):
    return como(uid, SALVAR, (email, nome, admin, json.dumps(niveis or {}), False, False, [], '[]'))


def test_modulo_existe(banco):
    assert banco.execute("select nome from hub.modulos where id = 'apresentacao'").fetchone()[0] == 'Apresentação semanal'


def test_salvar_acesso_com_apresentacao_nao_vira_editor(banco, pessoa, como):
    adm = pessoa('ap-adm1@x.com', admin=True)
    r = salvar(como, adm, 'ap1@x.com', niveis={'apresentacao': 'editor'})
    assert not r or r[0] != 'ERRO', r
    assert banco.execute("select papel from hub.acessos where email = 'ap1@x.com'").fetchone() == ('leitura',)


def test_apresentacao_so_aceita_editor(pessoa, como):
    adm = pessoa('ap-adm2@x.com', admin=True)
    r = salvar(como, adm, 'ap2@x.com', niveis={'apresentacao': 'leitura'})
    assert r[0] == 'ERRO' and 'Nível inválido' in r[1], r


def test_pode_usar(banco, pessoa, como):
    adm = pessoa('ap-adm3@x.com', admin=True)
    com, sem = pessoa('ap-com@x.com'), pessoa('ap-sem@x.com')
    banco.execute("insert into hub.usuario_modulos (usuario_id, modulo_id, nivel) values (%s, 'apresentacao', 'editor')", (com,))
    banco.execute("insert into hub.usuario_modulos (usuario_id, modulo_id, nivel) values (%s, 'plantio', 'leitura')", (sem,))
    assert como(com, 'select hub.pode_usar_apresentacao()') == [(True,)]
    assert como(sem, 'select hub.pode_usar_apresentacao()') == [(False,)]
    assert como(adm, 'select hub.pode_usar_apresentacao()') == [(True,)]
