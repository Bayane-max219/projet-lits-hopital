"""Module 2 : lits et indisponibilités."""
from datetime import datetime

from model.commun import CONFLIT, ErreurMetier

# Un mouvement "Sortie" est un simple repère (début = fin) : il n'occupe pas le lit.
AFFECTATION = "type_mouvement <> 'Sortie'"
FIN_DES_TEMPS = "9999-12-31 00:00:00"


class Lits:
    def __init__(self, db):
        self.db = db

    # ---------- gestion ----------
    def ajouter(self, code, id_service, description=""):
        code = code.strip().upper()
        if not code:
            raise ErreurMetier("Le code du lit est obligatoire.")
        if self.db.un("SELECT 1 FROM lits WHERE code_lit = %s", (code,)):
            raise ErreurMetier(f"Le code {code} existe déjà.")
        service = self.db.un("SELECT actif FROM services WHERE id_service = %s", (id_service,))
        if not service:
            raise ErreurMetier("Service inexistant.")
        if not service["actif"]:
            raise ErreurMetier("Service désactivé : impossible d'y ajouter un lit.")
        return self.db.ecrire("INSERT INTO lits (code_lit, id_service, description) VALUES (%s, %s, %s)",
                              (code, id_service, description))

    def modifier(self, id_lit, code, description=""):
        code = code.strip().upper()
        if not code:
            raise ErreurMetier("Le code du lit est obligatoire.")
        if self.db.un("SELECT 1 FROM lits WHERE code_lit = %s AND id_lit <> %s", (code, id_lit)):
            raise ErreurMetier(f"Le code {code} existe déjà.")
        self.db.ecrire("UPDATE lits SET code_lit=%s, description=%s WHERE id_lit=%s", (code, description, id_lit))

    def lister(self, id_service=None, etat=None, code=""):
        """Consulter par service / état et rechercher par code (recherche partielle)."""
        sql = "SELECT l.*, s.nom AS service FROM lits l JOIN services s USING (id_service) WHERE l.code_lit LIKE %s"
        params = [f"%{code.strip()}%"]
        if id_service:
            sql += " AND l.id_service = %s"
            params.append(id_service)
        if etat:
            sql += " AND l.etat = %s"
            params.append(etat)
        return self.db.lire(sql + " ORDER BY l.code_lit", params)

    def compter(self, id_service=None):
        """Nombre de lits par état (colonne `etat`)."""
        sql, params = "SELECT etat, COUNT(*) AS n FROM lits", ()
        if id_service:
            sql, params = sql + " WHERE id_service = %s", (id_service,)
        compte = {"Disponible": 0, "Occupé": 0, "Indisponible": 0}
        for ligne in self.db.lire(sql + " GROUP BY etat", params):
            compte[ligne["etat"]] = ligne["n"]
        compte["Total"] = sum(compte.values())
        return compte

    def historique(self, id_lit=None):
        """Historique des affectations (d'un lit, ou de tous les lits)."""
        sql = ("SELECT l.code_lit, p.code_patient, m.type_mouvement, m.date_debut, m.date_fin "
               "FROM mouvements m JOIN lits l USING (id_lit) JOIN sejours s USING (id_sejour) "
               "JOIN patients p USING (id_patient) WHERE m.type_mouvement <> 'Sortie'")
        params = ()
        if id_lit:
            sql, params = sql + " AND m.id_lit = %s", (id_lit,)
        return self.db.lire(sql + " ORDER BY m.date_debut DESC", params)

    # ---------- disponibilité ----------
    def verifier_libre(self, id_lit, instant, id_service=None):
        """Lève ErreurMetier si le lit ne peut pas recevoir un séjour à partir de `instant`."""
        if self.db.un(f"SELECT 1 FROM mouvements WHERE id_lit = %s AND {AFFECTATION} "
                      "AND (date_fin IS NULL OR date_fin > %s)", (id_lit, instant)):
            raise ErreurMetier("Lit déjà occupé : un autre séjour l'utilise.", CONFLIT, id_service)
        if self.db.un("SELECT 1 FROM indisponibilites WHERE id_lit = %s AND date_debut <= %s "
                      "AND (date_fin IS NULL OR date_fin > %s)", (id_lit, instant, instant)):
            raise ErreurMetier("Lit indisponible : il ne peut pas recevoir de patient.", CONFLIT, id_service)

    def declarer_indisponible(self, id_lit, debut, fin, motif):
        if not motif.strip():
            raise ErreurMetier("Le motif d'indisponibilité est obligatoire.")
        if fin is not None and fin <= debut:
            raise ErreurMetier("La fin de l'indisponibilité doit suivre son début.")
        with self.db.transaction():
            self.db.un("SELECT id_lit FROM lits WHERE id_lit = %s FOR UPDATE", (id_lit,))
            if self.db.un(f"SELECT 1 FROM mouvements WHERE id_lit = %s AND {AFFECTATION} "
                          "AND (date_fin IS NULL OR date_fin > %s)", (id_lit, debut)):
                raise ErreurMetier("Lit occupé : clôturez ou transférez le séjour d'abord.")
            if self.db.un("SELECT 1 FROM indisponibilites WHERE id_lit = %s AND date_debut < COALESCE(%s, %s) "
                          "AND (date_fin IS NULL OR date_fin > %s)", (id_lit, fin, FIN_DES_TEMPS, debut)):
                raise ErreurMetier("Une indisponibilité existe déjà sur cette période.")
            self.db.ecrire("INSERT INTO indisponibilites (id_lit, date_debut, date_fin, motif) "
                           "VALUES (%s, %s, %s, %s)", (id_lit, debut, fin, motif.strip()))
            self.maj_etat(id_lit)

    def remettre_en_service(self, id_lit, instant):
        """Ferme les indisponibilités en cours du lit."""
        with self.db.transaction():
            self.db.ecrire("UPDATE indisponibilites SET date_fin = %s WHERE id_lit = %s "
                           "AND date_debut < %s AND (date_fin IS NULL OR date_fin > %s)",
                           (instant, id_lit, instant, instant))
            self.maj_etat(id_lit)

    # ---------- cohérence de l'état ----------
    def maj_etat(self, id_lit, maintenant=None):
        """Recalcule `etat` depuis les séjours actifs et les indisponibilités (source de vérité)."""
        maintenant = maintenant or datetime.now()
        motif = None
        if self.db.un(f"SELECT 1 FROM mouvements WHERE id_lit = %s AND {AFFECTATION} AND date_fin IS NULL", (id_lit,)):
            etat = "Occupé"
        else:
            indispo = self.db.un("SELECT motif FROM indisponibilites WHERE id_lit = %s AND date_debut <= %s "
                                 "AND (date_fin IS NULL OR date_fin > %s)", (id_lit, maintenant, maintenant))
            etat, motif = ("Indisponible", indispo["motif"]) if indispo else ("Disponible", None)
        self.db.ecrire("UPDATE lits SET etat = %s, motif_indisponibilite = %s WHERE id_lit = %s", (etat, motif, id_lit))

    def maj_tous(self):
        for lit in self.db.lire("SELECT id_lit FROM lits"):
            self.maj_etat(lit["id_lit"])
