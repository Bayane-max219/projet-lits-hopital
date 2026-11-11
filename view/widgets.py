"""Petits composants réutilisés par toutes les pages."""
from datetime import datetime, time

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtCore import QDate, QDateTime
from PyQt5.QtWidgets import (QAbstractItemView, QDateEdit, QDateTimeEdit, QFrame, QHeaderView, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QVBoxLayout)


def texte(valeur):
    if valeur is None:
        return ""
    if isinstance(valeur, datetime):
        return valeur.strftime("%Y-%m-%d %H:%M")
    if isinstance(valeur, float):
        return f"{valeur:.1f}"
    return str(valeur)


def tableau(colonnes):
    """colonnes = [(titre, clé du dictionnaire)]"""
    t = QTableWidget(0, len(colonnes))
    t.colonnes, t.lignes = colonnes, []
    t.setHorizontalHeaderLabels([titre for titre, _ in colonnes])
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    return t


def remplir(t, lignes):
    t.lignes = lignes
    t.setRowCount(len(lignes))
    for i, ligne in enumerate(lignes):
        for j, (_, cle) in enumerate(t.colonnes):
            t.setItem(i, j, QTableWidgetItem(texte(ligne.get(cle))))


def selection(t):
    """Ligne (dictionnaire) sélectionnée dans un tableau, ou None."""
    i = t.currentRow()
    return t.lignes[i] if 0 <= i < len(t.lignes) else None


def remplir_combo(combo, elements, tout=None):
    """elements = [(texte, valeur)] ; `tout` = libellé d'un choix 'aucun filtre' (valeur None)."""
    ancienne = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    if tout:
        combo.addItem(tout, None)
    for libelle, valeur in elements:
        combo.addItem(libelle, valeur)
    i = combo.findData(ancienne)
    combo.setCurrentIndex(max(i, 0))
    combo.blockSignals(False)


def champ_date():
    champ = QDateTimeEdit(QDateTime.currentDateTime())
    champ.setCalendarPopup(True)
    champ.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
    return champ


def lire_date(champ):
    return champ.dateTime().toPyDateTime().replace(microsecond=0)


def bouton(titre, style=None):
    b = QPushButton(titre)
    if style:
        b.setProperty(style, True)
    return b


def carte(titre):
    """Carte d'indicateur : retourne (cadre, étiquette de la valeur)."""
    cadre = QFrame()
    cadre.setObjectName("carte")
    valeur = QLabel("-")
    valeur.setObjectName("carteValeur")
    legende = QLabel(titre)
    legende.setObjectName("carteTitre")
    mise_en_page = QVBoxLayout(cadre)
    mise_en_page.addWidget(valeur)
    mise_en_page.addWidget(legende)
    return cadre, valeur


def graphique():
    figure = Figure(figsize=(5, 3), facecolor="white")
    canvas = FigureCanvasQTAgg(figure)
    canvas.setMinimumHeight(230)
    return canvas, figure.add_subplot(111)


class Page(QFrame):
    """Page de base : un titre puis une pile verticale."""

    def __init__(self, titre):
        super().__init__()
        self.pile = QVBoxLayout(self)
        self.pile.setContentsMargins(22, 18, 22, 18)
        etiquette = QLabel(titre)
        etiquette.setObjectName("titrePage")
        self.pile.addWidget(etiquette)


def champ_jour(jours_avant=0):
    champ = QDateEdit(QDate.currentDate().addDays(-jours_avant))
    champ.setCalendarPopup(True)
    champ.setDisplayFormat("yyyy-MM-dd")
    return champ


def lire_periode(du, au):
    """(du, au) -> (début 00:00:00, fin 23:59:59) en datetime Python."""
    debut = datetime.combine(du.date().toPyDate(), time.min)
    return debut, datetime.combine(au.date().toPyDate(), time.max).replace(microsecond=0)
