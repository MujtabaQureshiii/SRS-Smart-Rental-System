'use strict';
// Purposefully restrained visual effects. All business operations remain server-validated.
document.querySelectorAll('form').forEach(form=>{
 form.addEventListener('submit',e=>{
  if(form.dataset.confirm && !window.confirm(form.dataset.confirm)){e.preventDefault();return;}
  if(e.defaultPrevented || !form.checkValidity())return;
  const button=form.querySelector('button[type="submit"],button:not([type])');
  if(button){button.classList.add('loading');button.setAttribute('aria-busy','true');}
 });
});
if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches){
 for(const el of document.querySelectorAll('.count[data-value]')){
  const target=Number(el.dataset.value);if(!Number.isFinite(target)||target>5000)continue;
  const started=performance.now();const duration=550;
  function tick(t){const p=Math.min(1,(t-started)/duration);el.textContent=String(Math.round(target*(1-(1-p)*(1-p))));if(p<1)requestAnimationFrame(tick);}
  requestAnimationFrame(tick);
 }
}

// Load actual licensed sample product photos; fall back gracefully when offline.
document.querySelectorAll('img[data-remote]').forEach(img=>{
 let triedRemote=false;
 img.addEventListener('load',()=>{img.style.opacity='1';});
 img.addEventListener('error',()=>{
  if(!triedRemote && img.dataset.remote){triedRemote=true;img.src=img.dataset.remote;return;}
  img.style.display='none';
  const fallback=img.nextElementSibling;
  if(fallback && fallback.classList.contains('cork-photo-fallback')) fallback.style.display='grid';
 });
 if(img.complete){if(img.naturalWidth>0)img.style.opacity='1';else img.dispatchEvent(new Event('error'));}
});
const printButton=document.querySelector('[data-print-station-qr]');
if(printButton)printButton.addEventListener('click',()=>window.print());
