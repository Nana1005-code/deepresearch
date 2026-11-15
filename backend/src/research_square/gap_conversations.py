"""Local, isolated history for the research-gap assistant."""
import json
from threading import RLock
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from .schemas import ChatInput
from .store import utcnow


def router(store, answer, source="local"):
    if source not in {"local", "openalex"}:
        raise ValueError("Invalid conversation source")
    table = "gap_conversations" if source == "local" else "academic_conversations"
    api = APIRouter(prefix="/gap-conversations" if source == "local" else "/academic-conversations")
    lock = RLock()
    with store.connect() as db:
        db.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        for row in db.execute(f"SELECT id,data FROM {table}").fetchall():
            item = json.loads(row["data"])
            if item["status"] == "running":
                item.update(status="idle", error="上次分析因服务重启而中断，请重新提问。")
                db.execute(f"UPDATE {table} SET data=? WHERE id=?", (json.dumps(item, ensure_ascii=False), row["id"]))

    def find(identifier):
        with store.connect() as db:
            row = db.execute(f"SELECT data FROM {table} WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise HTTPException(404, "遗漏助手对话不存在")
        item = json.loads(row["data"])
        with store.connect() as db:
            for message in item["messages"]:
                for suggestion in message.get("suggestions", []):
                    if not suggestion.get("public_id"):
                        topic = db.execute("SELECT public_id FROM openalex_canonical_topics WHERE canonical_name_zh=? AND status='active'", (suggestion["name"],)).fetchone()
                        if topic: suggestion["public_id"] = topic[0]
        return item

    def save(item):
        with store.connect() as db:
            db.execute(f"INSERT OR REPLACE INTO {table} VALUES (?,?)", (item["id"], json.dumps(item, ensure_ascii=False)))

    @api.get("")
    def history():
        with store.connect() as db:
            items = [json.loads(row["data"]) for row in db.execute(f"SELECT data FROM {table}")]
        return sorted([
            {"id": item["id"], "title": item["title"], "updated_at": item["updated_at"],
             "message_count": len(item["messages"]), "status": item["status"],
             "preview": next((m["content"][:80] for m in reversed(item["messages"]) if m["role"] == "user"), "")}
            for item in items
        ], key=lambda item: item["updated_at"], reverse=True)

    @api.post("", status_code=201)
    def create():
        timestamp = utcnow()
        item = {"id": uuid4().hex, "title": "新对话", "created_at": timestamp, "updated_at": timestamp,
                "messages": [], "status": "idle", "error": None}
        with lock:
            save(item)
        return item

    @api.get("/{identifier}")
    def detail(identifier: str):
        return find(identifier)

    @api.delete("/{identifier}", status_code=204)
    def delete(identifier: str):
        with lock:
            if find(identifier)["status"] == "running":
                raise HTTPException(409, "正在分析，请完成后再删除对话")
            with store.connect() as db:
                db.execute(f"DELETE FROM {table} WHERE id=?", (identifier,))

    @api.post("/{identifier}/messages")
    def send(identifier: str, payload: ChatInput):
        question = payload.question.strip()
        if not question or payload.data_source != source:
            raise HTTPException(422, "请输入研究问题，并使用当前助手的数据来源")
        with lock:
            item = find(identifier)
            if item["status"] == "running":
                raise HTTPException(409, "正在分析，请勿重复发送")
            if not item["messages"]:
                item["title"] = question[:36]
            item["messages"].append({"role": "user", "content": question})
            item.update(status="running", error=None, updated_at=utcnow())
            save(item)
        try:
            result = answer(payload.model_copy(update={"question": question}))
            message = {"role": "assistant", "content": result["answer"], "plan": result.get("plan"),
                       "suggestions": [
                           {key: suggestion[key] for key in ("public_id", "name", "cooccurrence_count", "my_research_count") if key in suggestion}
                           for suggestion in result.get("data", {}).get("suggestions", [])[:10]
                       ]}
            with lock:
                item = find(identifier)
                item["messages"].append(message)
                item.update(status="idle", error=None, updated_at=utcnow())
                save(item)
        except Exception:
            with lock:
                item = find(identifier)
                item.update(status="idle", error="分析失败，请稍后重新发送。", updated_at=utcnow())
                save(item)
        return item

    return api
