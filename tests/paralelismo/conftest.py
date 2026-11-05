"""Postgres local com as migrações de acesso + fluxo + Paralelismo. O Postgres local não tem PostGIS:
só nestes testes, a coluna geométrica vira texto e as funções ST_* são stubs."""
import json
import uuid
from pathlib import Path

import psycopg
import pytest

from tests.contas.conftest import como  # noqa: F401  (fixture reaproveitado)
from tests.fluxo import conftest as fluxo
from tests.fluxo.conftest import pg  # noqa: F401  (fixture reaproveitado)

RAIZ = Path(__file__).resolve().parents[2]
MIGRACOES = sorted(fluxo.MIGRACOES + ['20261003090000_modulo_colheita.sql', '20261005090000_admin_acessos_ferramentas.sql', '20261012090000_login_unico.sql',
                                      '20261023090000_niveis_por_modulo.sql', '20261029090000_apresentacao_acesso.sql',
                                      '20261104090000_paralelismo.sql', '20261105090000_paralelismo_cartao.sql'])
STUB_POSTGIS = """
create schema if not exists extensions;
create function extensions.st_geomfromgeojson(text) returns text language sql immutable as 'select $1';
create function extensions.st_setsrid(text, int) returns text language sql immutable as 'select $1';
create function extensions.st_asgeojson(text) returns text language sql immutable as 'select $1';
create function extensions.st_asgeojson(text, int) returns text language sql immutable as 'select $1';
create table hub.talhao_geom (cod_faz int not null, talhao_num int not null, geom text not null,
                              area_ha numeric not null, primary key (cod_faz, talhao_num));
"""


def montar(porta, nome):
    adm = psycopg.connect(f'host=127.0.0.1 port={porta} user=postgres dbname=postgres', autocommit=True)
    adm.execute(f'create database {nome}')
    adm.close()
    con = psycopg.connect(f'host=127.0.0.1 port={porta} user=postgres dbname={nome}', autocommit=True)
    con.execute((Path(fluxo.__file__).parent / 'stub_supabase.sql').read_text(encoding='utf-8'))
    con.execute("set check_function_bodies = off")
    for m in MIGRACOES:
        sql = (RAIZ / 'supabase' / 'migrations' / m).read_text(encoding='utf-8')
        if m.endswith('_paralelismo.sql'):
            con.execute(STUB_POSTGIS)
            sql = sql.replace('extensions.geometry(LineString, 31983)', 'text')
        con.execute(sql)
    return con


@pytest.fixture(scope='session')
def banco(pg):  # noqa: F811
    con = montar(pg, 'paralelismo')
    yield con
    con.close()


@pytest.fixture
def banco_descartavel(pg):  # noqa: F811
    con = montar(pg, f'paralelismo_{uuid.uuid4().hex[:8]}')
    yield con
    con.close()


@pytest.fixture
def conta(banco):
    """conta(nivel) -> uuid de uma conta com esse nível no Paralelismo ('admin' = admin do Hub; None = sem módulo)."""
    def _cria(nivel):
        uid = uuid.uuid4()
        banco.execute('insert into auth.users (id, email) values (%s, %s)', (uid, f'{uid}@x.com'))
        banco.execute('insert into hub.usuarios (id, nome, admin) values (%s, %s, %s)', (uid, 'Fulano', nivel == 'admin'))
        if nivel in ('leitura', 'solicitante', 'editor'):
            banco.execute("insert into hub.usuario_modulos (usuario_id, modulo_id, nivel) values (%s, 'paralelismo', %s)",
                          (uid, nivel))
        return uid
    return _cria


_cod = iter(range(50001, 59999))
_sha = iter(range(1, 99999))


@pytest.fixture
def cod_novo():
    return lambda: next(_cod)


@pytest.fixture
def enviar(como):  # noqa: F811
    """enviar(uid, cod ou [cods], base=None, shas=None, amostras=100, op='torta', rid=None, **extra) -> id ou ('ERRO', msg).
    rid reaproveita um id já reservado; extra sobrescreve campos do payload."""
    def _envia(uid, cod, base=None, shas=None, amostras=100, op='torta', rid=None, **extra):
        cods = cod if isinstance(cod, list) else [cod]
        cod = cods[0]
        rid = rid or como(uid, 'select hub.paralelismo_preparar_parte()')[0][0]
        shas = shas or [f'sha{next(_sha)}']
        r = como(uid, 'select hub.paralelismo_enviar(%s::jsonb)', (json.dumps({
            'rodada_id': rid, 'descricao': 'teste', 'partes': [{'url': 'https://x/u', 'bytes': 1, 'sha256': 'p'}],
            'arquivos': [{'sha256': s, 'caminho': f'{s}.jdl', 'bytes': 9, 'tipo': 'jdl', 'frota': '64086', 'cod_faz': cod}
                         for s in shas],
            'linhas': [{'operacao': op, 'cod_faz': c, 'frota': '64086', 'data': '2026-10-03',
                        'coords': [[0, rid], [100, rid]]} for c in cods],
            'analises': [{'operacao': op, 'cod_faz': c, 'mes': '2026-10-01', 'amostras': amostras,
                          'aderentes': amostras - 10, 'acima': 6, 'abaixo': 4, 'fora_talhao': 2,
                          'pll_total': amostras + 2, 'pll_aderentes': amostras - 9, 'base_analise_id': base,
                          'talhoes': [{'talhao_num': 1, 'amostras': amostras, 'aderentes': amostras - 10, 'acima': 6,
                                       'abaixo': 4, 'media_m': 3.012, 'frotas': ['64086']}]} for c in cods],
            **extra}),))
        return r if r[0] == 'ERRO' else r[0][0]
    return _envia
