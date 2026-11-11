"""Accès MySQL : connexion, requêtes paramétrées, transactions."""
import os
from contextlib import contextmanager

import mysql.connector

from config import CONFIG

CHEMIN_SCHEMA = os.path.join(os.path.dirname(__file__), "..", "schema.sql")


class BaseDeDonnees:
    def __init__(self, config=CONFIG):
        cfg = dict(config)
        nom = cfg.pop("database")
        self.cnx = mysql.connector.connect(**cfg, autocommit=True)
        cur = self.cnx.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{nom}` CHARACTER SET utf8mb4")
        cur.close()
        self.cnx.database = nom

    def creer_tables(self):
        """(Ré)crée toutes les tables vides à partir de schema.sql."""
        with open(CHEMIN_SCHEMA, encoding="utf-8") as f:
            lignes = [l for l in f if not l.strip().startswith("--")]
        for requete in "".join(lignes).split(";"):
            if requete.strip():
                self.ecrire(requete)

    def lire(self, sql, params=()):
        """SELECT -> liste de dictionnaires."""
        cur = self.cnx.cursor(dictionary=True)
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()

    def un(self, sql, params=()):
        """SELECT -> première ligne (ou None)."""
        lignes = self.lire(sql, params)
        return lignes[0] if lignes else None

    def ecrire(self, sql, params=()):
        """INSERT / UPDATE / DELETE -> id généré."""
        cur = self.cnx.cursor()
        try:
            cur.execute(sql, params)
            return cur.lastrowid
        finally:
            cur.close()

    @contextmanager
    def transaction(self):
        """Tout ou rien : COMMIT si le bloc réussit, ROLLBACK à la moindre exception."""
        self.cnx.start_transaction()
        try:
            yield
            self.cnx.commit()
        except BaseException:
            self.cnx.rollback()
            raise
