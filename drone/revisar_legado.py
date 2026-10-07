"""Revisão do legado fazenda a fazenda: junta os projetos do catálogo com os que estão dentro de .zip
na pasta da fazenda, consolida talhão a talhão e, se o resultado mudou, substitui a Rev0 publicada.
Uso: python -m drone.revisar_legado --simular                 (só relatório)
     python -m drone.revisar_legado [--fazendas 10008,10016]  (substitui o que mudou)
Nunca mexe em projeto que já tenha revisão feita pelo sistema (Rev1 em diante)."""
import csv
import datetime
import re
import statistics
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely import force_2d
from shapely.ops import unary_union
from shapely.validation import make_valid

from drone.banco import DroneBanco, carregar_env
from drone.base_talhoes import arquivo_mais_recente, talhoes_da_fazenda
from drone.config import CRS_TRABALHO, PASTA_TRABALHO, cfg
from drone.geometria import so_poligonos
from drone.importar_legado import (LIMIAR, MOTIVO, _texto, chave_recencia, consolidar, crs_pela_faixa,
                                   divergencia, ler_legado, projetos_por_fazenda, recorte_legado, safra_curta)
from drone.mapa_pdf import DadosMapa, gerar_pdf
from drone.montagem import dividir_por_talhao
from drone.publicacao import GitHubReleases, nome_arquivo, publicar
from drone.saida import gravar_aplicacao, montar_zip

FAZENDAS = Path('G:/GeoProc/GEOTECNOLOGIA/08 PROJETOS PILOTO AUTOMATICO/15 PROPRIO/FAZENDAS')
SAFRA = re.compile(r'^\d{4}-\d{4}$')
REV = re.compile(r'^rev\s*(\d+)', re.IGNORECASE)


# ── peças puras (testadas) ───────────────────────────────────────────────
def projetos_em_zips(pasta_fazenda: Path) -> list:
    """Shapes de aplicação de drone (campos de taxa/aplicável) dentro de .zip das pastas de projeto."""
    achados = []
    for z in sorted(Path(pasta_fazenda).glob('*/02 PROJETO/**/*.zip')):
        if re.search(r'exp', z.name, re.IGNORECASE):
            continue
        partes = z.relative_to(pasta_fazenda).parts
        safra = partes[0] if SAFRA.match(partes[0]) else None
        revisao = next((f'Rev{m[1]}' for p in reversed(partes[:-1]) if (m := REV.match(p))), None)
        try:
            with zipfile.ZipFile(z) as zf:
                shps = [i for i in zf.infolist() if i.filename.lower().endswith('.shp')]
                for info in shps:
                    caminho = f'zip://{z.as_posix()}!{info.filename}'
                    campos = [c.lower() for c in gpd.read_file(caminho, rows=1).columns]
                    if not any('taxa' in c or 'aplic' in c for c in campos):
                        continue
                    achados.append({'cod_fazenda': None, 'categoria': 'Aplicação', 'subtipo': None,
                                    'safra': safra, 'revisao': revisao, 'arquivo': Path(info.filename).name,
                                    'modificado_em': str(datetime.datetime(*info.date_time)), 'caminho': caminho})
        except Exception:
            continue                      # zip corrompido ou shape ilegível: segue para o próximo
    return achados


def mesma_geometria(a, b, tolerancia=0.01) -> bool:
    """Cópia do mesmo projeto (ex.: .zip com o shape de outra revisão)."""
    return a.symmetric_difference(b).area <= tolerancia * max(a.area, b.area)


def classificar(area, talhoes) -> str:
    """Normal cobre os talhões; Catação são manchas pequenas espalhadas (regra da fase 1)."""
    tocados = [g for g in talhoes.geometry if g.intersection(area).area > 1]
    cobertura = area.area / sum(g.area for g in tocados) if tocados else 0
    partes = list(getattr(area, 'geoms', [area]))
    mediana_ha = statistics.median(p.area for p in partes) / 1e4
    return 'catacao' if cobertura < 0.4 and mediana_ha < 0.2 else 'normal'


def precisa_refazer(usados: set, publicado: int, publicado_existe: bool, ja_consolidado: bool = False,
                    tipo: str = 'normal', motivo: str = '') -> bool:
    if not publicado_existe:
        return True
    if tipo == 'catacao':            # Catação = só o último levantamento (Parte 2)
        m = motivo or ''
        return 'último levantamento' not in m and (', ' in m or usados != {publicado})
    return not ja_consolidado and usados != {publicado}


# ── leitura ──────────────────────────────────────────────────────────────
def ler_projeto(caminho: str):
    if not caminho.startswith('zip://'):
        geoms, _ = ler_legado(Path(caminho))
        return so_poligonos(unary_union(geoms))
    gdf = gpd.read_file(caminho)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    if gdf.crs is None:
        epsg = crs_pela_faixa(gdf.total_bounds)
        if epsg is None:
            raise ValueError('zip sem .prj e com coordenadas irreconhecíveis')
        gdf = gdf.set_crs(epsg)
    gdf = gdf.to_crs(CRS_TRABALHO)
    return so_poligonos(unary_union([make_valid(force_2d(g)) for g in gdf.geometry]))


def pasta_da_fazenda(cod: int):
    pastas = sorted(FAZENDAS.glob(f'{cod} *')) + sorted(FAZENDAS.glob(f'{cod}-*'))
    return pastas[0] if pastas else None


# ── banco e GitHub ───────────────────────────────────────────────────────
def revisoes_do_documento(banco, cod, tipo) -> list:
    p = banco.selecionar('projetos', 'id', {'modulo_id': 'eq.drone', 'tipo': 'eq.individual', 'cod_faz': f'eq.{cod}'})
    if not p:
        return []
    return banco.selecionar('projeto_revisoes', 'id,numero,motivo', {'projeto_id': f"eq.{p[0]['id']}",
                                                              'documento': f'eq.{tipo}'})


def apagar(banco, tabela, filtro):
    r = requests.delete(f'{banco.url}/{tabela}', params=filtro, headers={**banco.headers, 'Prefer': 'return=minimal'},
                        timeout=60)
    banco._checar(r, tabela)


def apagar_rev0_legado(banco, gh, cod, nome_faz, tipo, rev_id):
    """Tira do ar a Rev0 do legado: arquivos no GitHub, solicitação de legado e a revisão (com os registros)."""
    release = gh.release(f'drone-{cod}', f'{nome_faz} — drone')
    nomes = {nome_arquivo(cod, nome_faz, 0, tipo, ext) for ext in ('zip', 'pdf')}
    for a in release.get('assets', []):
        if a['name'] in nomes:
            r = requests.delete(f'https://api.github.com/repos/{gh.repo}/releases/assets/{a["id"]}', headers=gh.h,
                                timeout=60)
            if r.status_code not in (204, 404):
                raise RuntimeError(f'GitHub: não apagou {a["name"]} ({r.status_code})')
    apagar(banco, 'drone_solicitacoes', {'cod_faz': f'eq.{cod}', 'tipo': f'eq.{tipo}', 'origem': 'eq.legado'})
    apagar(banco, 'projeto_revisoes', {'id': f'eq.{rev_id}'})


# ── laço fazenda a fazenda ───────────────────────────────────────────────
def main():
    simular = '--simular' in sys.argv
    so = set()
    if '--fazendas' in sys.argv:
        so = {int(x) for x in sys.argv[sys.argv.index('--fazendas') + 1].split(',')}
    sys.stdout.reconfigure(encoding='utf-8')
    c = cfg()
    cat = pd.read_excel(c['catalogo_legado'], sheet_name='Catalogo', dtype={'cod_fazenda': str})
    cat = cat[cat['cod_fazenda'].str.fullmatch(r'\d{5}', na=False)]
    grupos = projetos_por_fazenda(cat)
    banco = DroneBanco()
    gh = None if simular else GitHubReleases(carregar_env()['GH_TOKEN'], c['arquivos_repo'])
    fazendas = {f['cod_faz']: f['nome'] for f in banco.selecionar('fazendas', 'cod_faz,nome')}
    _, base = arquivo_mais_recente(c['base_talhoes_pasta'], c['base_talhoes_padrao'])
    hoje = datetime.date.today()
    cods = sorted({cod for cod, _ in grupos} | set())
    if so:
        cods = [x for x in cods if x in so]
    relatorio = []
    for n, cod in enumerate(cods, 1):
        if cod not in fazendas:
            continue
        try:
            talhoes = talhoes_da_fazenda(base, cod)
        except Exception as e:
            relatorio.append({'cod_faz': cod, 'tipo': '', 'resultado': 'erro', 'detalhe': str(e)})
            continue
        # projetos em .zip: entram no tipo que a geometria indicar, se não forem cópia de outro
        extras = {'normal': [], 'catacao': []}
        pasta = pasta_da_fazenda(cod)
        for p in (projetos_em_zips(pasta) if pasta else []):
            try:
                area = ler_projeto(p['caminho'])
                if not area.is_empty:
                    extras[classificar(area, talhoes)].append((pd.Series(p), area))
            except Exception:
                continue
        for tipo in ('normal', 'catacao'):
            base_cat = grupos.get((cod, tipo), [])
            if not base_cat and not extras[tipo]:
                continue
            linha = {'cod_faz': cod, 'tipo': tipo}
            try:
                lidos = []
                for l in base_cat:
                    try:
                        lidos.append((l, ler_projeto(l['caminho'])))
                    except Exception:
                        continue
                publicado = lidos[-1][0]['caminho'] if lidos else None   # o que a carga de 30/09 publicou
                novos = [(l, a) for l, a in extras[tipo] if not any(mesma_geometria(a, b) for _, b in lidos)]
                todos = sorted(lidos + novos, key=lambda x: chave_recencia(x[0]))
                if tipo == 'catacao':
                    todos = todos[-1:]                   # só o levantamento mais recente
                area, usados = consolidar(talhoes, [a for _, a in todos], LIMIAR[tipo])
                if area.is_empty:
                    raise ValueError('nenhum projeto cai nos talhões de hoje')
                revs = revisoes_do_documento(banco, cod, tipo)
                idx_pub = next((i for i, (l, _) in enumerate(todos) if l['caminho'] == publicado), -1)
                usados_l = [todos[i][0] for i in sorted(usados)]
                fontes = ', '.join(f"{safra_curta(l['safra'])} {_texto(l['revisao'])}"
                                   + (' (zip)' if str(l['caminho']).startswith('zip://') else '') for l in usados_l)
                linha['detalhe'] = f'{area.area / 1e4:.2f} ha de {len(usados_l)}: {fontes}'
                linha['cobre_pct'] = round(divergencia(talhoes, area)['cobertura_base_pct'])
                linha['zips_novos'] = len(novos)
                consolidado = any('consolidado' in (r['motivo'] or '') for r in revs)
                if not precisa_refazer(usados, idx_pub, bool(revs), consolidado, tipo=tipo,
                                       motivo=revs[0]['motivo'] if revs else ''):
                    linha['resultado'] = 'igual'
                elif any(r['numero'] > 0 for r in revs):
                    linha['resultado'] = 'tem revisão do sistema — não mexe'
                else:
                    linha['resultado'] = 'substituir' if revs else 'publicar'
                    if not simular:
                        pasta_t = PASTA_TRABALHO / 'revisao' / f'{cod}-{tipo}'
                        zip_ = montar_zip(gravar_aplicacao(area, 10, pasta_t / 'shape', cod), pasta_t / f'{cod}.zip')
                        pdf = pasta_t / f'{cod}.pdf'
                        gerar_pdf(DadosMapa(cod, fazendas[cod], tipo, 0, talhoes, recorte_legado(talhoes, area), hoje,
                                            safra=safra_curta(usados_l[-1]['safra'])), pdf)
                        if revs:
                            apagar_rev0_legado(banco, gh, cod, fazendas[cod], tipo, revs[0]['id'])
                        itens = dividir_por_talhao(area, talhoes, 'legado', 0)
                        motivo = (f'{MOTIVO} (último levantamento: {fontes})' if tipo == 'catacao'
                                  else f'{MOTIVO} (consolidado: {fontes})')
                        publicar(banco, gh, cod, tipo, motivo, {'zip': zip_, 'pdf': pdf},
                                 numero_esperado=0, legado=True, talhoes=itens)
                        linha['resultado'] += ' ✓'
            except Exception as e:
                linha['resultado'], linha['detalhe'] = 'erro', str(e)
            relatorio.append(linha)
            print(f"[{n}/{len(cods)}] {cod} {tipo}: {linha['resultado']}  {linha.get('detalhe', '')[:90]}", flush=True)

    saida = PASTA_TRABALHO / 'relatorio_revisao_legado.csv'
    PASTA_TRABALHO.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(relatorio)
    df.to_csv(saida, sep=';', index=False, encoding='utf-8-sig')
    print(df.groupby(['tipo', 'resultado']).size() if len(df) else 'nada a fazer')
    print(f'relatório: {saida}' + ('  (SIMULAÇÃO — nada gravado)' if simular else ''))


if __name__ == '__main__':
    main()
