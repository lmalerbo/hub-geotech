// Tela de projetos do Hub (Plantio e Preparo): barra de etapa com alça para trás,
// seleção por talhão, distribuição por etapa, nova revisão com arquivos e linha do tempo.
// Spec: docs/superpowers/specs/2026-10-23-fluxo-projetos-design.md (D1–D5 e contrato).
// Globais do index usados: sb, WORKER_URL, esc, fmtNum, fmtDataHora, podeEditar, recarregar,
// showToast, revisoesDe, ET.

const PJ_MO_VAZIO={ocupado:()=>()=>{},progresso:()=>({atualizar(){},fim(){}}),carregando(){},pronto(){},etapa(){},concluido(){}};
function pjMo(){return window.Mo||PJ_MO_VAZIO}
const pjH=v=>esc(v==null?'':String(v));

const PJ_COR_P='#a07840';
// Preparo: 5 etapas (0–4). p = rótulo que o banco guarda em talhao_preparo.etapa e recebe em p_para (A1).
// A etapa 3 aparece como "Projeto" na tela, mas o banco a chama de "Preparo".
const PJ_ET_P=[
  {l:'Identificação',c:PJ_COR_P,i:'pin_drop',p:'Identificação'},
  {l:'Escoamento',c:PJ_COR_P,i:'water',p:'Escoamento'},
  {l:'Observações',c:PJ_COR_P,i:'comment',p:'Observações'},
  {l:'Projeto',c:PJ_COR_P,i:'construction',p:'Preparo'},
  {l:'Ok',c:'#16a76b',i:'check_circle',p:'Ok'},
];
function pjEtapas(mod){return mod==='plantio'?ET.map(s=>({l:s.l,c:s.c,i:s.i,p:s.l})):PJ_ET_P}

// Campos de arquivo por módulo. k = chave do campo na tela; doc = código enviado ao Worker.
const PJ_CAMPOS={
  plantio:[
    {k:'exportacao',doc:'exportacao',ext:'zip',rot:'Exportação',rotulo:'Exportação (.zip)'},
    {k:'projeto',doc:'projeto',ext:'dwg',rot:'Projeto',rotulo:'Projeto (.dwg)'},
    {k:'mapa',doc:'projeto',ext:'pdf',rot:'Mapa de Plantio',rotulo:'Mapa de Plantio (.pdf)',opc:true},
  ],
  preparo:[
    {k:'escoamento',doc:'escoamento',ext:'pdf',rot:'Escoamento',rotulo:'Mapa de Escoamento (.pdf)'},
    {k:'projeto',doc:'projeto',ext:'dwg',rot:'Projeto',rotulo:'Projeto (.dwg)'},
    {k:'exportacao',doc:'exportacao',ext:'zip',rot:'Exportação',rotulo:'Exportação (.zip)'},
    {k:'sistematizacao',doc:'sistematizacao',ext:'pdf',rot:'Sistematização',rotulo:'Mapa de Sistematização (.pdf)'},
  ],
};
const PJ_TRAVA_PREPARO=['exportacao','sistematizacao']; // marcar Projeto marca e trava estes dois
const PJ_DOCS_COD={plantio:['exportacao','projeto'],preparo:['escoamento','projeto','exportacao','sistematizacao']};

// Ações por etapa atual (tabela do plano). rpc = projeto_avancar; envio = abre o modal de nova revisão.
const PJ_ACOES={
  plantio:{
    0:{tipo:'rpc',acao:'mapeamento_concluido',txt:'Mapeamento concluído',ico:'check'},
    1:{tipo:'rpc',acao:'iniciar',txt:'Iniciar projeto',ico:'play_arrow'},
    2:{tipo:'envio',txt:'Enviar exportação e projeto',ico:'upload_file',campos:['exportacao','projeto'],acaoDepois:'exportacao_enviada'},
    3:{tipo:'envio',txt:'Enviar Mapa de Plantio',ico:'map',campos:['mapa'],acaoDepois:null},
  },
  preparo:{
    0:{tipo:'rpc',acao:'identificacao',txt:'Confirmar identificação',ico:'check'},
    1:{tipo:'envio',txt:'Enviar Mapa de Escoamento',ico:'water',campos:['escoamento'],acaoDepois:'escoamento'},
    2:{tipo:'rpc',acao:'observacoes',txt:'Confirmar observações',ico:'check'},
    3:{tipo:'envio',txt:'Enviar projeto, exportação e sistematização',ico:'construction',campos:['projeto','exportacao','sistematizacao'],acaoDepois:'preparo'},
  },
};

// Estado da tela. sel: Map 'modulo|cod' -> Set de num (como texto); persiste entre redesenhos.
const PJ={sel:new Map(),ctx:null,tl:{},ok:{},arq:{},desf:null,drag:null};

function pjKey(mod,cod){return mod+'|'+cod}
function pjAlvo(c){return {modulo:c.mod,cod:String(c.cod)}}
function pjNTal(n){return n===1?'1 talhão':n+' talhões'}
// O banco devolve talhão como número ou {talhao,tipo} e documento como código ou {codigo,nome}.
function pjNumTal(x){return x&&typeof x==='object'?(x.talhao??x.num):x}
function pjCodDoc(x){return x&&typeof x==='object'?x.codigo:x}
function pjNorm(mod,f){
  if(!f||!Array.isArray(f.tals))return null;
  return {modulo:mod,cod:Number(f.cod),nome:f.n,ha:f.ha,obs:f.obs||'',
    talhoes:f.tals.map(t=>({num:t.num,ha:t.ha,e:Number(t.e)||0,sist_conser:t.sist_conser,mes:t.mes,cons:t.cons,mapeamento:t.mapeamento})),etapas:pjEtapas(mod)};
}
function pjContagens(fz){
  const c=Array(fz.etapas.length).fill(0);
  fz.talhoes.forEach(t=>{if(t.e>=0&&t.e<c.length)c[t.e]++});
  return c;
}
function pjSel(key){
  if(!PJ.sel.has(key))PJ.sel.set(key,new Set());
  return PJ.sel.get(key);
}
function pjSelHas(key,num){const s=PJ.sel.get(key);return !!s&&s.has(String(num))}
// Talhões da etapa i que a ação vale: os selecionados nela ou, sem seleção, todos dela.
function pjUsados(fz,key,i){
  const grupo=fz.talhoes.filter(t=>t.e===i);
  const selG=grupo.filter(t=>pjSelHas(key,t.num));
  return selG.length?selG:grupo;
}
// Posição da alça: etapa mais avançada entre os selecionados (ou entre todos).
function pjAtual(fz,key){
  const s=PJ.sel.get(key);
  const base=(s&&s.size)?fz.talhoes.filter(t=>s.has(String(t.num))):fz.talhoes;
  return base.length?Math.max(...base.map(t=>t.e)):0;
}
function pjVal(d,chave){
  if(Array.isArray(d))d=d[0];
  if(d&&typeof d==='object'&&chave)return d[chave];
  return d;
}
async function pjChamar(btn,fn,args,opc={}){
  const fim=btn?pjMo().ocupado(btn):()=>{};
  let ok=false;
  try{
    const r=await sb.rpc(fn,args);
    if(r.error)throw new Error(r.error.message||'Erro ao gravar');
    ok=true;
    return r.data;
  }catch(e){
    if(!opc.silencioso)showToast(e.message||'Erro ao gravar');
    throw e;
  }finally{fim(ok)}
}

// ── Revisões (D3) ─────────────────────────────────────────────
function pjMaxRev(mod,cod){
  let max=-1;
  PJ_DOCS_COD[mod].forEach(d=>revisoesDe(mod,cod,d).forEach(r=>{if(r.numero>max)max=r.numero}));
  return max;
}
// Revisão mais recente da linha do tempo (evento 'revisao' de maior número).
function pjUltimaRev(tl){
  const revs=tl.filter(e=>e.tipo==='revisao');
  if(!revs.length)return null;
  return revs.reduce((a,b)=>(Number(b.detalhe&&b.detalhe.numero)||0)>(Number((a.detalhe&&a.detalhe.numero))||0)?b:a);
}
// Essa revisão já tem o campo? O mapa é detalhe.mapa (vem do banco).
function pjRevTem(rev,cp){
  const d=rev.detalhe||{};
  if(cp.k==='mapa')return d.mapa===true;
  const docs=(d.documentos||(d.documento?[d.documento]:[])).map(pjCodDoc);
  return docs.includes(cp.doc);
}
function pjEfetivos(M){
  const s=new Set(M.marc);
  if(M.mod==='preparo'&&s.has('projeto'))PJ_TRAVA_PREPARO.forEach(k=>s.add(k));
  return s;
}
function pjTalNums(M){return M.talhoes.filter(t=>M.talMarcados.has(String(t.num))).map(t=>t.num)}
// Completa a revisão aberta (L2/D3): os talhões escolhidos já estão na revisão mais recente e
// nenhum dos campos marcados está nela. Aí o envio vai para ela, sem abrir outra.
function pjCompleta(M){
  if(!M.acao||!M.ult)return false;
  const sel=pjTalNums(M).map(String);
  if(!sel.length)return false;
  const na=((M.ult.detalhe&&M.ult.detalhe.talhoes)||[]).map(x=>String(pjNumTal(x)));
  if(!sel.every(n=>na.includes(n)))return false;
  return [...pjEfetivos(M)].every(k=>!pjRevTem(M.ult,M.campos.find(c=>c.k===k)));
}

// ── Linha do tempo (D5) ───────────────────────────────────────
async function pjTLDados(mod,cod,key){
  if(PJ.tl[key])return PJ.tl[key];
  const d=await pjChamar(null,'projeto_linha_do_tempo',{p_modulo:mod,p_cod_faz:cod},{silencioso:true});
  PJ.tl[key]=Array.isArray(d)?d:[];
  return PJ.tl[key];
}
async function pjTL(raiz,key,mod,cod){
  const box=raiz.querySelector('.pj-tl');
  if(!box)return;
  if(PJ.tl[key]){box.innerHTML=pjTLHtml(PJ.tl[key]);return}
  box.innerHTML='<div class="pj-carreg">Carregando histórico…</div>';
  pjMo().carregando(box);
  try{
    const ev=await pjTLDados(mod,cod,key);
    if(!box.isConnected)return;
    box.innerHTML=pjTLHtml(ev);
    pjMo().pronto(box);
  }catch(e){
    if(!box.isConnected)return;
    box.innerHTML='<div class="pj-erro">Não foi possível carregar a linha do tempo.</div><button type="button" class="btn-retro" data-pj-tl-retry>Tentar de novo</button>';
  }
}
const PJ_ICO_EV={avanco:'trending_up',retrocesso:'undo',desfazer:'restore',revisao:'description',arquivo:'upload_file'};
const PJ_NOME_DOC={exportacao:'Exportação',projeto:'Projeto',escoamento:'Escoamento',sistematizacao:'Sistematização',mapa:'Mapa'};
function pjTLHtml(ev){
  if(!Array.isArray(ev)||!ev.length)return '<div class="pj-vazio">Nenhum evento ainda</div>';
  // Lista vem do mais novo para o mais antigo: o primeiro retrocesso é o último da fazenda.
  const ultRetro=ev.find(x=>x.tipo==='retrocesso');
  const mostraDesf=!!ultRetro&&!(ultRetro.detalhe&&ultRetro.detalhe.desfeito)&&!!(ultRetro.detalhe&&ultRetro.detalhe.lote_id);
  return '<ol class="pj-tl-l">'+ev.map(x=>{
    const d=x.detalhe||{};
    // Revisão traz talhoes:[{talhao,tipo}]; avanço e retrocesso trazem só mudancas:[{talhao,...}].
    const tals=(Array.isArray(d.talhoes)?d.talhoes:Array.isArray(d.mudancas)?[...new Set(d.mudancas.map(m=>m.talhao).filter(n=>n!=null))].sort((a,b)=>a-b):[]).map(pjNumTal);
    const docs=(d.documentos||(d.documento?[d.documento]:[])).map(c=>(c&&typeof c==='object'&&c.nome)||PJ_NOME_DOC[pjCodDoc(c)]||pjCodDoc(c));
    const rev=(x.tipo==='revisao'&&d.numero!=null)?` <span class="ebadge">Rev${pjH(d.numero)}</span>`:'';
    const just=d.justificativa||d.motivo;
    const btn=(x===ultRetro&&mostraDesf)?`<button type="button" class="btn-retro" data-pj-tl-desf="${Number(d.lote_id)}">Desfazer</button>`:'';
    return `<li class="pj-ev pj-ev-${pjH(x.tipo)}"><span class="pj-ev-ico"><span class="ico">${PJ_ICO_EV[x.tipo]||'circle'}</span></span>`+
      `<div class="pj-ev-b"><div class="pj-ev-t">${pjH(x.texto)}${rev}</div>`+
      (just?`<div class="pj-ev-j">“${pjH(just)}”</div>`:'')+
      (tals.length?`<div class="pj-chips">${tals.map(t=>`<span class="pj-chip-t">${pjH(t)}</span>`).join('')}</div>`:'')+
      (docs.length?`<div class="pj-ev-docs">${docs.map(t=>`<span>${pjH(t)}</span>`).join('')}</div>`:'')+
      `<div class="pj-ev-q">${pjH(x.quem)} · ${pjH(fmtDataHora(x.em))}</div></div>${btn}</li>`;
  }).join('')+'</ol>';
}

// ── Barra e painel ────────────────────────────────────────────
function pjRedesenhar(){
  const c=PJ.ctx;
  if(!c)return;
  c.raiz.innerHTML=Proj.painelHtml(c.mod,c.f,PJ.arq[c.key]);
  pjTL(c.raiz,c.key,c.mod,c.cod);
}
function pjSelEtapa(i){
  const c=PJ.ctx;
  const grupo=c.fz.talhoes.filter(t=>t.e===i);
  const s=pjSel(c.key);
  const todos=grupo.length>0&&grupo.every(t=>s.has(String(t.num)))&&s.size===grupo.length;
  s.clear();
  if(!todos)grupo.forEach(t=>s.add(String(t.num)));
  pjRedesenhar();
}
async function pjAcaoRpc(btn,acao,idx){
  const c=PJ.ctx;
  const nums=pjUsados(c.fz,c.key,idx).map(t=>t.num);
  if(acao==='observacoes'){pjAbrirObs(c,idx,nums);return}
  try{
    const d=await pjChamar(btn,'projeto_avancar',{p_modulo:c.mod,p_cod_faz:c.cod,p_acao:acao,p_talhoes:nums});
    delete PJ.tl[c.key];
    showToast(`${pjNTal(Number(pjVal(d))||nums.length)} avançaram`);
    await recarregar(pjAlvo(c));
  }catch(e){}
}
async function pjDesfazer(btn,lote,alvo){
  const volta=PJ.desf&&PJ.desf.lote===lote?PJ.desf:null;
  try{
    const d=await pjChamar(btn,'projeto_desfazer',{p_lote_id:lote});
    PJ.desf=null;
    delete PJ.tl[pjKey(alvo.modulo,alvo.cod)];
    showToast(`Retrocesso desfeito: ${pjNTal(Number(pjVal(d))||0)} voltaram à etapa anterior`);
    await recarregar(alvo);
    // a barra anda de volta: da etapa do retrocesso para a de antes
    const barra=PJ.ctx&&PJ.ctx.raiz.querySelector('.pj-stp');
    if(barra&&volta&&volta.de)pjMo().etapa(barra,volta.para,volta.de,{cor:volta.cor});
  }catch(e){}
}

// Observações (Preparo): a ação pede o texto da observação recebida (A3, p_observacao). Opcional.
function pjModalObs(){
  let m=document.getElementById('pj-modal-obs');
  if(m)return m;
  m=document.createElement('div');
  m.id='pj-modal-obs';
  m.className='modal-fundo off pj-modal';
  m.innerHTML=`<div class="modal-caixa pj-caixa" role="dialog" aria-modal="true" aria-labelledby="pj-obs-t">`+
    `<div class="modal-t" id="pj-obs-t">Confirmar observações</div>`+
    `<div class="pj-volta-txt" data-pj-obs-txt></div>`+
    `<div class="envio-nota-rot">Observações recebidas (opcional)</div>`+
    `<textarea class="prep-obs-area" data-pj-obs placeholder="Observações de campo"></textarea>`+
    `<div class="pj-erro" data-pj-obs-erro role="alert"></div>`+
    `<div class="modal-botoes"><button type="button" class="btn-retro" data-pj-fechar>Cancelar</button>`+
    `<button type="button" class="btn-acao" data-pj-obs-ok>Confirmar</button></div></div>`;
  document.body.appendChild(m);
  m.addEventListener('click',e=>{
    if(e.target===m||e.target.closest('[data-pj-fechar]'))return pjFecharModal(m);
    const ok=e.target.closest('[data-pj-obs-ok]');
    if(ok)pjConfirmarObs(ok,m);
  });
  m.addEventListener('keydown',e=>{if(e.key==='Escape')pjFecharModal(m)});
  return m;
}
function pjAbrirObs(c,idx,nums){
  const m=pjModalObs();
  m._V={c,idx,nums};
  m._busy=false;
  m.querySelector('[data-pj-obs-txt]').innerHTML=`<strong>${pjNTal(nums.length)}</strong> passam para <strong>${pjH(c.fz.etapas[idx+1].l)}</strong>.`;
  const ta=m.querySelector('[data-pj-obs]');
  ta.value=c.fz.obs||'';
  m.querySelector('[data-pj-obs-erro]').textContent='';
  m.classList.remove('off');
  setTimeout(()=>ta.focus(),50);
}
async function pjConfirmarObs(btn,m){
  const V=m._V,c=V.c;
  const obs=m.querySelector('[data-pj-obs]').value.trim();
  const err=m.querySelector('[data-pj-obs-erro]');
  err.textContent='';
  m._busy=true;
  try{
    const d=await pjChamar(btn,'projeto_avancar',{p_modulo:c.mod,p_cod_faz:c.cod,p_acao:'observacoes',p_talhoes:V.nums,p_observacao:obs||null},{silencioso:true});
    m._busy=false;
    m.classList.add('off');
    delete PJ.tl[c.key];
    showToast(`${pjNTal(Number(pjVal(d))||V.nums.length)} avançaram`);
    await recarregar(pjAlvo(c));
  }catch(e){
    m._busy=false;
    err.textContent=e.message||'Não foi possível confirmar.';
  }
}

// Retroceder: alça ou clique numa etapa anterior. Abre a justificativa; depois, aviso com Desfazer.
function pjVolta(idx){
  const c=PJ.ctx;
  if(!c)return;
  const sel=PJ.sel.get(c.key);
  const base=(sel&&sel.size)?c.fz.talhoes.filter(t=>sel.has(String(t.num))):c.fz.talhoes;
  const nums=base.filter(t=>t.e>idx).map(t=>t.num);
  if(!nums.length){
    showToast(`Nenhum talhão ${sel&&sel.size?'selecionado ':''}está depois de ${c.fz.etapas[idx].l}.`);
    return;
  }
  pjAbrirVolta(c,idx,nums);
}
function pjModalVolta(){
  let m=document.getElementById('pj-modal-volta');
  if(m)return m;
  m=document.createElement('div');
  m.id='pj-modal-volta';
  m.className='modal-fundo off pj-modal';
  m.innerHTML=`<div class="modal-caixa pj-caixa" role="dialog" aria-modal="true" aria-labelledby="pj-volta-t">`+
    `<div class="modal-t" id="pj-volta-t">Retroceder etapa</div>`+
    `<div class="pj-volta-txt" data-pj-volta-txt></div>`+
    `<div class="envio-nota-rot">Justificativa (obrigatória)</div>`+
    `<textarea class="prep-obs-area" data-pj-just placeholder="Ex.: linhas deslocadas, projeto refeito"></textarea>`+
    `<div class="pj-erro" data-pj-volta-erro role="alert"></div>`+
    `<div class="modal-botoes"><button type="button" class="btn-retro" data-pj-fechar>Cancelar</button>`+
    `<button type="button" class="btn-acao pj-btn-perigo" data-pj-volta-ok>Voltar</button></div></div>`;
  document.body.appendChild(m);
  m.addEventListener('click',e=>{
    if(e.target===m||e.target.closest('[data-pj-fechar]'))return pjFecharModal(m);
    const ok=e.target.closest('[data-pj-volta-ok]');
    if(ok)pjConfirmarVolta(ok,m);
  });
  m.addEventListener('keydown',e=>{if(e.key==='Escape')pjFecharModal(m)});
  return m;
}
function pjAbrirVolta(c,idx,nums){
  const m=pjModalVolta();
  m._V={c,idx,nums};
  m._busy=false;
  m.querySelector('[data-pj-volta-txt]').innerHTML=`<strong>${pjNTal(nums.length)}</strong> voltam para <strong>${pjH(c.fz.etapas[idx].l)}</strong>.`+
    (c.mod==='plantio'&&idx===0?' Isso também volta o mapeamento para "Não".':'');
  const ta=m.querySelector('[data-pj-just]');
  ta.value='';
  m.querySelector('[data-pj-volta-erro]').textContent='';
  m.classList.remove('off');
  setTimeout(()=>ta.focus(),50);
}
async function pjConfirmarVolta(btn,m){
  const V=m._V,c=V.c;
  const just=m.querySelector('[data-pj-just]').value.trim();
  const err=m.querySelector('[data-pj-volta-erro]');
  if(!just){err.textContent='Escreva a justificativa.';return}
  err.textContent='';
  m._busy=true;
  const alvo=c.fz.etapas[V.idx];
  const de=c.fz.etapas[pjAtual(c.fz,c.key)];
  let lote=null;
  try{
    const d=await pjChamar(btn,'projeto_retroceder',{p_modulo:c.mod,p_cod_faz:c.cod,p_para:alvo.p,p_justificativa:just,p_talhoes:V.nums},{silencioso:true});
    lote=pjVal(d,'lote_id');
    m._busy=false;
    m.classList.add('off');
  }catch(e){
    m._busy=false;
    err.textContent=e.message||'Não foi possível retroceder.';
    return;
  }
  const ate=Date.now()+15000;
  PJ.desf={key:c.key,lote,n:V.nums.length,para:alvo.l,de:de.l,cor:de.c,ate};
  setTimeout(()=>{
    if(PJ.desf&&PJ.desf.lote===lote){
      PJ.desf=null;
      document.querySelectorAll('.pj-desf').forEach(x=>x.remove());
    }
  },15000);
  delete PJ.tl[c.key];
  showToast(`${pjNTal(V.nums.length)} voltaram para ${alvo.l}`);
  await recarregar(pjAlvo(c));
  const barra=PJ.ctx&&PJ.ctx.raiz.querySelector('.pj-stp');
  if(barra)pjMo().etapa(barra,de.l,alvo.l,{cor:alvo.c});
}

// ── Modal Nova revisão (D3, pj-modal-rev) ─────────────────────
function pjFecharModal(m){
  if(m._busy)return;
  m.classList.add('off');
}
function pjModalRev(){
  let m=document.getElementById('pj-modal-rev');
  if(m)return m;
  m=document.createElement('div');
  m.id='pj-modal-rev';
  m.className='modal-fundo off pj-modal';
  m.innerHTML=`<div class="modal-caixa pj-caixa" role="dialog" aria-modal="true" aria-labelledby="pj-rev-t">`+
    `<div class="modal-t" id="pj-rev-t"></div>`+
    `<div data-pj-corpo></div>`+
    `<div class="pj-prog" data-pj-prog hidden><div class="pj-prog-b"></div></div>`+
    `<div class="pj-erro" data-pj-rev-erro role="alert"></div>`+
    `<div class="modal-botoes"><button type="button" class="btn-retro" data-pj-fechar>Cancelar</button>`+
    `<button type="button" class="btn-acao" data-pj-rev-ok>Enviar</button></div></div>`;
  document.body.appendChild(m);
  pjLigarModal(m);
  return m;
}
function pjLigarModal(m){
  m.addEventListener('click',e=>{
    const M=m._M,t=e.target;
    if(t===m||t.closest('[data-pj-fechar]'))return pjFecharModal(m);
    const ok=t.closest('[data-pj-rev-ok]');
    if(ok)return pjConfirmarRev(ok);
    const slot=t.closest('[data-pj-slot]');
    if(slot&&t.tagName!=='INPUT'&&M&&!M.iniciado)slot.querySelector('input').click();
  });
  m.addEventListener('keydown',e=>{if(e.key==='Escape')pjFecharModal(m)});
  m.addEventListener('change',e=>{
    const M=m._M,t=e.target;
    if(!M||M.iniciado)return;
    if(t.dataset.pjCampo){
      const k=t.dataset.pjCampo;
      if(t.checked){
        M.marc.add(k);
        if(M.mod==='preparo'&&k==='projeto')PJ_TRAVA_PREPARO.forEach(x=>M.marc.add(x));
      }else M.marc.delete(k);
      M.erroMsg='';
      pjRenderRev(m);
    }else if(t.dataset.pjTal){
      const s=t.dataset.pjTal;
      if(t.checked)M.talMarcados.add(s);else M.talMarcados.delete(s);
      pjRenderRev(m);
    }else if(t.dataset.pjArq){
      pjDefArquivo(M,t.dataset.pjArq,t.files[0]);
      pjRenderRev(m);
    }
  });
  m.addEventListener('input',e=>{
    if(e.target.matches('[data-pj-motivo]')&&m._M)m._M.motivo=e.target.value;
  });
  m.addEventListener('dragover',e=>{if(e.target.closest('[data-pj-slot]'))e.preventDefault()});
  m.addEventListener('drop',e=>{
    const slot=e.target.closest('[data-pj-slot]'),M=m._M;
    if(!slot||!M||M.iniciado)return;
    e.preventDefault();
    const f=e.dataTransfer.files[0];
    if(!f)return;
    pjDefArquivo(M,slot.dataset.pjSlot,f);
    pjRenderRev(m);
  });
}
function pjDefArquivo(M,k,f){
  const cp=M.campos.find(c=>c.k===k);
  if(!f){delete M.arquivos[k];M.erroMsg='';return}
  if(!f.name.toLowerCase().endsWith('.'+cp.ext)){
    delete M.arquivos[k];
    M.erroMsg=`${cp.rotulo}: selecione um arquivo .${cp.ext}.`;
    return;
  }
  M.arquivos[k]=f;
  M.erroMsg='';
}
async function pjAbrirRev(acaoIdx){
  const c=PJ.ctx,fz=c.fz,campos=PJ_CAMPOS[c.mod];
  let tl;
  try{tl=await pjTLDados(c.mod,c.cod,c.key)}
  catch(e){showToast('Não foi possível carregar o histórico do projeto. Tente de novo.');return}
  const acao=(acaoIdx==null)?null:(PJ_ACOES[c.mod][acaoIdx]||null);
  const acaoTal=acao?pjUsados(fz,c.key,acaoIdx):[];
  const M={mod:c.mod,cod:c.cod,key:c.key,campos,talhoes:fz.talhoes,etapas:fz.etapas,
    limNovo:c.mod==='plantio'?3:4,acao,acaoIdx,
    acaoTal:acaoTal.map(t=>t.num),
    etapaNome:acao?fz.etapas[acaoIdx].l:'',
    talMarcados:new Set(acaoTal.map(t=>String(t.num))),
    trav:new Set(acaoTal.map(t=>String(t.num))),
    marc:new Set(acao?acao.campos:[]),
    ult:pjUltimaRev(tl),maxDoc:pjMaxRev(c.mod,c.cod),
    motivo:'',arquivos:{},enviados:new Set(),revCriada:false,revNumero:null,avancou:false,
    iniciado:false,enviando:false,erroMsg:''};
  M.proxNumero=M.maxDoc+1;
  const m=pjModalRev();
  m._M=M;
  m._busy=false;
  pjRenderRev(m);
  m.classList.remove('off');
}
function pjSlotHtml(cp,f){
  const nome=f?`${pjH(f.name)} · ${(f.size/1048576).toFixed(1)} MB`:'Nenhum arquivo · arraste aqui ou clique';
  return `<div class="arq-slot pj-slot${f?' ok':''}" data-pj-slot="${cp.k}">`+
    `<div class="arq-tipo ${pjH(cp.ext)}">${pjH(cp.ext.toUpperCase())}</div>`+
    `<div class="arq-slot-txt"><div class="arq-slot-rot">${pjH(cp.rot)}</div><div class="arq-slot-nome">${nome}</div></div>`+
    `<span class="arq-slot-btn">${f?'Trocar':'Escolher'}</span>`+
    `<input type="file" accept=".${pjH(cp.ext)}" data-pj-arq="${cp.k}" hidden></div>`;
}
function pjRenderRev(m){
  const M=m._M;
  const ef=pjEfetivos(M),comp=pjCompleta(M);
  const num=comp?Number(M.ult.detalhe.numero):(M.revNumero!=null?M.revNumero:M.proxNumero);
  m.querySelector('#pj-rev-t').textContent=comp?`Completar Rev${num}`:`Nova revisão · Rev${num}`;
  const bloq=M.iniciado;
  const docs=M.campos.map(cp=>{
    const on=ef.has(cp.k);
    const travado=M.mod==='preparo'&&PJ_TRAVA_PREPARO.includes(cp.k)&&ef.has('projeto');
    return `<div class="pj-doc${on?' on':''}"><label class="pj-doc-h">`+
      `<input type="checkbox" data-pj-campo="${cp.k}"${on?' checked':''}${(bloq||travado)?' disabled':''}>`+
      `<span>${pjH(cp.rotulo)}</span>`+
      (cp.opc?'<span class="pj-opc">opcional</span>':'')+
      (travado?'<span class="pj-opc">junto com o projeto</span>':'')+
      (M.enviados.has(cp.k)?'<span class="pj-ok-t">enviado</span>':'')+
      `</label>${on?pjSlotHtml(cp,M.arquivos[cp.k]):''}</div>`;
  }).join('');
  const sel=M.talhoes.filter(t=>M.talMarcados.has(String(t.num)));
  const nov=sel.filter(t=>t.e<M.limNovo).length,alt=sel.length-nov;
  const mapa=ef.has('mapa');
  const partes=[];
  if(nov)partes.push(`${nov} ${nov>1?'novos seguem':'novo segue'} o fluxo normal.`);
  if(alt){
    if(M.mod==='plantio')partes.push(mapa?`${alt} ${alt>1?'alterados ficam':'alterado fica'} Ok com o mapa.`:`${alt} ${alt>1?'alterados voltam':'alterado volta'} para Ag. Mapa até o mapa novo.`);
    else partes.push(`${alt} ${alt>1?'alterados não mudam':'alterado não muda'} de etapa.`);
  }
  let efeito=sel.length?partes.join(' '):'Nenhuma etapa muda.';
  if(comp)efeito+=' Completa a revisão aberta, sem nova numeração.';
  const chips=M.talhoes.map(t=>{
    const s=String(t.num),on=M.talMarcados.has(s),trav=M.trav.has(s),novo=t.e<M.limNovo;
    return `<label class="pj-chip${on?' on':''}${trav?' trav':''}"><input type="checkbox" data-pj-tal="${pjH(s)}"${on?' checked':''}${(trav||bloq)?' disabled':''}>`+
      `<span>${pjH(s)}</span><em class="pj-tag ${novo?'novo':'alt'}">${novo?'novo':'alterado'}</em></label>`;
  }).join('');
  const motivoObr=!comp&&M.maxDoc>=0;
  const dica=M.acao?`<div class="pj-dica">Aberta pela etapa ${pjH(M.etapaNome)}: ${pjNTal(M.acaoTal.length)} marcado${M.acaoTal.length>1?'s':''} e travado${M.acaoTal.length>1?'s':''}.</div>`:'';
  m.querySelector('[data-pj-corpo]').innerHTML=
    `<div class="pj-sec"><div class="envio-nota-rot">Documentos que mudam</div>${docs}</div>`+
    `<div class="pj-sec"><div class="envio-nota-rot">Talhões que chegam ou mudam</div>${dica}`+
    `<div class="pj-chips-w">${chips}</div><div class="pj-efeito">${pjH(efeito)}</div></div>`+
    `<div class="pj-sec"><div class="envio-nota-rot">${motivoObr?'Motivo da revisão (obrigatório)':'Motivo (opcional)'}</div>`+
    `<textarea class="prep-obs-area pj-motivo" data-pj-motivo placeholder="${motivoObr?'Ex.: projeto refeito após vistoria':'Opcional'}"${bloq?' disabled':''}>${pjH(M.motivo)}</textarea></div>`;
  m.querySelector('[data-pj-prog]').hidden=!M.enviando;
  m.querySelector('[data-pj-rev-erro]').textContent=M.erroMsg||'';
  const ok=m.querySelector('[data-pj-rev-ok]');
  ok.disabled=M.enviando;
  ok.textContent=M.enviando?'Enviando…':(M.erroMsg&&M.iniciado?'Tentar de novo':'Enviar');
  const cor=M.mod==='plantio'?'#16a76b':PJ_COR_P;
  ok.style.background=cor;
  ok.style.boxShadow=`0 6px 20px ${cor}44`;
}
function pjProgresso(el,total){
  const t=total||1;
  const mo=pjMo().progresso(el,{total:t});
  const fill=el&&el.querySelector('.pj-prog-b');
  return {
    atualizar(b){mo.atualizar(b);if(fill)fill.style.width=Math.min(100,b/t*100)+'%'},
    fim(ok){mo.fim(ok);if(fill&&ok)fill.style.width='100%'},
  };
}
// POST /enviar por documento, nova=0 (L2: cai na revisão aberta/mais recente do projeto).
// dwg+pdf do Plantio vão no mesmo POST, como dois campos 'arquivo'.
function pjUpload(M,doc,cps,token,onBytes){
  const rot=cps.map(c=>c.rotulo).join(' + ');
  const fd=new FormData();
  fd.append('modulo',M.mod);
  fd.append('cod_faz',String(M.cod));
  fd.append('documento',doc);
  fd.append('nova','0');
  const motivo=M.motivo.trim();
  if(motivo)fd.append('motivo',motivo);
  cps.forEach(cp=>{const f=M.arquivos[cp.k];fd.append('arquivo',f,f.name)});
  if(WORKER_URL==='demo'&&window.pjEnvioSimulado)return window.pjEnvioSimulado(fd,onBytes);
  return new Promise((ok,falha)=>{
    const x=new XMLHttpRequest();
    x.open('POST',WORKER_URL+'/enviar');
    x.setRequestHeader('Authorization','Bearer '+token);
    x.upload.onprogress=e=>{if(e.lengthComputable)onBytes(e.loaded)};
    x.onload=()=>{
      if(x.status>=200&&x.status<300)return ok();
      let corpo={};
      try{corpo=JSON.parse(x.responseText)||{}}catch(_){}
      falha(new Error(`${rot}: ${corpo.erro||'erro '+x.status}`));
    };
    x.onerror=()=>falha(new Error(`${rot}: falha de conexão com o envio`));
    x.send(fd);
  });
}
async function pjConfirmarRev(btn){
  const m=document.getElementById('pj-modal-rev'),M=m._M;
  if(!M||m._busy)return;
  const ef=pjEfetivos(M);
  if(!M.iniciado){
    let erro='';
    if(!ef.size)erro='Marque ao menos um documento.';
    else for(const k of ef){
      const cp=M.campos.find(c=>c.k===k),f=M.arquivos[k];
      if(!f){erro=`${cp.rotulo}: selecione o arquivo.`;break}
      if(!f.name.toLowerCase().endsWith('.'+cp.ext)){erro=`${cp.rotulo}: selecione um arquivo .${cp.ext}.`;break}
    }
    if(!erro&&!pjCompleta(M)&&M.maxDoc>=0&&!M.motivo.trim())erro='Informe o motivo da revisão.';
    if(erro){M.erroMsg=erro;pjRenderRev(m);return}
  }
  M.iniciado=true;M.enviando=true;m._busy=true;M.erroMsg='';
  pjRenderRev(m);
  const fim=pjMo().ocupado(btn);
  const prog=m.querySelector('[data-pj-prog]');
  let pr=null,sucesso=false,comp=false;
  try{
    comp=pjCompleta(M);
    if(!M.revCriada){
      if(comp){M.revCriada=true;M.revNumero=Number(M.ult.detalhe.numero)}
      else{
        const docs=[...new Set([...ef].map(k=>M.campos.find(c=>c.k===k).doc))];
        const d=await pjChamar(null,'projeto_nova_revisao',{p_modulo:M.mod,p_cod_faz:M.cod,p_motivo:M.motivo.trim()||null,p_documentos:docs,p_talhoes:pjTalNums(M)},{silencioso:true});
        M.revNumero=Number(pjVal(d,'numero'));
        M.revCriada=true;
      }
    }
    const token=(await sb.auth.getSession()).data?.session?.access_token;
    if(WORKER_URL.startsWith('__'))throw new Error('O serviço de envio de arquivos ainda não foi configurado.');
    const grupos=new Map();
    ef.forEach(k=>{
      if(M.enviados.has(k))return;
      const cp=M.campos.find(c=>c.k===k);
      if(!grupos.has(cp.doc))grupos.set(cp.doc,[]);
      grupos.get(cp.doc).push(cp);
    });
    const total=[...grupos.values()].flat().reduce((s,cp)=>s+M.arquivos[cp.k].size,0);
    pr=pjProgresso(prog,total);
    let base=0;
    for(const [doc,cps] of grupos){
      const tam=cps.reduce((s,cp)=>s+M.arquivos[cp.k].size,0),b0=base;
      await pjUpload(M,doc,cps,token,b=>pr.atualizar(b0+b));
      base+=tam;
      cps.forEach(cp=>M.enviados.add(cp.k));
    }
    pr.fim(true);
    if(M.acao&&M.acao.acaoDepois&&!M.avancou){
      // Novos talhões andam pelo avanço depois do envio (L7): um envio que falha não deixa talhão adiantado.
      await pjChamar(null,'projeto_avancar',{p_modulo:M.mod,p_cod_faz:M.cod,p_acao:M.acao.acaoDepois,p_talhoes:M.acaoTal},{silencioso:true});
      M.avancou=true;
    }
    sucesso=true;
  }catch(e){
    if(pr)pr.fim(false);
    M.enviando=false;m._busy=false;
    M.erroMsg=e.message||'Erro ao enviar.';
    pjRenderRev(m);
  }finally{
    fim(sucesso);
  }
  if(!sucesso)return;
  M.enviando=false;m._busy=false;
  m.classList.add('off');
  delete PJ.tl[M.key];
  showToast(comp?`Arquivos enviados à Rev${M.revNumero}`:`Rev${M.revNumero} aberta com os arquivos`);
  await recarregar({modulo:M.mod,cod:String(M.cod)});
}

// ── Ligação de eventos (uma vez por raiz) ────────────────────
function pjLigar(raiz){
  if(raiz._pjLigado)return;
  raiz._pjLigado=true;
  raiz.addEventListener('click',e=>{
    const c=PJ.ctx;
    if(!c||c.raiz!==raiz)return;
    const t=e.target;
    let el;
    if((el=t.closest('[data-pj-rpc]')))return pjAcaoRpc(el,el.dataset.pjRpc,Number(el.dataset.pjIdx));
    if((el=t.closest('[data-pj-envio]')))return pjAbrirRev(Number(el.dataset.pjEnvio));
    if(t.closest('[data-pj-nova]'))return pjAbrirRev(null);
    if((el=t.closest('[data-pj-etapa]')))return pjSelEtapa(Number(el.dataset.pjEtapa));
    if((el=t.closest('[data-pj-no]')))return pjVolta(Number(el.dataset.pjNo));
    if((el=t.closest('[data-pj-desfazer]')))return pjDesfazer(el,Number(el.dataset.pjDesfazer),pjAlvo(c));
    if((el=t.closest('[data-pj-tl-desf]')))return pjDesfazer(el,Number(el.dataset.pjTlDesf),pjAlvo(c));
    if(t.closest('[data-pj-tl-retry]')){delete PJ.tl[c.key];return pjTL(raiz,c.key,c.mod,c.cod)}
  });
  raiz.addEventListener('change',e=>{
    const c=PJ.ctx;
    if(!c||c.raiz!==raiz)return;
    const t=e.target;
    if(t.matches('.pj-tal-chk')){
      const s=pjSel(c.key);
      if(t.checked)s.add(t.dataset.pjNum);else s.delete(t.dataset.pjNum);
      pjRedesenhar();
    }else if(t.matches('.pj-todos')){
      const s=pjSel(c.key);
      s.clear();
      if(t.checked)c.fz.talhoes.forEach(x=>s.add(String(x.num)));
      pjRedesenhar();
    }
  });
  raiz.addEventListener('keydown',e=>{
    const c=PJ.ctx;
    if(!c||c.raiz!==raiz)return;
    if(e.key==='ArrowLeft'&&e.target.closest('.pj-alca')){
      const a=pjAtual(c.fz,c.key);
      if(a>0){e.preventDefault();pjVolta(a-1)}
    }
  });
  // Alça: arrasta só para trás. Solta numa etapa anterior -> justificativa.
  raiz.addEventListener('pointerdown',e=>{
    const al=e.target.closest('.pj-alca');
    if(!al||e.button>0)return;
    const c=PJ.ctx;
    const row=al.closest('.stp-row');
    const nodes=[...row.querySelectorAll('.snode')];
    const de=pjAtual(c.fz,c.key);
    PJ.drag={al,nodes,de,alvo:de};
    al.setPointerCapture(e.pointerId);
    al.classList.add('arrastando');
    e.preventDefault();
  });
  raiz.addEventListener('pointermove',e=>{
    const g=PJ.drag;
    if(!g)return;
    const xs=g.nodes.map(n=>{const b=n.getBoundingClientRect();return b.left+b.width/2});
    let alvo=g.de,dist=Infinity;
    xs.forEach((x,i)=>{
      if(i>g.de)return;
      const d=Math.abs(e.clientX-x);
      if(d<dist){dist=d;alvo=i}
    });
    g.alvo=alvo;
    g.nodes.forEach((n,i)=>n.classList.toggle('alvo',i===alvo&&alvo<g.de));
    const lo=xs[0]-xs[g.de];
    const dx=Math.max(lo,Math.min(0,e.clientX-xs[g.de]));
    g.al.style.transform=`translateX(${dx}px)`;
  });
  const fimArrasto=()=>{
    const g=PJ.drag;
    if(!g)return;
    PJ.drag=null;
    g.al.classList.remove('arrastando');
    g.al.style.transform='';
    g.nodes.forEach(n=>n.classList.remove('alvo'));
    if(g.alvo<g.de)pjVolta(g.alvo);
  };
  raiz.addEventListener('pointerup',fimArrasto);
  raiz.addEventListener('pointercancel',fimArrasto);
}

// ── API pública ──────────────────────────────────────────────
window.Proj={
  fazenda(mod,f){return pjNorm(mod,f)},

  distribuicaoHtml(mod,f){
    const fz=pjNorm(mod,f);
    if(!fz)return '';
    const c=pjContagens(fz),tot=fz.talhoes.length,ok=c[fz.etapas.length-1];
    const segs=c.map((q,i)=>q?`<span class="pj-dseg" style="flex:${q};background:${fz.etapas[i].c}" title="${pjH(fz.etapas[i].l)}: ${q}"></span>`:'').join('');
    return `<div class="pj-dcard"><div class="pj-dist pj-dist-s" aria-hidden="true">${segs}</div><div class="pj-dtxt">${ok}/${tot} Ok</div></div>`;
  },

  painelHtml(mod,f,htmlArq){
    const fz=pjNorm(mod,f);
    if(!fz)return '';
    const key=pjKey(mod,fz.cod),edit=podeEditar(mod),et=fz.etapas,n=et.length;
    const cont=pjContagens(fz),tot=fz.talhoes.length,ok=cont[n-1];
    PJ.arq[key]=htmlArq;
    const sel=pjSel(key),atual=pjAtual(fz,key),pct=n>1?atual/(n-1)*100:0;
    const todosSel=tot>0&&fz.talhoes.every(t=>sel.has(String(t.num)));
    const nomeMod=mod==='plantio'?'Plantio':'Preparo';

    const dist=cont.map((q,i)=>q?`<button type="button" class="pj-seg" data-pj-etapa="${i}" style="flex:${q};background:${et[i].c}" title="Selecionar ${pjH(et[i].l)} (${q})" aria-label="Selecionar talhões em ${pjH(et[i].l)}"></button>`:'').join('');
    const leg=cont.map((q,i)=>q?`<span class="pj-leg-i"><i style="background:${et[i].c}"></i>${pjH(et[i].l)} ${q}</span>`:'').join('');

    const nos=et.map((s,i)=>{
      const feito=i<atual,ativo=i===atual;
      const ds=(feito||ativo)?`background:${s.c};border-color:${s.c}`:'';
      const alca=(ativo&&edit)?`<span class="pj-alca" role="slider" tabindex="0" aria-label="Etapa atual: ${pjH(s.l)}. Arraste ou use a seta para a esquerda para voltar." aria-valuemin="0" aria-valuemax="${n-1}" aria-valuenow="${i}" aria-valuetext="${pjH(s.l)}" style="color:${s.c}"><span class="ico">chevron_left</span></span>`:'';
      const volta=(edit&&i<atual)?` data-pj-no="${i}" title="Voltar para ${pjH(s.l)}"`:'';
      return `<div class="snode${feito?' done':ativo?' act':''}"${volta}><div class="sdot" data-etapa="${pjH(s.l)}" style="${ds}"><span class="ico">${feito?'check':s.i}</span></div>`+
        `<div class="slbl" style="${ativo?`color:${s.c};font-weight:700`:''}">${pjH(s.l)}<br><small>${cont[i]}</small></div>${alca}</div>`;
    }).join('');

    const linhas=fz.talhoes.map(t=>{
      const s=sel.has(String(t.num)),e=et[t.e]||et[0];
      return `<tr class="${s?'pj-tal-sel':''}"><td>${edit?`<input type="checkbox" class="pj-tal-chk" data-pj-num="${pjH(t.num)}"${s?' checked':''} aria-label="Selecionar talhão ${pjH(t.num)}">`:''}</td>`+
        `<td><strong>${pjH(t.num)}</strong></td><td>${fmtNum(t.ha)} ha</td>`+
        (mod==='plantio'?`<td>${pjH(t.sist_conser||'—')}</td><td>${pjH(t.mes||'—')}</td><td>${pjH(t.mapeamento??'—')}</td>`:`<td>${t.cons?pjH(t.cons.split('-').reverse().join('/')):'—'}</td>`)+
        `<td><span class="ebadge" style="background:${e.c}1a;color:${e.c}">${pjH(e.l)}</span></td></tr>`;
    }).join('');

    let blocos;
    if(!edit){
      blocos=`<div class="aviso-leitura"><span class="ico">visibility</span>Seu acesso ao ${nomeMod} é só de consulta.</div>`;
    }else if(tot>0&&ok===tot){
      blocos=`<div class="done-b" style="background:${mod==='plantio'?'rgba(22,167,107,.1)':'rgba(160,120,64,.1)'};color:${et[n-1].c}"><span class="ico">check_circle</span>Fazenda concluída</div>`;
    }else{
      const bl=[];
      for(let i=0;i<n-1;i++){
        if(!cont[i])continue;
        const usados=pjUsados(fz,key,i),grupo=fz.talhoes.filter(t=>t.e===i);
        const selG=grupo.filter(t=>sel.has(String(t.num)));
        const a=PJ_ACOES[mod][i];
        const cor=mod==='plantio'?et[i+1].c:PJ_COR_P;
        const attrs=a.tipo==='rpc'?`data-pj-rpc="${a.acao}" data-pj-idx="${i}"`:`data-pj-envio="${i}"`;
        bl.push(`<div class="pj-bloco"><div class="pj-bloco-h"><span class="ebadge" style="background:${et[i].c}1a;color:${et[i].c}">${pjH(et[i].l)}</span>`+
          `<span>· ${usados.length} de ${grupo.length} talhões${selG.length?' selecionados':''}</span></div>`+
          `<button type="button" class="btn-acao" ${attrs} style="background:${cor};box-shadow:0 6px 20px ${cor}44"><span class="ico">${a.ico}</span>${pjH(a.txt)}</button></div>`);
      }
      blocos=`<div class="pj-blocos">${bl.join('')}</div>`;
    }

    const desf=(edit&&PJ.desf&&PJ.desf.key===key&&Date.now()<PJ.desf.ate)
      ?`<div class="pj-desf" role="status"><span>${pjNTal(PJ.desf.n)} voltaram para ${pjH(PJ.desf.para)}</span>`+
        `<button type="button" class="pj-desf-b" data-pj-desfazer="${Number(PJ.desf.lote)}">Desfazer</button></div>`
      :'';

    return `<div class="pj-painel">`+
      `<div class="dhead"><div class="dhead-l"><div class="dnome">${pjH(fz.nome)}</div><div class="dsub">${fmtNum(fz.ha)} ha · ${tot} talhões · ${nomeMod}</div></div>`+
      `<span class="dhead-cod">${pjH(fz.cod)}</span>`+
      (tot?(e=>`<div class="ebadge" style="background:${e.c}1a;color:${e.c};font-size:11px;padding:4px 10px">${pjH(e.l)}</div>`)(et[Math.min(...fz.talhoes.map(t=>t.e))]):'')+
      `</div>`+
      `<div class="pj-dist-w"><div class="pj-dist" role="group" aria-label="Talhões por etapa">${dist}</div><div class="pj-dist-leg">${leg}</div></div>`+
      `<div class="pj-stp"><div class="stp-w"><div class="stp-out"><div class="stp-bg"></div>`+
      `<div class="stp-fill" style="background:${et[atual].c};width:calc(17px + ${pct}% * (100% - 34px) / 100%)"></div>`+
      `<div class="stp-row">${nos}</div></div></div>`+
      (edit?'<div class="pj-dica">Arraste a alça para trás, ou clique numa etapa anterior, para retroceder. Avançar é pelas ações.</div>':'')+
      `</div>`+
      `<div class="tal-wrap"><table class="tal-tab"><thead><tr><th>${edit?`<input type="checkbox" class="pj-todos" aria-label="Selecionar todos"${todosSel?' checked':''}>`:''}</th>`+
      `<th>Talhão</th><th>Área</th>${mod==='plantio'?'<th>Conservação</th><th>Mês plantio</th><th>Mapeamento</th>':'<th>Conservação</th>'}<th>Etapa</th></tr></thead><tbody>${linhas}</tbody></table></div>`+
      (htmlArq||'')+
      `<div class="acao-w"><div class="acao-head"><span class="acao-lbl">Próximas ações</span></div>${blocos}</div>`+
      (edit?'<div class="pj-rev-w"><button type="button" class="btn-retro" data-pj-nova>↻ Nova revisão</button></div>':'')+
      desf+
      `<div class="pj-tl-w"><div class="acao-lbl">Linha do tempo</div><div class="pj-tl"></div></div>`+
      `</div>`;
  },

  montar(mod,f,raiz){
    const fz=pjNorm(mod,f);
    if(!fz||!raiz)return;
    const key=pjKey(mod,fz.cod);
    PJ.ctx={mod,f,fz,key,raiz,cod:fz.cod};
    pjLigar(raiz);
    const ultimo=fz.etapas.length-1;
    const todos=fz.talhoes.length>0&&fz.talhoes.every(t=>t.e===ultimo);
    const painel=raiz.querySelector('.pj-painel');
    // Conclusão: só anima quando a fazenda passa a ter todos os talhões Ok (não na primeira carga).
    if(PJ.ok[key]===false&&todos&&painel)pjMo().concluido(painel,{texto:'Fazenda concluída'});
    PJ.ok[key]=todos;
    pjTL(raiz,key,mod,fz.cod);
  },
};

// Estilo próprio da tela (injetado, como drone.js). Usa as variáveis e classes do index.
(function pjEstilo(){
  if(document.getElementById('pj-css'))return;
  const s=document.createElement('style');
  s.id='pj-css';
  s.textContent=`
.pj-painel{display:flex;flex-direction:column;gap:14px;min-width:0}
.pj-dist{display:flex;gap:2px;height:12px;border-radius:999px;overflow:hidden;background:var(--s2)}
.pj-dist-s{height:8px;margin-top:6px}
.pj-dseg{display:block;min-width:4px}
.pj-dtxt{font-size:11px;color:var(--t3);margin-top:4px;font-variant-numeric:tabular-nums}
.pj-seg{border:0;padding:0;min-width:8px;cursor:pointer;transition:filter var(--tf),transform var(--tf)}
.pj-seg:hover{filter:brightness(1.08)}
.pj-seg:focus-visible,.pj-alca:focus-visible{outline:2px solid var(--t1);outline-offset:3px}
.pj-dist-leg{display:flex;flex-wrap:wrap;gap:6px 12px;font-size:11px;color:var(--t2);margin-top:6px}
.pj-leg-i{display:inline-flex;align-items:center;gap:5px}
.pj-leg-i i{width:9px;height:9px;border-radius:3px;display:inline-block}
.pj-stp{display:flex;flex-direction:column;gap:6px}
.pj-stp .snode{position:relative}
.pj-stp .snode[data-pj-no]{cursor:pointer}
.pj-stp .sdot{transition:transform var(--tf),box-shadow var(--tb),background var(--tb)}
.pj-stp .snode[data-pj-no]:hover .sdot{transform:scale(1.06)}
.pj-stp .snode.alvo .sdot{box-shadow:0 0 0 5px rgba(20,24,30,.12)}
.pj-stp .stp-fill{transition:width .35s cubic-bezier(.16,1,.3,1)}
.pj-alca{position:absolute;left:50%;top:17px;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;border:2px solid currentColor;background:var(--sf);box-shadow:0 8px 22px rgba(20,24,30,.18);display:flex;align-items:center;justify-content:center;cursor:grab;touch-action:none;z-index:3;transition:transform .35s cubic-bezier(.16,1,.3,1),box-shadow var(--tb)}
.pj-alca .ico{font-size:18px}
.pj-alca.arrastando{cursor:grabbing;transition:box-shadow var(--tb);box-shadow:0 12px 30px rgba(20,24,30,.25)}
.pj-dica{font-size:11px;color:var(--t3)}
.pj-tal-chk{width:16px;height:16px;cursor:pointer;accent-color:${PJ_COR_P}}
.pj-tal-sel td{background:rgba(160,120,64,.06)}
.pj-blocos{display:flex;flex-direction:column;gap:10px}
.pj-bloco{display:flex;flex-direction:column;gap:10px;border:1px solid var(--bd);border-radius:12px;padding:12px 14px;background:var(--sf)}
.pj-bloco-h{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px;color:var(--t2)}
.pj-rev-w{display:flex;justify-content:flex-start}
.pj-desf{position:sticky;bottom:8px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;background:var(--t1);color:#fff;border-radius:12px;padding:10px 14px;font-size:12.5px;box-shadow:var(--sh-md);animation:pjEntra .35s cubic-bezier(.16,1,.3,1)}
.pj-desf-b{background:#fff;color:var(--t1);border:0;border-radius:8px;padding:6px 12px;font:600 12px 'Poppins',sans-serif;cursor:pointer}
@keyframes pjEntra{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.pj-tl-w{display:flex;flex-direction:column;gap:6px}
.pj-tl-l{list-style:none;margin:0;padding:0}
.pj-ev{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid var(--bd);align-items:flex-start;font-size:12px}
.pj-ev:last-child{border-bottom:0}
.pj-ev-ico{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--s2);color:var(--t2);flex:0 0 auto}
.pj-ev-ico .ico{font-size:16px}
.pj-ev-retrocesso .pj-ev-ico{background:rgba(212,137,10,.14);color:#9a6200}
.pj-ev-desfazer .pj-ev-ico{background:rgba(8,146,200,.12);color:#0892c8}
.pj-ev-revisao .pj-ev-ico{background:rgba(91,110,232,.12);color:#5b6ee8}
.pj-ev-avanco .pj-ev-ico{background:rgba(22,167,107,.12);color:#16a76b}
.pj-ev-b{flex:1;min-width:0;display:flex;flex-direction:column;gap:4px}
.pj-ev-t{color:var(--t1);font-weight:500;overflow-wrap:anywhere}
.pj-ev-j{font-style:italic;color:var(--t2);overflow-wrap:anywhere}
.pj-ev-q{color:var(--t3);font-size:11px}
.pj-chips,.pj-ev-docs{display:flex;flex-wrap:wrap;gap:4px}
.pj-chip-t{font-size:10.5px;background:var(--s2);color:var(--t2);border-radius:6px;padding:2px 6px;font-variant-numeric:tabular-nums}
.pj-ev-docs span{font-size:10.5px;border:1px solid var(--bd2);border-radius:6px;padding:1px 6px;color:var(--t2)}
.pj-vazio,.pj-carreg{font-size:12px;color:var(--t3);padding:10px 0}
.pj-erro{font-size:12px;color:#c23b3b;overflow-wrap:anywhere}
.pj-erro:empty{display:none}
.pj-chips-w{display:flex;flex-wrap:wrap;gap:6px;max-height:200px;overflow:auto;padding:2px}
.pj-chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--bd2);border-radius:999px;padding:4px 10px 4px 8px;font-size:12px;cursor:pointer;background:var(--sf);color:var(--t2)}
.pj-chip input{accent-color:${PJ_COR_P};margin:0}
.pj-chip.on{border-color:${PJ_COR_P};color:var(--t1)}
.pj-chip.trav{cursor:default}
.pj-tag{font-style:normal;font-size:10px;border-radius:6px;padding:1px 5px;background:var(--s2);color:var(--t3)}
.pj-tag.novo{background:rgba(22,167,107,.12);color:#16a76b}
.pj-tag.alt{background:rgba(212,137,10,.14);color:#9a6200}
.pj-efeito{font-size:12px;color:var(--t2);background:var(--s2);border-radius:8px;padding:8px 10px}
.pj-sec{display:flex;flex-direction:column;gap:8px}
.pj-doc{display:flex;flex-direction:column;gap:8px;border:1px solid var(--bd);border-radius:12px;padding:10px 12px;background:var(--sf)}
.pj-doc.on{border-color:var(--bd2)}
.pj-doc-h{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--t1);cursor:pointer;flex-wrap:wrap}
.pj-doc-h input{accent-color:${PJ_COR_P};width:16px;height:16px;margin:0}
.pj-opc{font-size:10.5px;color:var(--t3);background:var(--s2);border-radius:6px;padding:1px 6px}
.pj-ok-t{font-size:10.5px;color:#16a76b}
.pj-slot{position:relative}
.pj-slot.ok{border-color:${PJ_COR_P}}
.pj-prog{height:6px;border-radius:999px;background:var(--s2);overflow:hidden}
.pj-prog[hidden]{display:none}
.pj-prog-b{height:100%;width:0;background:${PJ_COR_P};border-radius:999px;transition:width .3s cubic-bezier(.16,1,.3,1)}
.pj-caixa{max-height:90vh;overflow:auto;max-width:94vw}
.pj-caixa>*{flex-shrink:0}
.pj-caixa .modal-botoes{position:sticky;bottom:-22px;background:var(--sf);padding:10px 0 2px;margin-bottom:-2px}
.pj-modal .modal-botoes{justify-content:flex-end}
.pj-btn-perigo{background:#c23b3b;box-shadow:0 6px 20px #c23b3b44}
.tal-wrap{overflow-x:auto}
@media (max-width:480px){.pj-caixa{padding:18px 16px}.pj-stp .slbl{font-size:10px}}
@media (prefers-reduced-motion: reduce){.pj-stp *,.pj-alca,.pj-desf,.pj-prog-b{transition:none!important;animation:none!important}}
`;
  document.head.appendChild(s);
})();
