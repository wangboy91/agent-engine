const exampleSkills = [
  "content-brief-planner",
  "hook-plan-generator",
  "style-bible-planner",
  "talking-script-writer",
  "script-segmenter",
  "storyboard-designer",
  "render-prompt-builder",
  "asset-manifest-builder",
  "video-timeline-planner",
  "video-render-dispatcher",
  "content-review-reporter",
  "content-video-workflow",
  "talking-video",
];

const exampleTools = ["subtitle_generate_srt", "mock_video_render"];

const state = {
  skills: [],
  workspaceSkills: [],
  identitySkills: [],
  identities: [],
  lastRunId: null,
};

const $ = (id) => document.getElementById(id);

function workspaceId() {
  return $("workspaceId").value.trim();
}

function identityId() {
  return $("identityId").value.trim();
}

function selectedSkillId() {
  return $("skillSelect").value || "";
}

function json(value) {
  return JSON.stringify(value, null, 2);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = payload.detail || json(payload);
    } catch (_error) {
      detail = await response.text();
    }
    throw new Error(`${response.status} ${detail}`);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function setOutput(value) {
  $("outputView").textContent = typeof value === "string" ? value : json(value);
}

function addMessage(role, text) {
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.textContent = text;
  $("messages").appendChild(node);
  node.scrollIntoView({ block: "end" });
}

function addEvent(name, data) {
  const item = document.createElement("li");
  const eventName = document.createElement("span");
  eventName.className = "event-name";
  eventName.textContent = name;
  const body = document.createElement("span");
  body.className = "event-body";
  body.textContent = summarizeEvent(data);
  item.append(eventName, body);
  $("eventList").appendChild(item);
  item.scrollIntoView({ block: "end" });
}

function summarizeEvent(data) {
  if (!data || typeof data !== "object") {
    return "";
  }
  const type = data.type || data.status || data.code || "";
  const message = data.message || data.skill_id || data.run_id || "";
  const step = data.data && (data.data.step_id || data.data.tool_id || data.data.skill_id);
  return [type, step, message].filter(Boolean).join(" · ") || json(data).slice(0, 180);
}

async function refreshHealth() {
  const target = $("healthStatus");
  try {
    const payload = await api("/health");
    target.textContent = payload.status === "ok" ? "正常" : payload.status;
    target.className = "status-pill ok";
  } catch (_error) {
    target.textContent = "离线";
    target.className = "status-pill fail";
  }
}

async function refreshState() {
  await refreshHealth();
  state.skills = await api("/skills");
  $("registeredCount").textContent = `${state.skills.length} 个技能`;
  await refreshWorkspaceSkills();
  renderSkills();
}

async function refreshWorkspaceSkills() {
  if (!workspaceId()) {
    state.workspaceSkills = [];
    state.identities = [];
    state.identitySkills = [];
    return;
  }
  try {
    state.workspaceSkills = await api(`/workspaces/${encodeURIComponent(workspaceId())}/skills`);
  } catch (_error) {
    state.workspaceSkills = [];
  }
  try {
    state.identities = await api(
      `/workspaces/${encodeURIComponent(workspaceId())}/identities`,
    );
  } catch (_error) {
    state.identities = [];
  }
  if (identityId()) {
    try {
      state.identitySkills = await api(
        `/workspaces/${encodeURIComponent(workspaceId())}/identities/${encodeURIComponent(
          identityId(),
        )}/skills`,
      );
    } catch (_error) {
      state.identitySkills = [];
    }
  }
}

function renderSkills() {
  const workspaceSkillIds = new Set(state.workspaceSkills.map((skill) => skill.skill_id));
  const workspaceSkillById = new Map(
    state.workspaceSkills.map((skill) => [skill.skill_id, skill]),
  );
  const enabledSkillIds = new Set(
    state.workspaceSkills.filter((skill) => skill.enabled).map((skill) => skill.skill_id),
  );
  const identitySkillIds = new Set(state.identitySkills.map((skill) => skill.id));
  const list = $("registeredSkills");
  list.textContent = "";
  const select = $("skillSelect");
  select.textContent = "";

  for (const skill of state.skills) {
    const item = document.createElement("div");
    item.className = "skill-item";
    const name = document.createElement("span");
    name.className = "skill-id";
    name.textContent = skill.id;
    const install = document.createElement("button");
    install.type = "button";
    install.textContent = workspaceSkillIds.has(skill.id) ? "已安装" : "安装";
    install.disabled = workspaceSkillIds.has(skill.id);
    install.addEventListener("click", () => installSkill(skill.id));
    const toggle = document.createElement("button");
    toggle.type = "button";
    const workspaceSkill = workspaceSkillById.get(skill.id);
    toggle.textContent = workspaceSkill && workspaceSkill.enabled ? "停用" : "启用";
    toggle.disabled = !workspaceSkill;
    toggle.addEventListener("click", () => {
      if (workspaceSkill) {
        setSkillEnabled(skill.id, !workspaceSkill.enabled);
      }
    });
    const bind = document.createElement("button");
    bind.type = "button";
    bind.textContent = identitySkillIds.has(skill.id) ? "已绑定" : "绑定";
    bind.disabled = !enabledSkillIds.has(skill.id) || identitySkillIds.has(skill.id);
    bind.addEventListener("click", () => bindSkill(skill.id));
    item.append(name, install, toggle, bind);
    list.appendChild(item);

    const option = document.createElement("option");
    option.value = skill.id;
    option.textContent = skill.id;
    if (skill.id === "content-video-workflow") {
      option.selected = true;
    }
    select.appendChild(option);
  }
}

async function setSkillEnabled(skillId, enabled) {
  await api(`/workspaces/${encodeURIComponent(workspaceId())}/skills/${encodeURIComponent(skillId)}`, {
    method: "PATCH",
    body: json({ enabled }),
  });
  await refreshState();
}

async function ensureWorkspace() {
  const workspace = workspaceId();
  const identity = identityId();
  if (!workspace || !identity) {
    throw new Error("需要填写工作区和身份");
  }
  await createIfMissing("/workspaces", {
    workspace_id: workspace,
    name: $("workspaceName").value.trim() || workspace,
  });
  await createIfMissing(`/workspaces/${encodeURIComponent(workspace)}/identities`, {
    identity_id: identity,
    name: $("identityName").value.trim() || identity,
  });
  await refreshState();
}

async function createIfMissing(path, payload) {
  try {
    await api(path, { method: "POST", body: json(payload) });
  } catch (error) {
    if (!String(error.message).includes("already exists")) {
      throw error;
    }
  }
}

async function registerSkillPath(path) {
  return api("/skills/register", {
    method: "POST",
    body: json({ path }),
  });
}

async function registerToolPath(path) {
  return api("/tools/register", {
    method: "POST",
    body: json({ path }),
  });
}

async function registerCurrentSkill() {
  const path = $("packagePath").value.trim();
  if (!path) {
    return;
  }
  await registerSkillPath(path);
  await refreshState();
}

async function registerExamples() {
  for (const skillId of exampleSkills) {
    try {
      await registerSkillPath(`examples/skills/${skillId}`);
    } catch (error) {
      addEvent("注册失败", { message: `${skillId}: ${error.message}` });
    }
  }
  await refreshState();
}

async function registerTools() {
  for (const toolId of exampleTools) {
    try {
      await registerToolPath(`examples/tools/${toolId}`);
    } catch (error) {
      addEvent("工具注册失败", { message: `${toolId}: ${error.message}` });
    }
  }
}

async function installSkill(skillId) {
  await ensureWorkspace();
  await api(`/workspaces/${encodeURIComponent(workspaceId())}/skills`, {
    method: "POST",
    body: json({ skill_id: skillId, display_name: skillId, enabled: true }),
  });
  await refreshState();
}

async function bindSkill(skillId) {
  await ensureWorkspace();
  await api(
    `/workspaces/${encodeURIComponent(workspaceId())}/identities/${encodeURIComponent(
      identityId(),
    )}/skills`,
    {
      method: "POST",
      body: json({ skill_id: skillId }),
    },
  );
  await refreshState();
}

async function submitChat(event) {
  event.preventDefault();
  const message = $("messageInput").value.trim();
  if (!message) {
    return;
  }
  addMessage("user", message);
  $("runStatus").textContent = "运行中";
  setOutput({});
  await streamChat(message);
}

async function streamChat(message) {
  const payload = {
    session_id: $("sessionId").value.trim() || null,
    message,
    skill_id: selectedSkillId() || null,
    context: {
      workspace_id: workspaceId() || null,
      identity_id: identityId() || null,
    },
  };
  const response = await fetch("/chat/messages/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: json(payload),
  });
  if (!response.ok || !response.body) {
    throw new Error(await response.text());
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) {
      handleSseFrame(frame);
    }
  }
  if (buffer.trim()) {
    handleSseFrame(buffer);
  }
}

function handleSseFrame(frame) {
  let eventName = "message";
  let data = {};
  for (const line of frame.split("\n")) {
    if (line.startsWith("event: ")) {
      eventName = line.slice(7).trim();
    }
    if (line.startsWith("data: ")) {
      try {
        data = JSON.parse(line.slice(6));
      } catch (_error) {
        data = { raw: line.slice(6) };
      }
    }
  }
  addEvent(eventName, data);
  if (eventName === "agent_completed") {
    state.lastRunId = Array.isArray(data.run_ids) ? data.run_ids.at(-1) : null;
    $("runStatus").textContent = translateStatus(data.status || "completed");
    setOutput(data.output || data);
    addMessage("assistant", data.message || translateStatus(data.status || "completed"));
  }
  if (eventName === "agent_failed" || eventName === "run_failed") {
    $("runStatus").textContent = "失败";
    setOutput(data);
    addMessage("assistant", data.message || "失败");
  }
}

function translateStatus(status) {
  const statusMap = {
    completed: "已完成",
    succeeded: "成功",
    failed: "失败",
    running: "运行中",
    needs_input: "需要补充信息",
    waiting_approval: "等待审批",
  };
  return statusMap[status] || status;
}

async function loadArtifacts() {
  if (!state.lastRunId) {
    $("artifactList").innerHTML = '<div class="artifact-item muted">暂无运行记录</div>';
    return;
  }
  const artifacts = await api(`/runs/${encodeURIComponent(state.lastRunId)}/artifacts`);
  const list = $("artifactList");
  list.textContent = "";
  if (!artifacts.length) {
    list.innerHTML = '<div class="artifact-item muted">暂无产物</div>';
    return;
  }
  for (const artifact of artifacts) {
    const item = document.createElement("div");
    item.className = "artifact-item";
    item.textContent = `${artifact.name || artifact.artifact_id} · ${artifact.uri || ""}`;
    list.appendChild(item);
  }
}

function wire() {
  $("ensureWorkspace").addEventListener("click", () => runAction(ensureWorkspace));
  $("refreshState").addEventListener("click", () => runAction(refreshState));
  $("registerSkill").addEventListener("click", () => runAction(registerCurrentSkill));
  $("registerExamples").addEventListener("click", () => runAction(registerExamples));
  $("registerTools").addEventListener("click", () => runAction(registerTools));
  $("chatForm").addEventListener("submit", (event) => runAction(() => submitChat(event)));
  $("clearEvents").addEventListener("click", () => {
    $("eventList").textContent = "";
  });
  $("loadArtifacts").addEventListener("click", () => runAction(loadArtifacts));
}

async function runAction(action) {
  try {
    await action();
  } catch (error) {
    addEvent("界面错误", { message: error.message });
    setOutput({ error: error.message });
  }
}

wire();
refreshState().catch((error) => addEvent("界面错误", { message: error.message }));
