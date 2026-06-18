"""
Async JSONL writer with background queue.

Records are serialised to JSON and written to a JSONL file via an asyncio
queue and a dedicated writer task.  This avoids blocking the LLM call path
on disk I/O.  At the end of each simulation step the queue is flushed.
"""

import asyncio
import json
import os
import time
from typing import Optional

from .config import RecordConfig


class RecordWriter:
    """Async writer for LLM-call record JSONL files.

    Usage:
        writer = RecordWriter(config)
        await writer.start()
        writer.write(record_dict)
        # ... simulation runs ...
        await writer.flush_step()  # optional — called after each sim step
        await writer.close()       # finalise meta.json
    """

    def __init__(self, config: RecordConfig):
        self._config = config
        self._queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._file = None
        self._record_count = 0
        self._step_counts: list[int] = []
        self._current_step = -1
        self._step_counter = 0

    @property
    def record_count(self) -> int:
        return self._record_count

    def open_sync(self) -> None:
        """Open the output file synchronously.

        This is called from ``enable_recording()`` (which is not async)
        to ensure the file is ready before the simulation starts.
        The async writer loop is started separately via ``start()``.
        """
        os.makedirs(self._config.output_dir, exist_ok=True)
        self._file = open(self._config.filepath, "a", encoding="utf-8")

    async def start(self) -> None:
        """Open the output file (if not already) and start the background writer task."""
        if self._file is None:
            self.open_sync()
        self._task = asyncio.create_task(self._writer_loop())

    async def write(self, record: dict) -> None:
        """Enqueue a record dict for writing (non-blocking)."""
        self._record_count += 1
        self._step_counter += 1
        self._queue.put_nowait(record)

    async def step_boundary(self, step: int) -> None:
        """Mark a step boundary — triggers flush and records step counts.

        Must be called at the *end* of each simulation step (i.e. before the
        next step's LLM calls begin).
        """
        # Flush any remaining records
        await self._flush()
        # Ensure we've accounted for steps with zero LLM calls
        while len(self._step_counts) <= step:
            self._step_counts.append(0)
        self._step_counts[step] = self._step_counter
        self._step_counter = 0
        self._current_step = step

    async def close(self) -> None:
        """Flush remaining records, stop the writer, and write meta.json."""
        await self._flush()
        if self._task is not None:
            self._queue.put_nowait(None)  # Sentinel to stop
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        if self._file is not None:
            self._file.close()
            self._file = None
        await self._write_meta()

    async def _flush(self) -> None:
        """Drain the queue synchronously (for step-boundary flushes)."""
        # Process items already in the queue
        while not self._queue.empty():
            item = self._queue.get_nowait()
            if item is not None and self._file is not None:
                self._file.write(json.dumps(item, ensure_ascii=False) + "\n")
                self._file.flush()
                self._queue.task_done()

    async def _writer_loop(self) -> None:
        """Background loop that drains the queue to the file."""
        try:
            while True:
                item = await self._queue.get()
                if item is None:
                    break
                if self._file is not None:
                    self._file.write(json.dumps(item, ensure_ascii=False) + "\n")
                    self._file.flush()
                self._queue.task_done()
        except asyncio.CancelledError:
            pass

    def _build_meta(self) -> dict:
        """Build the meta dict (shared by sync and async write)."""
        return {
            "scenario": self._config.scenario,
            "n_agents": self._config.n_agents,
            "n_steps": self._config.n_steps,
            "rng_seed": self._config.rng_seed,
            "agent_classes": [],
            "attitude_topics": [],
            "agentsociety_commit": self._config.agentsociety_commit,
            "record_concurrency": self._config.record_concurrency,
            "record_llm": {
                "provider": self._config.record_llm_provider,
                "model": self._config.record_llm_model,
            },
            "total_records": self._record_count,
            "step_record_counts": self._step_counts,
            **self._config.extra_meta,
        }

    def _write_meta_sync(self) -> None:
        """Synchronously write meta.json (used by disable_recording)."""
        meta = self._build_meta()
        os.makedirs(os.path.dirname(self._config.meta_filepath), exist_ok=True)
        with open(self._config.meta_filepath, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    async def _write_meta(self) -> None:
        """Async write meta.json."""
        self._write_meta_sync()
