// ===== Corretivos: funções puras (testadas em tests/app/corretivos_puro.test.js) =====
// `var` (não const) para as constantes ficarem visíveis no contexto vm dos testes.
var CR_CORES = { 'calcario:dolomitico': '#2f6db5', 'calcario:ph7': '#22a39f', fosfato: '#e07b1a', blend: '#7b4fb3' };
var CR_SEM = '#e4e7e8';
var CR_OPERACOES = { subsolagem: 'SubSolagem', supergrade: 'SuperGrade', arado: 'Arado', aerea: 'Aplicação aérea' };
var CR_CALC = { dolomitico: 'Dolomítico', ph7: 'PH7' };
// Aplicação aérea (iguais a mapas/corretivo_dados.py): cores dos insumos na ordem em que aparecem; margem de 5%.
var CR_PALETA_INSUMOS = ['#2f6db5', '#e07b1a', '#22a39f', '#7b4fb3', '#c23b3b', '#8a6d1f', '#2e8b57', '#d4558f', '#5b6770', '#b59a00'];
var CR_MARGEM = 0.05;
var CR_UNIDADE = { L: 'L', KG: 'kg' };

function crBr(v) {
  return Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function crNum(s) { return typeof s === 'number' ? s : Number(String(s ?? '').trim().replace(/\./g, '').replace(',', '.')); }
function crTotal(area, dose) { return Math.round(area * dose * 100) / 100; }
function crAerea(operacao) { return operacao === 'aerea'; }
// Dose com 2 casas, ou 3 quando a terceira importa (0,008 kg/ha).
function crBrDose(v) {
  const s = Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  return s.endsWith('0') ? s.slice(0, -1) : s;
}
// 'INSETICIDA BOUVERIZ WP PR' -> 'Inseticida Bouveriz WP PR' (siglas de até 3 letras ficam como estão; igual a str.title).
function crNomeInsumo(nome) {
  return String(nome ?? '').split(/\s+/).filter(Boolean)
    .map(p => p.length <= 3 ? p : p.toLowerCase().replace(/(^|[^a-zà-ÿ])([a-zà-ÿ])/g, (m, a, b) => a + b.toUpperCase())).join(' ');
}
function crUnidade(ap) { return ap.tipo === 'insumo' ? CR_UNIDADE[ap.insumo_unidade] : 't'; }
function crChaveCor(ap) {
  if (ap.tipo === 'insumo') return 'insumo:' + ap.insumo_nome;
  return ap.tipo === 'calcario' ? 'calcario:' + ap.calcario : ap.tipo;
}
function crCoresDoMapa(apls) {
  const cores = {};
  let n = 0;
  for (const a of crOrdenadas(apls)) {
    const k = crChaveCor(a);
    if (k in cores) continue;
    cores[k] = a.tipo === 'insumo' ? CR_PALETA_INSUMOS[n++ % CR_PALETA_INSUMOS.length] : CR_CORES[k];
  }
  return cores;
}
function crMargem(areas, operacao) {
  if (!crAerea(operacao)) return 0;
  const soma = Object.values(areas).reduce((s, v) => s + Number(v.area_ha), 0);
  return Math.round(soma * CR_MARGEM * 100) / 100;
}
function crAreaTotal(areas, operacao) {
  const soma = Object.values(areas).reduce((s, v) => s + Number(v.area_ha), 0);
  return Math.round((soma + crMargem(areas, operacao)) * 100) / 100;
}
function crRotulo(ap) {
  if (ap.tipo === 'insumo') return crNomeInsumo(ap.insumo_nome);
  if (ap.tipo === 'calcario') return 'Calc. ' + CR_CALC[ap.calcario];
  if (ap.tipo === 'blend') return 'Blend · ' + CR_CALC[ap.calcario];
  return 'Fosfato';
}
function crOrdenadas(apls) { return [...apls].sort((a, b) => a.ordem - b.ordem); }
function crCoresTalhao(apls, talhao) {
  const cores = crCoresDoMapa(apls);
  return crOrdenadas(apls).filter(a => a.talhoes.includes(talhao)).map(a => cores[crChaveCor(a)]);
}
function crTotaisPorProduto(apls, areas, operacao) {
  const soma = {};
  const area = a => a.talhoes.reduce((s, t) => s + Number(areas[t].area_ha), 0);
  const r2 = v => Math.round(v * 100) / 100;
  if (crAerea(operacao)) {                       // um quadro por insumo: dose × área dos talhões dele × 1,05
    const ordem = [];
    for (const a of crOrdenadas(apls)) {
      if (!soma[a.insumo_nome]) { soma[a.insumo_nome] = [0, crUnidade(a)]; ordem.push(a.insumo_nome); }
      soma[a.insumo_nome][0] += area(a) * (1 + CR_MARGEM) * a.dose;
    }
    return ordem.map(n => ({ titulo: crNomeInsumo(n), total: r2(soma[n][0]), unidade: soma[n][1], detalhe: null }));
  }
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
  return ['Calcário Dolomítico', 'Calcário PH7', 'Fosfato', 'Blend Dolomítico', 'Blend PH7'].filter(k => soma[k])
    .map(k => k.startsWith('Blend')
      ? { titulo: k, total: r2(soma[k][0] + soma[k][1]), unidade: 't', detalhe: `calc. ${crBr(soma[k][0])} t + gesso ${crBr(soma[k][1])} t` }
      : { titulo: k, total: r2(soma[k][0]), unidade: 't', detalhe: null });
}
function crValidarAplicacao(f) {
  if (!f.talhoes || !f.talhoes.length) return 'Marque ao menos um talhão no mapa.';
  if (f.tipo === 'insumo') {
    if (!f.insumo_id) return 'Escolha o insumo.';
    if (!(crNum(f.dose) > 0)) return 'Dose deve ser maior que zero.';
    if (!String(f.os ?? '').trim()) return 'Informe a O.S.';
    return null;
  }
  if ((f.tipo === 'calcario' || f.tipo === 'blend') && !f.calcario) return 'Escolha o calcário (Dolomítico ou PH7).';
  if (!(crNum(f.dose) > 0)) return 'Dose deve ser maior que zero (t/ha).';
  if (f.tipo === 'blend' && !(crNum(f.dose_gesso) > 0)) return 'Informe a dose do gesso (t/ha).';
  if (!String(f.os ?? '').trim()) return 'Informe a O.S.';
  return null;
}
function crMesma(a, b) {
  return a.tipo === b.tipo && (a.calcario || null) === (b.calcario || null) && crNum(a.dose) === crNum(b.dose)
    && (a.dose_gesso == null ? null : crNum(a.dose_gesso)) === (b.dose_gesso == null ? null : crNum(b.dose_gesso))
    && String(a.os).trim() === String(b.os).trim() && (a.insumo_id ?? null) === (b.insumo_id ?? null);
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
  const hoje = new Date();
  const geradoEm = c.geradoEm || [hoje.getFullYear(), String(hoje.getMonth() + 1).padStart(2, '0'),
                                  String(hoje.getDate()).padStart(2, '0')].join('-');   // data local, não UTC
  return { cod_faz: c.codFaz, nome: c.nome, operacao: c.operacao, data: c.data, gerado_por: c.geradoPor, gerado_em: geradoEm,
           talhoes_geo: c.geo, areas,
           aplicacoes: crOrdenadas(c.apls).map(a => ({ tipo: a.tipo, calcario: a.calcario || null, dose: crNum(a.dose),
             dose_gesso: a.dose_gesso == null ? null : crNum(a.dose_gesso), os: String(a.os).trim(), ordem: a.ordem,
             talhoes: [...a.talhoes],
             ...(a.tipo === 'insumo' ? { insumo_nome: a.insumo_nome, insumo_unidade: a.insumo_unidade } : {}) })) };
}
function crNomeArquivo(codFaz, operacao, data) {
  return crAerea(operacao) ? `aplicacao_aerea_${codFaz}_${data}.pdf` : `corretivo_${codFaz}_${operacao}_${data}.pdf`;
}

// ── Layout (27/10): textos e contas das telas, sem DOM ──
// Lista de talhões para textos: '11', '11 e 12', '11, 12 e 14'; acima de max, '1, 2, 3, 4, 5, 6 e mais 4'.
function crListaTalhoes(ts, max = 6) {
  const o = [...ts].sort((a, b) => a - b);
  if (o.length <= 1) return o.join('');
  if (o.length > max) return `${o.slice(0, max).join(', ')} e mais ${o.length - max}`;
  return `${o.slice(0, -1).join(', ')} e ${o[o.length - 1]}`;
}
function crSemAplicacao(talhoes, apls) {
  const com = new Set(apls.flatMap(a => a.talhoes));
  return talhoes.filter(t => !com.has(t)).sort((a, b) => a - b);
}
function crTextoDose(a) {
  if (a.tipo === 'insumo') return `${crBrDose(a.dose)} ${crUnidade(a)}/ha`;
  return `${crBr(a.dose)} t/ha` + (a.tipo === 'blend' ? ` + gesso ${crBr(a.dose_gesso)} t/ha` : '');
}
// Total previsto da nova aplicação, com a mesma conta do cartão (crTotalApl). null enquanto a dose não vale.
// Os campos vêm de <input type="number"> (ponto decimal), por isso Number e não crNum.
function crPrevisto(f, aerea, talhoes, areas) {
  const dose = Number(f.dose);
  if (!(dose > 0) || !talhoes.length) return null;
  const tipo = aerea ? 'insumo' : f.tipo;
  const gesso = tipo === 'blend' ? Number(f.gesso) : 0;
  if (tipo === 'blend' && !(gesso > 0)) return null;
  return crTotalApl({ tipo, dose, dose_gesso: gesso, talhoes }, areas);
}
function crDicaTalhao(t, areaHa, apls, marcado) {
  const doTalhao = crOrdenadas(apls).filter(a => a.talhoes.includes(t));
  return {
    titulo: `Talhão ${t}, ${crBr(areaHa)} ha`,
    linhas: doTalhao.length ? doTalhao.map(a => `${crRotulo(a)} ${crTextoDose(a)}, O.S. ${a.os}`) : ['Sem aplicação'],
    acao: marcado ? 'Clique para desmarcar' : 'Clique para marcar',
  };
}
// "Abertos por último": o texto guardado no navegador pode estar vazio ou estragado.
function crLerRecentes(texto) {
  try {
    const v = JSON.parse(texto || '[]');
    return Array.isArray(v) ? v.filter(r => r && r.id != null && r.cod_faz != null) : [];
  } catch (e) {
    return [];
  }
}
function crRecentesCom(lista, item, max = 3) {
  return [item, ...lista.filter(r => String(r.id) !== String(item.id))].slice(0, max);
}
function crRecentesSem(lista, id) { return lista.filter(r => String(r.id) !== String(id)); }

// ===== Corretivos: meio a meio por geometria (faixas diagonais) =====
// crFaixas corta um talhão em n faixas por retas x+y = constante, igualmente espaçadas entre min e max de x+y.
// Sutherland–Hodgman contra os dois semiplanos de cada faixa; externo e furos são recortados separadamente.
function crFaixas(geometria, n) {
  if (!(n > 1)) return [geometria];
  const poligonos = geometria.type === 'Polygon' ? [geometria.coordinates] : geometria.coordinates;
  let smin = Infinity, smax = -Infinity;
  for (const pol of poligonos) for (const anel of pol) for (const p of anel) {
    if (p[0] + p[1] < smin) smin = p[0] + p[1];
    if (p[0] + p[1] > smax) smax = p[0] + p[1];
  }
  const faixas = [];
  for (let k = 0; k < n; k++) {
    const a = smin + (smax - smin) * k / n;
    const b = smin + (smax - smin) * (k + 1) / n;
    const pols = [];
    for (const pol of poligonos) {
      const externo = crRecortarAnel(pol[0], a, b);
      if (!externo) continue;
      const furos = pol.slice(1).map(anel => crRecortarAnel(anel, a, b)).filter(Boolean);
      pols.push([externo, ...furos]);
    }
    faixas.push(pols.length === 1 ? { type: 'Polygon', coordinates: pols[0] } : { type: 'MultiPolygon', coordinates: pols });
  }
  return faixas;
}
function crRecortarAnel(anel, a, b) {
  const f = anel.length > 1 && anel[0][0] === anel[anel.length - 1][0] && anel[0][1] === anel[anel.length - 1][1];
  let pts = f ? anel.slice(0, -1) : anel.slice();
  pts = crCortarSemiplano(pts, p => p[0] + p[1] - a);
  pts = crCortarSemiplano(pts, p => b - (p[0] + p[1]));
  return pts.length >= 3 ? [...pts, pts[0]] : null;
}
function crCortarSemiplano(pts, dist) {
  const saida = [];
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const atual = pts[i], ant = pts[(i + n - 1) % n];
    const dA = dist(atual), dN = dist(ant);
    if (dA >= 0) {
      if (dN < 0) saida.push(crInterseccao(ant, atual, dN, dA));
      saida.push(atual);
    } else if (dN >= 0) {
      saida.push(crInterseccao(ant, atual, dN, dA));
    }
  }
  return saida;
}
function crInterseccao(p, q, dp, dq) {
  const t = dp / (dp - dq);
  return [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
}

// ===== Corretivos: acesso, API (real e demonstração) e telas =====
// As telas só são montadas quando há #cr-app no documento (o teste carrega este arquivo sem DOM).
function crEhDemo() {
  return location.protocol === 'file:' || (typeof URLSearchParams !== 'undefined' && new URLSearchParams(location.search).has('demo'));
}
const CR_DEMO = crEhDemo();
const CR_SB_URL = 'https://dpvsivypabmvmrrpgmhc.supabase.co';
const CR_SB_KEY = 'sb_publishable_3xv0R1kmhSXkoUh3i4vN0A_Q5oLBbVL';   // mesma chave pública do index.html
let CR_SB = null;
function crSb() {
  if (!CR_SB) CR_SB = window.supabase.createClient(CR_SB_URL, CR_SB_KEY, { db: { schema: 'hub' } });
  return CR_SB;
}
const CR_ST = { eu: null, fazendas: [], faz: null, mapas: [], trab: null, map: null, geo: null, det: null,
  sel: new Set(), destApl: null, areaNova: {}, form: null, formMsg: null, insumos: [], insEdit: null };
const CR_OP_VAR = { subsolagem: '--irrigacao', supergrade: '--plantio', arado: '--colheita', aerea: '--drones' };

function crEsc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function crNorm(s) { return String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
function crPad(n) { return String(n).padStart(2, '0'); }
function crHojeIso() { const d = new Date(); return `${d.getFullYear()}-${crPad(d.getMonth() + 1)}-${crPad(d.getDate())}`; }
function crDataIso(iso) { const [a, m, d] = String(iso).slice(0, 10).split('-'); return `${d}/${m}/${a}`; }
function crDiaMes(ts) { const d = new Date(ts); return `${crPad(d.getDate())}/${crPad(d.getMonth() + 1)}`; }

// Resumo do mapa no formato que as telas usam (mesmo formato de CR_DEMO_MAPAS).
function crResumoMapa(m, nomes) {
  const areas = {};
  for (const t of m.corretivo_talhoes || []) areas[t.talhao_num] = Number(t.area_ha);
  let total = 0;
  const insumos = new Set();
  for (const a of m.corretivo_aplicacoes || []) {
    if (a.tipo === 'insumo') { insumos.add(a.insumo_nome); continue; }   // L e kg não se somam
    const area = (a.corretivo_aplicacao_talhoes || []).reduce((s, x) => s + (areas[x.talhao_num] || 0), 0);
    total += area * Number(a.dose) + area * Number(a.dose_gesso || 0);
  }
  const os = [...new Set((m.corretivo_aplicacoes || []).map(a => String(a.os).trim()))].sort();
  return { id: m.id, operacao: m.operacao, data: m.data, os, talhoes: (m.corretivo_talhoes || []).length,
           toneladas: Math.round(total * 100) / 100, insumos: insumos.size,
           alterado_por_nome: nomes[m.alterado_por] || '—', alterado_em: m.alterado_em };
}
async function crNomesUsuarios(ids) {
  const unicos = [...new Set(ids)];
  if (!unicos.length) return {};
  const { data, error } = await crSb().from('usuarios').select('id,nome').in('id', unicos);
  if (error) throw error;
  return Object.fromEntries(data.map(u => [u.id, u.nome]));
}

const crApiReal = {
  async sessao() {
    const { data, error } = await crSb().auth.getSession();
    if (error) throw error;
    return data.session ? data.session.user : null;
  },
  async entrar(email, senha) {
    const { error } = await crSb().auth.signInWithPassword({ email, password: senha });
    if (!error) return;
    if (/banned/i.test(error.message)) throw new Error('Acesso bloqueado. Se o seu cadastro no GeoMap é novo, defina sua senha lá primeiro.');
    if (/invalid/i.test(error.message)) throw new Error('E-mail ou senha incorretos.');
    throw new Error('Não foi possível entrar agora. Tente de novo.');
  },
  async sair() {
    const { error } = await crSb().auth.signOut();
    if (error) throw error;
  },
  async eu() {
    const user = await crApiReal.sessao();
    if (!user) return null;
    const { data, error } = await crSb().from('usuarios').select('id,nome,admin,usuario_modulos(modulo_id)').eq('id', user.id).maybeSingle();
    if (error) throw error;
    if (!data) return null;
    const mods = (data.usuario_modulos || []).map(m => m.modulo_id);
    return { id: data.id, nome: data.nome, admin: !!data.admin, pode: !!data.admin || mods.includes('corretivos') };
  },
  async fazendas() {
    const { data, error } = await crSb().from('fazendas').select('cod_faz,nome').order('cod_faz');
    if (error) throw error;
    return data;
  },
  async mapas(codFaz) {
    const { data, error } = await crSb().from('corretivo_mapas')
      .select('id,operacao,data,alterado_por,alterado_em,corretivo_talhoes(talhao_num,area_ha),corretivo_aplicacoes(tipo,dose,dose_gesso,os,insumo_nome,corretivo_aplicacao_talhoes(talhao_num))')
      .eq('cod_faz', codFaz).order('data', { ascending: false }).order('id', { ascending: false });
    if (error) throw error;
    const nomes = await crNomesUsuarios(data.map(m => m.alterado_por).filter(Boolean));
    return data.map(m => crResumoMapa(m, nomes));
  },
  async criarMapa(codFaz, operacao) {
    const { data, error } = await crSb().from('corretivo_mapas').insert({ cod_faz: codFaz, operacao }).select('id').single();
    if (error) throw error;
    return data.id;
  },
  async excluirMapa(id) {
    const { error } = await crSb().from('corretivo_mapas').delete().eq('id', id);
    if (error) throw error;
  },
};

function crApi() { return CR_DEMO ? CR_API_DEMO : crApiReal; }

// ── Telas ──
function crMostrar(tela) {
  for (const t of ['carregando', 'login', 'sem-acesso', 'app']) document.getElementById('cr-' + t).classList.toggle('off', t !== tela);
}
function crTela(nome) {
  document.getElementById('cr-lista').classList.toggle('off', nome !== 'lista');
  document.getElementById('cr-trabalho').classList.toggle('off', nome !== 'trabalho');
}
function crToast(msg, erro = false) {
  const t = document.getElementById('cr-toast');
  t.textContent = msg;
  t.classList.toggle('erro', erro);
  t.classList.add('show');
  clearTimeout(crToast.timer);
  crToast.timer = setTimeout(() => t.classList.remove('show'), 2800);
}
// Diálogo simples: devolve o valor do botão escolhido (ou null ao fechar pelo fundo).
function crDialogo(titulo, texto, botoes) {
  return new Promise(resolver => {
    const fundo = document.getElementById('cr-modal-fundo');
    fundo.innerHTML = `<div class="cr-modal" role="dialog" aria-modal="true" aria-labelledby="cr-md-tit">
      <h3 id="cr-md-tit">${crEsc(titulo)}</h3><p>${crEsc(texto)}</p>
      <div class="cr-md-acoes">${botoes.map((b, i) => `<button class="${b.classe}" type="button" data-i="${i}">${crEsc(b.rotulo)}</button>`).join('')}</div>
    </div>`;
    const fechar = valor => { fundo.classList.add('off'); fundo.innerHTML = ''; resolver(valor); };
    fundo.onclick = e => { if (e.target === fundo) fechar(null); };
    fundo.querySelectorAll('button').forEach(b => { b.onclick = () => fechar(botoes[Number(b.dataset.i)].valor); });
    fundo.classList.remove('off');
    fundo.querySelector('button').focus();
  });
}

// ── Entrada: login, sessão e acesso ──
async function crEntrar(e) {
  e.preventDefault();
  const email = document.getElementById('cr-email').value.trim();
  const senha = document.getElementById('cr-senha').value;
  const erro = document.getElementById('cr-login-erro');
  const btn = document.getElementById('cr-entrar');
  erro.textContent = '';
  if (!email || !senha) { erro.textContent = 'Informe e-mail e senha.'; return; }
  btn.disabled = true;
  btn.textContent = 'Entrando…';
  try {
    await crApi().entrar(email, senha);
    document.getElementById('cr-senha').value = '';
    await crCarregarEntrada();
  } catch (err) {
    erro.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Entrar';
  }
}
async function crCarregarEntrada() {
  let eu;
  try {
    eu = await crApi().eu();
  } catch (e) {
    crMostrar('login');
    document.getElementById('cr-login-erro').textContent = 'Não foi possível verificar seu acesso. Tente de novo.';
    return;
  }
  CR_ST.eu = eu;
  if (!eu || !eu.pode) { crMostrar('sem-acesso'); return; }
  document.getElementById('cr-nome').textContent = eu.nome;
  if (!CR_DEMO && window.crGerador) {          // a 1ª carga do Python leva ~20 s: começa já, em segundo plano
    crGerador.aoMudar = () => { if (CR_ST.det) crRenderBotaoPdf(); };
    crGerador.preparar().catch(() => {});
  }
  crMostrar('app');
  crTela('lista');
  await crCarregarFazendas();
}
async function crSair() {
  try {
    await crApi().sair();
  } catch (e) {
    crToast('Não foi possível sair. Tente de novo.', true);
    return;
  }
  Object.assign(CR_ST, { eu: null, faz: null, mapas: [], trab: null });
  document.getElementById('cr-busca').value = '';
  document.getElementById('cr-pnl').classList.add('off');
  crMostrar('login');
}

// ── Busca de fazenda ──
async function crCarregarFazendas() {
  const res = document.getElementById('cr-res');
  res.innerHTML = '<div class="cr-esq curto" aria-hidden="true"></div>';
  try {
    CR_ST.fazendas = await crApi().fazendas();
  } catch (e) {
    res.innerHTML = '<div class="cr-msg cr-erro-bloco">Não foi possível carregar as fazendas.</div>'
      + '<div class="cr-msg"><button class="cr-btn2" type="button" id="cr-tentar-faz">Tentar de novo</button></div>';
    document.getElementById('cr-tentar-faz').onclick = crCarregarFazendas;
    return;
  }
  if (CR_DEMO && CR_ST.fazendas.length && !CR_ST.faz) crEscolherFazenda(CR_ST.fazendas[0], true);
  else crFiltrar();
}
function crFiltrar() {
  const res = document.getElementById('cr-res');
  const q = crNorm(document.getElementById('cr-busca').value.trim());
  if (!q) { res.innerHTML = '<div class="cr-msg">Digite o código ou o nome da fazenda.</div>'; return; }
  const achadas = CR_ST.fazendas.filter(f => String(f.cod_faz).startsWith(q) || crNorm(f.nome).includes(q)).slice(0, 30);
  res.innerHTML = achadas.length
    ? achadas.map(f => `<button class="cr-it" type="button" data-cod="${f.cod_faz}"><span class="cr-cod">${f.cod_faz}</span><span class="nm">${crEsc(f.nome)}</span></button>`).join('')
    : '<div class="cr-msg">Nenhuma fazenda encontrada.</div>';
}
async function crEscolherFazenda(f, abrirPrimeiro = false) {
  CR_ST.faz = f;
  document.getElementById('cr-busca').value = `${f.cod_faz} · ${f.nome}`;
  document.getElementById('cr-res').innerHTML = '';
  document.getElementById('cr-faz-nome').textContent = f.nome;
  document.getElementById('cr-faz-sub').textContent = `Código ${f.cod_faz}`;
  document.getElementById('cr-pnl').classList.remove('off');
  await crCarregarMapas();
  if (abrirPrimeiro && CR_DEMO && CR_ST.mapas.length) crAbrirMapa(CR_ST.mapas[0]);
}

// ── Lista de mapas ──
async function crCarregarMapas() {
  const alvo = document.getElementById('cr-mapas');
  const faz = CR_ST.faz;
  alvo.innerHTML = '<div class="cr-grid" aria-label="Carregando mapas"><div class="cr-esq"></div><div class="cr-esq"></div></div>';
  try {
    const mapas = await crApi().mapas(faz.cod_faz);
    if (CR_ST.faz !== faz) return;
    CR_ST.mapas = mapas;
    crRenderMapas();
  } catch (e) {
    if (CR_ST.faz !== faz) return;
    alvo.innerHTML = '<div class="cr-vazio"><span class="cr-erro-bloco">Não foi possível carregar os mapas.</span>'
      + '<button class="cr-btn2" type="button" data-tentar>Tentar de novo</button></div>';
  }
}
function crRenderMapas() {
  const alvo = document.getElementById('cr-mapas');
  if (!CR_ST.mapas.length) {
    alvo.innerHTML = '<div class="cr-vazio"><span class="ico">compost</span><span>Nenhum mapa nesta fazenda.</span>'
      + '<button class="cr-btn" type="button" data-novo><span class="ico">add</span> Novo mapa</button></div>';
    return;
  }
  alvo.innerHTML = `<div class="cr-grid">${CR_ST.mapas.map(crCardMapa).join('')}</div>`;
}
function crCardMapa(m) {
  const op = CR_OPERACOES[m.operacao] || m.operacao;
  const os = m.os.length ? m.os.join(', ') : '—';
  return `<article class="cr-mapa">
    <div class="cr-mapa-top">
      <span class="cr-op" style="--c:var(${CR_OP_VAR[m.operacao]})">${crEsc(op)}</span>
      <span class="cr-data">${crDataIso(m.data)}</span>
      <button class="cr-x" type="button" data-excluir="${m.id}" aria-label="Excluir mapa ${crEsc(op)} de ${crDataIso(m.data)}" title="Excluir mapa"><span class="ico">delete</span></button>
    </div>
    <div class="cr-os">O.S. ${crEsc(os)}</div>
    <div class="cr-stats">
      <div class="cr-stat"><small>Talhões</small><b>${m.talhoes}</b></div>
      ${crAerea(m.operacao)
        ? `<div class="cr-stat"><small>Insumos</small><b>${m.insumos}</b></div>`
        : `<div class="cr-stat"><small>Total</small><b>${crTon(m.toneladas)}</b></div>`}
    </div>
    <div class="cr-rod">alterado por ${crEsc(m.alterado_por_nome)} em ${crDiaMes(m.alterado_em)}</div>
    <button class="cr-btn2" type="button" data-abrir="${m.id}">Abrir mapa</button>
  </article>`;
}
async function crExcluir(id) {
  const m = CR_ST.mapas.find(x => String(x.id) === String(id));
  if (!m) return;
  const op = CR_OPERACOES[m.operacao] || m.operacao;
  const ok = await crDialogo('Excluir mapa', `Excluir o mapa ${op} de ${crDataIso(m.data)}? Isso não pode ser desfeito.`, [
    { rotulo: 'Cancelar', classe: 'cr-btn2', valor: false },
    { rotulo: 'Excluir', classe: 'cr-btn cr-btn-perigo', valor: true },
  ]);
  if (!ok) return;
  try {
    await crApi().excluirMapa(m.id);
  } catch (e) {
    crToast('Não foi possível excluir o mapa. Tente de novo.', true);
    return;
  }
  CR_ST.mapas = CR_ST.mapas.filter(x => x.id !== m.id);
  crRenderMapas();
  crToast('Mapa excluído.');
}
async function crNovoMapa() {
  const op = await crDialogo('Novo mapa', 'Escolha a operação do novo mapa.', [
    { rotulo: 'Cancelar', classe: 'cr-btn2', valor: null },
    { rotulo: 'SubSolagem', classe: 'cr-btn', valor: 'subsolagem' },
    { rotulo: 'SuperGrade', classe: 'cr-btn', valor: 'supergrade' },
    { rotulo: 'Arado', classe: 'cr-btn', valor: 'arado' },
    { rotulo: 'Aplicação aérea', classe: 'cr-btn', valor: 'aerea' },
  ]);
  if (!op) return;
  let id;
  try {
    id = await crApi().criarMapa(CR_ST.faz.cod_faz, op);
  } catch (e) {
    crToast('Não foi possível criar o mapa. Tente de novo.', true);
    return;
  }
  await crAbrirMapa({ id, operacao: op, data: crHojeIso() });
}

// ── Inicialização (só no navegador) ──
async function crIniciar() {
  document.getElementById('cr-form').onsubmit = crEntrar;
  document.getElementById('cr-busca').oninput = crFiltrar;
  document.getElementById('cr-res').onclick = e => {
    const b = e.target.closest('[data-cod]');
    const f = b && CR_ST.fazendas.find(x => String(x.cod_faz) === b.dataset.cod);
    if (f) crEscolherFazenda(f);
  };
  document.getElementById('cr-novo').onclick = crNovoMapa;
  crLigarTrabalho();
  document.getElementById('cr-mapas').onclick = e => {
    if (e.target.closest('[data-tentar]')) return crCarregarMapas();
    if (e.target.closest('[data-novo]')) return crNovoMapa();
    const a = e.target.closest('[data-abrir]');
    if (a) return crAbrirMapa(CR_ST.mapas.find(m => String(m.id) === a.dataset.abrir));
    const x = e.target.closest('[data-excluir]');
    if (x) crExcluir(x.dataset.excluir);
  };
  document.querySelectorAll('[data-sair]').forEach(b => { b.onclick = crSair; });
  document.getElementById('cr-demo').classList.toggle('off', !CR_DEMO);
  try {
    const user = await crApi().sessao();
    if (!user) { crMostrar('login'); return; }
    await crCarregarEntrada();
  } catch (e) {
    crMostrar('login');
  }
}
// ===== Corretivos: tela de trabalho (mapa, painel de aplicações) =====
// Persistência: cada ação chama crApi e recarrega o mapa (sem botão Salvar).

// Métodos reais da API de trabalho (tabelas hub.corretivo_*).
function crDetalheMapa(m) {
  const areas = {};
  for (const t of m.corretivo_talhoes || []) areas[t.talhao_num] = { area_ha: Number(t.area_ha), editada: !!t.area_editada };
  const apls = (m.corretivo_aplicacoes || []).map(a => ({
    id: a.id, tipo: a.tipo, calcario: a.calcario, dose: Number(a.dose),
    dose_gesso: a.dose_gesso == null ? null : Number(a.dose_gesso), os: String(a.os).trim(), ordem: a.ordem,
    insumo_id: a.insumo_id, insumo_nome: a.insumo_nome, insumo_unidade: a.insumo_unidade,
    talhoes: (a.corretivo_aplicacao_talhoes || []).map(x => x.talhao_num),
  }));
  return { id: m.id, cod_faz: m.cod_faz, operacao: m.operacao, data: m.data, areas, apls: crOrdenadas(apls) };
}
// Insere em corretivo_talhoes os talhões do mapa que ainda não existem (antes dos vínculos).
async function crInserirTalhoesFaltantes(mapaId, talhoes, areas) {
  const sb = crSb();
  const { data, error } = await sb.from('corretivo_talhoes').select('talhao_num').eq('mapa_id', mapaId);
  if (error) throw error;
  const existentes = new Set(data.map(t => t.talhao_num));
  const novos = talhoes.filter(t => !existentes.has(t))
    .map(t => ({ mapa_id: mapaId, talhao_num: t, area_ha: areas[t].area_ha, area_editada: !!areas[t].editada }));
  if (novos.length) {
    const { error: e } = await sb.from('corretivo_talhoes').insert(novos);
    if (e) throw e;
  }
}
// Remove do mapa os talhões de 'candidatos' que ficaram sem nenhuma aplicação.
async function crLimparOrfaos(mapaId, candidatos) {
  if (!candidatos.length) return;
  const sb = crSb();
  const { data, error } = await sb.from('corretivo_aplicacao_talhoes').select('talhao_num')
    .eq('mapa_id', mapaId).in('talhao_num', candidatos);
  if (error) throw error;
  const usados = new Set(data.map(v => v.talhao_num));
  const orfaos = candidatos.filter(t => !usados.has(t));
  if (orfaos.length) {
    const { error: e } = await sb.from('corretivo_talhoes').delete().eq('mapa_id', mapaId).in('talhao_num', orfaos);
    if (e) throw e;
  }
}
Object.assign(crApiReal, {
  async carregarMapa(id) {
    const { data, error } = await crSb().from('corretivo_mapas')
      .select('id,cod_faz,operacao,data,corretivo_talhoes(talhao_num,area_ha,area_editada),corretivo_aplicacoes(id,tipo,calcario,dose,dose_gesso,os,ordem,insumo_id,insumo_nome,insumo_unidade,corretivo_aplicacao_talhoes(talhao_num))')
      .eq('id', id).single();
    if (error) throw error;
    return crDetalheMapa(data);
  },
  async talhoesFazenda(codFaz) {
    const { data, error } = await crSb().rpc('corretivo_talhoes_fazenda', { p_cod_faz: codFaz });
    if (error) throw error;
    return data;
  },
  async salvarArea(mapaId, talhao, area) {
    const { error } = await crSb().from('corretivo_talhoes').update({ area_ha: area, area_editada: true })
      .eq('mapa_id', mapaId).eq('talhao_num', talhao);
    if (error) throw error;
  },
  // Aplicar, editar e excluir rodam no banco numa transação só (funções hub.corretivo_*), com trava por mapa:
  // ou grava tudo ou nada — sem aplicação órfã por duplo clique, falha no meio ou duas abas ao mesmo tempo.
  async aplicar(mapaId, p) {
    const { error } = await crSb().rpc('corretivo_aplicar', {
      p_mapa_id: mapaId,
      p_aplicacao: { tipo: p.tipo, calcario: p.calcario, dose: p.dose, dose_gesso: p.dose_gesso, os: p.os, insumo_id: p.insumo_id },
      p_talhoes: crTalhoesRpc(p.talhoes, p.areas),
    });
    if (error) throw error;
  },
  async editarAplicacao(mapaId, aplId, p) {
    const { error } = await crSb().rpc('corretivo_editar_aplicacao', {
      p_aplicacao_id: aplId,
      p_campos: { dose: p.dose, dose_gesso: p.dose_gesso, os: p.os },
      p_talhoes: crTalhoesRpc(p.talhoes, p.areas),
    });
    if (error) throw error;
  },
  async excluirAplicacao(mapaId, aplId) {
    const { error } = await crSb().rpc('corretivo_excluir_aplicacao', { p_aplicacao_id: aplId });
    if (error) throw error;
  },
});
function crTalhoesRpc(talhoes, areas) {
  return talhoes.map(t => ({ talhao_num: t, area_ha: Number(areas[t].area_ha), area_editada: !!areas[t].editada }));
}
// Cadastro de insumos (hub.insumos). Remover = ativo false: mapas antigos guardam nome e unidade próprios.
Object.assign(crApiReal, {
  async insumos() {
    const { data, error } = await crSb().from('insumos').select('id,codigo,nome,unidade,dose_sugerida,ativo')
      .eq('ativo', true).order('nome');
    if (error) throw error;
    return data;
  },
  async salvarInsumo(p) {
    const dados = { codigo: p.codigo, nome: String(p.nome).trim(), unidade: p.unidade, dose_sugerida: p.dose_sugerida };
    const sb = crSb().from('insumos');
    const { error } = p.id ? await sb.update(dados).eq('id', p.id) : await sb.insert(dados);
    if (error) {
      if (error.code === '23505') throw new Error(/codigo/i.test(error.message) ? 'Já existe um insumo com esse código.' : 'Já existe um insumo com esse nome.');
      throw error;
    }
  },
  async removerInsumo(id) {
    const { error } = await crSb().from('insumos').update({ ativo: false }).eq('id', id);
    if (error) throw error;
  },
});

// ── Cálculos da tela (usam as funções puras) ──
function crTon(v) { return crBr(v) + '\u00a0t'; }
function crSelecionados() { return Array.from(CR_ST.sel).sort((a, b) => a - b); }
function crTotalApl(a, areas) {
  // soma sem arredondar e arredonda uma vez no fim (igual ao Resumo e ao PDF); insumo leva a margem de 5%
  const fator = a.tipo === 'insumo' ? 1 + CR_MARGEM : 1;
  const t = a.talhoes.reduce((s, x) => {
    const ha = Number(areas[x] ? areas[x].area_ha : 0);
    return s + ha * fator * a.dose + (a.tipo === 'blend' ? ha * a.dose_gesso : 0);
  }, 0);
  return Math.round(t * 100) / 100;
}
function crAreaDe(t) {
  const feat = CR_ST.geo.features.find(f => f.properties.talhao === t);
  const padrao = Number(feat ? feat.properties.area_prod : 0);
  const atual = CR_ST.det.areas[t];
  if (atual) return { area_ha: atual.area_ha, editada: atual.editada };
  const nova = CR_ST.areaNova[t];
  if (nova != null) return { area_ha: nova, editada: nova !== padrao };
  return { area_ha: padrao, editada: false };
}

// ── Mapa ──
const CR_MAPA_ESTILO = {
  version: 8,
  glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
  sources: {},
  layers: [{ id: 'fundo', type: 'background', paint: { 'background-color': '#f7f8fa' } }],
};
// Duas fontes: 'cr-cor' (uma feição por faixa, com a cor da aplicação) e 'cr-tal' (talhão inteiro: contorno, número, seleção).
function crFeicoesMapa() {
  const { apls, areas } = CR_ST.det;
  const talhoes = [], cores = [];
  for (const f of CR_ST.geo.features) {
    const t = f.properties.talhao;
    talhoes.push({ type: 'Feature', geometry: f.geometry, properties: { talhao: t } });
    const cs = crCoresTalhao(apls, t);
    if (cs.length >= 2) {
      crFaixas(f.geometry, cs.length).forEach((g, i) => cores.push({ type: 'Feature', geometry: g, properties: { talhao: t, cor: cs[i] } }));
    } else {
      const cor = cs.length === 1 ? cs[0] : (areas[t] ? CR_SEM : '#ffffff');
      cores.push({ type: 'Feature', geometry: f.geometry, properties: { talhao: t, cor } });
    }
  }
  return {
    talhoes: { type: 'FeatureCollection', features: talhoes },
    cores: { type: 'FeatureCollection', features: cores },
  };
}
function crMapaCriar() {
  const m = new maplibregl.Map({ container: 'cr-mapa', attributionControl: false, style: CR_MAPA_ESTILO });
  CR_ST.map = m;
  m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  m.on('load', () => {
    const vazio = { type: 'FeatureCollection', features: [] };
    m.addSource('cr-cor', { type: 'geojson', data: vazio });
    m.addSource('cr-tal', { type: 'geojson', data: vazio, promoteId: 'talhao' });
    m.addLayer({ id: 'cr-fill', type: 'fill', source: 'cr-cor', paint: { 'fill-color': ['get', 'cor'] } });
    m.addLayer({ id: 'cr-linha', type: 'line', source: 'cr-tal', paint: {
      'line-color': ['case', ['boolean', ['feature-state', 'sel'], false], '#16a76b',
        ['boolean', ['feature-state', 'dest'], false], '#d4890a', '#1f2a30'],
      'line-width': ['case', ['any', ['boolean', ['feature-state', 'sel'], false],
        ['boolean', ['feature-state', 'dest'], false]], 3, 0.8] } });
    m.addLayer({ id: 'cr-num', type: 'symbol', source: 'cr-tal', layout: {
      'text-field': ['to-string', ['get', 'talhao']], 'text-font': ['Open Sans Semibold'], 'text-size': 11 },
      paint: { 'text-color': '#1f2a30', 'text-halo-color': '#fff', 'text-halo-width': 1.5 } });
    m.on('click', e => {
      const f = m.queryRenderedFeatures(e.point, { layers: ['cr-fill'] })[0];
      if (f) crToggleSel(f.properties.talhao);
    });
    m.on('mouseenter', 'cr-fill', () => { m.getCanvas().style.cursor = 'pointer'; });
    m.on('mouseleave', 'cr-fill', () => { m.getCanvas().style.cursor = ''; });
    crAtualizarMapa(true);
  });
}
function crAtualizarMapa(enquadrar = false) {
  const m = CR_ST.map;
  if (!m || !m.getSource('cr-tal') || !CR_ST.geo || !CR_ST.det) return;
  const { talhoes, cores } = crFeicoesMapa();
  m.getSource('cr-cor').setData(cores);
  m.getSource('cr-tal').setData(talhoes);
  crAtualizarEstados();
  if (enquadrar) {
    const b = new maplibregl.LngLatBounds();
    talhoes.features.forEach(f => (f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates)
      .forEach(p => p[0].forEach(c => b.extend(c))));
    if (!b.isEmpty()) m.fitBounds(b, { padding: 30, duration: 0 });
  }
}
// Seleção (sel) e destaque de aplicação (dest) como feature-state.
function crAtualizarEstados() {
  const m = CR_ST.map;
  if (!m || !m.getSource('cr-tal') || !CR_ST.geo || !CR_ST.det) return;
  const dest = new Set(CR_ST.destApl == null ? [] : (CR_ST.det.apls.find(a => a.id === CR_ST.destApl) || { talhoes: [] }).talhoes);
  for (const f of CR_ST.geo.features) {
    const t = f.properties.talhao;
    m.setFeatureState({ source: 'cr-tal', id: t }, { sel: CR_ST.sel.has(t), dest: dest.has(t) });
  }
}

// ── Abertura, recarga e navegação ──
async function crAbrirMapa(mapa) {
  if (!mapa) return;
  if (CR_ST.map) { CR_ST.map.remove(); CR_ST.map = null; }
  Object.assign(CR_ST, { trab: mapa, sel: new Set(), destApl: null, areaNova: {}, formMsg: null, det: null, geo: null, insumos: [],
    form: crAerea(mapa.operacao) ? { tipo: 'insumo', insumo_id: '', dose: '', os: '' }
      : { tipo: 'calcario', calcario: 'dolomitico', dose: '', gesso: '', os: '' } });
  document.getElementById('cr-trab-tit').textContent = `Mapa ${CR_OPERACOES[mapa.operacao]} · ${crDataIso(mapa.data)}`;
  crTela('trabalho');
  document.getElementById('cr-mapa').innerHTML = '<div class="cr-esq cr-mapa-esq" aria-hidden="true"></div>';
  document.getElementById('cr-painel').innerHTML = '<div class="cr-sec" role="status"><div class="cr-esq"></div><div class="cr-esq curto"></div></div>';
  try {
    const [geo, det, insumos] = await Promise.all([crApi().talhoesFazenda(CR_ST.faz.cod_faz), crApi().carregarMapa(mapa.id),
      crAerea(mapa.operacao) ? crApi().insumos() : Promise.resolve([])]);
    CR_ST.geo = geo;
    CR_ST.det = det;
    CR_ST.insumos = insumos;
  } catch (e) {
    document.getElementById('cr-mapa').innerHTML = '';
    document.getElementById('cr-painel').innerHTML = '<div class="cr-vazio"><span class="cr-erro-bloco">Não foi possível abrir o mapa.</span>'
      + '<button class="cr-btn2" type="button" data-tentar-trab>Tentar de novo</button></div>';
    return;
  }
  document.getElementById('cr-mapa').innerHTML = '';
  crMapaCriar();
  crRenderPainel();
}
// O painel mostra que está atualizando (Mo, modo discreto) até redesenhar.
async function crRecarregar() {
  const painel = document.getElementById('cr-painel');
  Mo.carregando(painel, { discreto: true });
  try {
    CR_ST.det = await crApi().carregarMapa(CR_ST.trab.id);
  } catch (e) {
    Mo.pronto(painel, { cascata: false });
    crToast('Não foi possível atualizar o mapa. Tente de novo.', true);
    return;
  }
  Mo.pronto(painel, { cascata: false });
  if (CR_ST.destApl != null && !CR_ST.det.apls.some(a => a.id === CR_ST.destApl)) CR_ST.destApl = null;
  crAtualizarMapa();
  crRenderPainel();
}
function crVoltarLista() {
  if (CR_ST.map) { CR_ST.map.remove(); CR_ST.map = null; }
  crTela('lista');
  crCarregarMapas();
}

// ── Seleção ──
function crToggleSel(t) {
  if (CR_ST.sel.has(t)) CR_ST.sel.delete(t); else CR_ST.sel.add(t);
  crAtualizarEstados();
  crRenderPainel();
}
function crSelecionarTodos() {
  CR_ST.sel = new Set(CR_ST.geo.features.map(f => f.properties.talhao));
  crAtualizarEstados();
  crRenderPainel();
}
function crLimparSel() {
  CR_ST.sel = new Set();
  crAtualizarEstados();
  crRenderPainel();
}
function crDestacar(id) {
  CR_ST.destApl = CR_ST.destApl === id ? null : id;
  crAtualizarEstados();
  crRenderPainel();
}

// ── Ações ──
async function crSalvarArea(t, valor) {
  const area = Number(valor);
  if (!(area > 0)) {
    crToast('Área deve ser maior que zero (ha).', true);
    return crRenderPainel();
  }
  if (!CR_ST.det.areas[t]) {
    CR_ST.areaNova[t] = area;
    return crRenderPainel();
  }
  const painel = document.getElementById('cr-painel');
  Mo.carregando(painel, { discreto: true });
  try {
    await crApi().salvarArea(CR_ST.trab.id, t, area);
  } catch (e) {
    Mo.pronto(painel, { cascata: false });
    crToast('Não foi possível salvar a área.', true);
    return;
  }
  await crRecarregar();
}
async function crAplicarMarcados() {
  if (CR_ST.gravando) return;                   // duplo clique: a segunda chamada é ignorada
  CR_ST.gravando = true;
  const fim = Mo.ocupado(document.querySelector('[data-aplicar]'), { texto: 'Gravando…' });
  let ok = false;
  try {
    ok = await crAplicarMarcadosAgora();
  } finally {
    CR_ST.gravando = false;
    fim(ok);   // se o painel já foi redesenhado, o botão antigo saiu da tela e isso não faz nada
  }
}
async function crAplicarMarcadosAgora() {
  const f = CR_ST.form;
  const talhoes = crSelecionados();
  const aerea = crAerea(CR_ST.trab.operacao);
  const ins = aerea ? CR_ST.insumos.find(i => String(i.id) === String(f.insumo_id)) : null;
  const dados = aerea ? {
    tipo: 'insumo', insumo_id: Number(f.insumo_id) || null, insumo_nome: ins ? ins.nome : null,
    insumo_unidade: ins ? ins.unidade : null, calcario: null, dose: Number(f.dose), dose_gesso: null,
    os: String(f.os ?? '').trim(), talhoes,
  } : {
    tipo: f.tipo,
    calcario: f.tipo === 'fosfato' ? null : f.calcario,
    dose: Number(f.dose),
    dose_gesso: f.tipo === 'blend' ? Number(f.gesso) : null,
    os: String(f.os ?? '').trim(),
    talhoes,
  };
  const erro = crValidarAplicacao(dados);
  if (erro) {
    CR_ST.formMsg = { tipo: 'erro', texto: erro };
    return crRenderPainel();
  }
  const dup = crDuplicadas(CR_ST.det.apls, dados, talhoes);
  const ok = talhoes.filter(t => !dup.includes(t));
  if (!ok.length) {
    CR_ST.formMsg = { tipo: 'erro', texto: `Os talhões ${dup.join(', ')} já têm esta aplicação.` };
    return crRenderPainel();
  }
  const areas = {};
  for (const t of ok) areas[t] = crAreaDe(t);
  try {
    await crApi().aplicar(CR_ST.trab.id, { ...dados, talhoes: ok, areas });
  } catch (e) {
    crToast('Não foi possível aplicar. Tente de novo.', true);
    return;
  }
  CR_ST.formMsg = dup.length ? { tipo: 'info', texto: `Os talhões ${dup.join(', ')} já têm esta aplicação. Gravei nos demais.` } : null;
  CR_ST.sel = new Set();
  CR_ST.areaNova = {};
  if (!dup.length) crToast('Aplicação gravada.');
  await crRecarregar();
  return true;
}
async function crEditarAplicacao(id) {
  const a = CR_ST.det.apls.find(x => x.id === id);
  if (!a) return;
  const blend = a.tipo === 'blend';
  const todos = [...new Set([...CR_ST.geo.features.map(f => f.properties.talhao), ...a.talhoes])].sort((x, y) => x - y);
  const fundo = document.getElementById('cr-modal-fundo');
  const fechar = () => { fundo.classList.add('off'); fundo.innerHTML = ''; };
  fundo.innerHTML = `<form class="cr-modal" role="dialog" aria-modal="true" aria-labelledby="cr-ed-tit">
    <h3 id="cr-ed-tit">Editar ${crEsc(crRotulo(a))}</h3>
    <div class="cr-form">
      <div><label class="cr-lbl" for="cr-ed-dose">${a.tipo === 'insumo' ? `Dose (${crUnidade(a)}/ha)` : 'Dose (t/ha)'}</label>
        <input class="cr-inp" id="cr-ed-dose" type="number" step="${a.tipo === 'insumo' ? '0.001' : '0.01'}" min="0" value="${a.dose}"></div>
      ${blend ? `<div><label class="cr-lbl" for="cr-ed-gesso">Dose do gesso (t/ha)</label>
        <input class="cr-inp" id="cr-ed-gesso" type="number" step="0.01" min="0" value="${a.dose_gesso}"></div>` : ''}
      <div><label class="cr-lbl" for="cr-ed-os">O.S.</label>
        <input class="cr-inp" id="cr-ed-os" type="text" value="${crEsc(a.os)}"></div>
      <fieldset class="cr-fs"><legend class="cr-lbl">Talhões</legend>
        <div class="cr-cks">${todos.map(t => `<label class="cr-ck"><input type="checkbox" value="${t}"${a.talhoes.includes(t) ? ' checked' : ''}> Talhão ${t}</label>`).join('')}</div>
      </fieldset>
      <p class="cr-erro" id="cr-ed-erro" role="alert"></p>
    </div>
    <div class="cr-md-acoes">
      <button class="cr-btn2" type="button" data-cancel>Cancelar</button>
      <button class="cr-btn" type="submit">Salvar</button>
    </div>
  </form>`;
  fundo.classList.remove('off');
  const form = fundo.querySelector('form');
  const erroEl = document.getElementById('cr-ed-erro');
  fundo.onclick = e => { if (e.target === fundo) fechar(); };
  form.querySelector('[data-cancel]').onclick = fechar;
  form.querySelector('input').focus();
  form.onsubmit = async e => {
    e.preventDefault();
    const talhoes = Array.from(form.querySelectorAll('input[type=checkbox]:checked')).map(c => Number(c.value));
    const dados = {
      tipo: a.tipo, calcario: a.calcario, insumo_id: a.insumo_id,
      dose: Number(document.getElementById('cr-ed-dose').value),
      dose_gesso: blend ? Number(document.getElementById('cr-ed-gesso').value) : null,
      os: document.getElementById('cr-ed-os').value.trim(), talhoes,
    };
    const erro = crValidarAplicacao(dados);
    if (erro) { erroEl.textContent = erro; return; }
    const dup = crDuplicadas(CR_ST.det.apls.filter(x => x.id !== a.id), dados, talhoes);
    if (dup.length) { erroEl.textContent = `Os talhões ${dup.join(', ')} já têm esta aplicação.`; return; }
    const areas = {};
    for (const t of talhoes) areas[t] = crAreaDe(t);
    const fim = Mo.ocupado(e.submitter || form.querySelector('[type=submit]'));
    try {
      await crApi().editarAplicacao(CR_ST.trab.id, a.id, { ...dados, areas });
    } catch (err) {
      fim(false);
      erroEl.textContent = 'Não foi possível salvar. Tente de novo.';
      return;
    }
    await fim(true);
    fechar();
    crToast('Aplicação atualizada.');
    await crRecarregar();
  };
}
async function crExcluirAplicacao(id) {
  const a = CR_ST.det.apls.find(x => x.id === id);
  if (!a) return;
  const ok = await crDialogo('Excluir aplicação', `Excluir a aplicação ${crRotulo(a)} (O.S. ${a.os}) dos talhões ${a.talhoes.join(', ')}? Isso não pode ser desfeito.`, [
    { rotulo: 'Cancelar', classe: 'cr-btn2', valor: false },
    { rotulo: 'Excluir', classe: 'cr-btn cr-btn-perigo', valor: true },
  ]);
  if (!ok) return;
  const painel = document.getElementById('cr-painel');
  Mo.carregando(painel, { discreto: true });
  try {
    await crApi().excluirAplicacao(CR_ST.trab.id, a.id);
  } catch (e) {
    Mo.pronto(painel, { cascata: false });
    crToast('Não foi possível excluir a aplicação. Tente de novo.', true);
    return;
  }
  if (CR_ST.destApl === a.id) CR_ST.destApl = null;
  crToast('Aplicação excluída.');
  await crRecarregar();
}

// ── Painel ──
function crCardAplicacao(a, areas, cores) {
  const cor = cores[crChaveCor(a)];
  const on = CR_ST.destApl === a.id;
  const un = crUnidade(a);
  const total = crTotalApl(a, areas);
  const doses = a.tipo === 'insumo'
    ? `dose ${crBrDose(a.dose)} ${un}/ha`
    : `dose ${crBr(a.dose)} t/ha` + (a.tipo === 'blend' ? ` · gesso ${crBr(a.dose_gesso)} t/ha` : '');
  const quanto = a.tipo === 'insumo' ? `${crBr(total)} ${un}` : crTon(total);
  return `<div class="cr-ap${on ? ' on' : ''}">
    <span class="cr-ap-sw" style="background:${cor}" aria-hidden="true"></span>
    <button class="cr-ap-main" type="button" data-dest="${a.id}" aria-pressed="${on}">
      <b>${crEsc(crRotulo(a))}</b>
      <small>${doses} · O.S. ${crEsc(a.os)}</small>
      <small>Talhões ${a.talhoes.slice().sort((x, y) => x - y).join(', ')} · ${quanto}</small>
    </button>
    <div class="cr-ap-acoes">
      <button class="cr-x" type="button" data-editar="${a.id}" aria-label="Editar ${crEsc(crRotulo(a))} O.S. ${crEsc(a.os)}" title="Editar"><span class="ico">edit</span></button>
      <button class="cr-x" type="button" data-excluir-apl="${a.id}" aria-label="Excluir ${crEsc(crRotulo(a))} O.S. ${crEsc(a.os)}" title="Excluir"><span class="ico">delete</span></button>
    </div>
  </div>`;
}
// Campos do formulário de corretivo (calcário, fosfato, blend).
function crCamposCorretivo(f) {
  const blend = f.tipo === 'blend';
  const calc = f.tipo !== 'fosfato';
  const tipos = [['calcario', 'Calcário'], ['fosfato', 'Fosfato'], ['blend', 'Blend']];
  return `<fieldset class="cr-fs">
        <legend class="cr-lbl">Tipo</legend>
        <div class="cr-seg">${tipos.map(([v, r]) => `<label class="cr-seg-o"><input type="radio" name="cr-tipo" value="${v}" data-tipo${f.tipo === v ? ' checked' : ''}><span>${r}</span></label>`).join('')}</div>
      </fieldset>
      ${calc ? `<div><label class="cr-lbl" for="cr-f-calc">Calcário</label>
        <select class="cr-inp" id="cr-f-calc" data-f="calcario">
          <option value="dolomitico"${f.calcario === 'dolomitico' ? ' selected' : ''}>Dolomítico</option>
          <option value="ph7"${f.calcario === 'ph7' ? ' selected' : ''}>PH7</option>
        </select></div>` : ''}
      <div><label class="cr-lbl" for="cr-f-dose">Dose (t/ha)</label>
        <input class="cr-inp" id="cr-f-dose" type="number" step="0.01" min="0" data-f="dose" value="${crEsc(f.dose)}"></div>
      ${blend ? `<div><label class="cr-lbl" for="cr-f-gesso">Dose do gesso (t/ha)</label>
        <input class="cr-inp" id="cr-f-gesso" type="number" step="0.01" min="0" data-f="gesso" value="${crEsc(f.gesso)}"></div>` : ''}`;
}
// Campos do formulário de aplicação aérea: insumo (com botão Insumos) e dose na unidade do insumo.
function crCamposAerea(f) {
  const ins = CR_ST.insumos.find(i => String(i.id) === String(f.insumo_id));
  const un = ins ? CR_UNIDADE[ins.unidade] : '';
  const opcoes = CR_ST.insumos.map(i => `<option value="${Number(i.id)}"${String(i.id) === String(f.insumo_id) ? ' selected' : ''}>${crEsc(`${crNomeInsumo(i.nome)} (${CR_UNIDADE[i.unidade]})`)}</option>`).join('');
  return `<div><label class="cr-lbl" for="cr-f-insumo">Insumo</label>
        <div class="cr-ins-linha">
          <select class="cr-inp" id="cr-f-insumo" data-f="insumo_id">
            <option value="">Escolha o insumo</option>${opcoes}
          </select>
          <button class="cr-btn2" type="button" data-insumos>Insumos</button>
        </div></div>
      <div><label class="cr-lbl" for="cr-f-dose">${un ? `Dose (${un}/ha)` : 'Dose/ha'}</label>
        <input class="cr-inp" id="cr-f-dose" type="number" step="0.001" min="0" data-f="dose" value="${crEsc(f.dose)}"></div>`;
}
// Linha de área do resumo (aérea): área dos talhões + 5% do talhão 400.
function crLinhaArea(areas, operacao) {
  const soma = Object.values(areas).reduce((s, v) => s + Number(v.area_ha), 0);
  return `<p class="cr-info">Área: ${crBr(soma)} ha + 5% (talhão 400: ${crBr(crMargem(areas, operacao))} ha) = ${crBr(crAreaTotal(areas, operacao))} ha</p>`;
}
function crRenderPainel() {
  const alvo = document.getElementById('cr-painel');
  if (!CR_ST.det || !CR_ST.geo) return;
  const { areas, apls } = CR_ST.det;
  const fora = crTalhoesForaDaBase(areas, CR_ST.geo);
  const sel = crSelecionados();
  const f = CR_ST.form;
  const aerea = crAerea(CR_ST.trab.operacao);
  const msg = CR_ST.formMsg ? `<p class="${CR_ST.formMsg.tipo === 'erro' ? 'cr-erro' : 'cr-info'}" role="${CR_ST.formMsg.tipo === 'erro' ? 'alert' : 'status'}">${crEsc(CR_ST.formMsg.texto)}</p>` : '';
  const cores = crCoresDoMapa(apls);
  const tot = crTotaisPorProduto(apls, areas, CR_ST.trab.operacao);
  alvo.innerHTML = `
    ${fora.length ? `<div class="cr-aviso" role="status"><span class="ico" aria-hidden="true">warning</span><span>Talhões que saíram da Base: ${fora.join(', ')}. Eles continuam no PDF, sem desenho.</span></div>` : ''}
    <section class="cr-sec" aria-labelledby="cr-h-nova">
      <div class="cr-sec-top">
        <h2 id="cr-h-nova">Nova aplicação</h2>
        <div class="cr-acoes-sel">
          <button class="cr-btn2" type="button" data-todos>Selecionar todos</button>
          <button class="cr-btn2" type="button" data-limpar>Limpar seleção</button>
        </div>
      </div>
      ${sel.length
        ? `<div class="cr-sel-lista">${sel.map(t => `<label class="cr-sel-l"><span>Talhão ${t} · área (ha)</span>
            <input class="cr-inp cr-inp-sm" type="number" step="0.01" min="0" value="${crAreaDe(t).area_ha}" data-area="${t}"></label>`).join('')}</div>`
        : '<p class="cr-msg">Marque talhões no mapa, ou use Selecionar todos.</p>'}
      ${aerea ? crCamposAerea(f) : crCamposCorretivo(f)}
      <div><label class="cr-lbl" for="cr-f-os">O.S.</label>
        <input class="cr-inp" id="cr-f-os" type="text" data-f="os" value="${crEsc(f.os)}"></div>
      ${msg}
      <button class="cr-btn cr-btn-bloco" type="button" data-aplicar${sel.length ? '' : ' disabled'}>Aplicar aos marcados</button>
    </section>
    <section class="cr-sec" aria-labelledby="cr-h-lista">
      <h2 id="cr-h-lista">Aplicações do mapa</h2>
      ${apls.length ? crOrdenadas(apls).map(a => crCardAplicacao(a, areas, cores)).join('') : '<p class="cr-msg">Nenhuma aplicação neste mapa ainda.</p>'}
    </section>
    <section class="cr-sec" aria-labelledby="cr-h-res">
      <h2 id="cr-h-res">Resumo</h2>
      ${tot.length
        ? `<div class="cr-tot-grid">${tot.map(t => `<div class="cr-tot"><small>${crEsc(t.titulo)}</small><b>${crBr(t.total)} ${t.unidade}</b>${t.detalhe ? `<small>${crEsc(t.detalhe.replace(/ t\b/g, '\u00a0t'))}</small>` : ''}</div>`).join('')}</div>`
        : '<p class="cr-msg">Sem aplicações ainda.</p>'}
      ${aerea ? crLinhaArea(areas, CR_ST.trab.operacao) : ''}
      <div id="cr-pdf"></div>
    </section>`;
  crRenderBotaoPdf();
}
// ── PDF (gerado no navegador por corretivos-pdf.js) ──
function crRenderBotaoPdf() {
  const alvo = document.getElementById('cr-pdf');
  if (!alvo) return;
  const vazio = !(CR_ST.det && CR_ST.det.apls.length);
  if (CR_DEMO || !window.crGerador) {
    alvo.innerHTML = '<button class="cr-btn2 cr-btn-bloco" type="button" disabled>Baixar PDF (indisponível na demonstração)</button>';
    return;
  }
  const est = crGerador.estado;
  if (est === 'erro') {
    alvo.innerHTML = '<p class="cr-msg cr-erro-bloco" role="alert">Não foi possível preparar o gerador de PDF. Os dados do mapa estão salvos.</p>'
      + '<button class="cr-btn2 cr-btn-bloco" type="button" data-pdf-tentar>Tentar de novo</button>';
  } else if (est === 'pronto' || est === 'parado') {
    alvo.innerHTML = `<button class="cr-btn cr-btn-bloco" type="button" data-pdf${vazio ? ' disabled' : ''}>Baixar PDF</button>`;
  } else {
    // ~20 s só na primeira vez: barra por passo, reaproveitada entre redesenhos para não voltar a 0
    if (!crProgPdf || !alvo.contains(crProgPdf.el)) {
      alvo.innerHTML = '<p class="cr-msg">Preparando o gerador de PDF (só na primeira vez)</p>';
      const api = Mo.progresso(alvo, { total: 4, mb: false });
      crProgPdf = { api, el: alvo.querySelector('.mo-prog') };
    }
    crProgPdf.api.atualizar(crGerador.passo, crGerador.passoTxt);
    return;
  }
  crProgPdf = null;
}
let crProgPdf = null;
async function crBaixarPdf() {
  const alvo = document.getElementById('cr-pdf');
  const m = CR_ST.trab;
  const fim = Mo.ocupado(alvo.querySelector('[data-pdf]'), { texto: 'Gerando o PDF…' });
  let ok = false;
  try {
    const dados = crMontarDados({ codFaz: CR_ST.faz.cod_faz, nome: CR_ST.faz.nome, operacao: m.operacao, data: m.data,
                                  geradoPor: CR_ST.eu.nome, geo: CR_ST.geo, areas: CR_ST.det.areas, apls: CR_ST.det.apls });
    const blob = await crGerador.gerar(dados);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = crNomeArquivo(CR_ST.faz.cod_faz, m.operacao, m.data);
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    ok = true;
  } catch (e) {
    crToast('Não foi possível gerar o PDF. Tente de novo.', true);
  }
  await fim(ok);
  crRenderBotaoPdf();
}
// ── Cadastro de insumos (janela Insumos, usada no mapa aéreo) ──
function crAbrirInsumos() {
  CR_ST.insEdit = null;
  crDesenharInsumos();
}
function crFecharInsumos() {
  const fundo = document.getElementById('cr-modal-fundo');
  fundo.classList.add('off');
  fundo.innerHTML = '';
  fundo.onclick = null;
  crRenderPainel();
}
// Monta a janela: lista dos insumos ativos e formulário (adicionar ou editar). 'v' repõe o que foi digitado após erro.
function crDesenharInsumos(v = null, erro = '') {
  const fundo = document.getElementById('cr-modal-fundo');
  const editId = CR_ST.insEdit;
  const atual = editId == null ? null : CR_ST.insumos.find(i => Number(i.id) === editId);
  const val = v || {
    nome: atual ? atual.nome : '', unidade: atual ? atual.unidade : 'L',
    dose: atual && atual.dose_sugerida != null ? String(atual.dose_sugerida) : '',
    codigo: atual && atual.codigo != null ? String(atual.codigo) : '',
  };
  const linhas = CR_ST.insumos.map(i => `<tr>
        <td>${crEsc(i.nome)}</td>
        <td>${crEsc(CR_UNIDADE[i.unidade] || i.unidade)}</td>
        <td>${i.dose_sugerida == null ? '—' : crBrDose(i.dose_sugerida)}</td>
        <td>${i.codigo == null ? '—' : crEsc(i.codigo)}</td>
        <td class="cr-ins-acoes">
          <button class="cr-x" type="button" data-ins-editar="${Number(i.id)}" aria-label="Editar ${crEsc(i.nome)}" title="Editar"><span class="ico">edit</span></button>
          <button class="cr-x" type="button" data-ins-remover="${Number(i.id)}" aria-label="Remover ${crEsc(i.nome)}" title="Remover"><span class="ico">delete</span></button>
        </td>
      </tr>`).join('');
  fundo.innerHTML = `<div class="cr-modal cr-modal-ins" role="dialog" aria-modal="true" aria-labelledby="cr-ins-tit">
    <h3 id="cr-ins-tit">Insumos</h3>
    <p>Lista usada na aplicação aérea. Remover tira o insumo da lista; os mapas já feitos continuam com ele.</p>
    <div class="cr-ins-lista">${CR_ST.insumos.length
      ? `<table class="cr-ins-tab"><thead><tr><th>Nome</th><th>Unid.</th><th>Dose sugerida</th><th>Código</th><th><span class="sr">Ações</span></th></tr></thead><tbody>${linhas}</tbody></table>`
      : '<p class="cr-msg">Nenhum insumo cadastrado.</p>'}</div>
    <form class="cr-form cr-ins-form" id="cr-ins-form" novalidate>
      <h4>${editId == null ? 'Adicionar insumo' : 'Editar insumo'}</h4>
      <div><label class="cr-lbl" for="cr-ins-nome">Nome</label>
        <input class="cr-inp" id="cr-ins-nome" type="text" value="${crEsc(val.nome)}"></div>
      <div><label class="cr-lbl" for="cr-ins-un">Unidade</label>
        <select class="cr-inp" id="cr-ins-un">
          <option value="L"${val.unidade === 'L' ? ' selected' : ''}>L</option>
          <option value="KG"${val.unidade === 'KG' ? ' selected' : ''}>KG</option>
        </select></div>
      <div><label class="cr-lbl" for="cr-ins-dose">Dose sugerida (opcional)</label>
        <input class="cr-inp" id="cr-ins-dose" type="number" step="0.001" min="0" value="${crEsc(val.dose)}"></div>
      <div><label class="cr-lbl" for="cr-ins-cod">Código (opcional)</label>
        <input class="cr-inp" id="cr-ins-cod" type="number" step="1" min="1" value="${crEsc(val.codigo)}"></div>
      <p class="cr-erro" role="alert">${crEsc(erro)}</p>
      <div class="cr-md-acoes">
        ${editId == null ? '' : '<button class="cr-btn2" type="button" data-ins-cancelar>Cancelar edição</button>'}
        <button class="cr-btn" type="submit">${editId == null ? 'Adicionar' : 'Salvar'}</button>
      </div>
    </form>
    <div class="cr-md-acoes"><button class="cr-btn2" type="button" data-ins-fechar>Fechar</button></div>
  </div>`;
  fundo.classList.remove('off');
  fundo.onclick = e => {
    if (e.target === fundo) return crFecharInsumos();
    const b = e.target.closest('[data-ins-editar],[data-ins-remover],[data-ins-cancelar],[data-ins-fechar]');
    if (!b) return;
    const d = b.dataset;
    if ('insEditar' in d) { CR_ST.insEdit = Number(d.insEditar); return crDesenharInsumos(); }
    if ('insRemover' in d) return crRemoverInsumo(Number(d.insRemover));
    if ('insCancelar' in d) { CR_ST.insEdit = null; return crDesenharInsumos(); }
    crFecharInsumos();
  };
  fundo.querySelector('#cr-ins-form').onsubmit = crSalvarInsumo;
  fundo.querySelector('#cr-ins-nome').focus();
}
async function crSalvarInsumo(e) {
  e.preventDefault();
  const v = {
    nome: document.getElementById('cr-ins-nome').value,
    unidade: document.getElementById('cr-ins-un').value,
    dose: document.getElementById('cr-ins-dose').value,
    codigo: document.getElementById('cr-ins-cod').value,
  };
  const nome = v.nome.trim();
  const dose = String(v.dose).trim() === '' ? null : Number(v.dose);
  const codigo = String(v.codigo).trim() === '' ? null : Number(v.codigo);
  let erro = null;
  if (!nome) erro = 'Informe o nome do insumo.';
  else if (dose !== null && !(dose > 0)) erro = 'Dose sugerida deve ser maior que zero.';
  else if (codigo !== null && !(Number.isInteger(codigo) && codigo > 0)) erro = 'Código deve ser um número inteiro maior que zero.';
  if (erro) return crDesenharInsumos(v, erro);
  const fim = Mo.ocupado(e.submitter);
  try {
    await crApi().salvarInsumo({ id: CR_ST.insEdit, codigo, nome, unidade: v.unidade, dose_sugerida: dose });
  } catch (err) {
    fim(false);
    return crDesenharInsumos(v, /^Já existe/.test(err.message) ? err.message : 'Não foi possível salvar. Tente de novo.');
  }
  await fim(true);
  CR_ST.insEdit = null;
  await crAtualizarInsumos('Insumo salvo.');
}
async function crRemoverInsumo(id) {
  const ins = CR_ST.insumos.find(i => Number(i.id) === id);
  if (!ins) return;
  const ok = await crDialogo('Remover insumo', `Remover ${crNomeInsumo(ins.nome)} da lista? Os mapas já feitos continuam com ele.`, [
    { rotulo: 'Cancelar', classe: 'cr-btn2', valor: false },
    { rotulo: 'Remover', classe: 'cr-btn cr-btn-perigo', valor: true },
  ]);
  if (!ok) return crDesenharInsumos();
  try {
    await crApi().removerInsumo(id);
  } catch (e) {
    return crDesenharInsumos(null, 'Não foi possível remover. Tente de novo.');
  }
  if (CR_ST.insEdit === id) CR_ST.insEdit = null;
  await crAtualizarInsumos('Insumo removido.');
}
// Recarrega os insumos do banco e atualiza a janela e o painel do mapa.
async function crAtualizarInsumos(msg) {
  try {
    CR_ST.insumos = await crApi().insumos();
    // insumo escolhido no formulário que saiu da lista: limpa a escolha (o banco recusaria a aplicação)
    if (CR_ST.form && CR_ST.form.insumo_id && !CR_ST.insumos.some(i => String(i.id) === String(CR_ST.form.insumo_id))) {
      CR_ST.form.insumo_id = '';
    }
  } catch (e) {
    crToast('Não foi possível atualizar a lista de insumos.', true);
  }
  if (msg) crToast(msg);
  crDesenharInsumos();
  crRenderPainel();
}
function crLigarTrabalho() {
  document.getElementById('cr-voltar').onclick = crVoltarLista;
  document.getElementById('cr-trab-corpo').innerHTML = `<div class="cr-trab-grid">
    <div class="cr-mapa-box"><div id="cr-mapa"></div></div>
    <aside class="cr-painel" id="cr-painel" aria-label="Aplicações do mapa"></aside>
  </div>`;
  const painel = document.getElementById('cr-painel');
  painel.onclick = e => {
    const b = e.target.closest('[data-todos],[data-limpar],[data-dest],[data-editar],[data-excluir-apl],[data-aplicar],[data-insumos],[data-tentar-trab],[data-pdf],[data-pdf-tentar]');
    if (!b || b.disabled) return;
    const d = b.dataset;
    if ('todos' in d) crSelecionarTodos();
    else if ('limpar' in d) crLimparSel();
    else if (d.dest) crDestacar(Number(d.dest));
    else if (d.editar) crEditarAplicacao(Number(d.editar));
    else if (d.excluirApl) crExcluirAplicacao(Number(d.excluirApl));
    else if ('insumos' in d) crAbrirInsumos();
    else if ('aplicar' in d) crAplicarMarcados();
    else if ('tentarTrab' in d) crAbrirMapa(CR_ST.trab);
    else if ('pdfTentar' in d) { crGerador.preparar().catch(() => {}); crRenderBotaoPdf(); }
    else if ('pdf' in d) crBaixarPdf();
  };
  painel.onchange = e => {
    const el = e.target;
    if (el.dataset.area) return crSalvarArea(Number(el.dataset.area), el.value);
    if ('tipo' in el.dataset) { CR_ST.form.tipo = el.value; CR_ST.formMsg = null; return crRenderPainel(); }
    if (el.dataset.f === 'insumo_id') {          // ao trocar o insumo, a dose vem com a sugerida
      CR_ST.form.insumo_id = el.value;
      const ins = CR_ST.insumos.find(i => String(i.id) === el.value);
      if (ins && ins.dose_sugerida != null) CR_ST.form.dose = String(ins.dose_sugerida);
      return crRenderPainel();
    }
    if (el.dataset.f) CR_ST.form[el.dataset.f] = el.value;
  };
  painel.oninput = e => { if (e.target.dataset.f) CR_ST.form[e.target.dataset.f] = e.target.value; };
}

if (typeof document !== 'undefined' && document.getElementById) crIniciar();
