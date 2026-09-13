import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useApp } from "../App";
import { PageShell } from "../components/PageShell";

interface AgentSession {
  session_id: string;
  messages: { role: string; content: string }[];
}

export function WorkbenchChatPage() {
  const { principal, toast } = useApp();
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [active, setActive] = useState<AgentSession | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function loadSessions() {
    try {
      const data = await api.get<AgentSession[]>("/api/v1/me/sessions", principal);
      setSessions(data);
      if (data[0]) setActive(data[0]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    void loadSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [principal.principalId]);

  async function send() {
    if (!text.trim() || !active) return;
    try {
      const res = await fetch("/chat/messages", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "X-Tenant-Id": principal.tenantId,
          "X-Principal-Id": principal.principalId,
          "X-Workspace-Roles": principal.workspaceRoles.join(","),
        },
        body: JSON.stringify({
          session_id: active.session_id,
          message: text.trim(),
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = (await res.json()) as { message?: string; output?: unknown };
      const reply = body.message || JSON.stringify(body.output || body);
      setActive((prev) =>
        prev
          ? {
              ...prev,
              messages: [
                ...prev.messages,
                { role: "user", content: text.trim() },
                { role: "assistant", content: reply },
              ],
            }
          : prev,
      );
      setText("");
      await loadSessions();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "danger");
    }
  }

  return (
    <PageShell crumb="用户工作台 / 会话" title="会话" desc="仅本人 Session">
      {error ? <div className="error-box">{error}</div> : null}
      {sessions.length === 0 ? (
        <div className="card">
          <div className="empty">
            <div className="empty-title">还没有会话</div>
            先到「我的智能体」开始会话
          </div>
        </div>
      ) : (
        <div className="chat-layout">
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">我的会话</h2>
            </div>
            <div className="card-body tight">
              {sessions.map((s) => (
                <button
                  key={s.session_id}
                  type="button"
                  className={`tree-node${active?.session_id === s.session_id ? " is-active" : ""}`}
                  onClick={() => setActive(s)}
                >
                  {s.session_id}
                </button>
              ))}
            </div>
          </div>
          <div className="card" style={{ display: "flex", flexDirection: "column" }}>
            <div className="card-header">
              <h2 className="card-title">{active?.session_id || "未选择"}</h2>
            </div>
            <div className="chat-messages">
              <div className="msg system">仅显示本人会话；跨用户 ID 返回 404。</div>
              {(active?.messages || []).map((m, i) => (
                <div key={i} className={`msg ${m.role === "user" ? "user" : "agent"}`}>
                  {m.content}
                </div>
              ))}
            </div>
            <form
              className="chat-composer"
              onSubmit={(e) => {
                e.preventDefault();
                void send();
              }}
            >
              <input value={text} onChange={(e) => setText(e.target.value)} placeholder="输入消息" />
              <button className="btn btn-primary" type="submit">
                发送
              </button>
            </form>
          </div>
        </div>
      )}
    </PageShell>
  );
}
