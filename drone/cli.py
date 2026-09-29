"""Operação manual do módulo Drone enquanto as telas (Parte 2) não existem."""
import argparse
import json
from pathlib import Path

from drone.banco import DroneBanco
from drone.insumos import classe_pelo_nome, ler_shapefile


def main():
    p = argparse.ArgumentParser(prog='python -m drone.cli')
    s = p.add_subparsers(dest='cmd', required=True)
    a = s.add_parser('solicitar'); a.add_argument('cod_faz', type=int); a.add_argument('tipo', choices=['normal', 'catacao']); a.add_argument('--data')
    a = s.add_parser('obstaculos'); a.add_argument('cod_faz', type=int); a.add_argument('arquivo'); a.add_argument('--classe', type=int, choices=[15, 25, 50])
    a = s.add_parser('infestacao'); a.add_argument('solicitacao_id', type=int); a.add_argument('arquivos', nargs='+'); a.add_argument('--empresa')
    a = s.add_parser('gerar'); a.add_argument('solicitacao_id', type=int)
    a = s.add_parser('publicar'); a.add_argument('geracao_id', type=int); a.add_argument('--motivo')
    a = s.add_parser('status'); a.add_argument('solicitacao_id', type=int)
    args = p.parse_args()
    b = DroneBanco()

    if args.cmd == 'solicitar':
        sol = b.criar_solicitacao(args.cod_faz, args.tipo, 'formulario', data_desejada=args.data)
        print(f"solicitação {sol['id']}: {sol['status']}")
    elif args.cmd == 'obstaculos':
        classe = args.classe or classe_pelo_nome(args.arquivo)
        if not classe:
            raise SystemExit('Não deu para saber a classe pelo nome do arquivo: use --classe 15|25|50')
        geoms = ler_shapefile(Path(args.arquivo))
        print(f'versão {b.gravar_obstaculos(args.cod_faz, classe, "upload", Path(args.arquivo).name, geoms)} '
              f'da classe {classe} m ({len(geoms)} feições)')
    elif args.cmd == 'infestacao':
        # a empresa entrega um shapefile por tipo de erva: todos entram na mesma infestação
        geoms = [g for a in args.arquivos for g in ler_shapefile(Path(a))]
        nomes = ' + '.join(Path(a).name for a in args.arquivos)
        print(f'infestação {b.gravar_infestacao(args.solicitacao_id, args.empresa, nomes, geoms)} '
              f'({len(geoms)} feições de {len(args.arquivos)} arquivo(s))')
    elif args.cmd == 'gerar':
        sol = b.solicitacao(args.solicitacao_id)
        if sol['status'] not in ('solicitado', 'em_elaboracao'):
            raise SystemExit(f"Solicitação está em '{sol['status']}': não dá para gerar agora")
        inf = b.ultima_infestacao(sol['id']) if sol['tipo'] == 'catacao' else None
        print(f"geração {b.pedir_geracao(sol['id'], inf)['id']} na fila")
    elif args.cmd == 'publicar':
        b.pedir_publicacao(args.geracao_id, args.motivo)
        print('publicação pedida; o agente publica no próximo ciclo')
    elif args.cmd == 'status':
        print(json.dumps(b.solicitacao(args.solicitacao_id), ensure_ascii=False, indent=1, default=str))
        for g in b.selecionar('drone_geracoes', 'id,status,orientacao,alertas,erro,publicacao_erro',
                              {'solicitacao_id': f'eq.{args.solicitacao_id}', 'order': 'id'}):
            print(json.dumps(g, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
