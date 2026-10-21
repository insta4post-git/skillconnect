"""SkillConnect end-to-end smoke test.  Uses only Python's standard library.

1. Start the server (uvicorn) and make sure MySQL has the tables and skills
   (create_tables.py and seed_skills.py already run).
2. In ANOTHER terminal:   python backend\\scripts\\smoke_test.py

It creates throw-away users named smoke_*@example.com, walks through the whole
product (register, login, profiles, search, requests, messages, reviews,
dashboards) and also tries bad input and attacks. Every line says PASS or FAIL.

Optional settings (environment variables):
  SC_BASE=http://127.0.0.1:8000     where the server runs
  SC_ADMIN_EMAIL / SC_ADMIN_PASSWORD   to test the admin panel too
  SC_SKIP_COMPLETE=1                skip the "finish the job" part (no SQL step)
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

BASE = os.environ.get("SC_BASE", "http://127.0.0.1:8000").rstrip("/")
STAMP = str(int(time.time()))
PASSWORD = "Smoke@Test1234"
passed, failed, skipped = [], [], []


class ServerDown(Exception):
    pass


# ----------------------------------------------------------------- plumbing


def call(method, path, body=None, token=None, raw_body=None):
    """Returns (status, parsed_json_or_None, text)."""
    data = raw_body if raw_body is not None else (json.dumps(body).encode() if body is not None else None)
    request = urllib.request.Request(BASE + path, data=data, method=method)
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    except (urllib.error.URLError, ConnectionError, TimeoutError) as error:
        raise ServerDown(str(error))
    text = raw.decode("utf-8", errors="ignore")
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    return status, parsed, text


def detail_of(js):
    if isinstance(js, dict):
        d = js.get("detail")
        return json.dumps(d) if isinstance(d, (list, dict)) else str(d)
    return ""


def check(name, ok, info=""):
    (passed if ok else failed).append(name)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"   -> {info}" if info and not ok else ""))
    return ok


def expect(name, got, *allowed, js=None):
    return check(name, got in allowed, f"got HTTP {got}, expected {'/'.join(map(str, allowed))} {detail_of(js)[:150]}")


def skip(name, why):
    skipped.append(name)
    print(f"  [SKIP] {name}   ({why})")


def section(title):
    print(f"\n=== {title}")


def get(js, *keys, default=None):
    for key in keys:
        if isinstance(js, dict):
            js = js.get(key)
        elif isinstance(js, list) and isinstance(key, int) and 0 <= key < len(js):
            js = js[key]
        else:
            return default
    return js if js is not None else default


def b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")


def forged_none_token(user_id: int) -> str:
    """A token that claims 'no signature needed' (the classic JWT attack)."""
    return f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': str(user_id), 'exp': 4102444800})}."


def tamper(token: str) -> str:
    head, payload, sig = token.split(".")
    flipped = ("A" if sig[0] != "A" else "B") + sig[1:]
    return f"{head}.{payload}.{flipped}"


def find_path(paths: dict, suffix: str, method="post", default=""):
    for path, ops in paths.items():
        if path.rstrip("/").endswith(suffix) and method in ops:
            return path
    return default


class Actor:
    def __init__(self, label, role):
        self.label, self.role = label, role
        self.email = f"smoke_{label}_{STAMP}@example.com"
        self.token = None
        self.id = None


# ----------------------------------------------------------------- the test


def run():
    ctx = {}
    section("0. Server")
    status, js, _ = call("GET", "/api/health")
    expect("GET /api/health answers", status, 200)
    check("database is connected", get(js, "database_connected") is True, str(get(js, "database_message")))
    status, spec, _ = call("GET", "/openapi.json")
    paths = get(spec, "paths", default={}) or {}
    register_path = find_path(paths, "/register", default="/api/auth/register")
    login_path = find_path(paths, "/login", default="/api/auth/login")
    check("API documentation (openapi.json) is available", status == 200)

    customer, provider, stranger = Actor("cust", "CUSTOMER"), Actor("prov", "PROVIDER"), Actor("other", "CUSTOMER")

    # ------------------------------------------------------------------ auth
    section("1. Registration")
    for actor, num in ((customer, 1), (provider, 2), (stranger, 3)):
        status, js, text = call("POST", register_path, {
            "full_name": f"Smoke {actor.label.title()}", "email": actor.email, "password": PASSWORD,
            "role": actor.role, "phone": f"+91 98000 0{num}{STAMP[-4:]}"})
        expect(f"register {actor.role.lower()} ({actor.label})", status, 200, 201, js=js)
        check(f"response for {actor.label} contains no password or hash", PASSWORD not in text and "hash" not in text.lower())
    base = {"full_name": "Smoke Dup", "email": customer.email, "password": PASSWORD, "role": "CUSTOMER"}
    s, js, _ = call("POST", register_path, base)
    expect("same email twice is refused", s, 400, 409, js=js)
    s, js, _ = call("POST", register_path, {**base, "email": customer.email.upper()})
    expect("same email in CAPITAL letters is also refused", s, 400, 409, 422, js=js)
    for label, change in (
        ("weak password (only digits)", {"password": "12345678", "email": f"w1_{STAMP}@example.com"}),
        ("common password 'password123'", {"password": "password123", "email": f"w2_{STAMP}@example.com"}),
        ("password too short", {"password": "Ab1", "email": f"w3_{STAMP}@example.com"}),
        ("password without a number", {"password": "OnlyLetters", "email": f"w4_{STAMP}@example.com"}),
        ("password longer than 72 bytes", {"password": "Aa1" * 30, "email": f"w5_{STAMP}@example.com"}),
        ("invalid email address", {"email": "not-an-email"}),
        ("role ADMIN cannot be self-assigned", {"role": "ADMIN", "email": f"w6_{STAMP}@example.com"}),
        ("empty name", {"full_name": "   ", "email": f"w7_{STAMP}@example.com"}),
        ("bad phone number", {"phone": "abc", "email": f"w8_{STAMP}@example.com"}),
    ):
        s, js, _ = call("POST", register_path, {**base, **change})
        expect(f"refused: {label}", s, 400, 403, 422, js=js)
    s, js, _ = call("POST", register_path, raw_body=b"{ this is not json")
    expect("broken JSON gives 422, not a crash", s, 400, 422)

    section("2. Login & JWT")
    for actor in (customer, provider, stranger):
        s, js, text = call("POST", login_path, {"email": actor.email, "password": PASSWORD})
        if expect(f"login {actor.label}", s, 200, js=js):
            actor.token = get(js, "access_token")
        check(f"{actor.label}: token received, no password in response", bool(actor.token) and "password" not in text.lower())
    s1, js1, _ = call("POST", login_path, {"email": customer.email, "password": "Wrong@Pass999"})
    s2, js2, _ = call("POST", login_path, {"email": f"nobody_{STAMP}@example.com", "password": "Wrong@Pass999"})
    expect("wrong password is refused", s1, 400, 401, 403, js=js1)
    check("unknown email and wrong password give the SAME answer (no user enumeration)", (s1, detail_of(js1)) == (s2, detail_of(js2)), f"{s1} {detail_of(js1)!r} vs {s2} {detail_of(js2)!r}")
    s, js, _ = call("POST", login_path, {"email": "' OR '1'='1", "password": "' OR '1'='1"})
    expect("SQL injection in the login form is refused", s, 400, 401, 403, 422, js=js)
    if not all(a.token for a in (customer, provider, stranger)):
        print("\nCannot continue without logins. Fix the section above first.")
        return
    s, js, _ = call("GET", "/api/users/me/profile", token=customer.token)
    expect("valid token opens my profile", s, 200, js=js)
    customer.id = get(js, "id")
    s, js, _ = call("GET", "/api/users/me/profile", token=provider.token)
    provider.id = get(js, "id")
    s, js, _ = call("GET", "/api/users/me/profile", token=stranger.token)
    stranger.id = get(js, "id")
    s, _, _ = call("GET", "/api/users/me/profile")
    expect("no token -> refused", s, 401, 403)
    s, _, _ = call("GET", "/api/users/me/profile", token="garbage.token.value")
    expect("garbage token -> refused", s, 401, 403)
    s, _, _ = call("GET", "/api/users/me/profile", token=tamper(customer.token))
    expect("token with a changed signature -> refused", s, 401, 403)
    s, _, _ = call("GET", "/api/users/me/profile", token=forged_none_token(customer.id or 1))
    expect("forged 'alg: none' token -> refused", s, 401, 403)
    s, _, _ = call("GET", "/api/users/me/profile", token=customer.token + "x")
    expect("token with extra characters -> refused", s, 401, 403)

    # --------------------------------------------------------------- profiles
    section("3. Profiles")
    where = {"city": "Pune", "area": "Kothrud", "pincode": "411038"}
    for actor in (customer, provider):
        s, js, _ = call("PUT", "/api/users/me/profile", {
            "full_name": f"Smoke {actor.label.title()}", "phone": "+91 98765 43210",
            "bio": "Created by the smoke test.", "location": where}, token=actor.token)
        expect(f"{actor.label}: save profile with location", s, 200, js=js)
    base_profile = {"full_name": "Smoke Cust", "phone": None, "bio": None, "location": where}
    for label, change in (("pincode with 2 digits", {"location": {**where, "pincode": "12"}}),
                          ("phone 'abc'", {"phone": "abc"}), ("bio over 1000 characters", {"bio": "x" * 1001}),
                          ("one-letter name", {"full_name": "A"})):
        s, js, _ = call("PUT", "/api/users/me/profile", {**base_profile, **change}, token=customer.token)
        expect(f"refused: {label}", s, 422, js=js)
    s, js, _ = call("GET", "/api/users/me/profile", token=customer.token)
    check("profile shows saved city", get(js, "location", "city") == "Pune")

    section("4. Provider profile, skills, availability")
    s, js, _ = call("GET", "/api/providers/me", token=customer.token)
    expect("a customer cannot open the provider area", s, 403, js=js)
    s, js, _ = call("GET", "/api/services/skills?limit=10")
    if s in (401, 403):
        s, js, _ = call("GET", "/api/services/skills?limit=10", token=customer.token)
    skills = js if isinstance(js, list) else []
    if not check("skills list is not empty (run seed_skills.py if this fails)", len(skills) >= 1):
        return
    ctx["skill"], ctx["skill_name"] = skills[0]["id"], skills[0]["name"]
    ctx["other_skill"] = skills[1]["id"] if len(skills) > 1 else None
    s, js, _ = call("PUT", "/api/providers/me", {
        "description": "Experienced professional created by the smoke test.", "experience_years": 5,
        "qualification": "Diploma", "working_area": "Kothrud, Pune", "service_mode": "BOTH",
        "pricing_info": "Rs 500 per visit", "availability_notes": "Weekdays"}, token=provider.token)
    expect("provider saves profile", s, 200, js=js)
    s, js, _ = call("PUT", "/api/providers/me", {"description": "short"}, token=provider.token)
    expect("refused: description under 10 characters", s, 422, js=js)
    s, js, _ = call("PUT", "/api/providers/me", {"description": "Long enough text here.", "experience_years": 99}, token=provider.token)
    expect("refused: 99 years of experience", s, 422, js=js)
    s, js, _ = call("PUT", "/api/providers/me/skills", {"skill_ids": [ctx["skill"]]}, token=provider.token)
    expect("provider saves skills", s, 200, js=js)
    s, js, _ = call("PUT", "/api/providers/me/skills", {"skill_ids": [ctx["skill"]]}, token=customer.token)
    expect("customer cannot change provider skills", s, 403, js=js)
    s, js, _ = call("PUT", "/api/providers/me/skills", {"skill_ids": [999999]}, token=provider.token)
    check("unknown skill id is refused (4xx, not a crash)", 400 <= s < 500, f"HTTP {s}")
    s, js, _ = call("PUT", "/api/providers/me/skills", {"skill_ids": [ctx["skill"]]}, token=provider.token)
    days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    s, js, _ = call("PUT", "/api/providers/me/availability", {"slots": [
        {"day_of_week": d, "start_time": "09:00", "end_time": "18:00"} for d in days]}, token=provider.token)
    expect("provider saves availability", s, 200, js=js)
    s, js, _ = call("PUT", "/api/providers/me/availability", {"slots": [
        {"day_of_week": "MONDAY", "start_time": "09:00", "end_time": "12:00"},
        {"day_of_week": "MONDAY", "start_time": "11:00", "end_time": "14:00"}]}, token=provider.token)
    expect("refused: overlapping time slots", s, 422, js=js)
    s, js, _ = call("PUT", "/api/providers/me/availability", {"slots": [
        {"day_of_week": "MONDAY", "start_time": "18:00", "end_time": "09:00"}]}, token=provider.token)
    expect("refused: end time before start time", s, 422, js=js)
    s, js, _ = call("PUT", "/api/providers/me/availability", {"slots": [
        {"day_of_week": d, "start_time": "09:00", "end_time": "18:00"} for d in days]}, token=provider.token)
    s, js, _ = call("GET", "/api/providers/me", token=provider.token)
    expect("provider reads own profile (route /me still works)", s, 200, js=js)
    check("profile is complete", get(js, "is_complete") is True)
    provider.id = get(js, "user_id", default=provider.id)

    if provider.id is None:
        print("\n  STOP: could not read the provider's id")
        print("  Everything after this depends on it, so the rest would only show confusing FAIL lines.")
        print("  Look at the FIRST [FAIL] line above (it shows the server's answer) and send it to Claude.")
        return

    # ----------------------------------------------------------------- search
    section("5. Search & public profile")
    q = urllib.parse.urlencode({"skill_id": ctx["skill"], "city": "Pune", "page_size": 50})
    s, js, text = call("GET", f"/api/search/providers?{q}")
    expect("search works without login", s, 200, js=js)
    ids = [get(r, "user_id") for r in get(js, "results", default=[])]
    check("my new provider is found", provider.id in ids, f"ids={ids[:10]}")
    check("search results show no email / phone", '"email"' not in text and '"phone"' not in text)
    s, js, _ = call("GET", "/api/search/providers?" + urllib.parse.urlencode({"q": ctx["skill_name"].split()[0], "page_size": 50}))
    expect("free-text search works", s, 200, js=js)
    for label, qs in (("quote injection", "q=%27+OR+%271%27%3D%271"), ("UNION injection", "q=x%27+UNION+SELECT+password_hash+FROM+users--"),
                      ("DROP TABLE", "q=%27%3B+DROP+TABLE+users%3B--"), ("percent sign", "q=%25"), ("underscore", "q=_"),
                      ("very long text", "q=" + "a" * 500), ("unicode", "q=%E0%A4%9F%E0%A5%87%E0%A4%B2%E0%A4%B0"),
                      ("script tag", "q=%3Cscript%3Ealert(1)%3C%2Fscript%3E"), ("city injection", "city=Pune%27+OR+1%3D1--")):
        s, js, text = call("GET", f"/api/search/providers?{qs}")
        check(f"search survives: {label}", s < 500 and "password_hash" not in text, f"HTTP {s}")
    for label, qs in (("min_rating=6", "min_rating=6"), ("page_size=1000", "page_size=1000"), ("page=0", "page=0"),
                      ("unknown sort", "sort=hack"), ("available_time without day", "available_time=10:00")):
        s, js, _ = call("GET", f"/api/search/providers?{qs}")
        expect(f"refused: {label}", s, 422, js=js)
    s, _, _ = call("GET", "/api/search/providers?near_me=true")
    expect("near_me needs a login", s, 401, 403)
    s, js, _ = call("GET", "/api/search/providers?near_me=true", token=customer.token)
    expect("near_me works for a logged-in customer", s, 200, js=js)
    s, js, text = call("GET", f"/api/providers/{provider.id}")
    expect("public provider profile opens without login", s, 200, js=js)
    check("profile has rating fields and no email/phone", "avg_rating" in text and "rating_breakdown" in text and '"email"' not in text and '"phone"' not in text)
    s, _, _ = call("GET", "/api/providers/999999")
    expect("unknown provider -> 404", s, 404)
    s, js, _ = call("GET", f"/api/providers/{customer.id}")
    expect("a customer's id is not a provider profile -> 404", s, 404, js=js)
    s, _, _ = call("GET", "/api/providers/abc")
    expect("provider id 'abc' -> 422/404", s, 404, 422)

    # --------------------------------------------------------------- requests
    section("6. Short-term service requests")
    tomorrow = date.today() + timedelta(days=1)

    def short_body(days_ahead, **over):
        body = {"provider_id": provider.id, "skill_id": ctx["skill"], "service_date": str(date.today() + timedelta(days=days_ahead)),
                "start_time": "10:00", "duration_hours": 2, "address_details": "Flat 4B, Smoke Society",
                "details": "Please come and help with the smoke test job."}
        body.update(over)
        return body

    s, js, _ = call("POST", "/api/requests/short-term", short_body(1), token=customer.token)
    expect("customer sends a short-term request", s, 201, js=js)
    s1_id = get(js, "id")
    if s1_id is None:
        print("\n  STOP: the first short-term request was not created (is Step 8 installed and the server restarted?)")
        print("  Everything after this depends on it, so the rest would only show confusing FAIL lines.")
        print("  Look at the FIRST [FAIL] line above (it shows the server's answer) and send it to Claude.")
        return
    check("status is PENDING", get(js, "status") == "PENDING")
    check("provider contact is hidden while PENDING", get(js, "provider", "email") is None and get(js, "provider", "phone") is None)
    for label, token, body, allowed in (
        ("provider cannot send requests", provider.token, short_body(2), (403,)),
        ("no login -> refused", None, short_body(2), (401, 403)),
        ("date in the past", customer.token, short_body(-1), (422,)),
        ("duration 0.2 hours", customer.token, short_body(2, duration_hours=0.2), (422,)),
        ("duration 0.75 (not a half-hour step)", customer.token, short_body(2, duration_hours=0.75), (422,)),
        ("description too short", customer.token, short_body(2, details="help"), (422,)),
        ("unknown provider", customer.token, short_body(2, provider_id=999999), (404,)),
        ("same day twice (duplicate)", customer.token, short_body(1), (409,)),
        ("200 days ahead", customer.token, short_body(200), (422,)),
        ("provider_id = 0", customer.token, short_body(2, provider_id=0), (422,)),
    ):
        s, js, _ = call("POST", "/api/requests/short-term", body, token=token)
        expect(f"refused: {label}", s, *allowed, js=js)
    if ctx["other_skill"]:
        s, js, _ = call("POST", "/api/requests/short-term", short_body(2, skill_id=ctx["other_skill"]), token=customer.token)
        expect("refused: skill the provider does not offer", s, 400, js=js)
    s, js, _ = call("POST", "/api/requests/short-term", short_body(2), token=customer.token)
    expect("second request (day +2) accepted", s, 201, js=js)
    s2_id = get(js, "id")
    s, js, _ = call("POST", "/api/requests/short-term", short_body(3), token=customer.token)
    expect("third request (day +3) accepted", s, 201, js=js)
    s3_id = get(js, "id")
    if s2_id is None or s3_id is None:
        print("\n  STOP: the extra short-term requests were not created")
        print("  Everything after this depends on it, so the rest would only show confusing FAIL lines.")
        print("  Look at the FIRST [FAIL] line above (it shows the server's answer) and send it to Claude.")
        return

    section("7. Regular (long-term) requests")
    start = date.today() + timedelta(days=5)

    def regular_body(**over):
        body = {"provider_id": provider.id, "skill_id": ctx["skill"], "start_date": str(start), "end_date": str(start + timedelta(days=60)),
                "working_days": ["MONDAY", "WEDNESDAY", "FRIDAY"], "start_time": "17:00", "end_time": "18:30",
                "address_details": "Flat 4B, Smoke Society", "details": "Long-term smoke test arrangement, three days a week."}
        body.update(over)
        return body

    s, js, _ = call("POST", "/api/requests/regular", regular_body(), token=customer.token)
    expect("customer sends a long-term request", s, 201, js=js)
    r1_id = get(js, "id")
    if r1_id is None:
        print("\n  STOP: the long-term request was not created (is Step 7 installed?)")
        print("  Everything after this depends on it, so the rest would only show confusing FAIL lines.")
        print("  Look at the FIRST [FAIL] line above (it shows the server's answer) and send it to Claude.")
        return
    check("sessions are counted (total_sessions > 0)", (get(js, "total_sessions") or 0) > 0)
    for label, body, allowed in (
        ("overlapping long-term request", regular_body(start_date=str(start + timedelta(days=10)), end_date=str(start + timedelta(days=40))), (409,)),
        ("end date before start date", regular_body(end_date=str(start - timedelta(days=1))), (422,)),
        ("no working days", regular_body(working_days=[]), (422,)),
        ("invalid weekday", regular_body(working_days=["FUNDAY"]), (422,)),
        ("longer than one year", regular_body(end_date=str(start + timedelta(days=400))), (422,)),
        ("end time before start time", regular_body(start_time="18:00", end_time="17:00"), (422,)),
        ("start date in the past", regular_body(start_date=str(date.today() - timedelta(days=2))), (422,)),
    ):
        s, js, _ = call("POST", "/api/requests/regular", body, token=customer.token)
        expect(f"refused: {label}", s, *allowed, js=js)

    section("8. Request history & access control")
    s, js, _ = call("GET", "/api/requests/mine", token=customer.token)
    expect("customer history", s, 200, js=js)
    mine = {get(r, "id") for r in (js if isinstance(js, list) else [])}
    check("customer sees all 4 own requests", {s1_id, s2_id, s3_id, r1_id} <= mine)
    s, js, _ = call("GET", "/api/requests/mine?status=PENDING", token=provider.token)
    expect("provider inbox filtered by PENDING", s, 200, js=js)
    check("provider received the requests", {s1_id, s2_id, s3_id, r1_id} <= {get(r, "id") for r in (js if isinstance(js, list) else [])})
    s, js, _ = call("GET", "/api/requests/mine", token=stranger.token)
    check("a stranger's history is empty", s == 200 and js == [], f"HTTP {s}")
    s, _, _ = call("GET", "/api/requests/mine?status=BOGUS", token=customer.token)
    expect("refused: unknown status filter", s, 422)
    s, _, _ = call("GET", "/api/requests/mine?page_size=1000", token=customer.token)
    expect("refused: page_size=1000", s, 422)
    s, _, _ = call("GET", "/api/requests/mine")
    expect("history needs a login", s, 401, 403)
    s, _, _ = call("GET", f"/api/requests/{s1_id}", token=stranger.token)
    expect("a stranger cannot open someone else's request -> 404", s, 404)
    s, _, _ = call("GET", "/api/requests/0", token=customer.token)
    expect("request id 0 -> 422", s, 422)
    s, _, _ = call("GET", "/api/requests/abc", token=customer.token)
    expect("request id 'abc' -> 422", s, 422)
    s, _, _ = call("GET", "/api/requests/999999", token=customer.token)
    expect("unknown request -> 404", s, 404)

    section("9. Accept / reject / cancel")
    s, js, _ = call("POST", f"/api/requests/{s1_id}/accept", token=customer.token)
    expect("customer cannot accept", s, 403, js=js)
    s, _, _ = call("POST", f"/api/requests/{s1_id}/accept", token=stranger.token)
    expect("stranger cannot accept -> 404", s, 404)
    s, js, _ = call("POST", f"/api/requests/{s1_id}/accept", token=provider.token)
    expect("provider accepts the short-term request", s, 200, js=js)
    check("status ACCEPTED", get(js, "status") == "ACCEPTED")
    check("contact details are now shared (customer email visible to provider)", get(js, "customer", "email") == customer.email and get(js, "customer", "phone"))
    s, js, _ = call("GET", f"/api/requests/{s1_id}", token=customer.token)
    check("customer sees the provider's email after acceptance", get(js, "provider", "email") == provider.email)
    s, js, _ = call("POST", f"/api/requests/{s1_id}/accept", token=provider.token)
    expect("accepting twice -> 409", s, 409, js=js)
    s, js, _ = call("POST", f"/api/requests/{s1_id}/reject", token=provider.token)
    expect("rejecting an accepted request -> 409", s, 409, js=js)
    s, js, _ = call("POST", f"/api/requests/{r1_id}/accept", token=provider.token)
    expect("provider accepts the long-term request", s, 200, js=js)
    s, js, _ = call("POST", f"/api/requests/{s2_id}/reject", token=provider.token)
    expect("provider rejects request #2", s, 200, js=js)
    check("status REJECTED and contact hidden", get(js, "status") == "REJECTED" and get(js, "customer", "email") is None)
    s, js, _ = call("POST", f"/api/requests/{s2_id}/cancel", token=customer.token)
    expect("cancelling a rejected request -> 409", s, 409, js=js)
    s, js, _ = call("POST", f"/api/requests/{s3_id}/cancel", token=provider.token)
    expect("provider cannot cancel the customer's request", s, 403, js=js)
    s, js, _ = call("POST", f"/api/requests/{s3_id}/cancel", token=customer.token)
    expect("customer cancels request #3", s, 200, js=js)
    check("status CANCELLED", get(js, "status") == "CANCELLED")
    s, js, _ = call("POST", f"/api/requests/{s1_id}/complete", token=provider.token)
    expect("cannot complete before the service starts -> 400", s, 400, js=js)

    section("10. Messaging")
    s, js, _ = call("POST", f"/api/requests/{s1_id}/messages", {"body": "Hello, are you free at 10?"}, token=customer.token)
    expect("customer sends a message", s, 201, js=js)
    m1 = get(js, "id")
    check("message belongs to the logged-in user", get(js, "is_mine") is True and get(js, "sender_id") == customer.id)
    s, js, _ = call("POST", f"/api/requests/{s1_id}/messages", {"body": "<script>alert('x')</script> & <b>bold</b>"}, token=provider.token)
    expect("provider replies (HTML text is stored as plain text)", s, 201, js=js)
    check("HTML in a message comes back unchanged (the page must show it with textContent)", get(js, "body") == "<script>alert('x')</script> & <b>bold</b>")
    s, js, _ = call("GET", f"/api/requests/{s1_id}/messages", token=provider.token)
    expect("provider reads the conversation", s, 200, js=js)
    check("2 messages, oldest first, can_send true", len(get(js, "messages", default=[])) == 2 and get(js, "messages", 0, "id") == m1 and get(js, "can_send") is True)
    s, js, _ = call("GET", f"/api/requests/{s1_id}/messages?after_id={m1}", token=customer.token)
    check("after_id returns only the newer message", s == 200 and len(get(js, "messages", default=[])) == 1)
    for label, body in (("empty message", {"body": ""}), ("blank message", {"body": "     "}), ("1001 characters", {"body": "x" * 1001}), ("missing body", {})):
        s, js, _ = call("POST", f"/api/requests/{s1_id}/messages", body, token=customer.token)
        expect(f"refused: {label}", s, 422, js=js)
    s, js, _ = call("POST", f"/api/requests/{s1_id}/messages", {"body": "sender_id spoof", "sender_id": provider.id}, token=customer.token)
    check("a spoofed sender_id is ignored", s == 201 and get(js, "sender_id") == customer.id, f"HTTP {s}")
    s, _, _ = call("GET", f"/api/requests/{s1_id}/messages", token=stranger.token)
    expect("stranger cannot read the chat -> 404", s, 404)
    s, _, _ = call("POST", f"/api/requests/{s1_id}/messages", {"body": "hi there"}, token=stranger.token)
    expect("stranger cannot write in the chat -> 404", s, 404)
    s, _, _ = call("GET", f"/api/requests/{s1_id}/messages")
    expect("chat needs a login", s, 401, 403)
    s, js, _ = call("POST", f"/api/requests/{s3_id}/messages", {"body": "still there?"}, token=customer.token)
    expect("chat of a cancelled request is closed -> 409", s, 409, js=js)
    s, js, _ = call("GET", f"/api/requests/{s3_id}/messages", token=customer.token)
    check("...but the history is still readable, can_send false", s == 200 and get(js, "can_send") is False)
    s, js, _ = call("GET", "/api/messages/inbox", token=customer.token)
    check("customer inbox lists the conversation", s == 200 and s1_id in [get(i, "request_id") for i in (js if isinstance(js, list) else [])])
    s, js, text = call("GET", "/api/messages/inbox", token=provider.token)
    check("provider inbox lists it, no contact details", s == 200 and s1_id in [get(i, "request_id") for i in (js if isinstance(js, list) else [])] and customer.email not in text)

    section("11. Finish the job & reviews")
    if os.environ.get("SC_SKIP_COMPLETE") == "1" or not sys.stdin.isatty():
        skip("complete + review flow", "needs a manual SQL step; run in a normal terminal")
    else:
        print("\n  A job can only be completed after its start time. Pretend the time has passed:")
        print("  Open MySQL Workbench, select the skillconnect database and run:\n")
        print(f"      UPDATE service_requests SET scheduled_at = NOW() - INTERVAL 3 HOUR WHERE id = {s1_id};\n")
        input("  Press Enter here when the SQL has run (or Ctrl+C to stop) ... ")
        s, js, _ = call("POST", f"/api/requests/{s1_id}/complete", token=customer.token)
        expect("customer cannot complete", s, 403, js=js)
        s, js, _ = call("POST", f"/api/requests/{s1_id}/complete", token=provider.token)
        expect("provider completes the job", s, 200, js=js)
        check("status COMPLETED", get(js, "status") == "COMPLETED")
        s, js, _ = call("POST", f"/api/requests/{s1_id}/complete", token=provider.token)
        expect("completing twice -> 409", s, 409, js=js)
        s, js, _ = call("POST", f"/api/requests/{s1_id}/messages", {"body": "after completion"}, token=customer.token)
        expect("chat closes after completion -> 409", s, 409, js=js)
        review = {"rating": 5, "comment": "Great smoke-test service!"}
        s, js, _ = call("POST", f"/api/requests/{s1_id}/review", review, token=provider.token)
        expect("provider cannot review own job", s, 403, js=js)
        s, _, _ = call("POST", f"/api/requests/{s1_id}/review", review, token=stranger.token)
        expect("stranger cannot review -> 404", s, 404)
        s, js, _ = call("POST", f"/api/requests/{r1_id}/review", review, token=customer.token)
        expect("cannot review a job that is not completed -> 409", s, 409, js=js)
        for bad in (0, 6, -1, 4.5, "five"):
            s, js, _ = call("POST", f"/api/requests/{s1_id}/review", {"rating": bad}, token=customer.token)
            expect(f"refused: rating {bad!r}", s, 422, js=js)
        s, js, _ = call("POST", f"/api/requests/{s1_id}/review", {"rating": 5, "comment": "x" * 1001}, token=customer.token)
        expect("refused: comment over 1000 characters", s, 422, js=js)
        s, js, _ = call("POST", f"/api/requests/{s1_id}/review", review, token=customer.token)
        expect("customer reviews the completed job", s, 201, js=js)
        s, js, _ = call("POST", f"/api/requests/{s1_id}/review", review, token=customer.token)
        expect("second review of the same job -> 409", s, 409, js=js)
        s, js, _ = call("GET", "/api/reviews/mine", token=customer.token)
        check("customer sees the review they wrote", s == 200 and len(js or []) >= 1)
        s, js, text = call("GET", "/api/reviews/mine", token=provider.token)
        check("provider sees the review they received", s == 200 and len(js or []) >= 1)
        s, js, text = call("GET", f"/api/providers/{provider.id}")
        check("public profile shows the new rating", get(js, "review_count", default=0) >= 1 and get(js, "avg_rating") is not None)
        name = get(js, "recent_reviews", 0, "reviewer_name", default="")
        check("reviewer name is shortened ('Smoke C.') and no email leaks", name.endswith(".") and customer.email not in text, name)
        s, js, _ = call("GET", f"/api/providers/{provider.id}/reviews")
        check("provider review list is public", s == 200 and len(js or []) >= 1)

    section("12. Dashboards")
    s, js, _ = call("GET", "/api/dashboard/customer", token=customer.token)
    expect("customer dashboard", s, 200, js=js)
    check("customer dashboard counts requests", (get(js, "requests", "total", default=0)) >= 4)
    s, js, _ = call("GET", "/api/dashboard/provider", token=provider.token)
    expect("provider dashboard", s, 200, js=js)
    check("provider is visible in search (checklist)", get(js, "checklist", "visible_in_search") is True)
    check("provider dashboard counts requests", (get(js, "requests", "total", default=0)) >= 4)
    s, _, _ = call("GET", "/api/dashboard/provider", token=customer.token)
    expect("customer cannot open the provider dashboard", s, 403)
    s, _, _ = call("GET", "/api/dashboard/customer", token=provider.token)
    expect("provider cannot open the customer dashboard", s, 403)
    s, _, _ = call("GET", "/api/dashboard/admin", token=customer.token)
    expect("customer cannot open the admin dashboard", s, 403)
    s, _, _ = call("GET", "/api/dashboard/admin", token=provider.token)
    expect("provider cannot open the admin dashboard", s, 403)
    s, _, _ = call("GET", "/api/dashboard/customer")
    expect("dashboards need a login", s, 401, 403)
    s, _, _ = call("GET", "/api/admin/users", token=customer.token)
    expect("customer cannot use the admin API", s, 403)
    s, _, _ = call("GET", "/api/admin/requests", token=provider.token)
    expect("provider cannot use the admin API", s, 403)
    s, _, _ = call("DELETE", f"/api/admin/skills/{ctx['skill']}", token=provider.token)
    expect("provider cannot delete skills", s, 403)
    admin_email, admin_pw = os.environ.get("SC_ADMIN_EMAIL"), os.environ.get("SC_ADMIN_PASSWORD")
    if admin_email and admin_pw:
        s, js, _ = call("POST", login_path, {"email": admin_email, "password": admin_pw})
        token = get(js, "access_token")
        if expect("admin login", s, 200, js=js) and token:
            s, js, _ = call("GET", "/api/dashboard/admin", token=token)
            expect("admin dashboard", s, 200, js=js)
            s, js, text = call("GET", "/api/admin/users?q=smoke_", token=token)
            check("admin finds the smoke users", s == 200 and len(js or []) >= 3 and "password" not in text.lower())
            for path in ("/api/admin/providers", "/api/admin/requests?status=PENDING", "/api/admin/skills?custom_only=true"):
                s, js, _ = call("GET", path, token=token)
                expect(f"admin {path.split('?')[0]}", s, 200, js=js)
            s, js, _ = call("DELETE", f"/api/admin/skills/{ctx['skill']}", token=token)
            expect("admin cannot delete a skill that is in use -> 409", s, 409, js=js)
    else:
        skip("admin panel", "set SC_ADMIN_EMAIL and SC_ADMIN_PASSWORD to test it")

    section("13. Other protection")
    s, _, _ = call("DELETE", "/api/users/me/profile", token=customer.token)
    expect("unsupported method -> 405", s, 405)
    s, _, _ = call("GET", "/api/does-not-exist")
    check("unknown API path gives a clean 404", s == 404, f"HTTP {s}")
    s, _, text = call("GET", f"/api/requests/{s1_id}", token=customer.token + "x")
    check("error answers never contain a stack trace", "Traceback" not in text and "sqlalchemy" not in text.lower())
    statuses = []
    for _ in range(14):
        s, _, _ = call("POST", login_path, {"email": f"nobody_{STAMP}@example.com", "password": "Wrong@Pass999"})
        statuses.append(s)
    if 429 in statuses:
        check("repeated wrong logins get slowed down (HTTP 429)", True)
    else:
        skip("login rate limit", "no 429 seen: the new main.py/ratelimit.py may not be installed, or RATE_LIMIT_DISABLED=1")
    print("\n  Note: that last check used up this computer's login attempts for about a minute.")
    print("  Clean up the test data afterwards in MySQL Workbench:")
    print("      DELETE FROM users WHERE email LIKE 'smoke!_%@example.com' ESCAPE '!';")


def main():
    print(f"SkillConnect smoke test against {BASE}")
    try:
        run()
    except ServerDown as error:
        print(f"\nCannot reach the server at {BASE}. Is uvicorn running? ({error})")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\nStopped.")
    print(f"\n==== {len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped")
    if failed:
        print("\nFAILED:")
        for name in failed:
            print(f"  - {name}")
        sys.exit(1)


if __name__ == "__main__":
    main()
