"""Importa o tipo de conservação do solo (Controle de Conservação) para
hub.talhoes.sist_conser.

Fonte: aba CONSERVAÇÃO da planilha de Preparo de Solo (caminho em
ingestao/config.json). Só as colunas SEÇÃO, TALHÃO e SISTEMA DE CONSERVAÇÃO
interessam ao Hub; o resto é controle da equipe de conservação.

Só grava talhão cujo tipo mudou, e marca sist_conser_em com a hora da
mudança — assim dá pra saber desde quando o Hub conhece o tipo atual.
Talhão que some da planilha mantém o último tipo conhecido.

Uso:  python ingestao/conservacao.py [--simular]
"""

import argparse
import collections
import datetime
import os

import openpyxl

from comum import (Execucao, Hub, achar_aba, agora_iso, calc_layer,
                   carregar_config, ler_tabela, norm, para_int)

# Vocabulário da especificação do Hub. INTERCALADO e "-" seguem a mesma
# equivalência que o sistema atual (project-plantio) já usa.
TIPOS = {
    'BASE LARGA': 'Base Larga',
    'EMBUTIDO': 'Embutido',
    'INTERCALADO': 'Embutido',
    'INTERCALADA': 'Embutido',
    '-': 'Sem Conservação',
    'LIVRE': 'Sem Conservação',
    'SEM CONSERVACAO': 'Sem Conservação',
}


def ler(caminho, aba):
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    colunas, linhas = ler_tabela(achar_aba(wb, aba), ['SEÇÃO', 'TALHÃO', 'SISTEMA DE CONSERVAÇÃO'])
    j_cod, j_tal, j_sc = colunas['SECAO'][0], colunas['TALHAO'][0], colunas['SISTEMA DE CONSERVACAO'][0]

    tipos, desconhecidos, sem_tipo = {}, collections.Counter(), 0
    for l in linhas:
        cod, tal = para_int(l[j_cod]), para_int(l[j_tal])
        if cod is None or tal is None:
            continue
        bruto = norm(l[j_sc])
        if not bruto:
            sem_tipo += 1
            continue
        if bruto not in TIPOS:
            desconhecidos[bruto] += 1
            continue
        tipos[calc_layer(cod, tal)] = TIPOS[bruto]
    return tipos, desconhecidos, sem_tipo


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--simular', action='store_true', help='lê e valida, sem gravar nada')
    args = ap.parse_args()

    cfg = carregar_config()['conservacao']
    modificado = datetime.datetime.fromtimestamp(os.path.getmtime(cfg['arquivo']))
    print(f'Controle de Conservação (salvo em {modificado:%d/%m/%Y %H:%M})')
    tipos, desconhecidos, sem_tipo = ler(cfg['arquivo'], cfg['aba'])
    print('  tipos:', ', '.join(f'{k}: {v}' for k, v in collections.Counter(tipos.values()).most_common()))
    if desconhecidos:
        print(f'  ⚠ valores desconhecidos (não gravados): {dict(desconhecidos)}')
    if sem_tipo:
        print(f'  {sem_tipo} talhões ainda sem tipo preenchido')

    hub = Hub()
    atuais = {t['layer']: t for t in hub.selecionar('talhoes', 'layer,cod_faz,talhao_num,sist_conser')}
    fora = sorted(layer for layer in tipos if layer not in atuais)
    mudancas = [
        {'cod_faz': atuais[layer]['cod_faz'], 'talhao_num': atuais[layer]['talhao_num'],
         'sist_conser': tipo, 'sist_conser_em': agora_iso()}
        for layer, tipo in tipos.items()
        if layer in atuais and atuais[layer]['sist_conser'] != tipo
    ]
    print(f'  {len(tipos)} talhões com tipo → {len(mudancas)} novos ou alterados, '
          f'{len(fora)} fora da Base Fazendas (ignorados)' + (f': {fora[:10]}' if fora else ''))

    if args.simular:
        print('Simulação: nada foi gravado.')
        return

    with Execucao(hub, 'conservacao') as execucao:
        execucao.linhas_lidas = len(tipos) + sum(desconhecidos.values()) + sem_tipo
        if mudancas:
            hub.upsert('talhoes', mudancas, 'cod_faz,talhao_num')
        execucao.linhas_gravadas = len(mudancas)
        execucao.detalhes = {'fora_da_base_fazendas': fora, 'valores_desconhecidos': dict(desconhecidos)}
    print('Gravado no Hub.')


if __name__ == '__main__':
    main()
