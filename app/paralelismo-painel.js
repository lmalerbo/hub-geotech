// ===== Paralelismo: aba Painel (Resumo e Talhões). Agregações em paralelismo-puro.js =====
// Lê só as análises vigentes (rodadas publicadas). Gráficos em HTML/SVG; mapa MapLibre só em Painel › Talhões.
const PAR_COR_SIT = { bom: '#1f9e63', atencao: '#e3a33c', critico: '#cf5b3f' };   // mesmas cores --r4, --r2, --r1
const PAR_COR_INSUF = '#c5ced6';
const PAR_SIT_TXT = { bom: ['check_circle', 'Bom'], atencao: ['warning', 'Atenção'], critico: ['error', 'Crítico'] };
const PAR_MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const PAR_MAPA_ESTILO = { version: 8, sources: {}, layers: [{ id: 'fundo', type: 'background', paint: { 'background-color': '#e6ecf0' } }] };

// ── Leitura ──
async function parPaginar(consulta) {
  const todos = [];
  for (let i = 0; ; i += 1000) {
    const { data, error } = await consulta().range(i, i + 999);
    if (error) throw error;
    todos.push(...data);
    if (data.length < 1000) return todos;
  }
}
const parApiPainelReal = {
  async painel() {
    const analises = await parPaginar(() => parSb().from('paralelismo_analises')
      .select('id,operacao,cod_faz,mes,amostras,aderentes,acima,abaixo,fora_talhao,paralelismo_talhoes(talhao_num,amostras,aderentes,acima,abaixo,media_m,frotas)')
      .eq('vigente', true).order('id'));
    const cods = [...new Set(analises.map((a) => a.cod_faz))];
    if (!cods.length) return { analises: [], base: {} };
    const [faz, tal] = await Promise.all([
      parPaginar(() => parSb().from('fazendas').select('cod_faz,nome').in('cod_faz', cods).order('cod_faz')),
      parPaginar(() => parSb().from('talhoes').select('cod_faz,talhao_num,area_ha,declividade').in('cod_faz', cods).order('layer')),
    ]);
    const nomes = new Map(faz.map((f) => [f.cod_faz, f.nome]));
    const base = {};
    for (const t of tal) base[`${t.cod_faz}|${t.talhao_num}`] = { area_ha: t.area_ha, declividade: t.declividade };
    return { analises: analises.map((a) => ({ ...a, fazenda: nomes.get(a.cod_faz) || '' })), base };
  },
  async geoFazenda(cod) {
    const rows = await parPaginar(() => parSb().from('talhao_geom').select('talhao_num,area_ha,geom').eq('cod_faz', cod).order('talhao_num'));
    return { type: 'FeatureCollection', features: rows.map((r) => ({ type: 'Feature', geometry: r.geom, properties: { talhao: r.talhao_num, area_ha: r.area_ha } })) };
  },
};
const parApiPainelDemo = {
  async painel() {
    if (window.PAR_DEMO_PAINEL_VAZIO) return { analises: [], base: {} };
    const fazendas = [
      { cod_faz: 10001, nome: 'Santa Rita', mes: '2026-09-01' }, { cod_faz: 10002, nome: 'São José <b>x</b>', mes: '2026-10-01' },
      { cod_faz: 10003, nome: 'Boa Vista', mes: '2026-10-01' }, { cod_faz: 10004, nome: 'Só amostra pouca', mes: '2026-10-01', pouca: true },
    ];
    const analises = [], base = {};
    for (const f of fazendas) {
      const grupos = [{ frota: '90001' }];
      const geo = parTalhoesDemo(f.cod_faz);
      const an = parAnaliseDemo({ cod_faz: f.cod_faz, talhoes: geo, grupos });
      if (f.pouca) for (const t of an.talhoes) Object.assign(t, { amostras: 10, aderentes: 9, acima: 1, abaixo: 0 });
      const soma = (k) => an.talhoes.reduce((s, t) => s + t[k], 0);
      analises.push({ operacao: f.cod_faz === 10003 ? 'torta' : 'cana', cod_faz: f.cod_faz, fazenda: f.nome, mes: f.mes, amostras: soma('amostras'), aderentes: soma('aderentes'), acima: soma('acima'), abaixo: soma('abaixo'), fora_talhao: 5, paralelismo_talhoes: an.talhoes });
      for (const g of geo.features) base[`${f.cod_faz}|${g.properties.talhao}`] = { area_ha: g.properties.area_ha, declividade: g.properties.talhao === 6 ? null : g.properties.declividade + (f.cod_faz % 7) };
    }
    return { analises, base };
  },
  async geoFazenda(cod) { return parTalhoesDemo(cod); },
};
const parApiP = () => (PAR_DEMO ? parApiPainelDemo : parApiPainelReal);

async function parCarregarPainel(forcar = false) {
  const P = PAR.painel;
  if (P.carregando || (P.dados && !forcar)) return;
  P.carregando = true; P.erro = null;
  parRenderTudo();
  try { P.dados = await parApiP().painel(); } catch (e) { P.erro = 'Não foi possível carregar o painel. Tente de novo.'; }
  P.carregando = false;
  parRenderTudo();
}

// ── Formatação ──
function parPctTxt(p) { return p == null ? '—' : `${(Math.round(p * 100) / 100).toFixed(2).replace('.', ',')}%`; }
function parNumTxt(n, casas = 0) { return n == null ? '—' : Number(n).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas }); }
function parMesTxt(m) { return m ? `${PAR_MESES[Number(m.slice(5, 7)) - 1]}/${m.slice(0, 4)}` : '—'; }
function parSelo(sit, insuficiente) {
  if (insuficiente) return '<span class="par-sit insuf"><span class="ico">help</span>Amostra insuficiente</span>';
  if (!sit) return '—';
  return `<span class="par-sit ${sit}"><span class="ico">${PAR_SIT_TXT[sit][0]}</span>${PAR_SIT_TXT[sit][1]}</span>`;
}
const parCorSit = (pct) => (pct == null ? PAR_COR_INSUF : PAR_COR_SIT[parSituacao(pct)]);

// ── Coluna ──
function parHtmlPainel() {
  const P = PAR.painel;
  const cab = `<div><div class="par-ey">Paralelismo</div><h2>Painel</h2>
    <div class="par-sub-abas" role="group" aria-label="Seção do painel">
      ${[['resumo', 'Resumo'], ['talhoes', 'Talhões']].map(([k, t]) => `<button type="button" class="par-btn2" data-acao="painel-sub" data-sub="${k}" aria-pressed="${P.sub === k}">${t}</button>`).join('')}
    </div></div>`;
  if (P.carregando && !P.dados) return `${cab}<p role="status">Carregando o painel…</p>`;
  if (P.erro) return `${cab}<div class="par-aviso erro" role="alert"><span class="ico">error</span><div>${parEsc(P.erro)} <button class="par-btn2" type="button" data-acao="painel-recarregar">Tentar de novo</button></div></div>`;
  if (!P.dados) return cab;
  if (!P.dados.analises.length) return `${cab}<div class="par-aviso"><span class="ico">inbox</span><div>Nenhuma rodada publicada ainda. Quando um editor publicar uma rodada, os números aparecem aqui.</div></div>`;
  return cab + (P.sub === 'resumo' ? parHtmlResumo() : parHtmlTalhoes());
}

function parHtmlResumo() {
  const { analises, base } = PAR.painel.dados;
  const r = parResumo(analises, base), planos = parTalhoesPlanos(analises, base);
  const kpi = (rot, val, sub) => `<div class="par-kpi"><div class="l">${rot}</div><div class="v num">${val}</div><div class="s">${sub}</div></div>`;
  const faixas = parPorFaixa(planos);
  const barras = faixas.map((f) => `<div class="par-barra-h" title="${parEsc(f.rotulo)}: ${parPctTxt(f.pct)} (${f.n} talhões)">
      <span class="r">${parEsc(f.rotulo)}</span><span class="tr"><i style="width:${f.pct == null ? 0 : f.pct}%"></i></span>
      <span class="n num">${parPctTxt(f.pct)}<small> · ${parPlural(f.n, 'talhão', 'talhões')}</small></span></div>`).join('');
  const meses = parPorMes(analises);
  const colunas = meses.map((m) => `<div class="par-col-v" title="${parMesTxt(m.mes)}: ${parPctTxt(m.pct)} (${parNumTxt(m.amostras)} amostras)">
      <span class="n num">${parPctTxt(m.pct)}</span><span class="tr"><i style="height:${m.pct == null ? 0 : m.pct}%"></i></span><span class="r">${parMesTxt(m.mes)}</span></div>`).join('');
  const fazendas = parTabelaFazendas(analises, base).map((f) => `<tr><td>${parEsc(f.fazenda || f.cod_faz)}<small>${f.cod_faz} · ${f.operacao}</small></td>
      <td class="num">${parMesTxt(f.mes)}</td><td class="num">${parPctTxt(f.pct)}</td><td>${parSelo(f.situacao, f.pct == null)}</td></tr>`).join('');
  return `<div class="par-kpis">${kpi('Aderência', parPctTxt(r.pct), parSelo(r.situacao))}${kpi('Amostras', parNumTxt(r.amostras), 'dentro de talhão')}
      ${kpi('Fazendas', parNumTxt(r.fazendas), `${parNumTxt(r.area, 0)} ha`)}${kpi('Talhões', parNumTxt(r.talhoesValidos), `de ${parNumTxt(r.talhoes)} · amostra suficiente`)}</div>
    <section><h3>Aderência por declividade<small>ideal 2,90–3,10 m</small></h3>${barras}</section>
    <section><h3>Aderência por mês</h3><div class="par-colunas">${colunas}</div></section>
    <section><h3>Fazendas<small>pior primeiro</small></h3><div class="par-tabela"><table><thead><tr><th>Fazenda</th><th>Mês</th><th>Aderência</th><th>Situação</th></tr></thead><tbody>${fazendas}</tbody></table></div></section>`;
}

function parHtmlDispersao(planos) {
  const pts = planos.filter((p) => !p.insuficiente && p.dec != null);
  if (!pts.length) return '<p>Nenhum talhão com declividade e amostra suficiente.</p>';
  const W = 340, H = 205, m = { l: 34, r: 8, t: 8, b: 40 };
  const xmax = Math.max(15, Math.ceil(Math.max(...pts.map((p) => p.dec)) / 5) * 5);
  const X = (v) => m.l + v / xmax * (W - m.l - m.r), Y = (v) => H - m.b - v / 100 * (H - m.t - m.b);
  const grade = [0, 25, 50, 75, 100].map((v) => `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" class="g"/><text x="${m.l - 5}" y="${Y(v) + 4}" text-anchor="end">${v}%</text>`).join('');
  const xs = Array.from({ length: xmax / 5 + 1 }, (_, i) => i * 5).map((v) => `<text x="${X(v)}" y="${H - 24}" text-anchor="middle">${v}</text>`).join('');
  const pontos = pts.map((p) => `<circle cx="${X(p.dec).toFixed(1)}" cy="${Y(p.pct).toFixed(1)}" r="5" fill="${parCorSit(p.pct)}"><title>${parEsc(p.fazenda || p.cod_faz)} · talhão ${p.talhao}: ${parPctTxt(p.pct)} · declividade ${parNumTxt(p.dec, 1)}%</title></circle>`).join('');
  return `<svg class="par-disp" viewBox="0 0 ${W} ${H}" role="img" aria-label="Aderência por declividade, um ponto por talhão; os mesmos dados estão na tabela abaixo">
    ${grade}${xs}<line x1="${m.l}" x2="${W - m.r}" y1="${Y(85)}" y2="${Y(85)}" class="ref"/><line x1="${m.l}" x2="${W - m.r}" y1="${Y(70)}" y2="${Y(70)}" class="ref"/>
    <text x="${m.l + (W - m.l - m.r) / 2}" y="${H - 4}" text-anchor="middle" class="t">Declividade do talhão (%)</text>${pontos}</svg>`;
}
function parLinhasTalhoes() {
  const P = PAR.painel, { analises, base } = P.dados;
  const lista = parFiltrarTalhoes(parTalhoesPlanos(analises, base), P.busca);
  const chave = (p) => `${p.operacao}|${p.cod_faz}`;
  const linhas = lista.slice(0, 300).map((p) => `<tr data-acao="painel-fazenda" data-chave="${chave(p)}" tabindex="0" class="${P.sel === chave(p) ? 'sel' : ''}">
      <td>${parEsc(p.fazenda || p.cod_faz)}<small>${p.cod_faz} · ${p.operacao}</small></td><td class="num">${p.talhao}</td><td class="num">${parNumTxt(p.dec, 1)}</td>
      <td class="num">${parNumTxt(p.area, 1)}</td><td class="num">${parNumTxt(p.amostras)}</td><td class="num">${p.insuficiente ? '—' : parPctTxt(p.pct)}</td><td>${parSelo(parSituacao(p.pct), p.insuficiente)}</td></tr>`).join('');
  return linhas || '<tr><td colspan="7">Nenhum talhão encontrado.</td></tr>';
}
function parHtmlTalhoes() {
  const P = PAR.painel, { analises, base } = P.dados;
  const planos = parTalhoesPlanos(analises, base);
  const mais = parFiltrarTalhoes(planos, P.busca).length > 300 ? '<p>Mostrando os 300 primeiros; refine a busca.</p>' : '';
  return `<section><h3>Declividade × aderência<small>um ponto por talhão</small></h3>${parHtmlDispersao(planos)}</section>
    <section><h3>Talhões<small>clique numa linha para ver no mapa</small></h3>
    <label class="par-busca"><span class="ico">search</span><input id="par-busca" type="search" placeholder="Buscar fazenda, código ou talhão" value="${parEsc(P.busca)}" aria-label="Buscar talhão"></label>
    <div class="par-tabela"><table><thead><tr><th>Fazenda</th><th>Talhão</th><th>Decl. %</th><th>Área ha</th><th>Amostras</th><th>Aderência</th><th>Situação</th></tr></thead><tbody id="par-tab-tal">${parLinhasTalhoes()}</tbody></table></div>${mais}</section>`;
}

// ── Palco: MapLibre em Painel › Talhões; nas outras abas volta o mapa de Processar ──
function parPainelNoMapa() { return PAR.aba === 'painel' && PAR.painel.sub === 'talhoes' && !!PAR.painel.dados && PAR.painel.dados.analises.length > 0; }
function parPainelPalco() {
  const ml = $par('par-maplibre');
  const ativo = parPainelNoMapa();
  ml.classList.toggle('off', !ativo);
  $par('par-legenda-painel').classList.toggle('off', !ativo);
  if (PAR.aba === 'painel' && !ativo) {
    $par('par-mapa-vazio').classList.remove('off');
    $par('par-mapa-vazio').textContent = PAR.painel.dados && !PAR.painel.dados.analises.length ? 'Sem análises publicadas para mostrar no mapa.' : 'Abra a seção Talhões para ver o mapa pintado pela aderência.';
    $par('par-legenda').classList.add('off');
  }
  $par('par-canvas').classList.toggle('off', ativo);
  $par('par-mais').parentElement.classList.toggle('off', ativo);   // o MapLibre tem os próprios botões de zoom
  if (!ativo) return;
  $par('par-mapa-vazio').classList.add('off');
  $par('par-trilha').innerHTML = '';
  $par('par-legenda').classList.add('off');
  if (!PAR.painel.sel) {
    const { analises, base } = PAR.painel.dados;
    const f = parTabelaFazendas(analises, base)[0];
    PAR.painel.sel = f ? `${f.operacao}|${f.cod_faz}` : null;
    document.querySelectorAll('#par-tab-tal tr[data-chave]').forEach((tr) => tr.classList.toggle('sel', tr.dataset.chave === PAR.painel.sel));
  }
  parPainelMapa();
}

async function parPainelMapa() {
  const P = PAR.painel, cont = $par('par-maplibre');
  if (!window.maplibregl) { cont.innerHTML = '<div class="par-vazio">Não foi possível carregar o mapa (MapLibre). A tabela continua valendo.</div>'; return; }
  if (!P.sel) return;
  const [op, cod] = P.sel.split('|');
  const meu = P.sel;
  if (!P.geo[cod]) {
    try { P.geo[cod] = await parApiP().geoFazenda(Number(cod)); } catch (e) { parToast('Não foi possível carregar os talhões da fazenda.', true); return; }
    if (P.sel !== meu || !parPainelNoMapa()) return;
  }
  const cores = {};
  for (const p of parTalhoesPlanos(P.dados.analises.filter((a) => `${a.operacao}|${a.cod_faz}` === meu), P.dados.base)) {
    cores[p.talhao] = { cor: p.insuficiente ? PAR_COR_INSUF : parCorSit(p.pct), txt: p.insuficiente ? 'amostra insuficiente' : `${parPctTxt(p.pct)} aderente`, amostras: p.amostras };
  }
  const geo = { type: 'FeatureCollection', features: P.geo[cod].features.map((f) => ({ ...f, properties: { ...f.properties, ...(cores[f.properties.talhao] || { cor: PAR_COR_INSUF, txt: 'sem análise', amostras: 0 }) } })) };
  if (!P.ml) {
    cont.innerHTML = '';
    const m = new maplibregl.Map({ container: cont, style: PAR_MAPA_ESTILO, attributionControl: false, center: [-48, -21], zoom: 12 });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    P.ml = { m, pronto: false, fila: null };
    m.on('load', () => {
      P.ml.pronto = true;
      m.addSource('talhoes', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
      m.addLayer({ id: 'talhoes-fill', type: 'fill', source: 'talhoes', paint: { 'fill-color': ['get', 'cor'], 'fill-opacity': 0.9 } });
      m.addLayer({ id: 'talhoes-line', type: 'line', source: 'talhoes', paint: { 'line-color': '#ffffff', 'line-width': 2 } });
      const dica = $par('par-dica');
      m.on('mousemove', 'talhoes-fill', (e) => {
        const p = e.features[0].properties;
        dica.innerHTML = `<b>Talhão ${parEsc(p.talhao)}</b> · ${parEsc(p.area_ha)} ha<br>${parEsc(p.txt)} · ${parEsc(p.amostras)} amostras`;
        dica.style.left = `${Math.min(e.point.x + 12, cont.clientWidth - 190)}px`; dica.style.top = `${e.point.y + 12}px`;
        dica.classList.add('on');
      });
      m.on('mouseleave', 'talhoes-fill', () => dica.classList.remove('on'));
      if (P.ml.fila) parPainelAplicar(P.ml.fila);
    });
  }
  if (P.ml.pronto) parPainelAplicar(geo); else P.ml.fila = geo;
}
function parPainelAplicar(geo) {
  const { m } = PAR.painel.ml;
  m.resize();
  m.getSource('talhoes').setData(geo);
  const b = new maplibregl.LngLatBounds();
  const ext = (c) => (typeof c[0] === 'number' ? b.extend(c) : c.forEach(ext));
  geo.features.forEach((f) => f.geometry && ext(f.geometry.coordinates));
  if (!b.isEmpty()) m.fitBounds(b, { padding: 60, duration: 0, maxZoom: 17 });
  window.PAR_PAINEL_DESENHADO = geo.features.length;   // gancho para o teste de tela
}

// ── Eventos (delegados na coluna) ──
function parAcaoPainel(b) {
  const P = PAR.painel;
  return {
    'painel-sub': () => { P.sub = b.dataset.sub; parRenderTudo(); },
    'painel-recarregar': () => parCarregarPainel(true),
    'painel-fazenda': () => { P.sel = b.dataset.chave; parRenderTudo(); },
  }[b.dataset.acao] || null;
}
function parLigarPainel() {
  const col = $par('par-col');
  col.addEventListener('input', (e) => {
    if (e.target.id !== 'par-busca') return;
    PAR.painel.busca = e.target.value;
    const tb = $par('par-tab-tal');
    if (tb) tb.innerHTML = parLinhasTalhoes();   // só a tabela: a caixa de busca mantém o foco
  });
  col.addEventListener('keydown', (e) => {
    const tr = e.target.closest && e.target.closest('tr[data-acao="painel-fazenda"]');
    if (tr && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); PAR.painel.sel = tr.dataset.chave; parRenderTudo(); }
  });
}
