import sys,json,unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from services.tool_protocol import parse_tool_calls,ToolProtocolError
from services.tool_agent import ResearchToolAgent
from services.text_processing import public_answer
from services.llm import ModelOutputError

DSML='<｜｜DSML｜｜ calls> <｜｜DSML｜｜ invoke name="note:read"> {"action":"read","note_id":"n1"}\\</｜｜DSML｜｜ parameter> \\</｜｜DSML｜｜ invoke> \\</｜｜DSML｜｜ calls>'
CALL='[TOOL_CALL:note:{"action":"read","note_id":"n1"}]'
class ProtocolTests(unittest.TestCase):
 def test_user_dsml_variant(self):
  call=parse_tool_calls(DSML)[0];self.assertEqual(call['tool_name'],'note');self.assertEqual(json.loads(call['parameters'])['note_id'],'n1')
 def test_plain_parameter_tags_inside_dsml(self):
  text='<｜｜DSML｜｜ calls><｜｜DSML｜｜ invoke name="note"><parameter name="action">read</parameter><parameter name="note_id">n1</parameter></｜｜DSML｜｜ invoke></｜｜DSML｜｜ calls>'
  self.assertEqual(json.loads(parse_tool_calls(text)[0]['parameters']),{'action':'read','note_id':'n1'})
 def test_user_angle_variant(self):
  self.assertEqual(len(parse_tool_calls('\\<TOOL_CALL:note:{"action":"read","note_id":"n1"}]')),1)
 def test_named_dsml_parameters(self):
  text='<｜DSML｜function_calls><｜DSML｜invoke name="note"><｜DSML｜parameter name="action" string="true">read</｜DSML｜parameter><｜DSML｜parameter name="note_id" string="true">n1</｜DSML｜parameter></｜DSML｜invoke></｜DSML｜function_calls>'
  self.assertEqual(json.loads(parse_tool_calls(text)[0]['parameters']),{'action':'read','note_id':'n1'})
 def test_arrays_brackets_and_backslashes(self):
  data={'action':'update','note_id':'n1','tags':['one','two'],'content':'[1] and "quoted" and C:\\test\\'}
  text='[TOOL_CALL:note:'+json.dumps(data)+']'
  call=parse_tool_calls(text)[0];self.assertEqual(json.loads(call['parameters']),data);self.assertEqual(call['original'],text)
 def test_incomplete_or_conflicting_input_rejected(self):
  for text in ['[TOOL_CALL:note:{"action":"read"}', '<｜DSML｜invoke name="note">oops',DSML.replace('"read","note_id"','"update","note_id"')]:
   with self.subTest(text=text),self.assertRaises(ToolProtocolError):parse_tool_calls(text)
 def test_duplicate_formats_execute_once(self):
  self.assertEqual(len(parse_tool_calls(DSML+'\n'+CALL)),1)
 def test_public_output_rejects_leaked_protocol(self):
  for text in [DSML,'\\<TOOL_CALL:note:{"action":"read"}]',CALL,'# 任务总结\n'+DSML]:self.assertEqual(public_answer(text),'')
 def agent(self,outputs):
  llm=Mock();llm.invoke.side_effect=outputs
  registry=Mock();registry.get_tool.return_value=Mock();registry.get_tools_description.return_value='note: JSON parameters';registry.get_tools_description.return_value='note: JSON parameters'
  agent=ResearchToolAgent(name='test',llm=llm,tool_registry=registry)
  agent._execute_tool_call=Mock(return_value='笔记正文：XQ-8472')
  return agent
 def test_tool_round_executes_and_context_reaches_final(self):
  a=self.agent([DSML,'<final_answer># 任务总结\nXQ-8472</final_answer>']);result=a.run('summarize')
  a._execute_tool_call.assert_called_once();self.assertIn('XQ-8472',result)
  self.assertTrue(any('笔记正文：XQ-8472' in x['content'] for x in a.llm.invoke.call_args.args[0]))
 def test_more_than_three_rounds(self):
  a=self.agent([CALL]*4+['# 任务总结\n真正的正文']);self.assertIn('真正',a.run('summarize'));self.assertEqual(a._execute_tool_call.call_count,4)
 def test_budget_exhaustion_does_not_return_tool_text(self):
  a=self.agent([CALL]*4)
  with self.assertRaises(ModelOutputError):a.run('summarize',max_tool_iterations=3)
  self.assertEqual(a._execute_tool_call.call_count,3)
 def test_malformed_call_gets_correction_without_execution(self):
  a=self.agent(['[TOOL_CALL:note:{"action":',CALL,'# 任务总结\n正文']);self.assertIn('正文',a.run('summarize'));a._execute_tool_call.assert_called_once()
 def test_unknown_tool_never_executed(self):
  a=self.agent(['[TOOL_CALL:shell:{"command":"bad"}]','# 任务总结\n资料不足']);a.tool_registry.get_tool.return_value=None;a.run('summarize');a._execute_tool_call.assert_not_called()
 def test_stream_does_not_leak_intermediate_round(self):
  a=self.agent([DSML,'# 任务总结\n正文']);self.assertEqual(list(a.stream_run('summarize')),['# 任务总结\n正文'])
if __name__=='__main__':unittest.main()
