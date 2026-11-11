-- Schéma MySQL du projet "Gestion des lits hospitaliers" (dates : AAAA-MM-JJ HH:MM:SS)
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS alertes, indisponibilites, mouvements, sejours, patients, lits, services, parametres;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE services (
    id_service       INT AUTO_INCREMENT PRIMARY KEY,
    nom              VARCHAR(100) NOT NULL,
    nom_normalise    VARCHAR(100) NOT NULL UNIQUE,   -- nom sans accent/majuscule : garantit l'unicité
    categorie        VARCHAR(100) NOT NULL,
    description      TEXT NULL,
    seuil_occupation DOUBLE NOT NULL,
    actif            TINYINT NOT NULL DEFAULT 1,
    CHECK (seuil_occupation BETWEEN 1 AND 100),
    CHECK (actif IN (0, 1))
);

CREATE TABLE lits (
    id_lit                INT AUTO_INCREMENT PRIMARY KEY,
    code_lit              VARCHAR(20) NOT NULL UNIQUE,
    id_service            INT NOT NULL,
    etat                  VARCHAR(15) NOT NULL DEFAULT 'Disponible',
    motif_indisponibilite VARCHAR(200) NULL,
    description           VARCHAR(200) NULL,
    FOREIGN KEY (id_service) REFERENCES services (id_service),
    CHECK (etat IN ('Disponible', 'Occupé', 'Indisponible'))
);

CREATE TABLE patients (
    id_patient    INT AUTO_INCREMENT PRIMARY KEY,
    code_patient  VARCHAR(20) NOT NULL UNIQUE,       -- pseudonyme : aucune donnée réelle
    date_creation DATETIME NOT NULL
);

CREATE TABLE sejours (
    id_sejour        INT AUTO_INCREMENT PRIMARY KEY,
    id_patient       INT NOT NULL,
    id_service       INT NOT NULL,                   -- service actuel (mis à jour par un transfert)
    date_admission   DATETIME NOT NULL,
    date_sortie      DATETIME NULL,
    statut           VARCHAR(10) NOT NULL DEFAULT 'En cours',
    -- Colonne calculée + UNIQUE : MySQL refuse 2 séjours "En cours" pour le même patient
    patient_en_cours INT GENERATED ALWAYS AS (IF(statut = 'En cours', id_patient, NULL)) STORED UNIQUE,
    FOREIGN KEY (id_patient) REFERENCES patients (id_patient),
    FOREIGN KEY (id_service) REFERENCES services (id_service),
    CHECK (statut IN ('En cours', 'Terminé'))
);

CREATE TABLE mouvements (
    id_mouvement   INT AUTO_INCREMENT PRIMARY KEY,
    id_sejour      INT NOT NULL,
    id_lit         INT NOT NULL,
    date_debut     DATETIME NOT NULL,
    date_fin       DATETIME NULL,
    type_mouvement VARCHAR(10) NOT NULL,
    -- Colonne calculée + UNIQUE : MySQL refuse 2 affectations ouvertes sur le même lit
    lit_occupe     INT GENERATED ALWAYS AS (IF(date_fin IS NULL AND type_mouvement <> 'Sortie', id_lit, NULL)) STORED UNIQUE,
    FOREIGN KEY (id_sejour) REFERENCES sejours (id_sejour),
    FOREIGN KEY (id_lit) REFERENCES lits (id_lit),
    CHECK (type_mouvement IN ('Admission', 'Transfert', 'Sortie'))
);

CREATE TABLE indisponibilites (
    id_indisponibilite INT AUTO_INCREMENT PRIMARY KEY,
    id_lit             INT NOT NULL,
    date_debut         DATETIME NOT NULL,
    date_fin           DATETIME NULL,
    motif              VARCHAR(200) NOT NULL,
    FOREIGN KEY (id_lit) REFERENCES lits (id_lit)
);

CREATE TABLE alertes (
    id_alerte   INT AUTO_INCREMENT PRIMARY KEY,
    id_service  INT NULL,
    type_alerte VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    date_alerte DATETIME NOT NULL,
    regle       VARCHAR(200) NOT NULL,               -- règle ayant déclenché l'alerte
    active      TINYINT NOT NULL DEFAULT 0,          -- 1 = condition toujours vraie
    FOREIGN KEY (id_service) REFERENCES services (id_service)
);

-- Table ajoutée : paramètres configurables (seuil d'indisponibilité de l'alerte 3)
CREATE TABLE parametres (
    cle    VARCHAR(50) PRIMARY KEY,
    valeur VARCHAR(50) NOT NULL
);
INSERT INTO parametres VALUES ('seuil_indisponibles', '2');
