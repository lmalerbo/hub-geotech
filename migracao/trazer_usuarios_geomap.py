"""Virada do login único (uma vez só): leva as pessoas do GeoMap para o Hub.

Para cada pessoa do GeoMap: conta no Hub com o MESMO hash de senha (ninguém
troca de senha), hub.usuarios e hub.acessos com os campos do GeoMap (ativo,
admin, grupos), mantendo os campos do Hub de quem já tinha acesso. Quem ainda
está com a senha provisória fixa do GeoMap não recebe esse hash: fica com
"precisa trocar senha" e o admin entrega uma provisória do Hub ("Redefinir
senha" na tela Usuários) — o script lista essas pessoas.

Lê o banco do GeoMap só em modo leitura. Nunca imprime hash.
Uso:  python migracao/trazer_usuarios_geomap.py [--simular]
"""
import argparse
import os
import ssl
import sys
import urllib.parse

import pg8000.native
import requests
import truststore

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ingestao'))
from comum import Hub, carregar_config, carregar_env  # noqa: E402

BLOQUEIO = '876000h'


def url_banco_geomap():
    url = carregar_env().get('GEOMAP_DATABASE_URL')
    if url:
        return url
    return next(linha.split('=', 1)[1].strip().strip('"').strip("'")
                for linha in open(carregar_config()['geomap_env'], encoding='utf-8')
                if linha.startswith('DATABASE_URL='))


def ler_geomap():
    u = urllib.parse.urlparse(url_banco_geomap())
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    con = pg8000.native.Connection(
        user=urllib.parse.unquote(u.username), password=urllib.parse.unquote(u.password or ''),
        host=u.hostname, port=u.port or 5432, database=u.path.lstrip('/'), ssl_context=ctx, timeout=30)
    try:
        con.run('set transaction read only')
        linhas = con.run("""select lower(u.email), u.nome, u.senha_hash, u.status, u.papel, u.precisa_trocar_senha,
                                   coalesce(array_agg(ug.grupo_id) filter (where ug.grupo_id is not null), '{}')
                              from usuarios u left join usuarios_grupos ug on ug.usuario_id = u.id
                             group by u.id""")
    finally:
        con.close()
    return {e: {'nome': n, 'hash': h, 'ativo': s == 'ativo', 'admin': p == 'admin',
                'senha_provisoria': bool(prov), 'grupos': sorted(g)}
            for e, n, h, s, p, prov, g in linhas}


def planejar(geomap, acessos):
    """Lista de ações por e-mail (pura, sem rede)."""
    plano = []
    for email in sorted(set(geomap) | set(acessos)):
        g, a = geomap.get(email), acessos.get(email)
        gm_ativo = bool(g and g['ativo'])
        acesso = {
            'email': email,
            'nome': (a or {}).get('nome') or g['nome'],
            'papel': (a or {}).get('papel', 'leitura'),
            'admin': bool((a or {}).get('admin')),
            'modulos': list((a or {}).get('modulos') or []),
            'geomap_ativo': gm_ativo,
            'geomap_admin': bool(g and g['ativo'] and g['admin']),
            'geomap_grupos': list(g['grupos']) if gm_ativo else [],
        }
        tem_acesso = bool(acesso['modulos']) or gm_ativo or acesso['admin']
        plano.append({
            'email': email, 'acesso': acesso,
            'copiar_hash': bool(g and not g['senha_provisoria']),
            'hash': g['hash'] if g else None,
            'precisa_trocar_senha': bool(g and g['senha_provisoria']),
            'bloquear': not tem_acesso,
        })
    return plano


class AuthAdmin:
    def __init__(self):
        env = carregar_env()
        self.url = env['SUPABASE_URL'].rstrip('/') + '/auth/v1/admin/users'
        k = env['SUPABASE_SERVICE_ROLE_KEY']
        self.headers = {'apikey': k, 'Authorization': f'Bearer {k}', 'Content-Type': 'application/json'}

    def _ok(self, r):
        if not r.ok:
            raise RuntimeError(f'Auth: HTTP {r.status_code} {r.text[:300]}')
        return r.json()

    def por_email(self):
        contas, pagina = {}, 1
        while True:
            lote = self._ok(requests.get(self.url, params={'page': pagina, 'per_page': 200}, headers=self.headers, timeout=60))['users']
            contas.update({c['email'].lower(): c for c in lote})
            if len(lote) < 200:
                return contas
            pagina += 1

    def criar(self, email, nome):
        return self._ok(requests.post(self.url, headers=self.headers, timeout=60,
                                      json={'email': email, 'email_confirm': True, 'user_metadata': {'nome': nome}}))['id']

    def bloquear(self, id_, sim):
        self._ok(requests.put(f'{self.url}/{id_}', headers=self.headers, timeout=60,
                              json={'ban_duration': BLOQUEIO if sim else 'none'}))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--simular', action='store_true')
    args = ap.parse_args()
    hub, auth = Hub(), AuthAdmin()
    acessos = {a['email']: a for a in hub.selecionar('acessos', 'email,nome,papel,admin,modulos', {'order': 'email'})}
    plano, contas = planejar(ler_geomap(), acessos), auth.por_email()
    pendentes = []
    for p in plano:
        a = p['acesso']
        print(f"  {p['email']}: {'atualizar' if p['email'] in contas else 'criar'} | Hub {a['papel']}"
              f"{' + admin' if a['admin'] else ''} {','.join(a['modulos']) or '-'} | GeoMap "
              f"{('admin ' if a['geomap_admin'] else '') + 'grupos ' + str(a['geomap_grupos']) if a['geomap_ativo'] else 'não'}"
              f"{' | BLOQUEADA' if p['bloquear'] else ''}{' | precisa senha provisória do Hub' if p['precisa_trocar_senha'] else ''}")
        if p['precisa_trocar_senha']:
            pendentes.append(p['email'])
        if args.simular:
            continue
        conta = contas.get(p['email'])
        id_ = conta['id'] if conta else auth.criar(p['email'], a['nome'])
        if p['copiar_hash']:
            hub.rpc('definir_senha_hash', {'p_usuario': id_, 'p_hash': p['hash']})
        hub.upsert('acessos', [a], 'email')
        hub.upsert('usuarios', [{'id': id_, 'nome': a['nome'], 'papel': a['papel'], 'admin': a['admin'],
                                 'precisa_trocar_senha': p['precisa_trocar_senha']}], 'id')
        requests.delete(f'{hub.url}/usuario_modulos', params={'usuario_id': f'eq.{id_}'}, headers=hub.headers, timeout=60).raise_for_status()
        if a['modulos']:
            hub.upsert('usuario_modulos', [{'usuario_id': id_, 'modulo_id': m} for m in a['modulos']], 'usuario_id,modulo_id')
        if bool(conta and conta.get('banned_until')) != p['bloquear'] or not conta:
            auth.bloquear(id_, p['bloquear'])
    if pendentes:
        print('\nAinda com a senha provisória do GeoMap — use "Redefinir senha" no Hub para cada um:')
        for e in pendentes:
            print('  ', e)
    print('Simulação: nada foi gravado.' if args.simular else f'{len(plano)} pessoa(s) no Hub.')


if __name__ == '__main__':
    main()
