# Processual Maestro Kernel v2.0.0

# Public Runtime Readiness Proof

# إثبات جاهزية تشغيل النسخة العامة

---

## العربية

### 1. معلومات عامة

**المشروع:** Processual Maestro Kernel
**الإصدار:** v2.0.0
**الريبو العام:** `https://github.com/don-zak/processual-maestro-kernel.git`
**الفرع:** `main`
**آخر commit تم التحقق منه محليًا:** `eeb1711`
**بيئة الاختبار:** Windows PowerShell / Localhost
**تاريخ التحقق:** 27 June 2026

هذه الوثيقة تثبت أن النسخة العامة من Processual Maestro Kernel تعمل من الريبو العام وحده، دون الحاجة إلى كشف أو استعمال الريبو الخاص.

---

### 2. الهدف من هذا الإثبات

الهدف ليس إثبات جاهزية إنتاج كاملة، بل إثبات أن النسخة العامة:

* قابلة للتشغيل محليًا.
* تحتوي modules التشغيل الأساسية.
* تعرض API واضحة عبر FastAPI / OpenAPI.
* تفصل بين الريبو العام والريبو الخاص.
* لا تحتاج إلى ملفات private أو مفاتيح API حقيقية حتى تعمل في وضع الاختبار المحلي.
* تحافظ على حماية endpoints المحمية عبر `X-API-Key`.

---

### 3. حالة الريبو العام

تم رفع الريبو العام إلى GitHub بنجاح، وآخر سجل commits محليًا كان:

```text
eeb1711 Ignore governor data Python cache
914d84a Restore public-safe governor data modules
551cad0 Document public repository scope
2a947bc Publish sanitized Processual Maestro Kernel public baseline
```

كما أن حالة العمل كانت نظيفة:

```powershell
git status --short
```

والنتيجة كانت فارغة، ما يعني أن شجرة العمل clean.

---

### 4. إصلاح module التشغيل الناقص

أثناء اختبار النسخة العامة ظهر خطأ:

```text
ModuleNotFoundError: No module named 'processual_api.cgt_governor.data'
```

تبيّن أن السبب هو استبعاد مجلد برمجي مطلوب بسبب قواعد النسخ أو `.gitignore`.

تمت إعادة الملفات العامة الآمنة التالية إلى الريبو العام:

```text
processual_api/cgt_governor/data/__init__.py
processual_api/cgt_governor/data/storage.py
processual_api/cgt_governor/data/telemetry_storage.py
```

وتم تثبيتها في commit:

```text
914d84a Restore public-safe governor data modules
```

ثم تم تجاهل cache Python المحلي في commit:

```text
eeb1711 Ignore governor data Python cache
```

---

### 5. اختبار الاستيراد العام

تم تنفيذ الأمر التالي من داخل الريبو العام:

```powershell
python -c "from processual_api.main import app; print('PUBLIC_IMPORT_OK')"
```

النتيجة:

```text
PUBLIC_IMPORT_OK
```

هذا يثبت أن تطبيق FastAPI يمكن استيراده من النسخة العامة دون الاعتماد على الريبو الخاص.

ظهرت تحذيرات أمنية متوقعة مثل:

```text
JWT_SECRET is still set to the insecure default
API_KEYS is missing or set to a weak value
DATABASE_URL is missing or set to a weak value
REDIS_URL is missing or set to a weak value
```

هذه التحذيرات لا تعني فشل التشغيل المحلي. معناها فقط أن التشغيل الحالي ليس إعداد production، وأنه يجب ضبط متغيرات بيئة قوية قبل أي نشر إنتاجي.

---

### 6. تشغيل السيرفر محليًا

تم تشغيل FastAPI محليًا عبر:

```powershell
$env:API_KEYS="dev-public-test-key"
python -m uvicorn processual_api.main:app --host 127.0.0.1 --port 8000
```

المفتاح `dev-public-test-key` مفتاح اختبار محلي فقط، وليس سرًا إنتاجيًا.

---

### 7. مسارات Health الصحيحة

المسارات الصحية الصحيحة في هذه النسخة هي:

```text
/health/live
/health/ready
```

وليس:

```text
/health
```

اختبار `/health` أعاد:

```json
{"detail":"Not Found"}
```

وهذا طبيعي لأن `/health` ليس route مسجّلًا في هذه النسخة. المسارات الصحيحة هي `/health/live` و`/health/ready`.

---

### 8. إثبات وجود OpenAPI وSwagger

النسخة العامة تعرض OpenAPI وواجهات التوثيق التالية:

```text
/openapi.json
/docs
/redoc
```

كما أن OpenAPI يعرّف API باسم:

```text
Processual Maestro Kernel API
```

وبإصدار:

```text
2.0.0
```

وهذا يثبت أن الواجهة العامة قابلة للفحص التقني عبر Swagger/OpenAPI.

---

### 9. اختبار endpoint محمي: adapters/status

تم تنفيذ:

```powershell
curl.exe -H "X-API-Key: dev-public-test-key" http://127.0.0.1:8000/adapters/status
```

النتيجة:

```json
{
  "providers": [
    {
      "name": "OpenAI",
      "configured": false,
      "default_model": "gpt-4o"
    },
    {
      "name": "Anthropic",
      "configured": false,
      "default_model": "claude-3-5-haiku-latest"
    },
    {
      "name": "Gemini",
      "configured": false,
      "default_model": "gemini-2.0-flash"
    },
    {
      "name": "DeepSeek",
      "configured": false,
      "default_model": "deepseek-chat"
    },
    {
      "name": "OpenCode",
      "configured": true,
      "default_model": "llama3"
    },
    {
      "name": "OpenRouter",
      "configured": false,
      "default_model": "openrouter/free"
    }
  ],
  "default": "OpenCode"
}
```

هذا يثبت أن:

* endpoint يعمل.
* نظام الحماية بالمفتاح يعمل.
* OpenCode مفعّل كمزود محلي افتراضي.
* المزودون الخارجيون غير مفعّلين لأن مفاتيحهم لم تُضبط بعد، وهذا متوقع وآمن.

---

### 10. اختبار endpoint محمي: cgt/govern/status

تم تنفيذ:

```powershell
curl.exe -H "X-API-Key: dev-public-test-key" http://127.0.0.1:8000/cgt/govern/status
```

النتيجة:

```json
{
  "enabled": true,
  "auto_repair": true,
  "max_repair_rounds": 2,
  "providers": [
    {
      "name": "OpenAI",
      "configured": false,
      "default_model": "gpt-4o"
    },
    {
      "name": "Anthropic",
      "configured": false,
      "default_model": "claude-3-5-haiku-latest"
    },
    {
      "name": "Gemini",
      "configured": false,
      "default_model": "gemini-2.0-flash"
    },
    {
      "name": "DeepSeek",
      "configured": false,
      "default_model": "deepseek-chat"
    },
    {
      "name": "OpenCode",
      "configured": true,
      "default_model": "llama3"
    },
    {
      "name": "OpenRouter",
      "configured": false,
      "default_model": "openrouter/free"
    }
  ],
  "default_provider": "OpenCode",
  "evaluation_count": 0
}
```

هذا يثبت أن طبقة CGT Governor مفعّلة، وأن auto-repair مفعّل، وأن المزود الافتراضي هو OpenCode، وأن النظام يبدأ بعدّاد تقييمات صفر في التشغيل المحلي الجديد.

---

### 11. المسارات الأساسية المتاحة

تمت طباعة routes من التطبيق، وتبيّن وجود مسارات رئيسية تشمل:

```text
/health/live
/health/ready
/auth/token
/auth/api-key
/auth/me
/cgt/evaluate
/governance/status
/telemetry/ingest
/telemetry/query
/reports/fate
/reports/generate-llm
/cgt/govern
/cgt/govern/batch
/cgt/govern/status
/cgt/govern/metrics
/cgt/govern/reports
/cgt/govern/compare
/cgt/govern/report
/cgt/govern/simulate
/cgt/analyze
/cgt/govern/gateway/evaluate
/cgt/govern/gateway/agents
/cgt/govern/gateway/dashboard
/adapters/status
/adapters/configure
/adapters/test
/settings
/applications
/billing/checkout
/billing/portal
/billing/webhook
/billing/subscription
/metrics
/docs
/redoc
/openapi.json
```

هذا يثبت أن النسخة العامة ليست مجرد ملفات توثيق، بل API تشغيلية فعلية.

---

### 12. ما الذي لا يحتويه الريبو العام

النسخة العامة sanitized ولا تحتوي عمدًا على:

```text
tests/
cgtlib/private/
data/
processual_api/data/
docs/PRIVATE_REPO_HANDOFF_AR.md
.env
مفاتيح API حقيقية
ملفات JSONL تشغيلية خاصة
تقارير إثبات داخلية خاصة
```

هذا يحقق الفصل بين:

* الريبو الخاص: للتطوير الكامل والاختبارات الداخلية.
* الريبو العام: للتقييم الخارجي والتشغيل العام المحدود والاطلاع التقني.

---

### 13. متطلبات production

قبل أي نشر إنتاجي يجب ضبط متغيرات بيئة قوية، منها:

```text
JWT_SECRET
API_KEYS
DATABASE_URL
REDIS_URL
POSTGRES_PASSWORD
REDIS_PASSWORD
GRAFANA_ADMIN_PASSWORD
```

ويجب عدم رفع أي ملف `.env` إلى GitHub.

---

### 14. حدود هذا الإثبات

هذا الإثبات يؤكد:

* تشغيل API محليًا.
* نجاح الاستيراد.
* نجاح endpoints المحمية بمفتاح.
* ظهور OpenAPI.
* جاهزية الريبو العام للتقييم التقني الأولي.

ولا يؤكد بعد:

* جاهزية production كاملة.
* اتصال كل المزودين الخارجيين.
* نجاح Docker deployment على منصة خارجية.
* تشغيل PostgreSQL/Redis production.
* اختبارات ضغط أو أمان موسعة.

---

### 15. الحكم النهائي

```text
PUBLIC RUNTIME READINESS: PASS
```

النسخة العامة من Processual Maestro Kernel v2.0.0 جاهزة للتشغيل المحلي والتقييم التقني الأولي، مع بقاء إعدادات production والمزودين الخارجيين خطوة لاحقة.

---

---

## English

### 1. General Information

**Project:** Processual Maestro Kernel
**Version:** v2.0.0
**Public repository:** `https://github.com/don-zak/processual-maestro-kernel.git`
**Branch:** `main`
**Latest locally verified commit:** `eeb1711`
**Test environment:** Windows PowerShell / Localhost
**Verification date:** 27 June 2026

This document proves that the public version of Processual Maestro Kernel can run from the public repository alone, without exposing or depending on the private repository.

---

### 2. Purpose of This Proof

This is not a full production-readiness certification. It is a public runtime readiness proof showing that the public repository:

* Can run locally.
* Contains the required runtime modules.
* Exposes a FastAPI/OpenAPI interface.
* Is separated from the private repository.
* Does not require private files or real API keys for local test mode.
* Protects secured endpoints through `X-API-Key`.

---

### 3. Public Repository State

The public repository was pushed to GitHub successfully. The latest local commit history was:

```text
eeb1711 Ignore governor data Python cache
914d84a Restore public-safe governor data modules
551cad0 Document public repository scope
2a947bc Publish sanitized Processual Maestro Kernel public baseline
```

The working tree was clean:

```powershell
git status --short
```

The command returned no output, meaning the local public repository was clean.

---

### 4. Restored Public-Safe Runtime Module

During testing, the public build initially failed with:

```text
ModuleNotFoundError: No module named 'processual_api.cgt_governor.data'
```

The cause was that a required code module had been excluded during public sanitization.

The following public-safe runtime files were restored:

```text
processual_api/cgt_governor/data/__init__.py
processual_api/cgt_governor/data/storage.py
processual_api/cgt_governor/data/telemetry_storage.py
```

They were committed in:

```text
914d84a Restore public-safe governor data modules
```

Python cache files were then ignored in:

```text
eeb1711 Ignore governor data Python cache
```

---

### 5. Public Import Test

The following command was executed from the public repository:

```powershell
python -c "from processual_api.main import app; print('PUBLIC_IMPORT_OK')"
```

Result:

```text
PUBLIC_IMPORT_OK
```

This proves that the FastAPI app can be imported from the public repository without relying on the private repository.

Expected security warnings appeared, such as:

```text
JWT_SECRET is still set to the insecure default
API_KEYS is missing or set to a weak value
DATABASE_URL is missing or set to a weak value
REDIS_URL is missing or set to a weak value
```

These warnings do not indicate local runtime failure. They indicate that production secrets and service URLs must be configured before production deployment.

---

### 6. Local Server Run

The FastAPI server was run locally with a temporary test API key:

```powershell
$env:API_KEYS="dev-public-test-key"
python -m uvicorn processual_api.main:app --host 127.0.0.1 --port 8000
```

The key `dev-public-test-key` is a local test key only. It is not a production secret.

---

### 7. Correct Health Endpoints

The correct health endpoints in this version are:

```text
/health/live
/health/ready
```

Not:

```text
/health
```

Testing `/health` returned:

```json
{"detail":"Not Found"}
```

This is expected because `/health` is not a registered route in this version.

---

### 8. OpenAPI and Swagger Availability

The public runtime exposes:

```text
/openapi.json
/docs
/redoc
```

The OpenAPI definition identifies the API as:

```text
Processual Maestro Kernel API
```

With version:

```text
2.0.0
```

This confirms that the public API is inspectable through Swagger/OpenAPI.

---

### 9. Secured Endpoint Test: adapters/status

The following command was executed:

```powershell
curl.exe -H "X-API-Key: dev-public-test-key" http://127.0.0.1:8000/adapters/status
```

Result:

```json
{
  "providers": [
    {
      "name": "OpenAI",
      "configured": false,
      "default_model": "gpt-4o"
    },
    {
      "name": "Anthropic",
      "configured": false,
      "default_model": "claude-3-5-haiku-latest"
    },
    {
      "name": "Gemini",
      "configured": false,
      "default_model": "gemini-2.0-flash"
    },
    {
      "name": "DeepSeek",
      "configured": false,
      "default_model": "deepseek-chat"
    },
    {
      "name": "OpenCode",
      "configured": true,
      "default_model": "llama3"
    },
    {
      "name": "OpenRouter",
      "configured": false,
      "default_model": "openrouter/free"
    }
  ],
  "default": "OpenCode"
}
```

This proves that:

* The endpoint works.
* API-key protection works.
* OpenCode is configured as the local default provider.
* External providers are intentionally not configured until real API keys are provided.

---

### 10. Secured Endpoint Test: cgt/govern/status

The following command was executed:

```powershell
curl.exe -H "X-API-Key: dev-public-test-key" http://127.0.0.1:8000/cgt/govern/status
```

Result:

```json
{
  "enabled": true,
  "auto_repair": true,
  "max_repair_rounds": 2,
  "providers": [
    {
      "name": "OpenAI",
      "configured": false,
      "default_model": "gpt-4o"
    },
    {
      "name": "Anthropic",
      "configured": false,
      "default_model": "claude-3-5-haiku-latest"
    },
    {
      "name": "Gemini",
      "configured": false,
      "default_model": "gemini-2.0-flash"
    },
    {
      "name": "DeepSeek",
      "configured": false,
      "default_model": "deepseek-chat"
    },
    {
      "name": "OpenCode",
      "configured": true,
      "default_model": "llama3"
    },
    {
      "name": "OpenRouter",
      "configured": false,
      "default_model": "openrouter/free"
    }
  ],
  "default_provider": "OpenCode",
  "evaluation_count": 0
}
```

This proves that the CGT Governor layer is enabled, auto-repair is enabled, the default provider is OpenCode, and the evaluation counter starts at zero in a fresh local runtime.

---

### 11. Available Core Routes

The public runtime exposes key routes including:

```text
/health/live
/health/ready
/auth/token
/auth/api-key
/auth/me
/cgt/evaluate
/governance/status
/telemetry/ingest
/telemetry/query
/reports/fate
/reports/generate-llm
/cgt/govern
/cgt/govern/batch
/cgt/govern/status
/cgt/govern/metrics
/cgt/govern/reports
/cgt/govern/compare
/cgt/govern/report
/cgt/govern/simulate
/cgt/analyze
/cgt/govern/gateway/evaluate
/cgt/govern/gateway/agents
/cgt/govern/gateway/dashboard
/adapters/status
/adapters/configure
/adapters/test
/settings
/applications
/billing/checkout
/billing/portal
/billing/webhook
/billing/subscription
/metrics
/docs
/redoc
/openapi.json
```

This confirms that the public repository is not merely documentation. It exposes a functional API runtime.

---

### 12. What the Public Repository Does Not Contain

The public repository is sanitized and intentionally excludes:

```text
tests/
cgtlib/private/
data/
processual_api/data/
docs/PRIVATE_REPO_HANDOFF_AR.md
.env
real API keys
private JSONL runtime files
private internal proof reports
```

This maintains a clear separation between:

* The private repository: full internal development and testing.
* The public repository: external review, limited public runtime testing, and technical evaluation.

---

### 13. Production Requirements

Before production deployment, strong environment variables must be configured, including:

```text
JWT_SECRET
API_KEYS
DATABASE_URL
REDIS_URL
POSTGRES_PASSWORD
REDIS_PASSWORD
GRAFANA_ADMIN_PASSWORD
```

No `.env` file or real API key should ever be committed to GitHub.

---

### 14. Scope and Limits of This Proof

This proof confirms:

* Local API runtime.
* Successful FastAPI app import.
* Secured endpoint access using `X-API-Key`.
* OpenAPI/Swagger availability.
* Public repository readiness for initial technical review.

It does not yet confirm:

* Full production readiness.
* External provider connectivity.
* Docker deployment on a public host.
* Production PostgreSQL/Redis configuration.
* Load testing or extended security testing.

---

### 15. Final Verdict

```text
PUBLIC RUNTIME READINESS: PASS
```

The public version of Processual Maestro Kernel v2.0.0 is ready for local runtime testing and initial external technical evaluation. Production secrets, external provider keys, and hosted deployment remain separate next steps.
