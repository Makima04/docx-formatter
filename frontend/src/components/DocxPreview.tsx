import React, { useState, useEffect, useRef } from 'react';
import mammoth from 'mammoth';

interface Props {
  taskIds: string[];
  initialIndex?: number;
  onClose: () => void;
}

export default function DocxPreview({ taskIds, initialIndex = 0, onClose }: Props) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [html, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);

  const taskId = taskIds[currentIndex];

  // Inject spinner keyframes once
  useEffect(() => {
    if (!document.getElementById('docx-preview-anim')) {
      const style = document.createElement('style');
      style.id = 'docx-preview-anim';
      style.textContent = '@keyframes spin{to{transform:rotate(360deg)}}';
      document.head.appendChild(style);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    setContent('');

    fetch(`/download/${taskId}`)
      .then((res) => {
        if (!res.ok) throw new Error('下载文件失败');
        return res.arrayBuffer();
      })
      .then((buffer) => mammoth.convertToHtml({ arrayBuffer: buffer }))
      .then((result) => {
        if (!cancelled) {
          setContent(result.value || '<p style="color:#888">文档内容为空</p>');
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : '预览失败');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [taskId]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft' && currentIndex > 0) setCurrentIndex((i) => i - 1);
      if (e.key === 'ArrowRight' && currentIndex < taskIds.length - 1) setCurrentIndex((i) => i + 1);
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose, currentIndex, taskIds.length]);

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={modalStyle} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={headerStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 16, fontWeight: 600, color: '#1a73e8' }}>文档预览</span>
            {taskIds.length > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <button
                  onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
                  disabled={currentIndex === 0}
                  style={navBtnStyle(currentIndex === 0)}
                >
                  &lt;
                </button>
                <span style={{ fontSize: 13, color: '#666', minWidth: 60, textAlign: 'center' }}>
                  {currentIndex + 1} / {taskIds.length}
                </span>
                <button
                  onClick={() => setCurrentIndex((i) => Math.min(taskIds.length - 1, i + 1))}
                  disabled={currentIndex === taskIds.length - 1}
                  style={navBtnStyle(currentIndex === taskIds.length - 1)}
                >
                  &gt;
                </button>
              </div>
            )}
          </div>
          <button onClick={onClose} style={closeBtnStyle}>&times;</button>
        </div>

        {/* Content */}
        <div ref={containerRef} style={contentStyle}>
          {loading && (
            <div style={statusStyle}>
              <div style={spinnerStyle} />
              <span style={{ marginLeft: 12 }}>加载中...</span>
            </div>
          )}
          {error && (
            <div style={{ ...statusStyle, color: '#c5221f' }}>{error}</div>
          )}
          {html && !loading && (
            <div
              style={docStyle}
              dangerouslySetInnerHTML={{ __html: html }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.5)',
  zIndex: 1000,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 24,
};

const modalStyle: React.CSSProperties = {
  background: '#fff',
  borderRadius: 12,
  width: '100%',
  maxWidth: 900,
  height: '85vh',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  boxShadow: '0 8px 40px rgba(0,0,0,0.2)',
};

const headerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '14px 20px',
  borderBottom: '1px solid #e8eaed',
  flexShrink: 0,
};

const contentStyle: React.CSSProperties = {
  flex: 1,
  overflow: 'auto',
  padding: 0,
};

const docStyle: React.CSSProperties = {
  padding: '32px 48px',
  fontSize: 14,
  lineHeight: 1.8,
  color: '#333',
  fontFamily: '"SimSun", "Songti SC", serif',
};

const statusStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  height: '100%',
  fontSize: 15,
  color: '#888',
};

function navBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    padding: '4px 10px',
    border: '1px solid #dadce0',
    borderRadius: 6,
    background: disabled ? '#f5f5f5' : '#fff',
    color: disabled ? '#ccc' : '#333',
    cursor: disabled ? 'not-allowed' : 'pointer',
    fontSize: 14,
  };
}

const closeBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  fontSize: 24,
  color: '#666',
  cursor: 'pointer',
  padding: '0 4px',
  lineHeight: 1,
};

const spinnerStyle: React.CSSProperties = {
  width: 20,
  height: 20,
  border: '3px solid #e8eaed',
  borderTopColor: '#1a73e8',
  borderRadius: '50%',
  animation: 'spin 0.8s linear infinite',
};
