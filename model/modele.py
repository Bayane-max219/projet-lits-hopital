"""Façade du modèle : regroupe toutes les classes métier autour d'une même connexion."""
from model.alertes import Alertes
from model.db import BaseDeDonnees
from model.lits import Lits
from model.sejours import Sejours
from model.services import Services
from model.simulation import Simulation
from model.stats import Stats


class Modele:
    def __init__(self, db=None):
        self.db = db or BaseDeDonnees()
        self.services = Services(self.db)
        self.lits = Lits(self.db)
        self.sejours = Sejours(self.db, self.lits)
        self.stats = Stats(self.db, self.lits)
        self.alertes = Alertes(self.db, self.lits, self.services)
        self.simulation = Simulation(self.lits, self.services, self.stats, self.alertes)
