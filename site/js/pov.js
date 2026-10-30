// Proof-of-Verification micro-tasks — same logic as Python aegis_miner.tiny_check.
export const CLAIMS = [["Water boils at 100 C at sea level.",true],["The Earth is flat.",false],["Python is a programming language.",true],["2 + 2 = 5",false],["Solana uses proof of history.",true],["The sun orbits the Earth.",false],["10 * 3 = 30",true]];
const BAD = ["flat","sun orbits","always","never","100% guaranteed","cure"];
export function tinyCheck(t){const m=t.match(/^\s*(\d+)\s*([+\-*])\s*(\d+)\s*=\s*(\d+)\s*\.?$/);
 if(m){const a=+m[1],b=+m[3],r=+m[4];return[{"+":a+b,"-":a-b,"*":a*b}[m[2]]===r,0.99]}
 const bad=BAD.some(k=>t.toLowerCase().includes(k));return[!bad,bad?0.8:0.65]}
export async function digest(o){const b=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(o)));return[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('').slice(0,16)}
