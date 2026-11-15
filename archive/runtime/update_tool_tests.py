from pathlib import Path
p=Path('backend/tests/test_tool_protocol.py');s=p.read_text(encoding='utf-8-sig').replace("registry=Mock();registry.get_tool.return_value=Mock()", "registry=Mock();registry.get_tool.return_value=Mock();registry.get_tools_description.return_value='note: JSON parameters'")
s=s.replace(' def test_user_angle_variant(self):', ''' def test_plain_parameter_tags_inside_dsml(self):
  text='<｜｜DSML｜｜ calls><｜｜DSML｜｜ invoke name="note"><parameter name="action">read</parameter><parameter name="note_id">n1</parameter></｜｜DSML｜｜ invoke></｜｜DSML｜｜ calls>'
  self.assertEqual(json.loads(parse_tool_calls(text)[0]['parameters']),{'action':'read','note_id':'n1'})
 def test_user_angle_variant(self):''');p.write_text(s,encoding='utf8')
p=Path('backend/src/services/tool_protocol.py');s=p.read_text();s=s.replace('PARAM = re.compile(TAG +', 'PARAM = re.compile(r"(?:" + TAG + r"|<\\s*)" +');s=s.replace("(.*?)\\\\?</\\s*[|｜]*DSML[|｜]*\\s*parameter", "(.*?)\\\\?</\\s*(?:[|｜]*DSML[|｜]*\\s*)?parameter");p.write_text(s,encoding='utf8')
