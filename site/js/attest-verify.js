// Verifies the AGIS network attestation (pov-r/seal-attest/1) in the browser with WebCrypto Ed25519.
// Not a government / eIDAS / notary signature.
import { RWA_API } from './rwa-jobs.js';
const FIELDS = ['alg','id','fingerprint','receiptTx','status','created','validUntil','anchoredBy','receiptAt'];
const A = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
export function b58(s){let n=0n;for(const c of s){const i=A.indexOf(c);if(i<0)throw Error('bad base58');n=n*58n+BigInt(i)}const o=[];while(n>0n){o.unshift(Number(n&255n));n>>=8n}for(const c of s){if(c!=='1')break;o.unshift(0)}return new Uint8Array(o)}
let keyP;const serverKey=()=>keyP||=fetch(RWA_API+'/card-key',{signal:AbortSignal.timeout(8000)}).then(r=>r.json()).then(d=>d.publicKey||null).catch(()=>null);
export async function verify(a){
  const msg=FIELDS.map(k=>`${k}=${a.fields?.[k]??''}`).join('\n');
  if(msg!==a.message)return{ok:false,why:'message does not match fields'};
  const pk=await serverKey();if(pk&&pk!==a.publicKey)return{ok:false,why:'signed by a key that is not the published AGIS key'};
  try{const k=await crypto.subtle.importKey('raw',b58(a.publicKey),{name:'Ed25519'},false,['verify']);
    return{ok:await crypto.subtle.verify({name:'Ed25519'},k,b58(a.signature),new TextEncoder().encode(msg)),pinned:!!pk}}
  catch(x){return{ok:null,why:'this browser cannot verify Ed25519 locally'}}
}
const e=t=>String(t??'').replace(/[&<>"']/g,c=>'&#'+c.charCodeAt(0)+';'),short=k=>k?k.slice(0,6)+'…'+k.slice(-4):'';
export async function attestBlock(el,j){
  const a=j&&j.attestation,s='font-size:13px;margin-top:8px';if(!el)return;
  if(!a){el.innerHTML='';return}
  if(a.status!=='signed'){el.innerHTML=`<p style="${s};color:#94a3b8">AGIS attestation: ${a.status==='pending'?'pending (waits for the Solana receipt)':'not available yet'}</p>`;return}
  el.innerHTML=`<p style="${s}">AGIS attestation: checking…</p>`;const r=await verify(a);
  const st=r.ok===true?'<b class="ok">✓ signature valid</b>'+(r.pinned?'':' <span class="w">(could not load published key)</span>'):r.ok===false?`<b class="bad">✗ invalid — ${e(r.why)}</b>`:`<b class="w">${e(r.why)}</b>`;
  el.innerHTML=`<p style="${s}">AGIS attestation: ${st}<br>Key <code title="${e(a.publicKey)}">${e(short(a.publicKey))}</code> · ${e(a.alg)} · Ed25519, checked in your browser</p><details style="font-size:12px;color:#94a3b8"><summary>Signed fields</summary><pre style="white-space:pre-wrap;word-break:break-all">${e(a.message)}</pre>Signature: <code>${e(a.signature)}</code><br>Public key: <a href="${RWA_API}/card-key" target="_blank">${e(a.publicKey)}</a></details><p style="font-size:12px;color:#94a3b8">This is the AGIS network confirming which seal receipt it accepted. It is not a government, eIDAS or notary signature.</p>`;
}
