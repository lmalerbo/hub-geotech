"""Processa uma geração: insumos → recorte → shapefile/zip → PDF → prévia (spec, seção 6)."""
import datetime
from pathlib import Path

from shapely.ops import unary_union

from drone.base_talhoes import talhoes_da_fazenda
from drone.erros import ErroGeracao
from drone.geometria import recortar, uniao_buffers
from drone.mapa_pdf import DadosMapa, gerar_pdf
from drone.saida import gravar_aplicacao, montar_zip


def alertas(recorte, versoes, params, hoje, infestacao_fora=False) -> list:
    msgs = []
    minimo = float(params['alerta_aproveitamento_min'])
    for t in recorte.por_talhao:
        if t['area_prod'] > 0 and t['aplicavel_ha'] < minimo * t['area_prod']:
            msgs.append(f"Talhão {t['talhao']}: aplicável {t['aplicavel_ha']:.2f} ha de {t['area_prod']:.2f} ha "
                        f"(abaixo de {minimo:.0%}).")
    for talhao in recorte.talhoes_sem_area_prod:
        msgs.append(f'Talhão {talhao} sem AREA_PROD na Base; contado como 0 na área total.')
    meses = int(params['alerta_obstaculos_meses'])
    limite = hoje - datetime.timedelta(days=30 * meses)
    for v in versoes:
        if datetime.date.fromisoformat(v['enviado_em'][:10]) < limite:
            msgs.append(f"Obstáculos da classe {v['classe_m']} m têm mais de {meses} meses.")
    classes = {v['classe_m'] for v in versoes}
    for c in (15, 25, 50):
        if c not in classes:
            msgs.append(f'Nenhum obstáculo cadastrado na classe {c} m.')
    if infestacao_fora:
        msgs.append('Parte da infestação está fora dos talhões da fazenda e foi descartada.')
    return msgs


def processar(geracao: dict, banco, base: tuple, pasta: Path, hoje: datetime.date) -> dict:
    data_base, arquivo_base = base
    sol = banco.solicitacao(geracao['solicitacao_id'])
    cod, tipo = sol['cod_faz'], sol['tipo']
    params, distancias = banco.parametros(), banco.distancias()
    faz = banco.fazenda(cod)
    talhoes = talhoes_da_fazenda(Path(arquivo_base), cod)
    obst, versoes = banco.obstaculos_vigentes(cod)

    infest, margem, fora = None, 0.0, False
    if tipo == 'catacao':
        if not geracao.get('infestacao_id'):
            raise ErroGeracao('Catação sem shape de infestação: envie a infestação antes de gerar.')
        infest = banco.infestacao(geracao['infestacao_id'])
        margem = float(params['margem_infestacao_m'])
        fora = not unary_union(infest).buffer(margem).difference(unary_union(list(talhoes.geometry))).is_empty

    recorte = recortar(talhoes, uniao_buffers(obst, distancias), infestacao=infest, margem=margem)
    revisao = banco.proximo_numero(cod, tipo)   # só leitura: o projeto nasce na publicação

    saida = Path(pasta) / f"geracao-{geracao['id']}"
    shp = gravar_aplicacao(recorte.area, int(params['taxa_l_ha']), saida / 'shape', cod)
    zip_ = montar_zip(shp, saida / f'{cod}.zip')
    pdf = saida / f'{cod}.pdf'
    orient = gerar_pdf(DadosMapa(cod, faz['nome'], tipo, revisao, talhoes, recorte, hoje), pdf)

    destino = f"geracao-{geracao['id']}"
    return {
        'status': 'pronta',
        'orientacao': orient,
        'insumos': {'distancias': distancias, 'taxa_l_ha': params['taxa_l_ha'], 'margem_infestacao_m': margem,
                    'base_talhoes': Path(arquivo_base).name, 'data_base': data_base.isoformat(),
                    'obstaculos': [v['versao_id'] for v in versoes], 'infestacao_id': geracao.get('infestacao_id'),
                    'revisao_prevista': revisao},
        'resumo': {'por_talhao': recorte.por_talhao, 'area_total_ha': recorte.area_total_ha,
                   'aplicacao_ha': recorte.aplicacao_ha},
        'alertas': alertas(recorte, versoes, params, hoje, fora),
        'previa_zip': banco.subir_previa(zip_, f'{destino}/{cod}.zip'),
        'previa_pdf': banco.subir_previa(pdf, f'{destino}/{cod}.pdf'),
    }
