// Funções puras da tela do Drone. Roda com: node --test tests/app/drone_puro.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');

const ctx = { document: {}, sb: {}, console };
vm.createContext(ctx);
for (const f of ['drone-dados', 'drone-previa', 'drone-inicio', 'drone-fazenda'])
  vm.runInContext(fs.readFileSync(__dirname + '/../../app/' + f + '.js', 'utf8'), ctx);

test('Catação pode gerar de novo depois de descartar ou dar erro', () => {
  assert.strictEqual(ctx.drPodeGerarCatacao({ status: 'solicitado' }), true);
  assert.strictEqual(ctx.drPodeGerarCatacao({ status: 'em_elaboracao' }), true);
  assert.strictEqual(ctx.drPodeGerarCatacao({ status: 'aguardando_infestacao' }), false);
  assert.strictEqual(ctx.drPodeGerarCatacao(null), false);
});

test('nome de arquivo seguro para o Storage (sem acento, mantém a classe)', () => {
  assert.strictEqual(ctx.drNomeSeguro('Obstáculos 15m (rede).shp'), 'Obstaculos_15m__rede_.shp');
  assert.strictEqual(ctx.drNomeSeguro('Infestação.ZIP'), 'Infestacao.ZIP');
  assert.strictEqual(ctx.drNomeSeguro('../x.shp'), '.._x.shp'.replace('..', '__'));
});

test('classe escolhida no envio de obstáculos', () => {
  assert.strictEqual(ctx.drClasseEscolhida('15'), 15);
  assert.strictEqual(ctx.drClasseEscolhida(' 50 m '), 50);
  assert.strictEqual(ctx.drClasseEscolhida(''), null);          // vazio = pelo nome do arquivo
  assert.strictEqual(ctx.drClasseEscolhida('30'), undefined);   // inválido
});

test('botão do shape de ajuste mostra o estado do envio', () => {
  assert.strictEqual(ctx.drRotuloShape(null), 'Enviar shape de ajuste');
  assert.strictEqual(ctx.drRotuloShape({ status: 'fila' }), 'Shape em processamento…');
  assert.strictEqual(ctx.drRotuloShape({ status: 'ok' }), 'Shape enviado ✓ (trocar)');
  assert.strictEqual(ctx.drRotuloShape({ status: 'erro' }), 'Erro no shape — enviar outro');
});

test('formulário de solicitação valida fazenda e data', () => {
  assert.strictEqual(ctx.drValidarSolicitacao({ cod: '', data: '' }), 'Escolha a fazenda.');
  assert.strictEqual(ctx.drValidarSolicitacao({ cod: '10008', data: '2000-01-01' }), 'A data desejada já passou.');
  assert.strictEqual(ctx.drValidarSolicitacao({ cod: '10008', data: '' }), null);
});

test('quem pode cancelar uma solicitação', () => {
  const editor = { id: 'e', role: 'editor', perms: { drone: true } };
  const solic = { id: 's', role: 'solicitante', perms: { drone: true } };
  const sol = { solicitante_id: 's', status: 'solicitado' };
  ctx.podeEditar = () => true;
  assert.strictEqual(ctx.drPodeCancelar(sol, null, editor), true);
  assert.strictEqual(ctx.drPodeCancelar(sol, { status: 'pronta' }, editor), true);
  assert.strictEqual(ctx.drPodeCancelar(sol, { status: 'processando' }, editor), false);         // agente trabalhando
  assert.strictEqual(ctx.drPodeCancelar(sol, { status: 'pronta', publicar_pedido_em: 'x' }, editor), false); // publicando
  ctx.podeEditar = () => false;
  assert.strictEqual(ctx.drPodeCancelar(sol, null, solic), true);                                 // a própria, sem prévia
  assert.strictEqual(ctx.drPodeCancelar(sol, { status: 'pronta' }, solic), false);              // já tem prévia
  assert.strictEqual(ctx.drPodeCancelar({ ...sol, solicitante_id: 'outro' }, null, solic), false); // de outra pessoa
});

test('último envio de um tipo: erro antigo não vale depois de um envio novo ok', () => {
  const envios = [   // do mais novo para o mais antigo, como vem do banco
    { id: 9, tipo: 'ajuste', status: 'erro' },
    { id: 8, tipo: 'obstaculos', status: 'ok' },
    { id: 7, tipo: 'obstaculos', status: 'erro' },
  ];
  assert.strictEqual(ctx.drUltimoEnvio(envios, 'obstaculos').id, 8);
  assert.strictEqual(ctx.drUltimoEnvio(envios, 'ajuste').id, 9);
  assert.strictEqual(ctx.drUltimoEnvio(envios, 'infestacao'), null);
  assert.strictEqual(ctx.drUltimoEnvio(null, 'obstaculos'), null);
});

test('assinatura dos obstáculos muda quando chega versão nova (descarta o desenho guardado)', () => {
  const a = ctx.drAssinaturaObst([{ classe_m: 25, versao: 1 }, { classe_m: 15, versao: 1 }]);
  const b = ctx.drAssinaturaObst([{ classe_m: 15, versao: 1 }, { classe_m: 25, versao: 1 }]);
  const c = ctx.drAssinaturaObst([{ classe_m: 15, versao: 2 }, { classe_m: 25, versao: 1 }]);
  assert.strictEqual(a, '15:1|25:1');
  assert.strictEqual(a, b);            // a ordem não importa
  assert.notStrictEqual(a, c);         // versão nova muda a assinatura
  assert.strictEqual(ctx.drAssinaturaObst([]), '');
  assert.strictEqual(ctx.drAssinaturaObst(null), '');
});

test('mapa é reaproveitado só se a fazenda/documento é o mesmo e o mapa existe', () => {
  assert.strictEqual(ctx.drMapaReaproveitavel('10372|normal', '10372|normal', true), true);
  assert.strictEqual(ctx.drMapaReaproveitavel('10372|normal', '10372|catacao', true), false);
  assert.strictEqual(ctx.drMapaReaproveitavel('10372|normal', '10156|normal', true), false);
  assert.strictEqual(ctx.drMapaReaproveitavel('10372|normal', '10372|normal', false), false);
  assert.strictEqual(ctx.drMapaReaproveitavel(undefined, '10372|normal', true), false);
});

test('assinaturas: painel ignora enviado_em e muda com o status da geração', () => {
  const geo = { normal: { revisao: 2 }, catacao: null, cobertura_pct: 100,
    features: [{ properties: { camada: 'talhao', talhao: 1, status: 'ok', area_ha: 10 }, geometry: null }] };
  const info = { faz: { cod_faz: 1, nome: 'X' }, sols: [], obst: [{ classe_m: 15, versao: 1 }], revs: [],
    ger: [{ id: 5, status: 'fila' }], envios: [{ id: 1, tipo: 'obstaculos', status: 'ok', enviado_em: '2026-10-01' }] };
  const a = ctx.drAssinaturas(info, geo, 'normal');
  const b = ctx.drAssinaturas({ ...info, envios: [{ ...info.envios[0], enviado_em: '2026-10-02' }] }, geo, 'normal');
  assert.strictEqual(a.painel, b.painel);
  const c = ctx.drAssinaturas({ ...info, ger: [{ id: 5, status: 'processando' }] }, geo, 'normal');
  assert.notStrictEqual(a.painel, c.painel);
  assert.strictEqual(a.mapa, c.mapa);
  assert.notStrictEqual(a.mapa, ctx.drAssinaturas(info, geo, 'catacao').mapa);
  assert.deepStrictEqual(Object.keys(a).sort(), ['cab', 'mapa', 'obst', 'painel']);
});

test('partes mudadas: tudo na primeira vez, só o que mudou depois', () => {
  const x = { cab: '1', painel: '2', obst: '3', mapa: '4' };
  assert.deepStrictEqual([...ctx.drPartesMudadas(null, x)], ['cab', 'painel', 'obst', 'mapa']);
  assert.deepStrictEqual([...ctx.drPartesMudadas(x, { ...x, painel: '9' })], ['painel']);
  assert.deepStrictEqual([...ctx.drPartesMudadas(x, { ...x })], []);
});

test('resposta de outra fazenda é descartada', () => {
  assert.strictEqual(ctx.drRespostaValida(10372, 10156), false);
  assert.strictEqual(ctx.drRespostaValida(10372, 10372), true);
});

test('ocupado: geração em andamento, publicação pedida ou envio na fila', () => {
  const info = { envios: [] };
  assert.strictEqual(ctx.drOcupado(info, null), false);
  assert.strictEqual(ctx.drOcupado(info, { status: 'fila' }), true);
  assert.strictEqual(ctx.drOcupado(info, { status: 'processando' }), true);
  assert.strictEqual(ctx.drOcupado(info, { status: 'pronta' }), false);
  assert.strictEqual(ctx.drOcupado(info, { status: 'pronta', publicar_pedido_em: 'x' }), true);
  assert.strictEqual(ctx.drOcupado(info, { status: 'pronta', publicar_pedido_em: 'x', publicacao_erro: 'e' }), false);
  assert.strictEqual(ctx.drOcupado({ envios: [{ status: 'processando' }] }, null), true);
});

test('talhões em geração saem do escopo, só com a geração em andamento', () => {
  const esc = { incluir: [{ talhao: 3, fonte: 'sistema' }, { talhao: 7, fonte: 'shape' }], remover: [9] };
  assert.deepStrictEqual([...ctx.drTalhoesGerando({ status: 'processando', escopo: esc })], [3, 7]);
  assert.deepStrictEqual([...ctx.drTalhoesGerando({ status: 'pronta', escopo: esc })], []);
  assert.deepStrictEqual([...ctx.drTalhoesGerando({ status: 'fila', escopo: null })], []);   // Catação
  assert.deepStrictEqual([...ctx.drTalhoesGerando(null)], []);
});

test('polling: um timer só, para e pausa com a aba oculta ou fora da tela', () => {
  const timers = new Map(); let seq = 0;
  const c = { console, sb: {}, document: { visibilityState: 'visible' },
    setTimeout: (f, ms) => { timers.set(++seq, f); return seq; }, clearTimeout: id => timers.delete(id) };
  vm.createContext(c);
  vm.runInContext(fs.readFileSync(__dirname + '/../../app/drone-dados.js', 'utf8'), c);
  let n = 0; const fn = () => n++;
  c.drPollIniciar(fn, 5000); c.drPollIniciar(fn, 5000);
  assert.strictEqual(timers.size, 1);
  c.drPollParar(); assert.strictEqual(timers.size, 0);
  c.document.visibilityState = 'hidden'; c.drPollIniciar(fn, 5000);
  assert.strictEqual(timers.size, 0);                       // aba oculta: não agenda
  c.document.visibilityState = 'visible'; c.drPollAgendar();
  assert.strictEqual(timers.size, 1);                       // voltou: retoma
  c.drPollVisivel(false); assert.strictEqual(timers.size, 0); // saiu da view drone
  c.drPollVisivel(true); assert.strictEqual(timers.size, 1);
  const [id, f] = [...timers][0]; timers.delete(id); f();   // dispara como o navegador: o timer some
  assert.strictEqual(n, 1);
  assert.strictEqual(timers.size, 0);                       // roda uma vez; só reagenda se fn chamar drPollIniciar de novo
});
