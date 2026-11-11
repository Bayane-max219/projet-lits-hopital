"""Module 8 : simulation de scénarios. LECTURE SEULE : aucune écriture en base."""
from model.stats import calculer_taux

# Hypothèses affichées à l'utilisateur avec chaque résultat
HYPOTHESES = [
    "On part de la situation réelle actuelle du service (lits occupés / disponibles / indisponibles).",
    "Scénario A : une admission simulée occupe un lit pendant la durée moyenne d'un séjour. Sur J jours, "
    "N admissions ajoutent en moyenne N x durée moyenne / J lits occupés. La demande au-delà de la capacité "
    "opérationnelle est « non satisfaite » (taux plafonné à 100 %).",
    "Scénario B : seuls des lits disponibles peuvent devenir indisponibles (un lit occupé ne le peut pas).",
    "Scénario C : seuls des lits indisponibles peuvent être rouverts.",
    "L'occupation réelle reste constante pendant la période. Ce n'est pas une prévision des admissions réelles.",
]


def _situation(occupes, disponibles, indisponibles):
    return {"occupes": occupes, "disponibles": disponibles, "indisponibles": indisponibles,
            "operationnels": occupes + disponibles, "taux": calculer_taux(occupes, disponibles)}


class Simulation:
    def __init__(self, lits, services, stats, alertes):
        self.lits, self.services, self.stats, self.alertes = lits, services, stats, alertes

    def simuler(self, scenario, id_service, nombre, jours=30, duree_moyenne=None):
        """scenario : 'A', 'B' ou 'C'. nombre : admissions (A), lits à fermer (B) ou à rouvrir (C)."""
        service = self.services.lire(id_service)
        c = self.lits.compter(id_service)
        occ, dispo, indispo = c["Occupé"], c["Disponible"], c["Indisponible"]
        avant = _situation(occ, dispo, indispo)
        notes = []

        if scenario == "A":
            if duree_moyenne is None:
                duree_moyenne = self.stats.duree_moyenne_sejours(id_service) or 3.0
            extra = nombre * duree_moyenne / jours
            demande = occ + extra
            occ_sim = min(demande, avant["operationnels"])
            apres = _situation(occ_sim, avant["operationnels"] - occ_sim, indispo)
            if demande > avant["operationnels"]:
                notes.append(f"Demande non satisfaite : {demande - avant['operationnels']:.1f} lit(s) manquant(s).")
            parametres = {"Admissions fictives": nombre, "Période (jours)": jours,
                          "Durée moyenne de séjour (jours)": round(duree_moyenne, 2),
                          "Lits occupés ajoutés (moyenne)": round(extra, 2)}
        elif scenario == "B":
            k = min(nombre, dispo)
            if k < nombre:
                notes.append(f"Seuls {dispo} lit(s) libre(s) peuvent être fermés (un lit occupé ne peut pas l'être).")
            apres = _situation(occ, dispo - k, indispo + k)
            parametres = {"Lits à rendre indisponibles": nombre, "Période (jours)": jours, "Lits réellement fermés": k}
        else:
            k = min(nombre, indispo)
            if k < nombre:
                notes.append(f"Seuls {indispo} lit(s) indisponible(s) peuvent être rouverts.")
            apres = _situation(occ, dispo + k, indispo - k)
            parametres = {"Lits à rouvrir": nombre, "Lits réellement rouverts": k}

        taux_apres = apres["taux"]
        alertes = [f"{t} : {d}" for t, d in
                   self.alertes.evaluer(service, apres["occupes"], apres["disponibles"], apres["indisponibles"])]
        difference = {"Capacité opérationnelle": apres["operationnels"] - avant["operationnels"],
                      "Taux d'occupation (points)": None if None in (avant["taux"], taux_apres) else taux_apres - avant["taux"]}
        return {"service": service["nom"], "scenario": scenario, "parametres": parametres, "avant": avant,
                "apres": apres, "alertes": alertes, "notes": notes, "difference": difference}
