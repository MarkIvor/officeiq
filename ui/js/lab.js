// Prompt Lab: A/B testing + Auto-Tune closed loop
let abWs = null;

function startAB() {
  const key = document.getElementById('ab-key').value.trim();
  const model = document.getElementById('ab-model').value.trim();
  const judgeKey = document.getElementById('ab-judge-key').value.trim();
  const judgeModel = document.getElementById('ab-judge-model').value.trim();
  if (!key || !model) { notify(t('msg_fill_one'), 'err'); return; }
  if (!judgeKey || !judgeModel) { notify(t('msg_fill_judge'), 'err'); return; }

  const promptA = document.getElementById('ab-prompt-a').value.trim();
  const promptB = document.getElementById('ab-prompt-b').value.trim();
  if (!promptB) { notify(t('msg_ab_b_empty'), 'err'); return; }

  const mode = document.querySelector('input[name="ab-mode"]:checked')?.value || 'quick';

  document.getElementById('ab-idle-card').style.display = 'none';
  document.getElementById('ab-result-wrap').innerHTML = '';
  document.getElementById('ab-progress-card').style.display = 'block';
  document.getElementById('ab-log').innerHTML = '';
  document.getElementById('ab-phase-text').textContent = t('run_init');
  document.getElementById('ab-spinner').style.display = '';
  document.getElementById('btn-ab-run').disabled = true;
  document.getElementById('btn-ab-stop').style.display = '';

  const payload = {
    model: {
      name: 'AB', base_url: document.getElementById('ab-url').value.trim(),
      api_key: key, model, concurrency: 5,
    },
    prompt_a: promptA, prompt_b: promptB,
    judge_key: judgeKey, judge_model: judgeModel,
    judge_base_url: document.getElementById('ab-judge-url').value.trim(),
    judge_concurrency: 3, mode,
    lang: benchLang(), ui_lang: LANG,
  };

  abWs = new WebSocket(`ws://${location.host}/ws/ab`);
  abWs.onopen = () => { abWs.send(JSON.stringify(payload)); abLog(t('msg_ws_ok'), 'ok'); };
  abWs.onmessage = e => handleABMsg(JSON.parse(e.data));
  abWs.onerror = () => { abLog(t('msg_ws_err'), 'err'); doneAB(); };
  abWs.onclose = () => { abWs = null; };
}

function stopAB() {
  if (abWs?.readyState === WebSocket.OPEN) {
    abWs.send(JSON.stringify({type:'cancel'}));
    document.getElementById('btn-ab-stop').disabled = true;
  }
}

function doneAB() {
  document.getElementById('btn-ab-run').disabled = false;
  document.getElementById('btn-ab-stop').style.display = 'none';
  document.getElementById('btn-ab-stop').disabled = false;
  document.getElementById('ab-spinner').style.display = 'none';
}

function abLog(text, cls='') {
  const log = document.getElementById('ab-log');
  const d = document.createElement('div');
  d.className = 'log-entry ' + cls;
  d.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function handleABMsg(msg) {
  if (msg.event === 'ab_start') abLog(`▶ ${msg.mode} · ${msg.total} ${t('msg_questions_n')} · ${msg.lang?.toUpperCase() || ''}`, 'phase');
  if (msg.event === 'ab_phase') {
    document.getElementById('ab-phase-text').textContent = msg.message;
    abLog(`⟶ ${msg.message}`, 'phase');
  }
  if (msg.event === 'model_start') abLog(`▷ [${msg.model_name}]`, 'phase');
  if (msg.event === 'response') {
    if (msg.error) abLog(`✗ [${msg.question_id}] ${msg.error}`, 'err');
    else abLog(`✓ [${msg.question_id}] ${msg.latency_ms}${t('res_ms')}`, 'ok');
  }
  if (msg.event === 'model_done') abLog(`✓ [${msg.model_name}] ${msg.overall_score.toFixed(2)}/10`, 'done');
  if (msg.event === 'ab_cancelled') { abLog('⏹ ' + t('msg_stopped'), 'warn'); doneAB(); }
  if (msg.event === 'ab_error') { abLog(`💥 ${msg.message}`, 'err'); notify(msg.message,'err'); doneAB(); }
  if (msg.event === 'ab_done') { renderABResult(msg); doneAB(); }
}

function renderABResult(r) {
  document.getElementById('ab-progress-card').style.display = 'none';
  const deltaSign = r.delta > 0 ? '+' : '';
  const deltaColor = r.delta > 0.2 ? 'var(--green)' : r.delta < -0.2 ? 'var(--red)' : 'var(--text3)';
  const winnerBg = r.winner === 'B' ? 'var(--green-light)' : r.winner === 'A' ? 'var(--orange-light)' : 'var(--bg3)';
  const winnerColor = r.winner === 'B' ? 'var(--green)' : r.winner === 'A' ? 'var(--orange)' : 'var(--text3)';

  const catRows = Object.entries(r.cat_delta).sort((a,b)=>Math.abs(b[1])-Math.abs(a[1])).map(([cat, d]) => {
    const cls = d > 0.1 ? 'ab-delta-pos' : d < -0.1 ? 'ab-delta-neg' : 'ab-delta-neu';
    return `<div class="cat-bar-row">
      <span class="cat-bar-label">${CAT[cat]||cat}</span>
      <div style="flex:1;display:flex;gap:8px;align-items:center;">
        <span class="${cls}">${d > 0 ? '+' : ''}${d.toFixed(2)}</span>
        <span style="color:var(--text3);font-size:11px;">→</span>
      </div>
    </div>`;
  }).join('');

  const itemRows = (r.item_deltas||[]).slice(0,10).map(it => {
    const cls = it.delta > 0.3 ? 'ab-delta-pos' : it.delta < -0.3 ? 'ab-delta-neg' : 'ab-delta-neu';
    return `<tr>
      <td style="font-size:11px;color:var(--text3);">${it.id}</td>
      <td><span class="badge badge-${it.difficulty}">${it.difficulty}</span></td>
      <td><span class="badge badge-accent">${CAT[it.category]||it.category}</span></td>
      <td style="max-width:200px;font-size:11px;color:var(--text2);">${esc(it.prompt)}…</td>
      <td>${pill(it.score_a)}</td>
      <td>${pill(it.score_b)}</td>
      <td class="${cls}">${it.delta > 0 ? '+' : ''}${it.delta.toFixed(2)}</td>
    </tr>`;
  }).join('');

  document.getElementById('ab-result-wrap').innerHTML = `
    <div class="card mb" style="background:${winnerBg};border-color:${winnerColor};text-align:center;padding:24px;">
      <div style="font-size:12px;font-weight:600;color:${winnerColor};text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;">
        ${r.winner === 'B' ? t('ab_win_b') : r.winner === 'A' ? t('ab_win_a') : t('ab_tie')}
      </div>
      <div style="display:flex;justify-content:center;gap:32px;align-items:center;">
        <div style="text-align:center;"><div style="font-size:2rem;font-weight:800;color:${sc(r.score_a)}">${r.score_a.toFixed(2)}</div><div style="font-size:11px;color:var(--text3);">${t('ab_prompt_a')}</div></div>
        <div style="font-size:1.6rem;font-weight:800;color:${deltaColor}">${deltaSign}${r.delta.toFixed(2)}</div>
        <div style="text-align:center;"><div style="font-size:2rem;font-weight:800;color:${sc(r.score_b)}">${r.score_b.toFixed(2)}</div><div style="font-size:11px;color:var(--text3);">${t('ab_prompt_b')}</div></div>
      </div>
    </div>
    <div class="card mb">
      <div class="card-label">${t('ab_cat_delta')}</div>
      ${catRows}
    </div>
    <div class="table-wrap">
      <div class="card-label" style="padding:12px 14px 0;">${t('ab_top')}</div>
      <table>
        <thead><tr><th>${t('col_id')}</th><th>${t('col_diff')}</th><th>${t('col_cat')}</th><th>${t('col_request')}</th><th>${t('ab_col_a')}</th><th>${t('ab_col_b')}</th><th>${t('ab_col_delta')}</th></tr></thead>
        <tbody>${itemRows}</tbody>
      </table>
    </div>`;
}
// __LAB_PART2__
// ─── AUTO-TUNE ──────────────────────────────────────────────
let atWs = null;

function populateAutotuneSelect() {
  const sel = document.getElementById('at-use-run');
  if (!sel) return;
  sel.innerHTML = `<option value="">${t('at_use_run_ph')}</option>` +
    allResults.map(r => `<option value="${r.filename}">${esc(r.model_name)} · ${r.run_at.slice(0,16).replace('T',' ')} · ${r.overall_score.toFixed(1)}</option>`).join('');
}

function startAutoTune() {
  const key = document.getElementById('at-key').value.trim();
  const model = document.getElementById('at-model').value.trim();
  const judgeKey = document.getElementById('at-judge-key').value.trim();
  const judgeModel = document.getElementById('at-judge-model').value.trim();
  if (!key || !model) { notify(t('msg_fill_one'), 'err'); return; }
  if (!judgeKey || !judgeModel) { notify(t('msg_fill_judge'), 'err'); return; }
  const basePrompt = document.getElementById('at-base-prompt').value.trim();
  const useRun = document.getElementById('at-use-run')?.value || null;
  if (!basePrompt && !useRun) { notify(t('msg_ab_b_empty').replace('B', 'A'), 'err'); return; }

  const iterations = parseInt(document.getElementById('at-iterations')?.value) || 1;
  const mode = document.querySelector('input[name="at-mode"]:checked')?.value || 'quick';

  document.getElementById('at-idle-card').style.display = 'none';
  document.getElementById('at-result-wrap').innerHTML = '';
  document.getElementById('at-progress-card').style.display = 'block';
  document.getElementById('at-log').innerHTML = '';
  document.getElementById('at-phase-text').textContent = t('run_init');
  document.getElementById('at-spinner').style.display = '';
  document.getElementById('btn-at-run').disabled = true;
  document.getElementById('btn-at-stop').style.display = '';

  const payload = {
    model: {
      name: document.getElementById('at-name')?.value.trim() || model,
      base_url: document.getElementById('at-url').value.trim(),
      api_key: key, model,
    },
    prompt_a: basePrompt,
    use_run: useRun,
    iterations,
    judge_key: judgeKey, judge_model: judgeModel,
    judge_base_url: document.getElementById('at-judge-url').value.trim(),
    judge_concurrency: 3,
    mode, lang: benchLang(), ui_lang: LANG,
  };

  atWs = new WebSocket(`ws://${location.host}/ws/autotune`);
  atWs.onopen = () => { atWs.send(JSON.stringify(payload)); atLog(t('msg_ws_ok'), 'ok'); };
  atWs.onmessage = e => handleATMsg(JSON.parse(e.data));
  atWs.onerror = () => { atLog(t('msg_ws_err'), 'err'); doneAT(); };
  atWs.onclose = () => { atWs = null; };
}

function stopAutoTune() {
  if (atWs?.readyState === WebSocket.OPEN) {
    atWs.send(JSON.stringify({type:'cancel'}));
    document.getElementById('btn-at-stop').disabled = true;
  }
}

function doneAT() {
  document.getElementById('btn-at-run').disabled = false;
  document.getElementById('btn-at-stop').style.display = 'none';
  document.getElementById('btn-at-stop').disabled = false;
  document.getElementById('at-spinner').style.display = 'none';
}

function atLog(text, cls='') {
  const log = document.getElementById('at-log');
  const d = document.createElement('div');
  d.className = 'log-entry ' + cls;
  d.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function handleATMsg(msg) {
  if (msg.event === 'autotune_start') atLog(`▶ Auto-Tune · ${msg.total} ${t('msg_questions_n')} · ${msg.iterations} × ${t('at_iter_lbl')}`, 'phase');
  if (msg.event === 'autotune_phase') {
    document.getElementById('at-phase-text').textContent = msg.message;
    atLog(`⟶ ${msg.message}`, 'phase');
  }
  if (msg.event === 'autotune_fixes') atLog(`✦ ${msg.count} ${t('pr_recs_n')}`, 'ok');
  if (msg.event === 'autotune_synth') atLog(`✎ ${t('at_final_lbl')}: ${msg.preview}…`, 'done');
  if (msg.event === 'model_start') atLog(`▷ [${msg.model_name}] ${msg.total} ${t('msg_questions_n')}`, 'phase');
  if (msg.event === 'response') {
    if (msg.error) atLog(`✗ [${msg.question_id}] ${msg.error}`, 'err');
    else atLog(`✓ [${msg.question_id}] ${msg.latency_ms}${t('res_ms')}`, 'ok');
  }
  if (msg.event === 'model_done') atLog(`✓ ${msg.model_name}: ${msg.overall_score.toFixed(2)}/10`, 'done');
  if (msg.event === 'autotune_iter') atLog(`⟳ ${t('at_iter_n')} ${msg.iter}: ${msg.score.toFixed(2)} (${msg.delta >= 0 ? '+' : ''}${msg.delta.toFixed(2)})`, 'done');
  if (msg.event === 'autotune_cancelled') { atLog('⏹ ' + t('msg_stopped'), 'warn'); doneAT(); }
  if (msg.event === 'autotune_error') { atLog(`💥 ${msg.message}`, 'err'); notify(msg.message, 'err'); doneAT(); }
  if (msg.event === 'autotune_done') { renderATResult(msg); doneAT(); }
}

function renderATResult(r) {
  document.getElementById('at-progress-card').style.display = 'none';
  const gain = r.delta > 0 ? `+${r.delta.toFixed(2)}` : r.delta.toFixed(2);
  const gainColor = r.delta > 0.05 ? 'var(--green)' : r.delta < -0.05 ? 'var(--red)' : 'var(--text3)';
  const histRows = (r.history||[]).map(h => `<tr>
    <td style="color:var(--text3);">${t('at_iter_n')} ${h.iter}</td>
    <td>${pill(h.score)}</td>
    <td class="${h.delta > 0.05 ? 'ab-delta-pos' : h.delta < -0.05 ? 'ab-delta-neg' : 'ab-delta-neu'}">${h.delta >= 0 ? '+' : ''}${h.delta.toFixed(2)}</td>
  </tr>`).join('');
  document.getElementById('at-result-wrap').innerHTML = `
    <div class="card mb" style="text-align:center;padding:24px;${r.delta > 0.05 ? 'background:var(--green-light);border-color:var(--green);' : ''}">
      <div style="display:flex;justify-content:center;gap:32px;align-items:center;">
        <div><div style="font-size:2rem;font-weight:800;color:${sc(r.score_a)}">${r.score_a.toFixed(2)}</div><div style="font-size:11px;color:var(--text3);">${t('at_base_score')}</div></div>
        <div style="font-size:1.6rem;font-weight:800;color:${gainColor}">${gain}</div>
        <div><div style="font-size:2rem;font-weight:800;color:${sc(r.score_b)}">${r.score_b.toFixed(2)}</div><div style="font-size:11px;color:var(--text3);">${t('at_final_score')}</div></div>
      </div>
      ${r.delta <= 0.05 ? `<div style="margin-top:10px;font-size:12px;color:var(--text3);">${t('at_no_gain')}</div>` : ''}
    </div>
    <div class="card mb">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div class="card-label" style="margin:0;">${t('at_final_lbl')}</div>
        <button class="btn btn-secondary btn-sm" onclick="copyToClipboard('at-final-prompt')">${t('at_copy')}</button>
      </div>
      <pre id="at-final-prompt" style="background:var(--bg3);padding:14px;border-radius:var(--radius-sm);font-size:12px;font-family:monospace;white-space:pre-wrap;color:var(--text2);line-height:1.6;max-height:340px;overflow-y:auto;">${esc(r.final_prompt)}</pre>
    </div>
    <div class="table-wrap">
      <div class="card-label" style="padding:12px 14px 0;">${t('at_history')}</div>
      <table>
        <thead><tr><th>${t('at_iter_n')}</th><th>${t('col_score')}</th><th>${t('ab_col_delta')}</th></tr></thead>
        <tbody>${histRows}</tbody>
      </table>
    </div>`;
}
