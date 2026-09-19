/* Concept A helpers — self-contained, no dependencies */
(function(){
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
  window.$=$; window.$$=$$;

  /* number count-up (ease-out quart) */
  window.countUp=function(el,to,{prefix='',suffix='',dur=1100,decimals=0,delay=0}={}){
    const t0=performance.now()+delay;
    function tick(now){
      const p=Math.min(1,Math.max(0,(now-t0)/dur));
      const e=1-Math.pow(1-p,4);
      const v=to*e;
      el.textContent=prefix+v.toLocaleString('he-IL',{minimumFractionDigits:decimals,maximumFractionDigits:decimals})+suffix;
      if(p<1)requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
    /* settle: guarantee the final value even if animation frames are throttled (background WebView) */
    setTimeout(()=>{el.textContent=prefix+to.toLocaleString('he-IL',{minimumFractionDigits:decimals,maximumFractionDigits:decimals})+suffix;},delay+dur+80);
  };

  /* toast */
  let toastT;
  window.toast=function(msg){
    let t=$('#toast'); if(!t){t=document.createElement('div');t.id='toast';t.className='toast';document.body.appendChild(t);}
    t.textContent=msg; t.classList.add('show'); clearTimeout(toastT); toastT=setTimeout(()=>t.classList.remove('show'),1800);
  };

  /* confetti burst (tiny particle system) */
  window.confetti=function(x,y,n=42){
    let c=$('#confetti'); if(!c){c=document.createElement('canvas');c.id='confetti';document.body.appendChild(c);}
    const dpr=window.devicePixelRatio||1; c.width=innerWidth*dpr; c.height=innerHeight*dpr; c.style.width=innerWidth+'px'; c.style.height=innerHeight+'px';
    const ctx=c.getContext('2d'); ctx.setTransform(dpr,0,0,dpr,0,0);
    const cols=['#FF5C6C','#FFC531','#2FD59A','#3E9BFF','#8F6BFF','#FF9E64'];
    const ps=Array.from({length:n},()=>({x,y,vx:(Math.random()-.5)*11,vy:-Math.random()*9-4,r:Math.random()*5+3,c:cols[Math.random()*cols.length|0],rot:Math.random()*6,vr:(Math.random()-.5)*.4,life:1}));
    let t0=performance.now();
    (function frame(now){
      const dt=Math.min(32,now-t0)/16; t0=now; ctx.clearRect(0,0,innerWidth,innerHeight);
      let alive=false;
      ps.forEach(p=>{p.vy+=.35*dt;p.x+=p.vx*dt;p.y+=p.vy*dt;p.rot+=p.vr;p.life-=.012*dt;if(p.life<=0)return;alive=true;
        ctx.save();ctx.translate(p.x,p.y);ctx.rotate(p.rot);ctx.globalAlpha=Math.max(0,p.life);ctx.fillStyle=p.c;ctx.fillRect(-p.r,-p.r*.6,p.r*2,p.r*1.2);ctx.restore();});
      if(alive)requestAnimationFrame(frame); else ctx.clearRect(0,0,innerWidth,innerHeight);
    })(t0);
  };

  /* bottom sheet */
  window.openSheet=id=>{$('#'+id).classList.add('open');};
  window.closeSheet=id=>{$('#'+id).classList.remove('open');};
  document.addEventListener('click',e=>{const ov=e.target.closest('.sheet-ov'); if(ov&&e.target===ov)ov.classList.remove('open');});

  document.addEventListener('DOMContentLoaded',()=>{
    /* FAB radial menu */
    const fw=$('.fab-wrap'), scrim=$('.fab-scrim');
    if(fw){
      const toggle=()=>{fw.classList.toggle('open');scrim&&scrim.classList.toggle('show',fw.classList.contains('open'));};
      $('.fab',fw).addEventListener('click',toggle);
      scrim&&scrim.addEventListener('click',toggle);
      $$('.fab-item',fw).forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();toggle();if(b.dataset.sheet){openSheet(b.dataset.sheet);}else{toast(b.dataset.toast||'נפתח…');}}));
    }
    /* nav blob position */
    const nav=$('.nav-pill'); if(nav){const items=$$('a',nav);const i=items.findIndex(a=>a.classList.contains('active'));const blob=$('.nav-blob',nav);
      const place=idx=>{blob.style.insetInlineStart=`calc(6px + ${idx} * (100% - 12px)/5)`;};
      place(Math.max(0,i));
      items.forEach((a,idx)=>a.addEventListener('click',e=>{if(a.getAttribute('href')==='#'){e.preventDefault();items.forEach(x=>x.classList.remove('active'));a.classList.add('active');place(idx);toast('המסך הזה לא נבנה בקונספט');}}));
    }
    /* simulate "loading → live" for skeletons, then fire data:ready */
    setTimeout(()=>{$$('.skel').forEach(s=>s.classList.remove('skel'));document.dispatchEvent(new Event('data:ready'));},700);
  });
})();
