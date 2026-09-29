"""Carga única do legado (spec, seção 8), a partir do catálogo da fase 1 (catalogo_drone.xlsx).
Uso: python -m drone.importar_legado --simular   (só relatório)
     python -m drone.importar_legado             (grava e publica)
Roda na máquina com acesso ao G:\\ e ao catálogo. Rodar de novo não duplica nada."""
import csv
import datetime
import re
import sys
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import force_2d
from shapely.ops import unary_union
from shapely.validation import make_valid

from drone.banco import DroneBanco, carregar_env
from drone.config import CRS_TRABALHO, PASTA_TRABALHO, cfg
from drone.geometria import resumir, so_poligonos
from drone.base_talhoes import arquivo_mais_recente, talhoes_da_fazenda
from drone.insumos import classe_pelo_nome, ler_shapefile
from drone.mapa_pdf import DadosMapa, gerar_pdf
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


def safra_curta(safra):
    m = re.match(r'(\d{4})-(\d{4})', _texto(safra))
    return f'{m[1][2:]}/{m[2][2:]}' if m else None


def recorte_legado(talhoes, area):
    """Mantém a geometria do projeto antigo; só reparte a área pelos talhões da Base de hoje."""
    return resumir(talhoes, area)


def divergencia(talhoes, area) -> dict:
    """Quanto do projeto antigo caiu fora dos talhões de hoje, e quanto da fazenda ele cobre."""
    uniao = unary_union(list(talhoes.geometry))
    return {'fora_da_base_pct': 100 * area.difference(uniao).area / area.area,
            'cobertura_base_pct': 100 * area.intersection(uniao).area / uniao.area}


def area_antiga(atributos: dict):
    """Área gravada no shape antigo, achada pelo nome do campo (área/aplicável), nunca pelo código."""
    for campo, valor in atributos.items():
        nome = unicodedata.normalize('NFD', str(campo)).encode('ascii', 'ignore').decode().lower()
        if re.search(r'area|apli', nome):
            v = pd.to_numeric(valor, errors='coerce')
            if pd.notna(v):
                return float(v)
    return None


def crs_pela_faixa(bounds):
    """Legado sem .prj: graus dentro do Brasil → WGS84; metros na faixa da UTM 23S → SIRGAS 2000."""
    minx, miny, maxx, maxy = bounds
    if -75 <= minx <= maxx <= -30 and -35 <= miny <= maxy <= 6:
        return 4326
    if 100_000 <= minx <= maxx <= 900_000 and 7_000_000 <= miny <= maxy <= 8_500_000:
        return CRS_TRABALHO
    return None


def ler_legado(caminho: Path):
    """Como ler_shapefile, mas aceita arquivo antigo sem .prj quando a faixa das coordenadas é inequívoca.
    Devolve (geometrias em 31983, aviso ou '')."""
    caminho = Path(caminho)
    if caminho.with_suffix('.prj').exists():
        return ler_shapefile(caminho), ''
    gdf = gpd.read_file(caminho)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    epsg = crs_pela_faixa(gdf.total_bounds)
    if epsg is None:
        raise ValueError(f'{caminho.name} sem .prj e com coordenadas que não dá para identificar')
    gdf = gdf.set_crs(epsg).to_crs(CRS_TRABALHO)
    return [make_valid(force_2d(g)) for g in gdf.geometry], f'{caminho.name} sem .prj: assumido EPSG:{epsg}'


def main():
    simular = '--simular' in sys.argv
    sys.stdout.reconfigure(encoding='utf-8')
    c = cfg()
    cat = pd.read_excel(c['catalogo_legado'], sheet_name='Catalogo', dtype={'cod_fazenda': str})
    cat = cat[cat['cod_fazenda'].str.fullmatch(r'\d{5}', na=False)]
    banco = DroneBanco()
    gh = None if simular else GitHubReleases(carregar_env()['GH_TOKEN'], c['arquivos_repo'])
    fazendas = {f['cod_faz']: f['nome'] for f in banco.selecionar('fazendas', 'cod_faz,nome')}
    _, base = arquivo_mais_recente(c['base_talhoes_pasta'], c['base_talhoes_padrao'])
    com_obstaculos = {cod for cod, _ in selecionar_obstaculos(cat)}
    hoje = datetime.date.today()
    # a solicitação de legado nasce na mesma transação da revisão (hub.drone_publicar)
    ja_legado = {(s['cod_faz'], s['tipo']) for s in banco.selecionar('drone_solicitacoes', 'cod_faz,tipo',
                                                                     {'origem': 'eq.legado'})}
    obst_legado = {(v['cod_faz'], v['classe_m']) for v in banco.selecionar('drone_obstaculo_versoes',
                                                                            'cod_faz,classe_m', {'origem': 'eq.legado'})}
    relatorio = []

    def rel(cod, item, resultado, detalhe='', diverge='', obstaculos=''):
        relatorio.append({'cod_faz': cod, 'item': item, 'resultado': resultado, 'diverge': diverge,
                          'tem_obstaculos': obstaculos, 'detalhe': detalhe})

    for (cod, classe), caminhos in sorted(selecionar_obstaculos(cat).items()):
        item = f'obstáculos {classe} m'
        if cod not in fazendas:
            rel(cod, item, 'fora', 'fazenda não está na Base Fazendas'); continue
        if (cod, classe) in obst_legado:
            rel(cod, item, 'pulado', 'já importado'); continue
        try:
            lidos = [ler_legado(Path(p)) for p in caminhos]
            geoms = [g for gs, _ in lidos for g in gs]
            avisos = '; '.join(a for _, a in lidos if a)
            if not simular:
                banco.gravar_obstaculos(cod, classe, 'legado', ' + '.join(Path(p).name for p in caminhos), geoms)
            rel(cod, item, 'ok', f'{len(geoms)} feições de {len(caminhos)} arquivo(s)' + (f' | {avisos}' if avisos else ''))
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
            geoms, aviso_crs = ler_legado(shp)
            area = so_poligonos(unary_union(geoms))
            orig = gpd.read_file(shp, ignore_geometry=True)
            valores = [area_antiga(l) for l in orig.to_dict('records')]
            antigo = [sum(valores)] if valores and None not in valores else []
            avisos = [aviso_crs] if aviso_crs else []
            if antigo and abs(area.area / 1e4 - antigo[0]) > 0.02 * antigo[0]:
                avisos.append(f'área recalculada {area.area / 1e4:.2f} ha x antiga {antigo[0]:.2f} ha')
            talhoes = talhoes_da_fazenda(base, cod)
            div = divergencia(talhoes, area)
            # talhões mudaram desde o projeto (ou Normal que não cobre a fazenda): candidato a projeto novo
            diverge = div['fora_da_base_pct'] > 5 or (tipo == 'normal' and div['cobertura_base_pct'] < 85)
            avisos.append(f"fora da Base {div['fora_da_base_pct']:.0f}%, cobre {div['cobertura_base_pct']:.0f}% da fazenda")
            if not simular:
                pasta = PASTA_TRABALHO / 'legado' / f'{cod}-{tipo}'
                zip_ = montar_zip(gravar_aplicacao(area, 10, pasta / 'shape', cod), pasta / f'{cod}.zip')
                pdf = pasta / f'{cod}.pdf'
                gerar_pdf(DadosMapa(cod, fazendas[cod], tipo, 0, talhoes, recorte_legado(talhoes, area), hoje,
                                    safra=safra_curta(l['safra'])), pdf)
                publicar(banco, gh, cod, tipo, f'{MOTIVO} ({shp})', {'zip': zip_, 'pdf': pdf}, numero_esperado=0,
                         legado=True)
            rel(cod, item, 'ok', '; '.join(avisos) + f' | origem: {shp}',
                'sim' if diverge else 'não', 'sim' if cod in com_obstaculos else 'não')
        except Exception as e:
            rel(cod, item, 'erro', str(e))

    PASTA_TRABALHO.mkdir(parents=True, exist_ok=True)
    saida = PASTA_TRABALHO / 'relatorio_legado.csv'
    with open(saida, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['cod_faz', 'item', 'resultado', 'diverge', 'tem_obstaculos', 'detalhe'], delimiter=';')
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
