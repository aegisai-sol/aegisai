// Seal page controller: Drop file → Connect wallet → Sign. Blockchain-only: no AegisAI server is called anywhere here.
import {wallet,connect,hasWallet} from './wallet.js';
import * as SC from './seal-chain.js';
import {signerText} from './chain-proof.js';
import {t,getLang} from './i18n.js';
import {RPCS} from './live.js';
import {certBlock} from './cert.js';
const $=i=>document.getElementById(i);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>'&#'+c.charCodeAt(0)+';');
const short=k=>k?String(k).slice(0,4)+'…'+String(k).slice(-4):'';
const loc=()=>getLang()==='bg'?'bg-BG':'en-GB';
const when=iso=>{try{return new Date(iso).toLocaleString(loc())}catch{return iso}};
const L=()=>{try{return JSON.parse(localStorage.agisSeals||'[]')}catch{return[]}},S=a=>localStorage.agisSeals=JSON.stringify(a.slice(0,200));
let W,file=null,fp=null,fname='',balance=null,feeLamports=SC.BASE_FEE_LAMPORTS,usd=0,busy=false,lastOut=null,lastVerify=null;
const web3=()=>W||(W=import('https://esm.sh/@solana/web3.js@1.95.3'));
async function conn(){const w=await web3();for(const u of RPCS){try{const c=new w.Connection(u,'confirmed');await c.getLatestBlockhash('confirmed');return c}catch(e){}}throw Object.assign(new Error('rpc'),{code:'rpc'})}
async function rpcCall(method,params){for(const u of RPCS){try{const r=await fetch(u,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params})});const j=await r.json();if(j.result!==undefined)return j.result}catch(e){}}throw new Error('rpc')}
async function saveBlob(blob,name){const mob=/iP(hone|ad|od)|Android/i.test(navigator.userAgent);if(mob)try{const f=new File([blob],name,{type:blob.type});if(navigator.canShare&&navigator.canShare({files:[f]})){await navigator.share({files:[f],title:name});return}}catch(e){if(e&&e.name==='AbortError')return}
 const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),6e4)}
function copy(text,btn){const done=()=>{const o=btn.textContent;btn.textContent=t('s2.r.copied');setTimeout(()=>btn.textContent=o,1600)};(navigator.clipboard?navigator.clipboard.writeText(text):Promise.reject()).then(done,()=>{const x=document.createElement('textarea');x.value=text;document.body.appendChild(x);x.select();document.execCommand('copy');x.remove();done()})}
// ── fee (live) ──
async function solUsd(){if(usd)return usd;try{const r=await fetch('https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd');usd=+(await r.json()).solana.usd||0}catch{}return usd}
async function liveFee(){try{if(!wallet.pubkey||!fp)return;const w=await web3(),c=await conn();const p=await SC.prepareSeal({fingerprint:fp,wallet:wallet.pubkey});const {blockhash,lastValidBlockHeight}=await c.getLatestBlockhash('confirmed');const tx=SC.buildSealTx(w,{payer:wallet.pubkey,memo:p.memo,indexAddress:p.indexAddress,blockhash,lastValidBlockHeight});const f=await c.getFeeForMessage(tx.compileMessage(),'confirmed');if(f&&typeof f.value==='number')feeLamports=f.value}catch(e){}renderFee()}
async function renderFee(){const sol=SC.feeSol(feeLamports),p=await solUsd();$('fee').textContent=`~${sol.toFixed(6).replace(/0+$/,'')} SOL`+(p?` (~$${(sol*p).toFixed(4)})`:'')}
async function refreshBalance(){balance=null;if(!wallet.pubkey)return renderSteps();try{const r=await rpcCall('getBalance',[wallet.pubkey,{commitment:'confirmed'}]);balance=r.value}catch{}renderSteps()}
// ── steps ──
function renderSteps(){const has=!!fp,con=!!wallet.pubkey,low=con&&balance!==null&&balance<feeLamports;
 $('st1').className='panel p-4 step '+(has?'ok':'on');$('st2').className='panel p-4 step '+(con?'ok':has?'on':'');$('st3').className='panel p-4 step '+(has&&con?'on':'');
 let h='';
 if(con)h=`<div class="text-sm text-emerald-300">✓ ${esc(t('s2.connected'))} <span class="font-mono text-slate-200">${esc(short(wallet.pubkey))}</span>${balance!==null?` · ${esc(t('s2.balance'))} <b class="text-slate-200">${(balance/1e9).toFixed(4)} SOL</b>`:''}</div>${low?`<p class="text-xs text-rose-300 mt-1">${esc(t('s2.lowsol'))}</p>`:''}`;
 else{const any=hasWallet();h=`<button id="wc" class="big bg-cyan text-navy">${esc(t(any?'s2.connect':'s2.getwallet'))}</button>${any?'':`<p class="text-[11px] text-slate-500 mt-1">${esc(t('s2.getwallet.sub'))}</p>`}<p class="text-xs text-amber-300 mt-2">⚠ ${esc(t('s2.nowallet'))}</p>${has?`<button id="lo" class="mt-2 w-full min-h-[44px] rounded-xl border border-slate-600 text-slate-300 text-sm">${esc(t('s2.localonly.btn'))}</button>`:''}`}
 $('w2').innerHTML=h;
 if($('wc'))$('wc').onclick=async()=>{try{await connect()}catch(e){}};
 if($('lo'))$('lo').onclick=saveLocal;
 $('sign').disabled=busy||!has||!con||low;
 $('need').textContent=busy?'':!has?t('s2.need1'):!con?t('s2.need2'):'';
}
function setStat(k,cls='text-cyan'){$('stat').innerHTML=k?`<span class="${cls}">${k}</span>`:''}
// ── file ──
async function pick(f){if(!f)return;if(f.size>200e6){alert(t('s2.toobig'));return}file=f;fname=f.name||'file';fp=null;$('fInfo').classList.remove('hidden');$('fName').textContent=fname+' · '+Math.max(1,Math.round(f.size/1e3))+' KB';$('fHash').textContent=t('s2.fp.working');$('fOk').classList.add('hidden');
 fp=await SC.sha256Hex(await f.arrayBuffer());$('fHash').textContent=fp;$('fOk').classList.remove('hidden');$('out').classList.add('hidden');setStat('');renderSteps();liveFee()}
$('f').onchange=e=>pick(e.target.files[0]);$('fc').onchange=e=>pick(e.target.files[0]);
const dnd=(el,fn)=>{el.addEventListener('dragover',e=>{e.preventDefault();el.classList.add('over')});el.addEventListener('dragleave',()=>el.classList.remove('over'));el.addEventListener('drop',e=>{e.preventDefault();el.classList.remove('over');const f=e.dataTransfer.files[0];if(f)fn(f)})};
dnd($('dz'),pick);
// ── seal ──
function errText(e){const m=String(e&&(e.message||e)||'');if(e&&(e.code===4001||/reject|cancel|denied|declined|closed/i.test(m)))return t('s2.err.reject');if(e&&e.code==='rpc'||/blockhash|failed to fetch|rpc|network|timeout/i.test(m))return t('s2.err.rpc');if(e&&e.code==='fail')return t('s2.err.fail');return t('s2.err.generic')+' '+m}
async function sealNow(rec){if(busy)return;const f=rec?rec.fingerprint:fp;if(!SC.isFp(f))return;
 if(!wallet.pubkey){try{await connect()}catch(e){}if(!wallet.pubkey)return}
 busy=true;renderSteps();setStat(esc(t('s2.st.approve')));
 try{const w=await web3(),c=await conn();const prep=await SC.prepareSeal({fingerprint:f,wallet:wallet.pubkey,validHours:+$('validFor').value||0});
  const {blockhash,lastValidBlockHeight}=await c.getLatestBlockhash('confirmed');const tx=SC.buildSealTx(w,{payer:wallet.pubkey,memo:prep.memo,indexAddress:prep.indexAddress,blockhash,lastValidBlockHeight});
  const p=wallet.provider;let sig;
  if(p&&p.signAndSendTransaction){const r=await p.signAndSendTransaction(tx);sig=r&&(r.signature||r)}
  else if(p&&p.signTransaction){const s=await p.signTransaction(tx);setStat(esc(t('s2.st.send')));sig=await c.sendRawTransaction(s.serialize())}
  else throw new Error('wallet cannot sign transactions');
  if(typeof sig!=='string')sig=SC.b58encode(sig);
  setStat(esc(t('s2.st.confirm')));
  await confirmHttp(sig,lastValidBlockHeight);
  const rc={...prep,tx:sig,receiptTx:sig,name:rec?rec.name:fname,status:'onchain',ts:Date.now(),final:false};
  const a=L().filter(x=>!(x.fingerprint===f&&!x.receiptTx&&!x.tx));S([rc,...a]);
  setStat('');showReceipt(rc);renderList();pollFinal(rc)}
 catch(e){console.warn(e);setStat(esc(errText(e)),'text-rose-300')}
 finally{busy=false;renderSteps()}}
$('sign').onclick=()=>sealNow();
// HTTP-only confirmation (no websocket): poll getSignatureStatuses until confirmed, error, or blockhash expiry.
async function confirmHttp(sig,lastValid){const t0=Date.now();while(Date.now()-t0<120e3){try{const s=await rpcCall('getSignatureStatuses',[[sig],{searchTransactionHistory:false}]);const v=s.value&&s.value[0];if(v&&v.err)throw Object.assign(new Error('fail'),{code:'fail'});if(v&&(v.confirmationStatus==='confirmed'||v.confirmationStatus==='finalized'))return v}catch(e){if(e.code==='fail')throw e}
 try{const h=await rpcCall('getBlockHeight',[{commitment:'confirmed'}]);if(h>lastValid)throw Object.assign(new Error('blockhash expired — not sealed'),{code:'fail'})}catch(e){if(e.code==='fail')throw e}await new Promise(r=>setTimeout(r,1500))}throw Object.assign(new Error('timeout'),{code:'rpc'})}
function saveLocal(){if(!fp)return;const rc={id:null,fingerprint:fp,name:fname,status:'local',ts:Date.now()};S([rc,...L().filter(x=>!(x.status==='local'&&x.fingerprint===fp))]);showLocal(rc);renderList()}
async function pollFinal(rc){for(let i=0;i<20;i++){await new Promise(r=>setTimeout(r,4000));try{const s=await rpcCall('getSignatureStatuses',[[rc.tx],{searchTransactionHistory:true}]);const v=s.value&&s.value[0];if(v&&v.err)return;if(v&&v.confirmationStatus==='finalized'){const tx=await rpcCall('getTransaction',[rc.tx,{encoding:'json',maxSupportedTransactionVersion:0,commitment:'finalized'}]).catch(()=>null);rc.final=true;rc.blockTime=tx&&tx.blockTime||null;const a=L();const x=a.find(y=>y.tx===rc.tx||y.receiptTx===rc.tx);if(x)Object.assign(x,{final:true,blockTime:rc.blockTime});S(a);if(lastOut&&lastOut.rc&&lastOut.rc.tx===rc.tx)showReceipt(rc);renderList();return}}catch{}}}
// ── receipt ──
function receiptRows(r){return[[t('s2.r.id'),r.id||'—'],[t('s2.r.fp'),r.fingerprint],[t('s2.r.tx'),r.tx],[t('s2.r.time'),(r.blockTime?when(new Date(r.blockTime*1000).toISOString()):when(r.created))+' · '+(r.created||'')],[t('s2.r.signer'),r.wallet||'—'],[t('s2.r.valid'),r.validUntil?when(r.validUntil):t('s2.valid.forever')],...(r.name?[[t('s2.r.file'),r.name]]:[])]}
function showReceipt(r){lastOut={kind:'receipt',rc:r};const o=$('out');o.classList.remove('hidden');const proof=SC.proofLink('https://aegisai-sol.github.io/aegisai/proof.html',r);
 o.innerHTML=`<div class="panel p-4" style="border-color:rgba(52,211,153,.45)"><div class="text-emerald-300 font-extrabold text-lg">${esc(t('s2.done'))}</div><p class="text-xs text-slate-400 mt-1">${esc(t('s2.done.sub'))}</p><span class="chip mt-2 ${r.final?'bg-emerald-500/15 text-emerald-300':'bg-amber-500/15 text-amber-300'}">${esc(t(r.final?'s2.final.ok':'s2.final.wait'))}</span>
 <dl class="kv mt-3">${receiptRows(r).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>
 <div class="grid grid-cols-2 gap-2 mt-4 text-sm"><button id="rDl" class="min-h-[44px] rounded-xl bg-gold text-navy font-bold">${esc(t('s2.r.dl'))}</button><button id="rPr" class="min-h-[44px] rounded-xl border border-gold/50 text-gold">${esc(t('s2.r.print'))}</button><button id="rLk" class="min-h-[44px] rounded-xl border border-cyan/40 text-cyan">${esc(t('s2.r.link'))}</button><a class="min-h-[44px] rounded-xl border border-cyan/40 text-cyan flex items-center justify-center" target="_blank" rel="noopener" href="${esc(SC.solscanTx(r.tx))}">${esc(t('s2.r.solscan'))}</a></div>
 <details class="mt-3 text-xs"><summary class="cursor-pointer text-slate-400 min-h-[32px]">${esc(t('s2.r.qr'))}</summary><div id="certB" class="mt-2"></div></details></div>`;
 $('rDl').onclick=()=>saveBlob(new Blob([JSON.stringify(SC.receiptObject(r),null,2)],{type:'application/json'}),`agis-seal-receipt-${r.id}.json`);
 $('rPr').onclick=()=>printReceipt(r);$('rLk').onclick=()=>copy(proof,$('rLk'));
 o.querySelector('details').addEventListener('toggle',function f(){o.querySelector('details').removeEventListener('toggle',f);certBlock($('certB'),{id:r.id,fingerprint:r.fingerprint,receiptTx:r.tx,status:'sealed',created:r.created,validUntil:r.validUntil})});
 o.scrollIntoView({behavior:'smooth',block:'start'})}
function printReceipt(r){$('printArea').innerHTML=`<h1 style="font-size:20px;margin:0 0 4px">AegisAI · AGIS seal receipt</h1><p style="margin:0 0 12px">Solana mainnet · AEGIS/rwa/v1</p><table style="border-collapse:collapse">${receiptRows(r).map(([k,v])=>`<tr><td style="padding:4px 12px 4px 0;vertical-align:top"><b>${esc(k)}</b></td><td style="padding:4px 0;font-family:monospace;word-break:break-all">${esc(v)}</td></tr>`).join('')}</table><p style="margin-top:14px">Solscan: ${esc(SC.solscanTx(r.tx))}</p><p>Verify: aegisai-sol.github.io/aegisai/rwa.html#verify — drop the original file or paste the transaction. Works from Solana alone.</p><p style="font-size:11px">A seal proves this exact file existed unchanged at that time. It is not a notary or eIDAS stamp.</p>`;window.print()}
function showLocal(r){lastOut={kind:'local',rc:r};const o=$('out');o.classList.remove('hidden');o.innerHTML=`<div class="panel p-4" style="border-color:rgba(251,191,36,.5)"><div class="text-amber-300 font-extrabold">⚠ ${esc(t('s2.local.h'))}</div><p class="text-xs text-slate-400 mt-1">${esc(t('s2.local.sub'))}</p><div class="font-mono text-[11px] text-slate-500 break-all mt-2">${esc(r.fingerprint)}</div><button id="lPut" class="big mt-3 bg-cyan text-navy">${esc(t('s2.local.put'))}</button></div>`;$('lPut').onclick=()=>sealNow(r)}
// ── list ──
function renderList(){const a=L();$('q').innerHTML=a.length?a.map((j,i)=>{const tx=j.receiptTx||j.tx;return`<div class="bg-deep/60 rounded-lg p-2"><div class="flex gap-2 items-center"><span class="truncate text-slate-200">${esc(j.name||'—')}</span><span class="ml-auto shrink-0 chip ${tx?'bg-emerald-500/15 text-emerald-300':'bg-amber-500/15 text-amber-300'}">${esc(t(tx?'s2.list.chain':'s2.list.local'))}</span></div><div class="font-mono text-[10px] text-slate-500 break-all">${esc(j.fingerprint)}</div><div class="flex gap-3 mt-1">${tx?`<a class="text-cyan underline" target="_blank" rel="noopener" href="${esc(SC.solscanTx(tx))}">Solscan ↗</a>${j.memo?`<button class="text-gold underline" data-rc="${i}">${esc(t('s2.list.receipt'))}</button>`:''}`:`<button class="text-cyan underline min-h-[28px]" data-put="${i}">${esc(t('s2.list.put'))}</button>`}</div></div>`}).join(''):`<div class="text-slate-500">${esc(t('s2.list.empty'))}</div>`;
 $('q').querySelectorAll('[data-rc]').forEach(b=>b.onclick=()=>{const j=L()[+b.dataset.rc];showReceipt({...j,tx:j.tx||j.receiptTx})});
 $('q').querySelectorAll('[data-put]').forEach(b=>b.onclick=()=>{const j=L()[+b.dataset.put];document.getElementById('tS').click();sealNow(j)})}
// ── verify ──
let vfp=null;
function proofHtml(p){const vu=p.validUntil;return`<div class="mt-2 rounded-lg bg-deep/60 p-3 text-xs space-y-1"><div>${esc(t('v2.sealed'))}: <b class="text-slate-100">${esc(p.blockTime?when(new Date(p.blockTime*1000).toISOString()):when(p.created))}</b></div><div>${esc(t('s2.r.id'))}: <span class="font-mono text-cyan">${esc(p.id)}</span></div><div class="text-slate-300">${esc(signerText(p,t))}</div>${vu?`<div>${esc(t('s2.r.valid'))}: <b class="${p.expired?'text-rose-400':'text-emerald-300'}">${p.expired?esc(t('v2.expired'))+' · ':''}${esc(when(vu))}</b></div>`:''}<div class="font-mono text-[10px] text-slate-500 break-all">${esc(p.fingerprint)}</div><div class="flex gap-3"><a class="text-cyan underline" target="_blank" rel="noopener" href="${esc(SC.solscanTx(p.receiptTx))}">Solscan ↗</a><a class="text-gold underline" href="proof.html?id=${esc(p.id)}&tx=${esc(p.receiptTx)}">${esc(t('v2.prooflink'))}</a></div></div>`}
function renderVerify(res){lastVerify=res;const o=$('vr');if(!res)return o.innerHTML='';const P=(res.proofs||[]).map(proofHtml).join('');const foot=`<p class="text-[11px] text-slate-500 mt-3">${esc(t('v2.chainonly'))}</p>`;
 const box=(cls,h,sub)=>`<div class="rounded-xl border ${cls} p-3"><div class="font-extrabold">${esc(t(h))}</div>${sub?`<p class="text-xs text-slate-300 mt-1">${esc(t(sub))}</p>`:''}</div>`;
 o.innerHTML={match:box('border-emerald-500/50 bg-emerald-500/10 text-emerald-300','v2.match','v2.match.sub')+P+foot,found:box('border-cyan/50 bg-cyan/10 text-cyan','v2.found','v2.found.sub')+P+foot,mismatch:box('border-rose-500/50 bg-rose-500/10 text-rose-300','v2.mismatch','v2.mismatch.sub')+P+foot,'no-seal':box('border-amber-500/50 bg-amber-500/10 text-amber-300','v2.none','v2.none.sub')+foot,'need-tx':box('border-amber-500/50 bg-amber-500/10 text-amber-300','v2.needtx'),bad:box('border-rose-500/50 text-rose-300','v2.bad'),empty:box('border-slate-600 text-slate-300','v2.empty'),rpc:box('border-rose-500/50 text-rose-300','s2.err.rpc'),working:`<div class="text-cyan">${esc(t('v2.working'))}</div>`}[res.status]||''}
async function runVerify(){const inp=SC.parseVerifyInput($('vh').value);if(inp.bad)return renderVerify({status:'bad'});if(!inp.tx&&!inp.fingerprint&&!inp.id&&!vfp)return renderVerify({status:'empty'});
 renderVerify({status:'working'});try{renderVerify(await SC.verifyOnChain({...inp,fileFp:vfp}))}catch(e){renderVerify({status:'rpc'})}}
async function pickV(f){if(!f)return;$('vfn').textContent=(f.name||'file')+' · '+t('s2.fp.working');vfp=await SC.sha256Hex(await f.arrayBuffer());$('vfn').textContent=(f.name||'file')+' · '+vfp.slice(0,16)+'…';runVerify()}
$('vf').onchange=e=>pickV(e.target.files[0]);dnd($('vdz'),pickV);$('vb').onclick=runVerify;$('vh').addEventListener('keydown',e=>{if(e.key==='Enter')runVerify()});
// ── tabs ──
function tab(v){$('pS').classList.toggle('hidden',v);$('pV').classList.toggle('hidden',!v);$('tS').setAttribute('aria-selected',String(!v));$('tV').setAttribute('aria-selected',String(v));history.replaceState(null,'',v?'#verify':location.pathname+location.search)}
$('tS').onclick=()=>tab(false);$('tV').onclick=()=>tab(true);
if(location.hash==='#verify')tab(true);
window.addEventListener('hashchange',()=>tab(location.hash==='#verify'));
{const q=new URLSearchParams(location.search),tx=q.get('tx');if(tx){$('vh').value=tx;tab(true);runVerify()}}
// ── wiring ──
document.addEventListener('agis:wallet',()=>{refreshBalance();liveFee()});
window.addEventListener('agis:lang',()=>{renderSteps();renderList();renderFee();if(lastOut)(lastOut.kind==='receipt'?showReceipt:showLocal)(lastOut.rc);if(lastVerify)renderVerify(lastVerify)});
window.addEventListener('load',()=>setTimeout(renderSteps,300));
renderSteps();renderList();renderFee();
