# podaci_json.py - skladiste podataka, JSON fajl verzija (LEGACY/FALLBACK).
#
# Ovo je bio originalni nacin cuvanja podataka pre prelaska na SQLite
# (vidi podaci_sqlite.py). Ostavljen je netaknut kao rezerva - ako SQLite
# ikad napravi problem, pokretanje sa PODACI_BACKEND=json vraca aplikaciju
# na ovaj fajl-bazirani nacin rada bez ijedne izmene u app.py.
#
# Mana ovog pristupa (razlog prelaska na SQLite): ceo fajl se cita i
# prepisuje pri SVAKOJ izmeni, pa dva istovremena zahteva teorijski mogu
# da se pobiju i pokvare podatke. Za licnu upotrebu jednog-dva korisnika
# to je redak rizik, ali SQLite ga resava iz korena.

import json
import os
import secrets
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")


def _ucitaj():
    if not os.path.exists(DATA_FILE):
        return {"sledeci_id": 1, "korisnici": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _sacuvaj(podaci):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(podaci, f, ensure_ascii=False, indent=2)


def _nadji(beleske, id_):
    for b in beleske:
        if b["id"] == id_:
            return b
    return None


def inicijalizuj():
    if not os.path.exists(DATA_FILE):
        _sacuvaj({"sledeci_id": 1, "korisnici": {}})


def korisnik_postoji(korisnicko_ime):
    return korisnicko_ime in _ucitaj()["korisnici"]


def lozinka_hash_za(korisnicko_ime):
    korisnik = _ucitaj()["korisnici"].get(korisnicko_ime)
    return korisnik["lozinka_hash"] if korisnik else None


def napravi_korisnika(korisnicko_ime, lozinka_hash):
    podaci = _ucitaj()
    podaci["korisnici"][korisnicko_ime] = {"lozinka_hash": lozinka_hash, "beleske": [], "kategorije": []}
    _sacuvaj(podaci)


def _upisi_kategoriju(korisnik, kategorija):
    if kategorija and kategorija not in korisnik.setdefault("kategorije", []):
        korisnik["kategorije"].append(kategorija)


def sve_kategorije(korisnicko_ime):
    korisnik = _ucitaj()["korisnici"].get(korisnicko_ime)
    return sorted(korisnik.get("kategorije", [])) if korisnik else []


def napravi_kategoriju(korisnicko_ime, naziv):
    if not naziv:
        return
    podaci = _ucitaj()
    _upisi_kategoriju(podaci["korisnici"][korisnicko_ime], naziv)
    _sacuvaj(podaci)


def sve_beleske(korisnicko_ime):
    beleske = _ucitaj()["korisnici"][korisnicko_ime]["beleske"]
    return sorted(beleske, key=lambda b: b["datum"], reverse=True)


def nadji_belesku(korisnicko_ime, id_):
    korisnik = _ucitaj()["korisnici"].get(korisnicko_ime)
    if not korisnik:
        return None
    return _nadji(korisnik["beleske"], id_)


def dodaj_belesku(korisnicko_ime, naslov, opis, kategorija, rok):
    podaci = _ucitaj()
    nova = {
        "id": podaci["sledeci_id"],
        "naslov": naslov,
        "opis": opis,
        "kategorija": kategorija,
        "datum": datetime.now().isoformat(timespec="seconds"),
        "uradjeno": False,
        "rok": rok,
        "deljenje_id": None,
    }
    podaci["sledeci_id"] += 1
    korisnik = podaci["korisnici"][korisnicko_ime]
    korisnik["beleske"].append(nova)
    _upisi_kategoriju(korisnik, kategorija)
    _sacuvaj(podaci)
    return nova


def izmeni_belesku(korisnicko_ime, id_, naslov, opis, kategorija, rok):
    podaci = _ucitaj()
    korisnik = podaci["korisnici"].get(korisnicko_ime)
    beleska = _nadji(korisnik["beleske"], id_) if korisnik else None
    if beleska is None:
        return False
    beleska["naslov"] = naslov
    beleska["opis"] = opis
    beleska["kategorija"] = kategorija
    beleska["rok"] = rok
    _upisi_kategoriju(korisnik, kategorija)
    _sacuvaj(podaci)
    return True


def obrisi_belesku(korisnicko_ime, id_):
    podaci = _ucitaj()
    korisnik = podaci["korisnici"].get(korisnicko_ime)
    if not korisnik:
        return None
    beleska = _nadji(korisnik["beleske"], id_)
    if beleska is None:
        return None
    korisnik["beleske"].remove(beleska)
    _sacuvaj(podaci)
    return beleska


def vrati_belesku(korisnicko_ime, beleska):
    podaci = _ucitaj()
    korisnik = podaci["korisnici"][korisnicko_ime]
    if _nadji(korisnik["beleske"], beleska["id"]) is None:
        korisnik["beleske"].append({
            "id": beleska["id"],
            "naslov": beleska["naslov"],
            "opis": beleska["opis"],
            "kategorija": beleska["kategorija"],
            "datum": beleska["datum"],
            "uradjeno": bool(beleska["uradjeno"]),
            "rok": beleska.get("rok"),
            "deljenje_id": beleska.get("deljenje_id"),
        })
        _sacuvaj(podaci)


def toggle_belesku(korisnicko_ime, id_):
    podaci = _ucitaj()
    korisnik = podaci["korisnici"].get(korisnicko_ime)
    beleska = _nadji(korisnik["beleske"], id_) if korisnik else None
    if beleska is None:
        return None
    beleska["uradjeno"] = not beleska["uradjeno"]
    _sacuvaj(podaci)
    return beleska["uradjeno"]


def premesti_belesku(korisnicko_ime, id_, nova_kategorija):
    podaci = _ucitaj()
    korisnik = podaci["korisnici"].get(korisnicko_ime)
    beleska = _nadji(korisnik["beleske"], id_) if korisnik else None
    if beleska is None:
        return None
    beleska["kategorija"] = nova_kategorija
    _upisi_kategoriju(korisnik, nova_kategorija)
    _sacuvaj(podaci)
    return beleska["kategorija"]


def postavi_deljenje(korisnicko_ime, id_):
    podaci = _ucitaj()
    korisnik = podaci["korisnici"].get(korisnicko_ime)
    beleska = _nadji(korisnik["beleske"], id_) if korisnik else None
    if beleska is None:
        return None
    beleska["deljenje_id"] = None if beleska.get("deljenje_id") else secrets.token_urlsafe(8)
    _sacuvaj(podaci)
    return beleska["deljenje_id"]


def nadji_po_deljenju(token):
    podaci = _ucitaj()
    for korisnicko_ime, korisnik in podaci["korisnici"].items():
        beleska = next((b for b in korisnik["beleske"] if b.get("deljenje_id") == token), None)
        if beleska is not None:
            return korisnicko_ime, beleska
    return None
