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
