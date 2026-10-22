// Regras puras da tela Usuários. Roda com: node --test tests/app/usuarios_puro.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const vm = require('vm');

const ctx = { console };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(__dirname + '/../../app/usuarios.js', 'utf8'), ctx);

const mapa = { id: 7, nome: 'Voos', grupos: [{ grupoId: 1, podeEditar: false }, { grupoId: 2, podeEditar: true }] };

test('o que os grupos marcados dão num mapa', () => {
  assert.strictEqual(ctx.usrPelosGrupos(mapa, []), 'nada');
  assert.strictEqual(ctx.usrPelosGrupos(mapa, [1]), 'ver');
  assert.strictEqual(ctx.usrPelosGrupos(mapa, [1, 2]), 'editar');
});

test('individual só acrescenta: vale o maior', () => {
  assert.strictEqual(ctx.usrNivelFinal('editar', 'ver'), 'editar');
  assert.strictEqual(ctx.usrNivelFinal('ver', 'editar'), 'editar');
  assert.strictEqual(ctx.usrNivelFinal('nada', 'ver'), 'ver');
  assert.strictEqual(ctx.usrNivelFinal('ver', 'nada'), 'ver');
});

test('ciclo da coluna Individual: — → Ver → Ver e editar → —', () => {
  assert.strictEqual(ctx.usrProximoIndividual('nada'), 'ver');
  assert.strictEqual(ctx.usrProximoIndividual('ver'), 'editar');
  assert.strictEqual(ctx.usrProximoIndividual('editar'), 'nada');
});

test('mapas individuais: ida e volta entre a tela e hub.acessos', () => {
  const tela = ctx.usrMapasDoBanco([{ mapa_id: 7, pode_editar: true }, { mapa_id: 9, pode_editar: false }]);
  assert.deepStrictEqual({ ...tela }, { 7: 'editar', 9: 'ver' });
  // JSON: o objeto nasce no contexto do vm (outro realm) e deepStrictEqual compararia os protótipos.
  assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.usrMapasParaBanco({ 7: 'editar', 9: 'ver', 4: 'nada' }))),
    [{ mapa_id: 7, pode_editar: true }, { mapa_id: 9, pode_editar: false }]);
});

test('resumo da linha da lista', () => {
  const a = { niveis: { plantio: 'editor', preparo: 'leitura', drone: 'solicitante', corretivos: 'editor' },
              geomap_ativo: true, geomap_grupos: [1, 2], geomap_mapas: [{ mapa_id: 7, pode_editar: false }] };
  assert.strictEqual(ctx.usrResumo(a), 'Plantio (editor) · Preparo · Drone (solicitante) · GeoMap: 2 grupos + 1 mapa · Mapas de aplicação');
  assert.strictEqual(ctx.usrResumo({ admin: true, niveis: {} }), 'Admin do Hub');
  assert.strictEqual(ctx.usrResumo({ niveis: {}, geomap_ativo: true, geomap_admin: true, geomap_grupos: [] }), 'GeoMap (admin)');
  assert.strictEqual(ctx.usrResumo({ niveis: { plantio: 'editor' }, bloqueado: true }), 'Sem acesso — bloqueado');
  assert.strictEqual(ctx.usrResumo({ niveis: {} }), 'Sem acesso');
});

test('situação, sem supor gênero', () => {
  assert.deepStrictEqual([...ctx.usrSituacao({ conta_criada: false })], ['espera', 'Sem conta']);
  assert.deepStrictEqual([...ctx.usrSituacao({ conta_criada: true, bloqueado: true })], ['erro', 'Bloqueado']);
  assert.deepStrictEqual([...ctx.usrSituacao({ conta_criada: true, precisa_trocar_senha: true })], ['espera', 'Senha provisória']);
  assert.deepStrictEqual([...ctx.usrSituacao({ conta_criada: true })], ['espera', 'Ainda não entrou']);
  assert.deepStrictEqual([...ctx.usrSituacao({ conta_criada: true, ultimo_login: '2026-10-20T10:00:00Z' })], ['ok', 'Acesso ativo']);
});

test('filtro e busca', () => {
  const lista = [
    { nome: 'Ana Souza', email: 'ana@x.com', niveis: { plantio: 'editor' } },
    { nome: 'Bruno Lima', email: 'bruno@x.com', niveis: {}, geomap_ativo: true },
    { nome: 'Carla', email: 'carla@x.com', niveis: { drone: 'leitura' }, precisa_trocar_senha: true },
  ];
  const nomes = (l) => l.map((a) => a.nome);
  assert.deepStrictEqual(nomes(ctx.usrFiltrar(lista, 'todos', '')), ['Ana Souza', 'Bruno Lima', 'Carla']);
  assert.deepStrictEqual(nomes(ctx.usrFiltrar(lista, 'plantio', '')), ['Ana Souza']);
  assert.deepStrictEqual(nomes(ctx.usrFiltrar(lista, 'geomap', '')), ['Bruno Lima']);
  assert.deepStrictEqual(nomes(ctx.usrFiltrar(lista, 'provisoria', '')), ['Carla']);
  assert.deepStrictEqual(nomes(ctx.usrFiltrar(lista, 'todos', 'BRUNO')), ['Bruno Lima']);
  assert.deepStrictEqual(nomes(ctx.usrFiltrar(lista, 'todos', 'carla@')), ['Carla']);
});
