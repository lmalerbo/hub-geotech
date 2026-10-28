// Drone: Início (fila, Atenção, busca, nova solicitação). Carregado por index.html depois de drone-previa.js.

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
    await drCarregarPainel();if(DR.cod)await drRecarregarFazenda();
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
