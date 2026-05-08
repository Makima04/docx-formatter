import React, { useState, useEffect, useRef } from 'react';
import FileUpload from '../components/FileUpload';
import { submitBatch, pollBatch, batchDownloadUrl, listTemplates } from '../api/client';
import { formatDuration } from '../utils/format';
import type { TemplateItem, BatchStatus } from '../types';

interface Props {
  code: string;
  onQuotaChange: () => void;
}

export default function Batch({ code, onQuotaChange }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [tplId, setTplId] = useState<number | undefined>();
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batch, setBatch] = useState<BatchStatus | null>(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startedAtRef = useRef<number>(0);

  useEffect(() => {
    listTemplates().then(setTemplates).catch(() => {});
  }, []);

  // Poll batch status
  useEffect(() => {
    if (!batchId) return;

    startedAtRef.current = Date.now();
    const tick = () => setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000));
    tick();
    const elapsedTimer = setInterval(tick, 1000);

    let pollTimer: ReturnType<typeof setInterval>;
    let pollInterval = 800;

    const poll = async () => {
      try {
        const data = await pollBatch(batchId);
        setBatch(data);
        if (data.status === 'completed' || data.status === 'partial' || data.status === 'failed') {
          clearInterval(pollTimer);
          clearInterval(elapsedTimer);
          onQuotaChange();
          return;
        }
        // Adaptive: fast first 30s, then normal
        const elapsed = Date.now() - startedAtRef.current;
        const next = elapsed < 30_000 ? 800 : 2000;
        if (next !== pollInterval) {
          pollInterval = next;
          clearInterval(pollTimer);
          pollTimer = setInterval(poll, pollInterval);
        }
      } catch {}
    };

    poll();
    pollTimer = setInterval(poll, pollInterval);

    return () => {
      clearInterval(pollTimer);
      clearInterval(elapsedTimer);
    };
  }, [batchId]);

  const handleSubmit = async () => {
    if (!files.length) return;
    setError('');
    setSubmitting(true);
    try {
      const { batch_id } = await submitBatch(code, files, { template_id: tplId });
      setBatchId(batch_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRestart = () => {
    setFiles([]);
    setBatchId(null);
    setBatch(null);
    setError('');
    setElapsed(0);
  };

  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      <div style={cardStyle}>
        <h2 style={cardTitle}>批量处理</h2>

        {!batchId ? (
          <>
            <FileUpload
              accept=".docx"
              multiple
              label="点击或拖拽上传多个 .docx 文件"
              onFiles={setFiles}
              files={files}
            />

            <div style={{ marginTop: 16 }}>
              <label style={labelStyle}>选择模板</label>
              <select
                value={tplId || ''}
                onChange={(e) => setTplId(e.target.value ? Number(e.target.value) : undefined)}
                style={inputStyle}
              >
                <option value="">默认（学术论文格式）</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.description || t.name}
                  </option>
                ))}
              </select>
            </div>

            {error && (
              <div style={{ background: '#fce8e6', color: '#c5221f', padding: '10px 14px', borderRadius: 8, fontSize: 13, marginTop: 14 }}>
                {error}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={!files.length || submitting}
              style={{
                width: '100%',
                marginTop: 18,
                padding: '14px',
                background: 'linear-gradient(135deg, #1a73e8, #0d47a1)',
                color: '#fff',
                border: 'none',
                borderRadius: 10,
                fontSize: 16,
                fontWeight: 600,
                cursor: !files.length || submitting ? 'not-allowed' : 'pointer',
                opacity: !files.length || submitting ? 0.5 : 1,
              }}
            >
              {submitting ? '提交中...' : `开始批量处理 (${files.length} 个文件)`}
            </button>
          </>
        ) : (
          <>
            {/* Progress */}
            {batch && (
              <>
                <div style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, marginBottom: 6 }}>
                    <span>进度</span>
                    <span>
                      {batch.completed} / {batch.total}
                      {batch.status === 'processing' && (
                        <span style={{ color: '#999', marginLeft: 10, fontSize: 13 }}>
                          已用时 {formatDuration(elapsed)}
                        </span>
                      )}
                    </span>
                  </div>
                  <div style={{ width: '100%', height: 8, background: '#e8eaed', borderRadius: 4, overflow: 'hidden' }}>
                    <div
                      style={{
                        height: '100%',
                        background: 'linear-gradient(90deg, #1a73e8, #34a853)',
                        borderRadius: 4,
                        transition: 'width 0.4s ease',
                        width: `${batch.total ? (batch.completed / batch.total) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
                    <span style={{ fontSize: 12, color: '#999' }}>
                      {batch.total ? Math.round((batch.completed / batch.total) * 100) : 0}%
                    </span>
                  </div>
                </div>

                {/* Item list */}
                <div style={{ maxHeight: 300, overflowY: 'auto', border: '1px solid #e8eaed', borderRadius: 8 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr>
                        <th style={thStyle}>文件名</th>
                        <th style={thStyle}>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {batch.items.map((item) => (
                        <tr key={item.task_id} style={{ borderBottom: '1px solid #f1f3f4' }}>
                          <td style={tdStyle}>{item.filename}</td>
                          <td style={tdStyle}>
                            <span
                              style={{
                                display: 'inline-block',
                                padding: '2px 8px',
                                borderRadius: 4,
                                fontSize: 12,
                                fontWeight: 500,
                                background: statusColor(item.status).bg,
                                color: statusColor(item.status).fg,
                              }}
                            >
                              {statusLabel(item.status)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Download */}
                {['completed', 'partial'].includes(batch.status) && (
                  <div style={{ textAlign: 'center', marginTop: 18 }}>
                    <a
                      href={batchDownloadUrl(batch.batch_id)}
                      download
                      style={{
                        display: 'inline-block',
                        padding: '12px 32px',
                        background: '#34a853',
                        color: '#fff',
                        borderRadius: 8,
                        textDecoration: 'none',
                        fontSize: 15,
                        fontWeight: 600,
                      }}
                    >
                      打包下载全部
                    </a>
                  </div>
                )}
              </>
            )}

            <button
              onClick={handleRestart}
              style={{
                marginTop: 16,
                padding: '10px 24px',
                background: 'transparent',
                color: '#1a73e8',
                border: '1px solid #1a73e8',
                borderRadius: 8,
                fontSize: 14,
                cursor: 'pointer',
              }}
            >
              继续批量处理
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    pending: '等待中',
    processing: '处理中',
    completed: '完成',
    failed: '失败',
  };
  return map[s] || s;
}

function statusColor(s: string): { bg: string; fg: string } {
  const map: Record<string, { bg: string; fg: string }> = {
    pending: { bg: '#f1f3f4', fg: '#555' },
    processing: { bg: '#e8f0fe', fg: '#1a73e8' },
    completed: { bg: '#e6f4ea', fg: '#137333' },
    failed: { bg: '#fce8e6', fg: '#c5221f' },
  };
  return map[s] || { bg: '#f1f3f4', fg: '#555' };
}

const cardStyle: React.CSSProperties = {
  background: '#fff',
  borderRadius: 12,
  boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
  padding: '28px 32px',
  marginBottom: 24,
};

const cardTitle: React.CSSProperties = {
  fontSize: 18,
  fontWeight: 600,
  marginBottom: 18,
  color: '#1a73e8',
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 14,
  fontWeight: 500,
  color: '#444',
  marginBottom: 6,
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  border: '1px solid #dadce0',
  borderRadius: 8,
  fontSize: 14,
  background: '#fff',
  outline: 'none',
  boxSizing: 'border-box',
};

const thStyle: React.CSSProperties = {
  background: '#f1f3f4',
  padding: '8px 10px',
  textAlign: 'left',
  fontWeight: 600,
  position: 'sticky',
  top: 0,
};

const tdStyle: React.CSSProperties = {
  padding: '6px 10px',
};
