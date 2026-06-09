import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { getGraph } from "../api.js";

const TYPE_COLOR = {
  technique: "#4fc3f7",
  benchmark: "#e0943a",
  analysis: "#b06fd6",
  survey: "#5cb96f",
  other: "#888",
};

export default function Graph() {
  const svgRef = useRef(null);
  const apiRef = useRef(null); // render()가 돌려준 {sim, focus, names}
  const lastQ = useRef(""); // 같은 검색어 Enter → 다음 매칭 순회
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState([]); // [{id, canonical}]
  const [matchIdx, setMatchIdx] = useState(0);
  const [searchMsg, setSearchMsg] = useState(""); // "없음" 등

  useEffect(() => {
    getGraph()
      .then((data) => {
        apiRef.current = render(svgRef.current, data, setSelected);
      })
      .catch((e) => setError(e.message));
    return () => apiRef.current && apiRef.current.sim.stop();
  }, []);

  function goTo(id, list, idx) {
    apiRef.current.focus(id);
    setMatches(list);
    setMatchIdx(idx);
    setSearchMsg("");
  }

  function runSearch(e) {
    e.preventDefault();
    const api = apiRef.current;
    if (!api) return;
    const q = query.trim().toLowerCase();
    if (!q) {
      setMatches([]);
      setSearchMsg("");
      return;
    }
    const found = api.names.filter((n) =>
      n.canonical.toLowerCase().includes(q)
    );
    if (found.length === 0) {
      setMatches([]);
      setSearchMsg("없음");
      lastQ.current = q;
      return;
    }
    // 같은 검색어로 다시 Enter → 다음 매칭으로 순회
    const advance = q === lastQ.current && found.length > 1;
    const idx = advance ? (matchIdx + 1) % found.length : 0;
    lastQ.current = q;
    goTo(found[idx].id, found, idx);
  }

  return (
    <div className="graph-page">
      <svg id="graph-svg" ref={svgRef} />
      <form className="graph-search" onSubmit={runSearch}>
        <input
          placeholder="노드 검색 (예: RLHF)…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {searchMsg && <div className="muted">{searchMsg}</div>}
        {matches.length > 1 && (
          <div className="match-list">
            {matches.map((m, i) => (
              <button
                type="button"
                key={m.id}
                className={i === matchIdx ? "active" : ""}
                onClick={() => goTo(m.id, matches, i)}
              >
                {m.canonical}
              </button>
            ))}
          </div>
        )}
      </form>
      <div className="graph-legend">
        <div>
          <span className="dot" style={{ background: TYPE_COLOR.technique }} />
          technique
        </div>
        <div>
          <span className="dot" style={{ background: TYPE_COLOR.benchmark }} />
          benchmark
        </div>
        <div>
          <span className="dot" style={{ background: TYPE_COLOR.analysis }} />
          analysis
        </div>
        <div>
          <span className="dot" style={{ background: TYPE_COLOR.survey }} />
          survey
        </div>
        <div style={{ marginTop: 3 }}>
          <span
            className="dot"
            style={{ background: "#16161a", border: "2px solid #4fc3f7" }}
          />
          빈 원 = 정의 없음
        </div>
      </div>
      <div className="graph-panel">
        {error ? (
          <div className="toast err">{error}</div>
        ) : selected ? (
          <>
            <h3>{selected.canonical}</h3>
            <div className="muted">
              type: {selected.ptype}
              {selected.domain && selected.domain !== "general"
                ? ` · domain: ${selected.domain}`
                : ""}
            </div>
            <div style={{ marginTop: 8 }}>
              {selected.definition ||
                (selected.def_status === "placeholder"
                  ? "정의 없음 — 원논문 미수록"
                  : "정의 없음")}
            </div>
            <div className="muted" style={{ marginTop: 12 }}>
              등장 {selected.papers.length}편: {selected.papers.join(", ")}
            </div>
          </>
        ) : (
          <>
            <h3>지형도</h3>
            <div className="muted">노드를 클릭하세요.</div>
          </>
        )}
      </div>
    </div>
  );
}

function render(svgEl, data, setSelected) {
  const W = window.innerWidth;
  const H = window.innerHeight - 41;
  const fill = (d) =>
    d.def_status === "placeholder" ? "#16161a" : TYPE_COLOR[d.ptype] || "#4fc3f7";
  const stroke = (d) => TYPE_COLOR[d.ptype] || "#4fc3f7";

  // normalized.json(객체 nodes + builds_on) → d3 배열 형태로 변환
  const nodes = Object.entries(data.nodes).map(([id, n]) => ({ id, ...n }));
  const nodeIds = new Set(nodes.map((n) => n.id));
  const links = data.builds_on
    .filter((b) => nodeIds.has(b.from) && nodeIds.has(b.to))
    .map((b) => ({
      source: b.from,
      target: b.to,
      from_type: data.nodes[b.from].ptype || "technique",
    }));

  const svg = d3.select(svgEl).attr("width", W).attr("height", H);
  svg.selectAll("*").remove();

  // 화살표 마커(ptype별)
  const defs = svg.append("defs");
  for (const [type, color] of Object.entries(TYPE_COLOR)) {
    defs
      .append("marker")
      .attr("id", `arr-${type}`)
      .attr("markerWidth", 10)
      .attr("markerHeight", 10)
      .attr("refX", 20)
      .attr("refY", 3)
      .attr("orient", "auto")
      .attr("markerUnits", "strokeWidth")
      .append("path")
      .attr("d", "M0,0L0,6L9,3z")
      .attr("fill", color);
  }

  const root = svg.append("g");
  const zoom = d3.zoom().on("zoom", (e) => root.attr("transform", e.transform));
  svg.call(zoom);

  const link = root
    .append("g")
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("stroke", (d) => TYPE_COLOR[d.from_type] || "#888")
    .attr("stroke-width", 1.8)
    .attr("stroke-opacity", 0.65)
    .attr("marker-end", (d) => `url(#arr-${d.from_type || "technique"})`);

  const node = root
    .append("g")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .call(
      d3
        .drag()
        .on("start", (e, d) => {
          if (!e.active) sim.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (e, d) => {
          d.fx = e.x;
          d.fy = e.y;
        })
        .on("end", (e, d) => {
          if (!e.active) sim.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
    );

  node
    .append("circle")
    .attr("r", 10)
    .attr("fill", fill)
    .attr("stroke", stroke)
    .attr("stroke-width", 2.5)
    .on("click", (e, d) => setSelected(d));

  node
    .append("text")
    .text((d) => d.canonical)
    .attr("x", 13)
    .attr("y", 4);

  const sim = d3
    .forceSimulation(nodes)
    .force(
      "link",
      d3
        .forceLink(links)
        .id((d) => d.id)
        .distance(160)
        .strength(0.3)
    )
    .force("charge", d3.forceManyBody().strength(-900))
    .force("center", d3.forceCenter(W / 2, H / 2))
    .force("collide", d3.forceCollide(28))
    .on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

  // 검색→포커스: 노드를 화면 중앙으로 이동(transition)하고 강조
  const nodeById = new Map(nodes.map((n) => [n.id, n]));
  function focus(id) {
    const d = nodeById.get(id);
    if (!d) return;
    const k = 1.5; // 적당한 확대
    const t = d3.zoomIdentity
      .translate(W / 2 - k * d.x, H / 2 - k * d.y)
      .scale(k);
    svg.transition().duration(500).call(zoom.transform, t);
    node
      .select("circle")
      .attr("stroke-width", (c) => (c.id === id ? 5 : 2.5))
      .attr("r", (c) => (c.id === id ? 15 : 10));
    setSelected(d); // 사이드 패널도 갱신
  }

  const names = nodes.map((n) => ({ id: n.id, canonical: n.canonical }));
  return { sim, focus, names };
}
