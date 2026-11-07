// Paid PoV-R batch solver + light-load tick. Same solve rules as claim-server / pov-solver.js / pov-worker-core.js.
// Messages in:  'start'|'stop'  OR  {type:'solve', i, task}  OR  {type:'solveBatch', tasks}
// Messages out: 'tick'          OR  {type:'answer', i, value, ms}  OR  {type:'batch', answers:[{i,value,ms}], ms}
//               OR {type:'error', i?, error}
// Practice-only ticks live in mine-worker.js (practice:true) — never used for paid /api/claim.
importScripts('./pov-worker-core.js');

let t = null;

async function solveOne(i, task) {
  const a = performance.now();
  const value = await self.__agisSolveTask(task);
  return { type: 'answer', i, value, ms: +(performance.now() - a).toFixed(2) };
}

onmessage = async (e) => {
  const d = e.data;
  if (d === 'start' && !t) {
    t = setInterval(() => postMessage('tick'), 1000);
    return;
  }
  if (d === 'stop') {
    clearInterval(t);
    t = null;
    return;
  }
  if (!d || typeof d !== 'object') return;
  if (d.type === 'solve') {
    try {
      postMessage(await solveOne(d.i, d.task));
    } catch (err) {
      postMessage({ type: 'error', i: d.i, error: String(err && err.message || err) });
    }
    return;
  }
  if (d.type === 'solveBatch') {
    try {
      const tasks = d.tasks || [];
      const answers = [];
      const a0 = performance.now();
      for (let i = 0; i < tasks.length; i++) {
        answers.push(await solveOne(i, tasks[i]));
      }
      postMessage({ type: 'batch', answers, ms: +(performance.now() - a0).toFixed(2) });
    } catch (err) {
      postMessage({ type: 'error', error: String(err && err.message || err) });
    }
  }
};
