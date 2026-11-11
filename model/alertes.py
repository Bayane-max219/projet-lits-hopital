"""Module 6 : alertes et contrôles de cohérence.

Les alertes 1, 2, 3 sont CALCULÉES à partir de l'état des lits puis enregistrées (table alertes).
Les alertes 4 et 5 sont des REFUS d'opération (ErreurMetier) que l'on journalise.
"""
from datetime import datetime

from model.commun import CONFLIT, HAUTE, INCOHERENCE, INDISPONIBILITE, SATURATION
from model.stats import calculer_taux

REGLES = {
    HAUTE: "Alerte 1 : taux d'occupation > seuil du service",
    SATURATION: "Alerte 2 : aucun lit opérationnel disponible",
    INDISPONIBILITE: "Alerte 3 : lits indisponibles > seuil configurable",
    INCOHERENCE: "Alerte 4 : date de sortie <= date d'admission",
    CONFLIT: "Alerte 5 : lit déjà affecté / indisponible",
}


class Alertes:
    def __init__(self, db, lits, services):
        self.db = db
        self.lits = lits
        self.services = services

    # ---------- paramètre configurable ----------
    def seuil_indisponibles(self):
        return int(self.db.un("SELECT valeur FROM parametres WHERE cle = 'seuil_indisponibles'")["valeur"])

    def definir_seuil_indisponibles(self, valeur):
        self.db.ecrire("UPDATE parametres SET valeur = %s WHERE cle = 'seuil_indisponibles'", (str(valeur),))

    # ---------- détection ----------
    def evaluer(self, service, occupes, disponibles, indisponibles):
        """Applique les règles 1 à 3 à des effectifs donnés (réels ou simulés). -> [(type, description)]"""
        trouvees, taux = [], calculer_taux(occupes, disponibles)
        if taux is not None and taux > service["seuil_occupation"]:
            trouvees.append((HAUTE, f"Taux {taux:.1f} % supérieur au seuil de {service['seuil_occupation']:.0f} %."))
        if occupes > 0 and disponibles == 0:
            trouvees.append((SATURATION, "Plus aucun lit opérationnel disponible."))
        if indisponibles > self.seuil_indisponibles():
            trouvees.append((INDISPONIBILITE,
                             f"{indisponibles} lits indisponibles (seuil : {self.seuil_indisponibles()})."))
        return trouvees

    def conditions(self):
        """Alertes vraies maintenant, pour chaque service actif."""
        courantes = []
        for service in self.services.lister(seulement_actifs=True):
            c = self.lits.compter(service["id_service"])
            for type_alerte, description in self.evaluer(service, c["Occupé"], c["Disponible"], c["Indisponible"]):
                courantes.append({"id_service": service["id_service"], "type_alerte": type_alerte,
                                  "description": description})
        return courantes

    def actualiser(self):
        """Synchronise la table : crée les nouvelles alertes, clôture celles qui ne sont plus vraies."""
        actives = {(a["id_service"], a["type_alerte"]): a for a in self.actives()}
        courantes = {(c["id_service"], c["type_alerte"]): c for c in self.conditions()}
        for cle, c in courantes.items():
            if cle in actives:
                self.db.ecrire("UPDATE alertes SET description = %s WHERE id_alerte = %s",
                               (c["description"], actives[cle]["id_alerte"]))
            else:
                self.db.ecrire("INSERT INTO alertes (id_service, type_alerte, description, date_alerte, regle, active) "
                               "VALUES (%s, %s, %s, %s, %s, 1)",
                               (c["id_service"], c["type_alerte"], c["description"], datetime.now(), REGLES[c["type_alerte"]]))
        for cle, a in actives.items():
            if cle not in courantes:
                self.db.ecrire("UPDATE alertes SET active = 0 WHERE id_alerte = %s", (a["id_alerte"],))

    def journaliser(self, erreur):
        """Enregistre un refus d'opération (alertes 4 et 5) dans l'historique."""
        if erreur.type_alerte:
            self.db.ecrire("INSERT INTO alertes (id_service, type_alerte, description, date_alerte, regle, active) "
                           "VALUES (%s, %s, %s, %s, %s, 0)",
                           (erreur.id_service, erreur.type_alerte, str(erreur), datetime.now(), REGLES[erreur.type_alerte]))

    # ---------- consultation ----------
    def _lire(self, filtre=""):
        return self.db.lire("SELECT a.*, s.nom AS service FROM alertes a LEFT JOIN services s USING (id_service) "
                            f"{filtre} ORDER BY a.date_alerte DESC, a.id_alerte DESC")

    def actives(self):
        return self._lire("WHERE a.active = 1")

    def historique(self):
        return self._lire()
