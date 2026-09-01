document.addEventListener("DOMContentLoaded", () => {
    // Pretraga uzivo: filtrira <li> elemente dok korisnik kuca.
    // Pascal: ovo bi bila petlja koja prolazi kroz niz i proverava svaki string.
    const pretragaUnos = document.getElementById("pretraga");
    const lista = document.getElementById("lista-beleski");

    if (pretragaUnos && lista) {
        pretragaUnos.addEventListener("input", () => {
            const upit = pretragaUnos.value.trim().toLowerCase();
            lista.querySelectorAll("li").forEach((stavka) => {
                const tekst = stavka.dataset.tekst || "";
                stavka.style.display = tekst.includes(upit) ? "" : "none";
            });
        });
    }

    // Tamna tema: izbor se pamti u localStorage (samo u ovom browseru).
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
