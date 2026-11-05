// ===== Paralelismo: abas Pendentes e Rodadas (com Frotas) =====
// Usa PAR, parEsc, parPlural, parMb, parDialogo, parToast, parRenderTudo, parContador, parApi, parEhEditor, parSb, PAR_DEMO
// (paralelismo.js) e as funções puras de paralelismo-gestao.js. Todo texto vindo do banco passa por parEsc;
// link só passa por parUrlSegura.

const parApiGestaoReal = {
  async rodadas() {
    const talh = 'paralelismo_talhoes(talhao_num,amostras,aderentes,acima,abaixo,media_m,frotas)';
    const ana = `paralelismo_analises(id,operacao,cod_faz,mes,amostras,aderentes,acima,abaixo,fora_talhao,pll_total,pll_aderentes,vigente,base_analise_id,amostras_url,${talh})`;
    const { data, error } = await parSb().from('paralelismo_rodadas')
      .select(`id,descricao,release_tag,partes,status,criado_por,criado_em,validado_por,validado_em,motivo_recusa,${ana}`)
      .order('id', { ascending: false }).limit(200);
    if (error) throw error;
    const ids = [...new Set(data.flatMap((r) => [r.criado_por, r.validado_por]).filter(Boolean))];
    const nomes = {};
    if (ids.length) {   // a RLS pode esconder o nome de outras pessoas: sem nome, a tela mostra "—"
      const { data: us } = await parSb().from('usuarios').select('id,nome').in('id', ids);
      for (const u of us || []) nomes[u.id] = u.nome;
    }
    const { data: vig, error: ev } = await parSb().from('paralelismo_analises').select('operacao,cod_faz,amostras,aderentes').eq('vigente', true);
    if (ev) throw ev;
    return { rodadas: data, nomes, vigentes: Object.fromEntries((vig || []).map((v) => [`${v.operacao}|${v.cod_faz}`, v])) };
  },
  async publicar(id, recalculo) {
    const { data, error } = await parSb().rpc('paralelismo_publicar', { p_rodada_id: id, p_recalculo: recalculo });
    if (error) throw error;
    return data;
  },
  async recusar(id, motivo) {
    const { error } = await parSb().rpc('paralelismo_recusar', { p_rodada_id: id, p_motivo: motivo });
    if (error) throw error;
  },
  async excluir(id) {
    const { data, error } = await parSb().rpc('paralelismo_excluir', { p_rodada_id: id });
    if (error) throw error;
    return data;
  },
  async marcarExcluida(tag) {
    const sessao = (await parSb().auth.getSession()).data.session;
    if (!sessao) throw new Error('Sessão expirada; entre de novo');
    const r = await fetch(`${PAR_WORKER_URL}/paralelismo/excluida`, {
      method: 'POST', headers: { Authorization: `Bearer ${sessao.access_token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ release_tag: tag }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
  },
  async buscarBaseRodada(operacao, codFaz, rodadaId) {
    const [v, t] = await Promise.all([
      parSb().rpc('paralelismo_linhas_vigentes', { p_operacao: operacao, p_cod_faz: codFaz, p_rodada_id: rodadaId }),
      parSb().rpc('paralelismo_talhoes_fazenda', { p_cod_faz: codFaz }),
    ]);
    if (v.error) throw v.error;
    if (t.error) throw t.error;
    return { analise_id: v.data.analise_id, linhas: v.data.linhas, talhoes: t.data };
  },
};
function parApiG() { return PAR_DEMO ? PAR_API_DEMO_G : parApiGestaoReal; }

// ── Dados (estado em PAR.gestao, PAR.sub e PAR.frotaForm, declarados em paralelismo.js) ──
let parSeqGestao = 0;
async function parCarregarGestao() {
  const G = PAR.gestao, seq = ++parSeqGestao;   // resposta mais antiga que a última carga é ignorada
  G.carregando = true;
  G.erro = null;
  parRenderTudo(true);
  try {
    const { rodadas, nomes, vigentes } = await parApiG().rodadas();
    if (seq !== parSeqGestao) return;
    G.rodadas = rodadas.map((r) => parRodadaDoBanco(r, nomes, vigentes));
    parContador(G.rodadas.filter((r) => r.status === 'pendente').length);
  } catch (e) {
    if (seq === parSeqGestao) G.erro = 'Não foi possível carregar as rodadas. Tente de novo.';
  } finally {
    if (seq === parSeqGestao) {
      G.carregando = false;
      parRenderTudo(true);
    }
  }
}

const parData = (iso) => (iso ? new Date(iso).toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo' }) : '—');

// ── Desenho ──
function parHtmlLink(url, texto) {
  return url
    ? `<a class="par-link" href="${parEsc(url)}" target="_blank" rel="noopener noreferrer">${parEsc(texto)}</a>`
    : `<span class="par-link-ruim" title="O endereço guardado não é de um arquivo do GitHub e foi bloqueado">${parEsc(texto)} (link inválido)</span>`;
}
function parHtmlBrutos(r) {
  if (!r.partes.length) return '';
  const links = r.partes.map((p) => `${parHtmlLink(p.url, p.nome)} <span class="sub">${parMb(p.bytes)}</span>`).join('<br>');
  return `<div class="par-brutos"><span class="par-ey">Arquivos brutos</span><br>${links}</div>`;
}
function parHtmlFazendasRodada(r) {
  const bloco = (a) => `<div class="par-aviso"><span class="ico">warning</span><div>${parEsc(a.texto)}</div></div>`;
  return r.previa.fazendas.map((f) => {
    const tal = f.talhoes.map((t) => `<div class="par-linha"><b>${t.talhao_num}</b><div class="sub num">${t.amostras} amostras${t.insuficiente ? ' · insuficiente' : ''}</div><b class="num">${t.pctTxt}</b></div>`).join('');
    return `<details class="par-faz"><summary><span><b>${f.cod_faz}</b> <span class="par-pil ${parEsc(f.operacao)}">${parEsc(f.operacao)}</span><br>
        <span class="sub num">${f.amostras} amostras · ${f.foraTalhao} fora de talhão${f.vigentePctTxt ? ` · vigente ${f.vigentePctTxt}` : ' · fazenda nova'}</span></span>
        <span style="text-align:right"><b class="num">${f.pctTxt}</b>${f.deltaTxt ? `<br><span class="sub num">${f.deltaTxt}</span>` : ''}</span></summary>
      ${f.avisos.map(bloco).join('')}${tal}${f.amostrasUrl ? `<div class="sub">${parHtmlLink(f.amostrasUrl, 'Amostras (shapefile)')}</div>` : ''}</details>`;
  }).join('');
}

function parHtmlErroGestao() {
  return `<div class="par-aviso erro" role="alert"><span class="ico">error</span><div>${parEsc(PAR.gestao.erro)}
    <div class="par-acoes" style="margin-top:6px"><button class="par-btn2" type="button" data-acao="recarregar-gestao">Tentar de novo</button></div></div></div>`;
}

function parHtmlPendentes() {
  const G = PAR.gestao;
  const cab = '<div><div class="par-ey">Paralelismo</div><h2>Pendentes</h2><p>Rodadas esperando validação de um editor.</p></div>';
  if (G.erro) return `<div data-tela="pendentes">${cab}${parHtmlErroGestao()}</div>`;
  if (G.carregando && !G.rodadas.length) return `<div data-tela="pendentes">${cab}<p role="status">Carregando…</p></div>`;
  const lista = G.rodadas.filter((r) => r.status === 'pendente');
  const cartoes = lista.map((r) => {
    const ocupado = G.ocupado === r.id;
    const acoes = parEhEditor()
      ? `<div class="par-acoes"><button class="par-btn" type="button" data-acao="publicar" data-id="${r.id}" ${G.ocupado ? 'disabled' : ''}><span class="ico">task_alt</span>${ocupado ? parEsc(G.msg) : 'Publicar'}</button>
         <button class="par-btn2" type="button" data-acao="recusar" data-id="${r.id}" ${G.ocupado ? 'disabled' : ''}>Recusar</button></div>`
      : '<div class="par-aviso"><span class="ico">hourglass_top</span><div>Aguardando validação de um editor.</div></div>';
    return `<article class="par-pend par-cartao-rod" data-rodada="${r.id}">
      <div class="topo"><b>Rodada ${r.id}</b><span class="par-pil">pendente</span></div>
      <div class="sub">${parEsc(r.descricao)}</div>
      <div class="sub num">Processada por ${parEsc(r.criadoPor)} em ${parData(r.criadoEm)}</div>
      <div class="par-grande"><span class="v num">${r.previa.total.pctTxt}</span><span class="sub" style="color:var(--t3)">aderentes (${r.previa.total.amostras} amostras)</span></div>
      <div class="sub">${parPlural(r.fazendas.length, 'fazenda', 'fazendas')} · ${parPlural(r.frotas.length, 'frota', 'frotas')}${r.frotas.length ? ` (${parEsc(r.frotas.join(', '))})` : ''}</div>
      ${parHtmlFazendasRodada(r)}${parHtmlBrutos(r)}${acoes}</article>`;
  }).join('');
  const vazio = parEhEditor() ? 'Nenhuma rodada esperando validação.' : 'Você não tem rodadas esperando validação.';
  return `<div data-tela="pendentes">${cab}${cartoes || `<div class="par-aviso ok"><span class="ico">done_all</span><div>${parEsc(vazio)}</div></div>`}</div>`;
}

function parHtmlRodadas() {
  const G = PAR.gestao;
  const sub = `<div class="par-sub-abas">
    <button type="button" class="par-btn2" data-acao="sub" data-sub="historico" aria-pressed="${PAR.sub !== 'frotas'}">Rodadas</button>
    <button type="button" class="par-btn2" data-acao="sub" data-sub="frotas" aria-pressed="${PAR.sub === 'frotas'}">Frotas</button></div>`;
  const cab = `<div><div class="par-ey">Paralelismo</div><h2>${PAR.sub === 'frotas' ? 'Frotas' : 'Rodadas'}</h2></div>${sub}`;
  if (PAR.sub === 'frotas') return `<div data-tela="frotas">${cab}${parHtmlFrotas()}</div>`;
  if (G.erro) return `<div data-tela="rodadas">${cab}${parHtmlErroGestao()}</div>`;
  if (G.carregando && !G.rodadas.length) return `<div data-tela="rodadas">${cab}<p role="status">Carregando…</p></div>`;
  const admin = !!PAR.eu && PAR.eu.nivel === 'admin';
  const itens = G.rodadas.map((r) => `<article class="par-rod par-cartao-rod" data-rodada="${r.id}">
    <div class="topo"><b>Rodada ${r.id}</b><span class="par-pil ${r.status === 'publicada' ? 'pronto' : r.status === 'recusada' ? 'erro' : ''}">${parEsc(r.status)}</span></div>
    <div class="sub">${parEsc(r.descricao)}</div>
    <div class="sub num">Processada por ${parEsc(r.criadoPor)} em ${parData(r.criadoEm)}${r.status === 'pendente' ? '' : ` · ${r.status === 'recusada' ? 'recusada' : 'validada'} por ${parEsc(r.validadoPor)} em ${parData(r.validadoEm)}`}</div>
    <div class="sub">${parPlural(r.fazendas.length, 'fazenda', 'fazendas')}: ${parEsc(r.fazendas.map((f) => f.cod_faz).join(', ') || '—')} · ${parPlural(r.frotas.length, 'frota', 'frotas')}${r.frotas.length ? ` (${parEsc(r.frotas.join(', '))})` : ''}</div>
    ${r.status === 'recusada' && r.motivo ? `<div class="par-aviso erro"><span class="ico">block</span><div>Motivo da recusa: ${parEsc(r.motivo)}</div></div>` : ''}
    ${parHtmlBrutos(r)}
    ${admin && r.status === 'publicada' ? `<div class="par-acoes"><button class="par-btn2 par-btn-perigo" type="button" data-acao="excluir" data-id="${r.id}" ${G.ocupado ? 'disabled' : ''}><span class="ico">delete</span>Excluir</button></div>` : ''}
  </article>`).join('');
  return `<div data-tela="rodadas">${cab}${itens || '<div class="par-aviso"><span class="ico">info</span><div>Nenhuma rodada ainda.</div></div>'}</div>`;
}

function parHtmlFrotas() {
  const ed = parEhEditor();
  const form = PAR.frotaForm;
  const campo = (nome, rot, v, extra = '') => `<label>${rot}<input name="${nome}" value="${parEsc(v ?? '')}" ${extra}></label>`;
  const opc = (lista, v) => [['', '—'], ...lista].map(([k, t]) => `<option value="${k}" ${k === (v || '') ? 'selected' : ''}>${t}</option>`).join('');
  const formulario = form ? `<form class="par-form-frota" data-form-frota-ed novalidate>
      ${campo('serie', 'Série', form.serie, form.novo ? '' : 'disabled')}${campo('frota', 'Frota', form.frota)}
      <label>Operação<select name="operacao">${opc([['cana', 'Cana'], ['torta', 'Torta']], form.operacao)}</select></label>
      <label>Tipo<select name="tipo">${opc([['propria', 'Própria'], ['prestador', 'Prestador']], form.tipo)}</select></label>
      ${campo('nomes_antigos', 'Nomes antigos', form.nomes_antigos)}${campo('observacao', 'Observação', form.observacao)}
      ${form.erro ? `<p class="par-erro" role="alert">${parEsc(form.erro)}</p>` : ''}
      <div class="acoes"><button class="par-btn" type="submit">Salvar frota</button><button class="par-btn2" type="button" data-acao="cancelar-frota">Cancelar</button></div></form>` : '';
  const linhas = PAR.frotas.slice().sort((a, b) => String(a.serie).localeCompare(String(b.serie))).map((f) => `<div class="par-frota" data-serie="${parEsc(f.serie)}">
      <div><b>${parEsc(f.frota)}</b> <span class="par-pil ${f.operacao === 'cana' || f.operacao === 'torta' ? f.operacao : ''}">${parEsc(f.operacao || '—')}</span> <span class="par-pil">${f.tipo === 'prestador' ? 'prestador' : f.tipo === 'propria' ? 'própria' : '—'}</span><br>
      <span class="sub num">${parEsc(f.serie)}${f.nomes_antigos ? ` · antes: ${parEsc(f.nomes_antigos)}` : ''}${f.observacao ? ` · ${parEsc(f.observacao)}` : ''}</span></div>
      ${ed ? `<button class="par-btn2" type="button" data-acao="editar-frota" data-serie="${parEsc(f.serie)}">Editar</button>` : ''}</div>`).join('');
  return `${ed ? '<div class="par-acoes"><button class="par-btn2" type="button" data-acao="nova-frota"><span class="ico">add</span>Nova frota</button></div>' : '<p class="sub">Só editores alteram as frotas.</p>'}
    ${formulario}<div class="par-lista">${linhas || '<p>Nenhuma frota cadastrada.</p>'}</div>`;
}

// ── Ações ──
function parPedirMotivo(id) {
  return new Promise((resolver) => {
    const fundo = $par('par-fundo');
    fundo.innerHTML = `<div class="par-modal" role="dialog" aria-modal="true" aria-labelledby="par-md-tit"><h3 id="par-md-tit">Recusar a rodada ${id}</h3>
      <p>Diga por que a rodada foi recusada. Quem enviou vai ler.</p><textarea id="par-motivo" rows="3" maxlength="300" aria-label="Motivo da recusa"></textarea>
      <p class="par-erro" id="par-motivo-erro" role="alert"></p>
      <div class="par-acoes"><button class="par-btn2" type="button" data-i="n">Cancelar</button><button class="par-btn" type="button" data-i="s">Recusar rodada</button></div></div>`;
    const fechar = (v) => { fundo.classList.add('off'); fundo.innerHTML = ''; resolver(v); };
    fundo.onclick = (e) => { if (e.target === fundo) fechar(null); };
    fundo.querySelector('[data-i="n"]').onclick = () => fechar(null);
    fundo.querySelector('[data-i="s"]').onclick = () => {
      const m = $par('par-motivo').value.trim();
      if (!m) { $par('par-motivo-erro').textContent = 'Informe o motivo da recusa.'; return; }
      fechar(m);
    };
    fundo.onkeydown = (e) => { if (e.key === 'Escape') fechar(null); };
    fundo.classList.remove('off');
    $par('par-motivo').focus();
  });
}

// Worker próprio e descartável: o recálculo não entra na fila de pen-drives nem mexe no OPFS.
function parRecalcularNoWorker(entrada) {
  return new Promise((resolver, rejeitar) => {
    const w = PAR_DEMO ? new ParWorkerDemo() : new Worker('paralelismo-worker.js');
    const id = `rec${Date.now()}`;
    const limite = setTimeout(() => fim(rejeitar, new Error(PAR_ERRO_PREPARO)), 5 * 60 * 1000);   // Pyodide travado não deixa a tela esperando para sempre
    const fim = (fn, v) => { clearTimeout(limite); w.terminate(); fn(v); };
    w.onmessage = (e) => {
      const m = e.data;
      if (m.id !== id) return;
      if (m.tipo === 'pronto') fim(resolver, m.resultado.fazendas);
      else if (m.tipo === 'erro') fim(rejeitar, new Error(m.msg));
    };
    w.onerror = () => fim(rejeitar, new Error(PAR_ERRO_PREPARO));
    w.onmessageerror = () => fim(rejeitar, new Error(PAR_ERRO_CONCLUIR));
    try { w.postMessage({ tipo: 'processar', item: { id, pulados: [], fazendas: entrada } }); } catch (e) { fim(rejeitar, e); }
  });
}

function parTextoRecalculo(results, r) {
  const linhas = results.map((x) => {
    const a = x.analise;
    const antes = r.previa.fazendas.find((f) => f.operacao === x.operacao && f.cod_faz === x.cod_faz);
    return `Fazenda ${x.cod_faz} (${x.operacao}): ${parFormatarPct(a.aderentes, a.amostras)} aderentes em ${a.amostras} amostras${antes ? `, eram ${antes.pctTxt}` : ''}`;
  });
  return `Outra rodada mudou as linhas vigentes desde o envio. Os números foram recalculados com as linhas vigentes mais as desta rodada. ${linhas.join('; ')}.`;
}

async function parPublicar(id) {
  const G = PAR.gestao, r = G.rodadas.find((x) => x.id === id);
  if (!r || G.ocupado) return;
  G.ocupado = id;
  G.msg = 'Publicando…';
  const api = parApiG();
  try {
    parRenderTudo();
    const res = await parPublicarComRecalculo(id, {
      publicar: (rid, rec) => api.publicar(rid, rec),
      buscarBase: (op, cod, rid) => api.buscarBaseRodada(op, cod, rid),
      recalcular: (entrada) => { G.msg = 'Recalculando…'; parRenderTudo(); return parRecalcularNoWorker(entrada); },
      confirmar: (results) => parDialogo('Números recalculados', parTextoRecalculo(results, r),
        [{ rotulo: 'Cancelar', classe: 'par-btn2', valor: false }, { rotulo: 'Publicar com o recálculo', classe: 'par-btn', valor: true }]),
    });
    if (res.cancelado) parToast('Publicação cancelada. A rodada continua pendente.');
    else parToast(res.recalculou ? `Rodada ${id} publicada com os números recalculados.` : `Rodada ${id} publicada.`);
  } catch (e) {
    parToast(parTextoErroGestao(e), true);
  } finally {
    G.ocupado = null;
    await parCarregarGestao();
  }
}

async function parRecusar(id) {
  const G = PAR.gestao;
  if (G.ocupado) return;
  const motivo = await parPedirMotivo(id);
  if (!motivo) return;
  G.ocupado = id;
  G.msg = 'Recusando…';
  parRenderTudo();
  try {
    await parApiG().recusar(id, motivo);
    parToast(`Rodada ${id} recusada.`);
  } catch (e) {
    parToast(parTextoErroGestao(e), true);
  } finally {
    G.ocupado = null;
    await parCarregarGestao();
  }
}

async function parExcluir(id) {
  const G = PAR.gestao;
  if (G.ocupado) return;
  const ok = await parDialogo(`Excluir a rodada ${id}?`, 'As linhas e os números dela saem do painel e a análise anterior de cada fazenda volta a valer. Os arquivos brutos ficam no GitHub, marcados como excluídos.',
    [{ rotulo: 'Cancelar', classe: 'par-btn2', valor: false }, { rotulo: 'Excluir rodada', classe: 'par-btn', valor: true }]);
  if (!ok) return;
  G.ocupado = id;
  try {
    parRenderTudo();
    const tag = await parApiG().excluir(id);
    try {
      await parApiG().marcarExcluida(tag);
      parToast(`Rodada ${id} excluída.`);
    } catch (e) {
      parToast(`Rodada ${id} excluída, mas a release ${tag} não foi marcada como excluída no GitHub.`, true);
    }
  } catch (e) {
    parToast(parTextoErroGestao(e), true);
  } finally {
    G.ocupado = null;
    await parCarregarGestao();
  }
}

async function parSalvarFrotaEd(formEl) {
  const f = PAR.frotaForm;
  const dados = Object.fromEntries(new FormData(formEl));
  const v = parValidarFrota({ ...dados, serie: f.novo ? dados.serie : f.serie });
  if (v.erro) { Object.assign(f, dados, { erro: v.erro }); parRenderTudo(); return; }
  try {
    await parApi().salvarFrota(v.valor);
    PAR.frotas = await parApi().frotas();
    PAR.frotaForm = null;
    parToast('Frota salva.');
  } catch (e) {
    Object.assign(f, dados, { erro: parTextoErroGestao(e) });
  }
  parRenderTudo();
}

// Ações de clique da coluna que pertencem a estas abas (null = não é daqui).
function parAcaoGestao(b) {
  const id = Number(b.dataset.id);
  return {
    publicar: () => parPublicar(id),
    recusar: () => parRecusar(id),
    excluir: () => parExcluir(id),
    'recarregar-gestao': parCarregarGestao,
    sub: () => { PAR.sub = b.dataset.sub; PAR.frotaForm = null; parRenderTudo(); },
    'nova-frota': () => { PAR.frotaForm = { novo: true, serie: '', frota: '', operacao: 'cana', tipo: 'propria', erro: null }; parRenderTudo(); },
    'editar-frota': () => { PAR.frotaForm = { novo: false, ...PAR.frotas.find((f) => f.serie === b.dataset.serie), erro: null }; parRenderTudo(); },
    'cancelar-frota': () => { PAR.frotaForm = null; parRenderTudo(); },
  }[b.dataset.acao] || null;
}
