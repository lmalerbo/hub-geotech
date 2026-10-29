"""Lançamento único do ciclo 25-26 no Preparo (spec 2026-10-28-preparo-mes-ciclo-design.md, D3).

Uso:
  python migracao/lancar_ciclo_25_26.py                 # lista os candidatos e grava o CSV (único modo que escreve o CSV; não grava no banco)
  python migracao/lancar_ciclo_25_26.py --gravar --esperado N   # lança; lê o CSV aprovado e aborta se o conjunto de
                                                        # talhões candidatos hoje for diferente dele (ou se não forem N)
  python migracao/lancar_ciclo_25_26.py --voltar LOTE   # desfaz o lançamento
"""
import argparse
import csv
import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ingestao'))
from comum import Hub  # noqa: E402


def candidatos(hub, pagina=1000):
    """Lista completa dos candidatos (o PostgREST corta em ~1000 linhas por chamada: pagina)."""
    todos, inicio = [], 0
    while True:
        r = requests.post(f'{hub.url}/rpc/preparo_ciclo_25_26_candidatos',
                          headers={**hub.headers, 'Range': f'{inicio}-{inicio + pagina - 1}'}, json={}, timeout=120)
        hub._checar(r, 'preparo_ciclo_25_26_candidatos')
        lote = r.json()
        todos.extend(lote)
        if len(lote) < pagina:
            return todos
        inicio += pagina


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument('--gravar', action='store_true')
    modo.add_argument('--voltar', type=int, metavar='LOTE')
    ap.add_argument('--esperado', type=int, metavar='N', help='nº de talhões aprovado na lista; obrigatório com --gravar')
    args = ap.parse_args()
    if args.gravar and args.esperado is None:
        ap.error('--gravar exige --esperado N (o número de talhões da lista aprovada)')
    hub = Hub()

    if args.voltar:
        n = hub.rpc('preparo_voltar_ciclo_25_26', {'p_lote': args.voltar})
        print(f'Volta do lote {args.voltar}: {n} talhões restaurados.')
        return

    cand = candidatos(hub)
    saida = os.path.join(os.path.dirname(__file__), 'ciclo_25_26_candidatos.csv')
    fazendas = {c['cod_faz'] for c in cand}
    print(f'{len(cand)} talhões em {len(fazendas)} fazendas, {sum(c["area_ha"] or 0 for c in cand):.1f} ha')

    if args.gravar:
        # O CSV aprovado não é reescrito aqui: compara-se o conjunto de layers de hoje com o dele.
        if not os.path.exists(saida):
            sys.exit(f'ABORTADO: não há CSV aprovado em {saida}. Rode sem flags, confira a lista e tente de novo.')
        with open(saida, newline='', encoding='utf-8-sig') as f:
            aprovados = {int(r['layer']) for r in csv.DictReader(f, delimiter=';')}
        agora = {int(c['layer']) for c in cand}
        if agora != aprovados:
            novos, saiu = sorted(agora - aprovados), sorted(aprovados - agora)
            sys.exit('ABORTADO: os candidatos de hoje não são os do CSV aprovado. Nada foi gravado.\n'
                     f'  entraram ({len(novos)}): {novos[:50]}\n  saíram ({len(saiu)}): {saiu[:50]}\n'
                     'Rode sem flags para gerar um CSV novo e aprove de novo.')
        if len(cand) != args.esperado:
            sys.exit(f'ABORTADO: há {len(cand)} talhões candidatos agora e a lista aprovada tinha {args.esperado}. Nada foi gravado.')
        lote = hub.rpc('preparo_lancar_ciclo_25_26')
        gravados = len(hub.selecionar('log_auditoria', 'id', {'lote_id': f'eq.{lote}'})) if lote else 0
        print(f'Lançado. Lote {lote}, {gravados} linhas no log (para desfazer: --voltar {lote}).')
    else:
        with open(saida, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list(cand[0]) if cand else ['cod_faz'], delimiter=';')
            w.writeheader()
            w.writerows(cand)
        print(f'CSV: {saida}')
        print('Só a lista: nada foi gravado no banco. Confira o CSV antes de rodar com --gravar.')


if __name__ == '__main__':
    main()
