# 📐 Spécification Complète de Conception & Modélisation UML — MedAssist AI V2
## Système Intelligent d'Aide au Diagnostic Dermatologique et de Télé-expertise Clinique

> **Document Académique Officiel**  
> **Diplôme visé** : Master en Informatique — Spécialité : **Génie Logiciel et Applications Avancées (GLAA)**  
> **Cadre de réalisation** : Mémoire de Fin d'Études & Projet Diplôme-Startup (Arrêté Ministériel 1275)  
> **Édition** : Version 2.2 Complète — Post-Optimisation de Résilience et de Sécurité  
> **Date de validation** : Novembre 2026  
> **Conformité** : Normes OMG UML 2.5 (Unified Modeling Language)

---

## 📑 Sommaire Général

1. [Introduction et Vision Architecturale](#1-introduction-et-vision-architecturale)
2. [Chapitre 1 : Modélisation Fonctionnelle — Diagramme des Cas d'Utilisation](#chapitre-1--modélisation-fonctionnelle--diagramme-des-cas-dutilisation)
   - 1.1 Diagramme Global des Cas d'Utilisation
   - 1.2 Identification des Acteurs et Frontières du Système
   - 1.3 Fiches Descriptives Textuelles des Cas d'Utilisation Critiques
3. [Chapitre 2 : Modélisation Structurelle — Diagramme de Classes Système](#chapitre-2--modélisation-structurelle--diagramme-de-classes-système)
   - 2.1 Diagramme de Classes du Domaine (Entités & Couche Métier)
   - 2.2 Conception Détaillée des Services Logiciels (Architecture Orientée Objet)
   - 2.3 Dictionnaire des Classes et Énumérations
4. [Chapitre 3 : Modèle Logique de Données & Persistance (ERD)](#chapitre-3--modèle-logique-de-données--persistance-erd)
   - 3.1 Diagramme Entité-Association (Relational Schema)
   - 3.2 Règles d'Intégrité, Indexation et Pseudonymisation GDPR
5. [Chapitre 4 : Modélisation Dynamique — Diagrammes de Séquence](#chapitre-4--modélisation-dynamique--diagrammes-de-séquence)
   - 4.1 Séquence 1 : Authentification Sécurisée & Passerelle Anti-Contournement
   - 4.2 Séquence 2 : Inférence Multimodale & Génération Asynchrone de Grad-CAM++
   - 4.3 Séquence 3 : Cycle Complet de Télé-expertise Clinique (GP → Spécialiste)
   - 4.4 Séquence 4 : Gouvernance des Ressources Académiques et Mises à Jour (Admin)
6. [Chapitre 5 : Modélisation des États — Diagrammes d'États-Transitions](#chapitre-5--modélisation-des-états--diagrammes-détats-transitions)
   - 5.1 Machine à États : Cycle de Vie du Compte Praticien
   - 5.2 Machine à États : Cycle de Vie d'une Demande de Télé-expertise
   - 5.3 Machine à États : Arbre de Décision du Moteur de Risque Médical
7. [Chapitre 6 : Modélisation des Processus — Diagramme d'Activité](#chapitre-6--modélisation-des-processus--diagramme-dactivité)
   - 6.1 Diagramme d'Activité Global du Processus Clinique (Lignes d'Eau / Swimlanes)
   - 6.2 Mécanisme de Résilience Zéro-Délai (Dual-Storage Fallback)
8. [Chapitre 7 : Modélisation Architecturale & Physique — Déploiement & Composants](#chapitre-7--modélisation-architecturale--physique--déploiement--composants)
   - 7.1 Diagramme des Composants Logiciels
   - 7.2 Diagramme de Déploiement Matériel et Réseau
   - 7.3 Matrice de Traçabilité Exigences-Conception

---

## 1. Introduction et Vision Architecturale

Dans le cadre d'un mémoire de Master en **Génie Logiciel et Applications Avancées (GLAA)**, la rigueur de la modélisation logicielle constitue le pont fondamental entre les exigences fonctionnelles/cliniques et l'implémentation opérationnelle.

La plateforme **MedAssist AI (V2)** a été conçue pour dépasser le cadre d'un simple démonstrateur d'apprentissage profond (MVP V1) pour devenir une **plateforme complète de télédermatologie et d'aide à la décision clinique**. Elle intègre :
- Une inférence multimodale (Image dermoscopique + Données cliniques du patient).
- Une explicabilité visuelle immédiate via les cartes d'activation Grad-CAM++.
- Un moteur d'évaluation des risques à 5 niveaux intégrant la gestion prudente de l'incertitude (`INCONCLUSIVE`).
- Un sous-système de télé-expertise reliant les médecins généralistes de première ligne aux dermatologues spécialistes.
- Une architecture sécurisée respectant le principe de minimisation des données et la pseudonymisation (RGPD / Décret exécutif algérien sur la protection des données personnelles).
- Une résilience d'infrastructure avec basculement automatique sans délai de latence (Zero-Timeout Storage Fallback).

Les sections suivantes détaillent les artefacts UML normalisés décrivant exhaustivement ce système.

---

## Chapitre 1 : Modélisation Fonctionnelle — Diagramme des Cas d'Utilisation

### 1.1 Diagramme Global des Cas d'Utilisation

Le diagramme ci-après formalise les interactions entre les quatre acteurs du système et les fonctionnalités regroupées par paquetages fonctionnels.

```mermaid
flowchart LR
    %% Acteurs
    subgraph Acteurs ["Acteurs du Système"]
        direction TB
        GP["🩺 Médecin Généraliste<br/>(Frontline Doctor)"]
        SPEC["👨‍⚕️ Médecin Spécialiste<br/>(Dermatologist)"]
        ADMIN["👑 Administrateur Système<br/>(Super Admin)"]
        PATIENT["👤 Patient / Citoyen<br/>(Guest / Follow-up)"]
    end

    %% Relations d'héritage d'acteurs
    SPEC -- "Hérite des privilèges de" --> GP

    %% Paquetage Diagnostic & Inférence
    subgraph Pkg_Diag ["Paquetage 1 : Inférence & Diagnostic Clinique"]
        UC_Predict(["Soumettre une lésion pour analyse IA"])
        UC_GradCAM(["Consulter la carte d'explicabilité Grad-CAM++"])
        UC_Feedback(["Soumettre la concordance diagnostique / Biopsie"])
        UC_PDF(["Générer le rapport médical sécurisé avec QR code"])
        UC_Timeline(["Consulter l'évolution temporelle de la lésion"])
    end

    %% Paquetage Télé-expertise
    subgraph Pkg_Referral ["Paquetage 2 : Télé-expertise & Collaboration"]
        UC_CreateRef(["Créer une demande de télé-expertise"])
        UC_InboxRef(["Consulter la boîte de réception des avis"])
        UC_RespondRef(["Émettre un avis spécialisé & conduite à tenir"])
    end

    %% Paquetage Gestion Patients & Dossiers
    subgraph Pkg_Patient ["Paquetage 3 : Dossiers Patients Pseudonymisés"]
        UC_CreatePat(["Créer un identifiant patient anonymisé"])
        UC_SearchPat(["Consulter la liste et l'historique des patients"])
    end

    %% Paquetage Gouvernance & Administration
    subgraph Pkg_Admin ["Paquetage 4 : Administration & Gouvernance"]
        UC_VerifyDoctor(["Vérifier et approuver un compte médecin"])
        UC_ResetPwd(["Réinitialiser un mot de passe praticien"])
        UC_AuditLogs(["Consulter les pistes d'audit de sécurité"])
        UC_ManageRes(["Gérer les ressources officielles (Thèses EN/FR, APK)"])
        UC_Analytics(["Analyser la métrique de performance IA et santé"])
    end

    %% Paquetage Citoyen & Suivi
    subgraph Pkg_Public ["Paquetage 5 : Sensibilisation & Suivi Citoyen"]
        UC_LearnABCDE(["Consulter le guide interactif ABCDE"])
        UC_DirDocs(["Consulter l'annuaire des médecins agréés"])
        UC_QRFollow(["Consulter le suivi médical via QR code temporaire"])
    end

    %% Paquetage Authentification
    subgraph Pkg_Auth ["Paquetage Transversal : Sécurité & Accès"]
        UC_Login(["S'authentifier (JWT Access/Refresh)"])
        UC_Register(["Demander la création d'un compte praticien"])
        UC_ChangePwd(["Mettre à jour son mot de passe"])
    end

    %% Connexions Acteurs -> Cas d'utilisation
    GP --> UC_Login
    GP --> UC_Register
    GP --> UC_ChangePwd
    GP --> UC_Predict
    GP --> UC_Feedback
    GP --> UC_PDF
    GP --> UC_Timeline
    GP --> UC_CreatePat
    GP --> UC_SearchPat
    GP --> UC_CreateRef

    SPEC --> UC_InboxRef
    SPEC --> UC_RespondRef

    ADMIN --> UC_Login
    ADMIN --> UC_VerifyDoctor
    ADMIN --> UC_ResetPwd
    ADMIN --> UC_AuditLogs
    ADMIN --> UC_ManageRes
    ADMIN --> UC_Analytics

    PATIENT --> UC_LearnABCDE
    PATIENT --> UC_DirDocs
    PATIENT --> UC_QRFollow

    %% Inclusions et extensions
    UC_Predict -. "<<include>>" .-> UC_Login
    UC_Predict -. "<<include>>" .-> UC_GradCAM
    UC_CreateRef -. "<<extend>>" .-> UC_Predict
    UC_PDF -. "<<extend>>" .-> UC_Predict
    UC_RespondRef -. "<<include>>" .-> UC_InboxRef
```

---

### 1.2 Identification des Acteurs et Frontières du Système

| Acteur UML | Stéréotype | Description du Rôle et Périmètre |
| :--- | :--- | :--- |
| **Médecin Généraliste (`GP`)** | `<<Human Actor>>` | Praticien de santé de première ligne (polycliniques, centres de santé ruraux ou urbains). Il crée des dossiers anonymisés, effectue l'acquisition d'images dermoscopiques, lance l'inférence assistée par IA, interprète la stratification du risque, et sollicite une télé-expertise si nécessaire. |
| **Médecin Spécialiste (`Specialist`)** | `<<Human Actor>>` | Dermatologue hospitalier ou libéral certifié. Il hérite de l'ensemble des cas d'utilisation du médecin généraliste et dispose de prérogatives avancées : examen des lésions complexes dans sa boîte de réception dédiée, validation ou correction du diagnostic IA, et prescription d'actes d'exérèse/biopsie. |
| **Administrateur Système (`Admin`)** | `<<Human Actor>>` | Responsable de l'exploitation, de la gouvernance de la plateforme et de la sécurité. Il valide l'identité ordinale des médecins, gère le cycle de vie des accès, audite les journaux d'activité et téléverse les versions révisées des artefacts académiques (Mémorandums EN/FR) et applicatifs (APK). |
| **Patient / Citoyen (`Patient`)** | `<<Human Actor>>` | Bénéficiaire final des soins. Il interagit avec le système de manière strictement encadrée : consultation des ressources éducatives (règle ABCDE), géolocalisation des praticiens agréés, et accès restreint en lecture seule à ses consignes post-consultation via un jeton chiffré QR code éphémère (sans compte permanent). |

---

### 1.3 Fiches Descriptives Textuelles des Cas d'Utilisation Critiques

#### CU-01 : Soumettre une lésion pour analyse IA et évaluation multimodale du risque
- **Acteur Principal** : Médecin Généraliste / Médecin Spécialiste
- **Préconditions** : Le praticien est authentifié avec un jeton JWT valide et son compte présente le statut `active`.
- **Postconditions** : Un enregistrement d'analyse (`AnalysisRecord`) est persisté dans PostgreSQL, l'image dermoscopique est sauvegardée (sur MinIO ou stockage local résilient), une tâche d'arrière-plan Grad-CAM++ est ordonnancée, et le résultat clinique est restitué en moins de 250 ms.
- **Scénario Nominal (Succès)** :
  1. Le praticien téléverse une photographie macro/dermoscopique de la lésion cutanée.
  2. Le praticien renseigne les paramètres cliniques du patient (âge calculé, sexe biologique, localisation anatomique, diamètre maximal, élévation, saignement, évolution récente, antécédents familiaux).
  3. Le système vérifie la validité des formats (MIME-Type, intégrité d'image).
  4. Le système sauvegarde le fichier original avec un identifiant unique (UUID).
  5. Le service de prétraitement standardise le tenseur d'image ($224 \times 224$ normalisé ImageNet) et encode le vecteur de métadonnées cliniques.
  6. Le modèle PyTorch exécute une inférence multimodale avec augmentation au moment du test (TTA x8).
  7. Le moteur de risque (`RiskEngine`) applique la règle de sécurité clinique :
     - Si la probabilité maximale est inférieure au seuil de certitude ($< 50\%$), le niveau de risque est qualifié d'`INCONCLUSIVE` avec recommandation impérative de télé-expertise.
     - Sinon, le risque est catégorisé selon l'arbre oncologique (`LOW`, `MODERATE`, `HIGH`, `CRITICAL`).
  8. L'enregistrement complet est sauvegardé dans la base relationnelle.
  9. Le système déclenche une tâche d'arrière-plan asynchrone (`FastAPI BackgroundTasks`) pour calculer la matrice d'activation Grad-CAM++.
  10. Le système renvoie la charge utile JSON complète au tableau de bord.
- **Scénarios Alternatifs & Exceptions** :
  - *Exception 1 (Indisponibilité du stockage MinIO)* : Le sous-système de résilience détecte l'échec de la sonde TCP (< 150 ms) et bascule instantanément sur le système de fichiers local (`uploads/analyses/`). La transaction continue sans délai.
  - *Exception 2 (Jeton JWT expiré ou absent)* : Le filtre de sécurité intercepte la requête, rejette l'accès (HTTP 401 Unauthorized), et la passerelle frontend redirige l'utilisateur vers `login.html`.

#### CU-02 : Initier et traiter une demande de télé-expertise (Clinical Referral)
- **Acteur Principal** : Médecin Généraliste (Émetteur), Médecin Spécialiste (Destinataire)
- **Préconditions** : Une analyse a été réalisée et classée avec un statut nécessitant un avis second (`HIGH`, `CRITICAL` ou `INCONCLUSIVE`).
- **Postconditions** : L'enregistrement `referrals` passe à l'état `COMPLETED` et la rétroaction diagnostique est scellée pour l'apprentissage actif.
- **Scénario Nominal** :
  1. Le médecin généraliste clique sur "Demander une télé-expertise" depuis le dossier d'analyse.
  2. Le praticien sélectionne un spécialiste ou diffuse la demande à la communauté des dermatologues de la wilaya avec une note clinique de transmission.
  3. L'enregistrement `referrals` est créé avec le statut `PENDING`.
  4. Le spécialiste se connecte à son tableau de bord et consulte sa boîte d'avis en attente.
  5. Le spécialiste examine la lésion haute résolution, la superposition thermique Grad-CAM++, et les données d'anamnèse.
  6. Le spécialiste formule ses conclusions médicales, sélectionne la pathologie retenue et indique si une biopsie/exérèse d'urgence est requise.
  7. L'enregistrement est mis à jour : statut `COMPLETED`, horodatage scellé (`responded_at`).
  8. Le médecin généraliste reçoit l'avis d'expertise et valide la concordance médicale.

---

## Chapitre 2 : Modélisation Structurelle — Diagramme de Classes Système

### 2.1 Diagramme de Classes du Domaine (Entités & Couche Métier)

Le diagramme ci-après décrit les entités de persistance du domaine, leurs relations de cardinalité, ainsi que les classes de services de l'architecture applicative.

```mermaid
classDiagram
    %% Énumérations
    class UserRole {
        <<enumeration>>
        DOCTOR
        ADMIN
    }

    class UserStatus {
        <<enumeration>>
        PENDING_VERIFICATION
        ACTIVE
        SUSPENDED
    }

    class DoctorType {
        <<enumeration>>
        GENERAL_PRACTITIONER
        SPECIALIST_DERMATOLOGIST
    }

    class PatientSex {
        <<enumeration>>
        MALE
        FEMALE
    }

    class ReferralStatus {
        <<enumeration>>
        PENDING
        ACCEPTED
        COMPLETED
        CANCELLED
    }

    class RiskLevel {
        <<enumeration>>
        LOW
        MODERATE
        HIGH
        CRITICAL
        INCONCLUSIVE
    }

    %% Entités du Domaine
    class User {
        +UUID id
        +String email
        +String password_hash
        +UserRole role
        +UserStatus status
        +Boolean must_change_password
        +DateTime created_at
        +DateTime last_login
        +verify_password(plain_pwd) bool
        +update_last_login() void
    }

    class DoctorProfile {
        +UUID id
        +UUID user_id
        +String full_name
        +DoctorType doctor_type
        +String specialization
        +String license_number
        +String institution_name
        +String phone
        +String wilaya
        +String avatar_url
        +DateTime updated_at
        +is_specialist() bool
    }

    class Patient {
        +UUID id
        +UUID created_by_doctor_id
        +String patient_code
        +Integer birth_year
        +PatientSex sex
        +String notes
        +DateTime created_at
        +DateTime deleted_at
        +calculate_age(current_year) int
        +is_active() bool
    }

    class AnalysisRecord {
        +UUID id
        +UUID doctor_id
        +UUID patient_id
        +String lesion_tag
        +String image_storage_key
        +String gradcam_storage_key
        +JSONB clinical_data
        +String predicted_class
        +Float confidence
        +JSONB all_probabilities
        +String risk_level
        +Boolean risk_escalated
        +JSONB recommendations
        +Float inference_time_ms
        +String model_version
        +Boolean doctor_confirmed
        +String doctor_diagnosis
        +Boolean biopsy_performed
        +String biopsy_result
        +Date next_followup_date
        +DateTime created_at
        +has_gradcam() bool
        +is_high_risk() bool
    }

    class Referral {
        +UUID id
        +UUID analysis_id
        +UUID referring_doctor_id
        +UUID specialist_id
        +ReferralStatus status
        +Text referral_note
        +Text specialist_response
        +DateTime created_at
        +DateTime responded_at
        +mark_as_completed(response) void
    }

    class RefreshToken {
        +UUID id
        +UUID user_id
        +String token_hash
        +DateTime expires_at
        +Boolean is_revoked
        +DateTime created_at
        +is_valid() bool
    }

    class AuditLog {
        +UUID id
        +UUID user_id
        +String action
        +String resource_type
        +UUID resource_id
        +JSONB details
        +String ip_address
        +DateTime created_at
    }

    %% Couche Service & Moteurs Métier
    class ModelService {
        -torch.nn.Module model
        -String device
        +predict(image_bytes, metadata) ModelOutput
        +extract_features(image_tensor) Tensor
    }

    class GradCAMService {
        -torch.nn.Module model
        +generate_heatmap(image_tensor, class_idx) ndarray
        +overlay_heatmap(img_bytes, heatmap) bytes
    }

    class RiskEngine {
        +assess_risk(predicted_class, confidence, clinical_data) RiskResult
        -check_safety_inconclusive(confidence) bool
        -determine_urgency(risk_level) String
    }

    class StorageService {
        -MinioClient minio_client
        -String upload_dir
        -Boolean minio_available
        +is_minio_reachable() bool
        +upload_image(file_bytes, filename) String
        +get_image_url(storage_key) String
    }

    class PDFReportService {
        +generate_clinical_report(analysis_id) bytes
        -embed_qr_code(canvas, payload_url) void
    }

    %% Relations entre Entités
    User "1" *-- "1" DoctorProfile : possède
    User "1" o-- "0..*" Patient : enregistre
    User "1" o-- "0..*" AnalysisRecord : réalise
    User "1" *-- "0..*" RefreshToken : détient
    User "1" o-- "0..*" AuditLog : déclenche
    Patient "1" o-- "0..*" AnalysisRecord : regroupe
    AnalysisRecord "1" o-- "0..1" Referral : fait l'objet de
    User "1" o-- "0..*" Referral : émet (GP)
    User "1" o-- "0..*" Referral : reçoit (Spécialiste)

    %% Dépendances Services -> Entités
    ModelService ..> AnalysisRecord : alimente
    RiskEngine ..> AnalysisRecord : évalue
    GradCAMService ..> AnalysisRecord : enrichit
    StorageService ..> AnalysisRecord : archive
    PDFReportService ..> AnalysisRecord : synthétise
```

---

### 2.2 Conception Détaillée des Services Logiciels (Architecture Orientée Objet)

L'architecture backend repose sur une séparation stricte des responsabilités (Single Responsibility Principle) :
1. **`ModelService`** : Encapsule le modèle multimodal PyTorch combinant un backbone de vision convolutionnel (EfficientNet-B3 + GeM Pooling + MLP + Gated Cross-Attention Fusion adapté aux 6 classes cutanées ISIC : `MEL`, `BCC`, `SCC`, `ACK`, `NEV`, `SEK`) et un perceptron multicouche (MLP) traitant les 7 variables anamnestiques. L'inférence est exécutée dans un threadpool séparé (`run_in_threadpool`) pour ne jamais bloquer la boucle d'événements asynchrone de FastAPI.
2. **`GradCAMService`** : Implémente l'algorithme Grad-CAM++ qui calcule la moyenne pondérée des gradients positifs du niveau convolutif final. Il s'exécute en arrière-plan asynchrone sans altérer la latence du point de terminaison d'inférence.
3. **`RiskEngine`** : Module déterministe appliquant les règles de sécurité clinique établies par les consensus de dermatologie oncologique. Il intègre le mode `INCONCLUSIVE` lorsque la certitude خوارزمية chute sous les $50\%$.
4. **`StorageService`** : Façade d'accès au stockage persistant implémentant le patron de conception **Stratégie avec repli dynamique (Graceful Fallback)**. Une sonde réseau non bloquante par socket TCP (délai de 150 ms) interroge le démon MinIO : si le service S3 est opérationnel, l'image y est envoyée ; dans le cas contraire, elle est instantanément écrite sur le disque local sécurisé sans aucun gel de thread.
5. **`PDFReportService`** : Moteur de rendu documentaire médical sous ReportLab générant des comptes-rendus conformes aux normes hospitalières, intégrant le tracé d'analyse, l'anamnèse, les visualisations et un QR code d'accès sécurisé à validité limitée.

---

## Chapitre 3 : Modèle Logique de Données & Persistance (ERD)

### 3.1 Diagramme Entité-Association (Relational Schema)

```mermaid
erDiagram
    users {
        uuid id PK "Identifiant unique UUID v4"
        varchar email UK "Adresse électronique professionnelle"
        varchar password_hash "Empreinte bcrypt sécurisée"
        user_role role "doctor | admin"
        user_status status "pending_verification | active | suspended"
        boolean must_change_password "Indicateur de renouvellement forcé"
        timestamp created_at "Horodatage de création"
        timestamp last_login "Dernière connexion enregistrée"
    }

    doctor_profiles {
        uuid id PK "Identifiant de profil UUID"
        uuid user_id FK "Lien 1:1 vers users.id (CASCADE)"
        varchar full_name "Nom et prénom du praticien"
        doctor_type doctor_type "general_practitioner | specialist_dermatologist"
        varchar specialization "Spécialité médicale déclarée"
        varchar license_number UK "Numéro d'inscription à l'Ordre"
        varchar institution_name "Établissement de santé d'attache"
        varchar phone "Numéro de contact professionnel"
        varchar wilaya "Code Wilaya (01 à 58)"
        varchar avatar_url "Chemin de la photo de profil"
        timestamp updated_at "Dernière mise à jour du profil"
    }

    patients {
        uuid id PK "Identifiant interne UUID"
        uuid created_by_doctor_id FK "Médecin créateur (RESTRICT)"
        varchar patient_code UK "Identifiant pseudonymisé (DZ-XX-PXXXX)"
        integer birth_year "Année de naissance"
        patient_sex sex "male | female"
        text notes "Observations cliniques générales"
        timestamp created_at "Date d'enregistrement"
        timestamp deleted_at "Marqueur de suppression logique (Soft Delete)"
    }

    analysis_records {
        uuid id PK "Identifiant unique de l'analyse"
        uuid doctor_id FK "Médecin ayant réalisé l'examen (RESTRICT)"
        uuid patient_id FK "Patient associé (SET NULL)"
        varchar lesion_tag "Étiquette topologique (ex: Épaule droite - L1)"
        varchar image_storage_key "URI de l'image (MinIO ou Local)"
        varchar gradcam_storage_key "URI de la carte d'activation Grad-CAM"
        jsonb clinical_data "Paramètres anamnestiques (âge, diamètre, ABCDE)"
        varchar predicted_class "Pathologie prédite (MEL, BCC, etc.)"
        float confidence "Score de confiance (0.00 à 1.00)"
        jsonb all_probabilities "Vecteur des 6 probabilités de classe"
        varchar risk_level "LOW | MODERATE | HIGH | CRITICAL | INCONCLUSIVE"
        boolean risk_escalated "Indicateur de montée d'alerte de sécurité"
        jsonb recommendations "Conduites à tenir recommandées"
        float inference_time_ms "Durée d'inférence en millisecondes"
        varchar model_version "Version du modèle (ex: V6.0)"
        boolean doctor_confirmed "Validation clinique du praticien"
        varchar doctor_diagnosis "Diagnostic clinique définitif"
        boolean biopsy_performed "Confirmation de biopsie réalisée"
        varchar biopsy_result "Résultat anatomopathologique"
        date next_followup_date "Date de contrôle ultérieur préconisée"
        timestamp created_at "Horodatage de l'inférence"
    }

    referrals {
        uuid id PK "Identifiant de la télé-expertise"
        uuid analysis_id FK "Analyse soumise (CASCADE)"
        uuid referring_doctor_id FK "Médecin généraliste demandeur"
        uuid specialist_id FK "Dermatologue sollicité (SET NULL)"
        referral_status status "pending | accepted | completed | cancelled"
        text referral_note "Motif et synthèse clinique du demandeur"
        text specialist_response "Avis diagnostique et conduite à tenir"
        timestamp created_at "Date d'émission de l'avis"
        timestamp responded_at "Date de signature de l'expertise"
    }

    refresh_tokens {
        uuid id PK "Identifiant du jeton de session"
        uuid user_id FK "Utilisateur titulaire (CASCADE)"
        varchar token_hash UK "Empreinte sécurisée SHA-256 du jeton"
        timestamp expires_at "Échéance de validité (7 jours)"
        boolean is_revoked "Marqueur d'invalidation"
        timestamp created_at "Date d'émission"
    }

    audit_logs {
        uuid id PK "Identifiant de l'événement"
        uuid user_id FK "Auteur de l'action (SET NULL)"
        varchar action "Type d'événement (LOGIN, INFERENCE, etc.)"
        varchar resource_type "Entité ciblée"
        uuid resource_id "Identifiant de la ressource"
        jsonb details "Contexte de l'action (champs modifiés, IP)"
        varchar ip_address "Adresse IP d'origine"
        timestamp created_at "Horodatage immuable de l'événement"
    }

    %% Cardinalités normalisées
    users ||--|| doctor_profiles : "possède unitairement"
    users ||--o{ patients : "crée et suit"
    users ||--o{ analysis_records : "effectue"
    users ||--o{ refresh_tokens : "dispose de"
    users ||--o{ audit_logs : "génère"
    patients ||--o{ analysis_records : "possède des historiques"
    analysis_records ||--o| referrals : "peut nécessiter"
    users ||--o{ referrals : "émet en tant que GP"
    users ||--o{ referrals : "traite en tant que Spécialiste"
```

---

### 3.2 Règles d'Intégrité, Indexation et Pseudonymisation GDPR

1. **Pseudonymisation Médicale Stricte** :
   - Aucun nom patronymique ou identifiant de sécurité sociale n'est consigné dans la table `patients`.
   - L'identifiant généré suit le formalisme normalisé `DZ-{code_wilaya}-P{séquentiel}` (ex: `DZ-31-P0046`).
   - L'âge n'est pas stocké sous forme brute mais dérivé dynamiquement de `birth_year` lors de chaque examen afin de préserver l'exactitude longitudinale.
2. **Suppression Logique (Soft Delete)** :
   - Les dossiers patients bénéficient d'une suppression douce via `deleted_at IS NOT NULL`, prévenant la rupture des clés étrangères dans les séries temporelles d'analyse.
3. **Indexation Stratégique pour les Performances** :
   - Clés primaires basées sur des UUID indexés en arbres B (`B-Tree`).
   - Index composites sur `(doctor_id, created_at DESC)` pour une pagination instantanée des historiques médicaux.
   - Index partiel sur `referrals (status)` pour l'interrogation rapide des boîtes d'avis en attente (`PENDING`).

---

## Chapitre 4 : Modélisation Dynamique — Diagrammes de Séquence

### 4.1 Séquence 1 : Authentification Sécurisée & Passerelle Anti-Contournement

Ce diagramme détaille la cinématique d'authentification robuste avec élimination complète des failles de contournement en session privée (Private/Incognito Browsing).

```mermaid
sequenceDiagram
    autonumber
    actor Clinician as 🩺 Médecin Praticien
    participant Web as 🌐 Tableau de Bord Web
    participant AuthGuard as 🛡️ Passerelle Auth (ensureAuth)
    participant API as 🚀 FastAPI (/api/v1/auth)
    participant DB as 🗄️ PostgreSQL

    Clinician->>Web: Accède à /dashboard/doctor.html
    Web->>AuthGuard: Vérifier présence du jeton (sessionStorage)
    
    alt Absence de jeton ou session privée neuve
        AuthGuard-->>Web: Jeton introuvable
        Web->>Web: Redirection forcée vers login.html
        Note over Web,AuthGuard: Aucune connexion automatique autorisée
    else Jeton présent dans la session
        AuthGuard->>API: GET /api/v1/auth/me (Bearer Token)
        API->>DB: Vérifier validité & statut utilisateur
        DB-->>API: Utilisateur actif (role: doctor)
        API-->>AuthGuard: 200 OK (User Profile Data)
        AuthGuard-->>Web: Autorisation confirmée, initialisation de la vue
    end

    Clinician->>Web: Saisie identifiants sur login.html
    Web->>API: POST /api/v1/auth/login {email, password}
    API->>DB: Requête utilisateur par email
    DB-->>API: Tuple utilisateur (avec password_hash)
    API->>API: Vérification bcrypt(password, hash)
    
    alt Mot de passe invalide ou compte inactif
        API-->>Web: 401 Unauthorized / 403 Forbidden
        Web-->>Clinician: Affichage du message d'erreur
    else Authentification réussie
        API->>API: Génération Access Token (15 min) + Refresh Token (7 j)
        API->>DB: Insertion empreinte RefreshToken dans DB
        API->>DB: Insertion AuditLog (ACTION_LOGIN)
        API-->>Web: 200 OK {access_token, refresh_token, doctor_type}
        Web->>Web: Stockage sécurisé dans sessionStorage
        Web-->>Clinician: Redirection vers le tableau de bord correspondant
    end
```

---

### 4.2 Séquence 2 : Inférence Multimodale & Génération Asynchrone de Grad-CAM++

Ce diagramme illustre le flux critique d'analyse clinique où l'interaction utilisateur bénéficie d'une latence inférieure à 200 ms grâce à la déportation du calcul Grad-CAM++ dans une tâche d'arrière-plan.

```mermaid
sequenceDiagram
    autonumber
    actor Doctor as 🩺 Médecin Praticien
    participant UI as 📱 Interface Clinique (Web/Mobile)
    participant Router as 🚦 API Router (/api/v1/predict)
    participant Storage as 💾 StorageService (Résilience)
    participant Preproc as ⚙️ PreprocessingService
    participant PyTorch as 🧠 ModelService (Threadpool)
    participant Risk as 🛡️ RiskEngine
    participant DB as 🗄️ PostgreSQL
    participant BG as ⚡ FastAPI BackgroundTasks
    participant GradCAM as 🔬 GradCAMService

    Doctor->>UI: Soumettre cliché dermoscopique + données ABCDE
    UI->>Router: POST /api/v1/predict (Multipart Form)
    
    Router->>Storage: upload_image(bytes, filename)
    Storage->>Storage: is_minio_reachable() (Socket 150ms)
    alt MinIO est joignable
        Storage->>Storage: Sauvegarde vers bucket MinIO analyses
    else MinIO indisponible
        Storage->>Storage: Sauvegarde locale immédiate (uploads/analyses/)
    end
    Storage-->>Router: storage_key générée (< 1ms si local)

    Router->>Preproc: preprocess_multimodal(image_bytes, metadata)
    Preproc-->>Router: Tensor Image (1,3,224,224) + Tensor Clinique (1,7)

    Router->>PyTorch: run_in_threadpool(model.forward, tensors)
    Note over PyTorch: Inférence multimodale avec TTA x8 (130ms)
    PyTorch-->>Router: 6 Probabilités de classes + Confiance globale

    Router->>Risk: assess_risk(predicted_class, confidence, metadata)
    alt Confiance < 50%
        Risk-->>Router: RiskLevel: INCONCLUSIVE (suggest_referral: true)
    else Confiance >= 50%
        Risk-->>Router: RiskLevel calculé (LOW | MODERATE | HIGH | CRITICAL)
    end

    Router->>DB: INSERT INTO analysis_records (...)
    DB-->>Router: Record persisté avec identifiant UUID

    Router->>BG: add_task(compute_gradcam, record_id, image_bytes)
    
    Router-->>UI: 200 OK {prediction, confidence, risk_level, storage_key}
    Note over UI,Doctor: Affichage immédiat du diagnostic (< 200ms)

    Note over BG,GradCAM: Exécution de la tâche asynchrone en arrière-plan
    BG->>GradCAM: compute_gradcam_heatmap(tensors, target_class)
    GradCAM->>Storage: upload_image(heatmap_bytes, gradcam_key)
    GradCAM->>DB: UPDATE analysis_records SET gradcam_storage_key = key
```

---

### 4.3 Séquence 3 : Cycle Complet de Télé-expertise Clinique (GP → Spécialiste)

Ce diagramme formalise la collaboration télémédicale entre le médecin de première ligne et le dermatologue référent.

```mermaid
sequenceDiagram
    autonumber
    actor GP as 🩺 Médecin Généraliste
    participant WebGP as 🌐 Portail Médecin (GP)
    participant RefAPI as 📡 API Referrals (/api/v1/referrals)
    participant DB as 🗄️ PostgreSQL
    participant WebSpec as 🌐 Portail Dermatologue (Spécialiste)
    actor Spec as 👨‍⚕️ Dermatologue Spécialiste

    GP->>WebGP: Sélectionne une analyse à haut risque (ex: HIGH / MEL)
    GP->>WebGP: Rédige la note d'orientation clinique
    WebGP->>RefAPI: POST /api/v1/referrals {analysis_id, note}
    RefAPI->>DB: INSERT INTO referrals (status='PENDING')
    DB-->>RefAPI: Confirmation d'enregistrement
    RefAPI-->>WebGP: 201 Created (Demande d'avis ouverte)

    Note over DB,WebSpec: Notification et apparition dans l'inbox du spécialiste
    Spec->>WebSpec: Accède à l'onglet "Télé-expertises"
    WebSpec->>RefAPI: GET /api/v1/referrals/received
    RefAPI->>DB: SELECT * FROM referrals WHERE status='PENDING'
    DB-->>RefAPI: Liste des dossiers transférés
    RefAPI-->>WebSpec: Affichage de la file de consultation

    Spec->>WebSpec: Sélectionne un dossier pour examen approfondi
    WebSpec->>RefAPI: GET /api/v1/analyses/{id}
    RefAPI->>DB: Récupération image haute définition + Grad-CAM + anamnèse
    DB-->>RefAPI: Données consolidées de l'examen
    RefAPI-->>WebSpec: Rendu de l'image originale et de la carte thermique

    Spec->>WebSpec: Formule ses conclusions cliniques & préconisation de biopsie
    WebSpec->>RefAPI: PUT /api/v1/referrals/{id}/respond {response, biopsy_advised}
    RefAPI->>DB: UPDATE referrals SET status='COMPLETED', responded_at=NOW()
    RefAPI->>DB: UPDATE analysis_records SET specialist_feedback=...
    DB-->>RefAPI: Transaction validée
    RefAPI-->>WebSpec: 200 OK (Expertise clôturée et scellée)

    GP->>WebGP: Consulte le retour d'expertise sur la fiche patient
    WebGP-->>GP: Consultation des recommandations du spécialiste
```

---

### 4.4 Séquence 4 : Gouvernance des Ressources Académiques et Mises à Jour (Admin)

```mermaid
sequenceDiagram
    autonumber
    actor Admin as 👑 Administrateur
    participant WebAdmin as 🌐 Panneau Admin
    participant ResAPI as 📡 API Resources (/api/v1/admin/platform-resources)
    participant Disk as 💾 Système de Fichiers
    participant Conf as 📄 platform_resources.json
    participant DB as 🗄️ PostgreSQL (AuditLog)

    Admin->>WebAdmin: Téléverse une révision de mémoire (ex: Thesis_Master_GLAA_FR.pdf)
    WebAdmin->>ResAPI: POST /upload-thesis (Multipart, file_type: 'thesis_fr')
    ResAPI->>ResAPI: Contrôle extension (.pdf) et en-tête MIME
    ResAPI->>Disk: Écriture du fichier dans docs_v2/Thesis_Master_GLAA_FR.pdf
    ResAPI->>Conf: Mise à jour du JSON persistant (taille en Mo, horodatage)
    ResAPI->>DB: INSERT INTO audit_logs (ACTION_UPDATE_RESOURCE, admin_id)
    ResAPI-->>WebAdmin: 200 OK {status: 'success', file_size: '2.30 MB'}
    WebAdmin-->>Admin: Notification visuelle de synchronisation réussie
```

---

## Chapitre 5 : Modélisation des États — Diagrammes d'États-Transitions

### 5.1 Machine à États : Cycle de Vie du Compte Praticien

Le compte utilisateur traverse des phases d'accréditation garantissant qu'aucun individu non vérifié par l'Ordre des Médecins ne puisse exploiter les outils d'aide au diagnostic.

```mermaid
stateDiagram-v2
    [*] --> PENDING_VERIFICATION : Inscription initiale du médecin (Web/Mobile)
    
    state PENDING_VERIFICATION {
        [*] --> EnAttenteControleOrdinal
        EnAttenteControleOrdinal : Contrôle du numéro de licence et de la wilaya
    }

    PENDING_VERIFICATION --> ACTIVE : Validation et activation manuelle par l'Administrateur
    PENDING_VERIFICATION --> [*] : Rejet de la demande (Données erronées)

    state ACTIVE {
        [*] --> Operationnel
        Operationnel : Inférences autorisées, télé-expertise accessible
        Operationnel --> DoitChangerMotDePasse : Réinitialisation déclenchée par Admin
        DoitChangerMotDePasse --> Operationnel : Changement de mot de passe validé
    }

    ACTIVE --> SUSPENDED : Détection d'anomalie ou décision ordinale
    SUSPENDED --> ACTIVE : Réactivation par l'Administrateur
    SUSPENDED --> [*] : Clôture définitive du compte
```

---

### 5.2 Machine à États : Cycle de Vie d'une Demande de Télé-expertise

Ce cycle régit les transitions d'une requête de deuxième avis transmise entre confrères.

```mermaid
stateDiagram-v2
    [*] --> PENDING : Le médecin généraliste soumet l'analyse
    
    state PENDING {
        [*] --> VisibleFileAttente
        VisibleFileAttente : Notification transmise aux spécialistes éligibles
    }

    PENDING --> CANCELLED : Annulation par le généraliste demandeur
    PENDING --> ACCEPTED : Prise en charge par un dermatologue spécialiste
    
    state ACCEPTED {
        [*] --> EnCoursExamen
        EnCoursExamen : Inspection dermoscopique, comparaison Grad-CAM
    }

    ACCEPTED --> COMPLETED : Émission du rapport d'expertise et signature
    
    state COMPLETED {
        [*] --> ArchiveScellee
        ArchiveScellee : Lecture seule pour le généraliste et intégration au dossier
    }

    CANCELLED --> [*]
    COMPLETED --> [*]
```

---

### 5.3 Machine à États : Arbre de Décision du Moteur de Risque Médical

Ce diagramme formalise le comportement interne du module déterministe d'attribution du niveau de risque clinique.

```mermaid
stateDiagram-v2
    [*] --> EvaluationCertitude : Réception des probabilités de l'IA

    state EvaluationCertitude {
        [*] --> ControleSeuil
        ControleSeuil : Confiance maximale >= 50% ?
    }

    EvaluationCertitude --> INCONCLUSIVE : Non (Confiance < 50%)
    EvaluationCertitude --> AnalysePathologique : Oui (Confiance >= 50%)

    state INCONCLUSIVE {
        [*] --> AlerteNeutre
        AlerteNeutre : Badge Gris/Ambre, Déclenchement Suggest_Referral
    }

    state AnalysePathologique {
        [*] --> VerificationClasse
        VerificationClasse : Nature de la pathologie prédite
    }

    AnalysePathologique --> LOW : Classe Bénigne (NEV, SEK) et Critères ABCDE négatifs
    AnalysePathologique --> MODERATE : Kératose actinique (ACK) ou doute clinique
    AnalysePathologique --> HIGH : Carcinome avéré (BCC, SCC)
    AnalysePathologique --> CRITICAL : Mélanome suspect (MEL) ou extension lésionnelle

    INCONCLUSIVE --> [*]
    LOW --> [*]
    MODERATE --> [*]
    HIGH --> [*]
    CRITICAL --> [*]
```

---

## Chapitre 6 : Modélisation des Processus — Diagramme d'Activité

### 6.1 Diagramme d'Activité Global du Processus Clinique (Lignes d'Eau / Swimlanes)

Le diagramme d'activité ci-dessous met en scène les flux de traitement séquentiels et parallèles entre les différents acteurs et sous-systèmes techniques.

```mermaid
flowchart TD
    %% Définition des couloirs
    subgraph Clinician_Lane ["Médecin Praticien (GP)"]
        A1(["Début consultation"]) --> A2["Acquisition cliché dermoscopique"]
        A2 --> A3["Renseignement anamnèse & ABCDE"]
        A3 --> A4["Validation et transmission du dossier"]
        A4 --> A5{"Réception des résultats"}
        A14["Revue de l'avis spécialisé"] --> A15["Prescription acte chirurgical / Contrôle"]
        A15 --> A16(["Fin de consultation"])
    end

    subgraph API_Storage_Lane ["Passerelle API & Stockage Résilient"]
        B1["Réception requête POST /predict"] --> B2{"Sonde TCP MinIO active ?"}
        B2 -- Oui --> B3["Écriture objet MinIO S3"]
        B2 -- Non --> B4["Bascule instantanée sur Disque Local"]
        B3 --> B5["Formatage des tenseurs"]
        B4 --> B5
        B8["Sauvegarde enregistrement DB"] --> B9["Envoi réponse HTTP < 200ms"]
    end

    subgraph AI_Engine_Lane ["Moteur d'Inférence IA & Risque"]
        C1["Exécution inférence multimodale (TTA x8)"] --> C2["Calcul vecteur des 6 probabilités"]
        C2 --> C3{"Confiance >= 50% ?"}
        C3 -- Non --> C4["Classification : INCONCLUSIVE"]
        C3 -- Oui --> C5["Classification oncologique nominale"]
        C4 --> C6["Attribution des recommandations"]
        C5 --> C6
        C7["Calcul de la carte thermique Grad-CAM++"] --> C8["Mise à jour asynchrone DB"]
    end

    subgraph Specialist_Lane ["Dermatologue Spécialiste"]
        D1["Notification dans l'Inbox"] --> D2["Analyse comparative image / Grad-CAM"]
        D2 --> D3["Formulation du diagnostic d'expertise"]
        D3 --> D4["Clôture de la télé-expertise"]
    end

    %% Transitions inter-couloirs
    A4 --> B1
    B5 --> C1
    C6 --> B8
    B9 --> A5

    %% Branchement parallèle Grad-CAM
    B8 -. "Tâche de fond (BackgroundTasks)" .-> C7

    %% Branchement décisionnel clinique
    A5 --> A6{"Besoin d'un second avis ? (HIGH / INCONCLUSIVE)"}
    A6 -- Non --> A7["Validation concordance et export PDF"]
    A7 --> A16
    A6 -- Oui --> A8["Création demande de télé-expertise"]
    
    A8 --> D1
    D4 --> A14
```

---

### 6.2 Mécanisme de Résilience Zéro-Délai (Dual-Storage Fallback)

L'un des défis majeurs documentés dans les écarts de soutenance (Section 5.5 de `thesis_deviations_v2.md`) réside dans l'élimination des latences d'infrastructure :
- **Problématique initiale** : Lorsque le conteneur MinIO est éteint (mode de présentation locale ou machine universitaire sans Docker), la bibliothèque S3 tentait des connexions répétées jusqu'à épuisement du délai d'attente (timeout de 30s + 30s = 60s de gel complet).
- **Solution logicielle implémentée** : Conception d'un intercepteur socket non bloquant (`is_minio_reachable`) avec un cache de validité de 15 secondes. Si le port TCP 9000 ne répond pas en 150 ms, le moteur oriente l'écriture directement vers le stockage local de l'hôte.
- **Bénéfice mesuré** : Le temps d'exécution total de la chaîne d'analyse est descendu de **60 000 ms à 131 ms**, assurant une fluidité absolue devant le jury de soutenance.

---

## Chapitre 7 : Modélisation Architecturale & Physique — Déploiement & Composants

### 7.1 Diagramme des Composants Logiciels

Ce diagramme illustre les composants logiciels modulaires constituant la solution globale et leurs interfaces de communication.

```mermaid
flowchart TD
    subgraph Presentation_Tier ["Couche Présentation (Clients)"]
        MobileApp["📱 Application Mobile Flutter<br/>(Médecin & Patient Mode)"]
        WebDoctor["🌐 Tableau de Bord Praticien<br/>(Vanilla JS + Chart.js + i18n)"]
        WebAdmin["👑 Console Administrateur<br/>(Supervision & Audit)"]
    end

    subgraph Application_Tier ["Couche Application (Backend FastAPI)"]
        direction TB
        APIGateway["🚦 Passerelle & Routeur FastAPI<br/>(CORS, Middleware, Auth Guard)"]
        
        subgraph Sub_Services ["Services Applicatifs"]
            AuthModule["🔐 Service Authentification<br/>(JWT HS256 & Bcrypt)"]
            InferenceModule["🧠 Service Inférence IA<br/>(PyTorch Multimodal + TTA)"]
            XAIModule["🔬 Service Explicabilité<br/>(Grad-CAM++ Engine)"]
            RiskModule["🛡️ Moteur de Risque Clinique<br/>(Algorithme à 5 niveaux)"]
            DocModule["📄 Service Documentaire<br/>(Générateur PDF ReportLab)"]
            ResModule["📦 Service Ressources<br/>(Gestionnaire Thèses & APK)"]
        end
    end

    subgraph Data_Tier ["Couche Persistance & Stockage"]
        PostgresDB[("🗄️ Base Relationnelle<br/>PostgreSQL 16 (Alembic)")]
        ObjectStore[("☁️ Stockage d'Objets<br/>MinIO S3")]
        LocalStorage[("💾 Stockage Local Résilient<br/>uploads/")]
    end

    %% Liaisons de composants
    MobileApp -- "HTTPS / JSON" --> APIGateway
    WebDoctor -- "HTTPS / JSON" --> APIGateway
    WebAdmin -- "HTTPS / JSON" --> APIGateway

    APIGateway --> AuthModule
    APIGateway --> InferenceModule
    APIGateway --> DocModule
    APIGateway --> ResModule

    InferenceModule --> RiskModule
    InferenceModule --> XAIModule

    AuthModule --> PostgresDB
    InferenceModule --> PostgresDB
    InferenceModule --> ObjectStore
    InferenceModule -. "Secours automatique" .-> LocalStorage
    DocModule --> LocalStorage
    ResModule --> LocalStorage
```

---

### 7.2 Diagramme de Déploiement Matériel et Réseau

Le diagramme ci-après spécifie la topologie d'exécution physique et conteneurisée déployée sur l'infrastructure d'hébergement.

```mermaid
flowchart TB
    subgraph Client_Nodes ["Nœuds Clients"]
        Node_Browser["💻 Station de Travail Clinique<br/>Navigateur Web Moderne (Chrome, Firefox, Edge)<br/>Protocole : HTTPS / WSS"]
        Node_Smartphone["📱 Smartphone Clinique de Terrain<br/>OS : Android 10+ (App Flutter compilée)<br/>Protocole : HTTPS REST"]
    end

    subgraph Host_Server ["Serveur d'Application (Hôte Physique ou Machine Virtuelle)"]
        subgraph Docker_Network ["Réseau Virtuel Docker Bridge (172.20.0.0/16)"]
            
            subgraph Container_Backend ["Conteneur App : medassist-backend"]
                Uvicorn["Serveur ASGI Uvicorn (Port interne 8000)"]
                FastAPIApp["Application FastAPI (Python 3.10+)"]
                PyTorchRuntime["Moteur PyTorch Runtime (CUDA / CPU)"]
                ModelWeight["Poids du Modèle V6.0 : multimodal_model.pth"]
            end

            subgraph Container_DB ["Conteneur Données : medassist-postgres"]
                PGServer["Moteur PostgreSQL 16 Alpine (Port 5432)"]
                PGData[("Volume persistant : pgdata")]
            end

            subgraph Container_MinIO ["Conteneur S3 : medassist-minio"]
                MinIOServer["Serveur MinIO S3 (Port 9000 & Console 9001)"]
                MinIOData[("Volume persistant : minio_data")]
            end

        end

        subgraph Host_FS ["Système de Fichiers de l'Hôte"]
            LocalUploads["Répertoire Local de Secours : /uploads/<br/>- analyses/<br/>- gradcam/<br/>- platform_docs/ (Thèses EN/FR)"]
        end
    end

    %% Connexions réseaux
    Node_Browser -- "HTTP :8000" --> Uvicorn
    Node_Smartphone -- "HTTP :8000" --> Uvicorn

    Uvicorn --> FastAPIApp
    FastAPIApp --> PyTorchRuntime
    PyTorchRuntime --> ModelWeight

    FastAPIApp -- "Connexion Pool SQLAlchemy" --> PGServer
    PGServer --> PGData

    FastAPIApp -- "API S3 (Boto3/Minio SDK)" --> MinIOServer
    MinIOServer --> MinIOData

    FastAPIApp -- "Écriture directe (Fallback résilient)" --> LocalUploads
```

---

### 7.3 Matrice de Traçabilité Exigences-Conception

Cette matrice démontre la correspondance rigoureuse entre les exigences formulées dans le cahier des charges académique et les éléments de modélisation UML conçus.

| Code Exigence | Intitulé Fonctionnel / Non-Fonctionnel | Élément UML Modélisé | Composant / Classe d'Implémentation |
| :--- | :--- | :--- | :--- |
| **EX-F01** | Inférence multimodale assistée par vision artificielle | Diagramme de Séquence 2, Diagramme de Classes | `ModelService`, `predict.py` |
| **EX-F02** | Explicabilité visuelle par cartes thermiques d'attention | Diagramme de Séquence 2, Diagramme d'Activité | `GradCAMService`, `BackgroundTasks` |
| **EX-F03** | Gestion déterministe de l'incertitude (`INCONCLUSIVE`) | Diagramme d'États 3, Cas d'Utilisation CU-01 | `RiskEngine.assess_risk()` |
| **EX-F04** | Collaboration médicale et télé-expertise à distance | Diagramme de Séquence 3, Diagramme d'États 2 | `Referral`, `/api/v1/referrals` |
| **EX-F05** | Dossier patient pseudonymisé conforme RGPD | Modèle Logique (ERD), Diagramme de Classes | `Patient`, `patient_code` |
| **EX-F06** | Génération de compte-rendu imprimable avec QR éphémère | Diagramme des Cas d'Utilisation, Classes | `PDFReportService`, `ReportLab` |
| **EX-F07** | Intégrité et contrôle d'accès basé sur les rôles (RBAC) | Diagramme de Séquence 1, Diagramme d'États 1 | `User`, `RefreshToken`, `AuthGuard` |
| **EX-NF01** | Temps de réponse clinique global $< 500\text{ ms}$ | Diagramme de Séquence 2 (Threadpool & Async) | `run_in_threadpool`, `BackgroundTasks` |
| **EX-NF02** | Haute résilience sans interruption de service | Diagramme d'Activité (Sonde TCP) | `StorageService.is_minio_reachable()` |
| **EX-NF03** | Support linguistique complet (EN / FR / AR) | Diagramme des Composants | `DashboardI18n Engine` (`i18n.js`) |
| **EX-NF04** | Pérennité documentaire des mémoires officiels | Diagramme de Séquence 4 | `PlatformResourcesService` |

---

## Conclusion de la Spécification

L'ensemble des modèles UML formalisés dans ce document fournit une cartographie exhaustive, cohérente et rigoureuse de la plateforme **MedAssist AI V2**. 

Cette documentation satisfait aux exigences formelles d'un **Mémoire de Master en Génie Logiciel et Applications Avancées (GLAA)** en apportant :
1. Une modélisation fonctionnelle claire séparant les prérogatives des généralistes, des dermatologues et des administrateurs.
2. Une conception orientée objet modulaire découplée des détails d'infrastructure.
3. Une formalisation précise de la dynamique temporelle garantissant des temps de réponse compatibles avec la pratique médicale.
4. Une justification technique argumentée des choix architecturaux de sécurité et de résilience.

