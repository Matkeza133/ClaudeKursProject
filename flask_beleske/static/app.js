document.addEventListener("DOMContentLoaded", () => {
    const lista = document.getElementById("lista-beleski");
    const pretragaUnos = document.getElementById("pretraga");
    const tabStatus = document.getElementById("tabovi-status");
    const tabKategorija = document.getElementById("tabovi-kategorije");
    const nemaRezultata = document.getElementById("nema-rezultata");
    const progresIspuna = document.getElementById("progres-ispuna");
    const progresTekst = document.getElementById("progres-tekst-vrednost");
    const porukeKontejner = document.getElementById("poruke");

    let stanjeStatus = "sve";
    let stanjeKategorija = "sve";

    // ---------- Pretraga + tabovi (status/kategorija) rade zajedno ----------
    // Pascal: umesto jedne petlje koja gasi/pali <li>, sad tri uslova moraju
    // svi da budu tacna (isto kao "if a and b and c then prikazi").

    function primeniFiltere() {
        if (!lista) return;
        const upit = pretragaUnos ? pretragaUnos.value.trim().toLowerCase() : "";
        let vidljivo = 0;

        lista.querySelectorAll("li").forEach((stavka) => {
            const tekst = stavka.dataset.tekst || "";
            const status = stavka.dataset.status || "";
            const kategorija = stavka.dataset.kategorija || "";

            const poklapaTekst = tekst.includes(upit);
            const poklapaStatus = stanjeStatus === "sve" || status === stanjeStatus;
            const poklapaKategoriju = stanjeKategorija === "sve" || kategorija === stanjeKategorija;

            const prikazi = poklapaTekst && poklapaStatus && poklapaKategoriju;
            stavka.style.display = prikazi ? "" : "none";
            if (prikazi) vidljivo++;
        });

        if (nemaRezultata) {
            nemaRezultata.style.display = vidljivo === 0 ? "" : "none";
        }
    }

    function postaviAktivanTab(kontejner, dugme) {
        kontejner.querySelectorAll(".tab").forEach((t) => t.classList.remove("aktivan"));
        dugme.classList.add("aktivan");
    }

    if (pretragaUnos) {
        pretragaUnos.addEventListener("input", primeniFiltere);
    }

    if (tabStatus) {
        tabStatus.addEventListener("click", (e) => {
            const dugme = e.target.closest(".tab");
            if (!dugme) return;
            stanjeStatus = dugme.dataset.vrednost;
            postaviAktivanTab(tabStatus, dugme);
            primeniFiltere();
        });
    }

    if (tabKategorija) {
        tabKategorija.addEventListener("click", (e) => {
            const dugme = e.target.closest(".tab");
            if (!dugme) return;
            stanjeKategorija = dugme.dataset.vrednost;
            postaviAktivanTab(tabKategorija, dugme);
            primeniFiltere();
        });
    }

    // ---------- Statistika: "X od Y uradjeno" + traka napretka ----------

    function azurirajProgres() {
        if (!lista || !progresIspuna || !progresTekst) return;
        const ukupno = lista.querySelectorAll("li").length;
        const uradjeno = lista.querySelectorAll("li.uradjeno").length;
        const procenat = ukupno === 0 ? 0 : Math.round((uradjeno / ukupno) * 100);
        progresIspuna.style.width = procenat + "%";
        progresTekst.textContent = `${uradjeno} od ${ukupno} urađeno`;
    }

    // ---------- Toast poruke (flash sa servera + dinamicke iz JS-a) ----------

    function ukloniPoruku(stavka) {
        stavka.classList.add("nestaje");
        setTimeout(() => stavka.remove(), 250);
    }

    function zakaziNestajanje(stavka, kasnjenje) {
        setTimeout(() => {
            if (stavka.isConnected) ukloniPoruku(stavka);
        }, kasnjenje);
    }

    function prikaziToast(tekst, akcija) {
        if (!porukeKontejner) return;
        const stavka = document.createElement("li");
        stavka.className = "poruka info";

        const raspon = document.createElement("span");
        raspon.textContent = tekst;
        stavka.appendChild(raspon);

        if (akcija) {
            const dugme = document.createElement("button");
            dugme.type = "button";
            dugme.className = "poruka-akcija";
            dugme.textContent = akcija.naziv;
            dugme.addEventListener("click", () => {
                akcija.klik();
                ukloniPoruku(stavka);
            });
            stavka.appendChild(dugme);
        }

        porukeKontejner.appendChild(stavka);
        zakaziNestajanje(stavka, akcija ? 6000 : 4000);
    }

    // Flash poruke renderovane sa servera takodje automatski nestaju.
    if (porukeKontejner) {
        porukeKontejner.querySelectorAll("li.poruka").forEach((stavka) => {
            zakaziNestajanje(stavka, 4000);
        });
    }

    // ---------- Kreiranje <li> elementa za belesku (koristi se pri "Ponisti") ----------

    function napraviLiElement(b) {
        const li = document.createElement("li");
        li.className = b.uradjeno ? "uradjeno" : "";
        li.dataset.id = b.id;
        li.dataset.status = b.uradjeno ? "uradjeno" : "aktivna";
        li.dataset.kategorija = (b.kategorija || "").toLowerCase();
        li.dataset.tekst = `${b.naslov} ${b.opis} ${b.kategorija}`.toLowerCase();

        const toggleForma = document.createElement("form");
        toggleForma.action = `/toggle/${b.id}`;
        toggleForma.method = "post";
        toggleForma.className = "toggle-forma";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = b.uradjeno;
        toggleForma.appendChild(checkbox);

        const sadrzaj = document.createElement("span");
        sadrzaj.className = "sadrzaj-beleske";
        const link = document.createElement("a");
        link.href = `/beleska/${b.id}`;
        link.className = "naslov-beleske";
        link.textContent = b.naslov;
        sadrzaj.appendChild(link);

        const meta = document.createElement("span");
        meta.className = "meta";
        if (b.kategorija) {
            const bedz = document.createElement("span");
            bedz.className = "bedz";
            bedz.textContent = b.kategorija;
            meta.appendChild(bedz);
        }
        const datum = document.createElement("span");
        datum.className = "datum";
        datum.textContent = (b.datum || "").replace("T", " ");
        meta.appendChild(datum);
        sadrzaj.appendChild(meta);

        const akcije = document.createElement("span");
        akcije.className = "akcije";
        const izmeni = document.createElement("a");
        izmeni.href = `/izmeni/${b.id}`;
        izmeni.className = "izmeni";
        izmeni.textContent = "Izmeni";
        akcije.appendChild(izmeni);

        const obrisiForma = document.createElement("form");
        obrisiForma.action = `/obrisi/${b.id}`;
        obrisiForma.method = "post";
        obrisiForma.className = "obrisi-forma";
        const obrisiDugme = document.createElement("button");
        obrisiDugme.type = "submit";
        obrisiDugme.className = "obrisi";
        obrisiDugme.textContent = "Obrisi";
        obrisiForma.appendChild(obrisiDugme);
        akcije.appendChild(obrisiForma);

        li.appendChild(toggleForma);
        li.appendChild(sadrzaj);
        li.appendChild(akcije);
        return li;
    }

    // ---------- Undo brisanja ----------

    async function vratiBelesku(beleska) {
        try {
            const odgovor = await fetch("/vrati", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify(beleska),
            });
            if (!odgovor.ok) throw new Error("vracanje nije uspelo");
        } catch (e) {
            window.location.reload();
            return;
        }

        if (!lista) {
            window.location.reload();
            return;
        }

        const nova = napraviLiElement(beleska);
        lista.prepend(nova);
        zakaciListenereNaStavku(nova);
        azurirajProgres();
        primeniFiltere();
    }

    // ---------- AJAX: checkbox toggle + brisanje sa undo toast-om ----------

    function zakaciListenereNaStavku(stavka) {
        const toggleForma = stavka.querySelector(".toggle-forma");
        const checkbox = toggleForma ? toggleForma.querySelector("input[type=checkbox]") : null;

        if (checkbox) {
            checkbox.addEventListener("change", async () => {
                try {
                    const odgovor = await fetch(toggleForma.action, {
                        method: "POST",
                        headers: { "X-Requested-With": "XMLHttpRequest" },
                    });
                    if (!odgovor.ok) throw new Error("toggle nije uspeo");
                    const podaci = await odgovor.json();
                    stavka.classList.toggle("uradjeno", podaci.uradjeno);
                    stavka.dataset.status = podaci.uradjeno ? "uradjeno" : "aktivna";
                    azurirajProgres();
                    primeniFiltere();
                } catch (e) {
                    toggleForma.submit();
                }
            });
        }

        const obrisiForma = stavka.querySelector(".obrisi-forma");
        if (obrisiForma) {
            obrisiForma.addEventListener("submit", async (e) => {
                e.preventDefault();
                try {
                    const odgovor = await fetch(obrisiForma.action, {
                        method: "POST",
                        headers: { "X-Requested-With": "XMLHttpRequest" },
                    });
                    if (!odgovor.ok) throw new Error("brisanje nije uspelo");
                    const obrisanaBeleska = await odgovor.json();

                    stavka.classList.add("uklanja-se");
                    setTimeout(() => {
                        stavka.remove();
                        azurirajProgres();
                        primeniFiltere();
                    }, 200);

                    prikaziToast("Beleska obrisana.", {
                        naziv: "Ponisti",
                        klik: () => vratiBelesku(obrisanaBeleska),
                    });
                } catch (err) {
                    obrisiForma.submit();
                }
            });
        }
    }

    if (lista) {
        lista.querySelectorAll("li").forEach(zakaciListenereNaStavku);
    }

    primeniFiltere();
    azurirajProgres();

    // ---------- Javno deljenje: dugme "Kopiraj" ----------

    const kopirajDugme = document.getElementById("deljenje-kopiraj-dugme");
    if (kopirajDugme) {
        kopirajDugme.addEventListener("click", async () => {
            const polje = document.getElementById("deljenje-link");
            try {
                await navigator.clipboard.writeText(polje.value);
            } catch (e) {
                polje.select();
                document.execCommand("copy");
            }
            kopirajDugme.textContent = "Kopirano!";
            setTimeout(() => {
                kopirajDugme.textContent = "Kopiraj";
            }, 1500);
        });
    }

    // ---------- Board (Kanban): prevuci-i-pusti izmedju kolona ----------

    const boardRed = document.querySelector(".board-red");
    let prevucenaKartica = null;

    function zakaciListenereNaKarticu(kartica) {
        kartica.addEventListener("dragstart", () => {
            prevucenaKartica = kartica;
            kartica.classList.add("prevlaci");
        });
        kartica.addEventListener("dragend", () => {
            kartica.classList.remove("prevlaci");
            prevucenaKartica = null;
        });

        const checkbox = kartica.querySelector(".board-checkbox");
        if (checkbox) {
            checkbox.addEventListener("change", async () => {
                try {
                    const odgovor = await fetch(`/toggle/${kartica.dataset.id}`, {
                        method: "POST",
                        headers: { "X-Requested-With": "XMLHttpRequest" },
                    });
                    const podaci = await odgovor.json();
                    kartica.classList.toggle("uradjeno", podaci.uradjeno);
                } catch (e) {
                    window.location.reload();
                }
            });
        }

        const obrisiDugme = kartica.querySelector(".board-obrisi");
        if (obrisiDugme) {
            obrisiDugme.addEventListener("click", async () => {
                try {
                    await fetch(`/obrisi/${kartica.dataset.id}`, {
                        method: "POST",
                        headers: { "X-Requested-With": "XMLHttpRequest" },
                    });
                    kartica.remove();
                } catch (e) {
                    window.location.reload();
                }
            });
        }
    }

    function zakaciListenereNaKolonu(kolona) {
        kolona.addEventListener("dragover", (e) => {
            e.preventDefault();
            kolona.classList.add("preko");
        });
        kolona.addEventListener("dragleave", () => {
            kolona.classList.remove("preko");
        });
        kolona.addEventListener("drop", async (e) => {
            e.preventDefault();
            kolona.classList.remove("preko");
            if (!prevucenaKartica) return;

            const novaKategorija = kolona.dataset.kategorija;
            kolona.querySelector(".board-kartice").appendChild(prevucenaKartica);

            try {
                await fetch(`/premesti/${prevucenaKartica.dataset.id}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: JSON.stringify({ kategorija: novaKategorija }),
                });
            } catch (e) {
                window.location.reload();
            }
        });
    }

    function napraviKolonuElement(naziv) {
        const kolona = document.createElement("div");
        kolona.className = "board-kolona";
        kolona.dataset.kategorija = naziv;

        const naslovRed = document.createElement("div");
        naslovRed.className = "board-kolona-naslov";
        const naslovTekst = document.createElement("span");
        naslovTekst.textContent = naziv;
        const brojBedz = document.createElement("span");
        brojBedz.className = "board-broj-bedz";
        brojBedz.textContent = "0";
        naslovRed.appendChild(naslovTekst);
        naslovRed.appendChild(brojBedz);

        const kartice = document.createElement("div");
        kartice.className = "board-kartice";

        kolona.appendChild(naslovRed);
        kolona.appendChild(kartice);
        return kolona;
    }

    if (boardRed) {
        boardRed.querySelectorAll(".board-kartica").forEach(zakaciListenereNaKarticu);
        boardRed.querySelectorAll(".board-kolona:not(.board-kolona-nova)").forEach(zakaciListenereNaKolonu);

        const novaKolonaForma = document.getElementById("nova-kolona-forma");
        if (novaKolonaForma) {
            novaKolonaForma.addEventListener("submit", async (e) => {
                e.preventDefault();
                const unos = novaKolonaForma.querySelector("input[name=naziv]");
                const naziv = unos.value.trim();
                if (!naziv) return;

                const vecPostoji = Array.from(boardRed.querySelectorAll(".board-kolona:not(.board-kolona-nova)")).some(
                    (k) => k.dataset.kategorija.toLowerCase() === naziv.toLowerCase()
                );
                if (vecPostoji) {
                    prikaziToast("Kolona sa tim imenom vec postoji.");
                    unos.value = "";
                    return;
                }

                try {
                    const odgovor = await fetch("/board/kategorija", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-Requested-With": "XMLHttpRequest",
                        },
                        body: JSON.stringify({ naziv }),
                    });
                    const podaciOdg = await odgovor.json();
                    if (!odgovor.ok) {
                        prikaziToast(podaciOdg.greska || "Greska pri dodavanju kolone.");
                        return;
                    }

                    const kolonaNova = document.querySelector(".board-kolona-nova");
                    const novaKolona = napraviKolonuElement(podaciOdg.naziv);
                    boardRed.insertBefore(novaKolona, kolonaNova);
                    zakaciListenereNaKolonu(novaKolona);
                    unos.value = "";
                } catch (err) {
                    prikaziToast("Ne mogu da se povezem sa serverom.");
                }
            });
        }
    }

    // ---------- AI asistent (plutajuci panel) ----------

    const aiPanel = document.getElementById("ai-panel");
    const aiOtvoriDugme = document.getElementById("ai-otvori-dugme");
    const aiZatvoriDugme = document.getElementById("ai-zatvori-dugme");
    const asistentUnosZaFokus = document.getElementById("asistent-unos");

    if (aiPanel && aiOtvoriDugme) {
        aiOtvoriDugme.addEventListener("click", () => {
            aiPanel.classList.toggle("otvoren");
            if (aiPanel.classList.contains("otvoren") && asistentUnosZaFokus) {
                asistentUnosZaFokus.focus();
            }
        });
    }

    if (aiZatvoriDugme) {
        aiZatvoriDugme.addEventListener("click", () => {
            aiPanel.classList.remove("otvoren");
        });
    }

    const asistentForma = document.getElementById("asistent-forma");
    if (asistentForma) {
        const unosAsistent = document.getElementById("asistent-unos");
        const porukeAsistent = document.getElementById("asistent-poruke");
        let istorijaAsistent = [];

        function dodajPoruku(tekst, ko) {
            const poruka = document.createElement("div");
            poruka.className = `asistent-poruka asistent-poruka-${ko}`;
            const raspon = document.createElement("span");
            raspon.textContent = tekst;
            poruka.appendChild(raspon);
            porukeAsistent.appendChild(poruka);
            porukeAsistent.scrollTop = porukeAsistent.scrollHeight;
            return poruka;
        }

        asistentForma.addEventListener("submit", async (e) => {
            e.preventDefault();
            const pitanje = unosAsistent.value.trim();
            if (!pitanje) return;

            dodajPoruku(pitanje, "ja");
            unosAsistent.value = "";
            unosAsistent.disabled = true;

            const ucitavanje = dodajPoruku("Razmišljam...", "ai");
            ucitavanje.classList.add("ucitava");

            try {
                const odgovor = await fetch("/api/asistent", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: JSON.stringify({ pitanje, istorija: istorijaAsistent }),
                });
                const podaci = await odgovor.json();
                ucitavanje.remove();

                if (!odgovor.ok) {
                    dodajPoruku(podaci.greska || "Doslo je do greske.", "ai").classList.add("greska");
                } else {
                    dodajPoruku(podaci.odgovor, "ai");
                    istorijaAsistent.push({ uloga: "user", tekst: pitanje });
                    istorijaAsistent.push({ uloga: "assistant", tekst: podaci.odgovor });
                }
            } catch (err) {
                ucitavanje.remove();
                dodajPoruku("Ne mogu da se povezem sa serverom.", "ai").classList.add("greska");
            } finally {
                unosAsistent.disabled = false;
                unosAsistent.focus();
            }
        });
    }

    // ---------- Podsetnici: notifikacija kad rok beleske stigne ----------
    // Radi samo dok je tab/app otvoren (ili nedavno otvoren, dok je service
    // worker jos "ziv") - nije pravi push koji stize i kad je sajt zatvoren.

    const podsetniciDugme = document.getElementById("podsetnici-dugme");
    if (podsetniciDugme && "Notification" in window) {
        function azurirajIzgledPodsetnika() {
            const ukljuceno = localStorage.getItem("podsetnici") === "ukljuceno" && Notification.permission === "granted";
            podsetniciDugme.classList.toggle("ukljuceno", ukljuceno);
        }

        async function proveriRokove() {
            if (Notification.permission !== "granted") return;
            try {
                const odgovor = await fetch("/api/beleske");
                if (!odgovor.ok) return;
                const beleske = await odgovor.json();
                const sada = Date.now();

                let vecObavesteni = [];
                try {
                    vecObavesteni = JSON.parse(sessionStorage.getItem("obavesteni-rokovi") || "[]");
                } catch (e) {}

                for (const b of beleske) {
                    if (!b.rok || b.uradjeno) continue;
                    const vreme = new Date(b.rok).getTime();
                    if (Number.isNaN(vreme) || vreme > sada || vecObavesteni.includes(b.id)) continue;

                    const opcije = { body: b.naslov, icon: "/static/icons/icon-192.png", tag: "rok-" + b.id };
                    const reg = await navigator.serviceWorker.getRegistration();
                    if (reg) {
                        reg.showNotification("Rok je stigao", opcije);
                    } else {
                        new Notification("Rok je stigao", opcije);
                    }
                    vecObavesteni.push(b.id);
                }

                try {
                    sessionStorage.setItem("obavesteni-rokovi", JSON.stringify(vecObavesteni));
                } catch (e) {}
            } catch (e) {
                // offline ili greska - probace ponovo na sledecoj proveri
            }
        }

        podsetniciDugme.addEventListener("click", async () => {
            if (Notification.permission === "denied") {
                prikaziToast("Notifikacije su blokirane u podesavanjima browsera - omoguci ih rucno da bi podsetnici radili.");
                return;
            }
            if (Notification.permission === "default") {
                const dozvola = await Notification.requestPermission();
                if (dozvola !== "granted") {
                    azurirajIzgledPodsetnika();
                    return;
                }
            }

            const bilo_ukljuceno = localStorage.getItem("podsetnici") === "ukljuceno";
            try {
                localStorage.setItem("podsetnici", bilo_ukljuceno ? "iskljuceno" : "ukljuceno");
            } catch (e) {}
            azurirajIzgledPodsetnika();

            if (!bilo_ukljuceno) {
                prikaziToast("Podsetnici ukljuceni - proverava rokove dok je app otvorena.");
                proveriRokove();
            }
        });

        azurirajIzgledPodsetnika();
        if (localStorage.getItem("podsetnici") === "ukljuceno" && Notification.permission === "granted") {
            proveriRokove();
            setInterval(proveriRokove, 60000);
        }
    }

    // ---------- Tamna tema: izbor se pamti u localStorage (samo u ovom browseru). ----------
    const temaDugme = document.getElementById("tema-dugme");
    const koren = document.documentElement;

    try {
        const sacuvanaTema = localStorage.getItem("tema");
        if (sacuvanaTema) {
            koren.setAttribute("data-tema", sacuvanaTema);
        }
    } catch (e) {
        // localStorage moze biti nedostupan (npr. privatni mod) - nije kriticno.
    }

    if (temaDugme) {
        temaDugme.addEventListener("click", () => {
            const nova = koren.getAttribute("data-tema") === "tamna" ? "svetla" : "tamna";
            koren.setAttribute("data-tema", nova);
            try {
                localStorage.setItem("tema", nova);
            } catch (e) {
                // ignorisi ako localStorage nije dostupan
            }
        });
    }
});

// Registracija service worker-a (PWA): van DOMContentLoaded jer ne zavisi
// od DOM-a, i mora se desiti sto ranije da bi offline rezim radio.
if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").catch(() => {
            // Ako registracija ne uspe (npr. stariji browser), app i dalje radi normalno.
        });
    });
}
