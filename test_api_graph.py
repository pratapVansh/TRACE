"""TRACE API verification script — tests all graph endpoints."""
import httpx, json, sys

BASE = "http://localhost:8000/api"

def log(label, status, data):
    print(f"  Status: {status}")
    if status >= 400:
        print(f"  Error: {data}")
    else:
        print(f"  OK: {json.dumps(data, indent=2)[:500]}")

# Login
r = httpx.post(f"{BASE}/auth/login",
    json={"email": "vanshprataps2004@gmail.com", "password": "superadmin@10000"}, timeout=10)
if r.status_code != 200:
    print(f"Login failed: {r.status_code} {r.text}")
    sys.exit(1)
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("Login OK\n")

# 1. Health
print("1. GET /graph/health")
r = httpx.get(f"{BASE}/graph/health", headers=headers, timeout=10)
log("health", r.status_code, r.json())
assert r.status_code == 200, f"Health check failed: {r.text}"
assert r.json().get("connection_status") == "connected"
print()

# 2. Statistics
print("2. GET /graph/statistics")
r = httpx.get(f"{BASE}/graph/statistics", headers=headers, timeout=10)
log("statistics", r.status_code, r.json())
assert r.status_code == 200
print()

# 3. Schema
print("3. GET /graph/schema")
r = httpx.get(f"{BASE}/graph/schema", headers=headers, timeout=10)
log("schema", r.status_code, r.json())
assert r.status_code == 200
print()

# 4. Entities
print("4. GET /graph/entities?limit=5")
r = httpx.get(f"{BASE}/graph/entities?skip=0&limit=5", headers=headers, timeout=10)
log("entities", r.status_code, r.json())
assert r.status_code == 200
data = r.json()
print(f"  Total entities: {data.get('total', '?')}")
print(f"  Items: {len(data.get('items', []))}")
for item in data.get("items", [])[:3]:
    print(f"    - id={item.get('id','?')[:16]}... name={item.get('name','?')} type={item.get('type','?')}")
print()

# 5. Search
print("5. GET /graph/search?q=pump")
r = httpx.get(f"{BASE}/graph/search?q=pump", headers=headers, timeout=10)
log("search", r.status_code, r.json())
assert r.status_code == 200
data = r.json()
print(f"  Total: {data.get('total', '?')}")
for item in data.get("items", []):
    print(f"    - id={item.get('id','?')[:16]}... name={item.get('name','?')} type={item.get('type','?')}")
print()

# 6. Neighbors (use first entity)
r = httpx.get(f"{BASE}/graph/entities?skip=0&limit=1", headers=headers, timeout=10)
data = r.json()
if data.get("items"):
    first_id = data["items"][0]["id"]
    print(f"6. GET /graph/neighbors/{first_id[:16]}...?limit=5")
    r = httpx.get(f"{BASE}/graph/neighbors/{first_id}?limit=5", headers=headers, timeout=10)
    log("neighbors", r.status_code, r.json())
    assert r.status_code == 200
    ndata = r.json()
    print(f"  Neighbors count: {ndata.get('total', '?')}")
    for n in ndata.get("items", [])[:3]:
        ent = n.get("entity", {})
        print(f"    - {ent.get('name','?')} ({ent.get('type','?')}) rel={n.get('relationship_type','?')}")
else:
    print("6. GET /graph/neighbors — SKIP (no entities in graph)")

print()
print("=== ALL API VERIFICATION PASSED ===")
