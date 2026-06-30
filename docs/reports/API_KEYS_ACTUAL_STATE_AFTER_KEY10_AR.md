# API Keys Actual State After KEY-10

## Processual Maestro Kernel v2.0.0

## 1. الغرض من التقرير

هذا التقرير يراجع الحالة الفعلية لنظام Dynamic API Keys بعد مرحلة KEY-10، وقبل بدء ربطه النهائي بمسار Productization / Auth / Pricing / Usage / Billing / Cloud Run.

الهدف ليس افتراض أن النظام إنتاجي بالكامل، بل التمييز بين:

```text
موجود ومثبت
موجود جزئيًا
مغطى بالاختبارات
يحتاج تدقيقًا إضافيًا
يحتاج تطويرًا قبل Cloud Run
```

يعتمد هذا التقرير على مراجعة الملفات التالية:

```text
processual_api/auth/security.py
processual_api/services/api_key_store.py
processual_api/routers/settings.py
tests/
```

---

## 2. الحكم المختصر

نظام API Keys بعد KEY-10 أصبح متقدمًا وموجودًا فعليًا، ولم يعد مجرد `API_KEYS` ثابتة من البيئة.

الموجود حاليًا:

```text
1. توليد مفاتيح dynamic بصيغة pmk_.
2. تخزين hash فقط بدل المفتاح الصريح.
3. قبول X-API-Key.
4. التحقق من dynamic pmk_ keys قبل fallback env keys.
5. منع env fallback في production.
6. دعم bcrypt و pbkdf2 fallback.
7. رفض المفاتيح revoked / disabled / expired.
8. تحديث last_used_at.
9. زيادة usage_count.
10. إرجاع public identity للمفتاح.
11. وجود scopes.
12. وجود require_scope.
13. وجود require_quota.
14. إنشاء مفاتيح من settings routes تحت admin:settings.
15. ربط أولي بالخطة plan_id.
16. ربط أولي بالحصة quota_limit / quota_used.
17. revoke بدون hard delete.
18. اختبارات متعددة تغطي أجزاء مهمة.
```

لكن النظام لا يجب اعتباره جاهزًا نهائيًا للإنتاج قبل تدقيق وتثبيت المسارات التالية:

```text
1. ربط API Key نهائيًا بعميل client حقيقي.
2. ربط العميل باشتراك subscription فعلي.
3. فرض quota في كل endpoints الحساسة.
4. توثيق usage logs وربطها بالتقارير.
5. تدقيق ownership بين admin/client.
6. تدقيق quota_store مباشرة.
7. تدقيق usage middleware/store مباشرة.
8. اختبار end-to-end بمفتاح dynamic مولد فعليًا.
9. نقل التخزين تدريجيًا من JSON إلى storage production-ready.
```

---

## 3. مسار التحقق الحالي

المسار الحالي في `get_current_user` هو:

```text
Bearer JWT
↓
verify_access_token
↓
return JWT user identity
```

أو:

```text
X-API-Key
↓
verify_dynamic_api_key(api_key)
↓
إن نجح: return dynamic api key identity
↓
إن فشل: فحص env fallback فقط في dev/local/test
↓
إن لم ينجح: 401 Invalid API key
```

هذا ترتيب صحيح من حيث المبدأ، لأن dynamic keys تُفحص قبل fallback المفاتيح الثابتة.

---

## 4. Dynamic pmk_ Keys

الدالة:

```text
verify_dynamic_api_key(api_key)
```

تقبل فقط المفاتيح التي تبدأ بـ:

```text
pmk_
```

إذا لم يبدأ المفتاح بـ `pmk_` ترجع الدالة `None`.

هذا يحافظ على تمييز واضح بين:

```text
dynamic production-like keys
dev/static fallback keys
```

---

## 5. مكان تخزين المفاتيح الحالي

التخزين الحالي يعتمد على ملفات JSON داخل:

```text
processual_api/data/settings_*.json
```

الدالة تفحص كل الملفات المطابقة:

```text
settings_*.json
```

وتبحث داخل:

```text
api_keys
```

هذا مناسب للتطوير المحلي والمرحلة الحالية، لكنه ليس التخزين النهائي المناسب للإنتاج السحابي، خصوصًا على Cloud Run.

القرار:

```text
JSON مقبول مؤقتًا للـ dev/local.
PostgreSQL أو storage adapter مطلوب لاحقًا للـ staging/production.
```

---

## 6. Hash Verification

النظام يدعم نوعين من التحقق:

```text
bcrypt
pbkdf2_sha256
```

المفتاح الصريح لا يُخزن في السجل، بل يتم تخزين:

```text
hashed
```

أو:

```text
hashed_key
```

عند إنشاء مفتاح جديد من `/settings/api-keys` يتم توليد المفتاح الصريح مرة واحدة وإرجاعه في response، بينما يُخزن hash فقط.

الحكم:

```text
PASS مبدئيًا
```

مع شرط استمرار اختبار:

```text
plain key appears once only
plain key is never stored
hash verification works after restart
```

---

## 7. Revoked / Disabled / Expired

التحقق الحالي يرفض الحالات التالية:

```text
status = revoked
status = disabled
status = expired
revoked_at موجود
expires_at منتهٍ
```

إذا كان `expires_at` منتهيًا، يقوم النظام بتغيير الحالة إلى:

```text
expired
```

ثم يحفظ الملف.

الحكم:

```text
PASS مبدئيًا
```

---

## 8. Usage Tracking داخل API Key Store

عند نجاح التحقق من المفتاح الديناميكي، يتم تحديث:

```text
last_used_at
usage_count
```

ثم حفظ السجل.

الحكم:

```text
PASS مبدئيًا
```

لكن هذا ليس بديلًا كاملًا عن usage logs التشغيلية.

`usage_count` يجيب عن سؤال:

```text
كم مرة استُعمل هذا المفتاح؟
```

أما usage logs فيجب أن تجيب عن:

```text
من استعمل؟
أي endpoint؟
متى؟
ما status_code؟
ما latency؟
أي provider/model؟
هل حدث خطأ؟
ما request_id؟
ما evaluation/report id؟
```

لذلك ما زال يلزم تثبيت usage logging كطبقة مستقلة.

---

## 9. Public Identity للمفتاح

بعد نجاح التحقق يرجع النظام identity تحتوي:

```text
sub
user_id
client_id
role
auth_method
session_type
api_key_id
api_key_prefix
scopes
```

القيم المهمة:

```text
auth_method = api_key
session_type = api_key
role = client افتراضيًا
```

هذا جيد لأنه يميز API Key عن JWT وعن جلسة الواجهة.

الحكم:

```text
PASS مبدئيًا
```

لكن يجب لاحقًا التأكد من أن:

```text
API Key لا يدخل Admin UI
API Key لا يعمل كـ Password
API Key لا يعمل كـ Bridge Token
```

---

## 10. Scopes

توجد scopes افتراضية للعميل:

```text
read:health
read:adapters
read:governor
run:analyze
run:govern
run:compare
read:reports
create:reports
```

وتوجد دالة:

```text
require_scope(required_scope)
```

تقبل المستخدم إذا:

```text
required_scope موجود
```

أو:

```text
* موجودة في scopes
```

وترفض بـ:

```text
403 Missing required scope
```

الحكم:

```text
PASS مبدئيًا
```

لكن يجب لاحقًا مراجعة كل endpoints الحساسة والتأكد من عدم وجود endpoint مفتوح أكثر من اللازم.

---

## 11. Admin Settings Scope

مسارات إدارة المفاتيح محمية بـ:

```text
admin:settings
```

وتشمل:

```text
GET /settings/api-keys
POST /settings/api-keys
PATCH /settings/api-keys/{key_id}/plan
PATCH /settings/api-keys/{key_id}/quota
DELETE /settings/api-keys/{key_id}
```

هذا مهم لأن العميل العادي لا يجب أن يملك القدرة على إنشاء أو تعديل مفاتيح إدارية.

الحكم:

```text
PASS مبدئيًا
```

---

## 12. إنشاء API Key

المسار:

```text
POST /settings/api-keys
```

ينشئ مفتاحًا جديدًا ويخزن:

```text
id
user_id
client_id
prefix
hashed
scopes
profile
label
plan_id
quota_policy
quota_scope
quota_limit
quota_used
quota_reset_at
status
created_at
last_used_at
usage_count
expires_at
revoked_at
```

ويرجع المفتاح الصريح مرة واحدة:

```text
api_key
```

الحكم:

```text
PASS مبدئيًا
```

مع بقاء نقطة مهمة:

```text
يجب تدقيق هل owner_user_id هو المكان الصحيح لتخزين مفاتيح العملاء عندما ينشئها admin لعميل آخر.
```

لأن الكود الحالي يحفظ في raw الخاص بـ owner_user_id، مع وضع `client_id` و`user_id` داخل سجل المفتاح. هذا قد يكون مقبولًا مؤقتًا، لكنه يحتاج قرارًا معماريًا واضحًا في مرحلة clients/subscriptions.

---

## 13. Plan Binding

عند إنشاء المفتاح، يتم تحديد:

```text
plan_id
quota_policy
quota_limit
```

اعتمادًا على:

```text
resolve_plan_id
get_plan_policy
quota_limit_for_plan
```

كما توجد مسارات لتحديث plan أو quota يدويًا.

الحكم:

```text
PASS جزئي
```

السبب:

```text
الربط بالخطة موجود، لكن يجب التأكد من أن الخطة مرتبطة باشتراك عميل فعلي وليس فقط raw settings أو billing fallback.
```

---

## 14. Quota

توجد دالة:

```text
require_quota(quota_scope="evaluation")
```

وتستدعي:

```text
consume_quota
```

من:

```text
processual_api/services/quota_store.py
```

وتوجد اختبارات تشير إلى أن route الحاكم الأساسي يتطلب quota:

```text
Depends(require_quota("evaluation"))
```

كما توجد اختبارات لتحديث quota حسب الخطة أو manual override.

الحكم:

```text
PASS جزئي
```

السبب:

```text
المسار موجود ومربوط جزئيًا، لكن يجب تدقيق quota_store.py مباشرة قبل إعلان الجاهزية.
```

يجب مراجعة:

```text
1. هل quota_used يزيد فعليًا عند request ناجح؟
2. هل quota يزيد قبل التنفيذ أم بعده؟
3. ماذا يحدث عند فشل request؟
4. هل quota تحسب حسب api_key_id؟
5. هل quota تحسب حسب client_id؟
6. هل quota_scope مضبوط لكل endpoint؟
7. هل يوجد reset window؟
8. هل يوجد quota_rejected_count؟
```

---

## 15. Usage Logs

نتائج البحث داخل الاختبارات تشير إلى وجود:

```text
UsageLogMiddleware
append_usage_log
tests/test_middleware_regression.py
```

وتوجد تغطية لتسجيل:

```text
api_key_id
api_key_prefix
auth_method
endpoint
request_id
```

الحكم:

```text
PASS جزئي
```

السبب:

```text
وجود middleware واختبارات لا يكفي وحده لإعلان usage production-ready.
```

يجب تدقيق:

```text
processual_api/middleware/usage_log.py
```

والتأكد من أن السجل يحتوي على:

```text
usage_id
client_id
api_key_id
user_id
endpoint
method
status_code
latency_ms
provider
model
evaluation_id
report_id
tokens_input
tokens_output
error_code
created_at
request_id
```

---

## 16. Production Boundary

الـ env fallback للمفاتيح الثابتة لا يعمل إلا في:

```text
dev
development
local
test
```

ويُمنع إذا كانت البيئة:

```text
production
prod
```

أو إذا كان:

```text
settings.is_production = true
```

كما توجد اختبارات واضحة:

```text
test_env_api_key_fallback_is_allowed_only_in_non_production
test_env_api_key_fallback_is_blocked_when_app_env_is_production
test_env_api_key_fallback_is_blocked_when_environment_is_production_even_without_app_env
test_dynamic_pmk_api_key_is_still_accepted_in_production
```

الحكم:

```text
PASS
```

---

## 17. Provider Keys / BYOK

في settings router يوجد تشفير لمفاتيح المزودين عند توفر:

```text
PROCESSUAL_CRYPTO_KEY_B64
```

ويتم حفظ:

```text
encrypted_key
```

بدل:

```text
api_key
```

كما توجد اختبارات تتأكد من أن مفاتيح LLM provider وadapter config لا تخزن صريحة عندما تكون crypto key متوفرة.

الحكم:

```text
PASS مبدئيًا
```

مع شرط:

```text
PROCESSUAL_CRYPTO_KEY_B64 إلزامي في production.
```

---

## 18. الاختبارات الموجودة

البحث داخل tests أظهر تغطية مهمة في الملفات التالية:

```text
tests/test_api_key_store.py
tests/test_api_key_settings_routes.py
tests/test_api_key_quota_plan_regression.py
tests/test_auth_fallback_production_boundary.py
tests/test_auth_scopes_regression.py
tests/test_cgt_governor_route_boundaries.py
tests/test_middleware_regression.py
tests/test_secret_encryption_readiness_regression.py
tests/test_settings_persistence_safety.py
```

هذه الاختبارات تغطي:

```text
dynamic key hash verification
wrong key rejection
non dynamic key rejection
revoked key rejection
usage_count update
admin settings scope
create key returns plain key once
hash-only storage
revoke without hard delete
quota plan binding
manual quota override
production fallback boundary
dynamic key accepted in production
scope enforcement
usage middleware basics
provider key encryption
safe JSON persistence
```

الحكم:

```text
Coverage جيدة، لكنها تحتاج end-to-end production-like scenarios.
```

---

## 19. النقائص التي يجب إغلاقها قبل Cloud Run

النقائص الأساسية:

```text
1. تدقيق quota_store.py مباشرة.
2. تدقيق usage_log middleware/store مباشرة.
3. تنفيذ end-to-end dynamic key flow:
   - admin creates key
   - client uses key
   - endpoint accepts key
   - quota decreases or usage increases
   - usage log created
   - revoked key rejected
   - exhausted quota rejected
4. تثبيت client ownership.
5. تثبيت subscription ownership.
6. ربط plan_id الحقيقي بالاشتراك.
7. منع client من إنشاء أو تعديل مفاتيح خارج نطاقه.
8. منع API Key من دخول Console كجلسة واجهة.
9. إضافة pricing_version إلى plan/subscription/api key snapshot عند الحاجة.
10. تقرير usage/quota ظاهر في Console.
```

---

## 20. قرار معماري مؤقت

الوضع الحالي جيد للمرحلة التالية:

```text
Productization audit and hardening
```

لكنه ليس كافيًا بعد لـ:

```text
Cloud Run production
```

القرار:

```text
نواصل التطوير من الحالة الحالية، ولا نعيد بناء نظام API Keys من الصفر.
```

بل نعمل وفق قاعدة:

```text
Preserve first.
Audit second.
Harden third.
Extend fourth.
```

---

## 21. أول مهام API Keys التالية

المهام المقترحة بعد هذا التقرير:

```text
KEY-AUDIT-02 مراجعة quota_store.py
KEY-AUDIT-03 مراجعة usage_log middleware/store
KEY-AUDIT-04 اختبار end-to-end dynamic API key
KEY-HARDEN-01 ربط API Key بالعميل والاشتراك والحصة
KEY-HARDEN-02 منع أي استعمال UI للمفتاح
KEY-HARDEN-03 توثيق ownership rules
KEY-HARDEN-04 إضافة tests للـ exhausted quota
KEY-HARDEN-05 إضافة tests للـ revoked dynamic key على endpoint حقيقي
```

---

## 22. الخلاصة النهائية

الحالة الحالية بعد KEY-10:

```text
Dynamic API Keys: موجودة
Hash-only storage: موجود
pmk_ prefix: موجود
Production fallback boundary: موجود
Scopes: موجودة
Admin settings protection: موجودة
Revocation: موجودة
Expiration: موجودة
last_used_at: موجود
usage_count: موجود
Plan binding: موجود جزئيًا
Quota binding: موجود جزئيًا
Usage logs: موجودة جزئيًا
Client/subscription binding: يحتاج تدقيق وتثبيت
Cloud Run readiness: غير مكتملة بعد
```

الحكم النهائي:

```text
API Keys layer is real and usable for the next hardening phase, but not yet final production-ready.
```

وبالعربية:

```text
طبقة مفاتيح API أصبحت حقيقية وقابلة للبناء عليها، لكنها تحتاج تدقيق quota وusage وclient/subscription ownership قبل اعتمادها كأساس إنتاجي نهائي.
```
