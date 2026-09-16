# generisi_vapid_kljuceve.py - JEDNOKRATNI skript, pokreni ga rucno:
#   python generisi_vapid_kljuceve.py
#
# VAPID (Voluntary Application Server Identification) je par kljuceva kojim
# nas server "potpisuje" push poruke, da push servisi (Chrome/Edge/Firefox)
# znaju da su stvarno od nas. Isti javni/privatni par se koristi za SVE
# korisnike - generise se JEDNOM, ne po korisniku (za razliku od lozinki).
#
# Pascal poredjenje: nema pravog ekvivalenta - najblize je "digitalni potpis"
# kojim dokazujes da si ti poslao poruku, a ne neko drugi.
#
# Ispisane vrednosti se postavljaju kao env varijable pre pokretanja app.py,
# isti obrazac kao vec postojeci SECRET_KEY/ANTHROPIC_API_KEY:
#   VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_KONTAKT_EMAIL
# Bez njih, push rute u app.py vracaju prijateljski 503 (isti obrazac kao
# /api/asistent bez ANTHROPIC_API_KEY).

import base64

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid01


def _bez_paddinga(sirovi_bajtovi):
    # Web Push ocekuje base64url BEZ "=" paddinga na kraju.
    return base64.urlsafe_b64encode(sirovi_bajtovi).rstrip(b"=").decode("ascii")


def main():
    vapid = Vapid01()
    vapid.generate_keys()

    javni_bajtovi = vapid.public_key.public_bytes(
        encoding=Encoding.X962, format=PublicFormat.UncompressedPoint
    )
    privatni_bajtovi = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")

    print("Generisan novi VAPID par. Postavi kao env varijable pre pokretanja app.py:\n")
    print(f"VAPID_PUBLIC_KEY={_bez_paddinga(javni_bajtovi)}")
    print(f"VAPID_PRIVATE_KEY={_bez_paddinga(privatni_bajtovi)}")
    print("VAPID_KONTAKT_EMAIL=tvoj-email@primer.com\n")
    print("(VAPID_KONTAKT_EMAIL je kontakt koji push servisi vide ako nesto zatreba da te obaveste - upisi svoj pravi mejl.)")


if __name__ == "__main__":
    main()
