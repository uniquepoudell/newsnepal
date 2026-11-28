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

  // ---- views, chips, search, paging
  // Home page shows a carousel and swipeable topic rails; picking a topic, searching or "browse all" switches to the full grid.
  var feed = $('.feed[data-view]');
  var chips = $$('.chip');
  var stories = $$('.stories .story');
  var ads = $$('.stories .ad');
  var q = $('#q');
  var noMatch = $('.no-match');
  var moreBtn = $('.show-more');
  var PAGE = 12, limit = PAGE, browsing = false;
  var cat = 'all';
  function apply() {
    var term = q ? q.value.trim().toLowerCase() : '';
    var grid = !feed || browsing || cat !== 'all' || !!term;
    if (feed) feed.dataset.view = grid ? 'grid' : 'rows';
    var shown = 0;
    stories.forEach(function (s) {
      var ok = (cat === 'all' || s.dataset.cat === cat) && (!term || (s.dataset.q || '').indexOf(term) !== -1);
      s.hidden = !ok;
      if (ok) shown++;
      s.classList.toggle('is-paged', ok && !!feed && shown > limit);
    });
    ads.forEach(function (a) { a.hidden = cat !== 'all' || !!term; });
    if (noMatch) noMatch.hidden = shown > 0 || !stories.length;
    if (moreBtn) moreBtn.hidden = !feed || shown <= limit;
  }
  function pick(c, scroll) {
    cat = c; limit = PAGE;
    chips.forEach(function (t) {
      var on = t.dataset.cat === c;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    store('nn-cat', c);
    apply();
    if (scroll && feed) feed.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  chips.forEach(function (t) { t.addEventListener('click', function () { browsing = false; pick(t.dataset.cat); }); });
  $$('[data-pick]').forEach(function (b) {
    b.addEventListener('click', function () { browsing = true; pick(b.dataset.pick, true); });
  });
  $$('.back-rows').forEach(function (b) {
    b.addEventListener('click', function () { browsing = false; if (q) q.value = ''; pick('all', true); });
  });
  if (moreBtn) moreBtn.addEventListener('click', function () { limit += PAGE; apply(); });
  var saved = store('nn-cat');
  if (saved && saved !== 'all' && $('.chip[data-cat="' + saved + '"]')) pick(saved); else apply();
  if (q) {
    q.addEventListener('input', function () { limit = PAGE; apply(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === '/' && document.activeElement !== q && !/input|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); q.focus(); }
    });
  }

  // ---- hero carousel: arrows, dots, autoplay (paused on hover/focus/touch, off for reduced motion)
  $$('.carousel').forEach(function (car) {
    var track = $('.slides', car), slides = $$('.slide', car), dots = $$('.dot', car);
    if (slides.length < 2) { dots.forEach(function (d) { d.hidden = true; }); return; }
    var cur = 0, timer, paused = false;
    var still = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
    function mark(i) {
      cur = i;
      slides.forEach(function (s, n) { s.classList.toggle('is-current', n === i); });
      dots.forEach(function (d, n) { d.classList.toggle('is-on', n === i); d.setAttribute('aria-current', n === i ? 'true' : 'false'); });
    }
    function go(i) { i = (i + slides.length) % slides.length; track.scrollTo({ left: i * track.clientWidth, behavior: still ? 'auto' : 'smooth' }); mark(i); }
    function restart() { clearInterval(timer); if (!still) timer = setInterval(function () { if (!paused && !document.hidden) go(cur + 1); }, 6500); }
    $$('.car-btn', car).forEach(function (b) {
      b.hidden = false;
      b.addEventListener('click', function () { go(cur + (b.classList.contains('car-next') ? 1 : -1)); restart(); });
    });
    dots.forEach(function (d, n) { d.addEventListener('click', function (e) { e.preventDefault(); go(n); restart(); }); });
    var st;
    track.addEventListener('scroll', function () {
      clearTimeout(st);
      st = setTimeout(function () { var i = Math.round(track.scrollLeft / track.clientWidth); if (i !== cur) mark(i); }, 80);
    }, { passive: true });
    track.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') { e.preventDefault(); go(cur + 1); restart(); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); go(cur - 1); restart(); }
    });
    ['mouseenter', 'focusin', 'touchstart'].forEach(function (ev) { car.addEventListener(ev, function () { paused = true; }, { passive: true }); });
    ['mouseleave', 'focusout'].forEach(function (ev) { car.addEventListener(ev, function () { paused = false; }); });
    mark(0); restart();
  });

  // ---- scroll reveal for rails, cards and boxes
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
    }, { rootMargin: '0px 0px -40px 0px' });
    $$('.row, .story, .side .box, .timeline li').forEach(function (el) { el.classList.add('reveal'); io.observe(el); });
  }

  // ---- back to top
  var topBtn = $('.to-top');
  if (topBtn) {
    var onScroll = function () { topBtn.classList.toggle('is-on', window.scrollY > 900); };
    window.addEventListener('scroll', onScroll, { passive: true }); onScroll();
    topBtn.addEventListener('click', function (e) { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }); });
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

  // Rates page converter: amount x NRB buying rate per unit. Shown only when this script runs.
  var calc = document.getElementById('fx-calc');
  if (calc) {
    var amt = document.getElementById('fx-amt'), cur = document.getElementById('fx-cur'), out = document.getElementById('fx-out');
    var conv = function () {
      var rate = +cur.options[cur.selectedIndex].dataset.rate, n = parseFloat(amt.value);
      if (isNaN(n) || !rate) { out.textContent = ''; return; }
      var v = (n * rate).toLocaleString('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 });
      out.textContent = out.dataset.pre + ' ' + (NE ? toNe(v) : v);
    };
    calc.hidden = false;
    calc.addEventListener('submit', function (e) { e.preventDefault(); });
    amt.addEventListener('input', conv); cur.addEventListener('change', conv); conv();
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

/* citizenship test practice: instant marking, values rule */
(function () {
  var quiz = document.getElementById('cz-quiz');
  if (!quiz) return;
  var res = document.getElementById('cz-result'), txt = document.getElementById('cz-text');
  var sets = quiz.querySelectorAll('fieldset.cq');
  function score() {
    var right = 0, done = 0, vwrong = false;
    sets.forEach(function (fs) {
      var pick = fs.querySelector('input:checked');
      fs.classList.remove('right', 'wrong');
      if (!pick) return;
      done++;
      var ok = pick.value === fs.dataset.answer;
      fs.classList.add(ok ? 'right' : 'wrong');
      if (ok) right++; else if (fs.dataset.values === '1') vwrong = true;
    });
    var total = sets.length;
    txt.textContent = right + ' / ' + total;
    if (done === total) {
      var key = vwrong ? 'vfail' : (right / total >= 0.75 ? 'pass' : 'fail');
      txt.textContent = res.dataset[key].replace('{s}', right).replace('{t}', total);
      res.className = 'result ' + (key === 'pass' ? 'ok' : 'bad');
    } else { res.className = 'result'; }
  }
  quiz.addEventListener('change', function (e) {
    var fs = e.target.closest('fieldset.cq');
    if (fs) { var d = fs.querySelector('details'); if (d) d.open = true; }
    score();
  });
  quiz.addEventListener('reset', function () {
    setTimeout(function () { sets.forEach(function (fs) { var d = fs.querySelector('details'); if (d) d.open = false; }); score(); }, 0);
  });
})();
