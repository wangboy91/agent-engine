export interface IdentityDefinition {
  definition_id: string;
  tenant_id: string;
  tenant_workspace_id: string;
  key: string;
  name: string;
  description: string | null;
}

export interface IdentityVersion {
  version_id: string;
  definition_id: string;
  version: string;
  status: string;
  model_profile: string;
  system_prompt: string;
}

export interface ArtifactMeta {
  artifact_id: string;
  owner_principal_id: string;
  logical_path: string;
  media_type: string;
  size_bytes: number;
  created_at: string;
}

export interface MeArtifactDir {
  path: string;
  folders: string[];
  files: {
    name: string;
    type: string;
    artifact_id: string;
    media_type: string;
    size_bytes: number;
    created_at: string;
  }[];
}

export interface RunResultDto {
  run_id: string;
  status: string;
  skill_id: string;
  context?: Record<string, unknown> | null;
  artifacts?: unknown[];
}
