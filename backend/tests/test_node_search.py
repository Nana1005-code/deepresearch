import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from research_square.node_search import router
from research_square.store import ResearchSquareStore


class NodeSearchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = ResearchSquareStore(str(Path(temp.name)/'test.sqlite3'))
        for run, topics in [('one',['多模态大模型','多模态检索']),('two',['孤立节点'])]:
            self.store.publish(source_run_id=run, owner_public_id='local-user', domain_slug='general',title=run,
                summary='', report=None, topics=topics, anonymous=False)
        app=FastAPI(); app.include_router(router(self.store)); self.client=TestClient(app)

    def test_search_returns_only_real_nodes_and_neighbors(self):
        matches=self.client.get('/nodes/search',params={'q':'多模态'}).json()
        self.assertEqual({r['name'] for r in matches},{'多模态大模型','多模态检索'})
        center=matches[0]['public_id']
        graph=self.client.get(f'/nodes/{center}/graph').json()
        self.assertEqual(len(graph['nodes']),2)
        self.assertEqual(len(graph['edges']),1)
        self.assertEqual(graph['edges'][0]['source'],center)
        self.assertEqual(graph['edges'][0]['cooccurrence_count'],1)

    def test_empty_unknown_and_source_isolation(self):
        for params in ({'q':''},{'q':'zxqv99999'},{'q':'多模态','source':'openalex'}):
            self.assertEqual(self.client.get('/nodes/search',params=params).json(),[])
        self.assertEqual(self.client.get('/nodes/missing/graph').status_code,404)

    def test_isolated_node_remains_visible(self):
        node=self.client.get('/nodes/search',params={'q':'孤立节点'}).json()[0]
        graph=self.client.get('/nodes/'+node['public_id']+'/graph').json()
        self.assertEqual(len(graph['nodes']),1)
        self.assertEqual(graph['edges'],[])
