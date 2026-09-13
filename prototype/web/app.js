/* Agent Engine Console Prototype 1.0.1-r2 — roles + create wizard + artifact FS */
(function () {
  "use strict";

  const ROLES = {
    platform_admin: {
      label: "平台管理员",
      user: "韩启",
      avatar: "韩",
      mode: "console",
      banner: "平台作用域：可管理租户与模板，默认不可读取租户用户会话正文。",
      can: {
        createAgent: false,
        publish: false,
        approve: true,
        readAnyArtifact: false,
        elevateArtifact: false,
        manageMembers: false,
        manageTenants: true,
      },
    },
    tenant_admin: {
      label: "企业管理员",
      user: "沈舟",
      avatar: "沈",
      mode: "console",
      banner: "租户作用域：成员/审计/定制开关。读取员工正文需提权 + 审计。",
      can: {
        createAgent: true,
        publish: true,
        approve: true,
        readAnyArtifact: true,
        elevateArtifact: true,
        manageMembers: true,
        manageTenants: false,
      },
    },
    ws_admin: {
      label: "空间管理员",
      user: "赵安",
      avatar: "赵",
      mode: "console",
      banner: "工作空间作用域：可配置、发布、授权。产物默认仅本人；管理读取需提权。",
      can: {
        createAgent: true,
        publish: true,
        approve: true,
        readAnyArtifact: true,
        elevateArtifact: true,
        manageMembers: true,
        manageTenants: false,
      },
    },
    developer: {
      label: "智能体开发者",
      user: "林晓晴",
      avatar: "林",
      mode: "console",
      banner: "开发者作用域：草稿配置与调试。不能直接改已发布版本，不能读他人生产正文。",
      can: {
        createAgent: true,
        publish: false,
        approve: false,
        readAnyArtifact: false,
        elevateArtifact: false,
        manageMembers: false,
        manageTenants: false,
      },
    },
    operator: {
      label: "业务运营",
      user: "李衡",
      avatar: "李",
      mode: "console",
      banner: "运营作用域：Run 脱敏摘要与审批。正文与产物需额外授权。",
      can: {
        createAgent: false,
        publish: false,
        approve: true,
        readAnyArtifact: false,
        elevateArtifact: true,
        manageMembers: false,
        manageTenants: false,
      },
    },
    auditor: {
      label: "审计员",
      user: "周谨",
      avatar: "周",
      mode: "console",
      banner: "审计只读：可看变更与访问审计，不能写配置，不能读正文。",
      can: {
        createAgent: false,
        publish: false,
        approve: false,
        readAnyArtifact: false,
        elevateArtifact: false,
        manageMembers: false,
        manageTenants: false,
      },
    },
    end_user: {
      label: "企业员工",
      user: "顾南",
      avatar: "顾",
      mode: "workbench",
      banner: "员工作用域：仅本人会话 / 任务 / 产物 / 记忆。不可见他人目录。",
      can: {
        createAgent: false,
        publish: false,
        approve: false,
        readAnyArtifact: false,
        elevateArtifact: false,
        manageMembers: false,
        manageTenants: false,
      },
    },
  };

  const state = {
    role: "ws_admin",
    mode: "console",
    route: "#/console/overview",
    tenant: "t-demo",
    workspace: "ws-content",
    agentTab: "overview",
    selectedAgentId: "ag-dev-consult",
    selectedSessionId: "s-1",
    filterStatus: "all",
    createStep: 0,
    createDraft: {
      name: "",
      desc: "",
      model: "production",
      skill: "growth-plan-generator",
      tools: ["org-api.get_member_profile"],
      grantGroup: "全体员工",
    },
    artifactPath: ["顾南", "发展规划助手", "2026-07-28", "run_9f2a"],
    elevateRequest: null,
  };

  const currentUserPrincipal = () => {
    if (state.role === "end_user") return { id: "u_2001", name: "顾南" };
    return { id: "u_admin", name: ROLES[state.role].user };
  };

  const navByRole = {
    console: [
      { section: "概览" },
      { id: "overview", label: "总览", icon: "▦", roles: "*" },
      { section: "业务" },
      { id: "agents", label: "智能体", icon: "◈", roles: "*" },
      { id: "agent-create", label: "创建智能体", icon: "＋", roles: ["ws_admin", "tenant_admin", "developer"] },
      { id: "skills", label: "Skill", icon: "⌘", roles: "*" },
      { id: "skill-import", label: "导入 Skill", icon: "⇪", roles: ["ws_admin", "tenant_admin", "developer"] },
      { id: "tools", label: "工具与连接器", icon: "⚙", roles: "*" },
      { section: "运行与产物" },
      { id: "runs", label: "Run", icon: "▶", roles: "*" },
      { id: "artifacts", label: "产出物目录", icon: "▤", roles: "*" },
      { id: "approvals", label: "审批", icon: "✓", roles: ["ws_admin", "tenant_admin", "operator", "platform_admin"] },
      { section: "治理" },
      { id: "audit", label: "审计日志", icon: "☰", roles: ["auditor", "ws_admin", "tenant_admin", "platform_admin"] },
      { id: "settings", label: "工作空间设置", icon: "⚒", roles: ["ws_admin", "tenant_admin"] },
    ],
    workbench: [
      { section: "工作台" },
      { id: "my-agents", label: "我的智能体", icon: "◈", roles: "*" },
      { id: "chat", label: "会话", icon: "💬", roles: "*" },
      { id: "my-runs", label: "我的任务", icon: "▶", roles: "*" },
      { id: "my-artifacts", label: "我的产出物", icon: "▤", roles: "*" },
      { id: "my-memory", label: "我的记忆", icon: "🧠", roles: "*" },
    ],
  };

  const mock = {
    metrics: [
      { label: "已发布智能体", value: "6", delta: "+1 本周", dir: "up", go: "#/console/agents" },
      { label: "24h Run", value: "1,284", delta: "+12.4%", dir: "up", go: "#/console/runs" },
      { label: "成功率", value: "96.8%", delta: "+0.6pt", dir: "up", go: "#/console/runs" },
      { label: "P95 延迟", value: "4.2s", delta: "-0.3s", dir: "up", go: "#/console/runs" },
      { label: "预估成本", value: "¥186", delta: "+¥12", dir: "down", go: "#/console/runs" },
      { label: "待审批", value: "3", delta: "最长等待 18m", dir: "down", go: "#/console/approvals" },
    ],
    agents: [
      {
        id: "ag-dev-consult",
        name: "发展规划助手",
        desc: "个人目标与能力规划助手",
        status: "published",
        version: "v1.4.2",
        owner: "林晓晴",
        skills: 4,
        tools: 3,
        users: 128,
        success: "97.2%",
        updated: "2026-07-28 16:20",
        model: "production",
        temp: "0.3",
        systemPrompt: "你是企业发展规划助手。基于目标生成结构化建议；调用允许的 Skill/Tool；输出必须符合 Schema。",
      },
      {
        id: "ag-content-writer",
        name: "内容策划助手",
        desc: "Brief → Hook → 脚本工作流",
        status: "published",
        version: "v2.1.0",
        owner: "周予",
        skills: 6,
        tools: 2,
        users: 56,
        success: "94.1%",
        updated: "2026-07-27 11:05",
        model: "production",
        temp: "0.5",
        systemPrompt: "你是内容生产策划助手。",
      },
      {
        id: "ag-ops-bot",
        name: "运营巡检机器人",
        desc: "日报摘要与异常初筛",
        status: "draft",
        version: "Draft v0.3",
        owner: "李衡",
        skills: 2,
        tools: 1,
        users: 0,
        success: "—",
        updated: "2026-07-29 09:40",
        model: "staging",
        temp: "0.2",
        systemPrompt: "草稿配置，尚未发布。",
      },
    ],
    skills: [
      { id: "growth-plan-generator", name: "生成发展计划", version: "1.1.0", status: "published", refs: 2, owner: "林晓晴", updated: "2026-07-20" },
      { id: "content-brief-planner", name: "内容 Brief 规划", version: "0.9.2", status: "published", refs: 3, owner: "周予", updated: "2026-07-18" },
      { id: "talking-video", name: "口播视频草稿", version: "0.1.0", status: "published", refs: 1, owner: "周予", updated: "2026-07-10" },
      { id: "hook-plan-generator", name: "Hook 策划", version: "0.8.0", status: "draft", refs: 0, owner: "周予", updated: "2026-07-29" },
    ],
    tools: [
      { id: "tool-service-org", name: "组织服务 OpenAPI", type: "HTTP/OpenAPI", url: "https://api.example.internal/org/v1", ops: 14, health: "healthy", sync: "2h 前", owner: "平台组" },
      { id: "subtitle_generate_srt", name: "字幕生成", type: "Python", url: "本地包", ops: 1, health: "healthy", sync: "—", owner: "周予" },
      { id: "render-mock", name: "视频渲染（Mock）", type: "Python", url: "本地包", ops: 1, health: "degraded", sync: "—", owner: "周予" },
    ],
    runs: [
      { id: "run_9f2a", agent: "发展规划助手", status: "completed", user: "u_2001", userName: "顾南", duration: "3.4s", tokens: "8.2k", error: "—", at: "10:22:41" },
      { id: "run_9f18", agent: "内容策划助手", status: "running", user: "u_1002", userName: "叶清", duration: "12.1s", tokens: "—", error: "—", at: "10:21:03" },
      { id: "run_9e91", agent: "发展规划助手", status: "waiting_approval", user: "u_1020", userName: "方远", duration: "—", tokens: "2.1k", error: "Tool ask: org-api.update_plan", at: "10:18:12" },
      { id: "run_9d77", agent: "发展规划助手", status: "completed", user: "u_1014", userName: "顾南", duration: "2.9s", tokens: "6.7k", error: "—", at: "09:58:10" },
      { id: "run_9c01", agent: "内容策划助手", status: "completed", user: "u_1002", userName: "叶清", duration: "5.1s", tokens: "3.2k", error: "—", at: "09:40:12" },
    ],
    runDetail: {
      id: "run_9f2a",
      timeline: [
        { title: "Skill 开始", meta: "growth-plan-generator@1.1.0 · 10:22:41.102", tone: "" },
        { title: "模型调用", meta: "profile=production · 1.8s · 6.1k tokens", tone: "", body: "messages=12 tools=3" },
        { title: "Tool 调用", meta: "org-api.get_member_profile · allow · 210ms", tone: "success", body: '{"member_id":"M2048"}' },
        { title: "输出校验", meta: "output.schema.json · passed", tone: "success" },
        { title: "Run 完成", meta: "completed · artifacts written under owner path", tone: "success" },
      ],
    },
    approvals: [
      { id: "apr_881", tool: "org-api.update_plan", agent: "发展规划助手", risk: "high", wait: "18m", user: "u_1020", reason: "写操作 · 更新发展计划" },
      { id: "apr_879", tool: "mail.send_draft", agent: "运营巡检机器人", risk: "medium", wait: "6m", user: "u_1008", reason: "外发草稿邮件" },
      { id: "apr_870", tool: "org-api.export_csv", agent: "发展规划助手", risk: "high", wait: "2m", user: "u_1011", reason: "批量导出 · 含个人信息" },
    ],
    audit: [
      { at: "10:20:11", actor: "沈舟", action: "提权读取正文", target: "session/s-88", result: "已授权+审计", reason: "排查串线投诉" },
      { at: "10:12:04", actor: "系统", action: "拒绝越权产物访问", target: "artifacts/叶清/... by 顾南", result: "403", reason: "owner mismatch" },
      { at: "09:55:33", actor: "林晓晴", action: "发布 IdentityVersion", target: "发展规划助手@v1.4.2", result: "成功", reason: "—" },
    ],
    sessions: [
      {
        id: "s-1",
        title: "制定 Q3 发展计划",
        agent: "发展规划助手",
        updated: "10:22",
        owner: "u_2001",
        messages: [
          { role: "user", text: "帮我制定本季度的发展计划，重点提升架构设计能力。" },
          { role: "agent", text: "已为你生成一版发展计划草稿：2 个能力项、3 个目标、5 条行动。", steps: ["解析意图", "Skill: 生成发展计划", "Schema 校验通过"] },
        ],
        artifacts: ["plan.json", "plan-summary.md"],
      },
    ],
    myAgents: [
      { id: "ag-dev-consult", name: "发展规划助手", desc: "生成发展计划、目标与行动计划", last: "12 分钟前" },
      { id: "ag-content-writer", name: "内容策划助手", desc: "帮我写 brief 与脚本草稿", last: "昨天" },
    ],
    memory: [
      { key: "pref.role", value: "后端工程师 / 技术负责人", source: "会话 s-1 · 可纠正" },
      { key: "pref.focus", value: "架构设计、跨团队协作", source: "会话 s-1 · 可纠正" },
    ],
    // 产出物虚拟文件系统：逻辑路径 tenants/{t}/workspaces/{w}/users/{owner}/...
    // 原型展示为用户目录视角
    artifactFS: {
      // key: owner user name
      顾南: {
        "发展规划助手": {
          "2026-07-28": {
            "run_9f2a": [
              { name: "plan.json", type: "file", size: "12 KB", at: "10:22", mime: "application/json", preview: '{\n  "goals": [\n    {"id": "g1", "title": "完成架构评审模板", "due": "2026-08-15"},\n    {"id": "g2", "title": "主导一次跨团队设计评审", "due": "2026-09-01"}\n  ],\n  "actions": ["每周五 30m 复盘", "两周一次评审", "月底架构笔记"]\n}' },
              { name: "plan-summary.md", type: "file", size: "4 KB", at: "10:22", mime: "text/markdown", preview: "# 发展计划摘要\n\n- 能力项：系统设计、跨团队协作\n- 目标：2 个\n- 行动：5 条\n- 产物归属：顾南（不可被他人下载）" },
            ],
            "run_9d77": [
              { name: "plan-v0.json", type: "file", size: "9 KB", at: "09:58", mime: "application/json", preview: '{ "version": 0, "note": "草稿" }' },
            ],
          },
        },
        "内容策划助手": {
          "2026-07-27": {
            "run_9c12": [
              { name: "script_60s.srt", type: "file", size: "2 KB", at: "18:10", mime: "text/plain", preview: "1\n00:00:00,000 --> 00:00:02,000\n（示例字幕）" },
            ],
          },
        },
      },
      叶清: {
        "内容策划助手": {
          "2026-07-28": {
            "run_9f18": [
              { name: "brief.json", type: "file", size: "6 KB", at: "10:21", mime: "application/json", preview: '{ "owner": "叶清", "secret_note": "他人不应看到此预览" }' },
            ],
          },
        },
      },
      方远: {
        "发展规划助手": {
          "2026-07-28": {
            "run_9e91": [
              { name: "pending-plan.json", type: "file", size: "3 KB", at: "10:18", mime: "application/json", preview: '{ "status": "waiting_approval" }' },
            ],
          },
        },
      },
    },
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function toast(msg, kind = "") {
    const host = $("#toastHost");
    const el = document.createElement("div");
    el.className = "toast" + (kind ? " " + kind : "");
    el.textContent = msg;
    host.appendChild(el);
    setTimeout(() => el.remove(), 2800);
  }

  function can(key) {
    return !!(ROLES[state.role].can && ROLES[state.role].can[key]);
  }

  function statusPill(status) {
    const map = {
      published: ["pill-success", "已发布"],
      draft: ["pill-warning", "草稿"],
      archived: ["pill-muted", "已归档"],
      completed: ["pill-success", "成功"],
      running: ["pill-info", "运行中"],
      failed: ["pill-danger", "失败"],
      waiting_approval: ["pill-warning", "待审批"],
      healthy: ["pill-success", "健康"],
      degraded: ["pill-warning", "降级"],
      high: ["pill-danger", "高"],
      medium: ["pill-warning", "中"],
    };
    const [cls, label] = map[status] || ["pill-muted", status];
    return `<span class="pill ${cls}">${label}</span>`;
  }

  function applyRoleChrome() {
    const role = ROLES[state.role];
    $("#userName").textContent = role.user;
    $("#userRole").textContent = role.label;
    $("#userAvatar").textContent = role.avatar;
    const banner = $("#permBanner");
    banner.hidden = false;
    banner.textContent = "当前 Principal：" + role.user + " · " + role.label + " — " + role.banner;
    banner.className = "perm-banner" + (state.role === "end_user" ? "" : "");
  }

  function allowedNav() {
    const items = navByRole[state.mode] || [];
    return items.filter((item) => {
      if (item.section) return true;
      if (item.roles === "*") return true;
      return item.roles.includes(state.role);
    });
  }

  function currentNavId() {
    const parts = state.route.split("/");
    return parts[2] || (state.mode === "console" ? "overview" : "my-agents");
  }

  function renderNav() {
    const items = allowedNav();
    const active = currentNavId();
    const sections = [];
    let buffer = [];
    items.forEach((item) => {
      if (item.section) {
        if (buffer.length) sections.push(buffer);
        buffer = [item];
      } else buffer.push(item);
    });
    if (buffer.length) sections.push(buffer);

    let html = "";
    sections.forEach((group) => {
      const section = group[0];
      const rest = group.slice(1);
      if (!rest.length) return;
      html += `<div class="nav-section">${escapeHtml(section.section)}</div>`;
      rest.forEach((item) => {
        const prefix = state.mode === "console" ? "console" : "app";
        const href = `#/${prefix}/${item.id}`;
        html += `<button type="button" class="nav-item${item.id === active ? " is-active" : ""}" data-nav="${item.id}">
          <span class="nav-icon" aria-hidden="true">${item.icon}</span>
          <span>${escapeHtml(item.label)}</span>
        </button>`;
      });
    });
    // mode switch for admin who can peek workbench self-view
    if (state.mode === "console") {
      html += `<div class="nav-section">切换入口</div>
        <button type="button" class="nav-item" data-switch-mode="workbench">
          <span class="nav-icon">↔</span><span>用户工作台</span>
        </button>`;
    } else {
      html += `<div class="nav-section">切换入口</div>
        <button type="button" class="nav-item" data-switch-mode="console">
          <span class="nav-icon">↔</span><span>管理控制台</span>
        </button>`;
    }
    $("#sidenav").innerHTML = html;
  }

  function pageShell({ crumb, title, desc, actions = "", body }) {
    return `
      <div class="page-header">
        <div>
          <div class="breadcrumb">${crumb}</div>
          <h1 class="page-title">${title}</h1>
          ${desc ? `<p class="page-desc">${desc}</p>` : ""}
        </div>
        <div class="page-actions">${actions}</div>
      </div>
      ${body}
    `;
  }

  function denyPage(what) {
    return pageShell({
      crumb: "无权限",
      title: "无法访问",
      desc: "当前角色没有该能力",
      body: `<section class="card"><div class="access-denied">
        <strong>权限不足</strong>
        当前角色「${escapeHtml(ROLES[state.role].label)}」不能${escapeHtml(what)}。
        请切换角色演示，或联系工作空间管理员授权。
      </div></section>`,
    });
  }

  /* ---------- Overview ---------- */
  function renderOverview() {
    const metrics = mock.metrics
      .map(
        (m) => `
      <article class="card metric" data-go="${m.go}" tabindex="0" role="link" aria-label="${m.label}">
        <div class="metric-label">${m.label}</div>
        <div class="metric-value">${m.value}</div>
        <div class="metric-delta ${m.dir}">${m.delta}</div>
      </article>`
      )
      .join("");

    return pageShell({
      crumb: "管理控制台 / 总览",
      title: "总览",
      desc: `角色：${ROLES[state.role].label} · 指标可下钻；正文与产物遵循所有权策略。`,
      actions: can("createAgent")
        ? `<button class="btn" data-nav-go="skill-import">导入 Skill</button>
           <button class="btn btn-primary" data-nav-go="agent-create">创建智能体</button>`
        : `<span class="form-hint">只读视角</span>`,
      body: `
        <div class="grid grid-metrics" style="margin-bottom:12px">${metrics}</div>
        <div class="grid grid-2">
          <section class="card">
            <div class="card-header"><h2 class="card-title">失败原因分布（24h）</h2></div>
            <div class="card-body">
              <div class="bars">
                <div class="bar-row"><span>模型超时</span><div class="bar-track"><div class="bar-fill danger" style="width:42%"></div></div><span class="bar-val">42%</span></div>
                <div class="bar-row"><span>Schema 校验</span><div class="bar-track"><div class="bar-fill danger" style="width:28%"></div></div><span class="bar-val">28%</span></div>
                <div class="bar-row"><span>Tool 拒绝</span><div class="bar-track"><div class="bar-fill" style="width:18%"></div></div><span class="bar-val">18%</span></div>
              </div>
            </div>
          </section>
          <section class="card">
            <div class="card-header"><h2 class="card-title">权限与隔离状态</h2></div>
            <div class="card-body">
              <div class="kv-list">
                <div class="kv"><span class="kv-k">Principal</span><span class="kv-v">${escapeHtml(ROLES[state.role].user)} · ${escapeHtml(ROLES[state.role].label)}</span></div>
                <div class="kv"><span class="kv-k">租户 / 空间</span><span class="kv-v">${escapeHtml(state.tenant)} / ${escapeHtml(state.workspace)}</span></div>
                <div class="kv"><span class="kv-k">产物根路径</span><span class="kv-v"><code>users/${state.role === "end_user" ? "顾南" : "*"}/…</code></span></div>
                <div class="kv"><span class="kv-k">跨用户产物</span><span class="kv-v pill pill-danger">默认拒绝</span></div>
              </div>
            </div>
          </section>
        </div>`,
    });
  }

  /* ---------- Agents ---------- */
  function renderAgents() {
    if (!can("createAgent") && state.role === "end_user") {
      // shouldn't reach
    }
    const rows = mock.agents
      .filter((a) => state.filterStatus === "all" || a.status === state.filterStatus)
      .map(
        (a) => `
      <tr>
        <td><strong>${escapeHtml(a.name)}</strong></td>
        <td>${statusPill(a.status)}</td>
        <td>${escapeHtml(a.version)}</td>
        <td>${escapeHtml(a.owner)}</td>
        <td>${a.skills} / ${a.tools}</td>
        <td>${a.users}</td>
        <td>${escapeHtml(a.updated)}</td>
        <td class="actions">
          <button class="btn btn-sm" data-open-agent="${a.id}">配置</button>
          ${can("publish") ? `<button class="btn btn-sm" data-action="publish-agent">发布</button>` : ""}
        </td>
      </tr>`
      )
      .join("");

    return pageShell({
      crumb: "管理控制台 / 智能体",
      title: "智能体",
      desc: "Identity Definition/Version。仅 Published 可授权给员工。",
      actions: can("createAgent")
        ? `<button class="btn btn-primary" data-nav-go="agent-create">创建智能体</button>`
        : "",
      body: `
        <section class="card">
          <div class="toolbar">
            <select class="field" id="agentStatusFilter">
              <option value="all">全部状态</option>
              <option value="published"${state.filterStatus === "published" ? " selected" : ""}>已发布</option>
              <option value="draft"${state.filterStatus === "draft" ? " selected" : ""}>草稿</option>
            </select>
            <div class="spacer"></div>
            <span class="form-hint">共 ${mock.agents.length} 条 · 可见性受角色限制</span>
          </div>
          <div class="table-wrap">
            <table class="data">
              <thead><tr><th>名称</th><th>状态</th><th>版本</th><th>负责人</th><th>Skill/Tool</th><th>授权用户</th><th>更新时间</th><th></th></tr></thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        </section>`,
    });
  }

  function renderAgentDetail() {
    const agent = mock.agents.find((a) => a.id === state.selectedAgentId) || mock.agents[0];
    const tabs = [
      ["overview", "概览"],
      ["model", "模型"],
      ["prompt", "提示词"],
      ["skills", "Skill"],
      ["tools", "工具"],
      ["versions", "版本"],
    ];
    let panel = "";
    if (state.agentTab === "overview") {
      panel = `<div class="form-grid">
        <div class="form-field"><label>名称</label><input value="${escapeHtml(agent.name)}" ${can("createAgent") ? "" : "disabled"} /></div>
        <div class="form-field"><label>负责人</label><input value="${escapeHtml(agent.owner)}" disabled /></div>
        <div class="form-field full"><label>描述</label><textarea ${can("createAgent") ? "" : "disabled"}>${escapeHtml(agent.desc)}</textarea></div>
      </div>`;
    } else if (state.agentTab === "model") {
      panel = `<div class="form-grid">
        <div class="form-field"><label>模型 Profile</label><input value="${escapeHtml(agent.model)}" ${can("createAgent") ? "" : "disabled"} /></div>
        <div class="form-field"><label>温度</label><input value="${escapeHtml(agent.temp)}" ${can("createAgent") ? "" : "disabled"} /></div>
      </div>`;
    } else if (state.agentTab === "prompt") {
      panel = `<div class="form-field"><label>System Prompt</label>
        <textarea style="min-height:140px" ${can("createAgent") ? "" : "disabled"}>${escapeHtml(agent.systemPrompt)}</textarea>
        <div class="form-hint">员工端不可见此全文。</div></div>`;
    } else if (state.agentTab === "skills") {
      panel = `<div class="table-wrap"><table class="data">
        <thead><tr><th>Skill</th><th>版本</th><th>场景</th><th>优先级</th></tr></thead>
        <tbody>
          <tr><td>生成发展计划</td><td>1.1.0</td><td>生成完整发展计划</td><td>10</td></tr>
          <tr><td>能力项解析</td><td>0.3.1</td><td>提取能力项</td><td>20</td></tr>
        </tbody></table></div>`;
    } else if (state.agentTab === "tools") {
      panel = `<div class="table-wrap"><table class="data">
        <thead><tr><th>工具</th><th>策略</th><th>审批</th></tr></thead>
        <tbody>
          <tr><td>org-api.get_member_profile</td><td><span class="pill pill-success">allow</span></td><td>否</td></tr>
          <tr><td>org-api.update_plan</td><td><span class="pill pill-warning">ask</span></td><td>是</td></tr>
        </tbody></table></div>`;
    } else {
      panel = `<div class="table-wrap"><table class="data">
        <thead><tr><th>版本</th><th>状态</th><th>发布时间</th><th>说明</th><th></th></tr></thead>
        <tbody>
          <tr><td>v1.4.2</td><td>${statusPill("published")}</td><td>2026-07-28</td><td>增强周复盘模板</td><td></td></tr>
          <tr><td>Draft v1.5</td><td>${statusPill("draft")}</td><td>—</td><td>接入知识库</td><td></td></tr>
        </tbody></table></div>`;
    }

    return pageShell({
      crumb: `管理控制台 / 智能体 / ${agent.name}`,
      title: `${escapeHtml(agent.name)} <span class="pill pill-info" style="vertical-align:middle">${escapeHtml(agent.version)}</span>`,
      desc: escapeHtml(agent.desc),
      actions: `
        ${can("createAgent") ? `<button class="btn" data-action="save-draft">保存草稿</button>` : ""}
        <button class="btn" data-action="debug-agent">测试</button>
        ${can("publish") ? `<button class="btn btn-primary" data-action="publish-agent">提交发布</button>` : ""}`,
      body: `
        <section class="card">
          <div class="tabs">${tabs
            .map(([id, label]) => `<button type="button" class="tab${state.agentTab === id ? " is-active" : ""}" data-agent-tab="${id}">${label}</button>`)
            .join("")}</div>
          <div class="card-body">${panel}</div>
        </section>
        <section class="card" style="margin-top:12px">
          <div class="card-header"><h2 class="card-title">发布检查</h2></div>
          <div class="card-body"><div class="check-list">
            <div class="check-row ok"><span>✓</span><div><strong>Schema / 引用</strong><div class="form-hint">输入输出与资源绑定完整</div></div></div>
            <div class="check-row warn"><span>!</span><div><strong>Secret</strong><div class="form-hint">1 项密钥待轮换</div></div></div>
            <div class="check-row ok"><span>✓</span><div><strong>Tool 策略预览</strong><div class="form-hint">写操作为 ask</div></div></div>
          </div></div>
        </section>`,
    });
  }

  /* ---------- Create agent wizard ---------- */
  function renderAgentCreate() {
    if (!can("createAgent")) return denyPage("创建智能体");

    const steps = ["基本信息", "模型", "能力绑定", "授权", "检查发布"];
    const step = state.createStep;
    const d = state.createDraft;

    let panel = "";
    if (step === 0) {
      panel = `<div class="form-grid">
        <div class="form-field"><label>名称 *</label>
          <input id="czName" value="${escapeHtml(d.name)}" placeholder="例如：发展规划助手" />
          <div class="form-hint">创建后生成 IdentityDefinition + Draft Version</div>
        </div>
        <div class="form-field"><label>负责人</label>
          <input value="${escapeHtml(ROLES[state.role].user)}" disabled />
        </div>
        <div class="form-field full"><label>描述</label>
          <textarea id="czDesc" placeholder="面向用户的简短说明">${escapeHtml(d.desc)}</textarea>
        </div>
      </div>`;
    } else if (step === 1) {
      panel = `<div class="form-grid">
        <div class="form-field"><label>模型 Profile</label>
          <select id="czModel">
            <option value="production"${d.model === "production" ? " selected" : ""}>production（推荐）</option>
            <option value="staging"${d.model === "staging" ? " selected" : ""}>staging</option>
            <option value="mock"${d.model === "mock" ? " selected" : ""}>mock（仅调试）</option>
          </select>
        </div>
        <div class="form-field"><label>温度</label><input value="0.3" /></div>
        <div class="form-field"><label>超时（秒）</label><input value="120" /></div>
        <div class="form-field"><label>Token 预算</label><input value="16000" /></div>
      </div>`;
    } else if (step === 2) {
      panel = `
        <div class="form-field" style="margin-bottom:12px">
          <label>绑定 Skill（已发布）</label>
          <select id="czSkill">
            ${mock.skills
              .filter((s) => s.status === "published")
              .map((s) => `<option value="${s.id}"${d.skill === s.id ? " selected" : ""}>${escapeHtml(s.name)}@${s.version}</option>`)
              .join("")}
          </select>
        </div>
        <div class="form-field">
          <label>绑定 Tool 与默认策略</label>
          <div class="check-list" style="margin-top:6px">
            <label class="check-row"><input type="checkbox" data-tool="org-api.get_member_profile" ${d.tools.includes("org-api.get_member_profile") ? "checked" : ""} /> <div><strong>org-api.get_member_profile</strong><div class="form-hint">默认 allow</div></div></label>
            <label class="check-row"><input type="checkbox" data-tool="org-api.update_plan" ${d.tools.includes("org-api.update_plan") ? "checked" : ""} /> <div><strong>org-api.update_plan</strong><div class="form-hint">默认 ask（需审批）</div></div></label>
            <label class="check-row"><input type="checkbox" data-tool="subtitle_generate_srt" ${d.tools.includes("subtitle_generate_srt") ? "checked" : ""} /> <div><strong>subtitle_generate_srt</strong><div class="form-hint">默认 allow</div></div></label>
          </div>
        </div>`;
    } else if (step === 3) {
      panel = `
        <div class="form-grid">
          <div class="form-field"><label>授权对象</label>
            <select id="czGrant">
              <option value="全体员工"${d.grantGroup === "全体员工" ? " selected" : ""}>用户组：全体员工</option>
              <option value="内容运营"${d.grantGroup === "内容运营" ? " selected" : ""}>用户组：内容运营</option>
              <option value="暂不授权"${d.grantGroup === "暂不授权" ? " selected" : ""}>暂不授权（仅调试）</option>
            </select>
            <div class="form-hint">仅 Published 版本可 Grant；员工端立即可见性取决于发布状态。</div>
          </div>
        </div>
        <div class="scope-path-hint">IdentityGrant
  tenant_id = ${escapeHtml(state.tenant)}
  tenant_workspace_id = ${escapeHtml(state.workspace)}
  identity_version = (发布后填写)
  grantee_type = group
  grantee = ${escapeHtml(d.grantGroup)}</div>`;
    } else {
      panel = `<div class="check-list">
        <div class="check-row ok"><span>✓</span><div><strong>基本信息</strong><div class="form-hint">${escapeHtml(d.name || "（未填写）")} · ${escapeHtml(d.desc || "无描述")}</div></div></div>
        <div class="check-row ok"><span>✓</span><div><strong>模型</strong><div class="form-hint">profile=${escapeHtml(d.model)}</div></div></div>
        <div class="check-row ok"><span>✓</span><div><strong>能力</strong><div class="form-hint">Skill=${escapeHtml(d.skill)} · Tools=${d.tools.length}</div></div></div>
        <div class="check-row ${d.grantGroup === "暂不授权" ? "warn" : "ok"}"><span>${d.grantGroup === "暂不授权" ? "!" : "✓"}</span>
          <div><strong>授权</strong><div class="form-hint">${escapeHtml(d.grantGroup)}</div></div></div>
        <div class="check-row warn"><span>!</span><div><strong>发布门禁</strong><div class="form-hint">Secret 轮换与评测集仍需处理；原型将写入草稿。</div></div></div>
      </div>
      <p class="form-hint" style="margin-top:12px">产物路径将在运行时写入：
        <code>tenants/${escapeHtml(state.tenant)}/workspaces/${escapeHtml(state.workspace)}/users/{owner_principal}/…</code></p>`;
    }

    return pageShell({
      crumb: "管理控制台 / 智能体 / 创建",
      title: "创建智能体",
      desc: "向导会创建 IdentityDefinition 与 Draft Version；发布前可反复修改。",
      body: `
        <section class="card">
          <div class="wizard-steps">
            ${steps
              .map((label, i) => {
                const cls = i === step ? "is-active" : i < step ? "is-done" : "";
                return `<div class="wizard-step ${cls}"><span class="step-num">${i + 1}</span>${label}</div>`;
              })
              .join("")}
          </div>
          <div class="card-body">${panel}</div>
          <div class="wizard-nav">
            <button class="btn" data-cz="prev" ${step === 0 ? "disabled" : ""}>上一步</button>
            <div style="display:flex;gap:8px">
              <button class="btn" data-cz="save">保存草稿</button>
              ${step < steps.length - 1
                ? `<button class="btn btn-primary" data-cz="next">下一步</button>`
                : `<button class="btn btn-primary" data-cz="submit" ${can("publish") ? "" : "disabled title='当前角色无发布权限，可先存草稿'"}>创建并提交发布</button>`}
            </div>
          </div>
        </section>`,
    });
  }

  function renderSkillImport() {
    if (!can("createAgent")) return denyPage("导入 Skill");
    return pageShell({
      crumb: "管理控制台 / Skill / 导入",
      title: "导入 Skill",
      desc: "支持目录扫描 / 包上传 / Registry。导入后生成 Draft，发布前校验 Schema 与依赖。",
      body: `
        <section class="card">
          <div class="card-body">
            <div class="form-grid">
              <div class="form-field"><label>来源</label>
                <select><option>本地目录</option><option>上传 ZIP</option><option>Git 仓库</option></select>
              </div>
              <div class="form-field"><label>包路径 / URL</label>
                <input placeholder="resources/skills/my-skill 或 https://…" />
              </div>
              <div class="form-field full"><label>导入说明</label>
                <textarea placeholder="变更说明（可选）"></textarea>
              </div>
            </div>
            <div class="scope-path-hint" style="margin-top:12px">校验项
  SKILL.md frontmatter (name/description)
  agent.skill.json + schemas/input|output
  tools.allow ⊆ 空间可见 Tool
  签名/来源（生产必填）</div>
          </div>
          <div class="wizard-nav">
            <span></span>
            <button class="btn btn-primary" data-action="import-skill-submit">开始导入</button>
          </div>
        </section>`,
    });
  }

  /* ---------- Skills / Tools / Runs / Approvals / Audit / Settings ---------- */
  function renderSkills() {
    const rows = mock.skills
      .map(
        (s) => `<tr>
        <td><strong>${escapeHtml(s.name)}</strong><div class="form-hint">${escapeHtml(s.id)}</div></td>
        <td>${escapeHtml(s.version)}</td><td>${statusPill(s.status)}</td>
        <td>${s.refs}</td><td>${escapeHtml(s.owner)}</td><td>${escapeHtml(s.updated)}</td>
        <td class="actions"><button class="btn btn-sm" data-action="view-skill">详情</button></td>
      </tr>`
      )
      .join("");
    return pageShell({
      crumb: "管理控制台 / Skill",
      title: "Skill",
      desc: "版本化能力包。编辑走新草稿，不覆盖已发布。",
      actions: can("createAgent") ? `<button class="btn btn-primary" data-nav-go="skill-import">导入 Skill</button>` : "",
      body: `<section class="card"><div class="table-wrap"><table class="data">
        <thead><tr><th>名称</th><th>版本</th><th>状态</th><th>引用</th><th>负责人</th><th>更新</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table></div></section>`,
    });
  }

  function renderTools() {
    const rows = mock.tools
      .map(
        (t) => `<tr>
        <td><strong>${escapeHtml(t.name)}</strong><div class="form-hint">${escapeHtml(t.id)}</div></td>
        <td>${escapeHtml(t.type)}</td><td>${escapeHtml(t.url)}</td><td>${t.ops}</td>
        <td>${statusPill(t.health)}</td><td>${escapeHtml(t.sync)}</td>
        <td class="actions">${can("createAgent") ? `<button class="btn btn-sm" data-action="sync-tool">刷新差异</button>` : "—"}</td>
      </tr>`
      )
      .join("");
    return pageShell({
      crumb: "管理控制台 / 工具",
      title: "工具与连接器",
      desc: "Service → Operation。刷新生成草稿差异，不静默覆盖生产。",
      body: `<section class="card"><div class="table-wrap"><table class="data">
        <thead><tr><th>服务</th><th>类型</th><th>入口</th><th>操作数</th><th>健康</th><th>同步</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table></div></section>`,
    });
  }

  function renderRuns() {
    const visible =
      state.role === "end_user"
        ? mock.runs.filter((r) => r.user === "u_2001")
        : mock.runs;
    const rows = visible
      .map(
        (r) => `<tr>
        <td><code>${escapeHtml(r.id)}</code></td>
        <td>${escapeHtml(r.agent)}</td>
        <td>${statusPill(r.status)}</td>
        <td>${escapeHtml(r.userName)} <span class="form-hint">${escapeHtml(r.user)}</span></td>
        <td>${escapeHtml(r.duration)}</td>
        <td>${state.role === "auditor" ? "（脱敏）" : escapeHtml(r.error)}</td>
        <td>${escapeHtml(r.at)}</td>
        <td class="actions"><button class="btn btn-sm" data-open-run="${r.id}">详情</button></td>
      </tr>`
      )
      .join("");

    return pageShell({
      crumb: "管理控制台 / Run",
      title: "Run",
      desc: "默认脱敏摘要。产物目录仅 owner 可下载；管理读取需提权。",
      body: `
        <section class="card" style="margin-bottom:12px">
          <div class="card-header"><h2 class="card-title">Run 详情 · ${mock.runDetail.id}</h2>${statusPill("completed")}</div>
          <div class="card-body"><div class="timeline">
            ${mock.runDetail.timeline
              .map(
                (t) => `<div class="timeline-item">
                <div class="tl-dot ${t.tone || ""}"></div>
                <div>
                  <div class="tl-title">${escapeHtml(t.title)}</div>
                  <div class="tl-meta">${escapeHtml(t.meta)}</div>
                  ${t.body ? `<div class="tl-body">${escapeHtml(t.body)}</div>` : ""}
                </div></div>`
              )
              .join("")}
          </div>
          <p class="form-hint" style="margin-top:8px">产物路径：
            <code>tenants/${escapeHtml(state.tenant)}/workspaces/${escapeHtml(state.workspace)}/users/顾南/发展规划助手/2026-07-28/run_9f2a/</code>
            <button class="btn btn-sm" data-nav-go="artifacts" style="margin-left:8px">打开产出物目录</button>
          </p>
          </div>
        </section>
        <section class="card"><div class="table-wrap"><table class="data">
          <thead><tr><th>Run</th><th>智能体</th><th>状态</th><th>用户</th><th>耗时</th><th>错误</th><th>时间</th><th></th></tr></thead>
          <tbody>${rows}</tbody></table></div>
          <div class="table-meta">当前角色：${escapeHtml(ROLES[state.role].label)}${state.role === "end_user" ? " · 仅本人 Run" : ""}</div>
        </section>`,
    });
  }

  /**
   * Artifact access decision (mirrors backend rules).
   * Returns { ok, reason, requiresElevate }
   */
  function checkArtifactAccess(ownerName, pathParts) {
    const me = state.role === "end_user" ? "顾南" : ROLES[state.role].user;
    const isOwner = ownerName === me;
    if (isOwner) return { ok: true, reason: "owner", requiresElevate: false };
    if (can("readAnyArtifact") && state.elevateRequest && state.elevateRequest.owner === ownerName) {
      return { ok: true, reason: "elevated+audit", requiresElevate: false };
    }
    if (can("elevateArtifact")) {
      return { ok: false, reason: "needs_elevate", requiresElevate: true };
    }
    return { ok: false, reason: "forbidden", requiresElevate: false };
  }

  function listArtifactChildren(owner, path) {
    let node = mock.artifactFS[owner];
    if (!node) return { kind: "missing" };
    for (const key of path) {
      if (!node || typeof node !== "object" || Array.isArray(node)) return { kind: "missing" };
      node = node[key];
      if (node === undefined) return { kind: "missing" };
    }
    if (Array.isArray(node)) return { kind: "dir", children: node.map((f) => ({ ...f, type: "file" })) };
    if (node && typeof node === "object") {
      return {
        kind: "dir",
        children: Object.keys(node).map((k) => ({
          name: k,
          type: Array.isArray(node[k]) ? "run-dir" : "folder",
        })),
      };
    }
    return { kind: "missing" };
  }

  function renderArtifactExplorer() {
    const owners = Object.keys(mock.artifactFS);
    const me = state.role === "end_user" ? "顾南" : null;

    // End user: only own tree
    const visibleOwners = me ? [me] : owners;
    const path = state.artifactPath.slice();
    // ensure path starts with a visible owner
    if (!visibleOwners.includes(path[0])) {
      path[0] = visibleOwners[0];
      path.length = 1;
      state.artifactPath = path.slice();
    }

    const owner = path[0];
    const rest = path.slice(1);
    const access = checkArtifactAccess(owner, rest);

    // Build tree UI
    const treeHtml = visibleOwners
      .map((o) => {
        const locked = o !== (me || o) && !can("readAnyArtifact") && !(can("elevateArtifact"));
        const isOpen = path[0] === o || (!me && can("readAnyArtifact"));
        let html = `<button type="button" class="tree-node${path[0] === o ? " is-active" : ""}${locked ? " is-locked" : ""}"
          data-art-path="${escapeHtml([o].join("/"))}" style="padding-left:8px">
          <span class="tree-icon">👤</span><span>${escapeHtml(o)}${o === me ? "（我）" : ""}</span>
          ${locked ? `<span class="pill pill-danger" style="margin-left:auto">锁定</span>` : ""}
        </button>`;
        if (!isOpen && !me) return html;
        // expand agents
        const agents = Object.keys(mock.artifactFS[o] || {});
        agents.forEach((ag) => {
          const active = path[0] === o && path[1] === ag;
          html += `<button type="button" class="tree-node${active ? " is-active" : ""}"
            data-art-path="${escapeHtml([o, ag].join("/"))}" style="padding-left:24px">
            <span class="tree-icon">◈</span><span>${escapeHtml(ag)}</span></button>`;
          if (active) {
            Object.keys(mock.artifactFS[o][ag] || {}).forEach((day) => {
              const activeDay = path[2] === day;
              html += `<button type="button" class="tree-node${activeDay ? " is-active" : ""}"
                data-art-path="${escapeHtml([o, ag, day].join("/"))}" style="padding-left:40px">
                <span class="tree-icon">📅</span><span>${escapeHtml(day)}</span></button>`;
              if (activeDay) {
                Object.keys(mock.artifactFS[o][ag][day] || {}).forEach((run) => {
                  const activeRun = path[3] === run;
                  html += `<button type="button" class="tree-node${activeRun ? " is-active" : ""}"
                    data-art-path="${escapeHtml([o, ag, day, run].join("/"))}" style="padding-left:56px">
                    <span class="tree-icon">▶</span><span>${escapeHtml(run)}</span></button>`;
                });
              }
            });
          }
        });
        return html;
      })
      .join("");

    let detail = "";
    if (!access.ok && access.requiresElevate) {
      detail = `<div class="access-denied">
        <strong>默认无权查看他人产出物</strong>
        目录归属：<code>${escapeHtml(owner)}</code>。<br/>
        当前角色「${escapeHtml(ROLES[state.role].label)}」可发起提权申请（需填写原因，写入审计）。
        <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
          <input id="elevateReason" class="field" style="min-width:220px" placeholder="提权原因（工单/投诉单号）" />
          <button class="btn btn-primary" data-action="elevate" data-owner="${escapeHtml(owner)}">申请提权读取</button>
        </div>
        <div class="form-hint" style="margin-top:8px">后端伪代码：WHERE tenant_id=? AND owner_principal_id=? 无结果且无 elevate claim → 拒绝。</div>
      </div>`;
    } else if (!access.ok) {
      detail = `<div class="access-denied">
        <strong>403 无权访问</strong>
        员工只能浏览自己的产出物目录。跨用户 ID 猜测不会返回内容。
      </div>`;
    } else {
      const listing = listArtifactChildren(owner, rest);
      if (listing.kind === "missing") {
        detail = `<div class="empty"><div class="empty-title">路径不存在</div>可能已被保留期清理，或路径无效。</div>`;
      } else if (rest.length < 4) {
        detail = `<div class="empty">
          <div class="empty-title">${rest.length === 0 ? "选择左侧智能体目录" : "继续展开日期与 Run"}</div>
          逻辑存储前缀：<br/><code>tenants/${escapeHtml(state.tenant)}/workspaces/${escapeHtml(state.workspace)}/users/${escapeHtml(owner)}/${rest.map(escapeHtml).join("/")}</code>
        </div>`;
      } else {
        const files = listing.children;
        detail = `
          <div class="table-wrap">
            <table class="data">
              <thead><tr><th>名称</th><th>类型</th><th>大小</th><th>时间</th><th>归属</th><th></th></tr></thead>
              <tbody>
                ${files
                  .map(
                    (f) => `<tr>
                    <td><button class="btn btn-sm" data-art-file="${escapeHtml(f.name)}">${escapeHtml(f.name)}</button></td>
                    <td>${escapeHtml(f.mime || "file")}</td>
                    <td>${escapeHtml(f.size || "—")}</td>
                    <td>${escapeHtml(f.at || "—")}</td>
                    <td><span class="pill ${owner === (me || owner) ? "pill-success" : "pill-warning"}">${owner === (me || owner) ? "本人" : "已提权"}</span></td>
                    <td class="actions">
                      <button class="btn btn-sm" data-art-file="${escapeHtml(f.name)}">预览</button>
                      <button class="btn btn-sm" data-action="download">下载</button>
                    </td>
                  </tr>`
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
          <div id="artPreview"></div>
          ${access.reason === "elevated+audit" ? `<div class="table-meta" style="color:var(--warning)">已通过提权访问 · 审计事件已记录（原型模拟）</div>` : ""}`;
      }
    }

    const crumbParts = ["产出物", ...path];
    const crumbHtml = crumbParts
      .map((p, i) => {
        const target = path.slice(0, i).join("/");
        return `<button type="button" data-art-path="${escapeHtml(target)}">${escapeHtml(p)}</button>` + (i < crumbParts.length - 1 ? `<span class="sep">/</span>` : "");
      })
      .join("");

    return pageShell({
      crumb: `管理控制台 / 产出物目录`,
      title: state.mode === "workbench" ? "我的产出物" : "产出物目录",
      desc:
        me
          ? "以文件目录方式浏览本人产出物。他人目录不可见。"
          : "按 owner 目录隔离；默认只能打开自己的目录，跨用户需提权+审计。",
      actions: `<span class="pill pill-info">owner 隔离</span>`,
      body: `
        <section class="card">
          <div class="breadcrumb-path">${crumbHtml}</div>
          <div class="card-body">
            <div class="file-explorer">
              <div class="card" style="margin:0">
                <div class="card-header"><h2 class="card-title">目录树</h2>
                  <span class="form-hint">${me ? "仅本人" : "全部 owner（受策略约束）"}</span>
                </div>
                <div class="file-tree">${treeHtml}</div>
              </div>
              <div class="card" style="margin:0">
                <div class="card-header">
                  <h2 class="card-title">${escapeHtml(path.join(" / ") || "根")}</h2>
                  ${statusPill(access.ok ? "published" : "failed").replace("已发布", access.ok ? "可访问" : "受限").replace("失败", "受限")}
                </div>
                ${detail}
              </div>
            </div>
          </div>
        </section>
        <section class="card" style="margin-top:12px">
          <div class="card-header"><h2 class="card-title">权限规则（与后端一致）</h2></div>
          <div class="card-body">
            <div class="scope-path-hint">访问判定
  1. Principal 必须属于当前 tenant
  2. 列表/读取强制 owner_principal_id = Principal
  3. 管理角色默认仅元数据；正文/文件需 elevate claim + reason
  4. 下载使用短时签名 URL，签发前二次校验 owner
  5. 对象前缀 tenants/{t}/workspaces/{w}/users/{owner}/… 不可枚举
  6. 任何失败写安全日志（不回显他人路径是否存在时可统一 404）</div>
          </div>
        </section>`,
    });
  }

  function renderApprovals() {
    if (!can("approve") && state.role !== "platform_admin") return denyPage("处理审批");
    const rows = mock.approvals
      .map(
        (a) => `<tr>
        <td><code>${escapeHtml(a.id)}</code></td>
        <td><code>${escapeHtml(a.tool)}</code></td>
        <td>${escapeHtml(a.agent)}</td>
        <td>${statusPill(a.risk)}</td>
        <td>${escapeHtml(a.wait)}</td>
        <td>${escapeHtml(a.user)}</td>
        <td>${escapeHtml(a.reason)}</td>
        <td class="actions">
          <button class="btn btn-sm btn-primary" data-action="approve" data-id="${a.id}">批准</button>
          <button class="btn btn-sm btn-danger" data-action="deny" data-id="${a.id}">拒绝</button>
        </td>
      </tr>`
      )
      .join("");
    return pageShell({
      crumb: "管理控制台 / 审批",
      title: "审批",
      desc: "高风险 Tool 的 ask 决策。批准后 Run 恢复，owner 保持原用户。",
      body: `<section class="card"><div class="table-wrap"><table class="data">
        <thead><tr><th>审批</th><th>工具</th><th>智能体</th><th>风险</th><th>等待</th><th>用户</th><th>原因</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table></div></section>`,
    });
  }

  function renderAudit() {
    if (!["auditor", "ws_admin", "tenant_admin", "platform_admin"].includes(state.role)) {
      return denyPage("查看审计日志");
    }
    const rows = mock.audit
      .map(
        (a) => `<tr>
        <td>${escapeHtml(a.at)}</td><td>${escapeHtml(a.actor)}</td>
        <td>${escapeHtml(a.action)}</td><td>${escapeHtml(a.target)}</td>
        <td>${escapeHtml(a.result)}</td><td>${escapeHtml(a.reason)}</td>
      </tr>`
      )
      .join("");
    return pageShell({
      crumb: "管理控制台 / 审计",
      title: "审计日志",
      desc: "不可修改。含越权拒绝、提权读取、发布与授权变更。",
      body: `<section class="card"><div class="table-wrap"><table class="data">
        <thead><tr><th>时间</th><th>操作者</th><th>动作</th><th>对象</th><th>结果</th><th>原因</th></tr></thead>
        <tbody>${rows}</tbody></table></div></section>`,
    });
  }

  function renderSettings() {
    if (!can("manageMembers")) return denyPage("管理工作空间成员");
    return pageShell({
      crumb: "管理控制台 / 设置",
      title: "工作空间设置",
      desc: "成员、角色与智能体授权。",
      body: `
        <div class="grid grid-2">
          <section class="card">
            <div class="card-header"><h2 class="card-title">成员与角色</h2></div>
            <div class="card-body tight"><table class="data">
              <thead><tr><th>成员</th><th>角色</th><th>状态</th></tr></thead>
              <tbody>
                <tr><td>赵安</td><td>空间管理员</td><td>${statusPill("published").replace("已发布", "启用")}</td></tr>
                <tr><td>林晓晴</td><td>智能体开发者</td><td>${statusPill("published").replace("已发布", "启用")}</td></tr>
                <tr><td>李衡</td><td>业务运营</td><td>${statusPill("published").replace("已发布", "启用")}</td></tr>
                <tr><td>顾南</td><td>企业员工</td><td>${statusPill("published").replace("已发布", "启用")}</td></tr>
              </tbody>
            </table></div>
          </section>
          <section class="card">
            <div class="card-header"><h2 class="card-title">智能体授权</h2></div>
            <div class="card-body"><div class="kv-list">
              <div class="kv"><span class="kv-k">发展规划助手@v1.4.2</span><span class="kv-v">组「全体员工」 · 128 人</span></div>
              <div class="kv"><span class="kv-k">内容策划助手@v2.1.0</span><span class="kv-v">组「内容运营」 · 56 人</span></div>
            </div></div>
          </section>
        </div>`,
    });
  }

  /* ---------- Workbench ---------- */
  function renderMyAgents() {
    const cards = mock.myAgents
      .map(
        (a) => `<article class="card agent-card" data-open-chat="${a.id}" tabindex="0">
        <div class="agent-card-head">
          <span class="avatar">${escapeHtml(a.name.slice(0, 1))}</span>
          <div><h3>${escapeHtml(a.name)}</h3><p>${escapeHtml(a.desc)}</p></div>
        </div>
        <div class="agent-card-foot"><span>最近：${escapeHtml(a.last)}</span><span class="pill pill-success">已授权</span></div>
      </article>`
      )
      .join("");
    return pageShell({
      crumb: "用户工作台 / 我的智能体",
      title: "我的智能体",
      desc: "仅显示 IdentityGrant 授权给你的已发布智能体。",
      body: `<div class="agent-cards">${cards}</div>`,
    });
  }

  function renderChat() {
    const session = mock.sessions[0];
    const msgs = session.messages
      .map((m) => {
        if (m.role === "user") return `<div class="msg user">${escapeHtml(m.text)}</div>`;
        const steps = m.steps ? `<div class="msg-steps">执行摘要：${m.steps.map(escapeHtml).join(" → ")}</div>` : "";
        return `<div class="msg agent">${escapeHtml(m.text)}${steps}</div>`;
      })
      .join("");
    return pageShell({
      crumb: "用户工作台 / 会话",
      title: session.title,
      desc: "会话与产物仅本人可见。",
      actions: `<button class="btn" data-nav-go="my-artifacts">查看产出物目录</button>`,
      body: `<div class="workbench-layout" style="grid-template-columns:1fr 1.2fr">
        <section class="card chat-panel">
          <div class="card-header"><h2 class="card-title">消息</h2><span class="pill pill-muted">${escapeHtml(session.agent)}</span></div>
          <div class="chat-messages" id="chatMessages">
            <div class="msg system">安全提示：仅显示脱敏执行步骤，不暴露模型私有推理。</div>
            ${msgs}
          </div>
          <form class="chat-composer" id="chatForm">
            <label class="sr-only" for="chatInput">消息</label>
            <input id="chatInput" placeholder="输入消息，Enter 发送" autocomplete="off" />
            <button class="btn btn-primary" type="submit">发送</button>
          </form>
        </section>
        <section class="card">
          <div class="card-header"><h2 class="card-title">本次产物</h2></div>
          <div class="artifact-item">
            <div class="artifact-name">plan.json</div>
            <div class="artifact-meta">application/json · 12 KB · 路径含 owner=顾南</div>
            <button class="btn btn-sm" style="margin-top:8px" data-nav-go="my-artifacts">在目录中打开</button>
          </div>
          <div class="artifact-item">
            <div class="artifact-name">plan-summary.md</div>
            <div class="artifact-meta">text/markdown · 4 KB</div>
          </div>
          <div class="card-body">
            <div class="scope-path-hint">storage key
tenants/${escapeHtml(state.tenant)}/workspaces/${escapeHtml(state.workspace)}/users/u_2001/发展规划助手/2026-07-28/run_9f2a/plan.json</div>
          </div>
        </section>
      </div>`,
    });
  }

  function renderMyRuns() {
    const rows = mock.runs
      .filter((r) => r.user === "u_2001")
      .map(
        (r) => `<tr>
        <td><code>${escapeHtml(r.id)}</code></td><td>${escapeHtml(r.agent)}</td>
        <td>${statusPill(r.status)}</td><td>${escapeHtml(r.at)}</td>
        <td class="actions"><button class="btn btn-sm" data-nav-go="my-artifacts">产物</button></td>
      </tr>`
      )
      .join("");
    return pageShell({
      crumb: "用户工作台 / 我的任务",
      title: "我的任务",
      desc: "仅本人发起的 Run。",
      body: `<section class="card"><div class="table-wrap"><table class="data">
        <thead><tr><th>Run</th><th>智能体</th><th>状态</th><th>时间</th><th></th></tr></thead>
        <tbody>${rows || `<tr><td colspan="5"><div class="empty">暂无任务</div></td></tr>`}</tbody>
      </table></div></section>`,
    });
  }

  function renderMyMemory() {
    const rows = mock.memory
      .map(
        (m) => `<tr>
        <td><code>${escapeHtml(m.key)}</code></td><td>${escapeHtml(m.value)}</td><td>${escapeHtml(m.source)}</td>
        <td class="actions">
          <button class="btn btn-sm" data-action="edit-memory">纠正</button>
          <button class="btn btn-sm btn-danger" data-action="delete-memory">删除</button>
        </td>
      </tr>`
      )
      .join("");
    return pageShell({
      crumb: "用户工作台 / 我的记忆",
      title: "我的记忆",
      desc: "命名空间：tenant + workspace + identity + user。",
      body: `<section class="card"><div class="table-wrap"><table class="data">
        <thead><tr><th>键</th><th>值</th><th>来源</th><th></th></tr></thead>
        <tbody>${rows}</tbody></table></div></section>`,
    });
  }

  /* ---------- Router ---------- */
  function renderConsolePage() {
    const id = currentNavId();
    if (id === "agents") {
      const rest = state.route.split("/")[3];
      if (rest) {
        state.selectedAgentId = rest;
        return renderAgentDetail();
      }
      return renderAgents();
    }
    if (id === "agent-create") return renderAgentCreate();
    if (id === "skill-import") return renderSkillImport();
    if (id === "skills") return renderSkills();
    if (id === "tools") return renderTools();
    if (id === "runs") return renderRuns();
    if (id === "artifacts") return renderArtifactExplorer();
    if (id === "approvals") return renderApprovals();
    if (id === "audit") return renderAudit();
    if (id === "settings") return renderSettings();
    return renderOverview();
  }

  function renderWorkbenchPage() {
    const id = currentNavId();
    if (id === "chat") return renderChat();
    if (id === "my-runs") return renderMyRuns();
    if (id === "my-artifacts" || id === "artifacts") return renderArtifactExplorer();
    if (id === "my-memory") return renderMyMemory();
    return renderMyAgents();
  }

  function render() {
    if (state.mode === "console" && !state.route.startsWith("#/console")) state.route = "#/console/overview";
    if (state.mode === "workbench" && !state.route.startsWith("#/app")) state.route = "#/app/my-agents";

    applyRoleChrome();
    renderNav();
    const main = $("#main");
    main.innerHTML = state.mode === "console" ? renderConsolePage() : renderWorkbenchPage();
    bindMain();
  }

  function navigate(hash) {
    state.route = hash;
    if (location.hash !== hash) location.hash = hash;
    else render();
  }

  function go(id) {
    const prefix = state.mode === "console" ? "console" : "app";
    navigate(`#/${prefix}/${id}`);
  }

  function bindMain() {
    $$("#main [data-go]").forEach((el) => {
      const jump = () => navigate(el.dataset.go);
      el.addEventListener("click", jump);
      el.addEventListener("keydown", (e) => e.key === "Enter" && jump());
    });
    $$("#main [data-nav-go]").forEach((el) => {
      el.addEventListener("click", () => {
        const id = el.dataset.navGo;
        // map some ids across modes
        if (id === "artifacts" && state.mode === "workbench") return go("my-artifacts");
        if (id === "agent-create" || id === "skill-import") {
          state.mode = "console";
          return go(id);
        }
        go(id);
      });
    });
    $$("#main [data-open-agent]").forEach((el) => {
      el.addEventListener("click", () => {
        state.selectedAgentId = el.dataset.openAgent;
        state.agentTab = "overview";
        navigate(`#/console/agents/${el.dataset.openAgent}`);
      });
    });
    $$("#main [data-agent-tab]").forEach((el) => {
      el.addEventListener("click", () => {
        state.agentTab = el.dataset.agentTab;
        render();
      });
    });
    $$("#main [data-open-chat]").forEach((el) => {
      el.addEventListener("click", () => {
        state.mode = "workbench";
        navigate("#/app/chat");
      });
    });

    const statusFilter = $("#agentStatusFilter");
    if (statusFilter) {
      statusFilter.addEventListener("change", () => {
        state.filterStatus = statusFilter.value;
        render();
      });
    }

    // wizard
    $$("#main [data-cz]").forEach((el) => {
      el.addEventListener("click", () => collectWizard());
      el.addEventListener("click", () => {
        const act = el.dataset.cz;
        if (act === "prev") state.createStep = Math.max(0, state.createStep - 1);
        if (act === "next") state.createStep = Math.min(4, state.createStep + 1);
        if (act === "save") toast("草稿已保存（模拟）", "success");
        if (act === "submit") {
          if (!state.createDraft.name) {
            toast("请先填写名称", "danger");
            state.createStep = 0;
          } else {
            toast(can("publish") ? "已创建 Draft 并提交发布流程（模拟）" : "已保存草稿，当前角色无法发布", "success");
          }
        }
        if (act !== "save") render();
      });
    });

    // artifact tree
    $$("#main [data-art-path]").forEach((el) => {
      el.addEventListener("click", () => {
        const raw = el.dataset.artPath;
        state.artifactPath = raw ? raw.split("/") : [];
        state.elevateRequest = null;
        render();
      });
    });
    $$("#main [data-art-file]").forEach((el) => {
      el.addEventListener("click", () => {
        const name = el.dataset.artFile;
        const owner = state.artifactPath[0];
        const rest = state.artifactPath.slice(1);
        const access = checkArtifactAccess(owner, rest);
        if (!access.ok) {
          toast("无权预览该文件", "danger");
          return;
        }
        const listing = listArtifactChildren(owner, rest);
        const file = (listing.children || []).find((f) => f.name === name);
        const box = $("#artPreview");
        if (box && file) {
          box.innerHTML = `<div class="file-preview">${escapeHtml(file.preview || "（无预览）")}</div>
            <div class="table-meta">预览内容来自 owner=${escapeHtml(owner)} 的产物；下载将签发短时 URL 并审计。</div>`;
        }
      });
    });

    const form = $("#chatForm");
    if (form) {
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const input = $("#chatInput");
        const text = input.value.trim();
        if (!text) return;
        mock.sessions[0].messages.push({ role: "user", text });
        mock.sessions[0].messages.push({
          role: "agent",
          text: "（原型）已收到。将按 Identity 绑定 Skill 执行，产物写入你的私有目录。",
          steps: ["Grant 校验", "Skill 执行", "Artifact → users/顾南/…"],
        });
        input.value = "";
        render();
        const box = $("#chatMessages");
        if (box) box.scrollTop = box.scrollHeight;
      });
    }

    $$("#main [data-action]").forEach((el) => {
      el.addEventListener("click", () => {
        const action = el.dataset.action;
        if (action === "elevate") {
          const reason = ($("#elevateReason") && $("#elevateReason").value.trim()) || "";
          if (!reason) {
            toast("请填写提权原因", "danger");
            return;
          }
          state.elevateRequest = { owner: el.dataset.owner, reason };
          mock.audit.unshift({
            at: "刚刚",
            actor: ROLES[state.role].user,
            action: "提权读取产物",
            target: `artifacts/${el.dataset.owner}/…`,
            result: "已授权+审计",
            reason,
          });
          toast("已授予临时读取权限，审计已记录", "success");
          render();
          return;
        }
        if (action === "approve") {
          toast(`已批准 ${el.dataset.id}，Run 可恢复且 owner 不变`, "success");
          return;
        }
        if (action === "deny") {
          toast(`已拒绝 ${el.dataset.id}`, "danger");
          return;
        }
        if (action === "publish-agent") {
          if (!can("publish")) {
            toast("当前角色无发布权限", "danger");
            return;
          }
          toast("发布检查未全部通过：请处理 Secret 与评测", "danger");
          return;
        }
        if (action === "download") {
          toast("短时签名 URL 已生成（模拟，15 分钟）· 已审计", "success");
          return;
        }
        if (action === "import-skill-submit") {
          toast("导入校验中…（模拟成功，已创建 Draft）", "success");
          return;
        }
        if (action === "save-draft") {
          toast("草稿已保存", "success");
          return;
        }
        toast("操作：" + action);
      });
    });
  }

  function collectWizard() {
    const name = $("#czName");
    const desc = $("#czDesc");
    const model = $("#czModel");
    const skill = $("#czSkill");
    const grant = $("#czGrant");
    if (name) state.createDraft.name = name.value;
    if (desc) state.createDraft.desc = desc.value;
    if (model) state.createDraft.model = model.value;
    if (skill) state.createDraft.skill = skill.value;
    if (grant) state.createDraft.grantGroup = grant.value;
    const tools = [];
    $$("#main [data-tool]").forEach((cb) => {
      if (cb.checked) tools.push(cb.dataset.tool);
    });
    if (tools.length || state.createStep === 2) state.createDraft.tools = tools;
  }

  function bindShell() {
    $("#roleSel").addEventListener("change", (e) => {
      state.role = e.target.value;
      const role = ROLES[state.role];
      state.mode = role.mode;
      state.elevateRequest = null;
      // end user artifact root
      if (state.role === "end_user") state.artifactPath = ["顾南", "发展规划助手", "2026-07-28", "run_9f2a"];
      else state.artifactPath = ["顾南", "发展规划助手", "2026-07-28", "run_9f2a"];
      navigate(state.mode === "console" ? "#/console/overview" : "#/app/my-agents");
      toast("已切换演示角色：" + role.label);
    });

    $("#btnApprovals").addEventListener("click", () => {
      state.mode = "console";
      navigate("#/console/approvals");
    });

    $("#tenantSel").addEventListener("change", () => {
      toast("已切换租户，前端缓存已清空（模拟）");
      state.elevateRequest = null;
      render();
    });
    $("#wsSel").addEventListener("change", () => {
      toast("已切换工作空间，前端缓存已清空（模拟）");
      state.elevateRequest = null;
      render();
    });

    $("#sidenav").addEventListener("click", (e) => {
      const modeBtn = e.target.closest("[data-switch-mode]");
      if (modeBtn) {
        state.mode = modeBtn.dataset.switchMode;
        navigate(state.mode === "console" ? "#/console/overview" : "#/app/my-agents");
        return;
      }
      const btn = e.target.closest("[data-nav]");
      if (!btn) return;
      go(btn.dataset.nav);
    });

    window.addEventListener("hashchange", () => {
      state.route = location.hash || state.route;
      if (state.route.startsWith("#/console")) state.mode = "console";
      if (state.route.startsWith("#/app")) state.mode = "workbench";
      render();
      $("#main").focus({ preventScroll: true });
    });
  }

  state.route = location.hash || "#/console/overview";
  if (state.route.startsWith("#/app")) state.mode = "workbench";
  bindShell();
  render();
})();
