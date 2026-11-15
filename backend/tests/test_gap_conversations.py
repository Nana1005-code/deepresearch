import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from fastapi import FastAPI
from fastapi.testclient import TestClient

from research_square.gap_conversations import router
from research_square.store import ResearchSquareStore


class GapConversationTests(unittest.TestCase):
    def test_academic_history_is_isolated_and_persistent(self):
        app = FastAPI()
        app.include_router(router(self.store, self.answer, 'openalex'))
        academic = TestClient(app)
        record = academic.post('/academic-conversations').json()
        url = '/academic-conversations/' + record['id']
        self.assertEqual(academic.post(url+'/messages', json={'question':'主题','data_source':'local'}).status_code,422)
        result = academic.post(url+'/messages', json={'question':'主题','data_source':'openalex'}).json()
        self.assertEqual(len(result['messages']),2)
        self.assertEqual(self.client.get('/gap-conversations/'+record['id']).status_code,404)
        self.assertEqual(academic.get('/academic-conversations/'+self.id).status_code,404)
        restored = FastAPI(); restored.include_router(router(self.store,self.answer,'openalex'))
        self.assertEqual(TestClient(restored).get(url).json(),result)
        self.assertEqual(academic.delete(url).status_code,204)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ResearchSquareStore(str(Path(self.temp.name) / 'square.sqlite3'))
        self.answer = lambda payload: {'answer': '说明', 'plan': {'source': 'local'}, 'data': {
            'suggestions': [{'name': '主题模型', 'cooccurrence_count': 15, 'my_research_count': 0}]}}
        self.client = self.make_client()
        self.id = self.client.post('/gap-conversations').json()['id']
        self.url = '/gap-conversations/' + self.id

    def make_client(self):
        app = FastAPI()
        app.include_router(router(self.store, lambda payload: self.answer(payload)))
        return TestClient(app)

    def test_persist_restore_and_delete(self):
        response = self.client.post(self.url + '/messages', json={'question': '  主题模型  '})
        self.assertEqual(response.status_code, 200)
        item = response.json()
        self.assertEqual(item['title'], '主题模型')
        self.assertEqual(item['messages'][0], {'role': 'user', 'content': '主题模型'})
        self.assertEqual(item['messages'][1]['suggestions'][0], {
            'name': '主题模型', 'cooccurrence_count': 15, 'my_research_count': 0})
        restored = self.make_client()
        self.assertEqual(restored.get(self.url).json(), item)
        history = restored.get('/gap-conversations').json()
        self.assertEqual(history[0]['message_count'], 2)
        self.assertEqual(history[0]['preview'], '主题模型')
        self.assertEqual(restored.delete(self.url).status_code, 204)
        self.assertEqual(restored.get(self.url).status_code, 404)
        self.assertEqual(restored.get('/gap-conversations').json(), [])

    def test_invalid_input_does_not_create_messages(self):
        for payload in ({'question': '   '}, {'question': '主题', 'data_source': 'openalex'}):
            self.assertEqual(self.client.post(self.url + '/messages', json=payload).status_code, 422)
        self.assertEqual(self.client.get(self.url).json()['messages'], [])

    def test_inflight_send_and_delete_are_rejected(self):
        started, release = Event(), Event()
        original = self.answer
        def blocking(payload):
            started.set()
            release.wait(5)
            return original(payload)
        self.answer = blocking
        with ThreadPoolExecutor() as pool:
            result = pool.submit(self.client.post, self.url + '/messages', json={'question': '主题'})
            try:
                self.assertTrue(started.wait(5))
                self.assertEqual(self.client.get(self.url).json()['status'], 'running')
                self.assertEqual(self.client.post(self.url + '/messages', json={'question': '重复'}).status_code, 409)
                self.assertEqual(self.client.delete(self.url).status_code, 409)
            finally:
                release.set()
            self.assertEqual(result.result().json()['status'], 'idle')

    def test_failure_allows_retry(self):
        original = self.answer
        def fail(payload):
            raise RuntimeError('private upstream error')
        self.answer = fail
        item = self.client.post(self.url + '/messages', json={'question': '主题'}).json()
        self.assertEqual(item['status'], 'idle')
        self.assertTrue(item['error'])
        self.assertNotIn('private', item['error'])
        self.answer = original
        item = self.client.post(self.url + '/messages', json={'question': '重试'}).json()
        self.assertIsNone(item['error'])
        self.assertEqual(len(item['messages']), 3)

    def test_restart_recovers_interrupted_history(self):
        import json
        item = self.client.get(self.url).json()
        item['status'] = 'running'
        with self.store.connect() as db:
            db.execute('UPDATE gap_conversations SET data=? WHERE id=?', (json.dumps(item), self.id))
        item = self.make_client().get(self.url).json()
        self.assertEqual(item['status'], 'idle')
        self.assertIn('中断', item['error'])
