// Live AGIS stats from Solana mainnet RPC (getTokenSupply). Burn = total ever minted − current supply (needs mint log; 0 until burns are recorded).
export const MINT='GhSiU95vtKwn7FBAW1u5krxYP2PnpFPotb1LJFZkbzhW';
export const RPCS=['https://solana.leorpc.com/?api_key=FREE','https://solana-rpc.publicnode.com','https://api.mainnet-beta.solana.com'];
export const CLAIM_API='https://agis-claim.onrender.com';
export const ALLOC_PREMINT=Number(localStorage.agisPremint||1.5e9); // team 10% + eco 5% pre-minted = 1.5B (on-chain supply at launch)
export async function rpc(method,params){for(const u of RPCS){try{const t=performance.now(),r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method,params}),signal:AbortSignal.timeout(6000)});if(!r.ok)continue;const j=await r.json();if(j.error)continue;if(j.result!==undefined)return{res:j.result,ms:Math.round(performance.now()-t),rpc:u}}catch(e){}}throw new Error('rpc down')}
async function proxySupply(){const t=performance.now(),r=await fetch(CLAIM_API+'/api/supply',{signal:AbortSignal.timeout(15000)}),j=await r.json();if(!j.ok)throw new Error('proxy');return{res:{value:{uiAmountString:j.uiAmountString}},ms:Math.round(performance.now()-t),rpc:'claim-proxy'}}
export async function snapshot(){const s=await rpc('getTokenSupply',[MINT]).catch(proxySupply),h=await rpc('getHealth',[]).catch(()=>({res:'unknown'})),slot=await rpc('getSlot',[]).catch(()=>({res:0}));
 const supply=+s.res.value.uiAmountString,minted=Math.max(supply,+(localStorage.agisMaxSeen||0));localStorage.agisMaxSeen=minted;
 const o={t:Date.now(),supply,mined:Math.max(0,supply-ALLOC_PREMINT),burned:+(minted-supply).toFixed(4),ms:s.ms,health:h.res==='ok'?'OK':String(h.res),slot:slot.res};
 const H=JSON.parse(localStorage.agisHist||'[]');H.push(o);localStorage.agisHist=JSON.stringify(H.slice(-500));return o}
export const hist=()=>JSON.parse(localStorage.agisHist||'[]');
export const fmt=x=>x>=1e9?(x/1e9).toFixed(2)+'B':x>=1e6?(x/1e6).toFixed(2)+'M':x>=1e3?(x/1e3).toFixed(1)+"K":(+x).toFixed(4);
export function spark(c,vals,col='#22d3ee'){const x=c.getContext('2d'),W=c.width=c.clientWidth,H=c.height;x.clearRect(0,0,W,H);if(vals.length<2){x.fillStyle='#475569';x.font='11px monospace';x.fillText('collecting data…',8,H/2);return}
 const lo=Math.min(...vals),hi=Math.max(...vals),r=hi-lo||1;x.beginPath();vals.forEach((v,i)=>x[i?'lineTo':'moveTo'](i/(vals.length-1)*W,H-4-(v-lo)/r*(H-8)));x.strokeStyle=col;x.lineWidth=1.5;x.stroke()}
// Mounts a compact live strip into any element with [data-live-strip]
export async function strip(){const el=document.querySelector('[data-live-strip]');if(!el)return;
 el.innerHTML='<div class="max-w-5xl mx-auto px-5 py-2 flex flex-wrap gap-x-6 gap-y-1 text-xs font-mono text-slate-400"><span><span id="lh" class="inline-block w-2 h-2 rounded-full bg-slate-500 mr-1"></span>Network <b id="lhs" class="text-slate-200">…</b></span><span>Mined <b id="lm" class="text-gold">…</b></span><span>Supply <b id="ls" class="text-cyan">…</b> / 10B</span><span>Burned <b id="lb" class="text-rose-300">…</b></span><a href="dashboard.html" class="ml-auto text-cyan">Live dashboard →</a></div>';
 const go=async()=>{try{const o=await snapshot();lm.textContent=fmt(o.mined);ls.textContent=fmt(o.supply);lb.textContent=fmt(o.burned);lhs.textContent=o.health+' · '+o.ms+'ms';lh.className='inline-block w-2 h-2 rounded-full mr-1 '+(o.health==='OK'?'bg-emerald-400':'bg-amber-400')}catch(e){lhs.textContent='RPC busy — retrying';lh.className='inline-block w-2 h-2 rounded-full mr-1 bg-amber-400'}};go();setInterval(go,30000)}
