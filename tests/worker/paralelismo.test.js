// Rotas do Paralelismo no Worker. Roda com: node --test tests/worker/paralelismo.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const MB = 1048576;
const ENV = { SUPABASE_URL: 'https://x.supabase.co', SUPABASE_ANON_KEY: 'anon', GH_REPO: 'dono/arquivos', GH_TOKEN: 'gh', ORIGENS: 'https://hub' };

// Carrega o Worker com um fetch falso: cada teste declara as respostas do banco e do GitHub.
function montar(respostas) {
  const chamadas = [];
  const falso = async (url, op = {}) => {
    const u = String(url), metodo = op.method || 'GET';
    let corpo = op.body;
    if (corpo && corpo.getReader) corpo = new Uint8Array(await new Response(corpo).arrayBuffer());
    chamadas.push({ url: u, metodo, corpo });
    for (const [padrao, r] of respostas) {
      const [m, trecho] = padrao.split(' ');
      if (m === metodo && u.includes(trecho)) {
        const v = typeof r === 'function' ? r(u, op) : r;
        return new Response(v.status === 204 ? null : JSON.stringify(v.corpo ?? null), { status: v.status ?? 200 });
      }
    }
    throw new Error(`chamada inesperada: ${metodo} ${u}`);
  };
  const fonte = fs.readFileSync(path.join(__dirname, '../../worker/arquivos.js'), 'utf8')
    .replace('export default {', 'module.exports.padrao = {')
    .replace('export async function voosIndicadores', 'module.exports.voosIndicadores = async function voosIndicadores');
  const mod = { exports: {} };
  vm.runInNewContext(fonte, {
    module: mod, URL, Response, console, setTimeout, Date, fetch: falso,
    FixedLengthStream: class extends TransformStream { constructor() { super(); } },
  });
  return { rota: (req) => mod.exports.padrao.fetch(req, ENV), chamadas, noGithub: () => chamadas.filter((c) => c.url.includes('github.com')) };
}

function reqParte({ rodada = '', nome = 'parte-001.zip', arquivo = new Blob(['conteudo']), token = 'jwt' } = {}) {
  const f = new FormData();
  f.set('rodada_id', rodada);
  f.set('nome', nome);
  if (arquivo) f.set('arquivo', arquivo, nome);
  return new Request('https://w/paralelismo/parte', { method: 'POST', body: f, headers: token ? { Authorization: `Bearer ${token}`, Origin: 'https://hub' } : {} });
}

const RPC_ID = (id) => ['POST rpc/paralelismo_preparar_parte', { corpo: id }];
const RELEASE = (id = 7) => ['GET /releases/tags/', { corpo: { id, assets: [] } }];
const SEM_ASSETS = ['GET /assets?per_page=100', { corpo: [] }];
const ASSET_NOVO = ['POST uploads.github.com', { status: 201, corpo: { id: 50, size: 8, browser_download_url: 'https://github.com/dono/arquivos/releases/download/paralelismo-r12/parte-001.zip' } }];

test('parte: sem token é 401 e não chama ninguém', async () => {
  const m = montar([]);
  const r = await m.rota(reqParte({ token: null }));
  assert.strictEqual(r.status, 401);
  assert.strictEqual(m.chamadas.length, 0);
});

test('parte: Content-Length acima de 95 MB é 413 sem ler o corpo', async () => {
  const m = montar([]);
  const r = await m.rota({
    method: 'POST', url: 'https://w/paralelismo/parte',
    headers: new Headers({ Authorization: 'Bearer jwt', 'Content-Length': String(95 * MB + 1) }),
    formData: async () => { throw new Error('não deveria ler o corpo'); },
  });
  assert.strictEqual(r.status, 413);
  assert.strictEqual(m.chamadas.length, 0);
});

test('parte: arquivo acima de 95 MB é 413 mesmo sem Content-Length', async () => {
  const m = montar([]);
  const f = new FormData();
  f.set('nome', 'parte-001.zip');
  f.set('arquivo', new Blob([new Uint8Array(95 * MB + 1)]), 'parte-001.zip');
  const r = await m.rota({ method: 'POST', url: 'https://w/paralelismo/parte', headers: new Headers({ Authorization: 'Bearer jwt' }), formData: async () => f });
  assert.strictEqual(r.status, 413);
  assert.strictEqual(m.chamadas.length, 0);
});

for (const nome of ['../fora.zip', 'pasta/parte.zip', 'parte 1.zip', 'parte.exe', '', '.zip']) {
  test(`parte: nome inválido "${nome}" é 400 sem chamar o banco`, async () => {
    const m = montar([]);
    const r = await m.rota(reqParte({ nome }));
    assert.strictEqual(r.status, 400);
    assert.strictEqual(m.chamadas.length, 0);
  });
}

test('parte: rodada_id que não é número é 400 sem chamar o banco', async () => {
  const m = montar([]);
  const r = await m.rota(reqParte({ rodada: '12;drop' }));
  assert.strictEqual(r.status, 400);
  assert.strictEqual(m.chamadas.length, 0);
});

test('parte: arquivo vazio ou ausente é 400', async () => {
  const m = montar([]);
  assert.strictEqual((await m.rota(reqParte({ arquivo: null }))).status, 400);
  assert.strictEqual((await m.rota(reqParte({ arquivo: new Blob([]) }))).status, 400);
  assert.strictEqual(m.chamadas.length, 0);
});

test('parte: o banco recusa (sem permissão ou id de outro) e nada chega ao GitHub', async () => {
  const m = montar([['POST rpc/paralelismo_preparar_parte', { status: 400, corpo: { message: 'rodada_invalida:12' } }]]);
  const r = await m.rota(reqParte({ rodada: '12' }));
  assert.strictEqual(r.status, 400);
  assert.match((await r.json()).erro, /rodada_invalida/);
  assert.strictEqual(m.noGithub().length, 0);
});

test('parte: sessão expirada no banco é 401', async () => {
  const m = montar([['POST rpc/paralelismo_preparar_parte', { status: 401, corpo: { message: 'JWT expired' } }]]);
  assert.strictEqual((await m.rota(reqParte())).status, 401);
});

test('parte: primeira parte reserva o id, cria a release e devolve rodada_id, url e bytes', async () => {
  const m = montar([RPC_ID(12), ['GET /releases/tags/', { status: 404, corpo: {} }], ASSET_NOVO,
    ['POST /repos/dono/arquivos/releases', { status: 201, corpo: { id: 7, assets: [] } }], SEM_ASSETS]);
  const r = await m.rota(reqParte());
  assert.strictEqual(r.status, 200);
  assert.deepStrictEqual(await r.json(), { rodada_id: 12, url: 'https://github.com/dono/arquivos/releases/download/paralelismo-r12/parte-001.zip', bytes: 8 });
  const rpc = m.chamadas.find((c) => c.url.includes('rpc/'));
  assert.deepStrictEqual(JSON.parse(rpc.corpo), { p_rodada_id: null });
  assert.ok(m.chamadas.some((c) => c.url.includes('/releases/tags/paralelismo-r12')));
  const criar = m.chamadas.find((c) => c.metodo === 'POST' && c.url.endsWith('/releases'));
  assert.strictEqual(JSON.parse(criar.corpo).tag_name, 'paralelismo-r12');
  const up = m.chamadas.find((c) => c.url.includes('uploads.github.com'));
  assert.ok(up.url.includes('/releases/7/assets?name=parte-001.zip'));
  assert.strictEqual(new TextDecoder().decode(up.corpo), 'conteudo');
});

test('parte: parte seguinte manda o id e reaproveita a release', async () => {
  const m = montar([RPC_ID(12), RELEASE(), SEM_ASSETS, ASSET_NOVO]);
  const r = await m.rota(reqParte({ rodada: '12' }));
  assert.strictEqual(r.status, 200);
  assert.deepStrictEqual(JSON.parse(m.chamadas[0].corpo), { p_rodada_id: 12 });
  assert.ok(!m.chamadas.some((c) => c.metodo === 'POST' && c.url.endsWith('/releases')));
});

test('parte: reenvio substitui o asset de mesmo nome', async () => {
  const m = montar([RPC_ID(12), RELEASE(), ['GET /assets?per_page=100', { corpo: [{ id: 40, name: 'parte-001.zip' }] }],
    ['POST uploads.github.com', { status: 201, corpo: { id: 50, size: 8 } }],
    ['DELETE /releases/assets/40', { status: 204 }],
    ['PATCH /releases/assets/50', { corpo: { id: 50, size: 8, browser_download_url: 'https://github.com/d/parte-001.zip' } }]]);
  const r = await m.rota(reqParte({ rodada: '12' }));
  assert.strictEqual(r.status, 200);
  assert.deepStrictEqual(await r.json(), { rodada_id: 12, url: 'https://github.com/d/parte-001.zip', bytes: 8 });
  const ren = m.chamadas.find((c) => c.metodo === 'PATCH');
  assert.strictEqual(JSON.parse(ren.corpo).name, 'parte-001.zip');
});

test('parte: acha o asset repetido além da primeira página', async () => {
  const cheia = Array.from({ length: 100 }, (_, i) => ({ id: i, name: `outro-${i}.zip` }));
  const m = montar([RPC_ID(12), RELEASE(),
    ['GET /assets?per_page=100&page=2', { corpo: [{ id: 400, name: 'parte-001.zip' }] }],
    ['GET /assets?per_page=100&page=1', { corpo: cheia }],
    ['POST uploads.github.com', { status: 201, corpo: { id: 50, size: 8 } }],
    ['DELETE /releases/assets/400', { status: 204 }],
    ['PATCH /releases/assets/50', { corpo: { id: 50, size: 8, browser_download_url: 'https://github.com/d/p.zip' } }]]);
  assert.strictEqual((await m.rota(reqParte({ rodada: '12' }))).status, 200);
  assert.ok(m.chamadas.some((c) => c.metodo === 'DELETE'));
});

test('parte: rodada_ja_enviada é sucesso e não toca no GitHub', async () => {
  const m = montar([['POST rpc/paralelismo_preparar_parte', { status: 400, corpo: { message: 'rodada_ja_enviada:12' } }]]);
  const r = await m.rota(reqParte({ rodada: '12' }));
  assert.strictEqual(r.status, 200);
  assert.deepStrictEqual(await r.json(), { rodada_id: 12, ja_enviada: true, url: null, bytes: 0 });
  assert.strictEqual(m.noGithub().length, 0);
});

test('parte: falha no GitHub depois da reserva devolve o id, para tentar de novo com o mesmo', async () => {
  const m = montar([RPC_ID(12), ['GET /releases/tags/', { status: 500, corpo: {} }]]);
  const r = await m.rota(reqParte());
  assert.strictEqual(r.status, 502);
  assert.strictEqual((await r.json()).rodada_id, 12);
});

test('parte: erro antes da reserva não inventa id', async () => {
  const m = montar([['POST rpc/paralelismo_preparar_parte', { status: 400, corpo: { message: 'Sem permissão' } }]]);
  const corpo = await (await m.rota(reqParte())).json();
  assert.strictEqual(corpo.rodada_id, undefined);
});

test('parte: resposta leva o CORS da origem permitida', async () => {
  const m = montar([RPC_ID(12), RELEASE(), SEM_ASSETS, ASSET_NOVO]);
  const r = await m.rota(reqParte({ rodada: '12' }));
  assert.strictEqual(r.status, 200);
  assert.strictEqual(r.headers.get('Access-Control-Allow-Origin'), 'https://hub');
});

test('parte: GitHub fora do ar é 502', async () => {
  const m = montar([RPC_ID(12), ['GET /releases/tags/', { status: 500, corpo: {} }]]);
  assert.strictEqual((await m.rota(reqParte({ rodada: '12' }))).status, 502);
});

function reqExcluida(corpo, token = 'jwt') {
  return new Request('https://w/paralelismo/excluida', { method: 'POST', body: typeof corpo === 'string' ? corpo : JSON.stringify(corpo), headers: token ? { Authorization: `Bearer ${token}` } : {} });
}
const NIVEL = (n) => ['POST rpc/paralelismo_nivel', { corpo: n }];
const SEM_RODADA = ['GET paralelismo_rodadas?', { corpo: [] }];
const TAG = { release_tag: 'paralelismo-r12' };

test('excluída: sem token é 401', async () => {
  const m = montar([]);
  assert.strictEqual((await m.rota(reqExcluida(TAG, null))).status, 401);
  assert.strictEqual(m.chamadas.length, 0);
});

for (const corpo of [{ release_tag: 'plantio-10728' }, { release_tag: 'paralelismo-r12/../x' }, {}, 'não é json']) {
  test(`excluída: tag fora do padrão (${JSON.stringify(corpo)}) é 400 sem chamar ninguém`, async () => {
    const m = montar([]);
    assert.strictEqual((await m.rota(reqExcluida(corpo))).status, 400);
    assert.strictEqual(m.chamadas.length, 0);
  });
}

test('excluída: corpo JSON null responde em português', async () => {
  const m = montar([]);
  const r = await m.rota(reqExcluida('null'));
  assert.strictEqual(r.status, 400);
  assert.strictEqual((await r.json()).erro, 'Release inválida');
});

for (const nivel of ['editor', 'solicitante', 'leitura', null]) {
  test(`excluída: nível ${nivel} é 403 e nada chega ao GitHub`, async () => {
    const m = montar([NIVEL(nivel)]);
    assert.strictEqual((await m.rota(reqExcluida(TAG))).status, 403);
    assert.strictEqual(m.noGithub().length, 0);
  });
}

test('excluída: rodada que ainda existe é 409 e nada chega ao GitHub', async () => {
  const m = montar([NIVEL('admin'), ['GET paralelismo_rodadas?', { corpo: [{ id: 12 }] }]]);
  assert.strictEqual((await m.rota(reqExcluida(TAG))).status, 409);
  assert.ok(m.chamadas.some((c) => c.url.includes('release_tag=eq.paralelismo-r12')));
  assert.strictEqual(m.noGithub().length, 0);
});

test('excluída: release inexistente é 404 e não cria release', async () => {
  const m = montar([NIVEL('admin'), SEM_RODADA, ['GET /releases/tags/paralelismo-r12', { status: 404, corpo: {} }]]);
  assert.strictEqual((await m.rota(reqExcluida(TAG))).status, 404);
  assert.ok(!m.chamadas.some((c) => c.metodo !== 'GET' && c.url.includes('github.com')));
});

test('excluída: acrescenta a marca com a data de São Paulo e preserva a descrição', async (t) => {
  // 02:00 UTC do dia 5 ainda é dia 4 em São Paulo.
  t.mock.timers.enable({ apis: ['Date'], now: Date.UTC(2026, 10, 5, 2, 0, 0) });
  let enviado;
  const m = montar([NIVEL('admin'), SEM_RODADA, ['GET /releases/tags/paralelismo-r12', { corpo: { id: 7, body: 'Arquivos publicados pelo Hub Geotech.' } }],
    ['PATCH /releases/7', (u, op) => { enviado = JSON.parse(op.body); return { corpo: { id: 7 } }; }]]);
  const r = await m.rota(reqExcluida(TAG));
  assert.strictEqual(r.status, 200);
  assert.deepStrictEqual(await r.json(), { release_tag: 'paralelismo-r12', marcada: true });
  assert.ok(/^Arquivos publicados pelo Hub Geotech\.\n\nEXCLUÍDA em \d{2}\/\d{2}\/\d{4}$/.test(enviado.body), enviado.body);
  assert.ok(enviado.body.endsWith('04/11/2026'), enviado.body);
});

test('excluída: release sem descrição recebe só a marca', async () => {
  let enviado;
  const m = montar([NIVEL('admin'), SEM_RODADA, ['GET /releases/tags/paralelismo-r12', { corpo: { id: 7, body: null } }],
    ['PATCH /releases/7', (u, op) => { enviado = JSON.parse(op.body); return { corpo: { id: 7 } }; }]]);
  assert.strictEqual((await m.rota(reqExcluida(TAG))).status, 200);
  assert.match(enviado.body, /^EXCLUÍDA em /);
});

test('excluída: segunda marcação não repete', async () => {
  const m = montar([NIVEL('admin'), SEM_RODADA, ['GET /releases/tags/paralelismo-r12', { corpo: { id: 7, body: 'x\n\nEXCLUÍDA em 01/11/2026' } }]]);
  const r = await m.rota(reqExcluida(TAG));
  assert.strictEqual(r.status, 200);
  assert.deepStrictEqual(await r.json(), { release_tag: 'paralelismo-r12', marcada: false });
  assert.ok(!m.chamadas.some((c) => c.metodo === 'PATCH'));
});

test('excluída: GitHub recusa a edição é 502', async () => {
  const m = montar([NIVEL('admin'), SEM_RODADA, ['GET /releases/tags/paralelismo-r12', { corpo: { id: 7, body: '' } }], ['PATCH /releases/7', { status: 500, corpo: {} }]]);
  assert.strictEqual((await m.rota(reqExcluida(TAG))).status, 502);
});

test('as rotas antigas continuam: GET em rota do Paralelismo é 404', async () => {
  const m = montar([]);
  const r = await m.rota(new Request('https://w/paralelismo/parte'));
  assert.strictEqual(r.status, 404);
});
