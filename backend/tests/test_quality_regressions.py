import unittest

from quality import engine, parse, render


class QualityRegressionTests(unittest.TestCase):
    def test_unnumbered_references_verified_and_deduplicated(self):
        report = '# 报告\n## 正文\n正文引用 [论文甲](https://a.test/1)。\n## 参考来源\n- 论文甲 — https://a.test/1\n- [论文乙](https://b.test/2)\n- 论文甲 — https://a.test/1\n'
        sources = parse.parse_sources('* 论文甲 : https://a.test/1\n* [论文乙](https://b.test/2)')
        result = engine.audit(report, sources)
        self.assertEqual(result['metrics']['references'], 2)
        self.assertEqual(result['metrics']['inline_citations'], 1)
        self.assertTrue(all(row['verified'] for row in result['references']))
        self.assertEqual([row['cited_in_body'] for row in result['references']], [True, False])
        self.assertTrue(all(row['line'] >= 4 and row['quote'] for row in result['references']))
        self.assertTrue(all(row['number'] is None for row in result['references']))
        rendered = render.render_quality_report(result)
        self.assertIn('条目 1', rendered)
        self.assertNotIn('[None]', rendered)

    def test_reference_subheadings_inherit_until_next_sibling(self):
        report = '# 报告\n## 参考文献\n### 任务一\n- A — https://a.test/1\n### 任务二\n#### 网络论文\n- B — https://b.test/2\n## 附录\n正文链接 https://a.test/1\n'
        sections = parse.split_sections(report)
        self.assertEqual([s.is_reference for s in sections], [False, True, True, True, True, False])
        result = engine.audit(report, [])
        self.assertEqual(result['metrics']['references'], 2)
        self.assertEqual(result['metrics']['inline_citations'], 1)
        self.assertNotIn('empty_reference_section', [i['type'] for i in result['issues']])
        self.assertEqual([r['verified'] for r in result['references']], [False, False])

    def test_numbered_links_ordered_lists_and_missing_url(self):
        report = '# 报告\n## 正文\n结论[1]，其他结论[2]，未提供来源[9]。\n## References\n[1] [Paper A](https://a.test/1)\n2. Paper B — https://b.test/2\n[3] 作者，只有纸质书目信息\n'
        result = engine.audit(report, parse.parse_sources('* A : https://a.test/1\n* B : https://b.test/2'))
        refs = {r['number']: r for r in result['references']}
        self.assertEqual(result['metrics']['references'], 3)
        self.assertTrue(refs[1]['verified'] and refs[1]['cited_in_body'])
        self.assertTrue(refs[2]['verified'] and refs[2]['cited_in_body'])
        self.assertIn('missing_reference_url', refs[3]['issue_types'])
        self.assertIn('unresolved_citation_number', refs[9]['issue_types'])
        self.assertEqual([i['number'] for i in result['issues'] if i['type'] == 'unresolved_citation_number'], [9])

    def test_bold_reference_heading_and_local_reference(self):
        report = '# 报告\n正文内容。\n\n**参考文献**\n- 本地资料 — local://documents/doc-a\n- 作者. 没有链接的纸质论文[J]. 2024.\n'
        result = engine.audit(report, [], known_document_ids={'doc-a'})
        self.assertEqual(result['metrics']['references'], 2)
        self.assertTrue(result['references'][0]['verified'])
        self.assertIn('missing_reference_url', result['references'][1]['issue_types'])
        self.assertEqual(result['metrics']['inline_citations'], 0)

    def test_global_findings_have_truthful_navigation_targets(self):
        report = '# 报告\n## 背景\n有待补充来源的**具体结论**。\n## 风险\n需要在交付前核验数据。\n## 参考来源\n- 论文 — https://a.test/1\n'
        result = engine.audit(report, parse.parse_sources('* 论文 : https://a.test/1'))
        issues = {i['type']: i for i in result['issues']}
        self.assertEqual(issues['missing_conclusion']['section'], '风险')
        self.assertEqual(issues['missing_conclusion']['location_scope'], 'end')
        self.assertIn('缺少内容', issues['missing_conclusion']['location_hint'])
        self.assertIn('section', issues['no_inline_citations'])
        self.assertIn('snippet', issues['no_inline_citations'])
        self.assertTrue(all(any(key in i for key in ['line', 'snippet', 'quote', 'location_scope']) for i in result['issues']))

    def test_body_links_and_code_are_not_reference_entries(self):
        report = '# 报告\n## 正文\n1. 一般正文列表 https://a.test/1\n```md\n## 参考文献\n- Fake — https://fake.test/2\n```\n'
        result = engine.audit(report, [])
        self.assertEqual(result['metrics']['references'], 0)
        self.assertEqual(result['metrics']['inline_citations'], 1)

    def test_followup_suggestions_are_not_paper_entries(self):
        report = '# 报告\n## 参考来源\n### 任务一\n- 论文标题. https://a.test/paper\n### 后续补充检索建议\n- 定向检索 2026 年技术报告，补齐证据。\n- 检查论文的链接是否完整。\n'
        result = engine.audit(report, [])
        self.assertEqual(result['metrics']['references'], 1)
        self.assertEqual(result['references'][0]['title'], '论文标题')
        self.assertNotIn('missing_reference_url', [issue['type'] for issue in result['issues']])


if __name__ == '__main__':
    unittest.main()
