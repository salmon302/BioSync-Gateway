# Demo: start server, generate token, curl /api/human-factors/export
import os, time, subprocess, sys, urllib.request, json

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

os.environ.setdefault("JWT_SECRET", "test-secret-for-phase-c")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "postgresql://biosync_user@localhost:5432/biosync")

# 1) generate a JWT with human_factors_read scope
from middleware.api.auth import create_access_token
token = create_access_token({
    "sub": "demo-user", "role": "qa_officer",
    "scopes": ["human_factors_read", "human_factors_write"],
    "iat": int(time.time()), "exp": int(time.time()) + 3600,
}, expires_delta=1)

# 2) start uvicorn
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8011"],
    cwd=os.path.join(_REPO, "middleware"),
    env=os.environ,
)
time.sleep(8)

try:
    # 3) POST a couple of events
    import urllib.request as u
    def post(url, payload):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json",
                                               "Authorization": f"Bearer {token}"},
                                     method="POST")
        return urllib.request.urlopen(req, timeout=30).read()

    post("http://127.0.0.1:8011/api/human-factors/events", {"events": [
        {"session_id": "curl-demo", "event_type": "selection_latency",
         "timestamp": time.time() * 1000, "latency_ms": 120, "component": "Dashboard"},
        {"session_id": "curl-demo", "event_type": "input_steps",
         "timestamp": time.time() * 1000, "steps_count": 4, "component": "MicroplateEditor"},
    ]})

    # 4) GET export and validate JSON
    req = urllib.request.Request(
        "http://127.0.0.1:8011/api/human-factors/export?session_id=curl-demo",
        headers={"Authorization": f"Bearer {token}"})
    body = urllib.request.urlopen(req, timeout=30).read()
    data = json.loads(body)  # raises if not valid JSON
    print("CURL_EXPORT_VALID_JSON_OK")
    print("total_events:", data["total_events"])
    print("event_type_counts:", data["event_type_counts"])
    print("latency_stats:", data["latency_stats"])
    print("steps_stats:", data["steps_stats"])
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
