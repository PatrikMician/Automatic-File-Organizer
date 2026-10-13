"""
Automatický organizátor souborů - webová aplikace (Flask).

Aplikace funguje jako jednoduchý průzkumník souborů v bezpečné složce
"workspace". Umí procházet složky, nahrávat soubory, mazat/přejmenovat
a hlavně automaticky třídit soubory do složek podle pravidel
(typ souboru, přípona, datum, velikost) s náhledem a funkcí Zpět.
"""
import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory, abort

BASE_DIR = Path(__file__).resolve().parent
ROOT = (BASE_DIR / "workspace").resolve()   # sandbox - sem aplikace nikdy nesahá mimo
HISTORY_FILE = BASE_DIR / "history.json"
ROOT.mkdir(exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB

# ---------------------------------------------------------------- kategorie
CATEGORIES = {
    "Obrázky": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic", ".tiff"},
    "Dokumenty": {".pdf", ".doc", ".docx", ".odt", ".txt", ".rtf", ".md", ".pptx", ".ppt",
                  ".xls", ".xlsx", ".csv", ".ods", ".odp"},
    "Hudba": {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"},
    "Videa": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"},
    "Archivy": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Kód": {".py", ".js", ".html", ".css", ".java", ".c", ".cpp", ".cs", ".json", ".xml", ".sql", ".php"},
    "Programy": {".exe", ".msi", ".apk", ".dmg", ".deb", ".iso"},
}


def category_of(path: Path) -> str:
    ext = path.suffix.lower()
    for name, exts in CATEGORIES.items():
        if ext in exts:
            return name
    return "Ostatní"


# ---------------------------------------------------------------- pomocné
def safe_path(rel: str) -> Path:
    """Převede relativní cestu na absolutní a zajistí, že leží uvnitř ROOT."""
    rel = (rel or "").strip().lstrip("/\\")
    p = (ROOT / rel).resolve()
    if p != ROOT and ROOT not in p.parents:
        abort(400, "Cesta mimo povolenou složku")
    return p


def rel_of(p: Path) -> str:
    r = p.resolve().relative_to(ROOT)
    return "" if str(r) == "." else r.as_posix()


def unique_target(dest: Path) -> Path:
    """Pokud soubor existuje, přidá (1), (2), ... před příponu."""
    if not dest.exists():
        return dest
    i = 1
    while True:
        cand = dest.with_name(f"{dest.stem} ({i}){dest.suffix}")
        if not cand.exists():
            return cand
        i += 1


def info(p: Path) -> dict:
    st = p.stat()
    is_dir = p.is_dir()
    return {
        "name": p.name,
        "path": rel_of(p),
        "is_dir": is_dir,
        "size": None if is_dir else st.st_size,
        "modified": datetime.fromtimestamp(st.st_mtime).strftime("%d.%m.%Y %H:%M"),
        "category": "Složka" if is_dir else category_of(p),
        "ext": "" if is_dir else p.suffix.lower().lstrip("."),
    }


def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def save_history(h: list) -> None:
    HISTORY_FILE.write_text(json.dumps(h[-50:], ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- stránky
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ---------------------------------------------------------------- API: průzkumník
@app.route("/api/list")
def api_list():
    p = safe_path(request.args.get("path", ""))
    if not p.is_dir():
        abort(404, "Složka neexistuje")
    items = [info(c) for c in p.iterdir()]
    items.sort(key=lambda i: (not i["is_dir"], i["name"].lower()))
    crumbs, acc = [{"name": "workspace", "path": ""}], ""
    for part in [x for x in rel_of(p).split("/") if x]:
        acc = f"{acc}/{part}".lstrip("/")
        crumbs.append({"name": part, "path": acc})
    return jsonify({"path": rel_of(p), "items": items, "breadcrumbs": crumbs})


@app.route("/api/tree")
def api_tree():
    def walk(d: Path, depth=0):
        out = []
        for c in sorted(d.iterdir(), key=lambda x: x.name.lower()):
            if c.is_dir():
                out.append({"name": c.name, "path": rel_of(c),
                            "children": walk(c, depth + 1) if depth < 4 else []})
        return out
    return jsonify({"name": "workspace", "path": "", "children": walk(ROOT)})


@app.route("/api/mkdir", methods=["POST"])
def api_mkdir():
    data = request.get_json(force=True)
    parent = safe_path(data.get("path", ""))
    name = os.path.basename(data.get("name", "").strip())
    if not name:
        abort(400, "Chybí název")
    (parent / name).mkdir(exist_ok=True)
    return jsonify(ok=True)


@app.route("/api/rename", methods=["POST"])
def api_rename():
    data = request.get_json(force=True)
    src = safe_path(data["path"])
    new = os.path.basename(data.get("name", "").strip())
    if not new or src == ROOT:
        abort(400, "Neplatný název")
    dst = src.with_name(new)
    if dst.exists():
        abort(409, "Takový název už existuje")
    src.rename(dst)
    return jsonify(ok=True)


@app.route("/api/delete", methods=["POST"])
def api_delete():
    data = request.get_json(force=True)
    for rel in data.get("paths", []):
        p = safe_path(rel)
        if p == ROOT:
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
    return jsonify(ok=True)


@app.route("/api/upload", methods=["POST"])
def api_upload():
    dest = safe_path(request.form.get("path", ""))
    saved = 0
    for f in request.files.getlist("files"):
        name = os.path.basename(f.filename or "")
        if not name:
            continue
        f.save(unique_target(dest / name))
        saved += 1
    return jsonify(ok=True, saved=saved)


@app.route("/api/download")
def api_download():
    p = safe_path(request.args.get("path", ""))
    if not p.is_file():
        abort(404)
    return send_file(p, as_attachment=True)


@app.route("/api/preview")
def api_preview():
    p = safe_path(request.args.get("path", ""))
    if not p.is_file():
        abort(404)
    return send_file(p)


@app.route("/api/stats")
def api_stats():
    p = safe_path(request.args.get("path", ""))
    counts, sizes = {}, {}
    total = 0
    for f in p.rglob("*"):
        if f.is_file():
            c = category_of(f)
            counts[c] = counts.get(c, 0) + 1
            sizes[c] = sizes.get(c, 0) + f.stat().st_size
            total += 1
    return jsonify(total=total, counts=counts, sizes=sizes)


# ---------------------------------------------------------------- API: organizátor
def plan_moves(base: Path, mode: str, recursive: bool, size_limit_mb: float) -> list:
    """Vytvoří plán přesunů (bez provedení). mode: type | extension | date | size"""
    files = [f for f in (base.rglob("*") if recursive else base.iterdir()) if f.is_file()]
    plan = []
    for f in files:
        if mode == "type":
            folder = category_of(f)
        elif mode == "extension":
            folder = f.suffix.lower().lstrip(".") or "bez_pripony"
        elif mode == "date":
            d = datetime.fromtimestamp(f.stat().st_mtime)
            folder = f"{d.year}/{d.month:02d}"
        elif mode == "size":
            folder = "Velké" if f.stat().st_size >= size_limit_mb * 1024 * 1024 else "Malé"
        else:
            abort(400, "Neznámý režim")
        target_dir = base / folder
        if f.parent == target_dir:
            continue  # už je na správném místě
        plan.append({"from": rel_of(f), "to_dir": rel_of(target_dir), "name": f.name,
                     "folder": folder, "size": f.stat().st_size})
    return plan


@app.route("/api/organize/preview", methods=["POST"])
def api_preview_org():
    d = request.get_json(force=True)
    base = safe_path(d.get("path", ""))
    plan = plan_moves(base, d.get("mode", "type"), bool(d.get("recursive")),
                      float(d.get("size_limit_mb", 10)))
    summary = {}
    for m in plan:
        summary[m["folder"]] = summary.get(m["folder"], 0) + 1
    return jsonify(plan=plan, summary=summary, count=len(plan))


@app.route("/api/organize/run", methods=["POST"])
def api_run_org():
    d = request.get_json(force=True)
    base = safe_path(d.get("path", ""))
    plan = plan_moves(base, d.get("mode", "type"), bool(d.get("recursive")),
                      float(d.get("size_limit_mb", 10)))
    moved = []
    for m in plan:
        src = safe_path(m["from"])
        target_dir = safe_path(m["to_dir"])
        target_dir.mkdir(parents=True, exist_ok=True)
        dst = unique_target(target_dir / src.name)
        shutil.move(str(src), str(dst))
        moved.append({"from": rel_of(src), "to": rel_of(dst)})
    if d.get("cleanup", True):
        remove_empty_dirs(base)
    if moved:
        h = load_history()
        h.append({"time": datetime.now().strftime("%d.%m.%Y %H:%M:%S"), "mode": d.get("mode"),
                  "path": rel_of(base), "moves": moved})
        save_history(h)
    return jsonify(ok=True, moved=len(moved))


def remove_empty_dirs(base: Path) -> None:
    for dirpath, _dirs, _files in os.walk(base, topdown=False):
        p = Path(dirpath)
        if p != base and not any(p.iterdir()):
            p.rmdir()


@app.route("/api/history")
def api_history():
    h = load_history()
    return jsonify([{"index": i, "time": x["time"], "mode": x["mode"], "path": x["path"],
                     "count": len(x["moves"])} for i, x in enumerate(h)][::-1])


@app.route("/api/organize/undo", methods=["POST"])
def api_undo():
    h = load_history()
    if not h:
        abort(404, "Není co vracet")
    last = h.pop()
    restored = 0
    for m in reversed(last["moves"]):
        cur, orig = ROOT / m["to"], ROOT / m["from"]
        if cur.exists():
            orig.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(cur), str(unique_target(orig)))
            restored += 1
    remove_empty_dirs(ROOT)
    save_history(h)
    return jsonify(ok=True, restored=restored)


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(409)
def err(e):
    return jsonify(error=getattr(e, "description", "Chyba")), e.code


if __name__ == "__main__":
    print(f"Pracovní složka: {ROOT}")
    print("Otevři v prohlížeči: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
