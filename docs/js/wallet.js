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
function render() {
  const n = providers().length;
  document.querySelectorAll('[data-wallet-btn]').forEach(b => b.textContent = wallet.pubkey ? short(wallet.pubkey) + ' · Disconnect' : (n ? 'Connect Wallet' : 'Install a Solana wallet'));
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
