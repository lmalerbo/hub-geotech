// Tela do Drone (spec Parte 2, §5): fila de trabalho + fazenda com mapa por talhão.
const DR={painel:null,cod:null,geo:null,mapa:null,sel:new Map(),rem:new Set(),modoRemover:false,
  doc:'normal',ajusteId:null,poll:null,info:null};
const DR_ST={aguardando_obstaculos:'aguardando obstáculos',aguardando_infestacao:'aguardando infestação',
  solicitado:'solicitado',em_elaboracao:'em elaboração',devolvido:'devolvido'};
const DR_COR={normal:'#a0694b',catacao:'#5b8c5a',sel:'#5b6ee8',rem:'#c23b3b',sem:'#e9ebef',fora:'#d4890a'};

function drEstilo(){
  if(document.getElementById('drone-css'))return;
  const s=document.createElement('style');s.id='drone-css';
  s.textContent=`
#drone-root{display:grid;grid-template-columns:330px 1fr;gap:16px}
.dr-grp{background:var(--sf);border-radius:14px;padding:10px;margin-bottom:12px;box-shadow:0 1px 3px #0000000d}
.dr-gh{display:flex;justify-content:space-between;align-items:center;font-weight:600;font-size:13px;padding:2px 4px 8px}
.dr-n{background:var(--s2);border-radius:20px;padding:1px 9px;font-size:12px}
.dr-it{display:flex;gap:10px;align-items:center;padding:8px;border-radius:10px;cursor:pointer;font-size:13px}
.dr-it:hover,.dr-it.on{background:#eef0fd}.dr-it.on{outline:1.5px solid var(--drones)}
.dr-it small{display:block;color:var(--t3);font-size:11px}.dr-it .r{margin-left:auto;font-size:11px;color:var(--t3);text-align:right}
.dr-cod{background:#eef0fd;color:var(--drones);font-weight:700;font-size:11px;border-radius:6px;padding:2px 6px}
.dr-pnl{background:var(--sf);border-radius:16px;box-shadow:0 1px 3px #0000000d;overflow:hidden;min-height:560px}
.dr-ph{display:flex;align-items:center;gap:12px;padding:16px 20px;border-bottom:1px solid var(--bd);flex-wrap:wrap}
.dr-ph .nm{font-size:17px;font-weight:600}.dr-ph .sub{color:var(--t3);font-size:12px}
.dr-docs{display:flex;gap:10px;margin-left:auto}
.dr-doc{border:1px solid var(--bd);border-radius:12px;padding:8px 12px;min-width:170px;cursor:pointer;font-size:12px}
.dr-doc.on{border-color:var(--drones);background:#f6f7fe}.dr-doc small{display:block;color:var(--t3);font-size:11px}
.dr-tag{display:inline-block;font-size:10px;font-weight:700;border-radius:6px;padding:1px 6px;margin-left:4px;background:#fdf1df;color:#d4890a}
.dr-body{display:grid;grid-template-columns:1fr 310px}
.dr-map{height:560px;border-right:1px solid var(--bd)}
.dr-leg{display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--t2);padding:8px 12px}
.dr-leg i{display:inline-block;width:12px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px;border:1px solid #1f2a30}
.dr-side{padding:14px 16px;display:flex;flex-direction:column;gap:12px;font-size:12px}
.dr-box{border:1px solid var(--bd);border-radius:12px;padding:10px 12px}
.dr-box h3{font-size:12px;font-weight:600;margin-bottom:6px}
.dr-row{display:flex;justify-content:space-between;padding:2px 0}.dr-row span:last-child{color:var(--t3)}
.dr-chips{display:flex;flex-wrap:wrap;gap:4px;margin:4px 0}
.dr-chip{font-size:11px;border-radius:6px;padding:1px 7px;background:#eef0fd;color:var(--drones);font-weight:600}
.dr-chip.r{background:#fbe0e0;color:#c23b3b}
.dr-seg{display:flex;background:var(--s2);border-radius:9px;padding:3px;gap:3px;margin:6px 0}
.dr-seg button{flex:1;border:0;background:none;padding:5px;border-radius:7px;font:inherit;font-size:11.5px;color:var(--t2);cursor:pointer}
.dr-seg button.on{background:#fff;color:var(--drones);font-weight:600;box-shadow:0 1px 2px #0002}
.dr-btn{background:var(--drones);color:#fff;border:0;border-radius:10px;padding:10px;font:inherit;font-weight:600;cursor:pointer;width:100%}
.dr-btn:disabled{opacity:.5;cursor:default}
.dr-btn2{border:1px solid var(--bd);background:#fff;border-radius:10px;padding:8px;font:inherit;color:var(--t2);cursor:pointer;width:100%}
.dr-msg{font-size:11px;color:var(--t3);text-align:center}.dr-err{color:#c23b3b;font-size:12px}
.dr-mot{width:100%;border:1px solid var(--bd);border-radius:8px;padding:7px;font:inherit;font-size:12px}
.dr-prev iframe{width:100%;height:420px;border:1px solid var(--bd);border-radius:10px}
.dr-modal-fundo{position:fixed;inset:0;background:#0006;display:flex;align-items:center;justify-content:center;z-index:50}
.dr-modal{background:var(--sf);border-radius:16px;padding:18px 20px;width:420px;max-width:92vw;font-size:13px}
.dr-modal h3{font-size:15px;margin-bottom:10px}.dr-modal label{display:block;font-size:12px;color:var(--t2);margin-top:10px}
.dr-modal input,.dr-modal textarea{width:100%;border:1px solid var(--bd);border-radius:8px;padding:7px;font:inherit;margin-top:4px}
.dr-vazio{display:flex;align-items:center;justify-content:center;height:560px;color:var(--t3)}`;
  document.head.appendChild(s);
}

async function droneIniciar(){
  drEstilo();
  const root=document.getElementById('drone-root');
  if(!root.dataset.pronto){
    root.innerHTML=`<div><div class="search-wrap"><span class="ico search-ico">search</span>
      <input class="search-inp" id="dr-busca" placeholder="Buscar fazenda ou código…" oninput="drBuscar(this.value)"></div>
      <div id="dr-busca-res"></div><div id="dr-fila"></div></div>
      <div class="dr-pnl" id="dr-faz"><div class="dr-vazio">Escolha um item da fila ou busque uma fazenda</div></div>`;
    root.dataset.pronto='1';
  }
  await drCarregarPainel();
}

async function drRpc(nome,args){
  const {data,error}=await sb.rpc(nome,args||{});
  if(error)throw new Error(error.message);
  return data;
}

async function drCarregarPainel(){
  try{DR.painel=await drRpc('drone_painel');}
  catch(e){document.getElementById('dr-fila').innerHTML=`<div class="dr-err">${esc(e.message)}</div>`;return;}
  const s=DR.painel.solicitacoes||[];
  const it=x=>{
    const g=x.geracao||{};
    const st=g.status==='pronta'?(g.publicar_pedido_em?'publicando…':`prévia pronta · ${g.alertas} alertas`)
      :g.status==='fila'||g.status==='processando'?'gerando…':g.status==='erro'?'erro na geração':DR_ST[x.status]||x.status;
    return`<div class="dr-it${DR.cod===x.cod_faz?' on':''}" onclick="drAbrirFazenda(${x.cod_faz},'${x.tipo}')">
      <span class="dr-cod">${x.cod_faz}</span><div>${esc(x.fazenda)}<small>${esc(x.observacao||st)}${x.solicitante?' · '+esc(x.solicitante):''}</small></div>
      <div class="r">${x.data_desejada?'para '+new Date(x.data_desejada+'T12:00').toLocaleDateString('pt-BR'):''}<br>${esc(st)}</div></div>`;
  };
  const grupo=(tit,lista,vazio)=>`<div class="dr-grp"><div class="dr-gh">${tit}<span class="dr-n">${lista.length}</span></div>
    ${lista.length?lista.map(it).join(''):`<div class="dr-msg">${vazio}</div>`}</div>`;
  const normal=s.filter(x=>x.tipo==='normal'&&!(x.geracao&&x.geracao.status==='pronta'));
  const cat=s.filter(x=>x.tipo==='catacao'&&!(x.geracao&&x.geracao.status==='pronta'));
  const prev=s.filter(x=>x.geracao&&x.geracao.status==='pronta');
  const inc=DR.painel.incompletas||[],obs=DR.painel.obstaculos_antigos||[],fora=DR.painel.fora_da_base||[];
  const nova=(podeEditar('drone')||(EU&&EU.role==='solicitante'&&EU.perms.drone))
    ?`<button class="dr-btn2" style="margin-bottom:12px" onclick="drNovaSolicitacao()"><span class="ico">add</span> Nova solicitação</button>`:'';
  const ajuda=`<a class="dr-msg" style="display:block;text-align:right;margin:-4px 0 8px" target="_blank" rel="noreferrer"
    href="https://github.com/lmalerbo/hub-geotech/blob/main/docs/drone-manual.md"><span class="ico" style="font-size:15px">help</span> Ajuda</a>`;
  document.getElementById('dr-fila').innerHTML=ajuda+nova
    +grupo('Solicitações Normal',normal,'nenhuma')
    +grupo('Catação · aguardando',cat,'nenhuma')
    +grupo('Prévias para conferir',prev,'nenhuma')
    +`<div class="dr-grp"><div class="dr-gh">Atenção<span class="dr-n">${inc.length+obs.length+fora.length}</span></div>
      <div class="dr-it" onclick="drListarAtencao('incompletas')"><span class="ico" style="color:#d4890a">incomplete_circle</span><div>Normais incompletas<small>${inc.length} fazendas com talhões sem projeto</small></div></div>
      <div class="dr-it" onclick="drListarAtencao('obstaculos_antigos')"><span class="ico" style="color:#d4890a">history</span><div>Obstáculos com mais de 24 meses<small>${obs.length} fazendas</small></div></div>
      <div class="dr-it" onclick="drListarAtencao('fora_da_base')"><span class="ico" style="color:#d4890a">wrong_location</span><div>Talhões fora da Base<small>${fora.length} fazendas</small></div></div></div>`;
}

function drListarAtencao(chave){
  const l=DR.painel[chave]||[];
  const linhas=l.map(x=>typeof x==='object'
    ?`<div class="dr-it" onclick="drAbrirFazenda(${x.cod_faz})"><span class="dr-cod">${x.cod_faz}</span><div>${esc(x.fazenda)}</div><div class="r">${x.pct}%</div></div>`
    :`<div class="dr-it" onclick="drAbrirFazenda(${x})"><span class="dr-cod">${x}</span></div>`).join('');
  document.getElementById('dr-busca-res').innerHTML=`<div class="dr-grp"><div class="dr-gh">Atenção<button class="dr-btn2" style="width:auto;padding:2px 8px" onclick="document.getElementById('dr-busca-res').innerHTML=''">fechar</button></div>${linhas||'<div class="dr-msg">nenhuma</div>'}</div>`;
}

async function drBuscar(txt){
  const alvo=document.getElementById('dr-busca-res');
  txt=(txt||'').trim();
  if(txt.length<2){alvo.innerHTML='';return;}
  const q=/^\d+$/.test(txt)?sb.from('fazendas').select('cod_faz,nome').eq('cod_faz',Number(txt))
    :sb.from('fazendas').select('cod_faz,nome').ilike('nome',`%${txt}%`).limit(12);
  const {data}=await q;
  alvo.innerHTML=`<div class="dr-grp">${(data||[]).map(f=>`<div class="dr-it" onclick="drAbrirFazenda(${f.cod_faz})"><span class="dr-cod">${f.cod_faz}</span><div>${esc(f.nome)}</div></div>`).join('')||'<div class="dr-msg">nenhuma fazenda</div>'}</div>`;
}

async function drAbrirFazenda(cod,doc){
  DR.cod=cod;DR.doc=doc||'normal';DR.obstGeo=null;DR.sel=new Map();DR.rem=new Set();DR.modoRemover=false;DR.ajusteId=null;
  clearTimeout(DR.poll);
  document.querySelectorAll('#dr-fila .dr-it').forEach(e=>e.classList.toggle('on',e.getAttribute('onclick')?.includes(`(${cod},`)));
  await drRecarregarFazenda();
}

async function drRecarregarFazenda(){
  const cod=DR.cod;
  try{
    const [geo,faz,sols,obst]=await Promise.all([
      drRpc('drone_mapa_fazenda',{p_cod_faz:cod}),
      sb.from('fazendas').select('cod_faz,nome').eq('cod_faz',cod).single(),
      sb.from('drone_solicitacoes').select('id,tipo,status,observacao').eq('cod_faz',cod).neq('origem','legado').not('status','in','(ok,cancelado)'),
      sb.from('drone_obstaculo_versoes').select('classe_m,versao,enviado_em').eq('cod_faz',cod).eq('vigente',true)]);
    const sIds=(sols.data||[]).map(s=>s.id);
    const ger=sIds.length?await sb.from('drone_geracoes').select('id,solicitacao_id,status,alertas,erro,previa_pdf,publicar_pedido_em,publicacao_erro,resumo')
      .in('solicitacao_id',sIds).neq('status','descartada').neq('status','publicada').order('id',{ascending:false}):{data:[]};
    const env=await sb.from('drone_envios').select('id,tipo,status,erro,enviado_em').eq('cod_faz',cod).order('id',{ascending:false}).limit(5);
    const proj=await sb.from('projetos').select('id').eq('modulo_id','drone').eq('tipo','individual').eq('cod_faz',cod);
    const revs=proj.data&&proj.data.length?await sb.from('projeto_revisoes').select('numero,documento,motivo,criado_em')
      .eq('projeto_id',proj.data[0].id).order('numero',{ascending:false}):{data:[]};
    DR.geo=geo;DR.info={faz:faz.data,sols:sols.data||[],obst:obst.data||[],ger:ger.data||[],envios:env.data||[],revs:revs.data||[]};
  }catch(e){document.getElementById('dr-faz').innerHTML=`<div class="dr-vazio dr-err">${esc(e.message)}</div>`;return;}
  drRender();
}

function drRender(){
  const g=DR.geo,i=DR.info,tal=g.features.filter(f=>f.properties.camada==='talhao');
  const area=tal.filter(f=>f.properties.status!=='fora_da_base').reduce((s,f)=>s+(f.properties.area_ha||0),0);
  const pct=g.cobertura_pct;
  const card=(doc,tit,x,extra)=>`<div class="dr-doc${DR.doc===doc?' on':''}" onclick="DR.doc='${doc}';DR.sel=new Map();DR.rem=new Set();drRender()">
    <b>${tit} · ${x?'Rev'+x.revisao:'sem projeto'}</b>${extra}<small>${x?fmtNum(x.area_ha)+' ha · '+new Date(x.em).toLocaleDateString('pt-BR'):'—'}</small></div>`;
  document.getElementById('dr-faz').innerHTML=`
    <div class="dr-ph"><span class="dr-cod" style="font-size:13px">${DR.cod}</span>
      <div><div class="nm">${esc(i.faz.nome)}</div><div class="sub">${tal.length} talhões · ${fmtNum(area)} ha</div></div>
      <div class="dr-docs">${card('normal','Normal',g.normal,pct!=null&&pct<100?`<span class="dr-tag">${Math.round(pct)}% DA FAZENDA</span>`:'')}
        ${card('catacao','Catação',g.catacao,'')}</div></div>
    <div class="dr-body"><div><div class="dr-map" id="dr-map"></div>
      <div class="dr-leg"><span><i style="background:${DR_COR[DR.doc]}"></i>área de aplicação vigente</span>
        <span><i style="background:${DR_COR.sem}"></i>sem projeto</span><span><i style="background:#fff;border-color:${DR_COR.fora}"></i>fora da Base</span>
        <span><i style="background:#d9defc;border-color:${DR_COR.sel}"></i>selecionado</span><span><i style="background:#fbe0e0;border-color:${DR_COR.rem}"></i>remover</span>
        <label style="margin-left:auto;cursor:pointer"><input type="checkbox" ${DR.mostrarObst?'checked':''} onchange="drObstaculos(this.checked)"> mostrar obstáculos</label></div></div>
      <div class="dr-side" id="dr-side"></div></div>`;
  drPintarMapa();
  drPainelLateral();
}

function drPintarMapa(){
  const fc={type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada==='talhao')};
  const apl={type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada===DR.doc)};
  if(DR.mapa){DR.mapa.remove();DR.mapa=null;}
  const m=new maplibregl.Map({container:'dr-map',attributionControl:false,
    style:{version:8,glyphs:'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',sources:{},
      layers:[{id:'fundo',type:'background',paint:{'background-color':'#f7f8fa'}}]}});
  DR.mapa=m;
  m.addControl(new maplibregl.NavigationControl({showCompass:false}),'top-right');
  m.on('load',()=>{
    m.addSource('tal',{type:'geojson',data:fc,promoteId:'talhao'});
    m.addSource('apl',{type:'geojson',data:apl});
    m.addLayer({id:'tal-f',type:'fill',source:'tal',paint:{'fill-color':['case',
      ['boolean',['feature-state','rem'],false],'#fbe0e0',['boolean',['feature-state','sel'],false],'#d9defc',
      ['==',['get','status'],'sem_projeto'],DR_COR.sem,'#ffffff']}});
    m.addLayer({id:'apl-f',type:'fill',source:'apl',paint:{'fill-color':DR_COR[DR.doc],'fill-opacity':.75}});
    m.addLayer({id:'tal-l',type:'line',source:'tal',paint:{'line-color':['case',
      ['boolean',['feature-state','rem'],false],DR_COR.rem,['boolean',['feature-state','sel'],false],DR_COR.sel,
      ['==',['get','status'],'fora_da_base'],DR_COR.fora,'#1f2a30'],
      'line-width':['case',['any',['boolean',['feature-state','sel'],false],['boolean',['feature-state','rem'],false],
        ['==',['get','status'],'fora_da_base']],2,0.6]}});
    m.addLayer({id:'tal-t',type:'symbol',source:'tal',layout:{'text-field':['to-string',['get','talhao']],
      'text-font':['Open Sans Semibold'],'text-size':11},paint:{'text-color':'#1f2a30','text-halo-color':'#fff','text-halo-width':1.5}});
    const b=new maplibregl.LngLatBounds();
    fc.features.forEach(f=>(f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates)
      .forEach(p=>p[0].forEach(c=>b.extend(c))));
    if(!b.isEmpty())m.fitBounds(b,{padding:30,duration:0});
    drAtualizarSelecaoMapa();
    if(DR.mostrarObst)drObstaculos(true);
    m.on('click','tal-f',e=>drClicarTalhao(e.features[0].properties));
    m.on('mouseenter','tal-f',()=>m.getCanvas().style.cursor='pointer');
    m.on('mouseleave','tal-f',()=>m.getCanvas().style.cursor='');
  });
}

function drAtualizarSelecaoMapa(){
  const m=DR.mapa;if(!m||!m.getSource('tal'))return;
  DR.geo.features.filter(f=>f.properties.camada==='talhao').forEach(f=>{
    const n=f.properties.talhao;
    m.setFeatureState({source:'tal',id:n},{sel:DR.sel.has(n),rem:DR.rem.has(n)});
  });
}

function drPodeGerarCatacao(sol){return !!sol&&['solicitado','em_elaboracao'].includes(sol.status);}
function drNomeSeguro(nome){
  return String(nome).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Za-z0-9._-]/g,'_').replace(/\.\./g,'__');
}
function drClasseEscolhida(txt){
  const t=String(txt??'').replace(/m/gi,'').trim();
  if(!t)return null;                                   // vazio: classe pelo nome do arquivo
  const n=Number(t);return [15,25,50].includes(n)?n:undefined;
}

function drAtual(){
  const tipo=DR.doc;
  const sol=DR.info.sols.find(s=>s.tipo===tipo)||null;
  const ger=sol?DR.info.ger.find(g=>g.solicitacao_id===sol.id)||null:null;
  return{sol,ger};
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
  const env=DR.info.envios.find(e=>e.status==='fila'||e.status==='processando');
  const err=DR.info.envios.find(e=>e.status==='erro');
  return`<div class="dr-box"><h3><span class="ico">warning</span> Obstáculos</h3>${linhas}
    ${env?`<div class="dr-msg">processando envio…</div>`:''}${err?`<div class="dr-err">Último envio: ${esc(err.erro)}</div>`:''}
    ${podeEditar('drone')?`<button class="dr-btn2" style="margin-top:6px" onclick="drEnviar('obstaculos')"><span class="ico">upload</span> Enviar obstáculos</button>`:''}</div>`;
}

function drPrevHtml(ger){
  if(ger.status==='fila'||ger.status==='processando')return`<div class="dr-box"><h3>Gerando prévia…</h3><div class="dr-msg">O agente está montando o PDF e o .zip. Esta tela atualiza sozinha.</div></div>`;
  if(ger.status==='erro')return`<div class="dr-box"><h3>Erro na geração</h3><div class="dr-err">${esc(ger.erro)}</div>
    <button class="dr-btn2" style="margin-top:8px" onclick="drDescartar(${ger.id})">Descartar e montar de novo</button></div>`;
  if(ger.publicar_pedido_em&&!ger.publicacao_erro)return`<div class="dr-box"><h3>Publicando…</h3><div class="dr-msg">O agente está subindo os arquivos para o portal.</div></div>`;
  const al=(ger.alertas||[]).map(a=>`<li>${esc(a)}</li>`).join('');
  return`<div class="dr-box dr-prev"><h3>Prévia pronta</h3><div id="dr-pdf"><div class="dr-msg">carregando PDF…</div></div>
    ${al?`<ul style="margin:8px 0 0 16px;color:#d4890a">${al}</ul>`:''}
    ${ger.publicacao_erro?`<div class="dr-err">Falha ao publicar: ${esc(ger.publicacao_erro)}</div>`:''}
    <div style="font-size:12px;font-weight:600;margin:8px 0 4px">Motivo</div>
    <input class="dr-mot" id="dr-mot" placeholder="ex.: completar talhões 20–33; talhão 129 reformado">
    <div style="display:flex;gap:8px;margin-top:8px"><button class="dr-btn" onclick="drPublicar(${ger.id})">Publicar</button>
    <button class="dr-btn2" onclick="drDescartar(${ger.id})">Descartar</button></div></div>`;
}

async function drMostrarPdf(ger){
  const {data,error}=await sb.storage.from('drone-previas').createSignedUrl(ger.previa_pdf,600);
  const alvo=document.getElementById('dr-pdf');if(!alvo)return;
  alvo.innerHTML=error?`<div class="dr-err">${esc(error.message)}</div>`:`<iframe src="${data.signedUrl}"></iframe>`;
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
  h+=`<div id="dr-err" class="dr-err"></div>`;
  side.innerHTML=h;
  if(ger&&ger.status==='pronta'&&!(ger.publicar_pedido_em&&!ger.publicacao_erro))drMostrarPdf(ger);
  clearTimeout(DR.poll);
  const ocupado=(ger&&(['fila','processando'].includes(ger.status)||(ger.publicar_pedido_em&&!ger.publicacao_erro)))
    ||DR.info.envios.some(e=>e.status==='fila'||e.status==='processando');
  if(ocupado)DR.poll=setTimeout(async()=>{await drRecarregarFazenda();drCarregarPainel();},5000);
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
  inp.onchange=async()=>{
    try{
      const pasta=`${DR.cod}/${Date.now()}`,caminhos=[];
      for(const f of inp.files){
        const c=`${pasta}/${drNomeSeguro(f.name)}`;
        const {error}=await sb.storage.from('drone-envios').upload(c,f);
        if(error)throw error;caminhos.push(c);
      }
      const {sol}=drAtual();
      const id=await drRpc('drone_registrar_envio',{p_cod_faz:DR.cod,p_tipo:tipo,p_classe_m:classe,
        p_solicitacao_id:tipo==='infestacao'?sol.id:null,p_arquivos:caminhos});
      if(tipo==='ajuste')DR.ajusteId=id;
      await drRecarregarFazenda();
    }catch(e){drErro(e);}
  };
  inp.click();
}

async function drGerarNormal(){
  try{
    if([...DR.sel.values()].includes('shape')&&!DR.ajusteId)throw new Error('Envie o shape de ajuste antes de gerar.');
    const escopo={incluir:[...DR.sel].map(([t,f])=>f==='shape'?{talhao:t,fonte:'shape',envio_id:DR.ajusteId}:{talhao:t,fonte:'sistema'}),
      remover:[...DR.rem]};
    const sol=drAtual().sol?.id||await drRpc('drone_solicitar',{p_cod_faz:DR.cod,p_tipo:'normal',p_data_desejada:null,p_observacao:null});
    await drRpc('drone_pedir_geracao',{p_solicitacao_id:sol,p_escopo:escopo});
    DR.sel=new Map();DR.rem=new Set();
    await drRecarregarFazenda();drCarregarPainel();
  }catch(e){drErro(e);}
}

async function drAbrirCatacao(){
  try{await drRpc('drone_solicitar',{p_cod_faz:DR.cod,p_tipo:'catacao',p_data_desejada:null,p_observacao:null});
    await drRecarregarFazenda();drCarregarPainel();}catch(e){drErro(e);}
}

async function drGerarCatacao(){
  try{await drRpc('drone_pedir_geracao',{p_solicitacao_id:drAtual().sol.id,p_escopo:null});
    await drRecarregarFazenda();drCarregarPainel();}catch(e){drErro(e);}
}

async function drPublicar(id){
  try{
    const mot=document.getElementById('dr-mot').value;
    if(!await confirmar('Publicar esta revisão no portal de downloads?',{titulo:'Publicar',ok:'Publicar'}))return;
    await drRpc('drone_publicar_pedido',{p_geracao_id:id,p_motivo:mot});
    await drRecarregarFazenda();drCarregarPainel();
  }catch(e){drErro(e);}
}

async function drDescartar(id){
  try{
    if(!await confirmar('Descartar esta prévia?',{titulo:'Descartar',ok:'Descartar',perigo:true}))return;
    await drRpc('drone_descartar',{p_geracao_id:id});
    await drRecarregarFazenda();drCarregarPainel();
  }catch(e){drErro(e);}
}

function drValidarSolicitacao(v){
  if(!v.cod)return'Escolha a fazenda.';
  if(v.data){const hoje=new Date();hoje.setHours(0,0,0,0);if(new Date(v.data+'T12:00')<hoje)return'A data desejada já passou.';}
  return null;
}

function drNovaSolicitacao(){
  drEstilo();
  const fundo=document.createElement('div');fundo.className='dr-modal-fundo';
  fundo.innerHTML=`<div class="dr-modal"><h3>Nova solicitação · projeto Normal</h3>
    <label>Fazenda<input id="drs-busca" placeholder="Nome ou código" autocomplete="off"></label>
    <div id="drs-res"></div><input type="hidden" id="drs-cod">
    <label>Data desejada (opcional)<input type="date" id="drs-data"></label>
    <label>Observação<textarea id="drs-obs" rows="3" placeholder="ex.: completar talhões do bloco norte"></textarea></label>
    <div class="dr-err" id="drs-err"></div>
    <div style="display:flex;gap:8px;margin-top:10px"><button class="dr-btn" id="drs-ok">Enviar solicitação</button>
    <button class="dr-btn2" id="drs-cancela">Cancelar</button></div></div>`;
  document.body.appendChild(fundo);
  const fechar=()=>fundo.remove();
  fundo.querySelector('#drs-cancela').onclick=fechar;
  fundo.onclick=e=>{if(e.target===fundo)fechar();};
  fundo.querySelector('#drs-busca').oninput=async e=>{
    const txt=e.target.value.trim();fundo.querySelector('#drs-cod').value='';
    const res=fundo.querySelector('#drs-res');
    if(txt.length<2){res.innerHTML='';return;}
    const q=/^\d+$/.test(txt)?sb.from('fazendas').select('cod_faz,nome').eq('cod_faz',Number(txt))
      :sb.from('fazendas').select('cod_faz,nome').ilike('nome',`%${txt}%`).limit(8);
    const {data}=await q;
    res.innerHTML=(data||[]).map(f=>`<div class="dr-it" data-cod="${f.cod_faz}" data-nome="${esc(f.nome)}"><span class="dr-cod">${f.cod_faz}</span><div>${esc(f.nome)}</div></div>`).join('')
      ||'<div class="dr-msg">nenhuma fazenda</div>';
    res.querySelectorAll('.dr-it').forEach(el=>el.onclick=()=>{
      fundo.querySelector('#drs-cod').value=el.dataset.cod;
      fundo.querySelector('#drs-busca').value=`${el.dataset.cod} · ${el.dataset.nome}`;res.innerHTML='';});
  };
  fundo.querySelector('#drs-ok').onclick=async()=>{
    const v={cod:fundo.querySelector('#drs-cod').value,data:fundo.querySelector('#drs-data').value,
             obs:fundo.querySelector('#drs-obs').value};
    const erro=drValidarSolicitacao(v);
    if(erro){fundo.querySelector('#drs-err').textContent=erro;return;}
    try{
      await drRpc('drone_solicitar',{p_cod_faz:Number(v.cod),p_tipo:'normal',p_data_desejada:v.data||null,p_observacao:v.obs||null});
      fechar();await drCarregarPainel();drAbrirFazenda(Number(v.cod),'normal');
    }catch(e){fundo.querySelector('#drs-err').textContent=e.message;}
  };
  fundo.querySelector('#drs-busca').focus();
}

function drIrFazenda(cod){
  trocar('drone',document.querySelector(`.ni[onclick*="'drone'"]`));
  drAbrirFazenda(Number(cod));
}

// ── obstáculos no mapa (objeto + buffer da classe) ──────────────────────
const DR_OBS_COR={15:'#2e7d32',25:'#e0a100',50:'#c62828'};
async function drObstaculos(ligar){
  DR.mostrarObst=ligar;
  const m=DR.mapa;if(!m)return;
  for(const id of ['obs-buf','obs-buf-l','obs-lin','obs-pt'])if(m.getLayer(id))m.removeLayer(id);
  if(m.getSource('obs'))m.removeSource('obs');
  if(!ligar)return;
  try{if(!DR.obstGeo)DR.obstGeo=await drRpc('drone_obstaculos_mapa',{p_cod_faz:DR.cod});}
  catch(e){drErro(e);return;}
  const cor=['match',['get','classe'],15,DR_OBS_COR[15],25,DR_OBS_COR[25],DR_OBS_COR[50]];
  m.addSource('obs',{type:'geojson',data:DR.obstGeo});
  m.addLayer({id:'obs-buf',type:'fill',source:'obs',filter:['==',['get','camada'],'buffer'],paint:{'fill-color':cor,'fill-opacity':.15}});
  m.addLayer({id:'obs-buf-l',type:'line',source:'obs',filter:['==',['get','camada'],'buffer'],paint:{'line-color':cor,'line-width':1,'line-dasharray':[2,2]}});
  m.addLayer({id:'obs-lin',type:'line',source:'obs',filter:['all',['==',['get','camada'],'obst'],['!=',['geometry-type'],'Point']],paint:{'line-color':cor,'line-width':2}});
  m.addLayer({id:'obs-pt',type:'circle',source:'obs',filter:['all',['==',['get','camada'],'obst'],['==',['geometry-type'],'Point']],paint:{'circle-color':cor,'circle-radius':3}});
}

function drRotuloShape(envio){
  if(!envio)return'Enviar shape de ajuste';
  if(envio.status==='erro')return'Erro no shape — enviar outro';
  if(envio.status==='ok')return'Shape enviado ✓ (trocar)';
  return'Shape em processamento…';
}
