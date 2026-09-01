# app.py - Flask sajt: "Beleske" (sada sa nalozima, kategorijama, datumima,
# checkbox "uradjeno", pretragom, JSON API-jem i validacijom).
#
# Pascal poredjenje: u Pascalu bi ovo bio program koji stalno slusa
# konekcije (kao "while true do" petlja koja ceka input), a Flask
# to radi umesto nas - mi samo pisemo "sta se desi kad neko otvori X putanju".

import json
import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# secret_key je potreban da Flask moze bezbedno da potpise sesijski kolacic
# (ko je ulogovan) i flash poruke. Pascal: nema ekvivalenta - ovo je web-specificno.
app.secret_key = "dev-tajni-kljuc-samo-za-vezbu"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Prijavi se da bi video svoje beleske."

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")


# ---------- Citanje/pisanje podataka ----------

def ucitaj_podatke():
    """Cita ceo JSON: {"sledeci_id": int, "korisnici": {ime: {lozinka_hash, beleske}}}."""
    if not os.path.exists(DATA_FILE):
        return {"sledeci_id": 1, "korisnici": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def sacuvaj_podatke(podaci):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(podaci, f, ensure_ascii=False, indent=2)


def korisnikove_beleske(podaci, korisnicko_ime):
    return podaci["korisnici"][korisnicko_ime]["beleske"]


def nadji_belesku(beleske, id_):
    for b in beleske:
        if b["id"] == id_:
            return b
    return None


# ---------- Flask-Login: ko je "User" u nasem sistemu ----------
# Pascal nema pojam sesije/naloga - najblizi opis je "svaki korisnik ima
# svoj fajl sa podacima", a Flask-Login pamti KOJI je korisnik trenutno ulogovan.

class Korisnik(UserMixin):
    def __init__(self, korisnicko_ime):
        self.id = korisnicko_ime


@login_manager.user_loader
def ucitaj_korisnika(korisnicko_ime):
    podaci = ucitaj_podatke()
    if korisnicko_ime in podaci["korisnici"]:
        return Korisnik(korisnicko_ime)
    return None


# ---------- Registracija / prijava / odjava ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        korisnicko_ime = request.form.get("korisnicko_ime", "").strip()
        lozinka = request.form.get("lozinka", "")
        potvrda = request.form.get("potvrda", "")

        podaci = ucitaj_podatke()

        if not korisnicko_ime or not lozinka:
            flash("Korisnicko ime i lozinka su obavezni.", "greska")
        elif korisnicko_ime in podaci["korisnici"]:
            flash("To korisnicko ime je vec zauzeto.", "greska")
        elif lozinka != potvrda:
            flash("Lozinke se ne poklapaju.", "greska")
        elif len(lozinka) < 4:
            flash("Lozinka mora imati bar 4 karaktera.", "greska")
        else:
            podaci["korisnici"][korisnicko_ime] = {
                "lozinka_hash": generate_password_hash(lozinka),
                "beleske": [],
            }
            sacuvaj_podatke(podaci)
            login_user(Korisnik(korisnicko_ime))
            return redirect(url_for("pocetna"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        korisnicko_ime = request.form.get("korisnicko_ime", "").strip()
        lozinka = request.form.get("lozinka", "")

        podaci = ucitaj_podatke()
        korisnik = podaci["korisnici"].get(korisnicko_ime)

        if korisnik and check_password_hash(korisnik["lozinka_hash"], lozinka):
            login_user(Korisnik(korisnicko_ime))
            return redirect(url_for("pocetna"))

        flash("Pogresno korisnicko ime ili lozinka.", "greska")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------- Beleske ----------

@app.route("/")
@login_required
def pocetna():
    podaci = ucitaj_podatke()
    beleske = korisnikove_beleske(podaci, current_user.id)
    # Najnovije prvo - ISO datum se moze sortirati kao obican string.
    beleske_sortirane = sorted(beleske, key=lambda b: b["datum"], reverse=True)
    return render_template("index.html", beleske=beleske_sortirane)


@app.route("/dodaj", methods=["POST"])
@login_required
def dodaj():
    naslov = request.form.get("naslov", "").strip()
    opis = request.form.get("opis", "").strip()
    kategorija = request.form.get("kategorija", "").strip()

    if not naslov:
        flash("Naslov ne moze biti prazan.", "greska")
        return redirect(url_for("pocetna"))

    podaci = ucitaj_podatke()
    nova_beleska = {
        "id": podaci["sledeci_id"],
        "naslov": naslov,
        "opis": opis,
        "kategorija": kategorija,
        "datum": datetime.now().isoformat(timespec="seconds"),
        "uradjeno": False,
    }
    podaci["sledeci_id"] += 1
    korisnikove_beleske(podaci, current_user.id).append(nova_beleska)
    sacuvaj_podatke(podaci)
    return redirect(url_for("pocetna"))


@app.route("/beleska/<int:id>")
@login_required
def detalji(id):
    podaci = ucitaj_podatke()
    beleske = korisnikove_beleske(podaci, current_user.id)
    beleska = nadji_belesku(beleske, id)

    if beleska is None:
        return redirect(url_for("pocetna"))

    return render_template("detalji.html", beleska=beleska)


@app.route("/izmeni/<int:id>", methods=["GET", "POST"])
@login_required
def izmeni(id):
    podaci = ucitaj_podatke()
    beleske = korisnikove_beleske(podaci, current_user.id)
    beleska = nadji_belesku(beleske, id)

    if beleska is None:
        return redirect(url_for("pocetna"))

    if request.method == "POST":
        novi_naslov = request.form.get("naslov", "").strip()
        if not novi_naslov:
            flash("Naslov ne moze biti prazan.", "greska")
            return redirect(url_for("izmeni", id=id))

        beleska["naslov"] = novi_naslov
        beleska["opis"] = request.form.get("opis", "").strip()
        beleska["kategorija"] = request.form.get("kategorija", "").strip()
        sacuvaj_podatke(podaci)
        return redirect(url_for("detalji", id=id))

    return render_template("izmeni.html", beleska=beleska)


@app.route("/toggle/<int:id>", methods=["POST"])
@login_required
def toggle(id):
    podaci = ucitaj_podatke()
    beleske = korisnikove_beleske(podaci, current_user.id)
    beleska = nadji_belesku(beleske, id)

    if beleska is not None:
        beleska["uradjeno"] = not beleska["uradjeno"]
        sacuvaj_podatke(podaci)

    return redirect(url_for("pocetna"))


@app.route("/obrisi/<int:id>", methods=["POST"])
@login_required
def obrisi(id):
    podaci = ucitaj_podatke()
    beleske = korisnikove_beleske(podaci, current_user.id)
    beleska = nadji_belesku(beleske, id)

    if beleska is not None:
        beleske.remove(beleska)
        sacuvaj_podatke(podaci)

    return redirect(url_for("pocetna"))


@app.route("/api/beleske")
@login_required
def api_beleske():
    podaci = ucitaj_podatke()
    return jsonify(korisnikove_beleske(podaci, current_user.id))


if __name__ == "__main__":
    app.run(debug=True)
