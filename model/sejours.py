"""Modules 3 et 4 : patients fictifs, admissions, sorties, transferts."""
from datetime import datetime, timedelta

from model.commun import CONFLIT, INCOHERENCE, ErreurMetier
from model.lits import AFFECTATION


class Sejours:
    def __init__(self, db, lits):
        self.db = db
        self.lits = lits

    # ---------- patients ----------
    def creer_patient(self, date_creation=None):
        numero = self.db.un("SELECT COALESCE(MAX(id_patient), 0) + 1 AS n FROM patients")["n"]
        return self.db.ecrire("INSERT INTO patients (code_patient, date_creation) VALUES (%s, %s)",
                              (f"PAT-{numero:04d}", date_creation or datetime.now()))

    def lister_patients(self):
        return self.db.lire("SELECT * FROM patients ORDER BY code_patient")

    # ---------- consultation ----------
    def lister(self, statut=None):
        sql = ("SELECT s.id_sejour, p.code_patient, sv.nom AS service, "
               "(SELECT l.code_lit FROM mouvements m JOIN lits l USING (id_lit) "
               f" WHERE m.id_sejour = s.id_sejour AND m.{AFFECTATION} "
               " ORDER BY m.date_debut DESC, m.id_mouvement DESC LIMIT 1) AS lit, "
               "s.date_admission, s.date_sortie, s.statut "
               "FROM sejours s JOIN patients p USING (id_patient) JOIN services sv USING (id_service)")
        params = ()
        if statut:
            sql, params = sql + " WHERE s.statut = %s", (statut,)
        return self.db.lire(sql + " ORDER BY s.date_admission DESC", params)

    def mouvements(self, id_sejour):
        return self.db.lire(
            "SELECT m.type_mouvement, l.code_lit, m.date_debut, m.date_fin FROM mouvements m "
            "JOIN lits l USING (id_lit) WHERE m.id_sejour = %s ORDER BY m.date_debut, m.id_mouvement", (id_sejour,))

    # ---------- règles communes ----------
    @staticmethod
    def _verifier_date(date):
        if date > datetime.now() + timedelta(minutes=1):
            raise ErreurMetier("La date ne peut pas être dans le futur.")

    def _sejour_en_cours(self, id_sejour):
        """Verrouille le séjour et son affectation ouverte (lève une erreur si terminé)."""
        sejour = self.db.un("SELECT * FROM sejours WHERE id_sejour = %s FOR UPDATE", (id_sejour,))
        if not sejour:
            raise ErreurMetier("Séjour inexistant.")
        if sejour["statut"] == "Terminé":
            raise ErreurMetier("Ce séjour est déjà terminé.")
        mouvement = self.db.un(f"SELECT * FROM mouvements WHERE id_sejour = %s AND {AFFECTATION} "
                               "AND date_fin IS NULL", (id_sejour,))
        return sejour, mouvement

    # ---------- opérations (chacune est une transaction : tout ou rien) ----------
    def admettre(self, id_patient, id_service, id_lit, date_admission):
        self._verifier_date(date_admission)
        with self.db.transaction():
            if not self.db.un("SELECT 1 FROM patients WHERE id_patient = %s", (id_patient,)):
                raise ErreurMetier("Patient inexistant.")
            service = self.db.un("SELECT actif FROM services WHERE id_service = %s", (id_service,))
            if not service:
                raise ErreurMetier("Service inexistant.")
            if not service["actif"]:
                raise ErreurMetier("Service désactivé : admission impossible.")
            lit = self.db.un("SELECT id_service FROM lits WHERE id_lit = %s FOR UPDATE", (id_lit,))
            if not lit or lit["id_service"] != id_service:
                raise ErreurMetier("Ce lit n'appartient pas au service choisi.")
            self.lits.verifier_libre(id_lit, date_admission, id_service)
            if self.db.un("SELECT 1 FROM sejours WHERE id_patient = %s AND (statut = 'En cours' "
                          "OR date_sortie > %s)", (id_patient, date_admission)):
                raise ErreurMetier("Ce patient a déjà un séjour simultané.", CONFLIT, id_service)
            id_sejour = self.db.ecrire("INSERT INTO sejours (id_patient, id_service, date_admission) "
                                       "VALUES (%s, %s, %s)", (id_patient, id_service, date_admission))
            self.db.ecrire("INSERT INTO mouvements (id_sejour, id_lit, date_debut, type_mouvement) "
                           "VALUES (%s, %s, %s, 'Admission')", (id_sejour, id_lit, date_admission))
            self.lits.maj_etat(id_lit)
        return id_sejour

    def sortir(self, id_sejour, date_sortie):
        self._verifier_date(date_sortie)
        with self.db.transaction():
            sejour, mouvement = self._sejour_en_cours(id_sejour)
            if date_sortie <= sejour["date_admission"] or date_sortie <= mouvement["date_debut"]:
                raise ErreurMetier("La date de sortie doit être postérieure à l'admission (et au dernier transfert).",
                                   INCOHERENCE, sejour["id_service"])
            self.db.ecrire("UPDATE sejours SET statut = 'Terminé', date_sortie = %s WHERE id_sejour = %s",
                           (date_sortie, id_sejour))
            self.db.ecrire("UPDATE mouvements SET date_fin = %s WHERE id_mouvement = %s",
                           (date_sortie, mouvement["id_mouvement"]))
            self.db.ecrire("INSERT INTO mouvements (id_sejour, id_lit, date_debut, date_fin, type_mouvement) "
                           "VALUES (%s, %s, %s, %s, 'Sortie')", (id_sejour, mouvement["id_lit"], date_sortie, date_sortie))
            self.lits.maj_etat(mouvement["id_lit"])

    def transferer(self, id_sejour, id_lit_destination, date_transfert):
        self._verifier_date(date_transfert)
        with self.db.transaction():
            sejour, mouvement = self._sejour_en_cours(id_sejour)
            if mouvement["id_lit"] == id_lit_destination:
                raise ErreurMetier("Le lit de destination est déjà le lit actuel.")
            if date_transfert <= mouvement["date_debut"]:
                raise ErreurMetier("Le transfert doit être postérieur au début de l'affectation actuelle.", INCOHERENCE,
                                   sejour["id_service"])
            lit = self.db.un("SELECT id_service FROM lits WHERE id_lit = %s FOR UPDATE", (id_lit_destination,))
            if not lit:
                raise ErreurMetier("Lit de destination inexistant.")
            if not self.db.un("SELECT actif FROM services WHERE id_service = %s", (lit["id_service"],))["actif"]:
                raise ErreurMetier("Le service de destination est désactivé.")
            self.lits.verifier_libre(id_lit_destination, date_transfert, lit["id_service"])
            self.db.ecrire("UPDATE mouvements SET date_fin = %s WHERE id_mouvement = %s",
                           (date_transfert, mouvement["id_mouvement"]))
            self.db.ecrire("INSERT INTO mouvements (id_sejour, id_lit, date_debut, type_mouvement) "
                           "VALUES (%s, %s, %s, 'Transfert')", (id_sejour, id_lit_destination, date_transfert))
            self.db.ecrire("UPDATE sejours SET id_service = %s WHERE id_sejour = %s", (lit["id_service"], id_sejour))
            self.lits.maj_etat(mouvement["id_lit"])
            self.lits.maj_etat(id_lit_destination)
