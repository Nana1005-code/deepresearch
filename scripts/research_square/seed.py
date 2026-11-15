"""Generate reproducible synthetic Research Square data.

Examples:
  python scripts/research_square/seed.py --preset small --reset
  python scripts/research_square/seed.py --preset medium --reset

Every generated title is prefixed with [模拟], so synthetic data cannot be
mistaken for real public research.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from research_square.store import ResearchSquareStore, normalize_name  # noqa: E402


PRESETS = {
    "small": dict(users=200, researches=1_000, topics=120, events=10_000),
    "medium": dict(users=2_000, researches=30_000, topics=500, events=300_000),
    "large": dict(users=10_000, researches=100_000, topics=1_000, events=2_000_000),
}
DOMAIN_TOPICS = {
    "ai": ["多模态大模型", "大语言模型", "RAG", "智能体", "机器学习", "视觉语言模型", "生成式AI", "模型评测", "提示工程", "联邦学习"],
    "database": ["向量数据库", "知识图谱", "图数据库", "分布式数据库", "云原生数据库", "HTAP", "数据湖", "查询优化", "事务处理", "数据库安全"],
    "medicine": ["医学影像", "精准医疗", "药物发现", "临床决策", "健康数据", "基因组学", "远程医疗", "医疗机器人"],
    "education": ["智慧教育", "个性化学习", "学习分析", "教育大模型", "自动评测", "虚拟实验", "数字教材"],
    "finance": ["金融科技", "量化研究", "风险控制", "智能投顾", "反欺诈", "数字货币", "金融大模型"],
    "security": ["隐私计算", "零信任", "数据安全", "大模型安全", "漏洞检测", "可信计算", "密码学"],
    "robotics": ["具身智能", "人形机器人", "自动驾驶", "世界模型", "VLA", "机器人控制", "群体智能"],
    "general": ["科研方法", "技术趋势", "产业分析", "开源生态", "伦理治理", "可持续发展"],
}

# Topic names are global canonical entities.  These mappings deliberately make
# several topics relevant to more than one domain; a topic is not copied just
# because it appears in multiple fields.
SHARED_DOMAINS = {
    "RAG": {"ai": 1.0, "database": .82},
    "知识图谱": {"database": 1.0, "ai": .86},
    "隐私计算": {"security": 1.0, "finance": .78, "medicine": .65},
    "大模型安全": {"security": 1.0, "ai": .92},
    "反欺诈": {"finance": 1.0, "security": .9, "ai": .76},
    "金融大模型": {"finance": 1.0, "ai": .92},
    "医学影像": {"medicine": 1.0, "ai": .74},
    "药物发现": {"medicine": 1.0, "ai": .72},
    "教育大模型": {"education": 1.0, "ai": .9},
    "自动评测": {"education": 1.0, "ai": .7},
    "自动驾驶": {"robotics": 1.0, "ai": .84, "security": .58},
    "世界模型": {"robotics": 1.0, "ai": .9},
    "数据安全": {"security": 1.0, "database": .86},
    "联邦学习": {"ai": 1.0, "security": .8, "medicine": .62},
    "科研方法": {"general": 1.0, "education": .55},
}
ALIASES = {
    "大语言模型": ["大模型", "LLM", "Large Language Model"],
    "生成式AI": ["生成式人工智能", "Generative AI"],
    "RAG": ["检索增强生成", "Retrieval-Augmented Generation"],
    "智能体": ["AI Agent", "人工智能智能体"],
    "知识图谱": ["Knowledge Graph", "KG"],
    "向量数据库": ["Vector Database", "向量数据存储"],
    "HTAP": ["混合事务分析处理"],
    "反欺诈": ["欺诈检测", "Fraud Detection"],
    "风险控制": ["风控", "Risk Control"],
    "隐私计算": ["Privacy Computing"],
    "零信任": ["Zero Trust"],
    "VLA": ["视觉语言动作模型", "Vision-Language-Action"],
    "自动驾驶": ["Autonomous Driving"],
    "医学影像": ["Medical Imaging"],
    "精准医疗": ["Precision Medicine"],
}
ASPECTS = [
    ("应用研究", None), ("方法比较", None), ("评测体系", None), ("工程实践", None),
    ("性能优化", "database"), ("安全治理", "security"), ("隐私保护", "security"),
    ("数据治理", "database"), ("可解释性", "ai"), ("人机协同", "ai"),
    ("产业生态", "general"), ("可靠性评估", "general"),
]
TITLE_ANGLES = ["技术演进", "应用现状", "方法比较", "系统设计", "挑战与机会", "实践路径", "评测分析"]


def build_topic_catalog(target: int):
    """Build unique, readable canonical topics with weighted domain links."""
    catalog = []
    seen = set()

    def add(name: str, base: str, domains: dict[str, float]):
        normalized = normalize_name(name)
        if normalized in seen or len(catalog) >= target:
            return
        seen.add(normalized)
        catalog.append({"name": name, "base": base, "normalized": normalized, "domains": domains})

    bases = []
    for primary_slug, names in DOMAIN_TOPICS.items():
        for base in names:
            domains = dict(SHARED_DOMAINS.get(base, {primary_slug: 1.0}))
            domains.setdefault(primary_slug, 1.0)
            bases.append((base, primary_slug, domains))
            add(base, base, domains)

    for aspect_index, (aspect, aspect_domain) in enumerate(ASPECTS):
        for base_index, (base, primary_slug, base_domains) in enumerate(bases):
            domains = dict(base_domains)
            # About one third of derived topics receive an additional plausible
            # domain, creating realistic cross-field overlap without making
            # every topic belong everywhere.
            if aspect_domain and aspect_domain != primary_slug and (base_index + aspect_index) % 3 == 0:
                domains.setdefault(aspect_domain, .58)
            add(f"{base}{aspect}", base, domains)
            if len(catalog) >= target:
                return catalog
    return catalog


def reset(store: ResearchSquareStore):
    """Remove only generated content, preserving any real local publications."""
    with store.connect() as db:
        db.execute("DELETE FROM public_researches WHERE source_run_id LIKE 'seed-%'")
        db.execute("DELETE FROM topics WHERE NOT EXISTS(SELECT 1 FROM research_topics rt WHERE rt.topic_id=topics.id)")
        db.execute("""DELETE FROM users WHERE public_id LIKE 'sim-user-%'
            AND NOT EXISTS(SELECT 1 FROM public_researches r WHERE r.owner_id=users.id)
            AND NOT EXISTS(SELECT 1 FROM research_events e WHERE e.user_id=users.id)""")


def generate(preset: str, should_reset: bool, seed: int):
    cfg = PRESETS[preset]; rng = random.Random(seed); store = ResearchSquareStore()
    if should_reset: reset(store)
    now = datetime.now(timezone.utc); stamp = now.isoformat()
    with store.connect() as db:
        domain_rows = [dict(x) for x in db.execute("SELECT id,slug,name FROM domains")]
        domain_by_slug = {x["slug"]: x for x in domain_rows}
        users = [(f"sim-user-{i:06d}", f"sim_user_{i:06d}", f"模拟研究者 {i:05d}", "active", stamp, stamp) for i in range(cfg["users"])]
        db.executemany("INSERT OR IGNORE INTO users(public_id,username,display_name,status,created_at,updated_at) VALUES(?,?,?,?,?,?)", users)
        user_ids = [x[0] for x in db.execute("SELECT id FROM users WHERE public_id LIKE 'sim-user-%'")]

        domain_cycle=list(DOMAIN_TOPICS)
        catalog=build_topic_catalog(cfg["topics"])
        if len(catalog) < cfg["topics"]:
            raise RuntimeError(f"主题目录只有 {len(catalog)} 条，无法满足 {cfg['topics']} 条")
        topic_payload=[(uuid4().hex,x["name"],x["normalized"],"active",stamp,stamp) for x in catalog]
        db.executemany("INSERT INTO topics(public_id,canonical_name,normalized_name,status,created_at,updated_at) VALUES(?,?,?,?,?,?)", topic_payload)
        topic_rows=[dict(x) for x in db.execute("SELECT id,canonical_name,normalized_name FROM topics")]
        topic_id_by_norm={x["normalized_name"]:x["id"] for x in topic_rows}
        topic_domain=[]
        topics_by_domain={slug:[] for slug in domain_cycle}
        shared_topic_ids=[]
        for item in catalog:
            topic_id=topic_id_by_norm[item["normalized"]]
            primary=max(item["domains"],key=item["domains"].get)
            if len(item["domains"]) > 1: shared_topic_ids.append(topic_id)
            for slug,score in item["domains"].items():
                topic_domain.append((topic_id,domain_by_slug[slug]["id"],score,int(slug==primary),"seed",.96,"approved"))
                topics_by_domain[slug].append(topic_id)
        db.executemany("""INSERT OR IGNORE INTO topic_domains(
            topic_id,domain_id,relevance_score,is_primary,source,confidence,review_status)
            VALUES(?,?,?,?,?,?,?)""",topic_domain)

        canonical_norms={x["normalized"] for x in catalog}; alias_norms=set(); alias_payload=[]
        for item in catalog:
            for alias_base in ALIASES.get(item["base"], [])[:1 if item["name"] != item["base"] else 3]:
                alias = item["name"].replace(item["base"], alias_base, 1)
                normalized_alias=normalize_name(alias)
                if normalized_alias in canonical_norms or normalized_alias in alias_norms: continue
                alias_norms.add(normalized_alias)
                alias_payload.append((topic_id_by_norm[item["normalized"]],alias,normalized_alias,"seed",.94,"approved",stamp))
        db.executemany("""INSERT OR IGNORE INTO topic_aliases(
            topic_id,alias,normalized_alias,source,confidence,review_status,created_at)
            VALUES(?,?,?,?,?,?,?)""",alias_payload)

        topic_name_by_id={x["id"]:x["canonical_name"] for x in topic_rows}
        # Give canonical topics distinct lifecycle profiles so the trend colour
        # scale contains rising, stable and cooling topics instead of a wall of
        # identical red nodes.
        topic_trend_by_id={topic_id:rng.choices(
            ["rising","stable","declining"],weights=[35,40,25],k=1)[0]
            for topic_id in topic_name_by_id}

        research_topics=[]; researches=[]; research_meta=[]
        for index in range(cfg["researches"]):
            slug=rng.choices(domain_cycle,weights=[20,18,10,8,8,7,12,5],k=1)[0]
            d=domain_by_slug[slug]; owner=rng.choice(user_ids); available=topics_by_domain[slug]
            chosen=[rng.choice(available)]
            desired=rng.randint(2,4)
            if rng.random()<.38:
                cross_candidates=[x for x in shared_topic_ids if x in available and x not in chosen]
                if cross_candidates: chosen.append(rng.choice(cross_candidates))
            remaining=[x for x in available if x not in chosen]
            if len(chosen)<desired: chosen.extend(rng.sample(remaining,min(len(remaining),desired-len(chosen))))
            lifecycle=topic_trend_by_id[chosen[0]]
            if lifecycle=="rising": age_days=int((rng.random()**2.2)*180)
            elif lifecycle=="declining": age_days=int((1-rng.random()**2.2)*180)
            else: age_days=rng.randint(0,179)
            published=now-timedelta(days=age_days,seconds=rng.randint(0,86400))
            primary=topic_name_by_id[chosen[0]]; secondary=topic_name_by_id[chosen[1]]
            title=f"[模拟] {primary}与{secondary}的{rng.choice(TITLE_ANGLES)}"
            topic_text="、".join(topic_name_by_id[x] for x in chosen)
            summary=f"这是用于本地功能和并发测试的模拟研究数据，涉及{topic_text}，主要领域为{d['name']}。不代表真实用户观点或真实热度。"
            public_id=uuid4().hex; views=rng.randint(0,500); heat=10+views*.2
            researches.append((public_id,owner,f"seed-{index}",d["id"],title,summary,None,"summary",rng.randint(0,5)==0,1,1,"published",published.isoformat(),published.isoformat(),1,views,0,0,0,heat))
            research_meta.append((public_id,owner,published,chosen))
        db.executemany("""INSERT INTO public_researches(public_id,owner_id,source_run_id,domain_id,title,summary,report_content,
            report_visibility,is_anonymous,allow_like,allow_favorite,status,published_at,updated_at,version,view_count,like_count,favorite_count,comment_count,heat_score)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",researches)
        research_ids={x["public_id"]:x["id"] for x in db.execute("SELECT id,public_id FROM public_researches WHERE source_run_id LIKE 'seed-%'")}
        for public_id,owner,published,chosen in research_meta:
            for rank,topic_id in enumerate(chosen):research_topics.append((research_ids[public_id],topic_id,max(.5,1-rank*.12),"seed",published.isoformat()))
        db.executemany("INSERT INTO research_topics VALUES(?,?,?,?,?)",research_topics)

        batches=[]; likes=set();favorites=set(); research_pairs=[(research_ids[x[0]],x[2]) for x in research_meta]
        for index in range(cfg["events"]):
            research_id,published=rng.choice(research_pairs);user_id=rng.choice(user_ids)
            action=rng.choices(["view","like","favorite","share"],weights=[78,12,6,4],k=1)[0]
            if action=="like":
                key=(research_id,user_id)
                if key in likes: action="view"
                else: likes.add(key)
            elif action=="favorite":
                key=(research_id,user_id)
                if key in favorites: action="view"
                else:favorites.add(key)
            event_time=published+timedelta(seconds=rng.randint(0,max(1,int((now-published).total_seconds()))))
            batches.append((f"seed-event-{index}",research_id,user_id,action,None,event_time.isoformat(),'{"synthetic":true}'))
            if len(batches)>=10000:
                db.executemany("INSERT INTO research_events(event_id,research_id,user_id,event_type,session_id,created_at,metadata_json) VALUES(?,?,?,?,?,?,?)",batches);batches=[]
        if batches:db.executemany("INSERT INTO research_events(event_id,research_id,user_id,event_type,session_id,created_at,metadata_json) VALUES(?,?,?,?,?,?,?)",batches)
        db.executemany("INSERT OR IGNORE INTO research_likes VALUES(?,?,?)",[(r,u,stamp) for r,u in likes])
        db.executemany("INSERT OR IGNORE INTO research_favorites VALUES(?,?,?)",[(r,u,stamp) for r,u in favorites])
        db.execute("""UPDATE public_researches SET view_count=(SELECT COUNT(*) FROM research_events e WHERE e.research_id=public_researches.id AND e.event_type='view')""")
    store.rebuild_analytics()
    print({"preset":preset,**cfg,"database":str(store.path)})


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--preset",choices=PRESETS,default="small");parser.add_argument("--reset",action="store_true");parser.add_argument("--seed",type=int,default=20261104)
    args=parser.parse_args();generate(args.preset,args.reset,args.seed)


if __name__=="__main__": main()
