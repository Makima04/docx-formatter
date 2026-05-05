import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Login from './pages/Login';
import Home from './pages/Home';
import Templates from './pages/Templates';
import Batch from './pages/Batch';
import History from './pages/History';
import { useAuth } from './hooks/useAuth';
import { checkCode } from './api/client';

export default function App() {
  const { code, setCode, valid, remaining, checking } = useAuth();
  const [loginError, setLoginError] = React.useState('');

  const handleLogin = async (inputCode: string) => {
    setLoginError('');
    try {
      const result = await checkCode(inputCode);
      if (result.valid) {
        setCode(inputCode);
      } else {
        setLoginError('兑换码无效或已用完');
      }
    } catch {
      setLoginError('验证失败，请重试');
    }
  };

  const handleLogout = () => {
    setCode('');
  };

  const refreshQuota = async () => {
    if (code) {
      try {
        const result = await checkCode(code);
        if (!result.valid) {
          setCode('');
        }
      } catch {}
    }
  };

  if (!code || !valid) {
    return <Login onLogin={handleLogin} checking={checking} error={loginError} />;
  }

  return (
    <BrowserRouter>
      <Layout code={code} remaining={remaining} onLogout={handleLogout}>
        <Routes>
          <Route path="/" element={<Home code={code} onQuotaChange={refreshQuota} />} />
          <Route path="/batch" element={<Batch code={code} onQuotaChange={refreshQuota} />} />
          <Route path="/templates" element={<Templates />} />
          <Route path="/history" element={<History />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
