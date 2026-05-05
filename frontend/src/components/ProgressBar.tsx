import React from 'react';

interface Props {
  progress: number;
  message: string;
}

export default function ProgressBar({ progress, message }: Props) {
  return (
    <div style={{ margin: '16px 0' }}>
      <div
        style={{
          width: '100%',
          height: 8,
          background: '#e8eaed',
          borderRadius: 4,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            background: 'linear-gradient(90deg, #1a73e8, #34a853)',
            borderRadius: 4,
            transition: 'width 0.4s ease',
            width: `${progress}%`,
          }}
        />
      </div>
      <p style={{ fontSize: 13, color: '#666', textAlign: 'center', marginTop: 8 }}>
        {message || '处理中...'}
      </p>
    </div>
  );
}
