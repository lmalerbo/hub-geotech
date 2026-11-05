// Prévia, avisos, carga do envio e envio em partes. Roda com: node --test tests/app/paralelismo_previa.test.js
// Só dados sintéticos: série BM0000X000000, frotas 9xxxx, fazendas fictícias.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');

const ctx = { console, setTimeout, clearTimeout };
vm.createContext(ctx);
for (const f of ['paralelismo-puro.js', 'paralelismo-previa.js']) vm.runInContext(fs.readFileSync(`${__dirname}/../../app/${f}`, 'utf8'), ctx);
const puro = (v) => JSON.parse(JSON.stringify(v));
const igual = (a, b) => assert.deepStrictEqual(puro(a), b);

const sha = (n) => String(n).padStart(64, '0');
const arq = (caminho, n, extra = {}) => ({ caminho, bytes: 1000 + n, sha256: sha(n), opfs: `f${n}.${caminho.split('.').pop()}`, serie: 'BM0000X000000', cod_faz: 10001, fazenda_monitor: 'USINA_10001Rev0', data: '2026-10-26', ...extra });

function analise(extra = {}) {
  return {
    pll_total: 100, pll_aderentes: 70, amostras: 90, aderentes: 63, acima: 20, abaixo: 7, fora_talhao: 10, mes: '2026-10-01',
    talhoes: [
      { talhao_num: 1, amostras: 60, aderentes: 45, acima: 10, abaixo: 5, media_m: 3.01, frotas: ['90001'], insuficiente: false },
      { talhao_num: 2, amostras: 30, aderentes: 18, acima: 10, abaixo: 2, media_m: 3.1, frotas: ['90001', '90002'], insuficiente: false },
    ],
    frotas: [{ frota: '90001', amostras: 60, aderentes: 45 }, { frota: '90002', amostras: 30, aderentes: 18 }],
    linhas_usadas: 5, pontos: [[0, 0]], ...extra,
  };
}
const fazenda = (extra = {}) => ({
  operacao: 'cana', cod_faz: 10001, base_analise_id: null,
  linhas_novas: [{ frota: '90001', data: '2026-10-26', coords: [[0, 0], [10, 0]] }],
  frotas_leitura: [{ frota: '90001', duracao_total_s: 7200, duracao_trabalho_s: 6000, sem_trabalho: false }],
  analise: analise(), shapefile: new Uint8Array([1, 2]), ...extra,
});
const resultado = (extra = {}) => ({ id: 'i1', pulados: [], parciais: [], fazendas: [fazenda()], ...extra });

// ── parRegistrosAceitos ──────────────────────────────────────────
test('registros: arquivo pulado não é registrado, nem o .fdd par do .fdl pulado', () => {
  const grupo = { frota: '90001', arquivos: [arq('a/1.fdl', 1), arq('a/1.fdd', 2), arq('a/2.fdl', 3), arq('a/2.fdd', 4)] };
  const r = ctx.parRegistrosAceitos([grupo], { pulados: [{ caminho: 'a/2.fdl', motivo: 'ilegivel' }] });
  igual(r.map((x) => x.caminho), ['a/1.fdl', 'a/1.fdd']);
  assert.strictEqual(r[0].frota, '90001');
  assert.strictEqual(r[1].cod_faz, 10001);
});

test('registros: arquivo parcial continua registrado (os pontos foram usados)', () => {
  const grupo = { frota: '90001', arquivos: [arq('a/1.jdl', 1)] };
  const r = ctx.parRegistrosAceitos([grupo], { pulados: [], parciais: [{ caminho: 'a/1.jdl' }] });
  igual(r.map((x) => x.caminho), ['a/1.jdl']);
});

// ── parPrevia ────────────────────────────────────────────────────
test('prévia: aderência por fazenda, talhão e frota, e comparação com a vigente', () => {
  const p = ctx.parPrevia(resultado(), { 'cana|10001': { amostras: 100, aderentes: 60 } });
  const f = p.fazendas[0];
  assert.strictEqual(f.pctTxt, '70,00%');
  assert.strictEqual(f.vigentePctTxt, '60,00%');
  assert.strictEqual(f.deltaTxt, '+10,00 p.p.');
  assert.strictEqual(f.talhoes[0].pctTxt, '75,00%');
  assert.strictEqual(f.frotas[1].pctTxt, '60,00%');
  assert.strictEqual(f.foraTalhao, 10);
  assert.strictEqual(p.total.pctTxt, '70,00%');
});

test('prévia: fazenda nova não tem comparação', () => {
  const f = ctx.parPrevia(resultado(), {}).fazendas[0];
  assert.strictEqual(f.vigentePctTxt, null);
  assert.strictEqual(f.deltaTxt, null);
});

test('avisos da fazenda: fora de talhão acima de 5%, insuficiente e frota sem trabalho', () => {
  const a = analise({ fora_talhao: 6, pll_total: 96, talhoes: [{ talhao_num: 9, amostras: 10, aderentes: 5, acima: 3, abaixo: 2, media_m: 3, frotas: [], insuficiente: true }] });
  const fz = fazenda({ analise: a, frotas_leitura: [{ frota: '90001', sem_trabalho: true }] });
  const f = ctx.parPrevia(resultado({ fazendas: [fz] }), {}).fazendas[0];
  igual(f.avisos.map((x) => x.codigo), ['fora_talhao_alto', 'insuficiente', 'sem_trabalho']);
});

test('fora de talhão exatamente 5% não avisa', () => {
  const fz = fazenda({ analise: analise({ fora_talhao: 5, pll_total: 100 }) });
  assert.strictEqual(ctx.parPrevia(resultado({ fazendas: [fz] }), {}).fazendas[0].avisos.length, 0);
});

test('fazenda sem linhas novas fica de fora do envio e avisa', () => {
  const novo = fazenda({ linhas_novas: [] });
  const p = ctx.parPrevia(resultado({ fazendas: [novo, fazenda({ cod_faz: 10002 })] }), {});
  assert.strictEqual(p.fazendas[0].enviavel, false);
  assert.strictEqual(p.fazendas[0].avisos[0].codigo, 'sem_linhas_novas');
  assert.strictEqual(p.fazendas[1].enviavel, true);
  assert.strictEqual(p.enviaveis, 1);
});

// ── parAvisosItem ────────────────────────────────────────────────
test('avisos do item: pulados com motivo, parciais e falhas de cópia, com o texto da spec §10', () => {
  const r = resultado({ pulados: [{ caminho: 'a/x.fdd', motivo: 'ilegivel' }, { caminho: 'b.jdl', motivo: 'sem_frota' }], parciais: [{ caminho: 'c.jdl' }] });
  const av = ctx.parAvisosItem(r, [{ caminho: 'd.jdl', motivo: 'nao_copiado' }]);
  igual(av.map((x) => x.codigo), ['pulados_ilegivel', 'pulados_sem_frota', 'parciais', 'nao_copiado']);
  assert.match(av[0].texto, /corrompido ou cortado/);
  igual(av[0].arquivos, ['a/x.fdd']);
});

// ── parPayloadEnvio ──────────────────────────────────────────────
test('carga do envio: sem pontos nem shapefile, só fazendas enviáveis, linhas com operação e fazenda', () => {
  const regs = [{ sha256: sha(1), caminho: 'a/1.jdl', bytes: 5, tipo: 'jdl', serie: 'S', frota: '90001', cod_faz: 10001, fazenda_monitor: 'x' }];
  const r = resultado({ fazendas: [fazenda({ base_analise_id: 7 }), fazenda({ cod_faz: 10002, linhas_novas: [] })] });
  const p = ctx.parPayloadEnvio({ rodadaId: 55, descricao: 'teste', registros: regs, partes: [{ nome: 'p55-01.zip', url: 'https://x/y', bytes: 9 }], resultado: r, urlsAmostras: { 'cana|10001': 'https://x/a.zip' } });
  assert.strictEqual(p.rodada_id, 55);
  assert.strictEqual(p.analises.length, 1);
  const a = p.analises[0];
  assert.strictEqual(a.base_analise_id, 7);
  assert.strictEqual(a.amostras_url, 'https://x/a.zip');
  assert.strictEqual(a.pontos, undefined);
  assert.strictEqual(a.shapefile, undefined);
  assert.strictEqual(a.talhoes[0].insuficiente, undefined);
  igual(p.linhas, [{ operacao: 'cana', cod_faz: 10001, frota: '90001', data: '2026-10-26', coords: [[0, 0], [10, 0]] }]);
  assert.strictEqual(p.arquivos.length, 1);
  assert.strictEqual(p.partes.length, 1);
});

test('nome da parte', () => {
  assert.strictEqual(ctx.parNomeParte(55, 3), 'p55-03.zip');
  assert.strictEqual(ctx.parNomeAmostras('cana', 10001), 'amostras-cana-10001.zip');
});

// ── parTextoErro ─────────────────────────────────────────────────
test('textos de erro do envio', () => {
  assert.match(ctx.parTextoErro(new Error('arquivo_ja_analisado:abc')), /já foram analisados/);
  assert.match(ctx.parTextoErro(new Error('rodada_ja_enviada:5')), /já foi enviada/);
  assert.match(ctx.parTextoErro(new Error('Sem permissão para enviar ao Paralelismo')), /nível/);
  assert.match(ctx.parTextoErro(new TypeError('Failed to fetch')), /conexão/);
  assert.match(ctx.parTextoErro(new Error('Sessão expirada; entre de novo')), /sessão expirou/);
  assert.match(ctx.parTextoErro(new Error('Parte maior que 95 MB')), /95 MB/);
  assert.doesNotMatch(ctx.parTextoErro(new TypeError("Cannot read properties of undefined")), /conexão/);
  assert.match(ctx.parTextoErro(new Error('qualquer coisa')), /Nada foi gravado/);
});

// ── parEnviarItem ────────────────────────────────────────────────
function deps(extra = {}) {
  const chamadas = [];
  return {
    chamadas,
    preparar: async (id) => { chamadas.push(['preparar', id]); return id ?? 77; },
    ler: async (opfs) => { chamadas.push(['ler', opfs]); return new Uint8Array(3); },
    zip: async (entradas) => ({ size: entradas.length, entradas }),
    subir: async (nome, blob, id) => { chamadas.push(['subir', nome, id]); return { rodada_id: id, url: `https://x/${nome}`, bytes: blob.size }; },
    enviar: async (p) => { chamadas.push(['enviar', p.rodada_id]); return p.rodada_id; },
    ...extra,
  };
}
const entrada = () => ({
  id: 'i1', rodadaId: null,
  todos: [arq('a/1.jdl', 1), arq('a/2.jdl', 2)],
  grupos: [{ frota: '90001', operacao: 'cana', arquivos: [arq('a/1.jdl', 1), arq('a/2.jdl', 2)] }],
  resultado: resultado(),
});

test('envio: reserva o id, sobe partes, manifesto e shapefiles e só então grava', async () => {
  const d = deps();
  const r = await ctx.parEnviarItem(entrada(), d);
  assert.strictEqual(r.rodadaId, 77);
  const nomes = d.chamadas.filter((c) => c[0] === 'subir').map((c) => c[1]);
  igual(nomes, ['p77-01.zip', 'manifesto.csv', 'amostras-cana-10001.zip']);
  assert.strictEqual(d.chamadas[d.chamadas.length - 1][0], 'enviar');
});

test('envio: falha numa parte não grava nada e devolve o id para tentar de novo', async () => {
  let n = 0;
  const d = deps({ subir: async (nome, blob, id) => { if (++n === 2) throw new Error('GitHub caiu'); return { rodada_id: id, url: 'https://x/' + nome, bytes: 1 }; } });
  const item = entrada();
  await assert.rejects(ctx.parEnviarItem(item, d), (e) => e.rodadaId === 77 && /Nada foi gravado/.test(e.message));
  assert.ok(!d.chamadas.some((c) => c[0] === 'enviar'));
  const d2 = deps();
  await ctx.parEnviarItem({ ...item, rodadaId: 77 }, d2);
  assert.deepStrictEqual(d2.chamadas[0], ['preparar', 77]);
});

test('envio: arquivo repetido na hora de gravar volta com texto claro e mantém o id', async () => {
  const d = deps({ enviar: async () => { throw new Error('arquivo_ja_analisado:abc'); } });
  await assert.rejects(ctx.parEnviarItem(entrada(), d), (e) => e.rodadaId === 77 && /já foram analisados/.test(e.message));
});

test('envio: sem nenhuma fazenda enviável nem reserva id', async () => {
  const d = deps();
  const item = entrada();
  item.resultado = resultado({ fazendas: [fazenda({ linhas_novas: [] })] });
  await assert.rejects(ctx.parEnviarItem(item, d), /Nada novo/);
  assert.strictEqual(d.chamadas.length, 0);
});

test('envio: o id inválido e o já enviado chegam em causa, para a tela decidir', async () => {
  const d = deps({ preparar: async () => { throw new Error('rodada_ja_enviada:5'); } });
  await assert.rejects(ctx.parEnviarItem({ ...entrada(), rodadaId: 5 }, d), (e) => e.rodadaId === 5 && /rodada_ja_enviada/.test(e.causa.message));
});
