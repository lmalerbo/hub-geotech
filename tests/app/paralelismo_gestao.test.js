// Pendentes, Rodadas e Frotas: funções puras. Roda com: node --test tests/app/paralelismo_gestao.test.js
// Só dados sintéticos (frotas 9xxxx, fazendas fictícias).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');

const ctx = { console, setTimeout, clearTimeout, URL };
vm.createContext(ctx);
for (const f of ['paralelismo-puro.js', 'paralelismo-previa.js', 'paralelismo-gestao.js']) vm.runInContext(fs.readFileSync(`${__dirname}/../../app/${f}`, 'utf8'), ctx);
const puro = (v) => JSON.parse(JSON.stringify(v));
const igual = (a, b) => assert.deepStrictEqual(puro(a), b);

const BOM = 'https://github.com/lmalerbo/hub-geotech-arquivos/releases/download/paralelismo-r7/p7-01.zip';

test('parUrlSegura aceita só https do github.com', () => {
  assert.strictEqual(ctx.parUrlSegura(BOM), BOM);
});
test('parUrlSegura recusa esquema perigoso, http, host de terceiro, credenciais e lixo', () => {
  for (const ruim of ['javascript:alert(1)', 'data:text/html,<script>', 'http://github.com/x', 'https://evil.example/x', 'https://github.com.evil.example/x',
    'https://u:p@github.com/x', 'https://github.com/a b', 'https://github.com/x"onmouseover="y', '', null, undefined, 42, 'github.com/x']) {
    assert.strictEqual(ctx.parUrlSegura(ruim), null, String(ruim));
  }
});

test('parRecalculoNecessario lê a lista do erro do banco', () => {
  igual(ctx.parRecalculoNecessario(new Error('recalculo_necessario:cana/10001,torta/10002')), [{ operacao: 'cana', cod_faz: 10001 }, { operacao: 'torta', cod_faz: 10002 }]);
  assert.strictEqual(ctx.parRecalculoNecessario(new Error('rodada_nao_pendente:3')), null);
  assert.strictEqual(ctx.parRecalculoNecessario(null), null);
});

const talhao = (n, amostras, aderentes) => ({ talhao_num: n, amostras, aderentes, acima: amostras - aderentes, abaixo: 0, media_m: 3.02, frotas: ['90001'] });
const analiseDb = (extra = {}) => ({
  id: 5, operacao: 'cana', cod_faz: 10001, mes: '2026-10-01', amostras: 90, aderentes: 63, acima: 20, abaixo: 7, fora_talhao: 10, pll_total: 100, pll_aderentes: 70,
  vigente: false, base_analise_id: 1, amostras_url: BOM, paralelismo_talhoes: [talhao(1, 60, 45), talhao(2, 30, 18)], ...extra,
});

test('parPreviaDoBanco monta o mesmo formato de parPrevia, com delta contra a vigente', () => {
  const p = ctx.parPreviaDoBanco([analiseDb()], { 'cana|10001': { amostras: 300, aderentes: 195 } });
  assert.strictEqual(p.fazendas.length, 1);
  const f = p.fazendas[0];
  assert.strictEqual(f.pctTxt, '70,00%');
  assert.strictEqual(f.vigentePctTxt, '65,00%');
  assert.strictEqual(f.deltaTxt, '+5,00 p.p.');
  assert.strictEqual(f.foraTalhao, 10);
  assert.strictEqual(f.talhoes[0].pctTxt, '75,00%');
  assert.strictEqual(p.total.pctTxt, '70,00%');
  assert.strictEqual(f.amostrasUrl, BOM);
});
test('parPreviaDoBanco: fazenda nova, fora de talhão alto e amostra insuficiente viram avisos; link ruim some', () => {
  const p = ctx.parPreviaDoBanco([analiseDb({ cod_faz: 10002, amostras_url: 'javascript:alert(1)', fora_talhao: 30, amostras: 70, aderentes: 49, acima: 14, abaixo: 7, pll_total: 100,
    paralelismo_talhoes: [talhao(1, 60, 45), talhao(2, 10, 4)] })], {});
  const f = p.fazendas[0];
  assert.strictEqual(f.vigentePctTxt, null);
  assert.strictEqual(f.deltaTxt, null);
  assert.strictEqual(f.amostrasUrl, null);
  igual(f.avisos.map((a) => a.codigo).sort(), ['fora_talhao_alto', 'insuficiente']);
});

test('parRodadaDoBanco normaliza, troca ids por nomes e descarta link inseguro', () => {
  const r = ctx.parRodadaDoBanco({
    id: 7, descricao: 'Pen-drive A', release_tag: 'paralelismo-r7', status: 'pendente', criado_por: 'u1', criado_em: '2026-11-04T12:00:00Z', validado_por: null, validado_em: null, motivo_recusa: null,
    partes: [{ nome: 'p7-01.zip', url: BOM, bytes: 1048576 }, { nome: 'p7-02.zip', url: 'javascript:alert(1)', bytes: 10 }],
    paralelismo_analises: [analiseDb({ paralelismo_talhoes: [talhao(1, 60, 45), { ...talhao(2, 30, 18), frotas: ['90001', '90002'] }] })],
  }, { u1: 'Ana' }, { 'cana|10001': { amostras: 300, aderentes: 195 } });
  assert.strictEqual(r.criadoPor, 'Ana');
  assert.strictEqual(r.validadoPor, '—');
  igual(r.frotas, ['90001', '90002']);
  assert.strictEqual(r.partes[0].url, BOM);
  assert.strictEqual(r.partes[1].url, null);
  assert.strictEqual(r.partes[1].urlInvalida, true);
  igual(r.fazendas.map((f) => [f.operacao, f.cod_faz]), [['cana', 10001]]);
  assert.strictEqual(r.previa.total.pctTxt, '70,00%');
});

test('parMontarRecalculo devolve o formato de p_recalculo, sem link do shapefile antigo', () => {
  const res = { operacao: 'cana', cod_faz: 10001, analise: { mes: '2026-10-01', amostras: 90, aderentes: 63, acima: 20, abaixo: 7, fora_talhao: 10, pll_total: 100, pll_aderentes: 70,
    talhoes: [{ ...talhao(1, 60, 45), insuficiente: false }], frotas: [] } };
  const r = ctx.parMontarRecalculo([res], { 'cana|10001': 42 });
  igual(r, [{ operacao: 'cana', cod_faz: 10001, base_analise_id: 42, mes: '2026-10-01', amostras: 90, aderentes: 63, acima: 20, abaixo: 7, fora_talhao: 10, pll_total: 100, pll_aderentes: 70,
    amostras_url: null, talhoes: [{ talhao_num: 1, amostras: 60, aderentes: 45, acima: 15, abaixo: 0, media_m: 3.02, frotas: ['90001'] }] }]);
  assert.strictEqual(ctx.parMontarRecalculo([res], {})[0].base_analise_id, null);
});

function deps(extra = {}) {
  const chamadas = [];
  const d = {
    chamadas,
    publicar: async (id, rec) => { chamadas.push(['publicar', id, rec]); return { rodada_id: id }; },
    buscarBase: async (op, cod, rid) => { chamadas.push(['base', op, cod, rid]); return { analise_id: 42, linhas: [{ frota: '90001', data: '2026-10-01', coords: [[0, 0], [1, 1]] }], talhoes: { features: [] } }; },
    recalcular: async (entrada) => { chamadas.push(['recalcular', entrada.map((e) => e.cod_faz)]); return entrada.map((e) => ({ operacao: e.operacao, cod_faz: e.cod_faz, analise: { amostras: 1, aderentes: 1, acima: 0, abaixo: 0, fora_talhao: 0, pll_total: 1, pll_aderentes: 1, mes: null, talhoes: [], frotas: [] } })); },
    confirmar: async () => true,
    ...extra,
  };
  return d;
}
const erroRecalc = (lista) => new Error(`recalculo_necessario:${lista}`);

test('publicar direto, sem recálculo, quando a vigente não mudou', async () => {
  const d = deps();
  const r = await ctx.parPublicarComRecalculo(7, d);
  assert.deepStrictEqual(puro(r), { publicada: true, recalculou: false });
  igual(d.chamadas, [['publicar', 7, null]]);
});
test('recálculo: busca a base com a rodada, recalcula só as fazendas listadas e confirma com p_recalculo', async () => {
  let n = 0;
  const d = deps({ publicar: async (id, rec) => { d.chamadas.push(['publicar', id, rec]); if (!n++) throw erroRecalc('cana/10001'); return {}; } });
  const r = await ctx.parPublicarComRecalculo(7, d);
  assert.deepStrictEqual(puro(r), { publicada: true, recalculou: true });
  assert.deepStrictEqual(puro(d.chamadas.slice(1, 3)), [['base', 'cana', 10001, 7], ['recalcular', [10001]]]);
  const rec = d.chamadas[3][2];
  assert.strictEqual(rec[0].base_analise_id, 42);
  assert.strictEqual(rec[0].cod_faz, 10001);
});
test('recálculo cancelado não publica de novo', async () => {
  const d = deps({ publicar: async (id, rec) => { d.chamadas.push(['publicar', id, rec]); throw erroRecalc('cana/10001'); }, confirmar: async () => false });
  const r = await ctx.parPublicarComRecalculo(7, d);
  assert.deepStrictEqual(puro(r), { cancelado: true });
  assert.strictEqual(d.chamadas.filter((c) => c[0] === 'publicar').length, 1);
});
test('corrida: a vigente muda de novo durante o recálculo; repete até 2 vezes e depois desiste', async () => {
  const d = deps({ publicar: async (id, rec) => { d.chamadas.push(['publicar', id, rec]); throw erroRecalc('cana/10001'); } });
  await assert.rejects(ctx.parPublicarComRecalculo(7, d), /recalculo_necessario/);
  assert.strictEqual(d.chamadas.filter((c) => c[0] === 'recalcular').length, 2);
});
test('erro que não é de recálculo sobe sem recalcular; falha do recálculo não publica', async () => {
  const d = deps({ publicar: async () => { throw new Error('rodada_nao_pendente:7'); } });
  await assert.rejects(ctx.parPublicarComRecalculo(7, d), /rodada_nao_pendente/);
  assert.strictEqual(d.chamadas.length, 0);
  let n = 0;
  const e = deps({ publicar: async (id, rec) => { e.chamadas.push(['publicar', id, rec]); throw erroRecalc('cana/10001'); }, recalcular: async () => { n++; throw new Error('Pyodide caiu'); } });
  await assert.rejects(ctx.parPublicarComRecalculo(7, e), /Pyodide caiu/);
  assert.strictEqual(n, 1);
  assert.strictEqual(e.chamadas.filter((c) => c[0] === 'publicar').length, 1);
});

test('parTextoErroGestao traduz os erros do banco', () => {
  const t = (m) => ctx.parTextoErroGestao(new Error(m));
  assert.match(t('exclua_antes_rodada_mais_nova:10001,10002'), /Exclua antes.*10001, 10002/);
  assert.match(t('rodada_pendente_depende:9'), /pendente.*9/);
  assert.match(t('rodada_nao_pendente:7'), /já foi decidida/);
  assert.match(t('rodada_nao_publicada:7'), /publicada/);
  assert.match(t('Só o editor publica rodadas do Paralelismo'), /nível/);
  assert.match(t('JWT expired'), /sessão expirou/);
  assert.match(t('Failed to fetch'), /Sem conexão/);
  assert.match(t('algo estranho'), /Não foi possível/);
});

test('parValidarFrota exige série e frota, operação e tipo válidos', () => {
  const ok = ctx.parValidarFrota({ serie: ' BM0000X000009 ', frota: ' 90009 ', operacao: 'torta', tipo: 'prestador', nomes_antigos: '', observacao: ' x ' });
  assert.strictEqual(ok.erro, null);
  igual(ok.valor, { serie: 'BM0000X000009', frota: '90009', operacao: 'torta', tipo: 'prestador', nomes_antigos: null, observacao: 'x' });
  assert.match(ctx.parValidarFrota({ serie: '', frota: '1', operacao: 'cana', tipo: 'propria' }).erro, /série/i);
  assert.match(ctx.parValidarFrota({ serie: 'S', frota: ' ', operacao: 'cana', tipo: 'propria' }).erro, /frota/i);
  assert.match(ctx.parValidarFrota({ serie: 'S', frota: '1', operacao: 'milho', tipo: 'propria' }).erro, /operação/i);
  assert.match(ctx.parValidarFrota({ serie: 'S', frota: '1', operacao: 'cana', tipo: 'outro' }).erro, /tipo/i);
});
