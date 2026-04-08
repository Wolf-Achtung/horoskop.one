// reading-type.js — handles selection of reading-type cards in index.html
// Externalized so the strict CSP (`script-src 'self'`) can serve it without
// 'unsafe-inline'.
(function () {
  'use strict';
  function init() {
    const cards = document.querySelectorAll('.rt-card');
    const hidden = document.getElementById('readingType');
    const summaryLabel = document.getElementById('rt-summary-label');
    function labelOf(card) {
      const strong = card.querySelector('strong');
      return strong ? strong.textContent.trim() : '';
    }
    cards.forEach(function (card) {
      card.addEventListener('click', function () {
        cards.forEach(function (c) { c.classList.remove('rt-selected'); });
        card.classList.add('rt-selected');
        if (hidden) hidden.value = card.getAttribute('data-rt') || 'classic';
        if (summaryLabel) summaryLabel.textContent = labelOf(card);
      });
    });
    // Initialise the summary label from whichever card starts selected
    if (summaryLabel) {
      const pre = document.querySelector('.rt-card.rt-selected');
      if (pre) summaryLabel.textContent = labelOf(pre);
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
