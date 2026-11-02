# 🏥 MedAssist AI — المعمارية النهائية المتفق عليها (V2)

> **الحالة**: مسودة نهائية للمناقشة قبل التنفيذ  
> **التاريخ**: 30 أكتوبر 2026  
> **السياق**: مذكرة ماستر GLAA + Startup (القرار الوزاري 1275)

---

## 1. 🎯 الرؤية المحدّثة

تحويل MedAssist AI من أداة فحص مستقلة (MVP) إلى **منظومة طب اتصالي (Telemedicine Ecosystem)** تربط:
- الطبيب العام في الخطوط الأمامية (يفحص ويُحيل)
- أخصائي الجلدية عن بُعد (يراجع ويؤكد)
- المريض (يتابع ملفه ويتثقف — بدون تشخيص ذاتي)
- مدير النظام (يدير، يراقب، يتحقق)

---

## 2. 👥 الأدوار الأربعة — التفصيل النهائي

### 2.1 🩺 طبيب الخطوط الأمامية (`general_practitioner`)

| البُعد | التفصيل |
|--------|---------|
| **المنصات** | 📱 Mobile (أساسي) + 🌐 Web (مراجعة السجلات) |
| **التسجيل** | من التطبيق أو عبر نموذج "انضم كطبيب" على الويب |
| **حالة الحساب** | `pending_verification` → `active` (بعد موافقة الأدمن) |
| **الصلاحيات الأساسية** | التقاط/رفع صورة، ملء الاستبيان السريري (7+1 متغير)، الحصول على نتيجة AI، إنشاء ملف مريض، تصدير PDF |
| **الإضافة التوسعية** | زر "طلب رأي ثانٍ" عند حالات `HIGH`/`CRITICAL` أو ثقة < 50% |
| **الـ Feedback** | تأكيد/تصحيح تشخيص AI + تسجيل نتيجة Biopsy إن وُجدت |

### 2.2 👨‍⚕️ أخصائي الأمراض الجلدية (`specialist_dermatologist`)

| البُعد | التفصيل |
|--------|---------|
| **المنصات** | 🌐 Web (أساسي — شاشة كبيرة لمراجعة الصور) + 📱 Mobile (مراجعة سريعة) |
| **التسجيل** | نفس مسار الطبيب العام — لكن مع تخصص `dermatology` |
| **يملك كل صلاحيات الطبيب العام** | ✅ |
| **الإضافات الحصرية** | قسم "الحالات المحولة للمراجعة" (Referrals Inbox)، كتابة التشخيص النهائي، تأكيد أو تصحيح قرار AI |
| **القيمة البيانية** | تصحيحات الأخصائي = بيانات ذهبية لإعادة تدريب النموذج (Active Learning) |

> [!NOTE]
> **تبسيط مهم**: في V1، الفرق بين GP و Specialist هو فقط **حقل التخصص في الملف الشخصي** + **ظهور قسم الإحالات الواردة**. لا تبنِ نظامين منفصلين بالكامل. يمكن أن يكون `role = doctor` واحد مع `specialization` يحدد الواجهة.

### 2.3 👤 المريض / المواطن (`patient`)

| البُعد | التفصيل |
|--------|---------|
| **المنصات** | 📱 Mobile فقط (وضع محدود) + 🔗 رابط ويب مؤقت عبر QR |
| **التسجيل** | ❌ لا تسجيل على الويب — لا حساب إلزامي على التطبيق |
| **ما يراه على التطبيق** | دليل ABCDE التفاعلي، نصائح الفحص الذاتي، دليل الأطباء المعتمدين حسب الولاية |
| **ما لا يمكنه فعله** | ❌ فحص AI ذاتي، ❌ الوصول لأي Dashboard |
| **ميزة المتابعة** | مسح QR من تقرير PDF الذي أعطاه الطبيب → يرى ملخص نتيجته + تاريخ الفحص القادم (رابط مؤقت بدون حساب) |

> [!CAUTION]
> **القرار الطبي الحاسم**: لا تشخيص ذاتي للمريض. معدل False Negative للميلانوما = 27.7%. مواطن عادي يحصل على `LOW RISK` لشامة خبيثة = كارثة طبية وقانونية.

### 2.4 👑 مدير النظام (`super_admin`)

| البُعد | التفصيل |
|--------|---------|
| **المنصات** | 🌐 Web Dashboard حصرياً |
| **التسجيل** | لا يُسجّل — يُنشأ يدوياً في قاعدة البيانات (Seed) |
| **الصلاحيات** | إدارة المستخدمين (التحقق، تفعيل، تعليق، إعادة تعيين كلمة المرور)، مراقبة النظام (إحصائيات، أداء AI، توزيع جغرافي)، سجل الرقابة (Audit Logs)، إعدادات النظام |

---

## 3. 🗄️ Database Schema النهائي (PostgreSQL)

> [!NOTE]
> **التصحيحات المُطبّقة (5 ثغرات مُغلقة)**:
> 1. ✅ إضافة `deleted_at` لـ `patients` لدعم Soft Delete
> 2. ✅ استبدال `int age` بـ `int birth_year` + حفظ العمر وقت الفحص داخل `clinical_data`
> 3. ✅ إضافة `lesion_tag` لـ `analysis_records` لتمييز الآفات المتعددة على نفس المريض
> 4. ✅ إضافة `next_followup_date` لـ `analysis_records` لدعم روابط QR
> 5. ✅ حذف `verify-email` endpoint وحقل `email_verified` — موافقة الأدمن تغني عنه في V1

```mermaid
erDiagram
    users {
        uuid id PK
        varchar email UK "بريد مهني"
        varchar password_hash
        enum role "doctor | admin"
        enum status "pending_verification | active | suspended"
        boolean must_change_password "false"
        timestamp created_at
        timestamp last_login
    }

    doctor_profiles {
        uuid id PK
        uuid user_id FK UK
        varchar full_name
        enum doctor_type "general_practitioner | specialist_dermatologist"
        varchar specialization "طب عام، أمراض جلدية..."
        varchar license_number "رقم عمادة الأطباء"
        varchar institution_name "المستشفى/العيادة"
        varchar phone
        varchar wilaya "من 01 إلى 58"
        varchar avatar_url "NULL"
        timestamp updated_at
    }

    patients {
        uuid id PK
        uuid created_by_doctor_id FK
        varchar patient_code "DZ-XX-PXXXX / MED-2026-XXXXX (مُجهّل Pseudonymized)"
        int birth_year "سنة الميلاد — العمر يُحسب ديناميكياً"
        enum sex "male | female"
        varchar notes "ملاحظات عامة اختيارية"
        timestamp created_at
        timestamp deleted_at "NULL — Soft Delete"
    }

    analysis_records {
        uuid id PK
        uuid doctor_id FK
        uuid patient_id FK "NULL إذا بدون ربط مريض"
        varchar lesion_tag "مُعرّف الآفة: مثلاً الكتف الأيمن - آفة 1"
        varchar image_storage_key "مسار الصورة في MinIO"
        varchar gradcam_storage_key "مسار خريطة Grad-CAM — NULL حتى تنتهي المهمة الخلفية"
        jsonb clinical_data "العمر وقت الفحص، الجنس، الموقع، القطر، البروز..."
        varchar predicted_class "MEL | BCC | SCC | ACK | NEV | SEK"
        float confidence
        jsonb all_probabilities
        varchar risk_level "LOW | MODERATE | HIGH | CRITICAL"
        boolean risk_escalated "true إذا تم تصعيد الخطر بسبب ثقة أقل من 50%"
        jsonb recommendations
        float inference_time_ms
        varchar model_version "V6.0"
        boolean doctor_confirmed "NULL = لم يُراجع بعد"
        varchar doctor_diagnosis "التشخيص النهائي للطبيب — NULL"
        boolean biopsy_performed "NULL"
        varchar biopsy_result "NULL"
        date next_followup_date "NULL — يحدده الطبيب للمتابعة عبر QR"
        timestamp created_at
    }

    referrals {
        uuid id PK
        uuid analysis_id FK UK
        uuid referring_doctor_id FK "الطبيب المُحيل — GP"
        uuid specialist_id FK "الأخصائي المُستقبِل — NULL إذا لم يُعيَّن بعد"
        enum status "pending | accepted | completed | cancelled"
        text referral_note "ملاحظة الإحالة من GP"
        text specialist_response "رد الأخصائي — NULL"
        timestamp created_at
        timestamp responded_at "NULL"
    }

    refresh_tokens {
        uuid id PK
        uuid user_id FK
        varchar token_hash
        timestamp expires_at
        boolean is_revoked
        timestamp created_at
    }

    audit_logs {
        uuid id PK
        uuid user_id FK "NULL للعمليات النظامية"
        varchar action "LOGIN | ANALYSIS | REFERRAL | PASSWORD_RESET | ..."
        varchar resource_type "user | analysis | referral"
        uuid resource_id "NULL"
        jsonb details
        varchar ip_address
        timestamp created_at
    }

    users ||--o| doctor_profiles : "has profile"
    users ||--o{ analysis_records : "performs"
    users ||--o{ refresh_tokens : "owns"
    users ||--o{ audit_logs : "generates"
    patients ||--o{ analysis_records : "has analyses"
    users ||--o{ patients : "creates"
    analysis_records ||--o| referrals : "may have"
    users ||--o{ referrals : "refers as GP"
    users ||--o{ referrals : "receives as Specialist"
```

---

## 4. 📡 Backend API Endpoints النهائية

### Auth (6 endpoints)
```
POST   /api/v1/auth/register              # تسجيل طبيب جديد → pending_verification
POST   /api/v1/auth/login                  # تسجيل دخول → JWT (access + refresh)
POST   /api/v1/auth/refresh                # تجديد access token
POST   /api/v1/auth/logout                 # إبطال refresh token
PUT    /api/v1/auth/change-password        # تغيير كلمة المرور (+ إجباري بعد reset)
GET    /api/v1/auth/me                     # بيانات المستخدم الحالي
```
> ❌ `verify-email` مُلغى في V1 — موافقة الأدمن اليدوية (`pending → active`) تغني عنه وتوفر تكوين SMTP.

### Doctor Profile (4 endpoints)
```
GET    /api/v1/profile                     # عرض الملف الشخصي
PUT    /api/v1/profile                     # تعديل الملف الشخصي
GET    /api/v1/profile/stats               # إحصائيات شخصية
```

### Patients (5 endpoints)
```
POST   /api/v1/patients                    # إنشاء ملف مريض جديد (مُجهّل)
GET    /api/v1/patients                    # قائمة مرضى الطبيب (paginated)
GET    /api/v1/patients/:id                # تفاصيل مريض + timeline تحليلاته
PUT    /api/v1/patients/:id                # تعديل ملاحظات المريض
DELETE /api/v1/patients/:id                # حذف ملف مريض (soft delete)
```

### Analysis (6 endpoints)
```
POST   /api/v1/predict                     # تحليل جديد — متوافق مع المذكرة وpytest الحالي
                                           # → يحفظ الصورة في MinIO + النتيجة في DB
                                           # → يعيد الرد فوراً (< 2s)
                                           # → يُطلق BackgroundTask لتوليد Grad-CAM++
GET    /api/v1/analyses                    # سجل التحليلات (paginated + filters)
GET    /api/v1/analyses/:id                # تفاصيل تحليل واحد (+ gradcam إن جاهز)
PUT    /api/v1/analyses/:id/feedback       # تأكيد/تصحيح التشخيص + biopsy + next_followup_date
DELETE /api/v1/analyses/:id                # حذف تحليل
POST   /api/v1/analyses/:id/export-pdf     # تصدير PDF مع QR code
```

> [!TIP]
> **حماية زمن الاستجابة**: `POST /predict` يعيد النتيجة فوراً بدون Grad-CAM (يبقى تحت 2s). توليد Grad-CAM++ يحدث في `FastAPI BackgroundTasks` (≈ 200-300ms إضافية) ويُحدّث `gradcam_storage_key` في DB — جاهز عند فتح الطبيب للوحة الويب.

### Referrals — الإحالات (5 endpoints)
```
POST   /api/v1/referrals                   # إنشاء إحالة (GP → Specialist)
GET    /api/v1/referrals/sent              # إحالاتي المرسلة (GP)
GET    /api/v1/referrals/received          # إحالات واردة (Specialist)
PUT    /api/v1/referrals/:id/respond       # رد الأخصائي على الإحالة
GET    /api/v1/referrals/:id               # تفاصيل إحالة
```

### Patient Follow-up — رابط QR (2 endpoints)
```
POST   /api/v1/patient-links/:analysis_id  # توليد رابط مؤقت آمن (Signed JWT, 30 يوم)
GET    /api/v1/public/follow-up/:token      # عرض ملخص النتيجة + next_followup_date للمريض (بدون حساب)
```

### Public — بدون مصادقة (2 endpoints)
```
GET    /api/v1/public/doctors              # دليل الأطباء المعتمدين (status=active فقط)
                                           # فلترة: wilaya, specialization, doctor_type
                                           # الحقول المكشوفة فقط: full_name, specialization,
                                           #   doctor_type, institution_name, wilaya
                                           # ❌ لا يكشف: email, phone, license_number
GET    /api/v1/public/follow-up/:token     # (مذكور أعلاه — رابط QR للمريض)
```

### Admin (8 endpoints)
```
GET    /api/v1/admin/users                 # قائمة المستخدمين (paginated + filters)
GET    /api/v1/admin/users/:id             # تفاصيل مستخدم
PUT    /api/v1/admin/users/:id/verify      # تفعيل حساب طبيب (بعد التحقق)
PUT    /api/v1/admin/users/:id/status      # تعليق/تفعيل حساب
POST   /api/v1/admin/users/:id/reset-pwd   # توليد كلمة مرور مؤقتة
GET    /api/v1/admin/stats                 # إحصائيات النظام
GET    /api/v1/admin/analytics             # تحليلات متقدمة (توزيع جغرافي، أداء AI)
GET    /api/v1/admin/audit-logs            # سجل الرقابة
```

---

## 5. 📱 تطبيق الهاتف (Flutter) — الهيكل المُعدَّل

### 5.1 Navigation Structure & Shell Architecture

**🩺 الطبيب المعتمد — هيكل الغلاف الموحد (`MainLayoutView` مع `NavigationBar` — 4 تبويبات):**
يعتمد التطبيق نمط `Shell Route` المدار بـ `IndexedStack` لضمان عدم إعادة تحميل الشاشات والحفاظ على حالة العمل السريري:
```
┌───────────────────────────────────────────────────┐
│  Tab 1: 🏠 الرئيسية        │  Tab 2: 👥 المرضى  │
│  - فحص جديد (التقاط/رفع)   │  - قائمة المرضى    │
│  - مؤشرات أداء وتشخيص      │  - إضافة مريض مجهّل │
│  - آخر التحليلات السريرية │  - Timeline تطور الآفة│
├───────────────────────────────────────────────────┤
│  Tab 3: 📋 الإحالات        │  Tab 4: 👤 حسابي   │
│  - GP: إحالاتي المرسلة     │  - الملف الشخصي    │
│  - Specialist: الواردة والرد│  - الإعدادات واللغة│
│  - تتبع حالة الإحالة       │  - تسجيل الخروج    │
└───────────────────────────────────────────────────┘
```

**👤 الشاشة الرئيسية المتكيفة ذاتياً (`Adaptive HomeView`):**
- **في وضع الضيف/المواطن (Guest Mode)**: تعرض شريط تنبيه الوضع التوعوي، دليل ABCDE التفاعلي المترجم، خريطة دليل الأطباء المعتمدين جغرافياً، ومسح رمز QR السريع للمتابعة، مع زر "دخول الطبيب".
- **في وضع الطبيب المسجل (Clinician Mode)**: تعرض فوراً بطاقة تعريف الممارس، إحصائيات الفحص السريع، واختصارات بدء الاستدلال السريري.

### 5.2 Routes المعيارية المنفذة (`AppRoutes`)
```dart
// Auth & Onboarding
static const SPLASH = '/splash';
static const ONBOARDING = '/onboarding';
static const LOGIN = '/login';
static const REGISTER = '/register';                        // Stepper متعدد المراحل
static const PENDING_VERIFICATION = '/pending-verification';
static const FORCE_CHANGE_PASSWORD = '/force-change-password';

// Main Shell & Clinical Diagnostic Flow
static const MAIN_LAYOUT = '/main';                         // غلاف الطبيب الموحد
static const HOME = '/home';                                // متكيف تلقائياً (Guest vs Doctor)
static const CAMERA = '/camera';                            // التقاط / اختيار صورة الآفة
static const CONSENT = '/consent';                          // 🛡️ شاشة الموافقة المستنيرة الإلزامية (GDPR/قانون 18-07)
static const CLINICAL_FORM = '/clinical-form';              // 7 متغيرات سريرية + القطر والبروز
static const ANALYSIS = '/analysis';                        // شاشة الانتظار مع مؤشر المعالجة
static const RESULT = '/result';                            // النتيجة: 5 مستويات خطورة + Grad-CAM++ Overlay + Feedback

// Telemedicine & Patient Longitudinal Tracking
static const PATIENTS = '/patients';                        // سجل المرضى المجهّل
static const REFERRALS = '/referrals';                      // منصة الإحالات (مرسلة / واردة)
static const DOCTOR_DIRECTORY = '/doctor-directory';        // دليل الأطباء العام المعتمدين
static const QR_FOLLOWUP = '/qr-followup';                  // مسح رمز QR ومتابعة موعد الفحص القادم
static const PROFILE = '/profile';                          // الملف الشخصي للطبيب

// History & Consultation
static const HISTORY = '/history';                          // سجل التحليلات السحابي/المحلي
static const HISTORY_DETAIL = '/history-detail';

// Preferences & Patient Education
static const SETTINGS = '/settings';                        // الإعدادات (اللغة والمظهر والشبكة)
static const ABOUT = '/about';                              // عن المنصة ومواصفات القرار 1275
static const EDUCATION = '/education';                      // دليل الفحص السريري ABCDE التفاعلي
```

---

## 6. 🌐 Web Dashboard — هيكل الصفحات

### 6.1 الصفحات المشتركة
```
/login                      # تسجيل الدخول الموحد
/join                       # نموذج "انضم كطبيب معتمد"
/force-change-password      # تغيير كلمة المرور الإجبارية
```

### 6.2 لوحة الطبيب (`/doctor/*`)
```
/doctor                     # الرئيسية — إحصائيات شخصية + آخر النشاط
/doctor/analyses             # أرشيف التحليلات (جدول + فلاتر + بحث)
/doctor/analyses/:id         # تفاصيل تحليل (صورة أصلية + Grad-CAM + نتائج)
/doctor/patients             # قائمة المرضى + بحث
/doctor/patients/:id         # ملف المريض + Lesion Timeline
/doctor/referrals            # GP: المُرسلة | Specialist: الواردة + الرد
/doctor/referrals/:id        # تفاصيل إحالة
/doctor/profile              # الملف الشخصي
/doctor/settings             # إعدادات (لغة، مظهر)
```

### 6.3 لوحة الأدمن (`/admin/*`)
```
/admin                       # نظرة عامة (مستخدمين، تحليلات، أداء النظام)
/admin/users                 # إدارة المستخدمين (جدول + فلاتر + إجراءات)
/admin/users/:id             # تفاصيل مستخدم + إحصائياته
/admin/analytics             # تحليلات متقدمة (رسوم بيانية، توزيع جغرافي)
/admin/feedback              # نسبة توافق AI مع الأطباء (Doctor Feedback Stats)
/admin/audit-logs            # سجل الرقابة
/admin/settings              # إعدادات النظام
```

### 6.4 صفحة عامة (بدون حساب)
```
/follow-up/:token            # رابط QR للمريض — ملخص نتيجة + تاريخ الفحص القادم
```

---

## 7. 🎨 التقنيات المعتمدة

| المكون | التقنية | السبب |
|--------|---------|-------|
| **Frontend Mobile** | Flutter 3.x + GetX | Feature-First Clean Architecture + إدارة حالة تفاعلية سريعة وخالية من العناصر المتقادمة (Zero Deprecations) |
| **Frontend Web** | Vanilla JS (ES6+) + TailwindCSS + Chart.js | تصميم طبي سريع وأداء خفيف مدمج مباشرة مع FastAPI كـ SPA دون الحاجة لخادم Node مستقل |
| **Charts (Web)** | Chart.js 4.x | خفيفة، تفاعلية، ومتزامنة لحظياً مع نظام التعريب الثلاثي (i18n) |
| **Backend** | FastAPI + SQLAlchemy 2.0 + Alembic | كفاءة غير متزامنة، توثيق تلقائي OpenAPI، وThreadPool لمنع حجب الاستدلال |
| **Database** | PostgreSQL 16 (عبر Docker) | سلامة المعاملات، علاقات متقدمة، وحقول JSONB للبيانات السريرية المرنة |
| **Image Storage** | MinIO (S3-compatible) + Local Fallback | نظام تخزين هجين بمقبس فحص سريع (Zero-Timeout Probe 150ms) لمنع تعليق النظام |
| **Email / Notifications**| Resend / Brevo API | إشعارات التحقق وإعادة تعيين الحسابات |
| **Auth & Security** | JWT (access 15min + refresh 7days) | مخصص بالكامل + تجديد تلقائي صامت على الهاتف (Silent 401 Auto-Refresh Interceptor) |
| **Containerization** | Docker Compose | بيئة تشغيل متكاملة ومؤتمتة مع فحوص الجاهزية (Healthchecks) |

---

## 8. ⏱️ تقسيم العمل والأولويات

> [!IMPORTANT]
> **سؤال حاسم**: كم من الوقت متبقي قبل تسليم المذكرة؟ هذا يحدد ما يدخل في V1 (إلزامي) وما يُؤجل لـ V2 (توسعي).

### المرحلة 1 — الأساس (P0 — إلزامي للمذكرة) ≈ 15-20 يوم عمل

| المهمة | المسؤول | الأيام |
|--------|---------|--------|
| PostgreSQL + Alembic + Schema الأساسي | Backend Dev | 3 |
| JWT Auth (register, login, refresh, RBAC middleware) | Backend Dev | 3 |
| تعديل `/predict` لحفظ في DB + MinIO | Backend Dev | 2 |
| Admin endpoints (users CRUD, reset password) | Backend Dev | 2 |
| Doctor endpoints (analyses, profile, stats) | Backend Dev | 2 |
| Login + Register (Stepper) في Flutter | Mobile Dev | 3 |
| Splash/Home تعديل (Guest vs Doctor) | Mobile Dev | 2 |
| BottomNavigationBar + Profile | Mobile Dev | 2 |
| إصلاح bugs (CRITICAL, elevation, i18n) | Mobile Dev | 1 |
| Web Dashboard — Setup + Login + Layout مشترك | Backend/Web Dev | 3 |
| Web Dashboard — Doctor Overview + Analysis History | Backend/Web Dev | 3 |
| Web Dashboard — Admin Users + Stats | Backend/Web Dev | 3 |

### المرحلة 2 — القيمة المضافة (P1 — مُثرِية للمذكرة) ≈ 10-15 يوم

| المهمة | المسؤول | الأيام |
|--------|---------|--------|
| نظام Patients + Timeline | Both | 4 |
| نظام Referrals (GP → Specialist) | Both | 4 |
| Doctor Feedback Loop (confirm/correct) | Both | 2 |
| Email (Resend/Brevo) — verification + notifications | Backend Dev | 1 |
| About Page + Doctor Directory | Mobile Dev | 2 |
| Grad-CAM++ integration في Backend + عرض في Web | Backend Dev | 3 |

### المرحلة 3 — تحسينات (P2 — بعد التسليم / للـ Startup)

| المهمة |
|--------|
| QR Follow-up للمريض |
| خريطة حرارية جغرافية للحالات حسب الولاية |
| Dark Mode في Flutter و Web |
| Audit Logs متقدم |
| CI/CD للـ Frontend + Web |
| Kubernetes + ONNX/TFLite (حسب خارطة طريق المذكرة) |

---

## 9. 🐳 Docker Compose المُحدَّث

```yaml
# docker-compose.yml
version: '3.8'

services:
  # FastAPI Backend
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://medassist:secret@postgres:5432/medassist_db
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=medassist
      - MINIO_SECRET_KEY=medassist_secret
      - JWT_SECRET_KEY=your-256-bit-secret
      - JWT_ALGORITHM=HS256
      - ACCESS_TOKEN_EXPIRE_MINUTES=15
      - REFRESH_TOKEN_EXPIRE_DAYS=7
    depends_on:
      postgres:
        condition: service_healthy
      minio:
        condition: service_started
    volumes:
      - ./models:/app/models

  # PostgreSQL Database
  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=medassist
      - POSTGRES_PASSWORD=secret
      - POSTGRES_DB=medassist_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U medassist -d medassist_db"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s

  # MinIO Object Storage (للصور + Grad-CAM)
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=medassist
      - MINIO_ROOT_PASSWORD=medassist_secret
    ports:
      - "9000:9000"   # API
      - "9001:9001"   # Console
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  pgdata:
  minio_data:
```

> [!WARNING]
> **إصلاح مُطبّق**: `depends_on` وحدها لا تنتظر جاهزية PostgreSQL لاستقبال الاتصالات. الآن `backend` ينتظر `condition: service_healthy` مع `healthcheck` يستخدم `pg_isready` — لا انهيار عند أول تشغيل.

---

## 10. 📊 الميزات الثلاث النوعية — التفصيل التقني

### 10.1 Lesion Timeline (تتبع زمني للآفة)

```
Patient Record
├── Analysis 1 (2026-03-15): NEV, Confidence 89%, Diameter 4mm
├── Analysis 2 (2026-06-20): NEV, Confidence 72%, Diameter 5.5mm ⚠️
├── Analysis 3 (2026-09-10): MEL suspect, Confidence 61%, Diameter 7mm 🔴
│   └── Referral → Dr. Specialist → Biopsy recommended
└── بصرياً: مخطط خطي يُظهر تطور القطر والثقة عبر الأشهر
```

**القيمة الطبية**: هذا هو حرف `E` (Evolution) من قاعدة ABCDE — أهم مؤشر سريري.

### 10.2 Grad-CAM++ (خريطة تفسير بصري وتفسيرية سريرية تفاعلية)

- **في الخادم (Backend)**:
  - تُولّد إما أثناء الاستدلال كبيانات Base64 فورية أو في `FastAPI BackgroundTasks` لتحديث السجل الدائم، مما يضمن بقاء زمن الاستجابة الكلي أقل من ثانيتين (`< 2s`).
  - تُحفظ كصورة PNG في MinIO (أو التخزين المحلي الاحتياطي) بجانب الصورة الأصلية → يُحدَّث `gradcam_storage_key` في قاعدة البيانات.
- **في تطبيق الهاتف (Flutter)**:
  - تم تنفيذ مفتاح تبديل تفاعلي في شاشة النتيجة (`ResultView`): **الصورة الأصلية ↔ التراكب الحراري (Grad-CAM++ Saliency Overlay)**.
  - يُمكّن الطبيب من التحقق البصري المباشر من تركيز خوارزمية التعلم العميق على معالم الآفة الجلدية دون الاعتماد الأعمى، مع الاحتفاظ بشارة التحذير السريرية ومستوى الخطورة الخماسي.
- **في لوحة تحكم الويب (Web Dashboard)**:
  - تُعرض الصورتان جنباً إلى جنب مع إمكانية التكبير والتبديل اللحظي لمساعدة أخصائي الأمراض الجلدية في جلسات المراجعة والتحقق.

```python
# مثال التنفيذ في FastAPI
@router.post("/predict")
async def predict(
    image: UploadFile,
    metadata: PatientMetadata,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_doctor),
    db: Session = Depends(get_db),
):
    # 1. المعالجة والاستدلال الفوري (< 2s مع TTA x8)
    result = model_service.predict(image_bytes, metadata)
    
    # 2. حفظ الصورة الأصلية في MinIO
    image_key = minio_service.upload(image_bytes, bucket="analyses")
    
    # 3. حفظ السجل في DB (بدون Grad-CAM بعد)
    record = AnalysisRecord(
        doctor_id=current_user.id,
        image_storage_key=image_key,
        gradcam_storage_key=None,  # ← سيُملأ لاحقاً
        predicted_class=result.predicted_class,
        confidence=result.confidence,
        # ...
    )
    db.add(record)
    db.commit()
    
    # 4. إطلاق مهمة خلفية لتوليد Grad-CAM++
    background_tasks.add_task(
        generate_and_store_gradcam,
        record_id=record.id,
        image_bytes=image_bytes,
    )
    
    # 5. إرجاع النتيجة فوراً للتطبيق
    return PredictionResponse(...)
```

### 10.3 Doctor Feedback Loop

```
بعد عرض النتيجة → زر "هل توافق على التشخيص؟"
├── ✅ نعم → doctor_confirmed = true
└── ❌ لا → اختر التشخيص الصحيح (dropdown 6 فئات)
              └── هل أُجريت خزعة؟
                  ├── نعم → نتيجة الخزعة (نص حر)
                  └── لا
```

**إحصائية الأدمن**: "MedAssist AI توافق مع الأطباء في 78% من الحالات" → رقم قوي للمذكرة والـ Startup.

---

## 11. ✅ سجل التصحيحات المُطبّقة على الوثيقة

| # | الثغرة | المكان | التصحيح المُطبّق |
|---|--------|--------|-----------------|
| 1 | حذف لين بدون `deleted_at` + عمر ثابت | `patients` | ✅ أُضيف `deleted_at TIMESTAMP NULL` + استُبدل `int age` بـ `int birth_year` (العمر يُحسب ديناميكياً، ويُحفظ وقت كل فحص داخل `clinical_data`) |
| 2 | Timeline يدمج شامات مختلفة | `analysis_records` | ✅ أُضيف `varchar lesion_tag` لتمييز كل آفة على نفس المريض (مثلاً: "الكتف الأيمن - آفة 1") |
| 3 | رابط QR بدون `next_followup_date` | `analysis_records` | ✅ أُضيف `date next_followup_date NULL` يحدده الطبيب — يعرضه رابط QR للمريض |
| 4a | دليل الأطباء بدون Endpoint | API | ✅ أُضيف `GET /api/v1/public/doctors` (يكشف فقط: الاسم، التخصص، المؤسسة، الولاية — بدون بريد أو رخصة) |
| 4b | `verify-email` بدون حقل في DB | Auth | ✅ حُذف `POST /auth/verify-email` من V1 — موافقة الأدمن (`pending → active`) تغني عنه وتوفر تكوين SMTP |
| 5a | اسم مسار التحليل غير موحّد | API | ✅ وُحِّد إلى `POST /api/v1/predict` (متوافق مع المذكرة + pytest) |
| 5b | Grad-CAM++ يُبطئ الاستجابة | `/predict` | ✅ نُقل إلى `FastAPI BackgroundTasks` — النتيجة تُرجع فوراً (< 2s)، Grad-CAM يُحسب بعدها ويُحدّث في DB |
| 5c | Docker يسقط عند أول تشغيل | `docker-compose.yml` | ✅ أُضيف `healthcheck` لـ PostgreSQL (`pg_isready`) + `depends_on: condition: service_healthy` |
| 6 | غياب الموافقة المستنيرة في تدفق الهاتف | Mobile Flow | ✅ إضافة مسار `Routes.CONSENT` كشاشة إلزامية بين الكاميرا والاستمارة لتوثيق موافقة المريض إلكترونياً (GDPR / قانون 18-07) |
| 7 | Grad-CAM++ غير متوفر للمحمول | Mobile UI | ✅ إضافة محول التراكب التفاعلي (Interactive Heatmap Overlay) في `ResultView` لتمكين الطبيب من الفحص البصري الفوري |
| 8 | تعليق الخادم لـ 60 ثانية عند غياب MinIO | Storage Engine | ✅ تطبيق مقبس فحص الاتصال الفوري (Zero-Timeout TCP Probe بمهلة 150ms) والتحويل الآلي الفوري للتخزين المحلي الاحتياطي |
| 9 | انقطاع جلسة الطبيب أثناء الكشف | Mobile Network | ✅ بناء `ApiProvider` مزود بـ `Silent 401 Auto-Refresh Interceptor` لتجديد التوكن دون مقاطعة العمل السريري |
| 10 | غياب عينات تجريبية للمناقشة | Mobile Assets | ✅ إدراج حزمة عينات سريرية معيارية أصلية من `PAD-UFES-20` قابلة للاختبار الفوري بنقرة واحدة أمام لجنة التحكيم |

> [!IMPORTANT]
> **الوثيقة الآن مكتملة ومُراجعة ومُدققة هندسياً.** تمثل هذه النسخة (V2.2) المرجع المعماري النهائي المعتمد المتطابق بنسبة 100% مع نماذج الـ UML وسجل الانحرافات والشيفرة المنفذة في مشروعي الـ Backend والـ Frontend.
---

## 12. 🌐 منصة الموارد والتعريب الثلاثي الشامل (Platform Resources & Trilingual Architecture - V2.1)

تمت ترقية المنصة في مرحلتها النهائية لإدماج طبقة حوكمة الموارد المركزية والنظام اللغوي الثلاثي المتقدم:

### 12.1 البنية اللغوية الثلاثية (Trilingual i18n Architecture)
```
                                 ┌─────────────────────────────────┐
                                 │       DashboardI18n Engine       │
                                 │   (dashboard/assets/js/i18n.js) │
                                 └───────────────┬─────────────────┘
                                                 │
                   ┌─────────────────────────────┼─────────────────────────────┐
                   ▼                             ▼                             ▼
       ┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
       │   English (EN - LTR)   │   │   Français (FR - LTR) │   │     العربية (AR - RTL) │
       │ Clinical terminology  │   │ Medical nomenclature  │   │  التعريب السريري السليم │
       │ dir="ltr"             │   │ dir="ltr"             │   │  dir="rtl"             │
       └───────────────────────┘   └───────────────────────┘   └───────────────────────┘
```
- **المزامنة والتصيير اللحظي**:
  - الربط مع عناصر DOM عبر وسوم `[data-i18n]` و `[data-i18n-placeholder]` و `[data-i18n-title]`.
  - دالة `refreshActiveTabLanguage(lang)` لإعادة تصيير التبويب النشط والمخططات البيانية لحظياً بدون تحديث كامل للمتصفح.
  - تكامل Chart.js: ترجمة تلقائية لتسميات الأمراض الستة ومستويات الخطورة الخمسة.

### 12.2 حوكمة الموارد ومذكرات التخرج (Academic Documentation & Resources Persistence)
- **مذكرتا التخرج الرسميتان (EN & FR)**:
  - الإنجليزية: `Thesis_Master_GLAA_EN.pdf` (2.30 MB).
  - الفرنسية: `Thesis_Master_GLAA_FR.pdf` (2.30 MB).
  - إبقاء قسم التوثيق ظاهراً دوماً للجمهور في صفحة الهبوط `landing.html`.
  - واجهات رفع المشرف في `admin.html` مع التحقق من امتداد PDF والحساب التلقائي للحجم.
- **ملف التكوين والاستمرارية (`platform_resources.json`)**:
  - حفظ وتوثيق روابط APK، الفيديو التوضيحي، إعلانات النظام، ومسارات المذكرات مع ضمان بقائها بعد إعادة تشغيل الخادم.
  - واجهات برمجية مخصصة:
    - `GET /api/v1/public/platform-resources` (Public)
    - `PUT /api/v1/admin/platform-resources` (Admin Protected)
    - `POST /api/v1/admin/platform-resources/upload-apk` (Admin Protected)
    - `POST /api/v1/admin/platform-resources/upload-thesis` (Admin Protected)
- **التوافقية السريرية للمحمول**:
  - نشر مسارات الجذر `/health` و `/predict` بجانب بادئة الإصدار لضمان اتصال سلس مع تطبيق الهاتف Flutter.
- **التحقق الآلي**:
  - اعتماد المنصة واجتيازها **119/119 اختباراً برمجياً مؤتمتاً** بنسبة نجاح 100%.

---

## 13. 🔖 استراتيجية إدارة الإصدارات والعمل التشاركي (Release Management & Collaborative Architecture)

لضمان أعلى معايير الحوكمة البرمجية في إطار **مشروع القرار الوزاري 1275 (مؤسسة ناشئة / براءة اختراع)** والعمل الجماعي بين أعضاء الفريق (Binôme)، تم اعتماد استراتيجية إدارة الإصدارات والتشغيل الموزع التالية:

### 13.1 حوكمة الإصدارات وتأطير النسخ (Git Release & Tagging Strategy)
تم تجميد وحماية نسختين رسميتين متمايزتين على مستودعات Git و GitHub لتمكين لجنة المناقشة من تتبع التطور الهندسي وتحميل أي نسخة برمجية بضغطة زر:
1. **الإصدار الأساسي — Version 1.0 (`v1.0.0` / Branch: `v1.0-baseline`)**:
   - يمثل النموذج الأولي الفردي (Baseline Decision Support MVP).
   - استدلال مباشر لحظي للصور السريرية دون اشتراط قواعد بيانات أو مصادقة.
   - **محمي برخصة الملكية الفكرية الحصرية (Proprietary License - Decree 1275)** لمنع استغلال أو نسخ كود النموذج من أي طرف.
2. **الإصدار الإنتاجي الموسع — Version 2.0 (`v2.0.0` / Branch: `v2.0-telemedicine` & `main`)**:
   - يمثل المنظومة المؤسسية الكاملة الجاهزة للتشغيل التجاري والسريري (Startup-Ready Product).
   - يتضمن: إدارة الحسابات JWT والمصادقة، قاعدة بيانات PostgreSQL 16 مع ترحيلات Alembic، مخزن MinIO، استشارات الطب عن بعد، لوحة التحكم المدمجة، وفحص رمز الـ QR.
   - اجتياز 119/119 اختباراً برمجياً وتطابق كامل مع القرار 1275.

### 13.2 معمارية التشغيل الثنائي الموزع (Two-Node Distributed Deployment)
نظراً لتوزيع المهام في المشروع المشترك، حيث يدير الطالب الأول خادم المعالجة المركزية، بينما يدير الشريك تطبيق العميل المحمول، تم اعتماد المعمارية التشغيلية التالية:
* **عقدة الخادم المركزية (Backend & AI Server Node)**:
  - يُشغّل خادم FastAPI، ونموذج التعلم العميق EfficientNet-B3، وقاعدة البيانات PostgreSQL ومخزن MinIO محلياً.
  - يُبث الخادم عالمياً عبر نفق مشفر فوري **Cloudflare Tunnel (`trycloudflare.com`)** دون الحاجة إلى IP عام ثابت، مما يوفر اتصال HTTPS آمن من الدرجة الطبية.
* **عقدة العميل المحمول (Mobile Client Node - Partner)**:
  - يُشغّل الشريك تطبيق Flutter على هاتفه أو المحاكي.
  - يرتبط بالخادم ديناميكياً عبر شاشة الإعدادات (`SettingsView`) عن طريق إدخال رابط النفق المشفر.
* **سير عمل التطوير والمزامنة (Fork & Pull Request Workflow)**:
  - يعتمد الفريق سير العمل القياسي للبرمجيات مفتوحة/مغلقة المصدر (Forking Workflow).
  - تُرفع مساهمات التطبيق المحمول من مستودع الفرع (`oussamachahoud/app_PFE`) إلى المستودع الرئيسي للشريك (`Abderrahmane-Laidisista/app_PFE`) عبر **Pull Request رسمي (#2)**.
  - بمجرد قبول ودمج الـ PR، يحصل الشريك على التحديثات المعمارية الـ 134 كاملة دون تعارض برمجياً.
