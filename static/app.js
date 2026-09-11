"use strict";

// Nombre maximal d'étoiles affichées (cohérent avec MAX_SCORE côté serveur).
const MAX_STARS = 3;

// Convertit une note numérique en chaîne d'étoiles pleines/vides.
function renderStars(score) {
    if (!score) {
        return "—";
    }
    return "★".repeat(score) + "☆".repeat(MAX_STARS - score);
}

// Met à jour l'affichage à partir d'un instantané d'état reçu du serveur.
function applyState(state) {
    document.getElementById("message").textContent = state.message || "";
    document.getElementById("etablissement").textContent = state.etablissement || "—";
    document.getElementById("uid").textContent = state.uid || "—";

    const hasWeight = state.weight_kg !== null && state.weight_kg !== undefined;
    document.getElementById("weight").textContent = hasWeight
        ? state.weight_kg.toFixed(1) + " kg"
        : "—";

    document.getElementById("score").textContent = renderStars(state.score);

    const photo = document.getElementById("photo");
    const placeholder = document.getElementById("photo-placeholder");
    if (state.photo_path) {
        photo.src = "/static/" + state.photo_path;
        photo.hidden = false;
        placeholder.hidden = true;
    } else {
        photo.hidden = true;
        placeholder.hidden = false;
    }

    // Met le bandeau en alerte si un bac présent est inconnu.
    const unknown = Boolean(state.uid) && !state.bin_known;
    document.body.classList.toggle("unknown-bin", unknown);
}

// Ouvre le flux SSE et applique chaque mise à jour poussée par le serveur.
function connectEvents() {
    const source = new EventSource("/events");
    source.onmessage = (event) => {
        try {
            applyState(JSON.parse(event.data));
        } catch (err) {
            console.error("Événement SSE illisible", err);
        }
    };
    source.onerror = () => {
        // EventSource tente une reconnexion automatique.
        document.getElementById("message").textContent = "Reconnexion…";
    };
}

// Envoie une commande de simulation (POST JSON) au serveur.
async function postJson(url, body) {
    try {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body || {}),
        });
        if (!response.ok) {
            console.error("Commande refusée", url, response.status);
        }
    } catch (err) {
        console.error("Échec de la commande", url, err);
    }
}

// Câble les boutons du panneau de simulation, s'ils sont présents dans la page.
function wireSimPanel() {
    document.querySelectorAll(".sim-present").forEach((button) => {
        button.addEventListener("click", () =>
            postJson("/sim/present", { uid: button.dataset.uid })
        );
    });
    document.querySelectorAll(".sim-score").forEach((button) => {
        button.addEventListener("click", () =>
            postJson("/sim/score", { value: Number(button.dataset.value) })
        );
    });
    const photoButton = document.getElementById("sim-photo");
    if (photoButton) {
        photoButton.addEventListener("click", () => postJson("/sim/photo"));
    }
}

document.addEventListener("DOMContentLoaded", () => {
    connectEvents();
    wireSimPanel();
});
