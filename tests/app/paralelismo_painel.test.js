// Agregações do Painel do Paralelismo. Roda com: node --test tests/app/paralelismo_painel.test.js
// Só dados sintéticos.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');

const ctx = { console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(__dirname + '/../../app/paralelismo-puro.js', 'utf8'), ctx);
const puro = (v) => JSON.parse(JSON.stringify(v));
const igual = (a, b) => assert.deepStrictEqual(puro(a), b);

const tal = (n, amostras, aderentes) => ({ talhao_num: n, amostras, aderentes, acima: amostras - aderentes, abaixo: 0, media_m: 3, frotas: ['90001'] });
const an = (cod, mes, talhoes, fora = 0, fazenda = `Faz ${cod}`) => {
  const soma = (k) => talhoes.reduce((s, t) => s + t[k], 0);
  return { operacao: 'cana', cod_faz: cod, fazenda, mes, amostras: soma('amostras'), aderentes: soma('aderentes'), acima: soma('acima'), abaixo: 0, fora_talhao: fora, paralelismo_talhoes: talhoes };
};
const BASE = { '10001|1': { area_ha: 10, declividade: 4 }, '10001|2': { area_ha: 30, declividade: 10 }, '10001|3': { area_ha: 5, declividade: null }, '10002|1': { area_ha: 20, declividade: 7 } };
const A = [
  an(10001, '2026-09-01', [tal(1, 100, 90), tal(2, 100, 50), tal(3, 24, 24)], 50),
  an(10002, '2026-10-01', [tal(1, 50, 40)]),
];

test('situação nas bordas', () => {
  assert.strictEqual(ctx.parSituacao(85), 'bom');
  assert.strictEqual(ctx.parSituacao(84.99), 'atencao');
  assert.strictEqual(ctx.parSituacao(70), 'atencao');
  assert.strictEqual(ctx.parSituacao(69.9), 'critico');
  assert.strictEqual(ctx.parSituacao(null), null);
});

test('faixas de declividade nas bordas e nulo', () => {
  assert.strictEqual(ctx.parFaixaDeclividade(0), 0);
  assert.strictEqual(ctx.parFaixaDeclividade(5.99), 0);
  assert.strictEqual(ctx.parFaixaDeclividade(6), 1);
  assert.strictEqual(ctx.parFaixaDeclividade(9), 2);
  assert.strictEqual(ctx.parFaixaDeclividade(12), 3);
  assert.strictEqual(ctx.parFaixaDeclividade(null), null);
  igual(vm.runInContext('PAR_FAIXAS', ctx), ['até 6%', '6 a 9%', '9 a 12%', 'acima de 12%']);
});

test('talhões planos: pct, insuficiente e atributos da base; sem base não quebra', () => {
  const p = puro(ctx.parTalhoesPlanos(A, BASE));
  assert.strictEqual(p.length, 4);
  const t3 = p.find((x) => x.cod_faz === 10001 && x.talhao === 3);
  assert.strictEqual(t3.insuficiente, true);
  assert.strictEqual(t3.dec, null);
  assert.strictEqual(t3.area, 5);
  assert.strictEqual(p.find((x) => x.talhao === 2).pct, 50);
  const sem = puro(ctx.parTalhoesPlanos(A, {}));
  assert.strictEqual(sem[0].dec, null);
  assert.strictEqual(sem[0].area, null);
});

test('resumo: fora_talhao não entra; lista vazia não dá NaN', () => {
  const r = puro(ctx.parResumo(A, BASE));
  assert.strictEqual(r.amostras, 274);
  assert.strictEqual(r.aderentes, 204);
  assert.strictEqual(r.fazendas, 2);
  assert.strictEqual(r.talhoes, 4);
  assert.strictEqual(r.talhoesValidos, 3);
  assert.strictEqual(r.area, 65);
  assert.ok(Math.abs(r.pct - 204 / 274 * 100) < 1e-9);
  const v = puro(ctx.parResumo([], {}));
  assert.strictEqual(v.pct, null);
  assert.strictEqual(v.situacao, null);
  assert.strictEqual(v.fazendas, 0);
});

test('por faixa: insuficiente e sem declividade ficam fora; faixas vazias mantidas', () => {
  const f = puro(ctx.parPorFaixa(ctx.parTalhoesPlanos(A, BASE)));
  assert.strictEqual(f.length, 4);
  assert.deepStrictEqual(f.map((x) => x.n), [1, 1, 1, 0]);   // 4% | 7% | 10% | —
  assert.strictEqual(f[0].pct, 90);
  assert.strictEqual(f[3].pct, null);
  assert.strictEqual(f[0].rotulo, 'até 6%');
});

test('por mês: ordenado e com pct', () => {
  const m = puro(ctx.parPorMes([A[1], A[0], an(10003, '2026-09-01', [tal(1, 100, 100)])]));
  assert.deepStrictEqual(m.map((x) => x.mes), ['2026-09-01', '2026-10-01']);
  assert.strictEqual(m[0].amostras, 324);
  assert.strictEqual(m[1].pct, 80);
  igual(ctx.parPorMes([]), []);
});

test('tabela de fazendas: declividade ponderada pela área, ordem por pior, todos insuficientes = pct nulo', () => {
  const t = puro(ctx.parTabelaFazendas([...A, an(10009, '2026-10-01', [tal(1, 10, 10)])], BASE));
  assert.deepStrictEqual(t.map((x) => x.cod_faz), [10001, 10002, 10009]);   // 10009 sem pct vai ao fim
  assert.strictEqual(t[0].talhoes, 3);
  assert.strictEqual(t[0].area, 45);
  assert.ok(Math.abs(t[0].decMedia - (4 * 10 + 10 * 30) / 40) < 1e-9);   // o talhão sem declividade não pesa
  assert.strictEqual(t[0].situacao, 'atencao');
  assert.strictEqual(t[2].pct, null);
  assert.strictEqual(t[2].decMedia, null);
});

test('busca sem acento e caixa em fazenda, código e talhão', () => {
  const planos = ctx.parTalhoesPlanos([an(10001, '2026-09-01', [tal(1, 30, 30), tal(12, 30, 30)], 0, 'Santa São José')], {});
  assert.strictEqual(ctx.parFiltrarTalhoes(planos, 'sao jose').length, 2);
  assert.strictEqual(ctx.parFiltrarTalhoes(planos, '10001').length, 2);
  assert.strictEqual(ctx.parFiltrarTalhoes(planos, '12').length, 1);
  assert.strictEqual(ctx.parFiltrarTalhoes(planos, '').length, 2);
  assert.strictEqual(ctx.parFiltrarTalhoes(planos, 'zzz').length, 0);
});
