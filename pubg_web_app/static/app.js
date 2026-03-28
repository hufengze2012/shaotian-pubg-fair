let players = Array.isArray(window.__PLAYERS__) ? [...window.__PLAYERS__] : [];
const appBasePath = typeof window.__APP_BASE_PATH__ === "string" ? window.__APP_BASE_PATH__ : "";

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
const addPlayerBtn = document.getElementById("add-player-btn");
const addPlayerBox = document.getElementById("add-player-box");
const newPlayerName = document.getElementById("new-player-name");
const savePlayerBtn = document.getElementById("save-player-btn");
const addPlayerMessage = document.getElementById("add-player-message");

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function withBasePath(path) {
  return `${appBasePath}${path}`;
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

function showAddPlayerMessage(message, isError = false) {
  addPlayerMessage.textContent = message;
  addPlayerMessage.classList.remove("hidden");
  addPlayerMessage.classList.toggle("error", isError);
}

function clearAddPlayerMessage() {
  addPlayerMessage.textContent = "";
  addPlayerMessage.classList.add("hidden");
  addPlayerMessage.classList.remove("error");
}

function getIndividualHandicapSnapshot() {
  const result = {};
  const inputs = [...individualHandicaps.querySelectorAll("input[data-player]")];
  for (const input of inputs) {
    result[input.dataset.player] = input.value;
  }
  return result;
}

function getTeamSelectionSnapshot() {
  return [...teamAPicker.querySelectorAll("input:checked")].map((x) => x.value);
}

function renderPlayerPicker(selectedNames = []) {
  playerPicker.innerHTML = players
    .map(
      (name) => `
      <label class="chip">
        <input type="checkbox" value="${escapeHtml(name)}" ${selectedNames.includes(name) ? "checked" : ""}>
        <span>${escapeHtml(name)}</span>
      </label>
    `
    )
    .join("");
}

function renderIndividualHandicaps(selected, handicapSnapshot = {}) {
  individualHandicaps.innerHTML = selected
    .map(
      (name) => `
      <div class="handicap-row">
        <label for="h-${escapeHtml(name)}">${escapeHtml(name)}</label>
        <input id="h-${escapeHtml(name)}" data-player="${escapeHtml(name)}" type="number" step="0.5" min="0" value="${escapeHtml(handicapSnapshot[name] ?? "0")}">
      </div>
    `
    )
    .join("");
}

function renderTeamPicker(selected, teamSelected = []) {
  teamAPicker.innerHTML = selected
    .map(
      (name) => `
      <label class="chip">
        <input type="checkbox" value="${escapeHtml(name)}" ${teamSelected.includes(name) ? "checked" : ""}>
        <span>${escapeHtml(name)}</span>
      </label>
    `
    )
    .join("");
}

function syncBySelection() {
  const selected = getSelectedPlayers();
  playerHint.textContent = `已选 ${selected.length} 人`;
  const handicapSnapshot = getIndividualHandicapSnapshot();
  const teamSelected = getTeamSelectionSnapshot().filter((name) => selected.includes(name));
  renderIndividualHandicaps(selected, handicapSnapshot);
  renderTeamPicker(selected, teamSelected);
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

function rerenderPlayerControls(selectedNames = []) {
  renderPlayerPicker(selectedNames);
  syncBySelection();
}

function buildPayload() {
  const selected = getSelectedPlayers();
  if (selected.length < 2 || selected.length > 4) {
    throw new Error("请选择 2-4 名参赛玩家。");
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
  if (teamA.length < 1 || teamA.length >= selected.length) {
    throw new Error("A 队至少选 1 人，且不能包含所有玩家。");
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
      <div class="result-head">
        <h3>${escapeHtml(title)}</h3>
        <span class="tag alt">分差 ${Number(block.gap ?? 0).toFixed(2)}</span>
      </div>
      <div class="table-shell">
        <table>
          <thead>
            <tr><th>玩家</th><th>总分</th><th>均分</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
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
      <div class="result-head">
        <h3>历史击杀画像</h3>
        <span class="tag">同局画像</span>
      </div>
      <div class="table-shell">
        <table>
          <thead>
            <tr><th>玩家</th><th>全局平均击杀</th><th>同局平均击杀</th><th>同局场次</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
  `;
}

function renderMetrics(data) {
  const refresh = data.refresh || {};
  return `
    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-label">样本场次</div>
        <div class="metric-value">${Number(data.meta.sample_count ?? 0)}</div>
        <div class="metric-sub">同局可用样本</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">目标场次</div>
        <div class="metric-value">${Number(data.meta.target_matches ?? 0)}</div>
        <div class="metric-sub">最近历史窗口上限</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">缓存命中</div>
        <div class="metric-value">${Number(refresh.cache_hits ?? 0)}</div>
        <div class="metric-sub">本次直接复用的场次</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">新拉取</div>
        <div class="metric-value">${Number(refresh.detail_requests ?? 0)}</div>
        <div class="metric-sub">本次新增请求</div>
      </div>
    </div>
  `;
}

function renderNoData(data) {
  const refresh = data.refresh
    ? `<p class="stat-line">刷新结果: 分片=${escapeHtml(data.refresh.shard)}, 同局候选=${data.refresh.common_candidates}, 缓存命中=${data.refresh.cache_hits}, 新拉取=${data.refresh.detail_requests}</p>`
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
      <div class="result-head">
        <h3>暂无同局数据</h3>
        <span class="tag warn">No Shared Matches</span>
      </div>
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
        <div class="result-head">
          <h3>刷新概况</h3>
          <span class="tag">${escapeHtml(data.refresh.shard)}</span>
        </div>
        <div class="pill-row">
          <span class="pill">同局候选 ${data.refresh.common_candidates}</span>
          <span class="pill">缓存命中 ${data.refresh.cache_hits}</span>
          <span class="pill">新拉取 ${data.refresh.detail_requests}</span>
        </div>
      </div>
    `
    : "";

  let teamInfo = "";
  if (data.mode === "team" && data.team) {
    teamInfo = `
      <div class="result-block">
        <div class="result-head">
          <h3>分队</h3>
          <span class="tag alt">Team Mode</span>
        </div>
        <div class="pill-row">
          <span class="pill">A队: ${escapeHtml(data.team.A.join(" / "))}</span>
          <span class="pill">B队: ${escapeHtml(data.team.B.join(" / "))}</span>
        </div>
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
    ${renderMetrics(data)}
    ${refresh}
    ${teamInfo}
    ${renderProfile(data.profile || [])}
    <div class="result-block">
      <div class="result-head">
        <h3>让分输入</h3>
        <span class="tag">${data.mode === "team" ? "当前队伍让分" : "当前个人让分"}</span>
      </div>
      <div class="pill-row">
        ${(manualHandicaps || "无").split(" | ").filter(Boolean).map((item) => `<span class="pill">${item}</span>`).join("")}
      </div>
    </div>
    ${renderEvaluation(manualTitle, data.selected_names, data.manual.evaluation)}
    <div class="result-block">
      <div class="result-head">
        <h3>推荐让分</h3>
        <span class="tag alt">Auto Suggest</span>
      </div>
      <div class="pill-row">
        ${(suggestHandicaps || "无").split(" | ").filter(Boolean).map((item) => `<span class="pill">${item}</span>`).join("")}
      </div>
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
    const response = await fetch(withBasePath("/api/analyze"), {
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

async function saveNewPlayer() {
  clearFormError();
  clearAddPlayerMessage();
  const name = newPlayerName.value.trim();
  if (!name) {
    showAddPlayerMessage("用户名不能为空。", true);
    return;
  }

  savePlayerBtn.disabled = true;
  try {
    const response = await fetch(withBasePath("/api/players"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "新增用户失败");
    }

    const selectedNames = getSelectedPlayers();
    players = Array.isArray(data.players) ? [...data.players] : players;
    rerenderPlayerControls(selectedNames);
    newPlayerName.value = "";
    addPlayerBox.classList.add("hidden");
    showAddPlayerMessage(`已添加用户：${data.name}`);
  } catch (error) {
    showAddPlayerMessage(error.message || "新增用户失败", true);
  } finally {
    savePlayerBtn.disabled = false;
  }
}

function bindEvents() {
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
  teamAPicker.addEventListener("change", (event) => {
    const picks = [...teamAPicker.querySelectorAll("input:checked")];
    const selected = getSelectedPlayers();
    if (picks.length >= selected.length) {
      event.target.checked = false;
      showFormError("A 队不能包含所有玩家，B 队至少需要 1 人。");
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
  addPlayerBtn.addEventListener("click", () => {
    clearAddPlayerMessage();
    addPlayerBox.classList.toggle("hidden");
    if (!addPlayerBox.classList.contains("hidden")) {
      newPlayerName.focus();
    }
  });
  savePlayerBtn.addEventListener("click", saveNewPlayer);
  newPlayerName.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      saveNewPlayer();
    }
  });
  form.addEventListener("submit", submitForm);
}

renderPlayerPicker();
syncBySelection();
syncModeView();
bindEvents();
