// Background tick worker: timers in workers are throttled less than main-thread timers when the tab is hidden.
let t=null;onmessage=e=>{if(e.data==='start'&&!t)t=setInterval(()=>postMessage('tick'),1000);if(e.data==='stop'){clearInterval(t);t=null}};
