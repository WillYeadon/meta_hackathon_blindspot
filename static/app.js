/* Shared read-only UI helpers. The recorded-study viewer never starts a model run. */
const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const points = value => value == null ? '—' : `${value>0?'+':''}${Math.round(value*100)} pp`;
async function api(path) {
  const response=await fetch(path,{headers:{'Accept':'application/json'}});
  const data=await response.json();
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data));
  return data;
}
let toastTimer;
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,5500);}
$('#method-button').addEventListener('click',()=>$('#method-dialog').showModal());
$('#close-method').addEventListener('click',()=>$('#method-dialog').close());
$('#method-dialog').addEventListener('click',event=>{if(event.target===event.currentTarget&&event.offsetX<0)event.currentTarget.close();});
