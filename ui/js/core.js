// Shared helpers: score colors, pills, nav, notifications, misc
const COLORS = ['#4f6ef7','#e84393','#0ea5e9','#f97316','#8b5cf6','#10b981'];

function sc(s) {
  if (s >= 8) return 'var(--green)';
  if (s >= 6) return 'var(--yellow)';
  if (s >= 4) return 'var(--orange)';
  return 'var(--red)';
}
function scBg(s) {
  if (s >= 8) return 'var(--green-light)';
  if (s >= 6) return 'var(--yellow-light)';
  if (s >= 4) return 'var(--orange-light)';
  return 'var(--red-light)';
}
function pill(s) {
  return `<span class="score-pill" style="background:${scBg(s)};color:${sc(s)}">${(+s).toFixed(1)}</span>`;
}
function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function levelLabel(s) {
  if (s >= 9) return [t('lvl_elite'),'var(--accent)'];
  if (s >= 8) return [t('lvl_strong'),'var(--green)'];
  if (s >= 7) return [t('lvl_good'),'var(--yellow)'];
  if (s >= 6) return [t('lvl_average'),'var(--orange)'];
  return [t('lvl_weak'),'var(--red)'];
}
function levelText(s) {
  if (s >= 9) return t('lvl_elite');
  if (s >= 8) return t('lvl_strong');
  if (s >= 7) return t('lvl_good');
  if (s >= 6) return t('lvl_average');
  return t('lvl_weak');
}

function nav(page, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-'+page).classList.add('active');
  if (el) el.classList.add('active');
  if (page==='results') loadResults();
  if (page==='compare') loadCompareList();
  if (page==='questions') loadQuestions();
  if (page==='leaderboard') { loadResults().then(renderLeaderboard); }
  if (page==='trend') { loadResults().then(populateTrendSelect); }
  if (page==='analytics') { loadResults().then(populateAnalyticsSelect); }
  if (page==='prompts') { loadResults().then(populatePromptsSelect); }
  if (page==='profiles') { loadResults().then(() => { populatePromptsSelect(); renderProfileResults(); }); }
  if (page==='autotune') { loadResults().then(populateAutotuneSelect); }
  if (page==='ab') {
    const jk = document.getElementById('judge-key')?.value;
    const jm = document.getElementById('judge-model')?.value;
    const ju = document.getElementById('judge-url')?.value;
    if (jk && !document.getElementById('ab-judge-key').value) document.getElementById('ab-judge-key').value = jk;
    if (jm && !document.getElementById('ab-judge-model').value) document.getElementById('ab-judge-model').value = jm;
    if (ju) document.getElementById('ab-judge-url').value = ju;
  }
  if (page==='consistency') {
    const jk = document.getElementById('judge-key')?.value;
    const jm = document.getElementById('judge-model')?.value;
    const ju = document.getElementById('judge-url')?.value;
    if (jk && !document.getElementById('cs-judge-key').value) document.getElementById('cs-judge-key').value = jk;
    if (jm && !document.getElementById('cs-judge-model').value) document.getElementById('cs-judge-model').value = jm;
    if (ju) document.getElementById('cs-judge-url').value = ju;
  }
}

function notify(msg, type='ok') {
  const el = document.createElement('div');
  el.className = `notif ${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function toggleDark() {
  const isDark = document.body.classList.toggle('dark');
  document.getElementById('btn-dark').textContent = isDark ? '🌙' : '☀';
  localStorage.setItem('dark', isDark ? '1' : '');
}

function suggestModelName(urlInput, modelInput, nameInput) {
  const url = urlInput?.value || '';
  const model = modelInput?.value || '';
  if (!model || (nameInput?.value && nameInput.value !== nameInput.dataset.auto)) return;
  const providerMap = {
    'openai.com': 'OpenAI', 'anthropic.com': 'Anthropic', 'together.ai': 'Together',
    'groq.com': 'Groq', 'mistral.ai': 'Mistral', 'deepinfra.com': 'DeepInfra',
    'cohere.com': 'Cohere', 'deepseek.com': 'DeepSeek', 'localhost': 'Local',
    '127.0.0.1': 'Local',
  };
  const provider = Object.entries(providerMap).find(([k]) => url.includes(k))?.[1] || '';
  const modelClean = model.split('/').pop().replace(/-/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
  const suggested = provider ? `${provider} · ${modelClean}` : modelClean;
  if (nameInput) { nameInput.value = suggested; nameInput.dataset.auto = suggested; }
}

function launchConfetti() {
  const canvas = document.createElement('canvas');
  canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:99999;';
  document.body.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  const pieces = Array.from({length: 120}, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * -canvas.height,
    r: Math.random() * 8 + 4,
    d: Math.random() * 120 + 20,
    color: ['#4f6ef7','#e84393','#10b981','#f97316','#8b5cf6','#0ea5e9','#fbbf24'][Math.floor(Math.random()*7)],
    tilt: Math.random() * 10 - 10,
    tiltAngle: 0,
    tiltSpeed: Math.random() * 0.1 + 0.05,
  }));
  let frame = 0;
  const MAX = 180;
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    pieces.forEach(p => {
      ctx.beginPath();
      ctx.fillStyle = p.color;
      ctx.globalAlpha = Math.max(0, 1 - frame / MAX);
      ctx.ellipse(p.x, p.y, p.r, p.r * 0.4, p.tiltAngle, 0, Math.PI * 2);
      ctx.fill();
      p.y += Math.cos(p.d) + 3;
      p.x += Math.sin(frame / 20) * 2;
      p.tiltAngle += p.tiltSpeed;
    });
    frame++;
    if (frame < MAX) requestAnimationFrame(draw);
    else canvas.remove();
  }
  draw();
}

function toggleRow(id) {
  const r = document.getElementById(id);
  if (r) r.style.display = r.style.display==='none' ? 'table-row' : 'none';
}

function copyToClipboard(id) {
  const el = document.getElementById(id);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent).then(() => notify(t('msg_copied'), 'ok'));
}
