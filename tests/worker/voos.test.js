const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const fonte = fs.readFileSync(path.join(__dirname, '../../worker/arquivos.js'), 'utf8')
  .replace('export default {', 'module.exports.padrao = {')
  .replace('export async function voosIndicadores', 'module.exports.voosIndicadores = async function voosIndicadores');
const mod = { exports: {} };
vm.runInNewContext(fonte, { module: mod, URL, Response, fetch: () => { throw new Error('sem rede'); }, console });
const { voosIndicadores } = mod.exports;
const ENV = { SUPABASE_URL: 'https://x.supabase.co', SUPABASE_ANON_KEY: 'anon', INDICADORES_TOKEN: 'segredo-123' };
const req = (q, token = 'jwt') => new Request(`https://w/voos-indicadores?${q}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });

function buscarFalso({ pode = true, geomap = { status: 200, corpo: { resumo: { realizadoHa: 10 } } } } = {}) {
  const chamadas = [];
  const f = async (url, op = {}) => {
    chamadas.push({ url: String(url), op });
    if (String(url).includes('/rpc/pode_usar_apresentacao')) return new Response(JSON.stringify(pode), { status: 200 });
    return new Response(JSON.stringify(geomap.corpo), { status: geomap.status });
  };
  f.chamadas = chamadas;
  return f;
}

test('sem token: 401', async () => {
  const r = await voosIndicadores(req('de=2026-04-01&ate=2026-10-28', null), ENV, buscarFalso());
  assert.strictEqual(r.status, 401);
});

test('sem a ferramenta: 403 e não chama o GeoMap', async () => {
  const b = buscarFalso({ pode: false });
  const r = await voosIndicadores(req('de=2026-04-01&ate=2026-10-28'), ENV, b);
  assert.strictEqual(r.status, 403);
  assert.ok(!b.chamadas.some((c) => c.url.includes('geomap')));
});

test('datas inválidas: 400', async () => {
  const r = await voosIndicadores(req('de=ontem&ate=2026-10-28'), ENV, buscarFalso());
  assert.strictEqual(r.status, 400);
});

test('repassa ao GeoMap com o token e não o devolve', async () => {
  const b = buscarFalso();
  const r = await voosIndicadores(req('de=2026-04-01&ate=2026-10-28'), ENV, b);
  const corpo = await r.text();
  assert.strictEqual(r.status, 200);
  assert.deepStrictEqual(JSON.parse(corpo), { resumo: { realizadoHa: 10 } });
  const g = b.chamadas.find((c) => c.url.includes('geomap'));
  assert.strictEqual(g.op.headers['x-indicadores-token'], 'segredo-123');
  assert.ok(g.url.includes('de=2026-04-01') && g.url.includes('ate=2026-10-28'));
  assert.ok(!corpo.includes('segredo-123'));
});

test('GeoMap com erro: 502', async () => {
  const r = await voosIndicadores(req('de=2026-04-01&ate=2026-10-28'), ENV, buscarFalso({ geomap: { status: 500, corpo: {} } }));
  assert.strictEqual(r.status, 502);
});

test('GeoMap fora do ar (exceção de rede): 502', async () => {
  const b = buscarFalso();
  const f = async (url, op) => { if (String(url).includes('geomap')) throw new Error('timeout'); return b(url, op); };
  const r = await voosIndicadores(req('de=2026-04-01&ate=2026-10-28'), ENV, f);
  assert.strictEqual(r.status, 502);
  assert.ok(!(await r.text()).includes('segredo-123'));
});
