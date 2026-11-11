"""Éléments partagés : exception métier, types d'alertes."""

HAUTE = "Occupation élevée"
SATURATION = "Saturation"
INDISPONIBILITE = "Indisponibilité importante"
INCOHERENCE = "Incohérence de séjour"
CONFLIT = "Conflit d'affectation"


class ErreurMetier(Exception):
    """Une règle métier est violée. `type_alerte` : alerte à journaliser (facultatif)."""

    def __init__(self, message, type_alerte=None, id_service=None):
        super().__init__(message)
        self.type_alerte = type_alerte
        self.id_service = id_service
