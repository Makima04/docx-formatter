import React from 'react';
import type { ClassificationItem } from '../types';

const TYPE_COLORS: Record<string, { bg: string; fg: string }> = {
  heading1: { bg: '#fce8e6', fg: '#c5221f' },
  heading2: { bg: '#fef7e0', fg: '#e37400' },
  heading3: { bg: '#e6f4ea', fg: '#137333' },
  body: { bg: '#f1f3f4', fg: '#555' },
  caption_figure: { bg: '#e8f0fe', fg: '#1a73e8' },
  caption_table: { bg: '#e8f0fe', fg: '#1a73e8' },
  reference: { bg: '#f3e8fd', fg: '#7627bb' },
  abstract: { bg: '#e0f7fa', fg: '#00838f' },
  keywords: { bg: '#e0f7fa', fg: '#00838f' },
};

export default function ClassificationTable({ items }: { items: ClassificationItem[] }) {
  if (!items.length) return null;

  return (
    <div
      style={{
        maxHeight: 300,
        overflowY: 'auto',
        border: '1px solid #e8eaed',
        borderRadius: 8,
        marginTop: 16,
      }}
    >
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr>
            <th style={thStyle}>#</th>
            <th style={thStyle}>类型</th>
            <th style={thStyle}>置信度</th>
            <th style={thStyle}>文本预览</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const c = TYPE_COLORS[item.type] || { bg: '#f1f3f4', fg: '#555' };
            return (
              <tr key={item.index} style={{ borderBottom: '1px solid #f1f3f4' }}>
                <td style={tdStyle}>{item.index}</td>
                <td style={tdStyle}>
                  <span
                    style={{
                      display: 'inline-block',
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: 12,
                      fontWeight: 500,
                      background: c.bg,
                      color: c.fg,
                    }}
                  >
                    {item.type}
                  </span>
                </td>
                <td style={tdStyle}>{(item.confidence * 100).toFixed(0)}%</td>
                <td
                  style={{ ...tdStyle, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                  title={item.text}
                >
                  {item.text}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

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
