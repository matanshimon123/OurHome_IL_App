/* Concept B helpers — self-contained, no dependencies */
(function(){
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
  window.$=$; window.$$=$$;

  /* theme: auto (prefers-color-scheme) unless overridden via the toggle */
  window.toggleTheme=function(){
    const root=document.documentElement;
    const dark=root.dataset.theme?root.dataset.theme==='dark':matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme=dark?'light':'dark';
    $$('.theme-btn').forEach(b=>b.classList.toggle('is-dark',!dark));
  };

  /* number count-up with ease-out */
  window.countUp=function(el,to,{prefix='',suffix='',dur=1400,decimals=0,delay=0}={}){
    const t0=performance.now()+delay;
    function tick(now){
      const p=Math.min(1,Math.max(0,(now-t0)/dur));
      const e=1-Math.pow(1-p,5);
      el.textContent=prefix+(to*e).toLocaleString('he-IL',{minimumFractionDigits:decimals,maximumFractionDigits:decimals})+suffix;
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
    t.textContent=msg; t.classList.add('show'); clearTimeout(toastT); toastT=setTimeout(()=>t.classList.remove('show'),1900);
  };

  /* mock OS notification banner */
  window.showBanner=function(title,body,when='עכשיו'){
    let b=$('#banner'); if(!b){b=document.createElement('div');b.id='banner';b.className='banner';document.body.appendChild(b);}
    b.innerHTML=`<div class="app-ico">O</div><div class="grow"><b></b><span></span></div><small></small>`;
    $('b',b).textContent=title; $('span',b).textContent=body; $('small',b).textContent=when;
    requestAnimationFrame(()=>b.classList.add('show')); setTimeout(()=>b.classList.remove('show'),3600);
  };

  /* sheets */
  window.openSheet=id=>$('#'+id).classList.add('open');
  window.closeSheet=id=>$('#'+id).classList.remove('open');
  document.addEventListener('click',e=>{const ov=e.target.closest('.sheet-ov');if(ov&&e.target===ov)ov.classList.remove('open');});

  /* segmented control: moves the thumb, fires seg:change */
  window.initSeg=function(seg){
    const btns=$$('button',seg), thumb=$('.thumb',seg);
    const place=i=>{const b=btns[i];thumb.style.width=b.offsetWidth+'px';thumb.style.transform=`translateX(${b.offsetLeft}px)`;btns.forEach((x,j)=>x.classList.toggle('on',j===i));};
    btns.forEach((b,i)=>b.addEventListener('click',()=>{place(i);seg.dispatchEvent(new CustomEvent('seg:change',{detail:{index:i,value:b.dataset.v||b.textContent}}));}));
    requestAnimationFrame(()=>place(Math.max(0,btns.findIndex(b=>b.classList.contains('on')))));
  };

  /* switches */
  document.addEventListener('click',e=>{
    const sw=e.target.closest('.switch'); if(!sw||sw.hasAttribute('disabled'))return;
    const on=sw.getAttribute('aria-checked')!=='true'; sw.setAttribute('aria-checked',on);
    if(navigator.vibrate)navigator.vibrate(8);
    sw.dispatchEvent(new CustomEvent('switch:change',{detail:{on},bubbles:true}));
  });

  document.addEventListener('DOMContentLoaded',()=>{
    $$('.seg').forEach(initSeg);
    $$('.theme-btn').forEach(b=>{b.addEventListener('click',toggleTheme);b.classList.toggle('is-dark',matchMedia('(prefers-color-scheme: dark)').matches);});
    /* nav placeholders */
    $$('.nav-bar a[href="#"]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();toast('המסך הזה לא נבנה בקונספט');}));
    /* skeleton → live */
    setTimeout(()=>{$$('.skel').forEach(s=>s.classList.remove('skel'));document.dispatchEvent(new Event('data:ready'));},750);
  });
})();
