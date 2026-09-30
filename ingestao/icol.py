"""Importa a demanda da Colheita do ICOL (Mapa de Colheitabilidade) para
hub.talhao_colheita.

Lê a aba "BASE PARA PLANEJAMENTO" (1 linha por talhão; cabeçalho achado pelo
nome). A demanda são TODOS os talhões (da Base Fazendas) de cada fazenda que
aparece no ICOL — a equipe faz as linhas da fazenda inteira, porque o projeto
de exportação é por fazenda (decisão de 29/09/2026, igual ao Expo_safra).
Talhão listado no ICOL recebe frente, período operacional e se já foi
cortado; os outros talhões da fazenda entram com esses campos vazios. Tipo de linha e ciclo (trabalho da equipe) não são
tocados; talhão novo nasce sem tipo (A FAZER). Estágio, data de corte e área
vêm da Base Fazendas.

A frente é texto: o ICOL tem frentes como "BIS - 3" (o sistema antigo
convertia pra número e perdia esses talhões).

Uso:  python ingestao/icol.py [--simular]
"""

import argparse
import collections
import datetime
import os

import openpyxl

from comum import (Execucao, Hub, achar_aba, calc_layer, carregar_config,
                   ler_tabela, norm, para_int)


def texto_frente(valor):
    if valor is None or str(valor).strip() == '':
        return None
    n = para_int(valor)
    return str(n) if n is not None and str(valor).replace('.0', '').strip().isdigit() else str(valor).strip()


def ler(caminho, aba):
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    colunas, linhas = ler_tabela(achar_aba(wb, aba),
                                 ['FRENTE', 'PERÍODO OPERACIONAL', 'CÓDIGO', 'TALHÕES', 'CORTADO'])
    j_fre, j_per = colunas['FRENTE'][0], colunas['PERIODO OPERACIONAL'][0]
    j_cod, j_tal, j_cor = colunas['CODIGO'][0], colunas['TALHOES'][0], colunas['CORTADO'][0]

    talhoes, repetidos, cortado = {}, [], collections.Counter()
    for l in linhas:
        cod, tal = para_int(l[j_cod]), para_int(l[j_tal])
        if cod is None or tal is None:
            continue
        layer = calc_layer(cod, tal)
        if layer in talhoes:
            repetidos.append(layer)
        c = norm(l[j_cor])
        cortado[c or '(vazio)'] += 1
        talhoes[layer] = {
            'layer': layer,
            'frente': texto_frente(l[j_fre]),
            'periodo_op': para_int(l[j_per]) if l[j_per] not in (None, '') else None,
            'cortado': c == 'CORTADO' if c else None,
        }
    return talhoes, repetidos, cortado


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--simular', action='store_true', help='lê e valida, sem gravar nada')
    args = ap.parse_args()

    cfg = carregar_config()['icol']
    modificado = datetime.datetime.fromtimestamp(os.path.getmtime(cfg['arquivo']))
    print(f"ICOL (salvo em {modificado:%d/%m/%Y %H:%M})")
    talhoes, repetidos, cortado = ler(cfg['arquivo'], cfg['aba'])
    frentes = collections.Counter(t['frente'] for t in talhoes.values())
    print(f"  {len(talhoes)} talhões em {len({l // 1000 for l in talhoes})} fazendas"
          + (f' ({len(repetidos)} linhas repetidas, vale a última)' if repetidos else ''))
    print('  frentes:', ', '.join(f'{k}: {v}' for k, v in sorted(frentes.items(), key=lambda x: str(x[0]))))
    print('  cortado:', dict(cortado))

    hub = Hub()
    existentes = hub.layers_existentes()
    validos = [t for layer, t in talhoes.items() if layer in existentes]
    fora = sorted(layer for layer in talhoes if layer not in existentes)
    print(f'  {len(validos)} na Base Fazendas, {len(fora)} fora dela (ignorados)'
          + (f': {fora[:10]}' if fora else ''))
    fazendas = {layer // 1000 for layer in talhoes}
    resto = [{'layer': l, 'frente': None, 'periodo_op': None, 'cortado': None}
             for l in sorted(existentes) if l // 1000 in fazendas and l not in talhoes]
    print(f'  + {len(resto)} talhões das mesmas fazendas que o ICOL não lista (entram sem frente)'
          f' → demanda: {len(validos) + len(resto)} talhões')

    if args.simular:
        print('Simulação: nada foi gravado.')
        return

    with Execucao(hub, 'icol') as execucao:
        execucao.linhas_lidas = len(talhoes)
        hub.upsert('talhao_colheita', validos + resto, 'layer')
        execucao.linhas_gravadas = len(validos) + len(resto)
        execucao.detalhes = {'fora_da_base_fazendas': fora}
    print('Gravado no Hub.')


if __name__ == '__main__':
    main()
