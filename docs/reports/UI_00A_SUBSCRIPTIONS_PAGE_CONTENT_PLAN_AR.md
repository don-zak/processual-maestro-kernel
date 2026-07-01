# تقرير تخطيط محتوى صفحة الاشتراكات

## Processual Maestro Kernel v2.0.0

### UI-00A — Subscriptions Page Content Plan

---

## 1. الغرض من التقرير

هذا التقرير يحدد محتوى ومنطق صفحة الاشتراكات المقترحة في **Processual Maestro** قبل تنفيذها برمجيًا.

الهدف الحالي ليس إنشاء صفحة HTML الآن، بل تثبيت:

1. بنية عرض الاشتراكات.
2. محتوى عروض التجربة.
3. محتوى خطط Pilot.
4. طريقة التعامل مع Enterprise / المؤسسات.
5. قاعدة الربط الآلي للخيارات العادية.
6. حدود BYOK.
7. حدود الاسترجاع.
8. معايير نجاح التجربة.
9. سبب تأجيل التنفيذ إلى ما بعد التفعيل والفوترة.

---

## 2. قرار التأجيل

تُؤجَّل صفحة الاشتراكات التنفيذية إلى ما بعد استكمال:

```text
AUTH-02 — create_admin + Client Activation Flow
BILL-01 — Billing webhook idempotency
PLAN-01 — Pricing versioning and plans
```

السبب:

```text
لا يجب أن تعرض صفحة الاشتراكات أزرارًا توحي بدفع أو تفعيل نهائي قبل أن تكون مسارات التفعيل والفوترة وربط الخطة بالعميل جاهزة.
```

لذلك يكون العمل الحالي:

```text
تخطيط وتوثيق فقط.
لا HTML الآن.
لا route الآن.
لا checkout الآن.
لا activation endpoint الآن.
```

---

## 3. موقع الصفحة لاحقًا داخل تجربة المستخدم

عند التنفيذ لاحقًا، يكون الدخول إلى صفحة الاشتراكات عبر زر:

```text
New User
```

الموجود أسفل صفحة الهبوط التي تحتوي على:

```text
User
Admin
New User
```

المسار المقترح لاحقًا:

```text
/subscriptions
```

القاعدة:

```text
Landing / Descent Gate
↓
New User
↓
Subscriptions Page
↓
اختيار تجربة أو خطة
↓
تفعيل أو فوترة حسب المسار الجاهز لاحقًا
```

---

## 4. القاعدة الأساسية للربط

يجب أن يكون الربط آليًا لكل الاختيارات العادية.

أي:

```text
Guided Preview
Pilot Evaluation
Technical Pilot
Pilot Starter
Pilot Standard
Pilot Technical
```

كلها يجب أن تقود لاحقًا إلى مسار آلي مناسب، مثل:

```text
/activation/start?offer=guided-preview
/activation/start?offer=pilot-evaluation
/activation/start?offer=technical-pilot
/activation/start?plan=pilot-starter
/activation/start?plan=pilot-standard
/activation/start?plan=pilot-technical
```

أو بعد اكتمال الفوترة:

```text
/billing/checkout?plan=pilot-starter
/billing/checkout?plan=pilot-standard
/billing/checkout?plan=pilot-technical
```

لكن لا يتم اعتماد هذه المسارات قبل إغلاق التفعيل والفوترة.

---

## 5. استثناء المؤسسات و Enterprise

الاستثناء الوحيد من الربط الآلي هو:

```text
Enterprise / Custom
المؤسسات
العروض المخصصة
النشر الخاص
الحدود المخصصة
الدعم أو التعاقد الخاص
```

هذه لا تُربط آليًا ولا تُعامل كخطة عادية.

النص المعتمد للمؤسسات:

```text
يرجى الاتصال بالمشرف عبر البريد وتحديد الحاجيات، ومحتوى التجربة، ونطاق الاستعمال، والعرض المطلوب حتى تتم المراجعة والتجهيز.
```

يمنع استعمال العبارة التالية في الصفحة:

```text
A supervisor will review the request and activate the appropriate client path.
```

سبب المنع:

```text
هذه العبارة توحي بأن كل الخطط تحتاج مراجعة يدوية، بينما المطلوب أن يكون الربط آليًا لكل الاختيارات العادية، وأن تبقى المراجعة اليدوية محصورة في المؤسسات وEnterprise فقط.
```

---

## 6. طريقة عرض الصفحة

المحتوى لا يجب أن يظهر كنص طويل في صفحة واحدة.

يجب أن تكون الصفحة لاحقًا صفحة واحدة منظمة، لكنها مقسمة بصريًا إلى أقسام وبطاقات وتفاصيل قابلة للفتح.

البنية المقترحة:

```text
1. Hero / رأس الصفحة
2. اختيار سريع
3. تنبيه BYOK
4. عروض التجربة
5. خطط Pilot
6. Enterprise / Custom
7. مقارنة مختصرة
8. Important Terms / FAQ
9. Continue / Footer
```

---

## 7. رأس الصفحة

العنوان المقترح:

```text
Choose your Processual Maestro path
```

أو:

```text
اختر طريقة تجربة أو تشغيل Processual Maestro
```

النص المختصر:

```text
ابدأ بتجربة موجهة، أو اختر خطة Pilot مناسبة، أو تواصل بخصوص عرض مؤسسات مخصص.
```

أزرار الاختيار السريع:

```text
Try Maestro first
Choose a Pilot plan
Enterprise / Custom
```

وبالعربية:

```text
أريد تجربة Maestro أولًا
أريد اختيار خطة Pilot
أحتاج عرض مؤسسات
```

---

## 8. تنبيه BYOK

يجب أن يظهر هذا التنبيه أعلى العروض والخطط:

```text
Provider costs are not included.
Bring your own provider keys.
```

وبالعربية:

```text
الأسعار لا تشمل تكلفة مزودي الذكاء الاصطناعي الخارجيين.
يلتزم العميل باستعمال مفاتيحه أو حساباته الخاصة لدى المزودين.
```

الغرض من هذا التنبيه:

```text
الفصل بين تكلفة استعمال Maestro وتكلفة OpenAI أو Gemini أو Anthropic أو DeepSeek أو أي مزود خارجي آخر.
```

---

## 9. عروض التجربة

تعرض قبل خطط الاشتراك لأنها موجهة للزائر الجديد.

### 9.1 Guided Preview

اسم العرض:

```text
Guided Preview
تجربة تعريفية موجهة
```

مناسب لـ:

```text
من يريد فهم البرنامج قبل اختيار خطة Pilot.
```

يشمل:

```text
- شرح مختصر للبرنامج.
- شرح Console.
- شرح API Keys.
- شرح BYOK.
- مثال استعمال واحد.
```

لا يشمل:

```text
- نشر إنتاجي.
- ربط مزود مضمون.
- تفعيل مؤسسة كامل.
```

الزر لاحقًا:

```text
Start guided preview
```

الربط لاحقًا:

```text
/activation/start?offer=guided-preview
```

---

### 9.2 Pilot Evaluation

اسم العرض:

```text
Pilot Evaluation
تجربة تقييم أولية
```

مناسب لـ:

```text
من يريد اختبار Maestro على حالة استعمال محددة قبل الاشتراك الكامل.
```

يشمل:

```text
- تفعيل عميل مؤقت.
- دخول Console.
- إنشاء API Key محدود.
- اختبار مزود واحد.
- عدد محدود من تقييمات CGT Governor.
- ملخص نهاية التجربة.
```

الزر لاحقًا:

```text
Start pilot evaluation
```

الربط لاحقًا:

```text
/activation/start?offer=pilot-evaluation
```

---

### 9.3 Technical Pilot

اسم العرض:

```text
Technical Pilot
تجربة تقنية موسعة
```

مناسب لـ:

```text
الفرق التقنية التي تريد اختبار المفاتيح، الحصص، الربط، وحدود التكامل.
```

يشمل:

```text
- تفعيل عميل.
- إنشاء API Keys ضمن حدود الخطة.
- اختبار readiness للمزود.
- مراجعة سلوك quota.
- مراجعة usage logging.
- اختبار endpoints أساسية.
- ملاحظات تقنية في نهاية التجربة.
```

الزر لاحقًا:

```text
Start technical pilot
```

الربط لاحقًا:

```text
/activation/start?offer=technical-pilot
```

---

## 10. خطط Pilot

تعرض في بطاقات مختصرة، مع تفاصيل قابلة للفتح.

### 10.1 Pilot Starter

اسم الخطة:

```text
Pilot Starter
```

الوصف:

```text
للبداية المحدودة والمنظمة.
```

مناسبة لـ:

```text
- فريق صغير.
- تجربة أولية.
- اختبار Console وAPI Keys.
- استعمال محدود.
```

تشمل:

```text
- مساحة عميل واحدة.
- دخول Client Console.
- API Keys محدودة.
- حصة استعمال أساسية.
- مسار ربط مزود واحد.
- Usage logging.
- ملخص تجربة بسيط.
```

لا تشمل:

```text
- نشر خاص.
- SLA.
- دعم تقني مخصص.
- تكاليف المزود الخارجي.
```

الزر لاحقًا:

```text
Continue with Pilot Starter
```

الربط لاحقًا:

```text
/activation/start?plan=pilot-starter
```

أو بعد اكتمال الفوترة:

```text
/billing/checkout?plan=pilot-starter
```

---

### 10.2 Pilot Standard

اسم الخطة:

```text
Pilot Standard
```

الوصف:

```text
لتجربة أوسع داخل فريق أو مؤسسة صغيرة.
```

مناسبة لـ:

```text
- فريق عمل.
- مؤسسة تريد تقييمًا عمليًا.
- استعمال أكثر من مفتاح API.
- أكثر من سيناريو اختبار.
```

تشمل:

```text
- مساحة عميل واحدة.
- دخول Console.
- API Keys أكثر من Starter.
- حصة استعمال أعلى.
- readiness check للمزود.
- رؤية أوضح للاستعمال والحصص.
- تقييمات CGT Governor.
- ملخص أو تقرير تجربة.
```

لا تشمل:

```text
- نشر خاص.
- Enterprise SLA.
- شروط أمنية مخصصة.
- تكاليف المزود الخارجي.
```

الزر لاحقًا:

```text
Continue with Pilot Standard
```

الربط لاحقًا:

```text
/activation/start?plan=pilot-standard
```

أو بعد اكتمال الفوترة:

```text
/billing/checkout?plan=pilot-standard
```

---

### 10.3 Pilot Technical

اسم الخطة:

```text
Pilot Technical
```

الوصف:

```text
للتقييم التقني العميق قبل اعتماد أوسع.
```

مناسبة لـ:

```text
- CTO.
- فريق تقني.
- مسؤول نظم.
- مؤسسة تريد اختبار التكامل وحدوده.
```

تشمل:

```text
- مساحة عميل.
- إعداد بمساعدة تقنية.
- API Keys متعددة ضمن حدود الخطة.
- حصة استعمال أعلى.
- Provider readiness review.
- مراجعة quota rejection behavior.
- مراجعة usage logging.
- تقرير تقني.
- إرشاد تكاملي.
```

لا تشمل:

```text
- تكاليف المزود الخارجي.
- نشر خاص كامل.
- SLA مؤسسات.
- عقد أمني أو قانوني مخصص.
- ضمان نجاح التجربة إذا كانت مفاتيح المزود غير صالحة.
```

الزر لاحقًا:

```text
Continue with Pilot Technical
```

الربط لاحقًا:

```text
/activation/start?plan=pilot-technical
```

أو بعد اكتمال الفوترة:

```text
/billing/checkout?plan=pilot-technical
```

---

## 11. Enterprise / Custom

اسم الخطة:

```text
Enterprise / Custom
```

الوصف:

```text
للمؤسسات والجهات التي تحتاج حدود استعمال مخصصة، دعمًا خاصًا، مراجعة نشر خاص، أو عرض تجربة مهيأ حسب الحاجيات.
```

مناسبة لـ:

```text
- المؤسسات الكبيرة.
- شركات الاتصالات.
- الجهات التي تحتاج private deployment.
- الجهات التي تحتاج SLA.
- الجهات التي تحتاج تقارير متقدمة.
- الجهات التي تحتاج مراجعة أمنية أو تعاقدية.
```

قد تشمل:

```text
- حدود حصة مخصصة.
- عدد API Keys مخصص.
- سياسة مزودين مخصصة.
- تقارير readiness متقدمة.
- Onboarding مخصص.
- مراجعة نشر خاص.
- دعم ومرافقة.
- شروط فوترة واسترجاع خاصة.
- مراجعة أمنية أو تشغيلية.
```

السعر:

```text
Contact us
```

النص الإلزامي:

```text
يرجى الاتصال بالمشرف عبر البريد وتحديد الحاجيات، ومحتوى التجربة، ونطاق الاستعمال، والعرض المطلوب حتى تتم المراجعة والتجهيز.
```

الزر لاحقًا:

```text
Contact administrator
```

الرابط لاحقًا:

```text
mailto:
```

أو صفحة تواصل خاصة لاحقًا:

```text
/contact-enterprise
```

---

## 12. المقارنة المختصرة

تعرض كقسم خفيف لا كجدول مزدحم.

```text
Guided Preview:
لفهم البرنامج قبل التفعيل.

Pilot Evaluation:
لتجربة أولية على حالة استعمال محددة.

Technical Pilot:
لتقييم تقني أعمق.

Pilot Starter:
لبداية محدودة ومنظمة.

Pilot Standard:
لتجربة أوسع داخل فريق أو مؤسسة صغيرة.

Pilot Technical:
لتقييم تقني وتكاملي متقدم.

Enterprise / Custom:
للمؤسسات والحاجيات المخصصة.
```

---

## 13. معايير نجاح التجربة

تعرض داخل قسم FAQ أو Important Terms.

النص المقترح:

```text
تعتبر التجربة ناجحة عندما يكتمل المسار الأدنى المتفق عليه، مثل:

- تفعيل حساب العميل.
- دخول Console.
- إنشاء API Key.
- ربط مزود واحد على الأقل أو إثبات أن الخطأ من جهة المزود.
- تنفيذ عدد أدنى من التقييمات الناجحة.
- ظهور نتائج Governor منظمة.
- إنتاج ملخص أو تقرير تجربة.
```

تنبيه:

```text
Maestro لا يضمن رصيد المزود الخارجي ولا صحة مفاتيح OpenAI أو Gemini أو Anthropic أو DeepSeek التي يوفرها العميل.
```

---

## 14. حدود الاسترجاع

تعرض داخل FAQ أو Important Terms.

النص المقترح:

```text
ينطبق الاسترجاع فقط عندما يفشل Processual Maestro نفسه في تسليم المسار الأدنى المتفق عليه.
```

أمثلة على فشل Maestro:

```text
- فشل تفعيل الحساب.
- فشل إصدار API Key.
- فشل endpoints الأساسية.
- فشل إنتاج نتائج منظمة.
- فشل تسليم ملخص أو تقرير متفق عليه.
```

لا ينطبق الاسترجاع عند:

```text
- مفتاح مزود خارجي غير صالح.
- نفاد رصيد العميل لدى المزود.
- قيود من OpenAI أو Gemini أو Anthropic أو DeepSeek أو غيرها.
- عدم توفير بيانات الاختبار من العميل.
- تغيير نطاق التجربة.
- تجاوز الحصة المحددة في الخطة.
```

---

## 15. صياغة نهاية الصفحة

بدل عبارة:

```text
A supervisor will review the request and activate the appropriate client path.
```

تعتمد الصفحة هذه الصياغة:

```text
Choose an offer or plan to continue automatically.
Enterprise and institutional custom offers require direct contact by email.
```

وبالعربية:

```text
اختر عرض التجربة أو خطة Pilot المناسبة للمتابعة آليًا.
العروض المؤسسية أو المخصصة تتطلب التواصل المباشر عبر البريد.
```

---

## 16. ما لا يجب تنفيذه الآن

```text
لا ننشئ صفحة HTML الآن.
لا نضيف /subscriptions route الآن.
لا نربط أزرارًا حقيقية بـ checkout الآن.
لا ننشئ activation flow الآن ضمن هذه المهمة.
لا نثبت أسعارًا نهائية الآن.
لا نثبت Enterprise كسعر ثابت.
لا نربط API Key بالـ UI session.
لا نخلط صفحة الاشتراكات مع Admin/Supervisor Mode.
```

---

## 17. المتطلبات السابقة للتنفيذ لاحقًا

قبل تنفيذ صفحة الاشتراكات يجب إغلاق أو تحديد:

```text
1. AUTH-02 create_admin + Client Activation Flow.
2. PLAN-01 pricing_version.
3. BILL-01 Billing checkout + webhook idempotency.
4. ربط plan_id بـ subscription.
5. ربط subscription بـ quota_limit.
6. ربط plan بـ api_key_limit.
7. تحديد مسار Enterprise contact.
8. تحديد البريد المعتمد للمؤسسات.
9. تحديد هل الأزرار تذهب إلى activation أم checkout.
10. تحديد هل توجد مرحلة trial قبل الدفع أم لا.
```

---

## 18. ملف pricing_version المستقبلي

عند الوصول إلى PLAN-01، يجب إنشاء ملف versioned للأسعار بدل كتابة الأسعار داخل الواجهة فقط.

محتوى الملف يجب أن يشمل:

```text
pricing_version
effective_from
currency
plans
plan_id
display_name
price
duration
quota_limit
api_key_limit
provider_limit
BYOK notice
success criteria
refund boundary
enterprise_contact_policy
```

الخطط الأولية:

```text
Pilot Starter
Pilot Standard
Pilot Technical
Enterprise / Custom
```

مع بقاء Enterprise قابلة للمراجعة وعدم تثبيتها كسعر نهائي.

---

## 19. الحكم النهائي

صفحة الاشتراكات مهمة، لكنها ليست خطوة تنفيذية الآن.

الحكم المعتمد:

```text
نثبت محتوى الصفحة ومنطقها في تقرير.
نؤجل التنفيذ إلى ما بعد التفعيل والفوترة.
نحافظ على أن كل الاختيارات العادية تسير آليًا.
نحصر التواصل اليدوي في المؤسسات وEnterprise فقط.
نثبت BYOK وحدود الاسترجاع ومعايير النجاح بوضوح.
```

اسم المهمة التخطيطية:

```text
UI-00A — Plan subscriptions page content and routing logic
```

اسم التقرير المقترح:

```text
docs/reports/UI_00A_SUBSCRIPTIONS_PAGE_CONTENT_PLAN_AR.md
```

اسم الكوميت عند حفظ التقرير فقط:

```text
Docs: plan subscriptions page content and routing
و ليتم الانطلاق في التنفيذ الابعد الاطلاع على ملفات واجهة البرنامج و محتواها ليكون التنفيذ مطابقا   لها 
```
و كذلك مراجعة صفحة المشرف و تجهيزها
