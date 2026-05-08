import React, { useState, useEffect, useCallback } from 'react';
import {
  listAdminCodes,
  createAdminCode,
  updateAdminCode,
  deleteAdminCode,
  getLLMConfig,
  updateLLMConfig,
  listLLMModels,
  testLLMConnection,
  getLLMLogs,
  type RedeemCodeItem,
  type LLMLogItem,
} from '../api/client';

const ADMIN_KEY_STORAGE = 'docfmt_admin_key';

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

const btnSmall: React.CSSProperties = {
  padding: '4px 10px',
  background: '#e8f0fe',
  color: '#1a73e8',
  border: 'none',
  borderRadius: 5,
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

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '10px 12px',
  fontSize: 12,
  fontWeight: 600,
  color: '#5f6368',
  borderBottom: '2px solid #e8eaed',
  whiteSpace: 'nowrap',
};

const tdStyle: React.CSSProperties = {
  padding: '10px 12px',
  fontSize: 13,
  borderBottom: '1px solid #f1f3f4',
};

export default function Admin() {
  const [adminKey, setAdminKey] = useState('');
  const [loggedIn, setLoggedIn] = useState(false);
  const [codes, setCodes] = useState<RedeemCodeItem[]>([]);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);

  // Create form state
  const [newCode, setNewCode] = useState('');
  const [newQuota, setNewQuota] = useState('100');
  const [newExpiry, setNewExpiry] = useState('');
  const [autoGenerate, setAutoGenerate] = useState(true);
  const [newCount, setNewCount] = useState('1');
  const [newPrefix, setNewPrefix] = useState('');
  const [createdCodes, setCreatedCodes] = useState<string[]>([]);

  // Edit state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editQuota, setEditQuota] = useState('');
  const [editExpiry, setEditExpiry] = useState('');

  // LLM settings state
  const [llmApiKey, setLlmApiKey] = useState('');
  const [llmBaseUrl, setLlmBaseUrl] = useState('');
  const [llmModel, setLlmModel] = useState('');
  const [llmConcurrent, setLlmConcurrent] = useState(3);
  const [llmModels, setLlmModels] = useState<string[]>([]);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmSaving, setLlmSaving] = useState(false);
  const [llmTesting, setLlmTesting] = useState(false);
  const [llmMsg, setLlmMsg] = useState('');
  const [llmMsgType, setLlmMsgType] = useState<'ok' | 'err' | ''>('');

  // LLM call logs state
  const [llmLogs, setLlmLogs] = useState<LLMLogItem[]>([]);
  const [llmLogsLoading, setLlmLogsLoading] = useState(false);
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);

  // Try restoring from localStorage
  useEffect(() => {
    const saved = localStorage.getItem(ADMIN_KEY_STORAGE);
    if (saved) {
      setAdminKey(saved);
      setLoggedIn(true);
    }
  }, []);

  const load = useCallback(async () => {
    if (!adminKey) return;
    try {
      setCodes(await listAdminCodes(adminKey));
    } catch (e: unknown) {
      if (e instanceof Error && e.message.includes('403')) {
        setLoggedIn(false);
        localStorage.removeItem(ADMIN_KEY_STORAGE);
        setError('Admin key 无效');
      } else {
        setError(e instanceof Error ? e.message : '加载失败');
      }
    }
  }, [adminKey]);

  useEffect(() => {
    if (loggedIn) load();
  }, [loggedIn, load]);

  // Load LLM config on login
  useEffect(() => {
    if (!loggedIn || !adminKey) return;
    getLLMConfig(adminKey).then((cfg) => {
      setLlmBaseUrl(cfg.base_url);
      setLlmModel(cfg.model);
      setLlmConcurrent(cfg.concurrent_requests ?? 3);
      // api_key comes masked; leave input empty so admin can type a new one
      setLlmApiKey('');
    }).catch(() => {});
  }, [loggedIn, adminKey]);

  // Load LLM logs on login
  const loadLLMLogs = useCallback(async () => {
    if (!adminKey) return;
    setLlmLogsLoading(true);
    try {
      const data = await getLLMLogs(adminKey, 50, 0);
      setLlmLogs(data.logs);
    } catch (e: unknown) {
      console.error('Failed to load LLM logs', e);
    } finally {
      setLlmLogsLoading(false);
    }
  }, [adminKey]);

  useEffect(() => {
    if (loggedIn) loadLLMLogs();
  }, [loggedIn, loadLLMLogs]);

  const handleLogin = async () => {
    setError('');
    if (!adminKey.trim()) {
      setError('请输入 Admin Key');
      return;
    }
    try {
      await listAdminCodes(adminKey.trim());
      localStorage.setItem(ADMIN_KEY_STORAGE, adminKey.trim());
      setLoggedIn(true);
    } catch (e: unknown) {
      if (e instanceof Error && e.message.includes('403')) {
        setError('Admin key 无效，请重试');
      } else {
        setError(e instanceof Error ? e.message : '验证失败');
      }
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(ADMIN_KEY_STORAGE);
    setAdminKey('');
    setLoggedIn(false);
    setCodes([]);
  };

  const handleCreate = async () => {
    setError('');
    setCreatedCodes([]);
    try {
      const result = await createAdminCode(adminKey, {
        code: autoGenerate ? undefined : newCode || undefined,
        total_quota: parseInt(newQuota) || 100,
        expires_at: newExpiry || undefined,
        prefix: autoGenerate ? (newPrefix || undefined) : undefined,
        count: autoGenerate ? (parseInt(newCount) || 1) : 1,
      });
      if (autoGenerate) {
        setCreatedCodes(result.codes || []);
      } else {
        setShowCreate(false);
      }
      setNewCode('');
      setNewQuota('100');
      setNewExpiry('');
      setNewPrefix('');
      setNewCount('1');
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '创建失败');
    }
  };

  const handleToggleActive = async (item: RedeemCodeItem) => {
    setError('');
    try {
      await updateAdminCode(adminKey, item.id, { is_active: !item.is_active });
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '更新失败');
    }
  };

  const handleStartEdit = (item: RedeemCodeItem) => {
    setEditingId(item.id);
    setEditQuota(String(item.total_quota));
    setEditExpiry(item.expires_at ? item.expires_at.slice(0, 16) : '');
  };

  const handleSaveEdit = async () => {
    if (editingId == null) return;
    setError('');
    try {
      await updateAdminCode(adminKey, editingId, {
        total_quota: parseInt(editQuota) || undefined,
        clear_expires: !editExpiry,
        expires_at: editExpiry || undefined,
      });
      setEditingId(null);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '更新失败');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除此兑换码？')) return;
    setError('');
    try {
      await deleteAdminCode(adminKey, id);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '删除失败');
    }
  };

  const handleSaveLLM = async () => {
    setLlmMsg('');
    setLlmMsgType('');
    setLlmSaving(true);
    try {
      const data: Record<string, string | number> = {};
      if (llmApiKey) data.api_key = llmApiKey;
      if (llmBaseUrl) data.base_url = llmBaseUrl;
      if (llmModel) data.model = llmModel;
      data.concurrent_requests = Math.max(1, Math.min(10, llmConcurrent));
      await updateLLMConfig(adminKey, data);
      setLlmMsg('LLM 配置已保存，下次任务将使用新配置');
      setLlmMsgType('ok');
      setLlmApiKey('');
    } catch (e: unknown) {
      setLlmMsg(e instanceof Error ? e.message : '保存失败');
      setLlmMsgType('err');
    } finally {
      setLlmSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setLlmMsg('');
    setLlmMsgType('');
    setLlmTesting(true);
    try {
      const result = await testLLMConnection(adminKey, {
        api_key: llmApiKey || undefined,
        base_url: llmBaseUrl || undefined,
        model: llmModel || undefined,
      });
      if (result.ok) {
        let msg = result.message;
        if (result.model_count != null) msg += `，共 ${result.model_count} 个模型`;
        if (result.model_found === true) msg += `，当前模型 ✓`;
        else if (result.model_found === false) msg += `，⚠ 当前模型不在列表中`;
        setLlmMsg(msg);
        setLlmMsgType('ok');
      } else {
        setLlmMsg(result.message);
        setLlmMsgType('err');
      }
    } catch (e: unknown) {
      setLlmMsg(e instanceof Error ? e.message : '检测失败');
      setLlmMsgType('err');
    } finally {
      setLlmTesting(false);
    }
  };

  const handleFetchModels = async () => {
    setLlmMsg('');
    setLlmMsgType('');
    setLlmLoading(true);
    try {
      const models = await listLLMModels(adminKey, {
        api_key: llmApiKey || undefined,
        base_url: llmBaseUrl || undefined,
      });
      setLlmModels(models);
      if (models.length === 0) {
        setLlmMsg('未获取到可用模型');
        setLlmMsgType('err');
      } else {
        setLlmMsg(`获取到 ${models.length} 个模型`);
        setLlmMsgType('ok');
      }
    } catch (e: unknown) {
      setLlmMsg(e instanceof Error ? e.message : '获取模型列表失败');
      setLlmMsgType('err');
    } finally {
      setLlmLoading(false);
    }
  };

  // ── Login form ──────────────────────────────────────────────────

  if (!loggedIn) {
    return (
      <div style={{ maxWidth: 420, margin: '80px auto' }}>
        <div style={cardStyle}>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: '#1a73e8', marginBottom: 20 }}>
            管理后台
          </h2>
          {error && (
            <div style={{ background: '#fce8e6', color: '#c5221f', padding: '10px 14px', borderRadius: 8, fontSize: 13, marginBottom: 14 }}>
              {error}
            </div>
          )}
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>
              Admin Key
            </label>
            <input
              type="password"
              value={adminKey}
              onChange={(e) => setAdminKey(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
              placeholder="输入管理员密钥"
              style={inputStyle}
            />
          </div>
          <button onClick={handleLogin} style={btnPrimary}>
            登录
          </button>
        </div>
      </div>
    );
  }

  // ── Main admin panel ────────────────────────────────────────────

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: '#1a73e8', margin: 0 }}>兑换码管理</h2>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={() => { setShowCreate(true); setEditingId(null); setNewCode(''); setNewQuota('100'); setNewExpiry(''); }}
              style={btnPrimary}
            >
              创建兑换码
            </button>
            <button onClick={handleLogout} style={{ ...btnPrimary, background: '#fff', color: '#666', border: '1px solid #dadce0' }}>
              退出管理
            </button>
          </div>
        </div>

        {error && (
          <div style={{ background: '#fce8e6', color: '#c5221f', padding: '10px 14px', borderRadius: 8, fontSize: 13, marginBottom: 14 }}>
            {error}
          </div>
        )}

        {/* Code table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={thStyle}>兑换码</th>
                <th style={thStyle}>用量</th>
                <th style={thStyle}>状态</th>
                <th style={thStyle}>创建时间</th>
                <th style={thStyle}>过期时间</th>
                <th style={{ ...thStyle, textAlign: 'center' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {codes.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ ...tdStyle, textAlign: 'center', color: '#999', padding: 24 }}>
                    暂无兑换码
                  </td>
                </tr>
              )}
              {codes.map((item) => (
                <tr key={item.id} style={{ background: item.is_active ? '#fff' : '#fafafa' }}>
                  <td style={{ ...tdStyle, fontFamily: 'monospace', fontWeight: 600 }}>
                    {item.code}
                  </td>
                  <td style={tdStyle}>
                    {editingId === item.id ? (
                      <input
                        value={editQuota}
                        onChange={(e) => setEditQuota(e.target.value)}
                        style={{ ...inputStyle, width: 80, padding: '6px 8px', fontSize: 13 }}
                        type="number"
                      />
                    ) : (
                      <span>
                        {item.used_quota} / {item.total_quota}
                      </span>
                    )}
                  </td>
                  <td style={tdStyle}>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '2px 10px',
                        borderRadius: 10,
                        fontSize: 12,
                        fontWeight: 500,
                        background: item.is_active ? '#e6f4ea' : '#fce8e6',
                        color: item.is_active ? '#137333' : '#c5221f',
                        cursor: 'pointer',
                      }}
                      onClick={() => handleToggleActive(item)}
                      title="点击切换状态"
                    >
                      {item.is_active ? '启用' : '禁用'}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, fontSize: 12, color: '#888' }}>
                    {item.created_at?.replace('T', ' ').slice(0, 16) || '-'}
                  </td>
                  <td style={tdStyle}>
                    {editingId === item.id ? (
                      <input
                        value={editExpiry}
                        onChange={(e) => setEditExpiry(e.target.value)}
                        type="datetime-local"
                        style={{ ...inputStyle, width: 180, padding: '6px 8px', fontSize: 12 }}
                      />
                    ) : (
                      <span style={{ fontSize: 12, color: item.expires_at ? '#888' : '#bbb' }}>
                        {item.expires_at ? item.expires_at.replace('T', ' ').slice(0, 16) : '无'}
                      </span>
                    )}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
                      {editingId === item.id ? (
                        <>
                          <button onClick={handleSaveEdit} style={btnSmall}>保存</button>
                          <button onClick={() => setEditingId(null)} style={{ ...btnSmall, background: '#f1f3f4', color: '#666' }}>
                            取消
                          </button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => handleStartEdit(item)} style={btnSmall}>编辑</button>
                          <button onClick={() => handleDelete(item.id)} style={btnDanger}>删除</button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Create form */}
        {showCreate && (
          <div style={{ marginTop: 24, padding: '20px', background: '#f8f9ff', borderRadius: 10, border: '1px solid #e0e3f2' }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>创建兑换码</h3>

            {/* Auto / Manual toggle */}
            <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                <input type="radio" checked={autoGenerate} onChange={() => setAutoGenerate(true)} />
                自动生成
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                <input type="radio" checked={!autoGenerate} onChange={() => setAutoGenerate(false)} />
                手动输入
              </label>
            </div>

            <div style={{ display: 'flex', gap: 12, marginBottom: 14, flexWrap: 'wrap' as const }}>
              {!autoGenerate ? (
                <div style={{ flex: '1 1 200px' }}>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>兑换码</label>
                  <input
                    value={newCode}
                    onChange={(e) => setNewCode(e.target.value)}
                    placeholder="如 SUMMER2026"
                    style={inputStyle}
                  />
                </div>
              ) : (
                <>
                  <div style={{ flex: '1 1 140px' }}>
                    <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>前缀（可选）</label>
                    <input
                      value={newPrefix}
                      onChange={(e) => setNewPrefix(e.target.value)}
                      placeholder="如 VIP"
                      style={inputStyle}
                    />
                  </div>
                  <div style={{ flex: '0 0 100px' }}>
                    <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>数量</label>
                    <input
                      value={newCount}
                      onChange={(e) => setNewCount(e.target.value)}
                      type="number"
                      min={1}
                      max={100}
                      style={inputStyle}
                    />
                  </div>
                </>
              )}
              <div style={{ flex: '0 0 120px' }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>总次数</label>
                <input
                  value={newQuota}
                  onChange={(e) => setNewQuota(e.target.value)}
                  type="number"
                  style={inputStyle}
                />
              </div>
              <div style={{ flex: '1 1 200px' }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>过期时间（可选）</label>
                <input
                  value={newExpiry}
                  onChange={(e) => setNewExpiry(e.target.value)}
                  type="datetime-local"
                  style={inputStyle}
                />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleCreate} style={btnPrimary}>创建</button>
              <button onClick={() => { setShowCreate(false); setCreatedCodes([]); }} style={{ ...btnPrimary, background: '#fff', color: '#666', border: '1px solid #dadce0' }}>
                取消
              </button>
            </div>

            {/* Show generated codes */}
            {createdCodes.length > 0 && (
              <div style={{ marginTop: 16, padding: '14px', background: '#e6f4ea', borderRadius: 8, border: '1px solid #a8dab5' }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#137333', marginBottom: 8 }}>
                  已生成 {createdCodes.length} 个兑换码：
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6 }}>
                  {createdCodes.map((c) => (
                    <span
                      key={c}
                      onClick={() => { navigator.clipboard.writeText(c); }}
                      title="点击复制"
                      style={{
                        fontFamily: 'monospace',
                        fontSize: 13,
                        fontWeight: 600,
                        padding: '4px 10px',
                        background: '#fff',
                        borderRadius: 5,
                        border: '1px solid #a8dab5',
                        cursor: 'pointer',
                        userSelect: 'all',
                      }}
                    >
                      {c}
                    </span>
                  ))}
                </div>
                <div style={{ fontSize: 11, color: '#666', marginTop: 6 }}>点击兑换码可复制到剪贴板</div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* LLM Settings */}
      <div style={cardStyle}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14, color: '#333' }}>LLM 配置</h3>
        <p style={{ fontSize: 12, color: '#888', marginBottom: 14 }}>
          配置 OpenAI 兼容的 LLM API，用于智能段落分类和自然语言模板解析。保存后立即生效。
        </p>

        {llmMsg && (
          <div style={{
            background: llmMsgType === 'err' ? '#fce8e6' : '#e6f4ea',
            color: llmMsgType === 'err' ? '#c5221f' : '#137333',
            padding: '10px 14px', borderRadius: 8, fontSize: 13, marginBottom: 14,
          }}>
            {llmMsg}
          </div>
        )}

        <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' as const }}>
          <div style={{ flex: '1 1 200px' }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>API Key</label>
            <input
              type="password"
              value={llmApiKey}
              onChange={(e) => setLlmApiKey(e.target.value)}
              placeholder="留空则不更新"
              style={inputStyle}
            />
          </div>
          <div style={{ flex: '1 1 280px' }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>Base URL</label>
            <input
              value={llmBaseUrl}
              onChange={(e) => setLlmBaseUrl(e.target.value)}
              placeholder="https://api.openai.com/v1"
              style={inputStyle}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'flex-end', flexWrap: 'wrap' as const }}>
          <div style={{ flex: '1 1 200px' }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>模型</label>
            {llmModels.length > 0 ? (
              <div>
                <select
                  value={llmModels.includes(llmModel) ? llmModel : ''}
                  onChange={(e) => { if (e.target.value) setLlmModel(e.target.value); }}
                  style={inputStyle}
                >
                  <option value="">-- 选择模型 --</option>
                  {llmModels.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                  {!llmModels.includes(llmModel) && llmModel && (
                    <option value={llmModel}>{llmModel} (自定义)</option>
                  )}
                </select>
                <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12, color: '#888' }}>或手动输入：</span>
                  <input
                    value={llmModel}
                    onChange={(e) => setLlmModel(e.target.value)}
                    placeholder="gpt-4o-mini"
                    style={{ ...inputStyle, flex: 1, padding: '6px 8px', fontSize: 13 }}
                  />
                </div>
              </div>
            ) : (
              <input
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                placeholder="gpt-4o-mini"
                style={inputStyle}
              />
            )}
          </div>
          <div style={{ flex: '0 0 120px' }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 4, color: '#444' }}>并发请求数</label>
            <input
              type="number"
              min={1}
              max={10}
              value={llmConcurrent}
              onChange={(e) => setLlmConcurrent(parseInt(e.target.value) || 1)}
              style={inputStyle}
            />
            <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>AI 识别时的最大并发数</div>
          </div>
          <div style={{ flex: '0 0 auto', display: 'flex', gap: 8, flexWrap: 'wrap' as const }}>
            <button onClick={handleTestConnection} disabled={llmTesting} style={{ ...btnPrimary, background: '#34a853' }}>
              {llmTesting ? '检测中...' : '检测连接'}
            </button>
            <button onClick={handleFetchModels} disabled={llmLoading} style={{ ...btnPrimary, background: '#6c63ff' }}>
              {llmLoading ? '获取中...' : '获取模型列表'}
            </button>
            <button onClick={handleSaveLLM} disabled={llmSaving} style={btnPrimary}>
              {llmSaving ? '保存中...' : '保存配置'}
            </button>
          </div>
        </div>
      </div>

      {/* LLM Call Logs */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0, color: '#333' }}>LLM 调用记录</h3>
          <button onClick={loadLLMLogs} disabled={llmLogsLoading} style={{ ...btnSmall, fontSize: 12 }}>
            {llmLogsLoading ? '刷新中...' : '刷新'}
          </button>
        </div>
        {llmLogs.length === 0 ? (
          <p style={{ fontSize: 13, color: '#888' }}>暂无调用记录</p>
        ) : (
          <div style={{ maxHeight: 480, overflowY: 'auto' as const }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  <th style={{ ...thStyle, width: 60 }}>ID</th>
                  <th style={{ ...thStyle, width: 90 }}>类型</th>
                  <th style={{ ...thStyle, width: 120 }}>模型</th>
                  <th style={{ ...thStyle, width: 70 }}>状态</th>
                  <th style={{ ...thStyle, width: 80 }}>耗时(ms)</th>
                  <th style={{ ...thStyle, width: 140 }}>时间</th>
                  <th style={{ ...thStyle, width: 60 }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {llmLogs.map((log) => (
                  <React.Fragment key={log.id}>
                    <tr>
                      <td style={tdStyle}>#{log.id}</td>
                      <td style={tdStyle}>{log.call_type}</td>
                      <td style={tdStyle}>{log.model}</td>
                      <td style={tdStyle}>
                        <span style={{
                          color: log.status === 'success' ? '#137333' : log.status === 'parse_failed' ? '#e37400' : '#c5221f',
                          fontWeight: 600,
                        }}>
                          {log.status === 'success' ? '成功' : log.status === 'parse_failed' ? '解析失败' : '调用失败'}
                        </span>
                      </td>
                      <td style={tdStyle}>{log.latency_ms ?? '-'}</td>
                      <td style={tdStyle}>{new Date(log.created_at).toLocaleString()}</td>
                      <td style={tdStyle}>
                        <button
                          onClick={() => setExpandedLogId(expandedLogId === log.id ? null : log.id)}
                          style={{ ...btnSmall, padding: '2px 8px', fontSize: 11 }}
                        >
                          {expandedLogId === log.id ? '收起' : '查看'}
                        </button>
                      </td>
                    </tr>
                    {expandedLogId === log.id && (
                      <tr>
                        <td colSpan={7} style={{ padding: '10px 12px', background: '#f8f9fa', borderBottom: '1px solid #e8eaed' }}>
                          {log.task_id && (
                            <div style={{ fontSize: 11, color: '#666', marginBottom: 6 }}>
                              任务ID: {log.task_id}
                            </div>
                          )}
                          <div style={{ marginBottom: 10 }}>
                            <div style={{ fontSize: 11, fontWeight: 600, color: '#444', marginBottom: 4 }}>Prompt</div>
                            <pre style={{
                              margin: 0, padding: 10, background: '#fff', borderRadius: 6,
                              fontSize: 11, color: '#333', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                              maxHeight: 200, overflowY: 'auto' as const, border: '1px solid #e8eaed',
                            }}>
                              {log.prompt}
                            </pre>
                          </div>
                          {log.status === 'success' ? (
                            <div>
                              <div style={{ fontSize: 11, fontWeight: 600, color: '#444', marginBottom: 4 }}>Response</div>
                              <pre style={{
                                margin: 0, padding: 10, background: '#fff', borderRadius: 6,
                                fontSize: 11, color: '#333', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                                maxHeight: 200, overflowY: 'auto' as const, border: '1px solid #e8eaed',
                              }}>
                                {log.response}
                              </pre>
                            </div>
                          ) : log.status === 'parse_failed' ? (
                            <>
                              <div style={{ marginBottom: 10 }}>
                                <div style={{ fontSize: 11, fontWeight: 600, color: '#e37400', marginBottom: 4 }}>解析错误</div>
                                <pre style={{
                                  margin: 0, padding: 10, background: '#fff', borderRadius: 6,
                                  fontSize: 11, color: '#e37400', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                                  maxHeight: 200, overflowY: 'auto' as const, border: '1px solid #e8eaed',
                                }}>
                                  {log.error_msg || '无法解析LLM返回的JSON格式'}
                                </pre>
                              </div>
                              <div>
                                <div style={{ fontSize: 11, fontWeight: 600, color: '#444', marginBottom: 4 }}>LLM原始响应</div>
                                <pre style={{
                                  margin: 0, padding: 10, background: '#fff', borderRadius: 6,
                                  fontSize: 11, color: '#333', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                                  maxHeight: 200, overflowY: 'auto' as const, border: '1px solid #e8eaed',
                                }}>
                                  {log.response}
                                </pre>
                              </div>
                            </>
                          ) : (
                            <div>
                              <div style={{ fontSize: 11, fontWeight: 600, color: '#c5221f', marginBottom: 4 }}>调用错误</div>
                              <pre style={{
                                margin: 0, padding: 10, background: '#fff', borderRadius: 6,
                                fontSize: 11, color: '#c5221f', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                                maxHeight: 200, overflowY: 'auto' as const, border: '1px solid #e8eaed',
                              }}>
                                {log.error_msg || '未知错误'}
                              </pre>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Stats summary */}
      <div style={cardStyle}>
        <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 14, color: '#333' }}>统计</h3>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' as const }}>
          <StatCard label="总兑换码" value={codes.length} />
          <StatCard label="启用中" value={codes.filter(c => c.is_active).length} />
          <StatCard label="已禁用" value={codes.filter(c => !c.is_active).length} />
          <StatCard label="总使用次数" value={codes.reduce((s, c) => s + c.used_quota, 0)} />
          <StatCard label="总配额" value={codes.reduce((s, c) => s + c.total_quota, 0)} />
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div style={{
      background: '#f8f9ff',
      borderRadius: 8,
      padding: '12px 20px',
      minWidth: 100,
      textAlign: 'center' as const,
    }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: '#1a73e8' }}>{value}</div>
      <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>{label}</div>
    </div>
  );
}
