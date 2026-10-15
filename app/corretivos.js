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
const CR_ST = { eu: null, fazendas: [], faz: null, mapas: [], trab: null };
const CR_OP_VAR = { subsolagem: '--irrigacao', supergrade: '--plantio', arado: '--colheita' };

async function crAFazer() { throw new Error('a fazer'); }
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
  for (const a of m.corretivo_aplicacoes || []) {
    const area = (a.corretivo_aplicacao_talhoes || []).reduce((s, x) => s + (areas[x.talhao_num] || 0), 0);
    total += area * Number(a.dose) + area * Number(a.dose_gesso || 0);
  }
  const os = [...new Set((m.corretivo_aplicacoes || []).map(a => String(a.os).trim()))].sort();
  return { id: m.id, operacao: m.operacao, data: m.data, os, talhoes: (m.corretivo_talhoes || []).length,
           toneladas: Math.round(total * 100) / 100, alterado_por_nome: nomes[m.alterado_por] || '—', alterado_em: m.alterado_em };
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
      .select('id,operacao,data,alterado_por,alterado_em,corretivo_talhoes(talhao_num,area_ha),corretivo_aplicacoes(tipo,dose,dose_gesso,os,corretivo_aplicacao_talhoes(talhao_num))')
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
  carregarMapa: crAFazer, salvarAplicacao: crAFazer, excluirAplicacao: crAFazer, talhoesFazenda: crAFazer,
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
  if (CR_DEMO && CR_ST.fazendas.length && !CR_ST.faz) crEscolherFazenda(CR_ST.fazendas[0]);
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
function crEscolherFazenda(f) {
  CR_ST.faz = f;
  document.getElementById('cr-busca').value = `${f.cod_faz} · ${f.nome}`;
  document.getElementById('cr-res').innerHTML = '';
  document.getElementById('cr-faz-nome').textContent = f.nome;
  document.getElementById('cr-faz-sub').textContent = `Código ${f.cod_faz}`;
  document.getElementById('cr-pnl').classList.remove('off');
  crCarregarMapas();
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
    alvo.innerHTML = '<div class="cr-vazio"><span class="ico">compost</span><span>Nenhum mapa de corretivo nesta fazenda.</span>'
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
      <div class="cr-stat"><small>Total</small><b>${crBr(m.toneladas)} t</b></div>
    </div>
    <div class="cr-rod">alterado por ${crEsc(m.alterado_por_nome)} em ${crDiaMes(m.alterado_em)}</div>
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
  ]);
  if (!op) return;
  let id;
  try {
    id = await crApi().criarMapa(CR_ST.faz.cod_faz, op);
  } catch (e) {
    crToast('Não foi possível criar o mapa. Tente de novo.', true);
    return;
  }
  CR_ST.trab = { id, operacao: op, data: crHojeIso() };
  document.getElementById('cr-trab-tit').textContent = `Mapa ${CR_OPERACOES[op]} · ${crDataIso(CR_ST.trab.data)}`;
  crTela('trabalho');
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
  document.getElementById('cr-voltar').onclick = () => { crTela('lista'); crCarregarMapas(); };
  document.getElementById('cr-mapas').onclick = e => {
    if (e.target.closest('[data-tentar]')) return crCarregarMapas();
    if (e.target.closest('[data-novo]')) return crNovoMapa();
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
if (typeof document !== 'undefined' && document.getElementById) crIniciar();
