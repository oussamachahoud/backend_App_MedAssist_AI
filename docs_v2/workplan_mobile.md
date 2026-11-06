# 📱 خطة عمل تطبيق الهاتف (Flutter) — MedAssist AI V2

> **المستودع**: `Abderrahmane-Laidisista/app_PFE.git` (origin) + `oussamachahoud/app_PFE.git` (myfork)  
> **الفرع الحالي**: `fix/backend-v6-compatibility`  
> **الفرع الجديد**: `feature/v2-telemedicine-expansion`  
> **آخر تحديث**: 31 أكتوبر 2026

---

## 🔀 إعداد فرع Git

```bash
# من داخل c:\Users\PC\Desktop\m2GLAA MF\app_PFE_frontend
git checkout fix/backend-v6-compatibility
git pull myfork fix/backend-v6-compatibility
git checkout -b feature/v2-telemedicine-expansion
git push myfork feature/v2-telemedicine-expansion
```

---

## المرحلة 0: إصلاحات فورية (Bugs — قبل أي ميزة جديدة)

### 0.1 إصلاح bug مستوى CRITICAL في صفحة النتائج
- [ ] ملف: `lib/modules/result/views/result_view.dart`
- [ ] تعديل `_getRiskLevelTranslation()` لدعم `CRITICAL` + **`INCONCLUSIVE`** (5 مستويات)
- [ ] تعديل `_getRiskColor()` ليعرض لون محايد (رمادي/برتقالي) لـ `INCONCLUSIVE`
- [ ] تعديل `risk_level_badge.dart` لعرض أيقونة `⚠️` مع نص "غير حاسم — يُنصح بإحالة" لـ `INCONCLUSIVE`

### 0.2 إضافة حقل البروز (elevation)
- [ ] ملف: `lib/modules/clinical_form/views/clinical_form_view.dart`
- [ ] إضافة `YesNoSelector` لحقل `elevation` (بروز الآفة)
- [ ] ملف: `lib/modules/clinical_form/controllers/clinical_form_controller.dart`
- [ ] إضافة متغير `elevation` + تضمينه في البيانات المُرسلة
- [ ] ملف: `lib/core/services/api_service.dart`
- [ ] إضافة `elevation` كحقل اختياري في طلب multipart

### 0.3 إزالة API URL من Settings
- [ ] ملف: `lib/modules/settings/views/settings_view.dart`
- [ ] لف قسم API URL بـ `if (kDebugMode)` — يختفي في Release
- [ ] ملف: `lib/modules/settings/controllers/settings_controller.dart`
- [ ] نفس الشرط

### 0.4 إصلاح Deprecated APIs
- [ ] استبدال `withOpacity()` بـ `withValues(alpha:)` في كل الملفات
- [ ] استبدال `textScaleFactor` بـ `textScaler` في `main.dart` (L93)

---

## المرحلة 1: نظام المصادقة (Auth System)

### 1.1 Auth Service جديد
- [ ] إنشاء: `lib/core/services/auth_service.dart`
  - [ ] `login(email, password)` → يحفظ access + refresh tokens في Secure Storage
  - [ ] `register(data)` → يرسل بيانات التسجيل
  - [ ] `refreshToken()` → يجدد access token
  - [ ] `logout()` → يمسح tokens
  - [ ] `isAuthenticated` getter
  - [ ] `currentUser` getter
  - [ ] Auto-refresh interceptor (يجدد token تلقائياً عند 401)

### 1.2 نماذج البيانات
- [ ] إنشاء: `lib/data/models/user_model.dart` — `UserModel` (id, email, role, status, doctorType)
- [ ] إنشاء: `lib/data/models/auth_response.dart` — `AuthResponse` (accessToken, refreshToken, user)
- [ ] إنشاء: `lib/data/models/doctor_profile.dart` — `DoctorProfile` (fullName, specialization, licenseNumber, institutionName, phone, wilaya)

### 1.3 صفحة تسجيل الدخول (`/login`)
- [ ] إنشاء: `lib/modules/auth/views/login_view.dart`
  - [ ] حقل Email + validation
  - [ ] حقل Password + toggle visibility
  - [ ] زر "تسجيل الدخول"
  - [ ] رابط "إنشاء حساب جديد" → Register
  - [ ] رابط "متابعة كـ Guest" (نص صغير)
  - [ ] ملاحظة: "لاسترجاع كلمة المرور، راجع إدارة المنصة"
- [ ] إنشاء: `lib/modules/auth/controllers/login_controller.dart`
- [ ] إنشاء: `lib/modules/auth/bindings/login_binding.dart`

### 1.4 صفحة التسجيل — Stepper (`/register`)
- [ ] إنشاء: `lib/modules/auth/views/register_view.dart`
  - [ ] **الخطوة 1**: الاسم الكامل، Email، كلمة المرور (مع مؤشر قوة)، تأكيد كلمة المرور
  - [ ] **الخطوة 2**: نوع الطبيب (GP/Specialist dropdown)، التخصص، رقم الترخيص، المستشفى، الولاية (58 ولاية dropdown)، الهاتف
  - [ ] زر "إنشاء الحساب"
- [ ] إنشاء: `lib/modules/auth/controllers/register_controller.dart`
- [ ] إنشاء: `lib/modules/auth/bindings/register_binding.dart`

### 1.5 صفحة الانتظار (`/pending-verification`)
- [ ] إنشاء: `lib/modules/auth/views/pending_view.dart`
  - [ ] رسالة: "حسابك قيد المراجعة من قبل إدارة المنصة"
  - [ ] أيقونة ساعة رملية مع animation
  - [ ] زر "تحقق مرة أخرى" (يفحص الحالة)
  - [ ] زر "تسجيل خروج"

### 1.6 صفحة تغيير كلمة المرور الإجبارية (`/force-change-password`)
- [ ] إنشاء: `lib/modules/auth/views/force_change_password_view.dart`
  - [ ] كلمة المرور الجديدة + تأكيد
  - [ ] لا يمكن تخطيها

### 1.7 تعديل Splash
- [ ] ملف: `lib/modules/splash/controllers/splash_controller.dart`
  - [ ] تعديل المنطق:
    ```
    أول مرة؟ → Onboarding
    JWT موجود + صالح؟ → فحص status
      → active → HOME (Doctor)
      → pending → PENDING
      → must_change_password → FORCE_CHANGE
    JWT منتهي؟ → محاولة refresh → نجح؟ HOME : LOGIN
    لا JWT؟ → HOME (Guest)
    ```

### 1.8 Auth Middleware
- [ ] ملف: `lib/core/middleware/auth_middleware.dart`
  - [ ] Guard يمنع الوصول لصفحات التحليل بدون JWT صالح
  - [ ] يُطبّق على: CAMERA, CLINICAL_FORM, ANALYSIS, RESULT, HISTORY, PATIENTS, REFERRALS, PROFILE

### 1.9 تحديث Routes
- [ ] ملف: `lib/app/routes/app_routes.dart` — إضافة Routes الجديدة
- [ ] ملف: `lib/app/routes/app_pages.dart` — تسجيل Pages + Bindings + Middleware

---

## المرحلة 2: تحويل واجهة المستخدم

### 2.1 BottomNavigationBar للطبيب المسجّل
- [ ] إنشاء: `lib/modules/main_layout/views/main_layout_view.dart`
  - [ ] 4 تبويبات: الرئيسية، المرضى، الإحالات، حسابي
  - [ ] يظهر فقط للطبيب المسجّل (`role == doctor`)
- [ ] إنشاء: `lib/modules/main_layout/controllers/main_layout_controller.dart`
- [ ] إنشاء: `lib/modules/main_layout/bindings/main_layout_binding.dart`

### 2.2 تعديل Home حسب الدور
- [ ] ملف: `lib/modules/home/views/home_view.dart`
  - [ ] **Doctor**: "مرحباً د. [الاسم]"، إحصائية سريعة، بطاقتا التقاط/رفع، آخر التحليلات
  - [ ] **Guest**: CTA كبير "سجّل كطبيب"، Education مفتوح، Settings مفتوح، بطاقات مقفلة للتحليل
- [ ] ملف: `lib/modules/home/controllers/home_controller.dart` — فحص auth state

### 2.3 تعديل Onboarding
- [ ] ملف: `lib/modules/onboarding/views/onboarding_view.dart`
  - [ ] إضافة slide أخير: "سجّل كطبيب"
  - [ ] تعديل زر "Get Started" → زرين: "إنشاء حساب" (primary) + "تصفح كـ Guest" (text)

### 2.4 صفحة الملف الشخصي (`/profile`)
- [ ] إنشاء: `lib/modules/profile/views/profile_view.dart`
- [ ] إنشاء: `lib/modules/profile/controllers/profile_controller.dart`
- [ ] إنشاء: `lib/modules/profile/bindings/profile_binding.dart`

### 2.5 صفحة About (`/about`)
- [ ] إنشاء: `lib/modules/about/views/about_view.dart`
- [ ] تسجيلها في `app_pages.dart` (Route موجود لكن بدون Page)

### 2.6 تعديل Settings
- [ ] ملف: `lib/modules/settings/views/settings_view.dart`
  - [ ] Guest: لغة فقط
  - [ ] Doctor: لغة + Dark Mode toggle + "تسجيل خروج" (أحمر)
  - [ ] إزالة API URL (أو `kDebugMode` فقط)

---

## المرحلة 3: شاشة الموافقة + ربط بالسيرفر

### 3.1 شاشة موافقة المريض (Consent Screen)
- [ ] إنشاء: `lib/modules/consent/views/consent_view.dart`
  - [ ] تظهر بعد التقاط الصورة وقبل إرسالها
  - [ ] نص واضح عن تخزين البيانات
  - [ ] مربع تأكيد إلزامي (`patient_consent`)
  - [ ] زر "أوافق وأرسل" + زر "إلغاء"
- [ ] تعديل التدفق: `CAMERA → CONSENT → CLINICAL_FORM`

### 3.2 تعديل API Service لـ JWT
- [ ] ملف: `lib/core/services/api_service.dart`
  - [ ] إضافة `Authorization: Bearer <token>` header
  - [ ] إضافة auto-refresh عند 401
  - [ ] إضافة error handling: 401 → LOGIN, 403 → رسالة, 429 → retry بعد X ثوانٍ

### 3.3 تعديل Analysis/Result لحفظ على السيرفر
- [ ] ملف: `lib/modules/analysis/controllers/analysis_controller.dart`
  - [ ] إرسال `patient_id` و `lesion_tag` مع الطلب (اختياري)
- [ ] ملف: `lib/modules/result/controllers/result_controller.dart`
  - [ ] حفظ `analysis_id` المُرجع من السيرفر
  - [ ] عرض زر "suggest_referral" إذا كان `true`
  - [ ] عرض حالة `INCONCLUSIVE` بصرياً

### 3.4 تعديل History لمزامنة مع السيرفر
- [ ] ملف: `lib/modules/history/controllers/history_controller.dart`
  - [ ] مصدر البيانات: Server أولاً → Local cache كـ fallback
  - [ ] Pagination
- [ ] ملف: `lib/modules/history/views/history_view.dart`
  - [ ] فلترة حسب التاريخ، التشخيص، مستوى الخطر

---

## المرحلة 4: المرضى والإحالات (P1)

### 4.1 وحدة المرضى (مكتملة ومُحدّثة ✅)
- [x] إنشاء: `lib/modules/patients/` (views, controllers, bindings, widgets)
  - [x] قائمة المرضى + بحث + عدّاد الفحوصات الفعلي لكل مريض (`analyses_count`)
  - [x] إنشاء ملف مريض جديد (كود مُجهّل + سنة الميلاد + الجنس)
  - [x] تفاصيل مريض + Lesion Timeline (مخطط خطي ومخطط زمني)
  - [x] التدفق المباشر للفحص: `Patient -> Scan Flow` وزر الفحص السريع من ملف المريض
  - [x] الإكمال التلقائي الذكي لبيانات المريض (الكود، العمر، الجنس) في نموذج الفحص

### 4.2 وحدة الإحالات (مكتملة ✅)
- [x] إنشاء: `lib/modules/referrals/` (views, controllers, bindings)
  - [x] GP: إنشاء إحالة + قائمة الإحالات المُرسلة
  - [x] Specialist: قائمة الإحالات الواردة + نموذج الرد
  - [x] تفاصيل إحالة

### 4.3 Doctor Feedback في صفحة النتائج (مكتمل ✅)
- [x] ملف: `lib/modules/result/views/result_view.dart`
  - [x] زر "هل توافق على التشخيص؟" → BottomSheet
  - [x] نعم / لا (dropdown 6 فئات)
  - [x] هل أُجريت خزعة؟ → نتيجة الخزعة

---

## المرحلة 5: واجهة الزائر/المريض (P1-P2)

### 5.1 ترجمة Education (مكتملة ✅)
- [x] ملف: `lib/modules/education/views/education_view.dart`
  - [x] نقل كل النصوص hardcoded إلى ملفات i18n (AR, EN, FR)
  - [x] إضافة صور توضيحية لكل حرف ABCDE

### 5.2 دليل الأطباء المعتمدين (مكتمل ✅)
- [x] إنشاء: `lib/modules/doctor_directory/` (views, controllers, bindings)
  - [x] يستدعي `GET /api/v1/public/doctors`
  - [x] فلترة بالولاية + التخصص
  - [x] لا يحتاج تسجيل دخول

### 5.3 مسح QR للمتابعة مع الكاميرا المدمجة (مكتمل ومُحدّث ✅)
- [x] إنشاء: `lib/modules/qr_followup/` — يعرض ملخص النتيجة + تاريخ الفحص القادم
  - [x] دمج ماسح الكاميرا المباشر داخل التطبيق (`mobile_scanner: ^5.2.3`)
  - [x] استخراج الـ Token الذكي `extractToken()` من أي رابط URL (مثل `https://medassist.dz/...`) وتجاهل اسم الدومين
  - [x] تصميم متجاوب بدون أي طفح أفقي (`Wrap` + `FittedBox` على `RiskLevelBadge`)
  - [x] طَيّ صندوق الإدخال تلقائياً عند ظهور النتيجة لتركيز الشاشة على التقرير الطبي وموعد المتابعة

---

## قائمة التحقق النهائية

- [ ] كل النصوص الجديدة مُضافة في `ar.dart`, `en.dart`, `fr.dart`
- [ ] Dark Mode يعمل (تفعيل `themeMode` في `main.dart`)
- [ ] لا أخطاء Deprecated (`withOpacity`, `textScaleFactor`)
- [ ] اختبار: Guest flow (تصفح محدود → prompt تسجيل)
- [ ] اختبار: Doctor flow (login → تحليل → نتيجة → حفظ)
- [ ] اختبار: Pending flow (تسجيل → انتظار → تفعيل)
- [ ] اختبار: INCONCLUSIVE risk display
- [ ] اختبار: Offline fallback (history من cache محلي)
