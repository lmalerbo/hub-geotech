// Drone: Início (três colunas da esteira, faixa Atenção, busca, nova solicitação). Carregado por index.html depois de drone-previa.js.

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

const DRI_COLUNAS=['solicitacoes','desenvolvimento','analisar'];
const DRI_VAZIO={solicitacoes:'Nenhuma solicitação aberta.',desenvolvimento:'Nada sendo gerado agora.',analisar:'Nenhuma prévia esperando conferência.'};
const DRI_ATENCAO=[['incompletas','Normais incompletas','incomplete_circle'],
  ['obstaculos_antigos','com obstáculos de mais de 24 meses','history'],
  ['fora_da_base','com talhões fora da Base','wrong_location']];

// Cria o cartão a partir do HTML das funções puras e guarda a assinatura (para não redesenhar cartão igual).
function driElemento(html,ass){
  const t=document.createElement('div');t.innerHTML=html;
  const el=t.firstElementChild;
  el.dataset.ass=ass;
  el.querySelectorAll('.dri-sit .ico').forEach(i=>{if(i.textContent.trim()==='flight')i.classList.add('dri-voa');});
  return el;
}
function driPodeNova(){return !!(podeEditar('drone')||(EU&&EU.niveis&&EU.niveis.drone==='solicitante'));}

// Reconcilia as três colunas com o painel. Tudo num só Mo.mover: cartão que muda de coluna sai de uma e entra na outra.
function driDesenhar(painel){
  const sec=document.querySelector('#dri .dri-cols');
  if(!sec)return;
  const agora=new Date(), editor=!!podeEditar('drone');
  const t=x=>Date.parse(x)||0;
  const g={solicitacoes:[],desenvolvimento:[],analisar:[]};
  (painel.solicitacoes||[]).forEach(s=>g[driColuna(s)].push(s));
  g.solicitacoes.sort((a,b)=>t(a.criado_em)-t(b.criado_em));
  const pedido=s=>(s.geracao&&s.geracao.pedido_em)||s.pedido_em;
  g.desenvolvimento.sort((a,b)=>t(pedido(a))-t(pedido(b)));
  g.analisar.sort((a,b)=>t(b.geracao.concluido_em)-t(a.geracao.concluido_em));
  const porId=new Map(), novos={};
  DRI_COLUNAS.forEach(c=>{
    novos[c]=g[c].map(s=>{const n={id:String(s.id),ass:JSON.stringify(s)+'|'+editor,sol:s};porId.set(n.id,n);return n;});
  });
  const cartao=(lista,id)=>[...lista.children].find(el=>el.dataset.id===id);
  Mo.mover(sec,()=>{
    DRI_COLUNAS.forEach(c=>{
      const lista=sec.querySelector(`.dri-col[data-col="${c}"] .dri-lista`);
      const alvo=novos[c];
      const atuais=[...lista.children].filter(el=>el.classList.contains('dri-card')).map(el=>({id:el.dataset.id,ass:el.dataset.ass}));
      const p=driPlano(atuais,alvo.map(n=>({id:n.id,ass:n.ass})));
      p.remover.forEach(id=>cartao(lista,id).remove());
      p.trocar.forEach(id=>{const n=porId.get(id);cartao(lista,id).replaceWith(driElemento(driCartaoHtml(n.sol,{editor,agora}),n.ass));});
      p.inserir.forEach(id=>{const n=porId.get(id);lista.appendChild(driElemento(driCartaoHtml(n.sol,{editor,agora}),n.ass));});
      if(alvo.length)lista.querySelectorAll(':scope > .dri-vazio').forEach(e=>e.remove());
      else if(!lista.querySelector(':scope > .dri-vazio'))lista.insertAdjacentHTML('beforeend',`<p class="dri-vazio">${DRI_VAZIO[c]}</p>`);
      let antes=null;
      alvo.forEach(n=>{
        const el=cartao(lista,n.id), quer=antes?antes.nextElementSibling:lista.firstElementChild;
        if(el!==quer)lista.insertBefore(el,quer);
        antes=el;
      });
    });
  });
  DRI_COLUNAS.forEach(c=>{const n=sec.querySelector(`.dri-col[data-col="${c}"] .dri-n`);if(n)n.textContent=novos[c].length;});
  const pub=document.getElementById('dri-pub7');
  if(pub)pub.textContent='Publicadas nos últimos 7 dias: '+(painel.publicadas_7d||0);
  driFaixa(painel);
  const nova=document.getElementById('dri-nova');
  if(nova)nova.hidden=!driPodeNova();
  driTempos();
}

// Contadores da faixa Atenção (zero deixa o botão apagado, mas clicável).
function driFaixa(painel){
  DRI_ATENCAO.forEach(([chave])=>{
    const b=document.querySelector(`.dri-at[data-chave="${chave}"]`);if(!b)return;
    const n=(painel[chave]||[]).length;
    b.querySelector('b').textContent=n;
    b.classList.toggle('dri-zero',n===0);
  });
}

// Tempos decorridos são reescritos no lugar a cada ciclo, sem redesenhar o cartão (o trilho não reinicia).
function driTempos(){
  const agora=new Date();
  document.querySelectorAll('#dri [data-desde]').forEach(el=>{el.textContent=driDesde(el.dataset.desde,agora);});
  document.querySelectorAll('#dri [data-quando]').forEach(el=>{el.textContent=driQuando(el.dataset.quando,agora);});
}

// Atalho "/" (foca a busca) e Esc (limpa a busca). Só com a tela do Drone visível e sem gaveta ou modal aberto.
function driTecla(e){
  const v=document.getElementById('v-drone'), dri=document.getElementById('dri');
  if(!v||!v.classList.contains('on')||!dri||dri.hidden)return;
  if(document.getElementById('dri-fundo')||document.querySelector('.dr-modal-fundo'))return;
  const busca=document.getElementById('dr-busca'), ativo=document.activeElement;
  if(!busca||!ativo)return;
  if(e.key==='/'&&!/^(INPUT|TEXTAREA|SELECT)$/.test(ativo.tagName)&&!ativo.isContentEditable){
    e.preventDefault();busca.focus();busca.select();
  }else if(e.key==='Escape'&&ativo===busca){
    busca.value='';document.getElementById('dr-busca-res').innerHTML='';busca.blur();
  }
}

async function droneIniciar(){
  const root=document.getElementById('drone-root');
  if(!root.dataset.pronto){
    root.innerHTML=`<div id="dri">
      <header class="dri-cab">
        <div><h1>Drone</h1><p>Projetos de voo por talhão</p></div>
        <div class="dri-busca-wrap">
          <label class="dri-busca"><span class="ico">search</span>
            <input id="dr-busca" placeholder="Buscar fazenda ou código" autocomplete="off" oninput="drBuscar(this.value)">
            <kbd>/</kbd></label>
          <div id="dr-busca-res"></div>
        </div>
        <button class="dri-nova" id="dri-nova" hidden onclick="drNovaSolicitacao()"><span class="ico">add</span>Nova solicitação</button>
      </header>
      <div id="dri-erro" class="dr-err" hidden></div>
      <section class="dri-cols">
        <div class="dri-col" data-col="solicitacoes"><header class="dri-ch"><span class="ico">inbox</span><h2>Solicitações</h2><span class="dri-n">0</span></header><div class="dri-lista"></div></div>
        <div class="dri-col" data-col="desenvolvimento"><header class="dri-ch"><span class="dri-ponto" aria-hidden="true"></span><h2>Em desenvolvimento</h2><span class="dri-n">0</span></header><div class="dri-lista"></div></div>
        <div class="dri-col" data-col="analisar"><header class="dri-ch"><span class="ico">fact_check</span><h2>A analisar</h2><span class="dri-n">0</span></header><div class="dri-lista"></div><p class="dri-pub7" id="dri-pub7"></p></div>
      </section>
      <div class="dri-atencao"><span class="dri-atl">Atenção na base</span>${DRI_ATENCAO.map(([k,txt,ico])=>`<button class="dri-at" data-chave="${k}" onclick="driAtencaoAbrir('${k}')"><span class="ico">${ico}</span><b>0</b> ${txt}</button>`).join('')}
        <a class="dri-ajuda" href="https://github.com/lmalerbo/hub-geotech/blob/main/docs/drone-manual.md" target="_blank" rel="noreferrer"><span class="ico">help</span> Ajuda</a></div>
    </div>
    <div id="dr-trab" hidden><button class="dri-voltar" onclick="driVoltar()">← Início</button>
      <div class="dr-pnl" id="dr-faz"><div class="dr-vazio">Escolha um projeto ou busque uma fazenda</div></div></div>`;
    root.dataset.pronto='1';
    if(document.addEventListener)document.addEventListener('keydown',driTecla);
    const sec=root.querySelector('.dri-cols');
    Mo.carregando(sec);await drCarregarPainel();Mo.pronto(sec);
    return;
  }
  await drCarregarPainel();
}

async function drCarregarPainel(){
  const erro=document.getElementById('dri-erro');
  try{DR.painel=await drRpc('drone_painel');}
  catch(e){if(erro){erro.textContent=e.message;erro.hidden=false;}return;}
  if(erro)erro.hidden=true;
  driDesenhar(DR.painel);
  if(DR.cod)return;   // com fazenda aberta, o polling é o da fazenda
  if(driAndamento(DR.painel)){if(DR_POLL.fn!==drCarregarPainel)drPollIniciar(drCarregarPainel,10000);}
  else drPollParar();
}

// Abre a área da fazenda no lugar do Início (o Início não é remontado; ao voltar, só recarrega).
// op.obstaculos só marca DR.abrirObst (a S5 usa para abrir a chave de obstáculos).
function driAbrirFazenda(cod,tipo,op){
  DR.abrirObst=!!(op&&op.obstaculos);
  document.getElementById('dri').hidden=true;
  document.getElementById('dr-trab').hidden=false;
  document.getElementById('dr-busca').value='';
  document.getElementById('dr-busca-res').innerHTML='';
  drPollParar();
  drAbrirFazenda(Number(cod),tipo);
  window.scrollTo(0,0);
}
function driVoltar(){
  drPollParar();drMapaDescartar();
  DR.cod=null;
  document.getElementById('dri').hidden=false;
  document.getElementById('dr-trab').hidden=true;
  drCarregarPainel();
}

// Faixa Atenção: gaveta à direita com as fazendas da categoria. X, Esc ou fundo fecham; o foco volta ao botão da faixa.
const DRI_ATENCAO_TIT={incompletas:'Normais incompletas',obstaculos_antigos:'Obstáculos com mais de 24 meses',fora_da_base:'Talhões fora da Base'};
let driFocoAtencao=null;
function driAtencaoAbrir(chave){
  if(document.getElementById('dri-fundo'))return;
  const itens=driAtencaoItens(DR.painel,chave);
  driFocoAtencao=document.querySelector(`.dri-at[data-chave="${chave}"]`);
  const fundo=document.createElement('div');
  fundo.id='dri-fundo';fundo.className='dri-fundo';
  const linhas=itens.map((it,i)=>`<button class="dri-linha" data-i="${i}"><span class="dr-cod">${esc(it.cod_faz)}</span><span class="dri-linha-n">${esc(it.fazenda)}</span><span class="dri-linha-x">${esc(it.extra)}</span></button>`).join('');
  fundo.innerHTML=`<aside class="dri-gaveta" id="dri-gaveta" role="dialog" aria-modal="true" aria-labelledby="dri-gav-t">
    <header><h2 id="dri-gav-t">${esc(DRI_ATENCAO_TIT[chave])}</h2><button class="dr-x" id="dri-gav-x" aria-label="Fechar"><span class="ico">close</span></button></header>
    <p class="dri-gav-n">${itens.length} ${itens.length===1?'fazenda':'fazendas'}</p>
    <div class="dri-gav-l">${linhas||'<p class="dri-vazio">Nenhuma fazenda nesta lista.</p>'}</div>
  </aside>`;
  document.body.appendChild(fundo);
  fundo.onclick=e=>{if(e.target===fundo)driAtencaoFechar();};
  fundo.querySelector('#dri-gav-x').onclick=driAtencaoFechar;
  fundo.querySelectorAll('.dri-linha').forEach(b=>b.onclick=()=>{
    const it=itens[Number(b.dataset.i)];
    driAtencaoFechar();
    driAbrirFazenda(it.cod_faz,null,{obstaculos:chave==='obstaculos_antigos'});
  });
  fundo._esc=e=>{if(e.key==='Escape'){e.preventDefault();driAtencaoFechar();}};
  document.addEventListener('keydown',fundo._esc);
  fundo.querySelector('#dri-gav-x').focus();
}
function driAtencaoFechar(){
  const fundo=document.getElementById('dri-fundo');
  if(!fundo)return;
  document.removeEventListener('keydown',fundo._esc);
  fundo.remove();
  if(driFocoAtencao&&driFocoAtencao.focus)driFocoAtencao.focus();
  driFocoAtencao=null;
}

async function drBuscar(txt){
  const alvo=document.getElementById('dr-busca-res');
  txt=(txt||'').trim();
  if(txt.length<2){alvo.innerHTML='';return;}
  const q=/^\d+$/.test(txt)?sb.from('fazendas').select('cod_faz,nome').eq('cod_faz',Number(txt))
    :sb.from('fazendas').select('cod_faz,nome').ilike('nome',`%${txt}%`).limit(12);
  const {data}=await q;
  alvo.innerHTML=`<div class="dr-grp">${(data||[]).map(f=>`<div class="dr-it" onclick="driAbrirFazenda(${f.cod_faz})"><span class="dr-cod">${f.cod_faz}</span><div>${esc(f.nome)}</div></div>`).join('')||'<div class="dr-msg">nenhuma fazenda</div>'}</div>`;
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
      fechar();await drCarregarPainel();driAbrirFazenda(Number(v.cod),'normal');
    }catch(e){fim(false);fundo.querySelector('#drs-err').textContent=e.message;}
  };
  fundo.querySelector('#drs-busca').focus();
}

function drIrFazenda(cod){
  trocar('drone',document.querySelector(`.ni[onclick*="'drone'"]`));
  driAbrirFazenda(Number(cod));
}
