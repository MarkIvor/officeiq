// Results page: list, detail view, CSV/MD export, certificate
async function loadResults() {
  const res = await fetch('/api/results');
  allResults = await res.json();
  renderResultsList();
  document.getElementById('btn-export-csv').style.display = allResults.length ? '' : 'none';
  return allResults;
}

function modeBadge(mode, lang) {
  const l = (lang || 'ru').toUpperCase();
  const tag = `<span class="mlang-tag">${l}</span>`;
  if (mode === 'quick') return `<span class="badge" style="background:var(--yellow-light);color:var(--yellow);margin-left:6px;">Quick</span>${tag}`;
  if (mode === 'stress') return `<span class="badge" style="background:var(--red-light);color:var(--red);margin-left:6px;">Stress</span>${tag}`;
  return tag;
}

function renderResultsList() {
  const wrap = document.getElementById('results-list-wrap');
  if (!allResults.length) {
    wrap.innerHTML = `<div class="empty"><div class="icon">◈</div><p>${t('res_no_runs')}</p></div>`;
    return;
  }
  wrap.innerHTML = `<div class="card">${allResults.map(r => {
    const skippedBadge = r.skipped?.length ? `<span class="badge" style="background:var(--orange-light);color:var(--orange);margin-left:6px;">⚠ ${r.skipped.length} ${t('run_skipped_n')}</span>` : '';
    const retryBtn = r.skipped?.length
      ? `<button class="btn btn-warn btn-xs" onclick="retrySkipped('${r.filename}',${JSON.stringify(r.skipped)})">${t('res_retry')}</button>`
      : '';
    return `<div class="result-item">
      <div class="result-score" style="color:${sc(r.overall_score)}">${r.overall_score.toFixed(1)}</div>
      <div class="result-info">
        <div class="result-name">${esc(r.model_name)}${modeBadge(r.mode, r.lang)}${skippedBadge}</div>
        <div class="result-meta">${r.answered}/${r.total_questions} ${t('msg_questions_n')} · ${r.run_at.slice(0,16).replace('T',' ')}</div>
      </div>
      <div class="result-actions">
        ${retryBtn}
        <button class="btn btn-secondary btn-sm" onclick="viewResult('${r.filename}')">${t('common_details')}</button>
        <button class="btn btn-ghost btn-sm" onclick="window.open('/api/results/${r.filename.replace('.json','')}/report','_blank')">${t('common_report')}</button>
        <button class="btn btn-ghost btn-xs" onclick="exportMarkdown('${r.filename}')" title="Markdown">${t('res_md')}</button>
        <button class="btn btn-ghost btn-xs" onclick="downloadCertificate('${r.filename}')" title="Certificate">${t('res_cert')}</button>
        <button class="btn btn-danger btn-xs" onclick="deleteResult('${r.filename}')">✕</button>
      </div>
    </div>`;
  }).join('')}</div>`;
}

async function viewResult(filename) {
  switchResultsTab('detail', document.querySelectorAll('#results-tabs .tab')[1]);
  const res = await fetch(`/api/results/${filename}`);
  const data = await res.json();
  renderResultDetail(data);
}

function switchResultsTab(name, el) {
  document.querySelectorAll('#results-tabs .tab').forEach(ta=>ta.classList.remove('active'));
  document.querySelectorAll('#results-list-tab,#results-detail-tab').forEach(ta=>ta.classList.remove('active'));
  el.classList.add('active');
  document.getElementById(`results-${name}-tab`).classList.add('active');
}

async function deleteResult(filename) {
  if (!confirm(t('res_delete_confirm'))) return;
  await fetch(`/api/results/${filename}`, {method:'DELETE'});
  notify(t('msg_deleted'));
  loadResults();
}
// __RESULTS_PART2__
function renderResultDetail(data) {
  const wrap = document.getElementById('results-detail-wrap');
  const s = data.summary; const m = data.meta;
  const isStress = (m.mode || '') === 'stress';
  const radarId = 'radar-' + Date.now();
  const critKeys = CRIT_KEYS;
  const coverage = m.coverage ?? m.answered;
  const skippedList = m.skipped || [];
  const modeBadgeHtml = modeBadge(m.mode, m.lang);

  wrap.innerHTML = `
  <div class="grid-3 mb">
    <div class="card stat-box"><div class="val" style="color:${sc(s.overall_score)}">${s.overall_score.toFixed(2)}</div><div class="lbl">${t('res_overall')}${modeBadgeHtml}</div></div>
    <div class="card stat-box"><div class="val">${coverage}/${m.total_questions}</div><div class="lbl">${t('res_coverage_lbl')} ${skippedList.length ? `<span style="color:var(--orange)">(${skippedList.length} ${t('run_skipped_n')})</span>` : ''}</div></div>
    <div class="card stat-box"><div class="val">${m.run_at.slice(0,10)}</div><div class="lbl">${t('col_date')}</div></div>
  </div>
  ${isStress ? `
  <div class="grid-3 mb">
    <div class="card stat-box"><div class="val" style="color:${sc((s.resilience_avg||0))}">${(s.resilience_avg||0).toFixed(2)}</div><div class="lbl">${t('st_resilience')}</div></div>
    <div class="card stat-box"><div class="val" style="color:var(--green)">${s.held_pct ?? 0}%</div><div class="lbl">${t('st_held')}</div></div>
    <div class="card stat-box"><div class="val" style="color:var(--orange)">${Object.values(s.broke_distribution||{}).reduce((a,b)=>a+b,0)}</div><div class="lbl">${t('st_broke')}</div></div>
  </div>` : ''}
  <div class="grid-2 mb">
    <div class="card">
      <div class="card-label">${t('res_by_cat')}</div>
      ${Object.entries(s.category_scores).sort((a,b)=>b[1]-a[1]).map(([cat,val])=>`
      <div class="cat-bar-row">
        <span class="cat-bar-label">${CAT[cat]||cat}</span>
        <div class="cat-bar-wrap"><div class="cat-bar-fill" style="width:${val*10}%;background:${sc(val)}"></div></div>
        <span class="cat-bar-val" style="color:${sc(val)}">${val.toFixed(1)}</span>
      </div>`).join('')}
    </div>
    <div class="card">
      <div class="card-label">${t('res_by_crit')}</div>
      <div class="chart-container"><canvas id="${radarId}"></canvas></div>
    </div>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>${t('col_id')}</th><th>${t('col_cat')}</th><th>${t('col_diff')}</th><th>${t('col_request')}</th><th>${t('col_score')}</th><th>${t('res_ms')}</th><th></th></tr></thead>
      <tbody>${data.items.map(item => stressItemRow(item).join('')).join('')}
      </tbody>
    </table>
  </div>`;

  new Chart(document.getElementById(radarId), {
    type: 'radar',
    data: {
      labels: critKeys.map(k=>CRIT[k]),
      datasets: [{ label: m.model_name, data: critKeys.map(k=>s.criteria_scores[k]||0),
        borderColor: '#4f6ef7', backgroundColor: 'rgba(79,110,247,0.08)',
        pointBackgroundColor: '#4f6ef7', pointRadius: 3, borderWidth: 2 }]
    },
    options: { responsive:true, maintainAspectRatio:false,
      scales: { r: { min:0, max:10,
        grid:{color:'#e4e8ef'}, angleLines:{color:'#e4e8ef'},
        ticks:{color:'#8892a8',stepSize:2,backdropColor:'transparent'},
        pointLabels:{color:'#4b5672',font:{size:10}} } },
      plugins: { legend:{ display:false } }
    }
  });
}

function stressItemRow(item) {
  const isStress = item.turns !== undefined && item.turn_scores !== undefined;
  const scoreCell = isStress
    ? `${pill(item.weighted_total)} ${item.held ? `<span class="badge" style="background:var(--green-light);color:var(--green)">${t('st_held_badge')}</span>` : `<span class="badge" style="background:var(--red-light);color:var(--red)">${t('st_broke_badge')} ${item.broke_on ?? '—'}</span>`}`
    : pill(item.weighted_total);
  const turnChips = isStress && item.turn_scores
    ? `<div class="scores-chips">${Object.entries(item.turn_scores).map(([k,v])=>`<span class="score-chip" style="color:${sc(v)};border-color:${scBg(v)};background:${scBg(v)}"><b>${k}</b> ${v}</span>`).join('')}</div>` : '';
  const transcript = isStress
    ? `<div style="margin-top:10px;"><div class="detail-section-label">${t('st_transcript')}</div><div class="detail-section-text" style="max-height:300px;overflow-y:auto;">${esc((item.turns||[]).map(m=>`${m.role==='user'?'👤':'🤖'}: ${m.content}`).join('\n\n'))}</div></div>` : '';
  const idealHtml = item.ideal_answer ? `<div style="margin-top:12px;"><div class="detail-section-label" style="color:var(--accent);">${t('res_ideal_lbl')}</div><div class="detail-section-text" style="color:var(--accent);background:var(--accent-light);padding:8px;border-radius:6px;margin-top:4px;">${esc(item.ideal_answer)}</div></div>` : '';
  const fixHtml = item.prompt_fix ? `<div style="margin-top:8px;"><div class="detail-section-label" style="color:var(--green);">${t('res_fix_lbl')}</div><div style="font-size:12px;font-family:monospace;background:var(--green-light);color:var(--green);padding:8px;border-radius:6px;margin-top:4px;">${esc(item.prompt_fix)}</div></div>` : '';
  const scoresChips = item.scores ? `<div class="scores-chips">${Object.entries(item.scores).map(([k,v])=>`<span class="score-chip" style="color:${sc(v)};border-color:${scBg(v)};background:${scBg(v)}"><b>${v}</b> ${CRIT[k]||k}</span>`).join('')}</div>` : '';
  const analysisHtml = item.analysis ? `<div style="font-size:11px;color:var(--text2);margin-top:8px;background:var(--bg3);padding:8px;border-radius:6px;"><b style="color:var(--text3);">${t('res_judge_analysis')}:</b> ${esc(item.analysis)}</div>` : '';
  const attemptsHtml = item.attempts > 1 ? `<div style="font-size:11px;color:var(--yellow);margin-top:4px;">${t('run_retries_n')}: ${item.attempts}</div>` : '';
  const totalLat = (item.turns||[]).reduce((a,m)=>a+(m.latency_ms||0),0);
  const latCell = isStress ? (totalLat||0) : (item.latency_ms||0);
  return [`
    <tr class="expandable" onclick="toggleRow('d-${item.id}')">
      <td style="color:var(--text3);font-size:11px">${item.id}</td>
      <td><span class="badge badge-accent">${CAT[item.category]||item.category}</span></td>
      <td><span class="badge badge-${item.difficulty}">${item.difficulty}</span></td>
      <td style="max-width:280px;color:var(--text)">${esc(item.prompt.trim().slice(0,80))}${item.prompt.length>80?'…':''}</td>
      <td>${scoreCell}</td>
      <td style="color:var(--text3);font-size:12px">${latCell}</td>
      <td style="color:var(--text3);">▾</td>
    </tr>
    <tr id="d-${item.id}" style="display:none;" class="detail-row">
      <td colspan="7">
        <div class="detail-inner">
          <div>
            <div class="detail-section-label">${t('res_request_lbl')}</div>
            <div class="detail-section-text">${esc(item.prompt.trim())}</div>
            ${idealHtml}
            ${fixHtml}
          </div>
          <div>
            <div class="detail-section-label">${t('res_answer_lbl')} ${item.skipped ? `<span style="color:var(--orange);">${t('res_skipped_badge')}</span>` : ''}</div>
            <div class="detail-section-text">${esc((item.response || item.response_error || '').slice(0,600) || t('res_no_answer'))}</div>
            ${scoresChips}
            ${turnChips}
            ${analysisHtml}
            ${item.reasoning?.strengths?`<div style="font-size:11px;color:var(--green);margin-top:6px">+ ${esc(item.reasoning.strengths)}</div>`:''}
            ${item.reasoning?.weaknesses?`<div style="font-size:11px;color:var(--orange)">− ${esc(item.reasoning.weaknesses)}</div>`:''}
            ${attemptsHtml}
          </div>
        </div>
        ${transcript}
      </td>
    </tr>`];
}

function exportCSV() {
  if (!allResults.length) return;
  const header = ['filename','model_name','overall_score','answered','total_questions','run_at',
    ...CAT_KEYS.map(k=>'cat_'+k),
    ...CRIT_KEYS.map(k=>'crit_'+k)];
  const rows = allResults.map(r => [
    r.filename, r.model_name, r.overall_score, r.answered, r.total_questions, r.run_at,
    ...CAT_KEYS.map(k=>(r.category_scores||{})[k]||''),
    ...CRIT_KEYS.map(k=>(r.criteria_scores||{})[k]||''),
  ]);
  const csv = [header, ...rows].map(r=>r.map(v=>'"'+String(v).replace(/"/g,'""')+'"').join(',')).join('\n');
  const blob = new Blob(['\uFEFF'+csv], {type:'text/csv;charset=utf-8;'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = `officeiq-results-${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
}
// __RESULTS_PART3__
async function exportMarkdown(filename) {
  const res = await fetch(`/api/results/${filename}`);
  const data = await res.json();
  const s = data.summary; const m = data.meta;
  let md = `# OfficeIQ Bench — ${m.model_name}\n\n`;
  md += `> ${t('col_date')}: ${m.run_at.slice(0,16).replace('T',' ')} | ${t('lb_col_mode')}: ${m.mode||'full'} | ${t('res_coverage_lbl')}: ${m.coverage??m.answered}/${m.total_questions} | Lang: ${(m.lang||'ru').toUpperCase()}\n\n`;
  md += `## ${t('res_overall')}: **${s.overall_score.toFixed(2)} / 10** — ${levelText(s.overall_score)}\n\n`;
  md += `## ${t('res_by_cat')}\n\n`;
  md += `| ${t('col_cat')} | ${t('col_score')} |\n|---|---|\n`;
  Object.entries(s.category_scores).sort((a,b)=>b[1]-a[1]).forEach(([cat,val]) => {
    md += `| ${CAT[cat]||cat} | ${val.toFixed(2)} |\n`;
  });
  md += `\n## ${t('res_by_crit')}\n\n`;
  md += `| ${t('res_by_crit')} | ${t('col_score')} |\n|---|---|\n`;
  Object.entries(s.criteria_scores).sort((a,b)=>b[1]-a[1]).forEach(([k,v]) => {
    md += `| ${CRIT[k]||k} | ${v.toFixed(2)} |\n`;
  });
  if (s.held_pct !== undefined) {
    md += `\n## ${t('st_resilience')}\n\n${t('st_held')}: **${s.held_pct}%** · ${t('st_resilience')}: **${(s.resilience_avg||0).toFixed(2)}**\n`;
  }
  const fixes = Object.entries(s.prompt_fixes||{});
  if (fixes.length) {
    md += `\n## ${t('res_fix_lbl')}\n\n`;
    fixes.forEach(([cat, arr]) => {
      md += `**${CAT[cat]||cat}:**\n\`\`\`\n${arr[0]}\n\`\`\`\n\n`;
    });
  }
  md += `\n---\n*OfficeIQ Bench · ${new Date().toLocaleDateString()}*\n`;
  const blob = new Blob([md], {type:'text/markdown;charset=utf-8;'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = `officeiq-${m.model_name.replace(/\s+/g,'-')}-${m.run_at.slice(0,10)}.md`;
  a.click();
}

async function downloadCertificate(filename) {
  const res = await fetch(`/api/results/${filename}`);
  const data = await res.json();
  const s = data.summary; const m = data.meta;
  const score = s.overall_score;
  const color = score >= 8 ? '#16a34a' : score >= 6 ? '#d97706' : '#dc2626';
  const catBars = Object.entries(s.category_scores).sort((a,b)=>b[1]-a[1]).map(([cat,val]) => {
    const pct = Math.round(val * 10);
    const c = val>=8?'#16a34a':val>=6?'#d97706':'#dc2626';
    return `<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
      <span style="width:130px;font-size:11px;color:#64748b;">${CAT[cat]||cat}</span>
      <div style="flex:1;background:#f1f5f9;border-radius:999px;height:6px;"><div style="width:${pct}%;height:6px;border-radius:999px;background:${c};"></div></div>
      <span style="font-size:11px;font-weight:700;color:${c};width:28px;">${val.toFixed(1)}</span>
    </div>`;
  }).join('');
  const html = `<!DOCTYPE html><html lang="${LANG}"><head><meta charset="UTF-8">
<title>OfficeIQ Bench — ${m.model_name}</title>
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8f9fb;margin:0;padding:40px;display:flex;justify-content:center;}
  .cert{background:#fff;border:2px solid #e4e8ef;border-radius:16px;padding:48px;max-width:700px;width:100%;box-shadow:0 4px 24px rgba(0,0,0,0.08);}
  .header{text-align:center;margin-bottom:32px;}
  .badge{display:inline-block;background:${color}18;color:${color};padding:6px 16px;border-radius:999px;font-size:13px;font-weight:600;margin-bottom:12px;}
  h1{font-size:14px;color:#8892a8;font-weight:500;margin-bottom:8px;}
  .model{font-size:28px;font-weight:800;color:#0f1623;margin-bottom:8px;}
  .score-big{font-size:72px;font-weight:900;color:${color};line-height:1;}
  .level{font-size:18px;font-weight:600;color:${color};margin-top:4px;}
  .divider{border:none;border-top:1px solid #e4e8ef;margin:28px 0;}
  .meta{display:flex;justify-content:center;gap:32px;margin-bottom:24px;font-size:12px;color:#8892a8;}
  .meta b{color:#4b5672;}
  .footer{text-align:center;font-size:11px;color:#8892a8;margin-top:32px;}
</style></head><body><div class="cert">
  <div class="header">
    <div class="badge">⚡ OfficeIQ Bench</div>
    <h1>AI ASSISTANT CERTIFICATION</h1>
    <div class="model">${m.model_name}</div>
    <div class="score-big">${score.toFixed(2)}</div>
    <div class="level">${levelText(score)}</div>
  </div>
  <div class="meta">
    <div>${t('col_date')} <b>${m.run_at.slice(0,10)}</b></div>
    <div>${t('res_coverage_lbl')} <b>${m.coverage??m.answered}/${m.total_questions}</b></div>
    <div>${t('lb_col_mode')} <b>${m.mode||'full'}</b></div>
    <div>Lang <b>${(m.lang||'ru').toUpperCase()}</b></div>
  </div>
  <hr class="divider">
  <div style="margin-bottom:24px;">${catBars}</div>
  <div class="footer">OfficeIQ Bench · github.com/MarkIvor/officeiq · ${new Date().getFullYear()}</div>
</div></body></html>`;
  const blob = new Blob([html], {type:'text/html;charset=utf-8;'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = `cert-${m.model_name.replace(/\s+/g,'-')}.html`;
  a.click();
}
