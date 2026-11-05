// ===== Paralelismo: acesso, API (real e demonstração) e aba Processar =====
// As telas só são montadas quando há #par-app no documento. Estado em PAR; funções com prefixo par.
const PAR_DEMO = location.protocol === 'file:' || new URLSearchParams(location.search).has('demo');
const PAR_SB_URL = 'https://dpvsivypabmvmrrpgmhc.supabase.co';
const PAR_SB_KEY = 'sb_publishable_3xv0R1kmhSXkoUh3i4vN0A_Q5oLBbVL';   // mesma chave pública do index.html
const PAR_WORKER_URL = 'https://hub-geotech-arquivos.leonardo-malerbo.workers.dev';   // mesma de app/index.html
let PAR_SB = null;
function parSb() {
  if (!PAR_SB) PAR_SB = window.supabase.createClient(PAR_SB_URL, PAR_SB_KEY, { db: { schema: 'hub' } });
  return PAR_SB;
}

const PAR = {
  eu: null, frotas: [], metas: new Map(), enviados: [], sel: null, faz: null, rascunho: null, sobras: [],
  aba: 'processar', vigentes: {}, geo: {}, fila: null, itens: [], mapa: null,
};
const PAR_FASES = ['preparando', 'lendo', 'linhas', 'analise'];
const PAR_FASE_TXT = {
  preparando: 'Preparando a análise (na primeira vez leva alguns segundos)', lendo: 'Lendo as trilhas',
  linhas: 'Montando as linhas', analise: 'Medindo o espaçamento',
};
const PAR_ABAS = {
  painel: ['Painel', 'Aderência por fazenda, talhão e mês, só com as análises vigentes.'],
  pendentes: ['Pendentes', 'Rodadas esperando validação de um editor.'],
  rodadas: ['Rodadas', 'Histórico de rodadas, com quem processou e o link dos brutos.'],
};

function parEsc(s) { return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function parMb(bytes) { return `${(bytes / 1048576).toFixed(1).replace('.', ',')} MB`; }
function parPlural(n, um, varios) { return `${n} ${n === 1 ? um : varios}`; }
function parPodeProcessar() { return !!PAR.eu && ['solicitante', 'editor', 'admin'].includes(PAR.eu.nivel); }
function parEhEditor() { return !!PAR.eu && ['editor', 'admin'].includes(PAR.eu.nivel); }
const $par = (id) => document.getElementById(id);

// ── API real ──
const parApiReal = {
  async sessao() {
    const { data, error } = await parSb().auth.getSession();
    if (error) throw error;
    return data.session ? data.session.user : null;
  },
  async entrar(email, senha) {
    const { error } = await parSb().auth.signInWithPassword({ email, password: senha });
    if (!error) return;
    if (/banned/i.test(error.message)) throw new Error('Acesso bloqueado. Se o seu cadastro no GeoMap é novo, defina sua senha lá primeiro.');
    if (/invalid/i.test(error.message)) throw new Error('E-mail ou senha incorretos.');
    throw new Error('Não foi possível entrar agora. Tente de novo.');
  },
  async sair() {
    const { error } = await parSb().auth.signOut();
    if (error) throw error;
  },
  async eu() {
    const user = await parApiReal.sessao();
    if (!user) return null;
    const { data, error } = await parSb().from('usuarios').select('id,nome,admin').eq('id', user.id).maybeSingle();
    if (error) throw error;
    if (!data) return null;
    const { data: nivel, error: e2 } = await parSb().rpc('paralelismo_nivel');
    if (e2) throw e2;
    return { id: data.id, nome: data.nome, admin: !!data.admin, nivel, pode: !!nivel };
  },
  async frotas() {
    const { data, error } = await parSb().from('paralelismo_frotas').select('serie,frota,operacao,tipo,nomes_antigos,observacao').order('serie');
    if (error) throw error;
    return data;
  },
  async salvarFrota(f) {
    const { error } = await parSb().from('paralelismo_frotas').upsert(f, { onConflict: 'serie' });
    if (error) throw error;
  },
  async jaAnalisados(shas) {
    const { data, error } = await parSb().rpc('paralelismo_ja_analisados', { p_sha256: shas });
    if (error) throw error;
    return data || [];
  },
  async buscarBase(operacao, codFaz) {
    const [v, t] = await Promise.all([
      parSb().rpc('paralelismo_linhas_vigentes', { p_operacao: operacao, p_cod_faz: codFaz }),
      parSb().rpc('paralelismo_talhoes_fazenda', { p_cod_faz: codFaz }),
    ]);
    if (v.error) throw v.error;
    if (t.error) throw t.error;
    let vigente = null;
    if (v.data.analise_id) {
      const { data } = await parSb().from('paralelismo_analises').select('amostras,aderentes').eq('id', v.data.analise_id).maybeSingle();
      vigente = data || null;
    }
    return { analise_id: v.data.analise_id, linhas: v.data.linhas, talhoes: t.data, vigente };
  },
  async pendentes() {
    const { count, error } = await parSb().from('paralelismo_rodadas').select('id', { count: 'exact', head: true }).eq('status', 'pendente');
    if (error) throw error;
    return count || 0;
  },
  async preparar(id) {
    const { data, error } = await parSb().rpc('paralelismo_preparar_parte', { p_rodada_id: id });
    if (error) throw error;
    return Number(data);
  },
  async subir(nome, conteudo, id) {
    const sessao = (await parSb().auth.getSession()).data.session;
    if (!sessao) throw new Error('Sessão expirada; entre de novo');
    const fd = new FormData();
    fd.append('rodada_id', String(id));
    fd.append('nome', nome);
    fd.append('arquivo', conteudo instanceof Blob ? conteudo : new Blob([conteudo]), nome);
    const r = await fetch(`${PAR_WORKER_URL}/paralelismo/parte`, { method: 'POST', headers: { Authorization: `Bearer ${sessao.access_token}` }, body: fd });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(j.erro || `HTTP ${r.status}`), { rodada_id: j.rodada_id });
    return j;
  },
  async enviar(carga) {
    const { data, error } = await parSb().rpc('paralelismo_enviar', { p: carga });
    if (error) throw error;
    return data;
  },
};
function parApi() { return PAR_DEMO ? PAR_API_DEMO : parApiReal; }

// ── Utilidades de interface ──
function parToast(msg, erro = false) {
  const t = $par('par-toast');
  t.textContent = msg;
  t.classList.toggle('erro', erro);
  t.classList.add('show');
  clearTimeout(parToast.timer);
  parToast.timer = setTimeout(() => t.classList.remove('show'), 3200);
}
function parDialogo(titulo, texto, botoes) {
  return new Promise((resolver) => {
    const fundo = $par('par-fundo');
    fundo.innerHTML = `<div class="par-modal" role="dialog" aria-modal="true" aria-labelledby="par-md-tit"><h3 id="par-md-tit">${parEsc(titulo)}</h3><p>${parEsc(texto)}</p>
      <div class="par-acoes">${botoes.map((b, i) => `<button class="${b.classe}" type="button" data-i="${i}">${parEsc(b.rotulo)}</button>`).join('')}</div></div>`;
    const fechar = (v) => { fundo.classList.add('off'); fundo.innerHTML = ''; resolver(v); };
    fundo.onclick = (e) => { if (e.target === fundo) fechar(null); };
    fundo.querySelectorAll('button').forEach((b) => { b.onclick = () => fechar(botoes[Number(b.dataset.i)].valor); });
    fundo.classList.remove('off');
    fundo.querySelector('button').focus();
  });
}
function parMostrar(tela) {
  for (const t of ['carregando', 'login', 'sem-acesso', 'app']) $par(`par-${t}`).classList.toggle('off', t !== tela);
}

// ── Entrada: login, sessão e acesso ──
async function parEntrar(e) {
  e.preventDefault();
  const email = $par('par-email').value.trim(), senha = $par('par-senha').value;
  const erro = $par('par-login-erro'), btn = $par('par-entrar');
  erro.textContent = '';
  if (!email || !senha) { erro.textContent = 'Informe e-mail e senha.'; return; }
  btn.disabled = true;
  btn.textContent = 'Entrando…';
  try {
    await parApi().entrar(email, senha);
    $par('par-senha').value = '';
    await parCarregarEntrada();
  } catch (err) {
    erro.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Entrar';
  }
}
async function parCarregarEntrada() {
  let eu;
  try {
    eu = await parApi().eu();
  } catch (e) {
    parMostrar('login');
    $par('par-login-erro').textContent = 'Não foi possível verificar seu acesso. Tente de novo.';
    return;
  }
  PAR.eu = eu;
  if (!eu || !eu.pode) { parMostrar('sem-acesso'); return; }
  $par('par-nome').textContent = eu.nome;
  parMostrar('app');
  parCriarFilaDaTela();
  parDesenharAbas();
  parRenderTudo();
  parIniciarMapa();
  try { PAR.frotas = await parApi().frotas(); } catch (e) { parToast('Não foi possível carregar as frotas.', true); }
  if (parEhEditor()) parApi().pendentes().then((n) => parContador(n)).catch(() => {});
  parVerSobras();
  setTimeout(parVerSobras, 900);   // logo após recarregar, o lock da sessão anterior ainda pode aparecer
  if (PAR_DEMO && !PAR.metas.size) parExemploDemo();
  parRenderTudo();
}
async function parSair() {
  try {
    await parApi().sair();
  } catch (e) {
    parToast('Não foi possível sair. Tente de novo.', true);
    return;
  }
  location.reload();
}
function parContador(n) {
  const c = $par('par-cont');
  c.textContent = n;
  c.classList.toggle('off', !n);
}

// ── Fila e sobras ──
function parCriarFilaDaTela() {
  if (PAR.fila) return;
  PAR.fila = parCriarFila({
    criarWorker: () => (PAR_DEMO ? new ParWorkerDemo() : new Worker('paralelismo-worker.js')),
    buscarBase: parBuscarBase,
    aoMudar: (itens) => { PAR.itens = itens; parRenderTudo(true); },
  });
}
async function parBuscarBase(operacao, codFaz) {
  const b = await parApi().buscarBase(operacao, codFaz);
  PAR.geo[codFaz] = b.talhoes;
  const chave = `${operacao}|${codFaz}`;
  if (b.vigente) PAR.vigentes[chave] = b.vigente; else delete PAR.vigentes[chave];
  return { analise_id: b.analise_id, linhas: b.linhas, talhoes: b.talhoes };
}
async function parVerSobras() {
  try { PAR.sobras = await parOpfsSobras(); } catch (e) { PAR.sobras = []; }
  parRenderTudo(true);
}
async function parDescartarSobras() {
  const ok = await parDialogo('Descartar cópias antigas?', 'Elas são de uma sessão que acabou e nada foi enviado delas. Para analisar de novo, escolha a pasta do pen-drive outra vez.',
    [{ rotulo: 'Cancelar', classe: 'par-btn2', valor: false }, { rotulo: 'Descartar', classe: 'par-btn', valor: true }]);
  if (!ok) return;
  for (const s of PAR.sobras) await parOpfsDescartar(s.id).catch(() => {});
  await parVerSobras();
  parToast('Cópias antigas descartadas.');
}

// ── Escolher pasta, copiar e conferir ──
function parPasta() {
  let el = $par('par-pasta');
  if (!el) {
    el = document.createElement('input');
    Object.assign(el, { type: 'file', id: 'par-pasta', multiple: true, hidden: true });
    el.setAttribute('webkitdirectory', '');
    el.addEventListener('change', parAoEscolher);
    document.body.appendChild(el);
  }
  return el;
}
async function parAoEscolher(e) {
  const files = [...e.target.files];
  e.target.value = '';
  if (!files.length) return;
  if (PAR.rascunho) await parDescartarRascunho();
  const id = `c${Date.now().toString(36)}`;
  const nome = (files[0].webkitRelativePath || files[0].name).split('/')[0];
  const r = PAR.rascunho = { id, nome, estado: 'copiando', pct: 0, arquivos: [], mapas: [], falhas: [], ja: [], gs3: {}, cadastrando: null, erro: null };
  parRenderTudo();
  try {
    const copia = await parOpfsCopiar(id, files, { aoProgresso: ({ feitos, total }) => { r.pct = total ? Math.floor(100 * feitos / total) : 100; parRenderTudo(true); } });
    Object.assign(r, copia);
  } catch (err) {
    r.estado = 'erro';
    r.erro = /espaço/.test(err.message) ? err.message : 'Não foi possível copiar o pen-drive para o navegador. Escolha a pasta de novo.';
    await parOpfsDescartar(id).catch(() => {});
    parRenderTudo();
    return;
  }
  r.estado = 'conferencia';
  await parConferirJaAnalisados();   // falha aqui não descarta a cópia: só repete esta consulta
}
async function parConferirJaAnalisados() {
  const r = PAR.rascunho;
  if (!r) return;
  r.ja = null;
  try {
    r.ja = await parApi().jaAnalisados(r.arquivos.map((a) => a.sha256));
  } catch (err) {
    r.ja = null;
  }
  parRenderTudo();
}
async function parDescartarRascunho() {
  const r = PAR.rascunho;
  PAR.rascunho = null;
  if (r) await parOpfsDescartar(r.id).catch(() => {});
  parRenderTudo();
}
// Conferência com a frota final: o GS3 usa a frota digitada (ou a sugerida pela pasta) no cadastro 'GS3:<frota>'.
function parGruposRascunho() {
  const r = PAR.rascunho;
  // Além do banco, o que já está na fila desta página (ainda não enviado) também conta como repetido.
  const locais = [...PAR.metas.values()].flatMap((m) => m.todos.map((a) => a.sha256));
  const grupos = parConferencia([...r.arquivos, ...r.mapas], PAR.frotas, [...(r.ja || []), ...locais]);
  return grupos.map((g) => {
    if (g.tipo !== 'gs3') return g;
    const escolhida = r.gs3[g.trator] ?? g.frotaSugerida ?? '';
    const cad = PAR.frotas.find((x) => x.serie === `GS3:${escolhida}`);
    const avisos = g.avisos.filter((a) => a !== 'serie_desconhecida');
    if (!cad) avisos.unshift('serie_desconhecida');
    return { ...g, frotaEscolhida: escolhida, frota: cad ? cad.frota : null, operacao: cad ? cad.operacao : null, avisos };
  });
}
const parSerieDe = (g) => (g.tipo === 'gs3' ? (g.frotaEscolhida ? `GS3:${g.frotaEscolhida}` : null) : g.trator);

async function parSalvarCadastro(i, form) {
  const g = parGruposRascunho()[i];
  const serie = parSerieDe(g);
  const frota = form.frota.value.trim();
  if (!serie || !frota) { parToast('Informe a frota.', true); return; }
  try {
    await parApi().salvarFrota({ serie, frota, operacao: form.operacao.value, tipo: form.tipo.value });
    PAR.frotas = await parApi().frotas();
    PAR.rascunho.cadastrando = null;
    parToast('Frota cadastrada.');
  } catch (e) {
    parToast('Não foi possível cadastrar a frota. Só editores cadastram.', true);
  }
  parRenderTudo();
}

function parAdicionarAFila() {
  const r = PAR.rascunho;
  const grupos = parGruposRascunho().filter((g) => g.nArquivos > 0);
  const plano = parPlanoDoItem(grupos, r.arquivos);
  PAR.metas.set(r.id, { id: r.id, nome: r.nome, todos: r.arquivos, grupos, falhas: r.falhas, plano, rodadaId: null, erroEnvio: null, enviando: false });
  PAR.rascunho = null;
  PAR.sel = r.id;
  PAR.faz = null;
  PAR.fila.adicionar({ id: r.id, plano });
}

// ── Enviar para validação ──
async function parZipFflate(arquivos, ler) {
  const pedacos = [];
  let falha = null;
  const zip = new fflate.Zip((err, chunk) => { if (err) falha = err; else pedacos.push(chunk); });
  for (const a of arquivos) {
    const f = new fflate.ZipDeflate(a.caminho, { level: 3 });
    zip.add(f);
    f.push(await ler(a.opfs), true);
  }
  zip.end();
  if (falha) throw falha;
  return new Blob(pedacos, { type: 'application/zip' });
}
async function parEnviar(id) {
  const meta = PAR.metas.get(id), item = PAR.itens.find((i) => i.id === id);
  if (!meta || !item || meta.enviando) return;
  meta.enviando = true;
  meta.erroEnvio = null;
  parRenderTudo();
  const api = parApi();
  const deps = {
    preparar: (rid) => api.preparar(rid),
    zip: (parte) => (meta.simulado ? Promise.resolve(new Blob(['demo'])) : parZipFflate(parte, (opfs) => parOpfsLer(id, opfs))),
    subir: (nome, conteudo, rid) => api.subir(nome, conteudo, rid),
    enviar: (carga) => api.enviar(carga),
  };
  const previa = parPrevia(item.resultado, PAR.vigentes);
  try {
    const r = await parEnviarItem({ rodadaId: meta.rodadaId, todos: meta.todos, grupos: meta.grupos, resultado: item.resultado, descricao: `Pen-drive ${meta.nome}` }, deps);
    PAR.enviados.push({ nome: meta.nome, rodadaId: r.rodadaId, fazendas: previa.enviaveis });
    PAR.metas.delete(id);
    if (PAR.sel === id) PAR.sel = null;
    PAR.faz = null;
    await PAR.fila.remover(id).catch(() => {});
    parToast(`Enviado para validação (rodada ${r.rodadaId}).`);
    if (parEhEditor()) api.pendentes().then(parContador).catch(() => {});
  } catch (e) {
    const causa = (e.causa && e.causa.message) || '';
    if (/rodada_ja_enviada/.test(causa)) {   // gravou, mas a resposta se perdeu: já está enviado
      PAR.enviados.push({ nome: meta.nome, rodadaId: e.rodadaId, fazendas: previa.enviaveis });
      PAR.metas.delete(id);
      if (PAR.sel === id) PAR.sel = null;
      PAR.faz = null;
      await PAR.fila.remover(id).catch(() => {});
      parToast(`A rodada ${e.rodadaId} já tinha sido gravada; está aguardando validação.`);
    } else {
      meta.erroEnvio = e.message;
      meta.rodadaId = /rodada_invalida/.test(causa) ? null : (e.rodadaId ?? meta.rodadaId);   // reserva inválida: pede outro id
    }
  } finally {
    meta.enviando = false;
    parRenderTudo();
  }
}
async function parRemover(id) {
  const ok = await parDialogo('Descartar este pen-drive?', 'A cópia no navegador será apagada e nada será enviado.',
    [{ rotulo: 'Cancelar', classe: 'par-btn2', valor: false }, { rotulo: 'Descartar', classe: 'par-btn', valor: true }]);
  if (!ok) return;
  PAR.metas.delete(id);
  if (PAR.sel === id) { PAR.sel = null; PAR.faz = null; }
  await PAR.fila.remover(id);
}

// ── Demonstração: um pen-drive pronto, para ver a prévia sem escolher pasta ──
function parExemploDemo() {
  const arq = (caminho, n, fdl) => ({ caminho, bytes: 4096 * n, sha256: String(n).padStart(64, '0'), opfs: `demo${n}`, tipo: 'jdl', serie: 'BM0000X000001', cod_faz: 10001, fazenda_monitor: '2026_USINA_10001Rev0', data: '2026-10-26' });
  const arquivos = [arq('PEN-DEMO/JD-Data/log/2026_USINA_10001Rev0/2026_10_26_08_00_00.jdl', 1), arq('PEN-DEMO/JD-Data/log/2026_USINA_10001Rev0/2026_10_26_14_00_00.jdl', 2)];
  const grupos = [{ tipo: 'jdl', trator: 'BM0000X000001', frota: '90001', operacao: 'cana', fazendas: [10001], nArquivos: 2, nJaAnalisados: 0, avisos: [], arquivos }];
  const plano = parPlanoDoItem(grupos, arquivos);
  PAR.metas.set('demo', { id: 'demo', nome: 'PEN-DEMO', todos: arquivos, grupos, falhas: [], plano, rodadaId: null, erroEnvio: null, enviando: false, simulado: true });
  PAR.sel = 'demo';
  PAR.fila.adicionar({ id: 'demo', plano });
}

// ===== Desenho da coluna =====
function parDesenharAbas() {
  document.querySelectorAll('.par-aba').forEach((b) => { b.onclick = () => { PAR.aba = b.dataset.aba; PAR.faz = null; parRenderTudo(); }; });
}
// auto = disparado pela fila ou pela cópia, não pelo usuário: se ele está digitando na coluna (cadastro de frota,
// frota do GS3), a coluna não é refeita, para não apagar o texto, o foco nem engolir o clique.
function parRenderTudo(auto = false) {
  if (!$par('par-app') || $par('par-app').classList.contains('off')) return;
  document.querySelectorAll('.par-aba').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.aba === PAR.aba)));
  const col = $par('par-col'), topo = col.scrollTop;
  const editando = col.contains(document.activeElement) && /^(INPUT|SELECT)$/.test(document.activeElement.tagName);
  if (!(auto && (editando || (PAR.rascunho && PAR.rascunho.cadastrando != null)))) {
    col.innerHTML = PAR.aba === 'processar' ? parHtmlProcessar() : parHtmlOutraAba();
    col.scrollTop = topo;
  }
  parRenderFaixa();
  parMapaAtualizar();
}
function parHtmlOutraAba() {
  const [titulo, texto] = PAR_ABAS[PAR.aba];
  return `<div><div class="par-ey">Paralelismo</div><h2>${titulo}</h2><p>${texto}</p></div>
    <div class="par-aviso"><span class="ico">schedule</span><div>Esta seção chega na próxima etapa. Por enquanto, use <b>Processar</b> para analisar um pen-drive.</div></div>`;
}

function parHtmlProcessar() {
  if (!parPodeProcessar()) {
    return `<div><div class="par-ey">Paralelismo</div><h2>Processar</h2></div>
      <div class="par-aviso"><span class="ico">lock</span><div>Seu nível é de leitura: você vê os resultados, mas só <b>solicitantes</b> e <b>editores</b> processam pen-drives.</div></div>`;
  }
  const partes = [`<div><div class="par-ey">Paralelismo</div><h2>Processar pen-drive</h2>
    <p>Escolha a pasta do pen-drive. A análise roda neste navegador; deixe a página aberta até terminar.</p></div>`];
  if (PAR.sobras.length) partes.push(parHtmlSobras());
  partes.push(PAR.rascunho ? parHtmlRascunho() : `<div class="par-acoes"><button class="par-btn" type="button" data-acao="escolher"><span class="ico">folder_open</span>Escolher pasta do pen-drive</button></div>`);
  partes.push(parHtmlFila());
  const sel = PAR.itens.find((i) => i.id === PAR.sel);
  if (sel) partes.push(parHtmlItem(sel));
  return partes.join('');
}
function parHtmlSobras() {
  const total = PAR.sobras.reduce((s, x) => s + x.bytes, 0);
  return `<div class="par-aviso"><span class="ico">history</span><div>Sobrou no navegador a cópia de ${parPlural(PAR.sobras.length, 'pen-drive', 'pen-drives')} de uma sessão anterior (${parMb(total)}). Nada foi enviado delas.
    <div class="par-acoes" style="margin-top:6px"><button class="par-btn2" type="button" data-acao="descartar-sobras">Descartar cópias antigas</button></div></div></div>`;
}

function parHtmlRascunho() {
  const r = PAR.rascunho;
  const cab = `<div class="par-ey">Pen-drive</div><h3 style="font-size:14px;margin:2px 0 0">${parEsc(r.nome)}</h3>`;
  if (r.estado === 'copiando') {
    return `<div>${cab}<p>Copiando para o navegador… ${r.pct}%</p><div class="par-barra" role="progressbar" aria-valuenow="${r.pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${r.pct}%"></i></div></div>`;
  }
  if (r.estado === 'erro') {
    return `<div>${cab}<div class="par-aviso erro" role="alert"><span class="ico">error</span><div>${parEsc(r.erro)}</div></div>
      <div class="par-acoes" style="margin-top:8px"><button class="par-btn2" type="button" data-acao="escolher">Escolher a pasta de novo</button><button class="par-btn2" type="button" data-acao="descartar-rascunho">Fechar</button></div></div>`;
  }
  const grupos = parGruposRascunho();
  const usaveis = r.ja === null ? [] : grupos.filter((g) => g.nArquivos > 0 && g.frota);
  const faltaMapa = grupos.length === 0;
  return `<div>${cab}
    <div class="par-aviso ok" style="margin-top:8px"><span class="ico">usb</span><div><b>Cópia pronta: pode retirar o pen-drive.</b></div></div></div>
    ${r.ja === null ? `<div class="par-aviso erro" role="alert"><span class="ico">wifi_off</span><div>Não foi possível conferir no Hub se os arquivos já foram analisados. A cópia está guardada.
      <div class="par-acoes" style="margin-top:6px"><button class="par-btn2" type="button" data-acao="reconferir">Conferir de novo</button></div></div></div>` : ''}
    ${r.falhas.length ? `<div class="par-aviso erro"><span class="ico">error</span><div>${parPlural(r.falhas.length, 'arquivo não pôde', 'arquivos não puderam')} ser copiado(s) e ficaram de fora.</div></div>` : ''}
    <div><h3>Conferência <small>${parPlural(grupos.length, 'trator', 'tratores')}</small></h3>
    <div class="par-cartoes-trator">${grupos.map((g, i) => parHtmlTrator(g, i)).join('') || '<p>Nenhum arquivo .jdl, .fdl ou .fdd nesta pasta.</p>'}</div></div>
    <div class="par-acoes">
      <button class="par-btn" type="button" data-acao="adicionar" ${usaveis.length ? '' : 'disabled'}><span class="ico">playlist_add</span>Adicionar à fila</button>
      <button class="par-btn2" type="button" data-acao="descartar-rascunho">Descartar</button>
    </div>${faltaMapa ? '' : usaveis.length ? '' : '<p>Cadastre a frota dos tratores acima para poder analisar.</p>'}`;
}
function parHtmlTrator(g, i) {
  const r = PAR.rascunho;
  const serie = parSerieDe(g);
  const avisos = [];
  if (g.avisos.includes('serie_desconhecida')) {
    avisos.push(serie
      ? `<div class="par-aviso"><span class="ico">help</span><div>Série <b>${parEsc(serie)}</b> sem frota cadastrada; sem isso os arquivos são pulados.
        ${parEhEditor() ? `<div class="par-acoes" style="margin-top:6px"><button class="par-btn2" type="button" data-acao="cadastrar" data-i="${i}">Cadastrar frota</button></div>` : '<br>Peça a um editor para cadastrar.'}</div></div>`
      : '<div class="par-aviso"><span class="ico">help</span><div>Nenhuma série de trator identificada nestes arquivos; eles serão pulados.</div></div>');
  }
  if (g.avisos.includes('gs3_sem_documentacao')) avisos.push('<div class="par-aviso"><span class="ico">folder_off</span><div>Sem executado (só mapa de cobertura e linhas-guia). Exporte de novo com <b>Documentation</b>.</div></div>');
  if (g.avisos.includes('ja_analisados')) avisos.push(`<div class="par-aviso"><span class="ico">done_all</span><div>${parPlural(g.nJaAnalisados, 'arquivo já foi analisado', 'arquivos já foram analisados')} em outra rodada e ${g.nJaAnalisados === 1 ? 'será ignorado' : 'serão ignorados'}.</div></div>`);
  const form = r.cadastrando === i ? `<form class="par-form-frota" data-form-frota="${i}">
      <label>Frota<input name="frota" value="${parEsc(g.tipo === 'gs3' ? g.frotaEscolhida : '')}" required></label>
      <label>Operação<select name="operacao"><option value="cana">Cana</option><option value="torta">Torta</option></select></label>
      <label>Tipo<select name="tipo"><option value="propria">Própria</option><option value="prestador">Prestador</option></select></label>
      <div class="acoes"><button class="par-btn" type="submit">Salvar frota</button><button class="par-btn2" type="button" data-acao="cancelar-cadastro">Cancelar</button></div></form>` : '';
  const gs3 = g.tipo === 'gs3' ? `<label class="sub">Frota desta pasta GS3 <input data-gs3="${parEsc(g.trator)}" value="${parEsc(g.frotaEscolhida)}" size="8" aria-label="Frota da pasta GS3"></label>` : '';
  return `<div class="par-trator"><div class="topo"><span class="nome">${g.tipo === 'gs3' ? 'GS3 · ' : ''}${parEsc(g.trator || 'série não identificada')}</span>
      ${g.operacao ? `<span class="par-pil ${g.operacao}">${g.operacao}</span>` : '<span class="par-pil">sem frota</span>'}</div>
    <div class="sub num">${g.frota ? `Frota ${parEsc(g.frota)} · ` : ''}${parPlural(g.nArquivos, 'arquivo novo', 'arquivos novos')} · ${g.fazendas.length ? `fazenda${g.fazendas.length > 1 ? 's' : ''} ${g.fazendas.join(', ')}` : 'sem fazenda identificada'}</div>
    ${gs3}${avisos.join('')}${form}</div>`;
}

function parHtmlFila() {
  if (!PAR.itens.length && !PAR.enviados.length) return '';
  const itens = PAR.itens.map((i) => {
    const meta = PAR.metas.get(i.id);
    const pil = { na_fila: ['', 'na fila'], processando: ['proc', `${i.pct_item || 0}%`], pronto: ['pronto', 'pronto'], erro: ['erro', 'erro'] }[i.estado];
    return `<button class="par-item" type="button" data-acao="abrir" data-id="${parEsc(i.id)}" aria-current="${i.id === PAR.sel}">
      <span><b>${parEsc(meta ? meta.nome : i.id)}</b><br><span class="sub">${i.estado === 'processando' ? parEsc(PAR_FASE_TXT[i.fase] || '') : parPlural(meta ? meta.plano.fazendas.length : 0, 'fazenda', 'fazendas')}</span></span>
      <span class="par-pil ${pil[0]}">${pil[1]}</span>
      ${i.estado === 'processando' ? `<div class="par-barra" role="progressbar" aria-valuenow="${i.pct_item || 0}" aria-valuemin="0" aria-valuemax="100"><i style="width:${i.pct_item || 0}%"></i></div>` : ''}</button>`;
  }).join('');
  const enviados = PAR.enviados.map((e) => `<div class="par-item" style="cursor:default"><span><b>${parEsc(e.nome)}</b><br><span class="sub">Rodada ${e.rodadaId} · ${parPlural(e.fazendas, 'fazenda', 'fazendas')} · aguardando validação</span></span><span class="par-pil pronto">enviado</span></div>`).join('');
  return `<div><h3>Fila <small>${parPlural(PAR.itens.length, 'pen-drive', 'pen-drives')}</small></h3><div class="par-lista" id="par-fila">${itens}${enviados}</div></div>`;
}

function parHtmlItem(item) {
  const meta = PAR.metas.get(item.id);
  if (!meta) return '';
  const nome = `<div class="par-ey">Pen-drive</div><h3 style="font-size:14px;margin:2px 0 0">${parEsc(meta.nome)}</h3>`;
  if (item.estado === 'na_fila') return `<div>${nome}<p>Na fila. Começa quando o item anterior terminar.</p></div>`;
  if (item.estado === 'processando') return `<div>${nome}<p>Processando… ${item.pct_item || 0}%. A página precisa ficar aberta.</p></div>`;
  if (item.estado === 'erro') {
    return `<div>${nome}<div class="par-aviso erro" role="alert"><span class="ico">error</span><div>${parEsc(item.erro)}<br>Nada foi gravado.</div></div>
      <div class="par-acoes" style="margin-top:8px"><button class="par-btn" type="button" data-acao="de-novo" data-id="${parEsc(item.id)}">Tentar de novo</button>
      ${item.erro === PAR_ERRO_PREPARO ? '<button class="par-btn2" type="button" data-acao="recarregar">Recarregar a página</button>' : ''}
      <button class="par-btn2" type="button" data-acao="remover" data-id="${parEsc(item.id)}">Descartar</button></div></div>`;
  }
  return parHtmlPrevia(item, meta, nome);
}

function parHtmlPrevia(item, meta, nome) {
  const previa = parPrevia(item.resultado, PAR.vigentes);
  const avisosItem = parAvisosItem(item.resultado, meta.falhas);
  const fazSel = previa.fazendas.find((f) => `${f.operacao}|${f.cod_faz}` === PAR.faz) || null;
  const bloco = (a) => `<div class="par-aviso"><span class="ico">warning</span><div>${parEsc(a.texto)}${a.arquivos ? `<ul>${a.arquivos.slice(0, 4).map((c) => `<li>${parEsc(c)}</li>`).join('')}${a.arquivos.length > 4 ? `<li>e mais ${a.arquivos.length - 4}</li>` : ''}</ul>` : ''}</div></div>`;
  const fazendas = previa.fazendas.map((f) => {
    const chave = `${f.operacao}|${f.cod_faz}`;
    const cor = parCorPct(f.amostras ? f.aderentes / f.amostras : 0);
    return `<button class="par-item" type="button" data-acao="faz" data-chave="${chave}" aria-current="${chave === PAR.faz}">
      <span><b>${f.cod_faz}</b> <span class="par-pil ${f.operacao}">${f.operacao}</span><br><span class="sub num">${f.amostras} amostras · ${f.foraTalhao} fora de talhão${f.vigentePctTxt ? ` · vigente ${f.vigentePctTxt}` : ' · fazenda nova'}</span></span>
      <span style="text-align:right"><b class="num">${f.pctTxt}</b>${f.deltaTxt ? `<br><span class="sub num">${f.deltaTxt}</span>` : ''}</span>
      <div class="par-barra"><i style="width:${f.amostras ? Math.round(100 * f.aderentes / f.amostras) : 0}%;background:${cor}"></i></div></button>${f.avisos.map(bloco).join('')}`;
  }).join('');
  const detalhe = fazSel ? `<div><h3>Talhões da ${fazSel.cod_faz} <small>aderência</small></h3>${fazSel.talhoes.map((t) => `<div class="par-linha"><b>${t.talhao_num}</b>
      <div><div class="sub num">${t.amostras} amostras${t.insuficiente ? ' · insuficiente' : ''}</div><div class="mini"><i style="width:${t.amostras ? Math.round(100 * t.aderentes / t.amostras) : 0}%;background:${parCorPct(t.amostras ? t.aderentes / t.amostras : 0)}"></i></div></div><b class="num">${t.pctTxt}</b></div>`).join('')}
    <h3 style="margin-top:12px">Frotas</h3>${fazSel.frotas.map((x) => `<div class="par-linha"><b>${parEsc(x.frota)}</b><span class="sub num">${x.amostras} amostras</span><b class="num">${x.pctTxt}</b></div>`).join('')}</div>` : '';
  const retomar = !!meta.erroEnvio;
  return `<div>${nome}</div>
    <div class="par-grande"><span class="v num">${previa.total.pctTxt}</span><span class="sub" style="color:var(--t3)">aderentes (${previa.total.amostras} amostras)</span></div>
    ${avisosItem.map(bloco).join('')}
    ${previa.fazendas.length ? `<div><h3>Fazendas <small>toque para ver os talhões</small></h3><div class="par-lista">${fazendas}</div></div>` : '<div class="par-aviso"><span class="ico">info</span><div>Nenhuma fazenda para analisar neste pen-drive.</div></div>'}
    ${detalhe}
    ${meta.erroEnvio ? `<div class="par-aviso erro" role="alert"><span class="ico">error</span><div>${parEsc(meta.erroEnvio)}</div></div>` : ''}
    <div class="par-acoes"><button class="par-btn" type="button" data-acao="enviar" data-id="${parEsc(item.id)}" ${meta.enviando || !previa.enviaveis ? 'disabled' : ''}>
      <span class="ico">cloud_upload</span>${meta.enviando ? 'Enviando…' : retomar ? 'Tentar de novo' : 'Enviar para validação'}</button>
      <button class="par-btn2" type="button" data-acao="remover" data-id="${parEsc(item.id)}" ${meta.enviando ? 'disabled' : ''}>Descartar</button></div>`;
}

function parCorPct(p) {
  return p < 0.5 ? 'var(--r1)' : p < 0.7 ? 'var(--r2)' : p < 0.85 ? 'var(--r3)' : 'var(--r4)';
}

// Faixa de fases no mapa (padrão de espera do Hub).
function parRenderFaixa() {
  const f = $par('par-faixa');
  const proc = PAR.itens.find((i) => i.estado === 'processando');
  f.classList.toggle('off', !proc || PAR.aba !== 'processar');
  if (!proc) return;
  const meta = PAR.metas.get(proc.id);
  const k = Math.max(0, PAR_FASES.indexOf(proc.fase));
  f.innerHTML = `<span class="par-campo" aria-hidden="true"><i></i><i></i><i></i><i></i></span><div class="txt"><div class="t">${parEsc(PAR_FASE_TXT[proc.fase] || 'Processando')}</div>
    <div class="s num">${parEsc(meta ? meta.nome : '')}${proc.fazenda ? ` · fazenda ${proc.fazenda}` : ''} · ${proc.pct_item || 0}%</div>
    <div class="par-passos">${PAR_FASES.map((_, j) => `<span class="${j < k ? 'feito' : j === k ? 'agora' : ''}"></span>`).join('')}</div></div>`;
}

// ===== Eventos da coluna =====
function parLigarColuna() {
  const col = $par('par-col');
  col.addEventListener('click', (e) => {
    const b = e.target.closest('[data-acao]');
    if (!b) return;
    clearTimeout(parLigarColuna.timer);
    const id = b.dataset.id;
    const acao = {
      escolher: () => parPasta().click(),
      'descartar-sobras': parDescartarSobras,
      'descartar-rascunho': parDescartarRascunho,
      adicionar: parAdicionarAFila,
      reconferir: parConferirJaAnalisados,
      cadastrar: () => { PAR.rascunho.cadastrando = Number(b.dataset.i); parRenderTudo(); },
      'cancelar-cadastro': () => { PAR.rascunho.cadastrando = null; parRenderTudo(); },
      abrir: () => { PAR.sel = id; PAR.faz = null; parRenderTudo(); },
      faz: () => { PAR.faz = PAR.faz === b.dataset.chave ? null : b.dataset.chave; parRenderTudo(); },
      'de-novo': () => PAR.fila.tentarDeNovo(id),
      recarregar: () => location.reload(),
      remover: () => parRemover(id),
      enviar: () => parEnviar(id),
    }[b.dataset.acao];
    if (acao) acao();
  });
  col.addEventListener('submit', (e) => {
    const f = e.target.closest('[data-form-frota]');
    if (!f) return;
    e.preventDefault();
    parSalvarCadastro(Number(f.dataset.formFrota), f);
  });
  col.addEventListener('change', (e) => {
    const g = e.target.closest('[data-gs3]');
    if (g && PAR.rascunho) {
      PAR.rascunho.gs3[g.dataset.gs3] = g.value.trim();
      clearTimeout(parLigarColuna.timer);
      parLigarColuna.timer = setTimeout(parRenderTudo, 500);   // um clique logo em seguida já refaz a coluna, sem perdê-lo
    }
  });
}

// ===== Mapa (canvas): talhões pintados pela aderência; varredura enquanto processa =====
const PAR_MAPA = { feicoes: [], chave: null, escala: 1, ox: 0, oy: 0, bbox: null, arrasto: null, raf: 0 };

function parGeoDoItem() {
  const meta = PAR.metas.get(PAR.sel);
  if (!meta || PAR.aba !== 'processar') return null;
  const item = PAR.itens.find((i) => i.id === PAR.sel);
  const chaveFaz = PAR.faz || (meta.plano.fazendas[0] ? `${meta.plano.fazendas[0].operacao}|${meta.plano.fazendas[0].cod_faz}` : null);
  if (!chaveFaz) return null;
  const [operacao, cod] = chaveFaz.split('|');
  const geo = PAR.geo[cod];
  if (!geo) return null;
  const cores = {};
  if (item && item.estado === 'pronto') {
    const f = parPrevia(item.resultado, PAR.vigentes).fazendas.find((x) => `${x.operacao}|${x.cod_faz}` === chaveFaz);
    if (f) for (const t of f.talhoes) cores[t.talhao_num] = t.amostras ? parCorPct(t.aderentes / t.amostras) : null;
  }
  return { chave: `${PAR.sel}|${chaveFaz}`, geo, cores, cod, operacao, item };
}
function parMapaAtualizar() {
  const canvas = $par('par-canvas');
  if (!canvas) return;
  const g = parGeoDoItem();
  const M = PAR_MAPA;
  M.dados = g;
  $par('par-mapa-vazio').classList.toggle('off', !!g);
  $par('par-legenda').classList.toggle('off', !g || !g.item || g.item.estado !== 'pronto');
  const meta = PAR.metas.get(PAR.sel);
  $par('par-trilha').innerHTML = g && meta ? `Processar › <b>${parEsc(meta.nome)}</b> › fazenda <b>${g.cod}</b>` : '';
  if (g && g.chave !== M.chave) { M.chave = g.chave; parMapaEnquadrar(); }
  if (!g) M.chave = null;
  const proc = g && g.item && g.item.estado === 'processando';
  if (proc && !M.raf) M.raf = requestAnimationFrame(parMapaQuadro);
  parMapaDesenhar();
}
function parMapaAneis(geo) {
  return geo.features.flatMap((f) => {
    const polis = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    return polis.map((p) => ({ talhao: f.properties.talhao, area: f.properties.area_ha, anel: p[0] }));
  });
}
function parMapaEnquadrar() {
  const M = PAR_MAPA, canvas = $par('par-canvas');
  const aneis = parMapaAneis(M.dados.geo);
  const pts = aneis.flatMap((a) => a.anel);
  if (!pts.length) return;
  const lat0 = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  M.k = Math.cos(lat0 * Math.PI / 180);
  const xs = pts.map((p) => p[0] * M.k), ys = pts.map((p) => p[1]);
  M.bbox = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  const w = canvas.clientWidth || 600, h = canvas.clientHeight || 400, m = Math.min(70, Math.round(h * 0.14));
  M.escala = Math.min((w - 2 * m) / ((M.bbox[2] - M.bbox[0]) || 1), (h - 2 * m) / ((M.bbox[3] - M.bbox[1]) || 1));
  M.ox = (w - (M.bbox[2] - M.bbox[0]) * M.escala) / 2 - M.bbox[0] * M.escala;
  M.oy = (h + (M.bbox[3] - M.bbox[1]) * M.escala) / 2 + M.bbox[1] * M.escala;
}
const parMapaX = (lon) => lon * PAR_MAPA.k * PAR_MAPA.escala + PAR_MAPA.ox;
const parMapaY = (lat) => PAR_MAPA.oy - lat * PAR_MAPA.escala;

function parMapaDesenhar() {
  const canvas = $par('par-canvas'), M = PAR_MAPA;
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); }
  const c = canvas.getContext('2d');
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.clearRect(0, 0, w, h);
  if (!M.dados || !M.bbox) return;
  M.caminhos = [];
  const css = getComputedStyle(document.documentElement);
  const cor = (v) => (v && v.startsWith('var(') ? css.getPropertyValue(v.slice(4, -1)).trim() : v);
  for (const a of parMapaAneis(M.dados.geo)) {
    const p = new Path2D();
    a.anel.forEach(([lon, lat], i) => (i ? p.lineTo(parMapaX(lon), parMapaY(lat)) : p.moveTo(parMapaX(lon), parMapaY(lat))));
    p.closePath();
    c.fillStyle = cor(M.dados.cores[a.talhao]) || css.getPropertyValue('--carreador').trim();
    c.fill(p);
    c.lineWidth = 2;
    c.strokeStyle = '#fff';
    c.stroke(p);
    M.caminhos.push({ p, talhao: a.talhao, area: a.area });
    const xs = a.anel.map((q) => parMapaX(q[0])), ys = a.anel.map((q) => parMapaY(q[1]));
    c.fillStyle = 'rgb(32 38 46 / .75)';
    c.font = '600 12px Poppins, sans-serif';
    c.textAlign = 'center';
    c.fillText(String(a.talhao), (Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2 + 4);
  }
  const it = M.dados.item;
  if (it && it.estado === 'processando') {   // varredura: uma faixa que avança com o progresso do item
    const x = w * ((it.pct_item || 0) / 100);
    const grad = c.createLinearGradient(x - 90, 0, x, 0);
    grad.addColorStop(0, 'rgb(22 167 107 / 0)');
    grad.addColorStop(1, 'rgb(22 167 107 / .28)');
    c.fillStyle = grad;
    c.fillRect(x - 90, 0, 90, h);
    c.fillStyle = 'rgb(22 167 107 / .9)';
    c.fillRect(x - 1, 0, 2, h);
  }
}
function parMapaQuadro() {
  PAR_MAPA.raf = 0;
  const it = PAR_MAPA.dados && PAR_MAPA.dados.item;
  if (!it || it.estado !== 'processando') return;
  parMapaDesenhar();
  PAR_MAPA.raf = requestAnimationFrame(parMapaQuadro);
}
function parIniciarMapa() {
  const canvas = $par('par-canvas'), M = PAR_MAPA, dica = $par('par-dica');
  if (canvas.dataset.pronto) return;
  canvas.dataset.pronto = '1';
  new ResizeObserver(() => { if (M.dados) parMapaEnquadrar(); parMapaDesenhar(); }).observe(canvas);
  const zoom = (f, cx, cy) => {
    M.ox = cx - (cx - M.ox) * f; M.oy = cy - (cy - M.oy) * f; M.escala *= f;
    parMapaDesenhar();
  };
  canvas.addEventListener('wheel', (e) => { e.preventDefault(); const r = canvas.getBoundingClientRect(); zoom(e.deltaY < 0 ? 1.2 : 1 / 1.2, e.clientX - r.left, e.clientY - r.top); }, { passive: false });
  $par('par-mais').onclick = () => zoom(1.4, canvas.clientWidth / 2, canvas.clientHeight / 2);
  $par('par-menos').onclick = () => zoom(1 / 1.4, canvas.clientWidth / 2, canvas.clientHeight / 2);
  canvas.addEventListener('pointerdown', (e) => { M.arrasto = { x: e.clientX, y: e.clientY }; canvas.setPointerCapture(e.pointerId); canvas.classList.add('arrastando'); });
  canvas.addEventListener('pointerup', () => { M.arrasto = null; canvas.classList.remove('arrastando'); });
  canvas.addEventListener('pointermove', (e) => {
    if (M.arrasto) {
      M.ox += e.clientX - M.arrasto.x; M.oy += e.clientY - M.arrasto.y;
      M.arrasto = { x: e.clientX, y: e.clientY };
      parMapaDesenhar();
      return;
    }
    const r = canvas.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    const c = canvas.getContext('2d');
    const t = (M.caminhos || []).find((q) => c.isPointInPath(q.p, x * (window.devicePixelRatio || 1), y * (window.devicePixelRatio || 1)));
    const f = t && M.dados.item && M.dados.item.estado === 'pronto'
      ? parPrevia(M.dados.item.resultado, PAR.vigentes).fazendas.find((z) => `${z.operacao}|${z.cod_faz}` === M.dados.chave.split('|').slice(1).join('|')) : null;
    const tl = f && f.talhoes.find((z) => z.talhao_num === t.talhao);
    dica.classList.toggle('on', !!t);
    if (t) {
      dica.innerHTML = `<b>Talhão ${parEsc(t.talhao)}</b> · ${parEsc(t.area)} ha${tl ? `<br>${parEsc(tl.pctTxt)} aderente · ${parEsc(tl.amostras)} amostras` : ''}`;
      dica.style.left = `${Math.min(x + 12, r.width - 190)}px`;
      dica.style.top = `${y + 12}px`;
    }
  });
  canvas.addEventListener('pointerleave', () => dica.classList.remove('on'));
}

// ===== Início =====
async function parIniciar() {
  $par('par-form').onsubmit = parEntrar;
  document.querySelectorAll('[data-sair]').forEach((b) => { b.onclick = parSair; });
  $par('par-demo').classList.toggle('off', !PAR_DEMO);
  parLigarColuna();
  window.addEventListener('beforeunload', (e) => {
    if (PAR.itens.length || PAR.rascunho) { e.preventDefault(); e.returnValue = ''; }   // spec §4: a fila só roda com a página aberta
  });
  try {
    const user = await parApi().sessao();
    if (!user) { parMostrar('login'); return; }
    await parCarregarEntrada();
  } catch (e) {
    parMostrar('login');
  }
}
if (document.getElementById('par-app')) parIniciar();
