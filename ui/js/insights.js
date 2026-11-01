// Insights: leaderboard, trend, analytics, prompt recommendations
function renderLeaderboard() {
  const wrap = document.getElementById('leaderboard-wrap');
  if (!wrap) return;
  const mode = document.getElementById('lb-filter-mode')?.value || '';
  let data = [...allResults];
  if (mode) data = data.filter(r => (r.mode || 'full') === mode);
  data.sort((a, b) => b.overall_score - a.overall_score);

  if (!data.length) { wrap.innerHTML = `<div class="empty"><div class="icon">◈</div><p>${t('lb_no_runs')}</p></div>`; return; }

  const medals = ['🥇','🥈','🥉'];
  wrap.innerHTML = `<div class="card">
    <table>
      <thead><tr><th>#</th><th>${t('lb_col_model')}</th><th>${t('lb_col_score')}</th><th>${t('lb_col_level')}</th><th>${t('lb_col_cov')}</th><th>${t('lb_col_mode')}</th><th>${t('lb_col_date')}</th><th></th></tr></thead>
      <tbody>${data.map((r, i) => {
        const [lvl, lvlColor] = levelLabel(r.overall_score);
        const medal = medals[i] || `${i+1}`;
        const modeName = r.mode === 'quick' ? t('lb_mode_quick') : r.mode === 'stress' ? t('lb_mode_stress') : t('lb_mode_full');
        return `<tr>
          <td style="font-size:1.2rem;width:40px;text-align:center;">${medal}</td>
          <td style="font-weight:600;color:var(--text)">${esc(r.model_name)}<span class="mlang-tag">${(r.lang||'ru').toUpperCase()}</span></td>
          <td>${pill(r.overall_score)}</td>
          <td><span style="font-size:12px;font-weight:600;color:${lvlColor}">${lvl}</span></td>
          <td style="font-size:12px;color:var(--text3)">${r.coverage ?? r.answered}/${r.total_questions}</td>
          <td style="font-size:11px;">${modeName}</td>
          <td style="font-size:11px;color:var(--text3)">${r.run_at.slice(0,10)}</td>
          <td><button class="btn btn-ghost btn-xs" onclick="viewResult('${r.filename}');nav('results',document.querySelector('[data-page=results]'))">→</button></td>
        </tr>`;
      }).join('')}
      </tbody>
    </table>
  </div>`;
}

function populateTrendSelect() {
  const sel = document.getElementById('trend-model-select');
  if (!sel) return;
  const names = [...new Set(allResults.map(r => r.model_name))].sort();
  sel.innerHTML = `<option value="">${t('tr_select_ph')}</option>` + names.map(n => `<option value="${esc(n)}">${esc(n)}</option>`).join('');
}

function renderTrend() {
  const name = document.getElementById('trend-model-select')?.value;
  const wrap = document.getElementById('trend-wrap');
  if (!wrap) return;
  if (!name) { wrap.innerHTML = ''; return; }

  const runs = allResults.filter(r => r.model_name === name).sort((a,b) => new Date(a.run_at)-new Date(b.run_at));
  if (runs.length < 2) { wrap.innerHTML = `<div class="empty"><p>${t('tr_min2')}</p></div>`; return; }

  const chartId = 'trend-chart-' + Date.now();
  const labels = runs.map((r,i) => `${i+1}. ${r.run_at.slice(0,10)}`);
  const scores = runs.map(r => r.overall_score);
  const first = scores[0], last = scores[scores.length-1];
  const delta = (last - first).toFixed(2);
  const deltaColor = delta >= 0 ? 'var(--green)' : 'var(--red)';

  wrap.innerHTML = `
    <div class="grid-3 mb">
      <div class="card stat-box"><div class="val" style="color:${sc(first)}">${first.toFixed(2)}</div><div class="lbl">${t('tr_start')}</div></div>
      <div class="card stat-box"><div class="val" style="color:${sc(last)}">${last.toFixed(2)}</div><div class="lbl">${t('tr_last')}</div></div>
      <div class="card stat-box"><div class="val" style="color:${deltaColor}">${delta >= 0 ? '+' : ''}${delta}</div><div class="lbl">${t('tr_progress')}</div></div>
    </div>
    <div class="card mb">
      <div class="card-label">${t('tr_dyn')}</div>
      <div class="chart-container"><canvas id="${chartId}"></canvas></div>
    </div>
    <div class="card">
      <div class="card-label">${t('tr_cats')}</div>
      ${CAT_KEYS.map(cat => {
        const v1 = (runs[0].category_scores||{})[cat] || 0;
        const v2 = (runs[runs.length-1].category_scores||{})[cat] || 0;
        const d = (v2 - v1).toFixed(1);
        const dc = d >= 0 ? 'var(--green)' : 'var(--red)';
        return `<div class="cat-bar-row">
          <span class="cat-bar-label">${CAT[cat]}</span>
          <div class="cat-bar-wrap" style="flex:1"><div class="cat-bar-fill" style="width:${v2*10}%;background:${sc(v2)}"></div></div>
          <span style="font-size:11px;color:${dc};width:36px;text-align:right;font-weight:700">${d >= 0 ? '+' : ''}${d}</span>
          <span class="cat-bar-val" style="color:${sc(v2)}">${v2.toFixed(1)}</span>
        </div>`;
      }).join('')}
    </div>`;

  new Chart(document.getElementById(chartId), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: name,
        data: scores,
        borderColor: '#4f6ef7',
        backgroundColor: 'rgba(79,110,247,0.08)',
        pointBackgroundColor: scores.map(s => s === Math.max(...scores) ? '#16a34a' : '#4f6ef7'),
        pointRadius: 6,
        borderWidth: 2,
        tension: 0.3,
        fill: true,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        y: { min: 0, max: 10, ticks: { color: '#8892a8' }, grid: { color: '#e4e8ef' } },
        x: { ticks: { color: '#8892a8' }, grid: { color: '#e4e8ef' } }
      },
      plugins: { legend: { display: false } }
    }
  });
}
// __INSIGHTS_PART2__
function populateAnalyticsSelect() {
  const sel = document.getElementById('analytics-run-select');
  if (!sel) return;
  sel.innerHTML = `<option value="">${t('lbl_select_ph')}</option>` +
    allResults.map(r => `<option value="${r.filename}">${esc(r.model_name)} · ${r.run_at.slice(0,16).replace('T',' ')}</option>`).join('');
}

async function loadAnalytics() {
  const fn = document.getElementById('analytics-run-select')?.value;
  const wrap = document.getElementById('analytics-wrap');
  if (!wrap || !fn) return;
  wrap.innerHTML = `<div class="empty"><p>${t('res_loading')}</p></div>`;
  const res = await fetch(`/api/results/${fn}`);
  const data = await res.json();
  renderAnalytics(data);
}

function renderAnalytics(data) {
  const wrap = document.getElementById('analytics-wrap');
  const items = data.items || [];
  const answered = items.filter(i => i.response && !i.skipped);
  const lengths = answered.map(i => i.response.split(/\s+/).length);
  const avgLen = lengths.length ? Math.round(lengths.reduce((a,b)=>a+b,0)/lengths.length) : 0;
  const maxItem = answered.reduce((a,b) => (b.response?.split(/\s+/).length||0) > (a.response?.split(/\s+/).length||0) ? b : a, answered[0] || {});
  const minItem = answered.reduce((a,b) => (b.response?.split(/\s+/).length||Infinity) < (a.response?.split(/\s+/).length||Infinity) ? b : a, answered[0] || {});
  const catLengths = {};
  answered.forEach(i => {
    catLengths[i.category] = catLengths[i.category] || [];
    catLengths[i.category].push(i.response.split(/\s+/).length);
  });
  const catAvg = Object.entries(catLengths).map(([cat, lens]) => [cat, Math.round(lens.reduce((a,b)=>a+b,0)/lens.length)]).sort((a,b)=>b[1]-a[1]);
  const withLists = answered.filter(i => /^[-•*]\s|\n[-•*]\s|\d+\.\s/m.test(i.response)).length;
  const listPct = Math.round(withLists / (answered.length||1) * 100);
  const failed = items.filter(i => i.response_error && i.response_error !== 'not run' && !i.response);
  const clusterByCat = {};
  const clusterByDiff = {};
  failed.forEach(i => {
    clusterByCat[i.category] = (clusterByCat[i.category]||0)+1;
    clusterByDiff[i.difficulty] = (clusterByDiff[i.difficulty]||0)+1;
  });
  const multiAttempt = items.filter(i => (i.attempts||1) > 1);
  const scoreBuckets = [0,0,0,0,0];
  items.filter(i=>!i.judge_error&&!i.skipped).forEach(i => {
    const s = i.weighted_total;
    scoreBuckets[Math.min(4, Math.floor(s/2))]++;
  });
  const distChartId = 'dist-' + Date.now();

  wrap.innerHTML = `
    <div class="grid-4 mb">
      <div class="card stat-box"><div class="val">${avgLen}</div><div class="lbl">${t('an_words')}</div></div>
      <div class="card stat-box"><div class="val">${listPct}%</div><div class="lbl">${t('an_lists')}</div></div>
      <div class="card stat-box"><div class="val" style="color:var(--${failed.length>5?'red':'green'})">${failed.length}</div><div class="lbl">${t('an_req_err')}</div></div>
      <div class="card stat-box"><div class="val" style="color:var(--${multiAttempt.length>0?'yellow':'green'})">${multiAttempt.length}</div><div class="lbl">${t('an_retry')}</div></div>
    </div>
    <div class="grid-2 mb">
      <div class="card">
        <div class="card-label">${t('an_len_cat')}</div>
        ${catAvg.map(([cat,avg]) => {
          const maxA = catAvg[0][1] || 1;
          return `<div class="cat-bar-row">
            <span class="cat-bar-label">${CAT[cat]||cat}</span>
            <div class="cat-bar-wrap"><div class="cat-bar-fill" style="width:${avg/maxA*100}%;background:var(--accent)"></div></div>
            <span class="cat-bar-val" style="color:var(--accent)">${avg}</span>
          </div>`;
        }).join('')}
      </div>
      <div class="card">
        <div class="card-label">${t('an_dist')}</div>
        <div class="chart-container"><canvas id="${distChartId}"></canvas></div>
      </div>
    </div>
    ${failed.length ? `<div class="card mb">
      <div class="card-label" style="color:var(--orange)">${t('an_cluster_n')} (${failed.length} ${t('an_failed_total')})</div>
      <div class="grid-2" style="margin-bottom:12px;">
        <div>
          <div style="font-size:11px;font-weight:600;color:var(--text3);margin-bottom:8px;">${t('an_by_cat')}</div>
          ${Object.entries(clusterByCat).sort((a,b)=>b[1]-a[1]).map(([cat,n])=>`
            <div class="cat-bar-row">
              <span class="cat-bar-label">${CAT[cat]||cat}</span>
              <div class="cat-bar-wrap"><div class="cat-bar-fill" style="width:${n/failed.length*100}%;background:var(--orange)"></div></div>
              <span class="cat-bar-val" style="color:var(--orange)">${n}</span>
            </div>`).join('')}
        </div>
        <div>
          <div style="font-size:11px;font-weight:600;color:var(--text3);margin-bottom:8px;">${t('an_by_diff')}</div>
          ${Object.entries(clusterByDiff).sort((a,b)=>b[1]-a[1]).map(([d,n])=>`
            <div class="cat-bar-row">
              <span class="cat-bar-label"><span class="badge badge-${d}">${d}</span></span>
              <div class="cat-bar-wrap"><div class="cat-bar-fill" style="width:${n/failed.length*100}%;background:var(--orange)"></div></div>
              <span class="cat-bar-val" style="color:var(--orange)">${n}</span>
            </div>`).join('')}
        </div>
      </div>
      <div style="font-size:11px;font-weight:600;color:var(--text3);margin-bottom:8px;">${t('an_failed_q')}</div>
      ${failed.map(i=>`<div style="font-size:12px;padding:6px 0;border-bottom:1px solid var(--border);display:flex;gap:10px;align-items:center;">
        <span style="font-family:monospace;color:var(--text3);width:70px;">${i.id}</span>
        <span class="badge badge-${i.difficulty}">${i.difficulty}</span>
        <span class="badge badge-accent">${CAT[i.category]||i.category}</span>
        <span style="color:var(--red);font-size:11px;">${esc((i.response_error||'').slice(0,60))}</span>
        ${(i.attempts||1)>1?`<span style="color:var(--yellow);font-size:11px;">↺${i.attempts}</span>`:''}
      </div>`).join('')}
    </div>` : `<div class="card mb" style="border-left:3px solid var(--green);"><div style="font-weight:600;color:var(--green);">${t('an_no_fails')}</div></div>`}
    <div class="card mb">
      <div class="card-label">${t('an_extremes')}</div>
      <div class="grid-2">
        <div>
          <div style="font-size:11px;font-weight:600;color:var(--text3);margin-bottom:8px;">${t('an_longest')}</div>
          ${maxItem?.id ? `<div style="font-size:12px;"><b>${maxItem.id}</b> · ${(maxItem.response||'').split(/\s+/).length} ${t('an_words_n')}<br><span style="color:var(--text3);">${esc((maxItem.response||'').slice(0,120))}…</span></div>` : '—'}
        </div>
        <div>
          <div style="font-size:11px;font-weight:600;color:var(--text3);margin-bottom:8px;">${t('an_shortest')}</div>
          ${minItem?.id ? `<div style="font-size:12px;"><b>${minItem.id}</b> · ${(minItem.response||'').split(/\s+/).length} ${t('an_words_n')}<br><span style="color:var(--text3);">${esc((minItem.response||'').slice(0,120))}…</span></div>` : '—'}
        </div>
      </div>
    </div>`;

  new Chart(document.getElementById(distChartId), {
    type: 'bar',
    data: {
      labels: ['0–2','2–4','4–6','6–8','8–10'],
      datasets: [{
        data: scoreBuckets,
        backgroundColor: ['#dc2626cc','#ea580ccc','#d97706cc','#16a34acc','#4f6ef7cc'],
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { ticks:{color:'#8892a8'}, grid:{color:'#e4e8ef'} }, x: { ticks:{color:'#8892a8'}, grid:{color:'transparent'} } },
      plugins: { legend: { display: false } }
    }
  });
}

function populatePromptsSelect() {
  const sel = document.getElementById('prompts-run-select');
  if (!sel) return;
  sel.innerHTML = `<option value="">${t('lbl_select_ph')}</option>` +
    allResults.map(r => `<option value="${r.filename}">${esc(r.model_name)} · ${r.run_at.slice(0,16).replace('T',' ')}</option>`).join('');
}

async function loadPromptRecs() {
  const fn = document.getElementById('prompts-run-select')?.value;
  const wrap = document.getElementById('prompts-wrap');
  if (!wrap || !fn) return;
  wrap.innerHTML = `<div class="empty"><p>${t('res_loading')}</p></div>`;
  const res = await fetch(`/api/results/${fn}`);
  const data = await res.json();
  renderPromptRecs(data);
}

function renderPromptRecs(data) {
  const wrap = document.getElementById('prompts-wrap');
  const items = data.items || [];
  const s = data.summary;
  const allFixes = [];
  items.forEach(item => {
    if (item.prompt_fix && item.prompt_fix.trim()) {
      allFixes.push({ category: item.category, fix: item.prompt_fix, score: item.weighted_total, id: item.id });
    }
  });
  const byCat = {};
  allFixes.forEach(f => { byCat[f.category] = byCat[f.category] || []; byCat[f.category].push(f); });
  const weakCats = Object.entries(s.category_scores || {}).filter(([,v]) => v < 7).sort((a,b)=>a[1]-b[1]);
  const systemPromptText = data.meta.system_prompt || '';
  let consolidated = '';
  Object.entries(byCat).forEach(([cat, fixes]) => {
    const unique = [...new Set(fixes.map(f=>f.fix.trim()))];
    if (unique[0]) consolidated += `// ${CAT[cat]||cat}\n${unique[0]}\n\n`;
  });

  wrap.innerHTML = `
    ${weakCats.length ? `<div class="card mb" style="border-left:3px solid var(--orange);">
      <div class="card-label">${t('pr_weak')}</div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;">
        ${weakCats.map(([cat,val])=>`<div style="display:flex;align-items:center;gap:6px;background:var(--orange-light);padding:6px 12px;border-radius:var(--radius-sm);">
          <span style="font-weight:600;color:var(--orange)">${CAT[cat]||cat}</span>
          <span style="color:var(--orange);font-size:12px;">${val.toFixed(1)}</span>
        </div>`).join('')}
      </div>
    </div>` : `<div class="card mb" style="border-left:3px solid var(--green);"><span style="font-weight:600;color:var(--green);">${t('pr_strong')}</span></div>`}

    ${consolidated ? `<div class="card mb">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div class="card-label" style="margin:0;">${t('pr_consol')}</div>
        <button class="btn btn-secondary btn-sm" onclick="copyToClipboard('consolidated-fixes')">${t('pr_copy_all')}</button>
      </div>
      <pre id="consolidated-fixes" style="background:var(--bg3);padding:14px;border-radius:var(--radius-sm);font-size:12px;font-family:monospace;white-space:pre-wrap;color:var(--text2);line-height:1.6;">${esc(consolidated.trim())}</pre>
    </div>` : ''}

    ${Object.entries(byCat).sort((a,b)=>(s.category_scores?.[a[0]]||10)-(s.category_scores?.[b[0]]||10)).map(([cat, fixes]) => {
      const catScore = (s.category_scores||{})[cat];
      const unique = [...new Set(fixes.map(f=>f.fix.trim()))];
      return `<div class="card mb">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <span class="badge badge-accent">${CAT[cat]||cat}</span>
            ${catScore !== undefined ? pill(catScore) : ''}
          </div>
          <span style="font-size:11px;color:var(--text3)">${fixes.length} ${t('pr_recs_n')}</span>
        </div>
        ${unique.slice(0,3).map((fix,i) => `<div style="display:flex;gap:10px;align-items:flex-start;margin-bottom:10px;">
          <button class="btn btn-ghost btn-xs" onclick="copyToClipboard('fix-${cat}-${i}')" style="flex-shrink:0;margin-top:2px;">⎘</button>
          <code id="fix-${cat}-${i}" style="display:block;background:var(--bg3);padding:8px 12px;border-radius:6px;font-size:12px;line-height:1.6;flex:1;font-family:monospace;color:var(--text2);">${esc(fix)}</code>
        </div>`).join('')}
        ${fixes.length > 3 ? `<div style="font-size:11px;color:var(--text3);margin-top:4px;">+${fixes.length-3} ${t('pr_more')}</div>` : ''}
      </div>`;
    }).join('')}

    ${systemPromptText ? `<div class="card">
      <div class="card-label">${t('pr_current')}</div>
      <pre style="background:var(--bg3);padding:14px;border-radius:var(--radius-sm);font-size:12px;font-family:monospace;white-space:pre-wrap;color:var(--text3);">${esc(systemPromptText)}</pre>
    </div>` : ''}`;
}
