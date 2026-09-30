"""Réussite+ — plateforme scolaire (Flask + SQLite). Lancer : python app.py"""
import os, re, sys, random, sqlite3, secrets, unicodedata
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, g, request, session, redirect, url_for, render_template, abort, flash, jsonify, Response
from jinja2 import DictLoader
from werkzeug.security import generate_password_hash, check_password_hash
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(os.environ.get("APP_TZ", "Africa/Dakar"))
except Exception:
    TZ = timezone.utc

DB = os.environ.get("DB", "reussite.db")
DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
TYPES = ["Cours", "Révision", "Devoir", "Exercices", "Pause", "Autre"]
SUBJECTS = ["Mathématiques", "Physique-Chimie", "Français", "Anglais", "Culture générale"]
MOTIV = ["Chaque séance compte : la régularité bat l'intensité.", "Une semaine à la fois. Fais mieux que la précédente.",
         "Tes erreurs d'aujourd'hui sont tes points gagnés de demain.", "Commence petit, mais commence maintenant.",
         "Le bac se prépare par des habitudes, pas par des miracles.", "Repose-toi aussi : un cerveau reposé retient mieux."]

def now(): return datetime.now(TZ)
def ts(sec=0): return (now() - timedelta(seconds=sec)).strftime("%Y-%m-%d %H:%M:%S")

def secret():
    k = os.environ.get("SECRET_KEY")
    if k: return k
    if not os.path.exists("secret.key"):
        with open("secret.key", "w") as f: f.write(secrets.token_hex(32))
        try: os.chmod("secret.key", 0o600)
        except OSError: pass
    return open("secret.key").read().strip()

app = Flask(__name__)
app.config.update(SECRET_KEY=secret(), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=os.environ.get("HTTPS") == "1", PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
                  MAX_CONTENT_LENGTH=64 * 1024)

# ---------- base de données ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB); g.db.row_factory = sqlite3.Row; g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(e):
    d = g.pop("db", None)
    if d: d.close()

def q(sql, a=(), one=False):
    c = db().execute(sql, a); r = c.fetchone() if one else c.fetchall(); db().commit(); return r

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, pw TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'eleve', active INTEGER NOT NULL DEFAULT 1, bac INTEGER NOT NULL DEFAULT 0, goal INTEGER NOT NULL DEFAULT 300, created TEXT);
CREATE TABLE IF NOT EXISTS slots(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, day INTEGER, start TEXT, end TEXT, subject TEXT, type TEXT, descr TEXT, reminder INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS subj(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, name TEXT, coef REAL, PRIMARY KEY(user_id,name));
CREATE TABLE IF NOT EXISTS grades(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, subject TEXT, label TEXT, value REAL, weight REAL, created TEXT);
CREATE TABLE IF NOT EXISTS exercises(id INTEGER PRIMARY KEY, subject TEXT, topic TEXT, question TEXT, answer TEXT);
CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE CASCADE, ok INTEGER, created TEXT);
CREATE TABLE IF NOT EXISTS work(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, subject TEXT, kind TEXT, minutes INTEGER, created TEXT);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, content TEXT, status TEXT, reason TEXT, action TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, user_id INTEGER, kind TEXT, detail TEXT, ip TEXT, created TEXT);
"""
SEED = [("Mathématiques", "Calcul", "Combien font 7 × 8 ?", "56"), ("Mathématiques", "Calcul", "Dérivée de x² ? (réponse : 2x)", "2x"),
        ("Mathématiques", "Probabilités", "Probabilité d'obtenir pile avec une pièce équilibrée ? (fraction)", "1/2"),
        ("Physique-Chimie", "Mécanique", "Unité de la force dans le SI ?", "newton"), ("Physique-Chimie", "Chimie", "Formule chimique de l'eau ?", "h2o"),
        ("Français", "Grammaire", "Passé simple de « il chante » (3e pers. sing.) : il ... ?", "chanta"), ("Français", "Littérature", "Auteur des « Misérables » ?", "victor hugo"),
        ("Anglais", "Vocabulaire", "Traduction anglaise de « livre » ?", "book"), ("Anglais", "Grammaire", "Past simple de « go » ?", "went"),
        ("Culture générale", "Géographie", "Capitale du Sénégal ?", "dakar"), ("Culture générale", "Sciences", "Planète la plus proche du Soleil ?", "mercure")]

def init_db():
    c = sqlite3.connect(DB); c.executescript(SCHEMA)
    if not c.execute("SELECT 1 FROM exercises").fetchone():
        c.executemany("INSERT INTO exercises(subject,topic,question,answer) VALUES(?,?,?,?)", SEED)
    c.commit(); c.close()

def log(kind, detail="", uid=None):
    q("INSERT INTO events(user_id,kind,detail,ip,created) VALUES(?,?,?,?,?)", (uid or session.get("uid"), kind, str(detail)[:200], request.remote_addr, ts()))

# ---------- sécurité ----------
def token():
    if "csrf" not in session: session["csrf"] = secrets.token_hex(16)
    return session["csrf"]

@app.before_request
def csrf_guard():
    if request.method == "POST":
        if not secrets.compare_digest(request.form.get("_csrf", "").encode(), session.get("csrf", "x").encode()):
            abort(400)

@app.after_request
def headers(r):
    r.headers["X-Content-Type-Options"] = "nosniff"; r.headers["X-Frame-Options"] = "DENY"
    r.headers["Referrer-Policy"] = "same-origin"
    r.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
    if request.endpoint != "sw": r.headers["Cache-Control"] = "no-store"
    return r

@app.errorhandler(403)
def e403(e): return render_template("err.html", msg="Accès refusé."), 403
@app.errorhandler(404)
def e404(e): return render_template("err.html", msg="Page introuvable."), 404
@app.errorhandler(400)
def e400(e): return render_template("err.html", msg="Requête invalide. Recharge la page."), 400

def cur():
    if "uid" not in session: return None
    u = q("SELECT * FROM users WHERE id=?", (session["uid"],), True)
    if not u or not u["active"]: session.clear(); return None
    return u

def need(admin=False):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            u = cur()
            if not u: return redirect(url_for("login"))
            if admin and u["role"] != "admin": log("forbidden", request.path, u["id"]); abort(403)
            g.u = u; return f(*a, **k)
        return w
    return deco

@app.context_processor
def ctx(): return dict(u=g.get("u"), csrf=token(), DAYS=DAYS, TYPES=TYPES, SUBJECTS=SUBJECTS)

# ---------- comptes ----------
@app.route("/")
def index(): return redirect(url_for("dash" if cur() else "login"))

@app.route("/inscription", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if q("SELECT COUNT(*) c FROM events WHERE kind='register' AND ip=? AND created>?", (request.remote_addr, ts(3600)), True)["c"] >= 5:
            log("register_blocked"); flash("Trop de créations de compte depuis ce réseau. Réessaie plus tard."); return render_template("register.html"), 429
        n, p = request.form.get("username", "").strip(), request.form.get("password", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", n) or len(p) < 8:
            flash("Identifiant : 3 à 30 caractères (lettres, chiffres, _ . -). Mot de passe : 8 caractères minimum."); return render_template("register.html")
        if q("SELECT 1 FROM users WHERE username=?", (n,), True):
            flash("Cet identifiant est déjà pris."); return render_template("register.html")
        q("INSERT INTO users(username,pw,role,bac,created) VALUES(?,?,?,?,?)", (n, generate_password_hash(p), "eleve", 1 if request.form.get("bac") else 0, ts()))
        log("register", n); flash("Compte créé. Connecte-toi."); return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/connexion", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        n, p = request.form.get("username", "").strip(), request.form.get("password", "")
        if q("SELECT COUNT(*) c FROM events WHERE kind='login_fail' AND (detail=? OR ip=?) AND created>?", (n, request.remote_addr, ts(900)), True)["c"] >= 5:
            log("login_blocked", n); flash("Trop de tentatives. Réessaie dans 15 minutes."); return render_template("login.html"), 429
        u = q("SELECT * FROM users WHERE username=?", (n,), True)
        if u and u["active"] and check_password_hash(u["pw"], p):
            session.clear(); session["uid"] = u["id"]; session.permanent = True
            log("login", n, u["id"]); return redirect(url_for("dash"))
        log("login_fail", n); flash("Identifiant ou mot de passe incorrect.")
    return render_template("login.html")

@app.route("/deconnexion", methods=["POST"])
def logout():
    if "uid" in session: log("logout")
    session.clear(); return redirect(url_for("login"))

# ---------- emploi du temps & rappels ----------
def upcoming(uid):
    n = now(); out = []
    for s in q("SELECT * FROM slots WHERE user_id=?", (uid,)):
        h, m = map(int, s["start"].split(":")); t = (n + timedelta(days=(s["day"] - n.weekday()) % 7)).replace(hour=h, minute=m, second=0, microsecond=0)
        if t < n: t += timedelta(days=7)
        out.append((t, s))
    return sorted(out, key=lambda x: x[0])

HM = re.compile(r"([01]\d|2[0-3]):[0-5]\d")

@app.route("/emploi", methods=["GET", "POST"])
@need()
def schedule():
    uid = g.u["id"]; f = request.form
    if request.method == "POST":
        try:
            d, s, e, sub, t = int(f["day"]), f["start"], f["end"], f.get("subject", "").strip()[:60], f.get("type")
            r = max(0, min(int(f.get("reminder") or 0), 1440)); ok = 0 <= d <= 6 and HM.fullmatch(s) and HM.fullmatch(e) and e >= s and t in TYPES
        except (KeyError, ValueError): ok = False
        if not ok: flash("Champs invalides : vérifie le jour, les heures (fin après début) et le type.")
        else:
            vals = (d, s, e, sub, t, f.get("descr", "").strip()[:200], r)
            if f.get("id"): q("UPDATE slots SET day=?,start=?,end=?,subject=?,type=?,descr=?,reminder=? WHERE id=? AND user_id=?", vals + (f["id"], uid))
            else: q("INSERT INTO slots(day,start,end,subject,type,descr,reminder,user_id) VALUES(?,?,?,?,?,?,?,?)", vals + (uid,))
            flash("Emploi du temps enregistré.")
        return redirect(url_for("schedule"))
    edit = q("SELECT * FROM slots WHERE id=? AND user_id=?", (request.args.get("edit", 0), uid), True)
    slots = q("SELECT * FROM slots WHERE user_id=? ORDER BY day,start", (uid,))
    return render_template("schedule.html", slots=slots, edit=edit)

@app.route("/emploi/<int:i>/supprimer", methods=["POST"])
@need()
def slot_del(i):
    q("DELETE FROM slots WHERE id=? AND user_id=?", (i, g.u["id"])); flash("Créneau supprimé."); return redirect(url_for("schedule"))

@app.route("/api/rappels")
@need()
def due():
    n = now(); out = []
    for t, s in upcoming(g.u["id"]):
        if s["reminder"] and 0 <= (t - n).total_seconds() <= s["reminder"] * 60:
            out.append(dict(key=f'{s["id"]}-{t:%Y%m%d%H%M}', title=f'{s["type"]} : {s["subject"] or "à venir"}', at=t.strftime("%H:%M")))
    return jsonify(out)

# ---------- notes ----------
def averages(uid):
    subj = {}
    for r in q("SELECT * FROM grades WHERE user_id=? ORDER BY created", (uid,)): subj.setdefault(r["subject"], []).append(r)
    coefs = {c["name"]: c["coef"] for c in q("SELECT * FROM subj WHERE user_id=?", (uid,))}
    res, tot, sw = [], 0, 0
    for name, rows in subj.items():
        w = sum(r["weight"] for r in rows); a = sum(r["value"] * r["weight"] for r in rows) / w
        prev = (sum(r["value"] * r["weight"] for r in rows[:-1]) / sum(r["weight"] for r in rows[:-1])) if len(rows) > 1 else None
        c = coefs.get(name, 1); res.append(dict(name=name, avg=round(a, 2), coef=c, n=len(rows), trend=None if prev is None else round(a - prev, 2))); tot += a * c; sw += c
    return res, (round(tot / sw, 2) if sw else None)

@app.route("/notes", methods=["GET", "POST"])
@need()
def grades():
    uid = g.u["id"]; f = request.form
    if request.method == "POST":
        try:
            v, w, c, s = float(f["value"].replace(",", ".")), float(f.get("weight", "1").replace(",", ".")), float(f.get("coef", "1").replace(",", ".")), f["subject"].strip()[:60]
            assert 0 <= v <= 20 and w > 0 and c > 0 and s
        except (KeyError, ValueError, AssertionError): flash("Note invalide : entre une matière, une note sur 20 et des coefficients positifs."); return redirect(url_for("grades"))
        q("INSERT INTO grades(user_id,subject,label,value,weight,created) VALUES(?,?,?,?,?,?)", (uid, s, f.get("label", "").strip()[:60], v, w, ts()))
        q("INSERT INTO subj(user_id,name,coef) VALUES(?,?,?) ON CONFLICT(user_id,name) DO UPDATE SET coef=excluded.coef", (uid, s, c))
        flash("Note enregistrée."); return redirect(url_for("grades"))
    subj, gen = averages(uid)
    return render_template("grades.html", subj=subj, gen=gen, rows=q("SELECT * FROM grades WHERE user_id=? ORDER BY created DESC", (uid,)))

@app.route("/notes/<int:i>/supprimer", methods=["POST"])
@need()
def grade_del(i):
    q("DELETE FROM grades WHERE id=? AND user_id=?", (i, g.u["id"])); return redirect(url_for("grades"))

# ---------- exercices ----------
def weak(uid, subject=None):
    sql = "SELECT e.subject s,e.topic t,COUNT(*) n,AVG(r.ok) a FROM results r JOIN exercises e ON e.id=r.exercise_id WHERE r.user_id=?"
    a = [uid]
    if subject: sql += " AND e.subject=?"; a.append(subject)
    return q(sql + " GROUP BY e.subject,e.topic ORDER BY a", a)

def pick(uid, subject):
    w = [x for x in weak(uid, subject) if x["a"] < 0.7]
    done = {r["exercise_id"] for r in q("SELECT exercise_id FROM results WHERE user_id=? AND ok=1", (uid,))}
    pool = q("SELECT * FROM exercises WHERE subject=?", (subject,))
    if w: pool2 = [e for e in pool if e["topic"] == w[0]["t"]] or pool
    else: pool2 = pool
    todo = [e for e in pool2 if e["id"] not in done] or [e for e in pool if e["id"] not in done] or pool
    return (random.choice(todo) if todo else None), (w[0]["t"] if w else None)

def nrm(t): return re.sub(r"\s+", " ", "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")).strip()

@app.route("/exercices")
@need()
def exercises():
    s = request.args.get("subject"); ex = focus = None
    if s in SUBJECTS: ex, focus = pick(g.u["id"], s)
    return render_template("exercises.html", s=s, ex=ex, focus=focus, weak=weak(g.u["id"]))

@app.route("/exercices/<int:i>", methods=["POST"])
@need()
def answer(i):
    e = q("SELECT * FROM exercises WHERE id=?", (i,), True) or abort(404)
    ok = int(nrm(request.form.get("answer", "")) == nrm(e["answer"]))
    q("INSERT INTO results(user_id,exercise_id,ok,created) VALUES(?,?,?,?)", (g.u["id"], i, ok, ts()))
    flash("Bonne réponse !" if ok else f"Incorrect. Réponse attendue : {e['answer']}")
    return redirect(url_for("exercises", subject=e["subject"]))

# ---------- progression, bilan, bac ----------
def week_stats(uid, n=8):
    mon = (now() - timedelta(days=now().weekday())).replace(hour=0, minute=0, second=0, microsecond=0); out = []
    for i in range(n - 1, -1, -1):
        a = mon - timedelta(days=7 * i); b = a + timedelta(days=7); A, B = a.strftime("%Y-%m-%d %H:%M:%S"), b.strftime("%Y-%m-%d %H:%M:%S")
        w = q("SELECT COALESCE(SUM(minutes),0) m,COUNT(*) n,COALESCE(SUM(kind='Devoir'),0) d FROM work WHERE user_id=? AND created>=? AND created<?", (uid, A, B), True)
        x = q("SELECT COUNT(*) n,COALESCE(SUM(ok),0) k FROM results WHERE user_id=? AND created>=? AND created<?", (uid, A, B), True)
        out.append(dict(label=a.strftime("%d/%m"), minutes=w["m"], sessions=w["n"], homework=w["d"], exos=x["n"], good=x["k"]))
    return out

@app.route("/bilan", methods=["GET", "POST"])
@need()
def review():
    uid = g.u["id"]; f = request.form
    if request.method == "POST":
        if f.get("goal"):
            try: q("UPDATE users SET goal=? WHERE id=?", (max(10, min(int(f["goal"]), 3000)), uid)); flash("Objectif mis à jour.")
            except ValueError: flash("Objectif invalide.")
        else:
            try:
                m = int(f["minutes"]); assert 1 <= m <= 720 and f.get("kind") in TYPES
                q("INSERT INTO work(user_id,subject,kind,minutes,created) VALUES(?,?,?,?,?)", (uid, f.get("subject", "").strip()[:60], f["kind"], m, ts())); flash("Séance enregistrée.")
            except (KeyError, ValueError, AssertionError): flash("Séance invalide (1 à 720 minutes).")
        return redirect(url_for("review"))
    ws = week_stats(uid); return render_template("review.html", ws=ws, mx=max([w["minutes"] for w in ws] + [1]), cur=ws[-1], motiv=MOTIV[now().isocalendar()[1] % len(MOTIV)])

@app.route("/tableau")
@need()
def dash():
    uid = g.u["id"]; subj, gen = averages(uid); ws = week_stats(uid, 1)[0]
    return render_template("dash.html", nxt=upcoming(uid)[:4], gen=gen, cur=ws, weak=weak(uid)[:3], motiv=MOTIV[now().isocalendar()[1] % len(MOTIV)])

# ---------- discussion & modération ----------
def chat_open(): n = now(); return n.weekday() == 5 and n.hour >= 14   # samedi 14h00 -> 00h00, heure du serveur

INS = ["idiot", "imbecile", "connard", "connasse", "salope", "cretin", "debile", "abruti", "enfoire", "ordure"]
RE_INS = "|".join(INS)
RE_DIR = re.compile(r"\b(tu|t|toi|vous)\b\W+(?:\w+\W+){0,2}(?:%s)" % RE_INS)
RE_THR = re.compile(r"\bje\s+(?:vais|va)\s+(?:te|vous)\s+(?:tuer|frapper|massacrer|casser)|\bje\s+te\s+(?:tue|frappe|casse)\b|\bon\s+va\s+te\s+retrouver")
RE_DIS = re.compile(r"\bsales?\s+(?:noirs?|arabes?|negres?|juifs?|blancs?|pauvres?|handicapes?)\b|\bretourne\s+dans\s+ton\s+pays")

def moderate(uid, text):
    n = nrm(text)
    if len(text) > 500: return "blocked", "message trop long"
    if len(re.findall(r"https?://|www\.", n)) > 2: return "blocked", "spam (liens)"
    if q("SELECT 1 FROM messages WHERE user_id=? AND content=? AND created>?", (uid, text, ts(300)), True): return "blocked", "spam (message répété)"
    if q("SELECT COUNT(*) c FROM messages WHERE user_id=? AND created>?", (uid, ts(60)), True)["c"] >= 5: return "blocked", "spam (trop rapide)"
    if RE_THR.search(n): return "blocked", "menace"
    if RE_DIS.search(n): return "blocked", "propos discriminatoire"
    for m in re.finditer(r"\b(?:\w[\W_]){4,}\w\b", n):
        if re.sub(r"[\W_]", "", m.group()) in INS: return "blocked", "contournement de la modération"
    if RE_DIR.search(n): return "blocked", "insulte"
    if re.search(RE_INS, n): return "pending", "mot ambigu : vérification par la modération"
    return "ok", ""

@app.route("/discussion", methods=["GET", "POST"])
@need()
def chat():
    uid = g.u["id"]
    if request.method == "POST":
        text = request.form.get("content", "").strip()
        if not chat_open(): log("chat_closed_attempt"); flash("La discussion est fermée. Ouverture le samedi de 14h00 à 00h00."); return redirect(url_for("chat"))
        if not text: return redirect(url_for("chat"))
        st, why = moderate(uid, text)
        if st == "blocked" and q("SELECT COUNT(*) c FROM messages WHERE user_id=? AND status='blocked' AND created>?", (uid, ts(3600)), True)["c"] >= 3:
            why = "tentatives répétées : " + why; log("moderation_evasion", why)
        q("INSERT INTO messages(user_id,content,status,reason,created) VALUES(?,?,?,?,?)", (uid, text, st, why, ts()))
        flash({"ok": "Message publié.", "pending": "Message envoyé à la modération.", "blocked": "Message bloqué : " + why + "."}[st]); return redirect(url_for("chat"))
    msgs = q("SELECT m.*,u.username FROM messages m JOIN users u ON u.id=m.user_id WHERE m.status='ok' OR m.action='approved' ORDER BY m.id DESC LIMIT 100")
    return render_template("chat.html", msgs=msgs, open=chat_open())

@app.route("/discussion/<int:i>/signaler", methods=["POST"])
@need()
def report(i):
    q("UPDATE messages SET status='pending',reason='signalé par ' || ?,action=NULL WHERE id=? AND status='ok'", (g.u["username"], i)); flash("Message signalé à la modération."); return redirect(url_for("chat"))

# ---------- administration ----------
@app.route("/admin")
@need(admin=True)
def admin():
    n = lambda t, w="1": q(f"SELECT COUNT(*) c FROM {t} WHERE {w}", (), True)["c"]
    st = dict(eleves=n("users", "role='eleve'"), actifs=n("users", "role='eleve' AND active=1"), notes=n("grades"), reponses=n("results"), messages=n("messages"))
    return render_template("admin.html", st=st, users=q("SELECT * FROM users ORDER BY id"), exs=q("SELECT * FROM exercises ORDER BY subject,topic"),
        mod=q("SELECT m.*,u.username FROM messages m JOIN users u ON u.id=m.user_id WHERE m.status IN ('blocked','pending') AND m.action IS NULL ORDER BY m.id DESC LIMIT 50"),
        ev=q("SELECT * FROM events ORDER BY id DESC LIMIT 40"), day=q("SELECT COUNT(*) c FROM events WHERE kind IN ('login_fail','login_blocked','forbidden','register_blocked','moderation_evasion','chat_closed_attempt') AND created>?", (ts(86400),), True)["c"])

@app.route("/admin/user/<int:i>/basculer", methods=["POST"])
@need(admin=True)
def toggle(i):
    if i == g.u["id"]: flash("Tu ne peux pas suspendre ton propre compte.")
    else: q("UPDATE users SET active=1-active WHERE id=?", (i,)); log("account_toggle", i)
    return redirect(url_for("admin"))

@app.route("/admin/message/<int:i>/<act>", methods=["POST"])
@need(admin=True)
def moderate_msg(i, act):
    if act not in ("approved", "deleted"): abort(404)
    q("UPDATE messages SET action=? WHERE id=?", (act, i)); log("moderation", f"{i}:{act}"); return redirect(url_for("admin"))

@app.route("/admin/exercice", methods=["POST"])
@need(admin=True)
def exo_add():
    f = request.form; v = [f.get(k, "").strip() for k in ("subject", "topic", "question", "answer")]
    if all(v): q("INSERT INTO exercises(subject,topic,question,answer) VALUES(?,?,?,?)", v); flash("Exercice ajouté.")
    else: flash("Tous les champs sont requis.")
    return redirect(url_for("admin"))

@app.route("/admin/exercice/<int:i>/supprimer", methods=["POST"])
@need(admin=True)
def exo_del(i): q("DELETE FROM exercises WHERE id=?", (i,)); return redirect(url_for("admin"))

# ---------- PWA ----------
@app.route("/manifest.json")
def manifest():
    return jsonify(name="Réussite+", short_name="Réussite+", start_url="/", display="standalone", background_color="#f1f4f8", theme_color="#0f4c5c", lang="fr")

@app.route("/sw.js")
def sw():
    return Response("self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(clients.claim()));"
                    "self.addEventListener('notificationclick',e=>{e.notification.close();e.waitUntil(clients.openWindow('/tableau'))});", mimetype="application/javascript")

# ---------- gabarits ----------
CSS = """:root{--ink:#12263a;--bg:#f1f4f8;--card:#fff;--teal:#0f4c5c;--acc:#e36414;--ok:#2a7f62;--bad:#b42318;--line:#d5dde6}
@media(prefers-color-scheme:dark){:root{--ink:#e6edf3;--bg:#0e1a24;--card:#16263a;--line:#2a3f55;--teal:#5fb3c4}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{display:flex;flex-wrap:wrap;gap:.5rem 1rem;align-items:center;padding:.7rem 1rem;border-bottom:2px solid var(--teal);background:var(--card)}
.brand{font:700 1.4rem Georgia,serif;color:var(--teal);text-decoration:none}.brand::after{content:"+";color:var(--acc)}
nav{display:flex;flex-wrap:wrap;gap:.2rem .9rem;flex:1}nav a,nav button{color:var(--ink);background:none;border:0;font:inherit;padding:.2rem 0;cursor:pointer;text-decoration:none}
nav a:hover,a:hover{text-decoration:underline}main{max-width:900px;margin:0 auto;padding:1rem}
h1{font:700 1.7rem Georgia,serif;margin:.3rem 0 1rem}h2{font-size:1.15rem;margin:1.4rem 0 .5rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:1rem;margin:.8rem 0;overflow-x:auto}
.flash{background:var(--card);border-left:4px solid var(--acc);padding:.6rem .9rem;margin:.6rem 0}
label{display:block;font-weight:600;margin:.5rem 0 .15rem}input,select,textarea{width:100%;padding:.55rem;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink);font:inherit}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.6rem}
button.b,.b{background:var(--teal);color:#fff;border:0;border-radius:6px;padding:.55rem 1rem;font:inherit;cursor:pointer;margin-top:.7rem;text-decoration:none;display:inline-block}
.b.red{background:var(--bad)}.b.g{background:var(--ok)}.b.s{padding:.2rem .6rem;margin:0;font-size:.85rem}
table{width:100%;border-collapse:collapse}td,th{padding:.4rem .5rem;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.big{font:700 2.2rem Georgia,serif;color:var(--teal)}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.8rem}
.bars{display:flex;gap:.5rem;align-items:flex-end;height:170px}.bar{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%;font-size:.75rem}
.bar i{display:block;width:100%;background:var(--teal);border-radius:4px 4px 0 0;min-height:2px}.prog{background:var(--line);border-radius:6px;height:12px;overflow:hidden}.prog i{display:block;height:100%;background:var(--acc)}
.up{color:var(--ok)}.dn{color:var(--bad)}.muted{opacity:.7;font-size:.9rem}.msg{border-bottom:1px solid var(--line);padding:.5rem 0}
:focus-visible{outline:3px solid var(--acc);outline-offset:2px}"""

def T(body): return "{% extends 'base.html' %}{% block c %}" + body + "{% endblock %}"
CSRF = '<input type="hidden" name="_csrf" value="{{csrf}}">'
BAR = '<div class="bars">{% for w in ws %}<div class="bar"><b>{{ w.minutes }}</b><i style="height:{{ (w.minutes/mx*130)|round|int }}px"></i><span>{{ w.label }}</span></div>{% endfor %}</div>'
LOGIN = lambda t, extra, b: T(f'<h1>{t}</h1><form class="card" method="post">{CSRF}<label>Identifiant</label><input name="username" required autocomplete="username"><label>Mot de passe</label><input name="password" type="password" required autocomplete="{ "new-password" if extra else "current-password" }">{extra}<button class="b">{b}</button></form>')

TEMPLATES = {
"base.html": """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Réussite+</title>
<link rel="manifest" href="/manifest.json"><meta name="theme-color" content="#0f4c5c"><style>""" + CSS + """</style></head><body>
<header><a class="brand" href="/">Réussite</a>{% if u %}<nav><a href="/tableau">Tableau de bord</a><a href="/emploi">Emploi du temps</a><a href="/notes">Notes</a><a href="/exercices">Exercices</a><a href="/bilan">Bilan</a><a href="/discussion">Discussion</a>{% if u.role=='admin' %}<a href="/admin">Admin</a>{% endif %}
<form method="post" action="/deconnexion" style="margin-left:auto"><input type="hidden" name="_csrf" value="{{csrf}}"><button>Déconnexion ({{u.username}})</button></form></nav>{% endif %}</header>
<main>{% for m in get_flashed_messages() %}<p class="flash" role="status">{{ m }}</p>{% endfor %}{% block c %}{% endblock %}</main>
{% if u %}<script>
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js');
async function rappels(){try{const r=await fetch('/api/rappels');if(!r.ok)return;const l=await r.json(),seen=JSON.parse(localStorage.getItem('rappels')||'[]');
for(const x of l){if(seen.includes(x.key))continue;seen.push(x.key);localStorage.setItem('rappels',JSON.stringify(seen.slice(-50)));
if('Notification' in window&&Notification.permission==='granted')new Notification('Réussite+',{body:x.title+' à '+x.at});else alert(x.title+' à '+x.at)}}catch(e){}}
if('Notification' in window&&Notification.permission==='default')document.addEventListener('click',()=>Notification.requestPermission(),{once:true});
rappels();setInterval(rappels,30000);</script>{% endif %}</body></html>""",
"err.html": T('<h1>{{ msg }}</h1><a href="/">Retour à l\'accueil</a>'),
"login.html": LOGIN("Connexion", "", "Se connecter") .replace("</form>", '</form><p>Pas de compte ? <a href="/inscription">Créer un compte</a></p>'),
"register.html": LOGIN("Créer un compte", '<label><input type="checkbox" name="bac" style="width:auto"> Je prépare le baccalauréat</label>', "Créer mon compte").replace("</form>", '</form><p><a href="/connexion">J\'ai déjà un compte</a></p>'),
"dash.html": T("""<h1>Tableau de bord</h1><p class="card"><em>{{ motiv }}</em></p>
<div class="stats"><div class="card"><div class="big">{{ gen if gen is not none else '–' }}</div>Moyenne générale /20</div><div class="card"><div class="big">{{ cur.minutes }} min</div>Travail cette semaine</div><div class="card"><div class="big">{{ cur.exos }}</div>Exercices cette semaine</div></div>
<h2>Prochains cours et rappels</h2><div class="card">{% for t,s in nxt %}<p>{{ DAYS[s.day] }} {{ s.start }}–{{ s.end }} · {{ s.type }} {{ s.subject }}{% if s.reminder %} <span class="muted">(rappel {{ s.reminder }} min avant)</span>{% endif %}</p>{% else %}<p>Aucun créneau. <a href="/emploi">Crée ton emploi du temps</a>.</p>{% endfor %}</div>
<h2>À travailler en priorité</h2><div class="card">{% for w in weak %}<p>{{ w.s }} · {{ w.t }} : {{ (w.a*100)|round|int }} % de réussite</p>{% else %}<p>Fais quelques <a href="/exercices">exercices</a> pour repérer tes difficultés.</p>{% endfor %}</div>"""),
"schedule.html": T("""<h1>Emploi du temps</h1><form class="card" method="post">""" + CSRF + """{% if edit %}<input type="hidden" name="id" value="{{ edit.id }}">{% endif %}
<div class="row"><div><label>Jour</label><select name="day">{% for d in DAYS %}<option value="{{ loop.index0 }}" {{ 'selected' if edit and edit.day==loop.index0 }}>{{ d }}</option>{% endfor %}</select></div>
<div><label>Début</label><input type="time" name="start" required value="{{ edit.start if edit }}"></div><div><label>Fin</label><input type="time" name="end" required value="{{ edit.end if edit }}"></div>
<div><label>Type</label><select name="type">{% for t in TYPES %}<option {{ 'selected' if edit and edit.type==t }}>{{ t }}</option>{% endfor %}</select></div></div>
<div class="row"><div><label>Matière</label><input name="subject" maxlength="60" value="{{ edit.subject if edit }}"></div><div><label>Rappel (minutes avant, 0 = aucun)</label><input type="number" name="reminder" min="0" max="1440" value="{{ edit.reminder if edit else 10 }}"></div></div>
<label>Description</label><input name="descr" maxlength="200" value="{{ edit.descr if edit }}"><button class="b">{{ 'Modifier' if edit else 'Ajouter' }}</button>{% if edit %} <a href="/emploi">Annuler</a>{% endif %}</form>
{% for d in DAYS %}{% set day=loop.index0 %}{% set l=slots|selectattr('day','equalto',day)|list %}{% if l %}<h2>{{ d }}</h2><div class="card"><table>{% for s in l %}<tr><td>{{ s.start }}–{{ s.end }}</td><td>{{ s.type }} {{ s.subject }}<div class="muted">{{ s.descr }}</div></td><td><a href="/emploi?edit={{ s.id }}">Modifier</a></td><td><form method="post" action="/emploi/{{ s.id }}/supprimer">""" + CSRF + """<button class="b red s">Supprimer</button></form></td></tr>{% endfor %}</table></div>{% endif %}{% endfor %}"""),
"grades.html": T("""<h1>Notes et moyennes</h1><div class="card"><div class="big">{{ gen if gen is not none else '–' }}</div>Moyenne générale (avec coefficients des matières)</div>
<form class="card" method="post">""" + CSRF + """<div class="row"><div><label>Matière</label><input name="subject" required list="m"><datalist id="m">{% for s in SUBJECTS %}<option>{{ s }}</option>{% endfor %}</datalist></div><div><label>Devoir</label><input name="label" placeholder="Devoir 1"></div>
<div><label>Note /20</label><input name="value" required inputmode="decimal"></div><div><label>Poids du devoir</label><input name="weight" value="1" inputmode="decimal"></div><div><label>Coef. matière</label><input name="coef" value="1" inputmode="decimal"></div></div><button class="b">Ajouter la note</button></form>
<h2>Moyennes par matière</h2><div class="card"><table><tr><th>Matière</th><th>Moyenne</th><th>Coef.</th><th>Évolution</th></tr>{% for s in subj %}<tr><td>{{ s.name }}</td><td>{{ s.avg }}</td><td>{{ s.coef|round(2) }}</td><td class="{{ 'up' if s.trend and s.trend>0 else 'dn' if s.trend and s.trend<0 }}">{{ '%+.2f'|format(s.trend) if s.trend is not none else '–' }}</td></tr>{% else %}<tr><td>Aucune note.</td></tr>{% endfor %}</table></div>
<h2>Historique</h2><div class="card"><table>{% for r in rows %}<tr><td>{{ r.subject }} {{ r.label }}</td><td>{{ r.value }}/20 (poids {{ r.weight }})</td><td><form method="post" action="/notes/{{ r.id }}/supprimer">""" + CSRF + """<button class="b red s">Supprimer</button></form></td></tr>{% endfor %}</table></div>"""),
"exercises.html": T("""<h1>Exercices</h1><p>{% for s in SUBJECTS %}<a class="b s" href="/exercices?subject={{ s }}">{{ s }}</a> {% endfor %}</p>
{% if s %}<div class="card">{% if ex %}{% if focus %}<p class="muted">Exercice adapté : tu dois progresser en « {{ focus }} ».</p>{% endif %}<p><b>{{ ex.topic }}</b> — {{ ex.question }}</p><form method="post" action="/exercices/{{ ex.id }}">""" + CSRF + """<input name="answer" required autocomplete="off"><button class="b">Valider</button></form>{% else %}<p>Aucun exercice dans cette matière.</p>{% endif %}</div>{% endif %}
<h2>Réussite par thème</h2><div class="card"><table>{% for w in weak|sort(attribute='s') %}<tr><td>{{ w.s }} · {{ w.t }}</td><td>{{ (w.a*100)|round|int }} % ({{ w.n }})</td></tr>{% else %}<tr><td>Pas encore de résultats.</td></tr>{% endfor %}</table></div>"""),
"review.html": T("""<h1>Bilan hebdomadaire</h1><p class="card"><em>{{ motiv }}</em></p><h2>Minutes travaillées par semaine</h2><div class="card">""" + BAR + """</div>
<div class="stats"><div class="card"><div class="big">{{ cur.sessions }}</div>Séances</div><div class="card"><div class="big">{{ cur.exos }}</div>Exercices ({{ cur.good }} réussis)</div><div class="card"><div class="big">{{ cur.homework }}</div>Devoirs terminés</div></div>
{% if u.bac %}<h2>Préparation au bac</h2><div class="card"><p>Objectif : {{ u.goal }} min/semaine — fait : {{ cur.minutes }} min</p><div class="prog"><i style="width:{{ [cur.minutes*100//u.goal,100]|min }}%"></i></div>
<form method="post">""" + CSRF + """<label>Nouvel objectif (minutes/semaine)</label><input type="number" name="goal" min="10" max="3000" value="{{ u.goal }}"><button class="b">Enregistrer l'objectif</button></form></div>{% endif %}
<h2>Enregistrer une séance</h2><form class="card" method="post">""" + CSRF + """<div class="row"><div><label>Matière</label><input name="subject" maxlength="60"></div><div><label>Type</label><select name="kind">{% for t in TYPES %}<option>{{ t }}</option>{% endfor %}</select></div><div><label>Minutes</label><input type="number" name="minutes" min="1" max="720" required></div></div><button class="b">Enregistrer</button></form>"""),
"chat.html": T("""<h1>Discussion</h1><p class="card">{% if open %}Ouverte jusqu'à 00h00.{% else %}Fermée. Ouverture le samedi de 14h00 à 00h00.{% endif %}</p>
{% if open %}<form class="card" method="post">""" + CSRF + """<textarea name="content" maxlength="500" rows="3" required></textarea><button class="b">Publier</button></form>{% endif %}
<div class="card">{% for m in msgs %}<div class="msg"><b>{{ m.username }}</b> <span class="muted">{{ m.created }}</span><div>{{ m.content }}</div><form method="post" action="/discussion/{{ m.id }}/signaler">""" + CSRF + """<button class="b s red">Signaler</button></form></div>{% else %}<p>Aucun message.</p>{% endfor %}</div>"""),
"admin.html": T("""<h1>Administration</h1><div class="stats">{% for k,v in st.items() %}<div class="card"><div class="big">{{ v }}</div>{{ k }}</div>{% endfor %}<div class="card"><div class="big">{{ day }}</div>alertes (24 h)</div></div>
<h2>Modération</h2><div class="card">{% for m in mod %}<div class="msg"><b>{{ m.username }}</b> [{{ m.status }}] {{ m.reason }}<div>{{ m.content }}</div>{% for a,l,c in [('approved','Approuver','g'),('deleted','Supprimer','red')] %}<form method="post" action="/admin/message/{{ m.id }}/{{ a }}" style="display:inline">""" + CSRF + """<button class="b s {{ c }}">{{ l }}</button></form> {% endfor %}</div>{% else %}<p>Rien à modérer.</p>{% endfor %}</div>
<h2>Comptes</h2><div class="card"><table>{% for x in users %}<tr><td>{{ x.username }}</td><td>{{ x.role }}</td><td>{{ 'actif' if x.active else 'suspendu' }}</td><td><form method="post" action="/admin/user/{{ x.id }}/basculer">""" + CSRF + """<button class="b s">{{ 'Suspendre' if x.active else 'Réactiver' }}</button></form></td></tr>{% endfor %}</table></div>
<h2>Exercices</h2><form class="card" method="post" action="/admin/exercice">""" + CSRF + """<div class="row"><div><label>Matière</label><input name="subject" list="m" required><datalist id="m">{% for s in SUBJECTS %}<option>{{ s }}</option>{% endfor %}</datalist></div><div><label>Thème</label><input name="topic" required></div></div><label>Question</label><input name="question" required><label>Réponse</label><input name="answer" required><button class="b">Ajouter</button></form>
<div class="card"><table>{% for e in exs %}<tr><td>{{ e.subject }} · {{ e.topic }}</td><td>{{ e.question }}</td><td><form method="post" action="/admin/exercice/{{ e.id }}/supprimer">""" + CSRF + """<button class="b red s">Supprimer</button></form></td></tr>{% endfor %}</table></div>
<h2>Journal de sécurité</h2><div class="card"><table>{% for e in ev %}<tr><td>{{ e.created }}</td><td>{{ e.kind }}</td><td>{{ e.detail }}</td><td>{{ e.ip }}</td></tr>{% endfor %}</table></div>"""),
}
app.jinja_loader = DictLoader(TEMPLATES)

# ---------- commandes ----------
def create_admin(name, pw):
    init_db(); c = sqlite3.connect(DB)
    c.execute("INSERT INTO users(username,pw,role,created) VALUES(?,?,'admin',?) ON CONFLICT(username) DO UPDATE SET pw=excluded.pw,role='admin',active=1", (name, generate_password_hash(pw), ts()))
    c.commit(); c.close(); print("Administrateur prêt :", name)

def backup():
    os.makedirs("backups", exist_ok=True); dst = f"backups/reussite-{now():%Y%m%d-%H%M%S}.db"
    s = sqlite3.connect(DB); d = sqlite3.connect(dst); s.backup(d); d.close(); s.close(); print("Sauvegarde :", dst)

init_db()
if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "createadmin": create_admin(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 2 and sys.argv[1] == "backup": backup()
    else: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
