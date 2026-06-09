"""시각화: builds_on(실선) + applies(점선) → graph.html"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config


def build_data():
    norm = json.load(open(config.OUT_DIR / "normalized.json"))
    nodes, links = [], []
    # problem 유사 쌍 로드 (같은 논문 출신 = 동일 paper 쌍은 제외)
    sim_pairs = []
    sim_path = config.OUT_DIR / "similarity.json"
    if sim_path.exists():
        sd = json.load(open(sim_path))
        node_papers = {k: set(v.get("papers", [])) for k, v in norm["nodes"].items()}
        for x in sd["sims"].get("problem", []):
            a, b = x["a"], x["b"]
            if a in norm["nodes"] and b in norm["nodes"]:
                # 같은 논문에서 나온 쌍이면 제외 (유사도 1.0 가짜)
                if node_papers.get(a) and node_papers.get(a) == node_papers.get(b):
                    continue
                sim_pairs.append({"source": a, "target": b, "sim": x["sim"]})
    for key, n in norm["nodes"].items():
        nodes.append({"id": key, "label": n["canonical"], "def_status": n["def_status"],
                      "ptype": n.get("ptype","technique"), "has_def": n["def_status"]=="ok",
                      "definition": n["definition"], "papers": n["papers"], "domain": n.get("domain","general")})
    for b in norm["builds_on"]:
        if b["from"] in norm["nodes"] and b["to"] in norm["nodes"]:
            ft = norm["nodes"][b["from"]].get("ptype","technique")
            links.append({"source": b["from"], "target": b["to"], "kind": "builds_on", "from_type": ft})
    for b in norm.get("applies", []):
        if b["from"] in norm["nodes"] and b["to"] in norm["nodes"]:
            links.append({"source": b["from"], "target": b["to"], "kind": "applies"})
    return {"nodes": nodes, "links": links, "sim_pairs": sim_pairs}


HTML = """<!doctype html><html><head><meta charset="utf-8"><title>map</title>
<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
<style>
 body{margin:0;background:#16161a;color:#e8e8e8;font-family:monospace;overflow:hidden}
 #panel{position:fixed;top:0;right:0;width:340px;padding:16px;background:#1f1f26;height:100%;
        overflow:auto;box-sizing:border-box;font-size:13px;line-height:1.5}
 #legend{position:fixed;top:12px;left:12px;font-size:12px;background:#1f1f26;padding:10px;border-radius:4px}
 .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
 circle{cursor:pointer} text{font-size:11px;fill:#ccc;pointer-events:none}
</style></head><body>
<div id="legend">
 <div><span class="dot" style="background:#4fc3f7"></span>technique</div>
 <div><span class="dot" style="background:#e0943a"></span>benchmark</div>
 <div><span class="dot" style="background:#b06fd6"></span>analysis</div>
 <div><span class="dot" style="background:#5cb96f"></span>survey</div>
 <div style="margin-top:3px"><span class="dot" style="background:#16161a;border:2px solid #4fc3f7"></span>빈 원 = 정의 없음(원논문 필요)</div>
 <div style="margin-top:4px;color:#e0a030">━ builds_on</div>
 <div style="margin-top:8px;border-top:1px solid #333;padding-top:6px">
   <div style="color:#b06fd6">problem 유사 인력: <span id="simval">0</span></div>
   <input id="simslider" type="range" min="0" max="100" value="0" style="width:160px">
 </div>
</div>
<div id="panel"><h3>map</h3><div style="color:#888">노드 클릭</div></div>
<svg id="g"><defs>
 <marker id="arr-technique" markerWidth="10" markerHeight="10" refX="20" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0L0,6L9,3z" fill="#4fc3f7"/></marker>
 <marker id="arr-benchmark" markerWidth="10" markerHeight="10" refX="20" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0L0,6L9,3z" fill="#e0943a"/></marker>
 <marker id="arr-analysis" markerWidth="10" markerHeight="10" refX="20" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0L0,6L9,3z" fill="#b06fd6"/></marker>
 <marker id="arr-survey" markerWidth="10" markerHeight="10" refX="20" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0L0,6L9,3z" fill="#5cb96f"/></marker>
 <marker id="arr-other" markerWidth="10" markerHeight="10" refX="20" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0L0,6L9,3z" fill="#888"/></marker>
</defs></svg>
<script>
const DATA=__DATA__;const W=innerWidth,H=innerHeight;
const svg=d3.select("#g").attr("width",W).attr("height",H);
const root=svg.append("g");svg.call(d3.zoom().on("zoom",e=>root.attr("transform",e.transform)));
const TYPE_COLOR={technique:"#4fc3f7",benchmark:"#e0943a",analysis:"#b06fd6",survey:"#5cb96f",other:"#888"};
const fillColor=d=>d.def_status==="placeholder"?"#16161a":(TYPE_COLOR[d.ptype]||"#4fc3f7");
const strokeColor=d=>TYPE_COLOR[d.ptype]||"#4fc3f7";
const link=root.append("g").selectAll("line").data(DATA.links).join("line")
 .attr("stroke",d=>TYPE_COLOR[d.from_type]||"#888")
 .attr("stroke-width",1.8)
 .attr("stroke-opacity",0.65)
 .attr("marker-end",d=>"url(#arr-"+(d.from_type||"technique")+")");
const node=root.append("g").selectAll("g").data(DATA.nodes).join("g").call(
 d3.drag().on("start",(e,d)=>{if(!e.active)sim.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y;})
  .on("drag",(e,d)=>{d.fx=e.x;d.fy=e.y;}).on("end",(e,d)=>{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;
   if(SIM_STRENGTH>0)sim.alpha(0.4).restart();}));
node.append("circle").attr("r",10).attr("fill",fillColor).attr("stroke",strokeColor).attr("stroke-width",2.5)
 .on("click",(e,d)=>d3.select("#panel").html(
   `<h3>${d.label}</h3>`+
   `<div style="color:#aaa">type: ${d.ptype}${d.domain&&d.domain!=="general"?" · domain: "+d.domain:""}</div>`+
   `<div style="margin-top:6px">${d.definition||(d.def_status==="placeholder"?"정의없음 — 원논문 미수록":"—")}</div>`+
   `<div style="color:#888;margin-top:10px">등장 ${d.papers.length}편: ${d.papers.join(', ')}</div>`));
node.append("text").text(d=>d.label).attr("x",13).attr("y",4);
// problem 유사 인력: 슬라이더값 × 유사도로 당김
let SIM_STRENGTH=0;
const simPairs=(DATA.sim_pairs||[]).map(p=>({
  source:DATA.nodes.find(n=>n.id===p.source),
  target:DATA.nodes.find(n=>n.id===p.target),
  sim:p.sim
})).filter(p=>p.source&&p.target);
function problemForce(alpha){
  if(SIM_STRENGTH===0)return;
  for(const p of simPairs){
    const dx=p.target.x-p.source.x, dy=p.target.y-p.source.y;
    const dist=Math.sqrt(dx*dx+dy*dy)||1;
    // 유사도가 높을수록, 슬라이더가 클수록 강하게 당김
    const k=SIM_STRENGTH*p.sim*p.sim*(alpha+0.15)*0.08;
    const fx=dx/dist*k, fy=dy/dist*k;
    p.source.vx+=fx; p.source.vy+=fy;
    p.target.vx-=fx; p.target.vy-=fy;
  }
}
const sim=d3.forceSimulation(DATA.nodes)
 .force("link",d3.forceLink(DATA.links).id(d=>d.id).distance(160).strength(0.3))
 .force("charge",d3.forceManyBody().strength(-900))
 .force("center",d3.forceCenter(W/2,H/2))
 .force("problem",problemForce)
 .on("tick",()=>{link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y)
   .attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
   node.attr("transform",d=>`translate(${d.x},${d.y})`);});
document.getElementById("simslider").addEventListener("input",e=>{
  SIM_STRENGTH=+e.target.value;
  document.getElementById("simval").textContent=SIM_STRENGTH;
  // 슬라이더 켜져 있으면 시뮬을 살짝 데운 채 유지 → 인력 지속
  sim.alphaTarget(SIM_STRENGTH>0?0.05:0).alpha(0.5).restart();
});
</script></body></html>"""


def main():
    data = build_data()
    (config.OUT_DIR / "graph.html").write_text(HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    nb = sum(1 for l in data["links"] if l["kind"]=="builds_on")
    na = sum(1 for l in data["links"] if l["kind"]=="applies")
    print(f"노드 {len(data['nodes'])}개, builds_on {nb} / applies {na}")
    print(f"→ file://{(config.OUT_DIR / 'graph.html').resolve()}")


if __name__ == "__main__":
    main()
