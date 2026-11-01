const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ctx = vm.createContext({ console });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/apresentacao-calculo.js'), 'utf8'), ctx);
const igual = (a, e) => assert.deepStrictEqual(JSON.parse(JSON.stringify(a)), e);
const METAS = { meta_ervas_ha: 20863, meta_fornecedor_ha: 3500, meta_ha_dia: 250, drone_pendente_ha: 2000,
                safra_atual: '26/27', inicio_safra: '2026-04-01' };
const VAZIO = { talhoes: [], colheita_talhoes: [], talhao_plantio: [], talhao_preparo: [], etapas: [], preparo_entregas: [],
                drone: [], voos: { resumo: { realizadoHa: 0, aVoarHa: 0 }, porTipo: [] } };

test('semana pela regra da quinta-feira', () => {
  igual(ctx.apSemana(new Date(2026, 9, 29)), { semana: 'S5M10', corte: '2026-10-28', quinta: '2026-10-29' });
  igual(ctx.apSemana(new Date(2026, 9, 27)), { semana: 'S4M10', corte: '2026-10-21', quinta: '2026-10-22' });
  igual(ctx.apSemana(new Date(2026, 9, 1)), { semana: 'S1M10', corte: '2026-09-30', quinta: '2026-10-01' });
  igual(ctx.apSemana(new Date(2026, 10, 3)), { semana: 'S5M10', corte: '2026-10-28', quinta: '2026-10-29' });
});

test('formato BR', () => {
  assert.strictEqual(ctx.apN(20863), '20.863');
  assert.strictEqual(ctx.apN(1234567.6), '1.234.568');
  assert.strictEqual(ctx.apPct(1, 3), 33);
  assert.strictEqual(ctx.apPct(1, 0), 0);
  assert.strictEqual(ctx.apP1(12.46), '12.5');
});

test('colheita: BIS soma na frente, Sem Linhas não é concluído', () => {
  const A = ctx.apAgregar({ ...VAZIO, colheita_talhoes: [
    { cod_faz: 1, status: 'CONCLUIDO', area_ha: 10, frente: '3', periodo_op: 5 },
    { cod_faz: 1, status: 'SEM LINHAS', area_ha: 4, frente: 'BIS - 3', periodo_op: 5 },
    { cod_faz: 2, status: 'CONCLUIDO', area_ha: 6, frente: 'FOCA 1', periodo_op: 6 },
  ] }, METAS);
  igual(A.colheita.frente['Frente 3'], { CONCLUIDO: 10, 'SEM LINHAS': 4 });
  igual(A.colheita.frente.FOCA, { CONCLUIDO: 6 });
  assert.strictEqual(A.colheita.faz_conc, 1);
  assert.strictEqual(A.colheita.total, 20);
});

test('plantio: status e mês', () => {
  const A = ctx.apAgregar({ ...VAZIO, talhoes: [{ layer: 1001, cod_faz: 1, area_ha: 5 }, { layer: 1002, cod_faz: 1, area_ha: 3 }],
    talhao_plantio: [{ layer: 1001, projeto: 'Ok', mes_plantio: '2026-10-01' }, { layer: 1002, projeto: 'Pendente', mes_plantio: null }] }, METAS);
  igual(A.plantio.status, { Ok: 5, Pendente: 3 });
  igual(Object.keys(A.plantio.mes), ['2026-10', 'Indef']);
});

test('preparo: entregue = Ok; ciclo 25-26 fora; mês pela data de São Paulo', () => {
  const A = ctx.apAgregar({ ...VAZIO,
    talhoes: [{ layer: 1001, cod_faz: 1, area_ha: 5 }, { layer: 1002, cod_faz: 1, area_ha: 3 }, { layer: 1003, cod_faz: 1, area_ha: 2 }],
    etapas: [{ modulo_id: 'preparo', nome: 'Preparo', ordem: 1 }],
    talhao_preparo: [{ layer: 1001, etapa: 'Ok' }, { layer: 1002, etapa: 'Preparo' }, { layer: 1003, etapa: 'Ok' }],
    preparo_entregas: [{ layer: 1001, origem: 'hub', entregue_em: '2026-10-01T02:00:00Z' },
                       { layer: 1003, origem: 'ciclo_25_26', entregue_em: '2025-08-01T12:00:00Z' }] }, METAS);
  igual(A.preparo.etapa.Entregue, [1, 5]);
  assert.strictEqual(A.preparo.fora_25_26, 2);
  igual(A.preparo.mes, { '2026-09': 5 });   // 02:00 UTC de 01/10 = 23:00 de 30/09 em SP
});

test('drone: soma por safra, sem dado listado e fora da soma', () => {
  const A = ctx.apAgregar({ ...VAZIO, drone: [
    { cod_faz: 1, documento: 'normal', revisao_id: 1, area_aplicacao_ha: 10.4, safra: '26/27' },
    { cod_faz: 2, documento: 'catacao', revisao_id: 2, area_aplicacao_ha: 5.3, safra: '26/27' },
    { cod_faz: 3, documento: 'normal', revisao_id: 3, area_aplicacao_ha: 7, safra: null },
    { cod_faz: 4, documento: 'normal', revisao_id: 4, area_aplicacao_ha: null, safra: null },
  ] }, METAS);
  assert.strictEqual(A.drone.por_safra['26/27'], 15);   // arredonda por (documento, safra), como o gerar.py
  assert.strictEqual(A.drone.por_safra['?'], 7);
  igual(A.drone.sem_dado.map((x) => x.revisao_id), [4]);
  assert.strictEqual(A.drone.n_base, 4);
  assert.ok(!Number.isNaN(A.drone.por_safra['26/27']));
});

test('voos: fornecedor fora da programação usa a meta', () => {
  const A = ctx.apAgregar({ ...VAZIO, voos: { resumo: { realizadoHa: 100, aVoarHa: 50 },
    porTipo: [{ tipo: 'Falhas Plantio Forn.', realizadoHa: 1000, aVoarHa: 500 }] } }, METAS);
  const [real, prev, fora] = ctx.apVoosNumeros(A, METAS);
  assert.deepStrictEqual([real, prev, fora], [100, 2050, 2000]);
});
