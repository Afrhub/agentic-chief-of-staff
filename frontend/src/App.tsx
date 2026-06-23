import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import Onboarding from './pages/Onboarding';
import { DEMO_FOUNDER_ID } from './demo';
import './App.css';

const App: React.FC = () => {
  const [founderId, setFounderId] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Theme tokens cascade off data-theme — set it before any screen renders.
    document.documentElement.setAttribute('data-theme', localStorage.getItem('cos-theme') || 'dark');

    // `?demo` or `?founder=demo-founder` → public canned demo, no login.
    const params = new URLSearchParams(window.location.search);
    if (params.has('demo') || params.get('founder') === DEMO_FOUNDER_ID) {
      setDemo(true);
      setFounderId(DEMO_FOUNDER_ID);
    } else {
      // Live: require a session from login (token + id stored by Login).
      const token = localStorage.getItem('token');
      const fid = localStorage.getItem('founder_id');
      if (token && fid) {
        setFounderId(fid);
        // resume onboarding if a fresh signup didn't finish it (survives refresh)
        if (localStorage.getItem('dcern_onboarding') === 'pending') setNeedsOnboarding(true);
      }
    }
    setReady(true);
  }, []);

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('founder_id');
    setFounderId(null);
  };

  const handleAuthed = (fid: string, isNew?: boolean) => {
    setFounderId(fid);
    if (isNew) setNeedsOnboarding(true);
  };

  if (!ready) return <div className="loading">Loading…</div>;
  if (!founderId) return <Login onAuthed={handleAuthed} />;
  if (needsOnboarding && !demo)
    return (
      <Onboarding
        founderId={founderId}
        onDone={() => {
          localStorage.setItem('dcern_onboarding', 'done');
          setNeedsOnboarding(false);
        }}
      />
    );

  return (
    <Router>
      <Routes>
        <Route
          path="/"
          element={<Dashboard founderId={founderId} onLogout={demo ? undefined : logout} />}
        />
      </Routes>
    </Router>
  );
};

export default App;
