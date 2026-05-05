import React, { useRef, useState, useCallback } from 'react';

interface Props {
  accept: string;
  multiple?: boolean;
  label: string;
  onFiles: (files: File[]) => void;
  files?: File[];
}

export default function FileUpload({ accept, multiple = false, label, onFiles, files = [] }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragover, setDragover] = useState(false);

  const handleClick = () => inputRef.current?.click();

  const handleChange = () => {
    if (inputRef.current?.files?.length) {
      onFiles(Array.from(inputRef.current.files));
    }
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragover(false);
      if (e.dataTransfer.files.length) {
        onFiles(Array.from(e.dataTransfer.files));
      }
    },
    [onFiles],
  );

  const names = files.map((f) => f.name).join(', ');

  return (
    <div>
      <div
        onClick={handleClick}
        onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
        onDragLeave={() => setDragover(false)}
        onDrop={handleDrop}
        style={{
          border: `2px dashed ${dragover ? '#1a73e8' : '#c4c9d4'}`,
          borderRadius: 10,
          padding: '32px 20px',
          textAlign: 'center',
          cursor: 'pointer',
          background: dragover ? '#e8f0fe' : '#fafbfc',
          transition: 'all 0.2s',
        }}
      >
        <div style={{ fontSize: 36, marginBottom: 8 }}>📄</div>
        <p style={{ fontSize: 14, color: '#666' }}>{label}</p>
        {names && (
          <p style={{ marginTop: 8, fontSize: 14, fontWeight: 600, color: '#1a73e8' }}>
            {names}
          </p>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handleChange}
        style={{ display: 'none' }}
      />
    </div>
  );
}
