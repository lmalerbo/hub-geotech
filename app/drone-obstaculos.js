// Drone: janela de obstáculos (maquete tela 3). Carregado por index.html depois de drone-fazenda.js.
// Só define funções e o estado DRO: nada roda ao carregar (tests/app/drone_puro.test.js também carrega este arquivo).
// Quem só lê abre a janela em modo consulta (cartões e erro do último envio). Quem edita sobe os arquivos.
const DRO={arquivos:[],escolhas:{},grupos:[],ign:new Set(),enviando:false,erro:null,foco:null,tecla:null};
let DRO_JSZIP=null;

// JSZip só é carregado quando um .zip é escolhido; a promessa fica guardada (carrega uma vez).
function droJSZip(){
  if(window.JSZip)return Promise.resolve(window.JSZip);
  if(!DRO_JSZIP)DRO_JSZIP=new Promise((res,rej)=>{
    const s=document.createElement('script');
    s.src='https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
    s.onload=()=>res(window.JSZip);
    s.onerror=()=>{DRO_JSZIP=null;s.remove();rej(new Error('não consegui carregar o leitor de .zip; confira a internet'));};
    document.head.appendChild(s);
  });
  return DRO_JSZIP;
}

// Abre o .zip e devolve só os shapes, no mesmo formato dos arquivos soltos. O resto vai para "ignorados".
async function droLerZip(f){
  const zip=await (await droJSZip()).loadAsync(f);
  const entradas=[];
  zip.forEach((caminho,entrada)=>entradas.push({caminho,entrada}));
  const achados=[];
  for(const {caminho,entrada} of entradas){
    if(entrada.dir)continue;
    const base=caminho.split('/').pop(),ext=drPartesNome(base).ext;
    if(caminho.startsWith('__MACOSX/')||base.startsWith('._')||!DR_EXT_SHAPE.includes(ext)){DRO.ign.add(`${f.name}|${caminho}`);continue;}
    const blob=await entrada.async('blob');
    achados.push({nome:caminho,tamanho:blob.size,origem:f.name,arq:new File([blob],base)});
  }
  return achados;
}

// Acrescenta arquivos (soltos ou dentro de .zip). Só a sugestão da classe entra nas escolhas, e só para camada nova.
async function droAdicionar(lista){
  if(DRO.enviando)return;
  const arqs=[...(lista||[])];
  DRO.erro=null;
  for(const f of arqs){
    const ext=drPartesNome(f.name).ext;
    if(ext==='zip'){
      try{DRO.arquivos.push(...await droLerZip(f));}
      catch(e){DRO.erro=`${f.name}: não consegui abrir este .zip (${e.message||e}).`;}
    }
    else if(DR_EXT_SHAPE.includes(ext))DRO.arquivos.push({nome:f.name,tamanho:f.size,origem:'',arq:f});
    else DRO.ign.add('|'+f.name);
  }
  droReagrupar();droLista();droRodape();
}

function droReagrupar(){
  const antes=new Set(DRO.grupos.map(g=>g.chave));
  DRO.grupos=drAgruparArquivos(DRO.arquivos);
  for(const g of DRO.grupos)if(!antes.has(g.chave)&&[15,25,50].includes(g.classe))DRO.escolhas[g.chave]=g.classe;
}

function droClasse(chave,c){
  if(DRO.enviando||![15,25,50].includes(c))return;
  DRO.escolhas[chave]=c;
  droLista();droRodape();
  document.querySelector(`#dro-lista [data-chave="${chave}"] [data-classe="${c}"]`)?.focus();
}

// Tira a camada inteira (todos os arquivos com o mesmo nome-base) e a escolha dela.
function droRemover(chave){
  if(DRO.enviando)return;
  DRO.arquivos=DRO.arquivos.filter(a=>{const p=drPartesNome(a.nome);return !(DR_EXT_SHAPE.includes(p.ext)&&drNomeSeguro(p.base).toLowerCase()===chave);});
  delete DRO.escolhas[chave];
  droReagrupar();droLista();droRodape();
  document.getElementById('dro-jan')?.focus();
}

// Diz o que seria enviado e o que falta. Não sobe nada.
function droPreparar(){
  const p=drPlanoEnvio(DRO.grupos,DRO.escolhas);
  return{pronto:p.pronto,motivo:p.motivo,nomes:p.arquivos.map(a=>a.nome)};
}

function droProcessando(){
  const ult=drUltimoEnvio(DR.info?.envios,'obstaculos');
  return !!ult&&['fila','processando'].includes(ult.status);
}

function droEscolher(){document.getElementById('dro-inp')?.click();}

// Cliques da janela (um só ouvinte, no próprio diálogo: sobrevive às redesenhas parciais).
function droClique(e){
  const b=e.target.closest('button');if(!b)return;
  const chave=b.closest('[data-chave]')?.dataset.chave;
  if(b.dataset.classe&&chave)droClasse(chave,Number(b.dataset.classe));
  else if(b.dataset.tirar!==undefined&&chave)droRemover(chave);
  else if(b.dataset.acao==='fechar')droFechar();
  else if(b.dataset.acao==='enviar')droEnviar(b);
}

function droCorpoHtml(){
  const ult=drUltimoEnvio(DR.info?.envios,'obstaculos'),editar=podeEditar('drone'),proc=droProcessando();
  const cartoes=drCartoesObst(DR.info?.obst,new Date()).map(c=>`<div class="dro-cartao${c.velho?' velho':''}">
      <div class="dro-cc"><i style="background:${DR_OBS_COR[c.classe]}"></i>${c.classe} m</div>
      <div class="dro-cd">${esc(c.desc)}</div><div class="dro-cv">${esc(c.texto)}</div></div>`).join('');
  const erroEnvio=ult&&ult.status==='erro'
    ?`<div class="dro-erro" role="alert"><span class="ico">error</span><div><b>O último envio deu erro.</b><br>${esc(ult.erro||'Sem detalhes.')}</div></div>`:'';
  let acao='';
  if(editar){
    if(DRO.enviando||proc)acao=`<div class="dro-proc"><span class="ico dr-gira">progress_activity</span>${DRO.enviando?'Enviando os arquivos…':'Processando o envio anterior…'}</div>`;
    else acao=`<div class="dro-solta" id="dro-solta">
        <span class="ico">upload_file</span>
        <div class="dro-solta-t"><b>Arraste aqui os shapes de 15, 25 e 50 m, todos de uma vez</b>
          <small>.shp + .shx + .dbf + .prj, ou .zip (aberto aqui mesmo). A classe vem do nome do arquivo; troque se precisar.</small></div>
        <button class="dro-escolher" onclick="droEscolher()">Escolher arquivos</button>
        <input type="file" id="dro-inp" multiple accept=".shp,.shx,.dbf,.prj,.cpg,.zip" hidden onchange="droAdicionar(this.files);this.value=''">
      </div>`;
  }
  return `<div class="dro-cartoes">${cartoes}</div>${erroEnvio}${acao}<div id="dro-lista"></div>`;
}

function droAbrir(){
  if(document.getElementById('dro-fundo'))return;
  const editar=podeEditar('drone');
  DRO.foco=document.activeElement;
  const f=document.createElement('div');f.className='dro-fundo';f.id='dro-fundo';
  f.innerHTML=`<section class="dro-jan" id="dro-jan" role="dialog" aria-modal="true" aria-labelledby="dro-t" tabindex="-1">
    <header class="dro-cab"><span class="ico dro-ico">warning</span>
      <div class="dro-tit"><h2 id="dro-t">Obstáculos da fazenda</h2>
        <p>${esc(DR.cod)} · ${esc(DR.info?.faz?.nome||'')} — valem para todas as revisões (Normal e Catação)</p></div>
      <button class="dr-x dro-x" data-acao="fechar" aria-label="Fechar" title="Fechar (Esc)"><span class="ico">close</span></button></header>
    <div class="dro-corpo" id="dro-corpo">${droCorpoHtml()}</div>
    ${editar?'<footer class="dro-rodape"><div id="dro-prog"></div><div id="dro-botoes" class="dro-botoes"></div></footer>':''}
  </section>`;
  document.body.appendChild(f);
  f.addEventListener('mousedown',e=>{if(e.target===f)droFechar();});
  const jan=document.getElementById('dro-jan');
  jan.addEventListener('click',droClique);
  DRO.tecla=e=>{
    if(e.key!=='Escape')return;
    const c=document.getElementById('modal-confirma');   // Esc não fecha o "confirmar" do Hub que estiver por cima
    if(!c||c.classList.contains('off')){e.preventDefault();droFechar();}
  };
  document.addEventListener('keydown',DRO.tecla);
  const solta=document.getElementById('dro-solta');
  if(solta){
    solta.addEventListener('dragover',e=>{e.preventDefault();solta.classList.add('on');});
    solta.addEventListener('dragleave',()=>solta.classList.remove('on'));
    solta.addEventListener('drop',e=>{e.preventDefault();solta.classList.remove('on');droAdicionar(e.dataTransfer?.files);});
  }
  droLista();droRodape();
  if(typeof Mo!=='undefined')Mo.pronto(document.getElementById('dro-corpo'));
  jan.focus();
}

// Fecha e descarta os arquivos. Pelo usuário (×, Esc, Cancelar, fundo) não fecha durante o envio;
// forca=true é para trocar de fazenda ou voltar ao Início.
function droFechar(forca){
  if(DRO.enviando&&!forca)return;
  const f=document.getElementById('dro-fundo');
  if(!f)return;
  document.removeEventListener('keydown',DRO.tecla);
  f.remove();
  const foco=DRO.foco;
  Object.assign(DRO,{arquivos:[],escolhas:{},grupos:[],ign:new Set(),erro:null,tecla:null,foco:null});
  if(!forca)(foco&&foco.isConnected?foco:document.querySelector('#dr-ph .dr-obst'))?.focus();
}

function droPlural(n,um,varios){return `${n} ${n===1?um:varios}`;}

function droLinha(g){
  const zips=g.origens.filter(Boolean),escolha=DRO.escolhas[g.chave]??null,d=drDicaClasse(g.classe,escolha);
  const nome=zips.length?`${esc(zips.join(', '))} › ${esc(g.base)}`:esc(g.base);
  const exts=['shp','shx','dbf','prj',...('cpg' in g.partes?['cpg']:[])];
  const pilulas=exts.map(e=>`<span class="dro-pc${g.falta.includes(e)?' falta':''}">.${e}</span>`).join('');
  const obs=g.conflito?`mesmo nome em ${esc(g.origens.map(o=>o||'arquivo solto').join(' e '))}: renomeie um deles`
    :g.falta.length?`falta ${esc(g.falta.map(e=>'.'+e).join(', '))}`:'';
  return `<div class="dro-linha" data-chave="${esc(g.chave)}">
      <span class="ico dro-li-ico">${zips.length?'folder_zip':'description'}</span>
      <div class="dro-li-nome"><div class="dro-li-t">${nome}</div>
        <div class="dro-pilulas">${pilulas}${obs?`<span class="dro-li-obs">${obs}</span>`:''}</div></div>
      <div class="dro-classes">${[15,25,50].map(c=>`<button class="dro-cl${escolha===c?' on':''}" data-classe="${c}" aria-pressed="${escolha===c}">${c} m</button>`).join('')}</div>
      <span class="dro-dica${d.tom==='aviso'?' aviso':''}">${esc(d.texto)}</span>
      <button class="dro-tirar" data-tirar aria-label="Tirar ${esc(g.base)}" title="Tirar esta camada"><span class="ico">close</span></button>
    </div>`;
}

function droLista(){
  const el=document.getElementById('dro-lista');if(!el)return;
  const n=DRO.grupos.length,ig=DRO.ign.size;
  el.innerHTML=(DRO.erro?`<div class="dro-erro" role="alert"><span class="ico">error</span><span>${esc(DRO.erro)}</span></div>`:'')
    +(n?`<h3 class="dro-h3">Camadas encontradas <span>· ${n}</span></h3><div class="dro-lista">${DRO.grupos.map(droLinha).join('')}</div>`:'')
    +(ig?`<p class="dro-ign">${droPlural(ig,'arquivo ignorado','arquivos ignorados')}</p>`:'');
}

function droRodape(){
  const el=document.getElementById('dro-botoes');if(!el)return;
  if(droProcessando()&&!DRO.enviando){
    el.innerHTML=`<span class="dro-resumo">Espere o envio anterior terminar para enviar de novo.</span><button class="dro-cancelar" data-acao="fechar">Fechar</button>`;
    return;
  }
  const p=drPlanoEnvio(DRO.grupos,DRO.escolhas),n=DRO.grupos.length;
  const texto=p.pronto?p.resumo:(n?p.motivo:'Nenhuma camada ainda: arraste ou escolha os arquivos.');
  const rot=DRO.enviando?'Enviando…':p.pronto?`<span class="ico">upload</span>Enviar ${n} camada${n>1?'s':''}`
    :!n?'Escolha arquivos':p.motivo.startsWith('Escolha a classe')?'Escolha a classe de todas':'Corrija para enviar';
  el.innerHTML=`<span class="dro-resumo">${esc(texto)}</span>
    <button class="dro-cancelar" data-acao="fechar"${DRO.enviando?' disabled':''}>Cancelar</button>
    <button class="dro-enviar" id="dro-enviar" data-acao="enviar"${p.pronto&&!DRO.enviando?'':' disabled'}>${rot}</button>`;
}

// Sobe cada arquivo como <classe>m_<nome> numa pasta só, registra o envio uma vez e fecha a janela.
async function droEnviar(btn){
  if(DRO.enviando)return;
  const plano=drPlanoEnvio(DRO.grupos,DRO.escolhas);
  if(!plano.pronto)return;
  const cod=DR.cod,envio=plano.arquivos.map(a=>({nome:a.nome,arq:DRO.arquivos[a.indice].arq}));
  const total=envio.reduce((s,x)=>s+x.arq.size,0);
  DRO.enviando=true;DRO.erro=null;
  const fim=Mo.ocupado(btn);
  const prog=Mo.progresso(document.getElementById('dro-prog'),{total});
  try{
    const pasta=`${cod}/${Date.now()}`,caminhos=[];let feitos=0;
    for(const [k,x] of envio.entries()){
      const c=`${pasta}/${x.nome}`,rot=`${x.nome}${envio.length>1?` (${k+1} de ${envio.length})`:''}`;
      prog.atualizar(feitos,'Enviando '+rot);
      await drSubirComProgresso('drone-envios',c,x.arq,b=>prog.atualizar(feitos+Math.min(b,x.arq.size),'Enviando '+rot));
      feitos+=x.arq.size;caminhos.push(c);
    }
    prog.processando('Registrando o envio…');
    await drRpc('drone_registrar_envio',{p_cod_faz:cod,p_tipo:'obstaculos',p_classe_m:null,p_solicitacao_id:null,p_arquivos:caminhos});
    prog.fim(true);await fim(true);
    DRO.enviando=false;
    droFechar(true);
    if(DR.cod!==cod)return;   // o envio ficou na fazenda de origem; não mexe na tela da outra
    DR.obstLigarAoFim=true;   // quando o agente gravar, a camada liga sozinha (drDesenhar)
    await drCarregarFazenda();
  }catch(e){
    prog.fim(false);fim(false);
    DRO.enviando=false;
    if(document.getElementById('dro-jan')){DRO.erro=e.message||String(e);droLista();droRodape();}
    else if(DR.cod===cod)drErro(e);
  }
}
