import { useEffect, useMemo, useRef, useState } from "react";
import {
  getLexicon,
  mergeLexicon,
  patchLexicon,
  rebuild,
} from "../api.js";

const STATUSES = ["approved", "unreviewed", "pending", "rejected"];
const FILTERS = ["pending", "unreviewed", "approved", "rejected", "all"];

export default function Lexicon() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("pending"); // 대기열 처리가 주 작업
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState(null); // "name" | "status" | "source" | "first_seen"
  const [sortDir, setSortDir] = useState("asc");
  const [toast, setToast] = useState(null); // {msg, err}
  const [rebuilding, setRebuilding] = useState(false);
  const firstMatchRef = useRef(null); // 검색 첫 매칭 행 → 스크롤 대상

  function toggleSort(key) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  const flash = (msg, err = false) => {
    setToast({ msg, err });
    setTimeout(() => setToast(null), 3000);
  };

  async function reload() {
    setLoading(true);
    try {
      setItems(await getLexicon());
    } catch (e) {
      flash(`로드 실패: ${e.message}`, true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  // 한 항목의 필드를 PATCH하고 로컬 상태도 갱신
  async function applyPatch(name, patch) {
    try {
      await patchLexicon(name, patch);
      setItems((prev) =>
        prev.map((it) => (it.name === name ? { ...it, ...patch } : it))
      );
    } catch (e) {
      flash(`저장 실패: ${e.message}`, true);
    }
  }

  async function doMerge(from) {
    const into = window.prompt(
      `"${from}"을(를) 어느 개념의 alias로 병합할까요?\n대상 개념명을 정확히 입력하세요.`
    );
    if (!into) return;
    if (!items.some((it) => it.name === into)) {
      flash(`대상 개념 없음: ${into}`, true);
      return;
    }
    try {
      await mergeLexicon(from, into);
      flash(`병합됨: ${from} → ${into}`);
      reload();
    } catch (e) {
      flash(`병합 실패: ${e.message}`, true);
    }
  }

  async function doRebuild() {
    setRebuilding(true);
    try {
      const r = await rebuild();
      flash(`그래프 갱신됨 — 노드 ${r.nodes} / 계보 ${r.builds_on}`);
    } catch (e) {
      flash(`재빌드 실패: ${e.message}`, true);
    } finally {
      setRebuilding(false);
    }
  }

  const counts = useMemo(() => {
    const c = {};
    for (const it of items) c[it.status] = (c[it.status] || 0) + 1;
    return c;
  }, [items]);

  // 필터(상태) + 정렬. 검색은 숨기지 않고 강조/스크롤로 처리한다.
  const visible = useMemo(() => {
    const arr = items.filter((it) => filter === "all" || it.status === filter);
    if (sortKey) {
      arr.sort((a, b) => {
        const av = (a[sortKey] ?? "").toString().toLowerCase();
        const bv = (b[sortKey] ?? "").toString().toLowerCase();
        const cmp = av < bv ? -1 : av > bv ? 1 : 0;
        return sortDir === "asc" ? cmp : -cmp;
      });
    }
    return arr;
  }, [items, filter, sortKey, sortDir]);

  const q = query.trim().toLowerCase();
  const matchSet = useMemo(() => {
    if (!q) return null;
    return new Set(
      visible.filter((it) => it.name.toLowerCase().includes(q)).map((it) => it.name)
    );
  }, [visible, q]);
  const firstMatch = q
    ? visible.find((it) => it.name.toLowerCase().includes(q))?.name
    : null;

  // 검색어/정렬/필터가 바뀌어 첫 매칭이 달라지면 그 행으로 스크롤
  useEffect(() => {
    if (firstMatchRef.current)
      firstMatchRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [firstMatch]);

  // 정렬 가능한 헤더 셀
  const th = (key, label, width) => (
    <th
      style={{ width, cursor: "pointer" }}
      onClick={() => toggleSort(key)}
      title="클릭하여 정렬"
    >
      {label}
      {sortKey === key ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
    </th>
  );

  return (
    <div className="lex-wrap">
      <div className="lex-toolbar">
        {FILTERS.map((f) => (
          <button
            key={f}
            className={`filter-btn${filter === f ? " active" : ""}`}
            onClick={() => setFilter(f)}
          >
            {f}
            {f !== "all" && counts[f] ? ` (${counts[f]})` : ""}
          </button>
        ))}
        <input
          placeholder="개념명 검색(강조)…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ width: 180 }}
        />
        {q && (
          <span className="muted">
            {matchSet && matchSet.size > 0
              ? `${matchSet.size}건 매칭`
              : "매칭 없음"}
          </span>
        )}
        <span className="spacer" />
        <span className="muted">승인/거부 후 재빌드해야 그래프에 반영됩니다 →</span>
        <button onClick={doRebuild} disabled={rebuilding}>
          {rebuilding ? "재빌드 중…" : "↻ 그래프 재빌드"}
        </button>
      </div>

      {loading ? (
        <div className="muted">로딩 중…</div>
      ) : (
        <table className="lex-table">
          <thead>
            <tr>
              {th("name", "개념명", "16%")}
              <th style={{ width: "22%" }}>aliases</th>
              {th("status", "status", "12%")}
              <th style={{ width: "28%" }}>definition</th>
              {th("source", "source", "8%")}
              {th("first_seen", "first_seen", "8%")}
              <th style={{ width: "6%" }}>액션</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((it) => (
              <Row
                key={it.name}
                item={it}
                onPatch={applyPatch}
                onMerge={doMerge}
                matched={matchSet ? matchSet.has(it.name) : false}
                rowRef={it.name === firstMatch ? firstMatchRef : null}
              />
            ))}
          </tbody>
        </table>
      )}
      {!loading && visible.length === 0 && (
        <div className="muted" style={{ padding: 20 }}>
          해당 조건의 개념이 없습니다.
        </div>
      )}

      {toast && (
        <div className={`toast${toast.err ? " err" : ""}`}>{toast.msg}</div>
      )}
    </div>
  );
}

function Row({ item, onPatch, onMerge, matched, rowRef }) {
  const [newAlias, setNewAlias] = useState("");
  const [def, setDef] = useState(item.definition || "");
  const defDirty = def !== (item.definition || "");

  function addAlias() {
    const a = newAlias.trim();
    if (!a || item.aliases.includes(a)) {
      setNewAlias("");
      return;
    }
    onPatch(item.name, { aliases: [...item.aliases, a] });
    setNewAlias("");
  }
  function removeAlias(a) {
    onPatch(item.name, { aliases: item.aliases.filter((x) => x !== a) });
  }

  return (
    <tr ref={rowRef} className={matched ? "matched" : ""}>
      <td>{item.name}</td>
      <td>
        {item.aliases.map((a) => (
          <span className="alias-chip" key={a}>
            {a}
            <button title="삭제" onClick={() => removeAlias(a)}>
              ×
            </button>
          </span>
        ))}
        <input
          placeholder="+ alias"
          value={newAlias}
          onChange={(e) => setNewAlias(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addAlias()}
          onBlur={addAlias}
          style={{ width: 80 }}
        />
      </td>
      <td>
        <select
          className={`badge st-${item.status}`}
          value={item.status}
          onChange={(e) => onPatch(item.name, { status: e.target.value })}
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </td>
      <td>
        <textarea
          rows={2}
          style={{ width: "100%", resize: "vertical" }}
          value={def}
          onChange={(e) => setDef(e.target.value)}
          onBlur={() => defDirty && onPatch(item.name, { definition: def })}
          placeholder="(비어 있음)"
        />
      </td>
      <td className="muted">{item.source}</td>
      <td className="muted">{item.first_seen}</td>
      <td>
        <button onClick={() => onMerge(item.name)} title="다른 개념의 alias로 병합">
          병합
        </button>
        <button disabled title="준비 중: 사용 맥락을 LLM에 질의" style={{ marginTop: 4 }}>
          AI 도우미
        </button>
      </td>
    </tr>
  );
}
