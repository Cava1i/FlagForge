export type ChallengeMetadata = {
  name: string;
  category: string;
  value: number;
  description: string;
  connection_info: string;
  tags: string[];
  hints: unknown[];
  solves?: number;
};

export type EditableChallengeMetadata = Pick<
  ChallengeMetadata,
  'name' | 'category' | 'value' | 'description' | 'connection_info' | 'tags' | 'hints'
>;

export type Challenge = Partial<ChallengeMetadata> & {
  id: string | number;
  path?: string;
  challenge_dir?: string;
  created_at?: string;
  updated_at?: string;
  metadata?: Partial<ChallengeMetadata>;
  distfiles?: string[];
};

export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'interrupted' | string;

export type Run = {
  id: string | number;
  challenge_id?: string | number;
  challenge_name?: string;
  status: RunStatus;
  active?: boolean;
  can_cancel?: boolean;
  model_specs?: string[];
  no_submit?: boolean;
  generate_writeup?: boolean;
  result_flag?: string | null;
  flag?: string | null;
  summary?: string | null;
  findings_summary?: string | null;
  result?: Record<string, unknown> | null;
  cost_usd?: number | null;
  log_path?: string | null;
  writeup_path?: string | null;
  winning_agent?: string | null;
  agent_session_available?: boolean;
  agent_skills?: string[];
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  updated_at?: string;
};

export type RunCreatePayload = {
  challenge_id: number;
  model_specs?: string[];
  agent_skills?: string[];
  no_submit: boolean;
  generate_writeup: boolean;
};

export type RunListOptions = {
  challengeId?: string | number;
  status?: string;
  active?: boolean;
};

export type RunLog = {
  run_id: string | number;
  path: string;
  content: string;
};

export type RunWriteup = {
  run_id: string | number;
  path?: string | null;
  content: string;
  available: boolean;
};

export type AgentChatMessage = {
  role: 'user' | 'agent' | string;
  content: string;
};

export type AgentChat = {
  run_id: string | number;
  available: boolean;
  model?: string | null;
  message?: AgentChatMessage;
  messages: AgentChatMessage[];
};

export type ModelCatalog = {
  models: string[];
  model_ids?: string[];
  default_models: string[];
  source?: 'api' | 'fallback' | string;
  base_url?: string;
  candidate_urls?: string[];
  configured?: boolean;
  model_count?: number;
  error?: string;
};

export type ModelApiTestResult = {
  ok: boolean;
  source: string;
  base_url?: string;
  candidate_urls: string[];
  checked_url: string;
  model_count: number;
  sample_models: string[];
  latency_ms?: number | null;
  error: string;
};

export type ManualChallengeFile = {
  file: File;
  name: string;
};

export type ManualChallengePayload = {
  slug?: string;
  metadata: Partial<EditableChallengeMetadata>;
  files: ManualChallengeFile[];
};

export type ConfigFieldStatus = {
  key: string;
  label: string;
  group: 'models' | 'ctfd' | 'agents' | 'writeup' | string;
  sensitive: boolean;
  configured: boolean;
  value?: string;
};

export type ConfigStatus = {
  env_path: string;
  fields: Record<string, ConfigFieldStatus>;
  agent_defaults?: {
    count: number;
    models: string[];
    skills: string[];
  };
  available_skills?: AvailableSkill[];
};

export type AvailableSkill = {
  name: string;
  description: string;
  path: string;
  selected: boolean;
};

export type RevealedSecret = {
  key: string;
  label: string;
  configured: boolean;
  value: string;
};

type ApiOptions = Omit<RequestInit, 'body'> & {
  body?: unknown;
};

const JSON_HEADERS = { 'Content-Type': 'application/json' };

export class ApiError extends Error {
  status: number;
  details: unknown;

  constructor(message: string, status: number, details: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';
  if (response.status === 204) return null;
  if (contentType.includes('application/json')) return response.json();
  return response.text();
}

function unwrapList<T>(data: unknown, keys: string[]): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>;
    for (const key of keys) {
      if (Array.isArray(record[key])) return record[key] as T[];
    }
  }
  return [];
}

function unwrapOne<T>(data: unknown, keys: string[]): T {
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>;
    for (const key of keys) {
      if (record[key] && typeof record[key] === 'object') return record[key] as T;
    }
  }
  return data as T;
}

function errorMessage(data: unknown, status: number): string {
  if (data && typeof data === 'object' && 'error' in data) {
    const error = (data as { error: unknown }).error;
    if (typeof error === 'string') return error;
    if (error && typeof error === 'object' && 'message' in error) {
      const message = (error as { message: unknown }).message;
      if (typeof message === 'string' && message.trim()) return message;
    }
  }

  return `请求失败，状态码 ${status}`;
}

export async function request<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body === undefined ? {} : JSON_HEADERS),
      ...options.headers,
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const data = await parseResponse(response);

  if (!response.ok) {
    throw new ApiError(errorMessage(data, response.status), response.status, data);
  }

  return data as T;
}

export async function requestForm<T>(path: string, form: FormData, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    method: options.method ?? 'POST',
    body: form,
  });
  const data = await parseResponse(response);

  if (!response.ok) {
    throw new ApiError(errorMessage(data, response.status), response.status, data);
  }

  return data as T;
}

export const api = {
  async listChallenges(): Promise<Challenge[]> {
    const data = await request<unknown>('/api/challenges');
    return unwrapList<Challenge>(data, ['challenges', 'items', 'data']);
  },

  async importChallenge(path: string): Promise<Challenge> {
    const data = await request<unknown>('/api/challenges', {
      method: 'POST',
      body: { path },
    });
    return unwrapOne<Challenge>(data, ['challenge', 'data']);
  },

  async createManualChallenge(payload: ManualChallengePayload): Promise<Challenge> {
    const form = new FormData();
    form.append('metadata', JSON.stringify(payload.metadata));
    if (payload.slug?.trim()) form.append('slug', payload.slug.trim());
    form.append('file_names', JSON.stringify(payload.files.map((file) => file.name)));
    for (const file of payload.files) {
      form.append('files', file.file);
    }

    const data = await requestForm<unknown>('/api/challenges/manual', form);
    return unwrapOne<Challenge>(data, ['challenge', 'data']);
  },

  async getChallenge(id: string | number): Promise<Challenge> {
    const data = await request<unknown>(`/api/challenges/${id}`);
    return unwrapOne<Challenge>(data, ['challenge', 'data']);
  },

  async updateChallenge(id: string | number, metadata: Partial<EditableChallengeMetadata>): Promise<Challenge> {
    const data = await request<unknown>(`/api/challenges/${id}`, {
      method: 'PUT',
      body: metadata,
    });
    return unwrapOne<Challenge>(data, ['challenge', 'data']);
  },

  async deleteChallenge(id: string | number, deleteFiles = false): Promise<Challenge> {
    const data = await request<unknown>(`/api/challenges/${id}`, {
      method: 'DELETE',
      body: { delete_files: deleteFiles },
    });
    return unwrapOne<Challenge>(data, ['challenge', 'data']);
  },

  async listRuns(options: RunListOptions = {}): Promise<Run[]> {
    const params = new URLSearchParams();
    if (options.challengeId !== undefined) params.set('challenge_id', String(options.challengeId));
    if (options.status) params.set('status', options.status);
    if (options.active !== undefined) params.set('active', String(options.active));
    const query = params.toString();
    const suffix = query ? `?${query}` : '';
    const data = await request<unknown>(`/api/runs${suffix}`);
    return unwrapList<Run>(data, ['runs', 'items', 'data']);
  },

  async createRun(payload: RunCreatePayload): Promise<Run> {
    const data = await request<unknown>('/api/runs', {
      method: 'POST',
      body: payload,
    });
    return unwrapOne<Run>(data, ['run', 'data']);
  },

  async getRun(id: string | number): Promise<Run> {
    const data = await request<unknown>(`/api/runs/${id}`);
    return unwrapOne<Run>(data, ['run', 'data']);
  },

  async deleteRun(id: string | number): Promise<Run> {
    const data = await request<unknown>(`/api/runs/${id}`, {
      method: 'DELETE',
    });
    return unwrapOne<Run>(data, ['run', 'data']);
  },

  async cancelRun(id: string | number): Promise<Run> {
    const data = await request<unknown>(`/api/runs/${id}/cancel`, {
      method: 'POST',
    });
    return unwrapOne<Run>(data, ['run', 'data']);
  },

  async getRunLog(id: string | number, tailLines?: number): Promise<RunLog> {
    const suffix = tailLines ? `?tail_lines=${encodeURIComponent(String(tailLines))}` : '';
    const data = await request<unknown>(`/api/runs/${id}/logs${suffix}`);
    return unwrapOne<RunLog>(data, ['log', 'data']);
  },

  async clearRunLog(id: string | number): Promise<RunLog> {
    const data = await request<unknown>(`/api/runs/${id}/logs`, {
      method: 'DELETE',
    });
    return unwrapOne<RunLog>(data, ['log', 'data']);
  },

  async getWriteup(id: string | number): Promise<RunWriteup> {
    const data = await request<unknown>(`/api/runs/${id}/writeup`);
    return unwrapOne<RunWriteup>(data, ['writeup', 'data']);
  },

  async getAgentMessages(id: string | number): Promise<AgentChat> {
    const data = await request<unknown>(`/api/runs/${id}/agent/messages`);
    return unwrapOne<AgentChat>(data, ['chat', 'data']);
  },

  async askAgent(id: string | number, message: string): Promise<AgentChat> {
    const data = await request<unknown>(`/api/runs/${id}/agent/messages`, {
      method: 'POST',
      body: { message },
    });
    return unwrapOne<AgentChat>(data, ['chat', 'data']);
  },

  async listModels(): Promise<ModelCatalog> {
    return request<ModelCatalog>('/api/models');
  },

  async testModels(payload: { base_url?: string; api_key?: string } = {}): Promise<ModelApiTestResult> {
    const data = await request<unknown>('/api/models/test', {
      method: 'POST',
      body: payload,
    });
    return unwrapOne<ModelApiTestResult>(data, ['test', 'data']);
  },

  async getConfig(): Promise<ConfigStatus> {
    const data = await request<unknown>('/api/config');
    return unwrapOne<ConfigStatus>(data, ['config', 'data']);
  },

  async revealSecret(key: string): Promise<RevealedSecret> {
    const data = await request<unknown>(`/api/config/secrets/${encodeURIComponent(key)}`);
    return unwrapOne<RevealedSecret>(data, ['secret', 'data']);
  },

  async updateConfig(values: Record<string, string>): Promise<ConfigStatus> {
    const data = await request<unknown>('/api/config', {
      method: 'PUT',
      body: { values },
    });
    return unwrapOne<ConfigStatus>(data, ['config', 'data']);
  },
};

export function challengeMeta(challenge: Challenge): Partial<ChallengeMetadata> {
  return {
    name: challenge.metadata?.name ?? challenge.name ?? '',
    category: challenge.metadata?.category ?? challenge.category ?? '',
    value: challenge.metadata?.value ?? challenge.value ?? 0,
    description: challenge.metadata?.description ?? challenge.description ?? '',
    connection_info: challenge.metadata?.connection_info ?? challenge.connection_info ?? '',
    tags: challenge.metadata?.tags ?? challenge.tags ?? [],
    hints: challenge.metadata?.hints ?? challenge.hints ?? [],
    solves: challenge.metadata?.solves ?? challenge.solves ?? 0,
  };
}

export function runSummary(run: Run): string {
  if (run.summary) return run.summary;
  if (run.findings_summary) return run.findings_summary;
  if (run.result && typeof run.result.summary === 'string') return run.result.summary;
  const flag = run.result_flag ?? run.flag;
  if (flag) return `Flag：${flag}`;
  return '暂无结果。';
}

export function runStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: '排队中',
    running: '运行中',
    succeeded: '成功',
    failed: '失败',
    cancelled: '已取消',
    interrupted: '已中断',
  };
  return labels[status] ?? status;
}

export function isRunTerminal(run: Pick<Run, 'status'>): boolean {
  return ['succeeded', 'failed', 'cancelled', 'interrupted'].includes(run.status);
}

export function canCancelRun(run: Run): boolean {
  return run.can_cancel ?? !isRunTerminal(run);
}

export function formatRunCost(value?: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return '-';
  if (value < 0.0001) return '<$0.0001';
  return `$${value.toFixed(4)}`;
}
