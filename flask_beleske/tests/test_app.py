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
    # Svaka test dobija svoju praznu SQLite bazu, da testovi ne bi
    # slucajno obrisali ili izmenili prave beleske korisnika.
    privremena_baza = tmp_path / "test.db"
    monkeypatch.setattr(app_modul.podaci, "DB_FILE", str(privremena_baza))
    app_modul.podaci.inicijalizuj()
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


def test_toggle_ajax_vraca_json(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Zavrsi zadatak"})
    odgovor = klijent.post("/toggle/1", headers={"X-Requested-With": "XMLHttpRequest"})
    assert odgovor.status_code == 200
    assert odgovor.get_json() == {"uradjeno": True}


def test_obrisi_ajax_vraca_obrisanu_belesku_i_vrati_je_nazad(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Za brisanje", "kategorija": "posao"})

    odgovor = klijent.post("/obrisi/1", headers={"X-Requested-With": "XMLHttpRequest"})
    obrisana = odgovor.get_json()
    assert obrisana["naslov"] == "Za brisanje"

    odgovor = klijent.get("/")
    assert b"Za brisanje" not in odgovor.data

    odgovor = klijent.post(
        "/vrati",
        json=obrisana,
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert odgovor.status_code == 200

    odgovor = klijent.get("/")
    assert b"Za brisanje" in odgovor.data


def test_asistent_bez_api_kljuca_vraca_prijateljsku_gresku(klijent, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    registruj(klijent)

    odgovor = klijent.post(
        "/api/asistent",
        json={"pitanje": "sta imam da radim danas"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert odgovor.status_code == 503
    assert "ANTHROPIC_API_KEY" in odgovor.get_json()["greska"]


def test_rok_se_cuva_i_prikazuje_kao_hitno_kad_prodje(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Sa rokom", "rok": "2020-01-01T10:00"})

    odgovor = klijent.get("/api/beleske")
    assert odgovor.get_json()[0]["rok"] == "2020-01-01T10:00"

    odgovor = klijent.get("/")
    assert b"hitno" in odgovor.data

    klijent.post("/izmeni/1", data={"naslov": "Sa rokom", "rok": "2099-01-01T10:00"})
    odgovor = klijent.get("/")
    assert b"hitno" not in odgovor.data


def test_opis_se_prikazuje_kao_markdown(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Beleska", "opis": "**vazno** i *hitno*"})

    odgovor = klijent.get("/beleska/1")
    assert b"<strong>vazno</strong>" in odgovor.data
    assert b"<em>hitno</em>" in odgovor.data


def test_opis_sanitizuje_skript_tagove(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Beleska", "opis": "<script>alert(1)</script>tekst"})

    odgovor = klijent.get("/beleska/1")
    assert b"<script>" not in odgovor.data
    assert b"tekst" in odgovor.data


def test_deljenje_pravi_javni_link_i_moze_se_ugasiti(klijent):
    registruj(klijent, "vlasnik", "sifra123")
    klijent.post("/dodaj", data={"naslov": "Tajna beleska", "opis": "sadrzaj"})

    # Bez deljenja, javna stranica ne postoji.
    odgovor = klijent.post("/beleska/1/deljenje", follow_redirects=True)
    assert b"Prestani sa deljenjem" in odgovor.data

    odgovor = klijent.get("/beleska/1")
    import re
    token = re.search(rb"/deljeno/([\w-]+)", odgovor.data)
    assert token is not None

    klijent.get("/logout")
    javna = klijent.get(f"/deljeno/{token.group(1).decode()}")
    assert javna.status_code == 200
    assert b"Tajna beleska" in javna.data
    assert b"vlasnik" in javna.data

    # Nepostojeci token vraca gresku i odvodi na login.
    odgovor = klijent.get("/deljeno/nepostojeci-token", follow_redirects=True)
    assert b"ne postoji" in odgovor.data


def test_board_grupise_po_kategoriji(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Sa kategorijom", "kategorija": "posao"})
    klijent.post("/dodaj", data={"naslov": "Bez kategorije"})

    odgovor = klijent.get("/board")
    assert odgovor.status_code == 200
    assert b"posao" in odgovor.data
    assert b"Bez kategorije" in odgovor.data
    assert b"Sa kategorijom" in odgovor.data


def test_board_prazna_kolona_ostaje_i_bez_beleski(klijent):
    registruj(klijent)

    odgovor = klijent.post(
        "/board/kategorija",
        json={"naziv": "Praznik"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert odgovor.status_code == 200

    odgovor = klijent.get("/board")
    assert b"Praznik" in odgovor.data
    assert b"Bez kategorije" in odgovor.data

    # Prazan naziv se odbija.
    odgovor = klijent.post(
        "/board/kategorija",
        json={"naziv": "   "},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert odgovor.status_code == 400


def test_premesti_menja_kategoriju(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Beleska", "kategorija": "posao"})

    odgovor = klijent.post(
        "/premesti/1",
        json={"kategorija": "licno"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert odgovor.status_code == 200
    assert odgovor.get_json() == {"kategorija": "licno"}

    odgovor = klijent.get("/api/beleske")
    assert odgovor.get_json()[0]["kategorija"] == "licno"


def test_statistika_prazna(klijent):
    registruj(klijent)
    odgovor = klijent.get("/statistika")
    assert odgovor.status_code == 200
    assert b"Nema jos beleski" in odgovor.data


def test_statistika_sa_beleskama(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Prva", "kategorija": "posao"})
    klijent.post("/dodaj", data={"naslov": "Druga", "kategorija": "posao"})
    klijent.post("/toggle/1")

    odgovor = klijent.get("/statistika")
    assert odgovor.status_code == 200
    assert b"50%" in odgovor.data
    assert b"posao" in odgovor.data


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
