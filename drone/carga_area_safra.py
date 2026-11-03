"""Carga ÚNICA de área de aplicação e safra dos projetos de drone vindos do legado (spec 2026-10-29, D4).

Projetos feitos no Hub não precisam: hub.drone_projetos_v lê o resumo da geração publicada.
Uso, da raiz do repositório:
    python -m drone.carga_area_safra            # só mostra o que faria
    python -m drone.carga_area_safra --aplicar  # grava em hub.projeto_revisoes
"""
import io
import re
import sys
import zipfile

import requests
import shapefile

from drone.banco import DroneBanco


def area_do_zip(conteudo):
    """Soma do campo de área de todos os .shp do ZIP; None se nenhum tiver campo de área."""
    z = zipfile.ZipFile(io.BytesIO(conteudo))
    nomes = z.namelist()
    total, achou = 0.0, False
    for base in [n[:-4] for n in nomes if n.lower().endswith('.shp')]:
        parte = {e: io.BytesIO(z.read(next(n for n in nomes if n.lower() == (base + e).lower())))
                 for e in ('.shp', '.dbf', '.shx')}
        sf = shapefile.Reader(shp=parte['.shp'], dbf=parte['.dbf'], shx=parte['.shx'], encoding='utf-8')
        campo = next((f[0] for f in sf.fields[1:] if f[0].lower().startswith(('área', 'area'))), None)
        if campo:
            achou = True
            total += sum(float(r[campo] or 0) for r in sf.records())
    return round(total, 2) if achou else None


def safra_do_motivo(motivo):
    """Safra registrada na importação do legado: '2025-2026' na pasta de origem ou '25/26 Rev'."""
    motivo = motivo or ''
    s = re.findall(r'(?<!\d)(20\d\d)-(20\d\d)(?!\d)', motivo)
    if s:
        return f'{s[-1][0][2:]}/{s[-1][1][2:]}'
    s = re.findall(r'(\d\d/\d\d) Rev', motivo)
    return max(s) if s else None


def main(aplicar):
    import truststore
    truststore.inject_into_ssl()   # o firewall da empresa inspeciona TLS (certificado só no Windows)
    b = DroneBanco()
    vig = [r for r in b.selecionar('arquivos_vigentes', '*', {'modulo_id': 'eq.drone'})
           if r['nome_arquivo'].lower().endswith('.zip')]
    view = {r['revisao_id']: r for r in b.selecionar('drone_projetos_v', 'revisao_id,origem', {})}
    ok, falhas, sem_safra = 0, [], []
    for r in vig:
        if view.get(r['revisao_id'], {}).get('origem') != 'sem_dado':
            continue   # já tem dado (Hub ou carga anterior)
        rev = b.selecionar('projeto_revisoes', 'id,motivo', {'id': f"eq.{r['revisao_id']}"})[0]
        try:
            area = area_do_zip(requests.get(r['release_url'], timeout=60).content)
        except Exception as e:  # noqa: BLE001  ZIP corrompido ou fora do ar: lista e segue
            falhas.append((r['revisao_id'], r['cod_faz'], f'zip: {str(e)[:80]}'))
            continue
        if area is None:
            falhas.append((r['revisao_id'], r['cod_faz'], 'sem campo de área no ZIP'))
            continue
        safra = safra_do_motivo(rev['motivo'])
        if safra is None:   # grava só a área: na view entra em "anteriores / sem safra" (spec, casos de borda)
            sem_safra.append((r['revisao_id'], r['cod_faz'], f'area={area}'))
        if aplicar:
            b.atualizar('projeto_revisoes', {'id': f"eq.{r['revisao_id']}"}, {'area_aplicacao_ha': area, 'safra': safra})
        ok += 1
    print(f"{'gravados' if aplicar else 'a gravar'}: {ok} (sem safra: {len(sem_safra)}) · sem dado: {len(falhas)}")
    for f in sem_safra:
        print('   sem safra', *f)
    for f in falhas:
        print('  ', *f)


if __name__ == '__main__':
    main('--aplicar' in sys.argv)
