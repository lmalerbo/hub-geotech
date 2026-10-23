// Tela do Drone (spec Parte 2, §5): fila de trabalho + fazenda com mapa por talhão.
const DR={painel:null,cod:null,geo:null,mapa:null,sel:new Map(),rem:new Set(),modoRemover:false,
  doc:'normal',ajusteId:null,poll:null,info:null};
const DR_ST={aguardando_obstaculos:'aguardando obstáculos',aguardando_infestacao:'aguardando infestação',
  solicitado:'solicitado',em_elaboracao:'em elaboração',devolvido:'devolvido'};
const DR_COR={normal:'#a0694b',catacao:'#5b8c5a',sel:'#5b6ee8',rem:'#c23b3b',sem:'#e9ebef',fora:'#d4890a'};

// Movimento (app/motion.js). Os botões do Drone chamam as funções sem passar o
// botão; ele é pego do evento do clique — antes de qualquer await/prompt, que
// apagam window.event.
function drBotao(){const e=window.event;return e&&e.target&&e.target.closest?e.target.closest('button'):null;}

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
.dr-x{border:0;background:none;color:var(--t3);cursor:pointer;padding:2px;border-radius:6px}
.dr-x:hover{color:#c23b3b;background:#fbe0e0}
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
    const fila=document.getElementById('dr-fila');
    Mo.carregando(fila);await drCarregarPainel();Mo.pronto(fila);
    return;
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
      <div class="r">${x.data_desejada?'para '+new Date(x.data_desejada+'T12:00').toLocaleDateString('pt-BR'):''}<br>${esc(st)}</div>
      ${drPodeCancelar(x,x.geracao,EU)?`<button class="dr-x" title="Cancelar solicitação" onclick="event.stopPropagation();drCancelar(${x.id})"><span class="ico">close</span></button>`:''}</div>`;
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
  const pnl=document.getElementById('dr-faz');
  DR.voo=null;
  Mo.carregando(pnl);await drRecarregarFazenda();Mo.pronto(pnl);
}

async function drRecarregarFazenda(){
  const cod=DR.cod;
  try{
    const [geo,faz,sols,obst]=await Promise.all([
      drRpc('drone_mapa_fazenda',{p_cod_faz:cod}),
      sb.from('fazendas').select('cod_faz,nome').eq('cod_faz',cod).single(),
      sb.from('drone_solicitacoes').select('id,tipo,status,observacao,solicitante_id').eq('cod_faz',cod).neq('origem','legado').not('status','in','(ok,cancelado)'),
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
      <div class="dr-docs">${card('normal','Normal',g.normal,pct!=null&&pct<100?`<span class="dr-tag">${Math.floor(pct)}% DA FAZENDA</span>`:'')}
        ${card('catacao','Catação',g.catacao,'')}</div></div>
    <div class="dr-body"><div><div class="dr-map" id="dr-map"></div>
      <div class="dr-leg"><span><i style="background:${DR_COR[DR.doc]}"></i>área de aplicação vigente</span>
        <span><i style="background:${DR_COR.sem}"></i>sem projeto</span><span><i style="background:#fff;border-color:${DR_COR.fora}"></i>fora da Base</span>
        <span><i style="background:#d9defc;border-color:${DR_COR.sel}"></i>selecionado</span><span><i style="background:#fbe0e0;border-color:${DR_COR.rem}"></i>remover</span>
        <label style="margin-left:auto;cursor:pointer"><input type="checkbox" ${DR.mostrarObst?'checked':''} onchange="drObstaculos(this.checked)"> mostrar obstáculos</label></div></div>
      <div class="dr-side" id="dr-side"></div></div>`;
  drPintarMapa();
  drPainelLateral();
  drVooPublicacao();
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
    Mo.voo(mapa,{texto:'Publicando no portal…',desde:DR.voo.desde});
  }else if(DR.voo){
    const erro=ger&&ger.id===DR.voo.id&&ger.publicacao_erro;
    Mo.voo(mapa,{desde:DR.voo.desde}).pousar(!erro,erro?'Falha ao publicar':'Publicado no portal');
    DR.voo=null;
  }
}

function drPintarMapa(){
  const fc={type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada==='talhao')};
  const apl={type:'FeatureCollection',features:DR.geo.features.filter(f=>f.properties.camada===DR.doc)};
  if(DR.mapa){DR.mapa.remove();DR.mapa=null;}
  // esboço só quando muda a fazenda/documento (o polling redesenha o mapa a cada 5 s)
  const box=document.getElementById('dr-map'),chave=DR.cod+'|'+DR.doc,novo=DR.mapaChave!==chave;
  DR.mapaChave=chave;
  if(novo)Mo.carregando(box);
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
    Mo.pronto(box,{cascata:false});
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

function drPodeCancelar(sol,ger,eu){
  if(!sol||!eu)return false;
  const ocupado=ger&&(ger.status==='processando'||(ger.status==='pronta'&&ger.publicar_pedido_em&&!ger.publicacao_erro));
  if(ocupado)return false;
  if(podeEditar('drone'))return true;
  return sol.solicitante_id===eu.id&&!ger;            // solicitante: só a própria e antes da prévia
}

async function drCancelar(id){
  const btn=drBotao();
  const motivo=prompt('Motivo do cancelamento:');
  if(motivo===null)return;
  if(!motivo.trim()){alert('Informe o motivo.');return;}
  if(!await confirmar('Cancelar esta solicitação? A prévia aberta, se houver, será descartada.',
                      {titulo:'Cancelar solicitação',ok:'Cancelar solicitação',perigo:true}))return;
  const fim=Mo.ocupado(btn);
  try{
    await drRpc('drone_cancelar',{p_solicitacao_id:id,p_motivo:motivo});
    fim(true);
    await drCarregarPainel();if(DR.cod)await drRecarregarFazenda();
  }catch(e){fim(false);drErro(e);alert(e.message);}
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

// ── Prévia de aprovação (S5) ─────────────────────────────────
// O PDF é baixado como bytes e desenhado com pdf.js, dentro do Hub: não depende
// de como o Storage serve o arquivo (content-type/download). O painel mostra a
// capa; a janela (modal grande) tem as páginas com zoom e as ações da prévia.
const DRP={cache:new Map(),gerando:new Set(),ger:null,zoom:1,ajustar:true,desenho:0,motivo:{}};
const DRP_PDFJS='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/';

function drPrevEstilo(){
  if(document.getElementById('drone-previa-css'))return;
  const s=document.createElement('style');s.id='drone-previa-css';
  s.textContent=`
.drp-capa{position:relative;display:block;width:100%;border:1px solid var(--bd);border-radius:10px;background:var(--s2);padding:0;cursor:zoom-in;overflow:hidden;min-height:90px}
.drp-capa canvas{display:block;width:100%;height:auto}
.drp-capa .drp-lupa{position:absolute;right:8px;bottom:8px;background:#fffe;border-radius:8px;padding:3px 8px;font-size:11px;font-weight:600;color:var(--drones);box-shadow:0 1px 3px #0002;transition:transform .2s}
.drp-capa:hover .drp-lupa{transform:translateY(-2px)}
.drp-passos{display:flex;gap:6px;margin:8px 0 6px}
.drp-passos span{flex:1;font-size:10.5px;text-align:center;padding:4px 2px;border-radius:7px;background:var(--s2);color:var(--t3)}
.drp-passos span.feito{background:#e5efe5;color:#3f7a3e}
.drp-passos span.agora{background:#eef0fd;color:var(--drones);font-weight:600;animation:drp-pulsa 1.6s ease-in-out infinite}
@keyframes drp-pulsa{50%{box-shadow:0 0 0 3px #5b6ee833}}
.drp-espera{display:flex;flex-direction:column;align-items:center;gap:6px;padding:6px 0}
.drp-fundo{position:fixed;inset:0;background:rgba(20,24,30,.55);display:flex;align-items:center;justify-content:center;z-index:240;animation:drp-entra-f .18s ease-out}
.drp-jan{background:var(--sf);border-radius:16px;box-shadow:0 20px 60px #0004;width:min(1100px,96vw);height:min(900px,94vh);display:grid;grid-template-columns:1fr 300px;grid-template-rows:auto 1fr;overflow:hidden;animation:drp-entra .22s cubic-bezier(.2,.9,.3,1.2)}
.drp-cab{grid-column:1/-1;display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid var(--bd)}
.drp-cab h3{font-size:15px;font-weight:600;margin-right:auto}
.drp-cab small{color:var(--t3);font-size:12px;font-weight:400;margin-left:6px}
.drp-zoom{display:flex;align-items:center;gap:2px;background:var(--s2);border-radius:9px;padding:3px}
.drp-zoom button{border:0;background:none;border-radius:7px;padding:4px 8px;font:inherit;font-size:12px;color:var(--t2);cursor:pointer}
.drp-zoom button:hover{background:#fff}.drp-zoom button.on{background:#fff;color:var(--drones);font-weight:600}
.drp-zoom output{min-width:44px;text-align:center;font-size:12px;font-variant-numeric:tabular-nums}
.drp-pags{overflow:auto;background:#5f6670;padding:18px;display:flex;flex-direction:column;align-items:center;gap:14px}
.drp-pg{position:relative;background:#fff;box-shadow:0 2px 10px #0005;flex:none;display:flex;align-items:center;justify-content:center}
.drp-pg canvas{display:block;width:100%;height:100%;opacity:0;transition:opacity .25s}
.drp-pg.ok canvas{opacity:1}.drp-pg .mo-campo{position:absolute}.drp-pg.ok .mo-campo{display:none}
.drp-carga{width:min(360px,80%);margin:auto;color:#fff}
.drp-lado{border-left:1px solid var(--bd);padding:14px 16px;display:flex;flex-direction:column;gap:10px;font-size:12px;overflow:auto}
.drp-lado .dr-btn,.drp-lado .dr-btn2{display:flex;align-items:center;justify-content:center;gap:6px}
@keyframes drp-entra{from{opacity:0;transform:translateY(12px) scale(.97)}}
@keyframes drp-entra-f{from{opacity:0}}
@media (max-width:760px){.drp-jan{grid-template-columns:1fr;grid-template-rows:auto 1fr auto}.drp-lado{border-left:0;border-top:1px solid var(--bd);max-height:40vh}}
@media (prefers-reduced-motion:reduce){.drp-fundo,.drp-jan,.drp-passos span.agora{animation:none}.drp-pg canvas{transition:none}}`;
  document.head.appendChild(s);
}

function drPrevPassosHtml(st){
  const p=[['fila','Na fila'],['processando','Montando'],['pronta','Prévia']],i=p.findIndex(x=>x[0]===st);
  return`<div class="drp-passos">${p.map(([,t],k)=>`<span class="${k<i?'feito':k===i?'agora':''}">${t}</span>`).join('')}</div>`;
}

function drPrevHtml(ger){
  drPrevEstilo();
  if(ger.status==='fila'||ger.status==='processando'){
    DRP.gerando.add(ger.id);
    return`<div class="dr-box"><h3>Gerando prévia…</h3>${drPrevPassosHtml(ger.status)}
      <div class="drp-espera">${Mo.campo(true)}<div class="dr-msg">${ger.status==='fila'?'Esperando o agente pegar o pedido.':'O agente está montando o PDF e o .zip.'}
      Esta tela atualiza sozinha e a prévia abre assim que ficar pronta.</div></div></div>`;
  }
  if(ger.status==='erro')return`<div class="dr-box"><h3>Erro na geração</h3><div class="dr-err">${esc(ger.erro)}</div>
    <button class="dr-btn2" style="margin-top:8px" onclick="drDescartar(${ger.id})">Descartar e montar de novo</button></div>`;
  if(ger.publicar_pedido_em&&!ger.publicacao_erro)return`<div class="dr-box"><h3>Publicando…</h3><div class="dr-msg">O agente está subindo os arquivos para o portal.</div></div>`;
  const al=(ger.alertas||[]).length;
  return`<div class="dr-box dr-prev"><h3>Prévia pronta</h3>
    <button class="drp-capa" id="dr-pdf" onclick="drPrevAbrir()" title="Abrir a prévia"></button>
    ${al?`<div style="color:#d4890a;margin-top:6px"><span class="ico" style="font-size:14px;vertical-align:-3px">warning</span> ${al} alerta${al>1?'s':''} — veja na prévia</div>`:''}
    ${ger.publicacao_erro?`<div class="dr-err">Falha ao publicar: ${esc(ger.publicacao_erro)}</div>`:''}
    <button class="dr-btn" style="margin-top:8px" onclick="drPrevAbrir()"><span class="ico" style="vertical-align:-3px">preview</span> Abrir prévia</button></div>`;
}

// Carrega o pdf.js uma vez só, sob demanda.
function drPdfjs(){
  if(window.pdfjsLib)return Promise.resolve(window.pdfjsLib);
  if(!DRP.pdfjs)DRP.pdfjs=new Promise((ok,falha)=>{
    const s=document.createElement('script');s.src=DRP_PDFJS+'pdf.min.js';
    s.onload=()=>{pdfjsLib.GlobalWorkerOptions.workerSrc=DRP_PDFJS+'pdf.worker.min.js';ok(pdfjsLib);};
    s.onerror=()=>{DRP.pdfjs=null;falha(new Error('Não deu para carregar o leitor de PDF.'));};
    document.head.appendChild(s);
  });
  return DRP.pdfjs;
}

// Baixa os bytes da prévia (com % real quando o servidor informa o tamanho) e abre no pdf.js.
// Fica em cache por arquivo: a capa do painel e a janela usam o mesmo download.
function drPrevCarregar(caminho){
  let c=DRP.cache.get(caminho);
  if(c&&!c.falhou)return c.pronto;
  c={ouvintes:new Set()};
  const avisa=(b,t)=>c.ouvintes.forEach(f=>f(b,t));
  c.pronto=(async()=>{
    const [{data,error}]=await Promise.all([sb.storage.from('drone-previas').createSignedUrl(caminho,600),drPdfjs()]);
    if(error)throw new Error(error.message);
    const r=await fetch(data.signedUrl);
    if(!r.ok)throw new Error('Não deu para baixar a prévia ('+r.status+').');
    const total=+r.headers.get('content-length')||0,partes=[];let lido=0;
    if(r.body&&r.body.getReader){
      const rd=r.body.getReader();
      for(;;){const {done,value}=await rd.read();if(done)break;partes.push(value);lido+=value.length;avisa(lido,total);}
    }else{partes.push(new Uint8Array(await r.arrayBuffer()));}
    const blob=new Blob(partes,{type:'application/pdf'});
    const pdf=await pdfjsLib.getDocument({data:new Uint8Array(await blob.arrayBuffer())}).promise;
    return{blob,pdf};
  })();
  c.pronto.catch(()=>{c.falhou=true;});
  DRP.cache.set(caminho,c);
  return c.pronto;
}
function drPrevOuvir(caminho,f){const c=DRP.cache.get(caminho);if(c)c.ouvintes.add(f);}

async function drDesenharPagina(pdf,n,canvas,larguraCss){
  const pg=await pdf.getPage(n),v1=pg.getViewport({scale:1}),k=larguraCss/v1.width;
  const dpr=Math.min(window.devicePixelRatio||1,2),v=pg.getViewport({scale:k*dpr});
  canvas.width=Math.floor(v.width);canvas.height=Math.floor(v.height);
  await pg.render({canvasContext:canvas.getContext('2d'),viewport:v}).promise;
}

// Capa do painel lateral (chamada por drPainelLateral quando a prévia está pronta).
async function drMostrarPdf(ger){
  const alvo=document.getElementById('dr-pdf');if(!alvo)return;
  DRP.ger=ger;
  // Acabou de sair de "Gerando prévia…" com a tela aberta: a janela abre sozinha.
  if(DRP.gerando.delete(ger.id))drPrevAbrir();
  const caixa=document.createElement('div');caixa.style.padding='14px';alvo.appendChild(caixa);
  const prog=Mo.progresso(caixa,{total:0});prog.processando('Baixando a prévia…');
  drPrevCarregar(ger.previa_pdf);
  drPrevOuvir(ger.previa_pdf,(b,t)=>t?prog.atualizar(b,'Baixando a prévia…'):prog.processando('Baixando a prévia… '+Math.round(b/1024)+' KB'));
  try{
    const {pdf}=await drPrevCarregar(ger.previa_pdf);
    if(!alvo.isConnected)return;
    prog.processando('Desenhando a capa…');
    const cv=document.createElement('canvas');
    await drDesenharPagina(pdf,1,cv,Math.max(260,alvo.clientWidth));
    if(!alvo.isConnected)return;
    alvo.innerHTML='';alvo.appendChild(cv);
    alvo.insertAdjacentHTML('beforeend',`<span class="drp-lupa">${pdf.numPages} pág. · abrir</span>`);
    alvo.classList.add('mo-surge');
  }catch(e){
    if(alvo.isConnected)caixa.innerHTML=`<div class="dr-err">${esc(e.message)}</div>`;
  }
}

// ── Janela da prévia ──
function drPrevAbrir(){
  const ger=DRP.ger;
  if(!ger||document.getElementById('drp-fundo'))return;
  drPrevEstilo();DRP.tam=null;DRP.ajustar=true;
  const al=(ger.alertas||[]).map(a=>`<li>${esc(a)}</li>`).join('');
  const nome=(ger.previa_pdf||'').split('/').pop();
  const f=document.createElement('div');f.className='drp-fundo';f.id='drp-fundo';
  f.innerHTML=`<div class="drp-jan" role="dialog" aria-modal="true" aria-labelledby="drp-t">
    <div class="drp-cab"><h3 id="drp-t">Prévia · ${esc(DR.info.faz?.nome||DR.cod)}<small>${esc(nome)}</small></h3>
      <div class="drp-zoom"><button onclick="drPrevZoom(-1)" title="Diminuir" aria-label="Diminuir"><span class="ico">remove</span></button>
        <output id="drp-pct">—</output>
        <button onclick="drPrevZoom(1)" title="Aumentar" aria-label="Aumentar"><span class="ico">add</span></button>
        <button id="drp-ajustar" class="on" onclick="drPrevZoom(0)">Ajustar à largura</button></div>
      <button class="dr-x" onclick="drPrevFechar()" title="Fechar (Esc)" aria-label="Fechar"><span class="ico">close</span></button></div>
    <div class="drp-pags" id="drp-pags"><div class="drp-carga" id="drp-carga"></div></div>
    <div class="drp-lado">
      ${al?`<div class="dr-box"><h3><span class="ico" style="color:#d4890a;font-size:15px;vertical-align:-3px">warning</span> Alertas</h3><ul style="margin:0;padding-left:16px;color:#d4890a">${al}</ul></div>`:''}
      ${ger.publicacao_erro?`<div class="dr-err">Falha ao publicar: ${esc(ger.publicacao_erro)}</div>`:''}
      <div style="font-size:12px;font-weight:600">Motivo</div>
      <input class="dr-mot" id="dr-mot" placeholder="ex.: completar talhões 20–33; talhão 129 reformado"
        value="${esc(DRP.motivo[ger.id]||'')}" oninput="DRP.motivo[${ger.id}]=this.value">
      <button class="dr-btn" onclick="drPrevAcao('publicar',this)"><span class="ico">publish</span> Publicar</button>
      <button class="dr-btn2" onclick="drPrevAcao('descartar',this)"><span class="ico">undo</span> Descartar e ajustar</button>
      <div class="dr-msg" style="text-align:left">Descartar libera a seleção para montar a prévia de novo com o ajuste.</div>
      <div id="drp-err" class="dr-err"></div>
      <div style="margin-top:auto;display:flex;flex-direction:column;gap:8px">
        <button class="dr-btn2" id="drp-baixar" onclick="drPrevBaixar(this)"><span class="ico">download</span> Baixar PDF</button>
        <button class="dr-btn2" onclick="drPrevFechar()">Fechar</button></div></div></div>`;
  f.addEventListener('mousedown',e=>{if(e.target===f)drPrevFechar();});
  document.body.appendChild(f);
  // Esc fecha, menos quando o "confirmar" do Hub está aberto por cima.
  DRP.tecla=e=>{const c=document.getElementById('modal-confirma');
    if(e.key==='Escape'&&(!c||c.classList.contains('off')))drPrevFechar();};
  document.addEventListener('keydown',DRP.tecla);
  DRP.redim=()=>{if(DRP.ajustar)drPrevRedesenhar();};
  window.addEventListener('resize',DRP.redim);
  document.getElementById('drp-pags').addEventListener('wheel',e=>{
    if(!e.ctrlKey)return;e.preventDefault();drPrevZoom(e.deltaY<0?1:-1);},{passive:false});
  drPrevMontar(ger);
}

function drPrevFechar(){
  const f=document.getElementById('drp-fundo');if(!f)return;
  document.removeEventListener('keydown',DRP.tecla);window.removeEventListener('resize',DRP.redim);
  DRP.desenho++;f.remove();
}

async function drPrevMontar(ger){
  const carga=document.getElementById('drp-carga');
  const prog=Mo.progresso(carga,{total:0});prog.processando('Baixando a prévia…');
  drPrevCarregar(ger.previa_pdf);
  drPrevOuvir(ger.previa_pdf,(b,t)=>t?prog.atualizar(b,'Baixando a prévia…'):prog.processando('Baixando a prévia… '+Math.round(b/1024)+' KB'));
  try{
    const {pdf}=await drPrevCarregar(ger.previa_pdf);
    const pags=document.getElementById('drp-pags');if(!pags)return;
    prog.fim(true,'Prévia baixada');
    // Molduras no tamanho certo antes de desenhar: nada pula enquanto as páginas chegam.
    const tam=[];
    for(let n=1;n<=pdf.numPages;n++){const v=(await pdf.getPage(n)).getViewport({scale:1});tam.push([v.width,v.height]);}
    DRP.pdf=pdf;DRP.tam=tam;
    pags.innerHTML=tam.map((_,i)=>`<div class="drp-pg" data-n="${i+1}">${Mo.campo(true)}<canvas></canvas></div>`).join('');
    drPrevRedesenhar();
  }catch(e){
    prog.fim(false,'Falhou');
    carga.insertAdjacentHTML('beforeend',`<div class="dr-err" style="color:#ffd0d0;margin-top:8px">${esc(e.message)}</div>`);
  }
}

// Zoom: passo = ±1, 0 = ajustar à largura. A moldura muda na hora (CSS) e a
// página é redesenhada nítida logo depois.
const DRP_PASSOS=[.5,.67,.8,1,1.25,1.5,2,2.5,3];
function drPrevLarguraAjuste(){
  const pags=document.getElementById('drp-pags');
  return Math.max(200,(pags?.clientWidth||800)-36)/Math.max(...(DRP.tam||[[600]]).map(t=>t[0]));
}
function drPrevZoom(passo){
  if(!DRP.tam)return;
  if(passo===0){DRP.ajustar=true;}
  else{
    const atual=DRP.ajustar?drPrevLarguraAjuste():DRP.zoom;
    const prox=passo>0?DRP_PASSOS.find(z=>z>atual+.01):[...DRP_PASSOS].reverse().find(z=>z<atual-.01);
    if(prox===undefined)return;
    DRP.ajustar=false;DRP.zoom=prox;
  }
  drPrevRedesenhar();
}
function drPrevRedesenhar(){
  const pags=document.getElementById('drp-pags');if(!pags||!DRP.tam)return;
  const z=DRP.ajustar?drPrevLarguraAjuste():DRP.zoom;
  document.getElementById('drp-pct').textContent=Math.round(z*100)+'%';
  document.getElementById('drp-ajustar').classList.toggle('on',DRP.ajustar);
  pags.style.alignItems=pags.clientWidth<DRP.tam[0][0]*z+36?'flex-start':'center';
  pags.querySelectorAll('.drp-pg').forEach((d,i)=>{d.style.width=DRP.tam[i][0]*z+'px';d.style.height=DRP.tam[i][1]*z+'px';});
  clearTimeout(DRP.tRedes);
  DRP.tRedes=setTimeout(async()=>{
    const vez=++DRP.desenho;
    for(const d of pags.querySelectorAll('.drp-pg')){
      if(vez!==DRP.desenho)return;
      const i=+d.dataset.n-1,cv=document.createElement('canvas');
      try{await drDesenharPagina(DRP.pdf,i+1,cv,DRP.tam[i][0]*z);}catch(e){continue;}
      if(vez!==DRP.desenho)return;
      d.querySelector('canvas').replaceWith(cv);
      requestAnimationFrame(()=>d.classList.add('ok'));
    }
  },120);
}

async function drPrevBaixar(btn){
  const ger=DRP.ger;if(!ger)return;
  const fim=Mo.ocupado(btn);
  try{
    const {blob}=await drPrevCarregar(ger.previa_pdf);
    fim(true);
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);
    a.download=(ger.previa_pdf||'previa.pdf').split('/').pop();
    document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(a.href),10000);
  }catch(e){fim(false);document.getElementById('drp-err').textContent=e.message;}
}

// Publicar/descartar continuam nas funções de sempre (drPublicar/drDescartar);
// a janela fecha quando a prévia sai de "pronta" e mostra o erro aqui dentro se falhar.
async function drPrevAcao(qual,btn){
  const ger=DRP.ger;if(!ger)return;
  const err=document.getElementById('drp-err');err.textContent='';
  const painelErr=document.getElementById('dr-err');if(painelErr)painelErr.textContent='';
  await (qual==='publicar'?drPublicar:drDescartar)(ger.id,btn);
  const agora=drAtual().ger;
  if(!agora||agora.id!==ger.id||agora.status!=='pronta'||(agora.publicar_pedido_em&&!agora.publicacao_erro)){
    delete DRP.motivo[ger.id];DRP.cache.delete(ger.previa_pdf);drPrevFechar();return;
  }
  const msg=document.getElementById('dr-err')?.textContent;
  if(msg&&document.getElementById('drp-err'))document.getElementById('drp-err').textContent=msg;
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
      await drRecarregarFazenda();
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
    await drRecarregarFazenda();drCarregarPainel();
  }catch(e){fim(false);drErro(e);}
}

async function drAbrirCatacao(){
  const fim=Mo.ocupado(drBotao());
  try{await drRpc('drone_solicitar',{p_cod_faz:DR.cod,p_tipo:'catacao',p_data_desejada:null,p_observacao:null});
    fim(true);await drRecarregarFazenda();drCarregarPainel();}catch(e){fim(false);drErro(e);}
}

async function drGerarCatacao(){
  const fim=Mo.ocupado(drBotao());
  try{await drRpc('drone_pedir_geracao',{p_solicitacao_id:drAtual().sol.id,p_escopo:null});
    fim(true);await drRecarregarFazenda();drCarregarPainel();}catch(e){fim(false);drErro(e);}
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
    await drRecarregarFazenda();drCarregarPainel();
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
    await drRecarregarFazenda();drCarregarPainel();
  }catch(e){fim(false);drErro(e);}
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
    const fim=Mo.ocupado(fundo.querySelector('#drs-ok'));
    try{
      await drRpc('drone_solicitar',{p_cod_faz:Number(v.cod),p_tipo:'normal',p_data_desejada:v.data||null,p_observacao:v.obs||null});
      await fim(true);
      fechar();await drCarregarPainel();drAbrirFazenda(Number(v.cod),'normal');
    }catch(e){fim(false);fundo.querySelector('#drs-err').textContent=e.message;}
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
