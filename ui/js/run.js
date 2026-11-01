// Run page: model config, speed finder, benchmark run over WebSocket
let allQuestions = [];
let allResults = [];
let compareChart = null;
let modelCounter = 0;
let runProgState = {};
let activeWs = null;

function benchLang() {
  const el = document.getElementById('cfg-bench-lang');
  return el ? el.value : 'ru';
}

function addModel() {
  modelCounter++;
  const idx = modelCounter;
  const wrap = document.getElementById('models-list');
  const div = document.createElement('div');
  div.className = 'model-config-card';
  div.id = `model-card-${idx}`;
  div.innerHTML = `
    <div class="model-header">
      <div style="display:flex;align-items:center;gap:8px;">
        <span class="model-num">${wrap.children.length + 1}</span>
        <span style="font-size:13px;font-weight:600;color:var(--text)">${t('run_model_n')} ${wrap.children.length + 1}</span>
      </div>
      <button class="btn btn-ghost btn-xs" onclick="removeModel(${idx})">✕</button>
    </div>
    <div class="form-group">
      <label class="form-label">${t('lbl_name')}</label>
      <input class="form-input" id="m${idx}-name" placeholder="GPT-4o mini">
    </div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">${t('lbl_base_url')}</label>
        <input class="form-input" id="m${idx}-url" value="https://api.openai.com/v1">
      </div>
      <div class="form-group">
        <label class="form-label">${t('lbl_model_id')}</label>
        <input class="form-input" id="m${idx}-model" placeholder="gpt-4o-mini">
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">${t('lbl_api_key')}</label>
      <input class="form-input" type="password" id="m${idx}-key" placeholder="sk-...">
    </div>
    <div class="form-group">
      <label class="form-label">${t('lbl_sysprompt_opt')} <span class="opt">${t('lbl_opt')}</span></label>
      <textarea class="form-textarea" id="m${idx}-sysprompt" placeholder="..." style="min-height:52px;"></textarea>
    </div>`;
  wrap.appendChild(div);
  renumberModels();
}

function removeModel(idx) {
  const el = document.getElementById(`model-card-${idx}`);
  if (el) el.remove();
  renumberModels();
}

function renumberModels() {
  const cards = document.querySelectorAll('#models-list .model-config-card');
  cards.forEach((card, i) => {
    const num = card.querySelector('.model-num');
    if (num) num.textContent = i + 1;
  });
}

function getModels() {
  const cards = document.querySelectorAll('#models-list .model-config-card');
  return [...cards].map(card => {
    const id = card.id.replace('model-card-','');
    return {
      name: document.getElementById(`m${id}-name`)?.value.trim() || document.getElementById(`m${id}-model`)?.value.trim() || 'model',
      base_url: document.getElementById(`m${id}-url`)?.value.trim() || 'https://api.openai.com/v1',
      api_key: document.getElementById(`m${id}-key`)?.value.trim() || '',
      model: document.getElementById(`m${id}-model`)?.value.trim() || '',
      system_prompt: document.getElementById(`m${id}-sysprompt`)?.value.trim() || null,
      concurrency: parseInt(document.getElementById('cfg-concurrency')?.value) || 5,
    };
  });
}

async function runSpeedTest() {
  const models = getModels();
  if (!models.length) { notify(t('msg_add_model'), 'err'); return; }
  const m = models[0];
  if (!m.api_key || !m.model) { notify(t('msg_fill_one'), 'err'); return; }
  const btn = document.getElementById('btn-speed');
  btn.disabled = true;
  btn.textContent = t('run_speed_testing');
  document.getElementById('speed-result').style.display = 'none';
  try {
    const res = await fetch('/api/speed-test', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ model: m })
    });
    const data = await res.json();
    if (data.error) { notify(data.error, 'err'); return; }
    const recConc = data.recommended_concurrency;
    document.getElementById('cfg-concurrency').value = recConc;
    let rows = data.results.map(r => {
      if (r.error) return `<div class="speed-result-row"><span style="width:60px;font-weight:600">×${r.concurrency}</span><span style="color:var(--red)">${esc(r.error.slice(0,60))}</span></div>`;
      const isBest = r.concurrency === recConc;
      return `<div class="speed-result-row" style="${isBest ? 'background:var(--accent-light);border-radius:6px;padding:8px;' : ''}">
        <span style="width:60px;font-weight:700;color:${isBest?'var(--accent)':'var(--text2)'}">×${r.concurrency}</span>
        <span style="flex:1;color:var(--text2)">${r.throughput_qps} ${t('run_qps')} · ${r.avg_latency_ms}ms avg · ${r.elapsed_s}s</span>
        ${isBest ? `<span class="badge badge-accent">${t('run_speed_best')}</span>` : ''}
      </div>`;
    }).join('');
    document.getElementById('speed-result').style.display = 'block';
    document.getElementById('speed-result').innerHTML = `
      <div style="font-size:12px;font-weight:600;color:var(--accent);margin-bottom:8px;">${esc(data.summary)}</div>
      <div style="font-size:11px;color:var(--text3);margin-bottom:10px;">${t('run_speed_set')}: <b>${recConc}</b></div>
      ${rows}`;
    notify(`${t('msg_optimal')}: ${recConc} ${t('msg_streams')}`, 'ok');
  } catch(e) {
    notify(t('msg_speed_err') + ': ' + e.message, 'err');
  } finally {
    btn.disabled = false;
    btn.textContent = t('run_speed_btn');
  }
}
// __RUN_PART2__
function startQuickRun() {
  document.getElementById('cfg-limit').value = '0';
  document.querySelectorAll('.checkbox-group input').forEach(c => c.checked = false);
  startRun('quick');
}

function startRun(mode) {
  mode = mode || 'full';
  const models = getModels();
  if (!models.length) { notify(t('msg_add_model'), 'err'); return; }
  for (const m of models) {
    if (!m.api_key || !m.model) { notify(t('msg_fill_model'), 'err'); return; }
  }
  const judgeKey = document.getElementById('judge-key').value.trim();
  const judgeModel = document.getElementById('judge-model').value.trim();
  const judgeUrl = document.getElementById('judge-url').value.trim();
  if (!judgeKey || !judgeModel) { notify(t('msg_fill_judge'), 'err'); return; }

  const limit = parseInt(document.getElementById('cfg-limit').value) || 0;
  const cats = [...document.querySelectorAll('.checkbox-group input:checked')].map(c => c.value);
  const judgeConc = parseInt(document.getElementById('judge-concurrency').value) || 3;
  const webhookUrl = document.getElementById('cfg-webhook')?.value.trim() || null;
  const payload = {
    models, judge_key: judgeKey, judge_model: judgeModel, judge_base_url: judgeUrl,
    judge_concurrency: judgeConc,
    limit: mode === 'quick' ? null : (limit || null),
    categories: mode === 'quick' ? null : (cats.length ? cats : null),
    webhook_url: webhookUrl || null,
    mode, lang: benchLang(), ui_lang: LANG,
  };

  document.getElementById('run-idle-card').style.display = 'none';
  document.getElementById('run-results-list').style.display = 'none';
  document.getElementById('run-progress-card').style.display = 'block';
  document.getElementById('btn-run').disabled = true;
  document.getElementById('btn-quick').disabled = true;
  document.getElementById('btn-stop').style.display = '';
  document.getElementById('run-log').innerHTML = '';
  document.getElementById('run-phase-text').textContent = t('run_init');
  document.getElementById('run-spinner').style.display = '';
  runProgState = {};

  const mbEl = document.getElementById('model-progress-blocks');
  mbEl.innerHTML = models.map((m, i) => `
    <div class="model-progress-block" id="mpb-${i}">
      <div class="model-progress-name">
        <span class="model-num" style="background:${COLORS[i%COLORS.length]}">${i+1}</span>
        ${esc(m.name || m.model)}
        <span id="mpb-status-${i}" style="margin-left:auto;font-size:11px;color:var(--text3)">${t('run_status_wait')}</span>
      </div>
      <div class="prog-row">
        <span class="prog-label">${t('run_prog_query')}</span>
        <div class="progress-wrap" style="flex:1"><div class="progress-bar" id="mpb-q-${i}" style="width:0%"></div></div>
        <span class="prog-val" id="mpb-q-lbl-${i}">0/—</span>
      </div>
      <div class="prog-row">
        <span class="prog-label">${t('run_prog_judge')}</span>
        <div class="progress-wrap" style="flex:1"><div class="progress-bar green" id="mpb-j-${i}" style="width:0%"></div></div>
        <span class="prog-val" id="mpb-j-lbl-${i}">0/—</span>
      </div>
      <div id="mpb-stats-${i}" style="display:flex;gap:16px;margin-top:8px;font-size:11px;color:var(--text3);"></div>
      <div id="mpb-preview-${i}" style="margin-top:8px;font-size:11px;color:var(--text2);background:var(--bg3);border-radius:6px;padding:7px 10px;display:none;font-style:italic;line-height:1.5;"></div>
    </div>`).join('');

  const ws = new WebSocket(`ws://${location.host}/ws/run`);
  activeWs = ws;
  ws.onopen = () => { ws.send(JSON.stringify(payload)); logLine(t('msg_ws_ok'), 'ok'); };
  ws.onmessage = e => handleMsg(JSON.parse(e.data), models.length);
  ws.onerror = () => { logLine(t('msg_ws_err'), 'err'); notify(t('msg_ws_err2'), 'err'); doneRun(); };
  ws.onclose = () => { activeWs = null; };
}

function stopRun() {
  if (activeWs && activeWs.readyState === WebSocket.OPEN) {
    activeWs.send(JSON.stringify({ type: 'cancel' }));
    logLine(t('msg_stop_sent'), 'warn');
    document.getElementById('btn-stop').disabled = true;
  }
}

function doneRun() {
  document.getElementById('btn-run').disabled = false;
  document.getElementById('btn-quick').disabled = false;
  document.getElementById('btn-stop').style.display = 'none';
  document.getElementById('btn-stop').disabled = false;
  document.getElementById('run-spinner').style.display = 'none';
  activeWs = null;
}

function logLine(text, cls='') {
  const log = document.getElementById('run-log');
  const div = document.createElement('div');
  div.className = 'log-entry ' + cls;
  div.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}
// __RUN_PART3__
function handleMsg(msg, totalModels) {
  const { event, model_idx } = msg;
  const i = model_idx ?? 0;

  if (event === 'start') {
    logLine(`▶ ${msg.total_models} × ${msg.total_questions} ${t('msg_questions_n')}`, 'phase');
  }
  if (event === 'model_start') {
    document.getElementById('run-phase-text').textContent = `[${msg.model_name}] ${t('run_status_query')}`;
    document.getElementById(`mpb-status-${i}`).textContent = t('run_status_query');
    logLine(`▷ [${msg.model_name}] ${msg.total} ${t('msg_questions_n')}`, 'phase');
    if (!runProgState[i]) runProgState[i] = { qTotal: msg.total, jTotal: msg.total };
  }
  if (event === 'response') {
    const tt = runProgState[i]?.qTotal || msg.total;
    const pct = Math.round(msg.done / tt * 100);
    const bar = document.getElementById(`mpb-q-${i}`);
    const lbl = document.getElementById(`mpb-q-lbl-${i}`);
    if (bar) bar.style.width = pct + '%';
    if (lbl) lbl.textContent = `${msg.done}/${tt}`;
    if (!runProgState[i]) runProgState[i] = {};
    runProgState[i].errors = (runProgState[i].errors || 0) + (msg.error ? 1 : 0);
    runProgState[i].latencies = runProgState[i].latencies || [];
    if (!msg.error) runProgState[i].latencies.push(msg.latency_ms);
    const statsEl = document.getElementById(`mpb-stats-${i}`);
    if (statsEl) {
      const errCount = runProgState[i].errors || 0;
      const lats = runProgState[i].latencies || [];
      const avgLat = lats.length ? Math.round(lats.slice(-10).reduce((a,b)=>a+b,0)/Math.min(lats.length,10)) : 0;
      const remaining = tt - msg.done;
      const eta = avgLat && remaining ? Math.round(remaining * avgLat / 1000) : null;
      statsEl.innerHTML = [
        errCount ? `<span style="color:var(--orange)">✗ ${errCount} ${t('run_errors_n')}</span>` : t('run_no_errors'),
        avgLat ? `<span>avg ${avgLat}ms</span>` : '',
        eta ? `<span>ETA ~${eta}s</span>` : '',
        msg.attempts > 1 ? `<span style="color:var(--yellow)">${t('run_attempt_n')} ${msg.attempts}</span>` : '',
      ].filter(Boolean).join(' · ');
    }
    if (msg.preview) {
      const prevEl = document.getElementById(`mpb-preview-${i}`);
      if (prevEl) {
        prevEl.style.display = 'block';
        prevEl.innerHTML = `<span style="color:var(--text3);font-style:normal;font-weight:600;">${msg.question_id}</span> → ${esc(msg.preview)}`;
      }
    }
    if (msg.error) logLine(`✗ [${msg.question_id}] ${msg.error}${msg.attempts > 1 ? ` (${t('run_attempt_n')} ${msg.attempts})` : ''}`, 'err');
    else logLine(`✓ [${msg.question_id}] ${msg.latency_ms}${t('res_ms')}${msg.attempts > 1 ? ` (${t('run_attempt_n')} ${msg.attempts})` : ''}`, 'ok');
  }
  if (event === 'phase') {
    document.getElementById('run-phase-text').textContent = msg.message;
    if (msg.phase === 'judging') {
      const s = document.getElementById(`mpb-status-${i}`);
      if (s) s.textContent = t('run_status_judge');
    }
    logLine(`⟶ ${msg.message}`, 'phase');
  }
  if (event === 'score') {
    const tt = runProgState[i]?.jTotal || msg.total;
    const pct = Math.round(msg.done / tt * 100);
    const bar = document.getElementById(`mpb-j-${i}`);
    const lbl = document.getElementById(`mpb-j-lbl-${i}`);
    if (bar) bar.style.width = pct + '%';
    if (lbl) lbl.textContent = `${msg.done}/${tt}`;
    if (msg.error) logLine(`⚠ judge err [${msg.question_id}]: ${msg.error}`, 'warn');
  }
  if (event === 'concurrency_reduced') {
    logLine(`⚠ ${msg.message}`, 'warn');
    notify(msg.message, 'warn');
  }
  if (event === 'model_done') {
    const s = document.getElementById(`mpb-status-${i}`);
    if (s) s.innerHTML = `<span style="color:var(--green);font-weight:700;">${msg.overall_score.toFixed(2)}</span>`;
    const bar = document.getElementById(`mpb-q-${i}`);
    const jbar = document.getElementById(`mpb-j-${i}`);
    if (bar) bar.style.width = '100%';
    if (jbar) jbar.style.width = '100%';
    const prevEl = document.getElementById(`mpb-preview-${i}`);
    if (prevEl) prevEl.style.display = 'none';
    const coverageStr = msg.coverage !== undefined && msg.coverage !== msg.total
      ? ` · ${t('run_coverage')} ${msg.coverage}/${msg.total}`
      : '';
    const skippedStr = msg.skipped?.length ? ` · ${t('run_skipped_n')} ${msg.skipped.length}` : '';
    logLine(`✓ [${msg.model_name}] ${msg.overall_score.toFixed(2)}/10${coverageStr}${skippedStr}`, 'done');
    if (msg.skipped?.length) {
      logLine(`${t('run_skipped_list')}: ${msg.skipped.join(', ')}`, 'warn');
    }
    const resEl = document.getElementById('run-results-list');
    resEl.style.display = 'block';
    const cardsEl = document.getElementById('run-result-cards');
    const div = document.createElement('div');
    div.className = 'card mb';
    div.style.borderLeft = `3px solid ${COLORS[i % COLORS.length]}`;
    const skippedBadge = msg.skipped?.length
      ? `<span class="badge" style="background:var(--orange-light);color:var(--orange);margin-left:8px;">⚠ ${msg.skipped.length} ${t('run_skipped_n')}</span>`
      : '';
    const fixesHtml = msg.prompt_fixes?.length
      ? `<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border);">
           <div style="font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">${t('run_prompt_recs')}</div>
           ${msg.prompt_fixes.map(f => `
             <div style="font-size:12px;margin-bottom:6px;display:flex;gap:8px;align-items:flex-start;">
               <span class="badge badge-accent" style="flex-shrink:0;">${CAT[f.category]||f.category}</span>
               <span style="color:var(--text2);font-family:monospace;background:var(--bg3);padding:3px 8px;border-radius:4px;font-size:11px;">${esc(f.fix)}</span>
             </div>`).join('')}
         </div>`
      : '';
    div.innerHTML = `
      <div style="display:flex;align-items:center;gap:14px;">
        <div style="font-size:2rem;font-weight:800;color:${sc(msg.overall_score)}">${msg.overall_score.toFixed(2)}</div>
        <div style="flex:1;">
          <div style="font-weight:600;font-size:14px;">${esc(msg.model_name)}${skippedBadge}</div>
          <div style="font-size:11px;color:var(--text3);">${msg.answered}/${msg.total} ${t('res_questions_n')} · ${t('run_coverage')} ${msg.coverage ?? msg.answered}/${msg.total}</div>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="window.open('/api/results/${esc(msg.filename.replace('.json',''))}/report','_blank')">${t('common_report')}</button>
      </div>
      <div style="margin-top:12px;">
        ${Object.entries(msg.category_scores).sort((a,b)=>b[1]-a[1]).map(([cat,val])=>`
        <div class="cat-bar-row">
          <span class="cat-bar-label">${CAT[cat]||cat}</span>
          <div class="cat-bar-wrap"><div class="cat-bar-fill" style="width:${val*10}%;background:${sc(val)}"></div></div>
          <span class="cat-bar-val" style="color:${sc(val)}">${val.toFixed(1)}</span>
        </div>`).join('')}
      </div>
      ${fixesHtml}`;
    cardsEl.appendChild(div);
    loadResults();
  }
  if (event === 'all_done') {
    document.getElementById('run-phase-text').textContent = t('run_phase_all_done');
    document.getElementById('run-spinner').style.display = 'none';
    logLine('✅ ' + t('run_phase_all_done'), 'done');
    doneRun();
    launchConfetti();
  }
  if (event === 'cancelled') {
    document.getElementById('run-phase-text').textContent = t('run_stopped');
    document.getElementById('run-spinner').style.display = 'none';
    logLine(`⏹ ${msg.message}`, 'warn');
    notify(t('msg_stopped'), 'warn');
    doneRun();
  }
  if (event === 'error') {
    logLine(`💥 ${t('msg_err')}: ${msg.message}`, 'err');
    notify(t('msg_err') + ': ' + msg.message, 'err');
    doneRun();
  }
}
// __RUN_PART4__
async function retrySkipped(filename, skippedIds) {
  const res = await fetch(`/api/results/${filename}`);
  const data = await res.json();
  nav('run', document.querySelector('[data-page=run]'));
  const cards = document.querySelectorAll('#models-list .model-config-card');
  if (!cards.length) { notify(t('msg_set_run_first'), 'warn'); return; }
  notify(`${t('msg_retry_warn')} (${skippedIds.length})`, 'warn');
  const judgeKey = document.getElementById('judge-key').value.trim();
  const judgeModel = document.getElementById('judge-model').value.trim();
  const judgeUrl = document.getElementById('judge-url').value.trim();
  if (!judgeKey || !judgeModel) { notify(t('msg_fill_judge'), 'err'); return; }
  const models = getModels();
  if (!models.length || !models[0].api_key) { notify(t('msg_fill_one'), 'err'); return; }

  models[0].concurrency = 1;
  const judgeConc = parseInt(document.getElementById('judge-concurrency').value) || 3;
  const payload = {
    models: [models[0]],
    judge_key: judgeKey, judge_model: judgeModel, judge_base_url: judgeUrl,
    judge_concurrency: judgeConc,
    question_ids: skippedIds,
    mode: 'retry',
    lang: data.meta?.lang || benchLang(),
    ui_lang: LANG,
  };

  document.getElementById('run-idle-card').style.display = 'none';
  document.getElementById('run-results-list').style.display = 'none';
  document.getElementById('run-progress-card').style.display = 'block';
  document.getElementById('btn-run').disabled = true;
  document.getElementById('btn-quick').disabled = true;
  document.getElementById('btn-stop').style.display = '';
  document.getElementById('run-log').innerHTML = '';
  document.getElementById('run-phase-text').textContent = t('res_retry');
  document.getElementById('run-spinner').style.display = '';
  runProgState = {};

  const mbEl = document.getElementById('model-progress-blocks');
  mbEl.innerHTML = `<div class="model-progress-block" id="mpb-0">
    <div class="model-progress-name"><span class="model-num" style="background:${COLORS[0]}">↺</span>${esc(models[0].name || models[0].model)}
      <span id="mpb-status-0" style="margin-left:auto;font-size:11px;color:var(--text3)">↺</span>
    </div>
    <div class="prog-row"><span class="prog-label">${t('run_prog_query')}</span><div class="progress-wrap" style="flex:1"><div class="progress-bar" id="mpb-q-0" style="width:0%"></div></div><span class="prog-val" id="mpb-q-lbl-0">0/${skippedIds.length}</span></div>
    <div class="prog-row"><span class="prog-label">${t('run_prog_judge')}</span><div class="progress-wrap" style="flex:1"><div class="progress-bar green" id="mpb-j-0" style="width:0%"></div></div><span class="prog-val" id="mpb-j-lbl-0">0/${skippedIds.length}</span></div>
    <div id="mpb-stats-0" style="display:flex;gap:16px;margin-top:8px;font-size:11px;color:var(--text3);"></div>
    <div id="mpb-preview-0" style="margin-top:8px;font-size:11px;color:var(--text2);background:var(--bg3);border-radius:6px;padding:7px 10px;display:none;font-style:italic;line-height:1.5;"></div>
  </div>`;

  const ws = new WebSocket(`ws://${location.host}/ws/run`);
  activeWs = ws;
  ws.onopen = () => { ws.send(JSON.stringify(payload)); logLine(`↺ ${t('res_retry')}: ${skippedIds.length} ${t('msg_questions_n')}`, 'phase'); };
  ws.onmessage = e => handleMsg(JSON.parse(e.data), 1);
  ws.onerror = () => { logLine(t('msg_ws_err'), 'err'); doneRun(); };
  ws.onclose = () => { activeWs = null; };
}
