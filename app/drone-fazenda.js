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
      sb.from('drone_solicitacoes').select('id,tipo,status,observacao,solicitante_id').eq('cod_faz',cod).neq('origem','legado').not('status','in','(ok,cancelado)'),
      sb.from('drone_obstaculo_versoes').select('classe_m,versao,enviado_em').eq('cod_faz',cod).eq('vigente',true)]);
    if(!drRespostaValida(minha,chave()))return;
    const sIds=(sols.data||[]).map(s=>s.id);
    const ger=sIds.length?await sb.from('drone_geracoes').select('id,solicitacao_id,status,alertas,erro,previa_pdf,publicar_pedido_em,publicacao_erro,resumo,escopo')
      .in('solicitacao_id',sIds).neq('status','descartada').neq('status','publicada').order('id',{ascending:false}):{data:[]};
    if(!drRespostaValida(minha,chave()))return;
    const env=await sb.from('drone_envios').select('id,tipo,status,erro,enviado_em').eq('cod_faz',cod).order('id',{ascending:false}).limit(5);
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
  if(!DR.mapa||!document.getElementById('dr-map')){drMapaDescartar();drEsqueleto();drMapaCriar();drPainelLateral();}
  else{
    if(tem('cab'))document.getElementById('dr-ph').outerHTML=drCabecalhoHtml();
    if(tem('mapa'))drMapaAtualizar();
    if(tem('obst')&&DR.mostrarObst)drObstaculos(true);
    if(tem('painel')){drPainelLateral();drAtualizarSelecaoMapa();}   // o estado 'ger' dos talhões segue a geração
  }
  drVooPublicacao();drAnimGeracao();
}
function drEsqueleto(){
  document.getElementById('dr-faz').innerHTML=drCabecalhoHtml()+`
    <div class="dr-body"><div><div class="dr-map" id="dr-map"></div>
      <div class="dr-leg"><span><i id="dr-leg-apl" style="background:${DR_COR[DR.doc]}"></i>área de aplicação vigente</span>
        <span><i style="background:${DR_COR.sem}"></i>sem projeto</span><span><i style="background:#fff;border-color:${DR_COR.fora}"></i>fora da Base</span>
        <span><i style="background:#d9defc;border-color:${DR_COR.sel}"></i>selecionado</span><span><i style="background:#fbe0e0;border-color:${DR_COR.rem}"></i>remover</span>
        <label style="margin-left:auto;cursor:pointer"><input type="checkbox" ${DR.mostrarObst?'checked':''} onchange="drObstaculos(this.checked)"> mostrar obstáculos</label></div></div>
      <div class="dr-side" id="dr-side"></div></div>`;
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
  DR.varr&&DR.varr.parar();DR.varr=null;
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
  const pct=g.cobertura_pct;
  const card=(doc,tit,x,extra)=>`<div class="dr-doc${DR.doc===doc?' on':''}" onclick="drTrocarDoc('${doc}')">
    <b>${tit} · ${x?'Rev'+x.revisao:'sem projeto'}</b>${extra}<small>${x?fmtNum(x.area_ha)+' ha · '+new Date(x.em).toLocaleDateString('pt-BR'):'—'}</small></div>`;
  return`<div class="dr-ph" id="dr-ph"><span class="dr-cod" style="font-size:13px">${DR.cod}</span>
      <div><div class="nm">${esc(i.faz.nome)}</div><div class="sub">${tal.length} talhões · ${fmtNum(area)} ha</div></div>
      <div class="dr-docs">${card('normal','Normal',g.normal,pct!=null&&pct<100?`<span class="dr-tag">${Math.floor(pct)}% DA FAZENDA</span>`:'')}
        ${card('catacao','Catação',g.catacao,'')}</div></div>`;
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
      ['==',['get','status'],'fora_da_base'],DR_COR.fora,'#1f2a30'],
      'line-width':['case',['any',['boolean',['feature-state','sel'],false],['boolean',['feature-state','rem'],false],
        ['boolean',['feature-state','ger'],false],['==',['get','status'],'fora_da_base']],2,0.6],
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
  const gerando=new Set(drTalhoesGerando(drAtual().ger));
  DR.geo.features.filter(f=>f.properties.camada==='talhao').forEach(f=>{
    const n=f.properties.talhao;
    m.setFeatureState({source:'tal',id:n},{sel:DR.sel.has(n),rem:DR.rem.has(n),ger:gerando.has(n)});
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
    DR.sel.has(n)?DR.sel.delete(n):(DR.sel.set(n,DR.fonte||'sistema'),DR.rem.delete(n));
  }
  drAtualizarSelecaoMapa();drPainelLateral();
}

function drSelecionarSemProjeto(){
  DR.geo.features.filter(f=>f.properties.camada==='talhao'&&f.properties.status==='sem_projeto')
    .forEach(f=>{DR.sel.set(f.properties.talhao,DR.fonte||'sistema');DR.rem.delete(f.properties.talhao);});
  drAtualizarSelecaoMapa();drPainelLateral();
}

function drFonte(f){DR.fonte=f;for(const k of DR.sel.keys())DR.sel.set(k,f);drPainelLateral();}

function drObstaculosHtml(){
  const linhas=[15,25,50].map(c=>{const v=DR.info.obst.find(o=>o.classe_m===c);
    return`<div class="dr-row"><span>${c} m</span><span>${v?'v'+v.versao+' · '+new Date(v.enviado_em).toLocaleDateString('pt-BR'):'sem cadastro'}</span></div>`;}).join('');
  const ult=drUltimoEnvio(DR.info.envios,'obstaculos');
  const env=ult&&['fila','processando'].includes(ult.status)?ult:null;
  const err=ult&&ult.status==='erro'?ult:null;
  return`<div class="dr-box"><h3><span class="ico">warning</span> Obstáculos</h3>${linhas}
    ${env?`<div class="dr-msg">processando envio…</div>`:''}${err?`<div class="dr-err">Último envio: ${esc(err.erro)}</div>`:''}
    ${podeEditar('drone')?`<button class="dr-btn2" style="margin-top:6px" onclick="drEnviar('obstaculos')"><span class="ico">upload</span> Enviar obstáculos</button>`:''}</div>`;
}

function drPainelLateral(){
  const side=document.getElementById('dr-side');if(!side)return;
  const {sol,ger}=drAtual(),edita=podeEditar('drone');
  let h='';
  if(ger){h+=drPrevHtml(ger);}
  else if(DR.doc==='normal'&&edita){
    const prox=DR.geo.normal?DR.geo.normal.revisao+1:0;
    const inc=[...DR.sel.keys()].sort((a,b)=>a-b),rem=[...DR.rem].sort((a,b)=>a-b);
    const shape=[...DR.sel.values()].includes('shape');
    h+=`<div class="dr-box"><h3><span class="ico" style="color:var(--drones)">edit_note</span> Nova revisão · Normal Rev${prox}</h3>
      <div class="dr-msg" style="text-align:left">Clique nos talhões do mapa</div>
      <div class="dr-seg"><button class="${DR.modoRemover?'':'on'}" onclick="DR.modoRemover=false;drPainelLateral()">Incluir / refazer</button>
        <button class="${DR.modoRemover?'on':''}" onclick="DR.modoRemover=true;drPainelLateral()">Remover</button></div>
      <button class="dr-btn2" onclick="drSelecionarSemProjeto()">Selecionar todos sem projeto</button>
      <div style="font-weight:600;margin-top:8px">Incluir / refazer (${inc.length})</div>
      <div class="dr-chips">${inc.map(n=>`<span class="dr-chip">${n}</span>`).join('')||'<span class="dr-msg">nenhum</span>'}</div>
      <div class="dr-seg"><button class="${shape?'':'on'}" onclick="drFonte('sistema')">Sistema gera</button>
        <button class="${shape?'on':''}" onclick="drFonte('shape')">Subir shape</button></div>
      ${shape?(()=>{const ev=DR.ajusteId?DR.info.envios.find(e=>e.id===DR.ajusteId)||{status:'fila'}:null;
        return`<button class="dr-btn2" onclick="drEnviar('ajuste')"><span class="ico">upload</span> ${drRotuloShape(ev)}</button>`
          +(ev&&ev.status==='erro'?`<div class="dr-err">${esc(ev.erro)}</div>`:'');})():''}
      <div style="font-weight:600;margin-top:8px">Remover (${rem.length})</div>
      <div class="dr-chips">${rem.map(n=>`<span class="dr-chip r">${n}</span>`).join('')||'<span class="dr-msg">nenhum</span>'}</div></div>
      ${drObstaculosHtml()}
      <button class="dr-btn" ${inc.length||rem.length?'':'disabled'} onclick="drGerarNormal()"><span class="ico">play_arrow</span> Gerar prévia</button>
      <div class="dr-msg">A prévia mostra a fazenda inteira (talhões de antes + os novos). Você confere e publica.</div>`;
  }else if(DR.doc==='catacao'&&edita){
    h+=`<div class="dr-box"><h3><span class="ico" style="color:#5b8c5a">grass</span> Catação</h3>
      ${sol?`<div class="dr-row"><span>Solicitação</span><span>${esc(DR_ST[sol.status]||sol.status)}</span></div>
        <button class="dr-btn2" style="margin-top:6px" onclick="drEnviar('infestacao')"><span class="ico">upload</span> Enviar infestação (várias camadas)</button>`
      :`<button class="dr-btn2" onclick="drAbrirCatacao()"><span class="ico">add</span> Abrir Catação desta fazenda</button>`}
      <div class="dr-msg" style="margin-top:6px">Um levantamento novo substitui a Catação inteira.</div></div>
      ${drObstaculosHtml()}
      <button class="dr-btn" ${drPodeGerarCatacao(sol)?'':'disabled'} onclick="drGerarCatacao()"><span class="ico">play_arrow</span> Gerar prévia</button>`;
  }else{
    h+=drObstaculosHtml()+`<div class="dr-msg">Somente consulta.</div>`;
  }
  const hist=(DR.info.revs||[]).filter(r=>r.documento===DR.doc).map(r=>
    `<div class="dr-row"><span>Rev${r.numero} · ${new Date(r.criado_em).toLocaleDateString('pt-BR')}</span><span>${esc((r.motivo||'').slice(0,40))}</span></div>`).join('');
  h+=`<div class="dr-box"><h3><span class="ico">history</span> Histórico</h3>${hist||'<div class="dr-msg">sem revisões</div>'}</div>`;
  if(sol&&drPodeCancelar(sol,ger,EU))
    h+=`<button class="dr-btn2" style="color:#c23b3b" onclick="drCancelar(${sol.id})"><span class="ico">cancel</span> Cancelar solicitação</button>`;
  h+=`<div id="dr-err" class="dr-err"></div>`;
  side.innerHTML=h;
  if(ger&&ger.status==='pronta'&&!(ger.publicar_pedido_em&&!ger.publicacao_erro))drMostrarPdf(ger);
}

function drErro(e){const el=document.getElementById('dr-err');if(el)el.textContent=e.message||e;}

function drEnviar(tipo){
  let classe=null;
  if(tipo==='obstaculos'){
    const r=prompt('Classe dos obstáculos: 15, 25 ou 50 m.\nDeixe vazio para usar o nome de cada arquivo (ex.: restricoes15m).','');
    if(r===null)return;
    classe=drClasseEscolhida(r);
    if(classe===undefined){alert('Classe inválida: use 15, 25 ou 50.');return;}
  }
  const inp=document.createElement('input');inp.type='file';inp.multiple=true;inp.accept='.shp,.shx,.dbf,.prj,.cpg,.zip';
  const btn=drBotao();
  inp.onchange=async()=>{
    const arqs=[...inp.files];if(!arqs.length)return;
    const fim=Mo.ocupado(btn);
    // barra de progresso logo abaixo do botão (ou no topo do painel)
    const lugar=document.createElement('div');
    (btn&&btn.isConnected?btn:document.getElementById('dr-side')?.firstChild)?.after?.(lugar);
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
  };
  inp.click();
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
  const fim=Mo.ocupado(drBotao());
  try{
    if([...DR.sel.values()].includes('shape')&&!DR.ajusteId)throw new Error('Envie o shape de ajuste antes de gerar.');
    const escopo={incluir:[...DR.sel].map(([t,f])=>f==='shape'?{talhao:t,fonte:'shape',envio_id:DR.ajusteId}:{talhao:t,fonte:'sistema'}),
      remover:[...DR.rem]};
    const sol=drAtual().sol?.id||await drRpc('drone_solicitar',{p_cod_faz:DR.cod,p_tipo:'normal',p_data_desejada:null,p_observacao:null});
    await drRpc('drone_pedir_geracao',{p_solicitacao_id:sol,p_escopo:escopo});
    DR.sel=new Map();DR.rem=new Set();
    fim(true);
    await drCarregarFazenda();drCarregarPainel();
  }catch(e){fim(false);drErro(e);}
}

async function drAbrirCatacao(){
  const fim=Mo.ocupado(drBotao());
  try{await drRpc('drone_solicitar',{p_cod_faz:DR.cod,p_tipo:'catacao',p_data_desejada:null,p_observacao:null});
    fim(true);await drCarregarFazenda();drCarregarPainel();}catch(e){fim(false);drErro(e);}
}

async function drGerarCatacao(){
  const fim=Mo.ocupado(drBotao());
  try{await drRpc('drone_pedir_geracao',{p_solicitacao_id:drAtual().sol.id,p_escopo:null});
    fim(true);await drCarregarFazenda();drCarregarPainel();}catch(e){fim(false);drErro(e);}
}

// Depois do pedido, drVooPublicacao (no redesenho) põe o drone para voar até o agente publicar.
async function drPublicar(id){
  const btn=drBotao();
  let fim=()=>{};
  try{
    const mot=document.getElementById('dr-mot').value;
    if(!await confirmar('Publicar esta revisão no portal de downloads?',{titulo:'Publicar',ok:'Publicar'}))return;
    fim=Mo.ocupado(btn);
    await drRpc('drone_publicar_pedido',{p_geracao_id:id,p_motivo:mot});
    fim(true);
    await drCarregarFazenda();drCarregarPainel();
  }catch(e){fim(false);drErro(e);}
}

async function drDescartar(id){
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
