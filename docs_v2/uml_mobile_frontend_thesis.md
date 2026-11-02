# 📱 Spécification Complète de Modélisation UML — Client Mobile MedAssist AI V2 (Flutter & GetX)
## Application Mobile d'Aide à la Décision Clinique Dermatologique et de Télé-expertise

> **Document Académique Officiel**  
> **Diplôme visé** : Master en Informatique — Spécialité : **Génie Logiciel et Applications Avancées (GLAA)**  
> **Cadre de réalisation** : Mémoire de Fin d'Études & Projet Diplôme-Startup (Arrêté Ministériel 1275)  
> **Édition** : Version 2.2 Complète — Architecture Mobile Réactive & Résiliente  
> **Date de validation** : Novembre 2026  
> **Conformité** : Normes OMG UML 2.5 (Unified Modeling Language)

---

## 📑 Sommaire Général

1. [Introduction et Choix Architecturaux du Client Mobile](#1-introduction-et-choix-architecturaux-du-client-mobile)
2. [Chapitre 1 : Modélisation Fonctionnelle — Diagramme des Cas d'Utilisation](#chapitre-1--modélisation-fonctionnelle--diagramme-des-cas-dutilisation)
   - 1.1 Diagramme Global des Cas d'Utilisation Mobile
   - 1.2 Identification des Acteurs Mobiles et Frontières
   - 1.3 Fiches Descriptives Textuelles des Cas d'Utilisation Mobiles Critiques
3. [Chapitre 2 : Modélisation Structurelle — Diagramme de Classes Logiciel (Clean Architecture / GetX)](#chapitre-2--modélisation-structurelle--diagramme-de-classes-logiciel)
   - 2.1 Conception en Couches : Presentation, Domain, Data & Provider Tiers
   - 2.2 Diagramme de Classes Détaillé des Contrôleurs, Vues et Dépôts
   - 2.3 Modèle des Données et Objets Métier Mobiles
4. [Chapitre 3 : Modélisation Dynamique — Diagrammes de Séquence Mobile](#chapitre-3--modélisation-dynamique--diagrammes-de-séquence-mobile)
   - 3.1 Séquence M-1 : Parcours d'Inférence Clinique & Consentement Éclairé Obligatoire
   - 3.2 Séquence M-2 : Interception Réseau & Rafraîchissement Silencieux du Jeton (401 Auto-Refresh)
   - 3.3 Séquence M-3 : Cycle Complet de Télé-expertise Mobile (Émission GP & Réponse Spécialiste)
   - 3.4 Séquence M-4 : Consultation et Suivi Médical Citoyen par Scan QR Code
5. [Chapitre 4 : Modélisation des États — Diagrammes d'États-Transitions](#chapitre-4--modélisation-des-états--diagrammes-détats-transitions)
   - 4.1 Machine à États : Navigation Applicative & Cycle de Session Clinique
   - 4.2 Machine à États : Évaluation Visuelle du Risque Clinique à 5 Niveaux
6. [Chapitre 5 : Modélisation des Processus — Diagramme d'Activité Client Mobile](#chapitre-5--modélisation-des-processus--diagramme-dactivité-client-mobile)
   - 5.1 Diagramme d'Activité : Gestion de la Connectivité & Résilience Offline-First
7. [Chapitre 6 : Modélisation Architecturale & Paquetages (Component & Package Diagrams)](#chapitre-6--modélisation-architecturale--paquetages)
   - 6.1 Diagramme des Paquetages Modulaires (Feature-First)
   - 6.2 Matrice de Traçabilité des Exigences Mobiles
8. [Conclusion de la Modélisation Mobile](#conclusion-de-la-modélisation-mobile)

---

## 1. Introduction et Choix Architecturaux du Client Mobile

L'application mobile **MedAssist AI (V2)** constitue le terminal de première ligne destiné aux praticiens de santé (médecins généralistes en polycliniques, centres de santé ruraux et dermatologues hospitaliers) ainsi qu'aux patients pour leur suivi post-consultation.

Pour répondre aux exigences de réactivité, de maintenabilité et de résilience dictées par le cadre d'un **Master GLAA** et d'un projet **Diplôme-Startup (Arrêté 1275)**, le client mobile a été structuré autour du patron d'architecture **Feature-First Clean Architecture** orchestré par le framework **GetX** (`get: ^4.6.6`).

Ce choix architectural apporte les garanties suivantes :
- **Découplage strict des responsabilités** : Séparation univoque entre l'interface graphique (`GetView`), la logique métier réactive (`GetxController`), l'abstraction des accès de données (`Repositories`) et les clients réseau/stockage (`Providers`).
- **Résilience déconnectée (Offline-First)** : Maintien de l'accès aux historiques et analyses antérieures via un cache persistant local (`GetStorage`) en cas d'interruption du réseau mobile 4G/WiFi.
- **Transparence de session** : Cycle de vie à double jeton JWT avec intercepteur HTTP capable de renouveler silencieusement l'accès (`Silent 401 Auto-Refresh`) sans perturber le médecin lors d'un acte clinique.
- **Rigueur réglementaire et éthique** : Intégration native de l'écran de consentement éclairé obligatoire (`ConsentScreen`), pseudonymisation des dossiers patients (`DZ-XX-PXXXX`) et gestion déterministe du risque à 5 niveaux (`INCONCLUSIVE`).

---

## Chapitre 1 : Modélisation Fonctionnelle — Diagramme des Cas d'Utilisation

### 1.1 Diagramme Global des Cas d'Utilisation Mobile

```mermaid
flowchart LR
    %% Acteurs Mobiles
    subgraph Acteurs_Mobile ["Acteurs de l'Application Mobile"]
        direction TB
        GP["🩺 Médecin Généraliste<br/>(Frontline Clinician)"]
        SPEC["👨‍⚕️ Médecin Spécialiste<br/>(Dermatologist)"]
        PATIENT["👤 Patient / Citoyen<br/>(Follow-up User)"]
        GUEST["🌐 Praticien Visiteur<br/>(Guest Mode)"]
    end

    %% Héritage d'acteurs
    SPEC -- "Hérite des droits de" --> GP

    %% Paquetage 1 : Inférence & Examen Clinique
    subgraph Pkg_Diag_Mobile ["Paquetage 1 : Diagnostic & Inférence Multimodale"]
        UC_Capture(["Acquérir un cliché dermoscopique (Caméra/Galerie)"])
        UC_Consent(["Valider le consentement éclairé du patient"])
        UC_ClinicalForm(["Saisir les 7 paramètres cliniques & ABCDE"])
        UC_Predict(["Lancer l'inférence multimodale IA"])
        UC_GradCAM_Toggle(["Basculer l'overlay explicatif Grad-CAM++"])
        UC_Feedback(["Soumettre la concordance diagnostique & biopsie"])
        UC_PDF_Export(["Exporter le compte-rendu médical PDF"])
    end

    %% Paquetage 2 : Télé-expertise Mobile
    subgraph Pkg_Ref_Mobile ["Paquetage 2 : Télé-expertise Médicale"]
        UC_DispatchRef(["Créer et expédier une demande d'avis (GP)"])
        UC_SentList(["Consulter l'historique des avis demandés"])
        UC_IncomingList(["Consulter la boîte des avis reçus (Spécialiste)"])
        UC_RespondRef(["Émettre un avis spécialisé & préconisation chirurgicale"])
    end

    %% Paquetage 3 : Dossiers Patients & Chronologie
    subgraph Pkg_Patient_Mobile ["Paquetage 3 : Dossiers Patients Pseudonymisés"]
        UC_AddPatient(["Créer un identifiant patient pseudonymisé"])
        UC_SearchPatient(["Rechercher un dossier patient par code"])
        UC_Timeline(["Consulter la frise chronologique d'évolution de la lésion"])
    end

    %% Paquetage 4 : Prévention & Espace Public
    subgraph Pkg_Public_Mobile ["Paquetage 4 : Prévention & Suivi Public"]
        UC_ABCDE(["Consulter le guide interactif ABCDE trilingue"])
        UC_DirDocs(["Consulter l'annuaire des dermatologues agréés"])
        UC_QRFollow(["Vérifier le suivi médical via QR code sans compte"])
    end

    %% Paquetage 5 : Authentification & Compte
    subgraph Pkg_Auth_Mobile ["Paquetage 5 : Authentification & Sécurité"]
        UC_Login(["S'authentifier (JWT Double Jeton)"])
        UC_Register(["S'inscrire via formulaire à étapes (58 wilayas)"])
        UC_Pending(["Consulter l'état de validation ordinale"])
        UC_ChangePwd(["Mettre à jour un mot de passe temporaire"])
        UC_Profile(["Consulter et modifier son profil praticien"])
    end

    %% Connexions Acteurs -> Cas d'Utilisation
    GP --> UC_Capture
    GP --> UC_Consent
    GP --> UC_ClinicalForm
    GP --> UC_Predict
    GP --> UC_GradCAM_Toggle
    GP --> UC_Feedback
    GP --> UC_PDF_Export
    GP --> UC_DispatchRef
    GP --> UC_SentList
    GP --> UC_AddPatient
    GP --> UC_SearchPatient
    GP --> UC_Timeline
    GP --> UC_Profile

    SPEC --> UC_IncomingList
    SPEC --> UC_RespondRef

    GUEST --> UC_Capture
    GUEST --> UC_ClinicalForm
    GUEST --> UC_Predict
    GUEST --> UC_ABCDE
    GUEST --> UC_DirDocs
    GUEST --> UC_QRFollow
    GUEST --> UC_Login
    GUEST --> UC_Register

    PATIENT --> UC_ABCDE
    PATIENT --> UC_DirDocs
    PATIENT --> UC_QRFollow

    %% Relations d'inclusion et extension
    UC_Capture -. "<<include>>" .-> UC_Consent
    UC_Consent -. "<<include>>" .-> UC_ClinicalForm
    UC_ClinicalForm -. "<<include>>" .-> UC_Predict
    UC_Predict -. "<<include>>" .-> UC_GradCAM_Toggle
    UC_DispatchRef -. "<<extend>>" .-> UC_Predict
    UC_Feedback -. "<<extend>>" .-> UC_Predict
    UC_RespondRef -. "<<include>>" .-> UC_IncomingList
```

---

### 1.2 Identification des Acteurs Mobiles et Frontières

| Acteur Mobile | Description du Périmètre d'Action |
| :--- | :--- |
| **Médecin Généraliste (`GP`)** | Utilisateur principal en cabinet ou polyclinique. Il réalise l'anamnèse, recueille le consentement du patient, lance l'analyse multimodale, consulte les explications visuelles Grad-CAM++, soumet son accord diagnostique et sollicite une télé-expertise si la lésion présente un risque élevé ou indéterminé (`INCONCLUSIVE`). |
| **Dermatologue Spécialiste (`Specialist`)** | Praticien hospitalier ou libéral référent. En plus des fonctionnalités du généraliste, il accède à sa boîte de réception mobile dédiée (`Incoming Cases`) pour examiner les clichés dermoscopiques haute définition, analyser les tenseurs Grad-CAM++ et émettre formellement un avis spécialisé et des consignes d'exérèse/biopsie. |
| **Praticien Visiteur (`Guest`)** | Médecin ou étudiant en phase d'évaluation de l'application sans compte actif. Il dispose d'un accès au dépistage exploratoire direct (sauvegarde locale uniquement dans `GetStorage` sans persistance PostgreSQL), à la règle éducative ABCDE, et à l'annuaire public des praticiens. |
| **Patient / Citoyen (`Patient`)** | Utilisateur final sans identifiant permanent. Il consulte le guide de sensibilisation ABCDE et accède à la synthèse médicale de sa consultation ainsi qu'à la date de son prochain contrôle en scannant le QR code de son compte-rendu via la vue publique `/qr-followup`. |

---

### 1.3 Fiches Descriptives Textuelles des Cas d'Utilisation Mobiles Critiques

#### CU-M01 : Acquisition, Consentement Éclairé et Inférence Multimodale
- **Acteur Principal** : Médecin Généraliste / Spécialiste.
- **Préconditions** : L'application est lancée ; l'accès à la caméra ou à la galerie photo est autorisé par le système d'exploitation.
- **Scénario Nominal** :
  1. Le praticien active le module de prise de vue dermoscopique avec cercle guide de centrage et contrôle de netteté.
  2. La photo est capturée et validée.
  3. L'application bascule automatiquement vers l'écran de **Consentement Éclairé** (`ConsentView`).
  4. Le médecin confirme l'accord formel du patient pour l'enregistrement et la transmission chiffrée de ses données cliniques.
  5. L'application ouvre la fiche clinique (`ClinicalFormView`). Le praticien renseigne les 7 variables cliniques (âge, sexe, localisation, diamètre en mm, élévation, saignement, antécédents, évolution) ou sélectionne un cas de référence préchargé PAD-UFES-20.
  6. Le praticien valide la soumission ; `DiagnosisRepository` émet une requête multipart vers `/api/v1/predict`.
  7. L'écran de résultat (`ResultView`) s'affiche : diagnostic principal parmi les 6 classes, pourcentage de confiance, badge de risque à 5 niveaux, recommandations personnalisées et bouton de bascule vers la carte d'attention Grad-CAM++.
  8. Le praticien enregistre son accord de concordance (`Doctor Concordance Feedback`) avec indication d'une biopsie éventuelle.

#### CU-M02 : Évaluation et Réponse à une Demande de Télé-expertise (Spécialiste)
- **Acteur Principal** : Médecin Spécialiste.
- **Préconditions** : Le spécialiste est authentifié avec son rôle certifié (`specialist_dermatologist`).
- **Scénario Nominal** :
  1. Le spécialiste sélectionne l'onglet "Télé-expertise" du `MainLayoutView` et bascule sur le sous-onglet "Incoming (Specialist)".
  2. Le contrôleur `ReferralsController` interroge `GET /api/v1/referrals/received` via `ReferralRepository`.
  3. Le spécialiste clique sur une expertise en attente (`PENDING REVIEW`).
  4. L'application ouvre le panneau d'évaluation spécialisée (`_showSpecialistResponseSheet`).
  5. Le dermatologue inspecte le cliché, la note clinique du généraliste, et formule son avis diagnostique détaillé ainsi que la préconisation d'une biopsie urgente.
  6. Le spécialiste valide la transmission ; la requête `PUT /api/v1/referrals/{id}/respond` scelle le dossier à l'état `COMPLETED`.
  7. Le généraliste émetteur voit le statut se mettre à jour instantanément dans son onglet "Sent Cases".

#### CU-M03 : Vérification du Suivi Post-Consultation par QR Code Public
- **Acteur Principal** : Patient / Citoyen.
- **Préconditions** : Le patient dispose de son compte-rendu imprimé ou numérique comportant le QR code sécurisé.
- **Scénario Nominal** :
  1. L'utilisateur lance l'application et clique sur "Patient QR Follow-up" depuis l'accueil (sans authentification).
  2. L'utilisateur saisit ou scanne le jeton d'accès temporaire.
  3. Le contrôleur `QRFollowUpController` sollicite `GET /api/v1/public/follow-up/{token}`.
  4. L'écran restitue le diagnostic certifié, l'établissement de santé de rattachement, les recommandations préventives et la **date exacte du prochain contrôle clinique programmé**.

---

## Chapitre 2 : Modélisation Structurelle — Diagramme de Classes Logiciel

### 2.1 Conception en Couches (Clean Architecture / GetX)

L'architecture du client mobile est découpée selon les 4 couches canoniques :
1. **Presentation Tier (Vues, Contrôleurs & Bindings)** :
   - `GetView<T>` : Composants graphiques déclaratifs sans état interne, observant les variables réactives du contrôleur via `Obx()`.
   - `GetxController` : Gestionnaires d'état détenant la logique métier, les observables (`.obs`) et les méthodes d'action asynchrones.
   - `Bindings` : Modules d'injection de dépendances paresseuse (`Get.lazyPut()`) liant les contrôleurs et référentiels aux routes.
2. **Domain Tier (Modèles de Données)** :
   - Entités métiers encapsulant la sérialisation/désérialisation JSON (`fromJson`, `toJson`, `toFormData`).
3. **Repository Tier (Dépôts d'Abstraction)** :
   - Classes passerelles unifiant l'accès aux sources de données (décision entre requête réseau et lecture du cache local).
4. **Data & Provider Tier (Infrastructure & Stockage)** :
   - `ApiProvider` : Client HTTP centralisé avec gestion des en-têtes d'autorisation `Bearer`, intercepteur silencieux sur code 401 et politique de timeouts stricts.
   - `LocalStorageProvider` : Encapsulation du moteur de stockage persistant `GetStorage`.

---

### 2.2 Diagramme de Classes Détaillé des Contrôleurs, Vues et Dépôts

```mermaid
classDiagram
    %% Couche Présentation (Vues & Contrôleurs)
    class MainLayoutController {
        +RxInt currentIndex
        +bool isDoctor
        +String doctorName
        +changeTab(int index) void
    }

    class HomeController {
        +RxBool isLoading
        +bool isAuthenticated
        +bool isDoctor
        +String clinicianName
        +takePhoto() Future
        +uploadFromGallery() Future
        +openPatients() void
        +openReferrals() void
        +openQRFollowUp() void
    }

    class ConsentController {
        +String imagePath
        +RxBool hasConsented
        +proceedToForm() void
        +cancel() void
    }

    class ClinicalFormController {
        +RxInt age
        +RxString sex
        +RxString localization
        +RxDouble diameter
        +RxBool elevation
        +RxBool grew
        +RxBool bleed
        +RxBool skinCancerHistory
        +RxString selectedSampleKey
        +loadBenchmarkSample(String key) void
        +submitAnalysis() void
    }

    class ResultController {
        +PredictionResponse result
        +RxBool showHeatmap
        +RxBool showProbabilities
        +RxBool feedbackSubmitted
        +toggleHeatmap() void
        +toggleProbabilities() void
        +exportPdfReport() void
        +requestSpecialistReferral() void
        +submitConcordanceFeedback(...) void
    }

    class ReferralsController {
        +RxList~ReferralModel~ sentReferrals
        +RxList~ReferralModel~ receivedReferrals
        +RxList~PublicDoctor~ specialists
        +RxBool isLoading
        +RxBool isSubmitting
        +loadSentReferrals() Future
        +loadReceivedReferrals() Future
        +submitReferral() Future
        +respondToReferral(id, response) Future
    }

    class PatientsController {
        +RxList~PatientModel~ patients
        +RxString searchQuery
        +RxBool isLoading
        +loadPatients() Future
        +createPatient(code, birthYear, sex, notes) Future
    }

    class QRFollowUpController {
        +TextEditingController tokenController
        +Rxn~PatientQRFollowUpModel~ followUpData
        +RxBool isLoading
        +fetchFollowUp() Future
        +clear() void
    }

    %% Couche Modèles de Données (Domain Models)
    class PredictionRequest {
        +String imagePath
        +double age
        +String sex
        +String localization
        +double diameter1
        +bool elevation
        +bool grew
        +bool bleed
        +bool skinCancerHistory
        +String patientId
        +String lesionTag
        +bool useTta
        +toFormData() Map~String,String~
    }

    class PredictionResponse {
        +String analysisId
        +String predictedClass
        +String predictedLabelFull
        +double confidence
        +String riskLevel
        +bool riskEscalated
        +String riskExplanation
        +bool suggestReferral
        +String recommendedNextAction
        +String gradcamUrl
        +String gradcamHeatmapBase64
        +Map~String,double~ allProbabilities
        +List~String~ recommendations
        +double inferenceTimeMs
        +getSortedProbabilities() List
        +getConfidencePercentage() String
    }

    class PatientModel {
        +String id
        +String patientCode
        +int birthYear
        +String sex
        +String notes
        +List~PatientTimelineItem~ timeline
        +DateTime createdAt
    }

    class ReferralModel {
        +String id
        +String analysisId
        +String referringDoctorId
        +String specialistId
        +String status
        +String referralNote
        +String specialistResponse
        +String referringDoctorName
        +String specialistName
        +DateTime createdAt
        +DateTime respondedAt
    }

    class PatientQRFollowUpModel {
        +String analysisId
        +String predictedClass
        +double confidence
        +String riskLevel
        +List~String~ recommendations
        +DateTime createdAt
        +DateTime nextFollowupDate
        +bool doctorConfirmed
        +String doctorDiagnosis
        +String doctorInstitution
    }

    %% Couche Référentiels (Repositories)
    class DiagnosisRepository {
        -ApiProvider _api
        -LocalStorageProvider _storage
        +predict(request) Future~PredictionResponse~
        +submitFeedback(analysisId, confirmed, ...) Future~bool~
        +getPatientQRFollowUp(token) Future~PatientQRFollowUpModel~
        -_cachePredictionLocally(request, response) Future~void~
    }

    class HistoryRepository {
        -ApiProvider _api
        -LocalStorageProvider _storage
        +getAnalyses(page, pageSize, riskLevel) Future~List~
        +deleteAnalysis(id, localIndex) Future~void~
        +clearAll() Future~void~
        -_syncRemoteToLocal(items) Future~void~
    }

    class PatientRepository {
        -ApiProvider _api
        +getPatients(page, search) Future~List~PatientModel~~
        +createPatient(request) Future~PatientModel~
        +getPatientDetail(id) Future~PatientModel~
    }

    class ReferralRepository {
        -ApiProvider _api
        +createReferral(req) Future~ReferralModel~
        +getSentReferrals(status) Future~List~ReferralModel~~
        +getReceivedReferrals(status) Future~List~ReferralModel~~
        +respondReferral(id, req) Future~ReferralModel~
        +getPublicDoctors(wilaya, type) Future~List~PublicDoctor~~
    }

    %% Couche Fournisseurs & Services (Infrastructure Tier)
    class ApiProvider {
        -LocalStorageProvider _storage
        -http.Client _client
        +get(endpoint, query, requiresAuth) Future~Response~
        +post(endpoint, body, requiresAuth) Future~Response~
        +put(endpoint, body, requiresAuth) Future~Response~
        +delete(endpoint, requiresAuth) Future~Response~
        +multipartPost(endpoint, fields, files) Future~Response~
        -refreshTokenSilently() Future~bool~
        -_buildHeaders(requiresAuth) Map
    }

    class LocalStorageProvider {
        -GetStorage _box
        +String accessToken
        +String refreshToken
        +bool isAuthenticated
        +String language
        +String themeMode
        +saveAuthTokens(access, refresh) Future~void~
        +clearAuth() Future~void~
        +getOfflineAnalyses() List
        +addOfflineAnalysis(item) Future~void~
    }

    class AuthService {
        -ApiProvider _api
        -LocalStorageProvider _storage
        +Rxn~UserModel~ currentUser
        +bool isDoctor
        +login(email, password) Future~AuthResponse~
        +register(data) Future~UserModel~
        +fetchCurrentProfile() Future~UserModel~
        +logout() Future~void~
    }

    %% Dépendances & Liaisons
    MainLayoutController o-- HomeController
    MainLayoutController o-- PatientsController
    MainLayoutController o-- ReferralsController
    HomeController ..> ConsentController : redirige
    ConsentController ..> ClinicalFormController : transmet imagePath
    ClinicalFormController --> PredictionRequest : instancie
    ClinicalFormController ..> DiagnosisRepository : sollicite
    ResultController --> PredictionResponse : visualise
    ResultController ..> DiagnosisRepository : valide concordance
    ResultController ..> ReferralsController : initie télé-expertise
    PatientsController ..> PatientRepository : interroge
    PatientRepository --> PatientModel : manipule
    ReferralsController ..> ReferralRepository : interroge
    ReferralRepository --> ReferralModel : manipule
    QRFollowUpController ..> DiagnosisRepository : décode
    DiagnosisRepository ..> ApiProvider : transmet HTTP
    DiagnosisRepository ..> LocalStorageProvider : sauvegarde cache
    HistoryRepository ..> ApiProvider : synchronise distant
    HistoryRepository ..> LocalStorageProvider : lit/écrit local
    PatientRepository ..> ApiProvider : transmet HTTP
    ReferralRepository ..> ApiProvider : transmet HTTP
    ApiProvider ..> LocalStorageProvider : injecte jeton JWT
    AuthService ..> ApiProvider : gère sessions
    AuthService ..> LocalStorageProvider : persiste identité
```

---

## Chapitre 3 : Modélisation Dynamique — Diagrammes de Séquence Mobile

### 3.1 Séquence M-1 : Parcours d'Inférence Clinique & Consentement Éclairé Obligatoire

Ce diagramme décrit la chaîne séquentielle rigoureuse depuis la prise de vue dermoscopique jusqu'au retour visuel de l'explicabilité Grad-CAM++ et la confirmation de concordance.

```mermaid
sequenceDiagram
    autonumber
    actor Med as 🩺 Médecin Praticien
    participant Cam as 📷 CameraView / ImagePicker
    participant Consent as 🛡️ ConsentView
    participant Form as 📝 ClinicalFormView
    participant Ctrl as ⚙️ AnalysisController
    participant Repo as 📦 DiagnosisRepository
    participant Provider as 🌐 ApiProvider
    participant API as 🚀 Backend FastAPI (/predict)
    participant Storage as 💾 LocalStorageProvider (Cache)
    participant Res as 📊 ResultView

    Med->>Cam: Capture de la lésion dermoscopique
    Cam->>Consent: Navigation automatique avec imagePath
    Note over Consent: Étape réglementaire obligatoire (Arrêté 1275)
    Med->>Consent: Coche hasConsented = true & clique "Procéder"
    Consent->>Form: Redirection vers le formulaire clinique 7 variables

    Med->>Form: Saisie (âge, sexe, localisation, diamètre mm, ABCDE)
    Med->>Form: Clic sur "Lancer l'Analyse Multimodale"
    Form->>Ctrl: analyze(PredictionRequest)
    Ctrl->>Repo: predict(request)

    Repo->>Provider: multipartPost('/predict', fields, fileBytes)
    Provider->>Provider: Injection Header (Authorization: Bearer <Token>)
    Provider->>API: HTTP POST multipart/form-data (Timeout 90s)
    
    API-->>Provider: 200 OK (JSON : predicted_class, confidence, risk_level, gradcam)
    Provider-->>Repo: PredictionResponse instanciée
    
    Repo->>Storage: addOfflineAnalysis(item) [Persistance locale GetStorage]
    Repo-->>Ctrl: Succès de l'inférence
    Ctrl->>Res: Get.offNamed(AppRoutes.RESULT, arguments)

    Med->>Res: Consultation du diagnostic (ex: MEL 91.4% - CRITICAL)
    Med->>Res: Bascule du bouton "Show Heatmap"
    Res-->>Med: Superposition dynamique de la carte d'attention Grad-CAM++
    
    Med->>Res: Clic sur "Doctor Confirmation / Feedback"
    Res->>Repo: submitFeedback(confirmed=true, biopsy=true)
    Repo->>Provider: PUT /api/v1/analyses/{id}/feedback
    Provider->>API: Enregistrement de la vérité terrain clinique
```

---

### 3.2 Séquence M-2 : Interception Réseau & Rafraîchissement Silencieux du Jeton (401 Auto-Refresh)

Ce diagramme formalise l'intercepteur de résilience réseau assurant qu'un médecin en consultation ne soit jamais expulsé brusquement de sa session clinique.

```mermaid
sequenceDiagram
    autonumber
    participant UI as 📱 Vue / Contrôleur Métier
    participant APIProv as 🌐 ApiProvider (Intercepteur)
    participant Storage as 💾 LocalStorageProvider
    participant Server as 🚀 Backend FastAPI (/api/v1)

    UI->>APIProv: get('/patients', requiresAuth: true)
    APIProv->>Storage: Lecture de accessToken
    Storage-->>APIProv: Access Token expiré (> 15 minutes)
    APIProv->>Server: GET /api/v1/patients (Bearer <AncienToken>)
    
    Server-->>APIProv: HTTP 401 Unauthorized (Token Expiré)
    Note over APIProv: Interception automatique de l'erreur 401
    
    APIProv->>APIProv: Entrée en section critique : refreshTokenSilently()
    APIProv->>Storage: Lecture de refreshToken
    Storage-->>APIProv: Refresh Token valide (7 jours)
    
    APIProv->>Server: POST /api/v1/auth/refresh {refresh_token}
    
    alt Rafraîchissement réussi
        Server-->>APIProv: 200 OK {access_token: <NouveauToken>, refresh_token: <NouveauToken>}
        APIProv->>Storage: saveAuthTokens(nouveau_access, nouveau_refresh)
        Note over APIProv: Rejeu transparent de la requête initiale
        APIProv->>Server: GET /api/v1/patients (Bearer <NouveauToken>)
        Server-->>APIProv: 200 OK (Liste des dossiers patients)
        APIProv-->>UI: Données restituées sans interruption perçue
    else Échec du rafraîchissement (Jeton révoqué ou session close)
        Server-->>APIProv: HTTP 401 / 403 Forbidden
        APIProv->>Storage: clearAuth()
        APIProv->>UI: Redirection forcée vers AppRoutes.LOGIN
    end
```

---

### 3.3 Séquence M-3 : Cycle Complet de Télé-expertise Mobile (Émission GP & Réponse Spécialiste)

```mermaid
sequenceDiagram
    autonumber
    actor GP as 🩺 Médecin Généraliste
    participant AppGP as 📱 App Mobile (Vue Généraliste)
    participant API as 🚀 Serveur FastAPI (/referrals)
    participant AppSpec as 📱 App Mobile (Vue Spécialiste)
    actor Spec as 👨‍⚕️ Dermatologue Spécialiste

    GP->>AppGP: Résultat d'analyse suspect (ex: HIGH ou INCONCLUSIVE)
    GP->>AppGP: Clic sur "Request Specialist Referral"
    AppGP->>AppGP: Renseignement de la note clinique & choix spécialiste
    AppGP->>API: POST /api/v1/referrals {analysis_id, referral_note}
    API-->>AppGP: 201 Created (Statut: PENDING)

    Note over API,AppSpec: Synchronisation de la boîte de réception
    Spec->>AppSpec: Sélectionne l'onglet "Télé-expertise" ➔ "Incoming"
    AppSpec->>API: GET /api/v1/referrals/received
    API-->>AppSpec: 200 OK (Liste des requêtes en attente)

    Spec->>AppSpec: Sélection d'un dossier & inspection de l'image et Grad-CAM
    Spec->>AppSpec: Clic sur "Provide Specialist Opinion"
    AppSpec->>AppSpec: Saisie du diagnostic d'expertise & conduite à tenir
    AppSpec->>API: PUT /api/v1/referrals/{id}/respond {response, status: completed}
    API-->>AppSpec: 200 OK (Statut: COMPLETED)

    GP->>AppGP: Actualisation de l'onglet "Sent Cases"
    AppGP->>API: GET /api/v1/referrals/sent
    API-->>AppGP: Dossier annoté avec la réponse officielle du dermatologue
```

---

### 3.4 Séquence M-4 : Consultation et Suivi Médical Citoyen par Scan QR Code

```mermaid
sequenceDiagram
    autonumber
    actor Patient as 👤 Patient / Citoyen
    participant App as 📱 Application Mobile
    participant Ctrl as ⚙️ QRFollowUpController
    participant Repo as 📦 DiagnosisRepository
    participant API as 🚀 Backend (/public/follow-up)

    Patient->>App: Clic sur "Patient QR Follow-up" depuis l'accueil
    App->>Ctrl: Initialisation de QRFollowUpView
    Patient->>Ctrl: Saisie ou scan du jeton éphémère (Token JWT)
    Ctrl->>Repo: getPatientQRFollowUp(token)
    Repo->>API: GET /api/v1/public/follow-up/{token} (Sans authentification)

    alt Jeton valide et non expiré
        API-->>Repo: 200 OK (PatientQRFollowUpModel JSON)
        Repo-->>Ctrl: Restitution des données de suivi
        Ctrl->>App: Affichage de la carte d'évaluation clinique
        Note over App,Patient: Affichage du diagnostic, de l'établissement traitant<br/>et de la date du prochain contrôle programmé
    else Jeton corrompu ou expiré
        API-->>Repo: 401 Unauthorized / 404 Not Found
        Repo-->>Ctrl: Valeur nulle retournée
        Ctrl->>App: Affichage du message d'alerte invitant à consulter son médecin
    end
```

---

## Chapitre 4 : Modélisation des États — Diagrammes d'États-Transitions

### 4.1 Machine à États : Navigation Applicative & Cycle de Session Clinique

```mermaid
stateDiagram-v2
    [*] --> SPLASH : Lancement de l'application
    
    state SPLASH {
        [*] --> VerificationStockage
        VerificationStockage : Contrôle isFirstTime & isAuthenticated
    }

    SPLASH --> ONBOARDING : isFirstTime == true
    ONBOARDING --> HOME_GUEST : Clic "Browse as Guest"
    ONBOARDING --> REGISTER : Clic "Register Clinician"
    ONBOARDING --> LOGIN : Clic "Sign In"

    SPLASH --> LOGIN : isAuthenticated == false
    LOGIN --> HOME_GUEST : Clic "Continuer en mode invité"
    
    SPLASH --> ControledStatut : isAuthenticated == true
    state ControledStatut {
        [*] --> VerificationProfil
    }

    ControledStatut --> PENDING_VERIFICATION : user.status == pending
    ControledStatut --> FORCE_CHANGE_PASSWORD : user.mustChangePassword == true
    ControledStatut --> MAIN_LAYOUT : user.status == active & role == doctor

    LOGIN --> PENDING_VERIFICATION : Compte en attente de validation
    LOGIN --> FORCE_CHANGE_PASSWORD : Mot de passe provisoire
    LOGIN --> MAIN_LAYOUT : Praticien actif vérifié

    state MAIN_LAYOUT {
        [*] --> Tab_Home
        Tab_Home : Consultation des statistiques et démarrage diagnostic
        Tab_Home --> Tab_Patients : Bascule vers le registre pseudonymisé
        Tab_Home --> Tab_Referrals : Bascule vers la télé-expertise
        Tab_Home --> Tab_Profile : Bascule vers les paramètres de profil
    }

    MAIN_LAYOUT --> HOME_GUEST : Déconnexion (logout)
```

---

### 4.2 Machine à États : Évaluation Visuelle du Risque Clinique à 5 Niveaux

```mermaid
stateDiagram-v2
    [*] --> IngestionResultat : Réception de PredictionResponse
    
    state IngestionResultat {
        [*] --> AnalyseConfiance
    }

    IngestionResultat --> INCONCLUSIVE : confidence < 0.50
    state INCONCLUSIVE {
        [*] --> RenduBadgeGris
        RenduBadgeGris : Couleur Slate (#64748B), Icône Alerte
        RenduBadgeGris : Activation automatique bouton Télé-expertise
    }

    IngestionResultat --> LOW : confidence >= 0.50 & classe in [NEV, SEK]
    state LOW {
        [*] --> RenduBadgeVert
        RenduBadgeVert : Couleur Émeraude (#22C55E), Recommandation surveillance
    }

    IngestionResultat --> MODERATE : confidence >= 0.50 & classe == ACK
    state MODERATE {
        [*] --> RenduBadgeAmbre
        RenduBadgeAmbre : Couleur Ambre (#F59E0B), Photoprotection stricte
    }

    IngestionResultat --> HIGH : confidence >= 0.50 & classe in [BCC, SCC]
    state HIGH {
        [*] --> RenduBadgeRouge
        RenduBadgeRouge : Couleur Rouge (#EF4444), Bouton Télé-expertise actif
    }

    IngestionResultat --> CRITICAL : confidence >= 0.50 & classe == MEL
    state CRITICAL {
        [*] --> RenduBadgeViolet
        RenduBadgeViolet : Couleur Pourpre (#7C3AED), Exérèse d'urgence
        RenduBadgeViolet : Bouton Télé-expertise prioritaire actif
    }

    INCONCLUSIVE --> [*]
    LOW --> [*]
    MODERATE --> [*]
    HIGH --> [*]
    CRITICAL --> [*]
```

---

## Chapitre 5 : Modélisation des Processus — Diagramme d'Activité Client Mobile

### 5.1 Diagramme d'Activité : Gestion de la Connectivité & Résilience Offline-First

```mermaid
flowchart TD
    Start(["Démarrage de l'action utilisateur"]) --> CheckNet{"Connectivité réseau active ?<br/>(ConnectivityService)"}
    
    CheckNet -- Oui --> CheckAuth{"Médecin authentifié ?<br/>(JWT présent)"}
    CheckNet -- Non --> ModeOffline["Basculement Mode Déconnecté (Offline)"]
    
    ModeOffline --> ReadCache["Lecture historique local (GetStorage)"]
    ReadCache --> ShowSnackbar["Notification d'information mode hors ligne"]
    ShowSnackbar --> EndOffline(["Fin consultation hors ligne"])

    CheckAuth -- Non --> FlowGuest["Mode Visiteur : Envoi direct sans patient_id"]
    FlowGuest --> ExecInference["Inférence standard sur /predict"]

    CheckAuth -- Oui --> ExecDoctor["Mode Praticien : Inclusion JWT + patient_id"]
    ExecDoctor --> ExecInference

    ExecInference --> CheckHTTP{"Code retour HTTP"}
    CheckHTTP -- 200 OK --> ParseData["Désérialisation PredictionResponse"]
    CheckHTTP -- 401 Unauthorized --> TriggerRefresh["Déclenchement Silent Token Refresh"]
    
    TriggerRefresh --> RefreshSuccess{"Rafraîchissement réussi ?"}
    RefreshSuccess -- Oui --> ExecInference
    RefreshSuccess -- Non --> ForceLogin["Redirection vers /login"]

    ParseData --> SaveLocal["Sauvegarde automatique dans cache GetStorage"]
    SaveLocal --> RenderUI["Affichage du diagnostic & Grad-CAM++"]
    RenderUI --> EndSuccess(["Fin de l'acte d'analyse"])
```

---

## Chapitre 6 : Modélisation Architecturale & Paquetages

### 6.1 Diagramme des Paquetages Modulaires (Feature-First)

```mermaid
flowchart TB
    subgraph App_Package ["Paquetage Applicatif Global : lib/"]
        
        subgraph Core_Layer ["Couche Transversale : core/"]
            Services["Services Singuliers :<br/>AuthService, ConnectivityService, PdfService"]
            Middleware["Garde de Navigation :<br/>AuthMiddleware"]
            Utils["Utilitaires :<br/>Constants, DateUtils, ImageUtils"]
        end

        subgraph Config_Layer ["Couche Configuration : app/"]
            Routes["Routage :<br/>AppRoutes, AppPages"]
            Theme["Thème & Chartes :<br/>AppTheme, AppColors"]
            Translations["i18n Trilingue :<br/>ar.dart, fr.dart, en.dart"]
            ApiConfig["Configuration API :<br/>ApiConstants, ApiConfig"]
        end

        subgraph Data_Layer ["Couche Données : data/"]
            Models["Modèles Métier :<br/>PredictionRequest, PredictionResponse, PatientModel, ReferralModel"]
            Repositories["Dépôts Abstraction :<br/>DiagnosisRepository, ReferralRepository, PatientRepository, HistoryRepository"]
            Providers["Fournisseurs Bas Niveau :<br/>ApiProvider (HTTP), LocalStorageProvider (GetStorage)"]
        end

        subgraph Modules_Layer ["Couche Modules Fonctionnels : modules/"]
            direction TB
            Mod_Auth["Module Auth (Login, Register, Pending)"]
            Mod_Layout["Module MainLayout (4 Tabs)"]
            Mod_Home["Module Home (Clinique & Guest)"]
            Mod_Consent["Module Consentement Éclairé"]
            Mod_Camera["Module Caméra Dermoscopique"]
            Mod_Form["Module Formulaire Clinique 7 Caractéristiques"]
            Mod_Result["Module Résultat & Grad-CAM++ Overlay"]
            Mod_Patients["Module Patients & Frise Chronologique"]
            Mod_Referrals["Module Télé-expertise (GP & Spécialiste)"]
            Mod_QR["Module Suivi Patient QR Code"]
            Mod_Education["Module ABCDE Trilingue"]
            Mod_Directory["Module Annuaire Public des Médecins"]
        end

    end

    %% Dépendances entre paquetages
    Modules_Layer ..> Data_Layer : consomme référentiels et modèles
    Modules_Layer ..> Core_Layer : utilise services et gardes
    Modules_Layer ..> Config_Layer : observe thèmes et routes
    Data_Layer ..> Config_Layer : lit constantes API
    Core_Layer ..> Data_Layer : pilote sessions et stockage
```

---

### 6.2 Matrice de Traçabilité des Exigences Mobiles

| Code Exigence | Intitulé Spécifique Mobile | Artefact UML Référent | Implémentation Logicielle Dart |
| :--- | :--- | :--- | :--- |
| **REQ-M-01** | Prise de vue dermoscopique avec cercle guide et contrôle qualité | Cas d'utilisation CU-M01, Diagramme Séquence M-1 | `CameraView`, `CameraGetxController` |
| **REQ-M-02** | Consentement éclairé obligatoire préalable à tout transfert | Diagramme de Séquence M-1, Machine à états | `ConsentView`, `ConsentController` |
| **REQ-M-03** | Saisie des 7 variables cliniques et sélection d'échantillons de test | Diagramme de Classes, Formulaire Clinique | `ClinicalFormView`, `AgeSlider`, `YesNoSelector` |
| **REQ-M-04** | Rendu explicable de la carte thermique Grad-CAM++ par bascule | Diagramme de Séquence M-1 | `ResultView._buildImageViewer()` |
| **REQ-M-05** | Affichage du badge de risque à 5 niveaux avec gestion d'incertitude | Machine à États 4.2 | `RiskLevelBadge` (avec cas `INCONCLUSIVE`) |
| **REQ-M-06** | Émission et suivi de télé-expertise médicale par le généraliste | Cas d'utilisation CU-M01, Diagramme Séquence M-3 | `ReferralsView._buildSentReferralsTab()` |
| **REQ-M-07** | Traitement et réponse formelle à l'expertise par le dermatologue | Cas d'utilisation CU-M02, Diagramme Séquence M-3 | `ReferralsView._buildReceivedReferralsTab()` |
| **REQ-M-08** | Gestion de dossiers patients pseudonymisés et chronologie lésionnelle | Diagramme de Classes, Modules Patients | `PatientsView`, `PatientDetailView` |
| **REQ-M-09** | Vérification publique de suivi post-consultation par QR code | Cas d'utilisation CU-M03, Diagramme Séquence M-4 | `QRFollowUpView`, `QRFollowUpController` |
| **REQ-M-10** | Résilience déconnectée et mise en cache transparente | Diagramme d'Activité 5.1 | `LocalStorageProvider`, `HistoryRepository` |
| **REQ-M-11** | Double jeton JWT et rafraîchissement automatique silencieux sur 401 | Diagramme de Séquence M-2 | `ApiProvider.refreshTokenSilently()` |
| **REQ-M-12** | Support trilingue intégral (AR/FR/EN) avec support RTL | Paquetage Configuration | `AppTranslations`, `ar.dart`, `fr.dart`, `en.dart` |

---

## Conclusion de la Modélisation Mobile

Cette spécification d'ingénierie logicielle fournit la modélisation formelle et exhaustive du client mobile **MedAssist AI V2** sous Flutter et GetX.

Elle démontre l'alignement rigoureux entre les objectifs cliniques (dépistage précoce, explicabilité visuelle, télé-expertise médicale décentralisée), les impératifs éthiques et réglementaires (consentement éclairé, pseudonymisation, gestion du doute algorithmique) et l'excellence de conception logicielle requise pour l'obtention du diplôme de **Master 2 en Génie Logiciel et Applications Avancées (GLAA)** dans le cadre du projet **Diplôme-Startup (Arrêté Ministériel 1275)**.

