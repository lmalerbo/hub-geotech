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
  document.getElementById('dr-fila').innerHTML=nova
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
  DR.cod=cod;DR.doc=doc||'normal';DR.sel=new Map();DR.rem=new Set();DR.modoRemover=false;DR.ajusteId=null;
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
        <span><i style="background:#d9defc;border-color:${DR_COR.sel}"></i>selecionado</span><span><i style="background:#fbe0e0;border-color:${DR_COR.rem}"></i>remover</span></div></div>
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

// Ações (clique, painel lateral, envios, prévia) ficam na Tarefa 9.
function drClicarTalhao(){}
function drPainelLateral(){document.getElementById('dr-side').innerHTML='';}
function drNovaSolicitacao(){}
