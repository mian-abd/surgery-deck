import { NavLink, Route, Routes } from "react-router-dom";
import Sessions from "./pages/Sessions";
import Monitor from "./pages/Monitor";
import Capture from "./pages/Capture";
import Review from "./pages/Review";
import Report from "./pages/Report";

function Nav() {
  const link = (to: string, label: string) => (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `px-3 py-1.5 rounded-md text-sm font-medium ${
          isActive ? "bg-sky-600 text-white" : "text-slate-300 hover:bg-edge"
        }`
      }
    >
      {label}
    </NavLink>
  );
  return (
    <header className="border-b border-edge bg-panel">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-3">
        <div className="flex items-center gap-2 mr-4">
          <span className="text-sky-400 text-lg">◆</span>
          <span className="font-semibold tracking-tight">ORGuard</span>
          <span className="text-xs text-slate-500">Surgical Safety Monitor</span>
        </div>
        <nav className="flex gap-1">
          {link("/", "Sessions")}
          {link("/capture", "Camera")}
          {link("/monitor", "Monitor")}
          {link("/review", "Review")}
          {link("/report", "Report")}
        </nav>
        <span className="ml-auto text-[11px] text-amber-400/80">
          Prototype · not for clinical use
        </span>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <div className="min-h-full flex flex-col">
      <Nav />
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<Sessions />} />
          <Route path="/capture" element={<Capture />} />
          <Route path="/capture/:sessionId" element={<Capture />} />
          <Route path="/monitor" element={<Monitor />} />
          <Route path="/monitor/:sessionId" element={<Monitor />} />
          <Route path="/review" element={<Review />} />
          <Route path="/review/:sessionId" element={<Review />} />
          <Route path="/report" element={<Report />} />
          <Route path="/report/:sessionId" element={<Report />} />
        </Routes>
      </main>
    </div>
  );
}
