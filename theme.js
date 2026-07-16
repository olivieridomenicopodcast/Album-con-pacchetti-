(function () {
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('app_theme', t);
  }
  window.toggleTheme = function () {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    return next;
  };
  window.getTheme = function () {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  };
  // Apply saved theme immediately (before paint) to avoid a flash of the wrong theme.
  applyTheme(localStorage.getItem('app_theme') || 'dark');
})();
