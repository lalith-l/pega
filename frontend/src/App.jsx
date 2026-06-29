import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Landing from './pages/Landing';
import CaseDashboard from './pages/CaseDashboard';
import './index.css';

function Navbar() {
  return (
    <nav className="navbar">
      <NavLink to="/" className="navbar-logo">
        ⬡ MORPHEUS
      </NavLink>
      <div className="navbar-links">
        <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          Dashboard
        </NavLink>
        <NavLink to="/court/new" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          + New Case
        </NavLink>
      </div>
    </nav>
  );
}

import { ErrorBoundary } from './components/ErrorBoundary';

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/court/new" element={<ErrorBoundary><CaseDashboard /></ErrorBoundary>} />
        <Route path="/court/:sessionId" element={<ErrorBoundary><CaseDashboard /></ErrorBoundary>} />
        <Route path="/cases/:caseId" element={<ErrorBoundary><CaseDashboard /></ErrorBoundary>} />
      </Routes>
    </BrowserRouter>
  );
}
