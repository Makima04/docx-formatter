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
    const err = await res.json().catch(() => ({}));
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
