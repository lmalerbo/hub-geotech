// Montagem das fazendas e recarga por fazenda (app/dados.js). Roda com: node --test tests/app/dados_puro.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');

const ctx = {
  console,
  ET: [{ l: 'Aguard. Map.' }, { l: 'Pendente' }, { l: 'Andamento' }, { l: 'Ag. Mapa' }, { l: 'Ok' }],
  mesLabel: (iso) => (iso ? iso.slice(0, 7) : ''),
  fmtDataHora: (d) => 'dt:' + d,
  tagPorte: (t) => (t.cortado ? 1 : null),
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(__dirname + '/../../app/dados.js', 'utf8'), ctx);
const limpo = (x) => JSON.parse(JSON.stringify(x));

const talP = (cod, num, projeto, nome, mes = null) => ({
  layer: cod * 1000 + num, mes_plantio: mes, mapeamento: null, projeto,
  talhoes: { cod_faz: cod, talhao_num: num, area_ha: 10.04, sist_conser: null, fazendas: { nome } },
});

test('a fazenda montada sozinha é igual à mesma fazenda montada junto com as outras', () => {
  const todas = [talP(10095, 2, 'Ok', 'Bela'), talP(10001, 1, 'Ok', 'Alfa'), talP(10095, 1, 'Andamento', 'Bela', '2026-11-01')];
  const juntas = ctx.montarPlantio(todas);
  const sozinha = ctx.montarPlantio(todas.filter((r) => r.layer >= 10095000 && r.layer <= 10095999));
  assert.deepStrictEqual(limpo(sozinha[0]), limpo(juntas.find((f) => f.cod === '10095')));
  assert.deepStrictEqual(limpo(juntas.map((f) => f.n)), ['Alfa', 'Bela']);
  assert.strictEqual(juntas[1].e, 2);                 // etapa do talhão menos avançado
  assert.deepStrictEqual(limpo(juntas[1].tals.map((t) => t.num)), [1, 2]);
  assert.strictEqual(juntas[1].ha, 20.1);
});

const talPrep = (cod, num, etapa, nome = 'Faz') => ({
  layer: cod * 1000 + num, etapa,
  talhoes: { cod_faz: cod, talhao_num: num, area_ha: 10.04, fazendas: { nome } },
});

test('Preparo: cada talhão leva a etapa do banco como índice; a fazenda fica na do menos avançado', () => {
  const todas = [talPrep(10455, 2, 'Ok', 'Beta'), talPrep(10455, 1, 'Escoamento', 'Beta'), talPrep(10001, 1, 'Preparo', 'Alfa')];
  const juntas = ctx.montarPreparo(todas, [], [], {}, []);
  assert.deepStrictEqual(limpo(juntas.map((f) => f.n)), ['Alfa', 'Beta']);
  assert.deepStrictEqual(limpo(juntas[1].tals), [
    { layer: 10455001, num: 1, ha: 10.04, e: 1, cons: null },
    { layer: 10455002, num: 2, ha: 10.04, e: 4, cons: null },
  ]);
  assert.strictEqual(juntas[1].e, 1);                 // o talhão 1 está em Escoamento
  assert.strictEqual(juntas[0].e, 3);                 // Preparo
  assert.strictEqual(juntas[1].ha, 20.1);
});

test('Preparo: fazenda montada sozinha é igual à mesma fazenda montada junto com as outras', () => {
  const todas = [talPrep(10455, 2, 'Ok', 'Beta'), talPrep(10001, 1, 'Preparo', 'Alfa'), talPrep(10455, 1, 'Escoamento', 'Beta')];
  const juntas = ctx.montarPreparo(todas, [], [], {}, []);
  const sozinha = ctx.montarPreparo(todas.filter((r) => r.layer >= 10455000 && r.layer <= 10455999), [], [], {}, []);
  assert.deepStrictEqual(limpo(sozinha[0]), limpo(juntas.find((f) => f.cod === '10455')));
});

test('Preparo: etapa desconhecida ou vazia cai em Identificação (índice 0)', () => {
  const [f] = ctx.montarPreparo([talPrep(10819, 1, undefined)], [], [], {}, []);
  assert.strictEqual(f.tals[0].e, 0);
  assert.strictEqual(f.e, 0);
});

test('Preparo: etapas concluídas por fazenda', () => {
  const linhas = [talPrep(10819, 1, 'Escoamento', 'X')];
  const etapas = [{ id: 1, ordem: 1 }, { id: 2, ordem: 2 }];
  const status = [{ etapa_id: 1, entidade_id: '10819', ok: true, usuario_id: 'u', concluido_em: 'd1', observacao: 'obs' },
                  { etapa_id: 9, entidade_id: '10819', ok: true }];
  const [f] = ctx.montarPreparo(linhas, etapas, status, { u: 'Ana' }, []);
  assert.deepStrictEqual(limpo(f.ok), [true, false]);
  assert.deepStrictEqual(limpo(f.usr), ['Ana', '']);
  assert.strictEqual(f.dt[0], 'dt:d1');
  assert.strictEqual(f.obs, 'obs');
});

// Desde o fluxo de 23/10 a etapa vale por talhão; etapa_status é só histórico (quem, quando, observação).
test('Preparo: talhões todos Ok concluem a fazenda mesmo sem a etapa 4 em etapa_status (10738)', () => {
  const linhas = [talPrep(10738, 1, 'Ok'), talPrep(10738, 2, 'Ok')];
  const etapas = [1, 2, 3, 4].map((i) => ({ id: i, ordem: i }));
  const status = [1, 2, 3].map((i) => ({ etapa_id: i, entidade_id: '10738', ok: true, usuario_id: 'u', concluido_em: 'd' + i }));
  const [f] = ctx.montarPreparo(linhas, etapas, status, { u: 'Ana' }, []);
  assert.deepStrictEqual(limpo(f.ok), [true, true, true, true]);
  assert.deepStrictEqual(limpo(f.usr), ['Ana', 'Ana', 'Ana', '—']);
  assert.strictEqual(f.dt[3], '');
});

test('Preparo: talhão em Identificação reabre a fazenda mesmo com etapa_status todo ok (10080)', () => {
  const linhas = [talPrep(10080, 1, 'Ok'), talPrep(10080, 4, 'Identificação')];
  const etapas = [1, 2, 3, 4].map((i) => ({ id: i, ordem: i }));
  const status = [1, 2, 3, 4].map((i) => ({ etapa_id: i, entidade_id: '10080', ok: true, usuario_id: 'u', concluido_em: 'd' }));
  const [f] = ctx.montarPreparo(linhas, etapas, status, { u: 'Ana' }, []);
  assert.deepStrictEqual(limpo(f.ok), [false, false, false, false]);
  assert.deepStrictEqual(limpo(f.usr), ['', '', '', '']);
});

test('Colheita: frentes mais frequentes primeiro e porte', () => {
  const r = (num, frente, cortado) => ({ layer: 10500000 + num, cod_faz: 10500, talhao_num: num, frente, cortado });
  const [f] = ctx.montarColheita([r(2, 'B', false), r(1, 'A', true), r(3, 'B', false)], { 10500: 'Faz' });
  assert.strictEqual(f.fr, 'B, A');
  assert.strictEqual(f.porte, 1);
  assert.deepStrictEqual(limpo(f.tals.map((t) => t.id)), [1, 2, 3]);
});

test('trocarFazenda: troca no lugar, tira, e insere na ordem do nome', () => {
  const lista = [{ cod: '1', n: 'Alfa' }, { cod: '3', n: 'Gama' }];
  ctx.trocarFazenda(lista, '3', { cod: '3', n: 'Gama', novo: true });
  assert.strictEqual(lista[1].novo, true);
  ctx.trocarFazenda(lista, 2, { cod: '2', n: 'Beta' });
  assert.deepStrictEqual(lista.map((f) => f.cod), ['1', '2', '3']);
  ctx.trocarFazenda(lista, '1', undefined);
  assert.deepStrictEqual(lista.map((f) => f.cod), ['2', '3']);
  ctx.trocarFazenda(lista, '9', undefined);
  assert.strictEqual(lista.length, 2);
});

test('alvoDaAcao: descobre módulo e fazenda; na dúvida devolve null (recarga inteira)', () => {
  assert.deepStrictEqual(limpo(ctx.alvoDaAcao('plantio_retroceder', { p_cod_faz: 10095, p_para: 'Pendente' })), { modulo: 'plantio', cod: '10095' });
  assert.deepStrictEqual(limpo(ctx.alvoDaAcao('preparo_concluir_etapa', { p_cod_faz: '10819', p_ordem: 1 })), { modulo: 'preparo', cod: '10819' });
  assert.deepStrictEqual(limpo(ctx.alvoDaAcao('projeto_avancar', { p_modulo: 'preparo', p_cod_faz: 10819, p_acao: 'escoamento' })), { modulo: 'preparo', cod: '10819' });
  assert.deepStrictEqual(limpo(ctx.alvoDaAcao('colheita_marcar_tipo', { p_layers: [10500001, 10500007], p_tipo: 'VANT' })), { modulo: 'colheita', cod: '10500' });
  assert.strictEqual(ctx.alvoDaAcao('colheita_marcar_tipo', { p_layers: [10500001, 10600001] }), null);
  assert.strictEqual(ctx.alvoDaAcao('projeto_desfazer', { p_lote_id: 7 }), null);
  assert.strictEqual(ctx.alvoDaAcao('salvar_parametro', { p_chave: 'x' }), null);
});

test('montarArquivos: individual vira docs da fazenda; personalizado entra em cada fazenda de origem', () => {
  const rev = (id, projetos, documento, numero, vigente, origens = []) => ({
    id, documento, numero, vigente, motivo: null, criado_em: 'c', projetos, revisao_arquivos: [],
    revisao_origens: origens.map((o) => ({ origem_revisao_id: o })),
  });
  const ind = (cod) => ({ id: cod, modulo_id: 'plantio', tipo: 'individual', cod_faz: cod, nome: '' });
  const per = { id: 99, modulo_id: 'plantio', tipo: 'personalizado', cod_faz: null, nome: 'Bloco' };
  const revisoes = [rev(1, ind(10095), 'projeto', 0, false), rev(2, ind(10095), 'projeto', 1, true),
                    rev(3, ind(10001), 'projeto', 0, true), rev(4, per, 'projeto', 0, true, [2, 3])];
  const arq = ctx.montarArquivos(revisoes);
  assert.deepStrictEqual(limpo(arq['plantio|10095'].docs.projeto.map((r) => r.numero)), [1, 0]);
  assert.strictEqual(arq['plantio|10095'].blocos[0].id, 99);
  assert.strictEqual(arq['plantio|10001'].blocos[0].id, 99);
});

const talPr = (cod, num, etapa, cons = null) => ({
  layer: cod * 1000 + num, etapa, conservacao_em: cons,
  talhoes: { cod_faz: cod, talhao_num: num, area_ha: 5, fazendas: { nome: 'F' + cod } },
});

test('Preparo: "Entregue em" é o mês do último talhão, só com a fazenda toda Ok', () => {
  const linhas = [talPr(1, 1, 'Ok'), talPr(1, 2, 'Ok', '2025-09-01'), talPr(2, 1, 'Ok'), talPr(2, 2, 'Preparo')];
  const ent = [
    { layer: 1001, entregue_em: '2026-08-10T15:00:00+00:00', origem: 'hub' },
    { layer: 1002, entregue_em: '2025-09-01T00:00:00+00:00', origem: 'ciclo_25_26' },
    { layer: 2001, entregue_em: '2026-09-01T15:00:00+00:00', origem: 'hub' },
  ];
  const [f1, f2] = ctx.montarPreparo(linhas, [], [], {}, ent);
  assert.strictEqual(f1.mes, '2026-08');
  assert.strictEqual(f1.ciclo25, true);
  assert.strictEqual(f1.tals[1].cons, '2025-09-01');
  assert.strictEqual(f2.mes, '');
  assert.strictEqual(f2.ciclo25, false);
});

test('Preparo: "Entregue em" usa a data de São Paulo, não a de UTC', () => {
  const ent = [{ layer: 3001, entregue_em: '2026-09-01T01:30:00+00:00', origem: 'hub' }];
  const [f] = ctx.montarPreparo([talPr(3, 1, 'Ok')], [], [], {}, ent);
  assert.strictEqual(f.mes, '2026-08');
});

test('Preparo: Ciclo 25-26 só com todos os talhões do lançamento; mesIso serve para ordenar', () => {
  const linhas = [talPr(1, 1, 'Ok'), talPr(1, 2, 'Ok'), talPr(2, 1, 'Ok'), talPr(2, 2, 'Identificação')];
  const ent = [
    { layer: 1001, entregue_em: '2025-09-01T15:00:00+00:00', origem: 'ciclo_25_26' },
    { layer: 1002, entregue_em: '2025-10-01T15:00:00+00:00', origem: 'ciclo_25_26' },
    { layer: 2001, entregue_em: '2025-09-01T15:00:00+00:00', origem: 'ciclo_25_26' },
  ];
  const [f1, f2] = ctx.montarPreparo(linhas, [], [], {}, ent);
  assert.strictEqual(f1.ciclo25, true);
  assert.strictEqual(f1.ciclo25Todos, true);
  assert.strictEqual(f1.mesIso, '2025-10');
  assert.strictEqual(f2.ciclo25, true);
  assert.strictEqual(f2.ciclo25Todos, false);
  assert.strictEqual(f2.mesIso, '');
});
