export const DEV_ROLE_SWITCHER = true;

export type PrincipalRole =
  | "platform_admin"
  | "tenant_admin"
  | "ws_admin"
  | "developer"
  | "operator"
  | "auditor"
  | "end_user";

export interface PrincipalProfile {
  role: PrincipalRole;
  label: string;
  tenantId: string;
  principalId: string;
  displayName: string;
  workspaceRoles: string[];
  groupIds: string[];
  mode: "console" | "workbench";
}

export const ROLES: Record<PrincipalRole, PrincipalProfile> = {
  platform_admin: {
    role: "platform_admin",
    label: "平台管理员",
    tenantId: "t-demo",
    principalId: "u_admin_platform",
    displayName: "韩启",
    workspaceRoles: ["platform_admin"],
    groupIds: [],
    mode: "console",
  },
  tenant_admin: {
    role: "tenant_admin",
    label: "企业管理员",
    tenantId: "t-demo",
    principalId: "u_admin_tenant",
    displayName: "沈舟",
    workspaceRoles: ["tenant_admin", "ws_admin"],
    groupIds: [],
    mode: "console",
  },
  ws_admin: {
    role: "ws_admin",
    label: "空间管理员",
    tenantId: "t-demo",
    principalId: "u_admin_ws",
    displayName: "赵安",
    workspaceRoles: ["ws_admin"],
    groupIds: [],
    mode: "console",
  },
  developer: {
    role: "developer",
    label: "智能体开发者",
    tenantId: "t-demo",
    principalId: "u_dev",
    displayName: "林晓晴",
    workspaceRoles: ["developer"],
    groupIds: [],
    mode: "console",
  },
  operator: {
    role: "operator",
    label: "业务运营",
    tenantId: "t-demo",
    principalId: "u_ops",
    displayName: "李衡",
    workspaceRoles: ["operator"],
    groupIds: [],
    mode: "console",
  },
  auditor: {
    role: "auditor",
    label: "审计员",
    tenantId: "t-demo",
    principalId: "u_auditor",
    displayName: "周谨",
    workspaceRoles: ["auditor"],
    groupIds: [],
    mode: "console",
  },
  end_user: {
    role: "end_user",
    label: "企业员工",
    tenantId: "t-demo",
    principalId: "u_alice",
    displayName: "顾南",
    workspaceRoles: ["end_user"],
    groupIds: ["all-staff"],
    mode: "workbench",
  },
};

export function canCreateAgent(p: PrincipalProfile): boolean {
  return ["platform_admin", "tenant_admin", "ws_admin", "developer"].includes(p.role);
}

export function canPublish(p: PrincipalProfile): boolean {
  return ["tenant_admin", "ws_admin"].includes(p.role);
}

export function canApprove(p: PrincipalProfile): boolean {
  return ["platform_admin", "tenant_admin", "ws_admin", "operator"].includes(p.role);
}

export function canManageMembers(p: PrincipalProfile): boolean {
  return ["tenant_admin", "ws_admin"].includes(p.role);
}
