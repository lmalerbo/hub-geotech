"""Carga única da Parte 2: grava os talhões (drone_revisao_talhoes) de cada revisão vigente do Drone,
recortando o .zip publicado pelos talhões da Base de hoje. Não republica nada.
Uso: python -m drone.migrar_parte2 [--simular]
Depois: python -m drone.revisar_legado   (Catações consolidadas voltam ao último levantamento)"""
import io
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import requests
from shapely.ops import unary_union

from drone.banco import DroneBanco
from drone.base_talhoes import arquivo_mais_recente, talhoes_da_fazenda
from drone.config import CRS_TRABALHO, PASTA_TRABALHO, cfg
from drone.geometria import so_poligonos
from drone.montagem import dividir_por_talhao, itens_para_json


def origem_da_revisao(motivo) -> str:
    return 'legado' if (motivo or '').startswith('Importado do legado') else 'sistema'


def geometria_publicada(url: str):
    import truststore
    truststore.inject_into_ssl()
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    pasta = PASTA_TRABALHO / 'migrar_parte2'
    pasta.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith('.shp'))
        z.extractall(pasta)
    g = gpd.read_file(pasta / nome).to_crs(CRS_TRABALHO)
    return so_poligonos(unary_union(list(g.geometry)))


def main():
    simular = '--simular' in sys.argv
    sys.stdout.reconfigure(encoding='utf-8')
    c = cfg()
    _, base = arquivo_mais_recente(c['base_talhoes_pasta'], c['base_talhoes_padrao'])
    banco = DroneBanco()
    vigentes = banco.selecionar('arquivos_vigentes', 'cod_faz,documento,revisao_id,nome_arquivo,release_url',
                                {'modulo_id': 'eq.drone', 'nome_arquivo': 'like.*.zip'})
    feitos = {r['revisao_id'] for r in banco.selecionar('drone_revisao_talhoes', 'revisao_id')}
    motivos = {r['id']: r['motivo'] for r in banco.selecionar('projeto_revisoes', 'id,motivo',
                                                              {'id': f"in.({','.join(str(v['revisao_id']) for v in vigentes)})"})} if vigentes else {}
    ok = erros = pulados = 0
    for n, v in enumerate(sorted(vigentes, key=lambda x: (x['cod_faz'], x['documento'])), 1):
        if v['revisao_id'] in feitos:
            pulados += 1
            continue
        try:
            talhoes = talhoes_da_fazenda(base, v['cod_faz'])
            area = geometria_publicada(v['release_url'])
            numero = int(v['nome_arquivo'].split('_Rev')[1].split('-')[0])
            itens = dividir_por_talhao(area, talhoes, origem_da_revisao(motivos.get(v['revisao_id'])), numero)
            if not simular:
                banco.rpc('drone_gravar_revisao_talhoes', {'p_revisao_id': v['revisao_id'],
                                                           'p_talhoes': itens_para_json(itens)})
            ok += 1
            print(f"[{n}/{len(vigentes)}] {v['cod_faz']} {v['documento']}: {len(itens)} talhões", flush=True)
        except Exception as e:
            erros += 1
            print(f"[{n}/{len(vigentes)}] {v['cod_faz']} {v['documento']}: ERRO {e}", flush=True)
    print(f'ok {ok} | erro {erros} | já tinham {pulados}' + ('  (SIMULAÇÃO — nada gravado)' if simular else ''))


if __name__ == '__main__':
    main()
