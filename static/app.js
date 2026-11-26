// News Nepal: topic chips, search, light/dark switch, share buttons, live coin prices, copy buttons.
// The page works without this file; it only adds interactivity.
(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var NE = document.documentElement.lang === 'ne';
  function toNe(n) { return String(n).replace(/[0-9]/g, function (d) { return '०१२३४५६७८९'[d]; }); }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } }

  // ---- toast
  var toastEl = $('#toast'), toastTimer;
  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg; toastEl.classList.add('is-on');
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { toastEl.classList.remove('is-on'); }, 1800);
  }

  // ---- light / dark
  var tbtn = $('#theme-toggle');
  if (tbtn) tbtn.addEventListener('click', function () {
    var root = document.documentElement;
    var dark = root.dataset.theme ? root.dataset.theme === 'dark'
      : window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    store('nn-theme', root.dataset.theme);
  });

  // ---- chips + search
  var chips = $$('.chip');
  var stories = $$('.story');
  var ads = $$('.stories .ad');
  var q = $('#q');
  var noMatch = $('.no-match');
  var cat = 'all';
  function apply() {
    var term = q ? q.value.trim().toLowerCase() : '';
    var shown = 0;
    stories.forEach(function (s) {
      var ok = (cat === 'all' || s.dataset.cat === cat) && (!term || (s.dataset.q || '').indexOf(term) !== -1);
      s.hidden = !ok; if (ok) shown++;
    });
    ads.forEach(function (a) { a.hidden = cat !== 'all' || !!term; });
    if (noMatch) noMatch.hidden = shown > 0 || !stories.length;
  }
  function pick(c) {
    cat = c;
    chips.forEach(function (t) {
      var on = t.dataset.cat === c;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    store('nn-cat', c);
    apply();
  }
  chips.forEach(function (t) { t.addEventListener('click', function () { pick(t.dataset.cat); }); });
  var saved = store('nn-cat');
  if (saved && $('.chip[data-cat="' + saved + '"]')) pick(saved);
  if (q) {
    q.addEventListener('input', apply);
    document.addEventListener('keydown', function (e) {
      if (e.key === '/' && document.activeElement !== q && !/input|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); q.focus(); }
    });
  }

  // ---- relative times
  $$('time[data-relative]').forEach(function (el) {
    var mins = Math.round((Date.now() - new Date(el.getAttribute('datetime'))) / 60000);
    if (isNaN(mins) || mins < 0) return;
    var h = Math.round(mins / 60), d = Math.round(mins / 1440);
    el.title = el.textContent;
    el.textContent = NE
      ? (mins < 1 ? 'भर्खरै' : mins < 60 ? toNe(mins) + ' मिनेट अगाडि' : h < 24 ? toNe(h) + ' घण्टा अगाडि' : toNe(d) + ' दिन अगाडि')
      : (mins < 1 ? 'just now' : mins < 60 ? mins + ' min ago'
        : h < 24 ? h + (h === 1 ? ' hour ago' : ' hours ago') : d + (d === 1 ? ' day ago' : ' days ago'));
  });

  // ---- copy buttons (crypto addresses)
  function copy(text, done) {
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () {});
  }
  $$('button.copy').forEach(function (b) {
    b.addEventListener('click', function () {
      var was = b.textContent;
      copy(b.dataset.copy, function () { b.textContent = NE ? 'कपी भयो' : 'Copied'; toast(NE ? 'ठेगाना कपी भयो' : 'Address copied'); setTimeout(function () { b.textContent = was; }, 1500); });
    });
  });

  // ---- share: native share sheet on phones, copy link elsewhere
  $$('.sh-copy').forEach(function (b) {
    b.addEventListener('click', function () {
      var data = { title: b.dataset.title, url: b.dataset.share };
      if (navigator.share) { navigator.share(data).catch(function () {}); return; }
      copy(data.url, function () { toast(NE ? 'लिंक कपी भयो' : 'Link copied'); });
    });
  });

  // ---- live coin prices from CoinGecko (free, no key). Market news only.
  var ticker = $('.ticker');
  if (ticker) {
    var cells = $$('.tk-coin', ticker);
    var vs = ticker.dataset.vs || 'usd';
    var fmt = function (n) {
      try { return new Intl.NumberFormat('en', { style: 'currency', currency: vs.toUpperCase(), maximumFractionDigits: n < 10 ? 4 : 0 }).format(n); }
      catch (e) { return n.toLocaleString(); }
    };
    var startMoving = function () {
      var track = $('.tk-track', ticker);
      if (!$('.tk', ticker)) { ticker.hidden = true; return; }
      if (!track || track.dataset.doubled) return;
      if (track.scrollWidth > $('.tk-scroll', ticker).clientWidth) {
        track.innerHTML += track.innerHTML; track.dataset.doubled = '1'; ticker.classList.add('is-moving');
      }
    };
    if (cells.length && window.fetch) {
      var ids = cells.map(function (c) { return c.dataset.coin; }).join(',');
      fetch('https://api.coingecko.com/api/v3/simple/price?ids=' + encodeURIComponent(ids) + '&vs_currencies=' + vs + '&include_24hr_change=true')
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .then(function (data) {
          cells.forEach(function (c) {
            var d = data[c.dataset.coin]; if (!d || d[vs] == null) { c.remove(); return; }
            $('.px', c).textContent = fmt(d[vs]);
            var ch = d[vs + '_24h_change'], el = $('.chg', c);
            if (ch != null) { el.textContent = (ch >= 0 ? '▲' : '▼') + Math.abs(ch).toFixed(1) + '%'; el.className = 'chg ' + (ch >= 0 ? 'up' : 'down'); }
          });
          startMoving();
        })
        .catch(function () { cells.forEach(function (c) { c.remove(); }); startMoving(); });
    } else { startMoving(); }
  }

  // "Check your agent": red-flag checklist score. Answers never leave the browser.
  var flags = document.querySelectorAll('#flags .flag');
  var result = document.getElementById('result');
  function score() {
    var total = 0, worst = 0;
    flags.forEach(function (f) { if (f.checked) { var w = +f.dataset.w; total += w; worst = Math.max(worst, w); } });
    var level = worst >= 3 || total >= 4 ? 'high' : total > 0 ? 'medium' : 'low';
    result.className = 'result is-' + level;
    document.getElementById('result-text').textContent = result.dataset[level];
  }
  if (result) { flags.forEach(function (f) { f.addEventListener('change', score); }); score(); }

  // MARN helper: copy the number, then open the official OMARA portal.
  var form = document.getElementById('marn-form');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var input = document.getElementById('marn'), msg = document.getElementById('marn-msg');
      var marn = input.value.replace(/\s+/g, '');
      if (!/^[0-9]{5,10}$/.test(marn)) { msg.textContent = msg.dataset.bad; input.focus(); return; }
      if (navigator.clipboard) navigator.clipboard.writeText(marn).catch(function () {});
      msg.textContent = msg.dataset.ok + ' (' + marn + ')';
      window.open('https://portal.mara.gov.au/', '_blank', 'noopener');
    });
  }
})();
