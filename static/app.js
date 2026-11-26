// Topic tabs, relative "updated" time and copy buttons. The page works without this file.
(function () {
  var NE = document.documentElement.lang === 'ne';
  function toNe(n) { return String(n).replace(/[0-9]/g, function (d) { return '०१२३४५६७८९'[d]; }); }
  var tabs = document.querySelectorAll('.tab');
  var stories = document.querySelectorAll('.story');
  var ads = document.querySelectorAll('.stories .ad');
  function show(cat) {
    tabs.forEach(function (t) {
      var on = t.dataset.cat === cat;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    stories.forEach(function (s) { s.hidden = cat !== 'all' && s.dataset.cat !== cat; });
    ads.forEach(function (a) { a.hidden = cat !== 'all'; });
    try { localStorage.setItem('nnc-tab', cat); } catch (e) {}
  }
  tabs.forEach(function (t) { t.addEventListener('click', function () { show(t.dataset.cat); }); });
  try {
    var saved = localStorage.getItem('nnc-tab');
    if (saved && document.querySelector('.tab[data-cat="' + saved + '"]')) show(saved);
  } catch (e) {}

  document.querySelectorAll('time[data-relative]').forEach(function (el) {
    var mins = Math.round((Date.now() - new Date(el.getAttribute('datetime'))) / 60000);
    if (isNaN(mins) || mins < 0) return;
    var hrs = Math.round(mins / 60);
    el.textContent = NE
      ? (mins < 1 ? 'भर्खरै' : mins < 60 ? toNe(mins) + ' मिनेट अगाडि' : toNe(hrs) + ' घण्टा अगाडि')
      : (mins < 1 ? 'just now' : mins < 60 ? mins + ' min ago' : hrs + (hrs === 1 ? ' hour ago' : ' hours ago'));
  });

  document.querySelectorAll('button.copy').forEach(function (b) {
    b.addEventListener('click', function () {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(b.dataset.copy).then(function () {
        var was = b.textContent;
        b.textContent = NE ? 'कपी भयो' : 'Copied'; setTimeout(function () { b.textContent = was; }, 1500);
      });
    });
  });

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
