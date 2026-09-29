"""Carga única do legado (spec, seção 8), a partir do catálogo da fase 1 (catalogo_drone.xlsx).
Uso: python -m drone.importar_legado --simular   (só relatório)
     python -m drone.importar_legado             (grava e publica)
Roda na máquina com acesso ao G:\\ e ao catálogo. Rodar de novo não duplica nada."""
import csv
import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union

from drone.banco import DroneBanco, carregar_env
from drone.config import CRS_TRABALHO, PASTA_TRABALHO, cfg
from drone.geometria import so_poligonos
from drone.insumos import classe_pelo_nome, ler_shapefile
from drone.publicacao import GitHubReleases, publicar
from drone.saida import gravar_aplicacao, montar_zip

MOTIVO = 'Importado do legado'
TIPOS = {'Normal': 'normal', 'Catação': 'catacao'}
OBSTACULO_CLASSE = {'Árvores': 15, 'Rede elétrica': 25, 'Sede': 50}


def _texto(v) -> str:
    return '' if v is None or pd.isna(v) else str(v)   # vazio (NaN) ordena como o mais antigo


def _numero_rev(rev) -> int:
    m = re.search(r'(\d+)', _texto(rev))
    return int(m.group(1)) if m else -1


def chave_recencia(l) -> tuple:
    return (_texto(l['safra']), _numero_rev(l['revisao']), _texto(l['modificado_em']))


def selecionar_projetos(catalogo: pd.DataFrame) -> pd.DataFrame:
    ap = catalogo[(catalogo['categoria'] == 'Aplicação') & catalogo['subtipo'].isin(TIPOS)].copy()
    ap['_k'] = ap.apply(chave_recencia, axis=1)
    return (ap.sort_values('_k').groupby(['cod_fazenda', 'subtipo'], as_index=False).tail(1)
            .drop(columns='_k').reset_index(drop=True))


def classe_do_legado(l) -> int | None:
    if l['categoria'] == 'Restrição':
        m = re.search(r'(\d+)', str(l['subtipo']))
        return int(m.group(1)) if m and int(m.group(1)) in (15, 25, 50) else classe_pelo_nome(l['arquivo'])
    if l['categoria'] == 'Obstáculo':
        nome = str(l['arquivo']).lower()
        if 'alta' in nome or 'tens' in nome:
            return 50
        return OBSTACULO_CLASSE.get(l['subtipo'])
    return None


def selecionar_obstaculos(catalogo: pd.DataFrame) -> dict:
    ob = catalogo[catalogo['categoria'].isin(['Restrição', 'Obstáculo'])].copy()
    ob['classe'] = ob.apply(classe_do_legado, axis=1)
    ob = ob[ob['classe'].notna()]
    ob['_k'] = ob.apply(lambda l: (_texto(l['safra']), _numero_rev(l['revisao'])), axis=1)
    saida = {}
    for (cod, classe), g in ob.groupby(['cod_fazenda', 'classe']):
        recente = g['_k'].max()
        saida[(int(cod), int(classe))] = g.loc[g['_k'] == recente, 'caminho'].tolist()
    return saida


def _pdf_do_projeto(shp: Path):
    for pasta in (shp.parent, shp.parent.parent):
        pdfs = sorted(pasta.glob('*.pdf'), key=lambda p: p.stat().st_mtime, reverse=True)
        if pdfs:
            return pdfs[0]
    return None


def main():
    simular = '--simular' in sys.argv
    sys.stdout.reconfigure(encoding='utf-8')
    c = cfg()
    cat = pd.read_excel(c['catalogo_legado'], sheet_name='Catalogo', dtype={'cod_fazenda': str})
    cat = cat[cat['cod_fazenda'].str.fullmatch(r'\d{5}', na=False)]
    banco = DroneBanco()
    gh = None if simular else GitHubReleases(carregar_env()['GH_TOKEN'], c['arquivos_repo'])
    fazendas = {f['cod_faz'] for f in banco.selecionar('fazendas', 'cod_faz')}
    legado = banco.selecionar('drone_solicitacoes', 'id,cod_faz,tipo,revisao_id', {'origem': 'eq.legado'})
    ja_legado = {(s['cod_faz'], s['tipo']) for s in legado if s['revisao_id']}
    # solicitação criada numa execução que caiu antes de publicar: reaproveita
    pendentes = {(s['cod_faz'], s['tipo']): s['id'] for s in legado if not s['revisao_id']}
    obst_legado = {(v['cod_faz'], v['classe_m']) for v in banco.selecionar('drone_obstaculo_versoes',
                                                                            'cod_faz,classe_m', {'origem': 'eq.legado'})}
    relatorio = []

    def rel(cod, item, resultado, detalhe=''):
        relatorio.append({'cod_faz': cod, 'item': item, 'resultado': resultado, 'detalhe': detalhe})

    for (cod, classe), caminhos in sorted(selecionar_obstaculos(cat).items()):
        item = f'obstáculos {classe} m'
        if cod not in fazendas:
            rel(cod, item, 'fora', 'fazenda não está na Base Fazendas'); continue
        if (cod, classe) in obst_legado:
            rel(cod, item, 'pulado', 'já importado'); continue
        try:
            geoms = [g for p in caminhos for g in ler_shapefile(Path(p))]
            if not simular:
                banco.gravar_obstaculos(cod, classe, 'legado', ' + '.join(Path(p).name for p in caminhos), geoms)
            rel(cod, item, 'ok', f'{len(geoms)} feições de {len(caminhos)} arquivo(s)')
        except Exception as e:
            rel(cod, item, 'erro', str(e))

    for _, l in selecionar_projetos(cat).iterrows():
        cod, tipo = int(l['cod_fazenda']), TIPOS[l['subtipo']]
        item = f'projeto {tipo} ({l["safra"]} {l["revisao"]})'
        if cod not in fazendas:
            rel(cod, item, 'fora', 'fazenda não está na Base Fazendas'); continue
        if (cod, tipo) in ja_legado:
            rel(cod, item, 'pulado', 'já importado'); continue
        try:
            shp = Path(l['caminho'])
            orig = gpd.read_file(shp)
            if orig.crs is None:
                raise ValueError('shape sem .prj')
            area = so_poligonos(unary_union(list(orig.to_crs(CRS_TRABALHO).geometry)))
            antigo = pd.to_numeric(orig.drop(columns='geometry').iloc[0], errors='coerce').dropna()
            antigo = [v for v in antigo if v != 10]      # o outro campo é a taxa (sempre 10)
            pdf = _pdf_do_projeto(shp)
            avisos = [] if pdf else ['sem PDF']
            if antigo and abs(area.area / 1e4 - antigo[0]) > 0.02 * antigo[0]:
                avisos.append(f'área recalculada {area.area / 1e4:.2f} ha x antiga {antigo[0]:.2f} ha')
            if not simular:
                pasta = PASTA_TRABALHO / 'legado' / f'{cod}-{tipo}'
                zip_ = montar_zip(gravar_aplicacao(area, 10, pasta / 'shape', cod), pasta / f'{cod}.zip')
                sol_id = pendentes.get((cod, tipo)) or banco.criar_solicitacao(cod, tipo, 'legado', status='ok')['id']
                # publicar() continua uma revisão interrompida, então repetir não cria Rev1
                rev = publicar(banco, gh, cod, tipo, f'{MOTIVO} ({shp})', {'zip': zip_, 'pdf': pdf})
                banco.atualizar('drone_solicitacoes', {'id': f'eq.{sol_id}'}, {'revisao_id': rev})
            rel(cod, item, 'ok', '; '.join(avisos) + f' | origem: {shp}')
        except Exception as e:
            rel(cod, item, 'erro', str(e))

    PASTA_TRABALHO.mkdir(parents=True, exist_ok=True)
    saida = PASTA_TRABALHO / 'relatorio_legado.csv'
    with open(saida, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['cod_faz', 'item', 'resultado', 'detalhe'], delimiter=';')
        w.writeheader(); w.writerows(relatorio)
    if relatorio:
        df = pd.DataFrame(relatorio)
        resumo = df.groupby([df['item'].str.split(' ').str[:2].str.join(' '), 'resultado']).size()
    else:
        resumo = 'nada a fazer'
    print(resumo)
    print(f'relatório: {saida}' + ('  (SIMULAÇÃO — nada gravado)' if simular else ''))


if __name__ == '__main__':
    main()
