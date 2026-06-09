"""추출 프롬프트. extract(내용+domain) / relate(builds_on+applies)."""

EXTRACT_SYSTEM = """You extract the CONTENT of an LLM/NLP/RAG/agent paper.
Given title, abstract, introduction, extract these fields. Do NOT judge relations to other papers here.

- title: verbatim.
- task: type(s) of work, short noun phrases. A list.
- defines: ONLY the main NAMED technique/system this paper defines or is known for
    (usually ONE, a proper noun like "LightRAG", "MedGraphRAG"). Each = {name, definition}.
    definition = ONE sentence. Do NOT list sub-components as defines — put those in `uses`.
- uses: names of techniques/components THIS paper uses internally. Names only.
- problem: the deficiency the paper addresses, ONE sentence.
- domain: the application domain this paper targets, as ONE short lowercase word/phrase
    (e.g. "medical", "legal", "finance", "code"). If general-purpose, output "general".
- paper_type: what KIND of paper this is. EXACTLY one of:
    "technique"  - proposes a new method/system (most papers)
    "benchmark"  - proposes an evaluation benchmark/framework/metric
    "analysis"   - studies/analyzes existing methods, reports findings, no new method
    "survey"     - reviews/categorizes a field
    "other"      - none of the above

Example (MedGraphRAG — a medical application of GraphRAG):
{
  "title": "Medical Graph RAG: Towards Safe Medical LLM via Graph RAG",
  "task": ["medical question answering"],
  "defines": [{"name": "MedGraphRAG", "definition": "A graph-based RAG framework for the medical domain using triple graph construction and U-retrieval."}],
  "uses": ["triple graph construction", "U-retrieval"],
  "problem": "General RAG lacks the safety and evidence grounding needed for clinical use.",
  "domain": "medical"
}
"""

EXTRACT_USER = """Paper text (title + abstract + introduction):
---
{text}
---
Extract the content fields as JSON."""

EXTRACT_SCHEMA = {
    "name": "paper_content",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "task": {"type": "array", "items": {"type": "string"}},
            "defines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "definition": {"type": "string"}},
                    "required": ["name", "definition"], "additionalProperties": False,
                },
            },
            "uses": {"type": "array", "items": {"type": "string"}},
            "problem": {"type": "string"},
            "domain": {"type": "string"},
            "paper_type": {"type": "string", "enum": ["technique","benchmark","analysis","survey","other"]},
        },
        "required": ["title", "task", "defines", "uses", "problem", "domain", "paper_type"],
        "additionalProperties": False,
    },
}

RELATE_SYSTEM = """You identify the LINEAGE of a research paper: which NAMED prior
techniques or systems this paper EXTENDS, IMPROVES UPON, or COMPARES AGAINST as a baseline.

Output `builds_on`: names of prior techniques this paper advances beyond.
- INCLUDE only NAMED prior techniques/systems (PROPER NOUNS): "RAG", "GraphRAG", "DPR", "HippoRAG".
- EXCLUDE generic phrases ("flat representations", "chunking"), datasets ("HotpotQA"),
  ontologies/tools ("UMLS", "Neo4J"), and the paper's OWN defined techniques.
- Names only. Empty list if none.

Note: domain application (e.g. using GraphRAG in medicine) still counts as builds_on
if the paper adapts/extends the method. Domain is tracked separately, not here."""

RELATE_USER = """This paper defines: {defines}
Its domain: {domain}
Its problem: {problem}

Paper text:
---
{text}
---
Output `builds_on` (NAMED prior techniques this paper advances beyond) as JSON."""

RELATE_SCHEMA = {
    "name": "paper_relations",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "builds_on": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["builds_on"],
        "additionalProperties": False,
    },
}
