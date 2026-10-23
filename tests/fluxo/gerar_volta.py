import re, sys
sys.path.insert(0, '.')
from hublocal import *
raiz = Path(sys.argv[1]); FLUXO = '20261023100000_fluxo_projetos.sql'
saida = raiz/'supabase/migrations/volta'/FLUXO.replace('.sql', '_volta.sql')
n = lambda s: re.sub(r'\s+', '', s or '')

def acl(s, a):
    linhas = [f'revoke all on function {s} from public, anon, authenticated, service_role;']
    if not a: return linhas + [f'grant execute on function {s} to public;']
    for item in a.strip('{}').split(','):
        quem, privs = item.split('=')[0], item.split('=')[1].split('/')[0]
        if quem == 'postgres' or 'X' not in privs: continue
        linhas.append(f'grant execute on function {s} to {quem or "public"};')
    return linhas

DADOS = """-- 1) Preparo: a etapa volta a ser da fazenda (hub.etapa_status). A fazenda fica na etapa do talhão
--    mais atrasado (Ok = as quatro concluídas). Observações e datas já gravadas ficam.
create temp table _faz_preparo on commit drop as
select t.cod_faz, min(coalesce(e.ordem, 5)) as ordem
  from hub.talhao_preparo tp
  join hub.talhoes t on t.layer = tp.layer
  left join hub.etapas e on e.modulo_id = 'preparo' and e.nome = tp.etapa
 group by t.cod_faz;

insert into hub.etapa_status (etapa_id, entidade_id, ok, concluido_em)
select e.id, f.cod_faz, true, now()
  from _faz_preparo f join hub.etapas e on e.modulo_id = 'preparo' and e.ordem < f.ordem
on conflict (etapa_id, entidade_id) do update
   set ok = true, concluido_em = coalesce(hub.etapa_status.concluido_em, now())
 where not hub.etapa_status.ok;

update hub.etapa_status s set ok = false
  from _faz_preparo f, hub.etapas e
 where e.id = s.etapa_id and e.modulo_id = 'preparo' and s.entidade_id = f.cod_faz
   and e.ordem >= f.ordem and s.ok;
"""

with banco(raiz) as con:
    for m in migracoes(raiz, ate=FLUXO): aplicar(con, m)
    A, VA = foto(con)
    opc = dict(con.execute("select oid::regclass::text, coalesce(array_to_string(reloptions, ', '), '') from pg_class "
                           "where relkind='v' and relnamespace='hub'::regnamespace").fetchall())
    aplicar(con, raiz/'supabase/migrations'/FLUXO)
    B, VB = foto(con)

    novas = sorted(set(B) - set(A))
    mudadas = sorted(s for s in A if s not in B or n(A[s]['d']) != n(B[s]['d']) or A[s]['acl'] != B[s]['acl'])
    views = sorted(v for v in VA if n(VA[v]) != n(VB.get(v)))
    out = ['-- Volta da migração 20261023100000_fluxo_projetos.sql. Gerado da cadeia de migrações (versões de antes',
           '-- do fluxo, já com 20261023090000_niveis_por_modulo) e conferido num Postgres local: depois desta volta',
           '-- as funções, as permissões e as views ficam iguais às de antes do fluxo.',
           '-- Rodar só para voltar atrás, junto com o revert do merge da fluxo-integracao (app antigo).',
           '-- Ficam no banco, sem uso pelo app antigo: log_auditoria.justificativa/lote_id, talhao_preparo.etapa,',
           '-- projeto_revisoes.unificada, hub.revisao_talhoes e hub.log_lote_seq (guardam o histórico).',
           '-- Para reaplicar o fluxo depois, apagar antes essas estruturas (bloco comentado no fim).',
           '', 'begin;', '', DADOS,
           '-- 2) Views de antes.']
    for v in views:
        w = f' with ({opc[v]})' if opc.get(v) else ''
        out += [f'create or replace view {v}{w} as', VA[v].rstrip().rstrip(';') + ';', '']
    out += ['-- 3) Funções de antes (mesmo corpo e mesmas permissões).']
    for s in mudadas:
        recriada = s not in B or A[s]['r'] != B[s]['r']
        if s in B and recriada:
            out.append(f'drop function {s};')
        out += [A[s]['d'].rstrip().replace('\r', '') + ';']
        out += (acl(s, A[s]['acl']) if recriada or A[s]['acl'] != B[s]['acl'] else []) + ['']
    out += ['-- 4) Funções que o fluxo criou.'] + [f'drop function if exists {s};' for s in novas]
    out += ['', 'commit;', '',
            '-- Antes de reaplicar o fluxo (não rodar junto com a volta):',
            '-- drop table hub.revisao_talhoes; drop sequence hub.log_lote_seq; drop index hub.log_auditoria_lote_idx;',
            '-- alter table hub.log_auditoria drop column justificativa, drop column lote_id;',
            '-- alter table hub.talhao_preparo drop column etapa; alter table hub.projeto_revisoes drop column unificada;', '']
    saida.parent.mkdir(exist_ok=True)
    saida.write_text('\n'.join(out), encoding='utf-8', newline='\n')
    print('novas', len(novas), 'mudadas', len(mudadas), 'views', views)
