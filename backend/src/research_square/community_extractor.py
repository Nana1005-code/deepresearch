from __future__ import annotations

import json
import re
from difflib import SequenceMatcher

from openai import OpenAI

from .store import ResearchSquareStore, normalize_name


PROMPT_VERSION = "community-keywords-v1"
ALLOWED_TYPES = {
    "domain", "task", "method", "modality", "object", "dataset", "metric",
    "constraint", "population", "application", "model", "problem", "topic",
}


def _candidate_score(research_input: str, name: str) -> float:
    source, candidate = normalize_name(research_input), normalize_name(name)
    if not candidate:
        return 0.0
    if candidate in source:
        return 1.0
    return SequenceMatcher(None, candidate, source).ratio()


def find_candidates(store: ResearchSquareStore, research_input: str, limit: int = 30) -> list[dict]:
    """Retrieve likely existing nodes before asking the model to reuse/create."""
    with store.connect() as db:
        community = db.execute("""SELECT t.id,t.canonical_name,
            GROUP_CONCAT(a.alias,'|') aliases FROM topics t LEFT JOIN topic_aliases a ON a.topic_id=t.id
            WHERE t.status='active' GROUP BY t.id""").fetchall()
        academic = db.execute("""SELECT c.id,c.canonical_name_zh,c.canonical_name_en,
            GROUP_CONCAT(a.alias,'|') aliases FROM openalex_canonical_topics c
            LEFT JOIN openalex_canonical_aliases a ON a.canonical_topic_id=c.id
            WHERE c.status='active' GROUP BY c.id""").fetchall()
    ranked: list[tuple[float, dict]] = []
    for row in community:
        names = [row["canonical_name"], *(row["aliases"] or "").split("|")]
        score = max((_candidate_score(research_input, name) for name in names if name), default=0)
        if score >= 0.12:
            ranked.append((score, {"candidate_key": f"community:{row['id']}",
                "name_zh": row["canonical_name"], "name_en": None, "source": "user_graph",
                "similarity": round(score, 3)}))
    for row in academic:
        names = [row["canonical_name_zh"], row["canonical_name_en"], *(row["aliases"] or "").split("|")]
        score = max((_candidate_score(research_input, name) for name in names if name), default=0)
        if score >= 0.12:
            ranked.append((score, {"candidate_key": f"openalex:{row['id']}",
                "name_zh": row["canonical_name_zh"], "name_en": row["canonical_name_en"],
                "source": "openalex", "similarity": round(score, 3)}))
    ranked.sort(key=lambda item: item[0], reverse=True)
    seen: set[str] = set()
    result = []
    for _, item in ranked:
        if item["candidate_key"] in seen:
            continue
        seen.add(item["candidate_key"]); result.append(item)
        if len(result) >= limit:
            break
    return result


def _parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise
        return json.loads(match.group(0))


def extract_keywords(store: ResearchSquareStore, research_input: str, profile: dict) -> list[dict]:
    candidates = find_candidates(store, research_input)
    prompt = f"""你是用户研究题目的关键词规范化器。只输出合法 JSON，不要解释。
目标：从一条完整研究输入中提取 3-8 个可复用研究概念，用于知识图谱。不要把整句话当一个关键词。
概念类型只能是：{', '.join(sorted(ALLOWED_TYPES))}。
优先覆盖：研究领域/对象、核心任务、方法或模型、数据模态、应用场景；不要提取“研究、分析、探讨”等空词。
每个概念必须包含：surface_text（原句证据）、canonical_name_zh（简洁规范中文名）、
concept_type、weight(0-1)、confidence(0-1)、aliases（0-3个别名）、evidence、candidate_key。
candidate_key 只能是下面候选的 candidate_key，或 null。语义等价才复用候选；相关但不等价必须新建。
同一次结果中语义重复的概念必须合并。最多8个。

完整研究输入：{research_input}
已有候选：{json.dumps(candidates, ensure_ascii=False)}

输出格式：
{{"concepts":[{{"surface_text":"多视图学习","canonical_name_zh":"多视图学习","concept_type":"method","weight":0.95,"confidence":0.95,"aliases":["Multi-view Learning"],"evidence":"原句明确出现","candidate_key":null}}]}}
"""
    last_error: Exception | None = None
    payload = None
    with OpenAI(base_url=profile["base_url"], api_key=profile.get("api_key") or "not-required",
                timeout=min(int(profile.get("timeout", 60)), 60), max_retries=0) as client:
        messages = [{"role": "user", "content": prompt}]
        for attempt in range(2):
            response = client.chat.completions.create(
                model=profile["model_id"], messages=messages,
                temperature=0, max_tokens=min(max(int(profile.get("max_tokens", 2048)), 3000), 4000),
            )
            message = response.choices[0].message
            raw = (message.content or getattr(message, "reasoning_content", "") or "").strip()
            try:
                payload = _parse_json(raw)
                break
            except Exception as exc:
                last_error = exc
                messages = [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": raw[:6000]},
                    {"role": "user", "content": "上一个输出不是可解析的JSON。请重新输出完整JSON对象，只输出JSON；每个字段值之间必须有逗号。"},
                ]
    if payload is None:
        raise ValueError(f"模型连续两次没有返回合法 JSON：{last_error}")
    candidate_map = {item["candidate_key"]: item for item in candidates}
    concepts: list[dict] = []
    seen: set[str] = set()
    for raw in payload.get("concepts", [])[:8]:
        key = raw.get("candidate_key")
        candidate = candidate_map.get(key)
        name = (candidate or {}).get("name_zh") or raw.get("canonical_name_zh")
        name = " ".join(str(name or "").split()).strip()[:80]
        normalized = normalize_name(name)
        if not name or not normalized or normalized in seen:
            continue
        seen.add(normalized)
        concept_type = raw.get("concept_type") if raw.get("concept_type") in ALLOWED_TYPES else "topic"
        concept = {
            "canonical_name_zh": name,
            "surface_text": str(raw.get("surface_text") or name)[:80],
            "concept_type": concept_type,
            "weight": max(0.05, min(1.0, float(raw.get("weight") or 0.7))),
            "confidence": max(0.0, min(1.0, float(raw.get("confidence") or 0.7))),
            "aliases": [str(x)[:80] for x in (raw.get("aliases") or [])[:3] if str(x).strip()],
            "evidence": str(raw.get("evidence") or raw.get("surface_text") or name)[:500],
        }
        if key and key.startswith("openalex:"):
            concept["openalex_canonical_id"] = int(key.split(":", 1)[1])
        concepts.append(concept)
    if not concepts:
        raise ValueError("模型没有返回可用关键词")
    return concepts


def extract_and_attach(store: ResearchSquareStore, public_id: str, research_input: str,
                       profile: dict) -> dict:
    concepts = extract_keywords(store, research_input, profile)
    item = store.replace_research_concepts(public_id, concepts)
    return {"item": item, "concepts": concepts, "prompt_version": PROMPT_VERSION}
