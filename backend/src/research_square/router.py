from __future__ import annotations

import json
import re

from fastapi import APIRouter, HTTPException, Query
from openai import OpenAI

from .schemas import ActorInput, ChatInput, PinInput, PublishResearchInput, QueryPlan
from .store import ResearchSquareStore
from .gap_conversations import router as gap_conversation_router
from .node_search import router as node_search_router, integrated_graph
from .concept_views import router as concept_views_router
from .topic_descriptions import ensure_description


def _latest_report(existing_store, run_id: str) -> str:
    events = existing_store.events(run_id, 0)
    reports = [x["event"].get("report", "") for x in events if x["event"].get("type") == "final_report"]
    return reports[-1] if reports else ""


def _plain_summary(text: str, fallback: str) -> str:
    cleaned = re.sub(r"[#>*_`\[\]()~-]+", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned[:800] or fallback)[:800]


TOPIC_INTENTS = {"topic_trend", "compare_topics", "related_topics"}
VALID_DOMAINS = {"general", "ai", "database", "medicine", "education", "finance", "security", "robotics"}


def _fallback_plan(question: str, days: int, domain_slug: str | None,
                   recognized_topics: list[str] | None = None) -> QueryPlan:
    intent = "rank_topics"
    if any(x in question for x in ("比较", "相比", "对比", "区别")): intent = "compare_topics"
    elif any(x in question for x in ("相关", "关联", "关系最密切")): intent = "related_topics"
    elif any(x in question for x in ("趋势", "变化", "走势")): intent = "topic_trend"
    elif any(x in question for x in ("公开研究", "研究记录", "研究文章", "有哪些研究")): intent = "list_researches"
    elif any(x in question for x in ("概括", "概览", "整体情况", "总结")): intent = "domain_summary"
    metric = "growth" if any(x in question for x in ("增长", "升温", "上升")) else "heat"
    if "浏览" in question: metric = "views"
    elif "点赞" in question: metric = "likes"
    elif "研究数量" in question or "研究最多" in question: metric = "research_count"
    found_days = re.search(r"(\d+)\s*天", question)
    if found_days: days = min(365, max(1, int(found_days.group(1))))
    found_limit = re.search(r"(?:前|最多|列出)\s*(\d+)\s*(?:个|条)?", question)
    limit = min(30, max(1, int(found_limit.group(1)))) if found_limit else 10
    if not domain_slug:
        for label, slug in {"数据库":"database","人工智能":"ai","AI":"ai","医学":"medicine",
                            "教育":"education","金融":"finance","安全":"security","机器人":"robotics"}.items():
            if label in question: domain_slug = slug; break
    quoted = re.findall(r"[“\"']([^”\"']{1,80})[”\"']", question)
    topics = (recognized_topics or quoted)[:5]
    return QueryPlan(intent=intent, metric=metric, days=days, domain_slug=domain_slug, limit=limit, topics=topics)


def _llm_plan(question: str, profile: dict, default: QueryPlan,
              recognized_topics: list[str]) -> QueryPlan:
    prompt = f"""你是研究热点查询规划器。只输出一个 JSON 对象，不输出解释，不输出 SQL。
字段约束：
- intent 只能是 rank_topics, topic_trend, compare_topics, related_topics, list_researches, domain_summary
- metric 只能是 heat, growth, research_count, views, likes
- domain_slug 只能是 general, ai, database, medicine, education, finance, security, robotics 或 null
- days 为 1-365，limit 为 1-30
- topics 只能填写用户明确提到的主题；related_topics/topic_trend 至少一个，compare_topics 至少两个
- 后端词表已匹配出的主题优先使用，不要改写：{json.dumps(recognized_topics, ensure_ascii=False)}

示例：
问题：最近30天数据库领域最热门的前10个主题是什么？
输出：{{"intent":"rank_topics","metric":"heat","days":30,"limit":10,"domain_slug":"database","topics":[]}}

问题：医学影像性能优化与哪些研究主题关系最密切？
输出：{{"intent":"related_topics","metric":"heat","days":30,"limit":10,"domain_slug":"medicine","topics":["医学影像性能优化"]}}

问题：RAG近90天的热度趋势怎样？
输出：{{"intent":"topic_trend","metric":"heat","days":90,"limit":10,"domain_slug":null,"topics":["RAG"]}}

问题：比较“RAG”和“知识图谱”近90天的热度变化
输出：{{"intent":"compare_topics","metric":"heat","days":90,"limit":10,"domain_slug":null,"topics":["RAG","知识图谱"]}}

问题：数据库领域最近有哪些公开研究记录？
输出：{{"intent":"list_researches","metric":"heat","days":30,"limit":10,"domain_slug":"database","topics":[]}}

问题：概括近30天金融领域的研究热点
输出：{{"intent":"domain_summary","metric":"heat","days":30,"limit":10,"domain_slug":"finance","topics":[]}}

现在处理：{question}"""
    try:
        with OpenAI(base_url=profile["base_url"], api_key=profile.get("api_key") or "not-required", timeout=min(profile.get("timeout", 60), 30), max_retries=0) as client:
            response = client.chat.completions.create(model=profile["model_id"], messages=[{"role":"user","content":prompt}], max_tokens=500, temperature=0)
        raw = (response.choices[0].message.content or "").strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.I).strip()
        values = json.loads(raw)
        values.setdefault("days", default.days); values.setdefault("limit", default.limit)
        values.setdefault("domain_slug", default.domain_slug)
        return QueryPlan.model_validate(values)
    except Exception:
        return default


def _repair_plan(plan: QueryPlan, default: QueryPlan,
                 recognized_topics: list[str]) -> QueryPlan:
    """Enforce deterministic entities and explicit keyword intent after LLM planning."""
    updates = {}
    if plan.domain_slug not in VALID_DOMAINS | {None}:
        updates["domain_slug"] = default.domain_slug
    elif default.domain_slug is not None:
        updates["domain_slug"] = default.domain_slug
    if default.intent in TOPIC_INTENTS and recognized_topics:
        updates["intent"] = default.intent
        updates["topics"] = recognized_topics[:5]
    elif plan.intent in TOPIC_INTENTS:
        topics = recognized_topics or plan.topics or default.topics
        updates["topics"] = topics[:5]
        if plan.intent == "compare_topics" and len(topics) < 2 and len(default.topics) >= 2:
            updates["topics"] = default.topics[:5]
    return plan.model_copy(update=updates)


def _deterministic_answer(plan: QueryPlan, data: dict) -> str:
    if data.get("error"):
        return data.get("message") or "查询条件不完整，请写出具体研究主题后重试。"
    if data.get("topics"):
        lines = [f"统计范围：最近 {plan.days} 天。"]
        for index, item in enumerate(data["topics"][:plan.limit], 1):
            noun = "真实论文" if data.get("source") == "openalex" else "公开研究"
            lines.append(f"{index}. {item['name']}：{noun} {item['research_count']} 条。")
        return "\n".join(lines)
    if data.get("trend_summaries") is not None:
        if not data["trend_summaries"]: return "没有找到指定主题的趋势数据。"
        lines = [f"统计范围：最近 {plan.days} 天，按滚动周期分段比较。"]
        metric_name = "论文数" if data.get("source") == "openalex" else "热度"
        count_name = "发表论文" if data.get("source") == "openalex" else "新增研究"
        direction_text = {"up":"上升","down":"下降","stable":"基本稳定"}
        for name, summary in data["trend_summaries"].items():
            lines.append(f"\n{name}：")
            for period in summary["periods"]:
                change = ""
                if period["change_pct"] is not None:
                    sign = "+" if period["change_pct"] >= 0 else ""
                    change = f"，环比 {sign}{period['change_pct']:.1f}%"
                lines.append(f"- {period['start']} 至 {period['end']}：{metric_name} {period['heat']:.1f}，{count_name} {period['new_research_count']} 条{change}")
            lines.append(f"结论：最近一个周期相对前一周期{direction_text.get(summary['direction'],'基本稳定')}。")
        return "\n".join(lines)
    if data.get("series") is not None:
        return "没有找到可比较的趋势分段数据。"
    if data.get("related") is not None:
        return "关联主题：\n" + "\n".join(f"- {x['name']}（关联度 {x['relation_score']:.2f}）" for x in data["related"][:plan.limit])
    if data.get("items") is not None:
        if data.get("source") == "openalex":
            return "真实论文：\n" + "\n".join(f"- {x['title']}（引用 {x['cited_by_count']}）" for x in data["items"][:plan.limit])
        return "公开研究：\n" + "\n".join(f"- {x['title']}（热度 {x['heat_score']:.1f}）" for x in data["items"][:plan.limit])
    return "当前筛选条件下没有足够数据。"


def _llm_answer(question: str, plan: QueryPlan, data: dict, profile: dict | None) -> str:
    fallback = _deterministic_answer(plan, data)
    if not profile or data.get("error"): return fallback
    source_note = "OpenAlex 真实论文元数据" if data.get("source") == "openalex" else "用户公开研究与模拟数据"
    prompt = f"""你是研究热点分析助手。只能依据下面经过后端验证的统计结果回答，不得编造。
当前数据源：{source_note}。OpenAlex 模式下 heat 表示论文数量，不是浏览、点赞或用户热度。
说明统计周期和筛选条件；数据不足要明确说。不要输出 SQL。
如果是趋势或对比问题，必须逐段列出热度、新增研究数和环比百分比，并给出上升、下降或稳定结论，不能只报告累计值。
用户问题：{question}\n查询计划：{plan.model_dump_json()}
统计结果：{json.dumps(data, ensure_ascii=False)[:16000]}"""
    try:
        with OpenAI(base_url=profile["base_url"], api_key=profile.get("api_key") or "not-required", timeout=min(profile.get("timeout", 60), 45), max_retries=0) as client:
            response = client.chat.completions.create(model=profile["model_id"], messages=[{"role":"user","content":prompt}], max_tokens=min(profile.get("max_tokens", 2048), 2048))
        return (response.choices[0].message.content or "").strip() or fallback
    except Exception:
        return fallback


def _gap_answer(question: str, data: dict, profile: dict | None) -> str:
    if data.get("error"):
        return data.get("message", "没有识别到要分析的主题。")
    suggestions = data.get("suggestions", [])
    if not suggestions:
        return "真实学术图谱中暂时没有找到足够的关联主题。"
    fallback = "从我的研究历史来看，建议补充了解：\n" + "\n".join(
        f"{index}. {item['name']}：与目标主题共同出现在 {item['cooccurrence_count']} 篇已导入论文中；"
        f"我的相关研究记录 {item['my_research_count']} 条。"
        for index, item in enumerate(suggestions, 1))
    if not profile:
        return fallback
    prompt = f"""你是个人研究记忆助手。只能依据后端从本地 OpenAlex 真实学术图谱和本机研究历史得到的数据回答。
任务：指出与用户目标主题学术关联较强、但用户从未研究或关注较少的主题，帮助发现知识盲区。
必须说明每个推荐主题为什么相关，并明确“我的研究记录数”；不要声称访问了互联网，不要编造论文或统计。
优先推荐 my_research_count=0 的主题，最多返回10项，最后给出建议的了解顺序。
用户问题：{question}
统计数据：{json.dumps(data, ensure_ascii=False)[:16000]}"""
    try:
        with OpenAI(base_url=profile["base_url"], api_key=profile.get("api_key") or "not-required",
                    timeout=min(profile.get("timeout", 60), 45), max_retries=0) as client:
            response = client.chat.completions.create(model=profile["model_id"],
                messages=[{"role": "user", "content": prompt}], max_tokens=1800, temperature=0)
        return (response.choices[0].message.content or "").strip() or fallback
    except Exception:
        return fallback


def router(existing_store, square_store: ResearchSquareStore, import_queue=None):
    api = APIRouter(prefix="/research-square", tags=["research-square"])

    @api.get("/domains")
    def domains(): return square_store.domains()

    @api.get("/overview")
    def overview(days: int = Query(30, ge=1, le=365), domain: str | None = None):
        return square_store.overview(days, domain)

    @api.get("/openalex/overview")
    def openalex_overview(days: int = Query(365, ge=1, le=3650), domain: str | None = None):
        return square_store.openalex_overview(days, domain)

    @api.get("/openalex/work-suggestions")
    def work_suggestions(q: str = Query("", max_length=200)):
        from .paper_search import suggestions
        return suggestions(square_store, q)

    @api.get("/openalex/works")
    def openalex_works(q: str = "", domain: str | None = None, sort: str = "latest",
                       limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        return square_store.list_openalex_works(query=q, domain_slug=domain, sort=sort, limit=limit, offset=offset)

    @api.get("/openalex/enrichment-status")
    def openalex_enrichment_status():
        return square_store.openalex_enrichment_status()

    @api.get("/openalex/topics/{public_id}")
    def openalex_topic_detail(public_id: str, limit: int = Query(100, ge=1, le=100), q: str = "", sort: str = "citations", offset: int = Query(0, ge=0)):
        try:
            return square_store.openalex_topic_detail(public_id, limit, query=q, sort=sort, offset=offset)
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @api.get("/openalex/graph")
    def openalex_graph(days: int = Query(30, ge=1, le=365), domain: str | None = None,
                       limit: int = Query(40, ge=5, le=100),
                       max_edges_per_node: int = Query(3, ge=1, le=10)):
        return integrated_graph(square_store, days, domain, limit, max_edges_per_node)

    @api.get("/researches")
    def researches(q: str = "", domain: str | None = None, sort: str = "heat",
                   limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                   viewer: str | None = None):
        return square_store.list_researches(query=q, domain_slug=domain, sort=sort, limit=limit, offset=offset, viewer_public_id=viewer)

    @api.get("/researches/{public_id}")
    def research(public_id: str):
        try: return square_store.get_research(public_id)
        except KeyError as exc: raise HTTPException(404, str(exc))
        except PermissionError as exc: raise HTTPException(403, str(exc))

    @api.get("/community/topics/{public_id}")
    def community_topic_detail(public_id: str, limit: int = Query(100, ge=1, le=100)):
        try:
            return ensure_description(square_store, existing_store, square_store.community_topic_detail(public_id, limit))
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @api.post("/publish", status_code=202)
    def publish(payload: PublishResearchInput):
        try: run = existing_store.run(payload.source_run_id)
        except KeyError as exc: raise HTTPException(404, "本地研究记录不存在") from exc
        if run.get("status") not in ("completed", "partial"):
            raise HTTPException(409, "只有已结束且有结果的研究可以导入")
        report = _latest_report(existing_store, payload.source_run_id)
        if not report: raise HTTPException(409, "研究尚未生成最终报告")
        restored = square_store.restore_hidden_import(payload.source_run_id)
        if restored:
            return {"ok": True, "restored": True, "research": restored,
                    "message": "已重新导入到我的研究图谱"}
        if not import_queue:
            raise HTTPException(503, "本地导入队列尚未启动")
        try:
            job = square_store.enqueue_import(payload.source_run_id, payload.model_profile_id, max_queued=10)
        except OverflowError as exc:
            raise HTTPException(429, str(exc)) from exc
        if job.get("already_exists"):
            if job.get("status") == "completed":
                raise HTTPException(409, "该研究已经导入到我的研究图谱，无需重复导入")
            raise HTTPException(409, "该研究正在后台导入，请勿重复操作")
        import_queue.notify()
        message = "上次导入失败，已重新加入后台队列" if job.get("retried") else "已加入后台导入队列"
        return {"ok": True, "job": job, "message": message}

    @api.get("/import-queue")
    def import_queue_status():
        return square_store.import_queue_status()

    @api.get("/import-status/{source_run_id}")
    def import_status(source_run_id: str):
        return square_store.import_status(source_run_id)

    @api.delete("/researches/{public_id}/publication")
    def unpublish(public_id: str, owner: str = "local-user"):
        try: square_store.unpublish(public_id, owner)
        except KeyError as exc: raise HTTPException(404, str(exc))
        except PermissionError as exc: raise HTTPException(403, str(exc))
        return {"ok": True}

    @api.delete("/researches/{public_id}/import")
    def remove_import(public_id: str):
        try: square_store.remove_import(public_id)
        except KeyError as exc: raise HTTPException(404, str(exc))
        return {"ok": True}

    @api.post("/researches/{public_id}/pin")
    def pin_import(public_id: str, payload: PinInput):
        try: return square_store.set_pinned(public_id, payload.pinned)
        except KeyError as exc: raise HTTPException(404, str(exc))

    @api.post("/researches/{public_id}/{action}")
    def action(public_id: str, action: str, payload: ActorInput):
        try: return square_store.record_action(public_id, payload.user_public_id, action, payload.event_id)
        except KeyError as exc: raise HTTPException(404, str(exc))
        except PermissionError as exc: raise HTTPException(403, str(exc))
        except ValueError as exc: raise HTTPException(422, str(exc))

    @api.get("/graph")
    def graph(days: int = Query(30, ge=1, le=365), domain: str | None = None,
              limit: int = Query(40, ge=5, le=100),
              max_edges_per_node: int = Query(3, ge=1, le=10)):
        return square_store.graph(days, domain, limit, max_edges_per_node)

    @api.post("/chat")
    def chat(payload: ChatInput):
        profile = None
        if payload.model_profile_id:
            try: profile = existing_store.profile(payload.model_profile_id)
            except KeyError: profile = None
        if payload.data_source == "local":
            data = square_store.research_gap_candidates(payload.question, 10)
            return {"plan": {"intent": "find_research_gaps", "source": "openalex_and_my_history"},
                    "matched_topics": data.get("matched_topics", []), "data": data,
                    "answer": _gap_answer(payload.question, data, profile)}
        recognized_topics = (square_store.resolve_openalex_topic_mentions(payload.question)
                             if payload.data_source == "openalex"
                             else square_store.resolve_topic_mentions(payload.question))
        default = _fallback_plan(payload.question, payload.days, payload.domain_slug, recognized_topics)
        plan = _llm_plan(payload.question, profile, default, recognized_topics) if profile else default
        plan = _repair_plan(plan, default, recognized_topics)
        data = (square_store.query_openalex_plan_data(plan) if payload.data_source == "openalex"
                else square_store.query_plan_data(plan))
        return {"plan": plan.model_dump(), "matched_topics": recognized_topics,
                "data": data, "answer": _llm_answer(payload.question, plan, data, profile)}

    api.include_router(gap_conversation_router(square_store, chat))
    api.include_router(gap_conversation_router(square_store, chat, "openalex"))
    api.include_router(node_search_router(square_store))
    api.include_router(concept_views_router(square_store))

    @api.post("/admin/rebuild")
    def rebuild():
        square_store.rebuild_analytics(); return {"ok": True}

    return api
