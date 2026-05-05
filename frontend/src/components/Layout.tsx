import React from 'react';
import { NavLink } from 'react-router-dom';

const linkStyle: React.CSSProperties = {
  padding: '10px 16px',
  borderRadius: '8px',
  textDecoration: 'none',
  fontSize: '14px',
  fontWeight: 500,
  transition: 'all 0.15s',
};

const activeStyle: React.CSSProperties = {
  ...linkStyle,
  background: 'rgba(255,255,255,0.2)',
  color: '#fff',
};

const inactiveStyle: React.CSSProperties = {
  ...linkStyle,
  color: 'rgba(255,255,255,0.7)',
};

export default function Layout({
  children,
  code,
  remaining,
  onLogout,
}: {
  children: React.ReactNode;
  code: string;
  remaining: number | null;
  onLogout: () => void;
}) {
  return (
    <div style={{ minHeight: '100vh', background: '#f5f7fa' }}>
      {/* Header */}
      <header
        style={{
          background: 'linear-gradient(135deg, #1a73e8, #0d47a1)',
          color: '#fff',
          padding: '0 24px',
        }}
      >
        <div
          style={{
            maxWidth: 1100,
            margin: '0 auto',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: 56,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
            <span style={{ fontSize: 18, fontWeight: 700 }}>Docx Formatter</span>
            <nav style={{ display: 'flex', gap: 4 }}>
              {[
                { to: '/', label: '排版' },
                { to: '/batch', label: '批量处理' },
                { to: '/templates', label: '模板管理' },
                { to: '/history', label: '历史记录' },
              ].map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  style={({ isActive }) => (isActive ? activeStyle : inactiveStyle)}
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 13 }}>
            {remaining != null && (
              <span style={{ opacity: 0.85 }}>
                剩余 <strong>{remaining}</strong> 次
              </span>
            )}
            <span
              style={{
                background: 'rgba(255,255,255,0.15)',
                padding: '4px 10px',
                borderRadius: 6,
                fontSize: 12,
                fontFamily: 'monospace',
              }}
            >
              {code.slice(0, 6)}...
            </span>
            <button
              onClick={onLogout}
              style={{
                background: 'rgba(255,255,255,0.15)',
                border: 'none',
                color: '#fff',
                padding: '4px 10px',
                borderRadius: 6,
                cursor: 'pointer',
                fontSize: 12,
              }}
            >
              切换
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main style={{ maxWidth: 1100, margin: '24px auto', padding: '0 16px' }}>
        {children}
      </main>
    </div>
  );
}
