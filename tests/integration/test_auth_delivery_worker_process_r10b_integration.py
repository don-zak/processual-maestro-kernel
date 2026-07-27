from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_real_process_finishes_active_batch_after_sigterm(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    lifecycle_path = tmp_path / "worker-lifecycle.jsonl"
    child_path = tmp_path / "auth_r10b_worker_child.py"

    child_source = textwrap.dedent(
        """
        from __future__ import annotations

        import asyncio
        import json
        import os
        import signal
        import sys
        from pathlib import Path
        from types import SimpleNamespace

        import processual_api.auth.delivery_worker as worker_module
        from processual_api.auth.delivery_worker import (
            run_continuous,
        )


        lifecycle_path = Path(sys.argv[1])


        def record(event: str, **values: object) -> None:
            payload = {
                "event": event,
                **values,
            }
            with lifecycle_path.open(
                "a",
                encoding="utf-8",
                newline="\\n",
            ) as stream:
                stream.write(
                    json.dumps(
                        payload,
                        sort_keys=True,
                    )
                    + "\\n"
                )
                stream.flush()
                os.fsync(stream.fileno())


        async def fake_init_db() -> None:
            record("db_initialized")


        async def fake_close_db() -> None:
            record("db_closed")


        class SignalDuringActiveBatchDispatcher:
            def __init__(self) -> None:
                self.calls = 0

            async def dispatch_once(self):
                self.calls += 1

                if self.calls != 1:
                    raise AssertionError(
                        "Worker started a second batch "
                        "after SIGTERM."
                    )

                record(
                    "batch_started",
                    call=self.calls,
                )

                loop = asyncio.get_running_loop()
                loop.call_later(
                    0.05,
                    signal.raise_signal,
                    signal.SIGTERM,
                )

                await asyncio.sleep(0.20)

                record(
                    "batch_completed",
                    call=self.calls,
                )

                return SimpleNamespace(
                    claimed=3,
                    delivered=2,
                    retry_scheduled=1,
                    dead_lettered=0,
                    stale_finalization=0,
                )


        async def main() -> int:
            dispatcher = (
                SignalDuringActiveBatchDispatcher()
            )

            worker_module.init_db = fake_init_db
            worker_module.close_db = fake_close_db

            record(
                "child_started",
                pid=os.getpid(),
            )

            result = await run_continuous(
                poll_interval_seconds=0.05,
                runtime_factory=lambda: SimpleNamespace(
                    dispatcher=dispatcher,
                ),
            )

            record(
                "worker_returned",
                batches=result.batches,
                claimed=result.claimed,
                delivered=result.delivered,
                retry_scheduled=(
                    result.retry_scheduled
                ),
                dead_lettered=result.dead_lettered,
                stale_finalization=(
                    result.stale_finalization
                ),
                dispatcher_calls=dispatcher.calls,
            )

            print(
                json.dumps(
                    result.as_dict(),
                    sort_keys=True,
                ),
                flush=True,
            )

            return 0


        raise SystemExit(asyncio.run(main()))
        """
    )

    child_path.write_text(
        child_source,
        encoding="utf-8",
        newline="\n",
    )

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repo_root)

    environment.update(
        {
            "MAESTRO_ADMIN_EMAIL": ("auth-r10b-admin@example.test"),
            "MAESTRO_ADMIN_PASSWORD": ("Auth-R10B-Test-Password-9f2d7a4c1e8b6f3d"),
            "JWT_SECRET": (
                "auth-r10b-test-jwt-secret-"
                "7c7e8c06d1464f318d9d875504af8979"
            ),
            "API_KEYS": (
                "auth-r10b-test-api-key-"
                "97b19e4a802648ee902bac98926657dd"
            ),
            "DATABASE_URL": (
                "postgresql+asyncpg://processual_r10b:"
                "Auth-R10B-Postgres-Password-"
                "952d4f7bc03c47a5b8062c4465394401"
                "@127.0.0.1:5432/processual_auth_r10b"
            ),
            "POSTGRES_PASSWORD": (
                "Auth-R10B-Postgres-Password-"
                "952d4f7bc03c47a5b8062c4465394401"
            ),
            "REDIS_PASSWORD": (
                "Auth-R10B-Redis-Password-"
                "4af93a7c49ee440fb65df9bc27d59141"
            ),
            "GRAFANA_ADMIN_PASSWORD": (
                "Auth-R10B-Grafana-Password-"
                "4e1f910fa93c4593a8a862a39c8b017f"
            ),
            "REDIS_URL": ("redis://auth-r10b:5d8c1f4a9e2b7d6c@127.0.0.1:6379/15"),
        }
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(child_path),
            str(lifecycle_path),
        ],
        cwd=repo_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0, (
        f"Worker child process failed.\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )

    stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]

    assert stdout_lines

    result = json.loads(stdout_lines[-1])

    assert result == {
        "batches": 1,
        "claimed": 3,
        "delivered": 2,
        "retry_scheduled": 1,
        "dead_lettered": 0,
        "stale_finalization": 0,
    }

    lifecycle = [
        json.loads(line)
        for line in lifecycle_path.read_text(
            encoding="utf-8",
        ).splitlines()
        if line.strip()
    ]

    events = [entry["event"] for entry in lifecycle]

    assert events == [
        "child_started",
        "db_initialized",
        "batch_started",
        "batch_completed",
        "db_closed",
        "worker_returned",
    ]

    child_started = lifecycle[0]
    returned = lifecycle[-1]

    assert isinstance(child_started["pid"], int)
    assert child_started["pid"] > 0

    assert returned == {
        "event": "worker_returned",
        "batches": 1,
        "claimed": 3,
        "delivered": 2,
        "retry_scheduled": 1,
        "dead_lettered": 0,
        "stale_finalization": 0,
        "dispatcher_calls": 1,
    }

    assert completed.stderr == ""
