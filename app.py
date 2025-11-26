from flask import Flask, render_template, redirect, url_for, request
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)
from models import db, User, Result   # ← wichtig

app = Flask(__name__)

# ---------------------------------------------------------
# ⚙️ Konfiguration
# ---------------------------------------------------------
app.config['SECRET_KEY'] = 'ändere-das-zu-etwas-geheimem'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# ✔️ WICHTIG für Flask 3.x: DB direkt beim App-Start erstellen
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
# 🌐 Deine bestehenden Seiten (unverändert, keine Auth-Pflicht)
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
    return render_template(
        "datenverarbeitung.html",
        title="Datenverarbeitung"
    )

@app.route("/programmieren")
@login_required
def programmieren():
    return render_template(
        "programmieren.html",
        title="Programmieren"
    )


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

        # Nutzername schon vergeben?
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
# 🔥 Punkte speichern + Ergebnisse
# ---------------------------------------------------------

@app.route("/quiz/<quiz_name>/finish", methods=["POST"])
@login_required
def finish_quiz(quiz_name):
    points = int(request.form.get("points", 0))

    result = Result(
        quiz_name=quiz_name,
        points=points,
        user_id=current_user.id
    )
    db.session.add(result)

    current_user.total_points += points

    db.session.commit()

    return redirect(url_for("my_results"))


@app.route("/me/results")
@login_required
def my_results():
    results = Result.query \
        .filter_by(user_id=current_user.id) \
        .order_by(Result.created_at.desc()) \
        .all()

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