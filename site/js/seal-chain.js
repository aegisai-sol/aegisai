// Blockchain-only seals (AEGIS/rwa/v1). Built in the browser, signed + paid by the user's wallet, sent straight to Solana RPC.
// No AegisAI server: no upload, no job, no index. The file never leaves the device — only its SHA-256 goes on-chain.
// Tx = [Memo "AEGIS/rwa/v1|id|sha256|sealed|createdISO|validUntil|forever"] + [0-lamport self-transfer carrying a read-only
// "fingerprint index" key = sha256("AEGIS/rwa/v1/fp|"+sha256)]. Anyone can later find the seal from the file alone via
// getSignaturesForAddress(indexKey) — an index that lives on Solana itself (same trick as Solana Pay "reference" keys).
import {rpc as liveRpc} from './live.js';
import {parseMemo,proofFromParsedTx,SEAL_SIGNER,fromTx as firmFromTx} from './chain-proof.js';
export const MEMO_PROGRAM='MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr';
export const SYSTEM_PROGRAM='11111111111111111111111111111111';
export const BASE_FEE_LAMPORTS=5000; // 1 signature
export const LAMPORTS=1e9;
const A='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
export function b58encode(bytes){const u=bytes instanceof Uint8Array?bytes:new Uint8Array(bytes);let n=0n;for(const b of u)n=n*256n+BigInt(b);let s='';while(n>0n){s=A[Number(n%58n)]+s;n/=58n}for(const b of u){if(b!==0)break;s='1'+s}return s}
export function b58decode(s){let n=0n;for(const c of String(s)){const i=A.indexOf(c);if(i<0)throw new Error('bad base58');n=n*58n+BigInt(i)}const o=[];while(n>0n){o.unshift(Number(n&255n));n>>=8n}for(const c of String(s)){if(c!=='1')break;o.unshift(0)}return new Uint8Array(o)}
const subtle=()=>globalThis.crypto.subtle;
export const hex=b=>[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('');
export async function sha256Hex(buf){return hex(await subtle().digest('SHA-256',buf))}
const enc=s=>new TextEncoder().encode(s);
export const isFp=s=>/^[0-9a-f]{64}$/.test(String(s||''));
export const isTxSig=s=>/^[1-9A-HJ-NP-Za-km-z]{64,90}$/.test(String(s||''));
export const isPubkey=s=>/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(String(s||''));
// Deterministic on-chain index key for a fingerprint (32 bytes, need not be on-curve; never signs, never holds funds).
export async function fpIndexBytes(fp){if(!isFp(fp))throw new Error('bad fingerprint');return new Uint8Array(await subtle().digest('SHA-256',enc('AEGIS/rwa/v1/fp|'+fp)))}
export async function fpIndexAddress(fp){return b58encode(await fpIndexBytes(fp))}
// 12-hex seal id: unique per (file, wallet, time); compatible with the verifier regex.
export async function makeSealId(fp,wallet,createdISO){return (await sha256Hex(enc(`${fp}|${wallet}|${createdISO}`))).slice(0,12)}
export function validUntilISO(createdISO,hours){const h=Number(hours||0);return h>0?new Date(Date.parse(createdISO)+h*3600e3).toISOString():null}
export function buildMemo({id,fingerprint,created,validUntil}){if(!/^[0-9a-f]{12}$/.test(id))throw new Error('bad seal id');if(!isFp(fingerprint))throw new Error('bad fingerprint');const m=`AEGIS/rwa/v1|${id}|${fingerprint}|sealed|${created}|${validUntil||'forever'}`;const p=parseMemo(m);if(!p||p.id!==id||p.fingerprint!==fingerprint)throw new Error('memo not verifier-compatible');return m}
export async function prepareSeal({fingerprint,wallet,validHours=0,now=new Date()}){if(!isPubkey(wallet))throw new Error('connect a wallet first');const created=new Date(now).toISOString();const id=await makeSealId(fingerprint,wallet,created);const validUntil=validUntilISO(created,validHours);const memo=buildMemo({id,fingerprint,created,validUntil});return{id,fingerprint,wallet,created,validUntil,memo,indexAddress:await fpIndexAddress(fingerprint)}}
// Build the unsigned legacy Transaction with an injected @solana/web3.js namespace W (browser: esm.sh; tests: mock or real).
export function buildSealTx(W,{payer,memo,indexAddress,blockhash,lastValidBlockHeight}){const P=new W.PublicKey(payer);const tx=new W.Transaction({feePayer:P,blockhash,lastValidBlockHeight});
 tx.add(new W.TransactionInstruction({programId:new W.PublicKey(MEMO_PROGRAM),keys:[{pubkey:P,isSigner:true,isWritable:false}],data:enc(memo)}));
 const t=W.SystemProgram.transfer({fromPubkey:P,toPubkey:P,lamports:0});t.keys.push({pubkey:new W.PublicKey(indexAddress),isSigner:false,isWritable:false});tx.add(t);return tx}
export const solscanTx=s=>'https://solscan.io/tx/'+s;
export const explorerTx=s=>'https://explorer.solana.com/tx/'+s;
export const proofLink=(base,r)=>`${base}?id=${r.id}&tx=${r.tx}`;
export function receiptObject(r){return{type:'AEGIS seal receipt',version:'rwa/v1',network:'solana-mainnet',sealId:r.id,fingerprintSha256:r.fingerprint,tx:r.tx,signer:r.wallet,memo:r.memo,created:r.created,validUntil:r.validUntil||'forever',blockTime:r.blockTime?new Date(r.blockTime*1000).toISOString():null,fileName:r.name||null,solscan:solscanTx(r.tx),explorer:explorerTx(r.tx),proof:proofLink('https://aegisai-sol.github.io/aegisai/proof.html',r),howToVerify:'Open aegisai-sol.github.io/aegisai/rwa.html#verify, drop the original file (or paste this tx). Works from Solana alone — no AegisAI server.'}}
export function parseReceiptText(s){s=String(s||'').trim();if(!s.startsWith('{'))return null;try{const j=JSON.parse(s);const tx=j.tx||j.receiptTx||j.signature;if(!isTxSig(tx))return null;return{tx,fingerprint:isFp(j.fingerprintSha256)?j.fingerprintSha256:isFp(j.fingerprint)?j.fingerprint:null,id:j.sealId||j.id||null}}catch{return null}}
// Normalise anything a user may paste: tx sig, proof URL (?tx= / ?id= / ?fp=), receipt JSON, fingerprint, seal id.
export function parseVerifyInput(raw){raw=String(raw||'').trim();if(!raw)return{};const r=parseReceiptText(raw);if(r)return r;
 try{if(/^https?:\/\//i.test(raw)){const u=new URL(raw);const tx=(u.searchParams.get('tx')||'').replace(/[^1-9A-HJ-NP-Za-km-z]/g,'');const fp=(u.searchParams.get('fp')||'').toLowerCase();const id=(u.searchParams.get('id')||'').toLowerCase();const m=/\/tx\/([1-9A-HJ-NP-Za-km-z]{64,90})/.exec(u.pathname);return{tx:isTxSig(tx)?tx:m?m[1]:null,fingerprint:isFp(fp)?fp:null,id:/^[0-9a-f]{12}$/.test(id)?id:null}}}catch{}
 const c=raw.replace(/\s+/g,'');if(isTxSig(c))return{tx:c};const l=c.toLowerCase();if(isFp(l))return{fingerprint:l};if(/^[0-9a-f]{12}$/.test(l))return{id:l};return{bad:true}}
const getTx=(rpc,sig)=>rpc('getTransaction',[sig,{encoding:'jsonParsed',maxSupportedTransactionVersion:0,commitment:'finalized'}]).then(x=>x.res);
export async function proofForTx(sig,expect,rpc=liveRpc){const res=await getTx(rpc,sig);if(!res)return null;return proofFromParsedTx(sig,res,expect)}
// File-only discovery, fully on-chain: index key history → finalized tx → memo must carry this fingerprint.
export async function findByFingerprint(fp,{rpc=liveRpc,limit=50,legacy=true}={}){const out=[];const idx=await fpIndexAddress(fp);
 const {res}=await rpc('getSignaturesForAddress',[idx,{limit,commitment:'finalized'}]).catch(()=>({res:[]}));
 for(const s of res||[]){if(s.err)continue;const p=await proofForTx(s.signature,{fingerprint:fp},rpc).catch(()=>null);if(p)out.push(p)}
 if(!out.length&&legacy)out.push(...await legacyScan(p=>p.fingerprint===fp,{rpc}))
 return out.sort((a,b)=>(a.blockTime||0)-(b.blockTime||0))}
// Older seals (before 2026-11-12) were signed by the firm key and carry no index key: scan its recent memo history.
export async function legacyScan(match,{rpc=liveRpc,limit=1000}={}){const {res}=await rpc('getSignaturesForAddress',[SEAL_SIGNER,{limit}]).catch(()=>({res:[]}));for(const s of res||[]){if(s.err)continue;const p=parseMemo(s.memo);if(p&&match(p)){const v=await proofForTx(s.signature,{id:p.id,fingerprint:p.fingerprint},rpc).catch(()=>null);if(v)return[v]}}return[]}
// Unified verify: {tx?, fingerprint?, id?} + optional file fingerprint → result
export async function verifyOnChain({tx,fingerprint,id,fileFp},{rpc=liveRpc}={}){const fp=fileFp||fingerprint||null;
 if(tx){const p=await proofForTx(tx,undefined,rpc).catch(()=>null);if(!p)return{status:'no-seal',tx};if(id&&p.id!==id)return{status:'mismatch',proofs:[p],reason:'id'};
  if(fp)return p.fingerprint===fp?{status:'match',proofs:[p]}:{status:'mismatch',proofs:[p],reason:'fingerprint'};return{status:'found',proofs:[p]}}
 if(fp){const ps=await findByFingerprint(fp,{rpc});const f=id?ps.filter(p=>p.id===id):ps;return f.length?{status:'match',proofs:f}:{status:'no-seal'}}
 if(id){const ps=await legacyScan(p=>p.id===id,{rpc});return ps.length?{status:'found',proofs:ps}:{status:'need-tx'}}
 return{status:'empty'}}
export function feeSol(lamports){return (lamports||BASE_FEE_LAMPORTS)/LAMPORTS}
export {parseMemo,firmFromTx};
