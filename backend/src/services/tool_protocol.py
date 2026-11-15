"""Parse supported text tool protocols without evaluating generated code."""
import json
import re

class ToolProtocolError(ValueError):
    pass

MARKER = re.compile(r"TOOL_CALL\s*:|<\s*[|｜]*DSML[|｜]*", re.I)
START = re.compile(r"(?:\\?[\[<])TOOL_CALL\s*:([\w.-]+):", re.I)
TAG = r"<\s*[|｜]*DSML[|｜]*\s*"
INVOKE = re.compile(TAG + r"invoke\s+name=[\"']([^\"']+)[\"']\s*>(.*?)\\?</\s*[|｜]*DSML[|｜]*\s*invoke\s*>", re.I | re.S)
PARAM = re.compile(r"(?:" + TAG + r"|<\s*)" + r"parameter\s+name=[\"']([^\"']+)[\"'](?:\s+string=[\"'](true|false)[\"'])?\s*>(.*?)\\?</\s*(?:[|｜]*DSML[|｜]*\s*)?parameter\s*>", re.I | re.S)


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
