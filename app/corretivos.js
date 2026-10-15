// ===== Corretivos: funções puras (testadas em tests/app/corretivos_puro.test.js) =====
// `var` (não const) para as constantes ficarem visíveis no contexto vm dos testes.
var CR_CORES = { 'calcario:dolomitico': '#2f6db5', 'calcario:ph7': '#22a39f', fosfato: '#e07b1a', blend: '#7b4fb3' };
var CR_SEM = '#e4e7e8';
var CR_OPERACOES = { subsolagem: 'SubSolagem', supergrade: 'SuperGrade', arado: 'Arado' };
var CR_CALC = { dolomitico: 'Dolomítico', ph7: 'PH7' };

function crBr(v) {
  return Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function crNum(s) { return typeof s === 'number' ? s : Number(String(s ?? '').trim().replace(/\./g, '').replace(',', '.')); }
function crTotal(area, dose) { return Math.round(area * dose * 100) / 100; }
function crChaveCor(ap) { return ap.tipo === 'calcario' ? 'calcario:' + ap.calcario : ap.tipo; }
function crRotulo(ap) {
  if (ap.tipo === 'calcario') return 'Calc. ' + CR_CALC[ap.calcario];
  if (ap.tipo === 'blend') return 'Blend · ' + CR_CALC[ap.calcario];
  return 'Fosfato';
}
function crOrdenadas(apls) { return [...apls].sort((a, b) => a.ordem - b.ordem); }
function crCoresTalhao(apls, talhao) {
  return crOrdenadas(apls).filter(a => a.talhoes.includes(talhao)).map(a => CR_CORES[crChaveCor(a)]);
}
function crTotaisPorProduto(apls, areas) {
  const soma = {};
  const area = a => a.talhoes.reduce((s, t) => s + Number(areas[t].area_ha), 0);
  for (const a of crOrdenadas(apls)) {
    if (a.tipo === 'blend') {
      const k = 'Blend ' + CR_CALC[a.calcario];
      const v = soma[k] || [0, 0];
      soma[k] = [v[0] + area(a) * a.dose, v[1] + area(a) * a.dose_gesso];
    } else {
      const k = a.tipo === 'fosfato' ? 'Fosfato' : 'Calcário ' + CR_CALC[a.calcario];
      soma[k] = [(soma[k] ? soma[k][0] : 0) + area(a) * a.dose];
    }
  }
  const r2 = v => Math.round(v * 100) / 100;
  return ['Calcário Dolomítico', 'Calcário PH7', 'Fosfato', 'Blend Dolomítico', 'Blend PH7'].filter(k => soma[k])
    .map(k => k.startsWith('Blend')
      ? { titulo: k, toneladas: r2(soma[k][0] + soma[k][1]), detalhe: `calc. ${crBr(soma[k][0])} t + gesso ${crBr(soma[k][1])} t` }
      : { titulo: k, toneladas: r2(soma[k][0]), detalhe: null });
}
function crValidarAplicacao(f) {
  if (!f.talhoes || !f.talhoes.length) return 'Marque ao menos um talhão no mapa.';
  if ((f.tipo === 'calcario' || f.tipo === 'blend') && !f.calcario) return 'Escolha o calcário (Dolomítico ou PH7).';
  if (!(crNum(f.dose) > 0)) return 'Dose deve ser maior que zero (t/ha).';
  if (f.tipo === 'blend' && !(crNum(f.dose_gesso) > 0)) return 'Informe a dose do gesso (t/ha).';
  if (!String(f.os ?? '').trim()) return 'Informe a O.S.';
  return null;
}
function crMesma(a, b) {
  return a.tipo === b.tipo && (a.calcario || null) === (b.calcario || null) && crNum(a.dose) === crNum(b.dose)
    && (a.dose_gesso == null ? null : crNum(a.dose_gesso)) === (b.dose_gesso == null ? null : crNum(b.dose_gesso))
    && String(a.os).trim() === String(b.os).trim();
}
function crDuplicadas(apls, nova, talhoes) {
  return talhoes.filter(t => apls.some(a => a.talhoes.includes(t) && crMesma(a, nova)));
}
function crTalhoesForaDaBase(areas, geo) {
  const naBase = new Set(geo.features.map(f => f.properties.talhao));
  return Object.keys(areas).map(Number).filter(t => !naBase.has(t)).sort((a, b) => a - b);
}
function crMontarDados(c) {
  const areas = {};
  for (const [t, v] of Object.entries(c.areas)) areas[String(t)] = { area_ha: Number(v.area_ha), editada: !!v.editada };
  return { cod_faz: c.codFaz, nome: c.nome, operacao: c.operacao, data: c.data, gerado_por: c.geradoPor,
           talhoes_geo: c.geo, areas,
           aplicacoes: crOrdenadas(c.apls).map(a => ({ tipo: a.tipo, calcario: a.calcario || null, dose: crNum(a.dose),
             dose_gesso: a.dose_gesso == null ? null : crNum(a.dose_gesso), os: String(a.os).trim(), ordem: a.ordem,
             talhoes: [...a.talhoes] })) };
}
function crNomeArquivo(codFaz, operacao, data) { return `corretivo_${codFaz}_${operacao}_${data}.pdf`; }
