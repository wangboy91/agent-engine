const resourceSkills = [
  "content-brief-planner",
  "hook-plan-generator",
  "style-bible-planner",
  "talking-script-writer",
  "script-segmenter",
  "storyboard-designer",
  "render-prompt-builder",
  "content-video-workflow",
  "talking-video",
  "wangbudong-experiment",
];

const resourceTools = ["subtitle_generate_srt", "mock_video_render"];

const state = {
  skills: [],
  workspaceSkills: [],
  identitySkills: [],
  identities: [],
  lastRunId: null,
  activePage: "config",
  pendingConfirmation: null,
  lastSubmittedMessage: "",
  currentThinkingList: null,
  currentThinkingStatus: null,
  currentMarkdownBody: null,
  currentMarkdownStatus: null,
  currentMarkdownText: "",
  receivedMarkdownStream: false,
  currentModelBody: null,
  currentModelStatus: null,
  currentModelText: "",
};

const $ = (id) => document.getElementById(id);

function workspaceId() {
  return $("workspaceId").value.trim();
}

function identityId() {
  return $("identityId").value.trim();
}

function selectedSkillId() {
  const value = $("skillSelect").value;
  return value === "__auto__" ? "" : value;
}

function switchPage(page) {
  state.activePage = page;
  const showConfig = page === "config";
  $("configPage").classList.toggle("active", showConfig);
  $("runPage").classList.toggle("active", !showConfig);
  $("configMenu").classList.toggle("active", showConfig);
  $("runMenu").classList.toggle("active", !showConfig);
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
  return node;
}

function addNodeMessage(role, node) {
  node.classList.add("message", role);
  $("messages").appendChild(node);
  node.scrollIntoView({ block: "end" });
  return node;
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
  const autoOption = document.createElement("option");
  autoOption.value = "__auto__";
  autoOption.textContent = "自动识别意图（不指定技能）";
  autoOption.selected = true;
  select.appendChild(autoOption);

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

async function registerIdentitySkillPath(path) {
  await ensureWorkspace();
  return api(
    `/workspaces/${encodeURIComponent(workspaceId())}/identities/${encodeURIComponent(
      identityId(),
    )}/skills/register`,
    {
      method: "POST",
      body: json({ path, enabled: true }),
    },
  );
}

async function registerIdentityToolPath(path) {
  await ensureWorkspace();
  return api(
    `/workspaces/${encodeURIComponent(workspaceId())}/identities/${encodeURIComponent(
      identityId(),
    )}/tools/register`,
    {
      method: "POST",
      body: json({
        path,
        effect: "allow",
        reason: "runtime console",
        enabled: true,
      }),
    },
  );
}

async function registerCurrentSkill() {
  const path = $("packagePath").value.trim();
  if (!path) {
    return;
  }
  const result = await registerIdentitySkillPath(path);
  addEvent("技能注册完成", { message: `${result.skill.id} 已绑定到当前身份` });
  await refreshState();
}

async function registerResources() {
  for (const skillId of resourceSkills) {
    try {
      await registerIdentitySkillPath(`resources/skills/${skillId}`);
    } catch (error) {
      addEvent("注册失败", { message: `${skillId}: ${error.message}` });
    }
  }
  await refreshState();
}

async function registerTools() {
  for (const toolId of resourceTools) {
    try {
      await registerIdentityToolPath(`resources/tools/${toolId}`);
    } catch (error) {
      addEvent("工具注册失败", { message: `${toolId}: ${error.message}` });
    }
  }
}

async function registerCurrentTool() {
  const path = $("toolPackagePath").value.trim();
  if (!path) {
    return;
  }
  const result = await registerIdentityToolPath(path);
  addEvent("工具注册完成", { message: `${result.tool.id} 已授权给当前身份` });
  setOutput(result);
}

async function scanWorkspaceSkills() {
  await ensureWorkspace();
  const payload = {
    skills_dir: $("skillsDir").value.trim() || "resources/skills",
    tools_dir: $("toolsDir").value.trim() || null,
    identity_id: identityId(),
    bind_to_identity: true,
    allow_tools_for_identity: true,
    enabled: true,
  };
  const result = await api(`/workspaces/${encodeURIComponent(workspaceId())}/skills/scan`, {
    method: "POST",
    body: json(payload),
  });
  addEvent("扫描完成", {
    message: `安装 ${result.installed_skills.length} 个技能，绑定 ${result.bound_skills.length} 个技能，授权 ${result.identity_tools.length} 个工具`,
  });
  setOutput(result);
  await refreshState();
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
  switchPage("run");
  state.lastSubmittedMessage = message;
  addMessage("user", message);
  $("runStatus").textContent = "运行中";
  setOutput({});
  startThinkingCard();
  resetModelStream();
  resetMarkdownStream();
  await streamChat(message, { confirm: false });
}

async function streamChat(message, options = {}) {
  const payload = {
    session_id: $("sessionId").value.trim() || null,
    message,
    skill_id: selectedSkillId() || null,
    confirm: Boolean(options.confirm),
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
  if (shouldShowEvent(eventName)) {
    addEvent(eventName, data);
  }
  appendThinkingEvent(eventName, data);
  if (eventName === "llm_delta") {
    appendModelDelta(extractDelta(data));
    return;
  }
  if (eventName === "markdown_delta") {
    appendMarkdownDelta(data.delta || "");
    return;
  }
  if (eventName === "markdown_completed") {
    finishMarkdownStream();
    return;
  }
  if (eventName === "agent_completed") {
    state.lastRunId = Array.isArray(data.run_ids) ? data.run_ids.at(-1) : null;
    $("runStatus").textContent = translateStatus(data.status || "completed");
    setOutput(data.output || data);
    if (data.status === "requires_confirmation" && data.requires_confirmation) {
      finishThinkingCard(data.status);
      showConfirmation(data);
    } else {
      state.pendingConfirmation = null;
      finishThinkingCard(data.status || "completed");
      finishModelStream();
      if (!state.receivedMarkdownStream) {
        addMarkdownResult(data);
      }
    }
  }
  if (eventName === "agent_failed" || eventName === "run_failed") {
    $("runStatus").textContent = "失败";
    setOutput(data);
    finishThinkingCard("failed");
    finishModelStream();
    addMessage("assistant", data.message || "失败");
  }
}

function shouldShowEvent(eventName) {
  return eventName !== "llm_delta";
}

function extractDelta(data) {
  if (!data || typeof data !== "object") {
    return "";
  }
  if (typeof data.delta === "string") {
    return data.delta;
  }
  if (data.data && typeof data.data.delta === "string") {
    return data.data.delta;
  }
  return "";
}

function deepThinkingEnabled() {
  return $("deepThinkingToggle").checked;
}

function startThinkingCard() {
  state.currentThinkingList = null;
  state.currentThinkingStatus = null;
  if (!deepThinkingEnabled()) {
    return;
  }
  const card = document.createElement("div");
  card.className = "thinking-card";
  const title = document.createElement("div");
  title.className = "thinking-title";
  const label = document.createElement("span");
  label.textContent = "深度思考";
  const status = document.createElement("span");
  status.textContent = "运行中";
  title.append(label, status);
  const list = document.createElement("ol");
  list.className = "thinking-list";
  card.append(title, list);
  addNodeMessage("assistant", card);
  state.currentThinkingList = list;
  state.currentThinkingStatus = status;
  appendThinkingLine(`收到用户输入：“${state.lastSubmittedMessage || "当前消息"}”。`);
  appendThinkingLine("读取当前工作区、身份和已绑定 Skill 状态。");
  if (selectedSkillId()) {
    appendThinkingLine(`用户已指定 Skill：${selectedSkillId()}，跳过自动意图匹配。`);
  } else {
    appendThinkingLine("未指定 Skill，进入意图识别和业务场景匹配。");
  }
}

function appendThinkingEvent(eventName, data) {
  if (!state.currentThinkingList || !deepThinkingEnabled()) {
    return;
  }
  const text = thinkingText(eventName, data);
  if (text) {
    appendThinkingLine(text);
  }
}

function appendThinkingLine(text) {
  if (!state.currentThinkingList) {
    return;
  }
  const item = document.createElement("li");
  item.textContent = text;
  state.currentThinkingList.appendChild(item);
  item.scrollIntoView({ block: "end" });
}

function finishThinkingCard(status) {
  if (state.currentThinkingStatus) {
    state.currentThinkingStatus.textContent = translateStatus(status);
  }
  state.currentThinkingList = null;
  state.currentThinkingStatus = null;
}

function thinkingText(eventName, data) {
  const payload = data && typeof data === "object" ? data : {};
  const detail = payload.data && typeof payload.data === "object" ? payload.data : payload;
  const stepId = detail.step_id || payload.step_id;
  const skillId = detail.skill_id || payload.skill_id;
  const toolId = detail.tool_id || payload.tool_id;
  if (eventName === "agent_started") {
    return "建立 SSE 会话流，准备实时接收执行状态。";
  }
  if (eventName === "workflow_step_started") {
    return `工作流调度：进入步骤 ${stepId || "unknown"}，准备运行 ${skillId || "子 Skill"}。`;
  }
  if (eventName === "skill_started") {
    return `执行确认：开始运行 Skill ${skillId || "unknown"}。`;
  }
  if (eventName === "llm_called") {
    return `模型调用完成：${skillId ? `${skillId} ` : ""}已生成结构化候选结果。`;
  }
  if (eventName === "tool_called") {
    return `工具调用：${toolId || "unknown"}，等待工具返回产物。`;
  }
  if (eventName === "tool_succeeded") {
    return `工具完成：${toolId || "unknown"} 已返回结果。`;
  }
  if (eventName === "skill_succeeded") {
    return `Skill 完成：${skillId || "unknown"} 输出已通过 schema 校验。`;
  }
  if (eventName === "workflow_step_succeeded") {
    return `工作流步骤完成：${stepId || skillId || "unknown"}，结果进入后续步骤上下文。`;
  }
  if (eventName === "agent_completed") {
    const route = payload.route_decision || {};
    const routedSkill = route.skill_id || "unknown";
    const reason = route.reason ? `，原因：${route.reason}` : "";
    return `对话完成：最终路由到 ${routedSkill}${reason}。`;
  }
  return "";
}

function showConfirmation(data) {
  state.pendingConfirmation = {
    message: state.lastSubmittedMessage,
    skillId: data.route_decision && data.route_decision.skill_id,
  };
  const node = addMessage("assistant", data.message || "需要确认后继续执行");
  const action = document.createElement("button");
  action.type = "button";
  action.className = "inline-action";
  action.textContent = data.confirmation?.message || "确认运行";
  action.addEventListener("click", () => runAction(confirmPendingRun));
  node.appendChild(action);
}

async function confirmPendingRun() {
  if (!state.pendingConfirmation || !state.pendingConfirmation.message) {
    return;
  }
  const message = state.pendingConfirmation.message;
  state.pendingConfirmation = null;
  $("runStatus").textContent = "运行中";
  setOutput({});
  startThinkingCard();
  resetModelStream();
  resetMarkdownStream();
  await streamChat(message, { confirm: true });
}

function addMarkdownResult(data) {
  const markdown = buildResultMarkdown(data);
  const card = document.createElement("div");
  card.className = "markdown-card";
  const title = document.createElement("div");
  title.className = "markdown-title";
  title.textContent = "运行结果";
  const body = document.createElement("div");
  body.className = "markdown-body";
  renderMarkdown(markdown, body);
  card.append(title, body);
  addNodeMessage("assistant", card);
}

function resetMarkdownStream() {
  state.currentMarkdownBody = null;
  state.currentMarkdownStatus = null;
  state.currentMarkdownText = "";
  state.receivedMarkdownStream = false;
}

function resetModelStream() {
  state.currentModelBody = null;
  state.currentModelStatus = null;
  state.currentModelText = "";
}

function appendModelDelta(delta) {
  if (!delta) {
    return;
  }
  if (!state.currentModelBody) {
    startModelStream();
  }
  state.currentModelText += delta;
  state.currentModelBody.textContent = state.currentModelText;
  state.currentModelBody.scrollIntoView({ block: "end" });
}

function startModelStream() {
  const card = document.createElement("div");
  card.className = "model-card";
  const title = document.createElement("div");
  title.className = "markdown-title";
  const label = document.createElement("span");
  label.textContent = "模型原生输出";
  const status = document.createElement("span");
  status.textContent = "接收中";
  title.append(label, status);
  const body = document.createElement("pre");
  body.className = "model-stream";
  card.append(title, body);
  addNodeMessage("assistant", card);
  state.currentModelBody = body;
  state.currentModelStatus = status;
}

function finishModelStream() {
  if (state.currentModelStatus) {
    state.currentModelStatus.textContent = "已完成";
  }
  state.currentModelBody = null;
  state.currentModelStatus = null;
}

function appendMarkdownDelta(delta) {
  if (!delta) {
    return;
  }
  if (!state.currentMarkdownBody) {
    startMarkdownStream();
  }
  state.receivedMarkdownStream = true;
  state.currentMarkdownText += delta;
  renderMarkdown(state.currentMarkdownText, state.currentMarkdownBody);
  state.currentMarkdownBody.scrollIntoView({ block: "end" });
}

function startMarkdownStream() {
  const card = document.createElement("div");
  card.className = "markdown-card";
  const title = document.createElement("div");
  title.className = "markdown-title";
  const label = document.createElement("span");
  label.textContent = "实时输出";
  const status = document.createElement("span");
  status.textContent = "生成中";
  title.append(label, status);
  const body = document.createElement("div");
  body.className = "markdown-body";
  card.append(title, body);
  addNodeMessage("assistant", card);
  state.currentMarkdownBody = body;
  state.currentMarkdownStatus = status;
}

function finishMarkdownStream() {
  if (state.currentMarkdownStatus) {
    state.currentMarkdownStatus.textContent = "已完成";
  }
  state.currentMarkdownBody = null;
  state.currentMarkdownStatus = null;
}

function buildResultMarkdown(data) {
  if (!data || typeof data !== "object") {
    return "### 运行结果\n\n无结构化输出。";
  }
  const output = data.output || {};
  const route = data.route_decision || {};
  const lines = [
    "### 运行结果",
    "",
    `- 状态：${translateStatus(data.status || "completed")}`,
    `- Skill：\`${route.skill_id || data.skill_id || "unknown"}\``,
  ];

  if (output.script && output.script.full_text) {
    lines.push("", "#### 口播脚本", "", output.script.full_text);
  } else if (output.script) {
    lines.push("", "#### 脚本", "", String(output.script));
  }

  if (Array.isArray(output.titles) && output.titles.length) {
    lines.push("", "#### 标题", "");
    output.titles.forEach((title) => lines.push(`- ${title}`));
  }

  if (output.subtitle_path) {
    lines.push("", "#### 字幕", "", `- \`${output.subtitle_path}\``);
  }

  if (Array.isArray(output.script_segments) && output.script_segments.length) {
    lines.push("", "#### 脚本分段", "");
    output.script_segments.slice(0, 8).forEach((segment) => {
      lines.push(
        `- ${segment.time_range || segment.start || ""} ${segment.spoken_text || segment.text || segment.screen_text || ""}`,
      );
    });
  }

  if (Array.isArray(output.segments) && output.segments.length) {
    lines.push("", "#### 片段", "");
    output.segments.slice(0, 8).forEach((segment) => {
      lines.push(
        `- ${segment.start || ""} ${segment.end || ""} ${segment.text || ""}`,
      );
    });
  }

  const shots = output.storyboard && Array.isArray(output.storyboard.shots)
    ? output.storyboard.shots
    : [];
  if (shots.length) {
    lines.push("", "#### 分镜", "");
    shots.slice(0, 8).forEach((shot) => {
      lines.push(
        `- ${shot.shot_id || ""}：${shot.description || ""}（${shot.duration || ""}s）`,
      );
    });
  }

  const prompts = output.render_prompt_pack && Array.isArray(output.render_prompt_pack.prompts)
    ? output.render_prompt_pack.prompts
    : [];
  if (prompts.length) {
    lines.push("", "#### 渲染提示词", "");
    prompts.slice(0, 8).forEach((prompt) => {
      lines.push(
        `- ${prompt.shot_id || ""}：${prompt.prompt || ""}`,
      );
    });
  }

  if (!output.script && !shots.length && !prompts.length) {
    lines.push("", "#### JSON 输出", "", "```json", json(output || data), "```");
  }

  if (Array.isArray(data.artifacts) && data.artifacts.length) {
    lines.push("", "#### 产物", "");
    data.artifacts.forEach((artifact) => {
      lines.push(`- \`${artifact.uri || artifact.name || artifact.id}\``);
    });
  }
  return lines.join("\n");
}

function renderMarkdown(markdown, target) {
  target.textContent = "";
  let list = null;
  let codeBlock = null;
  for (const rawLine of markdown.split("\n")) {
    const line = rawLine.trimEnd();
    if (line.startsWith("```")) {
      if (codeBlock) {
        target.appendChild(codeBlock);
        codeBlock = null;
      } else {
        codeBlock = document.createElement("pre");
      }
      continue;
    }
    if (codeBlock) {
      codeBlock.textContent += `${rawLine}\n`;
      continue;
    }
    if (!line.trim()) {
      list = null;
      continue;
    }
    if (line.startsWith("#### ")) {
      list = null;
      const heading = document.createElement("h4");
      heading.textContent = line.slice(5);
      target.appendChild(heading);
      continue;
    }
    if (line.startsWith("### ")) {
      list = null;
      const heading = document.createElement("h3");
      heading.textContent = line.slice(4);
      target.appendChild(heading);
      continue;
    }
    if (line.startsWith("- ")) {
      if (!list) {
        list = document.createElement("ul");
        target.appendChild(list);
      }
      const item = document.createElement("li");
      item.textContent = line.slice(2);
      list.appendChild(item);
      continue;
    }
    list = null;
    const paragraph = document.createElement("p");
    paragraph.textContent = line;
    target.appendChild(paragraph);
  }
  if (codeBlock) {
    target.appendChild(codeBlock);
  }
}

function translateStatus(status) {
  const statusMap = {
    completed: "已完成",
    succeeded: "成功",
    failed: "失败",
    running: "运行中",
    needs_input: "需要补充信息",
    requires_confirmation: "需要确认",
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
  $("configMenu").addEventListener("click", () => switchPage("config"));
  $("runMenu").addEventListener("click", () => switchPage("run"));
  $("ensureWorkspace").addEventListener("click", () => runAction(ensureWorkspace));
  $("refreshState").addEventListener("click", () => runAction(refreshState));
  $("registerSkill").addEventListener("click", () => runAction(registerCurrentSkill));
  $("registerTool").addEventListener("click", () => runAction(registerCurrentTool));
  $("registerResources").addEventListener("click", () => runAction(registerResources));
  $("registerTools").addEventListener("click", () => runAction(registerTools));
  $("scanWorkspaceSkills").addEventListener("click", () => runAction(scanWorkspaceSkills));
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
