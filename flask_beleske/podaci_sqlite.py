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

import calendar
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

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
        # Tagovi - nezavisni od kategorije, beleska moze imati vise njih
        # odjednom (za razliku od kategorije, koja je uvek tacno jedna).
        k.execute("""
            CREATE TABLE IF NOT EXISTS beleska_tagovi (
                beleska_id INTEGER NOT NULL,
                naziv TEXT NOT NULL,
                PRIMARY KEY (beleska_id, naziv)
            )
        """)
        k.execute("""
            CREATE TABLE IF NOT EXISTS podzadaci (
                id INTEGER PRIMARY KEY,
                beleska_id INTEGER NOT NULL,
                tekst TEXT NOT NULL,
                uradjeno INTEGER NOT NULL DEFAULT 0,
                redosled INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Saradnja: ko sme da PRISTUPI/menja belesku (vlasnik ILI saradnik) je
        # sad odvojeno od toga cija je beleska (uvek vlasnik, kolona
        # beleske.korisnicko_ime se ne dira).
        k.execute("""
            CREATE TABLE IF NOT EXISTS saradnici (
                beleska_id INTEGER NOT NULL,
                korisnicko_ime TEXT NOT NULL,
                PRIMARY KEY (beleska_id, korisnicko_ime)
            )
        """)
        # Istorija izmena - snapshot polja PRE svake izmene (ko, kada, sta je
        # bilo pre) - omogucava i "Vrati na ovu verziju".
        k.execute("""
            CREATE TABLE IF NOT EXISTS beleska_istorija (
                id INTEGER PRIMARY KEY,
                beleska_id INTEGER NOT NULL,
                korisnicko_ime TEXT NOT NULL,
                vreme TEXT NOT NULL,
                naslov TEXT,
                opis TEXT,
                kategorija TEXT,
                rok TEXT
            )
        """)
        # ALTER TABLE ADD COLUMN je bezbedan na postojecoj bazi u SQLite-u,
        # ali nije "IF NOT EXISTS" kao CREATE TABLE - probaj/uhvati "duplicate
        # column" da poziv ostane idempotentan (moze da se zove i posle prve
        # instalacije, kad kolona vec postoji).
        try:
            k.execute("ALTER TABLE beleske ADD COLUMN ponavljanje TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e):
                raise
        try:
            k.execute("ALTER TABLE beleske ADD COLUMN podsetnik_poslat INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e):
                raise
        # Push pretplate (Web Push) - jedan red po uredjaju/browseru na kome je
        # korisnik ukljucio podsetnike; endpoint je jedinstven (bez njega
        # server ne zna kome/kako da posalje notifikaciju).
        k.execute("""
            CREATE TABLE IF NOT EXISTS push_pretplate (
                korisnicko_ime TEXT NOT NULL,
                endpoint TEXT PRIMARY KEY,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL
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
        "korisnicko_ime": red["korisnicko_ime"],  # pravi vlasnik - vidi nadji_belesku_sa_pristupom
        "naslov": red["naslov"],
        "opis": red["opis"],
        "kategorija": red["kategorija"],
        "datum": red["datum"],
        "uradjeno": bool(red["uradjeno"]),
        "rok": red["rok"],
        "deljenje_id": red["deljenje_id"],
        "ponavljanje": red["ponavljanje"],
        "tagovi": tagovi_za_belesku(red["id"]),
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
        # Brojevi podzadataka se racunaju JEDNIM grupisanim upitom (za
        # razliku od tagova gore, koji idu po-belesci) - inace bi lista sa
        # N beleski otvorila jos N upita samo za "2/5" bedzeve.
        brojaci = k.execute(
            "SELECT beleska_id, COUNT(*) AS ukupno, SUM(uradjeno) AS uradjeno "
            "FROM podzadaci GROUP BY beleska_id"
        ).fetchall()

    brojaci_po_belesci = {r["beleska_id"]: (r["ukupno"], r["uradjeno"] or 0) for r in brojaci}
    beleske = [_red_u_recnik(r) for r in redovi]
    for b in beleske:
        ukupno, uradjeno = brojaci_po_belesci.get(b["id"], (0, 0))
        b["broj_podzadataka"] = ukupno
        b["broj_uradjeno_podzadataka"] = uradjeno
    return beleske


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


def dodaj_belesku(korisnicko_ime, naslov, opis, kategorija, rok, ponavljanje=None):
    datum = datetime.now().isoformat(timespec="seconds")
    with _konekcija() as k:
        kursor = k.execute(
            "INSERT INTO beleske "
            "(korisnicko_ime, naslov, opis, kategorija, datum, uradjeno, rok, deljenje_id, ponavljanje) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, NULL, ?)",
            (korisnicko_ime, naslov, opis, kategorija, datum, rok, ponavljanje),
        )
        novi_id = kursor.lastrowid
        _upisi_kategoriju(k, korisnicko_ime, kategorija)
    return nadji_belesku(korisnicko_ime, novi_id)


def izmeni_belesku(korisnicko_ime, id_, naslov, opis, kategorija, rok, ponavljanje=None, editor=None):
    with _konekcija() as k:
        stara = k.execute(
            "SELECT naslov, opis, kategorija, rok FROM beleske WHERE id = ? AND korisnicko_ime = ?",
            (id_, korisnicko_ime),
        ).fetchone()
        if stara is None:
            return False

        # Snapshot STAROG stanja PRE update-a - editor moze biti vlasnik ili
        # saradnik (ko je stvarno kliknuo "Sacuvaj"), za razliku od
        # korisnicko_ime koji je uvek vlasnik beleske.
        k.execute(
            "INSERT INTO beleska_istorija (beleska_id, korisnicko_ime, vreme, naslov, opis, kategorija, rok) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                id_, editor or korisnicko_ime, datetime.now().isoformat(timespec="seconds"),
                stara["naslov"], stara["opis"], stara["kategorija"], stara["rok"],
            ),
        )
        kursor = k.execute(
            # podsetnik_poslat se resetuje na 0 - rok je (mozda) promenjen,
            # pa ako je vec bio "prosao" i podsetnik poslat, novi/isti rok
            # treba ponovo da moze da okine podsetnik.
            "UPDATE beleske SET naslov = ?, opis = ?, kategorija = ?, rok = ?, ponavljanje = ?, "
            "podsetnik_poslat = 0 WHERE id = ? AND korisnicko_ime = ?",
            (naslov, opis, kategorija, rok, ponavljanje, id_, korisnicko_ime),
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
        # Bez ovoga bi tagovi/podzadaci ostali "siroci" u bazi - a kako id
        # NIJE AUTOINCREMENT (vidi inicijalizuj), sledeca NOVA beleska moze
        # dobiti bas ovaj isti id i slucajno naslediti tudje stare podatke.
        k.execute("DELETE FROM beleska_tagovi WHERE beleska_id = ?", (id_,))
        k.execute("DELETE FROM podzadaci WHERE beleska_id = ?", (id_,))
    return beleska


def vrati_belesku(korisnicko_ime, beleska):
    if nadji_belesku(korisnicko_ime, beleska["id"]) is not None:
        return
    with _konekcija() as k:
        k.execute(
            "INSERT INTO beleske "
            "(id, korisnicko_ime, naslov, opis, kategorija, datum, uradjeno, rok, deljenje_id, ponavljanje) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                beleska["id"], korisnicko_ime, beleska["naslov"], beleska["opis"],
                beleska["kategorija"], beleska["datum"], int(bool(beleska["uradjeno"])),
                beleska.get("rok"), beleska.get("deljenje_id"), beleska.get("ponavljanje"),
            ),
        )
    # Podzadaci se NE vracaju (namerno) - "Ponisti" posle brisanja je
    # zamisljen za brzu ispravku klika, ne kao puni backup checklist-e.
    postavi_tagove(korisnicko_ime, beleska["id"], beleska.get("tagovi") or [])


def _sledeci_rok(rok_iso, ponavljanje):
    # Pascal poredjenje: "dodaj mesec rucno" bez eksternog libaya poput
    # dateutil - calendar.monthrange daje broj dana u ciljnom mesecu, da
    # npr. 31. januar postane 28./29. februar umesto da baci gresku.
    trenutni = datetime.fromisoformat(rok_iso)
    if ponavljanje == "dnevno":
        sledeci = trenutni + timedelta(days=1)
    elif ponavljanje == "nedeljno":
        sledeci = trenutni + timedelta(weeks=1)
    elif ponavljanje == "mesecno":
        sledeca_godina = trenutni.year + (trenutni.month // 12)
        sledeci_mesec = trenutni.month % 12 + 1
        poslednji_dan = calendar.monthrange(sledeca_godina, sledeci_mesec)[1]
        sledeci = trenutni.replace(
            year=sledeca_godina, month=sledeci_mesec, day=min(trenutni.day, poslednji_dan)
        )
    else:
        return rok_iso
    return sledeci.isoformat(timespec="minutes")


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

    # Kad se ponavljajuci zadatak zavrsi, odmah se pravi SLEDECA instanca sa
    # pomerenim rokom - stara (upravo zavrsena) ostaje zavrsena, istorija se
    # ne gubi (za razliku od pukog pomeranja roka na istom redu).
    if novi_status and beleska["ponavljanje"] and beleska["rok"]:
        novi_rok = _sledeci_rok(beleska["rok"], beleska["ponavljanje"])
        nova = dodaj_belesku(
            korisnicko_ime, beleska["naslov"], beleska["opis"], beleska["kategorija"],
            novi_rok, beleska["ponavljanje"],
        )
        postavi_tagove(korisnicko_ime, nova["id"], beleska["tagovi"])

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


# ---------- Tagovi ----------

def tagovi_za_belesku(beleska_id):
    with _konekcija() as k:
        redovi = k.execute(
            "SELECT naziv FROM beleska_tagovi WHERE beleska_id = ? ORDER BY naziv",
            (beleska_id,),
        ).fetchall()
    return [r["naziv"] for r in redovi]


def sve_tagove_korisnika(korisnicko_ime):
    with _konekcija() as k:
        redovi = k.execute(
            "SELECT DISTINCT bt.naziv FROM beleska_tagovi bt "
            "JOIN beleske b ON b.id = bt.beleska_id "
            "WHERE b.korisnicko_ime = ? ORDER BY bt.naziv",
            (korisnicko_ime,),
        ).fetchall()
    return [r["naziv"] for r in redovi]


def postavi_tagove(korisnicko_ime, beleska_id, lista_tagova):
    # DELETE pa INSERT je prostije od diff-a starih/novih tagova - beleska
    # retko ima vise od par tagova, pa cena toga je zanemarljiva.
    if nadji_belesku(korisnicko_ime, beleska_id) is None:
        return
    with _konekcija() as k:
        k.execute("DELETE FROM beleska_tagovi WHERE beleska_id = ?", (beleska_id,))
        for tag in lista_tagova:
            k.execute(
                "INSERT OR IGNORE INTO beleska_tagovi (beleska_id, naziv) VALUES (?, ?)",
                (beleska_id, tag),
            )


# ---------- Podzadaci ----------

def podzadaci_za_belesku(beleska_id):
    with _konekcija() as k:
        redovi = k.execute(
            "SELECT id, tekst, uradjeno, redosled FROM podzadaci "
            "WHERE beleska_id = ? ORDER BY redosled, id",
            (beleska_id,),
        ).fetchall()
    return [
        {"id": r["id"], "tekst": r["tekst"], "uradjeno": bool(r["uradjeno"]), "redosled": r["redosled"]}
        for r in redovi
    ]


def dodaj_podzadatak(korisnicko_ime, beleska_id, tekst):
    if nadji_belesku(korisnicko_ime, beleska_id) is None:
        return None
    with _konekcija() as k:
        red = k.execute(
            "SELECT COALESCE(MAX(redosled), -1) + 1 AS sledeci FROM podzadaci WHERE beleska_id = ?",
            (beleska_id,),
        ).fetchone()
        sledeci_redosled = red["sledeci"]
        kursor = k.execute(
            "INSERT INTO podzadaci (beleska_id, tekst, uradjeno, redosled) VALUES (?, ?, 0, ?)",
            (beleska_id, tekst, sledeci_redosled),
        )
        novi_id = kursor.lastrowid
    return {"id": novi_id, "tekst": tekst, "uradjeno": False, "redosled": sledeci_redosled}


def _podzadatak_dostupan_korisniku(k, korisnicko_ime, podzadatak_id):
    # "Dostupan" = vlasnik ILI saradnik na belesci kojoj podzadatak pripada -
    # ne trazi se vise iskljucivo vlasnistvo (za razliku od Faze 1).
    red = k.execute(
        "SELECT p.id FROM podzadaci p JOIN beleske b ON b.id = p.beleska_id "
        "WHERE p.id = ? AND (b.korisnicko_ime = ? OR EXISTS ("
        "SELECT 1 FROM saradnici s WHERE s.beleska_id = b.id AND s.korisnicko_ime = ?"
        "))",
        (podzadatak_id, korisnicko_ime, korisnicko_ime),
    ).fetchone()
    return red is not None


def toggle_podzadatak(korisnicko_ime, podzadatak_id):
    with _konekcija() as k:
        if not _podzadatak_dostupan_korisniku(k, korisnicko_ime, podzadatak_id):
            return None
        red = k.execute("SELECT uradjeno FROM podzadaci WHERE id = ?", (podzadatak_id,)).fetchone()
        novi_status = not red["uradjeno"]
        k.execute("UPDATE podzadaci SET uradjeno = ? WHERE id = ?", (int(novi_status), podzadatak_id))
    return novi_status


def obrisi_podzadatak(korisnicko_ime, podzadatak_id):
    with _konekcija() as k:
        if not _podzadatak_dostupan_korisniku(k, korisnicko_ime, podzadatak_id):
            return False
        k.execute("DELETE FROM podzadaci WHERE id = ?", (podzadatak_id,))
    return True


# ---------- Saradnja (deljenje sa pravom izmene + istorija) ----------

def nadji_belesku_sa_pristupom(korisnicko_ime, id_):
    # Za razliku od nadji_belesku (STROGO vlasnik), ovo pusta i saradnika.
    # Vraceni dict ima "korisnicko_ime" = PRAVI vlasnik - pozivalac (ruta u
    # app.py) njega prosledjuje mutation funkcijama, ne current_user.id.
    with _konekcija() as k:
        red = k.execute(
            "SELECT b.* FROM beleske b WHERE b.id = ? AND (b.korisnicko_ime = ? OR EXISTS ("
            "SELECT 1 FROM saradnici s WHERE s.beleska_id = b.id AND s.korisnicko_ime = ?"
            "))",
            (id_, korisnicko_ime, korisnicko_ime),
        ).fetchone()
    return _red_u_recnik(red) if red else None


def beleske_dostupne(korisnicko_ime):
    # Zamena za sve_beleske na pocetnoj - unija sopstvenih i deljenih
    # beleski. Svaki red dobija "vlasnik" i "da_li_je_vlasnik" da template
    # zna kad da prikaze "Deljeno od X".
    with _konekcija() as k:
        redovi = k.execute(
            "SELECT b.* FROM beleske b WHERE b.korisnicko_ime = ? "
            "UNION "
            "SELECT b.* FROM beleske b JOIN saradnici s ON s.beleska_id = b.id "
            "WHERE s.korisnicko_ime = ? "
            "ORDER BY datum DESC",
            (korisnicko_ime, korisnicko_ime),
        ).fetchall()
        brojaci = k.execute(
            "SELECT beleska_id, COUNT(*) AS ukupno, SUM(uradjeno) AS uradjeno "
            "FROM podzadaci GROUP BY beleska_id"
        ).fetchall()

    brojaci_po_belesci = {r["beleska_id"]: (r["ukupno"], r["uradjeno"] or 0) for r in brojaci}
    beleske = [_red_u_recnik(r) for r in redovi]
    for b in beleske:
        ukupno, uradjeno = brojaci_po_belesci.get(b["id"], (0, 0))
        b["broj_podzadataka"] = ukupno
        b["broj_uradjeno_podzadataka"] = uradjeno
        b["vlasnik"] = b["korisnicko_ime"]
        b["da_li_je_vlasnik"] = b["korisnicko_ime"] == korisnicko_ime
    return beleske


def saradnici_za(beleska_id):
    with _konekcija() as k:
        redovi = k.execute(
            "SELECT korisnicko_ime FROM saradnici WHERE beleska_id = ? ORDER BY korisnicko_ime",
            (beleska_id,),
        ).fetchall()
    return [r["korisnicko_ime"] for r in redovi]


def dodaj_saradnika(vlasnik, beleska_id, korisnicko_ime_saradnika):
    if nadji_belesku(vlasnik, beleska_id) is None:
        return False
    if korisnicko_ime_saradnika == vlasnik or not korisnik_postoji(korisnicko_ime_saradnika):
        return False
    with _konekcija() as k:
        k.execute(
            "INSERT OR IGNORE INTO saradnici (beleska_id, korisnicko_ime) VALUES (?, ?)",
            (beleska_id, korisnicko_ime_saradnika),
        )
    return True


def ukloni_saradnika(vlasnik, beleska_id, korisnicko_ime_saradnika):
    if nadji_belesku(vlasnik, beleska_id) is None:
        return False
    with _konekcija() as k:
        k.execute(
            "DELETE FROM saradnici WHERE beleska_id = ? AND korisnicko_ime = ?",
            (beleska_id, korisnicko_ime_saradnika),
        )
    return True


def istorija_za_belesku(beleska_id):
    with _konekcija() as k:
        redovi = k.execute(
            "SELECT id, korisnicko_ime, vreme, naslov, opis, kategorija, rok "
            "FROM beleska_istorija WHERE beleska_id = ? ORDER BY vreme DESC, id DESC",
            (beleska_id,),
        ).fetchall()
    return [dict(r) for r in redovi]


def vrati_na_verziju(vlasnik, beleska_id, istorija_id):
    with _konekcija() as k:
        stara = k.execute(
            "SELECT * FROM beleska_istorija WHERE id = ? AND beleska_id = ?",
            (istorija_id, beleska_id),
        ).fetchone()
        trenutna = k.execute(
            "SELECT * FROM beleske WHERE id = ? AND korisnicko_ime = ?",
            (beleska_id, vlasnik),
        ).fetchone()
        if stara is None or trenutna is None:
            return False

        # Vracanje samo po sebi upisuje snapshot TRENUTNOG stanja pre nego sto
        # se prepise - tako je i samo vracanje reverzibilno.
        k.execute(
            "INSERT INTO beleska_istorija (beleska_id, korisnicko_ime, vreme, naslov, opis, kategorija, rok) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                beleska_id, vlasnik, datetime.now().isoformat(timespec="seconds"),
                trenutna["naslov"], trenutna["opis"], trenutna["kategorija"], trenutna["rok"],
            ),
        )
        k.execute(
            "UPDATE beleske SET naslov = ?, opis = ?, kategorija = ?, rok = ? WHERE id = ?",
            (stara["naslov"], stara["opis"], stara["kategorija"], stara["rok"], beleska_id),
        )
    return True


# ---------- Push pretplate (Web Push podsetnici) ----------

def sacuvaj_pretplatu(korisnicko_ime, endpoint, p256dh, auth):
    with _konekcija() as k:
        k.execute(
            "INSERT INTO push_pretplate (korisnicko_ime, endpoint, p256dh, auth) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(endpoint) DO UPDATE SET "
            "korisnicko_ime = excluded.korisnicko_ime, p256dh = excluded.p256dh, auth = excluded.auth",
            (korisnicko_ime, endpoint, p256dh, auth),
        )


def obrisi_pretplatu(endpoint):
    with _konekcija() as k:
        k.execute("DELETE FROM push_pretplate WHERE endpoint = ?", (endpoint,))


def pretplate_za(korisnicko_ime):
    with _konekcija() as k:
        redovi = k.execute(
            "SELECT endpoint, p256dh, auth FROM push_pretplate WHERE korisnicko_ime = ?",
            (korisnicko_ime,),
        ).fetchall()
    return [{"endpoint": r["endpoint"], "p256dh": r["p256dh"], "auth": r["auth"]} for r in redovi]


def beleske_za_podsetnik():
    # Cross-user (za razliku od ostatka fajla) - pozadinska nit u app.py
    # jednom u minuti proverava SVE korisnike odjednom, ne jednog po zahtevu.
    sada = datetime.now().isoformat(timespec="minutes")
    with _konekcija() as k:
        redovi = k.execute(
            "SELECT id, korisnicko_ime, naslov FROM beleske "
            "WHERE rok IS NOT NULL AND rok <= ? AND uradjeno = 0 AND podsetnik_poslat = 0",
            (sada,),
        ).fetchall()
    return [dict(r) for r in redovi]


def oznaci_podsetnik_poslat(id_):
    with _konekcija() as k:
        k.execute("UPDATE beleske SET podsetnik_poslat = 1 WHERE id = ?", (id_,))
