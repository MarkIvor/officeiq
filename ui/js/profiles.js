// Company profiles: reweight the score for a use case
const PROFILE_WEIGHTS = {
  hr:     { hr_team:2.0, emotional:2.0, ethics:1.8, stress:1.5, communication:1.2, meetings:1.0, documents:0.8, analytics:0.8, negotiations:0.8, adversarial:1.5 },
  sales:  { negotiations:2.0, communication:2.0, stress:1.5, analytics:1.3, meetings:1.0, hr_team:0.8, documents:0.8, ethics:1.3, emotional:1.0, adversarial:1.5 },
  pm:     { meetings:2.0, analytics:2.0, stress:1.8, documents:1.5, communication:1.3, hr_team:1.0, negotiations:1.0, ethics:1.0, emotional:0.8, adversarial:1.2 },
  custom: null,
};

let selectedProfile = null;

function selectProfile(name) {
  document.querySelectorAll('.profile-card').forEach(c => c.classList.remove('selected'));
  document.getElementById(`profile-${name}`)?.classList.add('selected');
  selectedProfile = name;

  const customCard = document.getElementById('custom-weights-card');
  if (name === 'custom') {
    customCard.style.display = 'block';
    const wrap = document.getElementById('custom-weights-inputs');
    wrap.innerHTML = CAT_KEYS.map(cat => `
      <div>
        <label class="form-label">${CAT[cat]} <span class="opt">${t('pf_w_norm')}</span></label>
        <input class="form-input" type="number" id="cw-${cat}" value="1.0" min="0.1" max="5" step="0.1">
      </div>`).join('');
  } else {
    customCard.style.display = 'none';
  }
  renderProfileResults();
}

function getProfileWeights() {
  if (!selectedProfile) return null;
  if (selectedProfile !== 'custom') return PROFILE_WEIGHTS[selectedProfile];
  const w = {};
  CAT_KEYS.forEach(cat => {
    w[cat] = parseFloat(document.getElementById(`cw-${cat}`)?.value) || 1.0;
  });
  return w;
}

function calcProfileScore(result, weights) {
  const cats = result.category_scores || {};
  let total = 0, wsum = 0;
  Object.entries(weights).forEach(([cat, w]) => {
    const v = cats[cat] || 0;
    total += v * w; wsum += w;
  });
  return wsum > 0 ? round2(total / wsum) : 0;
}

function round2(n) { return Math.round(n * 100) / 100; }

function renderProfileResults() {
  const wrap = document.getElementById('profiles-result-wrap');
  const weights = getProfileWeights();
  if (!weights || !allResults.length) { if(wrap) wrap.innerHTML=''; return; }

  const names = {hr: t('pf_hr'), sales: t('pf_sales'), pm: t('pf_pm'), custom: t('pf_custom_name')};
  const profileName = names[selectedProfile] || selectedProfile;

  const scored = allResults.map(r => ({
    ...r,
    profile_score: calcProfileScore(r, weights),
  })).sort((a,b) => b.profile_score - a.profile_score);

  wrap.innerHTML = `<div class="card">
    <div class="card-label">${t('pf_rating')}: ${profileName}</div>
    <table>
      <thead><tr><th>#</th><th>${t('lb_col_model')}</th><th>${t('pf_base')}</th><th style="color:var(--accent)">${t('pf_profile')}</th><th>${t('pf_diff')}</th><th>${t('col_date')}</th></tr></thead>
      <tbody>${scored.map((r, i) => {
        const delta = round2(r.profile_score - r.overall_score);
        const dCls = delta >= 0 ? 'ab-delta-pos' : 'ab-delta-neg';
        return `<tr>
          <td style="color:var(--text3);text-align:center;">${i+1}</td>
          <td style="font-weight:600;">${esc(r.model_name)}</td>
          <td>${pill(r.overall_score)}</td>
          <td><span class="score-pill" style="background:var(--accent-light);color:var(--accent);font-weight:800;">${r.profile_score.toFixed(2)}</span></td>
          <td class="${dCls}">${delta >= 0?'+':''}${delta.toFixed(2)}</td>
          <td style="font-size:11px;color:var(--text3);">${r.run_at.slice(0,10)}</td>
        </tr>`;
      }).join('')}
      </tbody>
    </table>
  </div>`;
}
