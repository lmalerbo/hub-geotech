"""Importa a demanda de Plantio e de Preparo do PLANAGRI para
hub.talhao_plantio e hub.talhao_preparo.

Entram só os talhões liberados (status PLAN. = LIB), como nos sistemas
atuais — Plantio e Preparo sempre leram a mesma demanda do PLANAGRI.
Grava só o que o PLANAGRI é dono: o talhão estar na demanda e o mês de
plantio. Mapeamento e projeto não são tocados em talhão que já existe
(talhão novo nasce com os valores padrão da tabela). O tipo de conservação
NÃO vem daqui — a coluna do PLANAGRI não é atualizada; o dono é o Controle de
Conservação.

Uso:  python ingestao/planagri.py [--simular]
"""

import argparse
import collections
import datetime
import os

import openpyxl

from comum import (Execucao, Hub, achar_aba, calc_layer, carregar_config,
                   ler_tabela, norm, para_int)


def coluna_status(colunas, linhas):
    # Há duas colunas "PLAN.": uma é o tipo (REFORMA / PASSAGEM CICLO /
    # EXPANSÃO) e outra o status (LIB / PLAN / EXP). O status é a que tem LIB.
    def qtd_lib(j):
        return sum(1 for l in linhas if j < len(l) and norm(l[j]) == 'LIB')
    return max(colunas['PLAN.'], key=qtd_lib)


def para_data(valor):
    if isinstance(valor, datetime.datetime):
        return valor.date().isoformat()
    if isinstance(valor, datetime.date):
        return valor.isoformat()
    return None


def ler(caminho, aba):
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    colunas, linhas = ler_tabela(achar_aba(wb, aba), ['CÓDIGO', 'TALHÃO', 'PLAN.', 'MÊS PLANTIO (PLAN)'])
    j_cod, j_tal = colunas['CODIGO'][0], colunas['TALHAO'][0]
    j_mes, j_status = colunas['MES PLANTIO (PLAN)'][0], coluna_status(colunas, linhas)

    status = collections.Counter()
    talhoes = {}
    for l in linhas:
        cod, tal = para_int(l[j_cod]), para_int(l[j_tal])
        if cod is None or tal is None:
            continue
        s = norm(l[j_status]) or '(vazio)'
        status[s] += 1
        if s != 'LIB':
            continue
        talhoes[calc_layer(cod, tal)] = {'layer': calc_layer(cod, tal), 'mes_plantio': para_data(l[j_mes])}
    return talhoes, status


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--simular', action='store_true', help='lê e valida, sem gravar nada')
    args = ap.parse_args()

    cfg = carregar_config()['planagri']
    modificado = datetime.datetime.fromtimestamp(os.path.getmtime(cfg['arquivo']))
    print(f"PLANAGRI (salvo em {modificado:%d/%m/%Y %H:%M})")
    talhoes, status = ler(cfg['arquivo'], cfg['aba'])
    print('  status na planilha:', ', '.join(f'{k}: {v}' for k, v in status.most_common()))

    hub = Hub()
    existentes = hub.layers_existentes()
    validos = [t for layer, t in talhoes.items() if layer in existentes]
    fora = sorted(layer for layer in talhoes if layer not in existentes)
    print(f'  {len(talhoes)} talhões liberados (LIB) → {len(validos)} na Base Fazendas, '
          f'{len(fora)} fora dela (ignorados)' + (f': {fora[:10]}' if fora else ''))

    if args.simular:
        print('Simulação: nada foi gravado.')
        return

    with Execucao(hub, 'planagri') as execucao:
        execucao.linhas_lidas = sum(status.values())
        hub.upsert('talhao_plantio', validos, 'layer')
        # No Preparo o andamento é por fazenda (etapas); aqui basta o talhão
        # estar na demanda.
        hub.upsert('talhao_preparo', [{'layer': t['layer']} for t in validos], 'layer')
        execucao.linhas_gravadas = len(validos)
        execucao.detalhes = {'fora_da_base_fazendas': fora}
    print('Gravado no Hub.')


if __name__ == '__main__':
    main()
