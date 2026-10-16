const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ctx = vm.createContext({ document: {}, window: {}, console, location: { protocol: 'https:', search: '' } });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app/corretivos.js'), 'utf8'), ctx);
// Valores criados dentro do contexto vm têm outros protótipos: compara pelo conteúdo.
const igual = (atual, esperado) => assert.deepStrictEqual(JSON.parse(JSON.stringify(atual)), esperado);

const DOL = { tipo: 'calcario', calcario: 'dolomitico', dose: 2, dose_gesso: null, os: '4520', ordem: 1, talhoes: [1, 3] };
const FOS = { tipo: 'fosfato', calcario: null, dose: 0.5, dose_gesso: null, os: '4521', ordem: 2, talhoes: [2, 3] };
const BLEND = { tipo: 'blend', calcario: 'dolomitico', dose: 1.5, dose_gesso: 1, os: '4530', ordem: 3, talhoes: [4, 5] };
const AREAS = { 1: { area_ha: 23, editada: false }, 2: { area_ha: 23, editada: false }, 3: { area_ha: 21.4, editada: false },
                4: { area_ha: 5.24, editada: true }, 5: { area_ha: 4.7, editada: false } };

test('formato e total', () => {
  assert.strictEqual(ctx.crBr(1234.5), '1.234,50');
  assert.strictEqual(ctx.crTotal(5.24, 1.5), 7.86);
});

test('rótulos e cores', () => {
  assert.strictEqual(ctx.crRotulo(BLEND), 'Blend · Dolomítico');
  assert.strictEqual(ctx.CR_CORES[ctx.crChaveCor({ ...DOL, calcario: 'ph7' })], '#22a39f');
  igual(ctx.crCoresTalhao([FOS, DOL], 3), ['#2f6db5', '#e07b1a']);
  igual(ctx.crCoresTalhao([DOL], 9), []);
});

test('totais por produto iguais ao Python', () => {
  igual(ctx.crTotaisPorProduto([DOL, FOS, BLEND], AREAS), [
    { titulo: 'Calcário Dolomítico', total: 88.8, unidade: 't', detalhe: null },
    { titulo: 'Fosfato', total: 22.2, unidade: 't', detalhe: null },
    { titulo: 'Blend Dolomítico', total: 24.85, unidade: 't', detalhe: 'calc. 14,91 t + gesso 9,94 t' },
  ]);
});

test('validação do formulário', () => {
  const ok = { tipo: 'blend', calcario: 'ph7', dose: '1,5', dose_gesso: '1', os: '4530', talhoes: [1] };
  assert.strictEqual(ctx.crValidarAplicacao(ok), null);
  assert.match(ctx.crValidarAplicacao({ ...ok, talhoes: [] }), /Marque ao menos um talhão/);
  assert.match(ctx.crValidarAplicacao({ ...ok, dose: '0' }), /Dose/);
  assert.match(ctx.crValidarAplicacao({ ...ok, dose_gesso: '' }), /gesso/);
  assert.match(ctx.crValidarAplicacao({ ...ok, os: '  ' }), /O\.S\./);
  assert.match(ctx.crValidarAplicacao({ ...ok, tipo: 'calcario', calcario: null }), /calcário/);
});

test('duplicadas', () => {
  igual(ctx.crDuplicadas([DOL], { ...DOL, ordem: 9 }, [1, 2, 3]), [1, 3]);
  igual(ctx.crDuplicadas([DOL], { ...DOL, os: '9999' }, [1]), []);
});

test('talhões fora da base', () => {
  const geo = { type: 'FeatureCollection', features: [{ properties: { talhao: 1 } }, { properties: { talhao: 2 } }] };
  igual(ctx.crTalhoesForaDaBase({ 1: {}, 7: {} }, geo), [7]);
});

test('JSON para o gerador e nome do arquivo', () => {
  const d = ctx.crMontarDados({ codFaz: 10156, nome: 'F', operacao: 'arado', data: '2026-10-15', geradoPor: 'Ana',
                                geo: { type: 'FeatureCollection', features: [] }, areas: AREAS, apls: [DOL] });
  igual(Object.keys(d).sort(), ['aplicacoes', 'areas', 'cod_faz', 'data', 'gerado_em', 'gerado_por', 'nome', 'operacao', 'talhoes_geo']);
  assert.match(d.gerado_em, /^\d{4}-\d{2}-\d{2}$/);       // data de hoje (rodapé "Gerado em"), não a data do mapa
  assert.strictEqual(ctx.crMontarDados({ codFaz: 1, nome: 'F', operacao: 'arado', data: '2026-10-15', geradoPor: 'A',
                                         geradoEm: '2026-11-03', geo: { type: 'FeatureCollection', features: [] },
                                         areas: AREAS, apls: [DOL] }).gerado_em, '2026-11-03');
  assert.strictEqual(d.areas['4'].editada, true);
  assert.strictEqual(ctx.crNomeArquivo(10156, 'arado', '2026-10-15'), 'corretivo_10156_arado_2026-10-15.pdf');
});

test('faixas cobrem o talhão', () => {
  const areaAnel = a => { let s = 0; for (let i = 0; i < a.length - 1; i++) s += a[i][0] * a[i + 1][1] - a[i + 1][0] * a[i][1]; return Math.abs(s) / 2; };
  const areaPol = p => areaAnel(p[0]) - p.slice(1).reduce((s, h) => s + areaAnel(h), 0);
  const area = g => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates).reduce((s, p) => s + areaPol(p), 0);
  const L = { type: 'Polygon', coordinates: [[[0, 0], [4, 0], [4, 1], [1, 1], [1, 4], [0, 4], [0, 0]]] };
  const MP = { type: 'MultiPolygon', coordinates: [
    [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]], [[2, 2], [4, 2], [4, 4], [2, 4], [2, 2]]],
    [[[20, 0], [25, 0], [25, 5], [20, 5], [20, 0]]],
  ] };
  for (const g of [L, MP]) for (const n of [2, 3]) {
    const faixas = ctx.crFaixas(g, n);
    assert.strictEqual(faixas.length, n);
    const total = area(g);
    const soma = faixas.reduce((s, f) => s + area(f), 0);
    assert.ok(Math.abs(soma - total) <= 1e-9 * total, `soma ${soma} != ${total}`);
    for (const f of faixas) assert.ok(area(f) > 0);
  }
});
