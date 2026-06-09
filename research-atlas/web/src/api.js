// 모든 호출은 상대경로 → Vite proxy가 :8000으로 전달.
async function jsonOrThrow(res) {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${body}`);
  }
  return res.json();
}

export const getGraph = () => fetch("/api/graph").then(jsonOrThrow);

export const getLexicon = () => fetch("/api/lexicon").then(jsonOrThrow);

export const patchLexicon = (name, patch) =>
  fetch(`/api/lexicon/${encodeURIComponent(name)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  }).then(jsonOrThrow);

export const mergeLexicon = (from, into) =>
  fetch("/api/lexicon/merge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from, into }),
  }).then(jsonOrThrow);

export const rebuild = () =>
  fetch("/api/rebuild", { method: "POST" }).then(jsonOrThrow);
