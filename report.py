"""HTML report generator — produces a self-contained dark-themed Gantt chart."""

import json
from datetime import date, timedelta

SCHEME_COLORS = [
    "#4A9FD9",  # blue
    "#9C27B0",  # purple
    "#4CAF50",  # green
    "#e07a2f",  # orange
    "#F44336",  # red
    "#00BCD4",  # teal
    "#E91E63",  # pink
    "#795548",  # brown
]


def working_days_to_date(start: date, offset: int) -> date:
    """Convert a working-day offset from start to a calendar date (skips weekends)."""
    if offset <= 0:
        return start
    d = start
    added = 0
    while added < offset:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def _fmt(d: date) -> str:
    return f"{d.day} {d.strftime('%b %Y')}"


def generate_report(project_data: dict, result: dict) -> str:
    start_str = project_data["project"].get("start_date", date.today().isoformat())
    start_date = date.fromisoformat(start_str)
    project_name = project_data["project"]["name"]
    makespan = result["makespan"]
    end_date = working_days_to_date(start_date, makespan)

    # Scheme → color
    schemes = list(dict.fromkeys(t["scheme"] for t in result["tasks"]))
    scheme_colors = {s: SCHEME_COLORS[i % len(SCHEME_COLORS)] for i, s in enumerate(schemes)}

    # Annotate tasks with calendar dates
    tasks_out = []
    for task in result["tasks"]:
        t = dict(task)
        t["start_date"] = _fmt(working_days_to_date(start_date, task["start"]))
        t["end_date"] = _fmt(working_days_to_date(start_date, task["end"]))
        t["color"] = scheme_colors.get(task["scheme"], "#888")
        tasks_out.append(t)

    # People in order of earliest task start
    people = list(dict.fromkeys(t["assigned_to"] for t in tasks_out if t["assigned_to"]))

    # Utilization per person
    capacity_map = {p["name"]: p.get("capacity", 1.0) for p in project_data["team"]}
    utilization = {}
    for person in people:
        busy = sum(t["duration"] for t in tasks_out if t["assigned_to"] == person)
        utilization[person] = {
            "days":     busy,
            "pct":      round(busy / makespan * 100) if makespan > 0 else 0,
            "capacity": capacity_map.get(person, 1.0),
        }

    # X-axis labels every 5 working days
    week_labels = [
        {"offset": d, "label": f"{working_days_to_date(start_date, d).day} {working_days_to_date(start_date, d).strftime('%b')}"}
        for d in range(0, makespan + 1, 5)
    ]

    data = {
        "project": {
            "name": project_name,
            "start_date": _fmt(start_date),
            "end_date": _fmt(end_date),
            "makespan": makespan,
            "status": result["status"],
        },
        "people": people,
        "tasks": tasks_out,
        "scheme_colors": scheme_colors,
        "utilization": utilization,
        "week_labels": week_labels,
    }

    # Replace </ with <\/ to prevent HTML parser from closing the script tag
    data_json = json.dumps(data, indent=2, ensure_ascii=False).replace("</", "<\\/")

    return _HTML_TEMPLATE.replace("__DATA__", data_json)


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Resource Plan</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scrollbar-gutter: stable; }

:root {
  --bg:       #141414;
  --surface:  #1c1c1c;
  --surface2: #222;
  --border:   #2a2a2a;
  --text:     #e0e0e0;
  --muted:    #666;
  --accent:   #e07a2f;
  --hdr:      52px;
}

body {
  font-family: 'Inter', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
}

/* ── Header ── */
.hdr {
  height: var(--hdr);
  background: var(--surface);
  border-bottom: 2px solid var(--accent);
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 10px;
  position: sticky;
  top: 0;
  z-index: 100;
}
.hdr-icon {
  width: 26px; height: 26px;
  background: var(--accent);
  border-radius: 5px;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 800; color: #fff;
  flex-shrink: 0;
}
.hdr-app { font-size: 11px; font-weight: 700; color: var(--accent); text-transform: uppercase; letter-spacing: .08em; white-space: nowrap; }
.hdr-sep { width: 1px; height: 18px; background: var(--border); }
.hdr-name { font-size: 14px; font-weight: 500; }
.hdr-badge {
  margin-left: auto;
  font-size: 10px; font-weight: 600;
  color: #4CAF50;
  background: rgba(76,175,80,.12);
  border: 1px solid rgba(76,175,80,.3);
  padding: 2px 8px; border-radius: 10px;
  text-transform: uppercase; letter-spacing: .06em;
}

/* ── Content ── */
.content { padding: 24px; max-width: 1600px; margin: 0 auto; }

/* ── Stat cards ── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
  margin-bottom: 28px;
}
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
}
.stat-value { font-size: 22px; font-weight: 700; color: var(--text); margin-bottom: 3px; }
.stat-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .07em; }

/* ── Section ── */
.section { margin-bottom: 32px; }
.section-title {
  font-size: 11px; font-weight: 600;
  color: var(--muted);
  text-transform: uppercase; letter-spacing: .08em;
  margin-bottom: 10px;
}

/* ── Gantt wrap ── */
.gantt-wrap {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow-x: auto;
  padding: 0;
}
#gantt-svg-container svg { display: block; }

/* ── Legend ── */
.legend { display: flex; flex-wrap: wrap; gap: 12px; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.legend-swatch { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }

/* ── Table ── */
.tbl-wrap {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th {
  background: var(--surface2);
  color: var(--muted);
  font-weight: 600; font-size: 10px;
  text-transform: uppercase; letter-spacing: .07em;
  padding: 10px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
tbody td {
  padding: 9px 14px;
  border-bottom: 1px solid #1e1e1e;
  color: var(--text);
}
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover td { background: var(--surface2); }

.badge {
  display: inline-block;
  padding: 2px 8px; border-radius: 10px;
  font-size: 11px; font-weight: 500;
}
.type-tag {
  font-size: 10px; font-weight: 600;
  text-transform: uppercase; letter-spacing: .06em;
  color: var(--muted);
}

/* ── Tooltip ── */
.tip {
  position: fixed;
  background: #0d0d0d;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 12px 14px;
  font-size: 12px;
  pointer-events: none;
  z-index: 9999;
  min-width: 210px;
  display: none;
  box-shadow: 0 6px 28px rgba(0,0,0,.7);
}
.tt-name { font-weight: 600; font-size: 13px; margin-bottom: 8px; }
.tt-row { display: flex; justify-content: space-between; gap: 20px; padding: 2px 0; color: var(--muted); }
.tt-row span:last-child { color: var(--text); }
</style>
</head>
<body>

<script>const DATA = __DATA__;</script>

<header class="hdr">
  <div class="hdr-icon">R</div>
  <span class="hdr-app">Resource Planner</span>
  <div class="hdr-sep"></div>
  <span class="hdr-name" id="hdr-name"></span>
  <span class="hdr-badge" id="hdr-badge"></span>
</header>

<div class="content">
  <div class="stats-grid" id="stats-grid"></div>

  <div class="section">
    <div class="section-title">Gantt Chart</div>
    <div class="gantt-wrap"><div id="gantt-svg-container"></div></div>
  </div>

  <div class="section">
    <div class="section-title">Schemes</div>
    <div class="legend" id="legend"></div>
  </div>

  <div class="section">
    <div class="section-title">All Tasks</div>
    <div class="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th>Task</th><th>Scheme</th><th>Type</th>
            <th>Assigned To</th><th>Start</th><th>End</th><th style="text-align:right">Days</th>
          </tr>
        </thead>
        <tbody id="tasks-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<div class="tip" id="tip"></div>

<script>
document.addEventListener('DOMContentLoaded', () => {
  const { project, people, tasks, scheme_colors, utilization, week_labels } = DATA;

  document.title = project.name + ' — Resource Plan';
  document.getElementById('hdr-name').textContent = project.name;
  const badge = document.getElementById('hdr-badge');
  badge.textContent = project.status;
  if (project.status !== 'OPTIMAL') { badge.style.color = '#FF9800'; badge.style.borderColor = 'rgba(255,152,0,.3)'; badge.style.background = 'rgba(255,152,0,.1)'; }

  // Stats
  const sg = document.getElementById('stats-grid');
  [
    [project.makespan + ' days', 'Makespan'],
    [project.start_date,  'Start'],
    [project.end_date,    'End'],
    [Object.keys(scheme_colors).length, 'Schemes'],
    [people.length, 'Team members'],
    [tasks.length,  'Tasks'],
  ].forEach(([v, l]) => {
    sg.insertAdjacentHTML('beforeend',
      `<div class="stat-card"><div class="stat-value">${v}</div><div class="stat-label">${l}</div></div>`);
  });

  // Legend
  const leg = document.getElementById('legend');
  Object.entries(scheme_colors).forEach(([scheme, color]) => {
    leg.insertAdjacentHTML('beforeend',
      `<div class="legend-item"><div class="legend-swatch" style="background:${color}"></div><span>${scheme}</span></div>`);
  });

  // Tasks table
  const tbody = document.getElementById('tasks-tbody');
  tasks.forEach(t => {
    const c = scheme_colors[t.scheme] || '#888';
    tbody.insertAdjacentHTML('beforeend', `<tr>
      <td>${t.name}</td>
      <td><span class="badge" style="background:${c}18;color:${c};border:1px solid ${c}40">${t.scheme}</span></td>
      <td><span class="type-tag">${t.type}</span></td>
      <td>${t.assigned_to || '—'}</td>
      <td style="font-variant-numeric:tabular-nums;white-space:nowrap">${t.start_date}</td>
      <td style="font-variant-numeric:tabular-nums;white-space:nowrap">${t.end_date}</td>
      <td style="text-align:right;font-variant-numeric:tabular-nums">${t.duration}</td>
    </tr>`);
  });

  renderGantt();
});

function renderGantt() {
  const { project, people, tasks, scheme_colors, utilization, week_labels } = DATA;

  const LABEL_W = 160;
  const DAY_W   = Math.max(10, Math.min(28, 1100 / project.makespan));
  const ROW_H   = 52;
  const HDR_H   = 52;
  const ROW_PAD = 10;
  const TASK_H  = ROW_H - ROW_PAD * 2;

  const svgW = LABEL_W + project.makespan * DAY_W;
  const svgH = HDR_H + people.length * ROW_H + 1;

  const NS = 'http://www.w3.org/2000/svg';
  const mk = (tag, attrs) => {
    const e = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([k, v]) => e.setAttribute(k, v));
    return e;
  };
  const txt = (s, attrs) => { const e = mk('text', attrs); e.textContent = s; return e; };

  const svg = mk('svg', { width: svgW, height: svgH, xmlns: NS });
  const defs = mk('defs');
  svg.appendChild(defs);

  // Canvas background
  svg.appendChild(mk('rect', { x: 0, y: 0, width: svgW, height: svgH, fill: '#141414' }));

  // Full-height week separators
  week_labels.forEach(wl => {
    const x = LABEL_W + wl.offset * DAY_W;
    svg.appendChild(mk('line', { x1: x, y1: 0, x2: x, y2: svgH, stroke: '#222', 'stroke-width': 1 }));
  });

  // Header band
  svg.appendChild(mk('rect', { x: 0, y: 0, width: svgW, height: HDR_H, fill: '#1a1a1a' }));
  svg.appendChild(mk('line', { x1: 0, y1: HDR_H, x2: svgW, y2: HDR_H, stroke: '#2a2a2a', 'stroke-width': 1 }));

  // Date labels
  week_labels.forEach(wl => {
    const x = LABEL_W + wl.offset * DAY_W + 4;
    svg.appendChild(txt(wl.label, { x, y: HDR_H / 2 + 4, fill: '#555', 'font-size': 11, 'font-family': 'Inter, sans-serif' }));
  });

  // Label column separator
  svg.appendChild(mk('line', { x1: LABEL_W, y1: 0, x2: LABEL_W, y2: svgH, stroke: '#2a2a2a', 'stroke-width': 1 }));

  // ── Rows ──
  people.forEach((person, i) => {
    const rowY  = HDR_H + i * ROW_H;
    const rowBg = i % 2 === 0 ? '#161616' : '#191919';

    svg.appendChild(mk('rect', { x: 0, y: rowY, width: svgW, height: ROW_H, fill: rowBg }));
    svg.appendChild(mk('line', { x1: 0, y1: rowY + ROW_H, x2: svgW, y2: rowY + ROW_H, stroke: '#202020', 'stroke-width': 1 }));

    // Person label
    svg.appendChild(txt(person, {
      x: 12, y: rowY + ROW_H / 2 + 4,
      fill: '#c0c0c0', 'font-size': 12, 'font-weight': 500, 'font-family': 'Inter, sans-serif'
    }));

    // Utilization %
    const u = utilization[person] || { pct: 0 };
    svg.appendChild(txt(u.pct + '%', {
      x: LABEL_W - 8, y: rowY + ROW_H / 2 + 4,
      fill: u.pct >= 90 ? '#e07a2f' : '#3a3a3a',
      'font-size': 10, 'text-anchor': 'end', 'font-family': 'Inter, sans-serif'
    }));

    // ── Tasks for this person ──
    tasks.filter(t => t.assigned_to === person).forEach(task => {
      const tx = LABEL_W + task.start * DAY_W;
      const tw = Math.max(task.duration * DAY_W - 2, 4);
      const ty = rowY + ROW_PAD;

      // Clip path so text stays inside the task rect
      const clipId = 'cp_' + task.id.replace(/[^a-zA-Z0-9]/g, '_');
      const cp = mk('clipPath', { id: clipId });
      cp.appendChild(mk('rect', { x: tx + 4, y: ty, width: Math.max(tw - 8, 0), height: TASK_H }));
      defs.appendChild(cp);

      const g = mk('g');
      g.dataset.task = JSON.stringify({
        name: task.name, scheme: task.scheme, type: task.type,
        assigned: task.assigned_to,
        start: task.start_date, end: task.end_date,
        duration: task.duration, base_duration: task.base_duration,
        capacity: (utilization[task.assigned_to] || {}).capacity,
      });

      g.appendChild(mk('rect', {
        x: tx, y: ty, width: tw, height: TASK_H,
        rx: 4, fill: task.color, opacity: 0.85,
      }));

      if (tw > 30) {
        g.appendChild(txt(task.name, {
          x: tx + 6, y: ty + TASK_H / 2 + 4,
          fill: '#fff', 'font-size': 10, 'font-weight': 500,
          'font-family': 'Inter, sans-serif',
          'clip-path': `url(#${clipId})`,
        }));
      }

      svg.appendChild(g);
    });
  });

  document.getElementById('gantt-svg-container').appendChild(svg);

  // ── Tooltip ──
  const tip = document.getElementById('tip');
  svg.addEventListener('mousemove', e => {
    const g = e.target.closest('[data-task]');
    if (!g) { tip.style.display = 'none'; return; }
    const d = JSON.parse(g.dataset.task);
    const capNote = d.capacity < 1
      ? ` <span style="color:#888">(${d.base_duration}d base @ ${d.capacity} capacity)</span>`
      : '';
    tip.innerHTML = `
      <div class="tt-name">${d.name}</div>
      <div class="tt-row"><span>Scheme</span><span>${d.scheme}</span></div>
      <div class="tt-row"><span>Type</span><span>${d.type}</span></div>
      <div class="tt-row"><span>Assigned to</span><span>${d.assigned}</span></div>
      <div class="tt-row"><span>Start</span><span>${d.start}</span></div>
      <div class="tt-row"><span>End</span><span>${d.end}</span></div>
      <div class="tt-row"><span>Duration</span><span>${d.duration} day${d.duration !== 1 ? 's' : ''}${capNote}</span></div>
    `;
    tip.style.display = 'block';
    tip.style.left = (e.clientX + 16) + 'px';
    tip.style.top  = (e.clientY  - 8) + 'px';
  });
  svg.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
}
</script>
</body>
</html>
"""
