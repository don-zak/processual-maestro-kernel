# Processual Maestro Kernel v2.0.0

# Public Technical Page

# الصفحة التقنية العامة

---

## English

### Public Runtime Status

**Status:** Public runtime readiness verified.

Processual Maestro Kernel v2.0.0 is a governance middleware for AI agent workflows. This public repository is a sanitized, runnable edition prepared for external technical review, local runtime testing, and limited pilot evaluation without exposing the private development repository.

### What is verified

The public runtime has been verified locally with:

* FastAPI import from the public repository;
* Uvicorn local server startup;
* OpenAPI / Swagger documentation;
* `X-API-Key` protected endpoints;
* `/health/live` and `/health/ready`;
* `/adapters/status`;
* `/cgt/govern/status`;
* OpenCode configured as the default local provider.

### Main documents

* [Public Runtime Readiness Proof AR/EN](./PUBLIC_RUNTIME_PROOF_AR_EN.md)
* [External Pilot Message AR/EN/FR](./EXTERNAL_PILOT_MESSAGE_AR_EN_FR.md)
* [Repository Scope AR](./REPOSITORY_SCOPE_AR.md)

### Quick local test

From the public repository root:

```powershell
$env:API_KEYS="dev-public-test-key"
python -m uvicorn processual_api.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell window:

```powershell
curl.exe http://127.0.0.1:8000/health/live
curl.exe http://127.0.0.1:8000/health/ready
curl.exe -H "X-API-Key: dev-public-test-key" http://127.0.0.1:8000/adapters/status
curl.exe -H "X-API-Key: dev-public-test-key" http://127.0.0.1:8000/cgt/govern/status
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

### Production note

The local test key is only for development. Before production deployment, strong environment variables must be configured:

```text
JWT_SECRET
API_KEYS
DATABASE_URL
REDIS_URL
POSTGRES_PASSWORD
REDIS_PASSWORD
GRAFANA_ADMIN_PASSWORD
```

Never commit `.env` files or real API keys to GitHub.

### Final verdict

```text
PUBLIC RUNTIME READINESS: PASS
```

---

## العربية

### حالة تشغيل النسخة العامة

**الحالة:** تم التحقق من جاهزية تشغيل النسخة العامة.

Processual Maestro Kernel v2.0.0 هو وسيط حوكمة لسير عمل وكلاء الذكاء الاصطناعي. هذا الريبو العام هو نسخة منقّحة وقابلة للتشغيل، مخصصة للمراجعة التقنية الخارجية، والاختبار المحلي، والتقييم التجريبي المحدود دون كشف الريبو الخاص.

### ما الذي تم التحقق منه

تم التحقق محليًا من:

* نجاح استيراد تطبيق FastAPI من الريبو العام؛
* تشغيل السيرفر محليًا عبر Uvicorn؛
* ظهور OpenAPI / Swagger؛
* عمل الحماية عبر `X-API-Key`؛
* عمل `/health/live` و`/health/ready`؛
* عمل `/adapters/status`؛
* عمل `/cgt/govern/status`؛
* تفعيل OpenCode كمزود محلي افتراضي.

### الوثائق الرئيسية

* [إثبات جاهزية التشغيل بالعربية والإنجليزية](./PUBLIC_RUNTIME_PROOF_AR_EN.md)
* [رسالة pilot خارجية بالعربية والإنجليزية والفرنسية](./EXTERNAL_PILOT_MESSAGE_AR_EN_FR.md)
* [نطاق الريبو العام والخاص](./REPOSITORY_SCOPE_AR.md)

### اختبار محلي سريع

من جذر الريبو العام:

```powershell
$env:API_KEYS="dev-public-test-key"
python -m uvicorn processual_api.main:app --host 127.0.0.1 --port 8000
```

في نافذة PowerShell ثانية:

```powershell
curl.exe http://127.0.0.1:8000/health/live
curl.exe http://127.0.0.1:8000/health/ready
curl.exe -H "X-API-Key: dev-public-test-key" http://127.0.0.1:8000/adapters/status
curl.exe -H "X-API-Key: dev-public-test-key" http://127.0.0.1:8000/cgt/govern/status
```

واجهة Swagger:

```text
http://127.0.0.1:8000/docs
```

### ملاحظة إنتاجية

مفتاح الاختبار المحلي أعلاه مخصص للتطوير فقط. قبل أي نشر إنتاجي يجب ضبط متغيرات بيئة قوية:

```text
JWT_SECRET
API_KEYS
DATABASE_URL
REDIS_URL
POSTGRES_PASSWORD
REDIS_PASSWORD
GRAFANA_ADMIN_PASSWORD
```

لا ترفع أبدًا ملفات `.env` أو مفاتيح API حقيقية إلى GitHub.

### الحكم النهائي

```text
PUBLIC RUNTIME READINESS: PASS
```
