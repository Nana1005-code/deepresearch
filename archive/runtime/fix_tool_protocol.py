from pathlib import Path
root=Path.cwd()
(root/'backend/src/services/tool_protocol.py').write_text(r'''"""Parse supported text tool protocols without evaluating generated code."""
import json
import re

class ToolProtocolError(ValueError):
    pass

MARKER = re.compile(r"TOOL_CALL\s*:|<\s*[|｜]*DSML[|｜]*", re.I)
START = re.compile(r"(?:\\?[\[<])TOOL_CALL\s*:([\w.-]+):", re.I)
TAG = r"<\s*[|｜]*DSML[|｜]*\s*"
INVOKE = re.compile(TAG + r"invoke\s+name=[\"']([^\"']+)[\"']\s*>(.*?)\\?</\s*[|｜]*DSML[|｜]*\s*invoke\s*>", re.I | re.S)
PARAM = re.compile(TAG + r"parameter\s+name=[\"']([^\"']+)[\"'](?:\s+string=[\"'](true|false)[\"'])?\s*>(.*?)\\?</\s*[|｜]*DSML[|｜]*\s*parameter\s*>", re.I | re.S)


def has_tool_protocol(text):
    return bool(MARKER.search(text or ''))


def normalized_call(name, args, original):
    if not isinstance(args, dict):
        raise ToolProtocolError('工具参数必须为 JSON 对象')
    if name.startswith('note:'):
        action = name.split(':', 1)[1]
        if action not in {'read', 'create', 'update', 'list', 'search', 'delete'}:
            raise ToolProtocolError('不支持的笔记操作')
        if args.get('action', action) != action:
            raise ToolProtocolError('工具名称与 action 不一致')
        args = {**args, 'action': action}
        name = 'note'
    return dict(tool_name=name, parameters=json.dumps(args, ensure_ascii=False), original=original)


def parse_tool_calls(text):
    calls = []
    remaining = text
    # DSML invokes can contain named parameters, or the gateway's raw JSON variant.
    for match in INVOKE.finditer(text):
        body = match[2].strip()
        params = list(PARAM.finditer(body))
        try:
            if params:
                args = {}
                for param in params:
                    value = param[3].strip()
                    args[param[1]] = json.loads(value) if param[2] == 'false' else value
            else:
                args, end = json.JSONDecoder().raw_decode(body)
                tail = body[end:].strip().replace('\\', '')
                # A known gateway variant adds an unmatched closing parameter tag.
                if tail and not re.fullmatch(r'</\s*[|｜]*DSML[|｜]*\s*parameter\s*>', tail, re.I):
                    raise ValueError('extra DSML arguments')
        except (ValueError, TypeError) as exc:
            raise ToolProtocolError('DSML 工具参数不完整或无效') from exc
        calls.append(normalized_call(match[1], args, match[0]))
        remaining = remaining.replace(match[0], '', 1)
    # Remove only recognized empty DSML envelope tags, never arbitrary payloads.
    remaining = re.sub(r'\\?</?\s*[|｜]*DSML[|｜]*\s*(?:calls|function_calls)\s*>', '', remaining, flags=re.I)
    for match in list(START.finditer(remaining)):
        body = remaining[match.end():].lstrip()
        try:
            args, end = json.JSONDecoder().raw_decode(body)
        except ValueError as exc:
            raise ToolProtocolError('工具参数 JSON 不完整或无效') from exc
        tail = body[end:]
        close = re.match(r'\s*\\?[\]>]', tail)
        if not close:
            raise ToolProtocolError('工具调用缺少结束标记')
        original = match[0] + remaining[match.end():len(remaining)-len(body)] + body[:end] + close[0]
        calls.append(normalized_call(match[1], args, original))
    residue = remaining
    for call in calls:
        residue = residue.replace(call['original'], '', 1)
    if has_tool_protocol(residue):
        raise ToolProtocolError('工具调用格式无法识别，请使用标准 JSON 工具格式')
    # Duplicate renderings in the same response must not duplicate writes.
    unique = {}
    for call in calls:
        key = (call['tool_name'], json.dumps(json.loads(call['parameters']), sort_keys=True))
        unique.setdefault(key, call)
    return list(unique.values())
''',encoding='utf8')
(root/'backend/src/services/tool_agent.py').write_text('''"""Project-owned tool loop; never return a tool round as a finished document."""
from hello_agents import ToolAwareSimpleAgent
from hello_agents.core.message import Message
from services.llm import ModelOutputError
from services.tool_protocol import parse_tool_calls, has_tool_protocol, ToolProtocolError


class ResearchToolAgent(ToolAwareSimpleAgent):
    def _parse_tool_calls(self, text):
        return parse_tool_calls(text)

    def run(self, input_text, max_tool_iterations=8, **kwargs):
        messages = [{'role': 'system', 'content': self._get_enhanced_system_prompt()},
                    *[{'role': m.role, 'content': m.content} for m in self._history],
                    {'role': 'user', 'content': input_text}]
        messages[0]['content'] += ('\\n工具调用只能使用 [TOOL_CALL:note:{"action":"read","note_id":"..."}] 格式。'
                                    '不要输出 DSML。工具执行结果由系统返回；完成工具操作后必须输出正式答案。')
        for turn in range(max_tool_iterations + 1):
            final_turn = turn == max_tool_iterations
            if final_turn:
                messages.append({'role': 'user', 'content': '工具调用预算已用完。请仅基于已获得的资料输出最终正文，不再调用工具。信息不足时明确说明，不得编造。'})
            response = self.llm.invoke(messages, **kwargs)
            try:
                calls = self._parse_tool_calls(response)
            except ToolProtocolError:
                if final_turn:
                    raise ModelOutputError('模型持续返回无法解析的工具指令，未生成正式正文，请重试任务。')
                messages.append({'role': 'user', 'content': '上一轮工具调用格式错误，未执行任何操作。请用 [TOOL_CALL:note:{"action":"read","note_id":"..."}] 和完整 JSON 重发，或直接输出正式答案。'})
                continue
            if not calls:
                if has_tool_protocol(response):
                    raise ModelOutputError('模型工具指令未完成，不能作为正式正文。')
                self.add_message(Message(input_text, 'user'))
                self.add_message(Message(response, 'assistant'))
                return response
            if final_turn or not self.enable_tool_calling:
                raise ModelOutputError('模型仍在请求工具，尚未返回正式正文；请重试任务。')
            results = []
            for call in calls:
                # The registry remains the sole allowlist and executor.
                if not self.tool_registry.get_tool(call['tool_name']):
                    results.append('未执行：工具不存在，请仅使用已注册的笔记工具。')
                else:
                    results.append(self._execute_tool_call(call['tool_name'], call['parameters']))
            messages.append({'role': 'assistant', 'content': '(请求调用已注册工具)'})
            messages.append({'role': 'user', 'content': '工具执行结果：\\n' + '\\n\\n'.join(results) + '\\n请据此继续，完成后输出正式答案。'})
        raise ModelOutputError('工具调用未能生成正式正文。')

    def stream_run(self, input_text, max_tool_iterations=8, **kwargs):
        # Buffer internal rounds, consistent with the summarization service.
        yield self.run(input_text, max_tool_iterations=max_tool_iterations, **kwargs)
''',encoding='utf8')
p=root/'backend/src/agent.py';s=p.read_text(encoding='utf8');s=s.replace('from services.llm import ResearchLLM, ModelOutputError, require_text','from services.llm import ResearchLLM, ModelOutputError, require_text\nfrom services.tool_agent import ResearchToolAgent');s=s.replace('return ToolAwareSimpleAgent(', 'return ResearchToolAgent(');p.write_text(s,encoding='utf8')
p=root/'backend/src/services/text_processing.py';s=p.read_text(encoding='utf8');s=s.replace('import re','import re\nfrom services.tool_protocol import has_tool_protocol');s=s.replace('    text = strip_tool_calls(text).strip()', '    # A pending or malformed tool round is not a completed document.\n    if has_tool_protocol(text):\n        return ""\n    text = strip_tool_calls(text).strip()');p.write_text(s,encoding='utf8')
print('Patched protocol parser, bounded agent loop and final-answer guard.')
