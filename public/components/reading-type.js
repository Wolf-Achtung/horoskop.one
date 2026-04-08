// reading-type.js — handles selection of reading-type cards in public/index.html
// Externalized so the strict CSP (`script-src 'self'`) can serve it without
// 'unsafe-inline'.
(function () {
  'use strict';
  function init() {
    const cards = document.querySelectorAll('.rt-card');
    const hidden = document.getElementById('readingType');
    cards.forEach(function (card) {
      card.addEventListener('click', function () {
        cards.forEach(function (c) { c.classList.remove('rt-selected'); });
        card.classList.add('rt-selected');
        if (hidden) hidden.value = card.getAttribute('data-rt') || 'classic';
      });
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
