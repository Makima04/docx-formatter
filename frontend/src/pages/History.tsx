import React from 'react';
import { useHistory } from '../hooks/useHistory';
import { downloadUrl } from '../api/client';

export default function History() {
  const { items, remove, clear } = useHistory();

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return d.toLocaleString('zh-CN');
  };

  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
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
              <div
                key={item.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 16px',
                  border: '1px solid #e8eaed',
                  borderRadius: 8,
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
                    onClick={() => remove(item.id)}
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
            ))}
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
