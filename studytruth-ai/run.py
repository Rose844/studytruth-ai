"""
One-command launcher for StudyTruth AI.

Starts the FastAPI backend (port 8000) and a static file server for the
frontend together, seeds sample data on first run if the database is
empty, and opens your browser automatically.

Run with:   python run.py
Stop with:  Ctrl+C  (stops both servers cleanly)

If a port is already in use (e.g. a previous run is still open in another
terminal), this script tells you clearly instead of silently failing.
"""
import socket
import subprocess
import sys
import time
import webbrowser
import signal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
DB_PATH = BACKEND_DIR / "data" / "storage" / "studytruth.db"

BACKEND_PORT = 8000
# 5500 is blocked by Windows' reserved-port-range on some machines (Hyper-V /
# WSL NAT reservations) even when nothing is using it. 8080 is far less
# likely to collide with that reserved range.
FRONTEND_PORT_CANDIDATES = [8080, 5500, 3000, 8090]

processes = []


def log(msg):
    print(f"[StudyTruth AI] {msg}")


def port_is_free(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) != 0


def find_free_frontend_port():
    for port in FRONTEND_PORT_CANDIDATES:
        if port_is_free(port):
            return port
    return None


def ensure_env_file():
    env_path = ROOT / ".env"
    example_path = ROOT / ".env.example"
    if not env_path.exists() and example_path.exists():
        env_path.write_text(example_path.read_text())
        log("Created .env from .env.example (local mock mode, no API keys needed)")


def ensure_seed_data():
    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        log("Database already seeded — skipping (delete backend/data/storage/studytruth.db to reseed)")
        return
    log("No database found — seeding sample data (Computer Networks, DNN, DSA)...")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_data.py")], cwd=ROOT)
    if result.returncode != 0:
        log("WARNING: seeding failed — check the error above. The app will still start with no documents.")


def start_backend():
    if not port_is_free(BACKEND_PORT):
        log(f"ERROR: Port {BACKEND_PORT} is already in use.")
        log("This usually means a previous 'run.py' or 'uvicorn' is still running in another terminal.")
        log(f"Close that terminal (or press Ctrl+C in it), then run 'python run.py' again.")
        sys.exit(1)
    log(f"Starting backend on http://localhost:{BACKEND_PORT} ...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(BACKEND_PORT)],
        cwd=BACKEND_DIR,
    )
    processes.append(proc)
    return proc


def start_frontend():
    port = find_free_frontend_port()
    if port is None:
        log(f"ERROR: All candidate frontend ports are in use: {FRONTEND_PORT_CANDIDATES}")
        log("Close other terminals running this app, or free one of these ports, then retry.")
        sys.exit(1)
    log(f"Starting frontend on http://localhost:{port} ...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port)],
        cwd=FRONTEND_DIR,
    )
    processes.append(proc)
    return proc, port


def shutdown(*_):
    log("Shutting down...")
    for p in processes:
        try:
            p.terminate()
        except Exception:
            pass
    time.sleep(0.5)
    for p in processes:
        try:
            p.kill()
        except Exception:
            pass
    sys.exit(0)


def ensure_dependencies():
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        log("Backend dependencies aren't installed yet.")
        log(f"Run this first:  pip install -r {BACKEND_DIR / 'requirements.txt'}")
        log("(Activate your virtual environment first if you're using one.)")
        sys.exit(1)


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    ensure_dependencies()
    ensure_env_file()
    ensure_seed_data()
    start_backend()
    time.sleep(2.5)  # give the backend a moment to build its vector index
    frontend_proc, frontend_port = start_frontend()
    time.sleep(1)

    url = f"http://localhost:{frontend_port}"
    log(f"Opening {url} in your browser...")
    try:
        webbrowser.open(url)
    except Exception:
        log(f"Could not auto-open a browser — go to {url} manually.")

    log("Both servers are running. Press Ctrl+C here to stop everything.")
    try:
        while True:
            time.sleep(1)
            for p in processes:
                if p.poll() is not None:
                    log("A server process stopped unexpectedly — shutting down.")
                    shutdown()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
