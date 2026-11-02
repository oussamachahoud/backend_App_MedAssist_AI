# 🚀 دليل تشغيل MedAssist AI Backend ونشره عبر الإنترنت

> **الهدف من هذا الملف**: شرح تام وخطوة بخطوة لكيفية تشغيل خادم الـ Backend على جهازك الشخصي (Windows)
> ثم ربطه بالإنترنت عبر **Cloudflare Tunnel** ليصبح متاحاً من أي مكان في العالم لتطبيق الهاتف.

---

## 🌍 المتطلبات الأساسية

تأكد من توافر ما يلي قبل البدء:

| المتطلب | الإصدار المستخدم | ملاحظة |
|---|---|---|
| **Python** | 3.12 | مثبّت مسبقاً |
| **venv** (البيئة الافتراضية) | مضمّن مع Python | مُعدّ مسبقاً في مجلد `venv/` |
| **ملفات الأوزان (Model Artifacts)** | V6.0 | موجودة في `app/ml_models/` |
| **cloudflared.exe** | 2026.8.3 | مُحمّل مسبقاً في جذر المشروع |

---

## 📋 الخطوة الأولى: تشغيل خادم الـ Backend

### 1.1 — فتح نافذة PowerShell في مجلد المشروع

```powershell
cd "C:\Users\PC\Desktop\m2GLAA MF\backend_App_MedAssist_AI"
```

### 1.2 — تفعيل البيئة الافتراضية (Virtual Environment)

```powershell
.\venv\Scripts\Activate.ps1
```

✅ **علامة النجاح**: ستظهر كلمة `(venv)` في بداية سطر الأوامر:

```
(venv) PS C:\Users\PC\Desktop\m2GLAA MF\backend_App_MedAssist_AI>
```

> **ملاحظة**: إذا ظهر خطأ "Execution Policy"، نفّذ أولاً:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 1.3 — تشغيل الخادم (FastAPI + Uvicorn)

```powershell
.\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
```

✅ **علامة النجاح** (خلال 10-20 ثانية):

```text
🚀 Starting MedAssist AI API v2.0.0
✅ V6.0 Model loaded securely in ~16000 ms | device=cpu | classes=[ACK, BCC, MEL, NEV, SCC, SEK]
✅ API ready | model_loaded=True | device=cpu
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

> ⚠️ انتظر حتى تظهر رسالة `API ready` قبل الانتقال للخطوة التالية.

### 1.4 — التحقق من نجاح التشغيل (محلياً)

- 🩺 **فحص الصحة**: http://localhost:8000/api/v1/health
- 📘 **توثيق Swagger**: http://localhost:8000/docs

```json
{"status": "ok", "model_loaded": true, "version": "2.0.0"}
```

---

## 🌐 الخطوة الثانية: ربط الـ Backend بالإنترنت (Cloudflare Tunnel)

**افتح نافذة PowerShell ثانية جديدة** (الخادم لا يزال يعمل في الأولى):

```powershell
cd "C:\Users\PC\Desktop\m2GLAA MF\backend_App_MedAssist_AI"
.\cloudflared.exe tunnel --url http://localhost:8000
```

✅ **علامة النجاح** (خلال 5-10 ثوانٍ):

```text
INF +--------------------------------------------------------------------------------------------+
INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
INF |  https://XXXX-XXXX-XXXX-XXXX.trycloudflare.com                                             |
INF +--------------------------------------------------------------------------------------------+
INF Registered tunnel connection ... protocol=quic
```

> 💡 انسخ الرابط `https://XXXX-XXXX-XXXX-XXXX.trycloudflare.com` — هذا هو رابطك العام العالمي.

---

## 📱 الخطوة الثالثة: ربط تطبيق Flutter بالرابط الجديد

### من داخل التطبيق (الأسهل):

1. افتح تطبيق Flutter على هاتفك أو المحاكي.
2. اذهب إلى شاشة **الإعدادات (Settings)**.
3. في حقل **API URL**، أدخل الرابط مع `/api/v1` في النهاية:
   ```
   https://XXXX-XXXX-XXXX-XXXX.trycloudflare.com/api/v1
   ```
4. اضغط **Save** ✅

### من الكود (تعديل الرابط الافتراضي):

الملف: `lib/core/services/storage_service.dart` السطر 65:

```dart
// قبل:
String get apiUrl => _box.read(KEY_API_URL) ?? 'http://192.168.222.111:8000/api/v1';

// بعد:
String get apiUrl => _box.read(KEY_API_URL) ?? 'https://XXXX-XXXX-XXXX.trycloudflare.com/api/v1';
```

> ⚠️ **مهم**: يجب أن ينتهي الرابط بـ `/api/v1` لأن التطبيق يضيف `/predict` بعده تلقائياً.

---

## 🗂️ ملخص الأوامر الكاملة (Copy-Paste)

**نافذة Terminal الأولى — Backend:**

```powershell
cd "C:\Users\PC\Desktop\m2GLAA MF\backend_App_MedAssist_AI"
.\venv\Scripts\Activate.ps1
.\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
```

**نافذة Terminal الثانية — Cloudflare Tunnel:**

```powershell
cd "C:\Users\PC\Desktop\m2GLAA MF\backend_App_MedAssist_AI"
.\cloudflared.exe tunnel --url http://localhost:8000
```

---

## 🕐 الجداول الزمنية

| المرحلة | المدة |
|---|---|
| تفعيل البيئة الافتراضية | أقل من 1 ثانية |
| تحميل النموذج في الذاكرة | 10 - 20 ثانية |
| إطلاق Cloudflare Tunnel | 5 - 10 ثوانٍ |
| **الإجمالي حتى الجاهزية الكاملة** | **~30 ثانية** |
| زمن استجابة التنبؤ (use_tta=false) | 30 - 60 ms |
| زمن استجابة التنبؤ (use_tta=true) | 300 - 700 ms |

---

## ⚠️ تنبيهات مهمة

| التنبيه | التفاصيل |
|---|---|
| **الرابط يتغير في كل جلسة** | كل مرة تشغّل `cloudflared.exe` يتغير الرابط. حدّثه في إعدادات التطبيق. |
| **ابقِ كلتا نافذتَي Terminal مفتوحتين** | إغلاق أي منهما يوقف الخدمة فوراً. |
| **الجهاز يجب أن يظل شغّالاً** | النفق يعمل فقط ما دام جهازك يعمل ومتصلاً بالإنترنت. |
| **CORS مفعّل بالكامل** | `ALLOWED_ORIGINS=*` في `.env` يسمح لأي تطبيق بالوصول. |

---

## 🔗 روابط مرجعية

| الاستخدام | الرابط |
|---|---|
| واجهة Swagger التفاعلية | `https://[رابطك].trycloudflare.com/docs` |
| نقطة نهاية التنبؤ | `POST https://[رابطك].trycloudflare.com/api/v1/predict` |
| فحص الصحة | `GET https://[رابطك].trycloudflare.com/api/v1/health` |
| معلومات النموذج | `GET https://[رابطك].trycloudflare.com/api/v1/model/info` |

---

*وُثِّق هذا الدليل بتاريخ 09 سبتمبر 2026 — MedAssist AI V6.0*
