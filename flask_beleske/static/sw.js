// Service worker za "Beleske" PWA.
// Pascal nema ekvivalent - ovo je poseban skript koji browser pokrece u
// pozadini (van stranice) i moze da presretne mrezne zahteve, cak i offline.

const CACHE_NAZIV = "beleske-v2";
const OSNOVNI_FAJLOVI = [
    "/static/style.css",
    "/static/app.js",
    "/static/manifest.json",
    "/static/icons/icon-192.png",
    "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAZIV).then((cache) => cache.addAll(OSNOVNI_FAJLOVI))
    );
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((imena) =>
            Promise.all(
                imena
                    .filter((ime) => ime !== CACHE_NAZIV)
                    .map((ime) => caches.delete(ime))
            )
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const zahtev = event.request;
    if (zahtev.method !== "GET") return;

    // Stranice: mreza prva (uvek svez sadrzaj kad ima interneta), a svaka
    // uspesno ucitana stranica se cuva pa je dostupna i offline sledeci put.
    if (zahtev.mode === "navigate") {
        event.respondWith(
            fetch(zahtev)
                .then((odgovor) => {
                    const kopija = odgovor.clone();
                    caches.open(CACHE_NAZIV).then((cache) => cache.put(zahtev, kopija));
                    return odgovor;
                })
                .catch(() => caches.match(zahtev))
        );
        return;
    }

    // Staticki fajlovi (CSS/JS/ikonice): mreza prva - isto kao stranice.
    // Bitno tokom razvoja: fajl se cesto menja, pa "kes prvi" bi znacio da
    // izmene u style.css/app.js ne bi bile vidljive dok se kes ne isprazni.
    if (zahtev.url.includes("/static/")) {
        event.respondWith(
            fetch(zahtev)
                .then((odgovor) => {
                    const kopija = odgovor.clone();
                    caches.open(CACHE_NAZIV).then((cache) => cache.put(zahtev, kopija));
                    return odgovor;
                })
                .catch(() => caches.match(zahtev))
        );
    }
});

// ---------- Web Push: server salje "push" dogadjaj cak i kad tab nije otvoren ----------
// Ovo je razlog zasto service worker uopste postoji za push - obican JS na
// stranici ne moze nista da uradi dok je tab zatvoren, service worker moze.

self.addEventListener("push", (event) => {
    let podaci = { naslov: "Rok je stigao", telo: "", id: null };
    try {
        podaci = event.data.json();
    } catch (e) {
        // ako telo poruke nije validan JSON, ostaju podrazumevane vrednosti
    }

    event.waitUntil(
        self.registration.showNotification(podaci.naslov || "Rok je stigao", {
            body: podaci.telo || "",
            icon: "/static/icons/icon-192.png",
            tag: podaci.id ? "rok-" + podaci.id : undefined,
            data: { id: podaci.id },
        })
    );
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const id = event.notification.data && event.notification.data.id;
    const putanja = id ? `/beleska/${id}` : "/";

    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then((listaKlijenata) => {
            for (const klijent of listaKlijenata) {
                if (klijent.url.includes(putanja) && "focus" in klijent) return klijent.focus();
            }
            if (clients.openWindow) return clients.openWindow(putanja);
        })
    );
});
