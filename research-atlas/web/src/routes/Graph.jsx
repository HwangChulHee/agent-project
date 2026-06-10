import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { getGraph, postCommand } from "../api.js";

const TYPE_COLOR = {
  technique: "#2563eb",
  benchmark: "#d97706",
  analysis: "#7c3aed",
  survey: "#059669",
  other: "#888",
};

// arXiv ID "2502.14192" → 등장 연월 "2025-02". 형식이 다르면 null.
function arxivMonth(id) {
  const m = String(id).slice(0, 4);
  if (!/^\d{4}$/.test(m)) return null;
  return `20${m.slice(0, 2)}-${m.slice(2, 4)}`;
}

// 노드 등장 시점 = papers 중 가장 이른 연월. papers 없으면 null(시점 불명).
function nodeMonth(node) {
  if (!node.papers || node.papers.length === 0) return null;
  let earliest = null;
  for (const id of node.papers) {
    const ym = arxivMonth(id);
    if (ym && (!earliest || ym < earliest)) earliest = ym;
  }
  return earliest;
}

export default function Graph() {
  const svgRef = useRef(null);
  const areaRef = useRef(null); // 그래프 영역 div (크기 측정용)
  const apiRef = useRef(null); // render()가 돌려준 {sim, focus, names, highlight, resize}
  const dataRef = useRef(null); // 원본 그래프 데이터 {nodes, builds_on}
  const lastQ = useRef(""); // 같은 검색어 Enter → 다음 매칭 순회
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState([]); // [{id, canonical}]
  const [matchIdx, setMatchIdx] = useState(0);
  const [searchMsg, setSearchMsg] = useState(""); // "없음" 등

  // --- 채팅 패널 상태 ---
  const [collapsed, setCollapsed] = useState(false);
  const [messages, setMessages] = useState([]); // [{role:'user'|'agent', text}]
  const [chatInput, setChatInput] = useState("");
  const [pending, setPending] = useState(false);
  const [chips, setChips] = useState([]); // 활성 조건 칩 라벨들
  const msgEndRef = useRef(null);

  useEffect(() => {
    getGraph()
      .then((data) => {
        dataRef.current = data;
        apiRef.current = render(areaRef.current, svgRef.current, data, setSelected);
      })
      .catch((e) => setError(e.message));
    return () => apiRef.current && apiRef.current.sim.stop();
  }, []);

  // 그래프 영역 크기 변화(패널 접기/펴기, 윈도우 리사이즈) → svg/force 갱신
  useEffect(() => {
    if (!areaRef.current) return;
    const ro = new ResizeObserver(() => apiRef.current && apiRef.current.resize());
    ro.observe(areaRef.current);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    msgEndRef.current && msgEndRef.current.scrollIntoView({ block: "end" });
  }, [messages, pending]);

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

  // --- 채팅: tool 실행 의미론 ---
  function applyFilter(args) {
    const nodes = dataRef.current.nodes;
    const ids = new Set();
    for (const [id, n] of Object.entries(nodes)) {
      if (args.ptype && n.ptype !== args.ptype) continue;
      if (args.domain && n.domain !== args.domain) continue;
      if (args.date_after) {
        const ym = nodeMonth(n);
        if (!ym || ym < args.date_after) continue;
      }
      ids.add(id);
    }
    return ids;
  }

  function lineageSets(node, direction) {
    const nodes = dataRef.current.nodes;
    const builds = dataRef.current.builds_on;
    const key = String(node).toLowerCase();
    if (!nodes[key]) return null;
    // 사이클 방지 visited 사용. start 자신은 결과 집합에 미포함(개수 분리용).
    const walk = (next) => {
      const out = new Set();
      const visited = new Set([key]);
      const stack = [key];
      while (stack.length) {
        const cur = stack.pop();
        for (const nx of next(cur)) {
          if (!visited.has(nx)) {
            visited.add(nx);
            out.add(nx);
            stack.push(nx);
          }
        }
      }
      return out;
    };
    // builds_on {from, to}: from이 to 위에 지어짐 = to가 조상.
    const ancestors = walk((cur) =>
      builds.filter((b) => b.from === cur).map((b) => b.to)
    );
    const descendants = walk((cur) =>
      builds.filter((b) => b.to === cur).map((b) => b.from)
    );
    let ids;
    if (direction === "ancestors") ids = new Set(ancestors);
    else if (direction === "descendants") ids = new Set(descendants);
    else ids = new Set([...ancestors, ...descendants]);
    ids.add(key);
    return { ids, key, ancestors: ancestors.size, descendants: descendants.size };
  }

  function filterSummary(args) {
    const parts = [];
    if (args.ptype) parts.push(args.ptype);
    if (args.domain) parts.push(args.domain);
    if (args.date_after) parts.push(`${args.date_after} 이후`);
    return parts.join(" · ") || "전체";
  }

  function filterChips(args) {
    const c = [];
    if (args.ptype) c.push(`ptype=${args.ptype}`);
    if (args.domain) c.push(`domain=${args.domain}`);
    if (args.date_after) c.push(`date_after=${args.date_after}`);
    return c;
  }

  function addAgent(text) {
    setMessages((m) => [...m, { role: "agent", text }]);
  }

  function handleResult(res) {
    if (!res.tool) {
      addAgent(res.message || "처리할 수 없는 요청입니다.");
      return;
    }
    if (res.tool === "filter") {
      const ids = applyFilter(res.args || {});
      if (ids.size === 0) {
        addAgent("조건에 맞는 노드가 없음"); // 강조 변경 없이 유지
        return;
      }
      apiRef.current.highlight(ids);
      setChips(filterChips(res.args || {}));
      addAgent(`${filterSummary(res.args || {})} · ${ids.size}개 강조`);
      return;
    }
    if (res.tool === "focus_lineage") {
      const args = res.args || {};
      const r = lineageSets(args.node, args.direction);
      if (!r) {
        addAgent(`'${args.node}' 노드를 찾지 못함`);
        return;
      }
      apiRef.current.highlight(r.ids);
      const canonical = dataRef.current.nodes[r.key].canonical;
      setChips([`lineage=${canonical}`]);
      addAgent(
        `'${canonical}' 계보 강조 (조상 ${r.ancestors} · 자손 ${r.descendants})`
      );
      return;
    }
    if (res.tool === "reset") {
      apiRef.current.highlight(null);
      setChips([]);
      addAgent("전체 표시로 복원");
      return;
    }
    addAgent(`알 수 없는 도구: ${res.tool}`);
  }

  async function sendCommand(e) {
    e.preventDefault();
    const text = chatInput.trim();
    if (!text || pending || !apiRef.current) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setChatInput("");
    setPending(true);
    try {
      const res = await postCommand(text);
      handleResult(res);
    } catch (err) {
      addAgent(`요청 실패: ${err.message}`);
    } finally {
      setPending(false);
    }
  }

  function clearHighlight() {
    apiRef.current && apiRef.current.highlight(null);
    setChips([]);
  }

  return (
    <div className="graph-page">
      <div className="graph-area" ref={areaRef}>
        <svg id="graph-svg" ref={svgRef} />
        {chips.length > 0 && (
          <div className="graph-chips">
            {chips.map((c) => (
              <span className="graph-chip" key={c}>
                {c}
                <button type="button" onClick={clearHighlight} title="전체 복원">
                  ✕
                </button>
              </span>
            ))}
          </div>
        )}
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
              style={{ background: "#fff", border: "2px dashed #64748b" }}
            />
            빈 원(점선) = 정의 없음
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

      {collapsed ? (
        <button
          className="chat-toggle collapsed"
          onClick={() => setCollapsed(false)}
          title="채팅 열기"
        >
          {"<"}
        </button>
      ) : (
        <div className="chat-panel">
          <div className="chat-head">
            <button
              className="chat-toggle"
              onClick={() => setCollapsed(true)}
              title="채팅 접기"
            >
              {">"}
            </button>
            <span className="muted">필터 에이전트</span>
          </div>
          <div className="chat-msgs">
            {messages.length === 0 && (
              <div className="muted chat-hint">
                예: "벤치마크만 보여줘", "RAG 계보만 보여줘", "다 보여줘"
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`chat-bubble ${m.role}`}>
                {m.text}
              </div>
            ))}
            {pending && <div className="chat-bubble agent">…</div>}
            <div ref={msgEndRef} />
          </div>
          <form className="chat-input" onSubmit={sendCommand}>
            <input
              placeholder="명령을 입력…"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
            />
            <button type="submit" disabled={pending}>
              전송
            </button>
          </form>
        </div>
      )}
    </div>
  );
}

function render(container, svgEl, data, setSelected) {
  const W = container.clientWidth;
  const H = container.clientHeight;
  const fill = (d) =>
    d.def_status === "placeholder" ? "#ffffff" : TYPE_COLOR[d.ptype] || "#2563eb";
  const stroke = (d) => TYPE_COLOR[d.ptype] || "#2563eb";
  const dash = (d) => (d.def_status === "placeholder" ? "3 2" : null);

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
    .attr("r", 12)
    .attr("fill", fill)
    .attr("stroke", stroke)
    .attr("stroke-width", 2.5)
    .attr("stroke-dasharray", dash)
    .on("click", (e, d) => setSelected(d));

  node
    .append("text")
    .text((d) => d.canonical)
    .attr("x", 16)
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
    .force("collide", d3.forceCollide(30))
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
    const w = container.clientWidth;
    const h = container.clientHeight;
    const k = 1.5; // 적당한 확대
    const t = d3.zoomIdentity
      .translate(w / 2 - k * d.x, h / 2 - k * d.y)
      .scale(k);
    svg.transition().duration(500).call(zoom.transform, t);
    node
      .select("circle")
      .attr("stroke-width", (c) => (c.id === id ? 5 : 2.5))
      .attr("r", (c) => (c.id === id ? 18 : 12));
    setSelected(d); // 사이드 패널도 갱신
  }

  // 강조/흐리게: 매칭 노드 opacity 1, 비매칭은 흐리게(숨기지 않음).
  // 엣지는 양 끝 모두 매칭일 때만 표시, 아니면 완전 숨김(화살촉 포함).
  // ids === null → 전체 복원.
  function highlight(ids) {
    if (!ids) {
      node.attr("opacity", 1);
      link.style("display", null).attr("stroke-opacity", 0.65);
      return;
    }
    node.attr("opacity", (d) => (ids.has(d.id) ? 1 : 0.18));
    link.style("display", (d) =>
      ids.has(d.source.id) && ids.has(d.target.id) ? null : "none"
    );
  }

  // 컨테이너 크기 변화 시 svg/force 갱신
  function resize() {
    const w = container.clientWidth;
    const h = container.clientHeight;
    if (!w || !h) return;
    svg.attr("width", w).attr("height", h);
    sim.force("center", d3.forceCenter(w / 2, h / 2));
    sim.alpha(0.2).restart();
  }

  const names = nodes.map((n) => ({ id: n.id, canonical: n.canonical }));
  return { sim, focus, names, highlight, resize };
}
