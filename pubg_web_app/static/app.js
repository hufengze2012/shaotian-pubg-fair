const players = Array.isArray(window.__PLAYERS__) ? window.__PLAYERS__ : [];

const playerPicker = document.getElementById("player-picker");
const teamAPicker = document.getElementById("team-a-picker");
const playerHint = document.getElementById("player-hint");
const modeInputs = document.querySelectorAll("input[name='mode']");
const individualBox = document.getElementById("individual-box");
const teamBox = document.getElementById("team-box");
const individualHandicaps = document.getElementById("individual-handicaps");
const refreshToggle = document.getElementById("refresh-toggle");
const teamHandicapA = document.getElementById("team-handicap-a");
const teamHandicapB = document.getElementById("team-handicap-b");
const form = document.getElementById("control-form");
const formError = document.getElementById("form-error");
const submitBtn = document.getElementById("submit-btn");
const resultRoot = document.getElementById("result-root");
const resultEmpty = document.getElementById("result-empty");
const loading = document.getElementById("loading");

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function isHalfStep(value) {
  return Math.abs(value * 2 - Math.round(value * 2)) < 1e-9;
}

function getSelectedPlayers() {
  return [...playerPicker.querySelectorAll("input[type='checkbox']:checked")].map((x) => x.value);
}

function getCurrentMode() {
  const checked = [...modeInputs].find((item) => item.checked);
  return checked ? checked.value : "individual";
}

function renderPlayerPicker() {
  playerPicker.innerHTML = players
    .map(
      (name) => `
      <label class="chip">
        <input type="checkbox" value="${escapeHtml(name)}">
        <span>${escapeHtml(name)}</span>
      </label>
    `
    )
    .join("");

  playerPicker.addEventListener("change", (event) => {
    const selected = getSelectedPlayers();
    if (selected.length > 4) {
      event.target.checked = false;
      showFormError("参赛玩家最多选 4 人。");
      return;
    }
    clearFormError();
    syncBySelection();
  });
}

function renderIndividualHandicaps(selected) {
  individualHandicaps.innerHTML = selected
    .map(
      (name) => `
      <div class="handicap-row">
        <label for="h-${escapeHtml(name)}">${escapeHtml(name)}</label>
        <input id="h-${escapeHtml(name)}" data-player="${escapeHtml(name)}" type="number" step="0.5" min="0" value="0">
      </div>
    `
    )
    .join("");
}

function renderTeamPicker(selected) {
  teamAPicker.innerHTML = selected
    .map(
      (name) => `
      <label class="chip">
        <input type="checkbox" value="${escapeHtml(name)}">
        <span>${escapeHtml(name)}</span>
      </label>
    `
    )
    .join("");
}

function syncBySelection() {
  const selected = getSelectedPlayers();
  playerHint.textContent = `已选 ${selected.length}/4`;
  renderIndividualHandicaps(selected);
  renderTeamPicker(selected);
}

function syncModeView() {
  const mode = getCurrentMode();
  if (mode === "individual") {
    individualBox.classList.remove("hidden");
    teamBox.classList.add("hidden");
  } else {
    individualBox.classList.add("hidden");
    teamBox.classList.remove("hidden");
  }
}

function showFormError(message) {
  formError.textContent = message;
  formError.classList.remove("hidden");
}

function clearFormError() {
  formError.textContent = "";
  formError.classList.add("hidden");
}

function buildPayload() {
  const selected = getSelectedPlayers();
  if (selected.length !== 4) {
    throw new Error("请先选择 4 名参赛玩家。");
  }

  const payload = {
    selected_names: selected,
    mode: getCurrentMode(),
    refresh: refreshToggle.checked,
  };

  if (payload.mode === "individual") {
    const handicapInputs = [...individualHandicaps.querySelectorAll("input[data-player]")];
    const handicaps = {};
    for (const input of handicapInputs) {
      const player = input.dataset.player;
      const value = Number(input.value);
      if (Number.isNaN(value) || value < 0 || !isHalfStep(value)) {
        throw new Error(`${player} 的个人让分必须是 >=0 的 0.5 倍数。`);
      }
      handicaps[player] = value;
    }
    payload.individual_handicaps = handicaps;
    return payload;
  }

  const teamA = [...teamAPicker.querySelectorAll("input:checked")].map((x) => x.value);
  if (teamA.length !== 2) {
    throw new Error("组队模式下，A 队必须选择 2 人。");
  }
  const hA = Number(teamHandicapA.value);
  const hB = Number(teamHandicapB.value);
  if (Number.isNaN(hA) || Number.isNaN(hB) || hA < 0 || hB < 0 || !isHalfStep(hA) || !isHalfStep(hB)) {
    throw new Error("队伍让分必须是 >=0 的 0.5 倍数。");
  }
  if (hA > 0 && hB > 0) {
    throw new Error("规则限制：A 队和 B 队不能同时让分。");
  }

  payload.team_a = teamA;
  payload.team_handicap_a = hA;
  payload.team_handicap_b = hB;
  return payload;
}

function renderEvaluation(title, selectedNames, block) {
  const rows = selectedNames
    .map((name) => {
      const total = Number(block.totals[name] ?? 0).toFixed(2);
      const avg = Number(block.avgs[name] ?? 0).toFixed(2);
      return `<tr><td>${escapeHtml(name)}</td><td>${total}</td><td>${avg}</td></tr>`;
    })
    .join("");

  return `
    <div class="result-block">
      <h3>${escapeHtml(title)}</h3>
      <table>
        <thead>
          <tr><th>玩家</th><th>总分</th><th>均分</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
      <p class="stat-line">分差(max-min): ${Number(block.gap ?? 0).toFixed(2)}</p>
      <p class="stat-line">方差: ${Number(block.var ?? 0).toFixed(4)}</p>
    </div>
  `;
}

function renderProfile(profileRows) {
  const rows = profileRows
    .map(
      (row) => `
      <tr>
        <td>${escapeHtml(row.name)}</td>
        <td>${Number(row.global_avg).toFixed(2)}</td>
        <td>${Number(row.together_avg).toFixed(2)}</td>
        <td>${Number(row.together_count).toFixed(0)}</td>
      </tr>
    `
    )
    .join("");
  return `
    <div class="result-block">
      <h3>历史击杀画像</h3>
      <table>
        <thead>
          <tr><th>玩家</th><th>全局平均击杀</th><th>四人同局平均击杀</th><th>四人同局场次</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function renderNoData(data) {
  const refresh = data.refresh
    ? `<p class="stat-line">刷新结果: 分片=${escapeHtml(data.refresh.shard)}, 四人同局候选=${data.refresh.common_candidates}, 缓存命中=${data.refresh.cache_hits}, 新拉取=${data.refresh.detail_requests}</p>`
    : "";

  const diagnostics = data.diagnostics
    ? `
      <div class="result-block">
        <h3>无数据诊断</h3>
        <p class="stat-line">${escapeHtml(data.diagnostics.reason)}</p>
        <p class="stat-line">每人最近比赛条数:</p>
        ${Object.entries(data.diagnostics.player_match_counts || {})
          .map(([name, count]) => `<p class="stat-line">${escapeHtml(name)}: ${count}</p>`)
          .join("")}
        <p class="stat-line">两两同局重合:</p>
        ${Object.entries(data.diagnostics.pair_overlaps || {})
          .map(([pair, count]) => `<p class="stat-line">${escapeHtml(pair)}: ${count}</p>`)
          .join("")}
      </div>
    `
    : "";

  resultRoot.innerHTML = `
    <div class="result-block">
      <h3>暂无同局数据</h3>
      <p class="stat-line">${escapeHtml(data.error || "未找到可用数据")}</p>
      ${refresh}
    </div>
    ${diagnostics}
  `;
}

function renderResult(data) {
  if (!data.ok) {
    renderNoData(data);
    return;
  }

  const refresh = data.refresh
    ? `
      <div class="result-block">
        <h3>刷新概况</h3>
        <p class="stat-line">分片: ${escapeHtml(data.refresh.shard)}</p>
        <p class="stat-line">四人同局候选: ${data.refresh.common_candidates}</p>
        <p class="stat-line">缓存命中: ${data.refresh.cache_hits}</p>
        <p class="stat-line">新拉取: ${data.refresh.detail_requests}</p>
      </div>
    `
    : "";

  let teamInfo = "";
  if (data.mode === "team" && data.team) {
    teamInfo = `
      <div class="result-block">
        <h3>分队</h3>
        <p class="stat-line">A队: ${escapeHtml(data.team.A.join(" / "))}</p>
        <p class="stat-line">B队: ${escapeHtml(data.team.B.join(" / "))}</p>
      </div>
    `;
  }

  const manualTitle = data.mode === "team" ? "当前队伍让分结果" : "当前个人让分结果";
  const suggestionTitle = data.mode === "team" ? "建议队伍让分结果" : "建议个人让分结果";

  const manualHandicaps = Object.entries(data.manual.handicaps || {})
    .map(([k, v]) => `${escapeHtml(k)}: ${Number(v).toFixed(2)}`)
    .join(" | ");
  const suggestHandicaps = Object.entries(data.suggestion.handicaps || {})
    .map(([k, v]) => `${escapeHtml(k)}: ${Number(v).toFixed(2)}`)
    .join(" | ");

  resultRoot.innerHTML = `
    <div class="result-block">
      <h3>样本概况</h3>
      <p class="stat-line">四人同局样本: ${data.meta.sample_count} 场</p>
      <p class="stat-line">目标样本: ${data.meta.target_matches} 场</p>
    </div>
    ${refresh}
    ${teamInfo}
    ${renderProfile(data.profile || [])}
    <div class="result-block">
      <h3>让分输入</h3>
      <p class="stat-line">${manualHandicaps || "无"}</p>
    </div>
    ${renderEvaluation(manualTitle, data.selected_names, data.manual.evaluation)}
    <div class="result-block">
      <h3>推荐让分</h3>
      <p class="stat-line">${suggestHandicaps || "无"}</p>
    </div>
    ${renderEvaluation(suggestionTitle, data.selected_names, data.suggestion.evaluation)}
  `;
}

async function submitForm(event) {
  event.preventDefault();
  clearFormError();
  submitBtn.disabled = true;
  loading.classList.remove("hidden");
  resultEmpty.classList.add("hidden");
  resultRoot.classList.remove("hidden");
  resultRoot.innerHTML = "";

  try {
    const payload = buildPayload();
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok && !data.ok) {
      throw new Error(data.error || "请求失败");
    }
    renderResult(data);
  } catch (error) {
    showFormError(error.message || "请求失败");
    resultRoot.classList.add("hidden");
    resultEmpty.classList.remove("hidden");
  } finally {
    submitBtn.disabled = false;
    loading.classList.add("hidden");
  }
}

function bindEvents() {
  teamAPicker.addEventListener("change", (event) => {
    const picks = [...teamAPicker.querySelectorAll("input:checked")];
    if (picks.length > 2) {
      event.target.checked = false;
      showFormError("A 队只能选 2 人。");
    } else {
      clearFormError();
    }
  });
  modeInputs.forEach((item) => {
    item.addEventListener("change", () => {
      clearFormError();
      syncModeView();
    });
  });
  form.addEventListener("submit", submitForm);
}

renderPlayerPicker();
syncBySelection();
syncModeView();
bindEvents();
