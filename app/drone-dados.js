// Drone: estado (DR), chamadas ao banco e regras puras. Carregado por index.html antes de drone-previa/inicio/fazenda.
// Tela do Drone (spec Parte 2, §5): fila de trabalho + fazenda com mapa por talhão.
const DR={painel:null,cod:null,geo:null,mapa:null,sel:new Map(),rem:new Set(),modoRemover:false,
  doc:'normal',ajusteId:null,info:null};
const DR_ST={aguardando_obstaculos:'aguardando obstáculos',aguardando_infestacao:'aguardando infestação',
  solicitado:'solicitado',em_elaboracao:'em elaboração',devolvido:'devolvido'};
const DR_COR={normal:'#a0694b',catacao:'#5b8c5a',sel:'#5b6ee8',rem:'#c23b3b',sem:'#e9ebef',fora:'#d4890a'};

// Movimento (app/motion.js). Os botões do Drone chamam as funções sem passar o
// botão; ele é pego do evento do clique — antes de qualquer await/prompt, que
// apagam window.event.
function drBotao(){const e=window.event;return e&&e.target&&e.target.closest?e.target.closest('button'):null;}

async function drRpc(nome,args){
  const {data,error}=await sb.rpc(nome,args||{});
  if(error)throw new Error(error.message);
  return data;
}

function drPodeGerarCatacao(sol){return !!sol&&['solicitado','em_elaboracao'].includes(sol.status);}
function drNomeSeguro(nome){
  return String(nome).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Za-z0-9._-]/g,'_').replace(/\.\./g,'__');
}
// Nome sem pasta (aceita / e \) e sem a última extensão; ext em minúscula, sem ponto.
function drPartesNome(nome){
  const f=String(nome).split(/[\\/]/).pop();const i=f.lastIndexOf('.');
  return i>0?{base:f.slice(0,i),ext:f.slice(i+1).toLowerCase()}:{base:f,ext:''};
}
// Mesma regra de drone/insumos.py::classe_pelo_nome.
function drClassePeloNome(nome){
  const s=drPartesNome(nome).base.normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();
  const m=s.match(/(\d+)\s*m(?![a-z])/)||s.match(/(\d+)$/);
  const n=m?Number(m[1]):null;
  return [15,25,50].includes(n)?n:null;
}
function drNomeComClasse(classe,nome){
  const p=drPartesNome(nome);
  return `${classe}m_${drNomeSeguro(p.base)}${p.ext?'.'+p.ext:''}`;
}
const DR_EXT_SHAPE=['shp','shx','dbf','prj','cpg'];
const DR_EXT_OBRIG=['shp','shx','dbf','prj'];
// Agrupa os arquivos por nome-base (sem diferenciar maiúsculas). Ignora o que não é de shape e o repetido.
function drAgruparArquivos(arquivos){
  const vistos=new Set(),mapa=new Map();
  (arquivos||[]).forEach((a,indice)=>{
    const {base,ext}=drPartesNome(a.nome);
    if(!DR_EXT_SHAPE.includes(ext))return;
    const dup=`${a.origem}|${a.nome}|${a.tamanho}`;
    if(vistos.has(dup))return;vistos.add(dup);
    const chave=drNomeSeguro(base).toLowerCase();
    let g=mapa.get(chave);
    if(!g){g={chave,base,origens:[],partes:{},nomes:{},repetida:false,itens:[]};mapa.set(chave,g);}
    if(!g.origens.includes(a.origem))g.origens.push(a.origem);
    if(ext in g.partes)g.repetida=true;else{g.partes[ext]=indice;g.nomes[ext]=a.nome;}
    g.itens.push(a);
  });
  return [...mapa.values()].map(g=>{
    const shp=g.itens.find(a=>drPartesNome(a.nome).ext==='shp')||g.itens[0];
    return{chave:g.chave,base:g.base,origens:g.origens,partes:g.partes,nomes:g.nomes,
      falta:DR_EXT_OBRIG.filter(e=>!(e in g.partes)),
      classe:drClassePeloNome(shp.nome),
      conflito:g.origens.length>1||g.repetida};
  });
}
// Escolhas: {[chave]: 15|25|50}. Não sobe nada; só diz o que enviar e o que falta.
function drPlanoEnvio(grupos,escolhas){
  const falhar=motivo=>({pronto:false,motivo,arquivos:[],resumo:motivo});
  if(!grupos.length)return falhar('Nenhuma camada para enviar.');
  for(const g of grupos)if(g.falta.length)return falhar(`${g.base}: falta ${g.falta.map(e=>'.'+e).join(', ')}`);
  for(const g of grupos)if(g.conflito){
    const orig=[...new Set(g.origens.map(o=>o||'arquivo solto'))].join(' e ');
    return falhar(`${g.base}: mesmo nome em ${orig} — renomeie um deles`);
  }
  if(grupos.some(g=>![15,25,50].includes((escolhas||{})[g.chave])))return falhar('Escolha a classe de todas as camadas.');
  const arquivos=[],contagem={};
  for(const g of grupos){
    const cl=escolhas[g.chave];contagem[cl]=(contagem[cl]||0)+1;
    for(const e of ['shp','shx','dbf','prj','cpg'])if(e in g.partes)
      arquivos.push({indice:g.partes[e],nome:drNomeComClasse(cl,g.nomes[e])});
  }
  const txt=Object.keys(contagem).map(Number).sort((a,b)=>a-b)
    .map(c=>`${c} m${contagem[c]>1?` (${contagem[c]} camadas juntas)`:''}`).join(', ');
  const resumo=`Vai criar uma versão nova de ${txt}. Classes que não aparecem aqui continuam como estão.`;
  return{pronto:true,motivo:null,arquivos,resumo};
}
function drDicaClasse(sugerida,escolhida){
  if(escolhida==null)return{texto:'escolha a classe',tom:'aviso'};
  return escolhida===sugerida?{texto:'pelo nome do arquivo',tom:''}:{texto:'trocada por você',tom:''};
}
// Cartões das três classes (15, 25, 50), sempre nessa ordem.
function drCartoesObst(obst,hoje,meses=24){
  const limite=new Date(hoje);limite.setMonth(limite.getMonth()-meses);
  return [15,25,50].map(c=>{
    const o=(obst||[]).find(v=>v.classe_m===c);
    if(!o)return{classe:c,desc:DR_OBS_DESC[c],texto:'sem cadastro',velho:false};
    const enviado=new Date(o.enviado_em);
    const data=enviado.toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric'});
    const velho=enviado<limite;
    return{classe:c,desc:DR_OBS_DESC[c],velho,
      texto:`v${o.versao} · ${data} · ${velho?`mais de ${meses} meses`:`${o.n_feicoes} feições`}`};
  });
}

function drPodeCancelar(sol,ger,eu){
  if(!sol||!eu)return false;
  const ocupado=ger&&(ger.status==='processando'||drPublicando(ger));
  if(ocupado)return false;
  if(podeEditar('drone'))return true;
  return sol.solicitante_id===eu.id&&!ger;            // solicitante: só a própria e antes da prévia
}

function drSolGer(info,doc){
  const sol=(info.sols||[]).find(s=>s.tipo===doc)||null;
  const ger=sol?(info.ger||[]).find(g=>g.solicitacao_id===sol.id)||null:null;
  return{sol,ger};
}
function drAtual(){return drSolGer(DR.info,DR.doc);}

function drValidarSolicitacao(v){
  if(!v.cod)return'Escolha a fazenda.';
  if(v.data){const hoje=new Date();hoje.setHours(0,0,0,0);if(new Date(v.data+'T12:00')<hoje)return'A data desejada já passou.';}
  return null;
}

// ── obstáculos no mapa (objeto + buffer da classe) ──────────────────────
const DR_OBS_COR={15:'#2e7d32',25:'#e0a100',50:'#c62828'};
const DR_OBS_DESC={15:'árvore isolada',25:'rede de energia padrão',50:'alta tensão, sede, APP, rodovia…'};

function drRotuloShape(envio){
  if(!envio)return'Enviar shape de ajuste';
  if(envio.status==='erro')return'Erro no shape — enviar outro';
  if(envio.status==='ok')return'Shape enviado ✓ (trocar)';
  return'Shape em processamento…';
}

// Envios vêm do mais novo para o mais antigo: o primeiro do tipo é o que vale.
// O cliente do Supabase devolve {data:null,error} em vez de lançar: sem isto, uma queda vira "lista vazia".
function drSemErro(r){if(r&&r.error)throw new Error(r.error.message||'Falha ao ler o banco.');return r;}
function drUltimoEnvio(envios,tipo){return (envios||[]).find(e=>e.tipo===tipo)||null;}
// Envio em fila/processando há mais de 2 h: o agente provavelmente está fora. Não segura mais a janela.
const DR_ENVIO_TRAVA_H=2;
function drEnvioTravado(e,agora){
  if(!e||!['fila','processando'].includes(e.status)||!e.enviado_em)return false;
  return new Date(agora)-new Date(e.enviado_em)>DR_ENVIO_TRAVA_H*36e5;
}

// Muda quando alguma classe ganha versão nova: aí o desenho guardado (DR.obstGeo) não vale mais.
function drAssinaturaObst(obst){return (obst||[]).map(o=>o.classe_m+':'+o.versao).sort().join('|');}

// ── motor de atualização (spec §4) ───────────────────────────────────────
// JSON das partes que alimentam cada pedaço da tela. Parte com a mesma
// assinatura do ciclo anterior não é redesenhada (fim do pisca-pisca).
function drAssinaturas(info,geo,doc){
  const tal=(geo.features||[]).filter(f=>f.properties.camada==='talhao');
  const envios=(info.envios||[]).map(({enviado_em,...e})=>e);
  const {sol,ger}=drSolGer(info,doc),card=(DR.painel?.solicitacoes||[]).find(c=>sol&&c.id===sol.id);
  return{
    cab:JSON.stringify([info.faz,doc,geo.normal,geo.catacao,geo.cobertura_pct,
      tal.map(f=>[f.properties.talhao,f.properties.status,f.properties.area_ha]),drChipObstaculos(info.obst,info.envios,new Date())]),
    painel:JSON.stringify([doc,geo.normal&&geo.normal.revisao,info.sols,info.ger,envios,info.obst,info.revs,DR.ajusteId,DR.modoRemover]),
    etapas:JSON.stringify([doc,sol&&sol.id,ger&&[ger.status,ger.publicar_pedido_em,ger.publicacao_erro],drContextoSol(card)]),
    obst:drAssinaturaObst(info.obst),
    mapa:JSON.stringify([doc,geo.features])};
}
function drPartesMudadas(antes,agora){return Object.keys(agora).filter(k=>!antes||antes[k]!==agora[k]);}
function drRespostaValida(codPedido,codAtual){return codPedido===codAtual;}
function drOcupado(info,ger){
  return !!((ger&&(['fila','processando'].includes(ger.status)||drPublicando(ger)))
    ||(info.envios||[]).some(e=>e.status==='fila'||e.status==='processando'));
}
// Talhões que pulsam no mapa enquanto a prévia é gerada (Catação não tem escopo: só a varredura).
function drTalhoesGerando(ger){
  if(!ger||!['fila','processando'].includes(ger.status))return[];
  return((ger.escopo&&ger.escopo.incluir)||[]).map(i=>i.talhao);
}

// ── área da fazenda (S4) ──
const drPublicando=ger=>!!(ger&&ger.publicar_pedido_em&&!ger.publicacao_erro);
function drEtapaAtiva(sol,ger){
  if(!ger)return 0;
  if(ger.status==='pronta')return drPublicando(ger)?3:2;
  return 1;                                            // fila, processando ou erro
}
function drEstadoPainel({doc,sol,ger,edita}){
  if(!edita)return'consulta';
  if(ger){
    if(drPublicando(ger))return'publicando';
    if(ger.status==='fila'||ger.status==='processando')return'gerando';
    if(ger.status==='erro')return'erro';
    if(ger.status==='pronta')return'previa';
  }
  return doc==='catacao'?'catacao':'montando';
}
function drDataCurta(iso){return new Date(iso).toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit',year:'2-digit'});}
function drChipObstaculos(obst,envios,hoje,meses=24){
  const ult=drUltimoEnvio(envios,'obstaculos');
  if(drEnvioTravado(ult,hoje))return{texto:'envio parado',tom:'velho'};
  if(ult&&['fila','processando'].includes(ult.status))return{texto:'processando envio…',tom:'proc'};
  if(ult&&ult.status==='erro')return{texto:'erro no último envio',tom:'erro'};
  const o=obst||[];if(!o.length)return{texto:'sem cadastro',tom:'velho'};
  const limite=new Date(hoje);limite.setMonth(limite.getMonth()-meses);
  const datas=o.map(v=>new Date(v.enviado_em)),recente=new Date(Math.max(...datas));
  return{texto:`${o.length} classe${o.length>1?'s':''} · ${drDataCurta(recente)}`,tom:datas.some(d=>d<limite)?'velho':'ok'};
}
function drForaDaBase(geo){
  return((geo&&geo.features)||[]).filter(f=>f.properties.camada==='talhao'&&f.properties.status==='fora_da_base').map(f=>f.properties.talhao);
}
// Marca os talhões fora da Base para sair, uma vez por montagem: o que o analista desmarcar não volta no ciclo seguinte.
function drMarcarForaDaBase(geo,est,rem,marcado){
  if(marcado||est!=='montando')return !!marcado;
  drForaDaBase(geo).forEach(n=>rem.add(n));
  return true;
}
// Área sobreposta (talhão antigo sobre os novos): cada ferramenta pula o talhão que ela não aceita.
function drTalhaoDoClique(feats,remover){
  const ignora=remover?'sem_projeto':'fora_da_base';
  return(feats.find(f=>f.properties.status!==ignora)||feats[0]).properties;
}
// Fazenda que saiu inteira da Base: não há revisão possível, só encerrar o projeto.
function drPodeEncerrar(geo,edita){
  const tal=(geo.features||[]).filter(f=>f.properties.camada==='talhao');
  return !!(edita&&(geo.normal||geo.catacao)&&tal.every(f=>f.properties.status==='fora_da_base'));
}
function drEscopo(sel,rem,ajusteId){
  const inc=[...sel].sort((a,b)=>a[0]-b[0]);
  if(inc.some(([,f])=>f==='shape')&&!ajusteId)throw new Error('Envie o shape de ajuste antes de gerar.');
  return{incluir:inc.map(([t,f])=>f==='shape'?{talhao:t,fonte:'shape',envio_id:ajusteId}:{talhao:t,fonte:'sistema'}),
    remover:[...rem].sort((a,b)=>a-b)};
}
function drIndicadoresPrevia(resumo,vigente,doc){
  const n=x=>typeof x==='number'?x:null,r=resumo||{},v=vigente||{},normal=doc==='normal';
  const area=n(r.aplicacao_ha),antes=n(v.area_ha);
  return{area,deltaArea:area!=null&&antes!=null?area-antes:null,cob:normal?n(r.cobertura_pct):null,cobAntes:normal?n(v.cobertura_pct):null};
}
function drSituacaoTalhao(p){return p.status==='sem_projeto'?'sem projeto':'refazer Rev'+p.desde_rev;}
function drDecorrido(desde,agora){
  if(!desde)return'';
  const s=Math.max(0,Math.floor((agora-Date.parse(desde))/1000));
  if(s<60)return s+' s';
  if(s<3600)return`${Math.floor(s/60)} min ${s%60} s`;
  return`${Math.floor(s/3600)} h ${String(Math.floor(s%3600/60)).padStart(2,'0')} min`;
}
function drContextoSol(c){
  if(!c)return'';
  const p=['Solicitação'+(c.solicitante?' de '+c.solicitante:'')];
  if(c.observacao)p.push(`“${c.observacao}”`);
  if(c.data_desejada)p.push('para '+new Date(c.data_desejada+'T12:00').toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'}));
  return p.join(' · ');
}
function drCamadasEnvio(env){
  return[...new Set(((env&&env.arquivos)||[]).map(a=>a.split('/').pop().replace(/\.[^.]+$/,'')))];
}

// Extensões aceitas ao arrastar arquivos para o painel do Drone (sem diferenciar maiúscula).
const DR_EXT_ACEITAS=['.shp','.shx','.dbf','.prj','.cpg','.zip'];
function drArquivosAceitos(nomes){return nomes.filter(n=>DR_EXT_ACEITAS.some(x=>n.toLowerCase().endsWith(x)));}
// Polling único (spec §4): um timer só. Pausa com a aba oculta ou fora da view
// do Drone e retoma ao voltar. O callback roda uma vez; quem quer continuar chama drPollIniciar de novo.
const DR_POLL={t:null,fn:null,ms:0,fora:false};
function drPollAgendar(){
  clearTimeout(DR_POLL.t);DR_POLL.t=null;
  if(!DR_POLL.fn||DR_POLL.fora||document.visibilityState==='hidden')return;
  DR_POLL.t=setTimeout(()=>{DR_POLL.t=null;const f=DR_POLL.fn;DR_POLL.fn=null;f();},DR_POLL.ms);
}
function drPollIniciar(fn,ms){DR_POLL.fn=fn;DR_POLL.ms=ms;drPollAgendar();}
function drPollParar(){clearTimeout(DR_POLL.t);DR_POLL.t=null;DR_POLL.fn=null;}
function drPollVisivel(naTela){DR_POLL.fora=!naTela;drPollAgendar();}
if(document.addEventListener)document.addEventListener('visibilitychange',drPollAgendar);
