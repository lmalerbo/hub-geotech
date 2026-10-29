// Drone: prévia do PDF (pdf.js). Carregado por index.html depois de drone-dados.js.

// ── Prévia de aprovação (S5) ─────────────────────────────────
// O PDF é baixado como bytes e desenhado com pdf.js, dentro do Hub: não depende
// de como o Storage serve o arquivo (content-type/download). O painel mostra a
// capa; a janela (modal grande) tem as páginas com zoom e as ações da prévia.
const DRP={cache:new Map(),gerando:new Set(),ger:null,zoom:1,ajustar:true,desenho:0,motivo:{}};
const DRP_PDFJS='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/';

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
    alvo.insertAdjacentHTML('beforeend',`<span class="drp-lupa"><span class="ico">open_in_full</span>Abrir prévia</span>`);
    alvo.classList.add('mo-surge');
  }catch(e){
    if(alvo.isConnected)caixa.innerHTML=`<div class="dr-err">${esc(e.message)}</div>`;
  }
}

// ── Janela da prévia ──
function drPrevAbrir(){
  const ger=DRP.ger;
  if(!ger||document.getElementById('drp-fundo'))return;
  DRP.tam=null;DRP.ajustar=true;
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
  // O campo do painel fica igual ao da janela: o que foi digitado aqui aparece lá.
  const p=document.querySelector('.dr-mot-painel');if(p&&DRP.ger)p.value=DRP.motivo[DRP.ger.id]||'';
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
