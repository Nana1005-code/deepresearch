from __future__ import annotations

from threading import Event, Lock, Thread

from .community_extractor import extract_and_attach
from .store import ResearchSquareStore


class ResearchImportQueue:
    """Single-worker, SQLite-backed queue for local graph imports."""

    def __init__(self, existing_store, square_store: ResearchSquareStore):
        self.existing_store = existing_store
        self.square_store = square_store
        self.wake = Event()
        self.stop_event = Event()
        self.lock = Lock()
        self.thread: Thread | None = None

    def start(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            self.square_store.recover_import_jobs()
            self.stop_event.clear()
            self.thread = Thread(target=self._run, name="research-import-queue", daemon=True)
            self.thread.start()
            self.wake.set()

    def stop(self):
        self.stop_event.set(); self.wake.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)

    def notify(self):
        self.wake.set()

    def _run(self):
        while not self.stop_event.is_set():
            job = self.square_store.claim_next_import_job()
            if not job:
                self.wake.clear()
                self.wake.wait(timeout=2)
                continue
            self._process(job)

    def _process(self, job: dict):
        item = None
        try:
            run = self.existing_store.run(job["source_run_id"])
            research_input = " ".join(str(run.get("topic") or run.get("title") or "").split()).strip()
            if not research_input:
                raise ValueError("研究题目为空")
            profile = (self.existing_store.profile(job["model_profile_id"])
                       if job.get("model_profile_id") else run.get("profile"))
            if not profile:
                raise ValueError("没有可用的模型配置")
            item = self.square_store.publish(
                source_run_id=job["source_run_id"], owner_public_id="local-user",
                domain_slug="general", title=research_input[:240], summary=research_input,
                report=None, topics=[], anonymous=True, research_input=research_input,
                data_origin="user", extraction_status="pending", create_initial_topics=False,
                research_started_at=run.get("created_at"),
            )
            extract_and_attach(self.square_store, item["public_id"], research_input, profile)
            self.square_store.finish_import_job(job["public_id"], status="completed",
                                                research_public_id=item["public_id"])
        except Exception as exc:
            if item:
                self.square_store.replace_research_concepts(item["public_id"], [],
                    extraction_status="failed", extraction_error=str(exc)[:500])
            self.square_store.finish_import_job(job["public_id"], status="failed", error=str(exc)[:500])
