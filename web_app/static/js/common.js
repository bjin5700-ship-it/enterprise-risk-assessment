
(function () {
  const base = (typeof window !== "undefined" && window.ERM_BASE) ? String(window.ERM_BASE).replace(/\/$/, "") : "";
  window.ermUrl = function (path) {
    if (!path) return base || "/";
    if (/^https?:\/\//i.test(path)) return path;
    if (path.charAt(0) !== "/") path = "/" + path;
    return base + path;
  };
  const _fetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    if (typeof input === "string" && input.charAt(0) === "/" && !input.startsWith("//")) {
      input = window.ermUrl(input);
    }
    return _fetch(input, init);
  };
})();

/**
 * 企业风险动态评估系统 - 公共前端工具
 */
const ERM = {
  STORAGE_KEY: "erm_form_draft",
  RESULT_KEY: "assessmentResult",
  RESULT_ID_KEY: "assessmentResultId",
  HISTORY_CACHE_KEY: "erm_history_cache",

  LEVEL_COLORS: {
    "低风险": "#16a34a",
    "中等风险": "#f59e0b",
    "高风险": "#ef4444",
    "极高风险": "#b91c1c",
  },

  levelBadge(level) {
    return { "低风险": "badge-low", "中等风险": "badge-medium", "高风险": "badge-high", "极高风险": "badge-critical" }[level] || "badge-low";
  },

  levelBg(level) {
    return { "低风险": "bg-low", "中等风险": "bg-medium", "高风险": "bg-high", "极高风险": "bg-critical" }[level] || "bg-low";
  },

  levelColor(level) {
    return this.LEVEL_COLORS[level] || "#6BCB77";
  },

  getAssessment() {
    try {
      const raw = sessionStorage.getItem(this.RESULT_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  },

  getAssessmentId() {
    return sessionStorage.getItem(this.RESULT_ID_KEY) || "";
  },

  setAssessment(result, recordId) {
    try {
      sessionStorage.setItem(this.RESULT_KEY, JSON.stringify(result));
      if (recordId) sessionStorage.setItem(this.RESULT_ID_KEY, recordId);
      else sessionStorage.removeItem(this.RESULT_ID_KEY);
    } catch (e) {
      console.warn("assessment too large for sessionStorage, storing id only", e);
      sessionStorage.removeItem(this.RESULT_KEY);
      if (recordId) sessionStorage.setItem(this.RESULT_ID_KEY, recordId);
    }
  },

  async resolveAssessment() {
    const cached = this.getAssessment();
    if (cached) return cached;
    const rid = this.getAssessmentId();
    if (!rid) return null;
    const record = await this.loadHistoryRecord(rid);
    return record?.assessment || null;
  },

  getDraft() {
    try {
      const raw = localStorage.getItem(this.STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  },

  saveDraft(formData) {
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify({ formData, savedAt: new Date().toISOString() }));
  },

  clearDraft() {
    localStorage.removeItem(this.STORAGE_KEY);
  },

  toast(message, type = "info") {
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3200);
  },

  startClock(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const tick = () => { el.textContent = new Date().toLocaleString("zh-CN"); };
    tick();
    setInterval(tick, 1000);
  },

  destroyCharts(instances) {
    if (!instances) return;
    Object.values(instances).forEach(c => { if (c && c.destroy) c.destroy(); });
  },

  createRadarChart(canvas, dimensions, existing) {
    if (existing) existing.destroy();
    return new Chart(canvas.getContext("2d"), {
      type: "radar",
      data: {
        labels: dimensions.map(d => d.name),
        datasets: [{
          label: "风险评分",
          data: dimensions.map(d => d.score),
          backgroundColor: "rgba(45, 106, 159, 0.15)",
          borderColor: "rgba(45, 106, 159, 0.8)",
          borderWidth: 2,
          pointBackgroundColor: dimensions.map(d => this.levelColor(d.level)),
          pointRadius: 5,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: { r: { min: 0, max: 4, ticks: { stepSize: 1 } } },
        plugins: { legend: { display: false } },
      },
    });
  },

  createBarChart(canvas, dimensions, existing, horizontal = true) {
    if (existing) existing.destroy();
    const sorted = [...dimensions].sort((a, b) => a.score - b.score);
    const colors = sorted.map(d => this.levelColor(d.level));
    return new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: sorted.map(d => d.name),
        datasets: [{
          label: "风险评分",
          data: sorted.map(d => d.score),
          backgroundColor: colors.map(c => c + "CC"),
          borderColor: colors,
          borderWidth: 1,
          borderRadius: 4,
        }],
      },
      options: {
        indexAxis: horizontal ? "y" : "x",
        responsive: true, maintainAspectRatio: false,
        scales: { x: { min: 0, max: 4, ticks: { stepSize: 1 } } },
        plugins: { legend: { display: false } },
      },
    });
  },

  createDoughnutChart(canvas, levelDistribution, existing) {
    if (existing) existing.destroy();
    const labels = ["低风险", "中等风险", "高风险", "极高风险"];
    const data = labels.map(l => levelDistribution[l] || 0);
    const colors = labels.map(l => this.levelColor(l));
    return new Chart(canvas.getContext("2d"), {
      type: "doughnut",
      data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 2, borderColor: "#fff" }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } } },
      },
    });
  },

  createWeightChart(canvas, dimensions, existing) {
    if (existing) existing.destroy();
    const sorted = [...dimensions].sort((a, b) => b.weight - a.weight);
    return new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: sorted.map(d => d.name),
        datasets: [{
          label: "权重占比",
          data: sorted.map(d => +(d.weight * 100).toFixed(1)),
          backgroundColor: sorted.map(d => this.levelColor(d.level) + "99"),
          borderColor: sorted.map(d => this.levelColor(d.level)),
          borderWidth: 1,
        }],
      },
      options: {
        indexAxis: "y", responsive: true, maintainAspectRatio: false,
        scales: { x: { title: { display: true, text: "权重 (%)" } } },
        plugins: { legend: { display: false } },
      },
    });
  },

  renderDimTable(tbody, dimensions) {
    tbody.innerHTML = "";
    dimensions.forEach(dim => {
      const tr = document.createElement("tr");
      const pct = (dim.score / 4 * 100).toFixed(0);
      tr.innerHTML = `
        <td>${this.escapeHtml(dim.name)}</td>
        <td><strong>${dim.score.toFixed(2)}</strong></td>
        <td><span class="badge ${this.levelBadge(dim.level)}">${this.escapeHtml(dim.level)}</span></td>
        <td><div class="progress-bar"><div class="fill" style="width:${pct}%;background:${this.levelColor(dim.level)};"></div></div></td>
        <td>${(dim.key_risks || []).length}</td>`;
      tbody.appendChild(tr);
    });
  },

  renderRiskList(container, keyRisks, emptyText) {
    container.innerHTML = "";
    if (!keyRisks?.length) {
      container.innerHTML = `<li style="color:#aaa;list-style:none;padding-left:0;">${emptyText}</li>`;
      return;
    }
    keyRisks.forEach(item => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="dim-tag">${this.escapeHtml(item.dimension)}</span>${this.escapeHtml(item.risk)}`;
      container.appendChild(li);
    });
  },

  renderFindings(container, dimensions) {
    container.innerHTML = "";
    const withFindings = dimensions.filter(d => d.findings?.length);
    if (!withFindings.length) {
      container.innerHTML = '<p class="text-muted" style="color:#888;font-size:13px;">暂无详细发现项</p>';
      return;
    }
    withFindings.forEach(dim => {
      const block = document.createElement("div");
      block.className = "findings-block";
      block.innerHTML = `<h4>${this.escapeHtml(dim.name)} <span class="badge ${this.levelBadge(dim.level)}">${dim.score.toFixed(2)}</span></h4>
        <ul>${dim.findings.map(f => `<li>${this.escapeHtml(f)}</li>`).join("")}</ul>`;
      container.appendChild(block);
    });
  },

  renderComparison(container, current, previous) {
    if (!previous || !container) return;
    const scoreDelta = current.overall_score - previous.overall_score;
    const cls = scoreDelta > 0 ? "delta-up" : scoreDelta < 0 ? "delta-down" : "";
    const arrow = scoreDelta > 0 ? "↑" : scoreDelta < 0 ? "↓" : "→";
    container.style.display = "block";
    container.innerHTML = `<strong><i class="fas fa-exchange-alt"></i> 与上次评估对比</strong>（${this.escapeHtml(previous.company_name)} · ${previous.assessed_at?.slice(0, 10) || ""}）
      <br>综合评分 ${previous.overall_score?.toFixed(2)} → ${current.overall_score.toFixed(2)}
      <span class="${cls}">${arrow} ${Math.abs(scoreDelta).toFixed(2)}</span>
      · 等级 ${previous.overall_level} → ${current.overall_level}`;
  },

  renderRiskChangeMatrix(container, section, timeline) {
    if (!container || !timeline?.matrix?.columns?.length) return;
    if (section) section.style.display = "block";
    const m = timeline.matrix;
    const cols = m.columns;
    let html = '<div class="risk-matrix-wrap"><table class="dim-table risk-matrix"><thead><tr><th>维度</th>';
    cols.forEach((c) => {
      const ev = (c.events || []).slice(0, 2).map(e => this.escapeHtml(e)).join("<br>");
      html += `<th>${this.escapeHtml(c.assessed_at || "")}<br><span class="action-meta">${c.overall_score != null ? c.overall_score.toFixed(2) : "—"}</span>${ev ? `<br><span class="matrix-event">${ev}</span>` : ""}</th>`;
    });
    html += "</tr></thead><tbody>";
    const allRows = [m.overall_row, ...(m.rows || [])].filter(Boolean);
    allRows.forEach((row) => {
      html += `<tr><td><strong>${this.escapeHtml(row.dimension)}</strong></td>`;
      (row.cells || []).forEach((cell) => {
        const d = cell.delta_from_prev;
        const deltaCls = d > 0.05 ? "delta-up" : d < -0.05 ? "delta-down" : "";
        const deltaTxt = d != null ? `<span class="${deltaCls}">${d > 0 ? "+" : ""}${d}</span>` : "";
        const sc = cell.score != null ? Number(cell.score).toFixed(2) : "—";
        html += `<td>${sc} ${deltaTxt}<br><span class="action-meta">${this.escapeHtml(cell.level || "")}</span></td>`;
      });
      html += "</tr>";
    });
    html += "</tbody></table></div>";
    if (timeline.message) html += `<p class="gap-summary">${this.escapeHtml(timeline.message)}</p>`;
    container.innerHTML = html;
  },

  renderAssessmentDiff(container, diff) {
    if (!container || !diff?.has_prior) return;
    const rows = (diff.dimension_changes || []).slice(0, 12).map((c) => {
      const d = c.delta;
      const cls = d > 0.05 ? "delta-up" : d < -0.05 ? "delta-down" : "";
      return `<tr><td>${this.escapeHtml(c.dimension)}</td><td>${c.prior_score ?? "—"}</td><td>${c.current_score ?? "—"}</td><td class="${cls}">${d != null ? (d > 0 ? "+" : "") + d : "—"}</td></tr>`;
    }).join("");
    container.innerHTML = `<h4>相对上一期（${this.escapeHtml((diff.prior_assessed_at || "").slice(0, 10))}）维度变动</h4>
      <table class="dim-table"><thead><tr><th>维度</th><th>上期</th><th>本期</th><th>Δ</th></tr></thead><tbody>${rows}</tbody></table>`;
  },

  renderExecutiveSummaryEn(container, section, summary) {
    if (!summary || !container) return;
    if (section) section.style.display = "block";
    const paras = (summary.paragraphs || []).map(p => `<p>${this.escapeHtml(p)}</p>`).join("");
    const board = (summary.board_asks_en || []).length
      ? `<p><strong>Board asks:</strong></p><ul>${summary.board_asks_en.map(b => `<li>${this.escapeHtml(b)}</li>`).join("")}</ul>` : "";
    container.innerHTML = `<p class="gap-summary"><strong>${this.escapeHtml(summary.headline || "")}</strong></p>${paras}${board}<p class="action-meta">${this.escapeHtml(summary.maturity_note || "")}</p>`;
  },

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  },

  fieldInputType(field) {
    const name = field.name || "";
    const type = (field.type || "").toLowerCase();
    if (type.includes("下拉") || type.includes("dropdown") || type.includes("select")) return "select";
    if (field.options && /[|，,]/.test(String(field.options))) return "select";
    if (type.includes("数字") || type.includes("数值") || type.includes("金额") || type === "number") return "number";
    if (name.includes("说明") || name.includes("描述") || name.includes("备注")) return "textarea";
    if (name.includes("日期")) return "date";
    if (name.includes("(%)") || name.includes("比例") || name.includes("率")) return "number";
    if (name.includes("(万元)") || name.includes("人数") || name.includes("数量")) return "number";
    return "text";
  },

  applyAuthUi(me) {
    const user = me && me.user;
    document.querySelectorAll(".admin-only").forEach((el) => {
      el.style.display = (user && user.can_admin) ? "" : "none";
    });
  },

  async refreshAuthUi() {
    try {
      const resp = await fetch("/api/auth/me");
      const me = await resp.json();
      this.applyAuthUi(me);
      window.ERM_USER = (me && me.user) || null;
      return me;
    } catch (_) {
      this.applyAuthUi(null);
      return null;
    }
  },

  adminHeaders(json) {
    const h = json ? { "Content-Type": "application/json" } : {};
    const token = (typeof sessionStorage !== "undefined" && sessionStorage.getItem("erm_admin_token")) || "";
    if (token) h["X-ERM-Token"] = token;
    return h;
  },

  async fetchTemplate() {
    const resp = await fetch("/api/template/fields");
    if (!resp.ok) throw new Error("模板加载失败");
    return resp.json();
  },

  async postAssess(formData, opts = {}) {
    let url = "/api/assess";
    const params = new URLSearchParams();
    if (opts.strict) params.set("strict", "1");
    if (opts.saveHistory) params.set("save_history", "1");
    if (opts.note) params.set("note", opts.note);
    const qs = params.toString();
    if (qs) url += "?" + qs;

    const resp = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(formData) });
    const json = await resp.json();
    if (!resp.ok) {
      if (resp.status === 401) throw new Error(json.error || "未登录，请先登录后再评估");
      throw new Error(json.error || "评估请求失败");
    }
    return json;
  },

  async importPackageFiles(fileList) {
    const fd = new FormData();
    [...fileList].forEach(f => fd.append("files", f));
    const resp = await fetch("/api/import/package", { method: "POST", body: fd });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.error || "文件包导入失败");
    return json;
  },

  async importExcelFile(file) {
    const fd = new FormData();
    fd.append("file", file);
    const resp = await fetch("/api/import/excel", { method: "POST", body: fd });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.error || "导入失败");
    return json;
  },

  async importLocalExcel(filename) {
    const resp = await fetch("/api/import/local", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.error || "导入失败");
    return json;
  },

  async fetchHistory() {
    try {
      const resp = await fetch("/api/history", { credentials: "same-origin" });
      if (!resp.ok) throw new Error(`history ${resp.status}`);
      const json = await resp.json();
      const records = json.records || [];
      localStorage.setItem(this.HISTORY_CACHE_KEY, JSON.stringify(records));
      return records;
    } catch (e) {
      console.warn("fetchHistory failed, using cache", e);
      try {
        const cached = JSON.parse(localStorage.getItem(this.HISTORY_CACHE_KEY) || "[]");
        return Array.isArray(cached) ? cached : [];
      } catch {
        return [];
      }
    }
  },

  async loadDemoArchive(id = "demo-mfg") {
    const record = await this.loadHistoryRecord(id);
    if (record?.assessment) {
      this.setAssessment(record.assessment, id);
      this.toast(`已加载演示档案：${record.company_name}`, "success");
      return record.assessment;
    }
    throw new Error("演示档案不可用");
  },

  async saveToHistory(assessment, note = "") {
    const resp = await fetch("/api/history", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assessment, note }),
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.error || "保存失败");
    await this.fetchHistory();
    return json;
  },

  async loadHistoryRecord(id) {
    const resp = await fetch(`/api/history/${id}`);
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.error || "加载失败");
    return json;
  },

  async exportReport(formData, fmt) {
    const resp = await fetch(`/api/export/${fmt}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || "导出失败");
    }
    const blob = await resp.blob();
    const disposition = resp.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename\*?=(?:UTF-8''|"?)([^";]+)/i);
    const filename = match ? decodeURIComponent(match[1].replace(/"/g, "")) : `report.${fmt}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  },

  generateConclusions(result) {
    const conclusions = [];
    const analytics = result.analytics || {};

    if (analytics.executive_summary?.length) {
      analytics.executive_summary.forEach(l => conclusions.push(l));
    } else {
      const score = result.overall_score;
      if (score <= 1.5) conclusions.push("企业整体风险较低，运营状况良好，建议维持现有风控体系并季度复评。");
      else if (score <= 2.5) conclusions.push("企业存在一定风险，建议关注中等及以上风险维度并制定针对性应对措施。");
      else if (score <= 3.0) conclusions.push("企业风险偏高，需重点关注高风险维度，30 日内启动专项整改。");
      else conclusions.push("企业风险极高，建议立即启动全面风险排查与应急预案，并上报管理层。");
    }

    if (analytics.risk_appetite) {
      conclusions.push(`风险偏好：${analytics.risk_appetite.stated_appetite} — ${analytics.risk_appetite.recommendation}`);
    }
    if (analytics.cross_risk_alerts?.length) {
      conclusions.push("交叉风险：" + analytics.cross_risk_alerts.map(c => c.message).join("；"));
    }
    if (result.form_stats?.completion_pct < 50) {
      conclusions.push(`数据完整度 ${result.form_stats.completion_pct}%，建议补充关键字段后复评以提高准确性。`);
    }
    return conclusions;
  },

  renderAnalyticsOverview(container, analytics) {
    if (!container || !analytics) return;
    const mat = analytics.erm_maturity || {};
    const conf = analytics.confidence || {};
    const appetite = analytics.risk_appetite || {};
    container.innerHTML = `
      <div class="analytics-grid">
        <div class="analytics-item"><div class="lbl">ERM 成熟度</div><div class="val">${mat.level || "—"}/5</div><div class="sub">${this.escapeHtml(mat.name || "")}</div></div>
        <div class="analytics-item"><div class="lbl">评估置信度</div><div class="val">${conf.score ?? "—"}%</div><div class="sub">${this.escapeHtml(conf.note || "")}</div></div>
        <div class="analytics-item"><div class="lbl">风险偏好对齐</div><div class="val ${appetite.within_appetite ? "text-ok" : "text-warn"}">${appetite.within_appetite ? "在承受范围内" : "超出承受度"}</div><div class="sub">${this.escapeHtml(appetite.stated_appetite || "未声明")}</div></div>
        <div class="analytics-item"><div class="lbl">模板覆盖度</div><div class="val">${analytics.gap_analysis?.template_coverage_pct ?? "—"}%</div><div class="sub">核心 ERM 域</div></div>
      </div>`;
  },

  renderFrameworkTable(tbody, rows) {
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!rows?.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#aaa;">暂无数据</td></tr>';
      return;
    }
    rows.forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${this.escapeHtml(r.dimension)}</td><td><strong>${r.score.toFixed(2)}</strong></td>
        <td><span class="badge ${this.levelBadge(r.level)}">${this.escapeHtml(r.level)}</span></td>
        <td style="font-size:12px;">${this.escapeHtml(r.iso31000)}</td>
        <td style="font-size:12px;">${this.escapeHtml(r.coso)} · ${this.escapeHtml(r.tcfd)}</td>`;
      tbody.appendChild(tr);
    });
  },

  renderCitations(items) {
    if (!items?.length) return "";
    const links = items.map(c => {
      const title = this.escapeHtml(c.title || c);
      if (c && c.url) {
        return `<a class="cite-link" href="${this.escapeHtml(c.url)}" target="_blank" rel="noopener noreferrer">${title}</a>`;
      }
      return title;
    }).join(" · ");
    return `<p><strong>法规/制度：</strong>${links}</p>`;
  },

  renderTaskList(container, tasks) {
    if (!container) return;
    const rows = tasks || [];
    if (!rows.length) {
      container.innerHTML = '<p class="gap-summary">暂无到期复评任务。</p>';
      return;
    }
    container.innerHTML = `<ul class="task-list">${rows.map(t => `
      <li>
        <strong>${this.escapeHtml(t.title || t.company_name || "复评任务")}</strong>
        <span class="task-due">到期 ${this.escapeHtml(t.due_date || "")}</span>
        ${t.urgency === "critical" || t.overdue ? '<span class="badge badge-critical">逾期</span>' : ""}
        ${t.status === "open" ? `<button type="button" class="btn btn-outline btn-sm task-done" data-task-id="${this.escapeHtml(t.id)}">完成</button>` : ""}
      </li>`).join("")}</ul>`;
    container.querySelectorAll(".task-done").forEach(btn => {
      btn.onclick = async () => {
        try {
          const resp = await fetch("/api/tasks/" + encodeURIComponent(btn.dataset.taskId) + "/complete", { method: "POST" });
          const json = await resp.json();
          if (!resp.ok) throw new Error(json.error || "失败");
          this.toast("任务已完成", "success");
          this.loadTaskList(container);
        } catch (e) { this.toast(e.message, "error"); }
      };
    });
  },

  async loadTaskList(container) {
    if (!container) return;
    try {
      const resp = await fetch("/api/tasks?status=open");
      if (resp.status === 401) {
        container.innerHTML = '<p class="gap-summary">登录后可查看到期复评任务。</p>';
        return;
      }
      const json = await resp.json();
      this.renderTaskList(container, json.tasks || []);
    } catch (_) {
      container.innerHTML = '<p class="gap-summary">任务列表暂不可用。</p>';
    }
  },

  renderGapAnalysis(container, gap) {
    if (!container || !gap) return;
    const domains = gap.extension_domains || [];
    container.innerHTML = `<p class="gap-summary">${this.escapeHtml(gap.summary || "")}</p>
      <table class="dim-table gap-table"><thead><tr><th>扩展域</th><th>当前缺口</th><th>建议补充</th><th>参考框架</th></tr></thead>
      <tbody>${domains.map(d => `<tr><td>${this.escapeHtml(d.domain)}</td><td>${this.escapeHtml(d.gap)}</td>
        <td>${this.escapeHtml(d.recommendation)}</td><td>${this.escapeHtml(d.framework)}</td></tr>`).join("")}</tbody></table>`;
  },

  renderActionPlans(container, plans) {
    if (!container) return;
    container.innerHTML = "";
    const items = plans?.action_items || [];
    if (!items.length) {
      container.innerHTML = '<p style="color:#888;padding:12px;background:#f5f7fa;border-radius:8px;">暂无待执行行动项，维持现有风控并定期复评。</p>';
      return;
    }
    items.forEach(a => {
      const block = document.createElement("details");
      block.className = "action-card";
      block.open = a.priority === "P0";
      const prioCls = { P0: "prio-high", P1: "prio-urgent", P2: "prio-medium", P3: "prio-medium" }[a.priority] || "prio-medium";
      block.innerHTML = `
        <summary>
          <span class="priority-tag ${prioCls}">${this.escapeHtml(a.priority)}</span>
          <strong>${this.escapeHtml(a.id)} · ${this.escapeHtml(a.title)}</strong>
          <span class="action-meta">${this.escapeHtml(a.dimension)} · ${this.escapeHtml(a.owner)} · ${a.timeline_days}天</span>
        </summary>
        <div class="action-body">
          <p><strong>触发风险：</strong>${this.escapeHtml(a.risk_trigger)}</p>
          <p><strong>成功标准：</strong>${this.escapeHtml(a.success_criteria)}</p>
          <p><strong>框架依据：</strong>${this.escapeHtml(a.framework_ref)}</p>
          ${a.treatment_strategy ? `<p><strong>ISO 31000 应对：</strong>${this.escapeHtml(a.treatment_strategy)}</p>` : ""}
          ${a.root_causes?.length ? `<p><strong>根因：</strong>${a.root_causes.map(c => this.escapeHtml(c)).join(" → ")}</p>` : ""}
          ${a.regulatory_refs?.length && !a.citations?.length ? `<p><strong>法规依据：</strong>${a.regulatory_refs.map(r => this.escapeHtml(r)).join("；")}</p>` : ""}
          ${this.renderCitations(a.citations)}
          <div class="action-steps"><strong>执行步骤</strong><ol>${(a.steps || []).map(s => `<li>${this.escapeHtml(s)}</li>`).join("")}</ol></div>
          <div class="action-deliverables"><strong>交付物</strong><ul>${(a.deliverables || []).map(d => `<li>${this.escapeHtml(d)}</li>`).join("")}</ul></div>
        </div>`;
      container.appendChild(block);
    });
  },

  renderImplementationPhases(container, phases) {
    if (!container || !phases?.length) return;
    container.innerHTML = phases.map(p => `
      <div class="phase-card">
        <h4>${this.escapeHtml(p.phase)}</h4>
        <div class="timeline">${this.escapeHtml(p.focus)}</div>
        <ul>${(p.actions || []).map(id => `<li>行动项 ${this.escapeHtml(id)}</li>`).join("") || "<li>按优先级滚动推进</li>"}</ul>
      </div>`).join("");
  },

  renderReassessmentBanner(container, reminder) {
    if (!container || !reminder) return;
    const cls = { critical: "notice-warning", high: "notice-warning", medium: "notice-info", low: "notice-success" }[reminder.urgency] || "notice-info";
    container.className = `notice ${cls} no-print`;
    container.style.display = "block";
    container.innerHTML = `<i class="fas fa-bell"></i> <strong>复评提醒：</strong>${this.escapeHtml(reminder.message)}（周期 ${reminder.interval_days} 天）`;
  },

  renderKriDashboard(container, kri) {
    if (!container || !kri) return;
    const s = kri.summary || {};
    container.innerHTML = `
      <div class="kri-header">KRI 健康度 <strong>${kri.health_score}%</strong>
        <span class="kri-pill green">${s.green || 0} 正常</span>
        <span class="kri-pill amber">${s.amber || 0} 预警</span>
        <span class="kri-pill red">${s.red || 0} 告警</span>
      </div>
      <table class="dim-table kri-table"><thead><tr><th>指标</th><th>当前值</th><th>目标</th><th>状态</th><th>关联维度</th></tr></thead>
      <tbody>${(kri.kris || []).slice(0, 12).map(k => `
        <tr><td>${this.escapeHtml(k.name)}</td><td>${k.value ?? "—"}${this.escapeHtml(k.unit || "")}</td>
        <td>${this.escapeHtml(k.target)}</td>
        <td><span class="kri-status kri-${k.status}">${this.escapeHtml(k.status_label)}</span></td>
        <td style="font-size:12px;">${this.escapeHtml(k.dimension || "")}</td></tr>`).join("")}
      </tbody></table>`;
  },

  renderScenarioAnalysis(container, scenario) {
    if (!container || !scenario) return;
    const rows = (scenario.scenarios || []).map(s => `
      <div class="scenario-card">
        <div class="scenario-name">${this.escapeHtml(s.name)}</div>
        <div class="scenario-score">${s.overall_score?.toFixed?.(2) ?? s.overall_score} · ${this.escapeHtml(s.overall_level)}</div>
        <div class="scenario-desc">${this.escapeHtml(s.description)}</div>
      </div>`).join("");
    const liq = scenario.liquidity_stress || {};
    container.innerHTML = `<div class="scenario-grid">${rows}</div>
      <p class="gap-summary" style="margin-top:12px;">流动性压力：${this.escapeHtml(liq.status || "—")} · ${this.escapeHtml(liq.shock_assumption || "")} · ${this.escapeHtml(scenario.recommendation || "")}</p>`;
  },

  async syncErpFinancial(formData) {
    const resp = await fetch("/api/integrations/financial", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ form_data: formData, force: false }),
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.error || "同步失败");
    return json.form_data;
  },

  renderRiskRegister(container, register) {
    if (!container || !register?.length) return;
    const user = window.ERM_USER;
    const company = (window.ERM_COMPANY || "");
    container.innerHTML = `<table class="dim-table risk-register"><thead><tr>
      <th>编号</th><th>维度</th><th>固有风险</th><th>残余风险</th><th>P×I</th><th>评级</th>
      <th>状态</th><th>应对策略</th><th>控制缺口</th>${user && user.can_write ? "<th>操作</th>" : ""}</tr></thead>
      <tbody>${register.slice(0, 15).map(r => {
        const st = r.workflow_status_label || "识别";
        const high = r.requires_approval || r.risk_rating === "极高" || r.risk_rating === "高";
        const ops = (user && user.can_write)
          ? `<td class="no-print">${this._workflowButtons("register", r.id, company, high, user)}</td>`
          : "";
        return `<tr>
        <td>${this.escapeHtml(r.seq || r.id)}</td><td>${this.escapeHtml(r.dimension)}</td>
        <td><strong>${r.inherent_score?.toFixed?.(2) ?? r.inherent_score}</strong></td>
        <td>${r.residual_score?.toFixed?.(2) ?? r.residual_score}</td>
        <td>P${r.probability}×I${r.impact}</td>
        <td><span class="badge ${r.risk_rating === '极高' || r.risk_rating === '高' ? 'badge-high' : 'badge-medium'}">${this.escapeHtml(r.risk_rating)}</span></td>
        <td><span class="wf-status wf-${r.workflow_status || "identified"}">${this.escapeHtml(st)}</span>
          ${r.approver ? `<div class="wf-meta">审批 ${this.escapeHtml(r.approver)}</div>` : ""}</td>
        <td style="font-size:12px;">${this.escapeHtml(r.treatment_primary || "")}</td>
        <td>${this.escapeHtml(r.control_gap || "")}</td>${ops}</tr>`;
      }).join("")}
      </tbody></table>
      <p class="gap-summary" style="margin-top:8px;">状态：识别 → 应对中 → 接受/关闭。高风险关闭须审批人、接受理由与复评日期。</p>`;
    this.bindWorkflowClicks(company || window.ERM_COMPANY);
  },

  _workflowButtons(kind, id, company, high, user) {
    if (!company || !id) return "";
    const treat = `<button type="button" class="btn btn-outline btn-sm wf-btn" data-wf-kind="${kind}" data-wf-id="${this.escapeHtml(id)}" data-wf-status="treating">应对中</button>`;
    const close = user && user.can_approve
      ? `<button type="button" class="btn btn-outline btn-sm wf-btn" data-wf-kind="${kind}" data-wf-id="${this.escapeHtml(id)}" data-wf-status="accepted" data-wf-high="${high ? 1 : 0}">接受</button>
         <button type="button" class="btn btn-outline btn-sm wf-btn" data-wf-kind="${kind}" data-wf-id="${this.escapeHtml(id)}" data-wf-status="closed" data-wf-high="${high ? 1 : 0}">关闭</button>`
      : (high ? `<span style="font-size:11px;color:#888;">关闭需审批人</span>` : `<button type="button" class="btn btn-outline btn-sm wf-btn" data-wf-kind="${kind}" data-wf-id="${this.escapeHtml(id)}" data-wf-status="closed" data-wf-high="0">关闭</button>`);
    return `<div class="wf-ops">${treat} ${close}</div>`;
  },

  renderSolutionProgram(container, program) {
    if (!container || !program) return;
    const portfolio = program.treatment_portfolio || [];
    const roadmap = program.roadmap_90d || [];
    const board = (program.board_asks || []).map(a => `<li>${this.escapeHtml(a)}</li>`).join("");
    const cards = portfolio.map(p => `
      <div class="action-card">
        <strong>${this.escapeHtml(p.dimension)}</strong> · ${p.score} · ${this.escapeHtml(p.level)}
        <span class="action-meta">${this.escapeHtml(p.treatment_strategy || "")}</span>
        <ul>${(p.measures || []).map(m => `<li>${this.escapeHtml(m.phase)}：${this.escapeHtml(m.measure)}（${this.escapeHtml(m.owner)}）</li>`).join("")}</ul>
      </div>`).join("");
    const road = roadmap.slice(0, 12).map(r => `
      <tr><td>${this.escapeHtml(r.day_window)}</td><td>${this.escapeHtml(r.dimension)}</td><td>${this.escapeHtml(r.action)}</td><td>${this.escapeHtml(r.owner)}</td></tr>`).join("");
    container.innerHTML = `
      <p class="gap-summary">${this.escapeHtml(program.executive_summary || "")}</p>
      ${board ? `<p><strong>董事会待决：</strong><ul>${board}</ul></p>` : ""}
      ${cards || "<p style='color:#888;'>暂无高优先级维度。</p>"}
      ${road ? `<table class="dim-table"><thead><tr><th>窗口</th><th>维度</th><th>行动</th><th>负责人</th></tr></thead><tbody>${road}</tbody></table>` : ""}`;
  },

  renderDeepSolutions(container, packages) {
    if (!container) return;
    if (!packages?.length) {
      container.innerHTML = '<p style="color:#888;">暂无待深度整改维度。</p>';
      return;
    }
    packages.forEach(pkg => {
      const block = document.createElement("details");
      block.className = "action-card deep-solution-card";
      block.open = pkg.score >= 2.8;
      const measures = (phase, items) => items?.length
        ? `<div class="action-steps"><strong>${phase}</strong><ul>${items.map(m =>
            `<li><strong>${this.escapeHtml(m.measure)}</strong>（${this.escapeHtml(m.owner)}）— ${this.escapeHtml(m.detail)}</li>`).join("")}</ul></div>` : "";
      block.innerHTML = `
        <summary><strong>${this.escapeHtml(pkg.dimension)}</strong> · ${pkg.score?.toFixed(2)} · ${this.escapeHtml(pkg.level)}
          <span class="action-meta">${this.escapeHtml(pkg.solution_hypothesis || "")}</span></summary>
        <div class="action-body">
          <p>${this.escapeHtml(pkg.problem_statement || "")}</p>
          <p><strong>科学依据：</strong>${(pkg.scientific_basis || []).map(s => this.escapeHtml(s)).join(" · ")}</p>
          ${pkg.citations?.length ? this.renderCitations(pkg.citations) : ""}
          ${pkg.root_cause_analysis?.length ? `<p><strong>根因分析：</strong>${pkg.root_cause_analysis.map(r => this.escapeHtml(r.cause)).join(" → ")}</p>` : ""}
          ${measures("立即行动", pkg.immediate_actions)}
          ${measures("短期措施", pkg.short_term_actions)}
          ${measures("中期规划", pkg.medium_term_actions)}
          ${pkg.kpis?.length ? `<p><strong>KPI：</strong>${pkg.kpis.map(k => `${this.escapeHtml(k.name)} ${this.escapeHtml(k.target)}`).join("；")}</p>` : ""}
          <p style="font-size:12px;color:#666;">资源：${this.escapeHtml(pkg.resources?.budget || "")} · ${this.escapeHtml(pkg.resources?.fte || "")} · ${this.escapeHtml(pkg.monitoring || "")}</p>
        </div>`;
      container.appendChild(block);
    });
  },

  renderBoardRecommendations(container, recs) {
    if (!container || !recs?.length) return;
    container.innerHTML = recs.map(r => `
      <div class="conclusion-item"><span class="priority-tag ${r.priority === 'P0' ? 'prio-high' : 'prio-urgent'}">${this.escapeHtml(r.priority)}</span>
        <strong>${this.escapeHtml(r.title)}</strong> — ${this.escapeHtml(r.detail)}
        <span style="font-size:11px;color:#888;">（${this.escapeHtml(r.framework || "")}）</span></div>`).join("");
  },

  renderIndustryBenchmark(container, bench) {
    if (!container || !bench) return;
    const rows = (bench.benchmarks || []).map(b =>
      `<tr><td>${this.escapeHtml(b.metric)}</td><td>${b.value}</td><td>${b.industry_threshold}</td>
      <td><span class="kri-status kri-${b.status === '超标' ? 'red' : 'green'}">${this.escapeHtml(b.status)}</span></td>
      <td style="font-size:12px;">${this.escapeHtml(b.note)}</td></tr>`).join("");
    container.innerHTML = `<p class="gap-summary">${this.escapeHtml(bench.industry)}行业 · ${this.escapeHtml(bench.overall_vs_industry || "")}</p>
      ${rows ? `<table class="dim-table"><thead><tr><th>指标</th><th>企业值</th><th>行业阈值</th><th>状态</th><th>说明</th></tr></thead><tbody>${rows}</tbody></table>` : '<p style="color:#888;">填报财务/经营关键指标后可显示行业对标</p>'}`;
  },

  renderMonteCarlo(canvas, mc, existing) {
    if (!canvas || !mc?.distribution) return null;
    if (existing) existing.destroy();
    const dist = mc.distribution;
    return new Chart(canvas.getContext("2d"), {
      type: "bar",
      data: {
        labels: dist.labels,
        datasets: [{ label: "模拟频次", data: dist.counts, backgroundColor: "rgba(45,106,159,0.7)", borderRadius: 4 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          title: { display: true, text: `综合评分不确定性 · P50=${mc.percentiles?.p50} · 80%区间 [${mc.confidence_interval_80?.join(", ")}]` },
          legend: { display: false },
        },
        scales: { y: { title: { display: true, text: "频次" } } },
      },
    });
  },

  renderMonteCarloSummary(container, mc) {
    if (!container || !mc) return;
    const p95 = mc.score_p95 ?? mc.var_95;
    const tail = mc.score_tail_mean ?? mc.cvar_95;
    const sensRows = (mc.sensitivity || []).map((s, i) =>
      `<tr><td>${i + 1}</td><td>${this.escapeHtml(s.dimension)}</td><td>${s.mu_star}</td><td>${s.base_score}</td></tr>`
    ).join("");
    const money = mc.money_track;
    let moneyHtml = `<p class="gap-summary">未填年营收或资产总额，不展示经营冲击情景。</p>`;
    if (money && (money.revenue_pressure || money.asset_pressure)) {
      const rp = money.revenue_pressure;
      const ap = money.asset_pressure;
      moneyHtml = `<div class="analytics-grid" style="margin-top:8px;">
        ${rp ? `<div class="analytics-item"><div class="lbl">营收承压（万元）</div><div class="val" style="font-size:16px;">${rp.p50}</div><div class="sub">P10 ${rp.p10} · P90 ${rp.p90}</div></div>` : ""}
        ${ap ? `<div class="analytics-item"><div class="lbl">资产承压（万元）</div><div class="val" style="font-size:16px;">${ap.p50}</div><div class="sub">P10 ${ap.p10} · P90 ${ap.p90}</div></div>` : ""}
        <div class="analytics-item"><div class="lbl">承压幅度</div><div class="val">${money.pressure_pct?.p50 ?? "—"}%</div><div class="sub">P10–P90 ${money.pressure_pct?.p10 ?? "—"}–${money.pressure_pct?.p90 ?? "—"}%</div></div>
      </div>
      <p class="gap-summary">${this.escapeHtml(money.disclaimer || "")}</p>`;
    }
    container.innerHTML = `
      <div class="analytics-grid">
        <div class="analytics-item"><div class="lbl">评分均值</div><div class="val">${mc.mean_score}</div><div class="sub">基准 ${mc.base_score} · ${this.escapeHtml(mc.unit || "评分 1–4")}</div></div>
        <div class="analytics-item"><div class="lbl">P95 评分</div><div class="val">${p95 ?? "—"}</div><div class="sub">尾部均值评分 ${tail ?? "—"}</div></div>
        <div class="analytics-item"><div class="lbl">80% 评分区间</div><div class="val" style="font-size:16px;">[${mc.confidence_interval_80?.join(" – ")}]</div></div>
        <div class="analytics-item"><div class="lbl">超偏好阈值概率</div><div class="val ${mc.probability_breach_appetite_pct > 30 ? "text-warn" : "text-ok"}">${mc.probability_breach_appetite_pct}%</div></div>
      </div>
      <p class="gap-summary">${this.escapeHtml(mc.interpretation || "")}</p>
      ${mc.disclaimer ? `<p class="gap-summary">${this.escapeHtml(mc.disclaimer)}</p>` : ""}
      <h4 style="font-size:14px;margin:14px 0 6px;">驱动综合分的主要假设（Morris μ*）</h4>
      ${sensRows
        ? `<table class="dim-table"><thead><tr><th>#</th><th>维度</th><th>μ*</th><th>基准分</th></tr></thead><tbody>${sensRows}</tbody></table>`
        : '<p class="gap-summary">敏感性暂不可用。</p>'}
      <h4 style="font-size:14px;margin:14px 0 6px;">经营冲击情景（可选金额轨）</h4>
      ${moneyHtml}`;
  },

  renderThreeLines(canvas, tld, existing) {
    if (!canvas || !tld) return null;
    if (existing) existing.destroy();
    const labels = ["第一道防线", "第二道防线", "第三道防线"];
    const data = [tld.line1_operational?.score, tld.line2_oversight?.score, tld.line3_assurance?.score];
    return new Chart(canvas.getContext("2d"), {
      type: "radar",
      data: {
        labels,
        datasets: [{
          label: "成熟度 (1-5)",
          data,
          backgroundColor: "rgba(112,48,160,0.15)",
          borderColor: "rgba(112,48,160,0.8)",
          pointBackgroundColor: "#7030A0",
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: { r: { min: 0, max: 5, ticks: { stepSize: 1 } } },
        plugins: { title: { display: true, text: `COSO 三道防线 · ${tld.overall_maturity} · 最弱：${tld.weakest_line}` } },
      },
    });
  },

  renderThreeLinesDetail(container, tld) {
    if (!container || !tld) return;
    const lines = [tld.line1_operational, tld.line2_oversight, tld.line3_assurance].filter(Boolean);
    container.innerHTML = lines.map(l => `
      <div style="margin-bottom:10px;padding:10px;background:#f5f7fa;border-radius:8px;">
        <strong>${this.escapeHtml(l.label)}</strong> — ${l.score}/5
        <ul style="margin:6px 0 0 18px;font-size:12px;">${(l.factors || []).map(f =>
          `<li>${this.escapeHtml(f.factor)}：${f.score}（${this.escapeHtml(f.note)}）</li>`).join("")}</ul>
      </div>`).join("") +
      (tld.gaps?.length ? `<p class="gap-summary"><strong>缺口：</strong>${tld.gaps.map(g => this.escapeHtml(g)).join("；")}</p>` : "") +
      (tld.recommendations?.length ? `<ul style="font-size:13px;margin-left:18px;">${tld.recommendations.map(r => `<li>${this.escapeHtml(r)}</li>`).join("")}</ul>` : "");
  },

  renderIndustryPlaybook(container, pb) {
    if (!container || !pb) return;
    container.innerHTML = `
      <p class="gap-summary">${this.escapeHtml(pb.tailored_note || "")}</p>
      <h4 style="font-size:14px;margin:12px 0 6px;">行业优先风险域</h4>
      <p>${(pb.priority_risks || []).map(r => `<span class="badge badge-medium" style="margin:2px;">${this.escapeHtml(r)}</span>`).join(" ")}</p>
      <h4 style="font-size:14px;margin:12px 0 6px;">最佳实践路径</h4>
      <ul style="margin-left:18px;font-size:13px;">${(pb.best_practices || []).map(p =>
        `<li>${this.escapeHtml(p.practice || p)}</li>`).join("")}</ul>
      <h4 style="font-size:14px;margin:12px 0 6px;">行业 KPI 包</h4>
      <p style="font-size:13px;">${(pb.industry_kpis || []).map(k => this.escapeHtml(k)).join(" · ")}</p>
      ${pb.priority_actions?.length ? `<table class="dim-table" style="margin-top:10px;"><thead><tr><th>风险域</th><th>建议行动</th><th>法规聚焦</th></tr></thead>
        <tbody>${pb.priority_actions.map(a => `<tr><td>${this.escapeHtml(a.risk_area)}</td><td style="font-size:12px;">${this.escapeHtml(a.action)}</td><td style="font-size:12px;">${this.escapeHtml(a.regulatory)}</td></tr>`).join("")}</tbody></table>` : ""}`;
  },

  renderBayesianUpdate(container, bayes) {
    if (!container || !bayes) return;
    const trendClass = bayes.overall_trend === "风险上升" ? "text-warn" : bayes.overall_trend === "风险下降" ? "text-ok" : "";
    container.innerHTML = `
      <div class="analytics-grid">
        <div class="analytics-item"><div class="lbl">先验评分</div><div class="val">${bayes.prior_overall ?? "—"}</div></div>
        <div class="analytics-item"><div class="lbl">当前观测</div><div class="val">${bayes.observation_overall ?? bayes.prior_overall ?? "—"}</div></div>
        <div class="analytics-item"><div class="lbl">后验评分</div><div class="val ${trendClass}">${bayes.posterior_overall ?? "—"}</div></div>
        <div class="analytics-item"><div class="lbl">趋势</div><div class="val" style="font-size:16px;">${this.escapeHtml(bayes.overall_trend || "—")}</div></div>
      </div>
      <p class="gap-summary">${this.escapeHtml(bayes.interpretation || "")}</p>
      ${bayes.dimension_updates?.length ? `<table class="dim-table" style="margin-top:8px;"><thead><tr>
        <th>维度</th><th>先验</th><th>观测</th><th>后验</th><th>Δ</th><th>趋势</th></tr></thead>
        <tbody>${bayes.dimension_updates.slice(0, 10).map(r => `<tr>
          <td>${this.escapeHtml(r.dimension)}</td><td>${r.prior}</td><td>${r.observation}</td><td><strong>${r.posterior}</strong></td>
          <td class="${r.delta > 0 ? 'text-warn' : r.delta < 0 ? 'text-ok' : ''}">${r.delta >= 0 ? '+' : ''}${r.delta}</td>
          <td>${this.escapeHtml(r.trend)}</td></tr>`).join("")}</tbody></table>` : ""}`;
  },

  renderCorrelationInsights(container, insights) {
    if (!container || !insights?.length) {
      if (container) container.innerHTML = '<p style="color:#888;font-size:13px;">当前无显著风险传导路径（需两个关联维度评分均≥2.3）</p>';
      return;
    }
    container.innerHTML = `<table class="dim-table"><thead><tr><th>传导路径</th><th>说明</th><th>评分</th><th>强度</th></tr></thead>
      <tbody>${insights.map(i => `<tr>
        <td>${this.escapeHtml(i.from)} → ${this.escapeHtml(i.to)}</td>
        <td style="font-size:12px;">${this.escapeHtml(i.message)}</td>
        <td>${this.escapeHtml(i.scores)}</td>
        <td><span class="badge ${i.strength === '强' ? 'badge-high' : 'badge-medium'}">${this.escapeHtml(i.strength)}</span></td>
      </tr>`).join("")}</tbody></table>`;
  },

  renderCorrelationNetwork(canvas, network) {
    if (!canvas || !network?.nodes?.length) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width = canvas.offsetWidth || 480;
    const h = canvas.height = canvas.offsetHeight || 320;
    ctx.clearRect(0, 0, w, h);
    const cx = w / 2, cy = h / 2, radius = Math.min(w, h) * 0.36;
    const nodeMap = {};
    network.nodes.forEach((n, i) => {
      const angle = (i / network.nodes.length) * Math.PI * 2 - Math.PI / 2;
      nodeMap[n.id] = { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius, ...n };
    });
    (network.edges || []).forEach(e => {
      const a = nodeMap[e.source], b = nodeMap[e.target];
      if (!a || !b) return;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = e.type === "causal" ? "rgba(255,107,107,0.55)" : "rgba(45,106,159,0.35)";
      ctx.lineWidth = e.weight || 1;
      ctx.stroke();
    });
    network.nodes.forEach(n => {
      const p = nodeMap[n.id];
      if (!p) return;
      ctx.beginPath();
      ctx.arc(p.x, p.y, n.size || 12, 0, Math.PI * 2);
      ctx.fillStyle = n.color || "#2d6a9f";
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "#333";
      ctx.font = "10px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(n.label || n.id.slice(0, 4), p.x, p.y + (n.size || 12) + 12);
    });
    const stats = network.stats || {};
    ctx.fillStyle = "#888";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(`节点 ${stats.node_count || network.nodes.length} · 关联 ${stats.edge_count || 0} · 传导 ${stats.causal_paths || 0}`, 8, h - 8);
  },

  renderHeatmapMatrix(canvas, matrix) {
    if (!canvas || !matrix?.length) return null;
    if (canvas._heatmapChart) { canvas._heatmapChart.destroy(); canvas._heatmapChart = null; }
    const data = matrix.map((m, i) => ({
      x: m.probability + (i % 3) * 0.06,
      y: m.impact + (Math.floor(i / 3) % 2) * 0.06,
      r: 7 + (m.score || 1) * 2.5,
      dim: m.dimension,
      level: m.level,
      source: m.source || "suggested",
      score: m.score,
      p: m.probability,
      i: m.impact,
    }));
    canvas._heatmapChart = new Chart(canvas.getContext("2d"), {
      type: "bubble",
      data: {
        datasets: [{
          label: "风险热力",
          data: data.map(d => ({ x: d.x, y: d.y, r: d.r })),
          backgroundColor: data.map(d => d.source === "independent" ? this.levelColor(d.level) + "cc" : "rgba(148,163,184,0.55)"),
          borderColor: data.map(d => d.source === "independent" ? this.levelColor(d.level) : "#94a3b8"),
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          title: { display: true, text: "5×5 可能性 × 影响（独立估计；灰色=建议占位）" },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const d = data[ctx.dataIndex];
                const src = d.source === "independent" ? "独立估计" : "建议值";
                return `${d.dim}: 可能性${d.p} × 影响${d.i} · 规则分 ${Number(d.score).toFixed(2)}（${src}）`;
              },
            },
          },
          legend: { display: false },
        },
        scales: {
          x: { min: 0.5, max: 5.5, title: { display: true, text: "可能性" }, ticks: { stepSize: 1 } },
          y: { min: 0.5, max: 5.5, title: { display: true, text: "影响" }, ticks: { stepSize: 1 } },
        },
      },
    });
    return canvas._heatmapChart;
  },

  renderHeatmapSummary(noteEl, tableEl, matrix, meta) {
    if (noteEl) {
      noteEl.innerHTML = `<p class="gap-summary">${this.escapeHtml((meta && meta.note) || "")}</p>`;
    }
    if (!tableEl || !matrix?.length) return;
    const rows = matrix.map(m => `<tr>
      <td>${this.escapeHtml(m.dimension)}</td>
      <td>${m.probability}</td><td>${m.impact}</td>
      <td>${Number(m.score).toFixed(2)}</td>
      <td>${this.escapeHtml(m.source === "independent" ? "独立估计" : "建议占位")}</td>
    </tr>`).join("");
    tableEl.innerHTML = `<table class="dim-table"><thead><tr>
      <th>维度</th><th>可能性</th><th>影响</th><th>规则综合分</th><th>矩阵来源</th>
    </tr></thead><tbody>${rows}</tbody></table>`;
  },

  renderExternalEvidence(container, pkg) {
    if (!container) return;
    if (!pkg) {
      container.innerHTML = "";
      return;
    }
    const recs = pkg.records || [];
    const rows = recs.map(r => `<tr>
      <td>${this.escapeHtml(r.category_label || r.category || "")}</td>
      <td>${this.escapeHtml(r.title || "")}</td>
      <td>${this.escapeHtml(r.date || "—")}</td>
      <td style="font-size:12px;">${this.escapeHtml(r.summary || "")}</td>
      <td>${r.url ? `<a href="${this.escapeHtml(r.url)}" target="_blank" rel="noopener">来源</a>` : this.escapeHtml(r.source || "")}</td>
    </tr>`).join("");
    const corr = (pkg.corroborated || []).map(x => this.escapeHtml(x)).join("；");
    container.innerHTML = `
      <p class="gap-summary">${this.escapeHtml(pkg.note || "")}${pkg.disclaimer ? " " + this.escapeHtml(pkg.disclaimer) : ""}</p>
      ${corr ? `<p class="gap-summary">与表单印证：${corr}</p>` : ""}
      ${rows
        ? `<table class="dim-table"><thead><tr><th>类型</th><th>事项</th><th>日期</th><th>摘要</th><th>来源</th></tr></thead><tbody>${rows}</tbody></table>`
        : '<p class="gap-summary">无外部命中记录。</p>'}`;
  },

  renderCorrelationMatrix(container, cm) {
    if (!container || !cm?.matrix?.length) {
      if (container) container.innerHTML = '<p style="color:#888;font-size:13px;">维度不足，暂无相关矩阵</p>';
      return;
    }
    const labels = cm.labels || [];
    const short = (s) => s.replace("风险", "").slice(0, 4);
    const cellColor = (v) => {
      if (v >= 0.72) return "background:#ffcdd2;color:#b71c1c;";
      if (v >= 0.55) return "background:#fff9c4;color:#f57f17;";
      return "background:#e8f5e9;color:#2e7d32;";
    };
    let html = '<div class="corr-matrix-wrap">';
    if (cm.source === "historical_pearson" || cm.methodology?.includes("Pearson")) {
      html += `<p class="gap-summary" style="margin-bottom:8px;"><span class="badge badge-info">历史 Pearson</span> ${this.escapeHtml(cm.methodology || "基于历史评估快照")}${cm.snapshot_basis ? ` · ${cm.snapshot_basis} 期` : ""}</p>`;
    }
    html += '<table class="corr-matrix"><thead><tr><th></th>';
    labels.forEach(l => { html += `<th title="${this.escapeHtml(l)}">${this.escapeHtml(short(l))}</th>`; });
    html += '</tr></thead><tbody>';
    cm.matrix.forEach((row, i) => {
      html += `<tr><th title="${this.escapeHtml(labels[i])}">${this.escapeHtml(short(labels[i]))}</th>`;
      row.forEach(v => { html += `<td style="${cellColor(v)}">${v.toFixed(2)}</td>`; });
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    if (cm.high_pairs?.length) {
      html += '<p class="gap-summary" style="margin-top:10px;"><strong>高相关对：</strong>' +
        cm.high_pairs.slice(0, 5).map(p => `${this.escapeHtml(p.dim_a)}↔${this.escapeHtml(p.dim_b)}(${p.correlation})`).join(' · ') + '</p>';
    }
    container.innerHTML = html;
  },


  renderPhase1Enhancement(result) {
    const analytics = (result && result.analytics) || {};
    const p1 = result.phase1_enhancement || analytics.phase1_enhancement || {};
    const gate = result.data_quality_gate || analytics.data_quality_gate || p1.data_quality_gate;
    const bench = (p1.industry_benchmark) || ((analytics.deep_analysis || {}).industry_benchmark);
    const actions = result.verifiable_actions || analytics.verifiable_actions || p1.verifiable_actions;
    const supplements = p1.supplements || (result.form_stats && result.form_stats._supplements) || null;

    const gateTop = document.getElementById("phase1GatePanel");
    if (gateTop && gate) {
      const cls = gate.gate === "pass" ? "notice-success" : gate.gate === "caution" ? "notice-warning" : "notice-warning";
      gateTop.innerHTML = `<div class="notice ${cls}"><i class="fas fa-shield-alt"></i> <strong>数据门禁：${this.escapeHtml(gate.gate_label || "")}</strong>
        · 置信度 ${gate.confidence_score ?? "--"}% · 关键字段 ${gate.key_completion_pct ?? "--"}% · 整体 ${gate.completion_pct ?? "--"}%
        ${(gate.decision_impact || []).slice(0, 2).map(x => `<div style="margin-top:6px;">${this.escapeHtml(x)}</div>`).join("")}
      </div>`;
    }

    const benchTop = document.getElementById("phase1BenchPanel");
    if (benchTop && bench && bench.percentile) {
      const pct = bench.percentile;
      benchTop.innerHTML = `<div class="card" style="margin-bottom:16px;padding:16px 20px;">
        <div style="display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between;">
          <div>
            <div style="font-size:12px;color:var(--erm-text-muted,#64748b);">行业分位对标 · ${this.escapeHtml(bench.industry || "")}</div>
            <div style="font-size:22px;font-weight:700;color:var(--erm-accent,#0d9f6e);margin-top:4px;">优于约 ${pct.better_than_peers_pct}% 同业</div>
            <div style="font-size:13px;color:var(--erm-text,#334155);margin-top:4px;">${this.escapeHtml(pct.band || "")}</div>
          </div>
          <div style="font-size:12px;color:#64748b;max-width:360px;line-height:1.5;">${this.escapeHtml(pct.method_note || "")}</div>
        </div>
      </div>`;
    }

    const gDetail = document.getElementById("phase1GateDetail");
    if (gDetail && gate) {
      gDetail.innerHTML = `
        <div class="analytics-grid">
          <div class="analytics-item"><div class="lbl">门禁</div><div class="val" style="font-size:16px;">${this.escapeHtml(gate.gate || "")}</div><div class="sub">${this.escapeHtml(gate.gate_label || "")}</div></div>
          <div class="analytics-item"><div class="lbl">置信度</div><div class="val">${gate.confidence_score ?? "--"}%</div></div>
          <div class="analytics-item"><div class="lbl">关键字段</div><div class="val">${gate.key_completion_pct ?? "--"}%</div></div>
          <div class="analytics-item"><div class="lbl">评分表已填</div><div class="val">${gate.scoring_sheets_filled ?? 0}/${gate.scoring_sheets_total ?? 0}</div></div>
        </div>
        <ul class="exec-summary-list">${(gate.decision_impact || []).map(x => `<li>${this.escapeHtml(x)}</li>`).join("")}</ul>
        ${(gate.missing_key_fields || []).length ? `<p class="gap-summary"><strong>待补关键字段：</strong>${gate.missing_key_fields.slice(0, 8).map(x => this.escapeHtml(x)).join("；")}</p>` : ""}
      `;
    }

    const bDetail = document.getElementById("phase1BenchDetail");
    if (bDetail && bench) {
      const rows = (bench.dimension_peer_positions || []).slice(0, 6).map(d =>
        `<tr><td>${this.escapeHtml(d.dimension)}</td><td>${Number(d.score).toFixed(2)}</td><td>${d.better_than_peers_pct}%</td><td>${this.escapeHtml(d.level || "")}</td></tr>`
      ).join("");
      const metrics = (bench.benchmarks || []).map(m =>
        `<li>${this.escapeHtml(m.metric)}：${m.value}（阈值 ${m.industry_threshold}）· <strong>${this.escapeHtml(m.status)}</strong></li>`
      ).join("");
      bDetail.innerHTML = `
        <p class="gap-summary">${this.escapeHtml(bench.overall_vs_industry || (bench.percentile || {}).band || "")}</p>
        ${metrics ? `<ul class="exec-summary-list">${metrics}</ul>` : ""}
        <table class="kpi-table"><thead><tr><th>维度</th><th>评分</th><th>优于同业</th><th>等级</th></tr></thead><tbody>${rows || '<tr><td colspan="4" style="text-align:center;color:#94a3b8;">暂无</td></tr>'}</tbody></table>
      `;
    }

    const aDetail = document.getElementById("phase1ActionsDetail");
    const aTop = document.getElementById("phase1ActionsPanel");
    if (actions && (actions.packs || []).length) {
      const cards = (actions.packs || []).slice(0, 8).map(p => `
        <details class="action-card">
          <summary><span class="badge badge-info">${this.escapeHtml(p.priority || "")}</span>
            <strong>${this.escapeHtml(p.title || "")}</strong>
            <span class="action-meta">${this.escapeHtml(p.dimension || "")} · ${p.baseline_score}→${p.target_score} · ${p.deadline_days || "--"}天</span>
          </summary>
          <div class="action-body">
            <div><strong>责任人：</strong>${this.escapeHtml(p.owner || "")}</div>
            <div><strong>验收标准：</strong>${this.escapeHtml(p.acceptance_criteria || "")}</div>
            <div><strong>复验方法：</strong>${this.escapeHtml(p.verification_method || "")}</div>
            <div class="action-deliverables"><strong>证据：</strong><ul>${(p.evidence_needed || []).map(e => `<li>${this.escapeHtml(e)}</li>`).join("")}</ul></div>
            <div class="action-steps"><strong>里程碑：</strong><ol>${(p.milestones || []).map(s => `<li>${this.escapeHtml(s)}</li>`).join("")}</ol></div>
          </div>
        </details>`).join("");
      if (aDetail) aDetail.innerHTML = `<p class="gap-summary">${this.escapeHtml(actions.howto || "")}</p>${cards}`;
      if (aTop) aTop.innerHTML = `<div class="card"><h3><i class="fas fa-check-double"></i> 可验证行动包（${actions.total}）</h3>${cards}</div>`;
    }

    const sDetail = document.getElementById("phase1SupplementsDetail");
    if (sDetail) {
      if (supplements && supplements.file_count) {
        sDetail.innerHTML = `<p class="gap-summary">${(supplements.coverage_notes || []).map(x => this.escapeHtml(x)).join(" · ")}</p>
          <ul class="exec-summary-list">${(supplements.files || []).map(f =>
            `<li><strong>${this.escapeHtml(f.filename)}</strong> · ${this.escapeHtml(f.category)} · ${this.escapeHtml(f.role)} · ${f.size_kb || 0}KB</li>`
          ).join("")}</ul>
          <p class="gap-summary">${this.escapeHtml(supplements.next_step || "")}</p>`;
      } else {
        sDetail.innerHTML = `<p class="gap-summary">尚未上传补充材料。可在「数据录入」一次选择主表 Excel + 财报/保单/制度等文件，增强证据链。</p>`;
      }
    }
  },

  renderExecutiveBrief(container, brief) {
    if (!container || !brief) return;
    container.innerHTML = `
      <div class="brief-card">
        <div class="brief-headline"><i class="fas fa-gavel"></i> ${this.escapeHtml(brief.headline || "")}</div>
        <div class="brief-grid">
          <div class="brief-col"><h4>核心判断</h4><ul>${(brief.key_messages || []).map(m => `<li>${this.escapeHtml(m)}</li>`).join("") || "<li>—</li>"}</ul></div>
          <div class="brief-col"><h4>董事会关注</h4><ul>${(brief.board_asks || []).map(m => `<li>${this.escapeHtml(m)}</li>`).join("") || "<li>—</li>"}</ul></div>
          <div class="brief-col"><h4>90 天行动</h4><ul>${(brief.next_90_days || []).map(m => `<li>${this.escapeHtml(m)}</li>`).join("") || "<li>—</li>"}</ul></div>
        </div>
      </div>`;
  },

  renderScoreGauge(canvas, score, level, existing) {
    if (!canvas) return null;
    if (existing) existing.destroy();
    const pct = Math.min(100, score / 4 * 100);
    const color = this.levelColor(level);
    return new Chart(canvas.getContext("2d"), {
      type: "doughnut",
      data: {
        datasets: [{
          data: [pct, 100 - pct],
          backgroundColor: [color, "rgba(255,255,255,0.2)"],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: false, maintainAspectRatio: false, cutout: "78%",
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        animation: { animateRotate: true, duration: 800 },
      },
    });
  },

  initSectionBlocks() {
    document.querySelectorAll(".section-header[data-toggle]").forEach(hdr => {
      hdr.onclick = () => {
        const id = hdr.dataset.toggle;
        document.getElementById(id)?.classList.toggle("collapsed");
      };
    });
  },

  initSectionNav(navId) {
    const nav = document.getElementById(navId);
    if (!nav) return;
    const links = nav.querySelectorAll("a[data-sec]");
    links.forEach(a => {
      a.onclick = (e) => {
        e.preventDefault();
        const el = document.getElementById(a.dataset.sec);
        el?.classList.remove("collapsed");
        el?.scrollIntoView({ behavior: "smooth", block: "start" });
        links.forEach(l => l.classList.remove("active"));
        a.classList.add("active");
      };
    });
    if (links[0]) links[0].classList.add("active");
  },

  renderAlertCenter(container, alerts) {
    if (!container || !alerts?.alerts?.length) {
      if (container) container.innerHTML = "";
      return;
    }
    const sevIcon = { critical: "fa-exclamation-circle", high: "fa-exclamation-triangle", medium: "fa-info-circle" };
    container.innerHTML = `
      <div class="alert-center ${alerts.critical_count ? 'alert-center-critical' : 'alert-center-warn'}">
        <div class="alert-center-head"><i class="fas fa-bell"></i> <strong>风险告警中心</strong> — ${this.escapeHtml(alerts.summary || "")}
          ${alerts.requires_reassessment ? '<span class="badge badge-critical" style="margin-left:8px;">建议立即复评</span>' : ""}
        </div>
        <ul class="alert-list">${alerts.alerts.slice(0, 6).map(a => `
          <li class="alert-item alert-${a.severity}">
            <i class="fas ${sevIcon[a.severity] || 'fa-info-circle'}"></i>
            <div><strong>${this.escapeHtml(a.title)}</strong><div class="alert-msg">${this.escapeHtml(a.message)}</div>
            <div class="alert-action">${this.escapeHtml(a.suggested_action || "")}</div></div>
          </li>`).join("")}</ul>
      </div>`;
  },

  renderClosedLoop(container, cl) {
    if (!container || !cl) return;
    const v = cl.remediation_verification || {};
    const ts = cl.timeseries || {};
    const verCls = { "有效": "text-ok", "部分有效": "", "待验证": "", "待复评": "", "无效": "text-warn", "首次评估基线": "" }[v.verification_label] || "";
    container.innerHTML = `
      <div class="closed-loop-panel">
        <div class="analytics-grid">
          <div class="analytics-item"><div class="lbl">闭环状态</div><div class="val ${verCls}">${this.escapeHtml(v.verification_label || v.verification || "—")}</div></div>
          <div class="analytics-item"><div class="lbl">评分变化</div><div class="val">${v.has_prior ? (v.overall_delta >= 0 ? "+" : "") + v.overall_delta : "—"}</div><div class="sub">${this.escapeHtml(v.overall_trend || "")}</div></div>
          <div class="analytics-item"><div class="lbl">行动完成率</div><div class="val">${v.actions_tracked?.completion_pct ?? 0}%</div><div class="sub">${v.actions_tracked?.completed || 0}/${v.actions_tracked?.total || 0} 项${v.actions_tracked?.source === "persisted" ? " · 已落库" : ""}</div></div>
          <div class="analytics-item"><div class="lbl">登记关闭</div><div class="val">${v.actions_tracked?.register_closed ?? cl.workflow?.register_closed ?? 0}/${v.actions_tracked?.register_total ?? cl.workflow?.register_total ?? 0}</div><div class="sub">P0 已关闭 ${v.actions_tracked?.p0_closed ?? 0}/${v.actions_tracked?.p0_total ?? 0}</div></div>
          <div class="analytics-item"><div class="lbl">KPI 快照</div><div class="val">${ts.snapshot_count || 0}</div><div class="sub">${this.escapeHtml(ts.score_trend_label || "累积中")}</div></div>
        </div>
        <p class="gap-summary">${this.escapeHtml(cl.summary || v.recommendation || "")}</p>
        <p class="gap-summary" style="font-size:12px;">完成率来自已保存的行动项与登记项状态；P0/高风险关闭须审批人、理由与复评日期。</p>
        ${v.dimension_changes?.length ? `<table class="dim-table" style="margin-top:8px;"><thead><tr><th>维度</th><th>前次</th><th>本次</th><th>Δ</th><th>趋势</th></tr></thead>
          <tbody>${v.dimension_changes.slice(0, 8).map(d => `<tr><td>${this.escapeHtml(d.dimension)}</td><td>${d.prior}</td><td>${d.current}</td>
            <td class="${d.delta < 0 ? 'text-ok' : d.delta > 0 ? 'text-warn' : ''}">${d.delta >= 0 ? '+' : ''}${d.delta}</td>
            <td>${this.escapeHtml(d.trend)}</td></tr>`).join("")}</tbody></table>` : ""}
        ${v.model_calibration ? `<p class="gap-summary" style="margin-top:8px;font-size:12px;"><strong>模型校准：</strong>预测 ${v.model_calibration.predicted_posterior} vs 观测 ${v.model_calibration.actual_observation}，误差 ${v.model_calibration.prediction_error}。${this.escapeHtml(v.model_calibration.note || "")}</p>` : ""}
      </div>`;
  },

  renderScoreTrendChart(canvas, timeseries, existing) {
    if (!canvas || !timeseries?.score_trend?.length) return null;
    if (existing) existing.destroy();
    const data = timeseries.score_trend;
    return new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: data.map(d => d.date),
        datasets: [{
          label: "综合评分",
          data: data.map(d => d.score),
          borderColor: "#2d6a9f",
          backgroundColor: "rgba(45,106,159,0.1)",
          fill: true,
          tension: 0.3,
          pointRadius: 4,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { title: { display: true, text: `评分时序 · ${timeseries.score_trend_label || ""} (Δ${timeseries.score_delta ?? 0})` }, legend: { display: false } },
        scales: { y: { min: 1, max: 4, title: { display: true, text: "评分" } } },
      },
    });
  },

  renderTrackableActionPlans(container, plans, companyName, onUpdate) {
    this.renderActionPlans(container, plans);
    if (!container || !companyName) return;
    window.ERM_COMPANY = companyName;
    const user = window.ERM_USER;
    container.querySelectorAll(".action-card").forEach((card, i) => {
      const item = plans.action_items[i];
      if (!item) return;
      const body = card.querySelector(".action-body");
      if (!body) return;
      const st = item.status_label || item.status;
      if (st) {
        const badge = document.createElement("p");
        badge.innerHTML = `<strong>状态：</strong><span class="wf-status wf-${item.status || "open"}">${this.escapeHtml(st)}</span>`
          + (item.approver ? ` · 审批 ${this.escapeHtml(item.approver)}` : "")
          + (item.owner ? ` · 责任人 ${this.escapeHtml(item.owner)}` : "");
        body.appendChild(badge);
      }
      if (!user || !user.can_write) return;
      const btn = document.createElement("button");
      btn.className = "btn btn-outline btn-sm wf-btn";
      btn.style.marginTop = "8px";
      const high = item.priority === "P0" || item.requires_approval;
      if (high && !(user && user.can_approve)) {
        btn.disabled = true;
        btn.textContent = "P0 关闭需审批人";
      } else {
        btn.innerHTML = high ? '<i class="fas fa-stamp"></i> 审批关闭' : '<i class="fas fa-check"></i> 标记已完成';
        btn.dataset.wfKind = "action";
        btn.dataset.wfId = item.id;
        btn.dataset.wfStatus = "closed";
        btn.dataset.wfHigh = high ? "1" : "0";
      }
      body.appendChild(btn);
    });
    this.bindWorkflowClicks(companyName, onUpdate);
  },

  async applyWorkflow(result) {
    if (!result?.company_name) return result;
    window.ERM_COMPANY = result.company_name;
    try {
      const resp = await fetch("/api/workflow?company=" + encodeURIComponent(result.company_name));
      if (!resp.ok) return result;
      const snap = await resp.json();
      const actMap = {};
      (snap.actions || []).forEach(a => { actMap[a.id] = a; });
      const regMap = {};
      (snap.register || []).forEach(r => { regMap[r.id] = r; });
      (result.action_plans?.action_items || []).forEach(a => {
        const st = actMap[a.id];
        if (st) Object.assign(a, st);
      });
      const reg = result.deep_analysis?.risk_register || result.analytics?.deep_analysis?.risk_register;
      (reg || []).forEach(r => {
        const st = regMap[r.id];
        if (st) {
          r.workflow_status = st.status;
          r.workflow_status_label = st.status_label;
          r.approver = st.approver;
          r.requires_approval = st.requires_approval;
          r.owner = st.owner || r.owner;
        }
      });
      if (result.closed_loop) {
        result.closed_loop.workflow = snap.completion;
        const v = result.closed_loop.remediation_verification || {};
        v.actions_tracked = Object.assign({}, v.actions_tracked || {}, snap.completion, { source: "persisted" });
        result.closed_loop.remediation_verification = v;
      }
    } catch (_) {}
    return result;
  },

  bindWorkflowClicks(companyName, onUpdate) {
    if (companyName) window.ERM_COMPANY = companyName;
    if (onUpdate) window.ERM_WF_ONUPDATE = onUpdate;
    if (this._wfBound) return;
    this._wfBound = true;
    document.addEventListener("click", async (ev) => {
      const btn = ev.target.closest?.(".wf-btn");
      if (!btn) return;
      const company = window.ERM_COMPANY;
      const id = btn.dataset.wfId;
      const kind = btn.dataset.wfKind || "register";
      const status = btn.dataset.wfStatus;
      const high = btn.dataset.wfHigh === "1";
      if (!company || !id || !status) return;
      let reason = "";
      let review_date = "";
      if (high && (status === "closed" || status === "accepted" || status === "completed")) {
        reason = window.prompt("接受/关闭理由（必填）", "") || "";
        if (!reason.trim()) { this.toast("P0/高风险关闭必须填写理由", "error"); return; }
        review_date = window.prompt("复评日期（必填，如 2026-11-21）", "") || "";
        if (!review_date.trim()) { this.toast("P0/高风险关闭必须填写复评日期", "error"); return; }
      }
      try {
        const url = kind === "action" ? "/api/actions/track" : "/api/workflow/status";
        const body = kind === "action"
          ? { company_name: company, action_id: id, status, note: reason, reason, review_date, priority: high ? "P0" : "P1" }
          : { company_name: company, item_id: id, kind, status, reason, review_date, priority: high ? "P0" : "P1" };
        const resp = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        const json = await resp.json();
        if (!resp.ok) throw new Error(json.error || "操作失败");
        this.toast(status === "treating" ? "已标为应对中" : "状态已更新", "success");
        if (window.ERM_WF_ONUPDATE) window.ERM_WF_ONUPDATE(json);
      } catch (e) { this.toast(e.message, "error"); }
    });
  },

  bindExportButtons(container, getFormData) {
    container.querySelectorAll("[data-export]").forEach(btn => {
      btn.onclick = async () => {
        const orig = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        try {
          await this.exportReport(await getFormData(), btn.dataset.export);
          this.toast("导出成功", "success");
        } catch (e) {
          this.toast(e.message, "error");
        } finally {
          btn.disabled = false;
          btn.innerHTML = orig;
        }
      };
    });
  },

  initHistorySidebar(selectId, onLoad) {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    const populate = (records) => {
      sel.innerHTML = '<option value="">— 评估档案 —</option>';
      (records || []).forEach(r => {
        const opt = document.createElement("option");
        opt.value = r.id;
        const isDemo = (r.company_name || "").startsWith("DEMO-") || (r.note || "").includes("演示");
        const demoMark = isDemo ? "演示 · " : "";
        opt.textContent = `${demoMark}${r.company_name} · ${r.overall_score?.toFixed(2) ?? "--"} · ${r.assessed_at?.slice(0, 10) || ""}`;
        sel.appendChild(opt);
      });
    };
    this.fetchHistory().then(populate).catch(() => populate([]));
    const demoParam = new URLSearchParams(location.search).get("demo");
    if (demoParam) {
      this.loadDemoArchive(demoParam).then((a) => { if (onLoad) onLoad(a); }).catch(() => {});
    }
    sel.onchange = async () => {
      if (!sel.value) return;
      try {
        const record = await this.loadHistoryRecord(sel.value);
        if (record.assessment) {
          this.setAssessment(record.assessment, sel.value);
          if (onLoad) onLoad(record.assessment);
          this.toast(`已加载：${record.company_name}`, "success");
        }
      } catch (e) {
        this.toast(e.message, "error");
      }
    };
  },

  _notifyPollTimer: null,

  async fetchNotifications(unreadOnly = false) {
    const url = `/api/notifications${unreadOnly ? "?unread=1" : ""}`;
    const resp = await fetch(url);
    if (!resp.ok) return { notifications: [], unread_count: 0 };
    return resp.json();
  },

  async markNotificationsRead(ids = null, markAll = false) {
    await fetch("/api/notifications/read", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids, mark_all: markAll }),
    });
  },

  renderNotificationList(items) {
    const list = document.getElementById("notifyList");
    if (!list) return;
    if (!items?.length) {
      list.innerHTML = '<li style="color:#888;padding:20px;text-align:center;">暂无告警通知</li>';
      return;
    }
    list.innerHTML = items.slice(0, 20).map(n => `
      <li class="${n.read ? "" : "unread"} notify-sev-${this.escapeHtml(n.severity || "medium")}" data-id="${this.escapeHtml(n.id)}">
        <div class="notify-title">${this.escapeHtml(n.title || "")}</div>
        <div>${this.escapeHtml(n.message || "")}</div>
        <div class="notify-meta">${this.escapeHtml(n.company_name || "")} · ${this.escapeHtml((n.created_at || "").slice(0, 16))}</div>
      </li>`).join("");
    list.querySelectorAll("li[data-id]").forEach(li => {
      li.onclick = async () => {
        await this.markNotificationsRead([li.dataset.id]);
        li.classList.remove("unread");
        this.refreshNotificationBadge();
      };
    });
  },

  async refreshNotificationBadge() {
    const data = await this.fetchNotifications();
    const badge = document.getElementById("notifyBadge");
    const count = data.unread_count || 0;
    if (badge) {
      badge.textContent = count > 99 ? "99+" : String(count);
      badge.style.display = count > 0 ? "flex" : "none";
    }
    this.renderNotificationList(data.notifications || []);
    return data;
  },

  pushBrowserNotifications(alerts, companyName) {
    if (!alerts?.alerts?.length) return;
    if (!("Notification" in window)) return;
    const cfg = localStorage.getItem("erm_notify_browser");
    if (cfg === "off") return;
    const show = () => {
      alerts.alerts.slice(0, 3).forEach(a => {
        try {
          new Notification(a.title || "风险告警", {
            body: `${companyName || ""}: ${a.message || ""}`,
            tag: a.id || "erm-alert",
          });
        } catch (_) {}
      });
    };
    if (Notification.permission === "granted") show();
    else if (Notification.permission !== "denied") {
      Notification.requestPermission().then(p => { if (p === "granted") show(); });
    }
  },

  initNotificationCenter() {
    const btn = document.getElementById("btnNotify");
    const dropdown = document.getElementById("notifyDropdown");
    const readAll = document.getElementById("btnNotifyReadAll");
    if (!btn) return;

    btn.onclick = (e) => {
      e.stopPropagation();
      const open = dropdown.style.display !== "none";
      dropdown.style.display = open ? "none" : "block";
      if (!open) this.refreshNotificationBadge();
    };
    document.addEventListener("click", () => { if (dropdown) dropdown.style.display = "none"; });
    dropdown?.addEventListener("click", e => e.stopPropagation());

    readAll?.addEventListener("click", async () => {
      await this.markNotificationsRead(null, true);
      await this.refreshNotificationBadge();
    });

    this.refreshNotificationBadge();
    clearInterval(this._notifyPollTimer);
    this._notifyPollTimer = setInterval(() => this.refreshNotificationBadge(), 60000);

    if ("Notification" in window && Notification.permission === "default") {
      setTimeout(() => {
        Notification.requestPermission().then(p => {
          if (p === "granted") localStorage.setItem("erm_notify_browser", "on");
        });
      }, 3000);
    }
  },

  async registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    try {
      const reg = await navigator.serviceWorker.register(ermUrl("/static/sw.js"));
      const deviceId = localStorage.getItem("erm_device_id") || ("web-" + Math.random().toString(36).slice(2, 10));
      localStorage.setItem("erm_device_id", deviceId);
      await fetch("/api/notifications/devices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: deviceId,
          platform: "web",
          device_name: navigator.userAgent.includes("Mobile") ? "移动浏览器" : "桌面浏览器",
        }),
      });
      return reg;
    } catch (_) {}
  },

  async registerMobileDevice(token, platform, companyFilter) {
    const resp = await fetch("/api/notifications/devices", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        platform: platform || "mobile",
        device_name: platform + " 客户端",
        company_filter: companyFilter || "",
      }),
    });
    const json = await resp.json();
    if (!resp.ok) throw new Error(json.error || "注册失败");
    return json.device;
  },
};
window.ERM = ERM;
