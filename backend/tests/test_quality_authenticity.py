import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from quality import authenticity as live
import quality_api
from storage import Store


class AuthenticityTests(unittest.TestCase):
    def setUp(self):
        live._CACHE.clear()
        self.row = dict(verified=True, title="多模态大模型幻觉检测的研究进展", url="https://example.org/paper", cited_in_body=False)

    def test_title_formatting_and_publisher_suffixes(self):
        self.assertTrue(live.title_matches(self.row['title'], "多模态 大模型幻觉检测的研究进展 | 学术出版社"))
        self.assertTrue(live.title_matches("张三. 多模态大模型幻觉检测的研究进展[J]. 2026.", self.row['title']))
        self.assertFalse(live.title_matches(self.row['title'], self.row['title'] + '补充实验'))
        self.assertTrue(live.title_matches('研究进展', '研究进展'))
        self.assertTrue(live.title_matches('VLM 评测集 | EvalScope', 'VLM评测集 | EvalScope'))
        self.assertTrue(live.title_matches('BERT', 'BERT'))
        self.assertTrue(live.title_matches('Evaluating Object Hallucination in Large Vision-Language Models（POPE, EMNLP 2023）', 'Evaluating Object Hallucination in Large Vision-Language Models'))
        self.assertFalse(live.title_matches('Evaluating Object Hallucination in Large Vision-Language Models（POPE）', 'Evaluating Object Hallucination in Small Models'))
        self.assertFalse(live.title_matches('招聘 | 完全不同的任务方向', '招聘 | 另一种任务方向'))
        self.assertFalse(live.title_matches('', ''))

    def test_acronym_and_conference_main_title(self):
        full = 'Decoupling Contrastive Decoding: Robust Hallucination Mitigation in Multimodal Large Language Models'
        self.assertTrue(live.title_matches('Decoupling Contrastive Decoding: Robust Hallucination Mitigation in MLLMs（DCD, NeurIPS 2025）', full))
        self.assertTrue(live.title_matches('NeurIPS Poster: Decoupling Contrastive Decoding', 'NeurIPS Poster ' + full))
        self.assertFalse(live.title_matches('Decoupling Contrastive Decoding', 'Contrastive Decoding: A Different Study'))
        self.assertFalse(live.title_matches('Medical Research', 'Medical Research: Different Study'))
        with patch.object(live, 'fetch_titles', return_value=(self.row['url'], ['Different paper'], '')):
            self.assertEqual(live.verify(self.row, force=True)['failure_kind'], 'title_mismatch')
        with patch.object(live, 'fetch_titles', side_effect=TimeoutError()):
            self.assertEqual(live.verify(self.row, force=True)['failure_kind'], 'unreachable')

    def test_transient_timeout_retries_and_multiple_publisher_suffixes(self):
        with patch.object(live, '_fetch_titles_once', side_effect=[TimeoutError(), ('https://a.test', ['Title'], '')]) as fetch:
            self.assertEqual(live.fetch_titles('https://a.test')[1], ['Title'])
            self.assertEqual(fetch.call_count, 2)
        self.assertTrue(live.title_matches('《MLLM 综述》（2025-12-19）', 'MLLM 综述 - Orzjh - 博客园'))
        self.assertFalse(live.title_matches('招聘 | 完全不同的任务方向', '招聘 | 另一种任务方向'))

    def test_real_requires_access_and_matching_title_and_preserves_uncited(self):
        with patch.object(live, 'fetch_titles', return_value=(self.row['url'], [self.row['title']], '')) as fetch:
            result = live.verify(self.row)
            self.assertEqual(result['status'], 'real')
            self.assertFalse(self.row['cited_in_body'])
            self.assertIn('checked_at', result)
            live.verify(self.row)
            self.assertEqual(fetch.call_count, 1)
            live.verify(self.row, force=True)
            self.assertEqual(fetch.call_count, 2)

    def test_mismatched_or_missing_title_and_unreachable_are_not_real(self):
        for titles in [[], ['错误页面'], ['同领域的其他论文研究进展']]:
            with patch.object(live, 'fetch_titles', return_value=(self.row['url'], titles, '')):
                self.assertEqual(live.verify(self.row, force=True)['status'], 'unconfirmed')
        for exc in [ValueError('链接访问返回 HTTP 404'), ValueError('链接访问返回 HTTP 403'), TimeoutError()]:
            with patch.object(live, 'fetch_titles', side_effect=exc):
                self.assertEqual(live.verify(self.row, force=True)['status'], 'unconfirmed')

    def test_do_not_promote_unmatched_or_local_references_or_check_repair_fallback(self):
        with patch.object(live, 'fetch_titles', return_value=(self.row['url'], [self.row['title']], '')) as fetch:
            self.assertEqual(live.verify({**self.row, 'verified':False})['status'], 'unconfirmed')
            self.assertEqual(live.verify({**self.row, 'url':'local://documents/doc'})['status'], 'unconfirmed')
            fetch.assert_not_called()
            live.verify({**self.row, 'matched_url':'https://example.org/paper/full'})
            fetch.assert_called_once_with(self.row['url'])

    def test_cache_is_bound_to_url_and_reported_title(self):
        with patch.object(live, 'fetch_titles', return_value=(self.row['url'], [self.row['title']], '')):
            self.assertEqual(live.verify(self.row)['status'], 'real')
            self.assertEqual(live.verify({**self.row, 'title':'完全不同的研究文章标题信息'})['status'], 'unconfirmed')

    def test_html_metadata_and_heading_titles(self):
        parser = live.Titles()
        parser.feed('<html><head><title>A &amp; B</title><meta property="og:title" content="Article title"></head><body><h1>论文<strong>完整</strong>标题</h1><p>Not a title</p></body></html>')
        self.assertEqual(parser.titles, ['A & B', 'Article title', '论文 完整 标题'])

    def test_private_destinations_and_credentials_are_rejected(self):
        with patch.object(live.socket, 'getaddrinfo', return_value=[(2,1,6,'',('127.0.0.1',80))]):
            with self.assertRaises(ValueError): live._public_url('http://localhost/')
        for url in ['file:///test', 'https://name:password@example.org/', 'http://example.org:8000/']:
            with self.assertRaises(ValueError): live._public_url(url)

    def test_fetch_checks_http_status_and_every_redirect_target(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status_code = 404
        session = MagicMock()
        session.__enter__.return_value = session
        session.get.return_value = response
        with patch.object(live.requests, 'Session', return_value=session), patch.object(live, '_public_url') as validate:
            with self.assertRaisesRegex(ValueError, '404'): live.fetch_titles(self.row['url'])
            response.status_code = 302
            response.headers = {'Location':'http://127.0.0.1/'}
            validate.side_effect = [None, ValueError('private')]
            with self.assertRaisesRegex(ValueError, 'private'): live.fetch_titles(self.row['url'])
            self.assertEqual(validate.call_args.args[0], 'http://127.0.0.1/')

    def test_pdf_heading_can_supply_wrapped_title(self):
        with patch.object(live, 'fetch_titles', return_value=(self.row['url'], [], '多模态大模型幻觉 检测的研究进展 张三 李四')):
            self.assertEqual(live.verify(self.row)['status'], 'real')


class AuthenticityApiTests(unittest.TestCase):
    def test_live_result_available_in_audit_and_export_without_modifying_report(self):
        live._CACHE.clear()
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/'test.sqlite3')
            store.create_run('Test', {'id':'fake'}, 'duckduckgo', identifier='auth-test')
            title = '多模态大模型幻觉检测的研究进展'
            store.append_events('auth-test', [
                {'type':'sources','task_id':1,'latest_sources':f'* {title} : https://example.org/paper'},
                {'type':'final_report','report':f'# 报告\n## 正文\n没有行内引用。\n## 参考文献\n- {title}. https://example.org/paper'}])
            app = FastAPI();app.include_router(quality_api.router(store));client = TestClient(app)
            before = store.events('auth-test')
            audit = client.get('/quality/audit/auth-test').json()
            row = audit['references'][0]
            self.assertEqual(row['authenticity']['status'], 'pending')
            with patch.object(live, 'fetch_titles', return_value=('https://example.org/paper', [title], '')):
                response = client.post('/quality/verify-reference/auth-test', json={'reference_id':row['id']})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['authenticity']['status'], 'real')
            checked = client.get('/quality/audit/auth-test').json()['references'][0]
            self.assertEqual(checked['authenticity']['status'], 'real')
            self.assertFalse(checked['cited_in_body'])
            exported = client.post('/quality/report',json={'run_id':'auth-test'}).json()['markdown']
            self.assertIn('真实；正文未引用', exported)
            self.assertEqual(store.events('auth-test'), before)
            self.assertEqual(client.post('/quality/verify-reference/auth-test',json={'reference_id':'missing'}).status_code,404)


if __name__ == '__main__': unittest.main()
