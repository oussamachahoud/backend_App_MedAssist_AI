# ⚙️ خطة عمل النظام الخلفي + لوحة تحكم الويب — MedAssist AI V2

> **مستودع Backend**: `oussamachahoud/backend_App_MedAssist_AI.git`
> **الفرع الحالي**: `feature/v2-telemedicine-expansion`
> **آخر تحديث**: 01 نوفمبر 2026
> **حالة الاختبارات الإجمالية**: `116/116 PASSED` بنسبة نجاح 100%

---

## 🔀 إعداد فرع Git

```bash
# Backend
cd "c:\Users\PC\Desktop\m2GLAA MF\backend_App_MedAssist_AI"
git checkout main
git pull origin main
git checkout -b feature/v2-telemedicine-expansion
git push origin feature/v2-telemedicine-expansion
```

---

## المرحلة 0: إعداد البنية التحتية

### 0.1 Docker Compose
- [x] تحديث `docker-compose.yml` بـ 3 خدمات: `backend` + `postgres` (مع healthcheck) + `minio`
- [x] إضافة `healthcheck` لـ PostgreSQL: `pg_isready -U medassist -d medassist_db`
- [x] إضافة `depends_on: condition: service_healthy`
- [x] اختبار: `docker-compose up` يعمل بدون انهيار

### 0.2 SQLAlchemy + Alembic
- [x] إنشاء: `app/core/database.py` — `SessionLocal`, `Base`, `get_db`
- [x] تثبيت Alembic: `alembic init alembic`
- [x] تكوين: `alembic.ini` + `alembic/env.py` (يقرأ `DATABASE_URL` من config)
- [x] إنشاء أول migration: `alembic revision --autogenerate -m "initial schema"`
- [x] اختبار: `alembic upgrade head` يُنشئ الجداول

### 0.3 MinIO Setup
- [x] إنشاء: `app/services/storage_service.py`
  - [x] `upload_image(image_bytes, folder)` → يرجع `storage_key`
  - [x] `get_presigned_url(storage_key, expires=3600)` → URL مؤقت للعرض
  - [x] `delete_image(storage_key)`
- [x] إنشاء Bucket `medassist-analyses` عند أول تشغيل (في Lifespan)

### 0.4 تحديث Config
- [x] ملف: `app/core/config.py`
  - [x] إضافة: `DATABASE_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`
  - [x] إضافة: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`

### 0.5 تحديث Requirements
- [x] إضافة: `sqlalchemy`, `alembic`, `psycopg2-binary`, `minio`, `pyjwt`, `passlib[bcrypt]`
- [x] إضافة: `timm` (مطلوب لـ EfficientNet)
- [x] إضافة: `opencv-python-headless` (مطلوب لـ DullRazor/CLAHE)

---

## المرحلة 1: جداول قاعدة البيانات (DB Models)

- [x] إنشاء: `app/db_models/user.py` — `User`, `DoctorProfile`, `RefreshToken`
- [x] إنشاء: `app/db_models/patient.py` — `Patient`
- [x] إنشاء: `app/db_models/analysis.py` — `AnalysisRecord`
- [x] إنشاء: `app/db_models/referral.py` — `Referral`
- [x] إنشاء: `app/db_models/audit.py` — `AuditLog`
- [x] إنشاء schemas: `app/schemas/` — Auth, Telemedicine, Admin, Common
- [x] تشغيل Alembic migration وإنشاء الجداول

---

## المرحلة 2: نظام المصادقة والتفويض (Auth System)

- [x] أمان كلمات المرور: `app/core/security.py` — `verify_password`, `get_password_hash`
- [x] إدارة التوكنات: `create_access_token`, `create_refresh_token`
- [x] تبعيات الحماية (Dependencies): `app/api/deps.py`
  - [x] `get_current_user`
  - [x] `get_current_active_doctor`
  - [x] `get_current_admin`
- [x] مسارات المصادقة: `app/api/v1/endpoints/auth.py`
  - [x] `POST /auth/register`
  - [x] `POST /auth/login`
  - [x] `POST /auth/refresh`
  - [x] `POST /auth/logout`
  - [x] `GET /auth/me`

---

## المرحلة 3: مسار الاستدلال السريري المتطور (Predict V2)

- [x] تحديث `POST /api/v1/predict` (ودعمه على الجذر `/predict`)
  - [x] استدعاء `model_service.predict` داخل `run_in_threadpool`
  - [x] دعم حساب `INCONCLUSIVE` للحالات ذات الثقة < 50%
  - [x] حفظ الصورة الأصلية في MinIO تلقائياً
  - [x] حفظ السجل في PostgreSQL مع ربط `patient_id` و `lesion_tag`
  - [x] تشغيل توليد Grad-CAM++ في الخلفية عبر `BackgroundTasks`
  - [x] إرجاع الاستجابة الفورية السريعة (< 2s)

---

## المرحلة 4: مسارات التطبيب عن بُعد والإدارة (Telemedicine & Admin Endpoints)

- [x] مسارات التحاليل: `app/api/v1/endpoints/analyses.py`
  - [x] `GET /analyses`
  - [x] `GET /analyses/{id}`
  - [x] `PUT /analyses/{id}/feedback` (تسجيل توافق الطبيب والخزعة)
- [x] مسارات المرضى: `app/api/v1/endpoints/patients.py`
  - [x] `POST /patients`
  - [x] `GET /patients`
  - [x] `GET /patients/{id}/timeline` (التتبع الزمني لتطور الآفة)
- [x] مسارات الإحالة الطبية: `app/api/v1/endpoints/referrals.py`
  - [x] `POST /referrals` (إرسال إحالة من GP إلى أخصائي)
  - [x] `GET /referrals` (عرض الحالات الواردة والصادرة)
  - [x] `PUT /referrals/{id}` (تسجيل رأي وتوصية الأخصائي)
- [x] مسارات الإشراف الإداري: `app/api/v1/endpoints/admin.py`
  - [x] `GET /admin/users`
  - [x] `PUT /admin/users/{id}/verify` (اعتماد وتفعيل حساب الطبيب)
  - [x] `PUT /admin/users/{id}/suspend`
  - [x] `POST /admin/users/{id}/reset-password`
  - [x] `GET /admin/analytics`
  - [x] `GET /admin/audit-logs`

---

## المرحلة 5: لوحة تحكم الويب (Web Dashboard)

- [x] إعداد البنية الأساسية المدمجة في خادم FastAPI تحت `/dashboard`
- [x] صفحة الدخول الموحدة (`/login.html`) مع أزرار الدخول التجريبي السريع (Demo Chips)
- [x] بوابة طلب الاعتماد للأطباء الجدد (`/join.html`)
- [x] لوحة الطبيب الشاملة (`/doctor.html`):
  - [x] Overview: إحصائيات الفحوصات ومعدل الاعتماد ومخططات الخطورة
  - [x] Clinical Inference: استمارة الفحص، رفع الصورة، وعارض نتائج الذكاء الاصطناعي
  - [x] Analyses History: استعراض وتصفية السجلات السابقة
  - [x] Patients & Lesion Timelines: ملفات المرضى وتتبع تطور الآفة عبر الزمن
  - [x] Referrals: إدارة طلبات الرأي الثاني بين الطبيب العام والأخصائي
  - [x] Profile: بيانات الاعتماد المهني والولاية والمؤسسة
- [x] لوحة الإدارة المركزية (`/admin.html`):
  - [x] Overview: مراقبة النشاط العام والطلبات المعلقة
  - [x] Clinicians & Users: إدارة الحسابات، التحقق والاعتماد، والتعليق
  - [x] Analytics: التغطية الجغرافية للولايات وتوزيع الأمراض المشخصة
  - [x] Audit Logs: سجل الرقابة والامتثال الأمني
- [x] صفحة متابعة المريض العامة (`/follow-up.html`) المفتوحة عبر مسح رمز QR

---

## المرحلة 6: خدمة التقارير الطبية PDF مع رمز الاستجابة السريعة (PDF + QR)

- [x] إنشاء: `app/services/pdf_service.py`
  - [x] توليد QR code آمن يشير لصفحة المتابعة الطبية للمريض
  - [x] تضمين خريطة التفسير الحراري Grad-CAM++ والصورة الأصلية
  - [x] تضمين التشخيص الأولي، درجة الثقة، ومستوى الخطورة وتوصيات التغذية الراجعة
  - [x] حماية التقرير وتوقيع الروابط المؤقتة بصلاحية 30 يوماً

---

## المرحلة 7: الحوكمة، التعريب الثلاثي الشامل وموارد المنصة (Platform Resources & Trilingual System)

- [x] التعريب الثلاثي الشامل (EN / FR / عربي):
  - [x] بناء محرك `dashboard/assets/js/i18n.js` مع أكثر من 150 مفتاح ترجمة طبي وتقني
  - [x] التبديل التلقائي لاتجاه الواجهة (RTL/LTR) وحفظ التفضيل في `localStorage`
  - [x] إعادة التصيير اللحظي للتبويبات النشطة (`refreshActiveTabLanguage`) دون الحاجة لتحديث الصفحة
  - [x] ربط محرك `charts.js` لترجمة تصنيفات الأمراض ومستويات الخطورة والمحاور في المخططات البيانية
- [x] حوكمة مذكرات التخرج الأكاديمية (English & French Theses):
  - [x] استبدال النسخة العربية بالنسخة الفرنسية تلبيةً للمتطلبات الجامعية لماستر 2 GLAA
  - [x] توفير النسخة الإنجليزية (`Thesis_Master_GLAA_EN.pdf`) والفرنسية (`Thesis_Master_GLAA_FR.pdf`)
  - [x] إنشاء مسار الرفع المباشر للأدمن: `POST /api/v1/admin/platform-resources/upload-thesis?lang=en|fr`
  - [x] توثيق عمليات الرفع في سجل التدقيق الأمني تحت نوع الحدث `THESIS_DOCUMENT_UPLOADED`
  - [x] إبقاء قسم المذكرات ظاهراً في صفحة الهبوط `landing.html`
- [x] إدارة وتحديث موارد المنصة وحزم APK ورمز QR:
  - [x] إنشاء مسار رفع وتحديث التطبيق: `POST /api/v1/admin/platform-resources/upload-apk`
  - [x] إنشاء مسار رفع رمز الاستجابة السريعة SVG المتجهي: `POST /api/v1/admin/platform-resources/upload-qr-code`
  - [x] التحقق الأمني من ملفات SVG وكتابتها إلى `dashboard/assets/images/qr-code.svg` وتوثيق `QR_CODE_UPLOADED`
  - [x] حفظ واستمرارية كافة الموارد الدائمة في `platform_resources.json`
  - [x] ربط فيديو الديمو الإرشادي (YouTube Shorts) واستخراج الصورة المصغرة عالية الدقة تلقائياً
  - [x] تنظيف الروابط القديمة لـ GitHub Pages في `landing.html` وتوجيهها للمسار الديناميكي `/dashboard/landing.html`
- [x] التوافقية الشاملة والتعريب اللحظي للمحتوى الديناميكي:
  - [x] تضمين مسارات الجذر `/health` و `/predict` لدعم كافة طلبات تطبيق الهاتف المحمول (Flutter)
  - [x] حل مشكلة بطاقات الصفر عبر التحقق النشط من صلاحية التوكن والتعافي التلقائي عند انتهاء الجلسة
  - [x] تعريب المحتوى المحقون ديناميكياً (Dynamic DOM Injection) في جداول الأطباء والإجراءات عبر `window.t` و 289 مفتاح ترجمة
  - [x] توسيع حزمة الاختبارات الآلية والتحقق من نجاح **119/119 اختباراً وحدوياً وتكاملياً** بنسبة 100%

---

## 🎯 قائمة التحقق النهائية للنظام (System Checklist)

### Backend
- [x] `docker-compose up` يعمل بدون انهيار
- [x] `alembic upgrade head` يطبق كل الجداول بنجاح
- [x] `/predict` و `/api/v1/predict` يعمل مع JWT وبدونه، ويحفظ في DB + MinIO للأطباء المعتمدين
- [x] Grad-CAM++ يُحسب في الخلفية ويُحدّث في DB
- [x] `INCONCLUSIVE` يُعرض عند ثقة < 50%
- [x] مسار رفع مذكرات التخرج `POST /admin/platform-resources/upload-thesis` يعمل ويحسب الأحجام
- [x] مسار رفع حزم التطبيق `POST /admin/platform-resources/upload-apk` يعمل مع التدقيق الأمني
- [x] `/public/doctors` يعمل بدون الحاجة لـ JWT
- [x] تسجيل وتوثيق العمليات الحساسة في `audit_logs`
- [x] سياسة CORS مضبوطة بدقة للمنافذ المصرح بها

### Web Dashboard
- [x] لوحة تحكم متكاملة بنظام التصميم الزجاجي (Glassmorphism)
- [x] تعريب وتبديل لغوي ثلاثي كامل (EN / FR / عربي) مع التوجيه من اليمين لليسار (RTL)
- [x] Doctor Dashboard يدعم الفحوصات + السجلات + المرضى + الإحالات + الملف المهني
- [x] Admin Dashboard يدعم المستخدمين + التحليلات + سجلات التدقيق + موارد المنصة ومذكرات التخرج
- [x] عارض Grad-CAM++ التفاعلي بشريط تمرير الشفافية (Opacity Slider)
- [x] تصميم متجاوب يعمل على كافة الشاشات والأجهزة

### التكامل مع تطبيق الهاتف (Mobile Interoperability)
- [x] تطبيق Flutter يتصل بسلاسة مع Backend عبر المسار الجذري `/predict` أو بادئة `/api/v1/predict`
- [x] إرسال واستقبال `patient_id` و `lesion_tag` وتوليد التقارير الطبية
- [x] توافقية كاملة مع استجابة النموذج وتصنيف الخطورة المعتمد
