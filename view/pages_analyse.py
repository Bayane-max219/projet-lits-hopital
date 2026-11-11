"""Pages d'analyse : tableau de bord, indicateurs, alertes, simulation."""
import matplotlib.dates as mdates
from PyQt5.QtWidgets import (QComboBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QSpinBox,
                             QTextBrowser, QVBoxLayout, QDoubleSpinBox)

from view.style import COULEURS
from view.widgets import (Page, bouton, carte, champ_jour, graphique, lire_periode, remplir, tableau)

COLONNES_ALERTES = [("Date", "date_alerte"), ("Type", "type_alerte"), ("Service", "service"),
                    ("Description", "description"), ("Règle", "regle")]


class PageTableauBord(Page):
    CARTES = ["Total des lits", "Lits occupés", "Lits disponibles", "Lits indisponibles",
              "Durée moyenne de séjour", "Admissions (période)", "Sorties (période)", "Alertes actives"]

    def __init__(self):
        super().__init__("Tableau de bord")
        self.du, self.au, self.btn = champ_jour(30), champ_jour(), bouton("Actualiser")
        filtres = QHBoxLayout()
        for w in (QLabel("Période du"), self.du, QLabel("au"), self.au, self.btn):
            filtres.addWidget(w)
        filtres.addStretch()
        grille = QGridLayout()
        self.valeurs = {}
        for i, titre in enumerate(self.CARTES):
            cadre, self.valeurs[titre] = carte(titre)
            grille.addWidget(cadre, i // 4, i % 4)
        self.canvas_barres, self.ax_barres = graphique()
        self.canvas_courbe, self.ax_courbe = graphique()
        graphiques = QHBoxLayout()
        graphiques.addWidget(self.canvas_barres)
        graphiques.addWidget(self.canvas_courbe)
        self.alertes = tableau(COLONNES_ALERTES)
        self.alertes.setMaximumHeight(150)
        self.pile.addLayout(filtres)
        self.pile.addLayout(grille)
        self.pile.addLayout(graphiques)
        self.pile.addWidget(QLabel("Alertes actives"))
        self.pile.addWidget(self.alertes)

    def periode(self):
        return lire_periode(self.du, self.au)

    def afficher(self, cartes, taux_services, serie, alertes):
        for titre, valeur in cartes.items():
            self.valeurs[titre].setText(valeur)
        remplir(self.alertes, alertes)
        # Graphique 1 : comparaison des taux d'occupation entre services
        ax = self.ax_barres
        ax.clear()
        noms = [n for n, _, _ in taux_services]
        taux = [t or 0 for _, t, _ in taux_services]
        couleurs = [COULEURS["danger"] if t is not None and t > seuil else COULEURS["principal"]
                    for _, t, seuil in taux_services]
        barres = ax.bar(noms, taux, color=couleurs)
        ax.hlines([s for _, _, s in taux_services], [i - 0.4 for i in range(len(noms))],
                  [i + 0.4 for i in range(len(noms))], color="black", linewidth=2, zorder=3, label="Seuil d'alerte")
        for barre, (_, t, _) in zip(barres, taux_services):
            ax.text(barre.get_x() + barre.get_width() / 2, barre.get_height() + 2, "N/C" if t is None else f"{t:.0f} %",
                    ha="center", fontsize=9)
        ax.set_ylim(0, 118)
        ax.set_title("Taux d'occupation par service (rouge = seuil dépassé)", fontsize=10)
        ax.tick_params(axis="x", labelsize=8)
        ax.legend(loc="upper left", fontsize=8)
        # Graphique 2 : évolution du taux global sur la période
        ax = self.ax_courbe
        ax.clear()
        ax.plot([j for j, _ in serie], [float("nan") if t is None else t for _, t in serie],
                marker="o", markersize=3, color=COULEURS["principal"])
        ax.set_ylim(0, 105)
        ax.set_title("Évolution du taux d'occupation (établissement)", fontsize=10)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(alpha=0.3)
        for canvas in (self.canvas_barres, self.canvas_courbe):
            canvas.figure.tight_layout()
            canvas.draw()


class PageIndicateurs(Page):
    def __init__(self):
        super().__init__("Indicateurs d'occupation")
        self.service, self.du, self.au = QComboBox(), champ_jour(30), champ_jour()
        self.btn = bouton("Calculer")
        filtres = QHBoxLayout()
        for w in (QLabel("Service"), self.service, QLabel("du"), self.du, QLabel("au"), self.au, self.btn):
            filtres.addWidget(w)
        filtres.addStretch()
        self.table = tableau([("Indicateur", "nom"), ("Valeur", "valeur")])
        self.depassements = tableau([("Service", "service"), ("Du", "debut"), ("Au", "fin"),
                                     ("Taux maximum (%)", "taux_max")])
        self.pile.addLayout(filtres)
        self.pile.addWidget(self.table, 3)
        self.pile.addWidget(QLabel("Périodes durant lesquelles le seuil a été dépassé"))
        self.pile.addWidget(self.depassements, 2)

    def periode(self):
        return lire_periode(self.du, self.au)

    def afficher(self, indicateurs, depassements):
        remplir(self.table, indicateurs)
        remplir(self.depassements, depassements)


class PageAlertes(Page):
    def __init__(self):
        super().__init__("Alertes et contrôles de cohérence")
        self.seuil = QSpinBox()
        self.seuil.setRange(0, 100)
        self.btn_seuil, self.btn_verifier = bouton("Enregistrer le seuil", "secondaire"), bouton("Vérifier maintenant")
        reglage = QHBoxLayout()
        for w in (QLabel("Alerte 3 : nombre de lits indisponibles toléré par service"), self.seuil, self.btn_seuil,
                  self.btn_verifier):
            reglage.addWidget(w)
        reglage.addStretch()
        self.actives = tableau(COLONNES_ALERTES)
        self.historique = tableau(COLONNES_ALERTES + [("Active", "etat")])
        self.pile.addLayout(reglage)
        self.pile.addWidget(QLabel("Alertes actives"))
        self.pile.addWidget(self.actives, 1)
        self.pile.addWidget(QLabel("Historique (alertes passées et opérations refusées)"))
        self.pile.addWidget(self.historique, 2)

    def afficher(self, actives, historique, seuil):
        remplir(self.actives, actives)
        remplir(self.historique, [dict(a, etat="Oui" if a["active"] else "Non") for a in historique])
        self.seuil.setValue(seuil)


class PageSimulation(Page):
    def __init__(self):
        super().__init__("Simulation de scénarios (lecture seule : rien n'est modifié en base)")
        self.scenario, self.service = QComboBox(), QComboBox()
        for texte, code in (("A - Augmentation des admissions", "A"), ("B - Indisponibilité de lits", "B"),
                            ("C - Réouverture de lits", "C")):
            self.scenario.addItem(texte, code)
        self.nombre, self.jours = QSpinBox(), QSpinBox()
        self.nombre.setRange(0, 1000)
        self.nombre.setValue(10)
        self.jours.setRange(1, 365)
        self.jours.setValue(30)
        self.duree = QDoubleSpinBox()
        self.duree.setRange(0, 60)
        self.duree.setSpecialValueText("automatique")
        self.btn = bouton("Simuler")
        formulaire = QGroupBox("Paramètres")
        f = QFormLayout(formulaire)
        f.addRow("Scénario", self.scenario)
        f.addRow("Service", self.service)
        f.addRow("Nombre (admissions / lits)", self.nombre)
        f.addRow("Période (jours)", self.jours)
        f.addRow("Durée moyenne séjour (A)", self.duree)
        f.addRow(self.btn)
        self.resultat = QTextBrowser()
        ligne = QHBoxLayout()
        colonne = QVBoxLayout()
        colonne.addWidget(formulaire)
        colonne.addStretch()
        ligne.addLayout(colonne, 1)
        ligne.addWidget(self.resultat, 2)
        self.pile.addLayout(ligne)

    def lire(self):
        return {"scenario": self.scenario.currentData(), "id_service": self.service.currentData(),
                "nombre": self.nombre.value(), "jours": self.jours.value(), "duree": self.duree.value() or None}

    def afficher(self, titre, parametres, lignes, alertes, notes, hypotheses):
        def liste(elements):
            return "".join(f"<li>{e}</li>" for e in elements) or "<li>Aucune</li>"

        tableau_html = "".join(f"<tr><td>{a}</td><td align='right'>{b}</td><td align='right'>{c}</td>"
                               f"<td align='right'><b>{d}</b></td></tr>" for a, b, c, d in lignes)
        self.resultat.setHtml(
            f"<h2 style='color:{COULEURS['fonce']}'>{titre}</h2>"
            f"<h3>Paramètres</h3><ul>{liste(f'{k} : {v}' for k, v in parametres.items())}</ul>"
            f"<h3>Situation initiale / simulée</h3><table cellpadding='6' border='1' style='border-collapse:collapse'>"
            f"<tr><th></th><th>Initiale</th><th>Simulée</th><th>Différence</th></tr>{tableau_html}</table>"
            f"<h3>Alertes éventuelles</h3><ul>{liste(alertes + notes)}</ul>"
            f"<h3>Hypothèses</h3><ul>{liste(hypotheses)}</ul>")
