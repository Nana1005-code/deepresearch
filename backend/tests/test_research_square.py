import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from main import create_app
from research_square.router import _deterministic_answer, _fallback_plan, _repair_plan
from research_square.canonical import bootstrap_canonical_topics
from research_square.schemas import QueryPlan
from research_square.store import ResearchSquareStore, normalize_name


class ResearchSquareStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=ResearchSquareStore(str(Path(self.temp.name)/"square.sqlite3"))
        self.store.publish(source_run_id="run-1",owner_public_id="local-user",domain_slug="database",
            title="向量数据库研究",summary="公开摘要",report=None,topics=["向量数据库","RAG"],anonymous=False)
        self.public_id=self.store.list_researches()["items"][0]["public_id"]

    def test_publication_is_idempotent_and_private_by_default(self):
        second=self.store.publish(source_run_id="run-1",owner_public_id="local-user",domain_slug="database",
            title="更新后的研究",summary="新版摘要",report=None,topics=["向量数据库"],anonymous=True)
        self.assertEqual(self.store.list_researches()["total"],1)
        self.assertEqual(second["title"],"更新后的研究")
        self.store.unpublish(self.public_id,"local-user")
        self.assertEqual(self.store.list_researches()["total"],0)

    def test_duplicate_like_is_not_counted_twice(self):
        first=self.store.record_action(self.public_id,"user-a","like","event-a")
        second=self.store.record_action(self.public_id,"user-a","like","event-b")
        self.assertTrue(first["changed"]);self.assertFalse(second["changed"])
        self.assertEqual(self.store.get_research(self.public_id)["like_count"],1)

    def test_graph_and_hot_topics_use_public_data(self):
        overview=self.store.overview(30,"database")
        graph=self.store.graph(30,"database")
        self.assertGreaterEqual(len(overview["hot_topics"]),2)
        self.assertEqual(len(graph["nodes"]),2)
        self.assertEqual(len(graph["edges"]),1)
        self.assertIn("recent_activity",graph["nodes"][0])
        self.assertIn("average_started_at",graph["nodes"][0])
        self.assertNotIn("growth_rate",graph["nodes"][0])
        self.assertNotIn("domains",graph["nodes"][0])

    def test_graph_activity_uses_research_start_time_not_import_time(self):
        old_start=(date.today()-timedelta(days=300)).isoformat()
        recent_start=(date.today()-timedelta(days=10)).isoformat()
        self.store.publish(source_run_id="old-start",owner_public_id="local-user",domain_slug="database",
            title="旧研究",summary="旧研究",report=None,topics=["旧方向"],
            research_started_at=old_start)
        self.store.publish(source_run_id="recent-start",owner_public_id="local-user",domain_slug="database",
            title="新研究",summary="新研究",report=None,topics=["新方向"],
            research_started_at=recent_start)
        nodes={node["name"]:node for node in self.store.graph(365,limit=20)["nodes"]}
        self.assertGreater(nodes["新方向"]["recent_activity"],nodes["旧方向"]["recent_activity"])
        self.assertEqual(nodes["新方向"]["average_started_at"],recent_start)

    def test_user_keyword_graph_preserves_full_input_and_node_detail(self):
        full_input="抑郁症语音检测中的因果不变表示能否与图神经网络结合，并减少跨医院域偏移？"
        item=self.store.publish(source_run_id="sample-detail",owner_public_id="sample-library",
            domain_slug="general",title=full_input,summary=full_input,report=None,topics=[],anonymous=True,
            research_input=full_input,data_origin="sample",extraction_status="pending",create_initial_topics=False)
        self.store.replace_research_concepts(item["public_id"],[
            {"canonical_name_zh":"抑郁症语音检测","concept_type":"task","weight":1,"confidence":.96,"surface_text":"抑郁症语音检测"},
            {"canonical_name_zh":"因果不变表示","concept_type":"method","weight":.9,"confidence":.93,"surface_text":"因果不变表示"},
            {"canonical_name_zh":"图神经网络","concept_type":"model","weight":.85,"confidence":.95,"surface_text":"图神经网络"},
        ])
        graph=self.store.graph(30,limit=20,max_edges_per_node=3)
        self.assertTrue({"抑郁症语音检测","因果不变表示","图神经网络"}.issubset({x["name"] for x in graph["nodes"]}))
        node=next(x for x in graph["nodes"] if x["name"]=="因果不变表示")
        detail=self.store.community_topic_detail(node["id"])
        self.assertEqual(detail["researches"][0]["research_input"],full_input)
        self.assertEqual(detail["researches"][0]["data_origin"],"sample")
        self.assertEqual(detail["concept_type"],"method")
        self.assertGreaterEqual(len(graph["edges"]),3)

    def test_personal_list_pinning_pagination_and_remove_import(self):
        sample=self.store.publish(source_run_id="sample-pin",owner_public_id="sample-library",
            domain_slug="general",title="可移除样例",summary="可移除样例",report=None,topics=["样例主题"],
            anonymous=True,research_input="可移除样例",data_origin="sample")
        self.store.set_pinned(sample["public_id"],True)
        first=self.store.list_researches(limit=1,offset=0)["items"][0]
        self.assertEqual(first["public_id"],sample["public_id"]);self.assertTrue(first["is_pinned"])
        self.store.remove_import(sample["public_id"])
        self.assertNotIn(sample["public_id"],{x["public_id"] for x in self.store.list_researches(limit=20)["items"]})

    def test_persistent_import_queue_limit_and_recovery(self):
        for index in range(10):
            self.store.enqueue_import(f"queued-{index}","profile",max_queued=10)
        with self.assertRaises(OverflowError):
            self.store.enqueue_import("queued-overflow","profile",max_queued=10)
        claimed=self.store.claim_next_import_job();self.assertEqual(claimed["status"],"processing")
        self.store.recover_import_jobs()
        self.assertEqual(self.store.import_queue_status()["counts"]["queued"],10)

    def test_completed_local_research_is_rejected_before_requeue(self):
        job=self.store.enqueue_import("run-1","profile",max_queued=10)
        self.assertTrue(job["already_exists"])
        self.assertEqual(job["status"],"completed")
        self.assertEqual(job["research_public_id"],self.public_id)

    def test_failed_keyword_extraction_is_reported_and_can_be_requeued(self):
        self.store.replace_research_concepts(self.public_id,[],extraction_status="failed",
                                             extraction_error="401 invalid api key")
        first=self.store.enqueue_import("run-1","profile",max_queued=10)
        self.assertFalse(first["already_exists"])
        self.store.finish_import_job(first["public_id"],status="failed",error="401 invalid api key")
        failed=self.store.import_status("run-1")
        self.assertEqual(failed["state"],"failed")
        self.assertIn("重试",failed["message"])
        retry=self.store.enqueue_import("run-1","profile",max_queued=10)
        self.assertFalse(retry["already_exists"])
        self.assertTrue(retry["retried"])
        self.assertEqual(retry["status"],"queued")

    def test_cancelled_real_import_restores_without_new_ai_job(self):
        self.store.remove_import(self.public_id)
        self.assertEqual(self.store.list_researches()["total"],0)
        restored=self.store.restore_hidden_import("run-1")
        self.assertIsNotNone(restored)
        self.assertEqual(restored["public_id"],self.public_id)
        self.assertEqual(set(restored["topics"]),{"向量数据库","RAG"})
        self.assertEqual(self.store.import_queue_status()["counts"]["queued"],0)

    def test_personal_records_expose_source_run_for_history_navigation(self):
        item=next(x for x in self.store.list_researches(limit=20)["items"] if x["public_id"]==self.public_id)
        self.assertEqual(item["source_run_id"],"run-1")
        topic=next(x for x in self.store.graph(30)["nodes"] if x["name"]=="向量数据库")
        detail=self.store.community_topic_detail(topic["id"])
        linked=next(x for x in detail["researches"] if x["public_id"]==self.public_id)
        self.assertEqual(linked["source_run_id"],"run-1")

    def test_alias_resolves_to_one_global_topic_with_multiple_domains(self):
        with self.store.connect() as db:
            topic=db.execute("SELECT id FROM topics WHERE normalized_name=?",(normalize_name("RAG"),)).fetchone()
            db.execute("""INSERT INTO topic_aliases(topic_id,alias,normalized_alias,source,confidence,review_status,created_at)
                VALUES(?,?,?,?,?,?,datetime('now'))""",(topic["id"],"检索增强生成",normalize_name("检索增强生成"),"seed",.95,"approved"))
        self.store.publish(source_run_id="run-alias",owner_public_id="local-user",domain_slug="ai",
            title="检索增强生成研究",summary="别名归一测试",report=None,topics=["检索增强生成"],anonymous=False)
        with self.store.connect() as db:
            topics=db.execute("SELECT COUNT(*) FROM topics WHERE id=?",(topic["id"],)).fetchone()[0]
            domains=db.execute("SELECT COUNT(*) FROM topic_domains WHERE topic_id=?",(topic["id"],)).fetchone()[0]
            duplicate=db.execute("SELECT COUNT(*) FROM topics WHERE normalized_name=?",(normalize_name("检索增强生成"),)).fetchone()[0]
        self.assertEqual(topics,1);self.assertGreaterEqual(domains,2);self.assertEqual(duplicate,0)

    def test_graph_limits_each_node_to_strongest_edges(self):
        topics=[f"稀疏图主题{x}" for x in "甲乙丙丁戊己"]
        self.store.publish(source_run_id="run-dense",owner_public_id="local-user",domain_slug="database",
            title="稠密关系测试",summary="测试图谱稀疏化",report=None,topics=topics,anonymous=False)
        graph=self.store.graph(30,"database",20,max_edges_per_node=2)
        degrees={node["id"]:0 for node in graph["nodes"]}
        for edge in graph["edges"]:
            degrees[edge["source"]]+=1;degrees[edge["target"]]+=1
        self.assertLessEqual(max(degrees.values()),2)

    def test_controlled_query_plan(self):
        data=self.store.query_plan_data(QueryPlan(intent="rank_topics",domain_slug="database",days=30))
        self.assertIn("topics",data);self.assertTrue(data["topics"])

    def test_free_text_topic_resolution_and_plan_repair(self):
        question="向量数据库与RAG有哪些关联主题？"
        matched=self.store.resolve_topic_mentions(question)
        self.assertEqual(set(matched),{"向量数据库","RAG"})
        default=_fallback_plan(question,30,None,matched)
        broken=QueryPlan(intent="related_topics",domain_slug="ai",topics=[])
        repaired=_repair_plan(broken,default,matched)
        self.assertEqual(repaired.intent,"related_topics")
        self.assertEqual(set(repaired.topics),set(matched))

    def test_missing_topic_does_not_fall_back_to_hot_ranking(self):
        data=self.store.query_plan_data(QueryPlan(intent="related_topics",topics=[]))
        self.assertEqual(data["error"],"missing_topic")
        self.assertNotIn("topics",data)

    def test_ninety_day_trend_has_three_periods_and_changes(self):
        with self.store.connect() as db:
            topic_id=db.execute("SELECT id FROM topics WHERE normalized_name=?",(normalize_name("RAG"),)).fetchone()[0]
            db.execute("DELETE FROM topic_daily_stats WHERE topic_id=?",(topic_id,))
            for age,heat,count in [(75,100,8),(45,150,11),(15,120,9)]:
                day=(date.today()-timedelta(days=age)).isoformat()
                db.execute("INSERT INTO topic_daily_stats VALUES(?,?,?,?,?,?,?,?,datetime('now'))",
                    (topic_id,day,count,20,3,1,10,heat))
        plan=QueryPlan(intent="topic_trend",topics=["RAG"],days=90)
        data=self.store.query_plan_data(plan)
        summary=data["trend_summaries"]["RAG"]
        self.assertEqual(summary["bucket_days"],30)
        self.assertEqual([x["heat"] for x in summary["periods"]],[100,150,120])
        self.assertEqual(summary["latest_change_pct"],-20)
        self.assertEqual(summary["direction"],"down")
        answer=_deterministic_answer(plan,data)
        self.assertIn("环比",answer);self.assertIn("下降",answer)

    def test_openalex_tables_are_isolated_and_overview_does_not_double_count(self):
        stamp="2026-11-04T00:00:00+00:00"
        with self.store.connect() as db:
            db.executemany("""INSERT INTO openalex_works(openalex_id,title,publication_date,cited_by_count,
                is_oa,authors_json,imported_at,updated_at) VALUES(?,?,?,?,?,?,?,?)""",[
                ("W1","真实论文一",date.today().isoformat(),5,1,'[]',stamp,stamp),
                ("W2","真实论文二",date.today().isoformat(),3,0,'[]',stamp,stamp)])
            db.executemany("""INSERT INTO openalex_topics(openalex_id,display_name,imported_at,updated_at)
                VALUES(?,?,?,?)""",[("T1","Topic One",stamp,stamp),("T2","Topic Two",stamp,stamp)])
            work_ids={x["openalex_id"]:x["id"] for x in db.execute("SELECT id,openalex_id FROM openalex_works")}
            topic_ids={x["openalex_id"]:x["id"] for x in db.execute("SELECT id,openalex_id FROM openalex_topics")}
            db.executemany("INSERT INTO openalex_work_topics VALUES(?,?,?,?,?)",[
                (work_ids["W1"],topic_ids["T1"],.9,1,1),(work_ids["W1"],topic_ids["T2"],.4,2,0),
                (work_ids["W2"],topic_ids["T2"],.8,1,1)])
        overview=self.store.openalex_overview(30)
        self.assertEqual(overview["stats"]["works"],2)
        self.assertEqual(overview["stats"]["topics"],2)
        self.assertEqual(overview["stats"]["citations"],8)
        self.assertEqual(self.store.list_openalex_works(limit=10)["total"],2)
        self.assertEqual(self.store.list_researches()["total"],1)

    def test_openalex_graph_uses_canonical_topics_and_same_contract(self):
        stamp="2026-11-04T00:00:00+00:00"
        today=date.today().isoformat()
        with self.store.connect() as db:
            db.executemany("""INSERT INTO openalex_works(openalex_id,title,publication_date,cited_by_count,
                is_oa,authors_json,imported_at,updated_at) VALUES(?,?,?,?,?,?,?,?)""",[
                ("WG1","论文标题不是主题甲",today,9,1,'[]',stamp,stamp),
                ("WG2","论文标题不是主题乙",today,4,0,'[]',stamp,stamp)])
            db.executemany("""INSERT INTO openalex_topics(openalex_id,display_name,imported_at,updated_at)
                VALUES(?,?,?,?)""",[("TG1","Machine Learning",stamp,stamp),("TG2","Medical Imaging",stamp,stamp),("TG3","Evaluation",stamp,stamp)])
            work_ids={x["openalex_id"]:x["id"] for x in db.execute("SELECT id,openalex_id FROM openalex_works")}
            topic_ids={x["openalex_id"]:x["id"] for x in db.execute("SELECT id,openalex_id FROM openalex_topics")}
            db.executemany("INSERT INTO openalex_work_topics VALUES(?,?,?,?,?)",[
                (work_ids["WG1"],topic_ids["TG1"],.9,1,1),(work_ids["WG1"],topic_ids["TG2"],.8,2,0),
                (work_ids["WG2"],topic_ids["TG1"],.7,1,1),(work_ids["WG2"],topic_ids["TG3"],.6,2,0)])
            db.executemany("""INSERT INTO openalex_topic_enrichments
                (topic_id,chinese_name,confidence,status,model_id,prompt_version,updated_at)
                VALUES(?,?,.9,'completed','test','v1',?)""",[
                (topic_ids["TG1"],"机器学习",stamp),(topic_ids["TG2"],"医学影像",stamp),(topic_ids["TG3"],"评测体系",stamp)])
        graph=self.store.openalex_graph(30,limit=10,max_edges_per_node=2)
        self.assertEqual({"nodes","edges"}.issubset(graph),True)
        self.assertEqual({x["name"] for x in graph["nodes"]},{"机器学习","医学影像","评测体系"})
        self.assertNotIn("论文标题不是主题甲",{x["name"] for x in graph["nodes"]})
        self.assertEqual(len(graph["edges"]),2)
        self.assertTrue(all("relation_score" in x and "cooccurrence_count" in x for x in graph["edges"]))
        detail=self.store.openalex_topic_detail(graph["nodes"][0]["id"],100)
        self.assertLessEqual(len(detail["works"]),100)
        self.assertEqual([x["cited_by_count"] for x in detail["works"]],
                         sorted([x["cited_by_count"] for x in detail["works"]],reverse=True))
        self.assertEqual(len({x["openalex_id"] for x in detail["works"]}),len(detail["works"]))
        self.assertEqual(self.store.resolve_openalex_topic_mentions("机器学习有哪些关联主题？"),["机器学习"])
        gaps=self.store.research_gap_candidates("从我的研究历史来看，机器学习还有哪些主题是我遗漏的？",5)
        self.assertEqual(gaps["matched_topics"],["机器学习"]);self.assertTrue(gaps["suggestions"])
        self.assertTrue(all("my_research_count" in item for item in gaps["suggestions"]))
        plan=QueryPlan(intent="related_topics",topics=["机器学习"],days=30)
        data=self.store.query_openalex_plan_data(plan)
        self.assertEqual(data["source"],"openalex")
        self.assertEqual({x["name"] for x in data["related"]},{"医学影像","评测体系"})

    def test_canonical_alias_reuse_and_reversible_mapping(self):
        stamp="2026-11-06T00:00:00+00:00"
        with self.store.connect() as db:
            db.executemany("""INSERT INTO openalex_topics(openalex_id,display_name,imported_at,updated_at)
                VALUES(?,?,?,?)""",[("TC1","AI for Medical Images",stamp,stamp),("TC2","Artificial Intelligence in Medical Imaging",stamp,stamp)])
            ids={x["openalex_id"]:x["id"] for x in db.execute("SELECT id,openalex_id FROM openalex_topics WHERE openalex_id IN ('TC1','TC2')")}
            db.executemany("""INSERT INTO openalex_topic_enrichments(topic_id,chinese_name,summary_zh,
                confidence,status,model_id,prompt_version,updated_at) VALUES(?,?,?,.96,'completed','test','v1',?)""",[
                (ids["TC1"],"医学影像人工智能","说明一",stamp),(ids["TC2"],"人工智能医学影像分析","说明二",stamp)])
        first=bootstrap_canonical_topics(self.store,[ids["TC1"]])
        with self.store.connect() as db:
            target=db.execute("SELECT canonical_topic_id FROM openalex_topic_canonical_mappings WHERE openalex_topic_id=?",(ids["TC1"],)).fetchone()[0]
        second=bootstrap_canonical_topics(self.store,[ids["TC2"]],{ids["TC2"]:{
            "target_canonical_id":target,"confidence":.97,"reason":"模型判断等价"}})
        with self.store.connect() as db:
            mapped={x[0] for x in db.execute("SELECT canonical_topic_id FROM openalex_topic_canonical_mappings WHERE openalex_topic_id IN (?,?)",(ids["TC1"],ids["TC2"]))}
            aliases={x[0] for x in db.execute("SELECT alias FROM openalex_canonical_aliases WHERE canonical_topic_id=?",(target,))}
        self.assertEqual(first["created"],1);self.assertEqual(second["reused"],1)
        self.assertEqual(mapped,{target});self.assertIn("人工智能医学影像分析",aliases)

    def test_concurrent_unique_likes_are_consistent(self):
        def like(index):
            return self.store.record_action(self.public_id,f"concurrent-{index}","like",f"concurrent-event-{index}")
        with ThreadPoolExecutor(max_workers=12) as pool:list(pool.map(like,range(40)))
        item=self.store.get_research(self.public_id)
        with self.store.connect() as db:detail=db.execute("SELECT COUNT(*) FROM research_likes").fetchone()[0]
        self.assertEqual(item["like_count"],detail)
        self.assertEqual(detail,40)


class ResearchSquareApiIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.old_db=os.environ.get("RESEARCH_DB_PATH");self.old_square=os.environ.get("RESEARCH_SQUARE_DB_URL")
        os.environ["RESEARCH_DB_PATH"]=str(Path(self.temp.name)/"research.sqlite3")
        os.environ["RESEARCH_SQUARE_DB_URL"]=str(Path(self.temp.name)/"square.sqlite3")
        self.app=create_app()

    def tearDown(self):
        if self.old_db is None:os.environ.pop("RESEARCH_DB_PATH",None)
        else:os.environ["RESEARCH_DB_PATH"]=self.old_db
        if self.old_square is None:os.environ.pop("RESEARCH_SQUARE_DB_URL",None)
        else:os.environ["RESEARCH_SQUARE_DB_URL"]=self.old_square

    def test_health_and_empty_square_do_not_modify_existing_store(self):
        paths={route.path for route in self.app.routes}
        self.assertIn("/healthz",paths)
        self.assertIn("/research-square/researches",paths)
        self.assertIn("/research-square/openalex/topics/{public_id}",paths)
        self.assertIn("/research-square/community/topics/{public_id}",paths)
        self.assertIn("/research-square/import-queue",paths)
        self.assertIn("/research-square/import-status/{source_run_id}",paths)
        self.assertIn("/research-square/researches/{public_id}/pin",paths)
        self.assertEqual(self.app.state.research_square.list_researches()["total"],0)
        self.assertEqual(self.app.state.store.runs(),[])
        with self.app.state.research_square.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM openalex_works").fetchone()[0],0)


if __name__=="__main__":unittest.main()
