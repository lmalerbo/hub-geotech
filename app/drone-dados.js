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
function drClasseEscolhida(txt){
  const t=String(txt??'').replace(/m/gi,'').trim();
  if(!t)return null;                                   // vazio: classe pelo nome do arquivo
  const n=Number(t);return [15,25,50].includes(n)?n:undefined;
}

function drPodeCancelar(sol,ger,eu){
  if(!sol||!eu)return false;
  const ocupado=ger&&(ger.status==='processando'||drPublicando(ger));
  if(ocupado)return false;
  if(podeEditar('drone'))return true;
  return sol.solicitante_id===eu.id&&!ger;            // solicitante: só a própria e antes da prévia
}

function drAtual(){
  const tipo=DR.doc;
  const sol=DR.info.sols.find(s=>s.tipo===tipo)||null;
  const ger=sol?DR.info.ger.find(g=>g.solicitacao_id===sol.id)||null:null;
  return{sol,ger};
}

function drValidarSolicitacao(v){
  if(!v.cod)return'Escolha a fazenda.';
  if(v.data){const hoje=new Date();hoje.setHours(0,0,0,0);if(new Date(v.data+'T12:00')<hoje)return'A data desejada já passou.';}
  return null;
}

// ── obstáculos no mapa (objeto + buffer da classe) ──────────────────────
const DR_OBS_COR={15:'#2e7d32',25:'#e0a100',50:'#c62828'};

function drRotuloShape(envio){
  if(!envio)return'Enviar shape de ajuste';
  if(envio.status==='erro')return'Erro no shape — enviar outro';
  if(envio.status==='ok')return'Shape enviado ✓ (trocar)';
  return'Shape em processamento…';
}

// Envios vêm do mais novo para o mais antigo: o primeiro do tipo é o que vale.
function drUltimoEnvio(envios,tipo){return (envios||[]).find(e=>e.tipo===tipo)||null;}

// Muda quando alguma classe ganha versão nova: aí o desenho guardado (DR.obstGeo) não vale mais.
function drAssinaturaObst(obst){return (obst||[]).map(o=>o.classe_m+':'+o.versao).sort().join('|');}

// ── motor de atualização (spec §4) ───────────────────────────────────────
// JSON das partes que alimentam cada pedaço da tela. Parte com a mesma
// assinatura do ciclo anterior não é redesenhada (fim do pisca-pisca).
function drAssinaturas(info,geo,doc){
  const tal=(geo.features||[]).filter(f=>f.properties.camada==='talhao');
  const envios=(info.envios||[]).map(({enviado_em,...e})=>e);
  return{
    cab:JSON.stringify([info.faz,doc,geo.normal,geo.catacao,geo.cobertura_pct,
      tal.map(f=>[f.properties.talhao,f.properties.status,f.properties.area_ha])]),
    painel:JSON.stringify([doc,geo.normal&&geo.normal.revisao,info.sols,info.ger,envios,info.obst,info.revs]),
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
  if(ult&&['fila','processando'].includes(ult.status))return{texto:'processando envio…',tom:'proc'};
  if(ult&&ult.status==='erro')return{texto:'erro no último envio',tom:'erro'};
  const o=obst||[];if(!o.length)return{texto:'sem cadastro',tom:'velho'};
  const limite=new Date(hoje);limite.setMonth(limite.getMonth()-meses);
  const datas=o.map(v=>new Date(v.enviado_em)),recente=new Date(Math.max(...datas));
  return{texto:`${o.length} classe${o.length>1?'s':''} · ${drDataCurta(recente)}`,tom:datas.some(d=>d<limite)?'velho':'ok'};
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
