"""Contrôleur : reçoit les actions de l'utilisateur, valide les saisies, appelle le modèle, met à jour la vue."""
from datetime import datetime

from model import donnees_demo
from model.commun import ErreurMetier
from model.stats import NON_CALCULABLE, formater
from model.simulation import HYPOTHESES
from view.widgets import remplir, remplir_combo


def exiger(valeur, message):
    """Validation d'une saisie : refuse une valeur vide."""
    if valeur is None or valeur == "":
        raise ValueError(message)
    return valeur


def jours(valeur):
    return NON_CALCULABLE if valeur is None else f"{valeur:.1f} j"


class Controleur:
    def __init__(self, modele, vue):
        self.m, self.v = modele, vue
        self._connecter()
        self.rafraichir()

    # ---------- branchement des boutons ----------
    def _connecter(self):
        v = self.v
        v.btn_demo.clicked.connect(self.reinitialiser_demo)
        v.tableau_bord.btn.clicked.connect(self.maj_tableau_bord)
        v.services.btn_creer.clicked.connect(self.creer_service)
        v.services.btn_modifier.clicked.connect(self.modifier_service)
        v.services.btn_actif.clicked.connect(self.basculer_service)
        v.lits.btn_ajouter.clicked.connect(self.ajouter_lit)
        v.lits.btn_modifier.clicked.connect(self.modifier_lit)
        v.lits.btn_indispo.clicked.connect(self.declarer_indisponible)
        v.lits.btn_service.clicked.connect(self.remettre_en_service)
        v.lits.f_service.currentIndexChanged.connect(self.maj_lits)
        v.lits.f_etat.currentIndexChanged.connect(self.maj_lits)
        v.lits.f_code.textChanged.connect(self.maj_lits)
        v.lits.table.itemSelectionChanged.connect(self.maj_historique_lit)
        v.sejours.btn_patient.clicked.connect(self.creer_patient)
        v.sejours.btn_admettre.clicked.connect(self.admettre)
        v.sejours.btn_sortir.clicked.connect(self.sortir)
        v.sejours.btn_transferer.clicked.connect(self.transferer)
        v.sejours.service.currentIndexChanged.connect(self.maj_lits_admission)
        v.sejours.table.itemSelectionChanged.connect(self.maj_mouvements)
        v.indicateurs.btn.clicked.connect(self.calculer_indicateurs)
        v.alertes.btn_verifier.clicked.connect(self.rafraichir)
        v.alertes.btn_seuil.clicked.connect(self.enregistrer_seuil)
        v.simulation.btn.clicked.connect(self.simuler)

    def executer(self, action, succes=""):
        """Exécute une action du modèle et gère toutes les erreurs au même endroit."""
        try:
            action()
        except ErreurMetier as erreur:
            self.m.alertes.journaliser(erreur)
            self.v.erreur(str(erreur))
        except ValueError as erreur:
            self.v.erreur(str(erreur))
        except Exception as erreur:  # noqa : une erreur inattendue ne doit pas fermer l'application
            self.v.erreur(f"Erreur inattendue : {erreur}")
        else:
            if succes:
                self.v.info(succes)
            self.rafraichir()

    # ---------- actualisation de la vue ----------
    def rafraichir(self):
        m, v = self.m, self.v
        m.lits.maj_tous()
        m.alertes.actualiser()
        services = m.services.lister()
        tous = [(s["nom"], s["id_service"]) for s in services]
        actifs = [(s["nom"], s["id_service"]) for s in services if s["actif"]]
        v.services.afficher(services)
        remplir_combo(v.lits.f_service, tous, tout="Tous les services")
        remplir_combo(v.lits.service, actifs)
        remplir_combo(v.sejours.service, actifs)
        remplir_combo(v.indicateurs.service, tous, tout="Tout l'établissement")
        remplir_combo(v.simulation.service, actifs)
        self.maj_lits()
        self.maj_sejours()
        self.maj_tableau_bord()
        v.alertes.afficher(m.alertes.actives(), m.alertes.historique(), m.alertes.seuil_indisponibles())
        v.sejours.maintenant()
        v.lits.maintenant()

    def maj_lits(self):
        id_service, etat, code = self.v.lits.filtres()
        self.v.lits.afficher(self.m.lits.lister(id_service, etat, code), self.m.lits.compter(id_service))
        self.maj_historique_lit()

    def maj_historique_lit(self):
        lit = self.v.lits.selectionne()
        remplir(self.v.lits.historique, self.m.lits.historique(lit["id_lit"] if lit else None))

    def maj_sejours(self):
        m, s = self.m, self.v.sejours
        en_cours = m.sejours.lister("En cours")
        occupes = {x["code_patient"] for x in en_cours}
        remplir_combo(s.patient, [(p["code_patient"], p["id_patient"]) for p in m.sejours.lister_patients()
                                  if p["code_patient"] not in occupes])
        choix = [(f"{x['code_patient']} - lit {x['lit']} ({x['service']})", x["id_sejour"]) for x in en_cours]
        remplir_combo(s.sejour_sortie, choix)
        remplir_combo(s.sejour_transfert, choix)
        remplir_combo(s.lit_dest, [(f"{l['code_lit']} ({l['service']})", l["id_lit"])
                                   for l in m.lits.lister(etat="Disponible")])
        self.v.sejours.afficher(m.sejours.lister())
        self.maj_lits_admission()
        self.maj_mouvements()

    def maj_lits_admission(self):
        id_service = self.v.sejours.service.currentData()
        remplir_combo(self.v.sejours.lit, [(l["code_lit"], l["id_lit"])
                                           for l in self.m.lits.lister(id_service, "Disponible")])

    def maj_mouvements(self):
        sejour = self.v.sejours.selectionne()
        self.v.sejours.afficher_mouvements(self.m.sejours.mouvements(sejour["id_sejour"]) if sejour else [])

    def maj_tableau_bord(self):
        m, t = self.m, self.v.tableau_bord
        debut, fin = t.periode()
        c = m.lits.compter()
        actives = m.alertes.actives()
        cartes = {"Total des lits": c["Total"], "Lits occupés": c["Occupé"], "Lits disponibles": c["Disponible"],
                  "Lits indisponibles": c["Indisponible"],
                  "Durée moyenne de séjour": jours(m.stats.duree_moyenne_sejours()),
                  "Admissions (période)": m.stats.compter_mouvements("Admission", debut, fin),
                  "Sorties (période)": m.stats.compter_mouvements("Sortie", debut, fin),
                  "Alertes actives": len(actives)}
        t.afficher({k: str(x) for k, x in cartes.items()}, m.stats.taux_par_service(),
                   m.stats.serie_taux(debut, fin), actives)

    # ---------- services ----------
    def creer_service(self):
        d = self.v.services.lire()
        self.executer(lambda: self.m.services.creer(d["nom"], d["categorie"], d["seuil"], d["description"]),
                      "Service créé.")

    def modifier_service(self):
        d, s = self.v.services.lire(), self.v.services.selectionne()
        self.executer(lambda: self.m.services.modifier(exiger(s, "Sélectionnez un service.")["id_service"],
                                                       d["nom"], d["categorie"], d["seuil"], d["description"]),
                      "Service modifié.")

    def basculer_service(self):
        s = self.v.services.selectionne()
        if not s:
            return self.v.erreur("Sélectionnez un service.")
        if s["actif"] and not self.v.confirmer(f"Désactiver {s['nom']} ? L'historique est conservé."):
            return
        self.executer(lambda: self.m.services.definir_actif(s["id_service"], not s["actif"]), "Statut modifié.")

    # ---------- lits ----------
    def ajouter_lit(self):
        d = self.v.lits.lire()
        self.executer(lambda: self.m.lits.ajouter(d["code"], exiger(d["id_service"], "Choisissez un service."),
                                                  d["description"]), "Lit ajouté.")

    def modifier_lit(self):
        d, lit = self.v.lits.lire(), self.v.lits.selectionne()
        self.executer(lambda: self.m.lits.modifier(exiger(lit, "Sélectionnez un lit.")["id_lit"], d["code"],
                                                   d["description"]), "Lit modifié.")

    def declarer_indisponible(self):
        d, lit = self.v.lits.lire(), self.v.lits.selectionne()
        self.executer(lambda: self.m.lits.declarer_indisponible(exiger(lit, "Sélectionnez un lit.")["id_lit"],
                                                                d["debut"], d["fin"], d["motif"]),
                      "Indisponibilité enregistrée.")

    def remettre_en_service(self):
        lit = self.v.lits.selectionne()
        self.executer(lambda: self.m.lits.remettre_en_service(exiger(lit, "Sélectionnez un lit.")["id_lit"],
                                                              datetime.now()), "Lit remis en service.")

    # ---------- séjours ----------
    def creer_patient(self):
        self.executer(self.m.sejours.creer_patient, "Patient fictif créé.")

    def admettre(self):
        d = self.v.sejours.lire()
        self.executer(lambda: self.m.sejours.admettre(
            exiger(d["id_patient"], "Choisissez un patient."), exiger(d["id_service"], "Choisissez un service."),
            exiger(d["id_lit"], "Aucun lit disponible dans ce service."), d["date_adm"]), "Admission enregistrée.")

    def sortir(self):
        d = self.v.sejours.lire()
        self.executer(lambda: self.m.sejours.sortir(exiger(d["id_sejour_sortie"], "Aucun séjour en cours."),
                                                    d["date_sortie"]), "Sortie enregistrée.")

    def transferer(self):
        d = self.v.sejours.lire()
        self.executer(lambda: self.m.sejours.transferer(
            exiger(d["id_sejour_transfert"], "Aucun séjour en cours."),
            exiger(d["id_lit_dest"], "Aucun lit de destination disponible."), d["date_transfert"]),
            "Transfert enregistré.")

    # ---------- indicateurs, alertes, simulation ----------
    def calculer_indicateurs(self):
        v, st = self.v.indicateurs, self.m.stats
        id_service, (debut, fin) = v.service.currentData(), v.periode()
        taux_i, etat = st.taux_instantane(id_service=id_service)
        periode = st.taux_periode(debut, fin, id_service)
        plus_occupe = st.service_le_plus_occupe()
        valeurs = [
            ("Lits disponibles / occupés / indisponibles", f"{etat['Disponible']} / {etat['Occupé']} / {etat['Indisponible']}"),
            ("Taux d'occupation instantané (maintenant)", formater(taux_i)),
            ("Taux d'occupation sur la période", formater(periode["taux"])),
            ("Journées-lits occupées / opérationnelles", f"{periode['occupees']:.1f} / {periode['operationnelles']:.1f}"),
            ("Durée moyenne des séjours terminés", jours(st.duree_moyenne_sejours(id_service))),
            ("Admissions sur la période", st.compter_mouvements("Admission", debut, fin, id_service)),
            ("Sorties sur la période", st.compter_mouvements("Sortie", debut, fin, id_service)),
            ("Transferts sur la période", st.compter_mouvements("Transfert", debut, fin, id_service)),
            ("Heures d'indisponibilité sur la période", f"{st.heures_indisponibilite(debut, fin, id_service):.1f} h"),
            ("Service au taux d'occupation le plus élevé", f"{plus_occupe[0]} ({plus_occupe[1]:.1f} %)" if plus_occupe else NON_CALCULABLE),
        ]
        v.afficher([{"nom": n, "valeur": x} for n, x in valeurs], st.depassements_seuil(debut, fin, id_service))

    def enregistrer_seuil(self):
        self.executer(lambda: self.m.alertes.definir_seuil_indisponibles(self.v.alertes.seuil.value()),
                      "Seuil enregistré.")

    def simuler(self):
        d = self.v.simulation.lire()
        try:
            r = self.m.simulation.simuler(d["scenario"], exiger(d["id_service"], "Choisissez un service."),
                                          d["nombre"], d["jours"], d["duree"])
        except Exception as erreur:
            return self.v.erreur(str(erreur))
        a, b, diff = r["avant"], r["apres"], r["difference"]
        ecart = diff["Taux d'occupation (points)"]
        lignes = [("Lits occupés", f"{a['occupes']:.1f}", f"{b['occupes']:.1f}", f"{b['occupes'] - a['occupes']:+.1f}"),
                  ("Lits disponibles", f"{a['disponibles']:.1f}", f"{b['disponibles']:.1f}", f"{b['disponibles'] - a['disponibles']:+.1f}"),
                  ("Lits indisponibles", a["indisponibles"], b["indisponibles"], f"{b['indisponibles'] - a['indisponibles']:+d}"),
                  ("Capacité opérationnelle", f"{a['operationnels']:.1f}", f"{b['operationnels']:.1f}", f"{diff['Capacité opérationnelle']:+.1f}"),
                  ("Taux d'occupation", formater(a["taux"]), formater(b["taux"]),
                   NON_CALCULABLE if ecart is None else f"{ecart:+.1f} pts")]
        self.v.simulation.afficher(f"Scénario {r['scenario']} - {r['service']}", r["parametres"], lignes,
                                   r["alertes"], r["notes"], HYPOTHESES)

    # ---------- données de démonstration ----------
    def reinitialiser_demo(self):
        if not self.v.confirmer("Toutes les données actuelles seront remplacées par les données de démonstration."):
            return
        self.executer(lambda: donnees_demo.reinitialiser(self.m), "Données de démonstration rechargées.")
