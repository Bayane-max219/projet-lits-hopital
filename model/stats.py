"""Modules 5 et 7 : indicateurs d'occupation.

CONVENTIONS DE CALCUL (utilisées partout) :
 - on travaille en HEURES ; une journée-lit = 24 heures de présence (heures / 24) ;
 - un séjour (ou une indisponibilité) couvre [date_debut, date_fin[ ; date_fin vide = jusqu'à la fin
   de la période étudiée ;
 - lits opérationnels = lits occupés + lits disponibles (les indisponibles sont exclus du dénominateur) ;
 - dénominateur nul -> None, affiché « Non calculable » (jamais de division par zéro) ;
 - le taux d'un jour de la courbe est le taux à 12:00 ce jour-là.
"""
from datetime import datetime, timedelta

from model.lits import AFFECTATION

NON_CALCULABLE = "Non calculable"


def calculer_taux(occupes, disponibles):
    """Formule unique du taux instantané : occupés / (occupés + disponibles) x 100."""
    operationnels = occupes + disponibles
    return occupes / operationnels * 100 if operationnels > 0 else None


def formater(taux):
    return NON_CALCULABLE if taux is None else f"{taux:.1f} %"


def _actif(ligne, instant):
    return ligne["date_debut"] <= instant and (ligne["date_fin"] is None or ligne["date_fin"] > instant)


def _heures(ligne, debut, fin):
    """Heures de `ligne` comprises dans la période [debut, fin]."""
    a, b = max(ligne["date_debut"], debut), min(ligne["date_fin"] or fin, fin)
    return max(0.0, (b - a).total_seconds() / 3600)


class Stats:
    def __init__(self, db, lits):
        self.db = db
        self.lits = lits

    def _charger(self, id_service=None):
        """Lit en base les lits, les affectations et les indisponibilités (filtre service facultatif)."""
        filtre, params = ("AND l.id_service = %s", (id_service,)) if id_service else ("", ())
        lits = self.db.lire(f"SELECT id_lit FROM lits l WHERE 1 = 1 {filtre}", params)
        affectations = self.db.lire(
            "SELECT m.id_lit, m.date_debut, m.date_fin FROM mouvements m JOIN lits l USING (id_lit) "
            f"WHERE m.{AFFECTATION} {filtre}", params)
        indispos = self.db.lire(
            f"SELECT i.id_lit, i.date_debut, i.date_fin FROM indisponibilites i JOIN lits l USING (id_lit) "
            f"WHERE 1 = 1 {filtre}", params)
        return lits, affectations, indispos

    @staticmethod
    def _etat_a(instant, lits, affectations, indispos):
        occupes = {a["id_lit"] for a in affectations if _actif(a, instant)}
        indisponibles = {i["id_lit"] for i in indispos if _actif(i, instant)} - occupes
        return {"Total": len(lits), "Occupé": len(occupes), "Indisponible": len(indisponibles),
                "Disponible": len(lits) - len(occupes) - len(indisponibles)}

    # ---------- taux ----------
    def taux_instantane(self, instant=None, id_service=None):
        """Retourne (taux ou None, nombre de lits par état) à un instant donné."""
        etat = self._etat_a(instant or datetime.now(), *self._charger(id_service))
        return calculer_taux(etat["Occupé"], etat["Disponible"]), etat

    def taux_periode(self, debut, fin, id_service=None):
        lits, affectations, indispos = self._charger(id_service)
        occupees = sum(_heures(a, debut, fin) for a in affectations) / 24
        indisponibles = sum(_heures(i, debut, fin) for i in indispos) / 24
        total = len(lits) * (fin - debut).total_seconds() / 86400
        operationnelles = total - indisponibles
        return {"occupees": occupees, "operationnelles": operationnelles,
                "taux": occupees / operationnelles * 100 if operationnelles > 0 else None}

    def serie_taux(self, debut, fin, id_service=None):
        """Un point par jour : [(date, taux ou None)] pour la courbe d'évolution."""
        donnees = self._charger(id_service)
        points, jour = [], debut.replace(hour=0, minute=0, second=0)
        while jour <= fin:
            instant = min(jour + timedelta(hours=12), datetime.now())
            etat = self._etat_a(instant, *donnees)
            points.append((jour, calculer_taux(etat["Occupé"], etat["Disponible"])))
            jour += timedelta(days=1)
        return points

    def depassements_seuil(self, debut, fin, id_service=None):
        """Périodes (jours consécutifs) où le taux d'un service dépasse son seuil."""
        resultat = []
        for service in self.db.lire("SELECT * FROM services WHERE actif = 1 AND (id_service = %s OR %s IS NULL)",
                                    (id_service, id_service)):
            debut_dep, taux_max = None, 0
            points = self.serie_taux(debut, fin, service["id_service"]) + [(None, None)]  # sentinelle de fin
            precedent = None
            for jour, taux in points:
                if taux is not None and taux > service["seuil_occupation"]:
                    debut_dep = debut_dep or jour
                    taux_max = max(taux_max, taux)
                elif debut_dep:
                    resultat.append({"service": service["nom"], "debut": debut_dep, "fin": precedent,
                                     "taux_max": taux_max})
                    debut_dep, taux_max = None, 0
                precedent = jour
        return resultat

    def service_le_plus_occupe(self):
        meilleur = None
        for service in self.db.lire("SELECT id_service, nom FROM services WHERE actif = 1"):
            taux, _ = self.taux_instantane(id_service=service["id_service"])
            if taux is not None and (meilleur is None or taux > meilleur[1]):
                meilleur = (service["nom"], taux)
        return meilleur

    # ---------- autres indicateurs ----------
    def duree_moyenne_sejours(self, id_service=None):
        """Moyenne (en jours) des séjours terminés, ou None s'il n'y en a aucun."""
        sql, params = "SELECT AVG(TIMESTAMPDIFF(SECOND, date_admission, date_sortie)) AS s FROM sejours WHERE statut = 'Terminé'", ()
        if id_service:
            sql, params = sql + " AND id_service = %s", (id_service,)
        secondes = self.db.un(sql, params)["s"]
        return float(secondes) / 86400 if secondes is not None else None

    def compter_mouvements(self, type_mouvement, debut, fin, id_service=None):
        """Admissions, sorties ou transferts sur une période."""
        sql = ("SELECT COUNT(*) AS n FROM mouvements m JOIN lits l USING (id_lit) "
               "WHERE m.type_mouvement = %s AND m.date_debut BETWEEN %s AND %s")
        params = [type_mouvement, debut, fin]
        if id_service:
            sql, params = sql + " AND l.id_service = %s", params + [id_service]
        return self.db.un(sql, params)["n"]

    def heures_indisponibilite(self, debut, fin, id_service=None):
        _, _, indispos = self._charger(id_service)
        return sum(_heures(i, debut, fin) for i in indispos)

    def taux_par_service(self):
        """Pour le graphique : [(nom, taux ou None, seuil)] des services actifs."""
        lignes = []
        for s in self.db.lire("SELECT * FROM services WHERE actif = 1 ORDER BY nom"):
            taux, _ = self.taux_instantane(id_service=s["id_service"])
            lignes.append((s["nom"], taux, s["seuil_occupation"]))
        return lignes
