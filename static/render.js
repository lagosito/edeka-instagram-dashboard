/* EDEKA Social Media & Marketing Intelligence
   Laedt die Kennzahlen aus data/dashboard.json und rendert sie in den Shell-Vorlagen.
   Fehlschlag: die Meldung "Daten werden aktualisiert" bleibt stehen, keine leeren Karten. */
(function () {
  function apply(d) {
    var views = (d && d.views) || {};
    var keys = Object.keys(views);
    document.querySelectorAll('[data-v]').forEach(function (el) {
      var k = el.getAttribute('data-v');
      if (keys.indexOf(k) !== -1) {
        el.innerHTML = views[k];
      } else if (el.hasAttribute('data-optional')) {
        var card = el.closest('.card');
        if (card && card.parentNode) card.parentNode.removeChild(card);
      }
    });
    document.body.classList.remove('loading');
  }

  function fail() {
    var b = document.querySelector('.boot');
    if (b) b.textContent = 'Daten werden aktualisiert · bitte kurz warten.';
    document.body.classList.add('loading');
  }

  fetch('data/dashboard.json', { cache: 'no-store' })
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(apply)
    .catch(fail);
})();
