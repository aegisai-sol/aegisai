// AGIS seal success animation: file -> SHA-256 fingerprint -> Solana Memo receipt. Illustrative only.
const CSS=`.sa{position:relative;height:150px;margin:0 0 12px;border-radius:14px;overflow:hidden;background:radial-gradient(120% 90% at 50% 0%,rgba(34,211,238,.10),transparent 60%),#060e1c;border:1px solid rgba(34,211,238,.18)}
.sa *{box-sizing:border-box}.sa-doc{position:absolute;left:8%;top:44px;width:40px;height:52px;border-radius:6px;background:linear-gradient(160deg,#1e293b,#0f172a);border:1.5px solid #22d3ee;box-shadow:0 0 14px rgba(34,211,238,.35);display:flex;align-items:center;justify-content:center;font:700 9px ui-monospace,monospace;color:#22d3ee;animation:saDoc 4.2s ease-in-out forwards}
.sa-doc:before{content:"";position:absolute;right:-1.5px;top:-1.5px;border:7px solid;border-color:#060e1c #060e1c transparent transparent}
.sa-fp{position:absolute;left:8%;top:52px;width:36px;height:36px;border-radius:50%;opacity:0;background:radial-gradient(circle,#f5c451 0 22%,rgba(245,196,81,.25) 45%,transparent 70%);box-shadow:0 0 22px #f5c451;animation:saFp 4.2s ease-in-out forwards}
.sa-chain{position:absolute;right:6%;top:50px;display:flex;gap:6px;align-items:center}
.sa-b{width:28px;height:28px;border-radius:7px;border:1.5px solid rgba(34,211,238,.45);background:rgba(34,211,238,.06);position:relative}
.sa-b:not(:last-child):after{content:"";position:absolute;right:-7px;top:12px;width:6px;height:2px;background:rgba(34,211,238,.45)}
.sa-b.n{border-color:#f5c451;opacity:.15;animation:saNew 4.2s ease-out forwards}
.sa-cap{position:absolute;left:0;right:0;bottom:12px;text-align:center;font:600 11px system-ui,sans-serif;color:#94a3b8;letter-spacing:.02em}
.sa-cap span{position:absolute;left:0;right:0;opacity:0}.sa-cap .c1{animation:saC 4.2s 0s forwards}.sa-cap .c2{animation:saC 4.2s 1.4s forwards}.sa-cap .c3{animation:saEnd 4.2s 2.8s forwards}
.sa-tag{position:absolute;right:6%;top:18px;font:700 10px ui-monospace,monospace;color:#f5c451;opacity:0;animation:saEnd 4.2s 2.9s forwards}
.sa-tag.ok{color:#34d399}
@keyframes saDoc{0%{opacity:0;transform:scale(.6)}12%{opacity:1;transform:scale(1)}30%{transform:translateX(30px)}42%{opacity:0;transform:translateX(60px) scale(.3)}100%{opacity:0}}
@keyframes saFp{0%,34%{opacity:0;left:8%;transform:scale(.3)}44%{opacity:1;left:calc(8% + 50px);transform:scale(1) rotate(90deg)}66%{opacity:1;left:calc(94% - 34px);transform:scale(.8) rotate(360deg)}74%,100%{opacity:0;left:calc(94% - 34px);transform:scale(.2)}}
@keyframes saNew{0%,66%{opacity:.15;box-shadow:none}74%{opacity:1;background:rgba(245,196,81,.35);box-shadow:0 0 22px #f5c451}100%{opacity:1;background:rgba(245,196,81,.15);box-shadow:0 0 10px rgba(245,196,81,.5)}}
@keyframes saC{0%{opacity:0}8%,30%{opacity:1}34%,100%{opacity:0}}
@keyframes saEnd{0%{opacity:0}10%,100%{opacity:1}}
@media (prefers-reduced-motion:reduce){.sa *{animation:none!important}.sa-doc,.sa-fp,.sa-cap .c1,.sa-cap .c2{opacity:0}.sa-b.n{opacity:1;background:rgba(245,196,81,.15)}.sa-cap .c3,.sa-tag{opacity:1}}`;
export function sealAnim(el,{ext='FILE',verified=false}={}){
 if(!document.getElementById('saCss')){const s=document.createElement('style');s.id='saCss';s.textContent=CSS;document.head.appendChild(s)}
 const e=String(ext).replace(/[^a-z0-9]/gi,'').slice(0,4).toUpperCase()||'FILE';
 el.innerHTML=`<div class="sa" role="img" aria-label="Your file's fingerprint is anchored as a receipt on Solana"><div class="sa-doc">${e}</div><div class="sa-fp"></div><div class="sa-chain"><div class="sa-b"></div><div class="sa-b"></div><div class="sa-b"></div><div class="sa-b n"></div></div><div class="sa-tag${verified?' ok':''}" data-satag>${verified?'✓ VERIFIED':'SEALING…'}</div><div class="sa-cap"><span class="c1">Fingerprint made in your browser (SHA-256)</span><span class="c2">Fingerprint travels to the network</span><span class="c3">Receipt joins Solana as a Memo — permanent</span></div></div>`;
}
export function sealAnimStatus(el,verified){const t=el&&el.querySelector('[data-satag]');if(t&&verified){t.textContent='✓ VERIFIED';t.classList.add('ok')}}
