# تقرير تدقيق Usage Logging بعد KEY-QUOTA-02

## Processual Maestro Kernel v2.0.0

### KEY-USAGE-01 — Audit usage_log middleware and store

---

## 1. الغرض من التقرير

هذا التقرير يوثق حالة نظام تسجيل الاستعمال `usage logging` في مشروع **Processual Maestro Kernel v2.0.0** بعد تثبيت طبقة API Keys وQuota، وبعد إضافة اختبارات regression مباشرة لمسار استنفاد الحصة.

الغرض من هذا التدقيق هو معرفة ما إذا كان النظام الحالي يسجل استعمال API Keys بما يكفي لمرحلة paid pilot، وقبل الانتقال إلى Cloud Run أو أي نشر إنتاجي.

هذا التقرير لا يضيف كودًا جديدًا، بل يثبت الحالة الحالية، ويحدد النواقص، ويقترح المهام التالية.

---

## 2. السياق الحالي

الفرع الحالي:

```text
pmk-productization-auth-pricing-usage-cloudrun
```

آخر baseline مثبت قبل هذا التدقيق:

```text
b1ca46b KEY-QUOTA-02 add exhausted quota endpoint regression
```

آخر تحقق شامل معروف:

```text
Ruff: PASS
Pytest: 185 passed, 6 warnings
Compileall: PASS
Git: clean
```

---

## 3. الملفات التي تم تدقيقها

الملف الرئيسي للـ middleware:

```text
processual_api/middleware/usage_log.py
```

ملف التفعيل داخل التطبيق:

```text
processual_api/main.py
```

ملف تخزين usage logs:

```text
processual_api/services/usage_log_store.py
```

ملف السجلات المحلي الحالي:

```text
processual_api/data/usage_logs.jsonl
```

ملف الاختبارات الذي يحتوي تغطية حالية للـ middleware:

```text
tests/test_middleware_regression.py
```

---

## 4. النتيجة العامة

نظام usage logging موجود وفعّال، وليس مجرد تصميم نظري.

`UsageLogMiddleware` مفعّل داخل التطبيق عبر:

```text
app.add_middleware(UsageLogMiddleware)
```

ويقوم بتسجيل طلبات API Key بعد اكتمال معالجة الطلب، بشرط أن يكون:

```text
request.state.current_user
```

موجودًا، وأن تكون طريقة المصادقة:

```text
auth_method = api_key
```

الحكم:

```text
Usage logging layer موجودة وقابلة للبناء عليها.
```

لكنها لا تزال تحتاج إلى توسيع اختبارات regression وتقوية أمنية قبل اعتبارها production-ready.

---

## 5. الحقول المسجلة حاليًا

يسجل النظام الحقول التالية:

```text
created_at
request_id
client_id
user_id
api_key_id
api_key_prefix
auth_method
session_type
method
endpoint
status_code
latency_ms
role
```

هذه الحقول تغطي الحد الأدنى المهم لربط الاستعمال بـ:

```text
العميل
المستخدم
مفتاح API
المسار
كود الاستجابة
زمن التنفيذ
نوع الجلسة
الدور
```

---

## 6. تخزين السجلات الحالي

التخزين الحالي يتم داخل:

```text
processual_api/data/usage_logs.jsonl
```

عن طريق:

```text
processual_api/services/usage_log_store.py
```

الدالة الحالية:

```text
append_usage_log(record)
```

تقوم بإنشاء سجل نظيف `clean_record`، ثم تكتبه كسطر JSON داخل ملف JSONL.

الحكم:

```text
التخزين المحلي JSONL مناسب للتطوير والاختبار المحلي.
```

لكنه ليس storage production-ready نهائيًا، لأنه لا يحتوي حاليًا على:

```text
rotation
retention policy
database backend
concurrency strategy قوية
query API
indexing
tenant isolation على مستوى التخزين
```

---

## 7. ما ثبت من ملف usage_logs.jsonl

ملف:

```text
processual_api/data/usage_logs.jsonl
```

يثبت وجود سجلات فعلية لطلبات API Key.

ظهرت سجلات لمسارات مثل:

```text
/adapters/status
/cgt/govern
/settings/api-keys
/settings/plans
/adapters/configure
/adapters/test
```

كما ظهرت status codes مختلفة:

```text
200
403
404
429
```

وهذا يعني أن usage logging لا يسجل فقط الطلبات الناجحة، بل يسجل أيضًا بعض الطلبات المرفوضة بعد نجاح التحقق من API Key.

---

## 8. إثبات تسجيل quota_exceeded

ظهر سجل فعلي لمسار:

```text
POST /cgt/govern
```

مع:

```text
status_code = 429
```

وهذا يثبت أن طلبات quota exhausted يمكن أن تصل إلى usage log عندما يكون المفتاح صحيحًا وتم تحميل `current_user`.

الحكم:

```text
quota_exceeded usage logging موجود عمليًا.
```

لكن يجب تثبيته باختبار regression صريح في المرحلة التالية، لأن وجوده في السجل المحلي وحده ليس كافيًا كضمان دائم.

---

## 9. الاختبارات الحالية

يوجد أصلًا اختبار مباشر داخل:

```text
tests/test_middleware_regression.py
```

باسم:

```text
test_usage_log_middleware_records_api_key_user
```

هذا الاختبار يثبت أن `UsageLogMiddleware` يسجل طلب API Key ويحتفظ بحقول مثل:

```text
request_id
api_key_id
api_key_prefix
status_code
latency_ms
```

لذلك، لا يجب أن تكون المهمة التالية مجرد إضافة أول اختبار usage log عام، لأن هذا موجود بالفعل.

المطلوب الآن هو توسيع التغطية لتشمل:

```text
usage_log_store schema
endpoint sanitization
quota_exceeded 429 logging
403 scoped rejection logging
raw API key leakage prevention
```

---

## 10. حدود التسجيل الحالية

النظام الحالي يسجل فقط إذا تحقق الشرطان:

```text
request.state.current_user موجود
auth_method = api_key
```

هذا يعني أن الطلبات التالية قد لا تُسجل:

```text
1. طلب بدون Authorization أو X-API-Key.
2. طلب بمفتاح API غير صالح.
3. طلب JWT عادي للواجهة.
4. طلب يفشل قبل ضبط request.state.current_user.
```

هذا قد يكون مقبولًا في المرحلة الحالية إذا كان القرار المعماري هو تسجيل API Key usage فقط، لكنه يجب أن يكون موثقًا بوضوح.

القرار الحالي المقترح:

```text
KEY-USAGE يركز على API Key usage.
JWT/UI audit logging يبقى مهمة منفصلة لاحقًا.
```

---

## 11. ملاحظة أمنية مهمة: خطر تسريب raw API key داخل endpoint

ظهر في بعض السجلات القديمة أن قيمة `endpoint` تحتوي مسارًا مثل:

```text
/settings/api-keys/pmk_.../plan
```

وهذا يعني أن raw API key قد يظهر داخل usage log إذا وصل المفتاح إلى URL path.

هذه نقطة أمنية مهمة.

الحكم:

```text
لا يوجد تسريب raw API key كحقل مستقل.
لكن يوجد خطر تسريب raw API key داخل endpoint path إذا استُعمل المفتاح الخام في المسار.
```

المطلوب لاحقًا:

```text
1. منع استعمال raw API key في URL path.
2. اعتماد api_key_id فقط في مسارات الإدارة.
3. إضافة sanitize للـ endpoint قبل التسجيل.
4. إضافة regression test يثبت أن usage log لا يحتوي pmk_ داخل endpoint.
```

---

## 12. تقييم الجاهزية

### ما هو جيد

```text
UsageLogMiddleware موجود.
Middleware مفعّل في main.py.
append_usage_log موجود.
usage_logs.jsonl موجود كتخزين محلي.
يسجل API key requests.
يسجل request_id.
يسجل client_id.
يسجل user_id.
يسجل api_key_id.
يسجل api_key_prefix.
يسجل auth_method.
يسجل session_type.
يسجل method.
يسجل endpoint.
يسجل status_code.
يسجل latency_ms.
يسجل role.
يسجل 403/404/429 بعد تحقق API key.
يسجل quota_exceeded عمليًا.
يوجد اختبار middleware مباشر حالي.
لا يسجل raw API key كحقل مستقل.
```

### ما يحتاج تقوية

```text
لا يوجد usage_id واضح في السجل الحالي.
لا يوجد sanitize مضمون للـ endpoint.
لا يوجد اختبار يمنع ظهور pmk_ في usage log.
لا يوجد اختبار endpoint حقيقي يثبت أن 429 quota_exceeded ينتج usage log.
لا يوجد اختبار صريح لـ usage_log_store schema.
التخزين JSONL محلي وليس production storage.
لا توجد rotation أو retention policy.
لا يوجد ربط واضح بـ evaluation_id أو report_id.
لا توجد token metrics.
لا توجد provider/model fields في middleware الحالي.
```

---

## 13. قرار KEY-USAGE-01

الحكم النهائي:

```text
KEY-USAGE-01 audit: PASS
```

بمعنى أن طبقة usage logging موجودة وتعمل، ويمكن الانتقال إلى توسيع اختبارات regression.

لكن لا يجوز اعتبارها production-ready قبل تنفيذ:

```text
KEY-USAGE-02
KEY-USAGE-03
Storage hardening لاحقًا
```

---

## 14. المهمة التالية: KEY-USAGE-02

اسم المهمة المقترح:

```text
KEY-USAGE-02 — Extend usage logging regression coverage
```

المطلوب:

```text
1. تثبيت أن usage_log_store يكتب schema نظيفًا.
2. تثبيت أن الحقول الأساسية محفوظة.
3. تثبيت أن raw API key لا يظهر كحقل مستقل.
4. تثبيت أن endpoint لا يحتوي pmk_ بعد إضافة sanitize.
5. تثبيت أن 429 quota_exceeded ينتج usage log عبر endpoint حقيقي.
6. تثبيت أن 403 scoped rejection يسجل عندما يكون API key صحيحًا.
```

الملفات المتوقعة:

```text
processual_api/services/usage_log_store.py
processual_api/middleware/usage_log.py
tests/test_middleware_regression.py
```

---

## 15. المهمة التالية بعدها: KEY-USAGE-03

اسم المهمة المقترح:

```text
KEY-USAGE-03 — Harden usage endpoint sanitization and quota rejection logging
```

المطلوب:

```text
1. إضافة sanitize للـ endpoint قبل تسجيله.
2. منع ظهور أي pmk_ داخل usage log.
3. تثبيت أن rejected quota request status_code=429 يسجل.
4. تثبيت أن rejected scoped request status_code=403 يسجل إذا كان API key صحيحًا.
5. ضمان عدم تسجيل X-API-Key الخام في أي حقل.
```

---

## 16. توصية حول usage_id

السجل الحالي لا يحتوي:

```text
usage_id
```

يوصى بإضافته لاحقًا، لكن ليس بالضرورة في أول اختبار usage log، حتى لا تكبر المهمة أكثر من اللازم.

الصيغة المقترحة لاحقًا:

```text
usage_id = uuid4
```

أو:

```text
usage_id = deterministic/local generated id
```

مع الاحتفاظ بـ `request_id` كربط request-level.

---

## 17. توصية حول provider/model/evaluation/report

السجل الحالي لا يحتوي:

```text
provider
model
evaluation_id
report_id
tokens_input
tokens_output
error_code
```

هذه الحقول مهمة لاحقًا للتقارير والفوترة والتحليل، لكنها تحتاج تصميمًا منفصلًا لأن الـ middleware وحده قد لا يعرف كل هذه القيم لحظة التسجيل.

المقترح:

```text
1. ترك middleware يسجل request-level usage.
2. إضافة event-level usage لاحقًا داخل /cgt/govern بعد إنتاج evaluation.
3. ربط request_id بين السجلين.
```

---

## 18. ممنوعات قبل إغلاق Usage

```text
لا تبدأ Cloud Run.
لا تعتمد usage_logs.jsonl كإنتاج نهائي.
لا تترك raw API key يظهر داخل endpoint.
لا تخلط JWT UI sessions مع API Key usage.
لا تضف Billing قبل تثبيت usage regression.
لا تستعمل git add .
لا تخلط Usage وAuth وBilling في كوميت واحد.
```

---

## 19. أوامر التحقق بعد إنشاء هذا التقرير

بعد حفظ التقرير، يجب تنفيذ:

```powershell
git status --short
python -m ruff check .
python -m pytest -q
python -m compileall .\tests .\processual_api .\processual_kernel .\cgtlib .\scripts
```

ثم إضافة التقرير فقط:

```powershell
git add .\docs\reports\API_KEYS_USAGE_LOG_AUDIT_AR.md
git commit -m "Docs: audit API key usage logging"
git status --short
```

---

## 20. الخلاصة

نظام usage logging في Processual Maestro Kernel v2.0.0 موجود ومفعّل ويثبت فعليًا أن طلبات API Key تسجل في ملف JSONL محلي، بما في ذلك بعض حالات الرفض مثل 403 و429.

هذا يؤكد أن المشروع يملك أساسًا حقيقيًا لتتبع الاستعمال وربطه لاحقًا بالحصص والخطط والفوترة.

لكن التدقيق كشف ضرورة توسيع اختبارات regression، وضرورة منع ظهور raw API key داخل endpoint path المسجل.

المرحلة التالية الصحيحة:

```text
KEY-USAGE-02 — Extend usage logging regression coverage
```
