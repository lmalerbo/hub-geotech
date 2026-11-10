// SEG4: dado externo não pode virar HTML nem sair da string de um handler inline.
// Roda com: node --test tests/app/escape_html.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');

const XSS = '<img src=x onerror=alert(1)>';
const QUEBRA = "'); alert(1); ('";
const APP = __dirname + '/../../app/';

// Extrai o texto de `function nome(...) {...}` por casamento de chaves (sem refatorar o app).
function extrai(src, nome) {
  const ini = src.search(new RegExp('(async )?function ' + nome + '[(]'));
  assert.ok(ini >= 0, 'função não encontrada: ' + nome);
  const linha = src.slice(ini, src.indexOf(String.fromCharCode(10), ini));
  if (/\}\s*$/.test(linha) && linha.includes('{')) return linha;   // função de uma linha (esc, escJs)
  let i = src.indexOf('{', src.indexOf(')', ini)), nivel = 0, str = null;
  for (; i < src.length; i++) {
    const c = src[i];
    if (str) { if (c === String.fromCharCode(92)) i++; else if (c === str) str = null; continue; }
    if (c === "'" || c === '"' || c === '`') { str = c; continue; }
    if (c === '{') nivel++;
    else if (c === '}' && --nivel === 0) return src.slice(ini, i + 1);
  }
  throw new Error('chaves não fecham: ' + nome);
}
function carrega(arquivo, nomes, ctx) {
  const src = fs.readFileSync(APP + arquivo, 'utf8');
  vm.createContext(ctx);
  for (const n of nomes) vm.runInContext(extrai(src, n), ctx);
  return ctx;
}
// Pega o conteúdo dos atributos on*="..." (decodificando as entidades do escape, como o navegador faz).
const handlers = html => [...html.matchAll(/\son\w+="([^"]*)"/g)].map(m =>
  m[1].replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&'));

// ── drone (mesmo carregamento do drone_puro.test.js) ──
const dr = { document: {}, sb: {}, console };
vm.createContext(dr);
for (const f of ['drone-dados', 'drone-previa', 'drone-inicio', 'drone-fazenda', 'drone-obstaculos'])
  vm.runInContext(fs.readFileSync(APP + f + '.js', 'utf8'), dr);
dr.esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

test('driCartaoHtml: texto do banco escapado e cod_faz só numérico no handler', () => {
  const base = { id: 7, cod_faz: 10, fazenda: 'F', tipo: 'normal', status: 'solicitado', solicitante: 'S', criado_em: '2026-10-28T10:00Z' };
  const agora = new Date('2026-10-28T12:00Z');
  for (const ruim of [XSS, QUEBRA]) {
    const h = dr.driCartaoHtml({ ...base, fazenda: ruim, solicitante: ruim, id: ruim, cod_faz: ruim }, { editor: true, agora });
    assert.ok(!h.includes('<img'));
    handlers(h).forEach(j => assert.doesNotMatch(j, /alert\(1\)/));
    assert.match(h, /driAbrirFazenda\(NaN,'normal'\)/);
  }
});

test('drLinhaResumo escapa os dois lados', () => {
  for (const ruim of [XSS, QUEBRA]) {
    const h = dr.drLinhaResumo(ruim, ruim);
    assert.ok(!h.includes('<img'));
    assert.ok(!h.includes("'); alert(1); ('"));
  }
  assert.strictEqual(dr.drLinhaResumo('Remover', '1, 2'), '<div class="dr-row"><span>Remover</span><span>1, 2</span></div>');
});

// ── index.html: slotHtml e listaSinoHtml ──
const ix = carrega('index.html', ['esc', 'slotHtml', 'listaSinoHtml'], {
  AVISOS: [], EU: { admin: true, perms: {} }, fmtDataHora: x => String(x), avisosVisiveis() { return this.AVISOS; },
});
ix.avisosVisiveis = () => ix.AVISOS;

test('slotHtml: extensão e rótulo escapados', () => {
  for (const ruim of [XSS, QUEBRA]) {
    const h = ix.slotHtml({ ext: ruim, rotulo: ruim }, 0, '');
    assert.ok(!h.includes('<img'));
    assert.ok(!h.includes("'); alert(1); ('"));
  }
});

test('listaSinoHtml: título/texto escapados e id só numérico no handler', () => {
  for (const ruim of [XSS, QUEBRA]) {
    ix.AVISOS = [{ id: ruim, modulo_id: 'colheita', titulo: ruim, texto: ruim, lido: false, atualizado_em: 'x' }];
    const h = ix.listaSinoHtml();
    assert.ok(!h.includes('<img'));
    handlers(h).forEach(j => assert.doesNotMatch(j, /alert\(1\)/));
    assert.match(h, /abrirAviso\(NaN\)/);
  }
});

test('esc do index escapa aspas e sinais de HTML', () => {
  assert.strictEqual(ix.esc(XSS), '&lt;img src=x onerror=alert(1)&gt;');
  assert.strictEqual(ix.esc(null), '');
});

// ── portal.html: escJs e cartao ──
const pt = carrega('portal.html', ['esc', 'escJs', 'cartao'], {
  modulo: 'plantio', visiveis: () => [], data: x => String(x), arquivo: () => '',
});

test('portal escJs: a string do handler não fecha', () => {
  const j = pt.escJs(QUEBRA).replace(/&#39;/g, "'");
  const b = String.fromCharCode(92);
  assert.strictEqual(j, b + "'); alert(1); (" + b + "'");
  assert.ok(!pt.escJs(XSS).includes('<img'));
});

test('portal cartao: cod/nome escapados e alternar com Number', () => {
  for (const ruim of [XSS, QUEBRA]) {
    const h = pt.cartao({ cod: ruim, nome: ruim, atualizado: 'x' }, false);
    assert.ok(!h.includes('<img'));
    handlers(h).forEach(j => assert.doesNotMatch(j, /alert\(1\)/));
    assert.match(h, /alternar\(NaN\)/);
  }
});
