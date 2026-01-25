import os
import random
from functools import wraps

from flask import Flask, render_template, redirect, url_for, request, session, abort
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from sqlalchemy import func, and_

from models import db, User, Result

app = Flask(__name__)

# ---------------------------------------------------------
# ⚙️ Konfiguration (stabiler DB-Pfad)
# ---------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

app.config["SECRET_KEY"] = "ändere-das-zu-etwas-geheimem"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(INSTANCE_DIR, "app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# ---------------------------------------------------------
# 🔐 Login-System
# ---------------------------------------------------------
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------
# 🧑‍🏫 Rollen-Schutz
# ---------------------------------------------------------
def teacher_required(func_):
    @wraps(func_)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if getattr(current_user, "role", "student") != "teacher":
            abort(403)
        return func_(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------
# ⭐ Hilfsfunktionen: Result speichern + Bestwerte
# ---------------------------------------------------------
def add_result(quiz_name: str, points: int):
    """Speichert einen Result-Eintrag mit Zeitstempel (created_at)."""
    if not current_user.is_authenticated:
        return
    if points is None:
        points = 0
    points = int(points)
    if points < 0:
        points = 0

    r = Result(quiz_name=quiz_name, points=points, user_id=current_user.id)
    db.session.add(r)
    db.session.commit()


def recompute_best_total_points(user_id: int):
    """
    Setzt user.total_points auf die Summe der Bestwerte je Bereich:
    DIA_RUN + DV_RUN + PRG_RUN
    => kein endloses Addieren.
    """
    user = User.query.get(user_id)
    if not user:
        return

    dia_best = db.session.query(func.max(Result.points)).filter_by(user_id=user_id, quiz_name="DIA_RUN").scalar() or 0
    dv_best = db.session.query(func.max(Result.points)).filter_by(user_id=user_id, quiz_name="DV_RUN").scalar() or 0
    prg_best = db.session.query(func.max(Result.points)).filter_by(user_id=user_id, quiz_name="PRG_RUN").scalar() or 0

    user.total_points = int(dia_best) + int(dv_best) + int(prg_best)
    db.session.commit()


# ---------------------------------------------------------
# 🧩 DIA: Fortschritt & Scoring (Session-basiert)
# ---------------------------------------------------------
DIA_TASK_VIEWS = ["dia_a1", "dia_a2", "dia_a3", "dia_a4", "dia_a5"]


def get_dia_done():
    done = session.get("dia_done", [])
    done = [v for v in done if v in DIA_TASK_VIEWS]
    session["dia_done"] = done
    return done


def get_dia_scored():
    scored = session.get("dia_scored", [])
    scored = [v for v in scored if v in DIA_TASK_VIEWS]
    session["dia_scored"] = scored
    return scored


def get_dia_progress_for_view(current_view: str):
    done = get_dia_done()
    count = len(done)
    if current_view in DIA_TASK_VIEWS and current_view not in done:
        count += 1
    return count, len(DIA_TASK_VIEWS)


def add_dia_run_points(points: int):
    """Addiert Punkte in den aktuellen DIA-Durchlauf (Run)."""
    session["dia_run_points"] = int(session.get("dia_run_points", 0)) + int(points or 0)


# ---------------------------------------------------------
# 🗄️ DB initialisieren + Lehrer anlegen
# ---------------------------------------------------------
with app.app_context():
    db.create_all()

    # Standard-Lehrer anlegen (falls noch nicht vorhanden)
    teacher = User.query.filter_by(username="lehrer").first()
    if not teacher:
        teacher = User(username="lehrer", role="teacher")
        teacher.set_password("lehrer123")
        db.session.add(teacher)
        db.session.commit()


# ---------------------------------------------------------
# 🌐 Seiten
# ---------------------------------------------------------
@app.route("/")
@login_required
def home():
    return render_template("index.html", title="InformatikFit")


@app.route("/digitaler-informationsaustausch")
@login_required
def digitaler_informationsaustausch():
    return render_template("digitaler_informationsaustausch.html", title="Digitaler Informationsaustausch")


@app.route("/datenverarbeitung")
@login_required
def datenverarbeitung():
    return render_template("datenverarbeitung.html", title="Datenverarbeitung")


@app.route("/programmieren")
@login_required
def programmieren():
    return render_template("programmieren.html", title="Programmieren")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


# ---------------------------------------------------------
# 🧑‍🏫 Teacher: Dashboard + Detail
# ---------------------------------------------------------

@app.route("/teacher")
@login_required
@teacher_required
def teacher_dashboard():
    # nur Schüler (keine Lehrer)
    students = (
        User.query
        .filter(User.role != "teacher")
        .order_by(User.username.asc())
        .all()
    )
    student_ids = [u.id for u in students]

    if not student_ids:
        return render_template("teacher_dashboard.html", rows=[])

    # ---------
    # Basisstats: Gesamtversuche + letzte Aktivität (ALLE Result-Einträge)
    # ---------
    base_stats = (
        db.session.query(
            Result.user_id.label("user_id"),
            func.count(Result.id).label("attempts_total"),
            func.max(Result.created_at).label("last_activity"),
        )
        .filter(Result.user_id.in_(student_ids))
        .group_by(Result.user_id)
        .all()
    )
    base_map = {s.user_id: s for s in base_stats}

    # ---------
    # Helper: best + attempts pro Bereich (nur RUNs)
    # ---------
    def best_map_for(quiz_name: str):
        rows = (
            db.session.query(Result.user_id, func.max(Result.points))
            .filter(Result.user_id.in_(student_ids), Result.quiz_name == quiz_name)
            .group_by(Result.user_id)
            .all()
        )
        return {uid: int(points or 0) for (uid, points) in rows}

    def attempts_map_for(quiz_name: str):
        rows = (
            db.session.query(Result.user_id, func.count(Result.id))
            .filter(Result.user_id.in_(student_ids), Result.quiz_name == quiz_name)
            .group_by(Result.user_id)
            .all()
        )
        return {uid: int(cnt or 0) for (uid, cnt) in rows}

    dia_best_map = best_map_for("DIA_RUN")
    dv_best_map  = best_map_for("DV_RUN")
    prg_best_map = best_map_for("PRG_RUN")

    dia_attempts_map = attempts_map_for("DIA_RUN")
    dv_attempts_map  = attempts_map_for("DV_RUN")
    prg_attempts_map = attempts_map_for("PRG_RUN")

    # ---------
    # rows fürs Template
    # ---------
    rows = []
    for u in students:
        st = base_map.get(u.id)

        dia_best = dia_best_map.get(u.id, 0)
        dv_best  = dv_best_map.get(u.id, 0)
        prg_best = prg_best_map.get(u.id, 0)

        best_sum = dia_best + dv_best + prg_best

        rows.append({
            "user": u,

            "dia_best": dia_best,
            "dv_best": dv_best,
            "prg_best": prg_best,
            "best_sum": best_sum,

            "dia_attempts": dia_attempts_map.get(u.id, 0),
            "dv_attempts": dv_attempts_map.get(u.id, 0),
            "prg_attempts": prg_attempts_map.get(u.id, 0),

            "attempts_total": int(st.attempts_total) if st else 0,
            "last_activity": st.last_activity if st else None,
        })

    # Sortierung: erst best_sum absteigend, dann letzte Aktivität (neueste zuerst)
    rows.sort(
        key=lambda r: (
            r["best_sum"],
            r["last_activity"] is not None,  # True > False
            r["last_activity"] or 0,
        ),
        reverse=True,
    )

    return render_template("teacher_dashboard.html", rows=rows)


@app.route("/teacher/student/<int:user_id>")
@login_required
@teacher_required
def teacher_student_detail(user_id):
    student = User.query.get_or_404(user_id)

    # optional: Lehrer nicht als "Schülerdetails" anzeigen
    if getattr(student, "role", "student") == "teacher":
        abort(404)

    results = (
        Result.query
        .filter_by(user_id=user_id)
        .order_by(Result.created_at.desc())
        .all()
    )

    def best_for(quiz_name: str) -> int:
        return int(
            db.session.query(func.max(Result.points))
            .filter_by(user_id=user_id, quiz_name=quiz_name)
            .scalar() or 0
        )

    def attempts_for(quiz_name: str) -> int:
        return int(
            db.session.query(func.count(Result.id))
            .filter_by(user_id=user_id, quiz_name=quiz_name)
            .scalar() or 0
        )

    dia_best = best_for("DIA_RUN")
    dv_best  = best_for("DV_RUN")
    prg_best = best_for("PRG_RUN")

    dia_attempts = attempts_for("DIA_RUN")
    dv_attempts  = attempts_for("DV_RUN")
    prg_attempts = attempts_for("PRG_RUN")

    return render_template(
        "teacher_student_detail.html",
        student=student,
        results=results,
        dia_best=dia_best,
        dv_best=dv_best,
        prg_best=prg_best,
        dia_attempts=dia_attempts,
        dv_attempts=dv_attempts,
        prg_attempts=prg_attempts,
    )



# ---------------------------------------------------------
# 🧩 DIA: Next / Summary / Restart
# ---------------------------------------------------------
@app.route("/dia/next")
@login_required
def dia_next():
    current = request.args.get("current")
    done = get_dia_done()

    if current in DIA_TASK_VIEWS and current not in done:
        done.append(current)
        session["dia_done"] = done

    remaining = [v for v in DIA_TASK_VIEWS if v not in done]
    if not remaining:
        return redirect(url_for("dia_summary"))

    return redirect(url_for(random.choice(remaining)))


@app.route("/dia/summary")
@login_required
def dia_summary():
    """
    Speichert EINEN Durchlauf als DIA_RUN (mit created_at),
    zeigt: Run-Punkte, Bestwert DIA, DIA-Versuche.
    """
    run_points = int(session.get("dia_run_points", 0))
    already_saved = bool(session.get("dia_run_saved", False))

    if not already_saved:
        add_result("DIA_RUN", run_points)
        session["dia_run_saved"] = True
        recompute_best_total_points(current_user.id)

    dia_best = db.session.query(func.max(Result.points)).filter_by(user_id=current_user.id, quiz_name="DIA_RUN").scalar() or 0
    dia_attempts = db.session.query(func.count(Result.id)).filter_by(user_id=current_user.id, quiz_name="DIA_RUN").scalar() or 0

    total_tasks = len(DIA_TASK_VIEWS)
    return render_template(
        "dia_summary.html",
        dia_points=run_points,
        total_tasks=total_tasks,
        dia_best=int(dia_best),
        dia_attempts=int(dia_attempts),
    )


@app.route("/dia/restart")
@login_required
def dia_restart():
    session["dia_done"] = []
    session["dia_scored"] = []
    session["dia_run_points"] = 0
    session["dia_run_saved"] = False
    return redirect(url_for("dia_next"))


# ---------------------------------------------------------
# ✅ DIA A1
# ---------------------------------------------------------
@app.route("/dia/a1", methods=["GET", "POST"])
@login_required
def dia_a1():
    beschreibungen = [
        {"id": "b1", "text": "… stellt die Verbindung vom internen Netzwerk zum Internet her."},
        {"id": "b2", "text": "… bezeichnet ein internetfähiges Endgerät."},
        {"id": "b3", "text": "… ist ein zentraler Speicher für ein lokales Netzwerk."},
        {"id": "b4", "text": "… ist ein Rechner, der in einem Netzwerk bestimmte Aufgaben übernimmt."},
    ]

    optionen = ["Router", "Client", "NAS", "Server"]

    korrekt = {"b1": "Router", "b2": "Client", "b3": "NAS", "b4": "Server"}

    erklaerung = {
        "b1": "Ein Router verbindet das interne Netzwerk mit dem Internet (Routing zwischen Netzen).",
        "b2": "Ein Client ist ein internetfähiges Endgerät, das Dienste nutzt (z. B. PC, Laptop).",
        "b3": "Ein NAS ist ein zentraler Netzwerkspeicher, auf den mehrere Geräte zugreifen können.",
        "b4": "Ein Server stellt im Netzwerk Dienste bereit (z. B. Dateien, Webseiten, Druckdienste).",
    }

    feedback = None
    punkte = 0
    geloest = False
    auswahl = {}

    if request.method == "POST":
        geloest = True
        for b in korrekt:
            auswahl[b] = request.form.get(b)
            if auswahl[b] == korrekt[b]:
                punkte += 1

        feedback = "Super! Alles richtig 🎉" if punkte == len(korrekt) else f"Du hast {punkte} von {len(korrekt)} richtig."

        scored = get_dia_scored()
        if "dia_a1" not in scored:
            add_result("DIA_A1", punkte)       # Detailverlauf
            add_dia_run_points(punkte)         # Run-Summe
            scored.append("dia_a1")
            session["dia_scored"] = scored

    dia_progress, dia_total = get_dia_progress_for_view("dia_a1")
    return render_template(
        "dia_a1.html",
        beschreibungen=beschreibungen,
        optionen=optionen,
        korrekt=korrekt,
        erklaerung=erklaerung,
        feedback=feedback,
        auswahl=auswahl,
        geloest=geloest,
        dia_progress=dia_progress,
        dia_total=dia_total,
    )


# ---------------------------------------------------------
# ✅ DIA A2
# ---------------------------------------------------------
@app.route("/dia/a2", methods=["GET", "POST"])
@login_required
def dia_a2():
    fragen = [
        {"id": "q1", "text": "Welches Gerät verteilt Datenpakete innerhalb eines lokalen Netzwerks (z. B. im Schulgebäude)?", "optionen": ["Router", "Switch", "Beamer"]},
        {"id": "q2", "text": "Welches Gerät stellt typischerweise eine WLAN-Verbindung für Smartphones und Laptops bereit?", "optionen": ["Access Point", "Drucker", "NAS"]},
        {"id": "q3", "text": "Welches Gerät ist hauptsächlich dafür da, Dokumente aus dem Netzwerk auf Papier auszugeben?", "optionen": ["Beamer", "Drucker", "Server"]},
        {"id": "q4", "text": "Welches Gerät wird meistens genutzt, um Dienste wie Webseiten oder Datenbanken im Netzwerk bereitzustellen?", "optionen": ["Client", "Server", "Smartphone"]},
    ]

    korrekt = {"q1": "Switch", "q2": "Access Point", "q3": "Drucker", "q4": "Server"}

    erklaerung = {
        "q1": "Ein Switch verteilt Daten innerhalb eines LAN und verbindet Geräte miteinander.",
        "q2": "Ein Access Point stellt WLAN bereit, damit Geräte drahtlos ins Netzwerk kommen.",
        "q3": "Ein Drucker gibt Dokumente aus dem Netzwerk auf Papier aus.",
        "q4": "Ein Server stellt Dienste im Netzwerk bereit (Web, Datenbanken, Dateien).",
    }

    feedback = None
    punkte = 0
    geloest = False
    auswahl = {}

    if request.method == "POST":
        geloest = True
        for f in fragen:
            fid = f["id"]
            auswahl[fid] = request.form.get(fid)
            if auswahl[fid] == korrekt[fid]:
                punkte += 1

        feedback = "Super! Alles richtig in DIA A2 🎉" if punkte == len(fragen) else f"Du hast {punkte} von {len(fragen)} richtig."

        scored = get_dia_scored()
        if "dia_a2" not in scored:
            add_result("DIA_A2", punkte)
            add_dia_run_points(punkte)
            scored.append("dia_a2")
            session["dia_scored"] = scored

    dia_progress, dia_total = get_dia_progress_for_view("dia_a2")
    return render_template(
        "dia_a2.html",
        fragen=fragen,
        korrekt=korrekt,
        erklaerung=erklaerung,
        auswahl=auswahl,
        feedback=feedback,
        geloest=geloest,
        dia_progress=dia_progress,
        dia_total=dia_total,
    )


# ---------------------------------------------------------
# ✅ DIA A3
# ---------------------------------------------------------
@app.route("/dia/a3", methods=["GET", "POST"])
@login_required
def dia_a3():
    aussagen = [
        {"id": "s1", "text": "Ein Router verbindet unterschiedliche Netzwerke miteinander (z. B. Heimnetz und Internet)."},
        {"id": "s2", "text": "Ein Switch stellt in der Regel die Verbindung eines Netzwerks ins Internet her."},
        {"id": "s3", "text": "Ein Access Point ermöglicht drahtlose Verbindungen für Geräte wie Smartphones und Laptops."},
        {"id": "s4", "text": "Ein NAS wird im Netzwerk hauptsächlich als zentraler Speicher verwendet."},
    ]

    optionen = ["Richtig", "Falsch"]

    korrekt = {"s1": "Richtig", "s2": "Falsch", "s3": "Richtig", "s4": "Richtig"}

    erklaerung = {
        "s1": "Ein Router verbindet unterschiedliche Netzwerke (z. B. Heimnetz ↔ Internet).",
        "s2": "Ein Switch verbindet Geräte im LAN; die Internetverbindung macht typischerweise der Router.",
        "s3": "Ein Access Point stellt WLAN bereit, damit Geräte drahtlos ins Netzwerk kommen.",
        "s4": "Ein NAS ist ein zentraler Speicher im Netzwerk (Network Attached Storage).",
    }

    feedback = None
    punkte = 0
    geloest = False
    auswahl = {}

    if request.method == "POST":
        geloest = True
        for a in aussagen:
            aid = a["id"]
            auswahl[aid] = request.form.get(aid)
            if auswahl[aid] == korrekt[aid]:
                punkte += 1

        feedback = "Stark! Alle Aussagen in DIA A3 richtig eingeschätzt 🎉" if punkte == len(aussagen) else f"Du hast {punkte} von {len(aussagen)} richtig."

        scored = get_dia_scored()
        if "dia_a3" not in scored:
            add_result("DIA_A3", punkte)
            add_dia_run_points(punkte)
            scored.append("dia_a3")
            session["dia_scored"] = scored

    dia_progress, dia_total = get_dia_progress_for_view("dia_a3")
    return render_template(
        "dia_a3.html",
        aussagen=aussagen,
        optionen=optionen,
        korrekt=korrekt,
        erklaerung=erklaerung,
        auswahl=auswahl,
        feedback=feedback,
        geloest=geloest,
        dia_progress=dia_progress,
        dia_total=dia_total,
    )


# ---------------------------------------------------------
# ✅ DIA A4
# ---------------------------------------------------------
@app.route("/dia/a4", methods=["GET", "POST"])
@login_required
def dia_a4():
    netzwerke = [
        {"id": "n1", "name": "Netzwerk 1", "image": "dia_a4_net1.png"},
        {"id": "n2", "name": "Netzwerk 2", "image": "dia_a4_net2.png"},
        {"id": "n3", "name": "Netzwerk 3", "image": "dia_a4_net3.png"},
    ]

    optionen = [
        "Dieses Netzwerk kann so funktionieren (alle IP-Adressen sind eindeutig und im selben Netz).",
        "Eine IP-Adresse gehört zu einem anderen Netz (z.B. 192.186 statt 192.168).",
        "Eine IP-Adresse kommt doppelt vor.",
        "Der Router hat eine falsche IP-Adresse.",
    ]

    korrekt = {
        "n1": "Eine IP-Adresse gehört zu einem anderen Netz (z.B. 192.186 statt 192.168).",
        "n2": "Eine IP-Adresse kommt doppelt vor.",
        "n3": "Dieses Netzwerk kann so funktionieren (alle IP-Adressen sind eindeutig und im selben Netz).",
    }

    erklaerung = {
        "n1": "Hier ist eine IP im falschen Netz (192.186 statt 192.168). Geräte können so nicht korrekt kommunizieren.",
        "n2": "Hier gibt es eine doppelte IP-Adresse. IPs müssen im selben Netz eindeutig sein.",
        "n3": "Alle Geräte haben eindeutige IPs im selben Netz (z. B. 192.168.0.x). So kann das Heimnetz funktionieren.",
    }

    feedback = None
    punkte = 0
    geloest = False
    auswahl = {}

    if request.method == "POST":
        geloest = True
        for net in netzwerke:
            nid = net["id"]
            auswahl[nid] = request.form.get(nid)
            if auswahl[nid] == korrekt[nid]:
                punkte += 1

        feedback = "Sehr gut! Du hast alle Heimnetzwerke richtig beurteilt 🎉" if punkte == len(netzwerke) else f"Du hast {punkte} von {len(netzwerke)} Netzwerken richtig erklärt."

        scored = get_dia_scored()
        if "dia_a4" not in scored:
            add_result("DIA_A4", punkte)
            add_dia_run_points(punkte)
            scored.append("dia_a4")
            session["dia_scored"] = scored

    dia_progress, dia_total = get_dia_progress_for_view("dia_a4")
    return render_template(
        "dia_a4.html",
        netzwerke=netzwerke,
        optionen=optionen,
        korrekt=korrekt,
        erklaerung=erklaerung,
        auswahl=auswahl,
        feedback=feedback,
        geloest=geloest,
        dia_progress=dia_progress,
        dia_total=dia_total,
    )


# ---------------------------------------------------------
# ✅ DIA A5
# ---------------------------------------------------------
@app.route("/dia/a5", methods=["GET", "POST"])
@login_required
def dia_a5():
    aufgaben = [
        {"id": "u1", "fehler_url": "https://www.bycsde", "korrekt": "https://www.bycs.de"},
        {"id": "u2", "fehler_url": "https:/ www.bycs.de", "korrekt": "https://www.bycs.de"},
        {"id": "u3", "fehler_url": "https://ww.bycs.de", "korrekt": "https://www.bycs.de"},
    ]

    optionen = [
        "Es fehlt ein / in https://",
        "Die Domainendung .de fehlt oder ist falsch",
        "www ist falsch geschrieben",
        "Leerzeichen an der falschen Stelle",
    ]

    korrekt_fehler = {
        "u1": "Die Domainendung .de fehlt oder ist falsch",
        "u2": "Es fehlt ein / in https://",
        "u3": "www ist falsch geschrieben",
    }

    erklaerung = {
        "u1": "Bei Domains ist die Endung wichtig. Korrekt ist bycs.de (mit Punkt und Endung).",
        "u2": "Bei https:// müssen zwei Slashes stehen und es dürfen keine Leerzeichen in der URL sein.",
        "u3": "Die Subdomain 'www' ist falsch geschrieben (ww statt www).",
    }

    feedback = None
    geloest = False
    auswahl_fehler = {}
    auswahl_korrekt = {}
    punkte = 0

    if request.method == "POST":
        geloest = True
        for a in aufgaben:
            aid = a["id"]
            auswahl_fehler[aid] = request.form.get(aid + "_fehler")
            auswahl_korrekt[aid] = request.form.get(aid + "_korrekt")

            richtig_fehler = auswahl_fehler[aid] == korrekt_fehler[aid]
            richtig_url = (auswahl_korrekt[aid] or "").strip() == a["korrekt"]

            if richtig_fehler and richtig_url:
                punkte += 1

        feedback = "Super! Alle URLs wurden richtig korrigiert 🎉" if punkte == len(aufgaben) else f"Du hast {punkte} von {len(aufgaben)} URLs vollständig richtig."

        scored = get_dia_scored()
        if "dia_a5" not in scored:
            add_result("DIA_A5", punkte)
            add_dia_run_points(punkte)
            scored.append("dia_a5")
            session["dia_scored"] = scored

    dia_progress, dia_total = get_dia_progress_for_view("dia_a5")
    return render_template(
        "dia_a5.html",
        aufgaben=aufgaben,
        optionen=optionen,
        korrekt_fehler=korrekt_fehler,
        erklaerung=erklaerung,
        geloest=geloest,
        auswahl_fehler=auswahl_fehler,
        auswahl_korrekt=auswahl_korrekt,
        feedback=feedback,
        dia_progress=dia_progress,
        dia_total=dia_total,
    )


# ---------------------------------------------------------
# 🔥 Auth
# ---------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if User.query.filter_by(username=username).first():
            return "Benutzername existiert bereits."

        user = User(username=username, role="student")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard"))

        return "Ungültiger Benutzername oder Passwort."

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------
# 🔥 Ergebnisse
# ---------------------------------------------------------
@app.route("/me/results")
@login_required
def my_results():
    results = Result.query.filter_by(user_id=current_user.id).order_by(Result.created_at.desc()).all()
    return render_template("my_results.html", results=results)


# ---------------------------------------------------------
# 🏆 Rangliste: Bestwerte + Datum + Attempts pro Bereich
# ---------------------------------------------------------
@app.route("/leaderboard")
@login_required
def leaderboard():
    # Bestwerte je User
    dia_best = (
        db.session.query(Result.user_id.label("user_id"), func.max(Result.points).label("best"))
        .filter(Result.quiz_name == "DIA_RUN")
        .group_by(Result.user_id)
        .subquery()
    )
    dv_best = (
        db.session.query(Result.user_id.label("user_id"), func.max(Result.points).label("best"))
        .filter(Result.quiz_name == "DV_RUN")
        .group_by(Result.user_id)
        .subquery()
    )
    prg_best = (
        db.session.query(Result.user_id.label("user_id"), func.max(Result.points).label("best"))
        .filter(Result.quiz_name == "PRG_RUN")
        .group_by(Result.user_id)
        .subquery()
    )

    # Datum zu Bestwert (max created_at, wenn points==best)
    dia_best_at = (
        db.session.query(Result.user_id.label("user_id"), func.max(Result.created_at).label("best_at"))
        .join(dia_best, and_(
            Result.user_id == dia_best.c.user_id,
            Result.points == dia_best.c.best,
            Result.quiz_name == "DIA_RUN"
        ))
        .group_by(Result.user_id)
        .subquery()
    )
    dv_best_at = (
        db.session.query(Result.user_id.label("user_id"), func.max(Result.created_at).label("best_at"))
        .join(dv_best, and_(
            Result.user_id == dv_best.c.user_id,
            Result.points == dv_best.c.best,
            Result.quiz_name == "DV_RUN"
        ))
        .group_by(Result.user_id)
        .subquery()
    )
    prg_best_at = (
        db.session.query(Result.user_id.label("user_id"), func.max(Result.created_at).label("best_at"))
        .join(prg_best, and_(
            Result.user_id == prg_best.c.user_id,
            Result.points == prg_best.c.best,
            Result.quiz_name == "PRG_RUN"
        ))
        .group_by(Result.user_id)
        .subquery()
    )

    # Attempts je Bereich (Anzahl Runs)
    dia_attempts = (
        db.session.query(Result.user_id.label("user_id"), func.count(Result.id).label("attempts"))
        .filter(Result.quiz_name == "DIA_RUN")
        .group_by(Result.user_id)
        .subquery()
    )
    dv_attempts = (
        db.session.query(Result.user_id.label("user_id"), func.count(Result.id).label("attempts"))
        .filter(Result.quiz_name == "DV_RUN")
        .group_by(Result.user_id)
        .subquery()
    )
    prg_attempts = (
        db.session.query(Result.user_id.label("user_id"), func.count(Result.id).label("attempts"))
        .filter(Result.quiz_name == "PRG_RUN")
        .group_by(Result.user_id)
        .subquery()
    )

    rows = (
        db.session.query(
            User,
            func.coalesce(dia_best.c.best, 0).label("dia_best"),
            dia_best_at.c.best_at.label("dia_best_at"),
            func.coalesce(dia_attempts.c.attempts, 0).label("dia_attempts"),

            func.coalesce(dv_best.c.best, 0).label("dv_best"),
            dv_best_at.c.best_at.label("dv_best_at"),
            func.coalesce(dv_attempts.c.attempts, 0).label("dv_attempts"),

            func.coalesce(prg_best.c.best, 0).label("prg_best"),
            prg_best_at.c.best_at.label("prg_best_at"),
            func.coalesce(prg_attempts.c.attempts, 0).label("prg_attempts"),
        )
        .filter(User.role != "teacher")
        .outerjoin(dia_best, User.id == dia_best.c.user_id)
        .outerjoin(dia_best_at, User.id == dia_best_at.c.user_id)
        .outerjoin(dia_attempts, User.id == dia_attempts.c.user_id)

        .outerjoin(dv_best, User.id == dv_best.c.user_id)
        .outerjoin(dv_best_at, User.id == dv_best_at.c.user_id)
        .outerjoin(dv_attempts, User.id == dv_attempts.c.user_id)

        .outerjoin(prg_best, User.id == prg_best.c.user_id)
        .outerjoin(prg_best_at, User.id == prg_best_at.c.user_id)
        .outerjoin(prg_attempts, User.id == prg_attempts.c.user_id)
        .all()
    )

    rows = sorted(rows, key=lambda r: (r.dia_best + r.dv_best + r.prg_best), reverse=True)
    return render_template("leaderboard.html", rows=rows)


# ---------------------------------------------------------
# 🚀 Start
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
