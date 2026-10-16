"""Postgres local temporário (initdb em pasta temporária) com o stub do Supabase e as migrações dos
Mapas de aplicação. Precisa de initdb/pg_ctl no PATH (Postgres do Scoop). Mesmo modelo de tests/contas."""
import shutil
import socket
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest

RAIZ = Path(__file__).resolve().parents[2]
MIGRACOES = ['20261015090000_corretivos.sql', '20261016090000_corretivos_transacoes.sql',
             '20261017090000_mapas_aplicacao.sql']


def _porta_livre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope='session')
def banco(tmp_path_factory):
    if not shutil.which('initdb'):
        pytest.skip('Postgres local (initdb) não encontrado no PATH')
    pasta, porta = tmp_path_factory.mktemp('pg'), _porta_livre()
    subprocess.run(['initdb', '-D', str(pasta), '-U', 'postgres', '-A', 'trust', '-E', 'UTF8'], check=True, capture_output=True)
    # Sem capture_output: no Windows o postgres herda o pipe e o pg_ctl nunca devolve (trava o pytest).
    subprocess.run(['pg_ctl', '-D', str(pasta), '-o', f'-p {porta}', '-l', str(pasta / 'log.txt'), '-w', 'start'],
                   check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        con = psycopg.connect(f'host=127.0.0.1 port={porta} user=postgres dbname=postgres', autocommit=True)
        con.execute((Path(__file__).parent / 'stub_supabase.sql').read_text(encoding='utf-8'))
        for m in MIGRACOES:
            con.execute((RAIZ / 'supabase' / 'migrations' / m).read_text(encoding='utf-8'))
        yield con
        con.close()
    finally:
        subprocess.run(['pg_ctl', '-D', str(pasta), '-m', 'fast', 'stop'], capture_output=True)


@pytest.fixture
def pessoa(banco):
    """pessoa(modulo=True) -> uuid de um usuário do Hub, com ou sem o módulo da ferramenta."""
    def _cria(modulo=True):
        uid = uuid.uuid4()
        banco.execute('insert into auth.users (id, email) values (%s, %s)', (uid, f'{uid}@t.local'))
        banco.execute('insert into hub.usuarios (id, nome) values (%s, %s)', (uid, 'Teste'))
        if modulo:
            banco.execute("insert into hub.usuario_modulos values (%s, 'corretivos')", (uid,))
        return uid
    return _cria


@pytest.fixture
def como(banco):
    """como(uid, sql, params) -> executa como 'authenticated' com auth.uid() = uid; devolve linhas ou ('ERRO', msg)."""
    def _exec(uid, sql, params=()):
        with banco.transaction():
            banco.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(uid),))
            banco.execute('set local role authenticated')
            try:
                with banco.transaction():
                    cur = banco.execute(sql, params)
                    return cur.fetchall() if cur.description else None
            except psycopg.Error as e:
                return ('ERRO', e.diag.message_primary)
    return _exec
