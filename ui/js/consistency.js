// Consistency test: same 5 questions, 3 runs
let csWs = null;

function startConsistency() {
  const key = document.getElementById('cs-key').value.trim();
  const model = document.getElementById('cs-model').value.trim();
  const judgeKey = document.getElementById('cs-judge-key').value.trim();
  const judgeModel = document.getElementById('cs-judge-model').value.trim();
  if (!key || !model) { notify(t('msg_fill_one'), 'err'); return; }
  if (!judgeKey || !judgeModel) { notify(t('msg_fill_judge'), 'err'); return; }

  document.getElementById('cs-idle-card').style.display = 'none';
  document.getElementById('cs-result-wrap').innerHTML = '';
  document.getElementById('cs-progress-card').style.display = 'block';
  document.getElementById('cs-log').innerHTML = '';
  document.getElementById('cs-phase-text').textContent = t('run_init');
  document.getElementById('cs-spinner').style.display = '';
  document.getElementById('btn-cs-run').disabled = true;

  const payload = {
    model: {
      name: model, base_url: document.getElementById('cs-url').value.trim(),
      api_key: key, model,
      system_prompt: document.getElementById('cs-sysprompt').value.trim() || null,
      concurrency: 3,
    },
    judge_key: judgeKey, judge_model: judgeModel,
    judge_base_url: document.getElementById('cs-judge-url').value.trim(),
    judge_concurrency: 3,
    lang: benchLang(), ui_lang: LANG,
  };

  csWs = new WebSocket(`ws://${location.host}/ws/consistency`);
  csWs.onopen = () => { csWs.send(JSON.stringify(payload)); csLog(t('msg_ws_ok'), 'ok'); };
  csWs.onmessage = e => handleCSMsg(JSON.parse(e.data));
  csWs.onerror = () => { csLog(t('msg_ws_err'), 'err'); doneCS(); };
  csWs.onclose = () => { csWs = null; };
}

function doneCS() {
  document.getElementById('btn-cs-run').disabled = false;
  document.getElementById('cs-spinner').style.display = 'none';
}

function csLog(text, cls='') {
  const log = document.getElementById('cs-log');
  const d = document.createElement('div');
  d.className = 'log-entry ' + cls;
  d.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
  log.appendChild(d); log.scrollTop = log.scrollHeight;
}

function handleCSMsg(msg) {
  if (msg.event === 'consistency_start') csLog(`▶ ${msg.total_runs} × ${msg.questions} ${t('msg_questions_n')}`, 'phase');
  if (msg.event === 'consistency_phase') { document.getElementById('cs-phase-text').textContent = msg.message; csLog(`⟶ ${msg.message}`, 'phase'); }
  if (msg.event === 'model_start') csLog(`▷ [${msg.model_name}] ${t('cs_run_n')} ${msg.model_idx+1}`, 'phase');
  if (msg.event === 'response') {
    if (msg.error) csLog(`✗ [${msg.question_id}] ${msg.error}`, 'err');
    else csLog(`✓ [${msg.question_id}] ${msg.latency_ms}${t('res_ms')}`, 'ok');
  }
  if (msg.event === 'model_done') csLog(`✓ ${t('cs_run_n')} ${msg.model_idx+1}: ${msg.overall_score.toFixed(2)}/10`, 'done');
  if (msg.event === 'consistency_error') { csLog(`💥 ${msg.message}`, 'err'); notify(msg.message,'err'); doneCS(); }
  if (msg.event === 'consistency_done') { renderCSResult(msg); doneCS(); }
}

function renderCSResult(r) {
  document.getElementById('cs-progress-card').style.display = 'none';
  const stabKey = r.stability_key || 'mid';
  const stabColor = stabKey === 'high' ? 'var(--green)' : stabKey === 'mid' ? 'var(--yellow)' : 'var(--red)';
  const stabBg = stabKey === 'high' ? 'var(--green-light)' : stabKey === 'mid' ? 'var(--yellow-light)' : 'var(--red-light)';
  const stabText = stabKey === 'high' ? t('cs_stab_hi') : stabKey === 'mid' ? t('cs_stab_med') : t('cs_stab_low');
  const stabLabel = { high: '↑', mid: '~', low: '!' }[stabKey] || '~';

  const qRows = (r.q_variance||[]).map(q => {
    const varColor = q.variance < 0.5 ? 'var(--green)' : q.variance < 1.5 ? 'var(--yellow)' : 'var(--red)';
    return `<tr>
      <td style="font-size:11px;color:var(--text3);">${q.id}</td>
      <td>${q.scores.map(s => pill(s)).join(' ')}</td>
      <td>${pill(q.avg)}</td>
      <td style="font-weight:700;color:${varColor};">${q.variance.toFixed(2)}</td>
    </tr>`;
  }).join('');

  document.getElementById('cs-result-wrap').innerHTML = `
    <div class="grid-3 mb">
      <div class="card stat-box">
        <div class="val" style="color:${stabColor}">${stabLabel}</div>
        <div class="lbl">${t('cs_stability')}</div>
      </div>
      <div class="card stat-box">
        <div class="val" style="color:${sc(r.avg)}">${r.avg.toFixed(2)}</div>
        <div class="lbl">${t('cs_avg')}</div>
      </div>
      <div class="card stat-box">
        <div class="val" style="color:${r.variance < 0.5 ? 'var(--green)' : 'var(--orange)'}">${r.variance.toFixed(2)}</div>
        <div class="lbl">${t('cs_spread')}</div>
      </div>
    </div>

    <div class="card mb" style="background:${stabBg};border-color:${stabColor};">
      <div style="font-weight:600;color:${stabColor};margin-bottom:4px;">${stabText}</div>
      <div style="font-size:12px;color:var(--text2);">${t('cs_scores_lbl')}: ${r.scores.map(s=>`<b>${s.toFixed(2)}</b>`).join(' · ')}</div>
    </div>

    <div class="table-wrap">
      <div class="card-label" style="padding:12px 14px 0;">${t('cs_q_stab')}</div>
      <table>
        <thead><tr><th>${t('col_id')}</th><th>${t('cs_col_scores')}</th><th>${t('cs_col_avg')}</th><th>${t('cs_col_spread')}</th></tr></thead>
        <tbody>${qRows}</tbody>
      </table>
    </div>`;
}
