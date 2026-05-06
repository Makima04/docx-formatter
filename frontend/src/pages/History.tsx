import React, { useState } from 'react';
import { useHistory } from '../hooks/useHistory';
import { downloadUrl } from '../api/client';
import ClassificationTable from '../components/ClassificationTable';
import DocxPreview from '../components/DocxPreview';

export default function History() {
  const { items, remove, clear } = useHistory();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return d.toLocaleString('zh-CN');
  };

  return (
    <div style={{ maxWidth: 820, margin: '0 auto' }}>
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: '#1a73e8', margin: 0 }}>历史记录</h2>
          {items.length > 0 && (
            <button
              onClick={clear}
              style={{
                padding: '6px 14px',
                background: '#fce8e6',
                color: '#c5221f',
                border: 'none',
                borderRadius: 6,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              清空全部
            </button>
          )}
        </div>

        {items.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#888', fontSize: 14 }}>
            暂无历史记录
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {items.map((item) => (
              <div key={item.id}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                    border: '1px solid #e8eaed',
                    borderRadius: 8,
                    borderBottomLeftRadius: expandedId === item.id ? 0 : 8,
                    borderBottomRightRadius: expandedId === item.id ? 0 : 8,
                    borderBottom: expandedId === item.id ? 'none' : '1px solid #e8eaed',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.filename}
                    </div>
                    <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
                      {formatTime(item.timestamp)}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, marginLeft: 12 }}>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        borderRadius: 4,
                        fontSize: 12,
                        fontWeight: 500,
                        background: item.status === 'completed' ? '#e6f4ea' : '#fce8e6',
                        color: item.status === 'completed' ? '#137333' : '#c5221f',
                      }}
                    >
                      {item.status === 'completed' ? '完成' : '失败'}
                    </span>
                    {item.status === 'completed' && item.classification_result && item.classification_result.length > 0 && (
                      <button
                        onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                        style={{
                          padding: '4px 10px',
                          background: '#e8f0fe',
                          color: '#1a73e8',
                          border: 'none',
                          borderRadius: 5,
                          fontSize: 12,
                          cursor: 'pointer',
                        }}
                      >
                        {expandedId === item.id ? '收起' : '查看分类'}
                      </button>
                    )}
                    {item.status === 'completed' && (
                      <button
                        onClick={() => setPreviewId(item.id)}
                        style={{
                          padding: '4px 12px',
                          background: '#1a73e8',
                          color: '#fff',
                          borderRadius: 6,
                          border: 'none',
                          fontSize: 12,
                          fontWeight: 500,
                          cursor: 'pointer',
                        }}
                      >
                        预览
                      </button>
                    )}
                    {item.status === 'completed' && (
                      <a
                        href={downloadUrl(item.id)}
                        download
                        style={{
                          padding: '4px 12px',
                          background: '#34a853',
                          color: '#fff',
                          borderRadius: 6,
                          fontSize: 12,
                          textDecoration: 'none',
                          fontWeight: 500,
                        }}
                      >
                        下载
                      </a>
                    )}
                    <button
                      onClick={() => { remove(item.id); if (expandedId === item.id) setExpandedId(null); }}
                      style={{
                        padding: '4px 8px',
                        background: 'transparent',
                        color: '#999',
                        border: 'none',
                        fontSize: 12,
                        cursor: 'pointer',
                      }}
                    >
                      删除
                    </button>
                  </div>
                </div>
                {expandedId === item.id && item.classification_result && (
                  <div style={{
                    border: '1px solid #e8eaed',
                    borderTop: 'none',
                    borderRadius: '0 0 8px 8px',
                    padding: '12px 16px',
                    background: '#fafbfc',
                  }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: '#555', marginBottom: 8 }}>
                      段落分类结果（共 {item.classification_result.length} 个段落）
                    </div>
                    <ClassificationTable items={item.classification_result} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      {previewId && (
        <DocxPreview
          taskIds={[previewId]}
          onClose={() => setPreviewId(null)}
        />
      )}
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
