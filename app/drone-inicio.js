// Drone: Início (fila, Atenção, busca, nova solicitação). Carregado por index.html depois de drone-previa.js.

// Regras puras do Início: coluna, situação, tempos, cartão e reconciliação (testadas em tests/app/drone_puro.test.js).
function driColuna(sol){
  const g=sol&&sol.geracao;
  if(!g)return'solicitacoes';
  if(['fila','processando','erro'].includes(g.status))return'desenvolvimento';
  if(g.status==='pronta')return g.publicar_pedido_em||g.publicacao_erro?'desenvolvimento':'analisar';
  return'solicitacoes';
}
function driSituacao(sol){
  const g=sol.geracao;
  if(!g){
    if(sol.status==='aguardando_obstaculos')return{ico:'warning',txt:'Aguardando obstáculos',cls:'aviso'};
    if(sol.status==='aguardando_infestacao')return{ico:'pest_control',txt:'Aguardando infestação',cls:'aviso'};
    if(sol.status==='devolvido')return{ico:'undo',txt:'Devolvido',cls:'aviso'};
    return sol.observacao?{ico:'',txt:sol.observacao,cls:''}:null;
  }
  if(g.status==='fila')return{ico:'schedule',txt:'Na fila',cls:'vivo'};
  if(g.status==='processando')return{ico:'',txt:'Gerando prévia',cls:'vivo'};
  if(g.status==='erro')return{ico:'error',txt:'Erro na geração: '+g.erro,cls:'erro'};
  if(g.status==='pronta'){
    if(g.publicacao_erro&&g.publicar_pedido_em)return{ico:'error',txt:'Erro ao publicar: '+g.publicacao_erro,cls:'erro'};
    if(g.publicar_pedido_em)return{ico:'flight',txt:'Publicando no portal…',cls:'vivo'};
    if(g.alertas>0)return{ico:'report',txt:'Prévia · '+g.alertas+(g.alertas===1?' alerta':' alertas'),cls:'aviso'};
    return{ico:'check_circle',txt:'Prévia · sem alertas',cls:'ok'};
  }
  return sol.observacao?{ico:'',txt:sol.observacao,cls:''}:null;
}
function driDesde(iso,agora){
  if(!iso)return'';
  const s=Math.floor((((agora||new Date())-new Date(iso))/1000));
  if(s<60)return'agora';
  if(s<3600)return Math.floor(s/60)+' min';
  if(s<86400)return Math.floor(s/3600)+' h';
  return Math.floor(s/86400)+' dias';
}
function driQuando(iso,agora){
  if(!iso)return'';
  const a=agora||new Date(), d=new Date(iso);
  const dia=x=>Date.UTC(x.getFullYear(),x.getMonth(),x.getDate());
  const n=Math.round((dia(a)-dia(d))/86400000);
  if(n<=0)return'hoje';
  if(n===1)return'ontem';
  return'há '+n+' dias';
}
function driAndamento(painel){
  return!!(painel&&(painel.solicitacoes||[]).some(x=>{
    const g=x.geracao;
    if(!g)return false;
    if(g.status==='fila'||g.status==='processando')return true;
    return g.status==='pronta'&&!!g.publicar_pedido_em&&!g.publicacao_erro;
  }));
}
function driAtencaoItens(painel,chave){
  return(painel&&painel[chave]||[]).map(x=>typeof x==='object'
    ?{cod_faz:x.cod_faz,fazenda:x.fazenda||'',extra:x.pct!=null?x.pct+'%':''}
    :{cod_faz:x,fazenda:'',extra:''});
}
function driCartaoHtml(sol,opts){
  const o=opts||{}, agora=o.agora||new Date();
  const g=sol.geracao||null;
  const col=driColuna(sol), sit=driSituacao(sol);
  const tipo=sol.tipo==='catacao'?'catacao':'normal';
  const cod=esc(sol.cod_faz);
  const emCurso=!!g&&(g.status==='fila'||g.status==='processando');
  let pe='';
  if(col==='solicitacoes'){
    const dt=sol.data_desejada?'para '+new Date(sol.data_desejada+'T12:00').toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'}):'sem data';
    pe=`<div class="dri-pe"><span>${esc(sol.solicitante||'')} · <span data-quando="${esc(sol.criado_em)}">${esc(driQuando(sol.criado_em,agora))}</span></span><span>${esc(dt)}</span></div>`;
  }else if(col==='desenvolvimento'&&emCurso){
    pe=`<div class="dri-pe"><span></span><span data-desde="${esc(sol.geracao.pedido_em||sol.pedido_em||'')}">${esc(driDesde(sol.geracao.pedido_em||sol.pedido_em,agora))}</span></div>`;
  }else if(col==='analisar'){
    const conf=o.editor?`<button class="dri-conferir" onclick="event.stopPropagation();driAbrirFazenda(${cod},'${tipo}')">Conferir</button>`:'';
    pe=`<div class="dri-pe"><span>gerada há <span data-desde="${esc(g.concluido_em)}">${esc(driDesde(g.concluido_em,agora))}</span></span>${conf}</div>`;
  }
  const situ=sit?`<div class="dri-sit${sit.cls?' dri-'+sit.cls:''}">${sit.ico?`<span class="ico">${sit.ico}</span>`:''}<span>${esc(sit.txt)}</span></div>`:'';
  const trilho=emCurso?'<div class="dri-trilho"><i></i></div>':'';
  return`<div class="dri-card${sit&&sit.cls==='erro'?' erro':''}" role="button" tabindex="0" data-id="${esc(sol.id)}" data-cod="${cod}" data-tipo="${tipo}" onclick="driAbrirFazenda(${cod},'${tipo}')" onkeydown="if(event.key==='Enter')this.click()">
    <div class="dri-l1"><span class="dr-cod">${cod}</span><b>${esc(sol.fazenda)}</b><span class="dri-tipo dri-${tipo==='catacao'?'C':'N'}">${tipo==='catacao'?'Catação':'Normal'}</span></div>
    ${situ}${trilho}${pe}
  </div>`;
}
function driPlano(atuais,novos){
  const ids=l=>new Map(l.map(x=>[x.id,x.ass]));
  const A=ids(atuais), N=ids(novos);
  return{
    remover:atuais.filter(x=>!N.has(x.id)).map(x=>x.id),
    trocar:novos.filter(x=>A.has(x.id)&&A.get(x.id)!==x.ass).map(x=>x.id),
    inserir:novos.filter(x=>!A.has(x.id)).map(x=>x.id)
  };
}

async function droneIniciar(){
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
  const nova=(podeEditar('drone')||(EU&&EU.niveis.drone==='solicitante'))
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
    await drCarregarPainel();if(DR.cod)await drCarregarFazenda();
  }catch(e){fim(false);drErro(e);alert(e.message);}
}

function drNovaSolicitacao(){
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
