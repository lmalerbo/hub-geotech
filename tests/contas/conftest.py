"""Postgres local temporário (initdb em pasta temporária) com o stub do Supabase
e as migrações de acesso. Precisa de initdb/pg_ctl no PATH (Postgres do Scoop)."""
import os
import shutil
import socket
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest

RAIZ = Path(__file__).resolve().parents[2]
MIGRACOES = ['20261005090000_admin_acessos_ferramentas.sql', '20261012090000_login_unico.sql']


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
    """pessoa(email, admin=False) -> uuid de uma conta auth + hub.usuarios + hub.acessos."""
    def _cria(email, admin=False, com_acesso=True):
        uid = uuid.uuid4()
        banco.execute('insert into auth.users (id, email) values (%s, %s)', (uid, email))
        banco.execute('insert into hub.usuarios (id, nome, admin) values (%s, %s, %s)', (uid, email.split('@')[0], admin))
        if com_acesso:
            banco.execute('insert into hub.acessos (email, nome, admin) values (%s, %s, %s)', (email, email.split('@')[0], admin))
        return uid
    return _cria


@pytest.fixture
def como(banco):
    """como(uid, sql, params) -> executa como 'authenticated' com auth.uid() = uid; devolve linhas ou a mensagem de erro."""
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
