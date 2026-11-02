// Apresentação semanal: tela (acesso, parâmetros, prévia, rascunho e PPTX).
// Padrão de corretivos.js (prefixo ap em vez de cr). Depende de apresentacao-calculo.js, -slides.js, -dados.js,
// -exportar.js e -demo.js, carregados antes deste arquivo.

// ===== Apresentação: acesso, API (real e demonstração) e estado =====
function apEhDemo() {
  return location.protocol === 'file:' || (typeof URLSearchParams !== 'undefined' && new URLSearchParams(location.search).has('demo'));
}
const AP_DEMO = apEhDemo();
const AP_DEMO_FALHA_VOOS = typeof URLSearchParams !== 'undefined' && new URLSearchParams(location.search).get('demo') === 'voos-falha';
const AP_SB_URL = 'https://dpvsivypabmvmrrpgmhc.supabase.co';
const AP_SB_KEY = 'sb_publishable_3xv0R1kmhSXkoUh3i4vN0A_Q5oLBbVL';   // mesma chave pública do corretivos.js
const AP_WORKER_URL = 'https://hub-geotech-arquivos.leonardo-malerbo.workers.dev';   // mesma de app/index.html
const AP_REGEX_SEMANA = /^S[1-5]M([1-9]|1[0-2])$/;
let AP_SB = null;
function apSb() {
  if (!AP_SB) AP_SB = window.supabase.createClient(AP_SB_URL, AP_SB_KEY, { db: { schema: 'hub' } });
  return AP_SB;
}

const AP_ST = { eu: null, metas: null, alterado: null, semana: null, corte: null, textos: {}, D: { hub: null, drone: null, voos: null },
  status: { hub: 'carregando', drone: 'carregando', voos: 'carregando' }, A: null, erroCalculo: null, sel: 'colheita',
  tentativasVoos: 0, timers: {} };

// Estado da demonstração (só em memória): metas e textos alterados.
const AP_DEMO_MEM = { metas: null, textos: {} };
function apEspera(ms) { return new Promise((r) => setTimeout(r, ms)); }
function apPad(n) { return String(n).padStart(2, '0'); }
function apHora(d) { return `${apPad(d.getHours())}:${apPad(d.getMinutes())}`; }
function apDataHora(iso) {
  const d = new Date(iso);
  return `${apPad(d.getDate())}/${apPad(d.getMonth() + 1)} às ${apHora(d)}`;
}
function apDataBr(iso) { const [a, m, d] = String(iso).slice(0, 10).split('-'); return `${d}/${m}/${a}`; }

async function apNomeUsuario(id) {
  if (!id) return null;
  const { data, error } = await apSb().from('usuarios').select('nome').eq('id', id).maybeSingle();
  if (error) throw error;
  return data ? data.nome : null;
}

const apApiReal = {
  async sessao() {
    const { data, error } = await apSb().auth.getSession();
    if (error) throw error;
    return data.session ? data.session.user : null;
  },
  async entrar(email, senha) {
    const { error } = await apSb().auth.signInWithPassword({ email, password: senha });
    if (!error) return;
    if (/banned/i.test(error.message)) throw new Error('Acesso bloqueado. Se o seu cadastro no GeoMap é novo, defina sua senha lá primeiro.');
    if (/invalid/i.test(error.message)) throw new Error('E-mail ou senha incorretos.');
    throw new Error('Não foi possível entrar agora. Tente de novo.');
  },
  async sair() {
    const { error } = await apSb().auth.signOut();
    if (error) throw error;
  },
  async eu() {
    const user = await apApiReal.sessao();
    if (!user) return null;
    const { data, error } = await apSb().from('usuarios').select('nome').eq('id', user.id).single();
    if (error) throw error;
    const { data: pode, error: erroPode } = await apSb().rpc('pode_usar_apresentacao');
    if (erroPode) throw erroPode;
    return { id: user.id, nome: data.nome, pode: !!pode };
  },
  async metas() {
    const { data, error } = await apSb().from('apresentacao_metas').select('*');
    if (error) throw error;
    let ultima = null;
    for (const l of data) if (!ultima || String(l.atualizado_em) > String(ultima.atualizado_em)) ultima = l;
    const alterado = ultima ? { nome: await apNomeUsuario(ultima.atualizado_por), em: ultima.atualizado_em } : null;
    return { metas: apMetasDeLinhas(data), alterado };
  },
  async salvarMetas(obj) {
    for (const [chave, valor] of Object.entries(obj)) {
      const { error } = await apSb().from('apresentacao_metas').update({ valor: String(valor) }).eq('chave', chave);
      if (error) throw error;
    }
  },
  async semana(semana) {
    const { data, error } = await apSb().from('apresentacao_semanas').select('*').eq('semana', semana).maybeSingle();
    if (error) throw error;
    if (!data) return { textos: {}, atualizado_por: null, nome: null, em: null };
    return { textos: data.textos || {}, atualizado_por: data.atualizado_por, nome: await apNomeUsuario(data.atualizado_por), em: data.atualizado_em };
  },
  async salvarTexto(semana, corte, slide, campo, valor) {
    const { data, error } = await apSb().rpc('apresentacao_texto_salvar', { p_semana: semana, p_corte: corte, p_slide: slide, p_campo: campo, p_valor: valor });
    if (error) throw error;
    return data;
  },
  fontes(corte, metas) {
    AP_ST.tentativasVoos++;   // a busca de voos feita junto com as outras fontes conta como uma tentativa
    return apFontes(apSb(), corte, metas, AP_WORKER_URL);
  },
  voos(corte, metas) {
    AP_ST.tentativasVoos++;
    return apBuscarVoos(apSb(), corte, metas, AP_WORKER_URL);
  },
};

const apApiDemo = {
  async sessao() { return { id: 'demo' }; },
  async entrar() {},
  async sair() {},
  async eu() { return { id: 'demo', nome: 'Demonstração', pode: true }; },
  async metas() {
    if (!AP_DEMO_MEM.metas) AP_DEMO_MEM.metas = { ...AP_DEMO_METAS };
    return { metas: { ...AP_DEMO_MEM.metas }, alterado: null };
  },
  async salvarMetas(obj) { AP_DEMO_MEM.metas = { ...(AP_DEMO_MEM.metas || AP_DEMO_METAS), ...obj }; },
  async semana(semana) { return { textos: AP_DEMO_MEM.textos[semana] || {}, atualizado_por: null, nome: null, em: null }; },
  async salvarTexto(semana, corte, slide, campo, valor) {
    const textos = AP_DEMO_MEM.textos[semana] || (AP_DEMO_MEM.textos[semana] = {});
    const s = textos[slide] || (textos[slide] = {});
    s[campo] = valor;
    return new Date().toISOString();
  },
  fontes(corte, metas) {
    return {
      hub: apEspera(400).then(() => AP_DEMO_HUB),
      drone: apEspera(300).then(() => AP_DEMO_DRONE),
      voos: apApiDemo.voos(),
    };
  },
  async voos() {
    AP_ST.tentativasVoos++;
    if (AP_DEMO_FALHA_VOOS) {
      await apEspera(2000);
      throw new Error('A API de voos do GeoMap não respondeu em 3 minutos');
    }
    await apEspera(1200);
    return AP_DEMO_VOOS;
  },
};

function apApi() { return AP_DEMO ? apApiDemo : apApiReal; }

// ── Telas ──
function apMostrar(tela) {
  for (const t of ['carregando', 'login', 'sem-acesso', 'app']) document.getElementById('apt-' + t).classList.toggle('off', t !== tela);
}
function apToast(msg, erro = false) {
  const t = document.getElementById('apt-toast');
  t.textContent = msg;
  t.classList.toggle('erro', erro);
  t.classList.add('show');
  clearTimeout(apToast.timer);
  apToast.timer = setTimeout(() => t.classList.remove('show'), 3200);
}

// ── Entrada: login, sessão e acesso ──
async function apEntrar(e) {
  e.preventDefault();
  const email = document.getElementById('apt-email').value.trim();
  const senha = document.getElementById('apt-senha').value;
  const erro = document.getElementById('apt-login-erro');
  const btn = document.getElementById('apt-entrar');
  erro.textContent = '';
  if (!email || !senha) { erro.textContent = 'Informe e-mail e senha.'; return; }
  btn.disabled = true;
  btn.textContent = 'Entrando…';
  try {
    await apApi().entrar(email, senha);
    document.getElementById('apt-senha').value = '';
    await apCarregarEntrada();
  } catch (err) {
    erro.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Entrar';
  }
}
async function apCarregarEntrada() {
  let eu;
  try {
    eu = await apApi().eu();
  } catch (e) {
    apMostrar('login');
    document.getElementById('apt-login-erro').textContent = 'Não foi possível verificar seu acesso. Tente de novo.';
    return;
  }
  AP_ST.eu = eu;
  if (!eu || !eu.pode) { apMostrar('sem-acesso'); return; }
  document.getElementById('apt-nome').textContent = eu.nome;
  apMostrar('app');
  apMostrarParametros();
  await apCarregarMetas();
  await apCarregarSemana();
}
async function apSair() {
  try {
    await apApi().sair();
  } catch (e) {
    apToast('Não foi possível sair. Tente de novo.', true);
    return;
  }
  apFlush();
  Object.assign(AP_ST, { eu: null, metas: null, alterado: null, semana: null, corte: null, textos: {}, A: null, timers: {} });
  apMostrar('login');
}

// ===== Parâmetros: semana, corte e metas =====
const AP_CHAVES_META = ['meta_ervas_ha', 'meta_fornecedor_ha', 'meta_ha_dia', 'drone_pendente_ha', 'safra_atual', 'inicio_safra'];
const AP_CHAVES_META_NUM = ['meta_ervas_ha', 'meta_fornecedor_ha', 'meta_ha_dia', 'drone_pendente_ha'];
const AP_NOME_FONTE = { hub: 'Hub Geotech', drone: 'Drone de Aplicação', voos: 'Voos com Drone' };
const AP_NOME_SLIDE = { divisoria: 'Divisória', colheita: 'Colheita', sistematizacao: 'Sistematização', plantio: 'Plantio', voos: 'Voos com Drone', drone: 'Drone de Aplicação' };
const AP_LIMITE_VOOS_TXT = '3:00';

function apMostrarParametros() {
  document.getElementById('apt-parametros').classList.remove('off');
  document.getElementById('apt-edicao').classList.add('off');
}

function apLerMetas() {
  const m = {};
  for (const c of AP_CHAVES_META_NUM) {
    const v = document.getElementById('apt-meta-' + c).value.trim();
    if (v === '' || !isFinite(Number(v))) return null;
    m[c] = Number(v);
  }
  m.safra_atual = document.getElementById('apt-meta-safra_atual').value.trim();
  m.inicio_safra = document.getElementById('apt-meta-inicio_safra').value;
  if (!m.safra_atual || !m.inicio_safra) return null;
  return m;
}

async function apCarregarMetas() {
  let r;
  try {
    r = await apApi().metas();
  } catch (e) {
    apToast('Não foi possível carregar as metas. Tente de novo.', true);
    return;
  }
  AP_ST.metas = r.metas;
  AP_ST.alterado = r.alterado;
  for (const c of AP_CHAVES_META) {
    const v = r.metas[c];
    document.getElementById('apt-meta-' + c).value = v === undefined || v === null || Number.isNaN(v) ? '' : String(v);
  }
  const el = document.getElementById('apt-metas-alteracao');
  el.textContent = r.alterado ? `Última alteração: ${r.alterado.nome || '—'}, ${apDataHora(r.alterado.em)}` : '';
}

async function apSalvarMetas() {
  const lidas = apLerMetas();
  if (!lidas) { apToast('Confira as metas: os números, a safra e o início da safra são obrigatórios.', true); return; }
  const mudou = {};
  for (const k of AP_CHAVES_META) {
    if (String(lidas[k]) !== String(AP_ST.metas ? AP_ST.metas[k] : '')) mudou[k] = lidas[k];
  }
  if (!Object.keys(mudou).length) { apToast('Nenhuma meta foi alterada.'); return; }
  const btn = document.getElementById('apt-salvar-metas');
  btn.disabled = true;
  try {
    await apApi().salvarMetas(mudou);
    apToast('Metas salvas.');
    await apCarregarMetas();
  } catch (e) {
    apToast('Não foi possível salvar as metas. Tente de novo.', true);
  } finally {
    btn.disabled = false;
  }
}

// Aviso do rascunho da semana (sem carregar os textos na tela de edição).
async function apAvisoRascunho(semana) {
  const aviso = document.getElementById('apt-aviso-rascunho');
  aviso.textContent = '';
  try {
    const r = await apApi().semana(semana);
    aviso.textContent = r.atualizado_por
      ? `Rascunho de ${semana}: editado por ${r.nome || 'outra pessoa'} às ${apHora(new Date(r.em))}`
      : `Nenhum rascunho para ${semana}. Os textos começam com o padrão.`;
    return r;
  } catch (e) {
    aviso.textContent = 'Não foi possível ler o rascunho desta semana.';
    return null;
  }
}

async function apCarregarSemana() {
  const s = apSemana(new Date());
  document.getElementById('apt-semana').value = s.semana;
  document.getElementById('apt-corte').value = s.corte;
  await apAvisoRascunho(s.semana);
}

// ===== Buscar dados e status das fontes =====
async function apBuscar() {
  const erro = document.getElementById('apt-param-erro');
  erro.textContent = '';
  const semana = document.getElementById('apt-semana').value.trim().toUpperCase();
  const corte = document.getElementById('apt-corte').value;
  if (!AP_REGEX_SEMANA.test(semana)) { erro.textContent = 'Semana inválida. Use o formato S5M10: semana do mês e mês, sem zero à esquerda.'; return; }
  if (!corte) { erro.textContent = 'Informe a data de corte.'; return; }
  const metas = apLerMetas();
  if (!metas) { erro.textContent = 'Confira as metas: os números, a safra e o início da safra são obrigatórios.'; return; }
  let rascunho;
  try {
    rascunho = await apApi().semana(semana);
  } catch (e) {
    erro.textContent = 'Não foi possível carregar o rascunho desta semana. Tente de novo.';
    return;
  }
  AP_ST.run = (AP_ST.run || 0) + 1;
  AP_ST.semana = semana;
  AP_ST.corte = corte;
  AP_ST.metas = metas;
  AP_ST.rascunho = rascunho;
  AP_ST.textos = rascunho.textos || {};
  AP_ST.D = { hub: null, drone: null, voos: null };
  AP_ST.A = null;
  AP_ST.erroCalculo = null;
  AP_ST.sel = 'colheita';
  AP_ST.status = { hub: 'carregando', drone: 'carregando', voos: 'carregando' };
  AP_ST.info = {};
  document.getElementById('apt-parametros').classList.add('off');
  document.getElementById('apt-edicao').classList.remove('off');
  apMostrarEdicao();
  apRenderTudo();
  const f = apApi().fontes(corte, metas);
  apAcompanhar('hub', f.hub);
  apAcompanhar('drone', f.drone);
  apAcompanharVoos(f.voos);
}

function apMostrarEdicao() {
  const r = AP_ST.rascunho || {};
  document.getElementById('apt-cabec').textContent = `${AP_ST.semana} · dados até ${apDataBr(AP_ST.corte)}`;
  const salvo = document.getElementById('apt-salvo');
  salvo.classList.remove('erro');
  salvo.textContent = r.atualizado_por && AP_ST.eu && r.atualizado_por !== AP_ST.eu.id
    ? `Rascunho editado por ${r.nome || 'outra pessoa'} às ${apHora(new Date(r.em))}`
    : '';
}

// Espera uma fonte (hub ou drone) e atualiza a linha de status.
function apAcompanhar(nome, p) {
  const run = AP_ST.run;
  AP_ST.info[nome] = { inicio: Date.now() };
  p.then((v) => {
    if (run !== AP_ST.run) return;
    AP_ST.info[nome].ms = Date.now() - AP_ST.info[nome].inicio;
    AP_ST.D[nome] = v;
    AP_ST.status[nome] = 'ok';
    if (AP_ST.status.hub === 'ok' && AP_ST.status.drone === 'ok') apRecalcular();
    else apRenderTudo();
  }, (e) => {
    if (run !== AP_ST.run) return;
    AP_ST.info[nome].ms = Date.now() - AP_ST.info[nome].inicio;
    AP_ST.info[nome].erro = e.message;
    AP_ST.status[nome] = 'falhou';
    apRenderTudo();
  });
}

// Voos: demora até 3 minutos. Tem contador na linha e pode ser tentado de novo.
function apAcompanharVoos(p) {
  const run = AP_ST.run;
  AP_ST.info.voos = { inicio: Date.now() };
  apIniciarTicker();
  p.then((v) => {
    if (run !== AP_ST.run) return;
    apPararTicker();
    AP_ST.info.voos.ms = Date.now() - AP_ST.info.voos.inicio;
    AP_ST.D.voos = v;
    AP_ST.status.voos = 'ok';
    if (AP_ST.status.hub === 'ok' && AP_ST.status.drone === 'ok') apRecalcular();
    else apRenderTudo();
  }, (e) => {
    if (run !== AP_ST.run) return;
    apPararTicker();
    AP_ST.info.voos.ms = Date.now() - AP_ST.info.voos.inicio;
    AP_ST.info.voos.erro = e.message;
    AP_ST.status.voos = 'falhou';
    apRenderTudo();
  });
}

function apTentarVoos() {
  AP_ST.status.voos = 'carregando';
  AP_ST.D.voos = null;
  apAcompanharVoos(apApi().voos(AP_ST.corte, AP_ST.metas));
  apRenderTudo();
}

function apIniciarTicker() {
  apPararTicker();
  AP_ST.timers.ticker = setInterval(apRenderFontes, 1000);
}
function apPararTicker() {
  clearInterval(AP_ST.timers.ticker);
  delete AP_ST.timers.ticker;
}

function apTempo(ms) { return `${(ms / 1000).toFixed(1).replace('.', ',')} s`; }

function apRenderFontes() {
  const ul = document.getElementById('apt-fontes');
  const linhas = ['hub', 'drone', 'voos'].map((f) => {
    const st = AP_ST.status[f];
    const info = AP_ST.info[f] || {};
    let icone = 'progress_activity';
    let classe = st === 'carregando' ? 'apt-girando' : '';
    let det = '';
    let tempo = '';
    if (st === 'ok') {
      icone = 'check_circle';
      if (f === 'hub' && AP_ST.D.hub) {
        const h = AP_ST.D.hub;
        det = `${h.colheita_talhoes.length.toLocaleString('pt-BR')} talhões de colheita · ${h.talhao_preparo.length.toLocaleString('pt-BR')} talhões de preparo · ${h.talhao_plantio.length.toLocaleString('pt-BR')} talhões de plantio`;
      } else if (f === 'drone' && AP_ST.D.drone) {
        const sem = AP_ST.A ? AP_ST.A.drone.sem_dado.length : null;
        det = `${AP_ST.D.drone.length.toLocaleString('pt-BR')} projetos vigentes` + (sem === null ? '' : ` · ${sem} sem área (aparecem na prévia)`);
      } else {
        det = 'ok';
      }
      tempo = apTempo(info.ms || 0);
    } else if (st === 'falhou') {
      icone = 'error';
      det = info.erro || 'Erro desconhecido';
      tempo = apTempo(info.ms || 0);
    } else if (f === 'voos') {
      det = 'Aguardando a API acordar. A primeira chamada do dia leva uns 2 minutos.';
      const s = Math.floor((Date.now() - (info.inicio || Date.now())) / 1000);
      tempo = `${Math.floor(s / 60)}:${apPad(s % 60)} / até ${AP_LIMITE_VOOS_TXT}`;
    }
    const detHtml = det ? `<span class="apt-fonte-det">${apEsc(det)}</span>` : '';
    return `<li class="apt-fonte" data-fonte="${f}" data-status="${st}">` +
      `<span class="ico ${classe}" aria-hidden="true">${icone}</span>` +
      `<span class="apt-fonte-txt">${apEsc(AP_NOME_FONTE[f])}${detHtml}</span>` +
      `<span class="apt-fonte-tempo">${apEsc(tempo)}</span></li>`;
  });
  ul.innerHTML = linhas.join('');
}

// ===== Recálculo, lista de slides, prévia e campos =====
function apRecalcular() {
  const D = { ...AP_ST.D.hub, drone: AP_ST.D.drone, voos: AP_ST.D.voos || null };
  try {
    AP_ST.A = apAgregar(D, AP_ST.metas);
    AP_ST.erroCalculo = null;
  } catch (e) {
    AP_ST.A = null;
    AP_ST.erroCalculo = e.message;
  }
  apRenderTudo();
}

function apTextosDo(k) { return AP_ST.textos[k] || {}; }
function apCtx(i) { return { semana: AP_ST.semana, corte: AP_ST.corte, num: i + 1 }; }

function apEstadoSlide(k) {
  const t = apTextosDo(k);
  const drone = AP_ST.A && AP_ST.A.drone && AP_ST.A.drone.sem_dado.length;
  if (k === 'voos' && AP_ST.status.voos === 'falhou') return ['erro', 'error'];
  if (k === 'divisoria' && AP_ST.status.voos === 'falhou') return ['aviso', 'warning'];
  if (k === 'drone' && drone) return ['info', 'info'];
  if ((k === 'divisoria' || k === 'voos') && AP_ST.status.voos === 'carregando') return ['espera', 'progress_activity'];
  if (!AP_ST.A) return ['espera', 'progress_activity'];
  if (t.subtitulo || t.destaque || t.notas) return ['edit', 'edit'];
  return ['ok', 'check'];
}

function apRenderLista() {
  const nav = document.getElementById('apt-lista');
  nav.innerHTML = AP_SLIDES.map((k, i) => {
    const [estado, icone] = apEstadoSlide(k);
    const sel = AP_ST.sel === k;
    return `<button class="apt-slide-btn" type="button" data-slide="${k}" data-estado="${estado}" aria-current="${sel ? 'true' : 'false'}">` +
      `<span class="apt-slide-num">${i + 1}</span>` +
      `<span class="apt-slide-nome">${apEsc(AP_NOME_SLIDE[k])}</span>` +
      `<span class="ico" aria-hidden="true">${icone}</span></button>`;
  }).join('');
}

function apVazio(titulo, texto, botao) {
  return `<div class="apt-vazio">${titulo ? `<p class="apt-vazio-tit">${apEsc(titulo)}</p>` : ''}` +
    (texto ? `<p>${apEsc(texto)}</p>` : '') + (botao || '') + '</div>';
}

function apAjustarEscala() {
  const previa = document.getElementById('apt-previa');
  const esc = previa.querySelector('.apt-escala');
  if (esc) esc.style.transform = `scale(${previa.clientWidth / 1920})`;
}

function apRenderPrevia() {
  const previa = document.getElementById('apt-previa');
  const k = AP_ST.sel;
  const i = AP_SLIDES.indexOf(k);
  if (AP_ST.erroCalculo) { previa.innerHTML = ''; return; }
  if (!AP_ST.A) { previa.innerHTML = apVazio('Carregando os dados…', ''); return; }
  if ((k === 'voos' || k === 'divisoria') && AP_ST.status.voos === 'carregando') {
    previa.innerHTML = apVazio('Aguardando a API de voos…', '');
    return;
  }
  if (k === 'voos' && AP_ST.status.voos === 'falhou') {
    previa.innerHTML = apVazio('Dados indisponíveis',
      'A API do GeoMap não respondeu. Este slide não entra no PPTX enquanto estiver assim.',
      '<button class="apt-btn" type="button" id="apt-tentar"><span class="ico">refresh</span> Tentar de novo</button>');
    return;
  }
  if (k === 'divisoria' && AP_ST.status.voos === 'falhou') {
    previa.innerHTML = apVazio('', 'Pendente: depende dos números de Voos.');
    return;
  }
  try {
    const html = apSlide(k, AP_ST.A, AP_ST.metas, apTextosDo(k), apCtx(i));
    previa.innerHTML = `<div class="apt-escala">${html}</div>`;
    apAjustarEscala();
  } catch (e) {
    previa.innerHTML = apVazio('Não foi possível montar este slide.', e.message);
  }
}

function apRenderCampos() {
  const k = AP_ST.sel;
  const i = AP_SLIDES.indexOf(k);
  const t = apTextosDo(k);
  document.getElementById('apt-slide-cab').textContent = `Slide ${i + 1} · ${AP_TITULOS[k]}`;
  const subGrupo = document.getElementById('apt-grupo-subtitulo');
  const sub = document.getElementById('apt-f-subtitulo');
  const dest = document.getElementById('apt-f-destaque');
  const notas = document.getElementById('apt-f-notas');
  subGrupo.classList.toggle('off', k === 'divisoria');
  // Sem dados de voos (busca falhou ou ainda carrega), o subtítulo padrão de voos ainda não existe.
  if (k !== 'divisoria') sub.placeholder = AP_ST.A && (k !== 'voos' || AP_ST.A.voos) ? apSubtituloPadrao(k, AP_ST.A, AP_ST.metas, apCtx(i)) : '';
  // Não sobrescreve o campo que está sendo digitado.
  if (document.activeElement !== sub) sub.value = t.subtitulo || '';
  if (document.activeElement !== dest) dest.value = t.destaque || '';
  if (document.activeElement !== notas) notas.value = t.notas || '';
  const sd = document.getElementById('apt-sem-dado');
  const semDado = AP_ST.A && AP_ST.A.drone.sem_dado;
  sd.classList.toggle('off', !semDado || !semDado.length);
  if (semDado && semDado.length) {
    document.getElementById('apt-sem-dado-tit').textContent = `Drone de Aplicação · ${semDado.length} ${semDado.length === 1 ? 'projeto' : 'projetos'}`;
    document.getElementById('apt-sem-dado-lista').innerHTML = semDado.map((r) =>
      `<li>${apEsc(r.cod_faz)} · ${apEsc(r.documento)} · rev. ${apEsc(r.revisao_id)}</li>`).join('');
  }
}

function apRenderFalta() {
  const faltam = ['hub', 'drone', 'voos'].filter((f) => AP_ST.status[f] !== 'ok').map((f) => AP_NOME_FONTE[f]);
  document.getElementById('apt-falta').textContent = faltam.length ? `Falta: ${faltam.join(', ')}` : '';
  return faltam.length === 0;
}

function apRenderBaixar() {
  const pronto = apRenderFalta() && !AP_ST.erroCalculo && !!AP_ST.A;
  const btn = document.getElementById('apt-baixar');
  btn.disabled = !pronto || AP_ST.baixando === true;
  btn.setAttribute('aria-disabled', String(!pronto));
}

function apRenderErroCalculo() {
  document.getElementById('apt-erro-calculo').textContent = AP_ST.erroCalculo
    ? `Não foi possível montar os slides: ${AP_ST.erroCalculo}. Avise o Leo.` : '';
}

function apRenderTudo() {
  apRenderErroCalculo();
  apRenderFontes();
  apRenderLista();
  apRenderPrevia();
  apRenderCampos();
  apRenderBaixar();
}

function apSelecionar(k) {
  AP_ST.sel = k;
  apRenderLista();
  apRenderPrevia();
  apRenderCampos();
}

// ===== Edição: rascunho (salva campo a campo, com atraso de 2 s) =====
function apMarcarSalvo() {
  const el = document.getElementById('apt-salvo');
  el.classList.remove('erro');
  el.textContent = `Rascunho salvo às ${apHora(new Date())}`;
}

async function apSalvarCampo(k, campo) {
  delete AP_ST.timers[k + '|' + campo];
  const valor = apTextosDo(k)[campo] || '';
  try {
    await apApi().salvarTexto(AP_ST.semana, AP_ST.corte, k, campo, valor);
    apMarcarSalvo();
  } catch (e) {
    const el = document.getElementById('apt-salvo');
    el.classList.add('erro');
    el.textContent = 'Não foi possível salvar o rascunho';
  }
}

// Salva agora os campos com gravação pendente (ao voltar, sair ou gerar o PPTX).
function apFlush() {
  for (const chave of Object.keys(AP_ST.timers)) {
    if (chave === 'ticker') continue;
    clearTimeout(AP_ST.timers[chave]);
    const [k, campo] = chave.split('|');
    apSalvarCampo(k, campo);
  }
}

function apEditarCampo(campo, valor) {
  const k = AP_ST.sel;
  const t = AP_ST.textos[k] || (AP_ST.textos[k] = {});
  t[campo] = valor;
  apRenderPrevia();
  apRenderLista();
  const chave = k + '|' + campo;
  clearTimeout(AP_ST.timers[chave]);
  AP_ST.timers[chave] = setTimeout(() => apSalvarCampo(k, campo), 2000);
}

function apVoltarParametros() {
  apFlush();
  apMostrarParametros();
}

// Volta o subtítulo ao texto padrão: grava vazio na hora.
function apTextoPadrao() {
  const k = AP_ST.sel;
  const chave = k + '|subtitulo';
  clearTimeout(AP_ST.timers[chave]);
  (AP_ST.textos[k] || (AP_ST.textos[k] = {})).subtitulo = '';
  apSalvarCampo(k, 'subtitulo');
  apRenderTudo();
}

// ===== PPTX =====
async function apBaixar() {
  const btn = document.getElementById('apt-baixar');
  const rotulo = document.getElementById('apt-baixar-rotulo');
  AP_ST.baixando = true;
  btn.disabled = true;
  rotulo.textContent = 'Gerando PPTX…';
  apFlush();
  const fora = document.createElement('div');
  fora.style.cssText = 'position:fixed;left:-20000px;top:0;';
  document.body.appendChild(fora);
  try {
    const els = AP_SLIDES.map((k, i) => {
      const div = document.createElement('div');
      div.style.cssText = 'position:relative;width:1920px;height:1080px;overflow:hidden;background:#fff;';
      div.innerHTML = apSlide(k, AP_ST.A, AP_ST.metas, apTextosDo(k), apCtx(i));
      fora.appendChild(div);
      return div;
    });
    const notas = AP_SLIDES.map((k) => apTextosDo(k).notas || '');
    await apExportar(els, notas, AP_ST.semana);
  } catch (e) {
    apToast('Não foi possível gerar o PPTX. Tente de novo.', true);
  } finally {
    fora.remove();
    AP_ST.baixando = false;
    rotulo.textContent = 'Baixar PPTX';
    apRenderBaixar();
  }
}

// ===== Inicialização (só no navegador) =====
function apLigarEventos() {
  document.getElementById('apt-form').onsubmit = apEntrar;
  document.querySelectorAll('[data-sair]').forEach((b) => { b.onclick = apSair; });
  document.getElementById('apt-demo').classList.toggle('off', !AP_DEMO);
  document.getElementById('apt-salvar-metas').onclick = apSalvarMetas;
  document.getElementById('apt-semana').onchange = (e) => {
    const s = e.target.value.trim().toUpperCase();
    e.target.value = s;
    if (AP_REGEX_SEMANA.test(s)) apAvisoRascunho(s);
  };
  document.getElementById('apt-buscar').onclick = apBuscar;
  document.getElementById('apt-voltar').onclick = apVoltarParametros;
  document.getElementById('apt-lista').onclick = (e) => {
    const b = e.target.closest('[data-slide]');
    if (b) apSelecionar(b.dataset.slide);
  };
  document.getElementById('apt-previa').onclick = (e) => {
    if (e.target.closest('#apt-tentar')) apTentarVoos();
  };
  document.getElementById('apt-f-subtitulo').oninput = (e) => apEditarCampo('subtitulo', e.target.value);
  document.getElementById('apt-f-destaque').oninput = (e) => apEditarCampo('destaque', e.target.value);
  document.getElementById('apt-f-notas').oninput = (e) => apEditarCampo('notas', e.target.value);
  document.getElementById('apt-padrao').onclick = apTextoPadrao;
  document.getElementById('apt-baixar').onclick = apBaixar;
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(apAjustarEscala).observe(document.getElementById('apt-previa'));
}

async function apIniciar() {
  apLigarEventos();
  apMostrar('carregando');
  try {
    const user = await apApi().sessao();
    if (!user) { apMostrar('login'); return; }
  } catch (e) {
    apMostrar('login');
    return;
  }
  await apCarregarEntrada();
}

if (typeof document !== 'undefined' && document.getElementById && document.getElementById('apt-app')) apIniciar();
