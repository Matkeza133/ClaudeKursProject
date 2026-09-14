# app.py - Flask sajt: "Beleske" (sada sa nalozima, kategorijama, datumima,
# checkbox "uradjeno", pretragom, JSON API-jem i validacijom).
#
# Pascal poredjenje: u Pascalu bi ovo bio program koji stalno slusa
# konekcije (kao "while true do" petlja koja ceka input), a Flask
# to radi umesto nas - mi samo pisemo "sta se desi kad neko otvori X putanju".

import math
import os
from datetime import datetime, timedelta

import anthropic
import bleach
import markdown
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
# U produkciji MORA doci iz SECRET_KEY env varijable - ko god zna dev
# vrednost moze da falsifikuje tudje sesijske kolacice.
app.secret_key = os.environ.get("SECRET_KEY", "dev-tajni-kljuc-samo-za-vezbu")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Prijavi se da bi video svoje beleske."

# ---------- Skladiste podataka ----------
# Podrazumevano SQLite (podaci_sqlite.py). Za povratak na stari JSON fajl
# (podaci_json.py) pre pokretanja: PODACI_BACKEND=json. Oba modula imaju
# isti "ugovor" (iste funkcije/potpise), pa ostatak app.py ne zna niti mu
# je bitno koji je aktivan - samo poziva podaci.sta_god_mu_treba().
if os.environ.get("PODACI_BACKEND") == "json":
    import podaci_json as podaci
else:
    import podaci_sqlite as podaci

podaci.inicijalizuj()
if hasattr(podaci, "migriraj_iz_json_ako_treba"):
    podaci.migriraj_iz_json_ako_treba()


DOZVOLJENI_MARKDOWN_TAGOVI = [
    "p", "br", "strong", "em", "ul", "ol", "li", "a", "code", "pre",
    "blockquote", "h1", "h2", "h3", "hr",
]
DOZVOLJENI_MARKDOWN_ATRIBUTI = {"a": ["href", "title", "rel"]}


def opis_u_html(opis):
    # Opis beleske se pise kao Markdown (bold/liste/linkovi...), a bleach
    # ovde ciscenjem HTML-a spreci XSS pre nego sto se prikaze - bitno
    # narocito za /deljeno/<token> stranicu koju vidi bilo ko na internetu.
    if not opis:
        return ""
    html = markdown.markdown(opis, extensions=["fenced_code", "nl2br"])
    return bleach.clean(html, tags=DOZVOLJENI_MARKDOWN_TAGOVI, attributes=DOZVOLJENI_MARKDOWN_ATRIBUTI, strip=True)


def zeli_json():
    # app.js salje ovaj header uz fetch() pozive, da server zna da vrati
    # JSON (za AJAX azuriranje bez reload-a) umesto klasicnog redirect-a.
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


# ---------- Flask-Login: ko je "User" u nasem sistemu ----------
# Pascal nema pojam sesije/naloga - najblizi opis je "svaki korisnik ima
# svoj fajl sa podacima", a Flask-Login pamti KOJI je korisnik trenutno ulogovan.

class Korisnik(UserMixin):
    def __init__(self, korisnicko_ime):
        self.id = korisnicko_ime


@login_manager.user_loader
def ucitaj_korisnika(korisnicko_ime):
    if podaci.korisnik_postoji(korisnicko_ime):
        return Korisnik(korisnicko_ime)
    return None


# ---------- Registracija / prijava / odjava ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        korisnicko_ime = request.form.get("korisnicko_ime", "").strip()
        lozinka = request.form.get("lozinka", "")
        potvrda = request.form.get("potvrda", "")

        if not korisnicko_ime or not lozinka:
            flash("Korisnicko ime i lozinka su obavezni.", "greska")
        elif podaci.korisnik_postoji(korisnicko_ime):
            flash("To korisnicko ime je vec zauzeto.", "greska")
        elif lozinka != potvrda:
            flash("Lozinke se ne poklapaju.", "greska")
        elif len(lozinka) < 4:
            flash("Lozinka mora imati bar 4 karaktera.", "greska")
        else:
            podaci.napravi_korisnika(korisnicko_ime, generate_password_hash(lozinka))
            login_user(Korisnik(korisnicko_ime))
            return redirect(url_for("pocetna"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        korisnicko_ime = request.form.get("korisnicko_ime", "").strip()
        lozinka = request.form.get("lozinka", "")

        lozinka_hash = podaci.lozinka_hash_za(korisnicko_ime)

        if lozinka_hash and check_password_hash(lozinka_hash, lozinka):
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
    beleske = podaci.sve_beleske(current_user.id)  # vec sortirano, najnovije prvo

    broj_ukupno = len(beleske)
    broj_uradjeno = sum(1 for b in beleske if b["uradjeno"])
    procenat_uradjeno = round(broj_uradjeno / broj_ukupno * 100) if broj_ukupno else 0
    kategorije = sorted({b["kategorija"] for b in beleske if b["kategorija"]})
    sada = datetime.now().isoformat(timespec="minutes")

    return render_template(
        "index.html",
        beleske=beleske,
        broj_ukupno=broj_ukupno,
        broj_uradjeno=broj_uradjeno,
        procenat_uradjeno=procenat_uradjeno,
        kategorije=kategorije,
        sada=sada,
    )


@app.route("/dodaj", methods=["POST"])
@login_required
def dodaj():
    naslov = request.form.get("naslov", "").strip()
    opis = request.form.get("opis", "").strip()
    kategorija = request.form.get("kategorija", "").strip()
    rok = request.form.get("rok", "").strip() or None

    if not naslov:
        flash("Naslov ne moze biti prazan.", "greska")
        return redirect(url_for("pocetna"))

    podaci.dodaj_belesku(current_user.id, naslov, opis, kategorija, rok)
    return redirect(url_for("pocetna"))


@app.route("/beleska/<int:id>")
@login_required
def detalji(id):
    beleska = podaci.nadji_belesku(current_user.id, id)

    if beleska is None:
        return redirect(url_for("pocetna"))

    sada = datetime.now().isoformat(timespec="minutes")
    return render_template("detalji.html", beleska=beleska, opis_html=opis_u_html(beleska["opis"]), sada=sada)


@app.route("/beleska/<int:id>/deljenje", methods=["POST"])
@login_required
def deljenje(id):
    # Toggle: prvi klik napravi javni link (nasumican token), drugi ga ugasi.
    podaci.postavi_deljenje(current_user.id, id)
    return redirect(url_for("detalji", id=id))


@app.route("/deljeno/<token>")
def deljena_beleska(token):
    najdeno = podaci.nadji_po_deljenju(token)
    if najdeno is not None:
        korisnicko_ime, beleska = najdeno
        return render_template(
            "deljeno.html",
            beleska=beleska,
            opis_html=opis_u_html(beleska["opis"]),
            autor=korisnicko_ime,
        )

    flash("Ova podeljena beleska ne postoji ili je deljenje ugaseno.", "greska")
    return redirect(url_for("login"))


@app.route("/izmeni/<int:id>", methods=["GET", "POST"])
@login_required
def izmeni(id):
    beleska = podaci.nadji_belesku(current_user.id, id)

    if beleska is None:
        return redirect(url_for("pocetna"))

    if request.method == "POST":
        novi_naslov = request.form.get("naslov", "").strip()
        if not novi_naslov:
            flash("Naslov ne moze biti prazan.", "greska")
            return redirect(url_for("izmeni", id=id))

        novi_opis = request.form.get("opis", "").strip()
        nova_kategorija = request.form.get("kategorija", "").strip()
        novi_rok = request.form.get("rok", "").strip() or None
        podaci.izmeni_belesku(current_user.id, id, novi_naslov, novi_opis, nova_kategorija, novi_rok)
        return redirect(url_for("detalji", id=id))

    return render_template("izmeni.html", beleska=beleska)


@app.route("/toggle/<int:id>", methods=["POST"])
@login_required
def toggle(id):
    novi_status = podaci.toggle_belesku(current_user.id, id)

    if zeli_json():
        return jsonify({"uradjeno": novi_status})
    return redirect(url_for("pocetna"))


@app.route("/obrisi/<int:id>", methods=["POST"])
@login_required
def obrisi(id):
    obrisana = podaci.obrisi_belesku(current_user.id, id)

    if zeli_json():
        return jsonify(obrisana if obrisana else {})
    return redirect(url_for("pocetna"))


@app.route("/vrati", methods=["POST"])
@login_required
def vrati():
    # Koristi se samo za dugme "Ponisti" u toast poruci posle brisanja -
    # klijent nam vrati tacno onu belesku koju je /obrisi upravo izbrisao.
    telo = request.get_json(silent=True) or {}
    potrebna_polja = {"id", "naslov", "opis", "kategorija", "datum", "uradjeno"}
    if not potrebna_polja.issubset(telo):
        return jsonify({"greska": "nepotpuni podaci"}), 400

    podaci.vrati_belesku(current_user.id, telo)
    return jsonify({"ok": True})


@app.route("/board")
@login_required
def board():
    beleske = podaci.sve_beleske(current_user.id)

    # Kolone = kategorije koje je korisnik ikad napravio/koristio (registar),
    # unija sa onim sto trenutno koriste beleske - tako prazna kolona koju
    # napravis na boardu ostaje vidljiva i pre nego sto joj dodas belesku.
    registrovane = set(podaci.sve_kategorije(current_user.id))
    iz_beleski = {b["kategorija"] for b in beleske if b["kategorija"]}
    kategorije = sorted(registrovane | iz_beleski)
    kolone = kategorije + ["Bez kategorije"]

    grupisano = {k: [] for k in kolone}
    for b in beleske:
        kljuc = b["kategorija"] if b["kategorija"] else "Bez kategorije"
        grupisano[kljuc].append(b)

    return render_template("board.html", kolone=kolone, grupisano=grupisano)


@app.route("/board/kategorija", methods=["POST"])
@login_required
def nova_kategorija_na_boardu():
    telo = request.get_json(silent=True) or {}
    naziv = (telo.get("naziv") or "").strip()
    if not naziv:
        return jsonify({"greska": "Naziv ne moze biti prazan."}), 400

    podaci.napravi_kategoriju(current_user.id, naziv)
    return jsonify({"naziv": naziv})


@app.route("/premesti/<int:id>", methods=["POST"])
@login_required
def premesti(id):
    # Koristi ga board (drag & drop) da promeni kategoriju beleske -
    # kolona u koju je kartica prevucena postaje njena nova kategorija.
    telo = request.get_json(silent=True) or {}
    nova_kategorija = (telo.get("kategorija") or "").strip()

    nova = podaci.premesti_belesku(current_user.id, id, nova_kategorija)
    return jsonify({"kategorija": nova})


@app.route("/statistika")
@login_required
def statistika():
    beleske = podaci.sve_beleske(current_user.id)

    ukupno = len(beleske)
    uradjeno = sum(1 for b in beleske if b["uradjeno"])
    aktivno = ukupno - uradjeno
    procenat = round(uradjeno / ukupno * 100) if ukupno else 0
    # Obim kruga (r=54) za SVG donut - stroke-dasharray trik za "popunjenost".
    obim_kruga = round(2 * math.pi * 54, 2)

    brojac_kategorija = {}
    for b in beleske:
        naziv = b["kategorija"] or "Bez kategorije"
        brojac_kategorija[naziv] = brojac_kategorija.get(naziv, 0) + 1
    najvise_u_kategoriji = max(brojac_kategorija.values(), default=0)
    kategorije = [
        {"naziv": naziv, "broj": broj, "procenat": round(broj / najvise_u_kategoriji * 100) if najvise_u_kategoriji else 0}
        for naziv, broj in sorted(brojac_kategorija.items(), key=lambda t: t[1], reverse=True)
    ]

    danas = datetime.now().date()
    raspon_dana = [danas - timedelta(days=i) for i in range(13, -1, -1)]
    brojac_po_danu = {d.isoformat(): 0 for d in raspon_dana}
    for b in beleske:
        dan = b["datum"][:10]
        if dan in brojac_po_danu:
            brojac_po_danu[dan] += 1
    najvise_u_danu = max(brojac_po_danu.values(), default=0)
    po_danu = [
        {
            "oznaka": d.strftime("%d.%m"),
            "broj": brojac_po_danu[d.isoformat()],
            "procenat": round(brojac_po_danu[d.isoformat()] / najvise_u_danu * 100) if najvise_u_danu else 0,
        }
        for d in raspon_dana
    ]

    return render_template(
        "statistika.html",
        ukupno=ukupno,
        uradjeno=uradjeno,
        aktivno=aktivno,
        procenat=procenat,
        obim_kruga=obim_kruga,
        kategorije=kategorije,
        po_danu=po_danu,
    )


@app.route("/sw.js")
def service_worker():
    # Mora biti servirano sa "/", ne "/static/", da bi service worker
    # dobio scope nad celim sajtom (scope = URL na kome je registrovan).
    odgovor = app.send_static_file("sw.js")
    odgovor.headers["Cache-Control"] = "no-cache"
    return odgovor


@app.route("/api/beleske")
@login_required
def api_beleske():
    return jsonify(podaci.sve_beleske(current_user.id))


# ---------- AI asistent ----------
# Pascal nema ekvivalent - ovo je poziv ka spoljnom Claude API-ju koji
# "vidi" korisnicove beleske (kao kontekst) i odgovara na pitanja o njima.

def izgradi_kontekst_beleski(beleske):
    if not beleske:
        return "(korisnik trenutno nema nijednu belesku)"

    redovi = []
    for b in beleske:
        red = f"- [{'zavrseno' if b['uradjeno'] else 'aktivno'}] {b['naslov']}"
        if b["kategorija"]:
            red += f" (kategorija: {b['kategorija']})"
        if b["opis"]:
            red += f": {b['opis']}"
        redovi.append(red)
    return "\n".join(redovi)


@app.route("/api/asistent", methods=["POST"])
@login_required
def api_asistent():
    telo = request.get_json(silent=True) or {}
    pitanje = (telo.get("pitanje") or "").strip()
    if not pitanje:
        return jsonify({"greska": "Pitanje ne moze biti prazno."}), 400

    beleske = podaci.sve_beleske(current_user.id)

    sistemska_poruka = (
        'Ti si AI asistent unutar aplikacije za licne beleske "Beleske". '
        f"Evo svih trenutnih beleski korisnika:\n\n{izgradi_kontekst_beleski(beleske)}\n\n"
        "Odgovaraj kratko, konkretno i na srpskom jeziku, iskljucivo na osnovu ovih beleski. "
        "Ako pitanje nema veze sa beleskama, ljubazno reci da mozes da pomognes samo oko njih."
    )

    poruke = []
    for stavka in telo.get("istorija", []):
        uloga = stavka.get("uloga")
        tekst = stavka.get("tekst")
        if uloga in ("user", "assistant") and tekst:
            poruke.append({"role": uloga, "content": tekst})
    poruke.append({"role": "user", "content": pitanje})

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return jsonify({"greska": "AI asistent nije podesen (nedostaje ANTHROPIC_API_KEY)."}), 503

    klijent = anthropic.Anthropic()
    try:
        odgovor = klijent.messages.create(
            model="claude-opus-5",
            max_tokens=1024,
            system=sistemska_poruka,
            output_config={"effort": "low"},
            messages=poruke,
        )
    except anthropic.AuthenticationError:
        return jsonify({"greska": "Nevazeci Anthropic API kljuc."}), 503
    except anthropic.RateLimitError:
        return jsonify({"greska": "AI servis je trenutno preopterecen, pokusaj ponovo."}), 503
    except anthropic.APIStatusError as e:
        return jsonify({"greska": f"Greska od AI servisa ({e.status_code})."}), 502
    except anthropic.APIConnectionError:
        return jsonify({"greska": "Nema konekcije ka AI servisu."}), 502

    tekst_odgovora = next((b.text for b in odgovor.content if b.type == "text"), "")
    return jsonify({"odgovor": tekst_odgovora})


if __name__ == "__main__":
    app.run(debug=True)
