const state = {
  file: null,
  auditResult: null,
  generateReport: false,
};

let DOM = {};

function initFileUpload() {
  DOM.selectBtn.addEventListener("click", () => {
    console.log("button clicked");
    DOM.fileInput.click();
  });

  DOM.fileInput.addEventListener("change", handleFileSelect);
  DOM.clearFileBtn.addEventListener("click", clearFile);

  DOM.uploadArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    DOM.uploadArea.classList.add("drag-over");
  });

  DOM.uploadArea.addEventListener("dragleave", () => {
    DOM.uploadArea.classList.remove("drag-over");
  });

  DOM.uploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    DOM.uploadArea.classList.remove("drag-over");
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      DOM.fileInput.files = files;
      handleFileSelect();
    }
  });
}

function handleFileSelect() {
  console.log("change event fired");

  const file = DOM.fileInput.files[0];

  console.log("selected file:", file);

  if (!file) {
    console.log("no file found");
    return;
  }

  if (!file.name.endsWith(".csv")) {
    console.log("not csv");
    showError("Please select a CSV file.");
    return;
  }

  console.log("valid csv selected");

  state.file = file;

  // Update UI
  DOM.uploadArea.style.display = "none";
  DOM.fileInfo.style.display = "block";
  DOM.fileName.textContent = `📋 ${file.name}`;
  DOM.optionsSection.style.display = "block";
  DOM.actionButtons.style.display = "block";

  console.log("UI updated successfully");
}

function clearFile() {
  state.file = null;
  DOM.fileInput.value = "";
  DOM.uploadArea.style.display = "block";
  DOM.fileInfo.style.display = "none";
  DOM.optionsSection.style.display = "none";
  DOM.actionButtons.style.display = "none";
}
function initOptions() {
  DOM.generateReportCheckbox.addEventListener("change", (e) => {
    state.generateReport = e.target.checked;
  });
}

function initAuditButton() {
  DOM.auditBtn.addEventListener("click", runAudit);
}

async function runAudit() {
  if (!state.file) {
    showError("Please select a file first.");
    return;
  }

  showLoading(true, "Processing your data...");
  hideError();

  try {
    const formData = new FormData();
    formData.append("file", state.file);
    formData.append("rules", "{}");
    formData.append("generate_report", "false");

    const auditResponse = await fetch("/audit", {
      method: "POST",
      body: formData,
    });

    if (!auditResponse.ok) {
      const error = await auditResponse.json();
      throw new Error(error.detail || "Audit failed");
    }

    const auditResult = await auditResponse.json();
    state.auditResult = auditResult;

    showLoading(false);
    showResults();
    renderResults(auditResult);

    if (state.generateReport) {
      streamReport(auditResult);
    }
  } catch (error) {
    showLoading(false);
    showError(error.message);
    console.error("Audit error:", error);
  }
}

async function streamReport(auditResult) {
  const { filename, profile, issues, anomalies, score } = auditResult;

  switchTab("report");
  DOM.reportLoading.style.display = "block";
  DOM.reportContent.textContent = "";

  try {
    const response = await fetch("/audit/report/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        filename,
        profile,
        issues,
        anomalies,
        score,
      }),
    });

    if (!response.ok) {
      throw new Error("Report streaming failed");
    }

    // Consume Server-Sent Events
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // Keep last incomplete line

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6)); // Remove 'data: '
            if (data.chunk) {
              appendToReport(data.chunk);
            }
          } catch (e) {
            console.warn("Failed to parse SSE chunk:", e);
          }
        }
      }
    }

    if (buffer.startsWith("data: ")) {
      try {
        const data = JSON.parse(buffer.slice(6));
        if (data.chunk) {
          appendToReport(data.chunk);
        }
      } catch (e) {
        console.warn("Failed to parse final SSE chunk:", e);
      }
    }

    DOM.reportLoading.style.display = "none";
  } catch (error) {
    DOM.reportLoading.style.display = "none";
    DOM.reportContent.textContent = `Error generating report: ${error.message}`;
    console.error("Report streaming error:", error);
  }
}

function appendToReport(chunk) {
  DOM.reportContent.textContent += chunk;
  // Auto-scroll to bottom
  DOM.reportContent.parentElement.scrollTop =
    DOM.reportContent.parentElement.scrollHeight;
}

// ── Results Rendering ──────────────────────────────────────────────────
function renderResults(result) {
  renderScore(result.score);
  renderDimensions(result.score.dimension_scores);
  renderDatasetInfo(result);
  renderIssueSummary(result.issue_stats);
  renderIssuesList(result.issues);
  renderAnomaliesList(result);
  renderProfile(result.profile);
}

function renderScore(score) {
  const { score: points, grade, verdict } = score;

  // Score circle color based on grade
  const colors = {
    A: "#10b981", // green
    B: "#3b82f6", // blue
    C: "#f59e0b", // amber
    D: "#f97316", // orange
    F: "#ef4444", // red
  };

  DOM.scoreDisplay.innerHTML = `
        <div class="score-circle" style="background-color: ${colors[grade]};">
            ${points}
        </div>
        <div class="score-details">
            <div class="score-grade">Grade: <strong>${grade}</strong></div>
            <div class="score-verdict">${verdict}</div>
        </div>
    `;
}

function renderDimensions(dims) {
  DOM.dimensionScores.innerHTML = Object.entries(dims)
    .map(
      ([key, value]) => `
        <div class="dimension-item">
            <span class="dimension-label">${formatLabel(key)}</span>
            <div class="dimension-bar">
                <div class="dimension-fill" style="width: ${value}%;"></div>
            </div>
            <span class="dimension-score">${value}</span>
        </div>
    `,
    )
    .join("");
}

function renderDatasetInfo(result) {
  DOM.datasetInfo.innerHTML = `
        <div class="info-item">
            <div class="info-label">Rows</div>
            <div class="info-value">${result.rows.toLocaleString()}</div>
        </div>
        <div class="info-item">
            <div class="info-label">Columns</div>
            <div class="info-value">${result.columns}</div>
        </div>
        <div class="info-item">
            <div class="info-label">File</div>
            <div class="info-value" style="font-size: 0.9rem; word-break: break-all;">${result.filename}</div>
        </div>
    `;
}

function renderIssueSummary(stats) {
  const { by_severity } = stats;

  DOM.issueSummary.innerHTML = `
        <div class="summary-block critical">
            <div class="summary-count">${by_severity.critical || 0}</div>
            <div class="summary-label">Critical Issues</div>
        </div>
        <div class="summary-block warning">
            <div class="summary-count">${by_severity.warning || 0}</div>
            <div class="summary-label">Warnings</div>
        </div>
        <div class="summary-block info">
            <div class="summary-count">${by_severity.info || 0}</div>
            <div class="summary-label">Info Messages</div>
        </div>
    `;
}

function renderIssuesList(issues) {
  if (!issues.length) {
    DOM.issuesList.innerHTML =
      '<p style="text-align: center; color: #10b981; padding: 2rem;">✓ No issues found!</p>';
    return;
  }

  DOM.issuesList.innerHTML = issues
    .slice(0, 20)
    .map(
      (issue) => `
        <div class="issue-item ${issue.severity}">
            <div class="issue-header">
                <div class="issue-type">${formatLabel(issue.type)}</div>
                <div style="display: flex; gap: 0.5rem;">
                    <span class="issue-badge ${issue.severity}">${issue.severity}</span>
                    <span class="issue-column">${issue.column || "ALL"}</span>
                </div>
            </div>
            <div class="issue-detail">${issue.detail}</div>
            <div class="issue-stats">
                <div class="issue-stat"><strong>Count:</strong> ${issue.count}</div>
                <div class="issue-stat"><strong>Percentage:</strong> ${issue.pct}%</div>
            </div>
        </div>
    `,
    )
    .join("");
}

function renderAnomaliesList(result) {
  const { anomalies } = result;
  const anomalyItems = [];

  // Per-column anomalies
  for (const anomaly of anomalies.per_column || []) {
    anomalyItems.push({
      type: "column",
      column: anomaly.column,
      method: anomaly.method,
      count: anomaly.outlier_count,
      pct: anomaly.outlier_pct,
      stats: anomaly.stats,
    });
  }

  // Multivariate anomalies
  for (const [method, data] of Object.entries(anomalies.multivariate || {})) {
    if (data.count > 0) {
      anomalyItems.push({
        type: "multivariate",
        method: method.replace(/_/g, " "),
        count: data.count,
        pct: data.pct,
      });
    }
  }

  if (!anomalyItems.length) {
    DOM.anomaliesList.innerHTML =
      '<p style="text-align: center; color: #10b981; padding: 2rem;">✓ No anomalies detected!</p>';
    return;
  }

  DOM.anomaliesList.innerHTML = anomalyItems
    .map(
      (item) => `
        <div class="anomaly-item">
            <div class="anomaly-header">
                <div>
                    <div class="anomaly-title">${item.column || "Multivariate"}</div>
                    <div class="anomaly-method">${item.method}</div>
                </div>
            </div>
            <div class="anomaly-stats">
                <div class="anomaly-stat">
                    <div class="anomaly-stat-label">Outliers</div>
                    <div class="anomaly-stat-value">${item.count}</div>
                </div>
                <div class="anomaly-stat">
                    <div class="anomaly-stat-label">% of Data</div>
                    <div class="anomaly-stat-value">${item.pct}%</div>
                </div>
                ${
                  item.stats
                    ? `
                    <div class="anomaly-stat">
                        <div class="anomaly-stat-label">Mean</div>
                        <div class="anomaly-stat-value">${item.stats.mean}</div>
                    </div>
                    <div class="anomaly-stat">
                        <div class="anomaly-stat-label">Std Dev</div>
                        <div class="anomaly-stat-value">${item.stats.std}</div>
                    </div>
                `
                    : ""
                }
            </div>
        </div>
    `,
    )
    .join("");
}

function renderProfile(profile) {
  DOM.profileColumns.innerHTML = profile
    .map(
      (col) => `
        <div class="profile-card">
            <div class="profile-header">
                <div class="profile-name">${col.column}</div>
                <span class="profile-type">${col.inferred_type}</span>
            </div>
            <div>
                ${renderProfileStats(col)}
            </div>
        </div>
    `,
    )
    .join("");
}

function renderProfileStats(col) {
  let stats = `
        <div class="profile-stat">
            <span class="profile-label">Total</span>
            <span class="profile-value">${col.total}</span>
        </div>
        <div class="profile-stat">
            <span class="profile-label">Null %</span>
            <span class="profile-value">${col.null_pct}%</span>
        </div>
        <div class="profile-stat">
            <span class="profile-label">Unique</span>
            <span class="profile-value">${col.unique_count}</span>
        </div>
    `;

  if (col.mean !== undefined) {
    stats += `
            <div class="profile-stat">
                <span class="profile-label">Mean</span>
                <span class="profile-value">${col.mean}</span>
            </div>
            <div class="profile-stat">
                <span class="profile-label">Std Dev</span>
                <span class="profile-value">${col.std}</span>
            </div>
            <div class="profile-stat">
                <span class="profile-label">Min/Max</span>
                <span class="profile-value">${col.min} / ${col.max}</span>
            </div>
        `;
  }

  return stats;
}

function initTabs() {
  DOM.tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabName = btn.getAttribute("data-tab");
      switchTab(tabName);
    });
  });
}

function switchTab(tabName) {
  // Deactivate all tabs
  DOM.tabButtons.forEach((btn) => btn.classList.remove("active"));
  DOM.tabContents.forEach((content) => content.classList.remove("active"));

  // Activate selected tab
  document.querySelector(`[data-tab="${tabName}"]`).classList.add("active");
  document.getElementById(`${tabName}-tab`).classList.add("active");
}

function showLoading(show, message = "Loading...") {
  DOM.loadingState.style.display = show ? "block" : "none";
  if (message) DOM.loadingText.textContent = message;
}

function showResults() {
  DOM.resultsSection.style.display = "block";
}

function showError(message) {
  DOM.errorMessage.textContent = message;
  DOM.errorAlert.style.display = "block";
}

function hideError() {
  DOM.errorAlert.style.display = "none";
}

function formatLabel(str) {
  return str.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function init() {
  DOM = {
    fileInput: document.getElementById("file-input"),
    uploadArea: document.getElementById("upload-area"),
    uploadHint: document.getElementById("upload-hint"),
    selectBtn: document.getElementById("select-btn"),
    fileInfo: document.getElementById("file-info"),
    fileName: document.getElementById("file-name"),
    clearFileBtn: document.getElementById("clear-file-btn"),

    optionsSection: document.getElementById("options-section"),
    generateReportCheckbox: document.getElementById("generate-report-checkbox"),

    actionButtons: document.getElementById("action-buttons"),
    auditBtn: document.getElementById("audit-btn"),

    loadingState: document.getElementById("loading-state"),
    loadingText: document.getElementById("loading-text"),
    errorAlert: document.getElementById("error-alert"),
    errorMessage: document.getElementById("error-message"),

    resultsSection: document.getElementById("results-section"),
    tabButtons: document.querySelectorAll(".tab-button"),
    tabContents: document.querySelectorAll(".tab-content"),

    scoreDisplay: document.getElementById("score-display"),
    datasetInfo: document.getElementById("dataset-info"),
    issueSummary: document.getElementById("issue-summary"),
    dimensionScores: document.getElementById("dimension-scores"),
    issuesList: document.getElementById("issues-list"),
    anomaliesList: document.getElementById("anomalies-list"),
    profileColumns: document.getElementById("profile-columns"),
    reportContent: document.getElementById("report-content"),
    reportLoading: document.getElementById("report-loading"),
  };

  console.log("App initialized");

  initFileUpload();
  initOptions();
  initAuditButton();
  initTabs();
}
document.addEventListener("DOMContentLoaded", () => {
  init();
});
