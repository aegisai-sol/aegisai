import assert from 'assert';
import * as T from '../docs/js/tokenomics.js';
import { RATE0, FREE_WALLETS, difficultyBps as serverDif, ONE_X_BPS } from '../token/scripts/mine-rules.mjs';

assert.equal(T.UNIT_BPS, 1);
assert.equal(T.FREE_WALLETS, FREE_WALLETS);
assert.equal(T.RATE0_BASE, Number(RATE0));
assert.ok(Math.abs(T.BASE_PER_UNIT - Number(RATE0) / 1e9 / 10000) < 1e-15);

assert.equal(T.difficultyBps(1), 10000);
assert.equal(T.difficultyBps(100), 10000);
assert.equal(T.difficultyBps(200), 5000);
assert.equal(Number(serverDif(200)), T.difficultyBps(200));
assert.equal(T.difficulty(200), 0.5);

const u = T.unitReward(1, 1);
assert.ok(Math.abs(u - T.BASE_PER_UNIT) < 1e-12);
assert.ok(T.unitReward(6, 1) === T.unitReward(2, 1)); // claim caps tier at ×2
assert.ok(T.unitReward(1, 200) === T.BASE_PER_UNIT * 0.5);

console.log('ok tokenomics mirrors mine-rules');
