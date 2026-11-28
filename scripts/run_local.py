import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
FRONTEND_PORT = 3000
BACKEND_PORT = 8000
FRONTEND_URL = f"http://{HOST}:{FRONTEND_PORT}"
BACKEND_URL = f"http://{HOST}:{BACKEND_PORT}"
WINDOWS = os.name == "nt"


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if WINDOWS:
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        if process.poll() is not None:
            return
        if WINDOWS:
            subprocess.run(
                ["taskkill", "/pid", str(process.pid), "/t", "/f"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def main() -> int:
    python = ROOT / "backend" / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
    next_cli = ROOT / "frontend" / "node_modules" / "next" / "dist" / "bin" / "next"
    node = shutil.which("node")
    if not python.is_file() or not next_cli.is_file() or node is None:
        print("Install the backend and frontend dependencies using the README, then retry.", file=sys.stderr)
        return 1

    backend_env = {
        **os.environ,
        "FACULTY_AI_ALLOWED_ORIGINS": f"{FRONTEND_URL},http://localhost:{FRONTEND_PORT}",
    }
    frontend_env = {
        **os.environ,
        "NEXT_PUBLIC_API_BASE_URL": BACKEND_URL,
        "NEXT_PUBLIC_FACULTY_AI_APP_API_KEY": "",
        "FACULTY_AI_ACCESS_CODE": "",
    }
    services = [
        (
            "Backend",
            [str(python), "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(BACKEND_PORT), "--reload"],
            ROOT / "backend",
            backend_env,
        ),
        ("Frontend", [node, str(next_cli), "dev", "--hostname", HOST, "--port", str(FRONTEND_PORT)], ROOT / "frontend", frontend_env),
    ]
    group_options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {"start_new_session": True}
    )
    processes: list[tuple[str, subprocess.Popen]] = []
    print(f"Faculty-AI is starting at {FRONTEND_URL}. Press Ctrl+C to stop both services.", flush=True)
    try:
        for name, command, cwd, env in services:
            processes.append((name, subprocess.Popen(command, cwd=cwd, env=env, **group_options)))
        while True:
            for name, process in processes:
                if (code := process.poll()) is not None:
                    print(f"{name} stopped (exit code {code}).", file=sys.stderr)
                    return code or 1
            time.sleep(0.2)
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        print(f"Unable to start Faculty-AI: {exc}", file=sys.stderr)
        return 1
    finally:
        for _, process in reversed(processes):
            stop_process(process)


if __name__ == "__main__":
    if WINDOWS:
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    sys.exit(main())
