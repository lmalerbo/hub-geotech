// ─────────────────────────────────────────────────────────────
// MOVIMENTO DO HUB — toda espera ganha animação (spec fluxo de projetos, D6).
// Estilos em motion.css. CSS/JS puro, sem dependência; quem pede menos
// movimento (prefers-reduced-motion) recebe só os estados finais.
//
// API (contrato; pode crescer, não mudar):
//   Mo.ocupado(botao,{texto}?)   → fim(ok,{travado}?)  botão vivo enquanto espera; ✓ ou ✕ no fim
//                                  (travado: continua desabilitado depois do ✓, quem chamou libera)
//   Mo.progresso(el,{total,mb})  → {atualizar(bytes,texto?), processando(texto?), fim(ok,texto?)}
//   Mo.carregando(container,{discreto}?) / Mo.pronto(container,{cascata}?)   esboço animado de lista/painel/mapa
//   Mo.etapa(barraEl,de,para)    → Promise  marca deslizando de uma etapa a outra
//   Mo.concluido(el,{texto})     → Promise  comemoração quando fazenda/projeto chega em Ok
//   Mo.voo(el,{texto,desde}?)    → {pousar(ok,texto?)→Promise, parar()}  drone sobrevoando el (esperas longas do Drone)
// Extras: Mo.campo(grande?) devolve o HTML do indicador de espera do Hub.
// ─────────────────────────────────────────────────────────────
(function(){
  const calmo=()=>window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  const campo=(cls='')=>`<span class="mo-campo ${cls}" aria-hidden="true"><i></i><i></i><i></i><i></i></span>`;
  const espera=ms=>new Promise(r=>setTimeout(r,ms));

  // ── Botão ocupado ──────────────────────────────────────────
  // O rótulo sobe e some, o "campo" entra no lugar e uma faixa de luz
  // atravessa o botão. A largura fica travada para nada pular na tela.
  function ocupado(btn,{texto}={}){
    if(!btn)return()=>Promise.resolve();
    // Se alguém trocou o textContent do botão, o invólucro sumiu: monta de novo.
    if(!btn.querySelector(':scope>.mo-sobre')){
      const rot=document.createElement('span');rot.className='mo-rot';
      while(btn.firstChild)rot.appendChild(btn.firstChild);
      const sobre=document.createElement('span');sobre.className='mo-sobre';
      btn.append(rot,sobre);btn.classList.add('mo-btn');
    }
    clearTimeout(btn._moT);
    const sobre=btn.querySelector(':scope>.mo-sobre');
    btn.style.minWidth=btn.getBoundingClientRect().width+'px';
    sobre.innerHTML=campo('b');
    if(texto)sobre.insertAdjacentText('beforeend',texto);
    btn.classList.remove('mo-ok','mo-erro','mo-fim');
    btn.classList.add('mo-ocupado');
    btn.disabled=true;btn.setAttribute('aria-busy','true');
    let feito=false;
    return function fim(ok,{travado}={}){
      if(feito||!btn.isConnected)return Promise.resolve();
      feito=true;
      btn.classList.remove('mo-ocupado');
      btn.classList.add('mo-fim',ok?'mo-ok':'mo-erro');
      btn.removeAttribute('aria-busy');
      sobre.innerHTML=`<span class="ico">${ok?'check':'close'}</span>`;
      return new Promise(res=>{btn._moT=setTimeout(()=>{
        btn.classList.remove('mo-fim','mo-ok','mo-erro');
        btn.disabled=!!travado;btn.style.minWidth='';sobre.innerHTML='';res();
      },ok?900:1200);});
    };
  }

  // ── Progresso de envio ─────────────────────────────────────
  // Barra com % e MB reais. Quando os bytes acabam e o servidor ainda
  // está gravando, a barra "respira" com o texto do passo atual.
  const fmtB=b=>b>=1048576?(b/1048576).toLocaleString('pt-BR',{maximumFractionDigits:1})+' MB'
    :Math.max(1,Math.round(b/1024)).toLocaleString('pt-BR')+' KB';
  function progresso(el,{total=0,mb:emMB=true}={}){  // mb:false = total em passos, não bytes
    el.querySelector(':scope>.mo-prog')?.remove();
    const p=document.createElement('div');p.className='mo-prog';p.setAttribute('role','progressbar');
    p.setAttribute('aria-valuemin','0');p.setAttribute('aria-valuemax','100');
    p.innerHTML=`<div class="mo-prog-cab"><span class="mo-prog-txt">Preparando…</span><span class="mo-prog-pct">0%</span></div>
      <div class="mo-prog-trilho"><div class="mo-prog-barra"></div></div><div class="mo-prog-mb"></div>`;
    el.appendChild(p);
    const txt=p.querySelector('.mo-prog-txt'),pct=p.querySelector('.mo-prog-pct'),
      barra=p.querySelector('.mo-prog-barra'),mb=p.querySelector('.mo-prog-mb');
    const pinta=f=>{const n=Math.round(f*100);barra.style.transform=`scaleX(${f})`;pct.textContent=n+'%';p.setAttribute('aria-valuenow',n);};
    const api={
      atualizar(bytes,texto){
        const f=total?Math.min(1,bytes/total):0;
        pinta(f);if(texto)txt.textContent=texto;
        mb.textContent=total&&emMB?`${fmtB(Math.min(bytes,total))} de ${fmtB(total)}`:'';
        p.classList.toggle('mo-proc',f>=1);
      },
      processando(texto){pinta(1);p.classList.add('mo-proc');txt.textContent=texto||'Gravando no servidor…';},
      fim(ok,texto){
        p.classList.remove('mo-proc');p.classList.add(ok?'mo-ok':'mo-erro');
        if(ok)pinta(1);
        txt.textContent=texto||(ok?'Enviado':'Envio interrompido');
        if(ok)pct.textContent='✓';
      },
    };
    return api;
  }

  // ── Esboço de lista/painel ─────────────────────────────────
  // discreto: conteúdo continua visível; só uma linha de luz no topo e o campo
  // no canto — para recargas curtas de um painel que já está na tela.
  function carregando(c,{discreto=false}={}){
    if(!c||c.querySelector(':scope>.mo-esboco'))return;
    c.classList.add('mo-carregando');c.classList.toggle('mo-discreto',discreto);c.setAttribute('aria-busy','true');
    const n=Math.max(4,Math.min(12,Math.floor((c.clientHeight||160)/26)));
    const e=document.createElement('div');e.className='mo-esboco';
    e.innerHTML=(discreto?'':'<i></i>'.repeat(n))+campo();
    c.appendChild(e);
  }
  // Tira o esboço e faz o conteúdo novo chegar em cascata curta
  // (só os primeiros itens; o resto aparece junto, sem fila longa).
  function pronto(c,{cascata=true}={}){  // cascata:false para mapa (não sacode o canvas)
    if(!c)return;
    c.classList.remove('mo-carregando','mo-discreto');c.removeAttribute('aria-busy');
    const e=c.querySelector(':scope>.mo-esboco');
    if(e){e.classList.add('mo-sai');setTimeout(()=>e.remove(),180);}
    if(calmo()||!cascata)return;
    [...c.children].filter(x=>!x.classList.contains('mo-esboco')).slice(0,10).forEach((x,i)=>{
      x.style.animationDelay=(i*28)+'ms';x.classList.add('mo-surge');
      x.addEventListener('animationend',()=>{x.classList.remove('mo-surge');x.style.animationDelay='';},{once:true});
    });
  }

  // ── Drone sobrevoando ──────────────────────────────────────
  // Para esperas longas do Drone (publicação, prévia): o drone faz passadas
  // sobre o elemento como numa aplicação e volta ao início. `desde` (Date.now()
  // de quando a espera começou) mantém a fase quando a tela é redesenhada
  // (polling): o drone continua de onde estava em vez de recomeçar.
  // pousar(ok): vai ao centro, desce e vira ✓ (Mo.concluido) ou balança e mostra o erro.
  const DRONE_SVG=`<svg viewBox="-32 -32 64 64" aria-hidden="true">
    <path d="M-16-16L16 16M16-16L-16 16" stroke="#2c3440" stroke-width="4.5" stroke-linecap="round"/>
    ${[[16,-16],[-16,-16],[16,16],[-16,16]].map(([x,y])=>`<g transform="translate(${x} ${y})"><circle r="10.5" class="mo-voo-disco"/>
      <g class="mo-helice"><rect x="-10" y="-1.6" width="20" height="3.2" rx="1.6"/></g><circle r="2.2" fill="#2c3440"/></g>`).join('')}
    <rect x="-8" y="-11" width="16" height="22" rx="6" class="mo-voo-corpo"/><circle cy="-6.5" r="2" fill="#fff"/></svg>`;
  const VOO_MS=12000;   // igual à duração de mo-voo-rota no CSS
  function voo(el,{texto='',desde=Date.now()}={}){
    if(!el)return{pousar:()=>Promise.resolve(),parar(){}};
    el.querySelector(':scope>.mo-voo')?.remove();
    if(getComputedStyle(el).position==='static')el.style.position='relative';
    const w=document.createElement('div');w.className='mo-voo';w.setAttribute('role','status');
    w.style.setProperty('--mo-voo-atraso',-((Date.now()-desde)%VOO_MS)+'ms');
    w.innerHTML=`<div class="mo-voo-rota"><div class="mo-voo-sombra"></div><div class="mo-voo-rumo"><div class="mo-voo-drone">${DRONE_SVG}</div></div></div>
      <div class="mo-voo-txt">${campo('b')}<span class="mo-voo-msg"></span></div>`;
    const t=w.querySelector('.mo-voo-txt');
    t.querySelector('.mo-voo-msg').textContent=texto;t.hidden=!texto;
    el.appendChild(w);
    const rota=w.querySelector('.mo-voo-rota'),rumo=w.querySelector('.mo-voo-rumo');
    return{
      parar(){w.remove();},
      pousar(ok,txt){
        if(!w.isConnected)return Promise.resolve();
        const de=getComputedStyle(rota).transform,giro=getComputedStyle(rumo).transform;
        w.classList.add('mo-pousa');   // tira as animações em laço e congela onde está
        rota.style.transform=de;rumo.style.transform=giro;
        if(ok)t.hidden=true;
        else{t.hidden=false;t.classList.add('mo-erro');t.querySelector('.mo-voo-msg').textContent=txt||'Não deu certo';t.querySelector('.mo-campo')?.remove();}
        const centro=`translate(${w.clientWidth/2}px,${w.clientHeight/2}px)`,dur=calmo()?0:650,
          curva={duration:dur,easing:'cubic-bezier(.65,0,.35,1)',fill:'forwards'};
        rumo.animate([{transform:giro},{transform:'rotate(0deg)'}],curva);
        return rota.animate([{transform:de},{transform:centro}],curva).finished.then(()=>{
          if(!ok){
            const d=w.querySelector('.mo-voo-drone');
            return(calmo()?Promise.resolve():d.animate([{transform:'rotate(0)'},{transform:'rotate(-12deg)'},{transform:'rotate(10deg)'},
              {transform:'rotate(-6deg)'},{transform:'rotate(0)'}],{duration:500}).finished).then(()=>espera(1400)).then(()=>w.remove());
          }
          w.classList.add('mo-desce');   // drone encolhe, sombra encontra o drone, hélices desaceleram
          return espera(calmo()?0:420).then(()=>{w.remove();return concluido(el,{texto:txt||'Concluído'});});
        });
      },
    };
  }

  // ── Barra de etapa ─────────────────────────────────────────
  // Etapas = filhos com [data-etapa] (ou os filhos diretos), em ordem.
  // de/para = índice (0…) ou o valor de data-etapa. Uma moldura desliza
  // de uma etapa à outra; as etapas no caminho pulsam quando ela passa.
  // A tela redesenha o estado final depois que a Promise resolve.
  function etapa(barra,de,para,{cor}={}){
    if(!barra)return Promise.resolve();
    const passos=[...(barra.querySelectorAll('[data-etapa]').length?barra.querySelectorAll('[data-etapa]'):barra.children)];
    const idx=v=>typeof v==='number'?v:passos.findIndex(p=>p.dataset.etapa===String(v));
    const a=idx(de),b=idx(para);
    if(a<0||b<0||a===b||!passos[a]||!passos[b]||calmo())return Promise.resolve();
    if(getComputedStyle(barra).position==='static')barra.style.position='relative';
    const base=barra.getBoundingClientRect();
    const caixa=p=>{const r=p.getBoundingClientRect();return{left:r.left-base.left+barra.scrollLeft,top:r.top-base.top+barra.scrollTop,width:r.width,height:r.height};};
    const ra=caixa(passos[a]),rb=caixa(passos[b]);
    const m=document.createElement('div');m.className='mo-etapa-marca';
    const c=cor||getComputedStyle(passos[b]).getPropertyValue('--mo-etapa-cor').trim()||'var(--mo-c1)';
    m.style.borderColor=c;m.style.borderRadius=Math.min(ra.height,rb.height)/2+'px';
    barra.appendChild(m);
    const n=Math.abs(b-a),dur=Math.min(260+n*110,820);
    const q=r=>({left:r.left-3+'px',top:r.top-3+'px',width:r.width+6+'px',height:r.height+6+'px'});
    const anim=m.animate([{...q(ra),opacity:0},{...q(ra),opacity:1,offset:.12},{...q(rb),opacity:1,offset:.82},{...q(rb),opacity:0}],
      {duration:dur+260,easing:'cubic-bezier(.16,1,.3,1)',fill:'forwards'});
    const dir=b>a?1:-1;
    for(let k=1;k<=n;k++){
      const p=passos[a+k*dir];
      setTimeout(()=>{p.classList.remove('mo-etapa-passa');void p.offsetWidth;p.classList.add('mo-etapa-passa');
        p.addEventListener('animationend',()=>p.classList.remove('mo-etapa-passa'),{once:true});},40+(dur*.82)*(k/n)-60);
    }
    return anim.finished.catch(()=>{}).then(()=>m.remove());
  }

  // ── Conclusão ──────────────────────────────────────────────
  // Selo verde que se desenha, uma onda e confete curto nas cores dos
  // módulos, por cima do elemento (cartão da fazenda, painel…).
  function concluido(el,{texto='Concluído'}={}){
    if(!el)return Promise.resolve();
    const pos=getComputedStyle(el).position==='static';
    if(pos)el.style.position='relative';
    const w=document.createElement('div');w.className='mo-conc';w.setAttribute('role','status');
    let conf='';
    if(!calmo()){
      const cores=['var(--mo-c1)','var(--mo-c2)','var(--mo-c3)','var(--mo-c4)'];
      for(let i=0;i<18;i++){
        const ang=(i/18)*Math.PI*2+Math.random()*.4,d=60+Math.random()*70;
        conf+=`<i class="mo-conc-p" style="background:${cores[i%4]};--dx:${Math.cos(ang)*d|0}px;--dy:${Math.sin(ang)*d-20|0}px;--r:${(Math.random()*540-270)|0}deg;animation-delay:${120+Math.random()*80|0}ms"></i>`;
      }
    }
    w.innerHTML=`<div class="mo-conc-fundo"></div>${conf}
      <div class="mo-conc-selo"><div class="mo-conc-onda"></div><svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="32"/><path d="M19 33l9 9 17-19"/></svg></div>
      <div class="mo-conc-txt"></div>`;
    w.querySelector('.mo-conc-txt').textContent=texto;
    el.appendChild(w);
    return espera(1900).then(()=>{w.remove();if(pos)el.style.position='';});
  }

  window.Mo={ocupado,progresso,carregando,pronto,etapa,concluido,voo,campo:g=>campo(g?'g':'')};
})();
