"""Traz para o Hub a situação dos voos do Drone MGMT (hub.voo_dronemgmt), que
alimenta a tag de voo da Falha Soca na tela da Colheita.

TEMPORÁRIO (fase 1 da Colheita): lê a tabela voo_status do banco do
Expo_safra, que a GitHub Action "Atualizar status de voo" do repositório
Expo_safra atualiza de hora em hora direto do Drone MGMT. Assim o Hub não
precisa guardar a senha do Drone MGMT nem rodar navegador no servidor. Na
fase 2 (Regra B: agendar voo) a integração passa a ser direta, e esta
leitura sai. Enquanto isso, a Action do Expo_safra NÃO pode ser desligada.

Uso:  python ingestao/voos_colheita.py [--simular]
"""

import argparse
import collections
import os
import re

import requests

from comum import Hub, carregar_config


def ler_voo_status():
    cfg = carregar_config()['colheita_antiga']
    html = open(cfg['formulario'], encoding='utf-8').read()
    url = re.search(r"SUPABASE_URL\s*=\s*'([^']+)'", html).group(1).rstrip('/') + '/rest/v1/voo_status'
    chave = re.search(r"SUPABASE_KEY\s*=\s*'([^']+)'", html).group(1)
    colunas = ('id,layer,flight_project_descricao,control_status,verify_flight_size,scheduled_date,'
               'start_date_flight,end_date_flight,modified_utc')
    linhas, inicio = [], 0
    while True:
        r = requests.get(url, params={'select': colunas, 'order': 'id'},
                         headers={'apikey': chave, 'Authorization': f'Bearer {chave}',
                                  'Range': f'{inicio}-{inicio + 999}'}, timeout=60)
        r.raise_for_status()
        lote = r.json()
        linhas += lote
        if len(lote) < 1000:
            return linhas
        inicio += 1000


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--simular', action='store_true', help='lê e mostra, sem gravar')
    args = ap.parse_args()

    voos = [v for v in ler_voo_status() if v['layer']]
    print(f'Drone MGMT (via Expo_safra): {len(voos)} voos com talhão')
    print('  por projeto:', dict(collections.Counter(v['flight_project_descricao'] for v in voos).most_common(8)))
    linhas = [{
        'dronemgmt_id': v['id'],
        'layer': v['layer'],
        'projeto_voo': v['flight_project_descricao'],
        'control_status': v['control_status'],
        'verify_flight_size': v['verify_flight_size'],
        'data_agendada': v['scheduled_date'],
        'inicio_voo': v['start_date_flight'],
        'fim_voo': v['end_date_flight'],
        'modificado_dronemgmt': v['modified_utc'],
    } for v in voos]
    if args.simular:
        print('Simulação: nada foi gravado.')
        return
    Hub().upsert('voo_dronemgmt', linhas, 'dronemgmt_id')
    print('Gravado no Hub.')


if __name__ == '__main__':
    main()
