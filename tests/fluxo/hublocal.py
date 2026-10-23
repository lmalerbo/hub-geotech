"""Postgres temporário com a cadeia de migrações do Hub (stubs de Supabase/PostGIS/Storage)."""
import json, re, shutil, socket, subprocess, tempfile, contextlib
from pathlib import Path
import psycopg
AQUI = Path(__file__).parent
SNAP = """select p.oid::regprocedure::text as s, pg_get_functiondef(p.oid) as d, coalesce(p.proacl::text,'') as acl,
                 pg_get_function_result(p.oid) as r
            from pg_proc p where p.pronamespace in ('hub'::regnamespace) and p.prokind='f'
             or (p.pronamespace='public'::regnamespace and p.proname='portal_arquivos')"""
VIEWS = "select c.oid::regclass::text, pg_get_viewdef(c.oid) from pg_class c where c.relkind='v' and c.relnamespace='hub'::regnamespace"

def preparar(sql):
    sql = re.sub(r'extensions\.geometry\([^)]*\)', 'extensions.geometry', sql)
    return re.sub(r'create extension if not exists postgis[^;]*;', '', sql, flags=re.I)

@contextlib.contextmanager
def banco(raiz):
    pasta = Path(tempfile.mkdtemp())
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); porta = s.getsockname()[1]
    subprocess.run(['initdb','-D',str(pasta),'-U','postgres','-A','trust','-E','UTF8'],check=True,capture_output=True)
    subprocess.run(['pg_ctl','-D',str(pasta),'-o',f'-p {porta}','-l',str(pasta/'log.txt'),'-w','start'],check=True,
                   stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        con = psycopg.connect(f'host=127.0.0.1 port={porta} user=postgres dbname=postgres', autocommit=True)
        con.execute((Path(raiz)/'tests/fluxo/stub_supabase.sql').read_text(encoding='utf-8'))
        con.execute('alter table auth.users add column encrypted_password text, add column banned_until timestamptz, '
                    'add column last_sign_in_at timestamptz, add column updated_at timestamptz')
        con.execute((AQUI/'stub_postgis.sql').read_text(encoding='utf-8'))
        yield con
    finally:
        subprocess.run(['pg_ctl','-D',str(pasta),'-m','fast','stop'],capture_output=True); shutil.rmtree(pasta, ignore_errors=True)

def migracoes(raiz, ate=None, sem=()):
    for m in sorted((Path(raiz)/'supabase/migrations').glob('*.sql')):
        if ate and m.name >= ate: break
        if m.name not in sem: yield m

def aplicar(con, arq):
    con.execute(preparar(Path(arq).read_text(encoding='utf-8')))

def foto(con):
    return {r[0]: {'d': r[1], 'acl': r[2], 'r': r[3]} for r in con.execute(SNAP).fetchall()}, dict(con.execute(VIEWS).fetchall())
