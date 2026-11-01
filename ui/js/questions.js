// Questions page
async function loadQuestions() {
  if (!allQuestions.length) {
    const [statsRes, qRes] = await Promise.all([
      fetch('/api/questions/stats'), fetch('/api/questions/all')
    ]);
    const stats = await statsRes.json();
    const qData = await qRes.json();
    allQuestions = qData.questions;
    document.getElementById('q-total').textContent = stats.total;
    document.getElementById('q-easy').textContent = stats.difficulties.easy||0;
    document.getElementById('q-medium').textContent = stats.difficulties.medium||0;
    document.getElementById('q-hard').textContent = stats.difficulties.hard||0;
  }
  filterQuestions();
}

function filterQuestions() {
  const cf = document.getElementById('q-filter-cat').value;
  const df = document.getElementById('q-filter-diff').value;
  const filtered = allQuestions.filter(q => (!cf||q.category===cf) && (!df||q.difficulty===df));
  const tbody = document.getElementById('q-table-body');
  tbody.innerHTML = filtered.map(q => `
    <tr class="expandable" onclick="toggleRow('qd-${q.id}')">
      <td style="color:var(--text3);font-size:11px;white-space:nowrap">${q.id}</td>
      <td><span class="badge badge-accent">${CAT[q.category]||q.category}</span></td>
      <td><span class="badge badge-${q.difficulty}">${q.difficulty}</span></td>
      <td style="color:var(--text)">${esc(q.prompt.trim().slice(0,90))}${q.prompt.length>90?'…':''}</td>
      <td style="color:var(--text3)">▾</td>
    </tr>
    <tr id="qd-${q.id}" style="display:none;" class="detail-row">
      <td colspan="5">
        <div style="padding:16px;">
          <div class="detail-section-label">${t('res_request_lbl')}</div>
          <div class="detail-section-text">${esc(q.prompt.trim())}</div>
        </div>
      </td>
    </tr>`).join('');
}
