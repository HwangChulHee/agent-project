import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Graph from "./routes/Graph.jsx";
import Lexicon from "./routes/Lexicon.jsx";
import Search from "./routes/Search.jsx";

export default function App() {
  return (
    <>
      <nav className="nav">
        <span className="brand">research-atlas</span>
        <NavLink to="/lexicon">사전</NavLink>
        <NavLink to="/graph">지형도</NavLink>
        <NavLink to="/search">질의</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/lexicon" replace />} />
        <Route path="/lexicon" element={<Lexicon />} />
        <Route path="/graph" element={<Graph />} />
        <Route path="/search" element={<Search />} />
      </Routes>
    </>
  );
}
