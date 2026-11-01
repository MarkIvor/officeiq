// Boot: dark mode, language, server status, initial model card
async function checkServer() {
  try {
    const r = await fetch('/api/questions/stats');
    if (r.ok) {
      document.getElementById('status-dot').classList.add('online');
      document.getElementById('status-text').textContent = t('status_online');
    }
  } catch {
    document.getElementById('status-text').textContent = t('status_offline');
  }
}

function toggleLang() {
  setLang(LANG === 'ru' ? 'en' : 'ru');
  document.getElementById('btn-lang').textContent = LANG === 'ru' ? 'EN' : 'RU';
  document.getElementById('btn-lang').title = LANG === 'ru' ? t('lang_title') : t('lang_title');
}

(async () => {
  if (localStorage.getItem('dark') === '1') {
    document.body.classList.add('dark');
    document.getElementById('btn-dark').textContent = '🌙';
  }
  if (!localStorage.getItem('ui_lang')) {
    localStorage.setItem('ui_lang', (navigator.language || 'ru').toLowerCase().startsWith('ru') ? 'ru' : 'en');
  }
  LANG = localStorage.getItem('ui_lang') || 'ru';
  document.getElementById('btn-lang').textContent = LANG === 'ru' ? 'EN' : 'RU';
  applyI18n();
  checkServer();
  addModel();

  document.addEventListener('input', e => {
    const id = e.target?.id;
    if (!id) return;
    const m = id.match(/^m(\d+)-(?:model|url)$/);
    if (m) {
      const idx = m[1];
      suggestModelName(
        document.getElementById(`m${idx}-url`),
        document.getElementById(`m${idx}-model`),
        document.getElementById(`m${idx}-name`)
      );
    }
  });
})();
