// Cópia no OPFS, sobras, plano do item e fila. Roda com: node --test tests/app/paralelismo_fila.test.js
// OPFS, Web Locks e Worker são falsos aqui; os de verdade são provados no Edge por tests/app/teste_paralelismo_worker.py.
// Só dados sintéticos: série BM0000X000000, frotas 9xxxx, fazendas fictícias.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');
const { createHash, webcrypto } = require('crypto');

const puro = (v) => JSON.parse(JSON.stringify(v));
const igual = (a, b) => assert.deepStrictEqual(puro(a), b);
const espera = () => new Promise((ok) => setImmediate(ok));

class ArquivoFalso {
  constructor(cota) { this.dados = new Uint8Array(); this.cota = cota; this.kind = 'file'; }
  async createWritable() {
    const dono = this;
    let novo = null;
    return {
      async write(b) {
        if (dono.cota.livre < b.length) throw Object.assign(new Error('cheio'), { name: 'QuotaExceededError' });
        dono.cota.livre -= b.length;
        novo = Uint8Array.from(b);
      },
      async close() { dono.dados = novo; },
      async abort() {},
    };
  }
  async getFile() {
    const d = this.dados;
    return { size: d.length, lastModified: 1000, arrayBuffer: async () => d.buffer.slice(d.byteOffset, d.byteOffset + d.length) };
  }
}

class PastaFalsa {
  constructor(cota) { this.filhos = new Map(); this.cota = cota; this.kind = 'directory'; }
  async getDirectoryHandle(nome, { create } = {}) {
    if (!this.filhos.has(nome)) {
      if (!create) throw Object.assign(new Error('sem pasta'), { name: 'NotFoundError' });
      this.filhos.set(nome, new PastaFalsa(this.cota));
    }
    return this.filhos.get(nome);
  }
  async getFileHandle(nome, { create } = {}) {
    if (!this.filhos.has(nome)) {
      if (!create) throw Object.assign(new Error('sem arquivo'), { name: 'NotFoundError' });
      this.filhos.set(nome, new ArquivoFalso(this.cota));
    }
    return this.filhos.get(nome);
  }
  async removeEntry(nome) {
    if (!this.filhos.delete(nome)) throw Object.assign(new Error('sem item'), { name: 'NotFoundError' });
  }
  async *entries() { yield* this.filhos.entries(); }
}

function ambiente({ cota = Infinity } = {}) {
  const raiz = new PastaFalsa({ livre: cota });
  const presas = new Map();
  const navigator = {
    storage: { getDirectory: async () => raiz },
    locks: {
      request(nome, cb) {
        presas.set(nome, true);
        return cb().then(() => presas.delete(nome));
      },
      query: async () => ({ held: [...presas.keys()].map((name) => ({ name })) }),
    },
  };
  const ctx = { console, navigator, crypto: webcrypto, TextDecoder, setTimeout, Uint8Array, ArrayBuffer };
  vm.createContext(ctx);
  for (const f of ['paralelismo-puro.js', 'paralelismo-fila.js']) {
    vm.runInContext(fs.readFileSync(`${__dirname}/../../app/${f}`, 'utf8'), ctx);
  }
  return { ctx, raiz, presas, navigator };
}

const bytesDe = (txt) => Uint8Array.from(Buffer.from(txt, 'latin1'));
const origem = (caminho, txt) => {
  const b = bytesDe(txt);
  return { webkitRelativePath: caminho, name: caminho.split('/').pop(), size: b.length, arrayBuffer: async () => b.buffer.slice(0) };
};
const sha = (txt) => createHash('sha256').update(Buffer.from(txt, 'latin1')).digest('hex');
const FDL = '<RCD><rcdsetup:Farm erid="f1" name="99999Rev2" /><rcdsetup:Field erid="t1" name="1" farmRef="f1" /><FieldRef eridRef="t1" />'
  + '<LogTaskRegion timeStamp="2026-10-10T10:00:00Z" /><X filePosition="0" /></RCD>';

// ── parOpfsCopiar ──────────────────────────────────────────────────────
test('copiar: SHA-256, bytes, nome no OPFS e identificação do .jdl', async () => {
  const { ctx } = ambiente();
  const txt = 'xxBM0000X000001yy';
  const r = await ctx.parOpfsCopiar('i1', [origem('pen/log/2026_U_99999Rev1_Parte 1/2026_10_26_a.jdl', txt)]);
  igual(r, {
    arquivos: [{
      caminho: 'pen/log/2026_U_99999Rev1_Parte 1/2026_10_26_a.jdl', bytes: txt.length, sha256: sha(txt), opfs: 'f000001.jdl',
      tipo: 'jdl', serie: 'BM0000X000001', cod_faz: 99999, revisao: 1, fazenda_monitor: '2026_U_99999Rev1_Parte 1', data: '2026-10-26',
    }],
    mapas: [], falhas: [],
  });
  assert.deepStrictEqual([...await ctx.parOpfsLer('i1', 'f000001.jdl')], [...bytesDe(txt)]);
});

test('copiar: .fdl identificado e .fdd copiado ao lado', async () => {
  const { ctx } = ambiente();
  const r = await ctx.parOpfsCopiar('i1', [origem('p/F8/s.fdl', FDL), origem('p/F8/s.fdd', 'binario')]);
  assert.strictEqual(r.arquivos[0].cod_faz, 99999);
  assert.strictEqual(r.arquivos[0].temFdd, true);
  assert.strictEqual(r.arquivos[0].opfs, 'f000001.fdl');
  assert.strictEqual(r.arquivos[1].opfs, 'f000002.fdd');
  assert.strictEqual(r.arquivos[1].sha256, sha('binario'));
});

test('copiar: mapa de cobertura entra só pelo nome e o resto é ignorado', async () => {
  const { ctx, raiz } = ambiente();
  const r = await ctx.parOpfsCopiar('i1', [origem('p/a.pth', 'mapa'), origem('p/b.PVF', 'mapa2'), origem('p/c.exe', 'lixo')]);
  igual(r, { arquivos: [], mapas: [{ caminho: 'p/a.pth', bytes: 4 }, { caminho: 'p/b.PVF', bytes: 5 }], falhas: [] });
  assert.strictEqual(raiz.filhos.get('paralelismo').filhos.get('i1').filhos.size, 0);
});

test('copiar: pen-drive retirado no meio vira falha do arquivo, e os outros seguem', async () => {
  const { ctx } = ambiente();
  const sumiu = { webkitRelativePath: 'p/a.jdl', name: 'a.jdl', size: 9, arrayBuffer: async () => { throw Object.assign(new Error('x'), { name: 'NotReadableError' }); } };
  const r = await ctx.parOpfsCopiar('i1', [sumiu, origem('p/b.jdl', 'ok')]);
  igual(r.falhas, [{ caminho: 'p/a.jdl', motivo: 'nao_copiado' }]);
  assert.deepStrictEqual(puro(r.arquivos.map((a) => a.caminho)), ['p/b.jdl']);
});

test('copiar: sem espaço apaga a cópia inteira e avisa', async () => {
  const { ctx, raiz, presas } = ambiente({ cota: 5 });
  await assert.rejects(ctx.parOpfsCopiar('i1', [origem('p/a.jdl', '123'), origem('p/b.jdl', '4567')]), (e) => /Não há espaço/.test(e.message));
  assert.strictEqual(raiz.filhos.get('paralelismo').filhos.has('i1'), false);
  await espera();
  assert.strictEqual(presas.size, 0);
});

test('copiar: avisa o progresso por arquivo copiado, em bytes', async () => {
  const { ctx } = ambiente();
  const visto = [];
  await ctx.parOpfsCopiar('i1', [origem('p/a.jdl', '123'), origem('p/z.exe', 'naoconta'), origem('p/b.jdl', '4567')], { aoProgresso: (p) => visto.push(puro(p)) });
  igual(visto, [{ feitos: 3, total: 7, caminho: 'p/a.jdl' }, { feitos: 7, total: 7, caminho: 'p/b.jdl' }]);
});

test('copiar: a segunda cópia com o mesmo id é recusada e não sobrescreve a primeira', async () => {
  const { ctx } = ambiente();
  await ctx.parOpfsCopiar('i1', [origem('p/a.jdl', 'primeiro')]);
  await assert.rejects(ctx.parOpfsCopiar('i1', [origem('p/c.jdl', 'outro')]));
  assert.deepStrictEqual([...await ctx.parOpfsLer('i1', 'f000001.jdl')], [...bytesDe('primeiro')]);
});

test('copiar: duas cópias simultâneas com o mesmo id: a segunda é recusada na hora', async () => {
  const { ctx } = ambiente();
  const primeira = ctx.parOpfsCopiar('i1', [origem('p/a.jdl', 'primeiro')]);
  await assert.rejects(ctx.parOpfsCopiar('i1', [origem('p/c.jdl', 'outro')]));
  await primeira;
  assert.deepStrictEqual([...await ctx.parOpfsLer('i1', 'f000001.jdl')], [...bytesDe('primeiro')]);
});

test('copiar: depois de descartar, o id pode ser usado de novo', async () => {
  const { ctx } = ambiente();
  await ctx.parOpfsCopiar('i1', [origem('p/a.jdl', 'primeiro')]);
  await ctx.parOpfsDescartar('i1');
  await ctx.parOpfsCopiar('i1', [origem('p/c.jdl', 'outro')]);
  assert.deepStrictEqual([...await ctx.parOpfsLer('i1', 'f000001.jdl')], [...bytesDe('outro')]);
});

// ── sobras ─────────────────────────────────────────────────────────────
test('sobras: sem nada no OPFS, lista vazia', async () => {
  const { ctx, raiz } = ambiente();
  igual(await ctx.parOpfsSobras(), []);
  assert.strictEqual(raiz.filhos.size, 0);
});

test('sobras: cópia em uso nesta sessão não aparece; sem a trava aparece com o tamanho', async () => {
  const { ctx, presas } = ambiente();
  await ctx.parOpfsCopiar('i1', [origem('p/a.jdl', '123'), origem('p/b.jdl', '4567')]);
  igual(await ctx.parOpfsSobras(), []);
  presas.clear(); // o que acontece quando a página fecha
  igual(await ctx.parOpfsSobras(), [{ id: 'i1', arquivos: 2, bytes: 7, modificado_em: 1000 }]);
});

test('descartar: apaga a pasta, solta a trava e aguenta ser chamado de novo', async () => {
  const { ctx, raiz, presas } = ambiente();
  await ctx.parOpfsCopiar('i1', [origem('p/a.jdl', '123')]);
  await ctx.parOpfsDescartar('i1');
  assert.strictEqual(raiz.filhos.get('paralelismo').filhos.has('i1'), false);
  await espera();
  assert.strictEqual(presas.size, 0);
  await ctx.parOpfsDescartar('i1');
});

// ── parPlanoDoItem ─────────────────────────────────────────────────────
const JDL = (caminho, cod_faz, extra = {}) => ({ caminho, opfs: `o-${caminho}`, bytes: 10, data: '2026-10-10', cod_faz, ...extra });
const grupo = (arquivos, extra = {}) => ({ frota: '90001', operacao: 'torta', arquivos, ...extra });

test('plano: separa por fazenda e frota, com os arquivos em ordem de caminho', () => {
  const { ctx } = ambiente();
  const r = ctx.parPlanoDoItem([
    grupo([JDL('b/2.jdl', 99999), JDL('a/1.jdl', 99999), JDL('c.jdl', 88888)]),
    grupo([JDL('d.jdl', 99999)], { frota: '90000' }),
    grupo([JDL('e.jdl', 99999)], { frota: '90002', operacao: 'cana' }),
  ], []);
  const item = (caminho) => ({ tipo: 'jdl', caminho, opfs: `o-${caminho}`, opfs_fdd: null, data: '2026-10-10', bytes: 10 });
  igual(r, {
    fazendas: [
      { operacao: 'cana', cod_faz: 99999, grupos: [{ frota: '90002', arquivos: [item('e.jdl')] }] },
      { operacao: 'torta', cod_faz: 88888, grupos: [{ frota: '90001', arquivos: [item('c.jdl')] }] },
      { operacao: 'torta', cod_faz: 99999, grupos: [{ frota: '90000', arquivos: [item('d.jdl')] }, { frota: '90001', arquivos: [item('a/1.jdl'), item('b/2.jdl')] }] },
    ],
    pulados: [],
  });
});

test('plano: duas pastas da mesma frota viram um grupo só', () => {
  const { ctx } = ambiente();
  const r = ctx.parPlanoDoItem([grupo([JDL('a.jdl', 99999)]), grupo([JDL('b.jdl', 99999)])], []);
  assert.strictEqual(r.fazendas[0].grupos.length, 1);
  assert.strictEqual(r.fazendas[0].grupos[0].arquivos.length, 2);
});

test('plano: .fdl leva o .fdd ao lado e soma os bytes', () => {
  const { ctx } = ambiente();
  const fdl = JDL('p/s.fdl', 99999), fdd = JDL('p/s.fdd', null, { bytes: 90 });
  const r = ctx.parPlanoDoItem([grupo([fdl, fdd])], [fdl, fdd]);
  igual(r.fazendas[0].grupos[0].arquivos, [{ tipo: 'gs3', caminho: 'p/s.fdl', opfs: 'o-p/s.fdl', opfs_fdd: 'o-p/s.fdd', data: '2026-10-10', bytes: 100 }]);
  igual(r.pulados, []);
});

test('plano: .fdl novo com o .fdd já analisado acha o par na lista completa', () => {
  const { ctx } = ambiente();
  const fdl = JDL('p/s.fdl', 99999), fdd = JDL('p/s.fdd', null);
  const r = ctx.parPlanoDoItem([grupo([fdl])], [fdl, fdd]);
  assert.strictEqual(r.fazendas[0].grupos[0].arquivos[0].opfs_fdd, 'o-p/s.fdd');
});

test('plano: .fdd novo com o .fdl já analisado é listado, sem gerar análise', () => {
  const { ctx } = ambiente();
  const fdl = JDL('p/s.fdl', 99999), fdd = JDL('p/s.fdd', null);
  const r = ctx.parPlanoDoItem([grupo([fdd])], [fdl, fdd]);
  igual(r, { fazendas: [], pulados: [{ caminho: 'p/s.fdd', motivo: 'fdd_sem_fdl' }] });
});

test('plano: sem frota, sem fazenda e sem .fdd vão para os pulados', () => {
  const { ctx } = ambiente();
  const r = ctx.parPlanoDoItem([
    grupo([JDL('a.jdl', 99999)], { frota: null, operacao: null }),
    grupo([JDL('b.jdl', null), JDL('c.fdl', 99999)]),
  ], []);
  igual(r, { fazendas: [], pulados: [{ caminho: 'a.jdl', motivo: 'sem_frota' }, { caminho: 'b.jdl', motivo: 'sem_fazenda' }, { caminho: 'c.fdl', motivo: 'sem_fdd' }] });
});

test('plano: a ordem compara pasta por pasta, como o sorted do Python na regressão', () => {
  const { ctx } = ambiente();
  const r = ctx.parPlanoDoItem([grupo([JDL('x-y/1.jdl', 99999), JDL('x/1.jdl', 99999)])], []);
  igual(r.fazendas[0].grupos[0].arquivos.map((a) => a.caminho), ['x/1.jdl', 'x-y/1.jdl']);
});

// ── parCriarFila ───────────────────────────────────────────────────────
class WorkerFalso {
  constructor() { this.postados = []; this.encerrado = false; WorkerFalso.criados.push(this); }
  postMessage(m) { this.postados.push(m); }
  terminate() { this.encerrado = true; }
  responder(m) { this.onmessage({ data: m }); }
}

function fila({ buscarBase } = {}) {
  WorkerFalso.criados = [];
  const { ctx } = ambiente();
  const mudancas = [];
  const f = ctx.parCriarFila({
    criarWorker: () => new WorkerFalso(),
    buscarBase: buscarBase || (async (operacao, cod_faz) => ({ analise_id: cod_faz + 1, linhas: [{ frota: 'v' }], talhoes: { type: 'FeatureCollection', features: [] } })),
    aoMudar: (itens) => mudancas.push(puro(itens)),
  });
  return { f, ctx, mudancas };
}
const PLANO = { pulados: [{ caminho: 'x', motivo: 'sem_frota' }], fazendas: [{ operacao: 'torta', cod_faz: 99999, grupos: [{ frota: '90001', arquivos: [] }] }] };
const estados = (f) => f.itens().map((i) => [i.id, i.estado]);

test('fila: roda um por vez, na ordem, num único Worker', async () => {
  const { f } = fila();
  f.adicionar({ id: 'a', plano: PLANO });
  f.adicionar({ id: 'b', plano: PLANO });
  await espera();
  igual(estados(f), [['a', 'processando'], ['b', 'na_fila']]);
  const w = WorkerFalso.criados[0];
  assert.strictEqual(w.postados.length, 1);
  w.responder({ tipo: 'pronto', id: 'a', resultado: { id: 'a' } });
  await espera();
  igual(estados(f), [['a', 'pronto'], ['b', 'processando']]);
  assert.strictEqual(WorkerFalso.criados.length, 1);
  assert.strictEqual(w.postados.length, 2);
  igual(f.itens()[0].resultado, { id: 'a' });
});

test('fila: manda ao Worker a base de cada fazenda junto do plano', async () => {
  const { f } = fila();
  f.adicionar({ id: 'a', plano: PLANO });
  await espera();
  igual(WorkerFalso.criados[0].postados[0], {
    tipo: 'processar',
    item: {
      id: 'a', pulados: PLANO.pulados,
      fazendas: [{ ...PLANO.fazendas[0], base_analise_id: 100000, vigentes: [{ frota: 'v' }], talhoes: { type: 'FeatureCollection', features: [] } }],
    },
  });
});

test('fila: progresso atualiza o item; o de outro item é ignorado', async () => {
  const { f } = fila();
  f.adicionar({ id: 'a', plano: PLANO });
  await espera();
  const w = WorkerFalso.criados[0];
  w.responder({ tipo: 'progresso', id: 'a', fazenda: 99999, pct: 40, pct_item: 20, fase: 'lendo' });
  w.responder({ tipo: 'progresso', id: 'velho', fazenda: 1, pct: 99, pct_item: 99, fase: 'lendo' });
  const i = f.itens()[0];
  igual([i.fazenda, i.pct, i.pct_item, i.fase], [99999, 40, 20, 'lendo']);
});

test('fila: erro num item não para os seguintes e troca o Worker', async () => {
  const { f } = fila();
  f.adicionar({ id: 'a', plano: PLANO });
  f.adicionar({ id: 'b', plano: PLANO });
  await espera();
  const w = WorkerFalso.criados[0];
  w.responder({ tipo: 'erro', id: 'a', msg: 'quebrou' });
  await espera();
  assert.strictEqual(w.encerrado, true);
  igual(estados(f), [['a', 'erro'], ['b', 'processando']]);
  assert.strictEqual(f.itens()[0].erro, 'quebrou');
  assert.strictEqual(WorkerFalso.criados.length, 2);
});

test('fila: Worker que não sobe dá o texto da spec, e tentar de novo refaz o item', async () => {
  const { f } = fila();
  f.adicionar({ id: 'a', plano: PLANO });
  await espera();
  WorkerFalso.criados[0].onerror({ message: 'x' });
  await espera();
  assert.strictEqual(f.itens()[0].erro, 'Não foi possível preparar a análise; recarregue a página');
  f.tentarDeNovo('a');
  await espera();
  igual(estados(f), [['a', 'processando']]);
  assert.strictEqual(f.itens()[0].erro, null);
  assert.strictEqual(WorkerFalso.criados[1].postados.length, 1);
});

test('fila: falha ao buscar a base dá erro do item, nomeia a fazenda e segue', async () => {
  let n = 0;
  const { f } = fila({ buscarBase: async () => { if (!n++) throw new Error('rede'); return { analise_id: null, linhas: [], talhoes: {} }; } });
  f.adicionar({ id: 'a', plano: PLANO });
  f.adicionar({ id: 'b', plano: PLANO });
  await espera(); await espera();
  igual(estados(f), [['a', 'erro'], ['b', 'processando']]);
  assert.match(f.itens()[0].erro, /99999/);
});

test('fila: remover o que está rodando encerra o Worker, apaga a cópia e passa ao próximo', async () => {
  const { f, ctx } = fila();
  await ctx.parOpfsCopiar('a', [origem('p/a.jdl', '123')]);
  f.adicionar({ id: 'a', plano: PLANO });
  f.adicionar({ id: 'b', plano: PLANO });
  await espera();
  await f.remover('a');
  await espera();
  assert.strictEqual(WorkerFalso.criados[0].encerrado, true);
  igual(estados(f), [['b', 'processando']]);
  await assert.rejects(ctx.parOpfsLer('a', 'f000001.jdl'));
});

test('fila: remover enquanto busca a base não posta o item removido', async () => {
  let solta;
  const { f } = fila({ buscarBase: () => new Promise((ok) => { solta = ok; }) });
  f.adicionar({ id: 'a', plano: PLANO });
  await espera();
  await f.remover('a');
  solta({ analise_id: null, linhas: [], talhoes: {} });
  await espera();
  assert.strictEqual(WorkerFalso.criados.length, 0);
});

test('fila: remover um pronto não mexe no que está rodando', async () => {
  const { f } = fila();
  f.adicionar({ id: 'a', plano: PLANO });
  f.adicionar({ id: 'b', plano: PLANO });
  await espera();
  const w = WorkerFalso.criados[0];
  w.responder({ tipo: 'pronto', id: 'a', resultado: {} });
  await espera();
  await f.remover('a');
  assert.strictEqual(w.encerrado, false);
  igual(estados(f), [['b', 'processando']]);
});

test('fila: avisa cada mudança', async () => {
  const { f, mudancas } = fila();
  f.adicionar({ id: 'a', plano: PLANO });
  await espera();
  assert.ok(mudancas.length >= 1);
  assert.strictEqual(mudancas.at(-1)[0].estado, 'processando');
});

test('fila: item sem nenhuma fazenda termina pronto, sem subir o Pyodide', async () => {
  const { f } = fila();
  f.adicionar({ id: 'a', plano: { pulados: [{ caminho: 'x', motivo: 'sem_frota' }], fazendas: [] } });
  await espera();
  assert.strictEqual(WorkerFalso.criados.length, 0);
  igual(estados(f), [['a', 'pronto']]);
  igual(f.itens()[0].resultado, { id: 'a', pulados: [{ caminho: 'x', motivo: 'sem_frota' }], parciais: [], fazendas: [] });
});

test('fila: mensagem que não chega ao destino vira erro do item', async () => {
  const { f } = fila();
  f.adicionar({ id: 'a', plano: PLANO });
  await espera();
  WorkerFalso.criados[0].onmessageerror({});
  await espera();
  igual(estados(f), [['a', 'erro']]);
});
