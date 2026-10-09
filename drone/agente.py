"""Agente do módulo Drone no servidor Geo: gera e publica o que estiver na fila.
Uso: python -m drone.agente            (laço contínuo, intervalo do config.json)
     python -m drone.agente --uma-vez  (um ciclo e sai — para testes)"""
import datetime
import sys
import time
import traceback

from drone.banco import DroneBanco, carregar_env
from drone.base_talhoes import arquivo_mais_recente
from drone.config import PASTA_TRABALHO, cfg
from drone.envios import processar_envio
from drone.erros import ErroGeracao
from drone.gerador import processar
from drone.publicacao import GitHubReleases, publicar


def _log(msg):
    print(f'{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}', flush=True)


def gerar_uma(banco, c) -> bool:
    g = banco.pegar_geracao()
    if not g:
        return False
    _log(f"geração {g['id']} (solicitação {g['solicitacao_id']})")
    try:
        base = arquivo_mais_recente(c['base_talhoes_pasta'], c['base_talhoes_padrao'])
        campos = processar(g, banco, base, PASTA_TRABALHO, datetime.date.today())
        banco.concluir_geracao(g['id'], **campos)
        _log(f"  pronta ({len(campos['alertas'])} alertas)")
    except ErroGeracao as e:
        banco.concluir_geracao(g['id'], status='erro', erro=str(e))
        _log(f'  erro: {e}')
    except Exception as e:  # erro inesperado: registra e segue a fila
        banco.concluir_geracao(g['id'], status='erro', erro=f'Erro interno do gerador: {e}')
        _log(traceback.format_exc())
    return True


def publicar_uma(banco, gh) -> bool:
    g = banco.pegar_publicacao()
    if not g:
        return False
    _log(f"publicando geração {g['id']}")
    try:
        sol = banco.solicitacao(g['solicitacao_id'])
        pasta = PASTA_TRABALHO / f"publicacao-{g['id']}"
        arquivos = {'zip': banco.baixar_previa(g['previa_zip'], pasta / 'p.zip'),
                    'pdf': banco.baixar_previa(g['previa_pdf'], pasta / 'p.pdf')}
        rev = publicar(banco, gh, sol['cod_faz'], sol['tipo'], g.get('publicar_motivo'), arquivos,
                       numero_esperado=(g.get('insumos') or {}).get('revisao_prevista'), geracao_id=g['id'])
        _log(f'  publicada (revisão {rev})')
    except Exception as e:
        banco.erro_publicacao(g['id'], str(e))
        _log(f'  falha na publicação: {e}')
    return True


def processar_um_envio(banco) -> bool:
    e = banco.pegar_envio()
    if not e:
        return False
    _log(f"envio {e['id']} ({e['tipo']}, fazenda {e['cod_faz']})")
    try:
        _log('  ' + processar_envio(e, banco, PASTA_TRABALHO))
        banco.concluir_envio(e['id'], 'ok')
    except ErroGeracao as erro:
        banco.concluir_envio(e['id'], 'erro', str(erro))
        _log(f'  erro: {erro}')
    except Exception as erro:
        banco.concluir_envio(e['id'], 'erro', f'Erro interno ao ler o envio: {erro}')
        _log(traceback.format_exc())
    return True


def limpar_previas(banco):
    """Prévias de gerações publicadas, descartadas ou prontas há mais de 30 dias saem do Storage."""
    for g in banco.previas_para_apagar():
        banco.apagar_previas([g['previa_zip'], g['previa_pdf']])
        banco.limpar_previa(g['id'], descartar=g['status'] == 'pronta')


def ciclo(banco, gh, c) -> bool:
    banco.batimento()
    try:
        limpar_previas(banco)
        banco.rpc('drone_avisos_limpar')             # "Publicado" some do sininho depois de 7 dias
    except Exception as e:   # Storage/banco fora não pode travar a fila
        _log(f'limpeza de prévias/avisos falhou: {e}')
    trabalhou = processar_um_envio(banco)
    trabalhou = gerar_uma(banco, c) or trabalhou
    return publicar_uma(banco, gh) or trabalhou


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    c = cfg()
    banco = DroneBanco()
    gh = GitHubReleases(carregar_env()['GH_TOKEN'], c['arquivos_repo'])
    if '--uma-vez' in sys.argv:
        ciclo(banco, gh, c)
        return
    _log('agente do Drone iniciado')
    while True:
        try:
            while ciclo(banco, gh, c):   # esvazia a fila antes de dormir
                pass
        except Exception:
            _log(traceback.format_exc())   # rede/banco fora: tenta de novo no próximo ciclo
        time.sleep(c['intervalo_s'])


if __name__ == '__main__':
    main()
