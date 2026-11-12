// Chain-first seal proof: reads AEGIS/rwa/v1 Memo straight from Solana. Survives API/index wipes.
// Memo format: AEGIS/rwa/v1|sealId|sha256|status|sealedISO|validUntilISO
// fromTx accepts a finalized memo signed by anyone; only D96 is firm-attested. scan() still walks D96 history only.
import {rpc} from './live.js';
export const SEAL_SIGNER='D96QgCXx93AMfKVLikbD8xbxQ6iB1bgrj9PWSiCVNgEg';
const RE=/AEGIS\/rwa\/v1\|([0-9a-f]{12})\|([0-9a-f]{64})\|(\w+)\|([^|"\]]+)\|([^|"\]]*)/;
export function parseMemo(s){const m=RE.exec(s||'');if(!m)return null;const vu=m[5]&&m[5]!=='forever'?m[5]:null;return{id:m[1],fingerprint:m[2],status:m[3],created:m[4],validUntil:vu,expired:!!(vu&&Date.parse(vu)<Date.now())}}
export function txSigners(res){return (res?.transaction?.message?.accountKeys||[]).filter(k=>k&&k.signer).map(k=>k.pubkey).filter(Boolean)}
export function classifySigners(signers){const list=Array.isArray(signers)?signers.filter(Boolean):[];const firmAttested=list.includes(SEAL_SIGNER);return{signer:firmAttested?SEAL_SIGNER:(list[0]||null),signers:list,firmAttested,signerKind:firmAttested?'firm':'sealer'}}
export function memoMatches(p,expect){if(!p)return false;if(!expect)return true;const id=String(expect.id||expect.sealId||'').toLowerCase();const fp=String(expect.fingerprint||expect.hash||expect.sha256||'').toLowerCase();if(id&&p.id!==id)return false;if(fp&&p.fingerprint!==fp)return false;return true}
export function isFinalized(res){if(!res||res.meta?.err)return false;if(res.confirmationStatus&&res.confirmationStatus!=='finalized')return false;return true}
function extractMemo(res){const memo=(res.transaction?.message?.instructions||[]).map(i=>typeof i.parsed==='string'?i.parsed:'').join(' ')||(res.meta?.logMessages||[]).join(' ');return parseMemo(memo)}
export function proofFromParsedTx(tx,res,expect){if(!isFinalized(res))return null;const signers=txSigners(res);if(!signers.length)return null;const p=extractMemo(res);if(!p||!memoMatches(p,expect))return null;return{...p,receiptTx:tx,blockTime:res.blockTime,_chainSource:true,...classifySigners(signers)}}
export function signerText(p,t){const tr=(k,fb)=>typeof t==='function'?(t(k,fb)||fb):fb;if(!p||!p.signer)return '';if(p.firmAttested)return tr('verify.signer.firm','Signed by the AGIS firm key')+' ('+p.signer+')';return tr('verify.signer.sealer','Signed by sealer wallet {addr} — not a firm attestation').replace('{addr}',p.signer)}
export async function fromTx(tx,expect){const {res}=await rpc('getTransaction',[tx,{encoding:'jsonParsed',maxSupportedTransactionVersion:0,commitment:'finalized'}]);return proofFromParsedTx(tx,res,expect)}
// Discovery without tx: scan recent firm-key history memos (last ~1000 txs; older / sealer-paid seals need ?tx= or receiptTx).
export async function scan(match){const {res}=await rpc('getSignaturesForAddress',[SEAL_SIGNER,{limit:1000}]);for(const s of res||[]){if(s.err)continue;const p=parseMemo(s.memo);if(p&&match(p)){const v=await fromTx(s.signature).catch(()=>null);if(v)return[v]}}return[]}
export const byId=id=>scan(p=>p.id===id);
export const byFp=fp=>scan(p=>p.fingerprint===fp); // memo carries sha256, so fp lookup works from chain too
