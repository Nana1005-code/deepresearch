import tempfile
import unittest
from pathlib import Path
from research_square.store import ResearchSquareStore
from research_square.canonical import bootstrap_canonical_topics
from research_square.paper_search import suggestions


class PaperSearchTests(unittest.TestCase):
    def test_evidence_nodes_share_search_and_neighbors_with_openalex(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from research_square.node_search import router, integrated_graph
        with self.store.connect() as db:
            db.executemany('INSERT INTO academic_concepts VALUES(?,?,?)',[
                ('concept-llm','大语言模型','定义'),('concept-stance','立场检测','定义')])
            db.execute("INSERT INTO academic_concept_aliases VALUES('concept-llm','LLM')")
            db.executemany('INSERT INTO academic_concept_works VALUES(?,1,?)',[
                ('concept-llm','论文标题摘要'),('concept-stance','论文标题摘要')])
        app=FastAPI();app.include_router(router(self.store));client=TestClient(app)
        matches=client.get('/nodes/search',params={'source':'openalex','q':'LLM'}).json()
        self.assertEqual(matches[0]['public_id'],'concept-llm')
        graph=client.get('/nodes/concept-llm/graph',params={'source':'openalex'}).json()
        self.assertTrue(any(n['id']=='concept-stance' for n in graph['nodes']))
        self.assertTrue(any(not n['id'].startswith('concept-') for n in graph['nodes']))
        self.assertTrue(all(e['cooccurrence_count']==1 for e in graph['edges']))
        self.assertEqual(self.store.list_openalex_works(query='大语言模型')['total'],1)
        self.assertTrue(any(r['id']=='concept-llm' for r in suggestions(self.store,'LLM')))
        overview=integrated_graph(self.store,days=365,limit=10)
        self.assertTrue(any(n['id']=='concept-llm' for n in overview['nodes']))

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.store=ResearchSquareStore(str(Path(temp.name)/'test.sqlite3'))
        stamp='2026-11-15'
        with self.store.connect() as db:
            db.execute("""INSERT INTO openalex_works(openalex_id,title,abstract,authors_json,source_name,doi,publication_date,imported_at,updated_at)
                VALUES('W1','Cross-modal learning','An English abstract','[{"name":"Alice"}]','Example Journal','10.123/example',?,?,?)""",(stamp,stamp,stamp))
            db.execute("INSERT INTO openalex_topics(openalex_id,display_name,imported_at,updated_at) VALUES('T1','Multimodal Learning',?,?)",(stamp,stamp))
            db.execute('INSERT INTO openalex_work_topics VALUES(1,1,.9,1,1)')
            db.execute("""INSERT INTO openalex_topic_enrichments(topic_id,chinese_name,confidence,status,model_id,prompt_version,updated_at)
                VALUES(1,'多模态学习',.9,'completed','test','v1',?)""",(stamp,))
        bootstrap_canonical_topics(self.store)

    def test_chinese_topic_and_metadata_find_english_paper(self):
        for query in ['多模态','  多模态  ','Multimodal','Cross-modal','Alice','Example Journal','10.123/example']:
            result=self.store.list_openalex_works(query=query,limit=5)
            self.assertEqual(result['total'],1,query)
            self.assertEqual(result['items'][0]['openalex_id'],'W1')

    def test_suggestions_are_backed_by_search_results(self):
        for query in ['多模态','Multimodal','Cross-modal']:
            hints=suggestions(self.store,query)
            self.assertTrue(hints,query)
            for hint in hints:
                self.assertGreater(self.store.list_openalex_works(query=hint['label'])['total'],0)

    def test_no_match_and_literal_wildcards(self):
        for query in ['不存在的词条','%','_']:
            self.assertEqual(self.store.list_openalex_works(query=query)['total'],0)
            self.assertEqual(suggestions(self.store,query),[])
        self.assertEqual(suggestions(self.store,''),[])

    def test_search_keeps_pagination_counts(self):
        result=self.store.list_openalex_works(query='多模态',offset=1,limit=5)
        self.assertEqual(result['total'],1)
        self.assertEqual(result['items'],[])
