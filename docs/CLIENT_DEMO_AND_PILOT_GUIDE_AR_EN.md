# Processual Maestro Kernel v2.0.0

# Client Demo and Limited Pilot Guide

# دليل عرض العميل والتجربة المحدودة

---

## English

### 1. Purpose

This document explains how to run a controlled client-facing demo or a limited pilot of **Processual Maestro Kernel v2.0.0** using only the public repository.

The goal is to allow an external technical contact, evaluator, or potential client to inspect and test the public runtime without exposing:

* the private development repository;
* private CGT modules;
* internal tests;
* local runtime data;
* private handoff reports;
* `.env` files;
* real provider API keys.

The public repository is intended for technical review, local runtime testing, and limited pilot evaluation.

---

### 2. Recommended Client Evaluation Levels

There are three recommended levels of client access.

#### Level 1 — Documentation Review

The client reviews:

* the public GitHub repository;
* the README;
* the public GitHub Pages documentation;
* the bilingual runtime readiness proof;
* the public repository scope document;
* the external pilot message.

This level does not require running the API.

#### Level 2 — Live Guided Demo

The project owner runs the API locally and demonstrates it to the client through screen sharing.

This is the preferred first demo because it gives the client a real technical view while keeping control over:

* local environment variables;
* API keys;
* provider configuration;
* runtime data;
* internal development material.

#### Level 3 — Limited Local Pilot

The client clones the public repository and runs it locally using their own temporary local API key and, if needed, their own provider keys.

This level is suitable after the client understands the scope and agrees to a limited evaluation.

---

### 3. What the Client Should See

During a controlled demo, the client may see:

* the public GitHub repository;
* the README;
* `docs/PUBLIC_RUNTIME_PROOF_AR_EN.md`;
* `docs/CLIENT_DEMO_AND_PILOT_GUIDE_AR_EN.md`;
* the Swagger/OpenAPI UI at `/docs`;
* `/health/live`;
* `/health/ready`;
* `/adapters/status`;
* `/cgt/govern/status`;
* one or more controlled governance requests to `/cgt/govern` or `/cgt/analyze`.

The client should understand that the public repository is not only documentation. It contains a runnable FastAPI runtime.

---

### 4. What the Client Must Not Receive

Do not share:

* the private repository;
* real API keys;
* `.env` files;
* private tests;
* `cgtlib/private/`;
* raw local data;
* internal proof reports;
* private handoff documents;
* personal provider accounts;
* production database or Redis credentials.

The public repository is designed to be a safe technical boundary.

---

### 5. Prerequisites for a Live Demo

For the live guided demo, the presenter needs:

* Windows PowerShell or a terminal;
* Python environment already prepared;
* the public repository cloned locally;
* local dependencies installed;
* optional local provider such as OpenCode/Ollama if available;
* a temporary local API key.

Example local path:

```text
C:\Users\zaksam\Desktop\Processual_Maestro_PUBLIC_READY
```

---

### 6. Start the Public Runtime

From the public repository root:

```powershell
cd "C:\Users\zaksam\Desktop\Processual_Maestro_PUBLIC_READY"
$env:API_KEYS="client-demo-key"
$env:JWT_SECRET="client-demo-jwt-secret-local-only-change-before-production"
python -m uvicorn processual_api.main:app --host 127.0.0.1 --port 8000
```

The key `client-demo-key` is only a local demo key. It is not a production secret.

---

### 7. Open a Second PowerShell Window

```powershell
Start-Process powershell -ArgumentList '-NoExit','-Command','cd "C:\Users\zaksam\Desktop\Processual_Maestro_PUBLIC_READY"'
```

In the second PowerShell window:

```powershell
$key="client-demo-key"
```

---

### 8. Health Checks

Run:

```powershell
curl.exe http://127.0.0.1:8000/health/live
curl.exe http://127.0.0.1:8000/health/ready
```

Expected meaning:

* `/health/live` proves the API process is alive.
* `/health/ready` proves the runtime is ready for basic requests.

Note: `/health` is not the correct endpoint in this version. The correct endpoints are `/health/live` and `/health/ready`.

---

### 9. Open Swagger/OpenAPI

Open in the browser:

```text
http://127.0.0.1:8000/docs
```

Explain to the client:

```text
This is not a static website. This is the live OpenAPI interface generated from the running FastAPI application.
```

---

### 10. Test Provider Status

Run:

```powershell
curl.exe -H "X-API-Key: client-demo-key" http://127.0.0.1:8000/adapters/status
```

What to explain:

* The endpoint is protected by `X-API-Key`.
* OpenCode can be configured as the local default provider.
* External providers such as OpenAI, Gemini, Anthropic, DeepSeek, and OpenRouter remain unconfigured until real keys are provided.
* This is intentional and protects secrets.

Example interpretation:

```text
OpenCode configured=true means the local provider path is available.
External providers configured=false means no real external API keys are exposed.
```

---

### 11. Test CGT Governor Status

Run:

```powershell
curl.exe -H "X-API-Key: client-demo-key" http://127.0.0.1:8000/cgt/govern/status
```

What to explain:

* `enabled=true` means the governance layer is active.
* `auto_repair=true` means the repair loop is available.
* `default_provider` shows which provider is used by default.
* `evaluation_count=0` is normal on a fresh local runtime.

---

### 12. Run a Simple Governance Evaluation

Use `/cgt/govern` with a controlled example:

```powershell
curl.exe -X POST -H "X-API-Key: client-demo-key" -H "Content-Type: application/json" -d "{\"client_query\":\"Give a clear refund policy summary.\",\"answer\":\"Customers can request a refund within 30 days with proof of purchase. Used or damaged items may be excluded depending on the policy.\",\"language\":\"en\"}" http://127.0.0.1:8000/cgt/govern
```

Purpose of this step:

* show that the runtime can evaluate an actual answer;
* demonstrate governance indicators;
* show that the system is not only reporting status;
* introduce the idea of answer assessment, rank, reward, policy, and repair.

---

### 13. Optional Raw CGT Analysis

Use `/cgt/analyze` when the goal is to inspect the analyzer without the full governance flow:

```powershell
curl.exe -X POST -H "X-API-Key: client-demo-key" -H "Content-Type: application/json" -d "{\"client_query\":\"Summarize a refund policy.\",\"answer\":\"Refunds are available within 30 days with proof of purchase.\",\"language\":\"en\"}" http://127.0.0.1:8000/cgt/analyze
```

---

### 14. Suggested Demo Script

A simple client demo should follow this order:

1. Show the public GitHub repository.
2. Show the README.
3. Show the public runtime readiness proof.
4. Explain that the private repository is not exposed.
5. Start the API locally.
6. Open `/docs`.
7. Run `/health/live` and `/health/ready`.
8. Run `/adapters/status`.
9. Run `/cgt/govern/status`.
10. Run one `/cgt/govern` evaluation.
11. Ask the client what use case they want to test next.

---

### 15. Suggested Client Explanation

Use this short explanation:

```text
This is the public, sanitized runtime of Processual Maestro Kernel.
It lets you inspect the API, run a local test, and evaluate controlled examples without access to the private development repository.
The private repository remains reserved for internal development, tests, and extended research.
The public version is sufficient for initial technical evaluation and pilot discussion.
```

---

### 16. Limited Pilot Plan

A recommended limited pilot lasts between 7 and 14 days.

#### Scope

The client may:

* clone the public repository;
* run the API locally;
* inspect OpenAPI;
* test health endpoints;
* test `/adapters/status`;
* test `/cgt/govern/status`;
* send 5 to 10 controlled examples to `/cgt/govern`;
* report usability and integration feedback.

#### Out of Scope

The client should not receive:

* private source code;
* private tests;
* real owner API keys;
* internal datasets;
* production deployment access;
* unrestricted hosted API access.

#### Pilot Outputs

At the end of the pilot, collect:

* whether installation succeeded;
* whether the API was understandable;
* whether OpenAPI was useful;
* whether governance outputs were clear;
* which provider the client wants to test;
* whether they need local, Docker, or hosted deployment;
* whether a second pilot with external provider keys is justified.

---

### 17. When to Move to Hosted Deployment

A hosted deployment should only be considered after the client confirms:

* the public local runtime is useful;
* the API shape fits their use case;
* they understand the security boundary;
* they want to test with real provider keys;
* there is a clear pilot objective.

For hosted deployment, GitHub Pages is not enough because GitHub Pages only hosts static documentation. The FastAPI backend requires a runtime platform such as a VPS, Render, Railway, Fly.io, or another container-capable host.

---

### 18. Production Checklist

Before production deployment, configure strong values for:

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

---

### 19. Final Demo Readiness Verdict

```text
CLIENT DEMO READINESS: READY
LIMITED PUBLIC PILOT: READY WITH LOCAL RUNTIME
HOSTED PRODUCTION: NOT YET, REQUIRES DEPLOYMENT SETUP
```

---

---

## العربية

### 1. الهدف

تشرح هذه الوثيقة كيفية تنفيذ عرض مضبوط لعميل، أو تجربة pilot محدودة، اعتمادًا على الريبو العام فقط من **Processual Maestro Kernel v2.0.0**.

الغاية هي تمكين جهة تقنية خارجية أو عميل محتمل من الاطلاع والاختبار دون كشف:

* الريبو الخاص؛
* modules الخاصة؛
* الاختبارات الداخلية؛
* بيانات التشغيل المحلية؛
* تقارير الانتقال الخاصة؛
* ملفات `.env`؛
* مفاتيح API الحقيقية.

الريبو العام مخصص للمراجعة التقنية، والاختبار المحلي، والتقييم التجريبي المحدود.

---

### 2. مستويات اطلاع العميل المقترحة

هناك ثلاثة مستويات آمنة للاطلاع.

#### المستوى 1 — الاطلاع الوثائقي

يراجع العميل:

* الريبو العام على GitHub؛
* README؛
* صفحة GitHub Pages العامة؛
* وثيقة إثبات الجاهزية الثنائية اللغة؛
* وثيقة نطاق الريبو العام؛
* رسالة pilot الخارجية.

هذا المستوى لا يحتاج تشغيل API.

#### المستوى 2 — عرض حي موجه

يشغّل صاحب المشروع API محليًا ويعرضه للعميل عبر مشاركة الشاشة.

هذا هو الخيار الأفضل لأول عرض، لأنه يعطي العميل مشاهدة تقنية حقيقية مع الحفاظ على التحكم في:

* متغيرات البيئة؛
* مفاتيح API؛
* إعداد المزودين؛
* بيانات التشغيل؛
* المواد الداخلية الخاصة.

#### المستوى 3 — Pilot محلي محدود

ينسخ العميل الريبو العام ويشغّله عنده محليًا باستعمال مفتاح مؤقت خاص به، ويمكنه لاحقًا ضبط مفاتيح مزودين خارجية تخصه هو.

هذا المستوى مناسب بعد فهم العميل للحدود والموافقة على تجربة محدودة.

---

### 3. ما الذي يمكن أن يراه العميل

في عرض مضبوط، يمكن للعميل أن يرى:

* الريبو العام على GitHub؛
* README؛
* `docs/PUBLIC_RUNTIME_PROOF_AR_EN.md`;
* `docs/CLIENT_DEMO_AND_PILOT_GUIDE_AR_EN.md`;
* واجهة Swagger/OpenAPI على `/docs`;
* `/health/live`;
* `/health/ready`;
* `/adapters/status`;
* `/cgt/govern/status`;
* طلبًا أو أكثر إلى `/cgt/govern` أو `/cgt/analyze`.

يجب أن يفهم العميل أن الريبو العام ليس مجرد توثيق، بل يحتوي runtime فعليًا قابلًا للتشغيل.

---

### 4. ما لا يجب تسليمه للعميل

لا تسلّم:

* الريبو الخاص؛
* مفاتيح API حقيقية؛
* ملفات `.env`؛
* الاختبارات الخاصة؛
* `cgtlib/private/`;
* بيانات التشغيل الخام؛
* تقارير الإثبات الداخلية؛
* وثائق handoff الخاصة؛
* حسابات المزودين الشخصية؛
* بيانات PostgreSQL أو Redis الإنتاجية.

الريبو العام هو الحدّ التقني الآمن.

---

### 5. متطلبات العرض الحي

لتنفيذ عرض حي موجه، تحتاج إلى:

* Windows PowerShell أو Terminal؛
* بيئة Python جاهزة؛
* الريبو العام محليًا؛
* dependencies منصبة؛
* مزود محلي اختياري مثل OpenCode/Ollama إذا كان متاحًا؛
* مفتاح API محلي مؤقت.

مثال مسار محلي:

```text
C:\Users\zaksam\Desktop\Processual_Maestro_PUBLIC_READY
```

---

### 6. تشغيل النسخة العامة

من جذر الريبو العام:

```powershell
cd "C:\Users\zaksam\Desktop\Processual_Maestro_PUBLIC_READY"
$env:API_KEYS="client-demo-key"
$env:JWT_SECRET="client-demo-jwt-secret-local-only-change-before-production"
python -m uvicorn processual_api.main:app --host 127.0.0.1 --port 8000
```

المفتاح `client-demo-key` مخصص للعرض المحلي فقط، وليس سرًا إنتاجيًا.

---

### 7. فتح PowerShell ثانية

```powershell
Start-Process powershell -ArgumentList '-NoExit','-Command','cd "C:\Users\zaksam\Desktop\Processual_Maestro_PUBLIC_READY"'
```

في نافذة PowerShell الثانية:

```powershell
$key="client-demo-key"
```

---

### 8. اختبار Health

نفّذ:

```powershell
curl.exe http://127.0.0.1:8000/health/live
curl.exe http://127.0.0.1:8000/health/ready
```

المعنى:

* `/health/live` يثبت أن عملية API حية.
* `/health/ready` يثبت أن runtime جاهز للطلبات الأساسية.

ملاحظة: `/health` ليس المسار الصحيح في هذه النسخة. المسارات الصحيحة هي `/health/live` و`/health/ready`.

---

### 9. فتح Swagger/OpenAPI

افتح في المتصفح:

```text
http://127.0.0.1:8000/docs
```

اشرح للعميل:

```text
هذه ليست صفحة ثابتة، بل واجهة OpenAPI حية مولّدة من تطبيق FastAPI الذي يعمل الآن.
```

---

### 10. اختبار حالة المزودين

نفّذ:

```powershell
curl.exe -H "X-API-Key: client-demo-key" http://127.0.0.1:8000/adapters/status
```

ما يجب شرحه:

* هذا endpoint محمي عبر `X-API-Key`.
* OpenCode يمكن أن يكون المزود المحلي الافتراضي.
* المزودون الخارجيون مثل OpenAI وGemini وAnthropic وDeepSeek وOpenRouter يبقون غير مفعّلين حتى يتم وضع مفاتيح حقيقية.
* هذا مقصود لحماية الأسرار.

تفسير نموذجي:

```text
OpenCode configured=true يعني أن مسار المزود المحلي متاح.
External providers configured=false يعني أننا لا نكشف أي مفاتيح خارجية حقيقية.
```

---

### 11. اختبار حالة CGT Governor

نفّذ:

```powershell
curl.exe -H "X-API-Key: client-demo-key" http://127.0.0.1:8000/cgt/govern/status
```

ما يجب شرحه:

* `enabled=true` يعني أن طبقة الحوكمة مفعّلة.
* `auto_repair=true` يعني أن مسار الإصلاح متاح.
* `default_provider` يبين المزود الافتراضي.
* `evaluation_count=0` طبيعي في تشغيل محلي جديد.

---

### 12. تنفيذ تقييم حوكمة بسيط

استعمل `/cgt/govern` بمثال مضبوط:

```powershell
curl.exe -X POST -H "X-API-Key: client-demo-key" -H "Content-Type: application/json" -d "{\"client_query\":\"Give a clear refund policy summary.\",\"answer\":\"Customers can request a refund within 30 days with proof of purchase. Used or damaged items may be excluded depending on the policy.\",\"language\":\"en\"}" http://127.0.0.1:8000/cgt/govern
```

هدف هذه الخطوة:

* إثبات أن runtime يقيّم جوابًا فعليًا؛
* عرض مؤشرات الحوكمة؛
* توضيح أن النظام لا يكتفي بعرض status؛
* تقديم فكرة assessment وrank وreward وpolicy وrepair.

---

### 13. تحليل CGT اختياري

استعمل `/cgt/analyze` عندما يكون الهدف فحص analyzer دون مسار الحوكمة الكامل:

```powershell
curl.exe -X POST -H "X-API-Key: client-demo-key" -H "Content-Type: application/json" -d "{\"client_query\":\"Summarize a refund policy.\",\"answer\":\"Refunds are available within 30 days with proof of purchase.\",\"language\":\"en\"}" http://127.0.0.1:8000/cgt/analyze
```

---

### 14. سيناريو العرض المقترح

اتبع هذا الترتيب:

1. عرض الريبو العام على GitHub.
2. عرض README.
3. عرض وثيقة إثبات جاهزية التشغيل.
4. شرح أن الريبو الخاص غير مكشوف.
5. تشغيل API محليًا.
6. فتح `/docs`.
7. اختبار `/health/live` و`/health/ready`.
8. اختبار `/adapters/status`.
9. اختبار `/cgt/govern/status`.
10. تنفيذ تقييم واحد عبر `/cgt/govern`.
11. سؤال العميل عن حالة الاستخدام التي يريد اختبارها لاحقًا.

---

### 15. صيغة شرح قصيرة للعميل

يمكن استعمال النص التالي:

```text
هذه هي النسخة العامة والمنقّحة من Processual Maestro Kernel.
تمكّنك من فحص API وتشغيل اختبار محلي وتقييم أمثلة مضبوطة دون الوصول إلى الريبو الخاص.
الريبو الخاص يبقى مخصصًا للتطوير الداخلي والاختبارات والبحث الموسع.
النسخة العامة كافية للتقييم التقني الأولي ونقاش pilot محدود.
```

---

### 16. خطة Pilot محدودة

المدة المقترحة:

```text
7 إلى 14 يومًا
```

#### النطاق

يمكن للعميل:

* نسخ الريبو العام؛
* تشغيل API محليًا؛
* فحص OpenAPI؛
* اختبار health endpoints؛
* اختبار `/adapters/status`;
* اختبار `/cgt/govern/status`;
* إرسال 5 إلى 10 أمثلة مضبوطة إلى `/cgt/govern`;
* إرسال ملاحظات عن سهولة الاستعمال وإمكانات الدمج.

#### خارج النطاق

لا يحصل العميل على:

* الكود الخاص؛
* الاختبارات الخاصة؛
* مفاتيح API الخاصة بك؛
* datasets داخلية؛
* وصول إنتاجي؛
* API مستضاف غير محدود.

#### مخرجات Pilot

في نهاية التجربة، يتم جمع:

* هل نجح التثبيت؟
* هل كانت API مفهومة؟
* هل كان OpenAPI مفيدًا؟
* هل كانت مخرجات الحوكمة واضحة؟
* أي مزود يريد العميل اختباره؟
* هل يحتاج تشغيلًا محليًا أو Docker أو hosted deployment؟
* هل تستحق المرحلة الثانية تفعيل مفاتيح مزودين خارجية؟

---

### 17. متى ننتقل إلى نشر مستضاف

لا ننتقل إلى نشر مستضاف إلا إذا أكد العميل:

* أن التشغيل المحلي العام مفيد؛
* أن شكل API مناسب لحالة استخدامه؛
* أنه يفهم الحدود الأمنية؛
* أنه يريد اختبار مفاتيح مزودين حقيقية؛
* أن هناك هدف pilot واضحًا.

GitHub Pages لا يكفي لتشغيل backend؛ هو يصلح للتوثيق الثابت فقط. أما FastAPI فيحتاج منصة تشغيل مثل VPS أو Render أو Railway أو Fly.io أو أي منصة تدعم containers.

---

### 18. قائمة production

قبل أي نشر إنتاجي، يجب ضبط قيم قوية لـ:

```text
JWT_SECRET
API_KEYS
DATABASE_URL
REDIS_URL
POSTGRES_PASSWORD
REDIS_PASSWORD
GRAFANA_ADMIN_PASSWORD
```

لا ترفع أبدًا `.env` أو مفاتيح API حقيقية إلى GitHub.

---

### 19. الحكم النهائي لجاهزية العرض

```text
CLIENT DEMO READINESS: READY
LIMITED PUBLIC PILOT: READY WITH LOCAL RUNTIME
HOSTED PRODUCTION: NOT YET, REQUIRES DEPLOYMENT SETUP
```
