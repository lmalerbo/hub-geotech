"""Fluxo de projetos do Plantio e do Preparo (spec 2026-10-23-fluxo-projetos-design.md): avanço por
talhão, volta com justificativa e desfazer, revisão numerada por fazenda com talhões, arquivo vigente
por extensão, linha do tempo e migração do Preparo para etapa por talhão."""

def etapas(banco, modulo, cod):
    col, tab = ('projeto', 'talhao_plantio') if modulo == 'plantio' else ('etapa', 'talhao_preparo')
    return dict(banco.execute(f'select t.talhao_num, p.{col} from hub.{tab} p join hub.talhoes t using (layer) '
                              'where t.cod_faz = %s order by 1', (cod,)).fetchall())


def por(banco, modulo, cod, etapa, talhoes=None):
    """Põe os talhões (todos, ou os dados) direto numa etapa (preparo do cenário, sem registro)."""
    col, tab = ('projeto', 'talhao_plantio') if modulo == 'plantio' else ('etapa', 'talhao_preparo')
    extra = ", mapeamento = 'Sim'" if modulo == 'plantio' and etapa != 'Aguard. Map.' else ''
    banco.execute(f'update hub.{tab} p set {col} = %s{extra} from hub.talhoes t where t.layer = p.layer '
                  'and t.cod_faz = %s and (%s::int[] is null or t.talhao_num = any(%s::int[]))',
                  (etapa, cod, talhoes, talhoes))


def enviar(como, uid, modulo, cod, documento, nomes, nova=False, motivo=None):
    """Imita o Worker: preparar_envio + registrar_arquivo. Devolve o número da revisão."""
    prep = como(uid, 'select revisao_id, numero from hub.preparar_envio(%s, %s, %s, %s, %s)',
                (modulo, cod, documento, nova, motivo))
    assert prep[0] != 'ERRO', prep
    rev, num = prep[0]
    for n in nomes:
        r = como(uid, 'select hub.registrar_arquivo(%s, %s, %s, 10)', (rev, f'{cod}_X_Rev{num}{n}', f'http://x/{n}'))
        assert r is None or r[0] != 'ERRO', r
    return num


def avancar(como, uid, modulo, cod, acao, talhoes=None):
    return como(uid, 'select hub.projeto_avancar(%s, %s, %s, %s)', (modulo, cod, acao, talhoes))


def retroceder(como, uid, modulo, cod, para, just='conferência', talhoes=None):
    return como(uid, 'select hub.projeto_retroceder(%s, %s, %s, %s, %s)', (modulo, cod, para, just, talhoes))


def nova_revisao(como, uid, modulo, cod, motivo, docs, talhoes):
    return como(uid, 'select revisao_id, numero, sufixo from hub.projeto_nova_revisao(%s, %s, %s, %s, %s)',
                (modulo, cod, motivo, docs, talhoes))


# ── Avanço por talhão ─────────────────────────────────────────────────────────

def test_plantio_avanca_so_os_talhoes_marcados(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(5)
    assert avancar(como, uid, 'plantio', cod, 'mapeamento_concluido', [1, 2]) == [(2,)]
    assert avancar(como, uid, 'plantio', cod, 'iniciar') == [(2,)]          # null = todos os elegíveis
    assert etapas(banco, 'plantio', cod) == {1: 'Andamento', 2: 'Andamento', 3: 'Aguard. Map.',
                                             4: 'Aguard. Map.', 5: 'Aguard. Map.'}
    assert banco.execute('select mapeamento from hub.talhao_plantio where layer = %s', (cod * 1000 + 1,)).fetchone() == ('Sim',)


def test_talhao_marcado_fora_da_etapa_e_erro_e_nada_muda(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(3)
    r = avancar(como, uid, 'plantio', cod, 'iniciar', [1])
    assert r[0] == 'ERRO' and 'Talhão(ões) 1' in r[1]
    assert set(etapas(banco, 'plantio', cod).values()) == {'Aguard. Map.'}


def test_avanco_que_exige_arquivo_continua_exigindo(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(2)
    por(banco, 'plantio', cod, 'Andamento')
    r = avancar(como, uid, 'plantio', cod, 'exportacao_enviada')
    assert r[0] == 'ERRO' and 'exportação (.zip)' in r[1]
    enviar(como, uid, 'plantio', cod, 'exportacao', ['.zip'])
    enviar(como, uid, 'plantio', cod, 'projeto', ['.dwg'])
    assert avancar(como, uid, 'plantio', cod, 'exportacao_enviada', [1]) == [(1,)]
    assert etapas(banco, 'plantio', cod) == {1: 'Ag. Mapa', 2: 'Andamento'}


def test_sem_permissao_nao_avanca(como, pessoa, fazenda):
    cod = fazenda(1)
    for uid in (pessoa(papel='leitura'), pessoa(modulos=('preparo',))):
        r = avancar(como, uid, 'plantio', cod, 'mapeamento_concluido')
        assert r[0] == 'ERRO' and 'Sem permissão' in r[1]


def test_funcoes_internas_nao_sao_chamaveis_pela_tela(como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(1)
    r = como(uid, "select hub.projeto_mudar_etapa('plantio', array[%s::bigint], 'Ok', 1, 'x')", (cod * 1000 + 1,))
    assert r[0] == 'ERRO' and 'projeto_mudar_etapa' in r[1]                      # permissão negada


def test_preparo_avanca_por_talhao_com_as_exigencias(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(4)
    assert avancar(como, uid, 'preparo', cod, 'identificacao', [1, 2]) == [(2,)]
    r = avancar(como, uid, 'preparo', cod, 'escoamento')
    assert r[0] == 'ERRO' and 'Escoamento (.pdf)' in r[1]
    enviar(como, uid, 'preparo', cod, 'escoamento', ['-Escoamento.pdf'])
    assert avancar(como, uid, 'preparo', cod, 'escoamento') == [(2,)]
    assert avancar(como, uid, 'preparo', cod, 'observacoes', [1]) == [(1,)]
    r = avancar(como, uid, 'preparo', cod, 'preparo', [1])
    assert r[0] == 'ERRO' and '3 arquivos' in r[1]
    for doc, ext in (('projeto', '.dwg'), ('exportacao', '.zip'), ('sistematizacao', '-Sistematizacao.pdf')):
        enviar(como, uid, 'preparo', cod, doc, [ext])
    assert avancar(como, uid, 'preparo', cod, 'preparo', [1]) == [(1,)]
    assert etapas(banco, 'preparo', cod) == {1: 'Ok', 2: 'Observações', 3: 'Identificação', 4: 'Identificação'}


# ── Volta com justificativa e desfazer ───────────────────────────────────────

def test_volta_exige_justificativa(como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(1)
    r = retroceder(como, uid, 'plantio', cod, 'Pendente', just='  ')
    assert r[0] == 'ERRO' and 'justificativa' in r[1]


def test_volta_e_desfazer_devolvem_cada_talhao_a_etapa_exata(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(4)
    por(banco, 'plantio', cod, 'Ok', [1])
    por(banco, 'plantio', cod, 'Ag. Mapa', [2])
    por(banco, 'plantio', cod, 'Pendente', [3])
    antes = etapas(banco, 'plantio', cod)
    lote = retroceder(como, uid, 'plantio', cod, 'Aguard. Map.', just='mapeamento refeito')[0][0]
    assert set(etapas(banco, 'plantio', cod).values()) == {'Aguard. Map.'}
    assert banco.execute("select count(*) from hub.talhao_plantio p join hub.talhoes t using (layer) "
                         "where t.cod_faz = %s and mapeamento = 'Sim'", (cod,)).fetchone() == (0,)
    assert banco.execute("select distinct justificativa from hub.log_auditoria where lote_id = %s",
                         (lote,)).fetchall() == [('mapeamento refeito',)]
    assert como(uid, 'select hub.projeto_desfazer(%s)', (lote,)) == [(3,)]
    assert etapas(banco, 'plantio', cod) == antes
    assert banco.execute("select count(*) from hub.talhao_plantio p join hub.talhoes t using (layer) "
                         "where t.cod_faz = %s and mapeamento = 'Sim'", (cod,)).fetchone() == (3,)
    r = como(uid, 'select hub.projeto_desfazer(%s)', (lote,))                     # o desfazer também é evento
    assert r[0] == 'ERRO' and 'mudou depois' in r[1]


def test_volta_so_dos_talhoes_marcados(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(3)
    por(banco, 'preparo', cod, 'Ok')
    retroceder(como, uid, 'preparo', cod, 'Escoamento', talhoes=[2])
    assert etapas(banco, 'preparo', cod) == {1: 'Ok', 2: 'Escoamento', 3: 'Ok'}


def test_desfazer_so_vale_enquanto_nada_mais_mudou(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(3)
    por(banco, 'plantio', cod, 'Andamento')
    lote = retroceder(como, uid, 'plantio', cod, 'Pendente', talhoes=[1])[0][0]
    avancar(como, uid, 'plantio', cod, 'iniciar', [1])
    r = como(uid, 'select hub.projeto_desfazer(%s)', (lote,))
    assert r[0] == 'ERRO' and 'mudou depois' in r[1]
    # envio de arquivo também conta
    lote = retroceder(como, uid, 'plantio', cod, 'Pendente', talhoes=[2])[0][0]
    enviar(como, uid, 'plantio', cod, 'exportacao', ['.zip'])
    assert como(uid, 'select hub.projeto_desfazer(%s)', (lote,))[0] == 'ERRO'
    # outra fazenda ou outro módulo não atrapalham
    lote = retroceder(como, uid, 'plantio', cod, 'Pendente', talhoes=[3])[0][0]
    outra = fazenda(1)
    avancar(como, uid, 'plantio', outra, 'mapeamento_concluido')
    avancar(como, uid, 'preparo', cod, 'identificacao')
    assert como(uid, 'select hub.projeto_desfazer(%s)', (lote,)) == [(1,)]


def test_so_volta_pode_ser_desfeita(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(1)
    avancar(como, uid, 'plantio', cod, 'mapeamento_concluido')
    lote = banco.execute("select max(lote_id) from hub.log_auditoria where origem = 'avancar'").fetchone()[0]
    r = como(uid, 'select hub.projeto_desfazer(%s)', (lote,))
    assert r[0] == 'ERRO' and 'Só uma volta' in r[1]


# ── Revisão numerada por fazenda ──────────────────────────────────────────────

def test_plantio_revisao_complementar_novos_e_alterados(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(6)
    # Rev0: talhões 1–3 pelo fluxo normal, com mapa → Ok
    por(banco, 'plantio', cod, 'Andamento', [1, 2, 3])
    enviar(como, uid, 'plantio', cod, 'exportacao', ['.zip'])
    enviar(como, uid, 'plantio', cod, 'projeto', ['.dwg'])
    avancar(como, uid, 'plantio', cod, 'exportacao_enviada')
    enviar(como, uid, 'plantio', cod, 'projeto', ['.pdf'])
    assert etapas(banco, 'plantio', cod) == {1: 'Ok', 2: 'Ok', 3: 'Ok', 4: 'Aguard. Map.', 5: 'Aguard. Map.', 6: 'Aguard. Map.'}
    # Rev1: talhões 4–5 novos e o 1 alterado; o 2 e o 3 continuam Ok
    por(banco, 'plantio', cod, 'Andamento', [4, 5])
    r = nova_revisao(como, uid, 'plantio', cod, '', ['exportacao', 'projeto'], [1, 4, 5])
    assert r[0] == 'ERRO' and 'motivo' in r[1]
    r = nova_revisao(como, uid, 'plantio', cod, 'bloco 2', ['exportacao', 'projeto'], [1, 4, 5])
    assert [(n, s) for _, n, s in r] == [(1, ''), (1, '')]
    assert etapas(banco, 'plantio', cod) == {1: 'Ag. Mapa', 2: 'Ok', 3: 'Ok', 4: 'Ag. Mapa', 5: 'Ag. Mapa', 6: 'Aguard. Map.'}
    assert banco.execute('select t.talhao_num, rt.tipo from hub.revisao_talhoes rt join hub.talhoes t using (layer) '
                         'where rt.revisao_id = %s order by 1', (r[0][0],)).fetchall() == [(1, 'alterado'), (4, 'novo'), (5, 'novo')]
    # o mapa da Rev1 leva só os talhões dela para Ok
    por(banco, 'plantio', cod, 'Ag. Mapa', [6])
    enviar(como, uid, 'plantio', cod, 'projeto', ['.dwg', '.pdf'])
    assert etapas(banco, 'plantio', cod) == {1: 'Ok', 2: 'Ok', 3: 'Ok', 4: 'Ok', 5: 'Ok', 6: 'Ag. Mapa'}


def test_plantio_regras_de_talhao_na_revisao(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(3)
    por(banco, 'plantio', cod, 'Andamento', [1])
    por(banco, 'plantio', cod, 'Ok', [2])
    r = nova_revisao(como, uid, 'plantio', cod, None, ['projeto'], [1])
    assert r[0] == 'ERRO' and 'projeto e a exportação' in r[1]
    r = nova_revisao(como, uid, 'plantio', cod, None, ['exportacao'], [2])
    assert r[0] == 'ERRO' and 'precisa trazer o projeto' in r[1]
    r = nova_revisao(como, uid, 'plantio', cod, None, ['exportacao', 'projeto'], [3])
    assert r[0] == 'ERRO' and 'ainda não tem projeto' in r[1]
    r = nova_revisao(como, uid, 'plantio', cod, None, ['exportacao', 'projeto'], [99])
    assert r[0] == 'ERRO' and 'não existe' in r[1]
    assert banco.execute('select count(*) from hub.projeto_revisoes r join hub.projetos p on p.id = r.projeto_id '
                         'where p.cod_faz = %s', (cod,)).fetchone() == (0,)       # erro não deixa revisão


def test_mapa_anexado_junto_vai_direto_para_ok(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(2)
    por(banco, 'plantio', cod, 'Andamento')
    nova_revisao(como, uid, 'plantio', cod, None, ['exportacao', 'projeto'], [1])
    enviar(como, uid, 'plantio', cod, 'exportacao', ['.zip'])
    enviar(como, uid, 'plantio', cod, 'projeto', ['.dwg', '.pdf'])
    assert etapas(banco, 'plantio', cod) == {1: 'Ok', 2: 'Andamento'}


def test_revisao_so_de_exportacao_nao_muda_etapa(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(2)
    por(banco, 'plantio', cod, 'Ok')
    nova_revisao(como, uid, 'plantio', cod, None, ['exportacao', 'projeto'], [])
    r = nova_revisao(como, uid, 'plantio', cod, 'exportação corrigida', ['exportacao'], None)
    assert [n for _, n, _ in r] == [1]
    assert set(etapas(banco, 'plantio', cod).values()) == {'Ok'}


def test_preparo_exemplo_da_spec_fazenda_voada_em_blocos(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(10)
    todos = ['escoamento', 'projeto', 'exportacao', 'sistematizacao']
    arq = {'escoamento': '-Escoamento.pdf', 'projeto': '.dwg', 'exportacao': '.zip', 'sistematizacao': '-Sistematizacao.pdf'}
    # Rev0 — bloco 1 voado (talhões 1–5 novos, pelo fluxo normal)
    por(banco, 'preparo', cod, 'Escoamento', [1, 2, 3, 4, 5])
    for d in todos:
        enviar(como, uid, 'preparo', cod, d, [arq[d]])
    avancar(como, uid, 'preparo', cod, 'escoamento')
    avancar(como, uid, 'preparo', cod, 'observacoes')
    avancar(como, uid, 'preparo', cod, 'preparo')
    # Rev1 — alteração no projeto: exportação e sistematização são obrigatórias; ninguém muda de etapa
    r = nova_revisao(como, uid, 'preparo', cod, 'alteração no projeto', ['projeto'], [1, 2])
    assert r[0] == 'ERRO' and 'vêm junto' in r[1]
    r = nova_revisao(como, uid, 'preparo', cod, 'alteração no projeto', ['projeto', 'exportacao', 'sistematizacao'], [1, 2])
    assert [n for _, n, _ in r] == [1, 1, 1] and [s for _, _, s in r] == ['', '', '-Sistematizacao']
    assert etapas(banco, 'preparo', cod) == {**{n: 'Ok' for n in range(1, 6)}, **{n: 'Identificação' for n in range(6, 11)}}
    # Rev2 — bloco 2: o escoamento abre a revisão com os talhões 6–10; o projeto depois completa a Rev2
    por(banco, 'preparo', cod, 'Escoamento', [6, 7, 8, 9, 10])
    r = nova_revisao(como, uid, 'preparo', cod, 'bloco 2 voado', ['escoamento'], [6, 7, 8, 9, 10])
    assert [n for _, n, _ in r] == [2]
    assert set(etapas(banco, 'preparo', cod)[n] for n in range(6, 11)) == {'Observações'}
    assert enviar(como, uid, 'preparo', cod, 'escoamento', [arq['escoamento']]) == 2
    avancar(como, uid, 'preparo', cod, 'observacoes', [6, 7, 8, 9, 10])
    for d in ('projeto', 'exportacao', 'sistematizacao'):
        assert enviar(como, uid, 'preparo', cod, d, [arq[d]]) == 2              # revisão aberta
    assert avancar(como, uid, 'preparo', cod, 'preparo') == [(5,)]
    # Rev3 — só exportação corrigida
    r = nova_revisao(como, uid, 'preparo', cod, 'exportação corrigida', ['exportacao'], [])
    assert [n for _, n, _ in r] == [3]
    enviar(como, uid, 'preparo', cod, 'exportacao', [arq['exportacao']])
    vig = dict(banco.execute('select documento, revisao from hub.arquivos_vigentes where cod_faz = %s', (cod,)).fetchall())
    assert vig == {'escoamento': 2, 'projeto': 2, 'exportacao': 3, 'sistematizacao': 2}
    assert set(etapas(banco, 'preparo', cod).values()) == {'Ok'}


def test_preparo_talhao_antes_da_etapa_da_revisao_e_erro(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(1)
    r = nova_revisao(como, uid, 'preparo', cod, None, ['escoamento'], [1])        # ainda em Identificação
    assert r[0] == 'ERRO' and 'conclua as etapas anteriores' in r[1]


def test_numeracao_continua_do_maior_numero_entre_documentos(banco, como, pessoa, fazenda):
    """Fazenda com numeração divergente de antes (ex.: 10095 exportação Rev2 × projeto Rev1): a próxima
    é Rev3, e o histórico antigo não muda."""
    uid, cod = pessoa(), fazenda(1)
    proj = banco.execute("insert into hub.projetos (modulo_id, tipo, cod_faz, nome) values ('plantio', 'individual', %s, 'F') "
                         'returning id', (cod,)).fetchone()[0]
    for doc, n in (('exportacao', 0), ('exportacao', 1), ('exportacao', 2), ('projeto', 0), ('projeto', 1)):
        banco.execute('insert into hub.projeto_revisoes (projeto_id, documento, numero, motivo, vigente) '
                      'values (%s, %s, %s, %s, %s)', (proj, doc, n, 'antigo' if n else None, n == (2 if doc == 'exportacao' else 1)))
    r = nova_revisao(como, uid, 'plantio', cod, 'correção', ['projeto'], [])
    assert [n for _, n, _ in r] == [3]
    assert banco.execute('select documento, numero from hub.projeto_revisoes where projeto_id = %s and vigente '
                         'order by 1', (proj,)).fetchall() == [('exportacao', 2), ('projeto', 3)]
    assert banco.execute('select count(*) from hub.projeto_revisoes where projeto_id = %s and not unificada',
                         (proj,)).fetchone() == (5,)


def test_mapa_em_revisao_antiga_ainda_vale_para_a_fazenda_inteira(banco, como, pessoa, fazenda):
    """Fazenda que já estava em Ag. Mapa antes da mudança: o mapa que chega completa a revisão antiga."""
    uid, cod = pessoa(), fazenda(2)
    proj = banco.execute("insert into hub.projetos (modulo_id, tipo, cod_faz, nome) values ('plantio', 'individual', %s, 'F') "
                         'returning id', (cod,)).fetchone()[0]
    banco.execute("insert into hub.projeto_revisoes (projeto_id, documento, numero, motivo) values "
                  "(%s, 'exportacao', 1, 'antigo'), (%s, 'projeto', 1, 'antigo')", (proj, proj))
    por(banco, 'plantio', cod, 'Ag. Mapa')
    assert enviar(como, uid, 'plantio', cod, 'projeto', ['.pdf']) == 1
    assert set(etapas(banco, 'plantio', cod).values()) == {'Ok'}


# ── Arquivo vigente por extensão e portal ─────────────────────────────────────

def test_documento_mostra_cada_arquivo_da_revisao_mais_recente_que_o_contem(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(1)
    por(banco, 'plantio', cod, 'Ok')
    enviar(como, uid, 'plantio', cod, 'projeto', ['.dwg', '.pdf'])
    enviar(como, uid, 'plantio', cod, 'exportacao', ['.zip'])
    nova_revisao(como, uid, 'plantio', cod, 'ajuste', ['exportacao', 'projeto'], [1])
    enviar(como, uid, 'plantio', cod, 'projeto', ['.dwg'])                      # mapa novo ainda não veio
    vig = sorted(banco.execute('select documento, revisao, nome_arquivo from hub.arquivos_vigentes where cod_faz = %s',
                               (cod,)).fetchall())
    assert [(d, r, n[-4:]) for d, r, n in vig] == [('exportacao', 0, '.zip'), ('projeto', 0, '.pdf'), ('projeto', 1, '.dwg')]
    portal = banco.execute('select documento, revisao, nome_arquivo from public.portal_arquivos() where cod_faz = %s',
                           (cod,)).fetchall()
    assert sorted(portal) == vig
    assert etapas(banco, 'plantio', cod) == {1: 'Ag. Mapa'}


# ── Linha do tempo ───────────────────────────────────────────────────────────

def test_linha_do_tempo_junta_etapas_revisoes_e_desfazer(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(3)
    por(banco, 'plantio', cod, 'Andamento')
    nova_revisao(como, uid, 'plantio', cod, None, ['exportacao', 'projeto'], [1, 2])
    enviar(como, uid, 'plantio', cod, 'projeto', ['.dwg', '.pdf'])
    lote = retroceder(como, uid, 'plantio', cod, 'Andamento', just='erro no projeto')[0][0]
    como(uid, 'select hub.projeto_desfazer(%s)', (lote,))
    linhas = como(uid, 'select tipo, texto, detalhe from hub.projeto_linha_do_tempo(%s, %s)', ('plantio', cod))
    assert [t for t, _, _ in linhas] == ['desfazer', 'retrocesso', 'mapa', 'revisao']
    assert 'erro no projeto' in linhas[1][1] and '2 talhão(ões)' in linhas[1][1]
    rev = linhas[3][2]
    assert rev['numero'] == 0 and rev['talhoes'] == [{'talhao': 1, 'tipo': 'novo'}, {'talhao': 2, 'tipo': 'novo'}]
    assert len(rev['arquivos']) == 2
    assert como(pessoa(papel='leitura'), 'select * from hub.projeto_linha_do_tempo(%s, %s)', ('plantio', cod))[0] == 'ERRO'


# ── RPCs antigas (tela atual) ────────────────────────────────────────────────

def test_rpcs_antigas_passam_pelas_novas(banco, como, pessoa, fazenda):
    uid, cod = pessoa(), fazenda(2)
    assert como(uid, 'select hub.plantio_mapeamento_concluido(%s)', (cod,)) == [(2,)]
    assert como(uid, "select hub.plantio_retroceder(%s, 'Aguard. Map.')", (cod,)) == [(2,)]
    como(uid, 'select hub.preparo_concluir_etapa(%s, 1)', (cod,))
    assert set(etapas(banco, 'preparo', cod).values()) == {'Escoamento'}
    assert como(uid, 'select hub.preparo_reabrir_etapa(%s, 1)', (cod,)) == [(2,)]
    assert set(etapas(banco, 'preparo', cod).values()) == {'Identificação'}


# ── Migração do Preparo para etapa por talhão ────────────────────────────────

def test_migracao_preparo_cada_talhao_herda_a_etapa_da_fazenda(montar_banco):
    def semear(con):
        con.execute("insert into hub.fazendas values (10001, 'A'), (10002, 'B'), (10003, 'C')")
        for cod in (10001, 10002, 10003):
            for n in (1, 2):
                con.execute('insert into hub.talhoes (cod_faz, talhao_num) values (%s, %s)', (cod, n))
                con.execute('insert into hub.talhao_preparo (layer) values (%s)', (cod * 1000 + n,))
        # A: tudo concluído; B: Identificação e Escoamento; C: nada
        con.execute("insert into hub.etapa_status (etapa_id, entidade_id, ok) "
                    "select id, 10001, true from hub.etapas where modulo_id = 'preparo'")
        con.execute("insert into hub.etapa_status (etapa_id, entidade_id, ok) "
                    "select id, 10002, true from hub.etapas where modulo_id = 'preparo' and ordem <= 2")
    con = montar_banco('migracao_preparo', semear)
    try:
        assert dict(con.execute('select layer, etapa from hub.talhao_preparo order by 1').fetchall()) == {
            10001001: 'Ok', 10001002: 'Ok', 10002001: 'Observações', 10002002: 'Observações',
            10003001: 'Identificação', 10003002: 'Identificação'}
        assert con.execute('select count(*) from hub.etapa_status').fetchone() == (6,)   # histórico fica
    finally:
        con.close()
