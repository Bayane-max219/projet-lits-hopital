"""Tests T1 à T15 du cahier des charges + quelques règles complémentaires.

Lancer (depuis projet_hopital/) :  python -m unittest -v
Utilise une base séparée `hopital_test` : la base de l'application n'est jamais touchée.
"""
import os
import unittest
from datetime import datetime, timedelta

os.environ.setdefault("DB_NAME", "hopital_test")

from model.commun import ErreurMetier  # noqa: E402
from model.modele import Modele  # noqa: E402
from model.stats import NON_CALCULABLE, formater  # noqa: E402

MAINTENANT = datetime.now().replace(microsecond=0)


def il_y_a(heures):
    return MAINTENANT - timedelta(hours=heures)


class BaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = Modele()

    def setUp(self):
        m = self.m
        m.db.creer_tables()
        self.service = m.services.creer("Médecine générale", "Médecine", 50)
        self.lits = [m.lits.ajouter(f"L{i}", self.service) for i in range(1, 4)]
        self.patients = [m.sejours.creer_patient() for _ in range(3)]

    def admettre(self, patient=0, lit=0, heures=10):
        return self.m.sejours.admettre(self.patients[patient], self.service, self.lits[lit], il_y_a(heures))

    def etat(self, lit):
        return self.m.db.un("SELECT etat FROM lits WHERE id_lit = %s", (self.lits[lit],))["etat"]


class TestServicesEtLits(BaseTest):
    def test_T1_service_valide(self):
        self.assertEqual(self.m.services.lire(self.service)["nom"], "Médecine générale")

    def test_T2_nom_deja_utilise(self):
        with self.assertRaises(ErreurMetier):
            self.m.services.creer("  MEDECINE   generale ", "Autre", 70)  # même nom normalisé

    def test_seuil_hors_limites(self):
        for seuil in (0, 101):
            with self.assertRaises(ErreurMetier):
                self.m.services.creer(f"S{seuil}", "X", seuil)

    def test_T3_code_lit_existant(self):
        with self.assertRaises(ErreurMetier):
            self.m.lits.ajouter("l1", self.service)

    def test_service_desactive_refuse_lits_et_admissions(self):
        self.m.services.definir_actif(self.service, False)
        with self.assertRaises(ErreurMetier):
            self.m.lits.ajouter("L9", self.service)
        with self.assertRaises(ErreurMetier):
            self.admettre()


class TestSejours(BaseTest):
    def test_T4_admission_lit_disponible(self):
        id_sejour = self.admettre()
        self.assertEqual(self.m.sejours.lister("En cours")[0]["id_sejour"], id_sejour)
        self.assertEqual(self.etat(0), "Occupé")

    def test_T5_admission_lit_indisponible(self):
        self.m.lits.declarer_indisponible(self.lits[0], il_y_a(20), None, "Maintenance")
        with self.assertRaises(ErreurMetier):
            self.admettre(lit=0)

    def test_T6_admission_lit_occupe(self):
        self.admettre(patient=0, lit=0)
        with self.assertRaises(ErreurMetier):
            self.admettre(patient=1, lit=0, heures=2)

    def test_patient_deja_en_sejour(self):
        self.admettre(patient=0, lit=0)
        with self.assertRaises(ErreurMetier):
            self.admettre(patient=0, lit=1, heures=2)

    def test_T7_sortie_avant_admission(self):
        id_sejour = self.admettre(heures=10)
        with self.assertRaises(ErreurMetier):
            self.m.sejours.sortir(id_sejour, il_y_a(11))
        with self.assertRaises(ErreurMetier):  # égale à l'admission : refusée aussi
            self.m.sejours.sortir(id_sejour, il_y_a(10))

    def test_T8_sortie_libere_le_lit(self):
        id_sejour = self.admettre()
        self.m.sejours.sortir(id_sejour, il_y_a(1))
        self.assertEqual(self.m.sejours.lister()[0]["statut"], "Terminé")
        self.assertEqual(self.etat(0), "Disponible")
        with self.assertRaises(ErreurMetier):  # une sortie ne se fait pas deux fois
            self.m.sejours.sortir(id_sejour, il_y_a(0))

    def test_sortie_avec_indisponibilite_en_cours(self):
        id_sejour = self.admettre(heures=10)
        self.m.db.ecrire("INSERT INTO indisponibilites (id_lit, date_debut, motif) VALUES (%s, %s, 'Nettoyage')",
                         (self.lits[0], il_y_a(2)))  # prévue pendant le séjour
        self.m.sejours.sortir(id_sejour, il_y_a(1))
        self.assertEqual(self.etat(0), "Indisponible")

    def test_lit_occupe_ne_peut_pas_etre_indisponible(self):
        self.admettre()
        with self.assertRaises(ErreurMetier):
            self.m.lits.declarer_indisponible(self.lits[0], il_y_a(1), None, "Maintenance")

    def test_T9_transfert_lit_disponible(self):
        id_sejour = self.admettre()
        self.m.sejours.transferer(id_sejour, self.lits[1], il_y_a(5))
        self.assertEqual((self.etat(0), self.etat(1)), ("Disponible", "Occupé"))
        types = [mv["type_mouvement"] for mv in self.m.sejours.mouvements(id_sejour)]
        self.assertEqual(types, ["Admission", "Transfert"])

    def test_T10_transfert_lit_occupe(self):
        id_sejour = self.admettre(patient=0, lit=0)
        self.admettre(patient=1, lit=1, heures=8)
        with self.assertRaises(ErreurMetier):
            self.m.sejours.transferer(id_sejour, self.lits[1], il_y_a(1))

    def test_T15_echec_transfert_conserve_les_donnees(self):
        id_sejour = self.admettre()
        avant = self.m.sejours.mouvements(id_sejour)
        original = self.m.lits.maj_etat
        appels = []

        def maj_qui_echoue(id_lit, *args):  # panne au milieu du transfert (après les écritures)
            appels.append(id_lit)
            if len(appels) == 2:
                raise RuntimeError("panne simulée")
            original(id_lit, *args)

        self.m.lits.maj_etat = maj_qui_echoue
        try:
            with self.assertRaises(RuntimeError):
                self.m.sejours.transferer(id_sejour, self.lits[1], il_y_a(5))
        finally:
            self.m.lits.maj_etat = original
        self.assertEqual(self.m.sejours.mouvements(id_sejour), avant)  # rien n'a changé
        self.assertEqual((self.etat(0), self.etat(1)), ("Occupé", "Disponible"))

    def test_garde_fou_mysql_double_occupation(self):
        """Même si le code Python avait un bug, MySQL refuserait 2 affectations ouvertes sur un lit."""
        self.admettre(patient=0, lit=0)
        autre = self.admettre(patient=1, lit=1)
        with self.assertRaises(Exception):
            self.m.db.ecrire("INSERT INTO mouvements (id_sejour, id_lit, date_debut, type_mouvement) "
                             "VALUES (%s, %s, %s, 'Transfert')", (autre, self.lits[0], il_y_a(1)))


class TestIndicateurs(BaseTest):
    def test_T11_base_sans_sejour(self):
        taux, etat = self.m.stats.taux_instantane()
        self.assertEqual(taux, 0.0)
        self.assertEqual(etat["Disponible"], 3)
        self.assertIsNone(self.m.stats.duree_moyenne_sejours())
        self.assertEqual(self.m.stats.taux_periode(il_y_a(48), MAINTENANT)["taux"], 0.0)

    def test_T12_aucun_lit_operationnel(self):
        for lit in self.lits:
            self.m.lits.declarer_indisponible(lit, il_y_a(5), None, "Travaux")
        taux, _ = self.m.stats.taux_instantane()
        self.assertIsNone(taux)
        self.assertEqual(formater(taux), NON_CALCULABLE)

    def test_taux_instantane_exclut_les_indisponibles(self):
        self.admettre()
        self.m.lits.declarer_indisponible(self.lits[2], il_y_a(5), None, "Travaux")
        taux, _ = self.m.stats.taux_instantane()
        self.assertAlmostEqual(taux, 50.0)  # 1 occupé / (1 occupé + 1 disponible)

    def test_taux_periode_en_journees_lits(self):
        self.admettre(heures=24)  # 1 lit occupé 24 h sur une période de 48 h, 3 lits
        res = self.m.stats.taux_periode(il_y_a(48), MAINTENANT)
        self.assertAlmostEqual(res["occupees"], 1.0)
        self.assertAlmostEqual(res["operationnelles"], 6.0)
        self.assertAlmostEqual(res["taux"], 100 / 6)

    def test_duree_moyenne(self):
        self.m.sejours.sortir(self.admettre(patient=0, lit=0, heures=48), il_y_a(24))  # 24 h
        self.m.sejours.sortir(self.admettre(patient=1, lit=1, heures=60), il_y_a(0))   # 60 h
        self.assertAlmostEqual(self.m.stats.duree_moyenne_sejours(), 42 / 24)

    def test_compteurs_de_mouvements(self):
        id_sejour = self.admettre(heures=20)
        self.m.sejours.transferer(id_sejour, self.lits[1], il_y_a(10))
        self.m.sejours.sortir(id_sejour, il_y_a(1))
        debut = il_y_a(30)
        compte = lambda t: self.m.stats.compter_mouvements(t, debut, MAINTENANT)
        self.assertEqual((compte("Admission"), compte("Transfert"), compte("Sortie")), (1, 1, 1))


class TestAlertesEtSimulation(BaseTest):
    def test_T13_depassement_du_seuil(self):
        self.admettre(patient=0, lit=0)
        self.admettre(patient=1, lit=1, heures=8)  # 2 occupés / 3 = 66 % > seuil 50 %
        self.m.alertes.actualiser()
        types = [a["type_alerte"] for a in self.m.alertes.actives()]
        self.assertIn("Occupation élevée", types)
        self.assertNotIn("Saturation", types)

    def test_saturation_puis_fin_d_alerte(self):
        ids = [self.admettre(patient=i, lit=i, heures=10 - i) for i in range(3)]
        self.m.alertes.actualiser()
        self.assertIn("Saturation", [a["type_alerte"] for a in self.m.alertes.actives()])
        self.m.sejours.sortir(ids[0], il_y_a(0))
        self.m.alertes.actualiser()
        self.assertNotIn("Saturation", [a["type_alerte"] for a in self.m.alertes.actives()])
        self.assertTrue(self.m.alertes.historique())  # l'alerte reste dans l'historique

    def test_indisponibilite_importante(self):
        self.m.alertes.definir_seuil_indisponibles(1)
        for lit in self.lits[:2]:
            self.m.lits.declarer_indisponible(lit, il_y_a(5), None, "Travaux")
        self.m.alertes.actualiser()
        self.assertIn("Indisponibilité importante", [a["type_alerte"] for a in self.m.alertes.actives()])

    def test_refus_journalise(self):
        self.admettre(patient=0, lit=0)
        try:
            self.admettre(patient=1, lit=0, heures=2)
        except ErreurMetier as e:
            self.m.alertes.journaliser(e)
        self.assertEqual(self.m.alertes.historique()[0]["type_alerte"], "Conflit d'affectation")

    def test_T14_simulation_sans_modification(self):
        self.admettre()
        tables = ("lits", "sejours", "mouvements", "indisponibilites", "alertes")
        instantane = lambda: [self.m.db.lire(f"SELECT * FROM {t}") for t in tables]
        avant = instantane()
        for scenario, n in (("A", 10), ("B", 1), ("C", 1)):
            self.m.simulation.simuler(scenario, self.service, n)
        self.assertEqual(instantane(), avant)

    def test_simulation_indisponibilite_recalcule_la_capacite(self):
        self.admettre()
        res = self.m.simulation.simuler("B", self.service, 1)
        self.assertEqual(res["avant"]["operationnels"], 3)
        self.assertEqual(res["apres"]["operationnels"], 2)
        self.assertAlmostEqual(res["apres"]["taux"], 50.0)

    def test_simulation_admissions_plafonnee(self):
        res = self.m.simulation.simuler("A", self.service, 100, jours=10, duree_moyenne=2)
        self.assertEqual(res["apres"]["taux"], 100.0)
        self.assertTrue(res["notes"])
        self.assertIn("Saturation", res["alertes"][-1] if len(res["alertes"]) == 1 else " ".join(res["alertes"]))


if __name__ == "__main__":
    unittest.main()
