# 📋 وثيقة التسليم والانتقال إلى المرحلة 2 (Handover to Phase 2: Authentication System)
## مشروع MedAssist AI V2 — فرع `feature/v2-telemedicine-expansion`

> **تاريخ التحديث**: 31 أكتوبر 2026  
> **حالة المشروع الحالية**: المرحلة 0 مكتملة 100% | المرحلة 1 مكتملة 100% ومُختبرة | جاهز تماماً للمرحلة 2  
> **حالة الاختبارات الحالية**: `38/38 PASSED` بنجاح كامل بدون أي تراجع (Zero Regressions)

---

## 1. 🌍 حالة البيئة والبنية التحتية (Infrastructure & Environment)

| البند | القيمة / الحالة | ملاحظات هامة |
|-------|-----------------|--------------|
| **مجلد العمل (Backend)** | `c:\Users\PC\Desktop\m2GLAA MF\backend_App_MedAssist_AI` | |
| **Git Branch** | `feature/v2-telemedicine-expansion` | تم العمل عليه واختباره بالكامل |
| **Python Virtualenv** | `.\venv\Scripts\python.exe` (Python 3.12) | جميع الحزم مثبتة مسبقاً |
| **PostgreSQL** | يعمل كخدمة ويندوز محلية على المنفذ `5432` | قاعدة البيانات: `medassist_db`<br>المستخدم: `medassist` / كلمة المرور: `secret` (Superuser) |
| **Connection URL** | `postgresql+psycopg2://medassist:secret@localhost:5432/medassist_db` | متطابق في `.env` و `config.py` و `docker-compose.yml` |
| **MinIO** | المنفذ `9000` (API) و `9001` (Console) | تم إعداده وخدمة `StorageService` جاهزة |

---

## 2. 🗄️ إنجازات المرحلة 1 (نماذج قاعدة البيانات والتهجير)

### 2.1 النماذج المنشأة في `app/db_models/`:
1. **[`app/db_models/user.py`](file:///c:/Users/PC/Desktop/m2GLAA%20MF/backend_App_MedAssist_AI/app/db_models/user.py)**:
   - `User`: يحتوي `id` (UUID), `email` (Unique), `password_hash`, `role` (`doctor`, `admin`), `status` (`pending_verification`, `active`, `suspended`), `must_change_password`, `created_at`, `last_login`.
   - `DoctorProfile`: علاقة 1:1 مع `User`، `doctor_type` (`general_practitioner`, `specialist_dermatologist`), `specialization`, `license_number`, `institution_name`, `phone`, `wilaya`, `avatar_url`, `updated_at` (مع `server_onupdate=FetchedValue()`).
   - `RefreshToken`: `token_hash` فريد (`unique=True`, `index=True`)، `expires_at`, `is_revoked`, `created_at`.
2. **[`app/db_models/patient.py`](file:///c:/Users/PC/Desktop/m2GLAA%20MF/backend_App_MedAssist_AI/app/db_models/patient.py)**:
   - `Patient`: `patient_code` (مجهّل Unique), `birth_year` (لحساب العمر ديناميكياً), `sex` (`male`, `female`), `deleted_at` (Soft Delete).
3. **[`app/db_models/analysis.py`](file:///c:/Users/PC/Desktop/m2GLAA%20MF/backend_App_MedAssist_AI/app/db_models/analysis.py)**:
   - `AnalysisRecord`: `clinical_data` (JSONB), `all_probabilities` (JSONB), `risk_level` (نصي يدعم 5 مستويات مع `INCONCLUSIVE`), `risk_escalated`, `recommendations`, MinIO keys (`image_storage_key`, `gradcam_storage_key`), حقول تعقيب الطبيب (`doctor_confirmed`, `doctor_diagnosis`, `biopsy_performed`, `biopsy_result`, `next_followup_date`).
4. **[`app/db_models/referral.py`](file:///c:/Users/PC/Desktop/m2GLAA%20MF/backend_App_MedAssist_AI/app/db_models/referral.py)**:
   - `Referral`: إحالة فريدة لكل فحص (`analysis_id` Unique FK)، تربط الطبيب العام `referring_doctor_id` بالأخصائي `specialist_id`، مع `status` (`pending`, `accepted`, `completed`, `cancelled`).
5. **[`app/db_models/audit.py`](file:///c:/Users/PC/Desktop/m2GLAA%20MF/backend_App_MedAssist_AI/app/db_models/audit.py)**:
   - `AuditLog`: رقابة للعمليات الأمنية والإدارية مع `user_id` (يدعم NULL للعمليات النظامية)، و `details` (JSONB).
6. **[`app/db_models/__init__.py`](file:///c:/Users/PC/Desktop/m2GLAA%20MF/backend_App_MedAssist_AI/app/db_models/__init__.py)**: تصدير مركزي لكافة النماذج والـ Enums.

### 2.2 الهجرات المطبقة في Alembic (`alembic/versions/`):
1. `bfc9459897b9_create_initial_v2_tables.py`: إنشاء الجداول السبعة كاملة مع ENUMs بأحرف صغيرة ودعم تنظيفها عند التراجع (`downgrade`).
2. `643ff0b2a439_add_unique_refresh_token_hash.py`: ترقية فهرس `token_hash` في جدول `refresh_tokens` إلى قيد فريد `unique=True`.

### 2.3 حساب الأدمن الأولي (Seed):
- تم إنشاء [`app/db_models/seed.py`](file:///c:/Users/PC/Desktop/m2GLAA%20MF/backend_App_MedAssist_AI/app/db_models/seed.py) مع دالة `create_initial_admin(db)` التي تُنشئ حساباً أولياً تلقائياً إذا لم يكن موجوداً:
  - **Email**: `admin@medassist.dz` (قابلة للتعديل عبر `INITIAL_ADMIN_EMAIL`)
  - **Password**: `Admin@MedAssist2026!` (قابلة للتعديل عبر `INITIAL_ADMIN_PASSWORD`)
- تم ربطها في Lifespan داخل `app/main.py`.

---

## 3. 🎯 مهام المرحلة 2 المطلوبة بالتفصيل (Phase 2 Action Plan)

وفقاً لوثيقة `docs_v2/workplan_backend_dashboard.md`، تنقسم المرحلة 2 إلى 4 أجزاء رئيسية:

### الخطوة 2.1 — تحديث وحدة الأمان والرموز (`app/core/security.py`)
- الحفاظ على دوال الـ Middleware الحالية (`add_security_middleware`, `add_request_size_limit`).
- تحديث CORS methods لإضافة `PUT` و `DELETE` (لأن `/change-password` يعتمد `PUT`).
- إضافة دوال التشفير باستخدام `passlib.context.CryptContext(schemes=["bcrypt"])`:
  - `hash_password(password: str) -> str`
  - `verify_password(plain: str, hashed: str) -> bool`
- إضافة دوال إدارة رموز الـ JWT (باستخدام `import jwt`):
  - `create_access_token(user_id: UUID, role: str) -> str` (صلاحية 15 دقيقة)
  - `create_refresh_token(user_id: UUID) -> tuple[str, str]` (صلاحية 7 أيام — يعيد الرمز الخام وهاش SHA-256 للحفظ)
  - `create_qr_token(analysis_id: UUID) -> str` (صلاحية 30 يوماً للمريض)
  - `decode_token(token: str) -> dict` (التحقق وإرجاع الـ payload أو رفع 401)

### الخطوة 2.2 — إنشاء مخططات البيانات للتوثيق (`app/schemas/auth.py`)
- إنشاء مجلد `app/schemas/` إذا لم يكن موجوداً.
- إنشاء المخططات (Pydantic Models):
  - `RegisterDoctorRequest`: بريد، كلمة مرور (min 8 chars)، الاسم الكامل، نوع الطبيب (`general_practitioner` أو `specialist_dermatologist`)، التخصص، رقم العمادة، المؤسسة، الهاتف، الولاية.
  - `LoginRequest`: بريد، كلمة مرور.
  - `TokenResponse`: `access_token`, `refresh_token`, `token_type = "bearer"`, `expires_in`, `must_change_password: bool`.
  - `RefreshTokenRequest`: `refresh_token: str`.
  - `ChangePasswordRequest`: `current_password`, `new_password`.
  - `UserResponse` و `DoctorProfileResponse` (مع إخفاء `password_hash` و `token_hash`).

### الخطوة 2.3 — تبعيات التحقق والحماية (`app/api/deps.py`)
- إنشاء ملف `app/api/deps.py` ليحتوي:
  - `get_db() -> Generator[Session]`: يوفّر جلسة قاعدة البيانات.
  - `get_current_user`: يفك رمز الـ Access Token (عبر `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")`) ويجلب كائن `User` النشط من DB.
  - `get_current_active_doctor`: يتحقق من أن `role == UserRole.DOCTOR` وأن `status == UserStatus.ACTIVE` (يرفع 403 إذا كان معلقاً أو بانتظار التفعيل).
  - `get_current_specialist`: يتحقق من أن الطبيب يحمل صفة `DoctorType.SPECIALIST_DERMATOLOGIST`.
  - `require_admin`: يتحقق من أن `role == UserRole.ADMIN`.

### الخطوة 2.4 — مسارات التوثيق (`app/api/v1/endpoints/auth.py`)
- إنشاء المجلدات: `app/api/v1/endpoints/`.
- برمجة المسارات الستة:
  1. `POST /api/v1/auth/register`:
     - التحقق من عدم تكرار البريد ورقم العمادة.
     - تشفير كلمة المرور وتعيين `status = pending_verification`.
     - إنشاء سجل المستخدم وسجل `DoctorProfile`.
     - تسجيل عملية الرقابة `AuditLog`.
  2. `POST /api/v1/auth/login`:
     - التحقق من البريد وكلمة المرور.
     - فحص ما إذا كان الحساب معلقاً (`suspended`).
     - تحديث `last_login`.
     - توليد Access Token و Refresh Token وحفظ هاش الأخير في `refresh_tokens`.
     - تسجيل `AuditLog`.
     - إرجاع الرموز مع علم `must_change_password`.
  3. `POST /api/v1/auth/refresh`:
     - فحص رمز التجديد ومطابقة الهاش في قاعدة البيانات والتأكد من عدم إلغائه (`is_revoked == False`) وعدم انتهاء صلاحيته.
     - إصدار Access Token جديد.
  4. `POST /api/v1/auth/logout`:
     - إبطال Refresh Token في قاعدة البيانات (`is_revoked = True`).
  5. `PUT /api/v1/auth/change-password`:
     - يتطلب مستخدم مسجل (`Depends(get_current_user)`).
     - التحقق من كلمة المرور الحالية وتحديثها بكلمة جديدة وتعيين `must_change_password = False`.
  6. `GET /api/v1/auth/me`:
     - إرجاع بيانات المستخدم الحالي مع ملفه المهني.

### الخطوة 2.5 — تجميع الموجّهات في `main.py`
- إنشاء `app/api/v1/api.py` وربط `auth.router`.
- تسجيل الراوتر الجديد في `app/main.py` تحت البادئة `/api/v1`.

### الخطوة 2.6 — الاختبارات الآلية
- إنشاء اختبارات متكاملة في `tests/test_auth.py` تغطي كافة الحالات (نجاح، كلمات سر خاطئة، حسابات معلقة، تجديد التوكن، إبطال التوكن، تغيير كلمة السر).
- التأكد من استمرار نجاح الاختبارات القديمة الـ 38 (`38 passed`).

---

## 4. 💡 رسالة البدء السريعة للشات الجديد (Prompt to copy-paste):

```markdown
مرحباً، نحن نواصل العمل على مشروع MedAssist AI V2 على فرع (feature/v2-telemedicine-expansion).
المرحلة 0 والمرحلة 1 مكتملتان ومختبرتان بنجاح (PostgreSQL + Alembic + 7 DB Models + Admin Seed).
جميع التفاصيل موثقة في `docs_v2/phase2_handover.md`.

المطلوب الآن: البدء مباشرة في تنفيذ المرحلة 2 (نظام المصادقة Auth System):
1. تحديث `app/core/security.py` بدوال التشفير وتوليد/فك رموز JWT ودعم PUT في CORS.
2. إنشاء مخططات `app/schemas/auth.py`.
3. إنشاء تبعيات الحماية `app/api/deps.py`.
4. إنشاء مسارات التوثيق الستة في `app/api/v1/endpoints/auth.py` وربطها في `app/main.py`.
5. كتابة اختبارات شاملة للنظام والتأكد من اجتياز كل الفحوصات.
```

