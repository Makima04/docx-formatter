import type { TaskInfo, TemplateItem, TemplateCreate, RedeemCheck, BatchStatus } from '../types';

const BASE = '';

function getHeaders(code?: string): Record<string, string> {
  const h: Record<string, string> = {};
  if (code) h['X-Redeem-Code'] = code;
  return h;
}

// ── Redeem ──────────────────────────────────────────────────────────

export async function checkCode(code: string): Promise<RedeemCheck> {
  const res = await fetch(`${BASE}/api/redeem/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) {
    await res.json().catch(() => ({}));
    return { valid: false, remaining: 0 };
  }
  return res.json();
}

// ── Format (single file) ────────────────────────────────────────────

export async function formatDocument(
  code: string,
  file: File,
  opts: {
    template_id?: number;
    template_name?: string;
    template_file?: File;
    template_description?: string;
  } = {},
): Promise<{ task_id: string }> {
  const fd = new FormData();
  fd.append('file', file);
  if (opts.template_id != null) fd.append('template_id', String(opts.template_id));
  if (opts.template_name) fd.append('template_name', opts.template_name);
  if (opts.template_file) fd.append('template_file', opts.template_file);
  if (opts.template_description) fd.append('template_description', opts.template_description);

  const res = await fetch(`${BASE}/api/format`, {
    method: 'POST',
    headers: getHeaders(code),
    body: fd,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
}

export async function pollTask(taskId: string): Promise<TaskInfo> {
  const res = await fetch(`${BASE}/api/tasks/${taskId}`);
  if (!res.ok) throw new Error('Failed to poll task');
  return res.json();
}

export function downloadUrl(taskId: string): string {
  return `${BASE}/download/${taskId}`;
}

// ── Templates ───────────────────────────────────────────────────────

export async function listTemplates(): Promise<TemplateItem[]> {
  const res = await fetch(`${BASE}/api/templates`);
  if (!res.ok) throw new Error('Failed to fetch templates');
  return res.json();
}

export async function getTemplate(id: number): Promise<TemplateItem> {
  const res = await fetch(`${BASE}/api/templates/${id}`);
  if (!res.ok) throw new Error('Template not found');
  return res.json();
}

export async function createTemplate(data: TemplateCreate): Promise<{ id: number }> {
  const res = await fetch(`${BASE}/api/templates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create template');
  }
  return res.json();
}

export async function updateTemplate(
  id: number,
  data: Partial<TemplateCreate>,
): Promise<void> {
  const res = await fetch(`${BASE}/api/templates/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update template');
  }
}

export async function deleteTemplate(id: number): Promise<void> {
  const res = await fetch(`${BASE}/api/templates/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to delete template');
  }
}

// ── Batch ───────────────────────────────────────────────────────────

export async function submitBatch(
  code: string,
  files: File[],
  opts: { template_id?: number } = {},
): Promise<{ batch_id: string }> {
  const fd = new FormData();
  files.forEach((f) => fd.append('files', f));
  if (opts.template_id != null) fd.append('template_id', String(opts.template_id));

  const res = await fetch(`${BASE}/api/batch`, {
    method: 'POST',
    headers: getHeaders(code),
    body: fd,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Batch submission failed');
  }
  return res.json();
}

export async function pollBatch(batchId: string): Promise<BatchStatus> {
  const res = await fetch(`${BASE}/api/batch/${batchId}`);
  if (!res.ok) throw new Error('Failed to poll batch');
  return res.json();
}

export function batchDownloadUrl(batchId: string): string {
  return `${BASE}/api/batch/${batchId}/download`;
}

// ── Admin ─────────────────────────────────────────────────────────

export interface RedeemCodeItem {
  id: number;
  code: string;
  total_quota: number;
  used_quota: number;
  is_active: number;
  created_at: string;
  expires_at: string | null;
}

function adminHeaders(adminKey: string): Record<string, string> {
  return { 'Content-Type': 'application/json', 'X-Admin-Key': adminKey };
}

export async function listAdminCodes(adminKey: string): Promise<RedeemCodeItem[]> {
  const res = await fetch(`${BASE}/api/redeem/admin/codes`, {
    headers: adminHeaders(adminKey),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch codes');
  }
  return res.json();
}

export async function createAdminCode(
  adminKey: string,
  data: { code?: string; total_quota: number; expires_at?: string; prefix?: string; count?: number },
): Promise<{ code?: string; codes?: string[] }> {
  const res = await fetch(`${BASE}/api/redeem/admin/codes`, {
    method: 'POST',
    headers: adminHeaders(adminKey),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create code');
  }
  return res.json();
}

export async function updateAdminCode(
  adminKey: string,
  id: number,
  data: { total_quota?: number; is_active?: boolean; expires_at?: string; clear_expires?: boolean },
): Promise<void> {
  const res = await fetch(`${BASE}/api/redeem/admin/codes/${id}`, {
    method: 'PUT',
    headers: adminHeaders(adminKey),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update code');
  }
}

export async function deleteAdminCode(adminKey: string, id: number): Promise<void> {
  const res = await fetch(`${BASE}/api/redeem/admin/codes/${id}`, {
    method: 'DELETE',
    headers: adminHeaders(adminKey),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to delete code');
  }
}

// ── Admin Settings ─────────────────────────────────────────────────

export interface LLMConfig {
  api_key: string;
  base_url: string;
  model: string;
  concurrent_requests: number;
}

export async function getLLMConfig(adminKey: string): Promise<LLMConfig> {
  const res = await fetch(`${BASE}/api/admin/settings/llm`, {
    headers: adminHeaders(adminKey),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to get LLM config');
  }
  return res.json();
}

export async function updateLLMConfig(
  adminKey: string,
  data: { api_key?: string; base_url?: string; model?: string; concurrent_requests?: number },
): Promise<void> {
  const res = await fetch(`${BASE}/api/admin/settings/llm`, {
    method: 'PUT',
    headers: adminHeaders(adminKey),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update LLM config');
  }
}

export async function listLLMModels(adminKey: string, params?: { api_key?: string; base_url?: string }): Promise<string[]> {
  const qs = new URLSearchParams();
  if (params?.api_key) qs.set('api_key', params.api_key);
  if (params?.base_url) qs.set('base_url', params.base_url);
  const query = qs.toString();
  const res = await fetch(`${BASE}/api/admin/settings/llm/models${query ? '?' + query : ''}`, {
    headers: adminHeaders(adminKey),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch models');
  }
  const data = await res.json();
  return data.models;
}

export async function testLLMConnection(
  adminKey: string,
  data: { api_key?: string; base_url?: string; model?: string },
): Promise<{ ok: boolean; message: string; model_count?: number; model_found?: boolean | null }> {
  const res = await fetch(`${BASE}/api/admin/settings/llm/test`, {
    method: 'POST',
    headers: adminHeaders(adminKey),
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    return { ok: false, message: err.detail || 'Connection test failed' };
  }
  return res.json();
}

export interface LLMLogItem {
  id: number;
  task_id: string | null;
  call_type: string;
  model: string;
  prompt: string;
  response: string;
  status: string;
  error_msg: string | null;
  latency_ms: number | null;
  created_at: string;
}

export async function getLLMLogs(adminKey: string, limit = 100, offset = 0): Promise<{ logs: LLMLogItem[]; total: number }> {
  const res = await fetch(`${BASE}/api/admin/settings/llm/logs?limit=${limit}&offset=${offset}`, {
    headers: adminHeaders(adminKey),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch LLM logs');
  }
  return res.json();
}
