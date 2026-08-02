import os
import json
import re
import datetime
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from urllib.parse import urlparse

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

from control_families import detect_controls

try:
    from serpapi import GoogleSearch
except ImportError:
    try:
        from serpapi.google_search import GoogleSearch
    except ImportError:
        GoogleSearch = None

ROOT_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = ROOT_DIR / "data" / "critical_infra_corpus.jsonl"


def _resolve_env_path() -> Optional[Path]:
    candidates = [
        Path.cwd() / ".env",
        Path.cwd() / ".env.local",
        ROOT_DIR / ".env",
        ROOT_DIR / ".env.local",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_environment() -> None:
    env_path = _resolve_env_path()
    if env_path is not None:
        load_dotenv(dotenv_path=env_path, override=False)
    else:
        load_dotenv(override=False)


_load_environment()

EMBED_MODEL_DEFAULT = "text-embedding-3-small"
WEB_SEARCH_RESULTS_DEFAULT = 3
WEB_MIN_CONTENT_CHARS = 160
WEB_CHUNK_SIZE = 2000
WEB_CHUNK_OVERLAP = 200
WEB_MAX_DOC_CHARS = 12000
WEB_METADATA_TEXT_CHARS = 4000


# =========================================================
# ENV
# =========================================================
def _env(name: str, default: Optional[str] = None) -> str:
    v = os.getenv(name, default)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def _env_optional(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


# =========================================================
# UTIL
# =========================================================
def _extract_json_object(text: str) -> str:
    t = (text or "").strip()

    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)

    first = t.find("{")
    last = t.rfind("}")

    if first != -1 and last != -1 and last > first:
        return t[first:last + 1]

    return t


def _as_dict(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj

    return {
        "id": getattr(obj, "id", None),
        "score": getattr(obj, "score", 0.0),
        "metadata": getattr(obj, "metadata", {}) or {},
    }


# =========================================================
# EMBEDDING
# =========================================================
def embed(client: OpenAI, text: str, model: str) -> List[float]:
    return client.embeddings.create(
        model=model,
        input=[text]
    ).data[0].embedding


def embed_texts(client: OpenAI, texts: List[str], model: str) -> List[List[float]]:
    if not texts:
        return []

    resp = client.embeddings.create(
        model=model,
        input=texts,
    )
    return [item.embedding for item in resp.data]


# =========================================================
# QUERY INTENT
# =========================================================
def detect_organization(query: str) -> Optional[str]:
    orgs = {
        "nerc": "NERC",
        "nist": "NIST",
        "cisa": "CISA",
        "ferc": "FERC",
        "doe": "DOE",
    }

    q = query.lower()
    for k, v in orgs.items():
        if k in q:
            return v
    return None


def wants_workflow_output(query: str) -> bool:
    q = query.lower()
    triggers = [
        "recommend", "action plan", "fix", "improve",
        "next steps", "ops", "operations", "draft",
        "write", "proposed", "regulatory text", "regulatory",
        "policy language", "language", "require", "must", "shall"
    ]
    return any(t in q for t in triggers)


def wants_risk_categorization(query: str) -> bool:
    q = query.lower()
    category_terms = ["categorize", "categorise", "category", "categories", "operational technology", "cyber-physical", "cyber physical"]
    risk_terms = ["risk", "threat", "warning", "vulnerability", "attack"]
    explicit_short_categories = bool(re.search(r"\bot\b", q) and re.search(r"\bit\b", q))
    return (any(term in q for term in category_terms) or explicit_short_categories) and any(term in q for term in risk_terms)


def wants_attack_vectors(query: str) -> bool:
    q = query.lower()
    return any(term in q for term in ["attack vector", "attack vectors", "initial access", "common attacks", "most common attack"])


def _clean_excerpt(text: str, max_chars: int = 180) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned
    trimmed = cleaned[: max_chars - 1]
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return trimmed + "..."


def _extract_relevant_sentence(text: str, query: str) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
    if not sentences:
        return ""

    query_terms = [term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) > 3]
    for sentence in sentences:
        lower = sentence.lower()
        if any(term in lower for term in query_terms):
            return _clean_excerpt(sentence, 180)

    return _clean_excerpt(sentences[0], 180)


def _synthesize_local_answer(query: str, evidence: List[str]) -> str:
    combined = " ".join(evidence).lower()
    themes = []
    if any(term in combined for term in ["remote access", "vendor", "third-party", "third party"]):
        themes.append("remote access and third-party pathways into OT environments")
    if any(term in combined for term in ["monitoring", "loss of view", "situational awareness", "detect"]):
        themes.append("limited monitoring and loss of operator visibility")
    if any(term in combined for term in ["incident", "response", "recovery", "resilien"]):
        themes.append("incident response and recovery readiness gaps")
    if any(term in combined for term in ["patch", "unpatched", "vulnerab"]):
        themes.append("unpatched or vulnerable systems")
    if any(term in combined for term in ["it and ot", "it/ot", "connectivity", "segmentation"]):
        themes.append("IT/OT interconnection and segmentation weaknesses")
    if any(term in combined for term in ["cyber-physical", "sensor", "false data", "control signal", "scada", "ics"]):
        themes.append("cyber-physical manipulation of ICS, sensors, or control processes")

    if not themes:
        themes = ["asset visibility, monitoring, incident response, and resilience gaps"]

    if "cisa" in combined or "cisa" in query.lower():
        lead = "Recent CISA-relevant energy-sector risk themes center on"
    elif "nerc" in combined or "nerc" in query.lower():
        lead = "For NERC CIP and energy reliability policy, the strongest risk themes are"
    elif "nist" in combined or "nist" in query.lower():
        lead = "Mapped to NIST-style cyber risk management, the evidence points to"
    else:
        lead = "For U.S. energy-sector critical infrastructure, the strongest cybersecurity risk themes are"

    return f"{lead} {', '.join(themes[:5])}."


def _risk_source(c: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "chunk_id": c.get("chunk_id"),
        "document_title": c.get("document_title"),
        "page_number": c.get("page_number"),
        "source_url": c.get("source_url"),
        "excerpt": _clean_excerpt(c.get("text") or "", 220),
    }


def _is_low_value_context(context: Dict[str, Any]) -> bool:
    text = " ".join([
        context.get("text") or "",
        context.get("document_title") or "",
    ]).lower()
    low_value_markers = [
        "appendix c: acronyms",
        "appendix c acronyms",
        "acronym definition",
        "table of contents",
        "references",
        "bibliography",
    ]
    return any(marker in text for marker in low_value_markers)


def _build_risk_categories(contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    risk_patterns = [
        (
            "Operational Technology (OT)",
            "Remote access and vendor access exposure",
            ["remote access", "vendor", "third-party", "third party"],
            "Compromised remote or vendor pathways can give attackers a route into control environments that were not designed for broad exposure.",
            "Require MFA for remote access, broker access through monitored jump hosts, time-bound vendor sessions, and strict network segmentation."
        ),
        (
            "Operational Technology (OT)",
            "Loss of visibility or control in ICS/SCADA environments",
            ["loss of view", "loss of control", "scada", "ics", "control system", "operator"],
            "Energy operations depend on reliable telemetry and control; degraded visibility can delay safe operational decisions.",
            "Deploy OT-aware monitoring, validate telemetry paths, maintain manual operating procedures, and exercise loss-of-view scenarios."
        ),
        (
            "Operational Technology (OT)",
            "Unpatched legacy OT assets and insecure protocols",
            ["unpatched", "patch", "legacy", "modbus", "iec 61850", "clear text", "clear-text"],
            "Legacy OT systems often have long lifecycles and weak protocol security, increasing exposure to known exploits and traffic manipulation.",
            "Prioritize risk-based patching, compensating controls, protocol allowlisting, and segmented enclaves for systems that cannot be patched quickly."
        ),
        (
            "Information Technology (IT)",
            "Enterprise intrusion enabling OT pivoting",
            ["it and ot", "it/ot", "connectivity", "segmentation", "corporate", "enterprise"],
            "Attackers can use enterprise IT compromise as a staging point to reach OT networks when segmentation and monitoring are weak.",
            "Separate IT and OT trust zones, enforce least privilege, monitor cross-zone traffic, and test incident containment between environments."
        ),
        (
            "Information Technology (IT)",
            "Ransomware, malware, and credential compromise",
            ["ransomware", "malware", "credential", "phishing", "authentication", "password"],
            "Business-network compromise can disrupt scheduling, billing, communications, and recovery coordination even when control systems remain intact.",
            "Harden identity controls, require phishing-resistant MFA for privileged accounts, maintain offline backups, and rehearse ransomware playbooks."
        ),
        (
            "Information Technology (IT)",
            "Weak monitoring, vulnerability management, and incident response",
            ["monitoring", "incident response", "vulnerability", "assessment", "detect", "response"],
            "Delayed detection and unclear response roles increase attacker dwell time and slow restoration of essential energy functions.",
            "Maintain asset inventories, tune detection for energy-sector threats, define response ownership, and run tabletop exercises with operations staff."
        ),
        (
            "Cyber-Physical Systems",
            "False data injection and sensor/telemetry manipulation",
            ["false data", "sensor", "telemetry", "measurement", "data integrity"],
            "Manipulated measurements can mislead automated or human decisions and cause unsafe or inefficient physical operations.",
            "Use data validation, physics-aware anomaly detection, independent measurement checks, and fail-safe control logic."
        ),
        (
            "Cyber-Physical Systems",
            "Cascading failures across interconnected energy systems",
            ["cascading", "interdepend", "cyber-physical", "integrated energy", "microgrid"],
            "Tightly coupled electric, gas, thermal, and communications systems can propagate cyber impacts into physical reliability consequences.",
            "Model cross-domain dependencies, isolate critical control paths, and exercise coordinated restoration across utilities and partners."
        ),
        (
            "Cyber-Physical Systems",
            "Command or control-signal manipulation",
            ["command", "control signal", "control signals", "actuator", "manipulation", "injection"],
            "Unauthorized command changes can affect breakers, generation, load management, or protective devices with direct operational consequences.",
            "Authenticate control commands, monitor command sequences, restrict engineering workstation access, and verify protective relay settings."
        ),
    ]

    categories: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    used_risks = set()
    for category, risk, terms, impact, mitigation in risk_patterns:
        matches = []
        for context in contexts:
            if _is_low_value_context(context):
                continue
            text = " ".join([
                context.get("text") or "",
                context.get("document_title") or "",
                context.get("document_type") or "",
            ]).lower()
            if any(term in text for term in terms):
                matches.append(context)
        if not matches or risk in used_risks:
            continue
        used_risks.add(risk)
        categories[category].append({
            "risk": risk,
            "why_it_matters": impact,
            "mitigation_focus": mitigation,
            "evidence": [m.get("chunk_id") for m in matches[:3] if m.get("chunk_id")],
            "sources": [_risk_source(m) for m in matches[:3]],
        })

    ordered = []
    for category in ["Operational Technology (OT)", "Information Technology (IT)", "Cyber-Physical Systems"]:
        risks = categories.get(category, [])[:3]
        if risks:
            ordered.append({"category": category, "risks": risks})
    return ordered


def _build_attack_vectors(contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    vector_patterns = [
        (
            "Phishing and credential theft",
            ["phishing", "spear-phishing", "credential", "password", "authentication"],
            "Attackers use email, credential harvesting, or weak authentication to obtain access to enterprise accounts that can support later movement toward OT.",
            "Identity systems, VPNs, remote access portals, administrator accounts, engineering workstations.",
            "Use phishing-resistant MFA for privileged and remote access, monitor impossible travel and abnormal logins, and remove shared administrator credentials."
        ),
        (
            "Exploitation of unpatched vulnerabilities",
            ["unpatched", "vulnerability", "vulnerabilities", "exploit", "patch"],
            "Known vulnerabilities in exposed services, enterprise systems, or OT support hosts give attackers reliable entry points.",
            "Internet-facing systems, historians, HMIs, engineering workstations, Windows servers, remote access services.",
            "Maintain asset inventory, prioritize exploited-known-vulnerability remediation, and apply compensating controls where OT patching requires outage windows."
        ),
        (
            "Insecure remote access",
            ["remote access", "vpn", "remote display", "remote attacker", "access vector"],
            "Poorly controlled remote access can bypass physical isolation assumptions and create direct or indirect paths into ICS networks.",
            "VPN gateways, remote desktop services, vendor maintenance connections, jump hosts.",
            "Broker remote sessions through monitored jump hosts, require MFA, disable persistent vendor access, and segment remote access from control networks."
        ),
        (
            "IT-to-OT pivoting",
            ["it and ot", "it/ot", "connectivity", "segmentation", "corporate", "pivot"],
            "Attackers compromise enterprise IT first, then use weak segmentation or trusted connections to approach OT assets.",
            "Corporate networks, shared identity services, firewalls, data historians, OT demilitarized zones.",
            "Enforce one-way or tightly governed conduits, monitor cross-zone traffic, and test containment between IT, OT DMZ, and control zones."
        ),
        (
            "Supply-chain and vendor compromise",
            ["supply chain", "supplier", "vendor", "third-party", "third party"],
            "Compromise of vendors, software updates, or managed service pathways can introduce trusted access into sensitive energy environments.",
            "Vendor remote access, software update channels, managed services, contractor accounts.",
            "Require vendor access approval, software integrity validation, SBOM/procurement controls, and rapid offboarding of third-party credentials."
        ),
        (
            "Malware or ransomware disruption",
            ["malware", "ransomware", "worm", "virus", "encrypt"],
            "Malware can disrupt business operations and, where pathways exist, affect OT support systems or recovery coordination.",
            "Enterprise IT, backup systems, file shares, OT support servers, operator workstations.",
            "Maintain offline backups, isolate recovery infrastructure, block unauthorized executables, and rehearse restoration of critical energy functions."
        ),
        (
            "Protocol manipulation and command injection",
            ["command", "control signal", "injection", "modbus", "iec 61850", "traffic manipulation", "message manipulation"],
            "Attackers who reach control networks may manipulate messages, commands, or protocol traffic that affects physical operations.",
            "SCADA communications, PLCs/RTUs, relays, substations, control-center networks.",
            "Authenticate commands where possible, monitor command sequences, restrict engineering workstation access, and validate protective relay settings."
        ),
        (
            "False data injection and telemetry manipulation",
            ["false data", "telemetry", "sensor", "measurement", "data integrity", "loss of view"],
            "Manipulated telemetry can mislead operators or automated control logic, creating unsafe operating decisions without obvious equipment failure.",
            "Sensors, measurement channels, historians, EMS/SCADA displays, state-estimation inputs.",
            "Use independent measurement validation, physics-aware anomaly detection, and fail-safe procedures for suspected loss-of-view conditions."
        ),
    ]

    vectors = []
    seen = set()
    for name, terms, method, targets, mitigation in vector_patterns:
        matches = []
        for context in contexts:
            if _is_low_value_context(context):
                continue
            text = " ".join([
                context.get("text") or "",
                context.get("document_title") or "",
                context.get("document_type") or "",
            ]).lower()
            if any(term in text for term in terms):
                matches.append(context)
        if not matches or name in seen:
            continue
        seen.add(name)
        vectors.append({
            "vector": name,
            "how_it_is_used": method,
            "typical_targets": targets,
            "mitigation_focus": mitigation,
            "evidence": [m.get("chunk_id") for m in matches[:3] if m.get("chunk_id")],
            "sources": [_risk_source(m) for m in matches[:3]],
        })

    return vectors[:6]


def _summarize_risk_categories(risk_categories: List[Dict[str, Any]]) -> str:
    if not risk_categories:
        return ""

    parts = []
    for category in risk_categories:
        risks = category.get("risks", []) or []
        if not risks:
            continue
        names = [r.get("risk", "") for r in risks[:2] if r.get("risk")]
        if names:
            parts.append(f"{category.get('category')}: {', '.join(names)}")

    if not parts:
        return ""

    return (
        "The top energy-sector cybersecurity risks cluster around "
        + "; ".join(parts)
        + "."
    )


def _summarize_attack_vectors(attack_vectors: List[Dict[str, Any]]) -> str:
    if not attack_vectors:
        return ""
    names = [item.get("vector", "") for item in attack_vectors[:5] if item.get("vector")]
    if not names:
        return ""
    return "The most common energy-sector ICS/OT attack vectors in the retrieved evidence are " + ", ".join(names) + "."


def _build_workflow_draft_text(query: str, evidence: List[str]) -> str:
    base = _synthesize_local_answer(query, evidence)
    if "ferc" in query.lower():
        return (
            "Each covered FERC-regulated operator shall conduct a documented gap assessment that compares its existing cyber controls against the current threat environment, including remote access, third-party access, patching, monitoring, and incident response. Where gaps are identified, the operator shall implement remediation measures, document compensating controls, and report status to the relevant oversight authority within a defined timeframe."
        )
    return (
        f"{base} To close those gaps, each covered operator shall perform a documented control-gap assessment, remediate high-risk weaknesses, and maintain evidence of ongoing monitoring and response readiness."
    )


def _build_local_grounded_response(
    query: str,
    contexts: List[Dict[str, Any]],
    workflow: bool,
    agg: Optional[Dict[str, Any]] = None,
    include_debug: bool = False,
) -> Dict[str, Any]:
    if not contexts:
        result = {
            "answer_summary": "I could not find enough local evidence to answer that question confidently.",
            "key_points": [
                "No relevant corpus chunks were available for this request.",
            ],
            "sources": [],
            "confidence": "Low",
        }
        if include_debug and agg is not None:
            result["debug"] = {"workflow": workflow, "num_contexts": 0, "control_families": agg}
        return result

    top_contexts = contexts[:6]
    risk_categories = _build_risk_categories(contexts)
    attack_vectors = _build_attack_vectors(contexts)
    evidence = []
    for c in top_contexts:
        text = c.get("text") or ""
        sentence = _extract_relevant_sentence(text, query)
        if sentence:
            evidence.append(sentence)
        else:
            evidence.append(_clean_excerpt(text, 180))

    evidence = [e for e in evidence if e]

    attack_summary = _summarize_attack_vectors(attack_vectors)
    category_summary = _summarize_risk_categories(risk_categories)

    if workflow:
        answer_text = attack_summary or category_summary or _synthesize_local_answer(query, evidence[:4])
        draft_text = _build_workflow_draft_text(query, evidence[:4])

        result = {
            "answer_summary": answer_text,
            "key_requirements": [
                {
                    "requirement": draft_text,
                    "evidence": [c.get("chunk_id") for c in top_contexts if c.get("chunk_id")],
                    "confidence": "Medium",
                }
            ],
            "policy_recommendations": [
                {
                    "recommendation": draft_text,
                    "priority": "Med",
                    "owner": "Security and compliance team",
                    "effort": "Low",
                    "evidence": [c.get("chunk_id") for c in top_contexts if c.get("chunk_id")],
                }
            ],
            "draft_policy_language": [draft_text],
            "sources": [_risk_source(c) for c in top_contexts],
            "confidence": "Medium",
            "used_chunk_ids": [c.get("chunk_id") for c in top_contexts if c.get("chunk_id")],
        }
    else:
        answer_text = attack_summary or category_summary or _synthesize_local_answer(query, evidence[:4])

        structured_sources = [
            source
            for item in attack_vectors
            for source in item.get("sources", [])
        ]

        result = {
            "answer_summary": answer_text,
            "key_points": [
                f"{item['vector']}: {item['how_it_is_used']}"
                for item in attack_vectors
            ][:6] or [
                f"{item['risk']}: {item['why_it_matters']}"
                for category in risk_categories
                for item in category.get("risks", [])
            ][:6] or evidence[:6],
            "sources": structured_sources or [
                {
                    "chunk_id": c.get("chunk_id"),
                    "document_title": c.get("document_title"),
                    "page_number": c.get("page_number"),
                    "source_url": c.get("source_url"),
                    "excerpt": _clean_excerpt(c.get("text") or "", 220),
                }
                for c in top_contexts
            ],
            "confidence": "Medium",
            "used_chunk_ids": [c.get("chunk_id") for c in top_contexts if c.get("chunk_id")],
        }

        if risk_categories and (wants_risk_categorization(query) or not attack_vectors):
            result["risk_categories"] = risk_categories
        if attack_vectors:
            result["attack_vectors"] = attack_vectors

    if include_debug and agg is not None:
        result["debug"] = {
            "workflow": workflow,
            "num_contexts": len(contexts),
            "control_families": agg,
        }

    return result


# =========================================================
# RETRIEVAL
# =========================================================
def _read_local_corpus(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    corpus_path = path or DATASET_PATH
    if not corpus_path.exists():
        return []

    items: List[Dict[str, Any]] = []
    with corpus_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _fallback_retrieve(
    query: str,
    top_k: int = 8,
    min_score: float = 0.65,
    exclude_owner_responses: bool = True,
) -> List[Dict[str, Any]]:
    chunks = _read_local_corpus()
    if not chunks:
        return []

    query_tokens = _tokenize(query)
    contexts: List[Dict[str, Any]] = []

    for item in chunks:
        if exclude_owner_responses and item.get("is_owner_response"):
            continue

        text = item.get("text", "")
        combined_text = " ".join([
            text,
            item.get("document_title", ""),
            item.get("organization", ""),
            item.get("topic", ""),
        ])
        tokens = _tokenize(combined_text)
        overlap = len(query_tokens & tokens)
        score = overlap

        if detect_organization(query) and item.get("organization") == detect_organization(query):
            score += 3

        if score <= 0:
            continue

        controls, _ = detect_controls(text)
        contexts.append({
            "id": item.get("chunk_id"),
            "score": float(score),
            "chunk_id": item.get("chunk_id"),
            "source_file": item.get("source_file"),
            "document_title": item.get("document_title"),
            "organization": item.get("organization"),
            "document_type": item.get("document_type"),
            "page_number": item.get("page_number"),
            "text": text,
            "controls": controls,
        })

    contexts = sorted(contexts, key=lambda x: x["score"], reverse=True)[:top_k]
    return contexts


def _chunk_text(
    text: str,
    chunk_size: int = WEB_CHUNK_SIZE,
    overlap: int = WEB_CHUNK_OVERLAP,
) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: List[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    return parsed.netloc.replace("www.", "") or "external"


def _infer_external_org(title: str, url: str) -> str:
    haystack = f"{title} {url}".lower()
    orgs = {
        "nerc": "NERC",
        "nist": "NIST",
        "cisa": "CISA",
        "ferc": "FERC",
        "energy.gov": "DOE",
        "doe": "DOE",
    }
    for marker, org in orgs.items():
        if marker in haystack:
            return org
    return _domain_from_url(url)


def _web_chunk_id(url: str, chunk_index: int, text: str) -> str:
    strategy = os.getenv("PINECONE_ID_STRATEGY", "url").strip().lower()
    if strategy == "content":
        digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
        return f"webc_{digest}"

    digest = hashlib.md5((url or text).encode("utf-8")).hexdigest()[:12]
    return f"web_{digest}_{chunk_index:03d}"


def external_search(query: str, max_results: Optional[int] = None) -> List[Dict[str, str]]:
    if not _env_bool("ENABLE_SERPAPI_SEARCH", True):
        return []

    serpapi_key = _env_optional("SERPAPI_API_KEY", "SERPAPI_KEY")
    if not serpapi_key or GoogleSearch is None:
        return []

    limit = max_results or _env_int("SERPAPI_MAX_RESULTS", WEB_SEARCH_RESULTS_DEFAULT)
    search_query = os.getenv(
        "SERPAPI_QUERY_TEMPLATE",
        "{query} critical infrastructure cybersecurity energy sector",
    ).format(query=query)

    params = {
        "q": search_query,
        "engine": "google",
        "api_key": serpapi_key,
        "num": limit,
        "hl": "en",
        "gl": "us",
    }

    try:
        result = GoogleSearch(params).get_dict()
    except Exception:
        return []

    docs: List[Dict[str, str]] = []
    seen_urls = set()
    for item in result.get("organic_results", [])[:limit]:
        url = item.get("link") or ""
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        docs.append({
            "title": item.get("title") or "External source",
            "url": url,
            "content": item.get("snippet") or "",
        })
    return docs


def fetch_full_text(url: str) -> str:
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        candidates = []
        for selector in ["article", "main", "div#content", "div.content", "div.article", "div.post"]:
            node = soup.select_one(selector)
            if not node:
                continue
            text = "\n".join(
                part.get_text(" ", strip=True)
                for part in node.find_all(["p", "li", "h1", "h2", "h3"])
            )
            if len(text) >= WEB_MIN_CONTENT_CHARS:
                candidates.append(text)

        if candidates:
            return max(candidates, key=len)[:WEB_MAX_DOC_CHARS]

        fallback = "\n".join(p.get_text(" ", strip=True) for p in soup.find_all("p"))
        return fallback[:WEB_MAX_DOC_CHARS]
    except Exception:
        return ""


def _web_docs_to_contexts(docs: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    contexts: List[Dict[str, Any]] = []
    retrieved_at = datetime.date.today().isoformat()

    for doc in docs:
        url = doc.get("url", "")
        title = doc.get("title") or "External source"
        content = (doc.get("content") or "").strip()
        if len(content) < WEB_MIN_CONTENT_CHARS:
            content = f"{title}\n\n{content}".strip()
        if len(content) < WEB_MIN_CONTENT_CHARS:
            continue

        org = _infer_external_org(title, url)
        for idx, chunk in enumerate(_chunk_text(content)):
            controls, _ = detect_controls(chunk)
            chunk_id = _web_chunk_id(url, idx, chunk)
            contexts.append({
                "id": chunk_id,
                "score": 1.0,
                "chunk_id": chunk_id,
                "source_file": url,
                "document_title": title,
                "organization": org,
                "document_type": "Web Search Result",
                "sector": "Energy",
                "page_number": 0,
                "chunk_index": idx,
                "text": chunk,
                "controls": controls,
                "source_url": url,
                "retrieved_at": retrieved_at,
                "is_external": True,
            })

    return contexts


def _pinecone_metadata_from_context(context: Dict[str, Any]) -> Dict[str, Any]:
    metadata = {
        "chunk_id": str(context.get("chunk_id") or context.get("id") or ""),
        "source_file": str(context.get("source_file") or ""),
        "document_title": str(context.get("document_title") or "External source"),
        "organization": str(context.get("organization") or "External"),
        "document_type": str(context.get("document_type") or "Web Search Result"),
        "sector": str(context.get("sector") or "Energy"),
        "page_number": int(context.get("page_number") or 0),
        "chunk_index": int(context.get("chunk_index") or 0),
        "text": str(context.get("text") or "")[:WEB_METADATA_TEXT_CHARS],
        "controls": [str(c) for c in (context.get("controls") or [])],
        "source_url": str(context.get("source_url") or context.get("source_file") or ""),
        "retrieved_at": str(context.get("retrieved_at") or datetime.date.today().isoformat()),
        "is_external": bool(context.get("is_external", True)),
    }
    return metadata


def save_external_contexts_to_pinecone(
    contexts: List[Dict[str, Any]],
    client: OpenAI,
    index: Any,
    namespace: str = "",
) -> int:
    if not contexts:
        return 0

    embed_model = os.getenv("OPENAI_EMBED_MODEL", EMBED_MODEL_DEFAULT)
    texts = [
        f"[ORG] {c.get('organization')}\n[DOC] {c.get('document_title')}\n[TYPE] {c.get('document_type')}\n\n{c.get('text')}"
        for c in contexts
    ]

    try:
        embeddings = embed_texts(client, texts, embed_model)
    except Exception:
        return 0

    vectors = []
    for context, embedding in zip(contexts, embeddings):
        vector_id = str(context.get("id") or context.get("chunk_id"))
        if not vector_id:
            continue
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": _pinecone_metadata_from_context(context),
        })

    upserted_total = 0
    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        try:
            response = index.upsert(vectors=batch, namespace=namespace)
        except Exception:
            continue
        if isinstance(response, dict):
            upserted_total += int(response.get("upserted_count", 0))
        else:
            upserted_total += int(getattr(response, "upserted_count", 0) or 0)

    return upserted_total


def refresh_external_contexts(query: str, client: OpenAI) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    docs = external_search(query)
    for doc in docs:
        full_text = fetch_full_text(doc.get("url", ""))
        if full_text:
            doc["content"] = full_text

    contexts = _web_docs_to_contexts(docs)
    stats: Dict[str, Any] = {
        "serpapi_docs": len(docs),
        "external_chunks": len(contexts),
        "pinecone_upserted": 0,
    }

    if not contexts:
        return contexts, stats

    try:
        pc = Pinecone(api_key=_env("PINECONE_API_KEY"))
        index = pc.Index(_env("PINECONE_INDEX"))
        namespace = os.getenv("PINECONE_NAMESPACE", "")
        stats["pinecone_upserted"] = save_external_contexts_to_pinecone(
            contexts=contexts,
            client=client,
            index=index,
            namespace=namespace,
        )
    except Exception:
        stats["pinecone_upserted"] = 0

    return contexts, stats


def _dedupe_contexts(contexts: List[Dict[str, Any]], limit: Optional[int] = None) -> List[Dict[str, Any]]:
    seen = set()
    deduped = []
    for context in contexts:
        key = context.get("chunk_id") or context.get("id") or context.get("source_url") or context.get("text")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(context)
        if limit and len(deduped) >= limit:
            break
    return deduped


def _retrieval_sources(contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sources = []
    for context in contexts:
        sources.append({
            "chunk_id": context.get("chunk_id"),
            "document_title": context.get("document_title"),
            "source_file": context.get("source_file"),
            "page_number": context.get("page_number"),
            "source_url": context.get("source_url"),
            "document_type": context.get("document_type"),
            "retrieved_at": context.get("retrieved_at"),
            "is_external": bool(context.get("is_external", False)),
        })
    return sources


def _context_index(contexts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {
        str(context.get("chunk_id")): context
        for context in contexts
        if context.get("chunk_id")
    }


def _source_from_context(context: Dict[str, Any], excerpt: Optional[str] = None) -> Dict[str, Any]:
    return {
        "chunk_id": context.get("chunk_id"),
        "document_title": context.get("document_title"),
        "source_file": context.get("source_file"),
        "page_number": context.get("page_number"),
        "source_url": context.get("source_url"),
        "excerpt": _clean_excerpt(excerpt or context.get("text") or "", 220),
    }


def _normalize_source(source: Any, index: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if isinstance(source, str):
        context = index.get(source)
        return _source_from_context(context) if context else None

    if not isinstance(source, dict):
        return None

    chunk_id = source.get("chunk_id")
    if chunk_id in index:
        return _source_from_context(index[chunk_id], source.get("excerpt"))

    source_url = source.get("source_url")
    if source_url:
        for context in index.values():
            if context.get("source_url") == source_url:
                return _source_from_context(context, source.get("excerpt"))

    return None


def _normalize_source_list(sources: Any, index: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    seen = set()
    if not isinstance(sources, list):
        return normalized

    for source in sources:
        item = _normalize_source(source, index)
        if not item:
            continue
        key = item.get("chunk_id") or item.get("source_url") or item.get("document_title")
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized


def _normalize_evidence(evidence: Any, index: Dict[str, Dict[str, Any]]) -> List[str]:
    if not isinstance(evidence, list):
        return []
    normalized = []
    for item in evidence:
        if isinstance(item, str) and item in index:
            normalized.append(item)
        elif isinstance(item, dict) and item.get("chunk_id") in index:
            normalized.append(item["chunk_id"])
    return normalized


def _sanitize_generated_output(out: Dict[str, Any], contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
    index = _context_index(contexts)
    if not index:
        return out

    out["used_chunk_ids"] = _normalize_evidence(out.get("used_chunk_ids", []), index)
    out["sources"] = _normalize_source_list(out.get("sources", []), index)

    for item in out.get("attack_vectors", []) or []:
        if not isinstance(item, dict):
            continue
        item["evidence"] = _normalize_evidence(item.get("evidence", []), index)
        item["sources"] = _normalize_source_list(item.get("sources", []), index)
        if not item["sources"]:
            item["sources"] = [_source_from_context(index[eid]) for eid in item["evidence"] if eid in index]

    for category in out.get("risk_categories", []) or []:
        if not isinstance(category, dict):
            continue
        for risk in category.get("risks", []) or []:
            if not isinstance(risk, dict):
                continue
            risk["evidence"] = _normalize_evidence(risk.get("evidence", []), index)
            risk["sources"] = _normalize_source_list(risk.get("sources", []), index)
            if not risk["sources"]:
                risk["sources"] = [_source_from_context(index[eid]) for eid in risk["evidence"] if eid in index]

    for key in ["key_requirements", "policy_recommendations"]:
        for item in out.get(key, []) or []:
            if isinstance(item, dict):
                item["evidence"] = _normalize_evidence(item.get("evidence", []), index)

    if not out["sources"]:
        candidate_ids = out.get("used_chunk_ids", [])
        if not candidate_ids:
            for item in out.get("attack_vectors", []) or []:
                if isinstance(item, dict):
                    candidate_ids.extend(item.get("evidence", []))
            for category in out.get("risk_categories", []) or []:
                if isinstance(category, dict):
                    for risk in category.get("risks", []) or []:
                        if isinstance(risk, dict):
                            candidate_ids.extend(risk.get("evidence", []))
        out["sources"] = [_source_from_context(index[eid]) for eid in candidate_ids[:8] if eid in index]

    if not out["sources"]:
        out["sources"] = [_source_from_context(context) for context in contexts[:6]]

    return out


def retrieve(
    query: str,
    top_k: int = 8,
    min_score: float = 0.65,
    exclude_owner_responses: bool = True,
) -> List[Dict[str, Any]]:
    try:
        client = OpenAI(api_key=_env("OPENAI_API_KEY"))
        pc = Pinecone(api_key=_env("PINECONE_API_KEY"))
        index = pc.Index(_env("PINECONE_INDEX"))

        qvec = embed(client, query, os.getenv("OPENAI_EMBED_MODEL", EMBED_MODEL_DEFAULT))

        filt = {}

        org = detect_organization(query)
        if org:
            filt["organization"] = {"$eq": org}

        if exclude_owner_responses:
            filt["is_owner_response"] = {"$ne": True}

        res = index.query(
            vector=qvec,
            top_k=top_k,
            include_metadata=True,
            include_values=False,
            filter=filt if filt else None,
            namespace=os.getenv("PINECONE_NAMESPACE", ""),
        )

        matches = getattr(res, "matches", []) or []

        contexts = []

        for m in matches:
            md = _as_dict(m)
            meta = md.get("metadata", {}) or {}

            score = float(md.get("score", 0.0))
            if score < min_score:
                continue

            text = meta.get("text", "")

            controls, _ = detect_controls(text)

            contexts.append({
                "id": md.get("id"),
                "score": score,
                "chunk_id": meta.get("chunk_id"),
                "source_file": meta.get("source_file"),
                "document_title": meta.get("document_title"),
                "organization": meta.get("organization"),
                "document_type": meta.get("document_type"),
                "page_number": meta.get("page_number"),
                "text": text,
                "controls": controls,
                "source_url": meta.get("source_url"),
                "retrieved_at": meta.get("retrieved_at"),
                "is_external": bool(meta.get("is_external", False)),
            })

        seen = set()
        deduped = []

        for c in sorted(contexts, key=lambda x: x["score"], reverse=True):
            if c["chunk_id"] in seen:
                continue
            seen.add(c["chunk_id"])
            deduped.append(c)

        return deduped
    except Exception:
        return _fallback_retrieve(
            query=query,
            top_k=top_k,
            min_score=min_score,
            exclude_owner_responses=exclude_owner_responses,
        )


# =========================================================
# AGGREGATION
# =========================================================
def aggregate_contexts(contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
    controls = defaultdict(int)

    for c in contexts:
        for ctrl in c.get("controls", []) or []:
            controls[ctrl] += 1

    return {
        "control_families": sorted(
            [{"control": k, "count": v} for k, v in controls.items()],
            key=lambda x: x["count"],
            reverse=True,
        )
    }


# =========================================================
# PROMPT
# =========================================================
def build_prompt(query, contexts, agg, workflow):

    ctx = []
    for c in contexts:
        txt = (c.get("text") or "")[:800]
        source_url = c.get("source_url") or ""
        retrieved_at = c.get("retrieved_at") or ""

        ctx.append(f"""
[chunk_id] {c.get("chunk_id")}
[org] {c.get("organization")}
[title] {c.get("document_title")}
[type] {c.get("document_type")}
[page] {c.get("page_number")}
[source_url] {source_url}
[retrieved_at] {retrieved_at}
[controls] {c.get("controls")}

{txt}
""")

    system = """
You are an expert Energy Sector Cybersecurity Risk Mitigation Assistant specializing in U.S. critical infrastructure cybersecurity policy development. You help security leaders, regulators, and utility operators translate evidence from NERC CIP, CISA, DOE, NIST, FERC, OT/ICS security literature, and current web sources into concrete policy analysis.

Your job is to answer the user's question using ONLY the CONTEXT provided in the "CONTEXT" section. Do NOT hallucinate, invent requirements, or add facts not present in the provided context.

Hard rules:
- Use ONLY provided context. If the answer cannot be supported entirely by the provided context, respond with a clear INSUFFICIENT_CONTEXT marker: {"INSUFFICIENT_CONTEXT": true, "clarifying_question": "<one short question to ask the user>"} (when JSON output is required) or a short clarifying question otherwise.
- Every factual claim, requirement, recommendation, or quote must cite at least one chunk_id from the CONTEXT. Use the exact chunk_id values.
- Do not invent source IDs or document names. Values like "CISA-ICS-2023", "DOE-C2M2-2022", or "NIST-SP-800-82r3" are invalid unless they appear exactly as chunk_id values in CONTEXT.
- When you include a citation, include the source_url when available, plus document_title, page_number (if available), chunk_id, and a one-sentence excerpt (<= 40 words) from the cited context that supports the claim.
- When asked for recommendations or an action plan, return prioritized, actionable steps with an estimated effort level (Low/Med/High), the role(s) that should own the step, and the minimal evidence (chunk_id list) supporting each step.
- When asked for policy or draft language, produce the draft text and then list the exact supporting chunk_ids and short justification lines tying each clause to the cited chunks.
- NEVER reveal chain-of-thought. You may provide a brief, concise rationale for your answer (1–3 sentences) that cites the supporting chunk_ids, but do not reveal internal deliberations.
- If asked to return JSON, return valid JSON only (no extraneous commentary). If asked for free text, structure your response in sections: Summary, Evidence (with chunk_ids), Recommendations, and Appendix (optional).
- Output a "confidence" field (Low/Medium/High) when returning recommendations or requirements, based solely on how many independent supporting chunks (distinct chunk_ids) support the assertion.

Quality rules:
- Never answer with generic phrases such as "regulatory expectations assume strong compliance discipline" unless that is directly relevant to the user's question.
- Do not paste raw document excerpts as key points. Convert evidence into concise policy/risk findings.
- Prefer named, concrete risks: remote access exposure, IT/OT pivoting, ransomware, insecure legacy protocols, loss of view/control, false data injection, supply-chain/vendor exposure, weak monitoring, delayed patching, and cyber-physical cascading impacts.
- For current-warning questions, identify the warning/advisory theme, affected energy-sector relevance, operational impact, and mitigation implication.
- For attack-vector questions, identify how the vector is used against ICS/OT, typical targets, and mitigation focus. Do not return a generic list without operational detail.
- For categorization questions, group findings by the user's categories and make each category actionable.
- Use crisp professional language. Avoid filler, vague nouns, and repeated wording.

Formatting rules:
- If workflow output is requested (the user requested "recommend", "action plan", "next steps", etc.), produce JSON with:
  {
    "answer_summary": "<concise summary>",
    "key_requirements": [{"requirement": "...", "evidence": ["chunk_id", ...], "confidence": "Low|Medium|High"}],
    "policy_recommendations": [{"recommendation": "...", "priority": "High|Med|Low", "owner": "...", "effort": "Low|Med|High", "evidence": ["chunk_id", ...]}],
    "draft_policy_language": ["<policy paragraph 1>", ...],
    "sources": [{"chunk_id":"...", "document_title":"...", "page_number":..., "source_url":"...", "excerpt":"..."}]
  }
- If workflow output is not requested, produce JSON with:
  {
    "answer_summary": "<concise summary>",
    "key_points": ["..."],
    "attack_vectors": [{"vector":"...", "how_it_is_used":"...", "typical_targets":"...", "mitigation_focus":"...", "evidence":["chunk_id"], "sources":[{"chunk_id":"...", "document_title":"...", "page_number":..., "source_url":"...", "excerpt":"..."}]}],
    "risk_categories": [{"category":"Operational Technology (OT)|Information Technology (IT)|Cyber-Physical Systems|Other", "risks":[{"risk":"...", "why_it_matters":"...", "mitigation_focus":"...", "evidence":["chunk_id"], "sources":[{"chunk_id":"...", "document_title":"...", "page_number":..., "source_url":"...", "excerpt":"..."}]}]}],
    "sources": [{"chunk_id":"...", "document_title":"...", "page_number":..., "source_url":"...", "excerpt":"..."}]
  }
- Always include a top-level "used_chunk_ids" array listing chunk_ids referenced in the response and a "confidence" field for the overall answer.
- Keep each excerpt <= 40 words and escape newline characters inside JSON strings.

Practical guidance:
- Prefer the most recent, highest-scoring chunks when multiple chunks support the same claim; cite at least two independent chunks for High confidence.
- When recommending fixes, provide short, actionable steps (max 8 steps), estimate effort, and map them to a control family when possible.
- If the user's request is ambiguous or missing scope (e.g., which organization, timeframe, or system), ask a single focused clarifying question before answering.
- If the context contains conflicts, identify the conflict and cite the conflicting chunk_ids.

Tone and audience:
- Use precise, professional language suitable for security teams and compliance officers.
- Provide plain-language summaries (1–2 sentences) for non-technical stakeholders, and a technical appendix for engineers when relevant.

Error handling:
- If your output cannot be expressed as valid JSON (when JSON is requested), return:
  {"error":"INVALID_JSON_OUTPUT", "raw": "<first 2000 chars of the raw generation>"}
- If no context chunks are provided, respond with:
  {"INSUFFICIENT_CONTEXT": true, "clarifying_question":"Please provide relevant documents or clarify scope."}

Follow these rules exactly. Responses that ignore these constraints should be avoided.
"""

    if workflow:
        schema = """
Return JSON:
{
  "answer_summary": "",
  "key_requirements": [],
  "policy_recommendations": [],
  "draft_policy_language": [],
  "sources": [{"chunk_id":"", "document_title":"", "page_number":0, "source_url":"", "excerpt":""}]
}
"""
    else:
        schema = """
Return JSON:
{
  "answer_summary": "",
  "key_points": [],
  "attack_vectors": [{"vector":"", "how_it_is_used":"", "typical_targets":"", "mitigation_focus":"", "evidence":[], "sources":[{"chunk_id":"", "document_title":"", "page_number":0, "source_url":"", "excerpt":""}]}],
  "risk_categories": [{"category":"", "risks":[{"risk":"", "why_it_matters":"", "mitigation_focus":"", "evidence":[], "sources":[{"chunk_id":"", "document_title":"", "page_number":0, "source_url":"", "excerpt":""}]}]}],
  "sources": [{"chunk_id":"", "document_title":"", "page_number":0, "source_url":"", "excerpt":""}]
}
"""

    user = f"""
QUESTION:
{query}

CONTROL SIGNALS:
{json.dumps(agg, indent=2)}

CONTEXT:
{chr(10).join(ctx)}

{schema}
"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# =========================================================
# MAIN
# =========================================================
def generate_grounded_response(
    query: str,
    top_k: int = 8,
    min_recurring_reviews: int = 2,
    include_debug: bool = False,
):

    workflow = wants_workflow_output(query)

    contexts = retrieve(query, top_k=top_k)

    try:
        client = OpenAI(api_key=_env("OPENAI_API_KEY"))
    except RuntimeError:
        agg = aggregate_contexts(contexts)
        out = _build_local_grounded_response(
            query=query,
            contexts=contexts,
            workflow=workflow,
            agg=agg,
            include_debug=include_debug,
        )
        out = _sanitize_generated_output(out, contexts)
        out["retrieval_sources"] = _retrieval_sources(contexts)
        return out

    external_contexts, external_stats = refresh_external_contexts(query, client)
    combined_limit = max(top_k + len(external_contexts), top_k)
    contexts = _dedupe_contexts(contexts + external_contexts, limit=combined_limit)
    agg = aggregate_contexts(contexts)

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    messages = build_prompt(query, contexts, agg, workflow)

    generation_error = None
    try:
        try:
            resp = client.responses.create(
                model=model,
                input=messages,
                text={"format": {"type": "json_object"}},
                temperature=0,
            )
            raw = resp.output_text.strip()
        except Exception as responses_exc:
            generation_error = f"responses_api: {responses_exc}"
            chat_resp = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            )
            raw = (chat_resp.choices[0].message.content or "").strip()

        cleaned = _extract_json_object(raw)
        out = json.loads(cleaned)
    except Exception as exc:
        generation_error = f"{generation_error}; fallback: {exc}" if generation_error else str(exc)
        out = _build_local_grounded_response(
            query=query,
            contexts=contexts,
            workflow=workflow,
            agg=agg,
            include_debug=include_debug,
        )

    if include_debug and "debug" not in out:
        out["debug"] = {
            "workflow": workflow,
            "num_contexts": len(contexts),
            "control_families": agg,
            "external_search": external_stats,
        }
        if generation_error:
            out["debug"]["generation_error"] = generation_error
    elif include_debug:
        out["debug"]["external_search"] = external_stats
        if generation_error:
            out["debug"]["generation_error"] = generation_error

    if wants_attack_vectors(query) and not out.get("attack_vectors"):
        attack_vectors = _build_attack_vectors(contexts)
        if attack_vectors:
            out["attack_vectors"] = attack_vectors
            out["answer_summary"] = out.get("answer_summary") or _summarize_attack_vectors(attack_vectors)
            out["key_points"] = [
                f"{item['vector']}: {item['how_it_is_used']}"
                for item in attack_vectors
            ][:6]

    if wants_risk_categorization(query) and not out.get("risk_categories"):
        risk_categories = _build_risk_categories(contexts)
        if risk_categories:
            out["risk_categories"] = risk_categories
            out["key_points"] = [
                f"{risk['risk']}: {risk['why_it_matters']}"
                for category in risk_categories
                for risk in category.get("risks", [])
            ][:6]

    if wants_attack_vectors(query) and not wants_risk_categorization(query):
        out.pop("risk_categories", None)

    out = _sanitize_generated_output(out, contexts)
    out["retrieval_sources"] = _retrieval_sources(contexts)

    return out
