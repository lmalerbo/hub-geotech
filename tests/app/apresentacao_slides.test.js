const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ctx = vm.createContext({ console });
for (const f of ['apresentacao-calculo.js', 'apresentacao-slides.js'])
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../../app', f), 'utf8'), ctx);
const pasta = path.join(__dirname, 'apresentacao');
const ler = (n) => JSON.parse(fs.readFileSync(path.join(pasta, 'dados', `${n}.json`), 'utf8'));
const D = { talhoes: ler('talhoes'), colheita_talhoes: ler('colheita_talhoes'), talhao_plantio: ler('talhao_plantio'),
            talhao_preparo: ler('talhao_preparo'), etapas: ler('etapas'), preparo_entregas: ler('preparo_entregas'),
            drone: ler('drone'), voos: ler('voos') };
const METAS = { meta_ervas_ha: 20863, meta_fornecedor_ha: 3500, meta_ha_dia: 250, drone_pendente_ha: 2000,
                safra_atual: '26/27', inicio_safra: '2026-04-01' };
const A = ctx.apAgregar(D, METAS);
const CTX = { semana: 'S5M10', corte: '2026-10-28' };

for (const chave of ['divisoria', 'colheita', 'sistematizacao', 'plantio', 'voos', 'drone']) {
  test(`paridade com o gerar.py: ${chave}`, () => {
    const esperado = fs.readFileSync(path.join(pasta, 'esperado', `${chave}.html`), 'utf8');
    assert.strictEqual(ctx.apCorpo(chave, A, METAS, CTX), esperado);
  });
}

test('frame: título, rodapé, número e subtítulo padrão', () => {
  const h = ctx.apSlide('colheita', A, METAS, {}, { ...CTX, num: 2 });
  assert.ok(h.includes(ctx.AP_TITULOS.colheita));
  assert.ok(h.includes('S5M10 · Dados até 28/10/2026'));
  assert.ok(h.includes(ctx.apEsc(ctx.apSubtituloPadrao('colheita', A, METAS, CTX))));
});

test('texto do usuário sai escapado', () => {
  const h = ctx.apSlide('drone', A, METAS, { subtitulo: '<b>x</b> & "y"', destaque: '<img src=x onerror=alert(1)>' }, { ...CTX, num: 6 });
  assert.ok(h.includes('&lt;b&gt;x&lt;/b&gt; &amp; &quot;y&quot;'));
  assert.ok(!h.includes('<img src=x'));
});

test('sem destaque, sem caixa de destaque', () => {
  assert.ok(!ctx.apSlide('plantio', A, METAS, { destaque: '  ' }, { ...CTX, num: 4 }).includes('ap-destaque'));
});

test('subtítulo do usuário substitui o padrão', () => {
  const h = ctx.apSlide('colheita', A, METAS, { subtitulo: 'Semana de chuva' }, { ...CTX, num: 2 });
  assert.ok(h.includes('Semana de chuva'));
  assert.ok(!h.includes(ctx.apSubtituloPadrao('colheita', A, METAS, CTX)));
});

test('títulos e ordem dos slides', () => {
  assert.deepStrictEqual([...ctx.AP_SLIDES], ['divisoria', 'colheita', 'sistematizacao', 'plantio', 'voos', 'drone']);
  assert.strictEqual(ctx.AP_TITULOS.drone, 'Projetos de Drone de Aplicação');
  assert.strictEqual(ctx.apEsc(`a'b`), 'a&#x27;b');
});
