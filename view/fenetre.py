"""Fenêtre principale : menu latéral à gauche + pile de pages à droite."""
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout,
                             QWidget)

from view.pages_analyse import PageAlertes, PageIndicateurs, PageSimulation, PageTableauBord
from view.pages_gestion import PageLits, PageServices, PageSejours
from view.style import FEUILLE
from view.widgets import bouton


class Fenetre(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestion des lits hospitaliers (données fictives)")
        self.resize(1280, 820)
        self.setStyleSheet(FEUILLE)
        self.tableau_bord, self.services, self.lits = PageTableauBord(), PageServices(), PageLits()
        self.sejours, self.indicateurs = PageSejours(), PageIndicateurs()
        self.alertes, self.simulation = PageAlertes(), PageSimulation()
        pages = [("Tableau de bord", self.tableau_bord), ("Services", self.services), ("Lits", self.lits),
                 ("Séjours", self.sejours), ("Indicateurs", self.indicateurs), ("Alertes", self.alertes),
                 ("Simulation", self.simulation)]
        self.menu, self.pile = QListWidget(), QStackedWidget()
        self.menu.setObjectName("menu")
        for nom, page in pages:
            self.menu.addItem(nom)
            self.pile.addWidget(page)
        self.menu.currentRowChanged.connect(self.pile.setCurrentIndex)
        self.menu.setCurrentRow(0)
        titre = QLabel("Lits hospitaliers")
        titre.setObjectName("titreMenu")
        self.btn_demo = bouton("Réinitialiser la démo")
        self.btn_demo.setObjectName("btnDemo")
        gauche = QVBoxLayout()
        gauche.setSpacing(0)
        gauche.setContentsMargins(0, 0, 0, 0)
        gauche.addWidget(titre)
        gauche.addWidget(self.menu)
        gauche.addWidget(self.btn_demo)
        cote = QWidget()
        cote.setStyleSheet("background: #134e4a;")
        cote.setLayout(gauche)
        centre = QWidget()
        ligne = QHBoxLayout(centre)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(0)
        ligne.addWidget(cote)
        ligne.addWidget(self.pile, 1)
        self.setCentralWidget(centre)

    # messages (la vue affiche, le contrôleur décide)
    def info(self, message):
        self.statusBar().showMessage(message, 6000)

    def erreur(self, message):
        QMessageBox.warning(self, "Opération refusée", message)

    def confirmer(self, message):
        return QMessageBox.question(self, "Confirmation", message) == QMessageBox.Yes
