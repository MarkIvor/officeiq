// Compare page: run selection, radar, native comparison, side-by-side
let _compareRuns = [];

async function loadCompareList() {
  const res = await fetch('/api/results');
  allResults = await res.json();
  const wrap = document.getElementById('compare-list');
  if (!allResults.length) { wrap.innerHTML = `<div class="empty"><div class="icon">◈</div><p>${t('res_no_runs')}</p></div>`; return; }
  wrap.innerHTML = allResults.map((r,i)=>`
    <div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);">
      <input type="checkbox" id="cmp-${i}" value="${r.filename}" style="accent-color:var(--accent);width:15px;height:15px;">
      <label for="cmp-${i}" style="flex:1;cursor:pointer;">
        <div style="font-size:13px;font-weight:500;color:var(--text)">${esc(r.model_name)}</div>
        <div style="font-size:11px;color:var(--text3)">${r.run_at.slice(0,16).replace('T',' ')} · ${r.answered}/${r.total_questions} ${t('msg_questions_n')}</div>
      </label>
      <span style="font-weight:700;font-size:1.1rem;color:${sc(r.overall_score)}">${r.overall_score.toFixed(1)}</span>
    </div>`).join('');
}

async function openCompare() {
  const checked = [...document.querySelectorAll('#compare-list input:checked')].map(c=>c.value);
  if (checked.length < 2) { notify(t('cmp_min2'),'err'); return; }
  const runs = [];
  for (const fn of checked) {
    const res = await fetch(`/api/results/${fn}`);
    const d = await res.json();
    runs.push(d);
  }
  _compareRuns = runs;
  await renderCompareRadar(runs);
  renderCompareNative(runs);
  document.getElementById('compare-result-wrap').scrollIntoView({behavior:'smooth'});
}

async function renderCompareRadar(runs) {
  const datasets = runs.map((d, i) => {
    const color = COLORS[i % COLORS.length];
    return {
      label: d.meta.model_name,
      data: CRIT_KEYS.map(k => d.summary.criteria_scores[k]||0),
      borderColor: color, backgroundColor: color+'18',
      pointBackgroundColor: color, pointRadius: 3, borderWidth: 2,
    };
  });
  document.getElementById('compare-radar-card').style.display = 'block';
  if (compareChart) compareChart.destroy();
  compareChart = new Chart(document.getElementById('compare-radar'), {
    type: 'radar',
    data: { labels: CRIT_KEYS.map(k=>CRIT[k]), datasets },
    options: { responsive:true, maintainAspectRatio:false,
      scales: { r: { min:0, max:10,
        grid:{color:'#e4e8ef'}, angleLines:{color:'#e4e8ef'},
        ticks:{color:'#8892a8',stepSize:2,backdropColor:'transparent'},
        pointLabels:{color:'#4b5672',font:{size:10}} } },
      plugins: { legend:{ labels:{ color:'#4b5672', font:{size:11} } } }
    }
  });
}

function toggleCompareBlock(i) {
  const body = document.getElementById(`compare-body-${i}`);
  const icon = document.getElementById(`compare-toggle-${i}`);
  const isOpen = body.classList.toggle('open');
  if (icon) icon.textContent = isOpen ? '▴' : '▾';
}

function renderCompareNative(runs) {
  const wrap = document.getElementById('compare-result-wrap');
  const summaryCards = runs.map((d, i) => {
    const color = COLORS[i % COLORS.length];
    const s = d.summary; const m = d.meta;
    return `<div class="card" style="border-top:3px solid ${color};text-align:center;">
      <div style="font-size:12px;color:var(--text3);margin-bottom:6px;font-weight:500;">${esc(m.model_name)}</div>
      <div style="font-size:2.4rem;font-weight:800;color:${color}">${s.overall_score.toFixed(2)}</div>
      <div style="font-size:11px;color:var(--text3);">/ 10.00 · ${m.coverage??m.answered}/${m.total_questions}</div>
      <div style="font-size:11px;color:var(--text3);margin-top:4px;">${m.run_at.slice(0,16).replace('T',' ')}</div>
    </div>`;
  }).join('');
  const catBarChart = `<div class="card mb">
    <div class="card-label">${t('res_by_cat')}</div>
    ${CAT_KEYS.map(cat => {
      const bars = runs.map((d, i) => {
        const val = (d.summary.category_scores||{})[cat] || 0;
        const color = COLORS[i % COLORS.length];
        return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px;">
          <span style="font-size:10px;color:${color};font-weight:600;width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(d.meta.model_name.slice(0,14))}</span>
          <div class="cat-bar-wrap" style="flex:1"><div class="cat-bar-fill" style="width:${val*10}%;background:${color}"></div></div>
          <span style="font-size:11px;font-weight:700;color:${color};width:28px;text-align:right;">${val.toFixed(1)}</span>
        </div>`;
      }).join('');
      return `<div style="margin-bottom:14px;">
        <div style="font-size:11px;font-weight:600;color:var(--text2);margin-bottom:6px;">${CAT[cat]}</div>
        ${bars}
      </div>`;
    }).join('')}
  </div>`;
  const modelAccordions = runs.map((d, i) => {
    const color = COLORS[i % COLORS.length];
    const s = d.summary; const m = d.meta;
    const critBars = CRIT_KEYS.map(k => {
      const val = (s.criteria_scores||{})[k] || 0;
      return `<div class="cat-bar-row">
        <span class="cat-bar-label">${CRIT[k]||k}</span>
        <div class="cat-bar-wrap"><div class="cat-bar-fill" style="width:${val*10}%;background:${color}"></div></div>
        <span class="cat-bar-val" style="color:${color}">${val.toFixed(1)}</span>
      </div>`;
    }).join('');
    const topItems = [...(d.items||[])].filter(x=>!x.judge_error&&!x.skipped).sort((a,b)=>b.weighted_total-a.weighted_total).slice(0,3);
    const botItems = [...(d.items||[])].filter(x=>!x.judge_error&&!x.skipped).sort((a,b)=>a.weighted_total-b.weighted_total).slice(0,3);
    const itemRows = (arr, label) => arr.length ? `<div style="font-size:11px;font-weight:600;color:var(--text3);margin:10px 0 6px;text-transform:uppercase;letter-spacing:0.05em;">${label}</div>` +
      arr.map(it=>`<div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:6px;font-size:12px;">
        <span style="color:var(--text3);flex-shrink:0;width:60px;">${it.id}</span>
        <span style="flex:1;color:var(--text2);">${esc(it.prompt.trim().slice(0,70))}…</span>
        ${pill(it.weighted_total)}
        <button class="btn btn-ghost btn-xs" onclick="openSideBySide('${it.id}')">⇌</button>
      </div>`).join('') : '';
    return `<div class="compare-model-block">
      <div class="compare-model-header" onclick="toggleCompareBlock(${i})">
        <div class="compare-model-score" style="color:${color}">${s.overall_score.toFixed(2)}</div>
        <div>
          <div class="compare-model-name">${esc(m.model_name)}</div>
          <div class="compare-model-meta">${m.coverage??m.answered}/${m.total_questions} ${t('cmp_answers_n')} · ${m.run_at.slice(0,10)}</div>
        </div>
        <span id="compare-toggle-${i}" style="color:var(--text3);font-size:16px;margin-left:auto;">▾</span>
      </div>
      <div class="compare-model-body" id="compare-body-${i}">
        <div style="margin-bottom:14px;"><div class="card-label">${t('res_by_crit')}</div>${critBars}</div>
        ${itemRows(topItems, t('cmp_best_answers'))}
        ${itemRows(botItems, t('cmp_worst_answers'))}
      </div>
    </div>`;
  }).join('');
  const gridCols = Math.min(runs.length, 4);
  wrap.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(${gridCols},1fr);gap:14px;margin-bottom:20px;">${summaryCards}</div>
    ${catBarChart}
    <div class="card-label" style="margin-bottom:12px;">${t('cmp_details_lbl')}</div>
    ${modelAccordions}
    <div id="sbs-wrap"></div>`;
}

function openSideBySide(questionId) {
  const wrap = document.getElementById('sbs-wrap');
  if (!wrap || !_compareRuns.length) return;
  const items = _compareRuns.map(run => {
    const item = (run.items||[]).find(i => i.id === questionId);
    return { model: run.meta.model_name, item };
  }).filter(x => x.item);
  if (!items.length) return;
  const prompt = items[0].item.prompt || '';
  wrap.innerHTML = `
    <div class="card" style="margin-top:16px;border-top:3px solid var(--accent);">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
        <div class="card-label" style="margin:0;">${t('cmp_sbs')}: ${questionId}</div>
        <button class="btn btn-ghost btn-xs" onclick="document.getElementById('sbs-wrap').innerHTML=''">✕</button>
      </div>
      <div style="background:var(--bg3);padding:10px 14px;border-radius:var(--radius-sm);margin-bottom:16px;font-size:12px;color:var(--text2);">${esc(prompt.trim())}</div>
      <div style="display:grid;grid-template-columns:repeat(${Math.min(items.length,3)},1fr);gap:14px;">
        ${items.map((x, i) => {
          const color = COLORS[i % COLORS.length];
          const it = x.item;
          return `<div>
            <div style="font-weight:600;font-size:12px;color:${color};margin-bottom:8px;padding-bottom:6px;border-bottom:2px solid ${color};">${esc(x.model)}</div>
            <div style="font-size:11px;margin-bottom:8px;">${pill(it.weighted_total)}</div>
            <div style="font-size:12px;color:var(--text2);line-height:1.6;max-height:300px;overflow-y:auto;background:var(--bg3);padding:10px;border-radius:6px;">${esc((it.response||t('res_no_answer')).slice(0,500))}</div>
            ${it.reasoning?.strengths ? `<div style="font-size:11px;color:var(--green);margin-top:8px;">+ ${esc(it.reasoning.strengths)}</div>` : ''}
            ${it.reasoning?.weaknesses ? `<div style="font-size:11px;color:var(--orange);">− ${esc(it.reasoning.weaknesses)}</div>` : ''}
            ${it.ideal_answer ? `<div style="font-size:11px;color:var(--accent);margin-top:6px;background:var(--accent-light);padding:6px 8px;border-radius:4px;"><b>${t('res_ideal_lbl')}:</b> ${esc(it.ideal_answer)}</div>` : ''}
          </div>`;
        }).join('')}
      </div>
    </div>`;
  wrap.scrollIntoView({behavior:'smooth'});
}
