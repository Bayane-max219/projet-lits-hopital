"""Point d'entrée : python main.py"""
import sys

from PyQt5.QtWidgets import QApplication, QMessageBox

from controller.controleur import Controleur
from model.donnees_demo import reinitialiser
from model.modele import Modele
from view.fenetre import Fenetre


def main():
    app = QApplication(sys.argv)
    try:
        modele = Modele()
        if not modele.db.un("SHOW TABLES LIKE 'services'"):  # première utilisation : on charge la démo
            reinitialiser(modele)
    except Exception as erreur:
        QMessageBox.critical(None, "MySQL", f"Connexion impossible : {erreur}\nVérifiez config.py.")
        return 1
    fenetre = Fenetre()
    fenetre.controleur = Controleur(modele, fenetre)  # on garde une référence : sinon Python le supprime
    fenetre.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
