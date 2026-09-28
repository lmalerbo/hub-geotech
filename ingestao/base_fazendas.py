"""Importa a Base Fazendas para hub.fazendas e hub.talhoes.

Fonte: o .dbf mais recente do shapefile diário do FME
(Talhoes_da_Pedra_DD_MM_AAAA_fme, pasta em ingestao/config.json) — o mesmo
arquivo que o GeoMap publica às 8:05.

Grava só os campos de que a Base Fazendas é dona: nome da fazenda, área
produtiva, estágio, data do último corte e propriedade. O layer é calculado
pelo banco a partir de SECAO + TALHAO; a coluna Layer do arquivo não é usada.

Uso:  python ingestao/base_fazendas.py [--simular]
"""

import argparse
import datetime
import glob
import os
import re
import sys

from dbfread import DBF

from comum import Execucao, Hub, carregar_config

PADRAO_DATA_ARQUIVO = re.compile(r'_(\d{2})_(\d{2})_(\d{4})_fme\.dbf$', re.IGNORECASE)


def arquivo_mais_recente(pasta, padrao):
    # A data vem do nome do arquivo, não da data de modificação.
    candidatos = []
    for caminho in glob.glob(os.path.join(pasta, padrao)):
        m = PADRAO_DATA_ARQUIVO.search(caminho)
        if m:
            data = datetime.date(int(m[3]), int(m[2]), int(m[1]))
            candidatos.append((data, caminho))
    return max(candidatos) if candidatos else (None, None)


def para_int(valor):
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def para_data(valor):
    if isinstance(valor, datetime.date):
        return valor.isoformat()
    try:
        return datetime.datetime.strptime(str(valor).strip(), '%d/%m/%Y').date().isoformat()
    except (TypeError, ValueError):
        return None


def texto(valor):
    return (str(valor).strip() or None) if valor is not None else None


def codificacao(caminho_dbf):
    # O shapefile declara a codificação no .cpg ao lado do .dbf (hoje: UTF-8).
    cpg = os.path.splitext(caminho_dbf)[0] + '.cpg'
    try:
        with open(cpg, encoding='ascii') as f:
            return f.read().strip() or 'utf-8'
    except OSError:
        return 'utf-8'


def ler(caminho):
    fazendas, talhoes = {}, {}
    vazias = invalidas = repetidos = 0
    for r in DBF(caminho, encoding=codificacao(caminho)):
        if not texto(r.get('SECAO')) and r.get('TALHAO') is None:
            vazias += 1   # forma sem atributo nenhum no shapefile
            continue
        cod, tal = para_int(r.get('SECAO')), para_int(r.get('TALHAO'))
        if cod is None or tal is None or not 10000 <= cod <= 99999 or not 0 <= tal <= 999:
            invalidas += 1
            continue
        fazendas[cod] = {'cod_faz': cod, 'nome': texto(r.get('DESC_SECAO')) or ''}
        if (cod, tal) in talhoes:
            repetidos += 1
        talhoes[(cod, tal)] = {
            'cod_faz': cod,
            'talhao_num': tal,
            'area_ha': r.get('AREA_PROD'),
            'estagio': texto(r.get('ESTAGIO')),
            'data_ultimo_corte': para_data(r.get('DATA_CORTE')),
            'propriedade': texto(r.get('PROPRIEDAD')),
        }
    return list(fazendas.values()), list(talhoes.values()), vazias, invalidas, repetidos


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--simular', action='store_true', help='lê e valida o arquivo, sem gravar nada')
    args = ap.parse_args()

    cfg = carregar_config()['base_fazendas']
    data, caminho = arquivo_mais_recente(cfg['pasta'], cfg['padrao'])
    if not caminho:
        sys.exit(f"Nenhum arquivo {cfg['padrao']} em {cfg['pasta']}")
    if data < datetime.date.today():
        print(f'⚠ O arquivo mais recente é de {data:%d/%m/%Y} — a exportação de hoje ainda não chegou.')

    fazendas, talhoes, vazias, invalidas, repetidos = ler(caminho)
    print(f'{os.path.basename(caminho)}: {len(fazendas)} fazendas, {len(talhoes)} talhões '
          f'({vazias} linhas vazias ignoradas, {invalidas} inválidas, {repetidos} talhões repetidos)')

    if args.simular:
        print('Simulação: nada foi gravado.')
        return

    hub = Hub()
    with Execucao(hub, 'base_fazendas') as execucao:
        execucao.linhas_lidas = len(talhoes) + vazias + invalidas + repetidos
        hub.upsert('fazendas', fazendas, 'cod_faz')
        hub.upsert('talhoes', talhoes, 'cod_faz,talhao_num')
        execucao.linhas_gravadas = len(talhoes)
    print('Gravado no Hub.')


if __name__ == '__main__':
    main()
