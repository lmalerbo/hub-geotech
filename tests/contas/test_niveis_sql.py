"""Nível por módulo (hub.usuario_modulos.nivel) e mapas individuais do GeoMap em hub.acessos."""
import json
from pathlib import Path

SALVAR = 'select hub.acesso_salvar(%s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb)'
MIGRACAO = Path(__file__).resolve().parents[2] / 'supabase' / 'migrations' / '20261023090000_niveis_por_modulo.sql'


def salvar(como, uid, email, nome='Fulano', admin=False, niveis=None, gm_ativo=False, gm_admin=False, gm_grupos=(), gm_mapas=()):
    return como(uid, SALVAR, (email, nome, admin, json.dumps(niveis or {}), gm_ativo, gm_admin, list(gm_grupos), json.dumps(list(gm_mapas))))


def niveis_de(banco, uid):
    return dict(banco.execute('select modulo_id, nivel from hub.usuario_modulos where usuario_id=%s', (uid,)).fetchall())


def test_grava_nivel_por_modulo_e_mantem_papel_para_voltar_atras(banco, pessoa, como):
    adm = pessoa('n-adm1@x.com', admin=True)
    uid = banco.execute("insert into auth.users (email) values ('n1@x.com') returning id").fetchone()[0]
    r = salvar(como, adm, 'n1@x.com', niveis={'plantio': 'editor', 'colheita': 'leitura', 'drone': 'solicitante', 'corretivos': 'editor'})
    assert r and r[0] != 'ERRO', r
    assert niveis_de(banco, uid) == {'plantio': 'editor', 'colheita': 'leitura', 'drone': 'solicitante', 'corretivos': 'editor'}
    assert banco.execute('select papel from hub.usuarios where id=%s', (uid,)).fetchone() == ('editor',)
    a = banco.execute("select niveis, modulos, papel from hub.acessos where email='n1@x.com'").fetchone()
    assert a[0]['drone'] == 'solicitante' and sorted(a[1]) == ['colheita', 'corretivos', 'drone', 'plantio'] and a[2] == 'editor'


def test_papel_resumo_ignora_corretivos(banco, pessoa, como):
    adm = pessoa('n-adm2@x.com', admin=True)
    salvar(como, adm, 'n2@x.com', niveis={'plantio': 'leitura', 'corretivos': 'editor'})
    assert banco.execute("select papel from hub.acessos where email='n2@x.com'").fetchone() == ('leitura',)


def test_recusa_niveis_invalidos(pessoa, como):
    adm = pessoa('n-adm3@x.com', admin=True)
    assert salvar(como, adm, 'n3@x.com', niveis={'plantio': 'solicitante'})[0] == 'ERRO'
    assert salvar(como, adm, 'n3@x.com', niveis={'plantio': 'dono'})[0] == 'ERRO'
    assert salvar(como, adm, 'n3@x.com', niveis={'corretivos': 'leitura'})[0] == 'ERRO'
    assert salvar(como, adm, 'n3@x.com', niveis={'naoexiste': 'leitura'})[0] == 'ERRO'


def test_grava_mapas_do_geomap_e_zera_sem_geomap(banco, pessoa, como):
    adm = pessoa('n-adm4@x.com', admin=True)
    salvar(como, adm, 'n4@x.com', gm_ativo=True, gm_grupos=[2], gm_mapas=[{'mapa_id': 12, 'pode_editar': True}])
    assert banco.execute("select geomap_mapas from hub.acessos where email='n4@x.com'").fetchone()[0] == [{'mapa_id': 12, 'pode_editar': True}]
    salvar(como, adm, 'n4@x.com', gm_ativo=False, gm_mapas=[{'mapa_id': 12, 'pode_editar': True}])
    assert banco.execute("select geomap_mapas from hub.acessos where email='n4@x.com'").fetchone()[0] == []


def test_recusa_mapa_malformado(pessoa, como):
    adm = pessoa('n-adm5@x.com', admin=True)
    assert salvar(como, adm, 'n5@x.com', gm_ativo=True, gm_mapas=[{'mapa_id': 'x', 'pode_editar': True}])[0] == 'ERRO'
    assert salvar(como, adm, 'n5@x.com', gm_ativo=True, gm_mapas=[{'mapa_id': 3}])[0] == 'ERRO'


def test_pode_editar_por_nivel(banco, pessoa, como):
    adm = pessoa('n-adm6@x.com', admin=True)
    uid = banco.execute("insert into auth.users (email) values ('n6@x.com') returning id").fetchone()[0]
    salvar(como, adm, 'n6@x.com', niveis={'plantio': 'editor', 'colheita': 'leitura'})
    assert como(uid, "select hub.pode_editar('plantio')") == [(True,)]
    assert como(uid, "select hub.pode_editar('colheita')") == [(False,)]
    assert como(uid, "select hub.pode_editar('preparo')") == [(False,)]
    assert como(adm, "select hub.pode_editar('preparo')") == [(True,)]


def test_situacao_traz_niveis_e_mapas(banco, pessoa, como):
    adm = pessoa('n-adm7@x.com', admin=True)
    salvar(como, adm, 'n7@x.com', niveis={'drone': 'solicitante'}, gm_ativo=True, gm_mapas=[{'mapa_id': 5, 'pode_editar': False}])
    linha = [l for l in como(adm, 'select email, niveis, geomap_mapas from hub.acessos_situacao()') if l[0] == 'n7@x.com'][0]
    assert linha[1] == {'drone': 'solicitante'} and linha[2] == [{'mapa_id': 5, 'pode_editar': False}]


def test_conversao_do_papel_para_niveis(banco):
    # Reaplica só o bloco de conversão sobre dados no formato antigo. Roda numa transação
    # desfeita no fim: o bloco recalcula todas as linhas e mexeria nos dados dos outros testes.
    uid = '00000000-0000-0000-0000-0000000000c1'
    sql = MIGRACAO.read_text(encoding='utf-8')
    bloco = sql[sql.index('-- >> conversão'):sql.index('-- << conversão')]
    with banco.transaction(force_rollback=True):
        banco.execute("insert into auth.users (id, email) values (%s, 'conv@x.com')", (uid,))
        banco.execute("insert into hub.usuarios (id, nome, papel) values (%s, 'Conv', 'solicitante')", (uid,))
        banco.execute("insert into hub.usuario_modulos (usuario_id, modulo_id) values (%s, 'drone'), (%s, 'plantio'), (%s, 'corretivos')",
                      (uid, uid, uid))
        banco.execute("insert into hub.acessos (email, nome, papel, modulos) values ('conv@x.com', 'Conv', 'solicitante', '{drone,plantio,corretivos}')")
        banco.execute(bloco)
        assert niveis_de(banco, uid) == {'drone': 'solicitante', 'plantio': 'leitura', 'corretivos': 'editor'}
        assert banco.execute("select niveis from hub.acessos where email='conv@x.com'").fetchone()[0] == \
            {'drone': 'solicitante', 'plantio': 'leitura', 'corretivos': 'editor'}


def test_nenhuma_checagem_le_papel(banco):
    nomes = [r[0] for r in banco.execute(
        "select proname from pg_proc where pronamespace = 'hub'::regnamespace and prosrc ~* '\\mpapel\\M'").fetchall()]
    assert set(nomes) <= {'acesso_salvar', 'acesso_remover'}, nomes
