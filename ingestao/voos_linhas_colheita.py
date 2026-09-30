"""Agente da Regra B da Colheita: agenda e acompanha os voos de Linhas de
Colheita no Drone MGMT (via GeoMap, rotas /integracao).

A cada execução:
  1. atualiza a fila (data de corte da safra atual + 100 dias, Base Fazendas);
  2. agenda no Drone MGMT os pedidos que já têm porte (liberar_em <= hoje);
  3. lê a situação dos voos agendados/voados (agendado → voado → divulgado).
Os avisos do sininho são gerados pelo banco a cada mudança.

O Hub não guarda a senha do Drone MGMT: quem fala com ele é o backend do
GeoMap. Precisa, no hub-geotech-supabase.env: GEOMAP_API_URL e
HUB_INTEGRACAO_TOKEN (o mesmo valor configurado no Render do GeoMap).

Uso:  python ingestao/voos_linhas_colheita.py [--simular]
"""

import argparse
import sys

import requests
import truststore

from comum import Hub, carregar_env

truststore.inject_into_ssl()   # o firewall da empresa inspeciona TLS (certificado só no Windows)


def geomap(env, rota, corpo):
    r = requests.post(env['GEOMAP_API_URL'].rstrip('/') + rota, json=corpo, timeout=300,
                      headers={'x-hub-token': env['HUB_INTEGRACAO_TOKEN']})
    if not r.ok:
        raise RuntimeError(f'GeoMap {rota}: HTTP {r.status_code} {r.text[:200]}')
    return r.json()['resultados']


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--simular', action='store_true', help='mostra a fila, sem agendar nem gravar')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    env, hub = carregar_env(), Hub()

    if args.simular:
        fila = hub.selecionar('colheita_voos', 'id,layer,tipo,status,data_corte,liberar_em',
                              {'status': 'not.in.(concluido,cancelado)', 'order': 'liberar_em.nullslast,id'})
        print(f'{len(fila)} pedido(s) ativo(s):')
        for v in fila:
            print(f"  {v['layer']} {v['tipo']:6} {v['status']:16} corte {v['data_corte'] or '—'} → voa {v['liberar_em'] or '—'}")
        print('Simulação: nada foi agendado.')
        return

    mudou = hub.rpc('colheita_voos_atualizar_fila')
    print(f'Fila atualizada ({mudou} pedido(s) mudaram de situação).')

    devidos = hub.rpc('colheita_voos_pegar_devidos', {'p_limite': 100}) or []
    falhou = False
    if devidos:
        print(f'Agendando {len(devidos)} voo(s) de Linhas de Colheita...')
        # Lotes pequenos: se uma chamada cair, só o lote volta para a fila. Voltar
        # é seguro porque o GeoMap não duplica: se o talhão já tem voo de Linhas de
        # Colheita ativo na safra (inclusive agendado à mão), devolve o existente.
        for i in range(0, len(devidos), 10):
            lote = devidos[i:i + 10]
            por_chave = {(d['section'], d['land_plot']): d for d in lote}
            try:
                resultados = geomap(env, '/integracao/dronemgmt/linhas-colheita/agendar', {
                    'harvest': lote[0]['harvest'],
                    'itens': [{'section': d['section'], 'landPlot': d['land_plot']} for d in lote]})
            except Exception as e:
                falhou = True
                print(f'  ✗ falha ao chamar o GeoMap ({e}); {len(lote)} pedido(s) voltam para a fila')
                requests.patch(f'{hub.url}/colheita_voos', params={'id': f"in.({','.join(str(d['id']) for d in lote)})",
                               'status': 'eq.agendando'}, headers=hub.headers, json={'status': 'na_fila'}, timeout=60)
                continue
            for res in resultados:
                d = por_chave.get((res['section'], res['landPlot']))
                if not d:
                    continue
                hub.rpc('colheita_voo_agendado', {'p_id': d['id'], 'p_dronemgmt_id': res.get('id'),
                                                  'p_erro': res.get('erro')})
                if res.get('erro'):
                    print(f"  {d['layer']}: ✗ {res['erro']}")
                elif res.get('existente'):
                    print(f"  {d['layer']}: já tinha voo de Linhas de Colheita no Drone MGMT ({res['id']}), ligado ao pedido")
                else:
                    print(f"  {d['layer']}: agendado ({res['id']})")
    else:
        print('Nenhum voo com porte para agendar agora.')

    ativos = hub.selecionar('colheita_voos', 'id,layer,dronemgmt_id,status',
                            {'status': 'in.(agendado,voado)', 'dronemgmt_id': 'not.is.null', 'order': 'id'})
    for i in range(0, len(ativos), 100):
        lote = ativos[i:i + 100]
        por_id = {a['dronemgmt_id']: a for a in lote}
        for res in geomap(env, '/integracao/dronemgmt/situacao', {'ids': list(por_id)}):
            a = por_id.get(res['id'])
            if a and res.get('controlStatus') is not None:
                hub.rpc('colheita_voo_situacao', {'p_id': a['id'], 'p_control_status': res['controlStatus']})
    print(f'Situação conferida de {len(ativos)} voo(s) agendado(s)/voado(s).')
    if falhou:
        sys.exit(1)


if __name__ == '__main__':
    main()
