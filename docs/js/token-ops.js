// AGIS on-chain token ops: Burn (pure SPL BurnChecked, no custody) + Stake vault (SPL transfer + Memo, ledger read from chain).
// Everything here is built and signed in the user's wallet; no AegisAI server is called.
export const MINT='GhSiU95vtKwn7FBAW1u5krxYP2PnpFPotb1LJFZkbzhW', DEC=9;
export const STAKE_VAULT='6gXafzpPUShAf5Voy7NvQHDw6uGEQ7K9UhF96eG5mhFQ';           // published owner of the stake vault
export const STAKE_VAULT_ATA='DhFNmnZs9TzhqLrxLWHd2uXZy3stg8dV7tMSicSX3cWJ';       // its AGIS token account
export const LOCK_DAYS=7;
const TOKEN='TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA', ATA_PROG='ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL', MEMO='MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr';
export const RPCS=['https://solana.leorpc.com/?api_key=FREE','https://solana-rpc.publicnode.com','https://api.mainnet-beta.solana.com'];
// amount string -> base units BigInt (exact, no float)
export function toBase(s){s=String(s).trim();if(!/^\d+(\.\d{1,9})?$/.test(s))throw new Error('Enter an amount like 10 or 0.5');const [i,f='']=s.split('.');const v=BigInt(i)*10n**9n+BigInt((f+'000000000').slice(0,9));if(v<=0n)throw new Error('Amount must be > 0');return v}
export const fromBase=v=>{v=BigInt(v);const f=(v%10n**9n).toString().padStart(9,'0').replace(/0+$/,'');return (v/10n**9n).toString()+(f?'.'+f:'')};
export function u64le(v){const b=new Uint8Array(8);let x=BigInt(v);for(let i=0;i<8;i++){b[i]=Number(x&255n);x>>=8n}return b}
export const burnData=v=>Uint8Array.from([15,...u64le(v),DEC]);       // SPL Token BurnChecked
export const xferData=v=>Uint8Array.from([12,...u64le(v),DEC]);       // SPL Token TransferChecked
export const stakeMemo=(w,v,ts)=>`AEGIS/stake/v1|${w}|${fromBase(v)}|${ts}`;
export const unstakeMemo=(w,v,ts)=>`AEGIS/unstake/v1|${w}|${fromBase(v)}|${ts}`;
const RE=/AEGIS\/(stake|unstake)\/v1\|([1-9A-HJ-NP-Za-km-z]{32,44})\|([\d.]+)\|(\d+)/;
export function parseStakeMemo(s){const m=RE.exec(s||'');return m&&{kind:m[1],wallet:m[2],amount:m[3],ts:+m[4]}}
let W;const web3=async()=>W||(W=await import('https://esm.sh/@solana/web3.js@1.95.3'));
async function conn(){const w=await web3();for(const u of RPCS){try{const c=new w.Connection(u,'confirmed');await c.getLatestBlockhash();return c}catch(e){}}throw new Error('Solana RPC busy — try again')}
export function provider(){const p=window.phantom?.solana||window.solana||window.backpack?.solana;if(!p)throw new Error('Install / open Phantom (or another Solana wallet) first.');return p}
async function me(){const p=provider();if(!p.publicKey)await p.connect();return p}
export async function ata(owner){const w=await web3();return w.PublicKey.findProgramAddressSync([new w.PublicKey(owner).toBytes(),new w.PublicKey(TOKEN).toBytes(),new w.PublicKey(MINT).toBytes()],new w.PublicKey(ATA_PROG))[0]}
export async function balance(owner){const c=await conn();const a=await ata(owner);try{const r=await c.getTokenAccountBalance(a);return BigInt(r.value.amount)}catch(e){return 0n}}
export async function supply(){const c=await conn();return BigInt((await c.getTokenSupply(new (await web3()).PublicKey(MINT))).value.amount)}
async function send(ixs){const w=await web3(),p=await me(),c=await conn(),payer=new w.PublicKey(p.publicKey.toString());const {blockhash,lastValidBlockHeight}=await c.getLatestBlockhash('confirmed');const tx=new w.Transaction({feePayer:payer,blockhash,lastValidBlockHeight});ixs(w,payer).forEach(i=>tx.add(i));const {signature}=await p.signAndSendTransaction(tx);const r=await c.confirmTransaction({signature,blockhash,lastValidBlockHeight},'confirmed');if(r.value?.err)throw new Error('Transaction failed on-chain: '+JSON.stringify(r.value.err));return signature}
const memoIx=(w,payer,s)=>new w.TransactionInstruction({programId:new w.PublicKey(MEMO),keys:[{pubkey:payer,isSigner:true,isWritable:false}],data:new TextEncoder().encode(s)});
export async function burn(amount){const v=toBase(amount),p=await me(),owner=p.publicKey.toString();if(await balance(owner)<v)throw new Error('Not enough AGIS in this wallet');const src=await ata(owner);
 return send((w,payer)=>[new w.TransactionInstruction({programId:new w.PublicKey(TOKEN),keys:[{pubkey:src,isSigner:false,isWritable:true},{pubkey:new w.PublicKey(MINT),isSigner:false,isWritable:true},{pubkey:payer,isSigner:true,isWritable:false}],data:burnData(v)}),memoIx(w,payer,`AEGIS/burn/v1|${owner}|${fromBase(v)}|${Date.now()}`)])}
export async function stake(amount){const v=toBase(amount),p=await me(),owner=p.publicKey.toString();if(await balance(owner)<v)throw new Error('Not enough AGIS in this wallet');const src=await ata(owner);
 return send((w,payer)=>{const vault=new w.PublicKey(STAKE_VAULT),vAta=new w.PublicKey(STAKE_VAULT_ATA),mint=new w.PublicKey(MINT),tp=new w.PublicKey(TOKEN);return[
  // create vault ATA if missing (idempotent, opcode 1) — first staker pays ~0.002 SOL rent once
  new w.TransactionInstruction({programId:new w.PublicKey(ATA_PROG),keys:[{pubkey:payer,isSigner:true,isWritable:true},{pubkey:vAta,isSigner:false,isWritable:true},{pubkey:vault,isSigner:false,isWritable:false},{pubkey:mint,isSigner:false,isWritable:false},{pubkey:w.SystemProgram.programId,isSigner:false,isWritable:false},{pubkey:tp,isSigner:false,isWritable:false}],data:Uint8Array.from([1])}),
  new w.TransactionInstruction({programId:tp,keys:[{pubkey:src,isSigner:false,isWritable:true},{pubkey:mint,isSigner:false,isWritable:false},{pubkey:vAta,isSigner:false,isWritable:true},{pubkey:payer,isSigner:true,isWritable:false}],data:xferData(v)}),
  memoIx(w,payer,stakeMemo(owner,v,Date.now()))]})}
export async function requestUnstake(amount){const v=toBase(amount),p=await me(),owner=p.publicKey.toString();const L=await ledger();const s=L[owner];if(!s||BigInt(s.staked)-BigInt(s.requested)<v)throw new Error('Request exceeds your on-chain stake');
 return send((w,payer)=>[memoIx(w,payer,unstakeMemo(owner,v,Date.now())),
  // 0-lamport touch of the vault owner so the request is indexed in the vault's own on-chain history
  w.SystemProgram.transfer({fromPubkey:payer,toPubkey:new w.PublicKey(STAKE_VAULT),lamports:0})])}
// Pure-chain ledger: stake = verified TransferChecked into vault ATA with matching memo signer; unstake = memo by the same wallet.
export function reduce(entries){const L={};for(const e of entries){const r=L[e.wallet]||(L[e.wallet]={staked:0n,requested:0n,returned:0n,since:e.ts,history:[]});if(e.kind==='stake')r.staked+=e.base;else if(e.kind==='unstake')r.requested+=e.base;else if(e.kind==='return')r.returned+=e.base;r.history.push(e)}
 for(const w in L){const r=L[w];r.staked=r.staked.toString();r.requested=r.requested.toString();r.returned=r.returned.toString()}return L}
export async function ledger(){const c=await conn(),w=await web3();const seen=new Set(),sigs=[];for(const a of [STAKE_VAULT_ATA,STAKE_VAULT])for(const s of await c.getSignaturesForAddress(new w.PublicKey(a),{limit:1000}).catch(()=>[]))if(!seen.has(s.signature)){seen.add(s.signature);sigs.push(s)}const out=[];
 for(const s of sigs){if(s.err)continue;const tx=await c.getParsedTransaction(s.signature,{maxSupportedTransactionVersion:0}).catch(()=>null);if(!tx)continue;const ins=tx.transaction.message.instructions;
  const memos=ins.filter(i=>typeof i.parsed==='string').map(i=>i.parsed);const signer=tx.transaction.message.accountKeys.find(k=>k.signer)?.pubkey?.toString();
  for(const i of ins){const pi=i.parsed;if(!pi||pi.type!=='transferChecked'||pi.info.mint!==MINT)continue;const amt=BigInt(pi.info.tokenAmount.amount);
   if(pi.info.destination===STAKE_VAULT_ATA){const m=memos.map(parseStakeMemo).find(x=>x&&x.kind==='stake');if(m&&m.wallet===signer)out.push({kind:'stake',wallet:signer,base:amt,ts:(tx.blockTime||0)*1000,sig:s.signature})}
   else if(pi.info.source===STAKE_VAULT_ATA){const to=memos.map(x=>/AEGIS\/return\/v1\|([1-9A-HJ-NP-Za-km-z]{32,44})/.exec(x)).find(Boolean);if(to)out.push({kind:'return',wallet:to[1],base:amt,ts:(tx.blockTime||0)*1000,sig:s.signature})}}
  for(const m of memos.map(parseStakeMemo))if(m&&m.kind==='unstake'&&m.wallet===signer)out.push({kind:'unstake',wallet:signer,base:toBase(m.amount),ts:(tx.blockTime||0)*1000,sig:s.signature})}
 return reduce(out.sort((a,b)=>a.ts-b.ts))}
export const solscan=s=>'https://solscan.io/tx/'+s;
