"""全功能端到端测试脚本"""
import requests, json, sys

BASE = "http://127.0.0.1:5000"
passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  OK  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}: {detail}")

def api_get(session, path, expect_code=200):
    r = session.get(f"{BASE}{path}", allow_redirects=False)
    return r.status_code == expect_code, r

# ============================================================
print("=" * 60)
print("  FULL FUNCTIONAL TEST")
print("=" * 60)

# ---- 1. Health Check ----
print("\n1. Health Check")
r = requests.get(f"{BASE}/health")
check("/health OK", r.status_code == 200, r.status_code)
data = r.json()
check("status=ok", data.get("status") == "ok")
check("php_api=ok", data.get("php_api") == "ok", data.get("php_api"))

# ---- 2. Login Page ----
print("\n2. Login Page")
r = requests.get(f"{BASE}/login")
check("GET /login 200", r.status_code == 200)
check("page contains login form", "登录" in r.text)
check("admin badge", "管理员" in r.text)
check("chuli001 badge", "处理员" in r.text)
check("zhangsan badge", "安保员" in r.text)

# ---- 3. Login Tests ----
print("\n3. Login - All 3 Users")
users = [
    ("admin", "123456", "管理员", "超"),
    ("chuli001", "123456", "处理员小张", "普通"),
    ("zhangsan", "123456", "张三", "普通"),
]
sessions = {}

for username, password, real_name, role_hint in users:
    print(f"\n  [{username}]")
    r = requests.post(f"{BASE}/api/v1/token", json={"username": username, "password": password})
    ok = r.status_code == 200 and r.json().get("code") == 200
    check(f"API login", ok, r.json().get("msg", r.status_code) if not ok else "")
    if not ok:
        continue

    token = r.json()["data"]["token"]
    user_info = r.json()["data"]["user"]
    check(f"real_name={real_name}", user_info.get("real_name") == real_name, user_info.get("real_name"))
    check(f"user_type correct", (username == "admin") == (user_info.get("user_type") == 1))

    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {token}"})
    sessions[username] = sess

    # Test alarm list
    ok2, r2 = api_get(sess, "/api/v1/alarm-events?per_page=3")
    check("alarm list", ok2, r2.status_code)

    # Test statistics
    ok2, r2 = api_get(sess, "/api/v1/statistics/overview")
    check("statistics", ok2, r2.status_code)

    # Page login
    page_sess = requests.Session()
    r3 = page_sess.post(f"{BASE}/login", data={"username": username, "password": password}, allow_redirects=False)
    check("page login 302", r3.status_code == 302, r3.status_code)

# ---- 4. All Page Routes ----
print("\n4. All Page Routes (admin)")
admin_sess = sessions.get("admin")
if admin_sess:
    pages = [
        ("/", "GIS Data Screen"),
        ("/dashboard", "Dashboard"),
        ("/system/config", "System Config"),
        ("/system/department", "Department"),
        ("/system/user", "User Management"),
        ("/system/role", "Role Management"),
        ("/system/datadict", "Data Dictionary"),
        ("/device/cloudbox", "Cloud Box"),
        ("/device/camera", "Camera"),
        ("/alarm/event", "Alarm Event"),
        ("/alarm/review", "Alarm Review"),
        ("/alarm/camera-fault", "Camera Fault"),
        ("/alarm/cloudbox-fault", "CloudBox Fault"),
        ("/log/access", "Access Log"),
        ("/log/operation", "Operation Log"),
    ]
    for path, name in pages:
        ok2, r = api_get(admin_sess, path)
        check(f"Page: {name} ({path})", ok2, r.status_code)

# ---- 5. API CRUD Tests ----
print("\n5. API CRUD (admin)")
if admin_sess:
    apis = [
        ("/api/v1/cloudboxes", "Cloud Boxes"),
        ("/api/v1/cameras", "Cameras"),
        ("/api/v1/users?per_page=5", "Users"),
        ("/api/v1/roles", "Roles"),
        ("/api/v1/departments", "Departments"),
        ("/api/v1/datadicts", "Data Dicts"),
        ("/api/v1/statistics/overview", "Stats Overview"),
        ("/api/v1/statistics/alarm-by-date?days=7", "Stats by Date"),
        ("/api/v1/statistics/alarm-by-region", "Stats by Region"),
        ("/api/v1/statistics/alarm-by-level", "Stats by Level"),
        ("/api/v1/statistics/device-fault-stats", "Fault Stats"),
        ("/api/v1/system-configs", "System Configs"),
        ("/api/v1/logs/access", "Access Logs"),
        ("/api/v1/logs/operation", "Operation Logs"),
        ("/api/v1/alarm-events?per_page=5", "Alarm Events"),
        ("/api/v1/camera-faults", "Camera Faults"),
        ("/api/v1/cloudbox-faults", "CloudBox Faults"),
    ]
    for path, name in apis:
        ok2, r = api_get(admin_sess, path)
        check(f"API: {name}", ok2, r.status_code)

# ---- 6. Permission Control ----
print("\n6. Permission Control")
normal_sess = sessions.get("chuli001")
if normal_sess:
    ok2, r = api_get(normal_sess, "/system/config")
    check("normal user /config blocked", r.status_code in [302, 403], r.status_code)

    ok2, r = api_get(normal_sess, "/api/v1/system-configs")
    check("normal user /system-configs blocked", r.status_code in [302, 403], r.status_code)

    ok2, r = api_get(normal_sess, "/api/v1/cloudboxes")
    check("normal user can view devices", ok2, r.status_code)

# ---- 7. Edge API ----
print("\n7. Edge Device API")
EDGE_KEY = "flame-edge-dev-key-2026"
r = requests.post(f"{BASE}/api/detect/alarm",
    json={"device_id": 1, "camera_id": 1, "event_type": "fire", "confidence": 0.95},
    headers={"X-API-Key": EDGE_KEY})
check("alarm with key", r.status_code in [200, 201], r.status_code)

r = requests.post(f"{BASE}/api/detect/alarm", json={"device_id": 1})
check("alarm without key rejected", r.status_code == 401, r.status_code)

r = requests.post(f"{BASE}/api/device/heartbeat",
    json={"device_id": 1}, headers={"X-API-Key": EDGE_KEY})
check("heartbeat", r.status_code in [200, 201], r.status_code)

# ---- 8. Auth Protection ----
print("\n8. Auth Protection")
anon = requests.Session()
ok2, r = api_get(anon, "/")
check("unauthenticated / -> 302", r.status_code == 302)
ok2, r = api_get(anon, "/dashboard")
check("unauthenticated /dashboard -> 302", r.status_code == 302)
ok2, r = api_get(anon, "/api/v1/alarm-events")
check("unauthenticated API -> 401", r.status_code == 401)

# ---- 9. Error Handling ----
print("\n9. Error Handling")
r = requests.get(f"{BASE}/nonexistent-page-xyz")
check("404 page", r.status_code == 404)

# ---- Summary ----
print("\n" + "=" * 60)
total = passed + failed
print(f"  Results: {passed}/{total} passed, {failed} failed")
if failed == 0:
    print("  ALL TESTS PASSED!")
else:
    print(f"  {failed} failures detected")
print("=" * 60)
