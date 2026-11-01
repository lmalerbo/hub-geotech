// Slides da Apresentação semanal: porte dos geradores do gerar.py e frame do design system Pedra.
// Sem DOM e sem module.exports (testado em tests/app/apresentacao_slides.test.js).
// Porte de gerar.py (linhas 24-43, 172-458). apCorpo() reproduz byte a byte o retorno de cada gerador.
// `function` e `var` (não const/let) para ficarem visíveis no contexto vm dos testes.
// Depende de app/apresentacao-calculo.js (apRound, apG, apN, apPct, apP1, apIso, apVoosNumeros).

var AP_VERDE = '#019640';
var AP_OURO = '#c99a2e';
var AP_AZUL = '#2f6fb0';
var AP_CINZA = '#a7b2a9';
var AP_ESCURO = '#16261b';
var AP_MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

var AP_SLIDES = ['divisoria', 'colheita', 'sistematizacao', 'plantio', 'voos', 'drone'];
var AP_TITULOS = {
  divisoria: 'Indicadores Operacionais',
  colheita: 'Projetos de Colheita',
  sistematizacao: 'Projetos de Sistematização',
  plantio: 'Projetos de Plantio',
  voos: 'Voos com Drone',
  drone: 'Projetos de Drone de Aplicação',
};

// html.escape(texto, quote=True) do Python.
function apEsc(texto) {
  if (texto === null || texto === undefined) return '';
  return String(texto)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

// CORTE_BR, POS e MES_CORTE do gerar.py, derivados de ctx.corte ('AAAA-MM-DD').
function apDerivados(ctx) {
  const c = ctx.corte;
  const corteBR = `${c.slice(8, 10)}/${c.slice(5, 7)}/${c.slice(0, 4)}`;
  return {
    corteBR,
    pos: `posição de ${corteBR}`,
    mesCorte: AP_MESES[parseInt(c.slice(5, 7), 10) - 1].toLowerCase(),
  };
}

// str.title() do Python: primeira letra de cada palavra maiúscula, o resto minúsculo.
function apTitle(s) {
  return s.toLowerCase().replace(/(^|[^\p{L}\p{M}])(\p{L})/gu, (_, a, b) => a + b.toUpperCase());
}

function apSomaV(segs) {
  return segs.reduce((a, [, v]) => a + v, 0);
}

// rot_mes() do gerar.py: 'AAAA-MM' -> 'Mmm/AA'; 'Indef' -> 'Indef.'.
function apRotMes(chave) {
  if (chave === 'Indef') return 'Indef.';
  const [a, m] = chave.split('-');
  return `${AP_MESES[parseInt(m, 10) - 1]}/${a.slice(2)}`;
}

// Parte do aviso de voos: o gerar.py subtrai 3 h do relógio do atualizadoEm (sem converter fuso).
function apAvisoVoos(V) {
  if (!V.desatualizado) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(V.atualizadoEm || '');
  if (!m) return '';
  const t = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4] - 3, +m[5]));
  const p2 = (x) => String(x).padStart(2, '0');
  const hora = `${p2(t.getUTCDate())}/${p2(t.getUTCMonth() + 1)} ${p2(t.getUTCHours())}h${p2(t.getUTCMinutes())}`;
  return ` Números da última busca bem-sucedida no DroneManagement (${hora}).`;
}

// Texto que o gerador passa a subtitulo(...), antes de virar HTML. Divisória não tem subtítulo.
function apSubtituloPadrao(chave, A, metas, ctx) {
  const { pos, mesCorte } = apDerivados(ctx);
  switch (chave) {
    case 'colheita':
      return `Dados do Hub Geotech — módulo Colheita · ${pos}.`;
    case 'sistematizacao':
      return `Dados do Hub Geotech — módulo Preparo · ${pos}.`;
    case 'plantio':
      return `Dados do Hub Geotech — módulo Plantio · ${pos}.`;
    case 'voos':
      return `Painel de controle — Voos com Drone · abr–${mesCorte}/${ctx.corte.slice(0, 4)}, por tipo de missão.${apAvisoVoos(A.voos)}`;
    case 'drone':
      return 'Projetos de drone de aplicação elaborados pela Geotecnologia — normal e catação.';
    default:
      return '';
  }
}

// ======================= componentes (gerar.py 172-233) =======================
function apKpi(rotulo, valor, sub, cor, grande) {
  const [fsL, fsV, fsS, pad] = grande
    ? ['14px', '38px', '14px', '20px 24px']
    : ['13px', '32px', '13px', '18px 20px'];
  return `<div style="flex:1;background:#ffffff;border:1px solid #e3ece0;border-top:4px solid ${cor};border-radius:10px;padding:${pad};box-sizing:border-box;">` +
    `<div style="font-size:${fsL};letter-spacing:1px;text-transform:uppercase;color:#8a978d;font-weight:600;">${rotulo}</div>` +
    `<div style="font-size:${fsV};font-weight:700;color:${cor === AP_CINZA ? '#5b6b60' : cor};margin-top:6px;">${valor}</div>` +
    `<div style="font-size:${fsS};color:#8a978d;margin-top:2px;">${sub}</div></div>`;
}

function apProgresso(p, mt = '22px') {
  return `<div style="display:flex;align-items:center;gap:18px;margin-top:${mt};">` +
    '<span style="font-size:14px;letter-spacing:1px;text-transform:uppercase;color:#8a978d;font-weight:600;white-space:nowrap;">Progresso Geral</span>' +
    `<div style="flex:1;height:14px;background:#e3ece0;border-radius:7px;overflow:hidden;"><div style="width:${p}%;height:100%;background:linear-gradient(90deg,#019640,#7BBB34);border-radius:7px;"></div></div>` +
    `<span style="font-size:20px;font-weight:700;color:#019640;">${p}%</span></div>`;
}

// barras: [[rótulo, [[cor, ha], ...] de baixo para cima], ...]
function apColunas(barras, fs = '10px', gap = '10px', mt = '10px') {
  if (!barras.length) return '';
  const mx = Math.max(...barras.map(([, segs]) => apSomaV(segs))) || 1;
  const out = [`<div style="display:flex;align-items:flex-end;gap:${gap};flex:1;margin-top:${mt};">`];
  for (const [rot, segs0] of barras) {
    const tot = apSomaV(segs0);
    const segs = segs0.filter(([, h]) => h > 0);
    const partes = segs.map(([c, h], i) =>
      `<div style="background:${c};height:${apP1(100 * h / tot)}%;${i === segs.length - 1 ? 'border-radius:2px 2px 0 0;' : ''}"></div>`).join('');
    out.push(`<div style="display:flex;flex-direction:column;align-items:center;justify-content:flex-end;flex:1;height:100%;">` +
      `<div style="font-size:${fs};color:#8a978d;">${apN(tot)}</div>` +
      `<div style="width:100%;display:flex;flex-direction:column-reverse;height:${apP1(100 * tot / mx)}%;">${partes}</div>` +
      `<div style="font-size:${fs};color:#8a978d;margin-top:4px;">${rot}</div></div>`);
  }
  return out.join('') + '</div>';
}

// itens: [[rótulo, [[cor, ha], ...] da esquerda para a direita], ...]; escala pelo maior total.
function apLinhas(itens, wRot = '70px', fs = '11px', h = '13px', gap = '8px') {
  const mx = Math.max(...itens.map(([, segs]) => apSomaV(segs))) || 1;
  const out = [`<div style="display:flex;flex-direction:column;gap:${gap};margin-top:10px;flex:1;justify-content:center;">`];
  for (const [rot, segs] of itens) {
    const barra = segs.filter(([, v]) => v > 0)
      .map(([c, v]) => `<div style="width:${apP1(100 * v / mx)}%;background:${c};"></div>`).join('');
    out.push(`<div style="display:flex;align-items:center;gap:8px;"><span style="width:${wRot};font-size:${fs};color:#5b6b60;">${rot}</span>` +
      `<div style="flex:1;height:${h};display:flex;border-radius:2px;overflow:hidden;background:#f2f6f1;">${barra}</div>` +
      `<span style="font-size:${fs};color:#8a978d;width:44px;">${apN(apSomaV(segs))}</span></div>`);
  }
  return out.join('') + '</div>';
}

function apLegenda(itens, fs = '11px', mt = '10px') {
  return `<div style="display:flex;gap:16px;margin-top:${mt};font-size:${fs};color:#5b6b60;">` +
    itens.map(([c, t]) => `<span><span style="display:inline-block;width:9px;height:9px;background:${c};border-radius:2px;margin-right:4px;"></span>${t}</span>`).join('') +
    '</div>';
}

function apPainel(titulo, corpo, flex = '1', pad = '18px 22px') {
  return `<div style="flex:${flex};background:#ffffff;border:1px solid #e3ece0;border-radius:10px;padding:${pad};display:flex;flex-direction:column;box-sizing:border-box;">` +
    `<div style="font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#8a978d;font-weight:600;">${titulo}</div>${corpo}</div>`;
}

function apFonte(txt) {
  return `<div style="font-size:11px;color:#8a978d;margin-top:8px;">${txt}</div>`;
}

function apSubtitulo(txt, mb = '18px', fs = '22px') {
  return `<p style="margin:0 0 ${mb};font-size:${fs};font-weight:300;color:#5b6b60;max-width:1600px;">${txt}</p>`;
}

// ======================= slides (gerar.py 244-454) =======================
function apColheita(A, metas, ctx, texto) {
  const c = A.colheita;
  const s = c.status, tot = c.total;
  const conc = s.CONCLUIDO || 0, sl = s['SEM LINHAS'] || 0, rea = s.REAVALIAR || 0, af = s['A FAZER'] || 0;
  const p = apPct(conc, tot);
  const seg = (d) => [[AP_AZUL, d['A FAZER'] || 0], [AP_OURO, d.REAVALIAR || 0], [AP_CINZA, d['SEM LINHAS'] || 0], [AP_VERDE, d.CONCLUIDO || 0]];
  const segL = (d) => [[AP_VERDE, d.CONCLUIDO || 0], [AP_CINZA, d['SEM LINHAS'] || 0], [AP_OURO, d.REAVALIAR || 0], [AP_AZUL, d['A FAZER'] || 0]];
  const barras = [];
  for (let m = 3; m <= 12; m++) barras.push([AP_MESES[m - 1], seg(c.mes[String(m)] || {})]);
  const ordem = [...Array.from({ length: 29 }, (_, i) => `Frente ${i + 1}`), 'FOCA', 'Outras', 'Indefinida'];
  const itens = ordem.filter((k) => Object.prototype.hasOwnProperty.call(c.frente, k)).map((k) => [k, segL(c.frente[k])]);
  const semPer = apSomaV(Object.entries(c.mes['None'] || {}));
  const outras = c.outras.map(apTitle).join(' e ') || '—';
  const { pos } = apDerivados(ctx);
  return '<div style="flex:1;padding:40px 100px 24px;display:flex;flex-direction:column;box-sizing:border-box;">' +
    apSubtitulo(texto) +
    '<div style="display:flex;gap:16px;">' +
    apKpi('Área Total', apN(tot), `${c.faz_conc}/${c.faz_tot} faz. concluídas`, AP_ESCURO) +
    apKpi('Ha Concluído', apN(conc), `${p}% do total`, AP_VERDE) +
    apKpi('Ha Reavaliar', apN(rea), 'projeto de safra anterior', AP_OURO) +
    apKpi('Ha A Fazer', apN(af), 'hectares restantes', AP_AZUL) +
    apKpi('Ha Sem Linhas', apN(sl), 'aguardando voo', AP_CINZA) +
    '</div>' + apProgresso(p, '20px') +
    '<div style="display:flex;gap:20px;margin-top:22px;flex:1;">' +
    apPainel('Ha Programado por Mês', apColunas(barras) +
      apLegenda([[AP_VERDE, 'Concluído'], [AP_CINZA, 'Sem Linhas'], [AP_OURO, 'Reavaliar'], [AP_AZUL, 'A Fazer']]) +
      apFonte(`${apN(semPer)} ha sem período programado no iCol (aparecem como “Indefinida” no painel de frentes).`), '1.15') +
    apPainel('Ha por Frente', apLinhas(itens, '70px', '11px', '13px', '7px') +
      apFonte(`Fonte: Hub Geotech (colheita_talhoes), ${apN(c.n_tal)} talhões / ${c.faz_tot} fazendas · dados exatos · ${pos}. ` +
        `“BIS - N” somado à Frente N; FOCA agrupa as frentes FOCA; “Outras” = ${outras}.`)) +
    '</div></div>';
}

function apSistematizacao(A, metas, ctx, texto) {
  const pr = A.preparo;
  const tot = pr.total;
  const ent = pr.etapa.Entregue;
  const p = apPct(ent[1], tot);
  const barras = Object.entries(pr.mes).map(([k, v]) => [k.startsWith('Lan') ? k : apRotMes(k), [[AP_VERDE, v]]]);
  const itens = Object.entries(pr.etapa).map(([e, v]) => [`${e} (${v[0]})`, [[e === 'Entregue' ? AP_VERDE : AP_AZUL, v[1]]]]);
  const { pos } = apDerivados(ctx);
  return '<div style="flex:1;padding:48px 100px 30px;display:flex;flex-direction:column;box-sizing:border-box;">' +
    apSubtitulo(texto) +
    '<div style="display:flex;gap:20px;">' +
    apKpi('Área Total', apN(tot), `${pr.n_faz} fazendas`, AP_ESCURO, true) +
    apKpi('Ha Concluído', apN(ent[1]), `${p}% do total · ${ent[0]} fazendas entregues`, AP_VERDE, true) +
    apKpi('Ha A Fazer', apN(tot - ent[1]), 'hectares restantes', AP_AZUL, true) +
    '</div>' + apProgresso(p) +
    '<div style="display:flex;gap:20px;margin-top:24px;flex:1;">' +
    apPainel('Projetos Entregues pela Geotecnologia por Mês', apColunas(barras, '10px', '10px', '12px') +
      apLegenda([[AP_VERDE, 'Entregue']], '12px', '12px'), '1', '20px 24px') +
    apPainel('Ha por Etapa (fazendas)', apLinhas(itens, '150px', '12px', '15px', '14px') +
      apFonte(`Fonte: Hub Geotech (talhão por etapa do Preparo), ${pr.n_tal} talhões / ${pr.n_faz} fazendas · dados exatos · ${pos}. ` +
        'Cada talhão aparece na etapa em que está; “Entregue” = Ok. Mês = data da entrega no Hub; ' +
        `ciclo 25-26 fora do slide (${apN(pr.fora_25_26)} ha lançados pelo PLANAGRI).`),
      '1', '20px 24px') +
    '</div></div>';
}

function apPlantio(A, metas, ctx, texto) {
  const pl = A.plantio;
  const s = pl.status, tot = pl.total;
  const conc = s.Ok || 0;
  const aberto = tot - conc;
  const p = apPct(conc, tot);
  const barras = Object.entries(pl.mes).map(([k, v]) => [
    apRotMes(k),
    [[AP_AZUL, Object.entries(v).filter(([st]) => st !== 'Ok').reduce((a, [, x]) => a + x, 0)], [AP_VERDE, v.Ok || 0]],
  ]);
  const nota = `* De ${apN(aberto)} ha em aberto: ${apN(s['Aguard. Map.'] || 0)} ha aguardando mapeamento, ${apN(s.Pendente || 0)} ha pendentes, ` +
    `${apN(s['Ag. Mapa'] || 0)} ha aguardando mapa de plantio e ${apN(s.Andamento || 0)} ha em andamento.`;
  const { pos } = apDerivados(ctx);
  return '<div style="flex:1;padding:48px 100px 30px;display:flex;flex-direction:column;box-sizing:border-box;">' +
    apSubtitulo(texto) +
    '<div style="display:flex;gap:20px;">' +
    apKpi('Área Total', apN(tot), `${pl.n_faz} fazendas`, AP_ESCURO, true) +
    apKpi('Ha Concluído', apN(conc), `${p}% do total`, AP_VERDE, true) +
    apKpi('Ha A Fazer', apN(aberto) + '*', 'hectares restantes', AP_AZUL, true) +
    '</div>' + apProgresso(p) +
    `<div style="font-size:13px;color:#8a978d;margin-top:8px;">${nota}</div>` +
    '<div style="background:#ffffff;border:1px solid #e3ece0;border-radius:10px;padding:22px 26px;display:flex;flex-direction:column;box-sizing:border-box;margin-top:16px;flex:1;">' +
    '<div style="font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#8a978d;font-weight:600;">Ha Programado por Mês de Plantio</div>' +
    apColunas(barras, '12px', '16px', '14px') +
    apLegenda([[AP_VERDE, 'Concluído'], [AP_AZUL, 'A Fazer']], '13px', '14px') +
    apFonte(`Fonte: Hub Geotech (talhao_plantio, mês de plantio do PLANAGRI), ${pl.n_tal} talhões / ${pl.n_faz} fazendas · dados exatos · ${pos}.`) +
    '</div></div>';
}

function apVoos(A, metas, ctx, texto) {
  const V = A.voos;
  const r = V.resumo, u = V.ultimos15DiasUteis;
  const [real, avoar, fora, forn] = apVoosNumeros(A, metas);
  const tot = real + avoar;
  const p = apPct(real, tot);
  const esperado = 15 * metas.meta_ha_dia;
  const dm = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
  const { corteBR } = apDerivados(ctx);
  const consulta = (V.atualizadoEm || apIso(new Date())).slice(0, 10);
  const linhasT = V.porTipo.map((t) => {
    let proj = t.realizadoHa + t.aVoarHa, marca = '';
    if (t.tipo === 'Ervas Daninhas') {
      proj = Math.max(metas.meta_ervas_ha, proj);
      marca = '*';
    } else if (t.tipo === 'Falhas Plantio Forn.') {
      proj = Math.max(metas.meta_fornecedor_ha, proj);
      marca = '**';
    }
    return [t.tipo, t.realizadoHa, proj, marca];
  });
  linhasT.sort((a, b) => b[2] - a[2]);
  const rows = linhasT.map(([nome, re, pj, mk]) => {
    const w = pj ? apRound(100 * re / pj, 1) : 0;
    const rot = apN(re);
    const dentro = w >= 8
      ? `<span style="font-size:11px;font-weight:700;color:#ffffff;white-space:nowrap;">${rot}</span>`
      : '';
    const foraRot = w >= 8
      ? ''
      : `<span style="position:absolute;left:${apP1(w)}%;top:50%;transform:translate(6px,-50%);font-size:11px;font-weight:700;color:#2f6fb0;white-space:nowrap;">${rot}</span>`;
    return `<div style="display:flex;align-items:center;gap:10px;"><span style="width:190px;font-size:13px;color:#5b6b60;">${nome}</span>` +
      `<div style="flex:1;height:20px;border-radius:3px;position:relative;background:rgba(47,111,176,0.28);">` +
      `<div style="position:absolute;left:0;top:0;height:100%;width:${apP1(w)}%;background:#019640;border-radius:3px;display:flex;align-items:center;justify-content:center;">${dentro}</div>${foraRot}</div>` +
      `<span style="font-size:13px;color:#2f6fb0;width:64px;text-align:right;">${apN(pj)}${mk}</span></div>`;
  });
  const nota = `* Inclui ${apN(fora)} ha de falha de plantio em área de fornecedor ainda fora do agendamento formal (meta de ${apN(metas.meta_fornecedor_ha)} ha, ` +
    `dos quais ${apN(forn.realizadoHa)} ha já voados e ${apN(forn.aVoarHa)} ha na fila). ` +
    `** Últimos 15 dias úteis: ${dm(u.de)} a ${dm(u.ate)}/${u.ate.slice(0, 4)}, ${u.diasComVoo} dias com voo, ${apN(u.talhoes)} talhões. ` +
    `Esperado = 15 dias úteis × ${metas.meta_ha_dia} ha/dia (média de voo diário).`;
  return '<div style="flex:1;padding:48px 100px 30px;display:flex;flex-direction:column;box-sizing:border-box;">' +
    apSubtitulo(texto) +
    '<div style="display:flex;gap:20px;">' +
    apKpi('Área Total', apN(tot), `${apN(r.realizadoTalhoes)} talhões voados + ${apN(r.aVoarTalhoes)} a voar`, AP_ESCURO, true) +
    apKpi('Ha Realizado', apN(real), `${p}% do total`, AP_VERDE, true) +
    apKpi('Ha Previsto (A Voar)', apN(avoar) + '*', 'hectares restantes', AP_AZUL, true) +
    apKpi('Últimos 15 Dias Úteis**', `${apN(u.ha)} ha`, `vs. ${apN(esperado)} ha esperado (${apPct(u.ha, esperado)}%)`, AP_OURO, true) +
    '</div>' + apProgresso(p) +
    `<div style="font-size:13px;color:#8a978d;margin-top:8px;">${nota}</div>` +
    '<div style="background:#ffffff;border:1px solid #e3ece0;border-radius:10px;padding:20px 28px;display:flex;flex-direction:column;box-sizing:border-box;margin-top:16px;flex:1;">' +
    '<div style="font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#8a978d;font-weight:600;">Ha Realizado × Projetado (por Tipo)</div>' +
    '<div style="display:flex;align-items:center;gap:10px;margin-top:14px;"><span style="width:190px;"></span><span style="flex:1;"></span>' +
    '<span style="font-size:11px;color:#2f6fb0;width:64px;text-align:right;font-weight:600;">Projetado</span></div>' +
    '<div style="display:flex;flex-direction:column;gap:11px;margin-top:8px;flex:1;justify-content:center;">' + rows.join('') + '</div>' +
    '<div style="display:flex;gap:16px;margin-top:10px;font-size:12px;color:#5b6b60;">' +
    '<span><span style="display:inline-block;width:9px;height:9px;background:#019640;border-radius:2px;margin-right:4px;"></span>Realizado</span>' +
    '<span><span style="display:inline-block;width:9px;height:9px;background:rgba(47,111,176,0.28);border:1px solid #2f6fb0;border-radius:2px;margin-right:4px;"></span>Projetado</span></div>' +
    apFonte(`Fonte: GeoMap / DroneManagement (integracao/voos/indicadores). Realizado = voos com status “Voado” de 01/04 a ${corteBR}; ` +
      `a voar = fila liberada em ${dm(consulta)}/${consulta.slice(0, 4)}. Projetado = realizado + a voar. ` +
      '“Outros” = Expansões, Sinistro, Ambiental, Drone Aplicação e Experimentação Agrícola. ' +
      `* Ervas Daninhas: projetado = meta oficial do ano-safra. ** Falhas Plantio Forn.: projetado = ${apN(metas.meta_fornecedor_ha)} ha de área de fornecedor.`) +
    '</div></div>';
}

function apDrone(A, metas, ctx, texto) {
  const d = A.drone;
  const safra = metas.safra_atual;
  const porSafra = d.por_safra;
  const real = porSafra[safra] || 0;
  const base = apSomaV(Object.entries(porSafra));
  const p = apPct(real, real + metas.drone_pendente_ha);
  const { pos, mesCorte } = apDerivados(ctx);
  const linhasSafra = [safra, '25/26', '24/25'].map((s) => [s, porSafra[s] || 0]);
  linhasSafra.push(['Anteriores / sem safra', base - apSomaV(linhasSafra)]);
  const mx = Math.max(...linhasSafra.map(([, v]) => v)) || 1;
  const barras = linhasSafra.map(([s, v]) =>
    '<div style="display:flex;align-items:center;gap:14px;margin-top:16px;">' +
    `<span style="width:200px;font-size:20px;color:#eaf5ee;">${s}</span>` +
    `<div style="flex:1;height:18px;background:rgba(255,255,255,.15);border-radius:4px;overflow:hidden;"><div style="width:${apP1(100 * v / mx)}%;height:100%;background:${s === safra ? '#ffffff' : '#9fd6b0'};"></div></div>` +
    `<span style="width:90px;text-align:right;font-size:22px;font-weight:600;">${apN(v)}</span></div>`).join('');
  const card = (r, v, c) =>
    `<div style="flex:1;background:#f2f6f1;border-radius:10px;padding:24px 22px;border-left:6px solid ${c};">` +
    `<div style="font-size:17px;letter-spacing:1px;text-transform:uppercase;color:#8a978d;">${r}</div>` +
    `<div style="font-size:40px;font-weight:700;color:#16261b;margin-top:8px;">${v}</div></div>`;
  return '<div style="flex:1;padding:48px 100px 30px;display:flex;flex-direction:column;box-sizing:border-box;">' +
    apSubtitulo(texto, '8px', '26px') +
    '<div style="display:flex;gap:48px;flex:1;margin-top:14px;"><div style="flex:1.3;display:flex;flex-direction:column;">' +
    '<div style="display:flex;align-items:baseline;gap:18px;">' +
    `<div style="font-size:96px;font-weight:700;color:#019640;line-height:1;">${apN(real)}</div>` +
    `<div style="font-size:20px;font-weight:600;letter-spacing:.5px;text-transform:uppercase;color:#5a9020;background:#eef6e6;padding:8px 18px;border-radius:20px;">Ha em projetos feitos na safra ${safra}</div></div>` +
    '<div style="display:flex;align-items:center;gap:18px;margin-top:22px;"><div style="flex:1;height:22px;background:#e3ece0;border-radius:11px;overflow:hidden;">' +
    `<div style="width:${p}%;height:100%;background:linear-gradient(90deg,#019640,#7BBB34);border-radius:11px;"></div></div>` +
    `<span style="font-size:28px;font-weight:700;color:#019640;">${p}%</span></div>` +
    '<div style="display:flex;gap:24px;margin-top:26px;">' +
    card('Área realizada', `${apN(real)} ha`, AP_VERDE) + card('Área pendente', `${apN(metas.drone_pendente_ha)} ha*`, AP_AZUL) +
    '</div>' +
    `<div style="margin-top:26px;font-size:22px;font-weight:300;color:#4a564d;line-height:1.4;">${apN(d.n_proj[safra] || 0)} projetos novos nesta safra (abr–${mesCorte}/${ctx.corte.slice(0, 4)}), em ${apN(d.faz_safra[safra] || 0)} fazendas.</div>` +
    '<div style="margin-top:10px;font-size:17px;font-weight:300;color:#8a978d;line-height:1.4;">* Área pendente informada pela equipe (mantida da S3M8). Progresso = realizado ÷ (realizado + pendente). Área = campo “Área Apli” (ha) do shape de aplicação publicado; safra = pasta de origem do projeto registrada na importação para o Hub (ou data da revisão, para projetos feitos no Hub).</div>' +
    '</div>' +
    '<div style="flex:1;background:#019640;border-radius:12px;padding:36px 38px;color:#ffffff;display:flex;flex-direction:column;box-sizing:border-box;">' +
    '<div style="font-size:20px;letter-spacing:1.5px;text-transform:uppercase;color:#bfe6cb;font-weight:600;">Base de projetos vigentes (ha)</div>' +
    `<div style="font-size:96px;font-weight:700;line-height:1;margin-top:16px;">${apN(base)}</div>` +
    `<div style="font-size:22px;font-weight:300;margin-top:16px;color:#eaf5ee;line-height:1.4;">ha de aplicação em ${apN(d.n_base)} projetos disponíveis no portal de downloads (${apN(d.faz_base)} fazendas) — por safra de elaboração:</div>` +
    `<div style="margin-top:12px;">${barras}</div>` +
    '<div style="flex:1;"></div>' +
    `<div style="font-size:16px;font-weight:300;color:#cbe8d4;line-height:1.4;">Fonte: Hub Geotech — portal de downloads, módulo Drone (revisões vigentes) · ${pos}.</div>` +
    '</div></div></div>';
}

function apDivisoria(A, metas) {
  const c = A.colheita, pr = A.preparo, pl = A.plantio;
  const [vReal, vPrev] = apVoosNumeros(A, metas);
  const dReal = A.drone.por_safra[metas.safra_atual] || 0;
  const prConc = pr.etapa.Entregue[1];
  const plConc = pl.status.Ok || 0;
  const cConc = c.status.CONCLUIDO || 0;
  const item = (titulo, l1, v1, l2, v2, p) =>
    '<div><div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px;">' +
    `<span style="font-size:24px;font-weight:600;">${titulo}</span>` +
    `<span style="font-size:19px;font-weight:600;color:#16261b;">${l1} <span style="color:#019640;font-weight:700;">${v1} ha</span> &nbsp;·&nbsp; ${l2} <span style="color:#5b6b60;font-weight:700;">${v2} ha</span></span></div>` +
    '<div style="height:22px;background:#e3ece0;border-radius:11px;overflow:hidden;">' +
    `<div style="width:${p}%;height:100%;background:linear-gradient(90deg,#019640,#7BBB34);border-radius:11px;"></div></div></div>`;
  return '<div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding:0 100px;box-sizing:border-box;">' +
    '<p style="margin:0 0 30px;font-size:32px;font-weight:300;color:#5b6b60;max-width:1400px;line-height:1.4;">A seguir, o desempenho dos cinco indicadores operacionais do setor.</p>' +
    '<div style="display:flex;flex-direction:column;gap:24px;max-width:1600px;">' +
    item('Projetos de Colheita', 'Concluído', apN(cConc), 'A Fazer', apN(c.status['A FAZER'] || 0), apPct(cConc, c.total)) +
    item('Projetos de Sistematização', 'Concluído', apN(prConc), 'A Fazer', apN(pr.total - prConc), apPct(prConc, pr.total)) +
    item('Projetos de Plantio', 'Concluído', apN(plConc), 'A Fazer', apN(pl.total - plConc), apPct(plConc, pl.total)) +
    item('Voos com Drone', 'Realizado', apN(vReal), 'Previsto', apN(vPrev), apPct(vReal, vReal + vPrev)) +
    item('Projetos de Drone de Aplicação', 'Realizado', apN(dReal), 'Pendente', apN(metas.drone_pendente_ha), apPct(dReal, dReal + metas.drone_pendente_ha)) +
    '</div></div>';
}

// Retorno do gerador Python do slide `chave`, byte a byte. Se `subtitulo` (texto do usuário)
// vier preenchido, substitui o texto padrão do subtítulo, escapado. Divisória não tem subtítulo.
function apCorpo(chave, A, metas, ctx, subtitulo) {
  if (chave === 'divisoria') return apDivisoria(A, metas);
  const usuario = (subtitulo || '').trim();
  const texto = usuario ? apEsc(usuario) : apSubtituloPadrao(chave, A, metas, ctx);
  switch (chave) {
    case 'colheita': return apColheita(A, metas, ctx, texto);
    case 'sistematizacao': return apSistematizacao(A, metas, ctx, texto);
    case 'plantio': return apPlantio(A, metas, ctx, texto);
    case 'voos': return apVoos(A, metas, ctx, texto);
    case 'drone': return apDrone(A, metas, ctx, texto);
    default: throw new Error(`slide desconhecido: ${chave}`);
  }
}

// Frame completo do slide ctx.num. textos = { subtitulo?, destaque? }.
function apSlide(chave, A, metas, textos, ctx) {
  const t = textos || {};
  const destaque = (t.destaque || '').trim();
  const corpo = apCorpo(chave, A, metas, ctx, t.subtitulo);
  const rodape = `${ctx.semana} · Dados até ${apDerivados(ctx).corteBR}`;
  return '<section class="ap-slide">' +
    '<div class="ap-regua"></div>' +
    '<header class="ap-cabecalho">' +
    `<h1 class="ap-titulo">${apEsc(AP_TITULOS[chave])}</h1>` +
    '<div class="ap-selo"><img class="ap-logo" src="assets/pedra/logo.png" alt="Pedra Agroindustrial S/A"></div>' +
    '</header>' +
    `<div class="ap-corpo">${corpo}</div>` +
    (destaque ? `<div class="ap-destaque">${apEsc(destaque)}</div>` : '') +
    `<footer class="ap-rodape"><span>${apEsc(rodape)}</span><span>${apEsc(ctx.num)}</span></footer>` +
    '</section>';
}
