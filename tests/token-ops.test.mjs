import * as T from '../docs/js/token-ops.js';
import assert from 'assert';
assert.equal(T.toBase('1'),10n**9n);assert.equal(T.toBase('0.000000001'),1n);assert.equal(T.fromBase(1500000000n),'1.5');
assert.throws(()=>T.toBase('-1'));assert.throws(()=>T.toBase('0'));assert.throws(()=>T.toBase('1.0000000001'));
assert.deepEqual([...T.burnData(1n)],[15,1,0,0,0,0,0,0,0,9]);assert.equal(T.xferData(1n)[0],12);
const w='6gXafzpPUShAf5Voy7NvQHDw6uGEQ7K9UhF96eG5mhFQ';const p=T.parseStakeMemo(T.stakeMemo(w,T.toBase('2.5'),5));assert.deepEqual(p,{kind:'stake',wallet:w,amount:'2.5',ts:5});
const L=T.reduce([{kind:'stake',wallet:w,base:5n,ts:1},{kind:'unstake',wallet:w,base:2n,ts:2}]);assert.equal(L[w].staked,'5');assert.equal(L[w].requested,'2');
console.log('ok')
