"""Migração única: traz para o Hub o que já existe nos sistemas atuais de
Plantio e Preparo. Só LÊ o sistema antigo; nada é alterado lá.

O que é trazido:
  - Plantio: status (mapeamento/projeto) de cada talhão. Talhão que ainda
    não está na Base Fazendas tem o status guardado (restaurado sozinho
    quando a Base cadastrar). O histórico de registros vai pro log.
  - Preparo: etapas concluídas por fazenda, com quem e quando.
  - Arquivos das GitHub Releases: viram projetos/revisões/arquivos. Cada tipo
    de documento com sua numeração; a maior revisão é a vigente. O arquivo
    fica onde está, só é referenciado.

A gravação é feita pela função hub.migrar_sistema_antigo, numa transação só:
ou entra tudo, ou nada. Arquivos entram ANTES dos status (anexar um .pdf
dispara o "mapa → Ok", mas o status que vale é o do sistema antigo).

Uso:
  python migracao/migrar_plantio_preparo.py --simular   só lê e mostra o plano
  python migracao/migrar_plantio_preparo.py --ensaio    grava, confere e desfaz
  python migracao/migrar_plantio_preparo.py             grava de verdade (corte)

O login antigo de cada pessoa vem do campo usuario_antigo em
ingestao/usuarios_hub.json (fora do git).
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

MOTIVO_LEGADO = 'Revisão feita no sistema anterior (motivo não registrado)'
USUARIOS_IGNORADOS = {'teste-diagnostico-rpc'}
ETAPAS_PREPARO = ['identificacao', 'escoamento', 'observacoes', 'preparo']  # mesma ordem de hub.etapas
RE_COD = re.compile(r'^(\d{5})')
RE_NUM = re.compile(r'(Rev|Exp)(\d+)', re.IGNORECASE)


class Antigo:
    def __init__(self, cfg):
        self.url = cfg['supabase_url'].rstrip('/') + '/rest/v1'
        self.chave = cfg['anon_key']

    def ler(self, tabela, schema, select='*'):
        linhas, inicio = [], 0
        while True:
            r = requests.get(
                f'{self.url}/{tabela}', params={'select': select},
                headers={'apikey': self.chave, 'Authorization': f'Bearer {self.chave}',
                         'Accept-Profile': schema, 'Range': f'{inicio}-{inicio + 999}'},
                timeout=60)
            r.raise_for_status()
            lote = r.json()
            linhas += lote
            if len(lote) < 1000:
                return linhas
            inicio += 1000


def assets_do_repo(repo):
    """(tag da release, asset). A tag da release é o código da fazenda."""
    assets, url = [], f'https://api.github.com/repos/{repo}/releases?per_page=100'
    while url:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        for rel in r.json():
            assets += [(rel['tag_name'], a) for a in rel.get('assets', [])]
        m = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get('Link', ''))
        url = m.group(1) if m else None
    return assets


def nome_bloco(nome):
    """'BLOCO.POMPEI_Rev0.dwg' e 'BLOCO_POMPEI_Exp0.zip' → 'BLOCO POMPEI'."""
    prefixo = RE_NUM.split(nome)[0]
    return re.sub(r'[._]+', ' ', prefixo).strip()


def classificar(modulo, nome):
    """(dono, documento, numero) do arquivo. dono = cod_faz (projeto
    individual) ou nome do bloco (personalizado, ex: 'BLOCO POMPEI').
    numero None = mapa de plantio no nome antigo (MapaPlantio.pdf), que vai
    pra revisão vigente do projeto. Tolera os nomes fora do padrão
    encontrados (ex: ...Escoamento.Rev0.pdf, BLOCO_POMPEI_Rev0.dwg)."""
    cod = RE_COD.match(nome)
    baixo = nome.lower()
    if cod:
        dono = int(cod.group(1))
    elif RE_NUM.search(nome) and nome_bloco(nome):
        dono = nome_bloco(nome)
    else:
        return None
    if modulo == 'plantio' and 'mapaplantio' in baixo:
        return dono, 'projeto', None
    m = RE_NUM.search(nome)
    if not m:
        return None
    marcador, numero = m.group(1).capitalize(), int(m.group(2))
    if modulo == 'preparo' and 'escoamento' in baixo:
        documento = 'escoamento'
    elif modulo == 'preparo' and 'sistematiza' in baixo:
        documento = 'sistematizacao'
    else:
        documento = 'exportacao' if marcador == 'Exp' else 'projeto'
    return dono, documento, numero


def planejar_arquivos(cfg, fazendas_hub):
    """Monta projetos → revisões → arquivos a partir das releases.

    O mesmo arquivo às vezes está publicado em várias releases (ex: arquivos
    de bloco, ou de uma fazenda na release de outra): entra uma vez só.
    As fazendas de um bloco são as releases em que os arquivos dele aparecem."""
    revisoes = collections.defaultdict(lambda: collections.defaultdict(dict))  # (mod, dono, doc) → numero → {nome: asset}
    fazendas_bloco = collections.defaultdict(set)                              # (mod, bloco) → {cod_faz}
    mapas, sem_padrao, sem_fazenda = [], [], collections.Counter()
    for modulo, repo in cfg['releases'].items():
        for tag, a in assets_do_repo(repo):
            c = classificar(modulo, a['name'])
            if not c:
                sem_padrao.append(f"{modulo}: {a['name']}")
                continue
            dono, documento, numero = c
            if isinstance(dono, str):
                if tag.isdigit():
                    fazendas_bloco[(modulo, dono)].add(int(tag))
            elif dono not in fazendas_hub:
                sem_fazenda[(modulo, dono)] += 1
                continue
            if numero is None:
                mapas.append((modulo, dono, a))
            else:
                revisoes[(modulo, dono, documento)][numero].setdefault(a['name'], a)
    for modulo, dono, a in mapas:
        numeros = revisoes[(modulo, dono, 'projeto')]
        numeros[max(numeros) if numeros else 0].setdefault(a['name'], a)
    return revisoes, fazendas_bloco, sem_padrao, sem_fazenda


def ids_dos_usuarios_antigos(usados):
    """login antigo → id da conta no Hub (pelo e-mail em usuarios_hub.json)."""
    with open(os.path.join(RAIZ, 'ingestao', 'usuarios_hub.json'), encoding='utf-8') as f:
        email_de = {u['usuario_antigo']: u['email'].lower()
                    for u in json.load(f)['usuarios'] if u.get('usuario_antigo')}
    contas = AuthAdmin().por_email()
    faltando = sorted(u for u in usados if email_de.get(u) not in contas)
    if faltando:
        sys.exit(f'Sem conta no Hub para o login antigo {faltando}: preencha usuario_antigo em '
                 'ingestao/usuarios_hub.json e rode sincronizar_usuarios.py.')
    return {u: contas[email_de[u]]['id'] for u in usados}


def montar_projetos(revisoes, fazendas_bloco):
    projetos = collections.defaultdict(list)                  # (modulo, dono) → revisões
    for (modulo, dono, documento), numeros in revisoes.items():
        maior = max(numeros)
        for numero, assets in numeros.items():
            projetos[(modulo, dono)].append({
                'documento': documento,
                'numero': numero,
                'motivo': MOTIVO_LEGADO if numero > 0 else None,
                'vigente': numero == maior,
                'criado_em': min(a['created_at'] for a in assets.values()),
                'origens': sorted(fazendas_bloco.get((modulo, dono), [])) if isinstance(dono, str) else [],
                'arquivos': [{'nome': nome, 'url': a['browser_download_url'], 'tamanho': a['size'],
                              'publicado_em': a['created_at']} for nome, a in sorted(assets.items())],
            })
    return [{'modulo': modulo,
             'tipo': 'personalizado' if isinstance(dono, str) else 'individual',
             'cod_faz': None if isinstance(dono, str) else dono,
             'nome': dono if isinstance(dono, str) else str(dono),
             'criado_em': min(r['criado_em'] for r in revs),
             'revisoes': revs}
            for (modulo, dono), revs in projetos.items()]


def montar_log(log_antigo, ids):
    """Cada registro antigo é uma "foto" do talhão (mapeamento + projeto):
    vira uma linha de log por campo que mudou em relação à foto anterior."""
    linhas, ultimo = [], {}
    quando = lambda r: r['registrado_em'] or r['data_consolidacao']   # parte dos registros antigos só tem a 2ª
    for r in sorted(log_antigo, key=lambda r: (r['layer'], quando(r), r['id'])):
        anterior = ultimo.get(r['layer'], {'mapeamento': 'Não', 'projeto': None})
        for campo in ('mapeamento', 'projeto'):
            if r[campo] and r[campo] != anterior[campo]:
                linhas.append({'layer': r['layer'], 'campo': campo, 'anterior': anterior[campo],
                               'novo': r[campo], 'usuario_id': ids[r['usuario']],
                               'criado_em': quando(r)})
        ultimo[r['layer']] = {c: r[c] or anterior[c] for c in ('mapeamento', 'projeto')}
    return linhas


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument('--simular', action='store_true', help='lê tudo e mostra o plano, sem gravar')
    modo.add_argument('--ensaio', action='store_true', help='grava, confere e desfaz (nada fica gravado)')
    args = ap.parse_args()

    cfg = carregar_config()['sistema_antigo']
    antigo, hub = Antigo(cfg), Hub()
    C = collections.Counter

    fazendas_hub = {f['cod_faz'] for f in hub.selecionar('fazendas', 'cod_faz')}
    base = {t['layer'] for t in hub.selecionar('talhoes', 'layer')}
    plantio_hub = {t['layer'] for t in hub.selecionar('talhao_plantio', 'layer')}

    # ── Plantio: status por talhão ──────────────────────────────────────────
    antigos = antigo.ler('programacao', 'plantio', 'layer,mes_plantio,seq_plantio,ambiente,mapeamento,projeto')
    atualizar = [a for a in antigos if a['layer'] in plantio_hub]
    criar = [a for a in antigos if a['layer'] in base and a['layer'] not in plantio_hub]
    guardar = [a for a in antigos if a['layer'] not in base]
    print('PLANTIO — status de', len(antigos), 'talhões')
    print(f'  {len(atualizar)} já no Hub (status atualizado) | {len(criar)} na Base mas fora do LIB atual (entram) '
          f'| {len(guardar)} fora da Base (status guardado)')
    print('  status que vão ficar:', dict(C(a['projeto'] for a in antigos)))

    log_antigo = [l for l in antigo.ler('log_exportacoes', 'plantio', 'id,layer,usuario,projeto,mapeamento,registrado_em,data_consolidacao')
                  if l['usuario'] not in USUARIOS_IGNORADOS]
    print(f'  histórico: {len(log_antigo)} registros', dict(C(l['usuario'] for l in log_antigo)))

    # ── Preparo: etapas por fazenda ─────────────────────────────────────────
    analises = antigo.ler('fazenda_analise', 'public')
    etapas_ok = [(f, i, e) for f in analises for i, e in enumerate(ETAPAS_PREPARO) if f.get(f'{e}_ok')]
    fora_base_preparo = sorted({f['cod_faz'] for f, _, _ in etapas_ok if f['cod_faz'] not in fazendas_hub})
    print(f'\nPREPARO — {len(analises)} fazendas, {len(etapas_ok)} etapas concluídas', dict(C(e for _, _, e in etapas_ok)))
    if fora_base_preparo:
        print('  fazendas fora da Base Fazendas (etapas vão mesmo assim, pelo código):', fora_base_preparo)

    # ── Arquivos ────────────────────────────────────────────────────────────
    revisoes, fazendas_bloco, sem_padrao, sem_fazenda = planejar_arquivos(cfg, fazendas_hub)
    projetos = sorted({(m, d) for m, d, _ in revisoes}, key=str)
    n_rev = sum(len(ns) for ns in revisoes.values())
    n_arq = sum(len(a) for ns in revisoes.values() for a in ns.values())
    print(f'\nARQUIVOS — {len(projetos)} projetos, {n_rev} revisões, {n_arq} arquivos (sem repetição)')
    print('  projetos por módulo:', dict(C(m for m, _ in projetos)))
    for (m, bloco), fazendas in fazendas_bloco.items():
        docs = sorted(d for (mm, dono, d) in revisoes if mm == m and dono == bloco)
        print(f'  personalizado {m}/"{bloco}": fazendas {sorted(fazendas)} | documentos {docs}')
    print('  revisões por documento:', dict(C(f'{m}/{d}' for (m, _, d), ns in revisoes.items() for _ in ns)))
    if sem_fazenda:
        print('  ⚠ fazendas das releases fora da Base Fazendas (arquivos NÃO migrados):', dict(sem_fazenda))
    if sem_padrao:
        print('  ⚠ arquivos fora do padrão (NÃO migrados):', sem_padrao)

    usuarios_antigos = sorted({l['usuario'] for l in log_antigo} |
                              {f.get(f'{e}_usuario') for f, _, e in etapas_ok if f.get(f'{e}_usuario')})
    print('\nUSUÁRIOS que aparecem no histórico:', usuarios_antigos)

    if args.simular:
        print('\nSimulação: nada foi gravado.')
        return

    ids = ids_dos_usuarios_antigos(usuarios_antigos)
    carga = {
        'projetos': montar_projetos(revisoes, fazendas_bloco),
        'plantio': [{'layer': a['layer'], 'mes_plantio': a['mes_plantio'], 'seq_plantio': a['seq_plantio'] or None,
                     'ambiente': a['ambiente'] or None, 'mapeamento': a['mapeamento'], 'projeto': a['projeto']}
                    for a in antigos],
        'log': montar_log(log_antigo, ids),
        'preparo': [{'cod_faz': f['cod_faz'], 'ordem': i + 1, 'usuario_id': ids.get(f.get(f'{e}_usuario')),
                     'concluido_em': f.get(f'{e}_data')} for f, i, e in etapas_ok],
    }
    print(f"\nCarga: {len(carga['projetos'])} projetos, {len(carga['plantio'])} talhões, "
          f"{len(carga['log'])} linhas de histórico, {len(carga['preparo'])} etapas do Preparo")

    if not args.ensaio:
        if input('\nGRAVAR DE VERDADE no Hub? Digite MIGRAR para confirmar: ').strip() != 'MIGRAR':
            sys.exit('Cancelado: nada foi gravado.')
    r = requests.post(f'{hub.url}/rpc/migrar_sistema_antigo', headers=hub.headers,
                      json={'p': carga, 'p_ensaio': args.ensaio}, timeout=300)
    if r.ok:
        resumo = r.json()
    else:
        # O ensaio termina com erro de propósito (é o que desfaz tudo); o
        # resumo conferido vem na mensagem.
        mensagem = r.json().get('message', '') if 'json' in r.headers.get('Content-Type', '') else r.text
        if not (args.ensaio and mensagem.startswith('ENSAIO ')):
            sys.exit(f'✗ Migração recusada pelo banco (nada foi gravado): HTTP {r.status_code} {mensagem}')
        resumo = json.loads(mensagem[len('ENSAIO '):])
    print('\nResultado conferido no banco:', json.dumps(resumo, ensure_ascii=False, indent=2))

    esperado = {'plantio_divergentes': 0,
                'plantio_guardados': len(guardar),
                'preparo_etapas': len(carga['preparo']),
                'log': len(carga['log']),
                'arquivos': n_arq,
                'revisoes': n_rev}
    erradas = {k: (resumo.get(k), v) for k, v in esperado.items() if resumo.get(k) != v}
    if erradas:
        sys.exit(f'⚠ Diferente do esperado (banco, esperado): {erradas}')
    print('\n✓ Tudo confere.', 'ENSAIO: nada ficou gravado.' if args.ensaio else 'Migração GRAVADA.')


if __name__ == '__main__':
    main()
