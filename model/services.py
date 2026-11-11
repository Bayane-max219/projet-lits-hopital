"""Module 1 : services hospitaliers."""
import unicodedata

from model.commun import ErreurMetier


def normaliser(nom):
    """'  Médecine   Générale ' -> 'medecine generale'."""
    sans_accent = unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode()
    return " ".join(sans_accent.lower().split())


class Services:
    def __init__(self, db):
        self.db = db

    def _verifier(self, nom, categorie, seuil, id_service=0):
        if not nom.strip() or not categorie.strip():
            raise ErreurMetier("Le nom et la catégorie sont obligatoires.")
        if not 1 <= seuil <= 100:
            raise ErreurMetier("Le seuil d'occupation doit être compris entre 1 et 100 %.")
        doublon = self.db.un(
            "SELECT 1 FROM services WHERE nom_normalise = %s AND id_service <> %s",
            (normaliser(nom), id_service))
        if doublon:
            raise ErreurMetier("Un service portant ce nom existe déjà.")

    def creer(self, nom, categorie, seuil, description=""):
        self._verifier(nom, categorie, seuil)
        return self.db.ecrire(
            "INSERT INTO services (nom, nom_normalise, categorie, description, seuil_occupation) "
            "VALUES (%s, %s, %s, %s, %s)",
            (nom.strip(), normaliser(nom), categorie.strip(), description, seuil))

    def modifier(self, id_service, nom, categorie, seuil, description=""):
        self._verifier(nom, categorie, seuil, id_service)
        self.db.ecrire(
            "UPDATE services SET nom=%s, nom_normalise=%s, categorie=%s, description=%s, "
            "seuil_occupation=%s WHERE id_service=%s",
            (nom.strip(), normaliser(nom), categorie.strip(), description, seuil, id_service))

    def definir_actif(self, id_service, actif):
        """Désactiver = actif 0. On ne supprime jamais : l'historique reste intact."""
        self.db.ecrire("UPDATE services SET actif=%s WHERE id_service=%s", (int(actif), id_service))

    def lire(self, id_service):
        return self.db.un("SELECT * FROM services WHERE id_service=%s", (id_service,))

    def lister(self, seulement_actifs=False):
        filtre = "WHERE actif = 1" if seulement_actifs else ""
        return self.db.lire(f"SELECT * FROM services {filtre} ORDER BY nom")
