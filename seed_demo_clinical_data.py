"""
seed_demo_clinical_data.py
Populates realistic clinical demo data into PostgreSQL for MedAssist AI V2:
- 5 Clinicians (GPs and Specialist Dermatologists across Algerian Wilayas: Alger, Oran, Skikda, Sétif)
- 1 Pending verification doctor for admin workflow demo
- 6 Pseudonymous Patients with full demographic and clinical histories
- 6 Diagnostic Analyses covering all 6 classes (MEL, BCC, SCC, ACK, SEK, NEV) with PAD-UFES-20 metadata
- 3 Telemedicine Referrals (Completed, Under Review, Pending)
- Governance Audit Logs
"""

import sys
import os
import uuid
from datetime import datetime, timezone, date, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.db_models.user import User, DoctorProfile, UserRole, UserStatus, DoctorType
from app.db_models.patient import Patient, PatientSex
from app.db_models.analysis import AnalysisRecord
from app.db_models.referral import Referral, ReferralStatus
from app.db_models.audit import AuditLog

def seed_clinical_data():
    db = SessionLocal()
    try:
        print("🌱 Seeding realistic clinical demo data into PostgreSQL...")

        # ── 1. Clinicians & Accounts ──────────────────────────────────────────
        doctors_data = [
            {
                "email": "doctor.amara@medassist.dz",
                "password": "DoctorPass123!",
                "role": UserRole.DOCTOR,
                "status": UserStatus.ACTIVE,
                "full_name": "Dr. Amara Yacine",
                "doctor_type": DoctorType.GENERAL_PRACTITIONER,
                "institution": "Polyclinique Mohamed Seghir Benali, Skikda",
                "wilaya": "21",
                "phone": "0550 12 34 56",
            },
            {
                "email": "dr.mansouri@chu-alger.dz",
                "password": "DoctorPass123!",
                "role": UserRole.DOCTOR,
                "status": UserStatus.ACTIVE,
                "full_name": "Pr. Mansouri Karim",
                "doctor_type": DoctorType.SPECIALIST_DERMATOLOGIST,
                "institution": "CHU Mustapha Bacha, Service Dermatologie, Alger",
                "wilaya": "16",
                "phone": "0551 98 76 54",
            },
            {
                "email": "dr.benali@chu-oran.dz",
                "password": "DoctorPass123!",
                "role": UserRole.DOCTOR,
                "status": UserStatus.ACTIVE,
                "full_name": "Dr. Benali Fatima Zohra",
                "doctor_type": DoctorType.SPECIALIST_DERMATOLOGIST,
                "institution": "EHU 1er Novembre 1954, Oran",
                "wilaya": "31",
                "phone": "0552 34 56 78",
            },
            {
                "email": "dr.khellaf@clinic-setif.dz",
                "password": "DoctorPass123!",
                "role": UserRole.DOCTOR,
                "status": UserStatus.ACTIVE,
                "full_name": "Dr. Khellaf Mourad",
                "doctor_type": DoctorType.GENERAL_PRACTITIONER,
                "institution": "Clinique El Hikma, Sétif",
                "wilaya": "19",
                "phone": "0553 45 67 89",
            },
            {
                "email": "dr.hamidi.pending@hospital.dz",
                "password": "DoctorPass123!",
                "role": UserRole.DOCTOR,
                "status": UserStatus.PENDING_VERIFICATION,
                "full_name": "Dr. Hamidi Selim",
                "doctor_type": DoctorType.GENERAL_PRACTITIONER,
                "institution": "EPH Skikda",
                "wilaya": "21",
                "phone": "0554 56 78 90",
            },
        ]

        clinicians = {}
        for doc in doctors_data:
            existing = db.query(User).filter(User.email == doc["email"]).first()
            if not existing:
                user = User(
                    email=doc["email"],
                    password_hash=hash_password(doc["password"]),
                    role=doc["role"],
                    status=doc["status"],
                )
                db.add(user)
                db.flush()

                profile = DoctorProfile(
                    user_id=user.id,
                    full_name=doc["full_name"],
                    doctor_type=doc["doctor_type"],
                    institution_name=doc["institution"],
                    wilaya=doc["wilaya"],
                    phone=doc["phone"],
                )
                db.add(profile)
                clinicians[doc["email"]] = user
                print(f"  + Created doctor: {doc['full_name']} ({doc['email']})")
            else:
                clinicians[doc["email"]] = existing
                print(f"  * Doctor already exists: {existing.email}")

        db.commit()

        # Find admin
        admin_user = db.query(User).filter(User.role == UserRole.ADMIN).first()

        # ── 2. Pseudonymous Patients ──────────────────────────────────────────
        patients_data = [
            {
                "code": "DZ-21-P0046",
                "birth_year": 1971,
                "sex": PatientSex.FEMALE,
                "notes": "55yo female, agricultural worker from Collo (Skikda), prolonged UV sun exposure. Ulcerated lesion on anterior neck (PAD-UFES-20 Case PAT_46).",
                "doctor": clinicians["doctor.amara@medassist.dz"],
            },
            {
                "code": "DZ-16-P0102",
                "birth_year": 1964,
                "sex": PatientSex.MALE,
                "notes": "62yo male, family history of malignant melanoma, irregular asymmetrical dark macule on upper thoracic back.",
                "doctor": clinicians["doctor.amara@medassist.dz"],
            },
            {
                "code": "DZ-31-P0088",
                "birth_year": 1988,
                "sex": PatientSex.FEMALE,
                "notes": "38yo female from Oran, changing pigmented lesion on right forearm with recent size progression over 3 months.",
                "doctor": clinicians["dr.mansouri@chu-alger.dz"],
            },
            {
                "code": "DZ-19-P0055",
                "birth_year": 1955,
                "sex": PatientSex.MALE,
                "notes": "71yo male, retired builder from Sétif, multiple actinic keratoses and hyperkeratotic nodular lesion on vertex scalp.",
                "doctor": clinicians["dr.khellaf@clinic-setif.dz"],
            },
            {
                "code": "DZ-21-P0120",
                "birth_year": 1997,
                "sex": PatientSex.FEMALE,
                "notes": "29yo female from Skikda, routine annual screening. Uniform benign melanocytic macule on left anterior shoulder.",
                "doctor": clinicians["doctor.amara@medassist.dz"],
            },
            {
                "code": "DZ-06-P0073",
                "birth_year": 1973,
                "sex": PatientSex.MALE,
                "notes": "53yo male from Béjaïa, asymptomatic stuck-on hyperpigmented plaque on lumbar back. Suspected seborrheic keratosis.",
                "doctor": clinicians["doctor.amara@medassist.dz"],
            },
        ]

        patients = {}
        for pdata in patients_data:
            existing_p = db.query(Patient).filter(Patient.patient_code == pdata["code"]).first()
            if not existing_p:
                patient = Patient(
                    patient_code=pdata["code"],
                    birth_year=pdata["birth_year"],
                    sex=pdata["sex"],
                    notes=pdata["notes"],
                    created_by_doctor_id=pdata["doctor"].id,
                )
                db.add(patient)
                db.flush()
                patients[pdata["code"]] = patient
                print(f"  + Created patient: {pdata['code']}")
            else:
                patients[pdata["code"]] = existing_p
                print(f"  * Patient exists: {existing_p.patient_code}")

        db.commit()

        # ── 3. Clinical Analyses (All 6 Classes) ──────────────────────────────
        analyses_data = [
            # 1. Melanoma (MEL) - Critical Risk
            {
                "doctor": clinicians["doctor.amara@medassist.dz"],
                "patient": patients["DZ-16-P0102"],
                "lesion_tag": "Upper Back Lesion (11.5mm)",
                "predicted_class": "MEL",
                "confidence": 0.892,
                "all_probabilities": {
                    "MEL": 0.892, "NEV": 0.054, "SEK": 0.021, "BCC": 0.015, "ACK": 0.010, "SCC": 0.008
                },
                "risk_level": "CRITICAL",
                "risk_escalated": True,
                "clinical_data": {
                    "age": 62, "sex": "male", "localization": "back",
                    "diameter_1": 11.5, "grew": True, "bleed": True,
                    "elevation": True, "skin_cancer_history": True
                },
                "image_key": "analyses/sample_mel_clinical.jpg",
                "gradcam_key": "analyses/sample_mel_gradcam.jpg",
                "doctor_confirmed": True,
                "doctor_diagnosis": "Superficial Spreading Melanoma (High Breslow suspected)",
                "biopsy_performed": True,
                "biopsy_result": "Malignant melanoma confirmed, Breslow thickness 1.2mm, Clark Level IV",
                "next_followup_date": date.today() + timedelta(days=14),
                "created_at": datetime.now(timezone.utc) - timedelta(days=5),
            },
            # 2. Basal Cell Carcinoma (BCC) - High Risk (PAD-UFES-20 PAT_46)
            {
                "doctor": clinicians["doctor.amara@medassist.dz"],
                "patient": patients["DZ-21-P0046"],
                "lesion_tag": "Anterior Neck Nodule (PAT_46)",
                "predicted_class": "BCC",
                "confidence": 0.785,
                "all_probabilities": {
                    "BCC": 0.785, "SCC": 0.124, "ACK": 0.051, "SEK": 0.018, "NEV": 0.012, "MEL": 0.010
                },
                "risk_level": "HIGH",
                "risk_escalated": False,
                "clinical_data": {
                    "age": 55, "sex": "female", "localization": "neck",
                    "diameter_1": 3.0, "grew": True, "bleed": True,
                    "elevation": True, "skin_cancer_history": True
                },
                "image_key": "analyses/PAT_46_881_939.png",
                "gradcam_key": "analyses/PAT_46_gradcam.png",
                "doctor_confirmed": True,
                "doctor_diagnosis": "Nodular Basal Cell Carcinoma with central ulceration",
                "biopsy_performed": True,
                "biopsy_result": "Infiltrative BCC, surgical excision scheduled",
                "next_followup_date": date.today() + timedelta(days=30),
                "created_at": datetime.now(timezone.utc) - timedelta(days=3),
            },
            # 3. Squamous Cell Carcinoma (SCC) - High Risk
            {
                "doctor": clinicians["dr.khellaf@clinic-setif.dz"],
                "patient": patients["DZ-19-P0055"],
                "lesion_tag": "Scalp Hyperkeratotic Mass",
                "predicted_class": "SCC",
                "confidence": 0.814,
                "all_probabilities": {
                    "SCC": 0.814, "ACK": 0.112, "BCC": 0.045, "SEK": 0.015, "MEL": 0.009, "NEV": 0.005
                },
                "risk_level": "HIGH",
                "risk_escalated": False,
                "clinical_data": {
                    "age": 71, "sex": "male", "localization": "scalp",
                    "diameter_1": 14.0, "grew": True, "bleed": False,
                    "elevation": True, "skin_cancer_history": False
                },
                "image_key": "analyses/sample_scc_clinical.jpg",
                "gradcam_key": "analyses/sample_scc_gradcam.jpg",
                "doctor_confirmed": None,
                "doctor_diagnosis": "Awaiting Telemedicine Second Opinion",
                "biopsy_performed": False,
                "biopsy_result": None,
                "next_followup_date": date.today() + timedelta(days=7),
                "created_at": datetime.now(timezone.utc) - timedelta(days=2),
            },
            # 4. Actinic Keratosis (ACK) - Moderate Risk (Evolution timeline for DZ-19-P0055)
            {
                "doctor": clinicians["dr.khellaf@clinic-setif.dz"],
                "patient": patients["DZ-19-P0055"],
                "lesion_tag": "Right Forehead Erythematous Plaque",
                "predicted_class": "ACK",
                "confidence": 0.865,
                "all_probabilities": {
                    "ACK": 0.865, "SCC": 0.082, "BCC": 0.031, "SEK": 0.012, "NEV": 0.006, "MEL": 0.004
                },
                "risk_level": "MODERATE",
                "risk_escalated": False,
                "clinical_data": {
                    "age": 71, "sex": "male", "localization": "face",
                    "diameter_1": 6.0, "grew": False, "bleed": False,
                    "elevation": False, "skin_cancer_history": False
                },
                "image_key": "analyses/sample_ack_clinical.jpg",
                "gradcam_key": "analyses/sample_ack_gradcam.jpg",
                "doctor_confirmed": True,
                "doctor_diagnosis": "Pre-malignant Actinic Keratosis, Cryotherapy applied",
                "biopsy_performed": False,
                "biopsy_result": None,
                "next_followup_date": date.today() + timedelta(days=90),
                "created_at": datetime.now(timezone.utc) - timedelta(days=1),
            },
            # 5. Seborrheic Keratosis (SEK) - Low Risk
            {
                "doctor": clinicians["doctor.amara@medassist.dz"],
                "patient": patients["DZ-06-P0073"],
                "lesion_tag": "Mid-back Verrucous Plaque",
                "predicted_class": "SEK",
                "confidence": 0.932,
                "all_probabilities": {
                    "SEK": 0.932, "NEV": 0.038, "MEL": 0.015, "BCC": 0.008, "ACK": 0.004, "SCC": 0.003
                },
                "risk_level": "LOW",
                "risk_escalated": False,
                "clinical_data": {
                    "age": 53, "sex": "male", "localization": "back",
                    "diameter_1": 8.0, "grew": False, "bleed": False,
                    "elevation": True, "skin_cancer_history": False
                },
                "image_key": "analyses/sample_sek_clinical.jpg",
                "gradcam_key": "analyses/sample_sek_gradcam.jpg",
                "doctor_confirmed": True,
                "doctor_diagnosis": "Benign Seborrheic Keratosis — reassure patient",
                "biopsy_performed": False,
                "biopsy_result": None,
                "next_followup_date": None,
                "created_at": datetime.now(timezone.utc) - timedelta(hours=18),
            },
            # 6. Nevus (NEV) - Low Risk
            {
                "doctor": clinicians["doctor.amara@medassist.dz"],
                "patient": patients["DZ-21-P0120"],
                "lesion_tag": "Left Shoulder Macule",
                "predicted_class": "NEV",
                "confidence": 0.958,
                "all_probabilities": {
                    "NEV": 0.958, "SEK": 0.022, "MEL": 0.011, "BCC": 0.005, "ACK": 0.002, "SCC": 0.002
                },
                "risk_level": "LOW",
                "risk_escalated": False,
                "clinical_data": {
                    "age": 29, "sex": "female", "localization": "shoulder",
                    "diameter_1": 4.0, "grew": False, "bleed": False,
                    "elevation": False, "skin_cancer_history": False
                },
                "image_key": "analyses/sample_nev_clinical.jpg",
                "gradcam_key": "analyses/sample_nev_gradcam.jpg",
                "doctor_confirmed": True,
                "doctor_diagnosis": "Benign Junctional Melanocytic Nevus",
                "biopsy_performed": False,
                "biopsy_result": None,
                "next_followup_date": date.today() + timedelta(days=365),
                "created_at": datetime.now(timezone.utc) - timedelta(hours=6),
            },
        ]

        analyses = []
        for adata in analyses_data:
            # Check if analysis exists for patient and lesion tag
            existing_a = db.query(AnalysisRecord).filter(
                AnalysisRecord.patient_id == adata["patient"].id,
                AnalysisRecord.lesion_tag == adata["lesion_tag"]
            ).first()

            if not existing_a:
                rec = AnalysisRecord(
                    doctor_id=adata["doctor"].id,
                    patient_id=adata["patient"].id,
                    lesion_tag=adata["lesion_tag"],
                    image_storage_key=adata["image_key"],
                    gradcam_storage_key=adata["gradcam_key"],
                    clinical_data=adata["clinical_data"],
                    predicted_class=adata["predicted_class"],
                    confidence=adata["confidence"],
                    all_probabilities=adata["all_probabilities"],
                    risk_level=adata["risk_level"],
                    risk_escalated=adata["risk_escalated"],
                    recommendations=[
                        f"Primary classification: {adata['predicted_class']}",
                        "Correlation with dermoscopy and ABCDE clinical criteria recommended.",
                    ],
                    inference_time_ms=105.4,
                    model_version="V6.0",
                    doctor_confirmed=adata["doctor_confirmed"],
                    doctor_diagnosis=adata["doctor_diagnosis"],
                    biopsy_performed=adata["biopsy_performed"],
                    biopsy_result=adata["biopsy_result"],
                    next_followup_date=adata["next_followup_date"],
                    created_at=adata["created_at"],
                )
                db.add(rec)
                db.flush()
                analyses.append(rec)
                print(f"  + Created analysis: {adata['predicted_class']} ({adata['risk_level']}) for patient {adata['patient'].patient_code}")
            else:
                analyses.append(existing_a)
                print(f"  * Analysis exists: {existing_a.id}")

        db.commit()

        # ── 4. Telemedicine Referrals ──────────────────────────────────────────
        # Referral 1: Melanoma Case -> Completed with specialist response
        mel_analysis = analyses[0]
        ref1 = db.query(Referral).filter(Referral.analysis_id == mel_analysis.id).first()
        if not ref1:
            ref1 = Referral(
                analysis_id=mel_analysis.id,
                referring_doctor_id=clinicians["doctor.amara@medassist.dz"].id,
                specialist_id=clinicians["dr.mansouri@chu-alger.dz"].id,
                status=ReferralStatus.COMPLETED,
                referral_note="Urgent referral: 62yo male presenting with rapid changes in a pigmented dorsal lesion. Multimodal AI confidence 89.2% for Melanoma. Please review for hospital admission.",
                specialist_response="Reviewed dermoscopy and Grad-CAM++ saliency focus on the asymmetric peripheral borders. High suspicion of invasive melanoma (Breslow > 1mm). Recommend urgent 2cm surgical margin wide excision with sentinel lymph node evaluation. Case accepted for admission at CHU Mustapha Bacha.",
                responded_at=datetime.now(timezone.utc) - timedelta(days=4),
                created_at=datetime.now(timezone.utc) - timedelta(days=5),
            )
            db.add(ref1)
            print("  + Created Referral 1 (COMPLETED): Melanoma case to Pr. Mansouri")

        # Referral 2: BCC Case -> Accepted / In review by Dr. Benali
        bcc_analysis = analyses[1]
        ref2 = db.query(Referral).filter(Referral.analysis_id == bcc_analysis.id).first()
        if not ref2:
            ref2 = Referral(
                analysis_id=bcc_analysis.id,
                referring_doctor_id=clinicians["doctor.amara@medassist.dz"].id,
                specialist_id=clinicians["dr.benali@chu-oran.dz"].id,
                status=ReferralStatus.ACCEPTED,
                referral_note="Patient DZ-21-P0046 (PAT_46) with 3mm bleeding ulcerated nodule on neck. High confidence BCC. Inquiring regarding suitability for Mohs micrographic surgery versus standard 4mm margin excision.",
                specialist_response=None,
                created_at=datetime.now(timezone.utc) - timedelta(days=2),
            )
            db.add(ref2)
            print("  + Created Referral 2 (ACCEPTED): BCC case to Dr. Benali")

        # Referral 3: SCC Case -> Pending in unassigned general queue
        scc_analysis = analyses[2]
        ref3 = db.query(Referral).filter(Referral.analysis_id == scc_analysis.id).first()
        if not ref3:
            ref3 = Referral(
                analysis_id=scc_analysis.id,
                referring_doctor_id=clinicians["dr.khellaf@clinic-setif.dz"].id,
                specialist_id=None,  # Unassigned queue
                status=ReferralStatus.PENDING,
                referral_note="71yo builder with painful rapidly expanding 14mm scalp nodule. High confidence Squamous Cell Carcinoma (81.4%). Requires specialist evaluation.",
                specialist_response=None,
                created_at=datetime.now(timezone.utc) - timedelta(hours=12),
            )
            db.add(ref3)
            print("  + Created Referral 3 (PENDING): SCC case in specialist pool")

        db.commit()

        # ── 5. Security Audit Logs ─────────────────────────────────────────────
        if admin_user:
            audit_events = [
                ("DOCTOR_VERIFY", clinicians["doctor.amara@medassist.dz"].id, {"email": "doctor.amara@medassist.dz", "name": "Dr. Amara Yacine"}),
                ("DOCTOR_VERIFY", clinicians["dr.mansouri@chu-alger.dz"].id, {"email": "dr.mansouri@chu-alger.dz", "name": "Pr. Mansouri Karim"}),
                ("DOCTOR_VERIFY", clinicians["dr.benali@chu-oran.dz"].id, {"email": "dr.benali@chu-oran.dz", "name": "Dr. Benali Fatima Zohra"}),
                ("USER_STATUS_ACTIVE", clinicians["dr.khellaf@clinic-setif.dz"].id, {"email": "dr.khellaf@clinic-setif.dz"}),
            ]
            for act, res_id, details in audit_events:
                db.add(
                    AuditLog(
                        user_id=admin_user.id,
                        action=act,
                        resource_type="USER",
                        resource_id=res_id,
                        details=details,
                        created_at=datetime.now(timezone.utc) - timedelta(days=7),
                    )
                )
            db.commit()
            print("  + Seeded governance audit logs.")

        print("✅ Clinical demo data seeding completed successfully!")

    except Exception as exc:
        db.rollback()
        print(f"❌ Error during seeding: {exc}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_clinical_data()
