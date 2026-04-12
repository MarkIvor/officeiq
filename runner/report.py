from pathlib import Path
import json


CATEGORY_LABELS = {
    "communication": "Коммуникация",
    "meetings": "Встречи",
    "documents": "Документы",
    "analytics": "Аналитика",
    "hr_team": "HR и команда",
    "negotiations": "Переговоры",
    "stress": "Стресс",
    "ethics": "Этика",
    "emotional": "Эмоции",
    "adversarial": "Adversarial",
}

CRITERIA_LABELS = {
    "accuracy": "Точность",
    "completeness": "Полнота",
    "instruction_following": "Следование инструкции",
    "practicality": "Практичность",
    "tone_style": "Тон и стиль",
    "structure": "Структура",
    "conciseness": "Краткость",
    "safety": "Безопасность",
    "ethical_soundness": "Этика",
    "autonomy": "Самостоятельность",
}

DIFFICULTY_COLORS = {
    "easy": "#16a34a",
    "medium": "#d97706",
    "hard": "#dc2626",
}

MODEL_COLORS = [
    "#4f6ef7", "#e84393", "#0ea5e9", "#f97316", "#8b5cf6", "#10b981"
]


def score_color(score: float) -> str:
    if score >= 8:
        return "#16a34a"
    if score >= 6:
        return "#d97706"
    if score >= 4:
        return "#ea580c"
    return "#dc2626"


def score_bg(score: float) -> str:
    if score >= 8:
        return "#dcfce7"
    if score >= 6:
        return "#fef3c7"
    if score >= 4:
        return "#ffedd5"
    return "#fee2e2"


def generate_report(runs: list[dict], output_path: Path):
    model_names = [r["meta"]["model_name"] for r in runs]
    is_compare = len(runs) > 1

    all_categories = list(CATEGORY_LABELS.keys())
    all_criteria = list(CRITERIA_LABELS.keys())

    radar_datasets = []
    for i, run in enumerate(runs):
        color = MODEL_COLORS[i % len(MODEL_COLORS)]
        radar_datasets.append({
            "label": run["meta"]["model_name"],
            "data": [run["summary"]["criteria_scores"].get(c, 0) for c in all_criteria],
            "color": color,
        })

    bar_datasets = []
    for i, run in enumerate(runs):
        color = MODEL_COLORS[i % len(MODEL_COLORS)]
        bar_datasets.append({
            "label": run["meta"]["model_name"],
            "data": [run["summary"]["category_scores"].get(c, 0) for c in all_categories],
            "color": color,
        })

    items_html = _build_items_table(runs)
    summary_cards = _build_summary_cards(runs)

    radar_data_json = json.dumps(radar_datasets, ensure_ascii=False)
    bar_data_json = json.dumps(bar_datasets, ensure_ascii=False)
    criteria_labels_json = json.dumps([CRITERIA_LABELS[c] for c in all_criteria], ensure_ascii=False)
    category_labels_json = json.dumps([CATEGORY_LABELS.get(c, c) for c in all_categories], ensure_ascii=False)

    title = "Сравнение моделей" if is_compare else f"Отчёт: {model_names[0]}"

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Skald Bench — {title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', sans-serif; background: #f8f9fb; color: #0f1623; line-height: 1.6; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
  h1 {{ font-size: 1.6rem; font-weight: 700; color: #0f1623; margin-bottom: 4px; }}
  .subtitle {{ color: #8892a8; font-size: 0.88rem; margin-bottom: 28px; }}
  h2 {{ font-size: 0.95rem; font-weight: 600; color: #4b5672; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 0.06em; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
  .grid-auto {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 20px; }}
  .card {{ background: #ffffff; border-radius: 10px; padding: 20px; border: 1px solid #e4e8ef; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
  .card-chart {{ background: #ffffff; border-radius: 10px; padding: 20px; border: 1px solid #e4e8ef; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
  .score-card {{ text-align: center; }}
  .score-card .model-name {{ font-size: 0.82rem; color: #8892a8; margin-bottom: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500; }}
  .score-card .big-score {{ font-size: 2.8rem; font-weight: 800; line-height: 1; }}
  .score-card .out-of {{ font-size: 0.9rem; color: #8892a8; }}
  .score-card .meta {{ font-size: 0.72rem; color: #8892a8; margin-top: 8px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ background: #f8f9fb; color: #8892a8; font-weight: 600; padding: 10px 14px; text-align: left; position: sticky; top: 0; z-index: 1; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #e4e8ef; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #f1f3f7; vertical-align: top; color: #4b5672; }}
  tr:hover td {{ background: #f8f9fb; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.70rem; font-weight: 600; }}
  .score-pill {{ display: inline-block; padding: 3px 9px; border-radius: 6px; font-weight: 700; font-size: 0.84rem; min-width: 42px; text-align: center; }}
  .detail-btn {{ background: #f1f3f7; border: 1px solid #e4e8ef; color: #4b5672; padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 0.72rem; }}
  .detail-btn:hover {{ background: #e4e8ef; color: #0f1623; }}
  .detail-row td {{ background: #f8f9fb; padding: 16px; }}
  .detail-inner {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  .detail-section h4 {{ font-size: 0.70rem; color: #8892a8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; font-weight: 600; }}
  .detail-section p {{ font-size: 0.84rem; color: #4b5672; white-space: pre-wrap; line-height: 1.6; }}
  .criteria-mini {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }}
  .crit-chip {{ background: #f1f3f7; border: 1px solid #e4e8ef; border-radius: 4px; padding: 3px 7px; font-size: 0.70rem; color: #4b5672; }}
  .crit-chip span {{ font-weight: 700; }}
  .table-wrap {{ overflow-x: auto; background: #ffffff; border-radius: 10px; border: 1px solid #e4e8ef; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
  .run-at {{ color: #8892a8; font-size: 0.75rem; }}
  canvas {{ max-height: 300px; }}
  @media (max-width: 768px) {{ .grid-2 {{ grid-template-columns: 1fr; }} .detail-inner {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="container">
  <h1>⚡ Skald Bench</h1>
  <p class="subtitle">{title} · Офисные и управленческие задачи · 100 вопросов · 10 критериев</p>

  <div class="grid-auto">
    {summary_cards}
  </div>

  <div class="grid-2">
    <div class="card-chart">
      <h2>Критерии оценки</h2>
      <canvas id="radarChart"></canvas>
    </div>
    <div class="card-chart">
      <h2>Категории вопросов</h2>
      <canvas id="barChart"></canvas>
    </div>
  </div>

  <div class="table-wrap">
    <h2 style="padding: 16px 20px 0; margin-bottom: 0;">Детальные результаты</h2>
    {items_html}
  </div>
</div>

<script>
const radarDatasets = {radar_data_json};
const barDatasets = {bar_data_json};
const criteriaLabels = {criteria_labels_json};
const categoryLabels = {category_labels_json};

const gridColor = 'rgba(228,232,239,0.8)';
const tickColor = '#8892a8';

new Chart(document.getElementById('radarChart'), {{
  type: 'radar',
  data: {{
    labels: criteriaLabels,
    datasets: radarDatasets.map(d => ({{
      label: d.label,
      data: d.data,
      borderColor: d.color,
      backgroundColor: d.color + '18',
      pointBackgroundColor: d.color,
      pointRadius: 3,
      borderWidth: 2,
    }}))
  }},
  options: {{
    responsive: true,
    scales: {{
      r: {{
        min: 0, max: 10,
        grid: {{ color: gridColor }},
        angleLines: {{ color: gridColor }},
        ticks: {{ color: tickColor, stepSize: 2, backdropColor: 'transparent' }},
        pointLabels: {{ color: '#4b5672', font: {{ size: 10 }} }}
      }}
    }},
    plugins: {{ legend: {{ labels: {{ color: '#4b5672' }} }} }}
  }}
}});

new Chart(document.getElementById('barChart'), {{
  type: 'bar',
  data: {{
    labels: categoryLabels,
    datasets: barDatasets.map(d => ({{
      label: d.label,
      data: d.data,
      backgroundColor: d.color + 'cc',
      borderColor: d.color,
      borderWidth: 1,
      borderRadius: 4,
    }}))
  }},
  options: {{
    responsive: true,
    scales: {{
      x: {{ ticks: {{ color: tickColor }}, grid: {{ color: gridColor }} }},
      y: {{ min: 0, max: 10, ticks: {{ color: tickColor }}, grid: {{ color: gridColor }} }}
    }},
    plugins: {{ legend: {{ labels: {{ color: '#4b5672' }} }} }}
  }}
}});

function toggleDetail(id) {{
  const row = document.getElementById('detail-' + id);
  row.style.display = row.style.display === 'none' ? 'table-row' : 'none';
}}
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def _build_summary_cards(runs: list[dict]) -> str:
    cards = []
    for i, run in enumerate(runs):
        color = MODEL_COLORS[i % len(MODEL_COLORS)]
        score = run["summary"]["overall_score"]
        meta = run["meta"]
        cards.append(f"""
<div class="card score-card">
  <div class="model-name" title="{meta['model_name']}">{meta['model_name']}</div>
  <div class="big-score" style="color:{color}">{score:.2f}</div>
  <div class="out-of">/ 10.00</div>
  <div class="meta">
    {meta['answered']}/{meta['total_questions']} ответов<br>
    <span class="run-at">{meta['run_at'][:16].replace('T', ' ')}</span>
  </div>
</div>""")
    return "\n".join(cards)


def _build_items_table(runs: list[dict]) -> str:
    is_compare = len(runs) > 1
    primary = runs[0]
    items = primary["items"]

    score_headers = ""
    if is_compare:
        for run in runs:
            score_headers += f'<th>Балл<br><small style="color:#8892a8">{run["meta"]["model_name"][:15]}</small></th>'
    else:
        score_headers = '<th>Балл</th>'

    rows = []
    for item in items:
        diff_color = DIFFICULTY_COLORS.get(item["difficulty"], "#8892a8")
        diff_bg = {"easy": "#dcfce7", "medium": "#fef3c7", "hard": "#fee2e2"}.get(item["difficulty"], "#f1f3f7")
        cat_label = CATEGORY_LABELS.get(item["category"], item["category"])

        score_cells = ""
        if is_compare:
            for run in runs:
                run_item = next((i for i in run["items"] if i["id"] == item["id"]), None)
                s = run_item["weighted_total"] if run_item else 0.0
                sc = score_color(s)
                sb = score_bg(s)
                score_cells += f'<td><span class="score-pill" style="background:{sb};color:{sc}">{s:.1f}</span></td>'
        else:
            s = item["weighted_total"]
            sc = score_color(s)
            sb = score_bg(s)
            score_cells = f'<td><span class="score-pill" style="background:{sb};color:{sc}">{s:.1f}</span></td>'

        criteria_chips = ""
        if item.get("scores"):
            for crit, val in item["scores"].items():
                cc = score_color(val)
                cb = score_bg(val)
                short = CRITERIA_LABELS.get(crit, crit)[:4]
                criteria_chips += f'<span class="crit-chip" style="color:{cc};background:{cb};border-color:{cb}"><span>{val}</span> {short}</span>'

        safe_id = item["id"].replace("_", "-")
        prompt_preview = item["prompt"].strip().replace("\n", " ")[:100]
        prompt_full = item["prompt"].strip()

        row = f"""<tr>
  <td style="color:#8892a8;font-size:0.72rem;white-space:nowrap">{item['id']}</td>
  <td><span class="badge" style="background:{diff_bg};color:{diff_color}">{item['difficulty']}</span></td>
  <td style="color:#4b5672"><span class="badge" style="background:#eef0fe;color:#4f6ef7">{cat_label}</span></td>
  <td style="max-width:320px;color:#0f1623">{prompt_preview}{'…' if len(item['prompt'].strip()) > 100 else ''}</td>
  {score_cells}
  <td><button class="detail-btn" onclick="toggleDetail('{safe_id}')">детали</button></td>
</tr>
<tr id="detail-{safe_id}" style="display:none">
  <td colspan="99">
    <div class="detail-inner">
      <div class="detail-section">
        <h4>Запрос</h4>
        <p>{prompt_full}</p>
      </div>
      <div class="detail-section">
        <h4>Ответ модели</h4>
        <p>{(item.get('response') or item.get('response_error', 'нет ответа'))[:800]}</p>
        {'<div class="criteria-mini">' + criteria_chips + '</div>' if criteria_chips else ''}
        {_reasoning_block(item.get('reasoning', {}))}
      </div>
    </div>
  </td>
</tr>"""
        rows.append(row)

    return f"""<table>
<thead>
  <tr>
    <th>ID</th>
    <th>Сложность</th>
    <th>Категория</th>
    <th>Запрос</th>
    {score_headers}
    <th></th>
  </tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>"""


def _reasoning_block(reasoning: dict) -> str:
    if not reasoning:
        return ""
    parts = []
    if reasoning.get("strengths"):
        parts.append(f'<p style="color:#16a34a;font-size:0.76rem;margin-top:6px">+ {reasoning["strengths"]}</p>')
    if reasoning.get("weaknesses"):
        parts.append(f'<p style="color:#ea580c;font-size:0.76rem">− {reasoning["weaknesses"]}</p>')
    if reasoning.get("notable"):
        parts.append(f'<p style="color:#8892a8;font-size:0.76rem">→ {reasoning["notable"]}</p>')
    return "\n".join(parts)
