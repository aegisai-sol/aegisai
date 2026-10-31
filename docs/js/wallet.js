// Multi-wallet Solana connect: Phantom, Solflare, Trust, MetaMask (Solana), Backpack, any injected provider.
// No keys ever touch this page; only the public key and optional signMessage.
const short = k => k.slice(0, 4) + '…' + k.slice(-4);
function providers() {
  const w = window, out = [];
  const add = (name, p) => { if (p && p.connect && !out.some(x => x.p === p)) out.push({ name, p }); };
  add('Phantom', w.phantom?.solana);
  add('Solflare', w.solflare?.isSolflare || w.solflare ? w.solflare : null);
  add('Trust', w.trustwallet?.solana || (w.solana?.isTrust || w.solana?.isTrustWallet ? w.solana : null));
  add('MetaMask', w.ethereum?.solana || w.metamask?.solana);
  add('Backpack', w.backpack?.solana || w.backpack);
  add(w.solana?.isPhantom ? 'Phantom' : 'Solana wallet', w.solana);
  return out;
}
export const wallet = { pubkey: null, name: null, provider: null };
window.agisWallet = wallet;
const CSS = '.agis-wallet-btn{display:inline-flex;align-items:center;gap:6px;background:transparent;border:1px solid rgba(34,211,238,.25);color:#94a3b8;border-radius:999px;font:500 11.5px/1.2 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:6px 11px;max-width:96px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer;transition:color .15s,border-color .15s,background .15s}.agis-wallet-btn:hover,.agis-wallet-btn:focus-visible{color:#22d3ee;border-color:rgba(34,211,238,.6);outline:none}.agis-wallet-btn[data-state=connected]{color:#e2e8f0;border-color:rgba(34,211,238,.45);background:rgba(34,211,238,.06);font-family:ui-monospace,SFMono-Regular,Menlo,monospace}@media(min-width:768px){.agis-wallet-btn{max-width:140px;font-size:12px}}';
function ensureCss() {
  if (document.getElementById('agis-wallet-css')) return;
  const s = document.createElement('style'); s.id = 'agis-wallet-css'; s.textContent = CSS; document.head.appendChild(s);
}
function render() {
  ensureCss();
  const n = providers().length;
  const state = wallet.pubkey ? 'connected' : (n ? 'idle' : 'install');
  const label = { connected: wallet.pubkey && short(wallet.pubkey), idle: 'Connect', install: 'Get wallet' }[state];
  const aria = { connected: 'Wallet ' + (wallet.pubkey || '') + ' connected. Tap to disconnect', idle: 'Connect Solana wallet', install: 'Get a Solana wallet (opens Phantom)' }[state];
  document.querySelectorAll('[data-wallet-btn]').forEach(b => {
    b.classList.add('agis-wallet-btn');
    b.classList.remove('bg-cyan', 'text-navy', 'ml-auto');
    b.textContent = label; b.title = aria; b.setAttribute('aria-label', aria); b.dataset.state = state;
  });
  document.querySelectorAll('[data-wallet-net]').forEach(e => e.textContent = wallet.pubkey ? wallet.name + ' · Solana mainnet' : 'Phantom · Solflare · Trust · MetaMask');
  document.dispatchEvent(new CustomEvent('agis:wallet', { detail: wallet.pubkey }));
}
function pick(list) {
  if (list.length < 2) return Promise.resolve(list[0]);
  return new Promise(res => {
    const d = document.createElement('div');
    d.style.cssText = 'position:fixed;inset:0;background:#0009;z-index:9999;display:flex;align-items:center;justify-content:center';
    d.innerHTML = '<div style="background:#0a1628;border:1px solid #22d3ee55;border-radius:12px;padding:16px;min-width:240px;color:#fff;font:14px sans-serif"><b>Choose wallet</b></div>';
    list.forEach(x => { const b = document.createElement('button'); b.textContent = x.name; b.style.cssText = 'display:block;width:100%;margin-top:8px;padding:10px;border-radius:8px;background:#22d3ee;color:#0a1628;font-weight:700'; b.onclick = () => { d.remove(); res(x); }; d.firstChild.appendChild(b); });
    d.onclick = e => { if (e.target === d) { d.remove(); res(null); } };
    document.body.appendChild(d);
  });
}
async function connectWith(x, opts) {
  const r = await x.p.connect(opts);
  const pk = (r?.publicKey || x.p.publicKey).toString();
  Object.assign(wallet, { pubkey: pk, name: x.name, provider: x.p });
  x.p.on?.('disconnect', () => { wallet.pubkey = null; render(); });
  x.p.on?.('accountChanged', k => { wallet.pubkey = k ? k.toString() : null; render(); });
}
export async function signText(text) {
  if (!wallet.provider?.signMessage) throw new Error('wallet cannot sign messages');
  const s = await wallet.provider.signMessage(new TextEncoder().encode(text), 'utf8');
  const sig = s.signature || s;
  return btoa(String.fromCharCode(...sig));
}
window.agisSign = signText;
async function toggle() {
  if (wallet.pubkey) { try { await wallet.provider.disconnect(); } catch {} wallet.pubkey = null; return render(); }
  const list = providers();
  if (!list.length) return window.open('https://phantom.app/ul/browse/' + encodeURIComponent(location.href), '_blank');
  const x = await pick(list); if (!x) return;
  try { await connectWith(x); } catch (e) { console.warn('rejected', e); }
  render();
}
window.addEventListener('load', () => {
  const p = providers()[0];
  if (p) connectWith(p, { onlyIfTrusted: true }).then(render).catch(() => {});
  document.querySelectorAll('[data-wallet-btn]').forEach(b => b.onclick = toggle);
  render();
});
