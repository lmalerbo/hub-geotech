"""Lançamento único do ciclo 25-26 no Preparo (spec 2026-10-28-preparo-mes-ciclo-design.md, D3).

Uso:
  python migracao/lancar_ciclo_25_26.py                 # lista os candidatos e grava um CSV (não grava no banco)
  python migracao/lancar_ciclo_25_26.py --gravar        # lança (depois do ok do usuário na lista)
  python migracao/lancar_ciclo_25_26.py --voltar LOTE   # desfaz o lançamento
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ingestao'))
from comum import Hub  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--gravar', action='store_true')
    ap.add_argument('--voltar', type=int, metavar='LOTE')
    args = ap.parse_args()
    hub = Hub()

    if args.voltar:
        n = hub.rpc('preparo_voltar_ciclo_25_26', {'p_lote': args.voltar})
        print(f'Volta do lote {args.voltar}: {n} talhões restaurados.')
        return

    cand = hub.rpc('preparo_ciclo_25_26_candidatos')
    saida = os.path.join(os.path.dirname(__file__), 'ciclo_25_26_candidatos.csv')
    with open(saida, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(cand[0]) if cand else ['cod_faz'], delimiter=';')
        w.writeheader()
        w.writerows(cand)
    fazendas = {c['cod_faz'] for c in cand}
    print(f'{len(cand)} talhões em {len(fazendas)} fazendas, {sum(c["area_ha"] or 0 for c in cand):.1f} ha → {saida}')

    if args.gravar:
        lote = hub.rpc('preparo_lancar_ciclo_25_26')
        print(f'Lançado. Lote {lote} (para desfazer: --voltar {lote}).')
    else:
        print('Só a lista: nada foi gravado. Confira o CSV antes de rodar com --gravar.')


if __name__ == '__main__':
    main()
