"""Import an idempotent anonymous sample library for the user research graph.

Samples live in the same normalized tables as real anonymous publications, but
``public_researches.data_origin='sample'`` keeps them distinguishable and
deletable.  The model uses the exact same extraction path as live publication.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from research_square.community_extractor import extract_and_attach  # noqa: E402
from research_square.store import ResearchSquareStore  # noqa: E402


SAMPLES = [
    "多视图学习在多模态情感识别中的应用，如何处理不同模态缺失与视图不一致问题？",
    "抑郁症语音检测中的因果不变表示能否与图神经网络结合，以减少不同医院和语言环境造成的域偏移？",
    "面向阿尔茨海默病早筛的语音、眼动和脑影像多模态融合，如何设计可解释的纵向预测模型？",
    "利用联邦学习训练跨医院医学影像分割模型时，怎样同时应对非独立同分布数据、隐私保护和通信成本？",
    "大语言模型辅助临床决策时，如何通过检索增强生成和知识图谱降低医学幻觉并提供可追溯证据？",
    "基于可穿戴设备的心律失常检测能否结合时序Transformer和自监督学习提升少样本患者的识别效果？",
    "多模态大模型在病理切片与临床文本联合诊断中的对齐机制、可靠性评测和偏差控制。",
    "面向金融反欺诈的动态图神经网络如何融合交易序列、设备指纹与社交关系，并处理概念漂移？",
    "如何用因果推断区分信贷风险模型中的真实风险因素与代理变量，兼顾公平性和可解释性？",
    "基于大语言模型的金融研报问答系统如何结合混合检索、重排序和引用校验减少错误回答？",
    "隐私计算环境下多机构反洗钱联合建模的安全性、可用性与审计机制研究。",
    "高频交易数据的流式异常检测如何利用在线学习适应市场状态变化，同时控制误报率？",
    "向量数据库在十亿级多模态检索中的索引结构、压缩策略和查询性能优化。",
    "RAG系统中混合检索、查询改写和交叉编码器重排序分别如何影响长文档问答的准确率与延迟？",
    "面向实时推荐的特征存储如何保证离线与在线特征一致性，并支持高并发更新？",
    "湖仓一体架构下增量数据处理、数据血缘和细粒度权限控制的工程实践。",
    "分布式数据库跨地域部署时，如何在一致性、可用性、写入延迟与故障恢复之间权衡？",
    "自然语言到SQL系统如何利用数据库模式链接、执行反馈与权限白名单提高复杂查询正确率？",
    "面向工业物联网的时序数据库怎样优化高基数标签、冷热分层和异常区间查询？",
    "知识图谱与向量检索联合用于企业数据治理时，实体消歧、增量更新和可信溯源怎么实现？",
    "软件供应链攻击检测如何结合代码图神经网络、依赖关系分析和行为日志？",
    "面向钓鱼邮件识别的文本、URL和页面截图多模态模型如何抵御对抗样本与新型攻击？",
    "零信任架构中持续身份认证如何融合鼠标行为、键盘节律和设备风险信号？",
    "大语言模型生成代码的安全评测应覆盖哪些漏洞类型、攻击场景和自动修复指标？",
    "用于恶意流量检测的自监督预训练模型如何跨网络环境迁移并保持可解释性？",
    "具身智能机器人在家庭环境中的视觉语言导航如何处理长期记忆、动态障碍和安全约束？",
    "多机器人协同探索中，如何结合强化学习与图神经网络优化通信受限条件下的任务分配？",
    "自动驾驶世界模型如何融合摄像头与激光雷达，并评估长尾场景预测的不确定性？",
    "柔性机械臂抓取透明物体时，触觉视觉融合与仿真到现实迁移可以怎样配合？",
    "生成式人工智能辅助编程课程中，怎样评估学生的真实学习增益并防止过度依赖？",
    "智能辅导系统如何通过知识追踪和大语言模型生成个性化反馈，同时保护未成年人数据？",
    "面向低资源语言教育的语音识别与自动评分系统如何降低口音偏差？",
    "科学文献综述代理如何规划检索、去重论文、核验引用并生成可复现的证据链？",
    "跨语言虚假信息检测能否结合多模态证据检索、传播图分析与事实核查？",
    "城市极端天气风险预测如何融合遥感影像、传感器时序数据和社会经济指标？",
    "面向碳排放监测的知识图谱如何连接企业披露、遥感观测和供应链数据并评估数据可信度？",
]


def load_profile(profile_id: str | None) -> dict:
    path = Path(ROOT / "backend" / "data" / "research.sqlite3")
    with sqlite3.connect(path) as db:
        if profile_id:
            row = db.execute("SELECT data FROM profiles WHERE id=?", (profile_id,)).fetchone()
        else:
            row = db.execute("SELECT data FROM profiles ORDER BY rowid DESC LIMIT 1").fetchone()
    if not row:
        raise SystemExit("没有找到模型配置，请传入 --model-profile-id")
    return json.loads(row[0])


def reset_samples(store: ResearchSquareStore) -> int:
    with store.connect() as db:
        ids = [row[0] for row in db.execute("SELECT id FROM public_researches WHERE data_origin='sample'")]
        db.execute("DELETE FROM public_researches WHERE data_origin='sample'")
        db.execute("DELETE FROM users WHERE public_id='sample-library' AND NOT EXISTS(SELECT 1 FROM public_researches WHERE owner_id=users.id)")
    store.rebuild_analytics()
    return len(ids)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-profile-id")
    parser.add_argument("--limit", type=int, default=len(SAMPLES))
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    store = ResearchSquareStore()
    if args.reset:
        print(json.dumps({"deleted_samples": reset_samples(store)}, ensure_ascii=False))
    profile = load_profile(args.model_profile_id)
    imported, failed = 0, []
    for index, research_input in enumerate(SAMPLES[:max(0, args.limit)], 1):
        sample_started_at = (datetime.now(timezone.utc) - timedelta(days=(index * 97) % 330)).isoformat()
        item = store.publish(source_run_id=f"sample-input-{index:03d}", owner_public_id="sample-library",
            domain_slug="general", title=research_input[:240], summary=research_input, report=None,
            topics=[], anonymous=True, research_input=research_input, data_origin="sample",
            extraction_status="pending", create_initial_topics=False,
            research_started_at=sample_started_at)
        try:
            extract_and_attach(store, item["public_id"], research_input, profile)
            imported += 1
            print(f"[{index}/{min(args.limit,len(SAMPLES))}] imported")
        except Exception as exc:
            store.replace_research_concepts(item["public_id"], [], extraction_status="failed",
                                            extraction_error=str(exc)[:500])
            failed.append({"index": index, "error": str(exc)[:160]})
            print(f"[{index}/{min(args.limit,len(SAMPLES))}] failed: {str(exc)[:120]}")
    print(json.dumps({"ok": not failed, "imported": imported, "failed": failed,
                      "database": str(store.path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
