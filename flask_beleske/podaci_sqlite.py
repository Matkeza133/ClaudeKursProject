# podaci_sqlite.py - skladiste podataka, SQLite verzija (PODRAZUMEVANO).
#
# Isti "ugovor" (funkcije sa istim imenima/potpisima) kao podaci_json.py,
# tako da app.py ne zna niti mu je bitno koji je od ova dva modula ucitan -
# samo poziva podaci.sta_god_mu_treba(). Prebacivanje nazad na JSON je
# jedna promena: postavi PODACI_BACKEND=json pre pokretanja.
#
# Pascal poredjenje: umesto da ceo "niz" (fajl) citas/upisujes za svaku
# sitnicu, ovde imas pravu tabelu i trazis/menjas samo red koji ti treba -
# baza sama vodi racuna o zakljucavanju kad dva zahteva stignu istovremeno.

import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), "beleske.db")


@contextmanager
def _konekcija():
    k = sqlite3.connect(DB_FILE)
    k.row_factory = sqlite3.Row
    try:
        yield k
        k.commit()
    finally:
        k.close()


def inicijalizuj():
    with _konekcija() as k:
        k.execute("""
            CREATE TABLE IF NOT EXISTS korisnici (
                korisnicko_ime TEXT PRIMARY KEY,
                lozinka_hash TEXT NOT NULL
            )
        """)
        # Namerno BEZ AUTOINCREMENT - "obican" INTEGER PRIMARY KEY racuna
        # sledeci id kao max(id)+1 u trenutku upisa, sto je bitno za
        # migraciju: stari id-jevi iz data.json se prenesu tacno takvi
        # kakvi jesu, a sledeca NOVA beleska nastavlja iznad njih.
        k.execute("""
            CREATE TABLE IF NOT EXISTS beleske (
                id INTEGER PRIMARY KEY,
                korisnicko_ime TEXT NOT NULL,
                naslov TEXT NOT NULL,
                opis TEXT NOT NULL DEFAULT '',
                kategorija TEXT NOT NULL DEFAULT '',
                datum TEXT NOT NULL,
                uradjeno INTEGER NOT NULL DEFAULT 0,
                rok TEXT,
                deljenje_id TEXT,
                FOREIGN KEY (korisnicko_ime) REFERENCES korisnici (korisnicko_ime)
            )
        """)
        # Registar kategorija - postoji nezavisno od beleski, da bi se na
        # boardu mogla napraviti PRAZNA kolona (kategorija bez ijedne beleske).
        k.execute("""
            CREATE TABLE IF NOT EXISTS kategorije (
                korisnicko_ime TEXT NOT NULL,
                naziv TEXT NOT NULL,
                PRIMARY KEY (korisnicko_ime, naziv),
                FOREIGN KEY (korisnicko_ime) REFERENCES korisnici (korisnicko_ime)
            )
        """)


def migriraj_iz_json_ako_treba():
    # Jednokratna migracija: ako postoji stari data.json a baza je jos
    # prazna, prebaci sve podatke jednom. Ne dira data.json fajl.
    json_putanja = os.path.join(os.path.dirname(__file__), "data.json")
    if not os.path.exists(json_putanja):
        return

    with _konekcija() as k:
        vec_ima_podatke = k.execute("SELECT 1 FROM korisnici LIMIT 1").fetchone() is not None
    if vec_ima_podatke:
        return

    with open(json_putanja, "r", encoding="utf-8") as f:
        stari_podaci = json.load(f)

    with _konekcija() as k:
        for korisnicko_ime, korisnik in stari_podaci.get("korisnici", {}).items():
            k.execute(
                "INSERT OR IGNORE INTO korisnici (korisnicko_ime, lozinka_hash) VALUES (?, ?)",
                (korisnicko_ime, korisnik["lozinka_hash"]),
            )
            for b in korisnik.get("beleske", []):
                k.execute(
                    "INSERT INTO beleske "
                    "(id, korisnicko_ime, naslov, opis, kategorija, datum, uradjeno, rok, deljenje_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        b["id"], korisnicko_ime, b["naslov"], b.get("opis", ""),
                        b.get("kategorija", ""), b["datum"], int(bool(b.get("uradjeno"))),
                        b.get("rok"), b.get("deljenje_id"),
                    ),
                )
    print(f"[migracija] Podaci iz {json_putanja} prebaceni u {DB_FILE}")


def _red_u_recnik(red):
    return {
        "id": red["id"],
        "naslov": red["naslov"],
        "opis": red["opis"],
        "kategorija": red["kategorija"],
        "datum": red["datum"],
        "uradjeno": bool(red["uradjeno"]),
        "rok": red["rok"],
        "deljenje_id": red["deljenje_id"],
    }


def korisnik_postoji(korisnicko_ime):
    with _konekcija() as k:
        red = k.execute(
            "SELECT 1 FROM korisnici WHERE korisnicko_ime = ?", (korisnicko_ime,)
        ).fetchone()
    return red is not None


def lozinka_hash_za(korisnicko_ime):
    with _konekcija() as k:
        red = k.execute(
            "SELECT lozinka_hash FROM korisnici WHERE korisnicko_ime = ?", (korisnicko_ime,)
        ).fetchone()
    return red["lozinka_hash"] if red else None


def napravi_korisnika(korisnicko_ime, lozinka_hash):
    with _konekcija() as k:
        k.execute(
            "INSERT INTO korisnici (korisnicko_ime, lozinka_hash) VALUES (?, ?)",
            (korisnicko_ime, lozinka_hash),
        )


def sve_beleske(korisnicko_ime):
    with _konekcija() as k:
        redovi = k.execute(
            "SELECT * FROM beleske WHERE korisnicko_ime = ? ORDER BY datum DESC",
            (korisnicko_ime,),
        ).fetchall()
    return [_red_u_recnik(r) for r in redovi]


def nadji_belesku(korisnicko_ime, id_):
    with _konekcija() as k:
        red = k.execute(
            "SELECT * FROM beleske WHERE id = ? AND korisnicko_ime = ?",
            (id_, korisnicko_ime),
        ).fetchone()
    return _red_u_recnik(red) if red else None


def _upisi_kategoriju(k, korisnicko_ime, kategorija):
    # Poziva se kad god beleska dobije kategoriju, da se ta kategorija
    # "zapamti" u registru i posle - npr. ako se sve beleske sa njom
    # obrisu, kolona na boardu i dalje ostaje dostupna za buduce beleske.
    if kategorija:
        k.execute(
            "INSERT OR IGNORE INTO kategorije (korisnicko_ime, naziv) VALUES (?, ?)",
            (korisnicko_ime, kategorija),
        )


def sve_kategorije(korisnicko_ime):
    with _konekcija() as k:
        redovi = k.execute(
            "SELECT naziv FROM kategorije WHERE korisnicko_ime = ? ORDER BY naziv",
            (korisnicko_ime,),
        ).fetchall()
    return [r["naziv"] for r in redovi]


def napravi_kategoriju(korisnicko_ime, naziv):
    if not naziv:
        return
    with _konekcija() as k:
        _upisi_kategoriju(k, korisnicko_ime, naziv)


def dodaj_belesku(korisnicko_ime, naslov, opis, kategorija, rok):
    datum = datetime.now().isoformat(timespec="seconds")
    with _konekcija() as k:
        kursor = k.execute(
            "INSERT INTO beleske "
            "(korisnicko_ime, naslov, opis, kategorija, datum, uradjeno, rok, deljenje_id) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, NULL)",
            (korisnicko_ime, naslov, opis, kategorija, datum, rok),
        )
        novi_id = kursor.lastrowid
        _upisi_kategoriju(k, korisnicko_ime, kategorija)
    return nadji_belesku(korisnicko_ime, novi_id)


def izmeni_belesku(korisnicko_ime, id_, naslov, opis, kategorija, rok):
    with _konekcija() as k:
        kursor = k.execute(
            "UPDATE beleske SET naslov = ?, opis = ?, kategorija = ?, rok = ? "
            "WHERE id = ? AND korisnicko_ime = ?",
            (naslov, opis, kategorija, rok, id_, korisnicko_ime),
        )
        _upisi_kategoriju(k, korisnicko_ime, kategorija)
    return kursor.rowcount > 0


def obrisi_belesku(korisnicko_ime, id_):
    beleska = nadji_belesku(korisnicko_ime, id_)
    if beleska is None:
        return None
    with _konekcija() as k:
        k.execute(
            "DELETE FROM beleske WHERE id = ? AND korisnicko_ime = ?",
            (id_, korisnicko_ime),
        )
    return beleska


def vrati_belesku(korisnicko_ime, beleska):
    if nadji_belesku(korisnicko_ime, beleska["id"]) is not None:
        return
    with _konekcija() as k:
        k.execute(
            "INSERT INTO beleske "
            "(id, korisnicko_ime, naslov, opis, kategorija, datum, uradjeno, rok, deljenje_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                beleska["id"], korisnicko_ime, beleska["naslov"], beleska["opis"],
                beleska["kategorija"], beleska["datum"], int(bool(beleska["uradjeno"])),
                beleska.get("rok"), beleska.get("deljenje_id"),
            ),
        )


def toggle_belesku(korisnicko_ime, id_):
    beleska = nadji_belesku(korisnicko_ime, id_)
    if beleska is None:
        return None
    novi_status = not beleska["uradjeno"]
    with _konekcija() as k:
        k.execute(
            "UPDATE beleske SET uradjeno = ? WHERE id = ? AND korisnicko_ime = ?",
            (int(novi_status), id_, korisnicko_ime),
        )
    return novi_status


def premesti_belesku(korisnicko_ime, id_, nova_kategorija):
    beleska = nadji_belesku(korisnicko_ime, id_)
    if beleska is None:
        return None
    with _konekcija() as k:
        k.execute(
            "UPDATE beleske SET kategorija = ? WHERE id = ? AND korisnicko_ime = ?",
            (nova_kategorija, id_, korisnicko_ime),
        )
        _upisi_kategoriju(k, korisnicko_ime, nova_kategorija)
    return nova_kategorija


def postavi_deljenje(korisnicko_ime, id_):
    beleska = nadji_belesku(korisnicko_ime, id_)
    if beleska is None:
        return None
    novi_token = None if beleska.get("deljenje_id") else secrets.token_urlsafe(8)
    with _konekcija() as k:
        k.execute(
            "UPDATE beleske SET deljenje_id = ? WHERE id = ? AND korisnicko_ime = ?",
            (novi_token, id_, korisnicko_ime),
        )
    return novi_token


def nadji_po_deljenju(token):
    with _konekcija() as k:
        red = k.execute("SELECT * FROM beleske WHERE deljenje_id = ?", (token,)).fetchone()
    if red is None:
        return None
    return red["korisnicko_ime"], _red_u_recnik(red)
