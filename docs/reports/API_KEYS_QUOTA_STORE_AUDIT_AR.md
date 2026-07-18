# API Keys Quota Store Audit

## Processual Maestro Kernel v2.0.0

## 1. الغرض من التقرير

هذا التقرير يراجع الحالة الفعلية لملف:

```text id="qwu1xp"
processual_api/services/quota_store.py
```

ضمن مرحلة:

```text id="zebzrt"
KEY-AUDIT-02
```

والهدف هو تحديد مدى جاهزية نظام الحصص المرتبط بمفاتيح API الديناميكية بعد KEY-10، وقبل ربطه النهائي بالعميل والاشتراك والتسعير والاستعمال والفوترة.

---

## 2. الحكم المختصر

نظام quota موجود وفعّال مبدئيًا.

الحالة الحالية:

```text id="5py3qf"
Quota enforcement: موجود
API-key-only counting: موجود
Counted endpoint filter: موجود
Plan-based quota: موجود
Manual override: موجود
Quota rejection: موجود
quota_rejected_count: موجود
Unlimited quota عبر -1: موجود
JSON-backed persistence: موجود
Direct test coverage for quota_store: ناقصة
Production readiness: غير مكتملة بعد
```

الحكم:

```text id="kw3c4j"
PASS جزئي — صالح كمرحلة محلية/تمهيدية، لكنه يحتاج اختبارات مباشرة وتقوية ownership قبل Cloud Run.
```

---

## 3. الملف محل المراجعة

```text id="dn7q68"
processual_api/services/quota_store.py
```

يفتتح الملف بتعليق مهم:

```text id="b5er3y"
KEY-04 starts with JSON-backed quota enforcement for dynamic API keys.
This is intentionally small and local-first before PostgreSQL / billing plans.
```

وهذا يؤكد أن التصميم الحالي مقصود أن يكون:

```text id="f2h6yx"
small
local-first
JSON-backed
قبل PostgreSQL
قبل billing plans النهائية
```

---

## 4. التخزين الحالي

مسار التخزين:

```text id="35mo0c"
processual_api/data
```

ويتم البحث عن ملفات:

```text id="qivgri"
settings_*.json
```

ثم البحث داخل:

```text id="22zt6d"
api_keys
```

الحكم:

```text id="8uwvra"
مناسب للتطوير المحلي.
غير كافٍ وحده للإنتاج السحابي.
```

السبب:

```text id="j1bnx9"
Cloud Run يحتاج runtime stateless أو قاعدة بيانات خارجية مثل PostgreSQL.
```

---

## 5. الحصة الافتراضية

يوجد متغير بيئة:

```text id="xm3f4g"
PMK_DEFAULT_API_KEY_QUOTA_LIMIT
```

والقيمة الافتراضية:

```text id="qqejxf"
50
```

هذا جيد كبداية، ويجب أن يبقى في `.env.production.example` وDocumentation.

---

## 6. endpoints التي تستهلك الحصة

القائمة الحالية:

```text id="qj62m3"
COUNTED_ENDPOINTS = {
    ("POST", "/cgt/govern"),
}
```

هذا يعني أن الحصة التجارية لا تُستهلك إلا عند:

```text id="w8kowd"
POST /cgt/govern
```

أما endpoints مثل status أو health أو readiness أو settings العادية فلا تستهلك الحصة.

الحكم:

```text id="wpai5b"
PASS مبدئيًا
```

وهذا مناسب لأن `/cgt/govern` هو endpoint مكلف ومباشر من حيث الاستعمال.

---

## 7. تطبيع endpoint

توجد دالة:

```text id="u1mdd3"
_normalize_endpoint(endpoint)
```

تقوم بإزالة `/` الزائدة في نهاية المسار.

مثال:

```text id="jxpl85"
/cgt/govern/
```

يتحول إلى:

```text id="izsbgp"
/cgt/govern
```

الحكم:

```text id="9y2mpu"
PASS
```

---

## 8. is_quota_counted

الدالة:

```text id="0uk9jo"
is_quota_counted(method, endpoint)
```

ترجع `True` فقط إذا كان:

```text id="57vaty"
method = POST
endpoint = /cgt/govern
```

الحكم:

```text id="7o0yh4"
PASS
```

---

## 9. سلوك consume_quota

الدالة الأساسية:

```text id="up6ggt"
consume_quota(
    current_user,
    method,
    endpoint,
    quota_scope="evaluation",
    amount=1,
)
```

### 9.1 Non API Key Users

إذا كان:

```text id="0o9jhj"
auth_method != api_key
```

فإن الدالة ترجع `current_user` دون استهلاك quota.

الحكم:

```text id="piq8ks"
PASS
```

هذا يمنع احتساب quota على جلسات JWT أو مستخدمين غير مرتبطين بمفتاح API.

---

### 9.2 Non Counted Endpoints

إذا لم يكن endpoint ضمن `COUNTED_ENDPOINTS`، ترجع الدالة المستخدم دون استهلاك quota.

الحكم:

```text id="jysosf"
PASS
```

---

### 9.3 Missing API Key Identity

إذا كان المستخدم API key لكن لا يحتوي على:

```text id="reqlpn"
api_key_id
```

ترفض الدالة الطلب بـ:

```text id="089tv3"
403 Missing API key quota identity
```

الحكم:

```text id="velazc"
PASS
```

هذا يمنع استهلاك quota دون هوية مفتاح واضحة.

---

## 10. العثور على سجل المفتاح

تبحث الدالة في كل ملفات:

```text id="uyc4el"
settings_*.json
```

ثم داخل:

```text id="neykkr"
api_keys
```

وتطابق:

```text id="9ip5ys"
key["id"] == api_key_id
```

إذا لم تجد سجل المفتاح، ترفض بـ:

```text id="1k6ml1"
403 API key quota record not found
```

الحكم:

```text id="4gka8y"
PASS مبدئيًا
```

لكن هذا البحث العام عبر كل ملفات settings مناسب محليًا، وليس مثاليًا إنتاجيًا.

---

## 11. ربط الخطة والحصة

تحدد الدالة `plan_id` من أول قيمة متاحة:

```text id="13wbf1"
key.plan_id
key.plan
subscription.plan_id
subscription.plan
Starter
```

ثم تستعمل:

```text id="k25lav"
resolve_plan_id
quota_limit_for_plan
get_plan_policy
```

الحكم:

```text id="h0lhtd"
PASS جزئي
```

السبب:

```text id="d542vw"
الربط بالخطة موجود، لكن الربط باشتراك عميل فعلي يحتاج تثبيت أعمق في مرحلة Billing/Productization.
```

---

## 12. Manual Quota Override

إذا كان:

```text id="ms7q3b"
quota_policy.source = manual
```

أو:

```text id="nay4gh"
quota_limit_override موجود
```

يتم اعتماد الحصة اليدوية بدل الحصة القادمة من الخطة.

الحكم:

```text id="4dnray"
PASS
```

وهذا مفيد للمشرف في التجارب المدفوعة أو الحالات الخاصة.

---

## 13. تجاوز الحصة

إذا كان:

```text id="g1siyd"
quota_limit >= 0
```

و:

```text id="06suq4"
quota_used + amount > quota_limit
```

تقوم الدالة بـ:

```text id="rlhitb"
1. تسجيل quota_last_rejected_at.
2. زيادة quota_rejected_count.
3. حفظ JSON.
4. رفع HTTP 429.
```

الخطأ:

```text id="cg32lz"
429 TOO MANY REQUESTS
```

والتفاصيل:

```text id="ya7q3w"
{
  "error": "quota_exceeded",
  "quota_scope": "evaluation",
  "quota_limit": quota_limit,
  "quota_used": quota_used
}
```

الحكم:

```text id="yc1t87"
PASS
```

---

## 14. زيادة quota_used

عند السماح بالطلب، يتم:

```text id="1c7gn3"
quota_used += amount
quota_last_used_at = now
quota_scope = quota_scope
```

ثم يتم حفظ الملف.

كما يرجع النظام نسخة محدثة من `current_user` تحتوي:

```text id="elfsg6"
quota.scope
quota.plan_id
quota.limit
quota.used
quota.remaining
```

الحكم:

```text id="kqfw97"
PASS
```

لكن يجب الانتباه إلى أن الحصة تُستهلك عند مرور dependency قبل تنفيذ العملية نفسها. لذلك إذا فشل `/cgt/govern` بعد اجتياز quota، قد تكون الحصة استُهلكت. هذا قرار يجب تثبيته:

```text id="61tcwi"
هل نحسب محاولة التشغيل؟
أم نحسب فقط نتيجة ناجحة؟
```

في المرحلة التجارية الأولى، احتساب المحاولة قد يكون مقبولًا، لكن يجب توضيحه في سياسة الاستعمال.

---

## 15. Unlimited Quota

إذا كان:

```text id="qlbwps"
quota_limit = -1
```

فإن شرط الاستهلاك لا يمنع الطلب، لأن المنع لا يعمل إلا عند:

```text id="82i4ce"
quota_limit >= 0
```

كما أن `remaining` يرجع:

```text id="cplvhx"
None
```

الحكم:

```text id="m90xvy"
PASS
```

هذا مناسب لخطط Enterprise أو مفاتيح داخلية محدودة الوصول.

---

## 16. ثغرات أو حدود التصميم الحالي

النظام الحالي جيد كبداية، لكنه يحتوي على حدود يجب توثيقها:

```text id="yzvf00"
1. التخزين JSON وليس PostgreSQL.
2. البحث يتم عبر كل settings_*.json.
3. لا توجد lock واضحة في quota_store.py مثل file_lock المستعمل في settings.py.
4. لا توجد اختبارات مباشرة كافية لـ consume_quota حسب نتائج البحث الحالية.
5. لا يظهر reset window فعلي للحصص.
6. لا يظهر ربط صارم بملكية client/subscription.
7. الحصة تُستهلك قبل تنفيذ endpoint نفسه.
8. فقط POST /cgt/govern يستهلك quota حاليًا.
```

---

## 17. نتائج البحث في الاختبارات

البحث داخل `tests` أظهر وجود تغطية لـ:

```text id="asjxy0"
quota plan regression
manual quota override
quota summary
api key settings routes
require_quota على /cgt/govern
production env template
```

وتحديدًا:

```text id="dtvso1"
tests/test_api_key_quota_plan_regression.py
tests/test_api_key_settings_routes.py
tests/test_cgt_governor_route_boundaries.py
tests/test_production_env_template_regression.py
```

لكن لا يظهر من نتائج البحث وجود ملف اختبار مباشر واضح مثل:

```text id="ij91ar"
tests/test_quota_store.py
```

ولا تظهر اختبارات مباشرة كافية لـ:

```text id="zexgi1"
consume_quota accepts counted endpoint
consume_quota skips non-counted endpoint
consume_quota rejects exhausted quota
consume_quota increments quota_used
consume_quota increments quota_rejected_count
consume_quota supports unlimited quota
consume_quota rejects missing api_key_id
consume_quota rejects missing quota record
```

الحكم:

```text id="q9dl0s"
Test coverage جزئية وتحتاج تقوية مباشرة.
```

---

## 18. قرار KEY-AUDIT-02

القرار النهائي:

```text id="8ta722"
quota_store.py موجود ومناسب للاستمرار، ولا يحتاج إعادة بناء من الصفر.
```

لكن قبل Cloud Run يجب تنفيذ:

```text id="plc6j2"
KEY-QUOTA-01 add direct quota_store regression tests
KEY-QUOTA-02 add exhausted quota endpoint test
KEY-QUOTA-03 document quota counting policy
KEY-QUOTA-04 add file locking or storage adapter before production
KEY-QUOTA-05 define monthly/daily reset model
```

---

## 19. اختبارات مباشرة مقترحة

يجب إضافة ملف:

```text id="8f4xmd"
tests/test_quota_store.py
```

ويغطي:

```text id="r2d1p0"
1. non_api_key_user_passes_without_consuming_quota
2. non_counted_endpoint_passes_without_consuming_quota
3. counted_endpoint_increments_quota_used
4. counted_endpoint_returns_updated_user_quota_summary
5. exhausted_quota_raises_429
6. exhausted_quota_increments_quota_rejected_count
7. unlimited_quota_minus_one_allows_request
8. missing_api_key_id_raises_403
9. missing_quota_record_raises_403
10. manual_override_limit_is_respected
```

---

## 20. الخلاصة النهائية

الحالة الحالية:

```text id="jkg5md"
Quota store: موجود
Counted endpoint filter: موجود
POST /cgt/govern فقط: نعم
API-key-only consumption: نعم
quota_used increment: نعم
429 quota_exceeded: نعم
quota_rejected_count: نعم
manual override: نعم
plan fallback: نعم
unlimited -1: نعم
direct tests: ناقصة
production storage: ناقص
client/subscription ownership: يحتاج تثبيت
```

الحكم النهائي:

```text id="ldvkm9"
Quota enforcement is real but still local-first. It should be preserved and hardened with direct regression tests before billing/cloud deployment.
```

وبالعربية:

```text id="f8mpbl"
نظام الحصص حقيقي وقابل للبناء عليه، لكنه ما زال نظامًا محليًا تمهيديًا يحتاج اختبارات مباشرة وتثبيت التخزين والملكية قبل Cloud Run.
```
