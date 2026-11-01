// Stress Simulator: multi-turn pressure test client
let stWs = null;

function startStress() {
  const key = document.getElementById('st-key').value.trim();
  const model = document.getElementById('st-model').value.trim();
  const judgeKey = document.getElementById('st-judge-key').value.trim();
  const judgeModel = document.getElementById('st-judge-model').value.trim();
  if (!key || !model) { notify(t('msg_fill_one'), 'err'); return; }
  if (!judgeKey || !judgeModel) { notify(t('msg_fill_judge'), 'err'); return; }

  document.getElementById('st-idle-card').style.display = 'none';
  document.getElementById('st-result-wrap').innerHTML = '';
  document.getElementById('st-progress-card').style.display = 'block';
  document.getElementById('st-log').innerHTML = '';
  document.getElementById('st-phase-text').textContent = t('st_init');
  document.getElementById('st-spinner').style.display = '';
  document.getElementById('btn-st-run').disabled = true;
  document.getElementById('btn-st-stop').style.display = '';

  const payload = {
    model: {
      name: document.getElementById('st-name')?.value.trim() || model,
      base_url: document.getElementById('st-url').value.trim(),
      api_key: key, model,
      system_prompt: document.getElementById('st-sysprompt').value.trim() || null,
    },
    judge_key: judgeKey, judge_model: judgeModel,
    judge_base_url: document.getElementById('st-judge-url').value.trim(),
    judge_concurrency: 3,
    lang: benchLang(), ui_lang: LANG,
  };

  stWs = new WebSocket(`ws://${location.host}/ws/stress`);
  stWs.onopen = () => { stWs.send(JSON.stringify(payload)); stLog(t('msg_ws_ok'), 'ok'); };
  stWs.onmessage = e => handleStressMsg(JSON.parse(e.data));
  stWs.onerror = () => { stLog(t('msg_ws_err'), 'err'); doneStress(); };
  stWs.onclose = () => { stWs = null; };
}

function stopStress() {
  if (stWs?.readyState === WebSocket.OPEN) {
    stWs.send(JSON.stringify({type:'cancel'}));
    document.getElementById('btn-st-stop').disabled = true;
  }
}

function doneStress() {
  document.getElementById('btn-st-run').disabled = false;
  document.getElementById('btn-st-stop').style.display = 'none';
  document.getElementById('btn-st-stop').disabled = false;
  document.getElementById('st-spinner').style.display = 'none';
}

function stLog(text, cls='') {
  const log = document.getElementById('st-log');
  const d = document.createElement('div');
  d.className = 'log-entry ' + cls;
  d.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function handleStressMsg(msg) {
  if (msg.event === 'stress_start') {
    stLog(`▶ ${msg.total} ${t('msg_questions_n')} × 4 ${t('st_turn_lbl')} · ${msg.lang.toUpperCase()}`, 'phase');
    const bar = document.getElementById('st-progress-bar');
    if (bar) bar.style.width = '0%';
    const lbl = document.getElementById('st-progress-lbl');
    if (lbl) lbl.textContent = `0/${msg.total}`;
  }
  if (msg.event === 'stress_turn') {
    stLog(`→ [${msg.question_id}] ${t('st_turn_lbl')} ${msg.turn} ${msg.error ? '✗ ' + msg.error : msg.latency_ms + t('res_ms')}`, msg.error ? 'err' : '');
  }
  if (msg.event === 'stress_progress') {
    const bar = document.getElementById('st-progress-bar');
    const lbl = document.getElementById('st-progress-lbl');
    const pct = Math.round(msg.done / msg.total * 100);
    if (bar) bar.style.width = pct + '%';
    if (lbl) lbl.textContent = `${msg.done}/${msg.total}`;
  }
  if (msg.event === 'stress_scoring') {
    document.getElementById('st-phase-text').textContent = t('run_status_judge');
    stLog(`⟶ ${t('run_status_judge')} ${msg.done}/${msg.total}`, 'phase');
  }
  if (msg.event === 'stress_cancelled') { stLog('⏹ ' + t('msg_stopped'), 'warn'); doneStress(); }
  if (msg.event === 'stress_error') { stLog(`💥 ${msg.message}`, 'err'); notify(msg.message, 'err'); doneStress(); }
  if (msg.event === 'stress_done') { renderStressResult(msg); doneStress(); }
}

function renderStressResult(r) {
  document.getElementById('st-progress-card').style.display = 'none';
  const s = r.summary;
  const brokeTotal = Object.values(s.broke_distribution || {}).reduce((a,b)=>a+b, 0);
  const heldColor = (s.held_pct || 0) >= 70 ? 'var(--green)' : (s.held_pct || 0) >= 40 ? 'var(--yellow)' : 'var(--red)';
  const maxBroke = Math.max(1, ...Object.values(s.broke_distribution || {1:0}));
  const distRows = [2,3,4].map(turn => {
    const n = (s.broke_distribution || {})[turn] || 0;
    return `<div class="cat-bar-row">
      <span class="cat-bar-label">${t('st_turn_lbl')} ${turn} → ${turn+1}</span>
      <div class="cat-bar-wrap"><div class="cat-bar-fill" style="width:${n/maxBroke*100}%;background:var(--red)"></div></div>
      <span class="cat-bar-val" style="color:var(--red)">${n}</span>
    </div>`;
  }).join('');
  const catRows = Object.entries(s.category_scores || {}).sort((a,b)=>b[1]-a[1]).map(([cat,val])=>`
    <div class="cat-bar-row">
      <span class="cat-bar-label">${CAT[cat]||cat}</span>
      <div class="cat-bar-wrap"><div class="cat-bar-fill" style="width:${val*10}%;background:${sc(val)}"></div></div>
      <span class="cat-bar-val" style="color:${sc(val)}">${val.toFixed(1)}</span>
    </div>`).join('');

  document.getElementById('st-result-wrap').innerHTML = `
    <div class="grid-3 mb">
      <div class="card stat-box"><div class="val" style="color:${sc((s.resilience_avg||0))}">${(s.resilience_avg||0).toFixed(2)}</div><div class="lbl">${t('st_resilience')}</div></div>
      <div class="card stat-box"><div class="val" style="color:${heldColor}">${s.held_pct ?? 0}%</div><div class="lbl">${t('st_held')}</div></div>
      <div class="card stat-box"><div class="val" style="color:var(--red)">${brokeTotal}</div><div class="lbl">${t('st_broke')}</div></div>
    </div>
    <div class="grid-2 mb">
      <div class="card">
        <div class="card-label">${t('st_broke_dist')}</div>
        ${brokeTotal ? distRows : `<div style="font-size:13px;color:var(--green);font-weight:600;">${t('st_none_broke')}</div>`}
      </div>
      <div class="card">
        <div class="card-label">${t('st_per_cat')}</div>
        ${catRows}
      </div>
    </div>
    <div class="card mb">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div style="font-size:12px;color:var(--text2);">${t('msg_lang_note')}: <b>${(r.lang||'ru').toUpperCase()}</b></div>
        <button class="btn btn-secondary btn-sm" onclick="viewResult('${r.filename}');nav('results',document.querySelector('[data-page=results]'))">${t('common_details')} →</button>
      </div>
    </div>`;
  loadResults();
}
