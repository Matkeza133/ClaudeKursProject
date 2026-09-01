# test_app.py - osnovni pytest testovi za Beleske aplikaciju.
# Pascal poredjenje: ovo je kao da napises poseban program koji poziva
# tvoje funkcije sa poznatim ulazom i proverava da li je izlaz ocekivan.

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_modul


@pytest.fixture
def klijent(tmp_path, monkeypatch):
    # Svaki test dobija svoj prazan data.json, da testovi ne bi
    # slucajno obrisali ili izmenili prave beleske korisnika.
    privremeni_fajl = tmp_path / "data.json"
    monkeypatch.setattr(app_modul, "DATA_FILE", str(privremeni_fajl))
    app_modul.app.config["TESTING"] = True

    with app_modul.app.test_client() as klijent:
        yield klijent


def registruj(klijent, korisnicko_ime="ana", lozinka="sifra123"):
    return klijent.post(
        "/register",
        data={"korisnicko_ime": korisnicko_ime, "lozinka": lozinka, "potvrda": lozinka},
        follow_redirects=True,
    )


def test_pocetna_bez_prijave_vodi_na_login(klijent):
    odgovor = klijent.get("/", follow_redirects=True)
    assert odgovor.status_code == 200
    assert b"Prijava" in odgovor.data


def test_registracija_prijavljuje_korisnika(klijent):
    odgovor = registruj(klijent)
    assert odgovor.status_code == 200
    assert b"Moje beleske" in odgovor.data


def test_registracija_sa_razlicitim_lozinkama_ne_uspeva(klijent):
    odgovor = klijent.post(
        "/register",
        data={"korisnicko_ime": "pera", "lozinka": "sifra123", "potvrda": "drugacije"},
        follow_redirects=True,
    )
    assert b"ne poklapaju" in odgovor.data


def test_prijava_sa_pogresnom_lozinkom_ne_uspeva(klijent):
    registruj(klijent, "mika", "sifra123")
    klijent.get("/logout")
    odgovor = klijent.post(
        "/login",
        data={"korisnicko_ime": "mika", "lozinka": "pogresna"},
        follow_redirects=True,
    )
    assert b"Pogresno korisnicko ime ili lozinka" in odgovor.data


def test_dodavanje_beleske(klijent):
    registruj(klijent)
    odgovor = klijent.post(
        "/dodaj",
        data={"naslov": "Kupovina", "opis": "Kupiti mleko i hleb", "kategorija": "kuca"},
        follow_redirects=True,
    )
    assert b"Kupovina" in odgovor.data
    assert b"kuca" in odgovor.data
    # Opis se ne prikazuje na pocetnoj, samo naslov.
    assert b"Kupiti mleko" not in odgovor.data


def test_prazan_naslov_se_odbija(klijent):
    registruj(klijent)
    odgovor = klijent.post("/dodaj", data={"naslov": "   ", "opis": "nesto"}, follow_redirects=True)
    assert b"Naslov ne moze biti prazan" in odgovor.data


def test_klik_na_naslov_otvara_detalje(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Kupovina", "opis": "Kupiti mleko i hleb"})
    odgovor = klijent.get("/beleska/1")
    assert b"Kupovina" in odgovor.data
    assert b"Kupiti mleko i hleb" in odgovor.data


def test_izmena_beleske(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Prvobitni naslov", "opis": "stari opis"})
    odgovor = klijent.post(
        "/izmeni/1",
        data={"naslov": "Izmenjeni naslov", "opis": "novi opis"},
        follow_redirects=True,
    )
    assert b"Izmenjeni naslov" in odgovor.data
    assert b"novi opis" in odgovor.data
    assert b"Prvobitni naslov" not in odgovor.data


def test_toggle_uradjeno(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Zavrsi zadatak"})
    odgovor = klijent.post("/toggle/1", follow_redirects=True)
    assert b'checked' in odgovor.data


def test_brisanje_beleske(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Za brisanje"})
    odgovor = klijent.post("/obrisi/1", follow_redirects=True)
    assert b"Za brisanje" not in odgovor.data
    assert b"Nema jos beleski" in odgovor.data


def test_api_beleske_vraca_json(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "API test", "opis": "opis za api"})
    odgovor = klijent.get("/api/beleske")
    podaci = odgovor.get_json()
    assert isinstance(podaci, list)
    assert podaci[0]["naslov"] == "API test"
    assert podaci[0]["opis"] == "opis za api"


def test_korisnik_ne_vidi_tudje_beleske(klijent):
    registruj(klijent, "prvi", "sifra123")
    klijent.post("/dodaj", data={"naslov": "Beleska prvog korisnika"})
    klijent.get("/logout")

    registruj(klijent, "drugi", "sifra123")
    odgovor = klijent.get("/")
    assert b"Beleska prvog korisnika" not in odgovor.data

    # Drugi korisnik ne moze da vidi ni otvori tudju belesku preko direktnog URL-a.
    odgovor = klijent.get("/beleska/1", follow_redirects=True)
    assert b"Beleska prvog korisnika" not in odgovor.data

    odgovor = klijent.post("/izmeni/1", data={"naslov": "Hakovano"}, follow_redirects=True)
    assert b"Hakovano" not in odgovor.data
