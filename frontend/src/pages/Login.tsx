import React from 'react';

interface Props {
  onLogin: (code: string) => void;
  checking: boolean;
  error: string;
}

export default function Login({ onLogin, checking, error }: Props) {
  const [input, setInput] = React.useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) onLogin(input.trim());
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f5f7fa',
      }}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
          padding: '40px 36px',
          width: 380,
          textAlign: 'center',
        }}
      >
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#1a73e8', marginBottom: 4 }}>
          Docx Formatter
        </h1>
        <p style={{ fontSize: 14, color: '#888', marginBottom: 28 }}>
          输入兑换码开始使用
        </p>
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="请输入兑换码"
            style={{
              width: '100%',
              padding: '12px 14px',
              border: '1px solid #dadce0',
              borderRadius: 8,
              fontSize: 15,
              outline: 'none',
              textAlign: 'center',
              letterSpacing: 1,
            }}
          />
          {error && (
            <p style={{ color: '#c5221f', fontSize: 13, marginTop: 8 }}>{error}</p>
          )}
          <button
            type="submit"
            disabled={checking || !input.trim()}
            style={{
              width: '100%',
              marginTop: 16,
              padding: '12px',
              background: 'linear-gradient(135deg, #1a73e8, #0d47a1)',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontSize: 15,
              fontWeight: 600,
              cursor: checking ? 'not-allowed' : 'pointer',
              opacity: checking ? 0.6 : 1,
            }}
          >
            {checking ? '验证中...' : '进入'}
          </button>
        </form>
      </div>
    </div>
  );
}
