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


def prijavi(klijent, korisnicko_ime, lozinka="sifra123"):
    # Za razliku od registruj() - koristi se da se VRATIS na nalog koji vec
    # postoji (drugi register bi tiho propao jer je ime zauzeto).
    return klijent.post(
        "/login",
        data={"korisnicko_ime": korisnicko_ime, "lozinka": lozinka},
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


def test_tagovi_se_cuvaju_prikazuju_i_deduplikuju(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Sa tagovima", "tagovi": "hitno, posao, hitno"})

    odgovor = klijent.get("/")
    assert b"#hitno" in odgovor.data
    assert b"#posao" in odgovor.data

    odgovor = klijent.get("/api/beleske")
    assert odgovor.get_json()[0]["tagovi"] == ["hitno", "posao"]


def test_izmena_menja_tagove(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Beleska", "tagovi": "stari"})
    klijent.post("/izmeni/1", data={"naslov": "Beleska", "tagovi": "novi"})

    odgovor = klijent.get("/api/beleske")
    assert odgovor.get_json()[0]["tagovi"] == ["novi"]


def test_dodavanje_podzadatka(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Sa podzadacima"})

    odgovor = klijent.post(
        "/beleska/1/podzadaci",
        json={"tekst": "Prvi korak"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert odgovor.status_code == 200
    podzadatak = odgovor.get_json()
    assert podzadatak["tekst"] == "Prvi korak"
    assert podzadatak["uradjeno"] is False

    odgovor = klijent.get("/beleska/1")
    assert b"Prvi korak" in odgovor.data


def test_prazan_podzadatak_se_odbija(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Beleska"})

    odgovor = klijent.post(
        "/beleska/1/podzadaci",
        json={"tekst": "   "},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert odgovor.status_code == 400


def test_toggle_i_brisanje_podzadatka(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Sa podzadacima"})
    odgovor = klijent.post(
        "/beleska/1/podzadaci", json={"tekst": "Korak"}, headers={"X-Requested-With": "XMLHttpRequest"}
    )
    podzadatak_id = odgovor.get_json()["id"]

    odgovor = klijent.post(f"/podzadatak/{podzadatak_id}/toggle", headers={"X-Requested-With": "XMLHttpRequest"})
    assert odgovor.get_json() == {"uradjeno": True}

    odgovor = klijent.post(f"/podzadatak/{podzadatak_id}/obrisi", headers={"X-Requested-With": "XMLHttpRequest"})
    assert odgovor.get_json() == {"obrisano": True}

    odgovor = klijent.get("/beleska/1")
    assert b"Korak" not in odgovor.data


def test_tudji_podzadatak_ne_moze_da_se_menja(klijent):
    registruj(klijent, "prvi", "sifra123")
    klijent.post("/dodaj", data={"naslov": "Beleska prvog"})
    odgovor = klijent.post(
        "/beleska/1/podzadaci", json={"tekst": "Korak"}, headers={"X-Requested-With": "XMLHttpRequest"}
    )
    podzadatak_id = odgovor.get_json()["id"]
    klijent.get("/logout")

    registruj(klijent, "drugi", "sifra123")
    odgovor = klijent.post(f"/podzadatak/{podzadatak_id}/toggle", headers={"X-Requested-With": "XMLHttpRequest"})
    assert odgovor.status_code == 404


def test_brisanje_beleske_cisti_tagove_i_podzadatke_zbog_reuse_id(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Prva", "tagovi": "x"})
    klijent.post("/beleska/1/podzadaci", json={"tekst": "korak"}, headers={"X-Requested-With": "XMLHttpRequest"})
    klijent.post("/obrisi/1")

    # id NIJE AUTOINCREMENT - sledeca beleska moze dobiti isti id (1), pa
    # ne sme da "nasledi" tagove/podzadatke obrisane beleske.
    klijent.post("/dodaj", data={"naslov": "Druga"})
    odgovor = klijent.get("/api/beleske")
    nova = odgovor.get_json()[0]
    assert nova["id"] == 1
    assert nova["tagovi"] == []

    odgovor = klijent.get("/beleska/1")
    assert b"korak" not in odgovor.data


def test_toggle_ponavljajuce_beleske_pravi_sledecu_instancu(klijent):
    registruj(klijent)
    klijent.post(
        "/dodaj",
        data={"naslov": "Zalivanje biljaka", "rok": "2024-01-01T09:00", "ponavljanje": "nedeljno"},
    )

    klijent.post("/toggle/1")  # zavrsava prvu instancu

    odgovor = klijent.get("/api/beleske")
    sve = odgovor.get_json()
    assert len(sve) == 2

    stara = next(b for b in sve if b["id"] == 1)
    assert stara["uradjeno"] is True
    assert stara["rok"] == "2024-01-01T09:00"

    nova = next(b for b in sve if b["id"] != 1)
    assert nova["uradjeno"] is False
    assert nova["rok"] == "2024-01-08T09:00"
    assert nova["ponavljanje"] == "nedeljno"


def test_toggle_obicne_beleske_ne_pravi_novu_instancu(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Jednokratna", "rok": "2024-01-01T09:00"})
    klijent.post("/toggle/1")

    odgovor = klijent.get("/api/beleske")
    assert len(odgovor.get_json()) == 1


def test_mesecno_ponavljanje_pomera_rok_mesec_unapred(klijent):
    registruj(klijent)
    klijent.post(
        "/dodaj",
        data={"naslov": "Racun", "rok": "2024-01-31T10:00", "ponavljanje": "mesecno"},
    )
    klijent.post("/toggle/1")

    odgovor = klijent.get("/api/beleske")
    nova = next(b for b in odgovor.get_json() if b["id"] != 1)
    # Januar ima 31 dan, februar 29 (2024 je prestupna) - dan se "skljoka" na 29.
    assert nova["rok"] == "2024-02-29T10:00"


def test_kalendar_prikazuje_belesku_na_ispravan_dan(klijent):
    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Sastanak", "rok": "2024-03-15T14:00"})

    odgovor = klijent.get("/kalendar?mesec=2024-03")
    assert odgovor.status_code == 200
    assert b"Sastanak" in odgovor.data
    assert b"Mart 2024." in odgovor.data


def test_kalendar_bez_parametra_koristi_trenutni_mesec(klijent):
    registruj(klijent)
    odgovor = klijent.get("/kalendar")
    assert odgovor.status_code == 200


def test_saradnik_moze_da_vidi_i_izmeni_ali_ne_i_obrise(klijent):
    registruj(klijent, "vlasnik", "sifra123")
    klijent.post("/dodaj", data={"naslov": "Zajednicka beleska", "opis": "stari opis"})
    odgovor = klijent.post(
        "/beleska/1/saradnici", data={"korisnicko_ime": "saradnik1"}, follow_redirects=True
    )
    assert b"ne postoji" in odgovor.data  # saradnik1 jos ne postoji kao nalog
    klijent.get("/logout")

    registruj(klijent, "saradnik1", "sifra123")
    klijent.get("/logout")

    prijavi(klijent, "vlasnik", "sifra123")
    klijent.post("/beleska/1/saradnici", data={"korisnicko_ime": "saradnik1"})
    klijent.get("/logout")

    prijavi(klijent, "saradnik1", "sifra123")
    # Vidi belesku i moze da je izmeni.
    odgovor = klijent.get("/beleska/1")
    assert odgovor.status_code == 200
    assert b"Zajednicka beleska" in odgovor.data
    assert b"Deljeno od vlasnik" in odgovor.data

    odgovor = klijent.post(
        "/izmeni/1", data={"naslov": "Izmenio saradnik", "opis": "novi opis"}, follow_redirects=True
    )
    assert b"Izmenio saradnik" in odgovor.data

    # Ne moze da obrise ni da javno deli.
    odgovor = klijent.post("/obrisi/1", follow_redirects=True)
    assert b"Samo vlasnik" in odgovor.data
    odgovor = klijent.post("/beleska/1/deljenje", follow_redirects=True)
    assert b"Samo vlasnik" in odgovor.data

    # Beleska je i dalje tu (nije obrisana).
    odgovor = klijent.get("/beleska/1")
    assert odgovor.status_code == 200


def test_nesaradnik_ne_vidi_tudju_belesku(klijent):
    registruj(klijent, "vlasnik2", "sifra123")
    klijent.post("/dodaj", data={"naslov": "Privatna beleska"})
    klijent.get("/logout")

    registruj(klijent, "nepovezan", "sifra123")
    odgovor = klijent.get("/beleska/1", follow_redirects=True)
    assert b"Privatna beleska" not in odgovor.data

    odgovor = klijent.post("/izmeni/1", data={"naslov": "Hakovano"}, follow_redirects=True)
    assert b"Hakovano" not in odgovor.data


def test_vlasnik_moze_ukloniti_saradnika(klijent):
    registruj(klijent, "vlasnik3", "sifra123")
    klijent.post("/dodaj", data={"naslov": "Beleska"})
    registruj(klijent, "saradnik3", "sifra123")
    klijent.get("/logout")

    prijavi(klijent, "vlasnik3", "sifra123")
    klijent.post("/beleska/1/saradnici", data={"korisnicko_ime": "saradnik3"})
    klijent.post("/beleska/1/saradnici/saradnik3/ukloni")
    klijent.get("/logout")

    prijavi(klijent, "saradnik3", "sifra123")
    odgovor = klijent.get("/beleska/1", follow_redirects=True)
    assert b"Beleska" not in odgovor.data


def test_deljena_beleska_se_pojavljuje_na_pocetnoj_saradnika(klijent):
    registruj(klijent, "vlasnik4", "sifra123")
    klijent.post("/dodaj", data={"naslov": "Timski zadatak"})
    registruj(klijent, "saradnik4", "sifra123")
    klijent.get("/logout")

    prijavi(klijent, "vlasnik4", "sifra123")
    klijent.post("/beleska/1/saradnici", data={"korisnicko_ime": "saradnik4"})
    klijent.get("/logout")

    prijavi(klijent, "saradnik4", "sifra123")
    odgovor = klijent.get("/")
    assert b"Timski zadatak" in odgovor.data
    assert b"Deljeno od vlasnik4" in odgovor.data


def test_istorija_se_puni_posle_izmene_i_vracanje_pravi_novi_snapshot(klijent):
    registruj(klijent, "pisac", "sifra123")
    klijent.post("/dodaj", data={"naslov": "Verzija 1", "opis": "prvi opis"})
    klijent.post("/izmeni/1", data={"naslov": "Verzija 2", "opis": "drugi opis"})
    klijent.post("/izmeni/1", data={"naslov": "Verzija 3", "opis": "treci opis"})

    odgovor = klijent.get("/beleska/1/istorija")
    assert odgovor.status_code == 200
    assert b"Verzija 1" in odgovor.data  # snapshot pre prve izmene
    assert b"Verzija 2" in odgovor.data  # snapshot pre druge izmene

    import re
    svi_id = re.findall(rb'/beleska/1/istorija/(\d+)/vrati', odgovor.data)
    assert len(svi_id) == 2

    odgovor = klijent.post(f"/beleska/1/istorija/{svi_id[-1].decode()}/vrati", follow_redirects=True)
    assert odgovor.status_code == 200

    odgovor = klijent.get("/beleska/1")
    assert b"Verzija 1" in odgovor.data  # vraceno na najstariju verziju

    # Vracanje samo po sebi je upisalo NOVI snapshot - sad ima 3 stavke.
    odgovor = klijent.get("/beleska/1/istorija")
    svi_id_posle = re.findall(rb'/beleska/1/istorija/(\d+)/vrati', odgovor.data)
    assert len(svi_id_posle) == 3


def test_push_javni_kljuc_bez_vapid_vraca_503(klijent, monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    registruj(klijent)

    odgovor = klijent.get("/api/push/javni-kljuc")
    assert odgovor.status_code == 503


def test_push_javni_kljuc_sa_vapid_vraca_kljuc(klijent, monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "test-javni-kljuc")
    registruj(klijent)

    odgovor = klijent.get("/api/push/javni-kljuc")
    assert odgovor.status_code == 200
    assert odgovor.get_json() == {"kljuc": "test-javni-kljuc"}


def test_push_pretplata_nepotpuna_vraca_400(klijent):
    registruj(klijent)
    odgovor = klijent.post(
        "/api/push/pretplata",
        json={"endpoint": "https://push.primer/x"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert odgovor.status_code == 400


def test_push_pretplata_se_cuva_i_moze_se_obrisati(klijent):
    registruj(klijent)
    telo = {
        "endpoint": "https://push.primer/abc123",
        "keys": {"p256dh": "javni-deo", "auth": "tajni-deo"},
    }
    odgovor = klijent.post("/api/push/pretplata", json=telo, headers={"X-Requested-With": "XMLHttpRequest"})
    assert odgovor.status_code == 200

    import app as app_modul
    pretplate = app_modul.podaci.pretplate_za("ana")
    assert len(pretplate) == 1
    assert pretplate[0]["endpoint"] == "https://push.primer/abc123"

    odgovor = klijent.delete(
        "/api/push/pretplata",
        json={"endpoint": "https://push.primer/abc123"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert odgovor.status_code == 200
    assert app_modul.podaci.pretplate_za("ana") == []


def test_posalji_podsetnike_salje_i_ne_salje_dvaput(klijent, monkeypatch):
    import app as app_modul

    monkeypatch.setenv("VAPID_PUBLIC_KEY", "k")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "k")
    monkeypatch.setenv("VAPID_KONTAKT_EMAIL", "a@b.com")

    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Hitno", "rok": "2020-01-01T10:00"})
    klijent.post(
        "/api/push/pretplata",
        json={"endpoint": "https://push.primer/x", "keys": {"p256dh": "a", "auth": "b"}},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    pozivi = []
    monkeypatch.setattr(app_modul, "webpush", lambda **kwargs: pozivi.append(kwargs))

    app_modul.posalji_podsetnike_ako_treba()
    assert len(pozivi) == 1
    assert pozivi[0]["subscription_info"]["endpoint"] == "https://push.primer/x"

    # Beleska je vec oznacena kao "podsetnik poslat" - drugi prolaz ne salje ponovo.
    app_modul.posalji_podsetnike_ako_treba()
    assert len(pozivi) == 1


def test_posalji_podsetnike_brise_mrtvu_pretplatu(klijent, monkeypatch):
    import app as app_modul

    monkeypatch.setenv("VAPID_PUBLIC_KEY", "k")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "k")
    monkeypatch.setenv("VAPID_KONTAKT_EMAIL", "a@b.com")

    registruj(klijent)
    klijent.post("/dodaj", data={"naslov": "Hitno", "rok": "2020-01-01T10:00"})
    klijent.post(
        "/api/push/pretplata",
        json={"endpoint": "https://push.primer/mrtva", "keys": {"p256dh": "a", "auth": "b"}},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    class LazniOdgovor:
        status_code = 410

    def lazni_webpush(**kwargs):
        raise app_modul.WebPushException("gone", response=LazniOdgovor())

    monkeypatch.setattr(app_modul, "webpush", lazni_webpush)
    app_modul.posalji_podsetnike_ako_treba()

    assert app_modul.podaci.pretplate_za("ana") == []


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
