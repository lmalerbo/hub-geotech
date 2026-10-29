// Drone: área de trabalho da fazenda (mapa, painel, envios, gerar/publicar). Carregado por index.html por último.

async function drAbrirFazenda(cod,doc){
  DR.cod=cod;DR.doc=doc||'normal';DR.obstGeo=null;DR.obstAss=null;DR.sel=new Map();DR.rem=new Set();DR.modoRemover=false;DR.ajusteId=null;
  drPollParar();drMapaDescartar();DR.ass=null;
  const pnl=document.getElementById('dr-faz');
  DR.voo=null;
  Mo.carregando(pnl);await drCarregarFazenda();Mo.pronto(pnl);
}

// Uma atualização por vez: resposta de outra fazenda (ou de um ciclo antigo) é descartada.
// A chave inclui o número do ciclo: um poll que estava em voo quando uma ação recarregou também é descartado.
async function drCarregarFazenda(){
  const cod=DR.cod,ciclo=DR.ciclo=(DR.ciclo||0)+1,chave=()=>DR.cod+':'+DR.ciclo,minha=cod+':'+ciclo;
  try{
    const [geo,faz,sols,obst]=await Promise.all([
      drRpc('drone_mapa_fazenda',{p_cod_faz:cod}),
      sb.from('fazendas').select('cod_faz,nome').eq('cod_faz',cod).single(),
      sb.from('drone_solicitacoes').select('id,tipo,status,observacao,solicitante_id,data_desejada,criado_em').eq('cod_faz',cod).neq('origem','legado').not('status','in','(ok,cancelado)'),
      sb.from('drone_obstaculo_versoes').select('classe_m,versao,enviado_em').eq('cod_faz',cod).eq('vigente',true)]);
    if(!drRespostaValida(minha,chave()))return;
    const sIds=(sols.data||[]).map(s=>s.id);
    const ger=sIds.length?await sb.from('drone_geracoes').select('id,solicitacao_id,status,alertas,erro,previa_pdf,publicar_pedido_em,publicacao_erro,resumo,escopo,pedido_em,iniciado_em')
      .in('solicitacao_id',sIds).neq('status','descartada').neq('status','publicada').order('id',{ascending:false}):{data:[]};
    if(!drRespostaValida(minha,chave()))return;
    const env=await sb.from('drone_envios').select('id,tipo,status,erro,enviado_em,arquivos,classe_m').eq('cod_faz',cod).order('id',{ascending:false}).limit(5);
    if(!drRespostaValida(minha,chave()))return;
    const proj=await sb.from('projetos').select('id').eq('modulo_id','drone').eq('tipo','individual').eq('cod_faz',cod);
    if(!drRespostaValida(minha,chave()))return;
    const revs=proj.data&&proj.data.length?await sb.from('projeto_revisoes').select('numero,documento,motivo,criado_em')
      .eq('projeto_id',proj.data[0].id).order('numero',{ascending:false}):{data:[]};
    if(!drRespostaValida(minha,chave()))return;
    DR.geo=geo;DR.info={faz:faz.data,sols:sols.data||[],obst:obst.data||[],ger:ger.data||[],envios:env.data||[],revs:revs.data||[]};
    const ass=drAssinaturaObst(DR.info.obst);
    if(ass!==DR.obstAss){DR.obstAss=ass;DR.obstGeo=null;}
  }catch(e){
    if(!drRespostaValida(minha,chave()))return;
    // Já desenhada: mantém o mapa, mostra o erro no painel e tenta de novo no próximo ciclo.
    if(DR.ass){drErro(e);drPollIniciar(drCicloFazenda,5000);}
    else document.getElementById('dr-faz').innerHTML=`<div class="dr-vazio dr-err">${esc(e.message)}</div>`;
    return;
  }
  drRedesenhar();
  if(drOcupado(DR.info,drAtual().ger))drPollIniciar(drCicloFazenda,5000);
  else drPollParar();
}
async function drCicloFazenda(){await drCarregarFazenda();drCarregarPainel();}

// Desenha só as partes que mudaram desde o ciclo anterior (assinaturas em drAssinaturas).
function drRedesenhar(){
  const ass=drAssinaturas(DR.info,DR.geo,DR.doc),partes=drPartesMudadas(DR.ass,ass);
  DR.ass=ass;drDesenhar(partes);
}
// Troca Normal/Catação: o mapa fica, só as fontes e a cor mudam.
function drTrocarDoc(doc){if(doc===DR.doc)return;DR.doc=doc;DR.sel=new Map();DR.rem=new Set();drRedesenhar();}
function drDesenhar(partes){
  const tem=p=>partes.includes(p);
  if(!DR.mapa||!document.getElementById('dr-map')){drMapaDescartar();drEsqueleto();drMapaCriar();drPainelLateral();drEtapasAtualizar();}
  else{
    if(tem('cab'))document.getElementById('dr-ph').outerHTML=drCabecalhoHtml();
    if(tem('etapas'))drEtapasAtualizar();
    if(tem('mapa'))drMapaAtualizar();
    if(tem('obst')&&DR.mostrarObst)drObstaculos(true);
    if(tem('painel')){drPainelLateral();drAtualizarSelecaoMapa();}   // o estado 'ger' dos talhões segue a geração
  }
  drVooPublicacao();drAnimGeracao();
}
function drEsqueleto(){
  document.getElementById('dr-faz').innerHTML=drCabecalhoHtml()+`
    <div id="dr-etapas" class="dr-etapas"></div>
    <div class="dr-trab"><div class="dr-mapa-box">
      <div class="dr-map" id="dr-map"></div>
      <div class="dr-ferr" id="dr-ferr" role="toolbar" aria-label="Ferramentas do mapa" hidden></div>
      <div class="dr-dica" id="dr-dica" hidden></div>
      <div id="dr-camadas"></div>
      <div class="dr-leg" id="dr-leg"></div>
    </div>
    <aside class="dr-side" id="dr-side" aria-label="Painel"><div class="dr-side-cab" id="dr-side-cab"></div><div class="dr-side-corpo" id="dr-side-corpo"></div><div class="dr-side-rodape" id="dr-side-rodape"></div></aside></div>`;
  DR.etapaAtiva=null;DR.camadasAb=false;
}
// Atualiza as fontes do mapa que já existe (o 'load' lê DR.geo se ainda estiver carregando).
function drMapaAtualizar(){
  const m=DR.mapa;if(!m||!m.getSource('tal'))return;
  m.getSource('tal').setData({type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada==='talhao')});
  m.getSource('apl').setData({type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada===DR.doc)});
  m.setPaintProperty('apl-f','fill-color',DR_COR[DR.doc]);
  const leg=document.getElementById('dr-leg-apl');if(leg)leg.style.background=DR_COR[DR.doc];
  drAtualizarSelecaoMapa();
}
function drMapaDescartar(){
  drPulsarGeracao(false);
  DR.varr&&DR.varr.parar();DR.varr=null;drTempoParar();
  DR.mapa&&DR.mapa.remove();DR.mapa=null;   // também depois de um erro que apagou #dr-faz
}
// Espera da geração: varredura no mapa, pulso nos talhões do escopo e trilho no painel.
function drAnimGeracao(){
  const {ger}=drAtual(),on=!!ger&&['fila','processando'].includes(ger.status);
  const box=document.getElementById('dr-map');
  if(on&&!DR.varr&&box)DR.varr=Mo.varredura(box);
  if(!on&&DR.varr){DR.varr.parar();DR.varr=null;}
  drPulsarGeracao(on);
  const g=document.querySelector('#dr-side .drp-gerando');   // painel só é redesenhado quando muda
  if(g&&!g.querySelector(':scope>.mo-trilho'))Mo.trilho(g);
}
// Pulso do contorno dos talhões em geração: line-opacity da camada tal-l só no estado 'ger', ~20 quadros/s.
function drPulsarGeracao(on){
  const m=DR.mapa,calmo=matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(!on||calmo||!m||!m.getLayer('tal-l')){
    cancelAnimationFrame(DR.pulso);DR.pulso=null;
    if(m&&m.getLayer('tal-l'))m.setPaintProperty('tal-l','line-opacity',1);
    return;
  }
  if(DR.pulso)return;
  const t0=performance.now();let ult=0;
  const passo=t=>{
    if(DR.mapa!==m||!m.getLayer('tal-l')){DR.pulso=null;return;}
    if(t-ult>=50&&!DR_POLL.fora){ult=t;                      // fora da view do Drone: não pinta
      const op=.35+.65*(.5+.5*Math.cos((t-t0)/1600*2*Math.PI));
      m.setPaintProperty('tal-l','line-opacity',['case',['boolean',['feature-state','ger'],false],op,1]);}
    DR.pulso=requestAnimationFrame(passo);
  };
  DR.pulso=requestAnimationFrame(passo);
}
// Camada nova chega em 300 ms (0 com menos movimento).
function drFadeCamada(id,prop,final){
  const m=DR.mapa;if(!m||!m.getLayer(id))return;
  const ms=matchMedia('(prefers-reduced-motion: reduce)').matches?0:300;
  m.setPaintProperty(id,prop+'-transition',{duration:ms,delay:0});
  requestAnimationFrame(()=>{if(m.getLayer(id))m.setPaintProperty(id,prop,final);});
}

function drCabecalhoHtml(){
  const g=DR.geo,i=DR.info,tal=g.features.filter(f=>f.properties.camada==='talhao');
  const area=tal.filter(f=>f.properties.status!=='fora_da_base').reduce((s,f)=>s+(f.properties.area_ha||0),0);
  const pct=g.cobertura_pct,ch=drChipObstaculos(i.obst,i.envios,new Date()),proc=ch.tom==='proc',edita=podeEditar('drone');
  const aba=(doc,tit,x,extra)=>`<button class="dr-aba${DR.doc===doc?' on':''}" aria-pressed="${DR.doc===doc}" onclick="drTrocarDoc('${doc}')">${tit} <span>${x?'Rev'+x.revisao+(extra?' · '+extra:''):'sem projeto'}</span></button>`;
  const ico=`<span class="ico${proc?' dr-gira':''}">${proc?'progress_activity':'warning'}</span>`;
  const chip=`<span class="dr-obst-chip tom-${ch.tom}">${esc(ch.texto)}</span>`;
  const obst=edita?`<button class="dr-obst" onclick="drEnviar('obstaculos')">${ico}<b>Obstáculos</b>${chip}</button>`
    :`<span class="dr-obst dr-obst-so">${ico}<b>Obstáculos</b>${chip}</span>`;
  return`<div class="dr-ph" id="dr-ph">
      <button class="dr-ini" onclick="driVoltar()"><span class="ico">arrow_back</span>Início</button>
      <span class="dr-sep" aria-hidden="true"></span>
      <span class="dr-cod">${DR.cod}</span>
      <div class="dr-ident"><div class="nm">${esc(i.faz.nome)}</div><div class="sub">${tal.length} talhões · ${fmtNum(area)} ha</div></div>
      <nav aria-label="Documento" class="dr-abas">${aba('normal','Normal',g.normal,pct!=null?Math.floor(pct)+'%':'')}${aba('catacao','Catação',g.catacao,'')}</nav>
      <div class="dr-ph-dir">${obst}<button id="dr-mais" class="dr-mais" aria-label="Mais ações" aria-haspopup="menu" aria-expanded="false" onclick="drMenuAbrir()"><span class="ico">more_horiz</span></button></div>
    </div>`;
}

// Publicação pedida: o drone sobrevoa o mapa até o agente responder. A tela é
// redesenhada a cada 5 s (polling); DR.voo guarda desde quando, para o voo
// continuar de onde estava. Quando a publicação some da lista (publicada) o
// drone pousa com ✓; se voltar com erro, mostra a falha.
function drVooPublicacao(){
  const mapa=document.getElementById('dr-map');if(!mapa)return;
  const {ger}=drAtual();
  if(ger&&ger.publicar_pedido_em&&!ger.publicacao_erro){
    if(!DR.voo||DR.voo.id!==ger.id)DR.voo={id:ger.id,desde:Date.now()};
    if(!mapa.querySelector(':scope>.mo-voo'))Mo.voo(mapa,{texto:'Publicando no portal…',desde:DR.voo.desde});
  }else if(DR.voo){
    const erro=ger&&ger.id===DR.voo.id&&ger.publicacao_erro;
    Mo.voo(mapa,{desde:DR.voo.desde}).pousar(!erro,erro?'Falha ao publicar':'Publicado no portal');
    DR.voo=null;
  }
}

// Cria o mapa uma vez por fazenda. As fontes saem de DR.geo/DR.doc na hora do 'load'.
function drMapaCriar(){
  const box=document.getElementById('dr-map');
  Mo.carregando(box);
  const m=new maplibregl.Map({container:'dr-map',attributionControl:false,
    style:{version:8,glyphs:'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',sources:{},
      layers:[{id:'fundo',type:'background',paint:{'background-color':'#f7f8fa'}}]}});
  DR.mapa=m;
  m.addControl(new maplibregl.NavigationControl({showCompass:false}),'top-right');
  m.on('load',()=>{
    const fc={type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada==='talhao')};
    const apl={type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada===DR.doc)};
    m.addSource('tal',{type:'geojson',data:fc,promoteId:'talhao'});
    m.addSource('apl',{type:'geojson',data:apl});
    m.addLayer({id:'tal-f',type:'fill',source:'tal',paint:{'fill-color':['case',
      ['boolean',['feature-state','rem'],false],'#fbe0e0',['boolean',['feature-state','sel'],false],'#d9defc',
      ['==',['get','status'],'sem_projeto'],DR_COR.sem,'#ffffff']}});
    m.addLayer({id:'apl-f',type:'fill',source:'apl',paint:{'fill-color':DR_COR[DR.doc],'fill-opacity':.75}});
    m.addLayer({id:'tal-l',type:'line',source:'tal',paint:{'line-color':['case',
      ['boolean',['feature-state','rem'],false],DR_COR.rem,['boolean',['feature-state','sel'],false],DR_COR.sel,
      ['boolean',['feature-state','ger'],false],DR_COR.sel,
      ['boolean',['feature-state','novo'],false],'#2f7a3e',
      ['==',['get','status'],'fora_da_base'],DR_COR.fora,'#1f2a30'],
      'line-width':['case',['boolean',['feature-state','novo'],false],2.5,['case',['any',['boolean',['feature-state','sel'],false],['boolean',['feature-state','rem'],false],
        ['boolean',['feature-state','ger'],false],['==',['get','status'],'fora_da_base']],2,0.6]],
      'line-opacity':1}});
    m.addLayer({id:'tal-t',type:'symbol',source:'tal',layout:{'text-field':['to-string',['get','talhao']],
      'text-font':['Open Sans Semibold'],'text-size':11},paint:{'text-color':'#1f2a30','text-halo-color':'#fff','text-halo-width':1.5}});
    const b=new maplibregl.LngLatBounds();
    fc.features.forEach(f=>(f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates)
      .forEach(p=>p[0].forEach(c=>b.extend(c))));
    if(!b.isEmpty())m.fitBounds(b,{padding:30,duration:0});
    Mo.pronto(box,{cascata:false});
    m.on('click','tal-f',e=>drClicarTalhao(e.features[0].properties));
    m.on('mouseenter','tal-f',()=>m.getCanvas().style.cursor='pointer');
    m.on('mouseleave','tal-f',()=>m.getCanvas().style.cursor='');
    drAtualizarSelecaoMapa();if(DR.mostrarObst)drObstaculos(true);drAnimGeracao();
  });
}

function drAtualizarSelecaoMapa(){
  const m=DR.mapa;if(!m||!m.getSource('tal'))return;
  const {ger}=drAtual(),gerando=new Set(drTalhoesGerando(ger)),
    novos=new Set(ger&&ger.status==='pronta'?((ger.escopo&&ger.escopo.incluir)||[]).map(i=>i.talhao):[]);
  DR.geo.features.filter(f=>f.properties.camada==='talhao').forEach(f=>{
    const n=f.properties.talhao;
    m.setFeatureState({source:'tal',id:n},{sel:DR.sel.has(n),rem:DR.rem.has(n),ger:gerando.has(n),novo:novos.has(n)});
  });
}

function drClicarTalhao(p){
  if(!podeEditar('drone')||DR.doc!=='normal')return;
  const {ger}=drAtual();if(ger)return;                       // prévia aberta: trava a seleção
  const n=p.talhao;
  if(DR.modoRemover){
    if(p.status==='sem_projeto')return;
    DR.rem.has(n)?DR.rem.delete(n):(DR.rem.add(n),DR.sel.delete(n));
  }else{
    if(p.status==='fora_da_base')return;
    DR.sel.has(n)?DR.sel.delete(n):(DR.sel.set(n,'sistema'),DR.rem.delete(n));
  }
  drAtualizarSelecaoMapa();drPainelLateral();
}

function drSelecionarSemProjeto(){
  DR.geo.features.filter(f=>f.properties.camada==='talhao'&&f.properties.status==='sem_projeto')
    .forEach(f=>{DR.sel.set(f.properties.talhao,'sistema');DR.rem.delete(f.properties.talhao);});
  drAtualizarSelecaoMapa();drPainelLateral();
}

// Fonte de um talhão (Sistema | Shape), pelo seletor da linha do painel.
function drFonteTalhao(n,f){if(!DR.sel.has(n))return;DR.sel.set(n,f);drAtualizarSelecaoMapa();drPainelLateral();}
// Arrastar arquivos para a área do painel: o mesmo fluxo do botão.
function drSoltar(e,tipo){e.preventDefault();const arqs=[...(e.dataTransfer?.files||[])];if(arqs.length)drEnviarArquivos(tipo,arqs,null,e.currentTarget);}
function drLimparErro(){const el=document.getElementById('dr-err');if(el)el.textContent='';}
// Tempo decorrido da geração: atualiza o texto no lugar, sem redesenhar o cartão (o trilho não reinicia).
function drTempoAtualizar(){
  const el=document.getElementById('dr-decorrido'),{ger}=drAtual();
  if(!el||!ger){drTempoParar();return;}
  el.textContent=drDecorrido(ger.pedido_em,Date.now());
}
function drTempoParar(){clearInterval(DR.tempo);DR.tempo=null;}


// ── cabeçalho, etapas, menu ⋯ e gaveta de revisões (S4.3) ──
const DR_ETAPAS=['Montar revisão','Gerar prévia','Conferir','Publicado'];
function drEtapasEstado(){
  const {sol,ger}=drAtual(),est=drEstadoPainel({doc:DR.doc,sol,ger,edita:podeEditar('drone')});
  return{sol,est,ativa:drEtapaAtiva(sol,ger),mostra:DR.doc==='normal'||['gerando','previa','publicando'].includes(est)};
}
function drEtapasHtml(){
  const {sol,est,ativa}=drEtapasEstado();
  const passos=DR_ETAPAS.map((t,k)=>{
    const nome=k===1&&est==='gerando'?'Gerando prévia':k===3&&est==='publicando'?'Publicando':t;
    const ocupado=k===ativa&&(est==='gerando'||est==='publicando');
    const marca=k<ativa?'<span class="ico">check</span>':ocupado?'<span class="ico dr-gira">progress_activity</span>':k+1;
    const cls=k<ativa?'feito':k===ativa?'agora':'';
    return(k?`<i class="dr-trilho-e${k<=ativa?' on':''}" aria-hidden="true"></i>`:'')
      +`<span class="dr-etapa ${cls}" data-etapa="${k}"${k===ativa?' aria-current="step"':''}><b>${marca}</b>${nome}</span>`;
  }).join('');
  const card=(DR.painel?.solicitacoes||[]).find(c=>sol&&c.id===sol.id);
  return`<div class="dr-etapas-l">${passos}</div><span class="dr-etapas-ctx">${esc(drContextoSol(card))}</span>`;
}
// Na troca de etapa entre ciclos, a moldura desliza (Mo.etapa); na primeira montagem, sem animação.
function drEtapasAtualizar(){
  const el=document.getElementById('dr-etapas');if(!el)return;
  const e=drEtapasEstado(),de=DR.etapaAtiva;
  DR.etapaAtiva=e.ativa;
  el.hidden=!e.mostra;
  el.innerHTML=e.mostra?drEtapasHtml():'';
  if(e.mostra&&de!=null&&de!==e.ativa)Mo.etapa(el,de,e.ativa);
}
// Menu ⋯: lista ancorada no botão. Esc ou clique fora fecha; escolher uma ação também fecha.
function drMenuAbrir(){
  if(document.getElementById('dr-menu')){drMenuFechar();return;}
  const btn=document.getElementById('dr-mais');if(!btn)return;
  const {sol,ger}=drAtual(),r=btn.getBoundingClientRect(),m=document.createElement('div');
  m.id='dr-menu';m.className='dr-menu';m.setAttribute('role','menu');
  m.style.top=r.bottom+6+'px';m.style.right=innerWidth-r.right+'px';
  m.innerHTML=`<button role="menuitem" onclick="drMenuFechar();drRevisoesAbrir()"><span class="ico">history</span>Revisões</button>`
    +(sol&&drPodeCancelar(sol,ger,EU)?`<button role="menuitem" class="perigo" onclick="drCancelar(${sol.id});drMenuFechar()"><span class="ico">cancel</span>Cancelar solicitação</button>`:'');
  document.body.appendChild(m);
  btn.setAttribute('aria-expanded','true');
  m.querySelector('button').focus();
  m._ouve=e=>{
    if(e.type==='keydown'&&e.key==='Escape'){e.preventDefault();drMenuFechar(true);}
    else if(e.type==='mousedown'&&!m.contains(e.target)&&e.target!==btn)drMenuFechar();
  };
  document.addEventListener('keydown',m._ouve);document.addEventListener('mousedown',m._ouve);
}
function drMenuFechar(voltarFoco){
  const m=document.getElementById('dr-menu');if(!m)return;
  document.removeEventListener('keydown',m._ouve);document.removeEventListener('mousedown',m._ouve);
  m.remove();
  const btn=document.getElementById('dr-mais');
  if(btn){btn.setAttribute('aria-expanded','false');if(voltarFoco)btn.focus();}
}
// Gaveta de revisões (mesmo modelo da gaveta da Atenção). Esc, × e clique no fundo fecham; o foco volta ao ⋯.
function drRevisoesAbrir(){
  if(document.getElementById('dr-rev-fundo'))return;
  const rev=(DR.info.revs||[]).filter(r=>r.documento===DR.doc),nome=DR.doc==='normal'?'Normal':'Catação';
  const fundo=document.createElement('div');fundo.id='dr-rev-fundo';fundo.className='dri-fundo';
  const linhas=rev.map(r=>`<div class="dr-rev-l"><span>Rev${r.numero} · ${esc(new Date(r.criado_em).toLocaleDateString('pt-BR'))} · ${esc(r.motivo||'sem motivo')}</span></div>`).join('');
  fundo.innerHTML=`<aside class="dri-gaveta" role="dialog" aria-modal="true" aria-labelledby="dr-rev-t">
    <header><h2 id="dr-rev-t">Revisões · ${nome}</h2><button class="dr-x" id="dr-rev-x" aria-label="Fechar"><span class="ico">close</span></button></header>
    <div class="dri-gav-l">${linhas||'<p class="dri-vazio">Nenhuma revisão publicada ainda.</p>'}</div>
  </aside>`;
  document.body.appendChild(fundo);
  fundo.onclick=e=>{if(e.target===fundo)drRevisoesFechar();};
  fundo.querySelector('#dr-rev-x').onclick=drRevisoesFechar;
  fundo._esc=e=>{if(e.key==='Escape'){e.preventDefault();drRevisoesFechar();}};
  document.addEventListener('keydown',fundo._esc);
  fundo.querySelector('#dr-rev-x').focus();
}
function drRevisoesFechar(){
  const f=document.getElementById('dr-rev-fundo');if(!f)return;
  document.removeEventListener('keydown',f._esc);f.remove();
  const btn=document.getElementById('dr-mais');if(btn)btn.focus();
}

// ── ferramentas, dica, Camadas e legenda do mapa (S4.4) ──
function drFerramenta(qual){
  if(qual==='semprojeto')return drSelecionarSemProjeto();
  if(qual==='limpar'){DR.sel=new Map();DR.rem=new Set();}
  else DR.modoRemover=qual==='remover';
  drAtualizarSelecaoMapa();drPainelLateral();
}
function drFerramentasHtml(){
  return`<button aria-pressed="${!DR.modoRemover}" onclick="drFerramenta('incluir')"><span class="ico">add_circle</span>Incluir</button>
    <button aria-pressed="${!!DR.modoRemover}" onclick="drFerramenta('remover')"><span class="ico">remove_circle</span>Remover</button>
    <span class="dr-ferr-sep" aria-hidden="true"></span>
    <button onclick="drFerramenta('semprojeto')"><span class="ico">select_all</span>Sem projeto</button>
    <button onclick="drFerramenta('limpar')"><span class="ico">deselect</span>Limpar</button>`;
}
function drDicaHtml(est){
  if(est==='montando')return DR.modoRemover?'Clique nos talhões para remover':'Clique nos talhões para incluir ou refazer';
  if(est==='gerando')return'<span class="ico">lock</span>Mapa travado enquanto a prévia é gerada. Pode navegar e dar zoom.';
  return'';
}
function drLegendaHtml(est){
  const sw=(cor,borda,t)=>`<span><i style="background:${cor};border-color:${borda}"></i>${t}</span>`;
  const dot=c=>`<span><i class="dr-bola" style="background:${DR_OBS_COR[c]}"></i>${c} m</span>`;
  if(DR.doc==='catacao')return sw(DR_COR.catacao,'#1f2a30','Catação vigente'+(DR.geo.catacao?` (Rev${DR.geo.catacao.revisao})`:''));
  const vig=sw(DR_COR.normal,'#1f2a30',est==='previa'?'já publicado':'aplicação vigente');
  if(est==='previa')return sw('#fff','#2f7a3e','novo nesta prévia')+vig+dot(15)+dot(25)+dot(50);
  return vig+sw(DR_COR.sem,'#1f2a30','sem projeto')+sw('#d9defc',DR_COR.sel,'na revisão')+sw('#fff',DR_COR.fora,'fora da Base');
}
// Barra de ferramentas, dica, Camadas e legenda dependem do estado do painel (drEstadoPainel).
function drMapaUi(){
  const {sol,ger}=drAtual(),est=drEstadoPainel({doc:DR.doc,sol,ger,edita:podeEditar('drone')});
  const ferr=document.getElementById('dr-ferr');
  if(ferr){
    const bts=[...ferr.querySelectorAll('button')],foco=bts.indexOf(document.activeElement);
    ferr.hidden=est!=='montando';
    ferr.innerHTML=est==='montando'?drFerramentasHtml():'';
    if(foco>=0)ferr.querySelectorAll('button')[foco]?.focus();
  }
  const dica=document.getElementById('dr-dica');
  if(dica){const t=drDicaHtml(est);dica.hidden=!t;dica.innerHTML=t;}
  const cam=document.getElementById('dr-camadas');
  if(cam){
    if(est==='previa'&&ger&&DR.obstPrevia!==ger.id){DR.obstPrevia=ger.id;if(!DR.mostrarObst)drObstaculos(true);}   // uma vez por prévia
    const rot=DR.mostrarObst&&est==='previa'?'Camadas · obstáculos ligados':'Camadas';
    cam.innerHTML=`<button class="dr-cam-btn" aria-expanded="${!!DR.camadasAb}"${DR.camadasAb?' aria-controls="dr-cam-caixa"':''} onclick="drCamadasAlternar()"><span class="ico">layers</span>${rot}</button>`
      +(DR.camadasAb?`<div class="dr-cam-caixa" id="dr-cam-caixa"><label><input type="checkbox" ${DR.mostrarObst?'checked':''} onchange="drObstaculos(this.checked);drMapaUi()"> Obstáculos</label></div>`:'');
  }
  const leg=document.getElementById('dr-leg');if(leg)leg.innerHTML=drLegendaHtml(est);
}
function drCamadasAlternar(){
  DR.camadasAb=!DR.camadasAb;drMapaUi();
  document.querySelector('.dr-cam-btn')?.focus();
}

// ── painel lateral: um estado por vez (S4.5) ──
// Cada drPainel_<estado> devolve {sobre, titulo, corpo, rodape}. drPainelLateral grava cabeçalho, corpo e rodapé;
// a linha de erro (#dr-err) vai no rodapé, ou no fim do corpo quando o estado não tem rodapé.
function drNomeDoc(doc){return doc==='normal'?'Normal':'Catação';}
function drRevProx(doc){const x=DR.geo[doc];return x?x.revisao+1:0;}
function drCartao(sol){return(DR.painel?.solicitacoes||[]).find(c=>sol&&c.id===sol.id)||null;}
function drQuando(iso){return new Date(iso).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});}
function drHora(iso){return iso?new Date(iso).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'}):'—';}
function drPlural(n,um,varios){return`${n} ${n===1?um:varios}`;}
function drTalhaoProps(){return new Map(DR.geo.features.filter(f=>f.properties.camada==='talhao').map(f=>[f.properties.talhao,f.properties]));}
function drPasso(k,atual,titulo,corpo){
  const cls=k<atual?'feito':k===atual?'agora':'';
  return`<li><span class="dr-num ${cls}">${k<atual?'<span class="ico">check</span>':k}</span><div class="dr-passo-c"><b>${titulo}</b>${corpo||''}</div></li>`;
}
function drLinhaResumo(a,b){return`<div class="dr-row"><span>${a}</span><span>${b}</span></div>`;}

function drPainel_montando(){
  const inc=[...DR.sel].sort((a,b)=>a[0]-b[0]),rem=[...DR.rem].sort((a,b)=>a-b),props=drTalhaoProps();
  const ha=n=>props.get(n)?.area_ha||0,soma=inc.reduce((s,[n])=>s+ha(n),0);
  const shape=inc.filter(([,f])=>f==='shape').map(([n])=>n);
  const ev=DR.ajusteId?(DR.info.envios.find(e=>e.id===DR.ajusteId)||{status:'fila'}):null;
  const linhas=inc.map(([n,f])=>`<div class="dr-linha"><span class="dr-chip">${n}</span>
      <span class="dr-linha-t">${esc(drSituacaoTalhao(props.get(n)||{}))} · ${fmtNum(ha(n))} ha</span>
      <span class="dr-seg" role="group" aria-label="Fonte do talhão ${n}">
        <button type="button" aria-pressed="${f==='sistema'}" class="${f==='sistema'?'on':''}" data-foco="f${n}s" onclick="drFonteTalhao(${n},'sistema')">Sistema</button>
        <button type="button" aria-pressed="${f==='shape'}" class="${f==='shape'?'on':''}" data-foco="f${n}h" onclick="drFonteTalhao(${n},'shape')">Shape</button></span></div>`).join('');
  const solta=shape.length?`<button type="button" class="dr-solta" data-foco="solta" onclick="drEnviar('ajuste')" ondragover="event.preventDefault()" ondrop="drSoltar(event,'ajuste')">
      <span class="ico">upload_file</span><span>Arraste o shape de ajuste dos talhões ${shape.join(', ')}</span>
      <small>.shp + .shx + .dbf + .prj, ou .zip</small><small>${esc(drRotuloShape(ev))}</small>${ev&&ev.status==='erro'?`<span class="dr-err">${esc(ev.erro)}</span>`:''}</button>`:'';
  const n=inc.length+rem.length;
  return{sobre:'Nova revisão',titulo:`Normal · Rev${drRevProx('normal')}`,
    corpo:`<div class="dr-cab-ln"><h3>Incluir ou refazer <span>· ${drPlural(inc.length,'talhão','talhões')}</span></h3>${inc.length?`<span>${fmtNum(soma)} ha</span>`:''}</div>
      ${linhas||'<p class="dr-msg-l">Nenhum talhão. Clique no mapa.</p>'}
      ${solta}
      <div class="dr-cab-ln"><h3>Remover <span>· ${rem.length?drPlural(rem.length,'talhão','talhões'):'nenhum'}</span></h3></div>
      ${rem.length?`<div class="dr-chips">${rem.map(t=>`<span class="dr-chip r">${t}</span>`).join('')}</div>`:'<p class="dr-msg-l">Use a ferramenta Remover no mapa.</p>'}
      <div class="dr-nota"><span class="ico">info</span><span>A prévia mostra a fazenda inteira: os talhões de antes e os novos. Você confere antes de publicar.</span></div>`,
    rodape:`<button class="dr-btn" ${n?'':'disabled'} onclick="drGerarNormal()"><span class="ico">play_arrow</span> Gerar prévia</button>`};
}

function drPainel_catacao(){
  const {sol}=drAtual(),env=drUltimoEnvio(DR.info.envios,'infestacao'),card=drCartao(sol);
  const enviado=!!env&&env.status==='ok',processa=!!env&&['fila','processando'].includes(env.status);
  const atual=!sol?1:enviado?3:2,cam=drCamadasEnvio(env);
  const passo1=drPasso(1,atual,'Solicitação aberta',sol
    ?`<small>${esc(card?.solicitante?card.solicitante+' · ':'')}${drQuando(sol.criado_em)}</small>`
    :'<button type="button" class="dr-btn2 dr-passo-bt" onclick="drAbrirCatacao()"><span class="ico">add</span> Abrir Catação desta fazenda</button>');
  const solta=`<button type="button" class="dr-solta" data-foco="solta-inf" onclick="drEnviar('infestacao')" ondragover="event.preventDefault()" ondrop="drSoltar(event,'infestacao')">
      <span class="ico">upload_file</span><span>Arraste as camadas de infestação</span><small>.shp + .shx + .dbf + .prj, ou .zip (várias camadas)</small></button>`;
  let c2;
  if(enviado)c2=`<small>${drPlural(cam.length,'camada','camadas')} · ${drQuando(env.enviado_em)}</small>
      <div class="dr-camadas-l">${cam.map(c=>`<div><span class="ico">description</span>${esc(c)}</div>`).join('')}</div>
      <button type="button" class="dr-linkbtn" onclick="drEnviar('infestacao')">Trocar arquivos</button>`;
  else if(processa)c2='<small>processando…</small>';
  else if(!sol)c2='<small>Abra a Catação primeiro.</small>';
  else c2=(env&&env.status==='erro'?`<div class="dr-err">${esc(env.erro)}</div>`:'')+solta;
  const passo2=drPasso(2,atual,enviado?'Infestação enviada':'Enviar infestação',c2);
  const passo3=drPasso(3,atual,'Gerar prévia','<small>Agrupa as manchas, recorta pelos talhões e tira os obstáculos.</small>');
  return{sobre:'Nova Catação',titulo:`Catação · Rev${drRevProx('catacao')}`,
    corpo:`<p class="dr-msg-l">Um levantamento novo substitui a Catação inteira.</p><ol class="dr-passos">${passo1}${passo2}${passo3}</ol>`,
    rodape:`<button class="dr-btn" ${drPodeGerarCatacao(sol)?'':'disabled'} onclick="drGerarCatacao()"><span class="ico">play_arrow</span> Gerar prévia</button>`};
}

function drPainel_gerando(){
  const {ger}=drAtual(),cat=DR.doc==='catacao',fila=ger.status==='fila';
  DRP.gerando.add(ger.id);                                   // drMostrarPdf abre a prévia sozinha quando ela ficar pronta
  const inc=(ger.escopo?.incluir||[]).map(i=>i.talhao).sort((a,b)=>a-b),rem=[...(ger.escopo?.remover||[])].sort((a,b)=>a-b);
  const cls=fila?['agora','','']:['feito','agora',''];
  const titulos=['Pedido recebido','Processando','Prévia pronta para conferir'];
  const passos=titulos.map((t,k)=>{
    const c=cls[k],ic=c==='agora'?'<span class="ico dr-gira">progress_activity</span>'
      :`<span class="ico">${c==='feito'?'check_circle':'radio_button_unchecked'}</span>`;
    return`<li class="${c}">${ic}${t}</li>`;}).join('');
  return{sobre:`${drNomeDoc(DR.doc)} · Rev${drRevProx(DR.doc)}`,titulo:'Gerando a prévia',
    corpo:`<div class="drp-gerando"><div class="drp-gerando-top"><b>${fila?'Esperando o agente pegar o pedido':'O agente está processando'}</b>
        <span id="dr-decorrido">${esc(drDecorrido(ger.pedido_em,Date.now()))}</span></div>
        <ol class="drp-gerando-passos">${passos}</ol></div>
      ${drLinhaResumo('Incluir ou refazer',cat?'Catação inteira':(inc.join(', ')||'nenhum'))}
      ${drLinhaResumo('Remover',rem.join(', ')||'nenhum')}
      ${drLinhaResumo('Pedido em',drHora(ger.pedido_em))}
      <div class="dr-nota"><span class="ico">notifications</span><span>Pode sair desta tela. Quando a prévia ficar pronta, ela aparece em <b>A analisar</b> e no sininho.</span></div>`,
    rodape:''};
}

function drPainel_previa(){
  const {ger}=drAtual(),doc=DR.doc,x=DR.geo[doc],
    ind=drIndicadoresPrevia(ger.resumo,{area_ha:x?.area_ha,cobertura_pct:DR.geo.cobertura_pct},doc),
    dA=ind.deltaArea,al=ger.alertas||[];
  const areaDelta=dA==null?(x?'':'<em>primeira revisão</em>')
    :`<em class="${dA>=0?'up':'dn'}">${dA>=0?'+ ':'− '}${fmtNum(Math.abs(dA))} ha</em>`;
  const indic=`<div class="drp-indic"><div><small>Área de aplicação</small><b>${ind.area==null?'—':fmtNum(ind.area)+' ha'}</b>${areaDelta}</div>`
    +(doc==='normal'?`<div><small>Cobertura da fazenda</small><b>${ind.cob==null?'—':Math.floor(ind.cob)+'%'}</b>${ind.cobAntes==null?'':`<em>antes ${Math.floor(ind.cobAntes)}%</em>`}</div>`:'')+'</div>';
  const alertas=al.length
    ?`<h3 class="dr-sec">${drPlural(al.length,'alerta','alertas')}</h3>`+al.map(a=>`<div class="drp-alerta"><span class="ico">${/meses/i.test(a)?'history':/fora/i.test(a)?'wrong_location':'warning'}</span><span>${esc(a)}</span></div>`).join('')
    :'<p class="dr-msg-l">Sem alertas.</p>';
  return{sobre:`Prévia · ${drNomeDoc(doc)} Rev${drRevProx(doc)}`,titulo:'Confira antes de publicar',
    corpo:`<button type="button" class="drp-capa" id="dr-pdf" onclick="drPrevAbrir()" title="Abrir a prévia" aria-label="Abrir a prévia"></button>`
      +indic+alertas
      +(ger.publicacao_erro?`<div class="dr-err">Falha ao publicar: ${esc(ger.publicacao_erro)}</div>`:'')
      +`<label class="dr-campo">Motivo da revisão<input class="dr-mot-painel" data-foco="motivo" value="${esc(DRP.motivo[ger.id]||'')}" oninput="DRP.motivo[${ger.id}]=this.value"></label>`,
    rodape:`<div class="dr-rodape-l"><button class="dr-btn2 perigo" onclick="drDescartar(${ger.id})"><span class="ico">undo</span> Descartar</button>
      <button class="dr-btn" onclick="drPublicar(${ger.id})"><span class="ico">publish</span> Publicar no portal</button></div>`};
}

function drPainel_publicando(){
  return{sobre:`${drNomeDoc(DR.doc)} · Rev${drRevProx(DR.doc)}`,titulo:'Publicando no portal',
    corpo:`<div class="dr-nota"><span class="ico dr-gira">progress_activity</span><span>O agente está subindo os arquivos para o portal. Pode sair desta tela.</span></div>`,rodape:''};
}

function drPainel_erro(){
  const {ger}=drAtual();
  return{sobre:`${drNomeDoc(DR.doc)} · Rev${drRevProx(DR.doc)}`,titulo:'Erro na geração',
    corpo:`<div class="dr-erro-caixa">${esc(ger.erro)}</div>`,
    rodape:`<button class="dr-btn2" onclick="drDescartar(${ger.id})"><span class="ico">restart_alt</span> Descartar e montar de novo</button>`};
}

function drPainel_consulta(){
  const {sol,ger}=drAtual(),doc=DR.doc,x=DR.geo[doc],est=drEstadoPainel({doc,sol,ger,edita:true}),ctx=drContextoSol(drCartao(sol));
  const sit={montando:'Sem pedido em andamento',catacao:sol?'Solicitação aberta':'Sem pedido em andamento',gerando:'Gerando prévia…',
    previa:'Prévia pronta, aguardando conferência',publicando:'Publicando…',erro:'A última geração deu erro'}[est];
  return{sobre:'Consulta',titulo:x?`${drNomeDoc(doc)} · Rev${x.revisao} vigente`:`${drNomeDoc(doc)} · sem projeto`,
    corpo:`<p class="dr-sit-l">${esc(sit)}</p>${ctx?`<p class="dr-msg-l">${esc(ctx)}</p>`:''}
      <div class="dr-nota"><span class="ico">visibility</span><span>Somente consulta. Peça acesso de editor ao administrador para alterar.</span></div>`,
    rodape:''};
}

function drPainelLateral(){
  const side=document.getElementById('dr-side-corpo'),aside=document.getElementById('dr-side');if(!side)return;
  const {sol,ger}=drAtual(),doc=DR.doc,est=drEstadoPainel({doc,sol,ger,edita:podeEditar('drone')});
  // Foco (Passo 10): o redesenho põe de volta o elemento marcado com data-foco, com o cursor no mesmo lugar.
  const foco=document.activeElement,dentro=!!aside&&!!foco&&aside.contains(foco),marca=dentro?foco.dataset.foco:null,pos=dentro?foco.selectionStart:null;
  drMapaUi();
  const p=({montando:drPainel_montando,catacao:drPainel_catacao,gerando:drPainel_gerando,previa:drPainel_previa,
    publicando:drPainel_publicando,erro:drPainel_erro,consulta:drPainel_consulta})[est]();
  document.getElementById('dr-side-cab').innerHTML=`<div class="dr-side-sobre">${esc(p.sobre)}</div><h2>${esc(p.titulo)}</h2>`;
  side.innerHTML=p.corpo;
  const rod=document.getElementById('dr-side-rodape'),erro='<div id="dr-err" class="dr-err"></div>';
  if(p.rodape)rod.innerHTML=erro+p.rodape;
  else{rod.innerHTML='';side.insertAdjacentHTML('beforeend',erro);}
  if(marca){
    const el=aside.querySelector(`[data-foco="${marca}"]`);
    if(el){el.focus();if(pos!=null){try{el.setSelectionRange(pos,pos);}catch(_){}}}
  }
  if(est==='previa')drMostrarPdf(ger);
  if(est==='gerando'){if(!DR.tempo)DR.tempo=setInterval(drTempoAtualizar,1000);}
  else drTempoParar();
}

function drErro(e){const el=document.getElementById('dr-err');if(el)el.textContent=e.message||e;}

function drEnviar(tipo){
  const btn=drBotao();                                   // antes do prompt, que apaga window.event
  let classe=null;
  if(tipo==='obstaculos'){
    const r=prompt('Classe dos obstáculos: 15, 25 ou 50 m.\nDeixe vazio para usar o nome de cada arquivo (ex.: restricoes15m).','');
    if(r===null)return;
    classe=drClasseEscolhida(r);
    if(classe===undefined){alert('Classe inválida: use 15, 25 ou 50.');return;}
  }
  const inp=document.createElement('input');inp.type='file';inp.multiple=true;inp.accept='.shp,.shx,.dbf,.prj,.cpg,.zip';
  inp.onchange=()=>{const arqs=[...inp.files];if(arqs.length)drEnviarArquivos(tipo,arqs,classe,btn);};
  inp.click();
}

// Sobe os arquivos e registra o envio. Vem do botão (drEnviar) ou de arrastar para a área do painel (drSoltar).
async function drEnviarArquivos(tipo,arqs,classe,btn){
  drLimparErro();
  const fim=Mo.ocupado(btn);
  // barra de progresso logo abaixo do botão (ou no topo do painel)
  const lugar=document.createElement('div');
  (btn&&btn.isConnected?btn:document.getElementById('dr-side-corpo')?.firstChild)?.after?.(lugar);
  const total=arqs.reduce((s,f)=>s+f.size,0),prog=Mo.progresso(lugar,{total});
  try{
    const pasta=`${DR.cod}/${Date.now()}`,caminhos=[];let feitos=0;
    for(const [k,f] of arqs.entries()){
      const c=`${pasta}/${drNomeSeguro(f.name)}`,rot=`${f.name}${arqs.length>1?` (${k+1} de ${arqs.length})`:''}`;
      prog.atualizar(feitos,'Enviando '+rot);
      await drSubirComProgresso('drone-envios',c,f,b=>prog.atualizar(feitos+Math.min(b,f.size),'Enviando '+rot));
      feitos+=f.size;caminhos.push(c);
    }
    prog.processando('Registrando o envio…');
    const {sol}=drAtual();
    const id=await drRpc('drone_registrar_envio',{p_cod_faz:DR.cod,p_tipo:tipo,p_classe_m:classe,
      p_solicitacao_id:tipo==='infestacao'?sol.id:null,p_arquivos:caminhos});
    if(tipo==='ajuste')DR.ajusteId=id;
    prog.fim(true);await fim(true);
    await drCarregarFazenda();
  }catch(e){prog.fim(false);fim(false);drErro(e);}
}

// sb.storage.upload não informa o progresso; a mesma chamada à API do Storage
// por XMLHttpRequest informa. Sem sobrescrever (igual ao upload padrão).
async function drSubirComProgresso(bucket,caminho,arq,aoProgredir){
  const token=(await sb.auth.getSession()).data.session?.access_token;
  return new Promise((res,rej)=>{
    const x=new XMLHttpRequest();
    x.open('POST',`${SB_URL}/storage/v1/object/${bucket}/${caminho.split('/').map(encodeURIComponent).join('/')}`);
    x.setRequestHeader('Authorization','Bearer '+token);x.setRequestHeader('apikey',SB_KEY);
    x.setRequestHeader('Content-Type',arq.type||'application/octet-stream');x.setRequestHeader('x-upsert','false');
    x.upload.onprogress=e=>{if(e.lengthComputable)aoProgredir(e.loaded);};
    x.onload=()=>{
      if(x.status>=200&&x.status<300)return res();
      let msg='erro '+x.status;try{const c=JSON.parse(x.responseText);msg=c.message||c.error||msg;}catch(_){}
      rej(new Error(`${arq.name}: ${msg}`));
    };
    x.onerror=()=>rej(new Error('Falha de conexão no envio. Confira a internet e tente de novo.'));
    x.send(arq);
  });
}

async function drGerarNormal(){
  drLimparErro();
  const fim=Mo.ocupado(drBotao());
  try{
    const escopo=drEscopo(DR.sel,DR.rem,DR.ajusteId);
    const sol=drAtual().sol?.id||await drRpc('drone_solicitar',{p_cod_faz:DR.cod,p_tipo:'normal',p_data_desejada:null,p_observacao:null});
    await drRpc('drone_pedir_geracao',{p_solicitacao_id:sol,p_escopo:escopo});
    DR.sel=new Map();DR.rem=new Set();
    fim(true);
    await drCarregarFazenda();drCarregarPainel();
  }catch(e){fim(false);drErro(e);}
}

async function drAbrirCatacao(){
  drLimparErro();
  const fim=Mo.ocupado(drBotao());
  try{await drRpc('drone_solicitar',{p_cod_faz:DR.cod,p_tipo:'catacao',p_data_desejada:null,p_observacao:null});
    fim(true);await drCarregarFazenda();drCarregarPainel();}catch(e){fim(false);drErro(e);}
}

async function drGerarCatacao(){
  drLimparErro();
  const fim=Mo.ocupado(drBotao());
  try{await drRpc('drone_pedir_geracao',{p_solicitacao_id:drAtual().sol.id,p_escopo:null});
    fim(true);await drCarregarFazenda();drCarregarPainel();}catch(e){fim(false);drErro(e);}
}

// Depois do pedido, drVooPublicacao (no redesenho) põe o drone para voar até o agente publicar.
async function drPublicar(id){
  drLimparErro();
  const btn=drBotao();
  let fim=()=>{};
  try{
    const mot=DRP.motivo[id]||'';
    if(!await confirmar('Publicar esta revisão no portal de downloads?',{titulo:'Publicar',ok:'Publicar'}))return;
    fim=Mo.ocupado(btn);
    await drRpc('drone_publicar_pedido',{p_geracao_id:id,p_motivo:mot});
    fim(true);
    await drCarregarFazenda();drCarregarPainel();
  }catch(e){fim(false);drErro(e);}
}

async function drDescartar(id){
  drLimparErro();
  const btn=drBotao();
  let fim=()=>{};
  try{
    if(!await confirmar('Descartar esta prévia?',{titulo:'Descartar',ok:'Descartar',perigo:true}))return;
    fim=Mo.ocupado(btn);
    await drRpc('drone_descartar',{p_geracao_id:id});
    fim(true);
    await drCarregarFazenda();drCarregarPainel();
  }catch(e){fim(false);drErro(e);}
}
async function drObstaculos(ligar){
  DR.mostrarObst=ligar;
  const m=DR.mapa;if(!m||!m.getSource('tal'))return;         // mapa ainda carregando: o 'load' chama de novo
  const tirar=()=>{for(const id of ['obs-buf','obs-buf-l','obs-lin','obs-pt'])if(m.getLayer(id))m.removeLayer(id);
    if(m.getSource('obs'))m.removeSource('obs');};
  tirar();
  if(!ligar)return;
  try{if(!DR.obstGeo)DR.obstGeo=await drRpc('drone_obstaculos_mapa',{p_cod_faz:DR.cod});}
  catch(e){drErro(e);return;}
  if(DR.mapa!==m||!DR.mostrarObst)return;                    // fazenda mudou ou desligaram durante o await
  tirar();                                                   // outra chamada pode ter adicionado no meio
  const cor=['match',['get','classe'],15,DR_OBS_COR[15],25,DR_OBS_COR[25],DR_OBS_COR[50]];
  m.addSource('obs',{type:'geojson',data:DR.obstGeo});
  m.addLayer({id:'obs-buf',type:'fill',source:'obs',filter:['==',['get','camada'],'buffer'],paint:{'fill-color':cor,'fill-opacity':0}});
  m.addLayer({id:'obs-buf-l',type:'line',source:'obs',filter:['==',['get','camada'],'buffer'],paint:{'line-color':cor,'line-width':1,'line-dasharray':[2,2],'line-opacity':0}});
  m.addLayer({id:'obs-lin',type:'line',source:'obs',filter:['all',['==',['get','camada'],'obst'],['!=',['geometry-type'],'Point']],paint:{'line-color':cor,'line-width':2,'line-opacity':0}});
  m.addLayer({id:'obs-pt',type:'circle',source:'obs',filter:['all',['==',['get','camada'],'obst'],['==',['geometry-type'],'Point']],paint:{'circle-color':cor,'circle-radius':3,'circle-opacity':0}});
  drFadeCamada('obs-buf','fill-opacity',.15);drFadeCamada('obs-buf-l','line-opacity',1);
  drFadeCamada('obs-lin','line-opacity',1);drFadeCamada('obs-pt','circle-opacity',1);
}
