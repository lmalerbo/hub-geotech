// Gera app/apresentacao-demo.js a partir da fixture de tests/app/apresentacao/dados (dados fictícios).
// Uso, na raiz do repo: node tests/app/apresentacao/gerar_demo.js
const fs = require('fs');
const path = require('path');

const raiz = path.join(__dirname, '../../..');
const dados = path.join(__dirname, 'dados');
const ler = (n) => JSON.parse(fs.readFileSync(path.join(dados, n + '.json'), 'utf8'));

// Uma linha por item: legível no diff e sem JSON gigante numa linha só.
function lista(itens) {
  if (!itens.length) return '[]';
  return '[\n  ' + itens.map((i) => JSON.stringify(i)).join(',\n  ') + '\n]';
}

const hubTabelas = ['talhoes', 'colheita_talhoes', 'talhao_plantio', 'talhao_preparo', 'etapas', 'preparo_entregas'];
const hub = hubTabelas.map((t) => '  ' + t + ': ' + lista(ler(t)).replace(/\n/g, '\n  ')).join(',\n');

const saida = `// Apresentação semanal: dados fictícios do modo demonstração (file:// ou ?demo). Mesma fixture dos testes
// (tests/app/apresentacao/dados). Não há dado real aqui.
// Gerado por tests/app/apresentacao/gerar_demo.js. Não editar à mão.
var AP_DEMO_HUB = {
${hub}
};
var AP_DEMO_DRONE = ${lista(ler('drone'))};
var AP_DEMO_VOOS = ${JSON.stringify(ler('voos'), null, 1)};
var AP_DEMO_METAS = { meta_ervas_ha: 20863, meta_fornecedor_ha: 3500, meta_ha_dia: 250, drone_pendente_ha: 2000, safra_atual: '26/27', inicio_safra: '2026-04-01' };
`;

fs.writeFileSync(path.join(raiz, 'app', 'apresentacao-demo.js'), saida, 'utf8');
console.log('app/apresentacao-demo.js gerado (' + saida.length + ' bytes)');
