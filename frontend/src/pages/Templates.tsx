import React, { useState, useEffect, useCallback } from 'react';
import {
  listTemplates,
  getTemplate,
  createTemplate,
  updateTemplate,
  deleteTemplate,
} from '../api/client';
import type { TemplateItem } from '../types';

const cardStyle: React.CSSProperties = {
  background: '#fff',
  borderRadius: 12,
  boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
  padding: '28px 32px',
  marginBottom: 24,
};

const btnPrimary: React.CSSProperties = {
  padding: '8px 18px',
  background: '#1a73e8',
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  fontSize: 13,
  fontWeight: 500,
  cursor: 'pointer',
};

const btnDanger: React.CSSProperties = {
  padding: '6px 14px',
  background: '#fce8e6',
  color: '#c5221f',
  border: 'none',
  borderRadius: 6,
  fontSize: 12,
  cursor: 'pointer',
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

export default function Templates() {
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [editing, setEditing] = useState<TemplateItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [configJson, setConfigJson] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setTemplates(await listTemplates());
    } catch {}
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    setError('');
    try {
      await createTemplate({ name, description: desc, config_json: configJson });
      setShowCreate(false);
      setName(''); setDesc(''); setConfigJson('');
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '创建失败');
    }
  };

  const handleEdit = async (tpl: TemplateItem) => {
    if (tpl.is_builtin) return;
    const full = await getTemplate(tpl.id);
    setEditing(full);
    setName(full.name);
    setDesc(full.description);
    setConfigJson(full.config_json || '');
  };

  const handleSaveEdit = async () => {
    if (!editing) return;
    setError('');
    try {
      await updateTemplate(editing.id, { name, description: desc, config_json: configJson });
      setEditing(null);
      setName(''); setDesc(''); setConfigJson('');
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '更新失败');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除此模板？')) return;
    try {
      await deleteTemplate(id);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '删除失败');
    }
  };

  return (
    <div style={{ maxWidth: 720, margin: '0 auto' }}>
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: '#1a73e8', margin: 0 }}>模板管理</h2>
          <button
            onClick={() => { setShowCreate(true); setEditing(null); setName(''); setDesc(''); setConfigJson(''); }}
            style={btnPrimary}
          >
            新建模板
          </button>
        </div>

        {error && (
          <div style={{ background: '#fce8e6', color: '#c5221f', padding: '10px 14px', borderRadius: 8, fontSize: 13, marginBottom: 14 }}>
            {error}
          </div>
        )}

        {/* Template list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {templates.map((t) => (
            <div
              key={t.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '14px 18px',
                border: '1px solid #e8eaed',
                borderRadius: 8,
                background: t.is_builtin ? '#f8f9ff' : '#fff',
              }}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>
                  {t.description || t.name}
                  {t.is_builtin && (
                    <span style={{ fontSize: 11, color: '#888', marginLeft: 8, fontWeight: 400 }}>内置</span>
                  )}
                </div>
                <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>{t.name}</div>
              </div>
              {!t.is_builtin && (
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => handleEdit(t)} style={{ ...btnPrimary, padding: '6px 14px', fontSize: 12 }}>
                    编辑
                  </button>
                  <button onClick={() => handleDelete(t.id)} style={btnDanger}>
                    删除
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Create / Edit form */}
        {(showCreate || editing) && (
          <div style={{ marginTop: 24, padding: '20px', background: '#f8f9ff', borderRadius: 10, border: '1px solid #e0e3f2' }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>
              {editing ? '编辑模板' : '新建模板'}
            </h3>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>名称</label>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="模板名称" style={inputStyle} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>描述</label>
              <input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="模板描述" style={inputStyle} />
            </div>
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>配置 JSON</label>
              <textarea
                value={configJson}
                onChange={(e) => setConfigJson(e.target.value)}
                placeholder='{"name": "...", "page": {...}, "body": {...}, ...}'
                style={{ ...inputStyle, minHeight: 200, fontFamily: 'monospace', fontSize: 12, resize: 'vertical' as const }}
              />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={editing ? handleSaveEdit : handleCreate} style={btnPrimary}>
                {editing ? '保存' : '创建'}
              </button>
              <button
                onClick={() => { setShowCreate(false); setEditing(null); }}
                style={{ ...btnPrimary, background: '#fff', color: '#666', border: '1px solid #dadce0' }}
              >
                取消
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
