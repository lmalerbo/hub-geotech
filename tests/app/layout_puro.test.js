const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ctx = vm.createContext({ document: {}, window: {}, console, location: { protocol: 'https:', search: '' } });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/corretivos.js'), 'utf8'), ctx);
const igual = (atual, esperado) => assert.deepStrictEqual(JSON.parse(JSON.stringify(atual)), esperado);

const DOL = { tipo: 'calcario', calcario: 'dolomitico', dose: 2, dose_gesso: null, os: '4520', ordem: 1, talhoes: [1, 3] };
const FOS = { tipo: 'fosfato', calcario: null, dose: 0.5, dose_gesso: null, os: '4521', ordem: 2, talhoes: [2, 3] };
const BLEND = { tipo: 'blend', calcario: 'dolomitico', dose: 1.5, dose_gesso: 1, os: '4530', ordem: 3, talhoes: [4, 5] };
const INS = { tipo: 'insumo', insumo_nome: 'INSETICIDA REVOLUX', insumo_unidade: 'L', dose: 0.15, os: '9', ordem: 4, talhoes: [1] };
const AREAS = { 1: { area_ha: 23 }, 2: { area_ha: 23 }, 3: { area_ha: 21.4 }, 4: { area_ha: 5.24 }, 5: { area_ha: 4.7 } };

test('lista de talhões para textos', () => {
  assert.strictEqual(ctx.crListaTalhoes([]), '');
  assert.strictEqual(ctx.crListaTalhoes([5]), '5');
  assert.strictEqual(ctx.crListaTalhoes([12, 11]), '11 e 12');
  assert.strictEqual(ctx.crListaTalhoes([14, 11, 12]), '11, 12 e 14');
  const dez = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1];
  assert.strictEqual(ctx.crListaTalhoes(dez), '1, 2, 3, 4, 5, 6 e mais 4');
  assert.strictEqual(ctx.crListaTalhoes(dez, Infinity), '1, 2, 3, 4, 5, 6, 7, 8, 9 e 10');
});

test('talhões sem aplicação', () => {
  igual(ctx.crSemAplicacao([9, 1, 2, 3, 4, 5], [DOL, FOS, BLEND]), [9]);
  igual(ctx.crSemAplicacao([2, 1], []), [1, 2]);
});

test('texto da dose', () => {
  assert.strictEqual(ctx.crTextoDose(DOL), '2,00 t/ha');
  assert.strictEqual(ctx.crTextoDose(BLEND), '1,50 t/ha + gesso 1,00 t/ha');
  assert.strictEqual(ctx.crTextoDose(INS), '0,15 L/ha');
});

test('total previsto da nova aplicação', () => {
  assert.strictEqual(ctx.crPrevisto({ tipo: 'calcario', dose: '2', gesso: '' }, false, [1, 3], AREAS), 88.8);
  assert.strictEqual(ctx.crPrevisto({ tipo: 'blend', dose: '1.5', gesso: '1' }, false, [4, 5], AREAS), 24.85);
  assert.strictEqual(ctx.crPrevisto({ insumo_id: '1', dose: '2' }, true, [1, 2], AREAS), 96.6);   // com 5% de margem
  assert.strictEqual(ctx.crPrevisto({ tipo: 'calcario', dose: '', gesso: '' }, false, [1], AREAS), null);
  assert.strictEqual(ctx.crPrevisto({ tipo: 'calcario', dose: '0', gesso: '' }, false, [1], AREAS), null);
  assert.strictEqual(ctx.crPrevisto({ tipo: 'blend', dose: '1.5', gesso: '' }, false, [4], AREAS), null);
  assert.strictEqual(ctx.crPrevisto({ tipo: 'calcario', dose: '2', gesso: '' }, false, [], AREAS), null);
});

test('dica do talhão', () => {
  igual(ctx.crDicaTalhao(3, 21.4, [FOS, DOL], false), {
    titulo: 'Talhão 3, 21,40 ha',
    linhas: ['Calc. Dolomítico 2,00 t/ha, O.S. 4520', 'Fosfato 0,50 t/ha, O.S. 4521'],
    acao: 'Clique para marcar',
  });
  igual(ctx.crDicaTalhao(9, 10, [DOL], true), { titulo: 'Talhão 9, 10,00 ha', linhas: ['Sem aplicação'], acao: 'Clique para desmarcar' });
});

test('abertos por último', () => {
  igual(ctx.crLerRecentes(null), []);
  igual(ctx.crLerRecentes('lixo'), []);
  igual(ctx.crLerRecentes('{"a":1}'), []);
  igual(ctx.crLerRecentes('[{"id":5,"cod_faz":10974},{"x":1},null]'), [{ id: 5, cod_faz: 10974 }]);
  igual(ctx.crRecentesCom([{ id: 1 }, { id: 2 }, { id: 3 }], { id: 2 }), [{ id: 2 }, { id: 1 }, { id: 3 }]);
  igual(ctx.crRecentesCom([{ id: 1 }, { id: 2 }, { id: 3 }], { id: 4 }), [{ id: 4 }, { id: 1 }, { id: 2 }]);
  igual(ctx.crRecentesSem([{ id: 1 }, { id: 2 }], '2'), [{ id: 1 }]);
});