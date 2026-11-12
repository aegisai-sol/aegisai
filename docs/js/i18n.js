// AGIS lightweight i18n — EN + BG. Persist: localStorage.agisLang = 'en'|'bg'
export const LANGS = ['en', 'bg'];
const KEY = 'agisLang';
export function getLang() {
  const v = (localStorage.getItem(KEY) || 'en').toLowerCase();
  return LANGS.includes(v) ? v : 'en';
}
export function setLang(l) {
  const lang = LANGS.includes(l) ? l : 'en';
  localStorage.setItem(KEY, lang);
  document.documentElement.lang = lang === 'bg' ? 'bg' : 'en';
  applyI18n(document);
  window.dispatchEvent(new CustomEvent('agis:lang', { detail: { lang } }));
  return lang;
}
export function t(key, fallback) {
  const lang = getLang();
  const d = DICT[lang] || DICT.en;
  return (d && d[key]) || (DICT.en && DICT.en[key]) || fallback || key;
}

export const DICT = {
  en: {
    'nav.home': 'Home', 'nav.mine': 'Mine', 'nav.seal': 'Seal', 'nav.verify': 'Verify',
    'nav.howto': 'How-to', 'nav.whitepaper': 'Whitepaper', 'nav.token': 'Burn/Stake', 'nav.roadmap': 'Roadmap',
    'lang.en': 'EN', 'lang.bg': 'BG', 'lang.label': 'Language',
    'trust.encrypt': 'Encrypted on your device AES-256-GCM',
    'trust.key': 'We never hold the key',
    'trust.quantum': 'AES-256-GCM — quantum-ready for secrecy',
    'home.cta.mine': 'Start mining', 'home.cta.seal': 'Seal a file',
    'seal.title': 'Seal (RWA add-on)',
    'seal.sub': 'Document seals for AGIS — proof layer, not a separate token. Fingerprint proofs only; not legal title or a notary.',
    'seal.trust': '🔐 Encrypted on your device (AES-256-GCM) · 🗝️ We never hold the key · ⚛️ AES-256-GCM — quantum-ready for secrecy',
    'seal.tab1': '1 · Seal a file', 'seal.tab2': '2 · Verify / Prove', 'seal.tab3': '3 · Open my document',
    'seal.cannot': '🔒 We cannot see your document — only you, with your key.',
    'seal.help': 'Help — why seal, and where things live',
    'seal.choose': '📄 Choose file', 'seal.camera': '📷 Scan with camera', 'seal.webcam': 'Desktop webcam',
    'seal.max': 'any type · max 20 MB',
    'seal.fp': 'Fingerprint (SHA-256):',
    'seal.backup': 'Encrypted backup',
    'seal.backup.help': 'Off by default. Uploads only ciphertext to Aegis servers so you can open the file later without the original. We never get the key. Not blockchain — best-effort. Skip if you only need a fingerprint stamp.',
    'seal.type': 'Document type',
    'seal.type.help': 'Label only — helps you find seals later. Does not change encryption or proof strength.',
    'seal.valid': 'How long is this seal “valid”?',
    'seal.valid.help': 'Written into the Solana Memo as validUntil. After that time Verify shows expired — useful for short offers. The Memo itself stays on-chain forever.',
    'seal.create': 'Create seal',
    'seal.adv': 'Advanced · Protect & recovery (optional — Seal works without these)',
    'seal.wallet': 'Wallet recovery (Phantom)',
    'seal.wallet.help': 'If you lose the key file, unlock the encrypted copy by signing with the same Phantom wallet. Needs wallet connected at seal time. Not required for a normal seal.',
    'seal.remember': 'Remember key on this device',
    'seal.remember.help': 'Stores the seal key in this browser so Open is faster. Off = safer if someone uses your unlocked phone — you keep the key yourself (download/share after seal).',
    'seal.l4': 'L4 package (prep)',
    'seal.l4.help': 'After seal, download an encrypted blob + hash you can pin to IPFS/Arweave yourself. Auto-upload not live yet — we will not fake a pin. Needs Encrypted backup on (ciphertext).',
    'seal.extra': 'Extra lock — passphrase (optional)',
    'seal.extra.help': 'If your phone is unlocked and stolen, a passphrase stops the thief from using a saved key. Your phrase becomes a lock that is hard to guess. Leave empty to skip — Seal stays one tap.',
    'seal.pp1': 'Passphrase (min 8, optional)', 'seal.pp2': 'Confirm passphrase',
    'seal.pp.hint': 'Skipping is fine. Export Seal ID + key after seal so you can recover if this phone dies.',
    'seal.step': 'Step 1 — Seal is free: your browser makes the fingerprint, no wallet needed.',
    'mine.title': 'Mine AGIS',
    'howto.title': 'Seal vs Verify (simple)',
    'roadmap.title': 'Roadmap',
    
    'team.public': 'Team Ops',
    'seal.hero': '<b class="text-cyan">Seal vs Verify — plain English</b><br><b>Where things live:</b> the fingerprint is made free on your phone and stays <b>on this device only</b> until you tap <b>Put on Solana</b>. Then a Solana Memo (Seal ID + fingerprint + time — <b>not the file</b>) is a permanent public proof. Your original file never leaves your phone.<br><b>Seal</b> = pick a file, tap Seal, save Seal ID. <b>Verify</b> = check a stamp. Optional Advanced: passphrase Extra lock, wallet recovery, remember key. Encrypted backup is off by default (⚠). L4 decentralized file store is preparing on the Roadmap — not a Seal option yet.<br><b>Quick rule:</b> “Stamp this file now” → Seal · “Is this stamp still good?” → Verify.',
    'howto.lead': 'Seal is the <b>RWA add-on</b> of AGIS: real-world files sealed as fingerprint proofs — same AGIS token, not a separate coin.',
    'howto.seal.h': 'Seal = create a stamp',
    'howto.seal': 'Use when you want proof a file looked a certain way at a certain time.<ol><li>Open <a href="rwa.html">Seal</a>.</li><li>Pick a file.</li><li>Tap <b>Create seal</b> — that is enough (simple by default).</li><li>Optional: Encrypted backup ⚠, validity window, or Advanced (passphrase Extra lock, wallet recovery).</li><li>Save your <b>Seal ID</b> and download the recovery kit if you used a key.</li></ol><p>After about 20 seconds the status becomes <span class="ok">verified</span>.</p>',
    'howto.verify.h': 'Verify = check a stamp',
    'howto.verify': 'Paste the Seal ID, open the proof link, or upload the <b>same</b> file again. Nobody sees the file contents — only stamp status.',
    'howto.lost.h': 'Lost phone?',
    'howto.lost': 'If you still have the file: Verify re-computes the fingerprint and finds the seal — no key needed. The key (or passphrase / wallet unlock) is only to open an encrypted backup copy. Download the recovery kit after seal.',
    'roadmap.h': 'Roadmap',
    'roadmap.lead': 'What works, what we are building, and what comes later. We update this page as things ship.',
    'mine.blurb': 'You get encrypted data only — never the document. Bigger jobs pay more.',
    'sched.title': 'Mining rewards schedule', 'sched.src': 'live from claim server',
    'sched.loading': 'Loading schedule from the claim server… (first request can take up to a minute while it wakes up)',
    'sched.pending': 'Schedule unavailable — server update pending. No numbers are shown until the claim server publishes them.',
    'sched.unreachable': 'Schedule unavailable — claim server unreachable right now. No numbers are shown while offline.',
    'sched.invalid': 'Schedule unavailable — the server reply did not pass checks, so nothing is shown.',
    'sched.epoch': 'Halving epoch', 'sched.perUnit': 'Reward per unit', 'sched.allowed': 'Released so far',
    'sched.next': 'Next halving', 'sched.daysShort': 'd', 'sched.mined': 'Mine pool mined',
    'sched.minedNA': 'Mined total unavailable — the server could not read Solana supply right now (claims pause until it can).',
    'sched.plain': 'Rewards halve every 2 years. Mining can never pay out more than the 8.5B pool (85% of 10B), and every claim is checked against this schedule and the on-chain supply. Per-unit reward is at 1× difficulty, phone tier.',
    'verify.audit.h': 'Someone sent you a file?',
    'verify.audit': 'Check it was not changed since it was sealed — for auditors, buyers, inspectors. You do not need the sealer’s key. Upload the file and/or paste Seal ID / proof link / Solana tx.',
    'verify.cta': 'Check a file (audit)',
    'verify.match': 'Match — this exact file matches the seal.',
    'verify.mismatch': 'No match — the file differs from what was sealed (or no seal found).',
    'verify.signer.firm': 'Signed by the AGIS firm key',
    'verify.signer.sealer': 'Signed by sealer wallet {addr} — not a firm attestation',
    'verify.record': 'Permanent record = the Solana Memo. A firm-key stamp is labeled as signed by the AGIS firm key; a sealer-paid stamp shows the sealer wallet and is not a firm attestation. Our server index is only an optional cache — verification reads the chain even if the server is down.',
    'verify.chain.firm': 'Read directly from the Solana Memo (signed by the AGIS firm key) — no AegisAI server needed.',
    'verify.chain.sealer': 'Read directly from the Solana Memo (signed by the sealer wallet — not a firm attestation) — no AegisAI server needed.',
    'life.h': 'Real life',
    'life.sub': 'Why people seal with AGIS',
    'life.1.h': 'Invoice before audit',
    'life.1': 'Seal the PDF now. Months later the auditor uploads it → Verify says match. You never sent us the readable invoice.',
    'life.2.h': 'Rental photos',
    'life.2': 'Stamp move-in photos. If something is disputed later, the fingerprint proves what the room looked like.',
    'life.3.h': 'Contract / receipt',
    'life.3': 'Seal the signed PDF or store receipt. Solana holds the stamp; the file stays with you.',


  },
  bg: {
    'nav.home': 'Начало', 'nav.mine': 'Mine', 'nav.seal': 'Печат', 'nav.verify': 'Проверка',
    'nav.howto': 'Как се ползва', 'nav.whitepaper': 'Документ', 'nav.token': 'Burn/Stake', 'nav.roadmap': 'Пътна карта',
    'lang.en': 'EN', 'lang.bg': 'BG', 'lang.label': 'Език',
    'trust.encrypt': 'Криптирано на устройството AES-256-GCM',
    'trust.key': 'Ние никога не държим ключа',
    'trust.quantum': 'AES-256-GCM — готов за секретност в квантов свят',
    'home.cta.mine': 'Започни Mine', 'home.cta.seal': 'Печат на файл',
    'seal.title': 'Печат (RWA добавка)',
    'seal.sub': 'Печати на документи за AGIS — слой за доказателство, не отделен токен. Само отпечатък; не е нотариус и не е правно право на собственост.',
    'seal.trust': '🔐 Криптирано на устройството (AES-256-GCM) · 🗝️ Ние никога не държим ключа · ⚛️ AES-256-GCM — готов за секретност в квантов свят',
    'seal.tab1': '1 · Печат на файл', 'seal.tab2': '2 · Проверка', 'seal.tab3': '3 · Отвори документа',
    'seal.cannot': '🔒 Не можем да видим документа — само ти, с ключа си.',
    'seal.help': 'Помощ — защо печат и къде живеят нещата',
    'seal.choose': '📄 Избери файл', 'seal.camera': '📷 Сканирай с камера', 'seal.webcam': 'Уеб камера',
    'seal.max': 'всякакъв тип · макс. 20 MB',
    'seal.fp': 'Отпечатък (SHA-256):',
    'seal.backup': 'Криптиран резерв',
    'seal.backup.help': 'Изключен по подразбиране. Качва само шифрован текст на сървърите на Aegis, за да отвориш файла по-късно без оригинала. Ние нямаме ключа. Не е блокчейн — по възможност. Пропусни, ако ти трябва само печат на отпечатъка.',
    'seal.type': 'Тип документ',
    'seal.type.help': 'Само етикет — помага да намериш печатите по-късно. Не променя криптирането или силата на доказателството.',
    'seal.valid': 'Колко дълго е „валиден“ печатът?',
    'seal.valid.help': 'Записва се в Solana Memo като validUntil. След това Verify показва изтекъл — удобно за кратки оферти. Самият запис в веригата остава завинаги.',
    'seal.create': 'Създай печат',
    'seal.adv': 'Разширени · Защита и възстановяване (по избор — Печатът работи и без тях)',
    'seal.wallet': 'Възстановяване с портфейл (Phantom)',
    'seal.wallet.help': 'Ако загубиш файла с ключа, отключи криптираното копие с подпис от същия Phantom. Трябва свързан портфейл при печата. Не е нужно за обикновен печат.',
    'seal.remember': 'Запомни ключа на това устройство',
    'seal.remember.help': 'Запазва ключа в браузъра за по-бързо отваряне. Изключено = по-безопасно при отключен телефон — пазиш ключа сам (изтегли/сподели след печат).',
    'seal.l4': 'L4 пакет (подготовка)',
    'seal.l4.help': 'След печат изтегляш криптиран пакет + хеш, който сам можеш да закачиш в IPFS/Arweave. Автоматично качване още не е на живо — няма да симулираме pin. Изисква включен Криптиран резерв.',
    'seal.extra': 'Допълнителна ключалка — парола (по избор)',
    'seal.extra.help': 'Ако телефонът е отключен и откраднат, паролата спира крадеца да ползва запазен ключ. Фразата ти става ключалка, която е трудна за отгатване. Оставяй празно, за да пропуснеш — Печатът остава с едно натискане.',
    'seal.pp1': 'Парола (мин. 8, по избор)', 'seal.pp2': 'Потвърди паролата',
    'seal.pp.hint': 'Да пропуснеш е наред. Изтегли Seal ID + ключ след печат, за да се възстановиш ако телефонът умре.',
    'seal.step': 'Стъпка 1 — Печатът е безплатен: браузърът прави отпечатъка, без портфейл.',
    'mine.title': 'Mine AGIS',
    'howto.title': 'Печат срещу Проверка (просто)',
    'roadmap.title': 'Пътна карта',
    
    'team.public': 'Екип · Ops',
    'seal.hero': '<b class="text-cyan">Печат срещу Проверка — просто</b><br><b>Къде живеят нещата:</b> отпечатъкът се прави безплатно на телефона и стои <b>само на устройството</b>, докато натиснеш <b>Put on Solana</b>. Тогава Solana Memo (Seal ID + отпечатък + час — <b>не файлът</b>) е постоянно публично доказателство. Оригиналният файл не напуска телефона.<br><b>Печат</b> = избери файл, натисни Печат, запази Seal ID. <b>Проверка</b> = провери печата. По избор в Разширени: парола (доп. ключалка), възстановяване с портфейл, запомни ключ. Криптираният резерв е изключен по подразбиране (⚠). L4 децентрализирано хранилище се подготвя в Пътната карта — още не е опция в Печат.<br><b>Бързо правило:</b> „Печат на файла сега“ → Печат · „Добър ли е още?“ → Проверка.',
    'howto.lead': 'Печатът е <b>RWA добавка</b> към AGIS: реални файлове като отпечатък-доказателства — същият токен AGIS, не отделна монета.',
    'howto.seal.h': 'Печат = създай печат',
    'howto.seal': 'Когато искаш доказателство, че файлът е изглеждал точно така в даден момент.<ol><li>Отвори <a href="rwa.html">Печат</a>.</li><li>Избери файл.</li><li>Натисни <b>Създай печат</b> — това е достатъчно (просто по подразбиране).</li><li>По избор: Криптиран резерв ⚠, срок на валидност или Разширени (парола, портфейл).</li><li>Запази <b>Seal ID</b> и изтегли recovery kit ако имаш ключ.</li></ol><p>След около 20 сек статусът става <span class="ok">verified</span>.</p>',
    'howto.verify.h': 'Проверка = провери печат',
    'howto.verify': 'Постави Seal ID, отвори proof линка или качи <b>същия</b> файл отново. Никой не вижда съдържанието — само статуса.',
    'howto.lost.h': 'Загубен телефон?',
    'howto.lost': 'Ако още имаш файла: Проверка преизчислява отпечатъка и намира печата — без ключ. Ключът (или парола / портфейл) е само за отваряне на криптиран резерв. Изтегли recovery kit след печат.',
    'roadmap.h': 'Пътна карта',
    'roadmap.lead': 'Какво работи, какво строим и какво идва по-късно. Обновяваме страницата при всеки ship.',
    'mine.blurb': 'Получаваш само криптирани данни — никога документа. По-големите задачи плащат повече.',
    'sched.title': 'График на наградите за копаене', 'sched.src': 'на живо от claim сървъра',
    'sched.loading': 'Зареждане на графика от claim сървъра… (първата заявка може да отнеме до минута, докато сървърът се събуди)',
    'sched.pending': 'Графикът не е наличен — предстои обновяване на сървъра. Не показваме числа, докато claim сървърът не ги публикува.',
    'sched.unreachable': 'Графикът не е наличен — claim сървърът не отговаря в момента. Без връзка не показваме числа.',
    'sched.invalid': 'Графикът не е наличен — отговорът на сървъра не мина проверките, затова не показваме нищо.',
    'sched.epoch': 'Епоха (халвинг)', 'sched.perUnit': 'Награда за единица', 'sched.allowed': 'Пуснати досега',
    'sched.next': 'Следващ халвинг', 'sched.daysShort': ' дни', 'sched.mined': 'Изкопано от пула',
    'sched.minedNA': 'Общото изкопано не е налично — сървърът не може да прочете Solana supply в момента (claim-овете спират, докато не може).',
    'sched.plain': 'Наградите се намаляват наполовина на всеки 2 години. Копаенето никога не може да изплати повече от пула от 8,5 млрд (85% от 10 млрд), а всеки claim се проверява спрямо този график и supply-а във веригата. Наградата за единица е при трудност 1×, ниво телефон.',
    'verify.audit.h': 'Някой ти е пратил файл?',
    'verify.audit': 'Провери дали не е променян след печата — за одитор, купувач, инспектор. Не ти трябва ключът на печатащия. Качи файла и/или сложи Seal ID / proof линк / Solana tx.',
    'verify.cta': 'Провери файл (одит)',
    'verify.match': 'Съвпадение — точно този файл съвпада с печата.',
    'verify.mismatch': 'Няма съвпадение — файлът се различава от отпечатания (или няма печат).',
    'verify.signer.firm': 'Подписано с фирмения ключ на AGIS',
    'verify.signer.sealer': 'Подписано от портфейла на печатащия {addr} — не е фирмено потвърждение',
    'verify.record': 'Постоянният запис е Solana Memo. Печат с фирмения ключ е означен като такъв; печат, платен от печатащия, показва портфейла му и не е фирмено потвърждение. Индексът на сървъра е само опционален кеш — проверката чете веригата дори ако сървърът е спрял.',
    'verify.chain.firm': 'Прочетено директно от Solana Memo (подписано с фирмения ключ на AGIS) — без нужда от сървър на AegisAI.',
    'verify.chain.sealer': 'Прочетено директно от Solana Memo (подписано от портфейла на печатащия — не е фирмено потвърждение) — без нужда от сървър на AegisAI.',
    'life.h': 'Реален живот',
    'life.sub': 'Защо хората печатат с AGIS',
    'life.1.h': 'Фактура преди одит',
    'life.1': 'Печатни PDF-а сега. Месеци по-късно одиторът го качва → Проверка казва съвпадение. Ние никога не виждаме четимата фактура.',
    'life.2.h': 'Снимки при наем',
    'life.2': 'Печатни снимки при нанасяне. При спор по-късно отпечатъкът доказва как е изглеждала стаята.',
    'life.3.h': 'Договор / бележка',
    'life.3': 'Подпечатай подписания PDF или бележката. Solana пази печата; файлът остава при теб.',


  },
};

// ── Blockchain-only Seal + Verify (2026-11-12). New keys; EN + BG kept in parity by tests/seal-chain.test.mjs ──
Object.assign(DICT.en, {
  'nav.seal2': 'Seal', 'nav.verify2': 'Verify', 'nav.roadmap2': 'Roadmap',
  's2.title': 'Seal a file on Solana',
  's2.sub': 'Prove a file existed — unchanged — at a moment in time. Your file never leaves this device; only its fingerprint goes on the blockchain.',
  's2.tab.seal': '🔒 Seal', 's2.tab.verify': '🔍 Verify',
  's2.step1': 'Choose your file', 's2.drop': 'Tap to choose a file — or drop it here', 's2.drop.sub': 'Any type · stays on your device', 's2.photo': '📷 Take a photo',
  's2.fp.ok': '✓ Fingerprint made on this device. The file was not uploaded.', 's2.fp.label': 'Fingerprint (SHA-256)', 's2.fp.working': 'Making fingerprint…', 's2.toobig': 'File is too big for this browser (max 200 MB).',
  's2.step2': 'Connect your wallet', 's2.connect': 'Connect wallet', 's2.getwallet': 'Get Phantom wallet', 's2.getwallet.sub': 'No wallet found in this browser. Phantom is free. On a phone, this opens the page inside Phantom.',
  's2.connected': 'Connected', 's2.balance': 'Balance', 's2.lowsol': 'Not enough SOL for the network fee. Add a little SOL (0.001 SOL is plenty for many seals).',
  's2.nowallet': 'Without a wallet nothing goes on the blockchain. The fingerprint would stay only on this device.', 's2.localonly.btn': 'Keep on this device only (not on blockchain)',
  's2.step3': 'Sign & seal', 's2.sign': 'Sign & seal on Solana', 's2.fee': 'Network fee', 's2.fee.note': 'paid by you to the Solana network — not to us',
  's2.need1': 'First choose a file (step 1).', 's2.need2': 'Connect a wallet (step 2).',
  's2.opts': 'Options', 's2.valid': 'Valid for', 's2.valid.forever': 'Forever (no expiry)', 's2.valid.help': 'Written into the Solana record. After that time Verify shows “expired”. The record itself stays forever.',
  's2.why.h': 'Why AGIS?', 's2.why': 'Coming: pay this fee with AGIS, prepaid “Seal credits” for AGIS holders, and free sponsored seals. Not live yet — the fee is paid in SOL today.',
  's2.st.approve': 'Approve in your wallet…', 's2.st.send': 'Sending to Solana…', 's2.st.confirm': 'Confirming on Solana…',
  's2.err.reject': 'You cancelled in the wallet. Nothing was sent.', 's2.err.rpc': 'Solana network is busy — try again in a moment.', 's2.err.fail': 'The transaction failed on Solana. Nothing was sealed.', 's2.err.generic': 'Could not seal:',
  's2.done': '✓ Sealed on Solana', 's2.done.sub': 'Your fingerprint and time are now on the blockchain. Keep your original file and this receipt.',
  's2.final.wait': 'Confirmed · becomes final in ~15 s', 's2.final.ok': 'Final on Solana',
  's2.r.id': 'Seal ID', 's2.r.fp': 'Fingerprint', 's2.r.tx': 'Transaction', 's2.r.time': 'Time', 's2.r.signer': 'Signed & paid by', 's2.r.valid': 'Valid until', 's2.r.file': 'File (name stays on your device)',
  's2.r.dl': '⬇ Download receipt', 's2.r.print': '🖨 Print / PDF', 's2.r.link': '🔗 Copy proof link', 's2.r.solscan': 'View on Solscan ↗', 's2.r.copied': 'Copied ✓',
  's2.local.h': 'Saved on this device only — NOT on blockchain', 's2.local.sub': 'Nothing was written to Solana. If this browser is cleared, it is gone. Connect a wallet to put it on Solana.', 's2.local.put': 'Put on Solana now',
  's2.list.h': 'My seals on this device', 's2.list.empty': 'No seals yet.', 's2.list.chain': '✓ On Solana', 's2.list.local': 'Local only — not on blockchain', 's2.list.receipt': 'Receipt', 's2.list.put': 'Put on Solana', 's2.list.note': 'This list is only a shortcut in your browser. The proof itself is on Solana.',
  'v2.h': 'Check a file', 'v2.sub': 'Someone sent you a file, or you sealed it yourself? Drop it here. We recompute the fingerprint in your browser and look for the seal directly on Solana — no AegisAI server.',
  'v2.drop': 'Tap to choose the file to check', 'v2.paste': 'Optional: paste Solana tx, proof link or receipt', 'v2.btn': 'Check on Solana', 'v2.working': 'Reading Solana… older records can take up to ~20 s',
  'v2.match': '✓ Match — this exact file is sealed on Solana', 'v2.match.sub': 'Same bytes as when it was sealed. Unchanged since the time below.',
  'v2.found': 'Seal found on Solana', 'v2.found.sub': 'Now drop the file above to check it matches this seal.',
  'v2.mismatch': '✗ No match — this file is different from the sealed one', 'v2.mismatch.sub': 'Even one changed byte gives a different fingerprint. Do not treat it as the sealed original.',
  'v2.none': 'No seal found on Solana for this file', 'v2.none.sub': 'It may be a different or edited file, never sealed, or sealed very recently (final after ~15 s). If you have the receipt or tx, paste it above.',
  'v2.needtx': 'Paste the Solana tx or proof link (a Seal ID alone can only find older firm seals).', 'v2.bad': 'Paste a Solana tx, proof link, receipt, fingerprint — or choose the file.', 'v2.empty': 'Choose a file or paste a tx first.',
  'v2.sealed': 'Sealed', 'v2.prooflink': 'Proof link', 's2.r.qr': 'QR code · certificate', 'v2.expired': 'EXPIRED', 'v2.chainonly': 'Checked directly on Solana — works even if our website is gone.',
  'h2.h': 'Help — where does my data live?',
  'h2.file': '<b>Your file</b> — only on your device. It is never uploaded, not even for Verify.',
  'h2.chain': '<b>Fingerprint + time</b> — on Solana, public and permanent. A fingerprint cannot be turned back into your file.',
  'h2.receipt': '<b>Receipt</b> — you download it. Anyone can check it on Solana.',
  'h2.server': '<b>Our servers</b> — store nothing about you or your files.',
  'h2.wallet': '<b>Why a wallet?</b> Solana only accepts records signed by a wallet. You sign, and you pay the tiny network fee (about $0.001) — directly to Solana.',
  'h2.proves': '<b>What a seal proves:</b> this exact file existed unchanged at that time. It does not prove who wrote it, and it is not a notary or eIDAS stamp.',
  'h2.legacy': 'Sealed before 12 Nov 2026 with an encrypted server backup? <a class="underline" href="rwa-legacy.html#retrieve">Open the old copy</a> (old server, may be unavailable).',
  'm2.banner': 'Mining rewards are moving on-chain. Today the miner and claim run through our beta test server — not yet a Solana program. Rewards and amounts may change. See the Roadmap.',
  'm2.rwa': 'Paused: seal checks moved fully on-chain. Seals no longer create server jobs.',
  'k2.stake': 'Staking is coming on-chain. A Solana stake program (you unstake yourself, no firm custody) is on the Roadmap. Staking via the firm vault is paused.',
  'k2.stake.btn': 'Stake — coming on-chain',
  'home2.h1': 'Seal any file on Solana.', 'home2.h2': 'Check it anytime.',
  'home2.sub': 'Proof that your file existed — unchanged. The file stays on your device; only its fingerprint goes on the blockchain.',
  'home2.seal': '🔒 Seal a file', 'home2.verify': '🔍 Verify a file', 'home2.mine': '⚡ Mine (beta)', 'home2.agis': '🪙 <b style="color:#f5c451">AGIS for seals (coming):</b> pay the seal fee in AGIS, prepaid Seal credits and sponsored seals for holders — after liquidity. Today the network fee is paid in SOL. <a href="roadmap.html#agis-seal" style="color:#22d3ee">Roadmap →</a>',
  'home2.t1': '📄 File never leaves your device', 'home2.t2': '⛓️ Fingerprint on Solana', 'home2.t3': '👛 You sign · ~$0.001 fee',
  'home2.how': '<b>Seal:</b> choose a file → connect your wallet → sign. The fingerprint and time are written to Solana. <b>Verify:</b> anyone drops the same file and the site checks Solana directly. <b>Mine (beta):</b> your device does small checks; on-chain rewards are coming. <a href="howto.html">Step-by-step →</a>',
  'home2.priv': 'Your file is never uploaded — the fingerprint is made in your browser. Only the fingerprint + time go on Solana, signed and paid by your wallet (~$0.001). Our servers store nothing. A seal is a fingerprint proof, not a legal notary. <a href="rwa.html#verify">Verify a file →</a>',
  'home2.claim': 'Mining rewards run through our beta test server today and are moving to a Solana program. Burn is fully on-chain from your wallet. <a href="roadmap.html">Roadmap →</a>',
});
Object.assign(DICT.bg, {
  'nav.seal2': 'Печат', 'nav.verify2': 'Проверка', 'nav.roadmap2': 'Пътна карта',
  's2.title': 'Подпечатай файл в Solana',
  's2.sub': 'Докажи, че файлът е съществувал — непроменен — в даден момент. Файлът не напуска устройството ти; в блокчейна отива само отпечатъкът му.',
  's2.tab.seal': '🔒 Печат', 's2.tab.verify': '🔍 Проверка',
  's2.step1': 'Избери файл', 's2.drop': 'Натисни, за да избереш файл — или го пусни тук', 's2.drop.sub': 'Всякакъв тип · остава на устройството ти', 's2.photo': '📷 Снимай',
  's2.fp.ok': '✓ Отпечатъкът е направен на устройството. Файлът не е качван.', 's2.fp.label': 'Отпечатък (SHA-256)', 's2.fp.working': 'Правя отпечатък…', 's2.toobig': 'Файлът е твърде голям за този браузър (макс. 200 MB).',
  's2.step2': 'Свържи портфейла', 's2.connect': 'Свържи портфейл', 's2.getwallet': 'Вземи портфейл Phantom', 's2.getwallet.sub': 'В този браузър няма портфейл. Phantom е безплатен. На телефон това отваря страницата в Phantom.',
  's2.connected': 'Свързан', 's2.balance': 'Баланс', 's2.lowsol': 'Нямаш достатъчно SOL за таксата. Добави малко SOL (0,001 SOL стига за много печати).',
  's2.nowallet': 'Без портфейл нищо не отива в блокчейна. Отпечатъкът ще остане само на това устройство.', 's2.localonly.btn': 'Запази само на устройството (не в блокчейна)',
  's2.step3': 'Подпиши и подпечатай', 's2.sign': 'Подпиши и подпечатай в Solana', 's2.fee': 'Такса на мрежата', 's2.fee.note': 'плащаш я ти на мрежата Solana — не на нас',
  's2.need1': 'Първо избери файл (стъпка 1).', 's2.need2': 'Свържи портфейл (стъпка 2).',
  's2.opts': 'Опции', 's2.valid': 'Валиден за', 's2.valid.forever': 'Завинаги (без срок)', 's2.valid.help': 'Записва се в Solana. След този момент Проверката показва „изтекъл“. Самият запис остава завинаги.',
  's2.why.h': 'Защо AGIS?', 's2.why': 'Предстои: плащане на таксата с AGIS, предплатени „кредити за печат“ за притежатели на AGIS и безплатни спонсорирани печати. Още не работи — днес таксата е в SOL.',
  's2.st.approve': 'Потвърди в портфейла…', 's2.st.send': 'Изпращам към Solana…', 's2.st.confirm': 'Потвърждавам в Solana…',
  's2.err.reject': 'Отказа в портфейла. Нищо не е изпратено.', 's2.err.rpc': 'Мрежата Solana е натоварена — опитай пак след малко.', 's2.err.fail': 'Транзакцията се провали в Solana. Нищо не е подпечатано.', 's2.err.generic': 'Печатът не стана:',
  's2.done': '✓ Подпечатано в Solana', 's2.done.sub': 'Отпечатъкът и часът вече са в блокчейна. Пази оригиналния файл и тази разписка.',
  's2.final.wait': 'Потвърдено · окончателно след ~15 сек.', 's2.final.ok': 'Окончателно в Solana',
  's2.r.id': 'ID на печата', 's2.r.fp': 'Отпечатък', 's2.r.tx': 'Транзакция', 's2.r.time': 'Час', 's2.r.signer': 'Подписано и платено от', 's2.r.valid': 'Валиден до', 's2.r.file': 'Файл (името остава на устройството)',
  's2.r.dl': '⬇ Свали разписка', 's2.r.print': '🖨 Печат / PDF', 's2.r.link': '🔗 Копирай линк за доказателство', 's2.r.solscan': 'Виж в Solscan ↗', 's2.r.copied': 'Копирано ✓',
  's2.local.h': 'Запазено само на устройството — НЕ е в блокчейна', 's2.local.sub': 'Нищо не е записано в Solana. Ако браузърът се изчисти, изчезва. Свържи портфейл, за да го сложиш в Solana.', 's2.local.put': 'Сложи в Solana сега',
  's2.list.h': 'Моите печати на това устройство', 's2.list.empty': 'Още няма печати.', 's2.list.chain': '✓ В Solana', 's2.list.local': 'Само локално — не е в блокчейна', 's2.list.receipt': 'Разписка', 's2.list.put': 'Сложи в Solana', 's2.list.note': 'Този списък е само пряк път в браузъра ти. Самото доказателство е в Solana.',
  'v2.h': 'Провери файл', 'v2.sub': 'Някой ти е пратил файл или ти си го подпечатал? Пусни го тук. Изчисляваме отпечатъка в браузъра и търсим печата директно в Solana — без сървър на AegisAI.',
  'v2.drop': 'Натисни, за да избереш файла за проверка', 'v2.paste': 'По избор: постави Solana транзакция, линк или разписка', 'v2.btn': 'Провери в Solana', 'v2.working': 'Чета Solana… по-старите записи може да отнемат до ~20 сек.',
  'v2.match': '✓ Съвпадение — точно този файл е подпечатан в Solana', 'v2.match.sub': 'Същите байтове като при печата. Непроменен от часа по-долу.',
  'v2.found': 'Намерен печат в Solana', 'v2.found.sub': 'Сега пусни файла горе, за да провериш дали съвпада.',
  'v2.mismatch': '✗ Няма съвпадение — този файл се различава от подпечатания', 'v2.mismatch.sub': 'Дори един променен байт дава друг отпечатък. Не го приемай за оригинала.',
  'v2.none': 'Няма печат в Solana за този файл', 'v2.none.sub': 'Може да е друг или редактиран файл, никога неподпечатан или подпечатан току-що (окончателно след ~15 сек.). Ако имаш разписка или транзакция, постави ги горе.',
  'v2.needtx': 'Постави Solana транзакцията или линка (само с ID се намират единствено по-старите фирмени печати).', 'v2.bad': 'Постави Solana транзакция, линк, разписка, отпечатък — или избери файла.', 'v2.empty': 'Първо избери файл или постави транзакция.',
  'v2.sealed': 'Подпечатан', 'v2.prooflink': 'Линк за доказателство', 's2.r.qr': 'QR код · сертификат', 'v2.expired': 'ИЗТЕКЪЛ', 'v2.chainonly': 'Проверено директно в Solana — работи дори ако сайтът ни изчезне.',
  'h2.h': 'Помощ — къде стоят данните ми?',
  'h2.file': '<b>Твоят файл</b> — само на устройството ти. Никога не се качва, дори при Проверка.',
  'h2.chain': '<b>Отпечатък + час</b> — в Solana, публично и завинаги. От отпечатъка не може да се възстанови файлът.',
  'h2.receipt': '<b>Разписка</b> — сваляш я ти. Всеки може да я провери в Solana.',
  'h2.server': '<b>Нашите сървъри</b> — не пазят нищо за теб или файловете ти.',
  'h2.wallet': '<b>Защо портфейл?</b> Solana приема само записи, подписани от портфейл. Ти подписваш и плащаш малката такса (около $0,001) — директно на Solana.',
  'h2.proves': '<b>Какво доказва печатът:</b> точно този файл е съществувал непроменен в този момент. Не доказва кой го е написал и не е нотариален или eIDAS печат.',
  'h2.legacy': 'Подпечатвал си преди 12 ноем. 2026 с криптиран резерв на сървъра? <a class="underline" href="rwa-legacy.html#retrieve">Отвори старото копие</a> (стар сървър, може да не е достъпен).',
  'm2.banner': 'Наградите от копаене се местят в блокчейна. Днес копаенето и тегленето минават през нашия тестов (бета) сървър — още не е програма в Solana. Наградите и сумите може да се променят. Виж Пътната карта.',
  'm2.rwa': 'Спряно: проверката на печати вече е изцяло в блокчейна. Печатите не създават задачи на сървъра.',
  'k2.stake': 'Залагането идва в блокчейна. Програма за залагане в Solana (сам си теглиш, без попечителство от фирмата) е в Пътната карта. Залагането през фирмения трезор е спряно.',
  'k2.stake.btn': 'Залагане — идва в блокчейна',
  'home2.h1': 'Подпечатай всеки файл в Solana.', 'home2.h2': 'Провери го по всяко време.',
  'home2.sub': 'Доказателство, че файлът ти е съществувал — непроменен. Файлът остава на устройството ти; в блокчейна отива само отпечатъкът.',
  'home2.seal': '🔒 Подпечатай файл', 'home2.verify': '🔍 Провери файл', 'home2.mine': '⚡ Копай (бета)', 'home2.agis': '🪙 <b style="color:#f5c451">AGIS за печати (предстои):</b> плащане на таксата с AGIS, предплатени кредити за печат и спонсорирани печати за притежатели — след ликвидност. Днес таксата на мрежата се плаща в SOL. <a href="roadmap.html#agis-seal" style="color:#22d3ee">Пътна карта →</a>',
  'home2.t1': '📄 Файлът не напуска устройството', 'home2.t2': '⛓️ Отпечатък в Solana', 'home2.t3': '👛 Ти подписваш · ~$0,001 такса',
  'home2.how': '<b>Печат:</b> избери файл → свържи портфейл → подпиши. Отпечатъкът и часът се записват в Solana. <b>Проверка:</b> всеки пуска същия файл и сайтът проверява директно в Solana. <b>Копаене (бета):</b> устройството прави малки проверки; наградите в блокчейна предстоят. <a href="howto.html">Стъпка по стъпка →</a>',
  'home2.priv': 'Файлът ти никога не се качва — отпечатъкът се прави в браузъра. В Solana отиват само отпечатъкът и часът, подписани и платени от портфейла ти (~$0,001). Сървърите ни не пазят нищо. Печатът е доказателство с отпечатък, не нотариус. <a href="rwa.html#verify">Провери файл →</a>',
  'home2.claim': 'Наградите от копаене днес минават през тестов (бета) сървър и се местят в програма в Solana. Изгарянето е изцяло в блокчейна от портфейла ти. <a href="roadmap.html">Пътна карта →</a>',
});

// Roadmap v2 (blockchain-only)
Object.assign(DICT.en, {
  "rm2.h.now": "Now — works today, on-chain only",
  "rm2.seal.t": "Seal on Solana",
  "rm2.seal.d": "Wallet-first: the fingerprint is made in your browser, you sign and pay ~$0.001 straight to Solana. The record includes an on-chain fingerprint index. No AegisAI server.",
  "rm2.tag.live": "live",
  "rm2.verify.t": "Verify from Solana",
  "rm2.verify.d": "Drop the file or paste the tx — the browser checks Solana directly and shows who signed (your wallet or the firm key).",
  "rm2.receipt.t": "Receipt: download, print, QR",
  "rm2.receipt.d": "Your receipt (fingerprint, tx, time) is saved by you. Anyone can check it on Solana.",
  "rm2.burn.t": "Burn AGIS",
  "rm2.burn.d": "Real SPL burn from your own wallet on Burn/Stake. Supply goes down on-chain.",
  "rm2.h.beta": "Beta — still uses our test server",
  "rm2.mine.t": "Mining rewards",
  "rm2.mine.d": "Miner grading and claims still run through our beta test server. They move to the Solana program below; until then rewards may change.",
  "rm2.tag.beta_server": "beta · server",
  "rm2.h.next": "Next — building",
  "rm2.program.t": "On-chain Solana program: stake, unstake, mining rewards",
  "rm2.program.d": "Replaces the server and the firm vault: time-locked stake you withdraw yourself, and reward emission enforced by the program. Audit before mainnet.",
  "rm2.tag.building": "building",
  "rm2.arweave.t": "Encrypted file copy on Arweave / IPFS",
  "rm2.arweave.d": "Optional: your file is encrypted in your browser and only you hold the key. The encrypted copy goes to Arweave/IPFS and its hash + ID into the Solana record. We never hold keys or files.",
  "rm2.tag.planned": "planned",
  "rm2.lp.t": "AGIS/SOL liquidity pool",
  "rm2.lp.d": "Needed before any payment in AGIS. No pool exists today.",
  "rm2.tag.after_funding": "after funding",
  "rm2.h.agis": "AGIS for easier sealing — coming",
  "rm2.payagis.t": "Pay the seal fee in AGIS",
  "rm2.payagis.d": "Your wallet swaps a little AGIS to SOL via Jupiter for the network fee in the same transaction; part can be burned.",
  "rm2.tag.after_LP": "after LP",
  "rm2.credits.t": "Seal credits",
  "rm2.credits.d": "Holding or staking AGIS gives prepaid or discounted seals, counted by the on-chain program — not by our server.",
  "rm2.tag.after_program": "after program",
  "rm2.sponsored.t": "Gasless (sponsored) seals for AGIS holders",
  "rm2.sponsored.d": "A fee-payer co-signs and pays the SOL fee; the program charges your AGIS credits. No SOL needed in your wallet.",
  "rm2.h.later": "Later",
  "rm2.mobile.t": "Mobile apps",
  "rm2.mobile.d": "Same Solana record format — apps talk to Solana directly.",
  "rm2.tag.later": "later",
  "rm2.qtsp.t": "QTSP / notary partner",
  "rm2.qtsp.d": "Qualified signatures only through a licensed partner — we will not imitate them.",
  "rm2.note": "Honest notes: seals prove a file fingerprint at a time — not legal title, not a notary or eIDAS stamp. Our servers store nothing for seals. AGIS has no liquidity pool and is not listed on any exchange yet. Everything marked “after LP / after program” is not live.",
});
Object.assign(DICT.bg, {
  "rm2.h.now": "Сега — работи днес, само в блокчейна",
  "rm2.seal.t": "Печат в Solana",
  "rm2.seal.d": "Първо портфейл: отпечатъкът се прави в браузъра, ти подписваш и плащаш ~$0,001 директно на Solana. Записът съдържа и индекс на отпечатъка в блокчейна. Без сървър на AegisAI.",
  "rm2.tag.live": "работи",
  "rm2.verify.t": "Проверка от Solana",
  "rm2.verify.d": "Пусни файла или постави транзакцията — браузърът проверява директно в Solana и показва кой е подписал (твоят портфейл или фирменият ключ).",
  "rm2.receipt.t": "Разписка: сваляне, печат, QR",
  "rm2.receipt.d": "Разписката (отпечатък, транзакция, час) я пазиш ти. Всеки може да я провери в Solana.",
  "rm2.burn.t": "Изгаряне на AGIS",
  "rm2.burn.d": "Истинско SPL изгаряне от твоя портфейл в Burn/Stake. Наличността намалява в блокчейна.",
  "rm2.h.beta": "Бета — още ползва тестовия сървър",
  "rm2.mine.t": "Награди от копаене",
  "rm2.mine.d": "Оценката и тегленето още минават през тестовия (бета) сървър. Местят се в програмата в Solana по-долу; дотогава наградите може да се променят.",
  "rm2.tag.beta_server": "бета · сървър",
  "rm2.h.next": "Следва — в разработка",
  "rm2.program.t": "Програма в Solana: залагане, теглене, награди",
  "rm2.program.d": "Заменя сървъра и фирмения трезор: заключено залагане, което теглиш сам, и емисия на наградите, гарантирана от програмата. Одит преди mainnet.",
  "rm2.tag.building": "в разработка",
  "rm2.arweave.t": "Криптирано копие на файла в Arweave / IPFS",
  "rm2.arweave.d": "По избор: файлът се криптира в браузъра и само ти държиш ключа. Криптираното копие отива в Arweave/IPFS, а хешът и ID-то му — в записа в Solana. Ние никога не държим ключове или файлове.",
  "rm2.tag.planned": "планирано",
  "rm2.lp.t": "Пул за ликвидност AGIS/SOL",
  "rm2.lp.d": "Нужен е преди всяко плащане с AGIS. Днес няма пул.",
  "rm2.tag.after_funding": "след финансиране",
  "rm2.h.agis": "AGIS за по-лесен печат — предстои",
  "rm2.payagis.t": "Плащане на таксата с AGIS",
  "rm2.payagis.d": "Портфейлът разменя малко AGIS за SOL през Jupiter за таксата в същата транзакция; част може да се изгаря.",
  "rm2.tag.after_LP": "след пул",
  "rm2.credits.t": "Кредити за печат",
  "rm2.credits.d": "Притежание или залагане на AGIS дава предплатени или по-евтини печати, отчитани от програмата в Solana — не от наш сървър.",
  "rm2.tag.after_program": "след програмата",
  "rm2.sponsored.t": "Печати без такса (спонсорирани) за притежатели на AGIS",
  "rm2.sponsored.d": "Платец на таксата подписва и плаща SOL таксата; програмата удържа от AGIS кредитите ти. Не ти трябва SOL в портфейла.",
  "rm2.h.later": "По-късно",
  "rm2.mobile.t": "Мобилни приложения",
  "rm2.mobile.d": "Същият формат на записа — приложенията говорят директно със Solana.",
  "rm2.tag.later": "по-късно",
  "rm2.qtsp.t": "QTSP / нотариален партньор",
  "rm2.qtsp.d": "Квалифицирани подписи само чрез лицензиран партньор — няма да ги имитираме.",
  "rm2.note": "Честно: печатите доказват отпечатък на файл в даден момент — не собственост, не нотариален или eIDAS печат. Сървърите ни не пазят нищо за печатите. AGIS още няма пул за ликвидност и не е листнат на борса. Всичко с „след пул / след програмата“ не работи още.",
});

// How-to v2 (blockchain-only) — overrides older howto.seal/howto.lost
Object.assign(DICT.en, {
  "howto.seal": "<p>Use when you want proof a file looked a certain way at a certain time.</p><ol><li>Open <a href=\"rwa.html\">Seal</a> and choose the file (or take a photo). The fingerprint is made in your browser — the file is not uploaded.</li><li>Connect your wallet (Phantom or any Solana wallet).</li><li>Tap <b>Sign &amp; seal on Solana</b>. You pay the tiny network fee (~$0.001) directly to Solana.</li><li>Download or print the <b>receipt</b> (fingerprint, transaction, time). Keep the original file.</li></ol><p>No wallet? Then nothing goes on the blockchain — the fingerprint stays only on your device, clearly marked “Local only”.</p>",
  "howto.lost": "<p>Lost your phone? If you still have the file, <a href=\"rwa.html#verify\">Verify</a> finds the seal on Solana from the file alone — no key, no account, no AegisAI server. The receipt or transaction link works too.</p>",
  "howto2.verify": "<p>Use when you (or an auditor, buyer, friend) want to check a file.</p><ol><li>Open <a href=\"rwa.html#verify\">Verify</a>.</li><li>Drop the <b>same</b> file — and optionally paste the transaction, proof link or receipt.</li><li>See: match or no match, the time it was sealed, who signed it, and the Solana link.</li></ol><p>The file is never uploaded. The check reads Solana directly.</p>",
  "howto2.why": "<ul><li><b>Your file never leaves your device</b> — only its fingerprint goes on Solana.</li><li><b>Our servers store nothing</b> — no files, no copies, no accounts.</li><li><b>No human reviewer, no AI judgement</b> — the check is a fingerprint match.</li><li><b>Anyone can check</b> — from the file, the receipt or the Solana link, even if our website is gone.</li></ul>",
  "howto2.seal2": "<ol><li>Open <a href=\"rwa.html\">Seal</a> → choose a file or take a photo.</li><li>Connect your wallet.</li><li>Tap <b>Sign &amp; seal on Solana</b> (~$0.001 network fee, paid by you to Solana). Download the receipt.</li></ol><p class=\"w\">Coming: pay the fee with AGIS, Seal credits and sponsored seals for AGIS holders — see the <a href=\"roadmap.html#agis-seal\">Roadmap</a>.</p>",
  "howto2.short": "Same file → the seal is found on Solana. No wallet → local only, not on the blockchain. Our servers keep nothing.",
  "howto2.mine": "<ol><li>Install Phantom (or Solflare / Trust).</li><li>Open <a href=\"miner.html\">Miner</a> → Connect → Start.</li><li>Claim (beta) — today this runs through our test server; on-chain rewards are coming.</li></ol><p class=\"w\">Beta: no trading (LP/DEX) yet. Not financial advice.</p>",
});
Object.assign(DICT.bg, {
  "howto.seal": "<p>Ползвай, когато искаш доказателство как е изглеждал файлът в даден момент.</p><ol><li>Отвори <a href=\"rwa.html\">Печат</a> и избери файла (или снимай). Отпечатъкът се прави в браузъра — файлът не се качва.</li><li>Свържи портфейла (Phantom или друг Solana портфейл).</li><li>Натисни <b>Подпиши и подпечатай в Solana</b>. Плащаш малката такса (~$0,001) директно на Solana.</li><li>Свали или разпечатай <b>разписката</b> (отпечатък, транзакция, час). Пази оригиналния файл.</li></ol><p>Без портфейл нищо не отива в блокчейна — отпечатъкът остава само на устройството, ясно отбелязан „Само локално“.</p>",
  "howto.lost": "<p>Изгуби телефона? Ако имаш файла, <a href=\"rwa.html#verify\">Проверка</a> намира печата в Solana само от файла — без ключ, без акаунт, без сървър на AegisAI. Разписката или линкът на транзакцията също вършат работа.</p>",
  "howto2.verify": "<p>Ползвай, когато ти (или одитор, купувач, приятел) искате да проверите файл.</p><ol><li>Отвори <a href=\"rwa.html#verify\">Проверка</a>.</li><li>Пусни <b>същия</b> файл — и по избор постави транзакцията, линка или разписката.</li><li>Виждаш: съвпада или не, кога е подпечатан, кой е подписал и линк към Solana.</li></ol><p>Файлът никога не се качва. Проверката чете директно Solana.</p>",
  "howto2.why": "<ul><li><b>Файлът не напуска устройството</b> — в Solana отива само отпечатъкът.</li><li><b>Сървърите ни не пазят нищо</b> — без файлове, копия и акаунти.</li><li><b>Без човек, без AI преценка</b> — проверката е сравнение на отпечатъци.</li><li><b>Всеки може да провери</b> — от файла, разписката или линка в Solana, дори ако сайтът ни изчезне.</li></ul>",
  "howto2.seal2": "<ol><li>Отвори <a href=\"rwa.html\">Печат</a> → избери файл или снимай.</li><li>Свържи портфейла.</li><li>Натисни <b>Подпиши и подпечатай в Solana</b> (~$0,001 такса, плащаш я ти на Solana). Свали разписката.</li></ol><p class=\"w\">Предстои: плащане на таксата с AGIS, кредити за печат и спонсорирани печати за притежатели на AGIS — виж <a href=\"roadmap.html#agis-seal\">Пътната карта</a>.</p>",
  "howto2.short": "Същият файл → печатът се намира в Solana. Без портфейл → само локално, не в блокчейна. Сървърите ни не пазят нищо.",
  "howto2.mine": "<ol><li>Инсталирай Phantom (или Solflare / Trust).</li><li>Отвори <a href=\"miner.html\">Копаене</a> → Свържи → Старт.</li><li>Теглене (бета) — днес минава през тестовия ни сървър; наградите в блокчейна предстоят.</li></ol><p class=\"w\">Бета: още няма търговия (LP/DEX). Не е финансов съвет.</p>",
});

/** Story beats for Home — parallel EN/BG */
export const STORY = {
  en: [
    { k: '1 · Your moment', h: 'Every file tells a story', p: 'A photo, an invoice, a contract. Today it is easy to fake — or to lose.' },
    { k: '2 · Fingerprint', h: 'Your phone stamps a unique code', p: 'Change one pixel and the code changes. Free, instant, done on your device.' },
    { k: '3 · Stays with you', h: 'Your file never leaves', p: 'Only the fingerprint is used. The file itself stays on your device — we never see it.' },
    { k: '4 · Your wallet', h: 'Connect and sign', p: 'Phantom or any Solana wallet. You sign the record yourself — no account, no password.' },
    { k: '5 · Forever stamp', h: 'On Solana for ~$0.001', p: 'Only the code + time go on-chain — never your file. A proof that outlives any website, including ours.' },
    { k: '6 · Verify anywhere', h: 'Same file? It matches.', p: 'Years later, anyone can check it. A different file says “not the same”. Instantly.' },
    { k: '7 · Mine', h: 'Your phone powers the network', p: 'Open Mine, keep the tab on. Your device does small checks and earns AGIS.' },
    { k: '8 · AGIS (coming)', h: 'Seal credits with AGIS', p: 'Coming after liquidity: pay seals with AGIS and get prepaid or sponsored seals as a holder. Today the fee is in SOL.' },
    { k: '9 · Real life, 2026', h: 'Proof it existed — then', p: 'Rental photos, receipts, signed contracts, creative work. Your word, now with evidence.' },
    { k: '10 · Your move', h: 'Seal or Verify — start now', p: 'No sign-up. Choose a file, connect a wallet, sign. Done.' },
  ],
  bg: [
    { k: '1 · Твоят момент', h: 'Всеки файл разказва история', p: 'Снимка, фактура, договор. Днес лесно се фалшифицира — или се губи.' },
    { k: '2 · Отпечатък', h: 'Телефонът слага уникален код', p: 'Смени един пиксел — кодът се сменя. Безплатно, мигновено, на устройството.' },
    { k: '3 · Остава при теб', h: 'Файлът не напуска устройството', p: 'Използва се само отпечатъкът. Самият файл остава при теб — ние никога не го виждаме.' },
    { k: '4 · Твоят портфейл', h: 'Свържи и подпиши', p: 'Phantom или друг Solana портфейл. Сам подписваш записа — без акаунт, без парола.' },
    { k: '5 · Вечен печат', h: 'В Solana за ~$0,001', p: 'Само кодът + часът отиват във веригата — никога файлът. Доказателство, което надживява всеки сайт, и нашия.' },
    { k: '6 · Проверка навсякъде', h: 'Същият файл? Съвпада.', p: 'Години по-късно всеки може да провери. Друг файл казва „не е същият“. Мигновено.' },
    { k: '7 · Mine', h: 'Телефонът захранва мрежата', p: 'Отвори Mine, дръж таба. Устройството прави малки проверки и печели AGIS.' },
    { k: '8 · AGIS (предстои)', h: 'Кредити за печат с AGIS', p: 'След ликвидност: плащане на печати с AGIS и предплатени или спонсорирани печати за притежатели. Днес таксата е в SOL.' },
    { k: '9 · Реален живот, 2026', h: 'Доказателство, че е съществувало', p: 'Снимки за наем, бележки, договори, творчество. Твоята дума — вече с доказателство.' },
    { k: '10 · Твой ход', h: 'Печат или Проверка — сега', p: 'Без регистрация. Избери файл, свържи портфейл, подпиши. Готово.' },
  ],
};

export function applyI18n(root = document) {
  const lang = getLang();
  document.documentElement.lang = lang === 'bg' ? 'bg' : 'en';
  root.querySelectorAll('[data-i18n]').forEach(el => {
    const k = el.getAttribute('data-i18n');
    const v = t(k);
    if (v && v !== k) el.textContent = v;
  });
  root.querySelectorAll('[data-i18n-html]').forEach(el => {
    const k = el.getAttribute('data-i18n-html');
    const v = t(k);
    if (v && v !== k) el.innerHTML = v;
  });
  root.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const k = el.getAttribute('data-i18n-placeholder');
    const v = t(k);
    if (v && v !== k) el.setAttribute('placeholder', v);
  });
  root.querySelectorAll('[data-i18n-title]').forEach(el => {
    const k = el.getAttribute('data-i18n-title');
    const v = t(k);
    if (v && v !== k) el.setAttribute('title', v);
  });
  // Update lang toggle buttons
  root.querySelectorAll('[data-agis-lang-btn]').forEach(btn => {
    const L = btn.getAttribute('data-agis-lang-btn');
    btn.setAttribute('aria-pressed', L === lang ? 'true' : 'false');
    btn.classList.toggle('agis-lang-on', L === lang);
  });
}

export function mountLangSwitch(slot) {
  if (!slot) return;
  slot.innerHTML = `<span class="agis-lang" role="group" aria-label="${t('lang.label')}" style="display:inline-flex;gap:4px;align-items:center;margin-right:6px"><button type="button" data-agis-lang-btn="en" class="agis-lang-btn" style="font:600 11px/1 system-ui;padding:5px 8px;border-radius:8px;border:1px solid #22d3ee44;background:transparent;color:#94a3b8;cursor:pointer">EN</button><button type="button" data-agis-lang-btn="bg" class="agis-lang-btn" style="font:600 11px/1 system-ui;padding:5px 8px;border-radius:8px;border:1px solid #22d3ee44;background:transparent;color:#94a3b8;cursor:pointer">BG</button></span>
<style>.agis-lang-btn.agis-lang-on{color:#05090f!important;background:#22d3ee!important;border-color:#22d3ee!important}</style>`;
  slot.querySelectorAll('[data-agis-lang-btn]').forEach(btn => {
    btn.addEventListener('click', () => setLang(btn.getAttribute('data-agis-lang-btn')));
  });
  applyI18n(document);
}

/** Call once: finds [data-agis-lang-slot] or inserts before .agis-social in nav */
export function bootI18n() {
  let slot = document.querySelector('[data-agis-lang-slot]');
  if (!slot) {
    const social = document.querySelector('nav .agis-social, .agis-social');
    if (social && social.parentElement) {
      slot = document.createElement('span');
      slot.setAttribute('data-agis-lang-slot', '');
      social.parentElement.insertBefore(slot, social);
    }
  }
  if (slot) mountLangSwitch(slot);
  else applyI18n(document);
}

if (typeof window !== 'undefined') {
  window.agisI18n = { getLang, setLang, t, applyI18n, bootI18n, STORY, DICT };
}
