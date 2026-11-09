"""Agente da fase de voo do Preparo: lê no Drone MGMT (via GeoMap, rota /integracao)
os voos de Sistematização/Expansão das fazendas com talhões em Identificação e grava
o espelho em hub.voo_dronemgmt. A situação por talhão sai da view hub.preparo_voo_talhao.

Só leitura no Drone MGMT. Precisa, no hub-geotech-supabase.env: GEOMAP_API_URL e
HUB_INTEGRACAO_TOKEN (os mesmos do voos_linhas_colheita.py).

Cada rodada fica em hub.execucoes_ingestao (fonte 'voos_preparo'), para o card
"Dados atualizados" acusar quando ela parar. O --simular não registra nada.

Uso:  python ingestao/voos_preparo.py [--simular]
"""

import argparse
import collections
import sys

import requests
import truststore

from comum import Execucao, Hub, carregar_env

truststore.inject_into_ssl()   # o firewall da empresa inspeciona TLS (certificado só no Windows)


def lotes(itens, tamanho):
    return [itens[i:i + tamanho] for i in range(0, len(itens), tamanho)]


def separar(resultados):
    """Fazendas lidas sem erro e os registros delas. Fazenda com erro fica de fora: nada é apagado nela."""
    secoes, registros = [], []
    for r in resultados:
        if r.get('erro'):
            print(f"  {r['section']}: {r['erro']}")
            continue
        secoes.append(int(r['section']))
        registros += r['registros']
    return secoes, registros


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--simular', action='store_true', help='mostra o que leu, sem gravar')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    env, hub = carregar_env(), Hub()

    if args.simular:
        ler(env, hub, simular=True)
        return
    with Execucao(hub, 'voos_preparo') as execucao:
        lidos, erros, n_fazendas = ler(env, hub)
        sit = collections.Counter(x['situacao'] for x in hub.selecionar('preparo_voo_talhao', 'situacao'))
        print('Situação dos talhões em Identificação:', dict(sit))
        execucao.linhas_lidas = execucao.linhas_gravadas = lidos
        execucao.detalhes = {'fazendas': n_fazendas, 'fazendas_com_erro': erros, 'situacao': dict(sit)}


def ler(env, hub, simular=False):
    """Lê os voos no GeoMap e grava. Devolve (registros gravados, fazendas com erro, fazendas consultadas)."""
    em_ident = hub.selecionar('talhao_preparo', 'layer', {'etapa': 'eq.Identificação'})
    fazendas = sorted({str(r['layer'] // 1000) for r in em_ident})
    print(f'{len(em_ident)} talhões em Identificação, {len(fazendas)} fazendas')

    lidos, erros = 0, []
    for lote in lotes(fazendas, 50):
        r = requests.post(env['GEOMAP_API_URL'].rstrip('/') + '/integracao/dronemgmt/preparo/voos',
                          json={'secoes': lote}, timeout=300, headers={'x-hub-token': env['HUB_INTEGRACAO_TOKEN']})
        if not r.ok:
            raise RuntimeError(f'GeoMap: HTTP {r.status_code} {r.text[:200]}')
        resultados = r.json()['resultados']
        erros += [str(x['section']) for x in resultados if x.get('erro')]
        secoes, registros = separar(resultados)
        print(f'  lote: {len(secoes)} fazendas lidas, {len(registros)} registros')
        if simular:
            print('   ', collections.Counter((x['projeto'], x['controlStatus']) for x in registros))
            continue
        hub.rpc('preparo_voos_gravar', {'p_secoes': secoes, 'p_registros': registros})
        lidos += len(registros)
    return lidos, erros, len(fazendas)

if __name__ == '__main__':
    main()
