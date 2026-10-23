"""Postgres local temporário (initdb em pasta temporária) com o stub do Supabase e as migrações do
Plantio/Preparo até o fluxo de projetos. Precisa de initdb/pg_ctl no PATH (Postgres do Scoop).
Mesmo modelo de tests/aplicacao."""
import shutil
import socket
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest

RAIZ = Path(__file__).resolve().parents[2]
MIGRACOES = ['20260928120000_hub_schema_inicial.sql', '20260928130000_talhoes_propriedade.sql',
             '20260929090000_projetos_revisoes.sql', '20260929110000_documentos_mapa_e_status_guardado.sql',
             '20260930090000_acoes_plantio_preparo.sql', '20260930120000_envio_de_arquivos.sql',
             '20261001100000_portal_publico.sql', '20261023100000_fluxo_projetos.sql']


def _porta_livre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope='session')
def pg(tmp_path_factory):
    if not shutil.which('initdb'):
        pytest.skip('Postgres local (initdb) não encontrado no PATH')
    pasta, porta = tmp_path_factory.mktemp('pg'), _porta_livre()
    subprocess.run(['initdb', '-D', str(pasta), '-U', 'postgres', '-A', 'trust', '-E', 'UTF8'], check=True, capture_output=True)
    # Sem capture_output: no Windows o postgres herda o pipe e o pg_ctl nunca devolve (trava o pytest).
    subprocess.run(['pg_ctl', '-D', str(pasta), '-o', f'-p {porta}', '-l', str(pasta / 'log.txt'), '-w', 'start'],
                   check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        yield porta
    finally:
        subprocess.run(['pg_ctl', '-D', str(pasta), '-m', 'fast', 'stop'], capture_output=True)


def montar(porta, nome, antes_da_ultima=None):
    """Cria um banco novo com as migrações. antes_da_ultima(con) roda antes da migração do fluxo
    (para semear dados no formato antigo e conferir a migração)."""
    adm = psycopg.connect(f'host=127.0.0.1 port={porta} user=postgres dbname=postgres', autocommit=True)
    adm.execute(f'create database {nome}')
    adm.close()
    con = psycopg.connect(f'host=127.0.0.1 port={porta} user=postgres dbname={nome}', autocommit=True)
    con.execute((Path(__file__).parent / 'stub_supabase.sql').read_text(encoding='utf-8'))
    for m in MIGRACOES:
        if m == MIGRACOES[-1] and antes_da_ultima:
            antes_da_ultima(con)
        con.execute((RAIZ / 'supabase' / 'migrations' / m).read_text(encoding='utf-8'))
    return con


@pytest.fixture(scope='session')
def montar_banco(pg):
    """montar_banco(nome, antes_da_ultima=None) -> conexão com um banco novo (ver montar)."""
    return lambda nome, antes_da_ultima=None: montar(pg, nome, antes_da_ultima)


@pytest.fixture(scope='session')
def banco(pg):
    con = montar(pg, 'fluxo')
    yield con
    con.close()


_cod = iter(range(20001, 99999))


@pytest.fixture
def fazenda(banco):
    """fazenda(talhoes=5) -> cod_faz novo, com os talhões 1..n no Plantio e no Preparo."""
    def _cria(talhoes=5, nome='FAZENDA TESTE'):
        cod = next(_cod)
        banco.execute('insert into hub.fazendas (cod_faz, nome) values (%s, %s)', (cod, nome))
        for n in range(1, talhoes + 1):
            banco.execute('insert into hub.talhoes (cod_faz, talhao_num) values (%s, %s)', (cod, n))
            banco.execute('insert into hub.talhao_plantio (layer) values (%s)', (cod * 1000 + n,))
            banco.execute('insert into hub.talhao_preparo (layer) values (%s)', (cod * 1000 + n,))
        return cod
    return _cria


@pytest.fixture
def pessoa(banco):
    """pessoa(papel='editor', modulos=('plantio','preparo')) -> uuid de um usuário do Hub."""
    def _cria(papel='editor', modulos=('plantio', 'preparo')):
        uid = uuid.uuid4()
        banco.execute('insert into auth.users (id, email) values (%s, %s)', (uid, f'{uid}@t.local'))
        banco.execute('insert into hub.usuarios (id, nome, papel) values (%s, %s, %s)', (uid, 'Teste', papel))
        for m in modulos:
            banco.execute('insert into hub.usuario_modulos values (%s, %s)', (uid, m))
        return uid
    return _cria


@pytest.fixture
def como(banco):
    """como(uid, sql, params) -> executa como 'authenticated' com auth.uid() = uid; devolve linhas ou ('ERRO', msg)."""
    def _exec(uid, sql, params=()):
        with banco.transaction():
            banco.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(uid),))
            banco.execute("select set_config('request.jwt.claim.role', 'authenticated', true)")
            banco.execute('set local role authenticated')
            try:
                with banco.transaction():
                    cur = banco.execute(sql, params)
                    return cur.fetchall() if cur.description else None
            except psycopg.Error as e:
                return ('ERRO', e.diag.message_primary)
    return _exec
