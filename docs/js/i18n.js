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
    'life.h': 'Real life',
    'life.sub': 'Why people seal with AGIS',
    'life.1.h': 'Invoice before audit',
    'life.1': 'Seal the PDF now. Months later the auditor uploads it → Verify says match. You never sent us the readable invoice.',
    'life.2.h': 'Rental photos',
    'life.2': 'Stamp move-in photos. If something is disputed later, the fingerprint proves what the room looked like.',
    'life.3.h': 'Contract / receipt',
    'life.3': 'Seal the signed PDF or store receipt. Solana holds the stamp; optional Extra lock protects the key on your phone.',


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
    'life.h': 'Реален живот',
    'life.sub': 'Защо хората печатат с AGIS',
    'life.1.h': 'Фактура преди одит',
    'life.1': 'Печатни PDF-а сега. Месеци по-късно одиторът го качва → Проверка казва съвпадение. Ние никога не виждаме четимата фактура.',
    'life.2.h': 'Снимки при наем',
    'life.2': 'Печатни снимки при нанасяне. При спор по-късно отпечатъкът доказва как е изглеждала стаята.',
    'life.3.h': 'Договор / бележка',
    'life.3': 'Печатни подписания PDF или бележка. Solana държи печата; по избор Extra lock пази ключа на телефона.',


  },
};

/** Story beats for Home — parallel EN/BG */
export const STORY = {
  en: [
    { k: '1 · Your moment', h: 'Every file tells a story', p: 'A photo, an invoice, a contract. Today it is easy to fake — or to lose.' },
    { k: '2 · Fingerprint', h: 'Your phone stamps a unique code', p: 'Change one pixel and the code changes. Free, instant, done on your device.' },
    { k: '3 · Locked', h: 'Encrypted before it leaves', p: 'AES-256-GCM in your browser. The key stays with you — we can never open it.' },
    { k: '4 · Optional backup', h: 'Encrypted backup ⚠', p: 'Off by default. Sealed copy on our servers — we never get the key. Handy, not the blockchain.' },
    { k: '5 · Forever stamp', h: 'Put it on Solana', p: 'Only the code + time go on-chain — never your file. A proof that outlives any website.' },
    { k: '6 · Verify anywhere', h: 'Same file? It matches.', p: 'Years later, anyone can check it. A different file says “not the same”. Instantly.' },
    { k: '7 · Mine', h: 'Your phone powers the network', p: 'Open Mine, keep the tab on. Your device does small checks and earns AGIS.' },
    { k: '8 · Extra lock', h: 'Optional passphrase', p: 'Want more protection? Add a phrase under Advanced so an unlocked stolen phone is not enough. Skip anytime — Seal stays one tap.' },
    { k: '9 · Real life, 2026', h: 'Proof it existed — then', p: 'Rental photos, receipts, signed contracts, creative work. Your word, now with evidence.' },
    { k: '10 · Your move', h: 'Mine or Seal — start now', p: 'No sign-up to seal. Connect a wallet only when you want to.' },
  ],
  bg: [
    { k: '1 · Твоят момент', h: 'Всеки файл разказва история', p: 'Снимка, фактура, договор. Днес лесно се фалшифицира — или се губи.' },
    { k: '2 · Отпечатък', h: 'Телефонът слага уникален код', p: 'Смени един пиксел — кодът се сменя. Безплатно, мигновено, на устройството.' },
    { k: '3 · Заключено', h: 'Криптирано преди да тръгне', p: 'AES-256-GCM в браузъра. Ключът остава при теб — ние никога не можем да го отворим.' },
    { k: '4 · Резерв по избор', h: 'Криптиран резерв ⚠', p: 'Изключен по подразбиране. Копие на нашите сървъри — без ключ при нас. Удобно, не е блокчейн.' },
    { k: '5 · Вечен печат', h: 'Сложи го на Solana', p: 'Само кодът + часът отиват във веригата — никога файлът. Доказателство, което надживява всеки сайт.' },
    { k: '6 · Проверка навсякъде', h: 'Същият файл? Съвпада.', p: 'Години по-късно всеки може да провери. Друг файл казва „не е същият“. Мигновено.' },
    { k: '7 · Mine', h: 'Телефонът захранва мрежата', p: 'Отвори Mine, дръж таба. Устройството прави малки проверки и печели AGIS.' },
    { k: '8 · Доп. ключалка', h: 'Парола по избор', p: 'Искаш повече защита? Добави фраза в Разширени, за да не стигне отключен откраднат телефон. Пропусни — Печатът остава с едно натискане.' },
    { k: '9 · Реален живот, 2026', h: 'Доказателство, че е съществувало', p: 'Снимки за наем, бележки, договори, творчество. Твоята дума — вече с доказателство.' },
    { k: '10 · Твой ход', h: 'Mine или Печат — сега', p: 'Без регистрация за печат. Портфейл само когато поискаш.' },
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
