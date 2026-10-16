// Aplicação aérea na tela: as contas têm de bater com mapas/corretivo_dados.py (tests/mapas/test_aerea_dados.py).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ctx = vm.createContext({ document: {}, window: {}, console, location: { protocol: 'https:', search: '' } });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/corretivos.js'), 'utf8'), ctx);
const igual = (atual, esperado) => assert.deepStrictEqual(JSON.parse(JSON.stringify(atual)), esperado);

const ap = (id, nome, unidade, dose, talhoes, ordem, os = '9001') => ({ tipo: 'insumo', insumo_id: id, insumo_nome: nome,
  insumo_unidade: unidade, calcario: null, dose, dose_gesso: null, os, ordem, talhoes });
const APLS = [ap(1, 'INSETICIDA REVOLUX', 'L', 0.5, [1, 2], 1), ap(2, 'ADJUVANTE LIQUIDO OCHIMA', 'L', 0.1, [1], 2),
              ap(3, 'REGULADOR SUMITOMO PROGIB', 'KG', 0.008, [2], 3)];
const AREAS = { 1: { area_ha: 60, editada: false }, 2: { area_ha: 40, editada: true } };

test('nome legível, dose com até 3 casas e unidade', () => {
  assert.strictEqual(ctx.crNomeInsumo('INSETICIDA BOUVERIZ WP PR'), 'Inseticida Bouveriz WP PR');
  assert.strictEqual(ctx.crNomeInsumo('INSETICIDA CHLORANTR+LAMB'), 'Inseticida Chlorantr+Lamb');
  assert.strictEqual(ctx.crRotulo(APLS[0]), 'Inseticida Revolux');
  igual([0.5, 0.15, 0.008, 0.035, 10, 1234.5].map(ctx.crBrDose), ['0,50', '0,15', '0,008', '0,035', '10,00', '1.234,50']);
  igual(APLS.map(ctx.crUnidade), ['L', 'L', 'kg']);
  assert.strictEqual(ctx.crUnidade({ tipo: 'fosfato' }), 't');
});

test('margem de 5% (talhão 400) e área total só no aéreo', () => {
  assert.strictEqual(ctx.crMargem(AREAS, 'aerea'), 5);
  assert.strictEqual(ctx.crAreaTotal(AREAS, 'aerea'), 105);
  assert.strictEqual(ctx.crMargem(AREAS, 'subsolagem'), 0);
  assert.strictEqual(ctx.crAreaTotal(AREAS, 'subsolagem'), 100);
});

test('total de cada insumo = dose × área dos talhões dele × 1,05 (igual ao Python)', () => {
  igual(ctx.crTotaisPorProduto(APLS, AREAS, 'aerea'), [
    { titulo: 'Inseticida Revolux', total: 52.5, unidade: 'L', detalhe: null },
    { titulo: 'Adjuvante Liquido Ochima', total: 6.3, unidade: 'L', detalhe: null },
    { titulo: 'Regulador Sumitomo Progib', total: 0.34, unidade: 'kg', detalhe: null },
  ]);
  const duas = [ap(1, 'INSETICIDA REVOLUX', 'L', 0.5, [1], 1), ap(1, 'INSETICIDA REVOLUX', 'L', 0.4, [2], 2, '9002')];
  igual(ctx.crTotaisPorProduto(duas, AREAS, 'aerea'), [{ titulo: 'Inseticida Revolux', total: 48.3, unidade: 'L', detalhe: null }]);
});

test('cores por insumo na ordem de aparição, iguais ao PDF', () => {
  const cores = ctx.crCoresDoMapa(APLS);
  igual(Object.values(cores), [...ctx.CR_PALETA_INSUMOS.slice(0, 3)]);
  igual(ctx.crCoresTalhao(APLS, 2), [ctx.CR_PALETA_INSUMOS[0], ctx.CR_PALETA_INSUMOS[2]]);
  const doze = Array.from({ length: 12 }, (_, i) => ap(i + 1, 'INSUMO ' + i, 'L', 1, [1], i));
  assert.strictEqual(Object.values(ctx.crCoresDoMapa(doze))[10], ctx.CR_PALETA_INSUMOS[0]);
});

test('validação e duplicada consideram o insumo', () => {
  assert.match(ctx.crValidarAplicacao({ tipo: 'insumo', insumo_id: null, dose: 1, os: '1', talhoes: [1] }), /insumo/i);
  assert.strictEqual(ctx.crValidarAplicacao({ tipo: 'insumo', insumo_id: 3, dose: '0,008', os: '1', talhoes: [1] }), null);
  igual(ctx.crDuplicadas(APLS, { ...APLS[0] }, [1, 2]), [1, 2]);
  igual(ctx.crDuplicadas(APLS, { ...APLS[0], insumo_id: 2, insumo_nome: 'ADJUVANTE LIQUIDO OCHIMA' }, [2]), []);
});

test('dados do PDF levam nome e unidade do insumo; arquivo com nome do aéreo', () => {
  const d = ctx.crMontarDados({ codFaz: 10001, nome: 'F', operacao: 'aerea', data: '2026-10-16', geradoPor: 'Leo',
                                geradoEm: '2026-10-16', geo: { features: [] }, areas: AREAS, apls: APLS });
  igual(d.aplicacoes[2], { tipo: 'insumo', calcario: null, dose: 0.008, dose_gesso: null, os: '9001', ordem: 3, talhoes: [2],
                           insumo_nome: 'REGULADOR SUMITOMO PROGIB', insumo_unidade: 'KG' });
  assert.strictEqual(ctx.crNomeArquivo(10001, 'aerea', '2026-10-16'), 'aplicacao_aerea_10001_2026-10-16.pdf');
  assert.strictEqual(ctx.crNomeArquivo(10001, 'arado', '2026-10-16'), 'corretivo_10001_arado_2026-10-16.pdf');
});
