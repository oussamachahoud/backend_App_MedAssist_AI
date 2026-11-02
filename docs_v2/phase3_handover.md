# 📋 وثيقة التسليم والانتقال إلى المرحلة 3 (Handover to Phase 3: Clinical Prediction & Grad-CAM)
## مشروع MedAssist AI V2 — فرع `feature/v2-telemedicine-expansion`

> **تاريخ التحديث**: 31 أكتوبر 2026  
> **حالة المشروع الحالية**: المرحلة 0 (مكتملة 100%) | المرحلة 1 (مكتملة 100%) | المرحلة 2 (مكتملة 100% ومختبرة)  
> **حالة الاختبارات الحالية**: `62/62 PASSED` بنجاح كامل بدون أي تراجع (Zero Regressions)

---

## 1. 🗄️ إنجازات المرحلة 2 (نظام المصادقة والتفويض Auth System)

### 1.1 وحدة الأمان والتشفير والرموز ([`app/core/security.py`](file:///c:/Users/PC/Desktop/m2GLAA%20MF/backend_App_MedAssist_AI/app/core/security.py))
- **Bcrypt Password Hashing**:
  - `hash_password(password: str) -> str`
  - `verify_password(plain_password: str, hashed_password: str) -> bool`
- **JWT Token Management**:
  - `create_access_token(user_id, role, extra_claims=None) -> str` (صلاحية 15 دقيقة افتراضياً)
  - `create_refresh_token(user_id) -> tuple[str, str]` (صلاحية 7 أيام — يعيد الرمز الخام وهاش SHA-256 للحفظ الآمن)
  - `hash_refresh_token(token: str) -> str` (توليد هاش SHA-256 فريد)
  - `create_qr_token(analysis_id) -> str` (صلاحية 30 يوماً لوصول المريض بالباركود)
  - `decode_token(token: str) -> dict` (فك التشفير، والتحقق من الصلاحية، ورفع 401 عند الخطأ أو انتهاء الرمز)
- **CORS Enhancement**:
  - دعم أساليب: `["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]` لدعم تغيير كلمة السر والعمليات الإدارية.

### 1.2 مخططات البيانات Pydantic ([`app/schemas/auth.py`](file:///c:/Users/PC/Desktop/m2GLAA%20MF/backend_App_MedAssist_AI/app/schemas/auth.py))
- `RegisterDoctorRequest`: بريد إلكتروني، كلمة مرور، الاسم، نوع الطبيب، التخصص، رقم العمادة، المؤسسة، الهاتف، الولاية، الصورة.
- `LoginRequest`: البريد وكلمة المرور.
- `TokenResponse`: `access_token`, `refresh_token`, `token_type`, `expires_in`, `must_change_password`, `user`.
- `TokenRefreshResponse`: `access_token`, `token_type`, `expires_in`.
- `RefreshTokenRequest`: `refresh_token`.
- `ChangePasswordRequest`: `current_password`, `new_password`.
- `UserResponse` و `DoctorProfileResponse`: استجابات موحدة متوافقة مع ORM (`from_attributes=True`) مع حجب بيانات التشفير الحساسة.

### 1.3 تبعيات الحماية والتفويض ([`app/api/deps.py`](file:///c:/Users/PC/Desktop/m2GLAA%20MF/backend_App_MedAssist_AI/app/api/deps.py))
- `get_db`: توفير جلسة الـ DB وإغلاقها بأمان.
- `get_current_user`: فك Access Token وجلب كائن `User` النشط من PostgreSQL.
- `get_current_active_doctor`: التحقق من أن المستخدم يحمل دور `doctor` وحالته `active` (يرفع 403 للحسابات المعلقة أو بانتظار التفعيل).
- `get_current_specialist`: التحقق من أن الطبيب يحمل صفة `specialist_dermatologist`.
- `require_admin`: التحقق من أن المستخدم يحمل دور `admin` وحالته `active`.

### 1.4 مسارات التوثيق الستة ([`app/api/v1/endpoints/auth.py`](file:///c:/Users/PC/Desktop/m2GLAA%20MF/backend_App_MedAssist_AI/app/api/v1/endpoints/auth.py))
1. `POST /api/v1/auth/register`: تسجيل الأطباء الجدد مع حالة `pending_verification` وتسجيل `AuditLog`.
2. `POST /api/v1/auth/login`: مصادقة المستخدم وإصدار رمزي Access و Refresh وتحديث `last_login` وتسجيل `AuditLog`.
3. `POST /api/v1/auth/refresh`: تجديد الـ Access Token باستخدام Refresh Token غير ملغى وغير منتهي الصلاحية.
4. `POST /api/v1/auth/logout`: إبطال الـ Refresh Token في DB (`is_revoked = True`).
5. `PUT /api/v1/auth/change-password`: تحديث كلمة المرور وإعادة ضبط `must_change_password = False` وإبطال الجلسات السابقة.
6. `GET /api/v1/auth/me`: جلب بيانات المستخدم وملفه الطبي المصادق عليه.

---

## 2. 🧪 الاختبارات المؤتمتة (Test Results)

- **الملف**: [`tests/test_auth.py`](file:///c:/Users/PC/Desktop/m2GLAA%20MF/backend_App_MedAssist_AI/tests/test_auth.py) (24 اختباراً جديداً شاملاً).
- **إجمالي الاختبارات في المشروع**: **62 اختباراً**
- **النتيجة**: **`62/62 PASSED`** بنسبة نجاح 100%.

---

## 3. 🎯 المهام القادمة — المرحلة 3: تعديل مسار التحليل (`/predict`)

وفق خطة العمل في `docs_v2/workplan_backend_dashboard.md`:
1. تحديث محرك المخاطر في `app/services/risk_engine.py` لدعم مستوى `INCONCLUSIVE` (عند ثقة < 50%) واقتراح الإحالة `suggest_referral: bool`.
2. إنشاء خدمة Grad-CAM++ في `app/services/gradcam_service.py` وتخزين الخرائط الحرارية في MinIO.
3. تحديث مسار `POST /api/v1/predict`:
   - حماية المسار بـ `Depends(get_current_active_doctor)`.
   - تشغيل التنبؤ في `run_in_threadpool`.
   - حفظ صورة الفحص في MinIO وإنشاء سجل في جدول `analysis_records`.
   - إطلاق مهمة خلفية `BackgroundTasks` لتوليد Grad-CAM++.
   - إرجاع `analysis_id` ورابط تخزين و `suggest_referral`.

