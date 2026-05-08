import React, { useEffect, useRef, useCallback } from 'react';
import FileUpload from '../components/FileUpload';
import ProgressBar from '../components/ProgressBar';
import ClassificationTable from '../components/ClassificationTable';
import DocxPreview from '../components/DocxPreview';
import { formatDocument, downloadUrl, pollTask } from '../api/client';
import { listTemplates } from '../api/client';
import { useFormatSession } from '../hooks/useFormatSession';
import { useHistory } from '../hooks/useHistory';
import type { TemplateItem } from '../types';

const FAST_INTERVAL = 800;
const NORMAL_INTERVAL = 2000;
const FAST_DURATION_MS = 30_000;

interface Props {
  code: string;
  onQuotaChange: () => void;
}

type TemplateMode = 'builtin' | 'upload' | 'nl';

export default function Home({ code, onQuotaChange }: Props) {
  const {
    file, setFile,
    tplMode, setTplMode,
    tplId, setTplId,
    tplFile, setTplFile,
    tplDesc, setTplDesc,
    task, setTask,
    polling, setPolling,
    startedAt, setStartedAt,
    done, setDone,
    error, setError,
    showPreview, setShowPreview,
    reset,
  } = useFormatSession();

  const [templates, setTemplates] = React.useState<TemplateItem[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAtRef = useRef<number>(0);
  const intervalRef = useRef(FAST_INTERVAL);
  const history = useHistory();

  useEffect(() => {
    listTemplates().then(setTemplates).catch(() => {});
  }, []);

  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setPolling(false);
  }, [setPolling]);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const startPolling = useCallback((taskId: string) => {
    setPolling(true);
    setTask(null);
    setDone(false);
    setError('');
    const now = Date.now();
    startedAtRef.current = now;
    setStartedAt(now);

    const poll = async () => {
      try {
        const data = await pollTask(taskId);
        setTask(data);

        if (data.status === 'completed') {
          stopPolling();
          setDone(true);
          onQuotaChange();
          history.add({
            id: data.task_id,
            filename: file?.name || '',
            template: tplId ? String(tplId) : 'default',
            status: 'completed',
            timestamp: Date.now(),
            classification_result: data.classification_result || undefined,
          });
        } else if (data.status === 'failed') {
          stopPolling();
          setError(data.message || '处理失败');
          history.add({
            id: data.task_id,
            filename: file?.name || '',
            template: tplId ? String(tplId) : 'default',
            status: 'failed',
            timestamp: Date.now(),
          });
          return;
        }

        const elapsed = Date.now() - startedAtRef.current;
        const nextInterval = elapsed < FAST_DURATION_MS ? FAST_INTERVAL : NORMAL_INTERVAL;
        if (nextInterval !== intervalRef.current) {
          intervalRef.current = nextInterval;
          if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = setInterval(poll, nextInterval);
          }
        }
      } catch {
        // ignore transient errors
      }
    };

    poll();
    timerRef.current = setInterval(poll, FAST_INTERVAL);
  }, [setPolling, setTask, setDone, setError, setStartedAt, stopPolling, onQuotaChange, file, tplId, history]);

  const handleSubmit = async () => {
    if (!file) return;
    setError('');

    try {
      const opts: Record<string, unknown> = {};
      if (tplMode === 'builtin' && tplId) opts.template_id = tplId;
      if (tplMode === 'upload' && tplFile) opts.template_file = tplFile;
      if (tplMode === 'nl' && tplDesc.trim()) opts.template_description = tplDesc.trim();

      const { task_id } = await formatDocument(code, file, opts as Parameters<typeof formatDocument>[2]);
      startPolling(task_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '上传失败');
    }
  };

  const handleRestart = () => {
    reset();
  };

  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      {/* Upload */}
      <div style={cardStyle}>
        <h2 style={cardTitle}>1. 上传文档</h2>
        <FileUpload
          accept=".docx"
          label="点击或拖拽上传 .docx 文件"
          onFiles={(files) => setFile(files[0])}
          files={file ? [file] : []}
        />
      </div>

      {/* Template */}
      <div style={cardStyle}>
        <h2 style={cardTitle}>2. 选择模板</h2>
        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          {(['builtin', 'upload', 'nl'] as TemplateMode[]).map((mode) => {
            const labels = { builtin: '内置模板', upload: '上传模板文件', nl: '自然语言描述' };
            return (
              <button
                key={mode}
                onClick={() => setTplMode(mode)}
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  border: '1px solid #dadce0',
                  background: tplMode === mode ? '#1a73e8' : '#fff',
                  color: tplMode === mode ? '#fff' : '#333',
                  borderRadius: 8,
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                {labels[mode]}
              </button>
            );
          })}
        </div>

        {tplMode === 'builtin' && (
          <div style={{ marginBottom: 0 }}>
            <label style={labelStyle}>模板</label>
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
        )}

        {tplMode === 'upload' && (
          <FileUpload
            accept=".docx"
            label="上传模板 .docx 文件（将提取页面设置）"
            onFiles={(files) => setTplFile(files[0])}
            files={tplFile ? [tplFile] : []}
          />
        )}

        {tplMode === 'nl' && (
          <div>
            <label style={labelStyle}>描述你想要的排版格式</label>
            <textarea
              value={tplDesc}
              onChange={(e) => setTplDesc(e.target.value)}
              placeholder="例如：A4纸，上下边距2.54cm，左右3.17cm，正文宋体小四号，标题黑体三号居中..."
              style={{ ...inputStyle, minHeight: 80, resize: 'vertical' as const }}
            />
            <p style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
              需要配置 LLM API 才能使用此功能
            </p>
          </div>
        )}
      </div>

      {/* Submit */}
      <div style={cardStyle}>
        <button
          onClick={handleSubmit}
          disabled={!file || polling}
          style={{
            width: '100%',
            padding: '14px',
            background: 'linear-gradient(135deg, #1a73e8, #0d47a1)',
            color: '#fff',
            border: 'none',
            borderRadius: 10,
            fontSize: 16,
            fontWeight: 600,
            cursor: !file || polling ? 'not-allowed' : 'pointer',
            opacity: !file || polling ? 0.5 : 1,
          }}
        >
          {polling ? '处理中...' : '开始排版'}
        </button>

        {polling && task && (
          <ProgressBar task={task} startedAt={startedAt} />
        )}

        {task?.classification_result && task.classification_result.length > 0 && (
          <ClassificationTable items={task.classification_result} />
        )}

        {error && (
          <div
            style={{
              background: '#fce8e6',
              color: '#c5221f',
              padding: '14px 18px',
              borderRadius: 8,
              fontSize: 14,
              marginTop: 14,
            }}
          >
            {error}
          </div>
        )}

        {done && task && (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <div style={{ fontSize: 48, marginBottom: 10 }}>✅</div>
            <p style={{ fontSize: 16, fontWeight: 500 }}>排版完成！</p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 14 }}>
              <button
                onClick={() => setShowPreview(true)}
                style={{
                  padding: '12px 32px',
                  background: '#1a73e8',
                  color: '#fff',
                  borderRadius: 8,
                  border: 'none',
                  fontSize: 15,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                在线预览
              </button>
              <a
                href={downloadUrl(task.task_id)}
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
                下载排版文档
              </a>
            </div>
            <button
              onClick={handleRestart}
              style={{
                marginTop: 10,
                padding: '10px 24px',
                background: 'transparent',
                color: '#1a73e8',
                border: '1px solid #1a73e8',
                borderRadius: 8,
                fontSize: 14,
                cursor: 'pointer',
              }}
            >
              继续排版下一个文档
            </button>
            {showPreview && (
              <DocxPreview
                taskIds={[task.task_id]}
                onClose={() => setShowPreview(false)}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
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
  borderBottom: '2px solid #e8eaed',
  paddingBottom: 10,
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
