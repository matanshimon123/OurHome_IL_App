/* Concept C helpers — self-contained, no dependencies */
(function(){
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
  window.$=$; window.$$=$$;
  const NS='http://www.w3.org/2000/svg';
  window.svgEl=(n,a={},text)=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);if(text!=null)e.textContent=text;return e;};
  window.fmt=(n,d=0)=>n.toLocaleString('he-IL',{minimumFractionDigits:d,maximumFractionDigits:d});

  /* mono count-up */
  window.countUp=function(el,to,{prefix='',suffix='',dur=1000,decimals=0,delay=0}={}){
    const t0=performance.now()+delay;
    (function tick(now){const p=Math.min(1,Math.max(0,(now-t0)/dur));const e=1-Math.pow(1-p,3);el.textContent=prefix+fmt(to*e,decimals)+suffix;if(p<1)requestAnimationFrame(tick);})(performance.now());
    /* settle: guarantee the final value even if animation frames are throttled (background WebView) */
    setTimeout(()=>{el.textContent=prefix+fmt(to,decimals)+suffix;},delay+dur+80);
  };

  /* toast */
  let toastT;
  window.toast=function(msg){let t=$('#toast');if(!t){t=document.createElement('div');t.id='toast';t.className='toast';document.body.appendChild(t);}t.textContent=msg;t.classList.add('show');clearTimeout(toastT);toastT=setTimeout(()=>t.classList.remove('show'),1800);};

  /* tooltip anchored inside a tile */
  window.tipAt=function(host,x,y,text){let t=$('.tip',host);if(!t){t=document.createElement('div');t.className='tip';host.appendChild(t);}t.textContent=text;t.style.left=x+'px';t.style.top=y+'px';t.classList.add('show');clearTimeout(t._t);t._t=setTimeout(()=>t.classList.remove('show'),2200);};

  /* sheets */
  window.openSheet=id=>$('#'+id).classList.add('open');
  window.closeSheet=id=>$('#'+id).classList.remove('open');
  document.addEventListener('click',e=>{const ov=e.target.closest('.sheet-ov');if(ov&&e.target===ov)ov.classList.remove('open');});

  /* squarified treemap: items [{n,v,c}] → rects [{...,x,y,w,h}] */
  window.treemap=function(data,x,y,w,h){
    const total=data.reduce((s,d)=>s+d.v,0);const scale=w*h/total;
    const items=data.map(d=>({...d,a:d.v*scale})).sort((a,b)=>b.a-a.a);const rects=[];let i=0;
    while(i<items.length){
      const vertical=w>=h,side=vertical?h:w;let row=[],rowArea=0,best=Infinity;
      while(i<items.length){const cand=[...row,items[i]],ca=rowArea+items[i].a,rw=ca/side;let worst=0;cand.forEach(c=>{const len=c.a/rw;worst=Math.max(worst,rw/len,len/rw);});if(worst<=best){row=cand;rowArea=ca;best=worst;i++;}else break;}
      const rw=rowArea/side;let off=0;
      row.forEach(c=>{const len=c.a/rw;rects.push(vertical?{...c,x,y:y+off,w:rw,h:len}:{...c,x:x+off,y,w:len,h:rw});off+=len;});
      if(vertical){x+=rw;w-=rw;}else{y+=rw;h-=rw;}
    }
    return rects;
  };

  /* smooth path through points (Catmull-Rom → cubic bezier) */
  window.smooth=function(pts){if(pts.length<2)return '';let d=`M${pts[0][0]} ${pts[0][1]}`;for(let i=0;i<pts.length-1;i++){const p0=pts[i-1]||pts[i],p1=pts[i],p2=pts[i+1],p3=pts[i+2]||p2;const c1=[p1[0]+(p2[0]-p0[0])/6,p1[1]+(p2[1]-p0[1])/6],c2=[p2[0]-(p3[0]-p1[0])/6,p2[1]-(p3[1]-p1[1])/6];d+=` C${c1[0]} ${c1[1]} ${c2[0]} ${c2[1]} ${p2[0]} ${p2[1]}`;}return d;};

  document.addEventListener('DOMContentLoaded',()=>{
    $$('.nav-bar a[href="#"]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();toast('// screen not built in this concept');}));
    $$('.chips').forEach(c=>c.addEventListener('click',e=>{const ch=e.target.closest('.chip');if(!ch||ch.dataset.noSelect!=null)return;$$('.chip',c).forEach(x=>x.classList.remove('on'));ch.classList.add('on');}));
    setTimeout(()=>{$$('.skel').forEach(s=>s.classList.remove('skel'));document.body.classList.add('ready');document.dispatchEvent(new Event('data:ready'));},700);
  });
})();
