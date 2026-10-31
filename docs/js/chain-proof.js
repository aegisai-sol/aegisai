// Chain-first seal proof: reads AEGIS/rwa/v1 Memo straight from Solana. Survives API/index wipes.
// Memo format: AEGIS/rwa/v1|sealId|sha256|status|sealedISO|validUntilISO
import {rpc} from './live.js';
export const SEAL_SIGNER='D96QgCXx93AMfKVLikbD8xbxQ6iB1bgrj9PWSiCVNgEg'; // only memos signed by this key count
const RE=/AEGIS\/rwa\/v1\|([0-9a-f]{12})\|([0-9a-f]{64})\|(\w+)\|([^|"\]]+)\|([^|"\]]*)/;
export function parseMemo(s){const m=RE.exec(s||'');if(!m)return null;const vu=m[5]&&m[5]!=='forever'?m[5]:null;return{id:m[1],fingerprint:m[2],status:m[3],created:m[4],validUntil:vu,expired:!!(vu&&Date.parse(vu)<Date.now())}}
export async function fromTx(tx){const {res}=await rpc('getTransaction',[tx,{encoding:'jsonParsed',maxSupportedTransactionVersion:0,commitment:'confirmed'}]);if(!res||res.meta?.err)return null;
const signers=res.transaction.message.accountKeys.filter(k=>k.signer).map(k=>k.pubkey);if(!signers.includes(SEAL_SIGNER))return null;
const memo=res.transaction.message.instructions.map(i=>typeof i.parsed==='string'?i.parsed:'').join(' ')||(res.meta.logMessages||[]).join(' ');const p=parseMemo(memo);return p&&{...p,receiptTx:tx,blockTime:res.blockTime,_chainSource:true}}
// Discovery without tx: scan recent signer history memos (last ~1000 txs; older seals need ?tx=).
export async function scan(match){const {res}=await rpc('getSignaturesForAddress',[SEAL_SIGNER,{limit:1000}]);for(const s of res||[]){if(s.err)continue;const p=parseMemo(s.memo);if(p&&match(p)){const v=await fromTx(s.signature).catch(()=>null);if(v)return[v]}}return[]}
export const byId=id=>scan(p=>p.id===id);
export const byFp=fp=>scan(p=>p.fingerprint===fp); // memo carries sha256, so fp lookup works from chain too
