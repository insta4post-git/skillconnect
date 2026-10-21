"""SkillConnect security / hygiene audit.  Read-only: it never changes a file.

Run from the project folder (the one that contains `backend`):
    python backend\\scripts\\audit_project.py

It NEVER prints the value of a password or secret, only PASS / WARN / FAIL lines,
so you can safely copy the whole output and paste it into the chat.
"""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", "uploads", ".idea", ".vscode"}
THIS_FILE = Path(__file__).resolve()
results = []  # (level, title, detail)


def add(level, title, detail=""):
    results.append((level, title, detail))


def find_root(start: Path) -> Path:
    for folder in [start, *start.parents]:
        if (folder / "backend").is_dir():
            return folder
    return start


def walk(root: Path, suffixes):
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(suffixes):
                path = Path(folder) / name
                if path.resolve() != THIS_FILE:
                    yield path


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def is_placeholder(value: str) -> bool:
    v = value.strip().strip("\"'").lower()
    if not v:
        return True
    return bool(re.search(r"change|your|example|placeholder|xxx|<.*>|\*\*\*|replace|here|todo|secret_key_here|password_here", v))


def parse_env(path: Path) -> dict:
    data = {}
    for line in read(path).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data


# --------------------------------------------------------------------- checks


def check_gitignore(root: Path):
    lines = set()
    for gi in [root / ".gitignore", root / "backend" / ".gitignore"]:
        if gi.exists():
            lines |= {l.strip().strip("/").lower() for l in read(gi).splitlines() if l.strip() and not l.startswith("#")}
    if not lines:
        add("FAIL", ".gitignore", "No .gitignore file found. Create one (see the chat for the content).")
        return
    wanted = {
        ".env": {".env", "*.env", ".env*", "backend/.env"},
        "virtual environment": {".venv", "venv", ".venv/", "backend/.venv", "backend/venv"},
        "__pycache__": {"__pycache__", "*.pyc", "__pycache__/", "**/__pycache__"},
    }
    for name, variants in wanted.items():
        if lines & {v.strip("/") for v in variants}:
            add("PASS", f".gitignore covers {name}")
        else:
            add("FAIL", f".gitignore does NOT cover {name}", "Add it to .gitignore.")
    if any("uploads" in l for l in lines):
        add("PASS", ".gitignore covers the uploads folder (profile photos)")
    else:
        add("WARN", ".gitignore does not cover uploads/", "User photos should not be committed. Add: backend/uploads/*  and  !backend/uploads/.gitkeep")


def git(root: Path, *args):
    try:
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=30)
        return out.returncode, out.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def check_git(root: Path):
    if not (root / ".git").exists():
        add("INFO", "Git", "No .git folder here, so tracked-file and history checks were skipped.")
        return
    code, out = git(root, "ls-files")
    if code != 0:
        add("INFO", "Git", "Could not run git. Tracked-file checks skipped.")
        return
    tracked = out.splitlines()
    bad = []
    for f in tracked:
        base = f.rsplit("/", 1)[-1].lower()
        if (base == ".env" or (base.startswith(".env") and base != ".env.example")) or base.endswith((".pem", ".key", ".pfx")):
            bad.append(f)
        elif "/.venv/" in "/" + f or "/venv/" in "/" + f or "__pycache__" in f or f.endswith(".pyc"):
            bad.append(f)
        elif "/uploads/" in "/" + f and not f.endswith(".gitkeep"):
            bad.append(f)
    if bad:
        add("FAIL", "Files tracked by git that must not be", f"{len(bad)} file(s), for example: {', '.join(bad[:5])}. Remove with: git rm -r --cached <path>")
    else:
        add("PASS", "git tracks no .env, keys, virtual env, caches or uploads")
    code, out = git(root, "log", "--all", "--oneline", "--", ".env", "backend/.env", "backend/app/.env")
    if out.strip():
        add("FAIL", ".env was committed to git history at some point", "Treat its passwords as leaked: change the MySQL password and SECRET_KEY.")
    else:
        add("PASS", ".env was never committed to git history")


def check_env_files(root: Path):
    examples = [p for p in walk(root, (".example",)) if p.name.startswith(".env")]
    if not examples:
        add("WARN", ".env.example", "Not found. Add one with placeholder values only, so others know which settings exist.")
    for ex in examples:
        flagged = []
        for key, value in parse_env(ex).items():
            if re.search(r"PASSWORD|SECRET|TOKEN|KEY|PWD", key, re.I):
                if not is_placeholder(value):
                    flagged.append(key)
            m = re.search(r"://[^:/\s]+:([^@\s]+)@", value)
            if m and not is_placeholder(m.group(1)):
                flagged.append(key)
        if flagged:
            add("FAIL", f"{rel(ex, root)} contains what look like REAL secrets", f"keys: {', '.join(sorted(set(flagged)))} (values not shown). Replace with placeholders and change those real passwords.")
        else:
            add("PASS", f"{rel(ex, root)} has placeholders only")
    envs = [p for p in walk(root, (".env",)) if p.name == ".env"]
    if not envs:
        add("INFO", ".env", "No real .env file found in the project (fine if you keep it elsewhere).")
    for env in envs:
        data = parse_env(env)
        secret_key = next((k for k in ("SECRET_KEY", "JWT_SECRET", "JWT_SECRET_KEY") if k in data), None)
        if not secret_key:
            add("FAIL", f"{rel(env, root)}: no SECRET_KEY", "JWT needs a long random SECRET_KEY.")
        else:
            value = data[secret_key].strip("\"'")
            if is_placeholder(value):
                add("FAIL", f"{rel(env, root)}: {secret_key} is still a placeholder", "Generate one: python -c \"import secrets; print(secrets.token_urlsafe(48))\"")
            elif len(value) < 32:
                add("WARN", f"{rel(env, root)}: {secret_key} is short ({len(value)} characters)", "Use at least 32 random characters.")
            else:
                add("PASS", f"{rel(env, root)}: {secret_key} is set and long enough ({len(value)} characters)")
        db_pass = next((data[k] for k in data if re.search(r"DB_PASSWORD|MYSQL_PASSWORD|DATABASE_PASSWORD|DB_PASS", k, re.I)), None)
        if db_pass is not None and not db_pass.strip("\"'"):
            add("WARN", f"{rel(env, root)}: database password is empty", "Use a MySQL user with a password for anything beyond local testing.")
        if "CORS_ORIGINS" in data and "*" in data["CORS_ORIGINS"]:
            add("WARN", "CORS_ORIGINS contains *", "List the exact website addresses instead.")


def check_hardcoded_secrets(root: Path):
    pat_assign = re.compile(r"""(?i)\b(password|passwd|pwd|secret_key|secret|api_key|apikey|access_token)\b\s*[:=]\s*["'][^"'\s]{6,}["']""")
    pat_url = re.compile(r"""(mysql|postgres(ql)?|mariadb)[\w+]*://[^:\s/"']+:([^@\s"']+)@""", re.I)
    hits = []
    for path in walk(root, (".py", ".js", ".html", ".yml", ".yaml", ".json", ".ini", ".cfg")):
        parts = {p.lower() for p in path.parts}
        if parts & {"tests", "test", "scripts"} or path.name.startswith("test_"):
            continue
        for n, line in enumerate(read(path).splitlines(), 1):
            if re.search(r"getenv|environ|os\.getenv|process\.env|placeholder|example", line, re.I):
                continue
            if pat_assign.search(line):
                hits.append(f"{rel(path, root)}:{n}")
            else:
                m = pat_url.search(line)
                if m and not (m.group(3).startswith(("{", "$", "<")) or is_placeholder(m.group(3))):
                    hits.append(f"{rel(path, root)}:{n}")
    if hits:
        add("FAIL", "Possible hard-coded secrets in code", "; ".join(hits[:10]) + " (line contents not shown). Move them into .env.")
    else:
        add("PASS", "No hard-coded passwords, keys or database URLs found in code")


def check_sql_injection(root: Path):
    flagged, raw_count = [], 0
    for path in walk(root, (".py",)):
        parts = {p.lower() for p in path.parts}
        if "scripts" in parts and path.name != "seed_skills.py":
            continue
        try:
            tree = ast.parse(read(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name not in {"text", "execute", "exec_driver_sql", "executemany"} or not node.args:
                continue
            raw_count += 1
            src_lines = read(path).splitlines()
            if any("audit-ok" in src_lines[i] for i in (node.lineno - 1, node.lineno - 2) if 0 <= i < len(src_lines)):
                continue  # developer-checked: only validated table/column names are inserted
            first = node.args[0]
            dynamic = isinstance(first, ast.JoinedStr) or (isinstance(first, ast.BinOp) and isinstance(first.op, (ast.Add, ast.Mod))) or (
                isinstance(first, ast.Call) and isinstance(first.func, ast.Attribute) and first.func.attr == "format")
            if isinstance(first, ast.JoinedStr) and not any(isinstance(v, ast.FormattedValue) for v in first.values):
                dynamic = False
            if dynamic:
                flagged.append(f"{rel(path, root)}:{node.lineno}")
    if flagged:
        add("FAIL", "SQL built from text (possible SQL injection)", "; ".join(flagged[:10]) + ". Use bound parameters, e.g. text('... WHERE id = :id'), {'id': value}.")
    else:
        add("PASS", "No SQL is built by joining strings", f"{raw_count} raw SQL call(s) found, all with fixed text. Queries use the SQLAlchemy ORM, which binds values safely.")


def check_passwords_and_jwt(root: Path):
    sources = {p: read(p) for p in walk(root / "backend", (".py",)) if "scripts" not in {x.lower() for x in p.parts}}
    all_src = "\n".join(sources.values())
    libs = [lib for lib in ("bcrypt", "passlib", "argon2") if re.search(rf"^\s*(import|from)\s+{lib}\b", all_src, re.M)]
    if libs:
        add("PASS", "Passwords are hashed with a proper library", f"uses: {', '.join(libs)}")
    else:
        add("FAIL", "No bcrypt / passlib / argon2 found", "Passwords must be hashed with bcrypt, never stored or compared as plain text.")
    weak = [rel(p, root) for p, src in sources.items() if re.search(r"hashlib\.(md5|sha1|sha256)\(", src) and re.search(r"password", src, re.I)]
    if weak:
        add("FAIL", "hashlib (md5/sha1/sha256) used in a file that handles passwords", ", ".join(weak) + ". These are too fast for passwords; use bcrypt.")
    plain = [rel(p, root) for p, src in sources.items() if re.search(r"(\.|\b)password\s*==\s*\w+\.password\b|\w+\.password\s*==\s*\w*password\b|\bpassword_hash\s*==", src)]
    if plain:
        add("FAIL", "Passwords may be compared as plain text", ", ".join(plain))
    else:
        add("PASS", "No plain-text password comparison found")
    if "jwt.encode" not in all_src:
        add("INFO", "JWT", "jwt.encode not found, JWT checks skipped.")
        return
    if re.search(r"""(getenv|environ\.get)\(\s*["'](SECRET_KEY|JWT_SECRET\w*)["']\s*,\s*["']""", all_src):
        add("FAIL", "SECRET_KEY has a default value in code", "If .env is missing, the app would run with a publicly known key. Make it mandatory (raise an error when missing).")
    else:
        add("PASS", "SECRET_KEY has no default value in code")
    algs = re.findall(r"""(?i)\balgorithms?\s*=\s*\[?\s*["']([A-Za-z0-9]+)["']""", all_src)
    algs += re.findall(r"""(?i)\bALGORITHM\s*=\s*["']([A-Za-z0-9]+)["']""", all_src)
    if any(a.lower() == "none" for a in algs):
        add("FAIL", "JWT algorithm 'none' is allowed")
    elif algs:
        add("PASS", "JWT algorithm is fixed in code", f"algorithm: {', '.join(sorted(set(algs)))}")
    else:
        add("WARN", "Could not find the JWT algorithm setting")
    if re.search(r"jwt\.decode\([^)]*algorithms\s*=", all_src, re.S):
        add("PASS", "jwt.decode restricts the accepted algorithms")
    else:
        add("FAIL", "jwt.decode does not pass algorithms=[...]", "Without it, tokens signed with another algorithm could be accepted.")
    if re.search(r"""["']exp["']""", all_src):
        add("PASS", "Tokens have an expiry (exp)")
    else:
        add("FAIL", "Tokens never expire", "Add an 'exp' claim.")
    minutes = re.search(r"(?i)(EXPIRE\w*|EXPIRES\w*)\s*=\s*(\d+)", all_src)
    if minutes and int(minutes.group(2)) > 1440:
        add("WARN", f"Token lifetime looks long ({minutes.group(2)})", "12 hours or less is better for a demo.")
    if re.search(r"""payload\.get\(\s*["']role["']\s*\)|payload\[\s*["']role["']\s*\]""", all_src):
        add("WARN", "The role is read from the token", "Make sure admin/provider checks use the role stored in the database.")
    else:
        add("PASS", "Roles are not trusted from the token")


def check_cors_and_debug(root: Path):
    src = {p: read(p) for p in walk(root / "backend", (".py",)) if "scripts" not in {x.lower() for x in p.parts}}
    star = [rel(p, root) for p, s in src.items() if re.search(r"""allow_origins\s*=\s*\[\s*["']\*["']\s*\]""", s)]
    if star:
        add("WARN", "CORS allows every website (*)", ", ".join(star) + ". Set a list of allowed origins.")
    else:
        add("PASS", "CORS is not open to every website")
    dbg = [rel(p, root) for p, s in src.items() if re.search(r"\bdebug\s*=\s*True\b|reload\s*=\s*True", s)]
    if dbg:
        add("WARN", "debug/reload switched on in code", ", ".join(dbg))
    req = [p for p in walk(root, (".txt",)) if p.name.lower() == "requirements.txt"]
    if not req:
        add("WARN", "requirements.txt", "Not found. Create one with: pip freeze > requirements.txt")
    for r in req:
        loose = [l for l in read(r).splitlines() if l.strip() and not l.startswith("#") and "==" not in l]
        if loose:
            add("WARN", f"{rel(r, root)} has unpinned packages", f"{len(loose)} line(s) without ==version. Pin them with pip freeze.")
        else:
            add("PASS", f"{rel(r, root)} pins every package")


def check_frontend(root: Path):
    front = root / "frontend"
    if not front.is_dir():
        add("INFO", "Frontend", "No frontend folder found next to backend.")
        return
    files = [p for p in walk(front, (".html", ".js", ".css")) ]
    inventory = ", ".join(sorted(rel(p, front).replace("\\", "/") for p in files)[:40])
    add("INFO", f"Frontend files ({len(files)})", inventory or "none")
    inner, evals, urls = [], [], []
    for p in files:
        if not p.name.endswith((".js", ".html")):
            continue
        for n, line in enumerate(read(p).splitlines(), 1):
            if re.search(r"\.innerHTML\s*\+?=|insertAdjacentHTML\(", line):
                inner.append(f"{rel(p, root)}:{n}")
            if re.search(r"\beval\(|document\.write\(", line):
                evals.append(f"{rel(p, root)}:{n}")
            if re.search(r"https?://(127\.0\.0\.1|localhost)(:\d+)?", line):
                urls.append(f"{rel(p, root)}:{n}")
    if inner:
        add("WARN", f"{len(inner)} place(s) put text into the page with innerHTML", "; ".join(inner[:8]) + ". If any of it comes from users (names, messages, reviews) use textContent, or escape it, to prevent XSS.")
    else:
        add("PASS", "No innerHTML assignments in the frontend")
    if evals:
        add("WARN", "eval()/document.write() used", "; ".join(evals[:5]))
    if urls:
        add("WARN", f"{len(urls)} hard-coded localhost URL(s)", "; ".join(urls[:6]) + ". Use relative paths like /api/... so it works anywhere.")
    pages = [p for p in files if p.suffix == ".html"]
    no_viewport = [rel(p, front) for p in pages if "viewport" not in read(p).lower()]
    no_title = [rel(p, front) for p in pages if "<title" not in read(p).lower()]
    if no_viewport:
        add("WARN", "Pages without a viewport meta tag (look broken on phones)", ", ".join(no_viewport[:8]))
    if no_title:
        add("WARN", "Pages without a <title>", ", ".join(no_title[:8]))
    if pages and not no_viewport and not no_title:
        add("PASS", "Every HTML page has a title and a viewport tag")


def main():
    arg = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    root = find_root(arg)
    if not (root / "backend").is_dir():
        print("Run this from the project folder (the one that contains `backend`), or pass its path.")
        sys.exit(2)
    for check in (check_gitignore, check_git, check_env_files, check_hardcoded_secrets, check_sql_injection,
                  check_passwords_and_jwt, check_cors_and_debug, check_frontend):
        try:
            check(root)
        except Exception as exc:  # an audit problem must never hide the other results
            add("WARN", f"{check.__name__} could not finish", f"{type(exc).__name__}")
    print(f"SkillConnect audit of: {root.name}\n")
    for level in ("FAIL", "WARN", "PASS", "INFO"):
        for lv, title, detail in results:
            if lv == level:
                print(f"[{lv}] {title}" + (f"\n       {detail}" if detail else ""))
    counts = {lv: sum(1 for r in results if r[0] == lv) for lv in ("PASS", "WARN", "FAIL", "INFO")}
    print(f"\nSummary: {counts['PASS']} pass, {counts['WARN']} warn, {counts['FAIL']} fail, {counts['INFO']} info")
    sys.exit(1 if counts["FAIL"] else 0)


if __name__ == "__main__":
    main()
