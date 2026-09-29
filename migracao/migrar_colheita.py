"""Migração única da Colheita: traz para o Hub o que já existe no Expo_safra.
Só LÊ o sistema antigo; nada é alterado lá.

O que é trazido:
  - Tipo de linha e ciclo de cada talhão (o status é calculado no Hub).
    Talhão Sem Linhas sem ciclo foi marcado nesta safra → ciclo da safra atual.
  - Histórico de registros (log_exportacoes) → log da Colheita, com usuário.
  - Arquivos das GitHub Releases (Exp1L/Exp2L .dwg/.zip e o Mapa .pdf):
    viram projetos Rev0 (o Expo_safra não numerava revisões). Blocos
    ("10531+10627_Exp1L.dwg") viram projeto personalizado ligado às fazendas.
    O arquivo fica onde está, só é referenciado.

A gravação é feita pela função hub.migrar_colheita_antiga, numa transação só.

Uso:
  python migracao/migrar_colheita.py --simular   só lê e mostra o plano
  python migracao/migrar_colheita.py --ensaio    grava, confere e desfaz
  python migracao/migrar_colheita.py             grava de verdade (corte)
"""

import argparse
import collections
import json
import os
import re
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ingestao'))
from comum import RAIZ, Hub, carregar_config  # noqa: E402
from sincronizar_usuarios import AuthAdmin  # noqa: E402

TIPOS = {'VANT', 'PROJETO', 'SEM LINHAS'}
# 10967_TABOCA.4_Exp1L.dwg | 10623.AGROPASTORIL.AMERICANA.Exp2L.zip | 10951_GUANABARA.102_Exp.Mapa.pdf
RE_INDIVIDUAL = re.compile(r'^(\d{5})[._].*?[._]Exp(1L|2L|\.?Mapa)\.(dwg|zip|pdf)$', re.IGNORECASE)
# 10531+10627_Exp1L.dwg | 10531+10627_Exp.Mapa.pdf
RE_BLOCO = re.compile(r'^(\d{5}(?:\+\d{5})+)_Exp(1L|2L|\.?Mapa)\.(dwg|zip|pdf)$', re.IGNORECASE)
DOC = {'1l': 'exp1l', '2l': 'exp2l', 'mapa': 'mapa', '.mapa': 'mapa'}
EXT_OK = {'exp1l': {'dwg', 'zip'}, 'exp2l': {'dwg', 'zip'}, 'mapa': {'pdf'}}


class Antigo:
    def __init__(self):
        html = open(os.path.join(carregar_config()['colheita_antiga']['formulario']), encoding='utf-8').read()
        self.url = re.search(r"SUPABASE_URL\s*=\s*'([^']+)'", html).group(1).rstrip('/') + '/rest/v1'
        self.chave = re.search(r"SUPABASE_KEY\s*=\s*'([^']+)'", html).group(1)

    def ler(self, tabela, select, ordem):
        linhas, inicio = [], 0
        while True:
            r = requests.get(f'{self.url}/{tabela}', params={'select': select, 'order': ordem},
                             headers={'apikey': self.chave, 'Authorization': f'Bearer {self.chave}',
                                      'Range': f'{inicio}-{inicio + 999}'}, timeout=60)
            r.raise_for_status()
            lote = r.json()
            linhas += lote
            if len(lote) < 1000:
                return linhas
            inicio += 1000


def assets(repo):
    lista, url = [], f'https://api.github.com/repos/{repo}/releases?per_page=100'
    while url:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        for rel in r.json():
            lista += [(rel['tag_name'], a) for a in rel.get('assets', [])]
        m = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get('Link', ''))
        url = m.group(1) if m else None
    return lista


def planejar_arquivos(repo, fazendas_hub):
    """(modulo 'colheita') dono → documento → {nome: asset}. dono = cod_faz ou
    tupla de cod_faz (bloco). O mesmo arquivo de bloco está em várias releases:
    entra uma vez."""
    docs = collections.defaultdict(lambda: collections.defaultdict(dict))
    fora, sem_padrao, sem_fazenda = [], [], collections.Counter()
    for tag, a in assets(repo):
        nome = a['name']
        m = RE_BLOCO.match(nome) or RE_INDIVIDUAL.match(nome)
        if not m:
            sem_padrao.append(nome)
            continue
        doc, ext = DOC[m.group(2).lower()], m.group(3).lower()
        if ext not in EXT_OK[doc]:
            sem_padrao.append(nome)
            continue
        if '+' in m.group(1):
            dono = tuple(sorted(int(c) for c in m.group(1).split('+')))
            faltando = [c for c in dono if c not in fazendas_hub]
            if faltando:
                sem_fazenda[dono] += 1
                continue
        else:
            dono = int(m.group(1))
            if dono not in fazendas_hub:
                sem_fazenda[dono] += 1
                continue
        docs[dono][doc].setdefault(nome, a)
    return docs, sem_padrao, sem_fazenda


def montar_projetos(docs):
    projetos = []
    for dono, por_doc in docs.items():
        bloco = isinstance(dono, tuple)
        projetos.append({
            'modulo': 'colheita',
            'tipo': 'personalizado' if bloco else 'individual',
            'cod_faz': None if bloco else dono,
            'nome': 'BLOCO ' + '+'.join(map(str, dono)) if bloco else str(dono),
            'revisoes': [{
                'documento': doc, 'numero': 0, 'motivo': None, 'vigente': True,
                'criado_em': min(a['created_at'] for a in arqs.values()),
                'origens': list(dono) if bloco else [],
                'arquivos': [{'nome': n, 'url': a['browser_download_url'], 'tamanho': a['size'],
                              'publicado_em': a['created_at']} for n, a in sorted(arqs.items())],
            } for doc, arqs in por_doc.items()],
        })
    return projetos


def ids_dos_usuarios_antigos(usados):
    with open(os.path.join(RAIZ, 'ingestao', 'usuarios_hub.json'), encoding='utf-8') as f:
        email_de = {u['usuario_antigo']: u['email'].lower()
                    for u in json.load(f)['usuarios'] if u.get('usuario_antigo')}
    contas = AuthAdmin().por_email()
    faltando = sorted(u for u in usados if email_de.get(u) not in contas)
    if faltando:
        sys.exit(f'Sem conta no Hub para o login antigo {faltando}: preencha usuario_antigo em '
                 'ingestao/usuarios_hub.json e rode sincronizar_usuarios.py.')
    return {u: contas[email_de[u]]['id'] for u in usados}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument('--simular', action='store_true', help='lê tudo e mostra o plano, sem gravar')
    modo.add_argument('--ensaio', action='store_true', help='grava, confere e desfaz (nada fica gravado)')
    args = ap.parse_args()

    cfg = carregar_config()['colheita_antiga']
    antigo, hub = Antigo(), Hub()
    C = collections.Counter
    safra = hub.rpc('safra_colheita')
    fazendas_hub = {f['cod_faz'] for f in hub.selecionar('fazendas', 'cod_faz')}
    demanda = {t['layer'] for t in hub.selecionar('talhao_colheita', 'layer')}

    # ── Tipo de linha e ciclo por talhão ────────────────────────────────
    antigos = antigo.ler('programacao', 'layer,status,tipo_linha,ciclo', 'layer')
    log_antigo = antigo.ler('log_exportacoes', 'id,layer,usuario,tipo_linha,ciclo,status,registrado_em,data_consolidacao', 'id')
    quando = lambda r: r['registrado_em'] or r['data_consolidacao']
    ultimo_ciclo = {}
    for r in sorted(log_antigo, key=lambda r: (quando(r) or '', r['id'])):
        if r['ciclo']:
            ultimo_ciclo[r['layer']] = r['ciclo']

    talhoes, descartes = [], C()
    for a in antigos:
        tipo = a['tipo_linha'] if a['tipo_linha'] in TIPOS else None
        if a['status'] == 'SEM LINHAS':
            tipo = 'SEM LINHAS'
        if not tipo:
            descartes['sem tipo de linha'] += 1
            continue
        ciclo = a['ciclo'] or ultimo_ciclo.get(a['layer']) or (safra if tipo == 'SEM LINHAS' else None)
        talhoes.append({'layer': a['layer'], 'tipo_linha': tipo, 'ciclo': ciclo})
    na_demanda = [t for t in talhoes if t['layer'] in demanda]
    fora_demanda = [t for t in talhoes if t['layer'] not in demanda]
    status_novo = C('A FAZER' if not t['ciclo'] else 'REAVALIAR' if t['ciclo'] != safra
                    else t['tipo_linha'] if t['tipo_linha'] == 'SEM LINHAS' else 'CONCLUIDO' for t in na_demanda)
    print(f'COLHEITA — {len(antigos)} talhões no Expo_safra, {len(talhoes)} com tipo de linha')
    print(f'  {len(na_demanda)} estão na demanda do ICOL (entram) | {len(fora_demanda)} fora do ICOL atual (não entram)')
    print('  status que vão ficar (dos que entram):', dict(status_novo))
    print('  sem tipo (continuam A FAZER):', dict(descartes))
    if fora_demanda:
        por_faz = C(t['layer'] // 1000 for t in fora_demanda)
        print(f'  fora do ICOL: {len(por_faz)} fazendas, ex.:', por_faz.most_common(8))

    # ── Histórico ───────────────────────────────────────────────────────
    usados = sorted({l['usuario'] for l in log_antigo if l['usuario']})
    print(f'\nHISTÓRICO — {len(log_antigo)} registros', dict(C(l['usuario'] for l in log_antigo)))

    # ── Arquivos ────────────────────────────────────────────────────────
    docs, sem_padrao, sem_fazenda = planejar_arquivos(cfg['releases'], fazendas_hub)
    projetos = montar_projetos(docs)
    n_arq = sum(len(r['arquivos']) for p in projetos for r in p['revisoes'])
    n_rev = sum(len(p['revisoes']) for p in projetos)
    print(f'\nARQUIVOS — {len(projetos)} projetos ({sum(p["tipo"] == "personalizado" for p in projetos)} blocos), '
          f'{n_rev} revisões Rev0, {n_arq} arquivos (sem repetição)')
    print('  revisões por documento:', dict(C(r['documento'] for p in projetos for r in p['revisoes'])))
    if sem_fazenda:
        print('  ⚠ fazendas fora da Base Fazendas (NÃO migrados):', dict(sem_fazenda))
    if sem_padrao:
        print('  ⚠ arquivos fora do padrão (NÃO migrados):', sem_padrao)

    if args.simular:
        print('\nSimulação: nada foi gravado.')
        return

    ids = ids_dos_usuarios_antigos(usados)
    log = []
    anterior = {}
    for r in sorted(log_antigo, key=lambda r: (r['layer'], quando(r) or '', r['id'])):
        novo = ' · '.join(x for x in (r['tipo_linha'] or ('SEM LINHAS' if r['status'] == 'SEM LINHAS' else ''), r['ciclo']) if x)
        if not novo or novo == anterior.get(r['layer']):
            continue
        log.append({'layer': r['layer'], 'anterior': anterior.get(r['layer']), 'novo': novo,
                    'usuario_id': ids.get(r['usuario']), 'criado_em': quando(r)})
        anterior[r['layer']] = novo
    carga = {'projetos': projetos, 'talhoes': na_demanda, 'log': log}
    print(f"\nCarga: {len(projetos)} projetos, {len(na_demanda)} talhões, {len(log)} linhas de histórico")

    if not args.ensaio:
        if input('\nGRAVAR DE VERDADE no Hub? Digite MIGRAR para confirmar: ').strip() != 'MIGRAR':
            sys.exit('Cancelado: nada foi gravado.')
    r = requests.post(f'{hub.url}/rpc/migrar_colheita_antiga', headers=hub.headers,
                      json={'p': carga, 'p_ensaio': args.ensaio}, timeout=300)
    if r.ok:
        resumo = r.json()
    else:
        mensagem = r.json().get('message', '') if 'json' in r.headers.get('Content-Type', '') else r.text
        if not (args.ensaio and mensagem.startswith('ENSAIO ')):
            sys.exit(f'✗ Migração recusada pelo banco (nada foi gravado): HTTP {r.status_code} {mensagem}')
        resumo = json.loads(mensagem[len('ENSAIO '):])
    print('\nResultado conferido no banco:', json.dumps(resumo, ensure_ascii=False, indent=2))

    esperado = {'talhoes_divergentes': 0, 'log': len(log), 'arquivos': n_arq, 'revisoes': n_rev,
                'projetos': len(projetos)}
    erradas = {k: (resumo.get(k), v) for k, v in esperado.items() if resumo.get(k) != v}
    if erradas:
        sys.exit(f'⚠ Diferente do esperado (banco, esperado): {erradas}')
    print('\n✓ Tudo confere.', 'ENSAIO: nada ficou gravado.' if args.ensaio else 'Migração GRAVADA.')


if __name__ == '__main__':
    main()
