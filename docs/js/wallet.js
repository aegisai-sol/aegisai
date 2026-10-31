// Phantom connect (window.phantom.solana / window.solana). No keys ever touch this page.
const P = () => window.phantom?.solana || (window.solana?.isPhantom ? window.solana : null);
const short = k => k.slice(0, 4) + '…' + k.slice(-4);
export const wallet = { pubkey: null };
function render() {
  document.querySelectorAll('[data-wallet-btn]').forEach(b => b.textContent = wallet.pubkey ? short(wallet.pubkey) + ' · Disconnect' : (P() ? 'Connect Wallet' : 'Install Phantom'));
  document.querySelectorAll('[data-wallet-net]').forEach(e => e.textContent = wallet.pubkey ? 'Solana · mainnet-beta (UI) — network as set in Phantom' : 'Not connected');
  document.dispatchEvent(new CustomEvent('agis:wallet', { detail: wallet.pubkey }));
}
async function toggle() {
  const p = P();
  if (!p) return window.open('https://phantom.app/', '_blank');
  if (wallet.pubkey) { await p.disconnect(); wallet.pubkey = null; return render(); }
  try { const r = await p.connect(); wallet.pubkey = r.publicKey.toString(); } catch (e) { console.warn('rejected', e); }
  render();
}
window.addEventListener('load', () => {
  const p = P();
  p?.on?.('disconnect', () => { wallet.pubkey = null; render(); });
  p?.on?.('accountChanged', k => { wallet.pubkey = k ? k.toString() : null; render(); });
  p?.connect({ onlyIfTrusted: true }).then(r => { wallet.pubkey = r.publicKey.toString(); render(); }).catch(() => {});
  document.querySelectorAll('[data-wallet-btn]').forEach(b => b.onclick = toggle);
  render();
});
