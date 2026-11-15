import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from research_square.store import ResearchSquareStore
from research_square.gaps import resolve, candidates

ROWS=[dict(id='concept-llm',public_id='concept-llm',name='大语言模型',aliases=['LLM'],research_count=2),
      dict(id='concept-mllm',public_id='concept-mllm',name='多模态大模型',aliases=['MLLM'],research_count=1),
      dict(id=3,public_id='topic-3',name='幻觉检测',aliases=[],research_count=1)]

class GapTopicTests(unittest.TestCase):
    def test_names_aliases_and_word_boundaries(self):
        for name,expected in [('大语言模型','concept-llm'),('LLM','concept-llm'),('多模态大模型','concept-mllm'),('MLLM','concept-mllm'),('幻觉检测',3)]:
            self.assertEqual(resolve(f'从我的研究历史来看，{name}还有哪些相关主题是我遗漏的？',ROWS)[0]['id'],expected)
        self.assertEqual(resolve('unknownxyz',ROWS),[])
        self.assertEqual(resolve('smallllmword',ROWS),[])

    def test_concepts_and_original_topics_share_real_paper_membership(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=ResearchSquareStore(str(Path(tmp)/'square.sqlite3'))
            sql="SELECT 'concept-llm' node,1 work UNION ALL SELECT 'concept-llm',2 UNION ALL SELECT 'concept-mllm',1 UNION ALL SELECT 3,1"
            with patch('research_square.gaps.catalog',return_value=ROWS),patch('research_square.gaps.membership',return_value=sql):
                result=candidates(store,'大语言模型还有哪些遗漏方向？')
                self.assertEqual(result['matched_topics'],['大语言模型'])
                self.assertEqual({r['public_id'] for r in result['suggestions']},{'concept-mllm','topic-3'})
                self.assertTrue(all(r['cooccurrence_count']==1 and r['my_research_count']==0 for r in result['suggestions']))
                self.assertEqual(candidates(store,'不存在的节点')['error'],'missing_topic')
