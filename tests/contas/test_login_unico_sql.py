SALVAR = 'select hub.acesso_salvar(%s, %s, %s, %s, %s, %s, %s, %s)'


def salvar(como, uid, email, nome='Fulano', papel='leitura', admin=False, modulos=(), gm_ativo=False, gm_admin=False, gm_grupos=()):
    return como(uid, SALVAR, (email, nome, papel, admin, list(modulos), gm_ativo, gm_admin, list(gm_grupos)))


def test_salvar_grava_campos_do_geomap(banco, pessoa, como):
    adm = pessoa('adm1@x.com', admin=True)
    r = salvar(como, adm, '  Nova@X.com ', gm_ativo=True, gm_admin=True, gm_grupos=[3, 5])
    assert r and r[0] != 'ERRO', r          # função void: o psycopg 3 devolve [('',)]
    linha = banco.execute("select email, geomap_ativo, geomap_admin, geomap_grupos from hub.acessos where email='nova@x.com'").fetchone()
    assert linha == ('nova@x.com', True, True, [3, 5])


def test_salvar_cria_hub_usuarios_quando_a_conta_existe(banco, pessoa, como):
    adm = pessoa('adm2@x.com', admin=True)
    uid = banco.execute("insert into auth.users (email) values ('soconta@x.com') returning id").fetchone()[0]
    salvar(como, adm, 'soconta@x.com', nome='Só Conta', papel='editor', modulos=['plantio'])
    assert banco.execute('select nome, papel from hub.usuarios where id=%s', (uid,)).fetchone() == ('Só Conta', 'editor')
    assert banco.execute('select modulo_id from hub.usuario_modulos where usuario_id=%s', (uid,)).fetchall() == [('plantio',)]


def test_nao_admin_nao_salva(pessoa, como):
    comum = pessoa('comum@x.com')
    assert salvar(como, comum, 'outro@x.com')[0] == 'ERRO'


def test_nao_tira_o_proprio_admin(pessoa, como):
    adm = pessoa('adm3@x.com', admin=True)
    pessoa('adm3b@x.com', admin=True)
    r = salvar(como, adm, 'adm3@x.com', admin=False)
    assert r[0] == 'ERRO' and 'próprio admin' in r[1]


def test_nao_remove_o_ultimo_admin(banco, pessoa, como):
    banco.execute('update hub.acessos set admin = false')
    banco.execute('update hub.usuarios set admin = false')
    unico = pessoa('unico@x.com', admin=True)
    outro = pessoa('outro-adm@x.com', admin=True)
    banco.execute("update hub.acessos set admin = false where email = 'outro-adm@x.com'")  # só o 'unico' é admin na lista
    r = salvar(como, outro, 'unico@x.com', admin=False)
    assert r[0] == 'ERRO' and 'pelo menos um administrador' in r[1]
    assert unico


def test_situacao_traz_geomap_e_senha_provisoria(banco, pessoa, como):
    adm = pessoa('adm4@x.com', admin=True)
    uid = pessoa('prov@x.com')
    banco.execute('update hub.usuarios set precisa_trocar_senha = true where id=%s', (uid,))
    salvar(como, adm, 'prov@x.com', gm_ativo=True, gm_grupos=[2])
    linhas = {r[0]: r for r in como(adm, 'select email, geomap_ativo, geomap_grupos, precisa_trocar_senha from hub.acessos_situacao()')}
    assert linhas['prov@x.com'][1:] == (True, [2], True)


def test_senha_definida_so_desliga_a_propria(banco, pessoa, como):
    a, b = pessoa('a@x.com'), pessoa('b@x.com')
    banco.execute('update hub.usuarios set precisa_trocar_senha = true where id in (%s, %s)', (a, b))
    como(a, 'select hub.senha_definida()')
    assert banco.execute('select precisa_trocar_senha from hub.usuarios where id=%s', (a,)).fetchone() == (False,)
    assert banco.execute('select precisa_trocar_senha from hub.usuarios where id=%s', (b,)).fetchone() == (True,)
