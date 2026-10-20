"""Asynchronous task manager: queue, progress, cancellation, history.

Every long-running operation (PDF processing and media downloads) runs as a
task. Tasks are executed on the asyncio loop (media) or in worker threads
(CPU-bound PDF work via `asyncio.to_thread`), report progress into a
`TaskRecord`, can be cancelled (cooperative flag + subprocess termination),
and are archived into a bounded JSON history file.
"""
from __future__ import annotations

import asyncio
import shutil
import threading
import traceback
from pathlib import Path
from typing import Any, Awaitable, Callable

from .utils import new_id, now_iso

TERMINAL = {"completed", "failed", "cancelled"}
LOG_CAP = 400


class TaskCancelled(Exception):
    """Raised inside a runner when the user requested cancellation."""


class TaskRecord:
    __slots__ = (
        "id", "kind", "title", "status", "progress", "stage", "message",
        "error", "result", "log", "meta", "created_at", "started_at",
        "finished_at", "async_task", "cancel_event", "process", "temp_dir",
    )

    def __init__(self, kind: str, title: str, meta: dict | None = None,
                 temp_dir: Path | None = None):
        self.id = new_id()
        self.kind = kind
        self.title = title
        self.status = "queued"
        self.progress: float | None = None
        self.stage = "Queued"
        self.message = ""
        self.error = ""
        self.result: dict = {}
        self.log: list[str] = []
        self.meta = meta or {}
        self.created_at = now_iso()
        self.started_at: str | None = None
        self.finished_at: str | None = None
        # runtime-only (never serialized)
        self.async_task: asyncio.Task | None = None
        self.cancel_event = threading.Event()
        self.process: Any = None          # running subprocess handle (media)
        self.temp_dir: Path | None = temp_dir

    # ------------------------------------------------------------- helpers
    def add_log(self, line: str) -> None:
        line = (line or "").rstrip()
        if not line:
            return
        self.log.append(line[:500])
        if len(self.log) > LOG_CAP:
            del self.log[: len(self.log) - LOG_CAP]

    def report(self, stage: str, progress: float | None = None) -> None:
        self.stage = stage
        if progress is not None:
            self.progress = max(0.0, min(1.0, float(progress)))

    def public(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "message": self.message,
            "error": self.error,
            "result": self.result,
            "log_tail": self.log[-60:],
            "meta": self.meta,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


def check_cancel(rec: TaskRecord) -> None:
    """Cooperative cancellation point for runner code (thread-safe)."""
    if rec.cancel_event.is_set():
        raise TaskCancelled("Cancelled by user")


class TaskManager:
    def __init__(self, history_path: Path, history_limit: int, max_concurrent: int):
        self.history_path = history_path
        self.history_limit = max(5, int(history_limit))
        self.sem = asyncio.Semaphore(max(1, int(max_concurrent)))
        self.tasks: dict[str, TaskRecord] = {}
        self.history: list[dict] = []
        self._load_history()

    # ------------------------------------------------------------- history
    def _load_history(self) -> None:
        try:
            if self.history_path.exists():
                raw = self.history_path.read_text(encoding="utf-8")
                import json
                data = json.loads(raw)
                if isinstance(data, list):
                    self.history = [d for d in data if isinstance(d, dict)]
        except Exception:
            self.history = []

    def _archive(self, rec: TaskRecord) -> None:
        entry = rec.public()
        entry.pop("log_tail", None)
        self.history.insert(0, entry)
        del self.history[self.history_limit:]
        try:
            import json
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.write_text(
                json.dumps(self.history[:self.history_limit], indent=1, ensure_ascii=False),
                encoding="utf-8")
        except Exception:
            pass

    # -------------------------------------------------------------- submit
    def submit(
        self,
        kind: str,
        title: str,
        runner: Callable[[TaskRecord], Awaitable[dict]],
        meta: dict | None = None,
        temp_dir: Path | None = None,
    ) -> str:
        rec = TaskRecord(kind, title, meta=meta, temp_dir=temp_dir)
        self.tasks[rec.id] = rec
        rec.async_task = asyncio.get_running_loop().create_task(self._wrap(rec, runner))
        return rec.id

    async def _wrap(self, rec: TaskRecord, runner: Callable[[TaskRecord], Awaitable[dict]]):
        try:
            async with self.sem:
                if rec.cancel_event.is_set():
                    rec.status = "cancelled"
                    rec.stage = "Cancelled"
                    rec.finished_at = now_iso()
                    return
                rec.status = "running"
                rec.started_at = now_iso()
                rec.report("Starting")
                result = await runner(rec) or {}
                outputs = result.get("outputs", []) or []
                for out in outputs:
                    p = Path(out.get("path", ""))
                    if not p.is_file() or p.stat().st_size <= 0:
                        raise RuntimeError(f"Output validation failed: '{out.get('name')}' is missing or empty")
                rec.result = result
                rec.status = "completed"
                rec.progress = 1.0
                rec.stage = "Completed"
        except TaskCancelled:
            rec.status = "cancelled"
            rec.stage = "Cancelled"
        except asyncio.CancelledError:
            rec.status = "cancelled" if rec.cancel_event.is_set() else "failed"
            rec.error = rec.error or ("Task was cancelled." if rec.status == "cancelled"
                                      else "Task interrupted unexpectedly.")
            rec.stage = "Cancelled" if rec.status == "cancelled" else "Failed"
        except Exception as exc:  # noqa: BLE001 - boundary of task execution
            rec.add_log(f"ERROR: {exc}")
            rec.add_log(traceback.format_exc(limit=8))
            rec.status = "failed"
            rec.error = str(exc) or exc.__class__.__name__
            rec.stage = "Failed"
        finally:
            rec.finished_at = rec.finished_at or now_iso()
            rec.process = None
            rec.async_task = None
            if rec.temp_dir:
                shutil.rmtree(rec.temp_dir, ignore_errors=True)
            self._archive(rec)

    # -------------------------------------------------------------- cancel
    def cancel(self, task_id: str) -> bool:
        rec = self.tasks.get(task_id)
        if rec is None or rec.status in TERMINAL:
            return False
        rec.cancel_event.set()
        rec.message = "Cancellation requested"
        if rec.status == "queued":
            rec.status = "cancelled"
            rec.stage = "Cancelled"
        proc = rec.process
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
        if rec.async_task is not None:
            rec.async_task.cancel()
        return True

    def remove(self, task_id: str) -> bool:
        """Remove a finished task from memory + history."""
        rec = self.tasks.pop(task_id, None)
        if rec is not None and rec.status not in TERMINAL:
            return False  # refuse to forget running tasks; cancel first
        before = len(self.history)
        self.history = [h for h in self.history if h.get("id") != task_id]
        if len(self.history) != before:
            try:
                import json
                self.history_path.write_text(
                    json.dumps(self.history, indent=1, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        return True

    # ---------------------------------------------------------------- list
    def list_tasks(self, limit: int = 50, status: str | None = None,
                   kind: str | None = None) -> list[dict]:
        items: list[dict] = [r.public() for r in self.tasks.values()]
        known = {i["id"] for i in items}
        items.extend(h for h in self.history if h.get("id") not in known)
        if status:
            items = [i for i in items if i["status"] == status]
        if kind:
            items = [i for i in items if i["kind"] == kind]
        items.sort(key=lambda i: i.get("created_at") or "", reverse=True)
        return items[: max(1, min(int(limit), 500))]

    def get(self, task_id: str) -> TaskRecord | None:
        return self.tasks.get(task_id)

    async def shutdown(self) -> None:
        """Terminate running subprocesses and cancel tasks on app shutdown."""
        for rec in list(self.tasks.values()):
            if rec.status in ("queued", "running"):
                rec.cancel_event.set()
                proc = rec.process
                if proc is not None:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                if rec.async_task is not None:
                    rec.async_task.cancel()
