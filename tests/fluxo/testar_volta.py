import re, sys
sys.path.insert(0, '.')
from hublocal import *
raiz = Path(sys.argv[1]); FLUXO = '20261023100000_fluxo_projetos.sql'
volta = raiz/'supabase/migrations/volta'/FLUXO.replace('.sql', '_volta.sql')
n = lambda s: re.sub(r'\s+', '', s or '')
ST = "select entidade_id, e.ordem, ok from hub.etapa_status s join hub.etapas e on e.id = s.etapa_id where e.modulo_id='preparo' order by 1, 2"
falhas = []
def conferir(nome, cond):
    print(('ok    ' if cond else 'FALHA ') + nome); cond or falhas.append(nome)
with banco(raiz) as con:
    for m in migracoes(raiz, ate=FLUXO): aplicar(con, m)
    con.execute("insert into hub.fazendas values (10001, 'A'), (10002, 'B'), (10003, 'C')")
    for cod in (10001, 10002, 10003):
        for t in (1, 2):
            con.execute('insert into hub.talhoes (cod_faz, talhao_num) values (%s, %s)', (cod, t))
            con.execute('insert into hub.talhao_preparo (layer) values (%s)', (cod * 1000 + t,))
    con.execute("insert into hub.etapa_status (etapa_id, entidade_id, ok, observacao) select id, 10001, true, case when ordem=3 then 'obs A' end from hub.etapas where modulo_id = 'preparo'")
    con.execute("insert into hub.etapa_status (etapa_id, entidade_id, ok) select id, 10002, true from hub.etapas where modulo_id = 'preparo' and ordem <= 2")
    A, VA = foto(con); st0 = con.execute(ST).fetchall()
    aplicar(con, raiz/'supabase/migrations'/FLUXO)
    # 1) ida e volta sem uso: etapa_status igual ao de antes
    con.execute('begin'); aplicar(con, volta)
    C, VC = foto(con)
    for k in sorted(set(A)|set(C)):
        if k not in A or k not in C or n(A[k]['d'])!=n(C[k]['d']) or A[k]['acl']!=C[k]['acl']: print('  dif', k, k in A, k in C, A.get(k,{}).get('acl'), C.get(k,{}).get('acl'), n(A.get(k,{}).get('d'))==n(C.get(k,{}).get('d')))
    conferir('funcoes iguais as de antes', {s: (n(v['d']), v['acl']) for s, v in A.items()} == {s: (n(v['d']), v['acl']) for s, v in C.items()})
    conferir('views iguais as de antes', {k: n(v) for k, v in VA.items()} == {k: n(v) for k, v in VC.items()})
    conferir('etapa_status sem uso volta igual', con.execute(ST).fetchall() == st0)
    con.execute('rollback')
    # 2) com uso no modelo novo: C avança os dois talhões até Preparo; A tem um talhão voltado para Escoamento
    con.execute("update hub.talhao_preparo set etapa = 'Preparo' where layer in (10003001, 10003002)")
    con.execute("update hub.talhao_preparo set etapa = 'Escoamento' where layer = 10001002")
    aplicar(con, volta)
    st = con.execute(ST).fetchall()
    conferir('A: so Identificacao ok', [r for r in st if r[0] == 10001] == [(10001, 1, True), (10001, 2, False), (10001, 3, False), (10001, 4, False)])
    conferir('A: observacao preservada', con.execute("select observacao from hub.etapa_status s join hub.etapas e on e.id=s.etapa_id where entidade_id=10001 and e.ordem=3").fetchone() == ('obs A',))
    conferir('B: igual a antes', [r for r in st if r[0] == 10002] == [r for r in st0 if r[0] == 10002])
    conferir('C: 1-3 ok, 4 sem linha', [r for r in st if r[0] == 10003] == [(10003, 1, True), (10003, 2, True), (10003, 3, True)])
    # app antigo: RPC antiga do Preparo funciona depois da volta
    con.execute("insert into auth.users (id) values ('00000000-0000-0000-0000-000000000001')")
    con.execute("insert into hub.usuarios (id, nome, admin) values ('00000000-0000-0000-0000-000000000001', 'Adm', true)")
    con.execute("select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000001', false)")
    con.execute("select hub.preparo_reabrir_etapa(10003, 3)")
    conferir('RPC antiga preparo_reabrir_etapa funciona', con.execute("select ok from hub.etapa_status s join hub.etapas e on e.id=s.etapa_id where entidade_id=10003 and e.ordem=3").fetchone() == (False,))
    # 3) reaplicar o fluxo depois do bloco de limpeza
    limpeza = '\n'.join(l[3:] for l in volta.read_text(encoding='utf-8').splitlines()[-3:])
    con.execute(limpeza); aplicar(con, raiz/'supabase/migrations'/FLUXO)
    conferir('fluxo reaplica depois da limpeza', con.execute("select etapa from hub.talhao_preparo where layer=10003001").fetchone() == ('Observações',))
print('FALHAS:', falhas or 'nenhuma')
