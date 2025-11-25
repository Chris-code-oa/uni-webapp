ffrom flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html", title="InformatikFit")

@app.route("/digitaler-informationsaustausch")
def digitaler_informationsaustausch():
    return render_template(
        "digitaler_informationsaustausch.html",
        title="Digitaler Informationsaustausch"
    )

@app.route("/datenverarbeitung")
def datenverarbeitung():
    return render_template(
        "datenverarbeitung.html",
        title="Datenverarbeitung"
    )

@app.route("/programmieren")
def programmieren():
    return render_template(
        "programmieren.html",
        title="Programmieren"
    )

if __name__ == "__main__":
    app.run(debug=True)
