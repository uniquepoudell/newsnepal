// Topic tabs, relative "updated" time and copy buttons. The page works without this file.
(function () {
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
    el.textContent = mins < 1 ? 'just now' : mins < 60 ? mins + ' min ago'
      : Math.round(mins / 60) + (Math.round(mins / 60) === 1 ? ' hour ago' : ' hours ago');
  });

  document.querySelectorAll('button.copy').forEach(function (b) {
    b.addEventListener('click', function () {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(b.dataset.copy).then(function () {
        b.textContent = 'Copied'; setTimeout(function () { b.textContent = 'Copy'; }, 1500);
      });
    });
  });
})();
