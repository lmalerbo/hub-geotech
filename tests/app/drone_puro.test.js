// Funções puras da tela do Drone. Roda com: node --test tests/app/drone_puro.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');

const ctx = { document: {}, sb: {}, console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(__dirname + '/../../app/drone.js', 'utf8'), ctx);

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
