"""Jeu de données fictives (aucune donnée réelle) : 4 services, 40 lits, 30 patients, 38 séjours,
8 transferts, 7 indisponibilités. Tout passe par les vraies méthodes du modèle : les règles métier
sont donc appliquées aux données de démonstration elles-mêmes."""
import random
from datetime import datetime, timedelta

from model.commun import ErreurMetier

SERVICES = [  # nom, catégorie, seuil %, préfixe des codes, nombre de lits
    ("Médecine générale", "Médecine", 75, "MG", 12),
    ("Chirurgie", "Chirurgie", 80, "CH", 10),
    ("Pédiatrie", "Pédiatrie", 85, "PE", 8),
    ("Maternité", "Obstétrique", 75, "MA", 10),
]
INDISPONIBILITES = [  # code, début (jours), fin (jours, None = sans fin), motif
    ("PE08", -6, None, "Maintenance de la climatisation"),
    ("MA10", -1, 1, "Préparation après désinfection"),
    ("CH08", -3, None, "Maintenance du système d'oxygène"),
    ("CH09", -1, 2, "Réparation du sommier"),
    ("CH10", -2, None, "Lit en attente de remplacement"),
    ("MG12", -12, -9, "Maintenance programmée"),
    ("CH07", -15, -14, "Désinfection"),
]
EN_COURS = {"MG": 6, "CH": 2, "PE": 7, "MA": 7}  # séjours en cours par service (PE : saturé)


def reinitialiser(m, maintenant=None):
    """Vide la base, recrée les tables et insère la démo. Retourne les refus d'opérations invalides."""
    m.db.creer_tables()
    now = (maintenant or datetime.now()).replace(microsecond=0)
    hasard = random.Random(2026)

    # --- services, lits, patients ---
    lits, service_de = {}, {}
    for nom, categorie, seuil, prefixe, nombre in SERVICES:
        id_service = m.services.creer(nom, categorie, seuil, f"Service fictif : {nom.lower()}")
        for i in range(1, nombre + 1):
            code = f"{prefixe}{i:02d}"
            lits[code] = m.lits.ajouter(code, id_service)
            service_de[code] = prefixe
    def service_du(code):
        return m.db.un("SELECT id_service FROM lits WHERE id_lit = %s", (lits[code],))["id_service"]

    patients = [m.sejours.creer_patient(now - timedelta(days=40)) for _ in range(30)]

    # --- périodes d'indisponibilité (ces lits ne servent pas aux séjours) ---
    for code, debut, fin, motif in INDISPONIBILITES:
        m.lits.declarer_indisponible(lits[code], now + timedelta(days=debut),
                                     None if fin is None else now + timedelta(days=fin), motif)
    utilisables = [c for c in lits if c not in {i[0] for i in INDISPONIBILITES}]

    # --- planification des séjours : on garde, pour chaque lit/patient, l'heure où il se libère ---
    libre_lit = {c: datetime.min for c in utilisables}
    libre_pat = {p: datetime.min for p in patients}
    sejours = []

    def choisir_lit(prefixes, debut):
        candidats = [c for c in utilisables if service_de[c] in prefixes and libre_lit[c] <= debut]
        return hasard.choice(candidats)

    def planifier(prefixes, debut, fin, transfert_meme_service):
        lit = choisir_lit(prefixes, debut)
        patient = hasard.choice([p for p in patients if libre_pat[p] <= debut])
        sejour = {"patient": patient, "debut": debut, "fin": fin, "lit": lit, "transfert": None}
        libre_lit[lit] = libre_pat[patient] = fin or datetime.max
        if transfert_meme_service is not None:  # transfert au milieu du séjour
            moment = debut + ((fin or now) - debut) / 2
            dest = choisir_lit(transfert_meme_service, moment)
            if dest != lit:
                sejour["transfert"] = (dest, moment)
                libre_lit[lit] = moment
                libre_lit[dest] = fin or datetime.max
        sejours.append(sejour)

    tous = {"MG", "CH", "PE", "MA"}
    for i in range(16):  # séjours terminés (il y a 26 à 12 jours), 5 avec transfert
        debut = now - timedelta(days=26) + timedelta(hours=21 * i)
        planifier(tous, debut, debut + timedelta(days=hasard.randint(1, 5), hours=hasard.randint(0, 12)),
                  tous if i % 3 == 0 else None)
    ordre = [p for p, n in EN_COURS.items() for _ in range(n)]
    hasard.shuffle(ordre)
    for i, prefixe in enumerate(ordre):  # séjours en cours (admis il y a 5 jours à maintenant)
        debut = now - timedelta(days=5) + timedelta(hours=5 * i + 1)
        planifier({prefixe}, debut, None, {prefixe} if prefixe in ("MG", "MA") and i % 6 == 0 else None)

    # --- exécution dans l'ordre chronologique, avec les vraies règles métier ---
    evenements = []
    for s in sejours:
        evenements.append((s["debut"], 0, s))
        if s["transfert"]:
            evenements.append((s["transfert"][1], 1, s))
        if s["fin"]:
            evenements.append((s["fin"], 2, s))
    for moment, genre, s in sorted(evenements, key=lambda e: e[:2]):
        if genre == 0:
            s["id"] = m.sejours.admettre(s["patient"], service_du(s["lit"]), lits[s["lit"]], moment)
        elif genre == 1:
            m.sejours.transferer(s["id"], lits[s["transfert"][0]], moment)
        else:
            m.sejours.sortir(s["id"], moment)

    # --- tentatives invalides : refusées, puis journalisées comme alertes 4 et 5 ---
    refus = []
    en_cours = [s for s in sejours if not s["fin"]]
    tentatives = [
        lambda: m.sejours.admettre(patients[0], service_du("PE08"), lits["PE08"], now),  # lit indisponible
        lambda: m.sejours.admettre(patients[1], service_du(en_cours[0]["lit"]), lits[en_cours[0]["lit"]], now),  # lit occupé
        lambda: m.sejours.sortir(en_cours[1]["id"], en_cours[1]["debut"] - timedelta(hours=2)),  # sortie avant admission
    ]
    for tentative in tentatives:
        try:
            tentative()
        except ErreurMetier as erreur:
            m.alertes.journaliser(erreur)
            refus.append(str(erreur))

    m.lits.maj_tous()
    m.alertes.actualiser()
    return refus
