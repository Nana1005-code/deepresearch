"""Project-owned tool loop; never return a tool round as a finished document."""
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
        messages[0]['content'] += ('\n工具调用只能使用 [TOOL_CALL:note:{"action":"read","note_id":"..."}] 格式。'
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
            messages.append({'role': 'user', 'content': '工具执行结果：\n' + '\n\n'.join(results) + '\n请据此继续，完成后输出正式答案。'})
        raise ModelOutputError('工具调用未能生成正式正文。')

    def stream_run(self, input_text, max_tool_iterations=8, **kwargs):
        # Buffer internal rounds, consistent with the summarization service.
        yield self.run(input_text, max_tool_iterations=max_tool_iterations, **kwargs)
