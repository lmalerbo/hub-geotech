const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ctx = vm.createContext({ console, AbortController, setTimeout, clearTimeout });
for (const f of ['apresentacao-exportar.js', 'apresentacao-dados.js'])
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app', f), 'utf8'), ctx);

test('nome do arquivo', () => {
  assert.strictEqual(ctx.apNomeArquivo('S5M10'), 's5m10 - Apresentacao Geotecnologia - Indicadores e Entregas.pptx');
});

test('lê em páginas de 1000 até acabar', async () => {
  const pedidos = [];
  const cliente = { from: (t) => ({ select: () => ({ order: () => ({ range: async (a, b) => {
    pedidos.push([t, a, b]); return { data: Array(a === 0 ? 1000 : 3).fill({}), error: null }; } }),
    range: async (a, b) => { pedidos.push([t, a, b]); return { data: Array(a === 0 ? 1000 : 3).fill({}), error: null }; } }) }) };
  const linhas = await ctx.apLerTudo(cliente, 'talhoes');
  assert.strictEqual(linhas.length, 1003);
  assert.deepStrictEqual(pedidos, [['talhoes', 0, 999], ['talhoes', 1000, 1999]]);
});

test('preparo_entregas passa por order(layer) antes do range', async () => {
  const ordens = [];
  const cliente = { from: () => ({ select: () => ({
    order: (campo) => { ordens.push(campo); return { range: async () => ({ data: [{}], error: null }) }; },
    range: async () => { throw new Error('sem order'); } }) }) };
  const linhas = await ctx.apLerTudo(cliente, 'preparo_entregas');
  assert.deepStrictEqual(ordens, ['layer']);
  assert.strictEqual(linhas.length, 1);
});

test('erro do Supabase vira exceção com o nome da tabela', async () => {
  const cliente = { from: () => ({ select: () => ({ range: async () => ({ data: null, error: { message: 'permissão negada' } }) }) }) };
  // Erro criado dentro do vm vem de outro realm: compara a mensagem, não instanceof.
  await assert.rejects(ctx.apLerTudo(cliente, 'etapas'), (e) => e.message === 'etapas: permissão negada');
});

test('apMetasDeLinhas converte números e mantém os textos', () => {
  const linhas = [
    { chave: 'meta_ervas_ha', valor: '20863', rotulo: 'x', atualizado_por: null, atualizado_em: null },
    { chave: 'meta_fornecedor_ha', valor: '3500', rotulo: 'x', atualizado_por: null, atualizado_em: null },
    { chave: 'meta_ha_dia', valor: '250', rotulo: 'x', atualizado_por: null, atualizado_em: null },
    { chave: 'drone_pendente_ha', valor: '2000.5', rotulo: 'x', atualizado_por: null, atualizado_em: null },
    { chave: 'safra_atual', valor: '26/27', rotulo: 'x', atualizado_por: null, atualizado_em: null },
    { chave: 'inicio_safra', valor: '2026-04-01', rotulo: 'x', atualizado_por: null, atualizado_em: null },
  ];
  const m = ctx.apMetasDeLinhas(linhas);
  // JSON para tirar o protótipo do vm (outro realm) antes de comparar.
  assert.deepStrictEqual(JSON.parse(JSON.stringify(m)), { meta_ervas_ha: 20863, meta_fornecedor_ha: 3500, meta_ha_dia: 250,
    drone_pendente_ha: 2000.5, safra_atual: '26/27', inicio_safra: '2026-04-01' });
  assert.strictEqual(typeof m.meta_ervas_ha, 'number');
  assert.strictEqual(typeof m.safra_atual, 'string');
});

test('apBuscarVoos monta URL e header e rejeita com a mensagem do worker', async () => {
  const cliente = { auth: { getSession: async () => ({ data: { session: { access_token: 'tok' } } }) } };
  const metas = { inicio_safra: '2026-04-01' };
  let chamada = null;
  const ok = await ctx.apBuscarVoos(cliente, '2026-10-28', metas, 'https://w.test',
    async (url, opts) => { chamada = [url, opts]; return { ok: true, json: async () => ({ x: 1 }) }; });
  assert.deepStrictEqual(ok, { x: 1 });
  assert.strictEqual(chamada[0], 'https://w.test/voos-indicadores?de=2026-04-01&ate=2026-10-28');
  assert.strictEqual(chamada[1].headers.Authorization, 'Bearer tok');

  const falso = async () => ({ ok: false, status: 502, json: async () => ({ erro: 'GeoMap fora do ar' }) });
  await assert.rejects(ctx.apBuscarVoos(cliente, '2026-10-28', metas, 'https://w.test', falso),
    (e) => e.message === 'GeoMap fora do ar');
});
