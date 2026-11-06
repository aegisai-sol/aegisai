const C='agis-v36';
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll(['index.html','miner.html','dashboard.html','protocol.html','docs-pov.md','js/pov.js','js/api.js','js/wallet.js','js/miner-worker.js','js/pov-solver.js','js/tokenomics.js','js/live.js','rwa.html','howto.html','proof.html','roadmap.html','token.html','js/token-ops.js','js/rwa-jobs.js','js/seal-anim.js','manifest.webmanifest','assets/agis-logo.png','api/mock-stats.json'])))});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{if(e.request.method==='GET'&&new URL(e.request.url).origin===location.origin)e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)))});
// Keep-alive: page heartbeats; SW replies so clients know it is alive. Periodic sync (Chromium installed PWA) pings open clients.
self.addEventListener('message',e=>{if(e.data&&e.data.type==='heartbeat')e.source&&e.source.postMessage({type:'alive',ts:Date.now()})});
self.addEventListener('periodicsync',e=>{if(e.tag==='agis-mine')e.waitUntil(self.clients.matchAll().then(cs=>cs.forEach(c=>c.postMessage({type:'tick'}))))});
