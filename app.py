import random
from flask import Flask, render_template, redirect, url_for, request, session
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)
from models import db, User, Result

app = Flask(__name__)

# ---------------------------------------------------------
# ⚙️ Konfiguration
# ---------------------------------------------------------
app.config["SECRET_KEY"] = "ändere-das-zu-etwas-geheimem"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

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
# ⭐ Hilfsfunktionen: Punkte + Fortschritt
# ---------------------------------------------------------
def add_points(quiz_name: str, points: int):
    """Speichert Punkte für den aktuellen Benutzer."""
    if not current_user.is_authenticated:
        return
    if points <= 0:
        return

    result = Result(
        quiz_name=quiz_name,
        points=points,
        user_id=current_user.id
    )
    db.session.add(result)

    current_user.total_points += points
    db.session.commit()


# Alle vorhandenen Aufgaben im Bereich DIA
DIA_TASK_VIEWS = ["dia_a1", "dia_a2", "dia_a3", "dia_a4", "dia_a5"]


def get_dia_done():
    """Session-Liste: welche DIA-Aufgaben wurden in dieser Runde schon bearbeitet?"""
    done = session.get("dia_done", [])
    done = [v for v in done if v in DIA_TASK_VIEWS]
    session["dia_done"] = done
    return done


def get_dia_scored():
    """Session-Liste: welche DIA-Aufgaben haben in dieser Runde schon Punkte bekommen?"""
    scored = session.get("dia_scored", [])
    scored = [v for v in scored if v in DIA_TASK_VIEWS]
    session["dia_scored"] = scored
    return scored


def get_dia_progress_for_view(current_view: str):
    """Gibt (Fortschritt_inkl_aktueller, Gesamtanzahl) zurück."""
    done = get_dia_done()
    count = len(done)
    if current_view in DIA_TASK_VIEWS and current_view not in done:
        count += 1
    return count, len(DIA_TASK_VIEWS)


# ---------------------------------------------------------
# 🌐 Seiten (nur für eingeloggte Nutzer)
# ---------------------------------------------------------
@app.route("/")
@login_required
def home():
    return render_template("index.html", title="InformatikFit")


@app.route("/digitaler-informationsaustausch")
@login_required
def digitaler_informationsaustausch():
    return render_template(
        "digitaler_informationsaustausch.html",
        title="Digitaler Informationsaustausch"
    )


@app.route("/datenverarbeitung")
@login_required
def datenverarbeitung():
    return render_template("datenverarbeitung.html", title="Datenverarbeitung")


@app.route("/programmieren")
@login_required
def programmieren():
    return render_template("programmieren.html", title="Programmieren")


# ---------------------------------------------------------
# 🧩 Lernaufgaben – Digitaler Informationsaustausch (DIA)
# ---------------------------------------------------------
@app.route("/dia/next")
@login_required
def dia_next():
    """
    Gibt die nächste Aufgabe im Bereich DIA aus.
    Jede Aufgabe kommt pro Runde nur einmal. Danach -> Summary.
    """
    current = request.args.get("current")  # z.B. "dia_a1"
    done = get_dia_done()

    if current in DIA_TASK_VIEWS and current not in done:
        done.append(current)
        session["dia_done"] = done

    remaining = [v for v in DIA_TASK_VIEWS if v not in done]

    if not remaining:
        return redirect(url_for("dia_summary"))

    next_view = random.choice(remaining)
    return redirect(url_for(next_view))


# ---------------------- DIA A1 ---------------------------
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

    korrekt = {
        "b1": "Router",
        "b2": "Client",
        "b3": "NAS",
        "b4": "Server",
    }

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
            add_points("DIA_A1", punkte)
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


# ---------------------- DIA A2 ---------------------------
@app.route("/dia/a2", methods=["GET", "POST"])
@login_required
def dia_a2():
    fragen = [
        {
            "id": "q1",
            "text": "Welches Gerät verteilt Datenpakete innerhalb eines lokalen Netzwerks (z. B. im Schulgebäude)?",
            "optionen": ["Router", "Switch", "Beamer"],
        },
        {
            "id": "q2",
            "text": "Welches Gerät stellt typischerweise eine WLAN-Verbindung für Smartphones und Laptops bereit?",
            "optionen": ["Access Point", "Drucker", "NAS"],
        },
        {
            "id": "q3",
            "text": "Welches Gerät ist hauptsächlich dafür da, Dokumente aus dem Netzwerk auf Papier auszugeben?",
            "optionen": ["Beamer", "Drucker", "Server"],
        },
        {
            "id": "q4",
            "text": "Welches Gerät wird meistens genutzt, um Dienste wie Webseiten oder Datenbanken im Netzwerk bereitzustellen?",
            "optionen": ["Client", "Server", "Smartphone"],
        },
    ]

    korrekt = {
        "q1": "Switch",
        "q2": "Access Point",
        "q3": "Drucker",
        "q4": "Server",
    }

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

        for frage in fragen:
            fid = frage["id"]
            auswahl[fid] = request.form.get(fid)
            if auswahl[fid] == korrekt[fid]:
                punkte += 1

        feedback = "Super! Alles richtig in DIA A2 🎉" if punkte == len(fragen) else f"Du hast {punkte} von {len(fragen)} richtig."

        scored = get_dia_scored()
        if "dia_a2" not in scored:
            add_points("DIA_A2", punkte)
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


# ---------------------- DIA A3 ---------------------------
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

    korrekt = {
        "s1": "Richtig",
        "s2": "Falsch",
        "s3": "Richtig",
        "s4": "Richtig",
    }

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
            add_points("DIA_A3", punkte)
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


# ---------------------- DIA A4 ---------------------------
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
            add_points("DIA_A4", punkte)
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


# ---------------------- DIA A5 ---------------------------
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
            add_points("DIA_A5", punkte)
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


# ---------------------- DIA SUMMARY + RESTART ---------------------------
@app.route("/dia/summary")
@login_required
def dia_summary():
    results = (
        Result.query.filter_by(user_id=current_user.id)
        .filter(Result.quiz_name.like("DIA_%"))
        .all()
    )
    dia_points = sum(r.points for r in results)
    total_tasks = len(DIA_TASK_VIEWS)

    return render_template("dia_summary.html", dia_points=dia_points, total_tasks=total_tasks)


@app.route("/dia/restart")
@login_required
def dia_restart():
    session["dia_done"] = []
    session["dia_scored"] = []
    return redirect(url_for("dia_next"))


# ---------------------------------------------------------
# 🔥 Benutzerverwaltung
# ---------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if User.query.filter_by(username=username).first():
            return "Benutzername existiert bereits."

        user = User(username=username)
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
# 🔥 Ergebnisse & Rangliste
# ---------------------------------------------------------
@app.route("/me/results")
@login_required
def my_results():
    results = (
        Result.query.filter_by(user_id=current_user.id)
        .order_by(Result.created_at.desc())
        .all()
    )
    return render_template("my_results.html", results=results)


@app.route("/leaderboard")
@login_required
def leaderboard():
    users = User.query.order_by(User.total_points.desc()).all()
    return render_template("leaderboard.html", users=users)


# ---------------------------------------------------------
# 🚀 Start der App
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
