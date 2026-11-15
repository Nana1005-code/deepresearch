import unittest

from quality import engine, parse, render


class RetrievedSourceMatchingTests(unittest.TestCase):
    def audit(self, title, short, sources):
        return engine.audit(f"# 报告\n## 分析\n正文证据[1]。\n## 参考文献\n[1] {title}. {short}", parse.parse_sources(sources))

    def test_truncated_urls_match_recorded_titles_without_being_declared_valid(self):
        cases = [
            ("圆满落幕丨2026 具身感知融合与多模态大模型创新研讨会 | 盖世汽车", "圆满落幕丨2026具身感知融合与多模态大模型创新研讨会 | 盖世汽车", "https://www.gasgoo.com/robot/news/70472097", "https://www.gasgoo.com/robot/news/70472097-%E5%9C%86%E6%BB%A1"),
            ("智源研究院院长王仲远：至少 5-10 年，具身智能模型才能成熟落地｜钛媒体 AGI", "智源研究院院长王仲远：至少5-10年，具身智能模型才能成熟落地｜钛媒体AGI | 学习AIGC", "https://www.xuexiaigc.com/aigcnews/", "https://www.xuexiaigc.com/aigcnews/article-title"),
            ("具身跃迁 生态共荣丨2025 全球具身智能机器人前沿技术与产业生态合作大会隆重举办 | 珞石机器人 ROKAE", "具身跃迁 生态共荣丨2025全球具身智能机器人前沿技术与产业生态合作大会隆重举办_珞石机器人ROKAE,新一代智能机器人专家", "https://www.rokae.com/cn/news/show/2380/", "https://www.rokae.com/cn/news/show/2380/article-title.html"),
        ]
        for title, source_title, short, full in cases:
            with self.subTest(short=short):
                result = self.audit(title, short, f"* {source_title} : {full}")
                self.assertEqual(result['metrics']['unverified'], 0)
                self.assertEqual(result['metrics']['verified'], 1)
                self.assertEqual(result['metrics']['uncited'], 0)
                ref = result['references'][0]
                self.assertTrue(ref['verified'] and ref['cited_in_body'])
                self.assertEqual(ref['url'], short)  # Original navigation stays intact.
                self.assertEqual(ref['matched_url'], full)
                self.assertEqual(ref['issue_types'], ['reference_url_mismatch'])
                warnings = [i for i in result['issues'] if i['type'] == 'reference_url_mismatch']
                self.assertEqual(len(warnings), 1)
                self.assertEqual(warnings[0]['severity'], 'warn')
                self.assertEqual(result['sources'][0]['url'], full)
                self.assertIn('链接待修正', render.render_quality_report(result))
                self.assertNotIn('疑似编造', render.render_quality_report(result))

    def test_nearby_titles_different_hosts_queries_ids_and_ambiguous_matches_are_rejected(self):
        title = '多模态大模型在复杂任务中进行幻觉检测的实验研究'
        short = 'https://a.test/news/123'
        cases = [
            f'* {title} : https://b.test/news/123/article',
            f'* {title}的补充研究 : https://a.test/news/123/article',
            f'* {title} : https://a.test/news/1234/article',
            f'* {title} : https://a.test/news/123/article?edition=2',
            f'* {title} : https://a.test/news/456/article',
            f'* {title} : https://a.test/news/123/article\n* {title} : https://a.test/news/456/article',
        ]
        for sources in cases:
            with self.subTest(sources=sources):
                result = self.audit(title, short, sources)
                self.assertEqual(result['metrics']['unverified'], 1)
                self.assertIsNone(result['references'][0]['matched_url'])

    def test_short_generic_title_cannot_verify_directory_url(self):
        result = self.audit('研究进展', 'https://a.test/news/', '* 研究进展 : https://a.test/news/123')
        self.assertEqual(result['metrics']['unverified'], 1)

    def test_exact_url_still_matches_without_title_or_repair_warning(self):
        result = self.audit('论文', 'https://www.a.test/paper?utm_source=x', '* Source : http://a.test/paper')
        self.assertEqual(result['metrics']['unverified'], 0)
        self.assertEqual(result['references'][0]['issue_types'], [])
        self.assertIsNone(result['references'][0]['matched_url'])


if __name__ == '__main__':
    unittest.main()
