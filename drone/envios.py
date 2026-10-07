"""Envios de arquivo feitos pelo Hub (obstáculos, infestação, shape de ajuste): o navegador sobe no
Storage `drone-envios` e registra; aqui o agente baixa, valida, reprojeta e grava (spec Parte 2, §3.3)."""
import zipfile
from pathlib import Path

from drone.erros import ErroGeracao
from drone.insumos import classe_pelo_nome, ler_shapefile


def shapefiles(arquivos: list, pasta: Path) -> list:
    pasta = Path(pasta)
    for a in arquivos:
        a = Path(a)
        if a.suffix.lower() == '.zip':
            with zipfile.ZipFile(a) as z:
                z.extractall(pasta / a.stem)
    candidatos = [Path(a) for a in arquivos] + list(pasta.rglob('*'))
    return sorted({p.resolve() for p in candidatos if p.suffix.lower() == '.shp'}, key=lambda p: p.name)


def processar_envio(envio: dict, banco, pasta: Path) -> str:
    pasta = Path(pasta) / f"envio-{envio['id']}"
    locais = [banco.baixar_envio(c, pasta / 'arquivos' / c.split('/')[-1]) for c in envio['arquivos']]
    shps = shapefiles(locais, pasta / 'extraidos')
    if not shps:
        raise ErroGeracao('Nenhum shapefile (.shp) no envio. Envie o .shp com .shx, .dbf e .prj, ou um .zip.')
    lidos = []
    for shp in shps:                                     # valida tudo antes de gravar qualquer coisa
        geoms = ler_shapefile(shp)
        if not geoms:
            raise ErroGeracao(f'{shp.name} não tem nenhuma feição.')
        lidos.append((shp, geoms))
    cod, usuario, tipo = envio['cod_faz'], envio.get('enviado_por'), envio['tipo']
    if tipo == 'obstaculos':
        por_classe = {}
        for shp, geoms in lidos:
            classe = envio.get('classe_m') or classe_pelo_nome(shp.name)
            if classe is None:
                raise ErroGeracao(f'{shp.name}: não deu para saber a classe (15, 25 ou 50 m) pelo nome; '
                                  'escolha a classe no envio.')
            nomes, gs = por_classe.setdefault(classe, ([], []))
            nomes.append(shp.name)
            gs.extend(geoms)
        for classe, (nomes, gs) in sorted(por_classe.items()):
            banco.gravar_obstaculos(cod, classe, 'upload', ' + '.join(nomes), gs, usuario=usuario)
        return 'obstáculos: ' + ', '.join(f'{c} m ({len(g)} feições)' for c, (_, g) in sorted(por_classe.items()))
    geoms = [g for _, gs in lidos for g in gs]
    nomes = ' + '.join(shp.name for shp, _ in lidos)
    if tipo == 'infestacao':
        banco.gravar_infestacao(envio['solicitacao_id'], None, nomes, geoms, usuario=usuario)
        return f'infestação: {len(geoms)} feições de {len(lidos)} camada(s)'
    banco.gravar_ajuste(envio['id'], geoms)
    return f'shape de ajuste: {len(geoms)} feições'
