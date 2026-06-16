import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import { DEMO_FOUNDER_ID } from './demo';
import './App.css';

const App: React.FC = () => {
  const [founderId, setFounderId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Real auth (OAuth/session) sets `founder_id`. With none present we fall
    // back to a self-contained demo founder so the app is never a dead end.
    const stored = localStorage.getItem('founder_id');
    setFounderId(stored || DEMO_FOUNDER_ID);
    setLoading(false);
  }, []);

  if (loading) {
    return <div className="loading">Loading…</div>;
  }

  if (!founderId) {
    return <div className="auth-required">Redirecting to auth…</div>;
  }

  return (
    <Router>
      <Routes>
        <Route path="/" element={<Dashboard founderId={founderId} />} />
      </Routes>
    </Router>
  );
};

export default App;
