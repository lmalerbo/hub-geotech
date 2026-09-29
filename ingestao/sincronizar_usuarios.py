"""Sincroniza as contas do Hub com o GeoMap (mesmo e-mail, mesma senha).

Para cada pessoa de ingestao/usuarios_hub.json:
  - cria a conta no Supabase Auth, se não existir;
  - copia o hash da senha do GeoMap (o GeoMap é o dono da senha);
  - bloqueia no Hub quem está inativo no GeoMap, desbloqueia quem voltou;
  - grava papel e módulos em hub.usuarios / hub.usuario_modulos.

Lê o banco do GeoMap só em modo leitura. Nunca imprime hash de senha.

Uso:  python ingestao/sincronizar_usuarios.py [--apenas email] [--simular]
"""

import argparse
import json
import os
import ssl
import urllib.parse

import pg8000.native
import requests
import truststore

from comum import RAIZ, Hub, carregar_config, carregar_env

BLOQUEIO = '876000h'   # ~100 anos: "bloqueado até alguém desbloquear"


def url_banco_geomap():
    # No servidor Geo a conexão fica no próprio .env do Hub (GEOMAP_DATABASE_URL);
    # no PC de desenvolvimento, cai no .env do backend do GeoMap.
    url = carregar_env().get('GEOMAP_DATABASE_URL')
    if url:
        return url
    return next(linha.split('=', 1)[1].strip().strip('"').strip("'")
                for linha in open(carregar_config()['geomap_env'], encoding='utf-8')
                if linha.startswith('DATABASE_URL='))


def usuarios_geomap():
    url = url_banco_geomap()
    u = urllib.parse.urlparse(url)
    # Certificados do Windows: a rede da empresa tem um firewall que inspeciona
    # TLS com certificado próprio, que só o repositório do Windows conhece.
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    con = pg8000.native.Connection(
        user=urllib.parse.unquote(u.username), password=urllib.parse.unquote(u.password or ''),
        host=u.hostname, port=u.port or 5432, database=u.path.lstrip('/'), ssl_context=ctx, timeout=30)
    try:
        con.run('set transaction read only')
        linhas = con.run('select lower(email), nome, senha_hash, status, precisa_trocar_senha from usuarios')
    finally:
        con.close()
    return {email: {'nome': nome, 'hash': h, 'ativo': status == 'ativo', 'senha_provisoria': bool(provisoria)}
            for email, nome, h, status, provisoria in linhas}


class AuthAdmin:
    def __init__(self):
        env = carregar_env()
        self.url = env['SUPABASE_URL'].rstrip('/') + '/auth/v1/admin/users'
        chave = env['SUPABASE_SERVICE_ROLE_KEY']
        self.headers = {'apikey': chave, 'Authorization': f'Bearer {chave}', 'Content-Type': 'application/json'}

    def _checar(self, r):
        if not r.ok:
            raise RuntimeError(f'Auth: HTTP {r.status_code} {r.text[:300]}')
        return r.json()

    def por_email(self):
        contas, pagina = {}, 1
        while True:
            lote = self._checar(requests.get(self.url, params={'page': pagina, 'per_page': 200},
                                             headers=self.headers, timeout=60))['users']
            contas.update({c['email'].lower(): c for c in lote})
            if len(lote) < 200:
                return contas
            pagina += 1

    def criar(self, email, nome):
        return self._checar(requests.post(self.url, headers=self.headers, timeout=60, json={
            'email': email, 'email_confirm': True, 'user_metadata': {'nome': nome}}))['id']

    def bloquear(self, id_, bloquear):
        self._checar(requests.put(f'{self.url}/{id_}', headers=self.headers, timeout=60,
                                  json={'ban_duration': BLOQUEIO if bloquear else 'none'}))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--apenas', help='sincroniza só este e-mail')
    ap.add_argument('--simular', action='store_true', help='mostra o que faria, sem gravar')
    args = ap.parse_args()

    with open(os.path.join(RAIZ, 'ingestao', 'usuarios_hub.json'), encoding='utf-8') as f:
        desejados = json.load(f)['usuarios']
    if args.apenas:
        desejados = [d for d in desejados if d['email'].lower() == args.apenas.lower()]

    geomap = usuarios_geomap()
    auth, hub = AuthAdmin(), Hub()
    contas = auth.por_email()

    for d in desejados:
        email = d['email'].lower()
        g = geomap.get(email)
        if not g:
            print(f'  ⚠ {email}: não existe no GeoMap — cadastre lá primeiro')
            continue
        conta = contas.get(email)
        acao = 'atualizar' if conta else 'criar'
        # Cadastro novo no GeoMap nasce com uma senha provisória padrão (a
        # troca é obrigada pelo GeoMap, não pelo Hub): até a pessoa definir a
        # própria senha lá, a conta no Hub fica bloqueada.
        liberado = g['ativo'] and not g['senha_provisoria']
        situacao = ('ativo' if liberado else
                    'INATIVO no GeoMap → bloqueado no Hub' if not g['ativo'] else
                    'ainda com senha provisória no GeoMap → bloqueado no Hub até definir a própria')
        print(f"  {email}: {acao} | {d['papel']}{' + admin' if d['admin'] else ''} | {', '.join(d['modulos'])} | {situacao}")
        if args.simular:
            continue

        id_ = conta['id'] if conta else auth.criar(email, g['nome'])
        if not g['senha_provisoria']:
            hub.rpc('definir_senha_hash', {'p_usuario': id_, 'p_hash': g['hash']})
        esta_bloqueado = bool(conta and conta.get('banned_until'))
        if not conta or esta_bloqueado == liberado:
            auth.bloquear(id_, not liberado)
        hub.upsert('usuarios', [{'id': id_, 'nome': g['nome'], 'papel': d['papel'], 'admin': d['admin']}], 'id')
        requests.delete(f'{hub.url}/usuario_modulos', params={'usuario_id': f'eq.{id_}'},
                        headers=hub.headers, timeout=60).raise_for_status()
        hub.upsert('usuario_modulos', [{'usuario_id': id_, 'modulo_id': m} for m in d['modulos']],
                   'usuario_id,modulo_id')

    print('Simulação: nada foi gravado.' if args.simular else 'Contas sincronizadas.')


if __name__ == '__main__':
    main()
