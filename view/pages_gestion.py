"""Pages de gestion : services, lits, séjours (formulaires + tableaux, aucune logique métier)."""
from PyQt5.QtCore import QDateTime
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QVBoxLayout)

from view.widgets import (Page, bouton, champ_date, lire_date, remplir, remplir_combo, selection, tableau)


class PageServices(Page):
    def __init__(self):
        super().__init__("Services hospitaliers")
        self.table = tableau([("Nom", "nom"), ("Catégorie", "categorie"), ("Seuil d'alerte", "seuil"),
                              ("Statut", "statut")])
        self.nom, self.categorie, self.description = QLineEdit(), QLineEdit(), QLineEdit()
        self.seuil = QDoubleSpinBox()
        self.seuil.setRange(1, 100)
        self.seuil.setValue(80)
        self.seuil.setSuffix(" %")
        self.btn_creer = bouton("Créer")
        self.btn_modifier = bouton("Modifier", "secondaire")
        self.btn_actif = bouton("Désactiver / Réactiver", "danger")

        formulaire = QGroupBox("Service")
        champs = QFormLayout(formulaire)
        for libelle, champ in (("Nom", self.nom), ("Catégorie", self.categorie), ("Description", self.description),
                               ("Seuil d'occupation", self.seuil)):
            champs.addRow(libelle, champ)
        colonne = QVBoxLayout()
        colonne.addWidget(formulaire)
        for b in (self.btn_creer, self.btn_modifier, self.btn_actif):
            colonne.addWidget(b)
        colonne.addStretch()
        ligne = QHBoxLayout()
        ligne.addWidget(self.table, 3)
        ligne.addLayout(colonne, 1)
        self.pile.addLayout(ligne)
        self.table.itemSelectionChanged.connect(self._remplir_formulaire)

    def _remplir_formulaire(self):
        s = selection(self.table)
        if s:
            self.nom.setText(s["nom"])
            self.categorie.setText(s["categorie"])
            self.description.setText(s["description"] or "")
            self.seuil.setValue(s["seuil_occupation"])

    def selectionne(self):
        return selection(self.table)

    def afficher(self, services):
        remplir(self.table, [dict(s, seuil=f"{s['seuil_occupation']:.0f} %",
                                  statut="Actif" if s["actif"] else "Inactif") for s in services])

    def lire(self):
        return {"nom": self.nom.text(), "categorie": self.categorie.text(),
                "seuil": self.seuil.value(), "description": self.description.text()}


class PageLits(Page):
    ETATS = ["Disponible", "Occupé", "Indisponible"]

    def __init__(self):
        super().__init__("Lits")
        self.f_service, self.f_etat, self.f_code = QComboBox(), QComboBox(), QLineEdit()
        self.f_code.setPlaceholderText("Rechercher un code…")
        remplir_combo(self.f_etat, [(e, e) for e in self.ETATS], tout="Tous les états")
        self.resume = QLabel()
        filtres = QHBoxLayout()
        for w in (self.f_service, self.f_etat, self.f_code):
            filtres.addWidget(w)
        filtres.addWidget(self.resume)
        self.table = tableau([("Code", "code_lit"), ("Service", "service"), ("État", "etat"),
                              ("Motif d'indisponibilité", "motif_indisponibilite"), ("Description", "description")])

        self.code, self.description, self.service = QLineEdit(), QLineEdit(), QComboBox()
        self.btn_ajouter, self.btn_modifier = bouton("Ajouter"), bouton("Modifier", "secondaire")
        g_lit = QGroupBox("Lit")
        f = QFormLayout(g_lit)
        f.addRow("Code", self.code)
        f.addRow("Service", self.service)
        f.addRow("Description", self.description)
        boutons = QHBoxLayout()
        boutons.addWidget(self.btn_ajouter)
        boutons.addWidget(self.btn_modifier)
        f.addRow(boutons)

        self.motif, self.debut, self.fin = QLineEdit(), champ_date(), champ_date()
        self.avec_fin = QCheckBox("Date de fin connue")
        self.fin.setEnabled(False)
        self.avec_fin.toggled.connect(self.fin.setEnabled)
        self.btn_indispo = bouton("Déclarer indisponible", "danger")
        self.btn_service = bouton("Remettre en service", "secondaire")
        g_indispo = QGroupBox("Indisponibilité du lit sélectionné")
        f2 = QFormLayout(g_indispo)
        f2.addRow("Motif", self.motif)
        f2.addRow("Début", self.debut)
        f2.addRow(self.avec_fin, self.fin)
        boutons2 = QHBoxLayout()
        boutons2.addWidget(self.btn_indispo)
        boutons2.addWidget(self.btn_service)
        f2.addRow(boutons2)

        self.historique = tableau([("Lit", "code_lit"), ("Patient", "code_patient"), ("Type", "type_mouvement"),
                                   ("Début", "date_debut"), ("Fin", "date_fin")])
        g_histo = QGroupBox("Historique des affectations du lit sélectionné")
        QVBoxLayout(g_histo).addWidget(self.historique)

        bas = QHBoxLayout()
        bas.addWidget(g_lit, 1)
        bas.addWidget(g_indispo, 1)
        bas.addWidget(g_histo, 2)
        self.pile.addLayout(filtres)
        self.pile.addWidget(self.table, 2)
        self.pile.addLayout(bas, 2)
        self.table.itemSelectionChanged.connect(self._remplir_formulaire)

    def _remplir_formulaire(self):
        lit = selection(self.table)
        if lit:
            self.code.setText(lit["code_lit"])
            self.description.setText(lit["description"] or "")

    def selectionne(self):
        return selection(self.table)

    def filtres(self):
        return self.f_service.currentData(), self.f_etat.currentData(), self.f_code.text()

    def maintenant(self):
        self.debut.setDateTime(QDateTime.currentDateTime())

    def afficher(self, lits, compte):
        remplir(self.table, lits)
        self.resume.setText(f"Disponibles : {compte['Disponible']}   Occupés : {compte['Occupé']}   "
                            f"Indisponibles : {compte['Indisponible']}")

    def lire(self):
        return {"code": self.code.text(), "id_service": self.service.currentData(),
                "description": self.description.text(), "motif": self.motif.text(),
                "debut": lire_date(self.debut), "fin": lire_date(self.fin) if self.avec_fin.isChecked() else None}


class PageSejours(Page):
    def __init__(self):
        super().__init__("Admissions, sorties et transferts")
        self.patient, self.service, self.lit, self.date_adm = QComboBox(), QComboBox(), QComboBox(), champ_date()
        self.btn_patient, self.btn_admettre = bouton("Nouveau patient fictif", "secondaire"), bouton("Admettre")
        g1 = QGroupBox("1. Admission")
        f1 = QFormLayout(g1)
        for libelle, champ in (("Patient", self.patient), ("Service", self.service), ("Lit disponible", self.lit),
                               ("Date et heure", self.date_adm)):
            f1.addRow(libelle, champ)
        ligne1 = QHBoxLayout()
        ligne1.addWidget(self.btn_patient)
        ligne1.addWidget(self.btn_admettre)
        f1.addRow(ligne1)

        self.sejour_sortie, self.date_sortie, self.btn_sortir = QComboBox(), champ_date(), bouton("Enregistrer la sortie")
        g2 = QGroupBox("2. Sortie")
        f2 = QFormLayout(g2)
        f2.addRow("Séjour en cours", self.sejour_sortie)
        f2.addRow("Date et heure", self.date_sortie)
        f2.addRow(self.btn_sortir)

        self.sejour_transfert, self.lit_dest, self.date_transfert = QComboBox(), QComboBox(), champ_date()
        self.btn_transferer = bouton("Transférer")
        g3 = QGroupBox("3. Transfert")
        f3 = QFormLayout(g3)
        f3.addRow("Séjour en cours", self.sejour_transfert)
        f3.addRow("Lit de destination", self.lit_dest)
        f3.addRow("Date et heure", self.date_transfert)
        f3.addRow(self.btn_transferer)

        gauche = QVBoxLayout()
        for g in (g1, g2, g3):
            gauche.addWidget(g)
        gauche.addStretch()

        self.table = tableau([("Patient", "code_patient"), ("Service", "service"), ("Lit", "lit"),
                              ("Admission", "date_admission"), ("Sortie", "date_sortie"), ("Statut", "statut")])
        self.mouvements = tableau([("Type", "type_mouvement"), ("Lit", "code_lit"), ("Début", "date_debut"),
                                   ("Fin", "date_fin")])
        g_mvt = QGroupBox("Mouvements du séjour sélectionné")
        QVBoxLayout(g_mvt).addWidget(self.mouvements)
        droite = QVBoxLayout()
        droite.addWidget(self.table, 3)
        droite.addWidget(g_mvt, 2)
        ligne = QHBoxLayout()
        ligne.addLayout(gauche, 1)
        ligne.addLayout(droite, 2)
        self.pile.addLayout(ligne)

    def selectionne(self):
        return selection(self.table)

    def maintenant(self):
        """Remet les dates des formulaires à l'heure actuelle."""
        for champ in (self.date_adm, self.date_sortie, self.date_transfert):
            champ.setDateTime(QDateTime.currentDateTime())

    def afficher(self, sejours):
        remplir(self.table, sejours)

    def afficher_mouvements(self, mouvements):
        remplir(self.mouvements, mouvements)

    def lire(self):
        return {"id_patient": self.patient.currentData(), "id_service": self.service.currentData(),
                "id_lit": self.lit.currentData(), "date_adm": lire_date(self.date_adm),
                "id_sejour_sortie": self.sejour_sortie.currentData(), "date_sortie": lire_date(self.date_sortie),
                "id_sejour_transfert": self.sejour_transfert.currentData(),
                "id_lit_dest": self.lit_dest.currentData(), "date_transfert": lire_date(self.date_transfert)}
