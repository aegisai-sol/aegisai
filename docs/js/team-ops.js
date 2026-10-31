import {rpc,RPCS,CLAIM_API,MINT,fmt,spark} from './live.js';
const MAX=1e10,PREMINT=1.5e9,MINT_AUTH='D96QgCXx93AMfKVLikbD8xbxQ6iB1bgrj9PWSiCVNgEg';
export const WALLETS=[{id:'team',name:'Team 10%',addr:'2MzLPXNvkU2VsezPFgdM6SGFHzddGURMguAFAFwKkoXM',ata:'GYiwsyME7ZRn9kQRBaxABA6aZy86F6r5qEatkYbr4Lx2',expect:1e9,col:'#f5c451'},{id:'eco',name:'Eco / pool 5%',addr:'9DmwoF1qJ8fASDasjkE2jacrEAWuRwUnDWwJ41eQgKan',ata:'C7QUgxf9BXLCho8Cod7FUgLMa6GrroqgumaFrsUmtrNZ',expect:5e8,col:'#22d3ee'}];
const $=i=>document.getElementById(i);
const ss=a=>`<a class="text-cyan underline" target="_blank" rel="noopener" href="https://solscan.io/account/${a}">${a.slice(0,6)}…${a.slice(-6)}</a>`;
const abort=ms=>{try{return AbortSignal.timeout(ms)}catch(e){const c=new AbortController();setTimeout(()=>c.abort(),ms);return c.signal}};
async function ping(u,o={}){const t=performance.now();try{const r=await fetch(u,{signal:abort(12000),...o});return{ok:r.ok,ms:Math.round(performance.now()-t)}}catch(e){return{ok:false,ms:Math.round(performance.now()-t)}}}
const row=(t,ok,x='')=>`<li class="flex justify-between gap-3"><span>${ok?'✅':'⚠️'} ${t}</span><span class="text-slate-500">${x}</span></li>`;
const busy=el=>` <p class="text-amber-300 text-xs mt-2">RPC busy — retrying…</p>`;

async function system(){
  $('sys').innerHTML='<li class="text-slate-500">checking…</li>';
  const [api,site,miner]=await Promise.all([
    ping(CLAIM_API+'/api/health'),
    ping(new URL('index.html',location.href).href,{cache:'no-store'}),
    ping(new URL('miner.html',location.href).href,{cache:'no-store'})
  ]);
  // Only probe first RPC quickly for health strip; others optional
  const primary=RPCS[0];
  let rpOk=false,rpMs=0;
  try{const t=performance.now();const r=await fetch(primary,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'getSlot'}),signal:abort(8000)});const j=await r.json();rpOk=r.ok&&j.result!==undefined;rpMs=Math.round(performance.now()-t)}catch(e){}
  $('sys').innerHTML=row('Claim API',api.ok,api.ms+' ms')+row('Public site',site.ok,site.ms+' ms')+row('Miner page',miner.ok,miner.ms+' ms')+row('RPC '+new URL(primary).host,rpOk,rpOk?rpMs+' ms':'down');
  return rpMs}

async function token(){
  $('tok').innerHTML='<div class="text-slate-500 text-sm">loading supply…</div>';
  const s=await rpc('getTokenSupply',[MINT]);const sup=+s.res.value.uiAmountString;
  const mi=await rpc('getAccountInfo',[MINT,{encoding:'jsonParsed'}]).catch(()=>null);const info=mi?.res?.value?.data?.parsed?.info||{};
  const mx=Math.max(sup,+(localStorage.teamMaxSeen||0));localStorage.teamMaxSeen=mx;
  $('tok').innerHTML=`<div><div class="k">Mint</div><div class="font-mono text-gold break-all text-xs">${MINT}</div></div>
 <div><div class="k">Supply / 10B</div><div class="font-mono text-cyan text-xl">${fmt(sup)} <span class="text-xs text-slate-500">(${(sup/MAX*100).toFixed(2)}%)</span></div></div>
 <div><div class="k">Mined ≈ supply − 1.5B</div><div class="font-mono text-gold text-xl">${fmt(Math.max(0,sup-PREMINT))}</div></div>
 <div><div class="k">Burned (est.)</div><div class="font-mono text-rose-300 text-xl">${fmt(mx-sup)}</div></div>
 <div><div class="k">Mint authority</div><div class="font-mono text-xs">${ss(info.mintAuthority||MINT_AUTH)} ${info.mintAuthority&&info.mintAuthority!==MINT_AUTH?'<b class="text-rose-400">CHANGED!</b>':''}</div></div>
 <div><div class="k">Freeze</div><div class="font-mono text-xs">${info.freezeAuthority===null?'✅ revoked':info.freezeAuthority?'⚠️ '+info.freezeAuthority:'revoked (expected)'}</div></div>`}

async function wallet(w){
  $(w.id).innerHTML=`<h2 class="font-bold text-lg">${w.name}</h2><p class="text-slate-500 text-sm mt-2">loading…</p>`;
  const tok=async()=>{try{return +(await rpc('getTokenAccountBalance',[w.ata])).res.value.uiAmountString}catch(e){const t=await rpc('getTokenAccountsByOwner',[w.addr,{mint:MINT},{encoding:'jsonParsed'}]);return t.res.value.reduce((a,x)=>a+(+x.account.data.parsed.info.tokenAmount.uiAmountString),0)}};
  const [bal,b]=await Promise.all([tok(),rpc('getBalance',[w.addr]).catch(()=>({res:{value:0}}))]);const sol=(b.res.value||0)/1e9;
  const H=JSON.parse(localStorage['teamHist_'+w.id]||'[]');H.push({t:Date.now(),bal});localStorage['teamHist_'+w.id]=JSON.stringify(H.slice(-300));
  const drop=bal<w.expect*0.999;
  $(w.id).innerHTML=`<div class="flex items-center justify-between"><h2 class="font-bold text-lg">${w.name}</h2>${drop?'<span class="px-2 py-1 rounded bg-rose-500/20 text-rose-300 text-xs font-bold">⚠ BELOW EXPECTED</span>':'<span class="px-2 py-1 rounded bg-emerald-500/15 text-emerald-300 text-xs">intact</span>'}</div>
 <div class="text-xs font-mono mt-1">${ss(w.addr)}</div>
 <div class="grid grid-cols-3 gap-3 mt-3"><div><div class="k">AGIS</div><div class="font-mono text-xl" style="color:${w.col}">${fmt(bal)}</div></div><div><div class="k">% of 10B</div><div class="font-mono text-xl">${(bal/MAX*100).toFixed(3)}%</div></div><div><div class="k">SOL</div><div class="font-mono text-xl">${sol.toFixed(4)}</div></div></div>
 <div class="text-[11px] text-slate-500 mt-1">Expected ${fmt(w.expect)} · diff ${fmt(bal-w.expect)}</div><canvas id="${w.id}c" height="50" class="w-full mt-2"></canvas>`;
  spark($(w.id+'c'),H.map(x=>x.bal),w.col)}

async function chain(){
  $('chain').innerHTML='<li class="text-slate-500">loading…</li>';
  const [sl,h,ep]=await Promise.all([rpc('getSlot',[]),rpc('getHealth',[]).catch(()=>({res:'unknown'})),rpc('getEpochInfo',[]).catch(()=>null)]);
  $('chain').innerHTML=row('Cluster health: '+h.res,h.res==='ok'||h.res==='OK')+row('Current slot',true,Number(sl.res).toLocaleString())+(ep&&ep.res?row('Epoch',true,ep.res.epoch+' ('+(ep.res.slotIndex/ep.res.slotsInEpoch*100).toFixed(1)+'%)'):'')+row('RPC via',true,new URL(sl.rpc).host+' · '+sl.ms+' ms')}

export async function run(){
  $('upd').textContent='loading…';
  const tick=async()=>{
    // Parallel sections — each paints as soon as ready
    await Promise.all([
      system().catch(e=>{$('sys').innerHTML=busy('sys')}),
      token().catch(e=>{$('tok').innerHTML=busy('tok')}),
      ...WALLETS.map(w=>wallet(w).catch(e=>{$(w.id).innerHTML=`<h2 class="font-bold">${w.name}</h2>`+busy(w.id)})),
      chain().catch(e=>{$('chain').innerHTML=busy('chain')})
    ]);
    $('upd').textContent=new Date().toLocaleString('en-GB',{timeZone:'Europe/Sofia'})+' (Sofia)';
  };
  tick();
  setInterval(tick,10000); // realtime-ish: 10s
}
