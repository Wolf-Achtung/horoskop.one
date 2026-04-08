// reading-type.js — handles selection of reading-type cards + syncs
// the summary label on the collapsible details wrapper, if present.
// Externalized so the strict CSP (`script-src 'self'`) can serve it without
// 'unsafe-inline'.
(function () {
  'use strict';
  function init() {
    const cards = document.querySelectorAll('.rt-card');
    const hidden = document.getElementById('readingType');
    const summary = document.getElementById('rt-summary-value');
    function syncSummary(card) {
      if (!summary) return;
      const title = card.querySelector('strong');
      summary.textContent = title ? title.textContent : '';
    }
    // Initial sync from current selection
    const initial = document.querySelector('.rt-card.rt-selected') || cards[0];
    if (initial) syncSummary(initial);
    cards.forEach(function (card) {
      card.addEventListener('click', function () {
        cards.forEach(function (c) { c.classList.remove('rt-selected'); });
        card.classList.add('rt-selected');
        if (hidden) hidden.value = card.getAttribute('data-rt') || 'classic';
        syncSummary(card);
        // Auto-collapse after selection so the form stays compact
        const details = card.closest('details');
        if (details) setTimeout(function () { details.open = false; }, 180);
      });
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
