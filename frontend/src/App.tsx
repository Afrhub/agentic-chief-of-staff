import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import { DEMO_FOUNDER_ID } from './demo';
import './App.css';

const App: React.FC = () => {
  const [founderId, setFounderId] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
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
      if (token && fid) setFounderId(fid);
    }
    setReady(true);
  }, []);

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('founder_id');
    setFounderId(null);
  };

  if (!ready) return <div className="loading">Loading…</div>;
  if (!founderId) return <Login onAuthed={setFounderId} />;

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
