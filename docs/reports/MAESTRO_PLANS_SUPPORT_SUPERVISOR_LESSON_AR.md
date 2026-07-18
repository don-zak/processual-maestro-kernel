# درس المشرفة: خطط Processual Maestro والوحدات والدعم الإضافي

## المرحلة

PRICING-COMMERCIAL-01 — document plan packaging lesson.

هذا الملف تقرير Markdown تعليمي للمشرفة التي تتابع العملاء، الاستهلاك،
الدعم، الترقية، والإجابة عن أسئلة التسعير.

هذا التقرير ليس enforcement code. لا يضيف حظرًا للطلبات ولا يغير quota في
backend. وظيفته شرح القرار التجاري حتى تكون مرحلة enforcement التالية مبنية
على فهم واضح.

---

## 1. الفكرة الأساسية

Processual Maestro لا يبيع tokens.

Processual Maestro يبيع:

- قدرة حوكمة Governance capacity.
- API integration layer.
- Usage ledger.
- Quota controls.
- Scoped service API keys.
- Reports and decision metadata.
- BYOK boundary.
- دعم وتشغيل حسب الخطة.

الجملة المختصرة التي يجب أن تحفظها المشرفة:

> Maestro لا يبيع provider tokens. Maestro يبيع governance capacity.

---

## 2. ما معنى BYOK؟

BYOK تعني Bring Your Own Key.

في Maestro:

- العميل يستعمل Maestro API Key للوصول إلى Maestro.
- العميل لا يحصل على provider key مملوك لـ Maestro.
- أي OpenAI أو Gemini أو Anthropic أو DeepSeek أو provider آخر يكون من حساب
  العميل نفسه.
- تكلفة provider tokens ليست ضمن سعر Maestro.
- Maestro يحاسب على Maestro usage units.

### جواب جاهز للعميل

إذا سأل العميل: هل السعر يشمل تكلفة OpenAI أو Gemini؟

الجواب:

> لا. سياسة Maestro هي BYOK. السعر يشمل استعمال Maestro ووحدات الحوكمة
> والسجل والدعم حسب الخطة، أما تكلفة provider tokens فتدفع من حساب العميل
> لدى المزود الخارجي.

---

## 3. ما هي Maestro usage unit؟

Maestro usage unit هي وحدة قياس تجارية داخل Maestro.

ليست:

- token.
- API key.
- raw HTTP request فقط.
- provider call.

هي تمثل قيمة العمل داخل Maestro مثل:

- تحليل.
- قرار حوكمة.
- مقارنة.
- تقرير.
- auto-repair.
- usage ledger.
- quota accounting.
- audit metadata.

---

## 4. كتالوج المهام والوحدات

| المهمة | Endpoint | Units |
| --- | --- | ---: |
| Health live | `/health/live` | 0 |
| Health ready | `/health/ready` | 0 |
| Adapter status | `/adapters/status` | 0 |
| Subscription check | `/settings/subscription` | 0 |
| Analyze | `/cgt/analyze` | 1 |
| Governance decision | `/cgt/govern` | 1 |
| Batch governance | `/cgt/govern/batch` | item_count × 1 |
| Compare | `/cgt/govern/compare` | 2 |
| Fate report | `/reports/fate` | 2 |
| Governance report | `/cgt/govern/report` | 3 |
| LLM report generation | `/reports/generate-llm` | 5 |
| Auto repair | `/cgt/govern/auto-repair` | 5 |

### قاعدة المتابعة

- 0 units تعني endpoint تشغيلي مجاني.
- 1 unit تعني عملية أساسية.
- 2 إلى 5 units تعني عملية أثقل أو أعلى قيمة.
- batch يحسب بعدد العناصر، لا كطلب واحد فقط.

---

## 5. الخطط الأساسية

### 5.1 Developer / Internal

| بند | القيمة |
| --- | --- |
| Monthly units | 2,000 |
| السعر | مجاني أو داخلي |
| الاستخدام | تطوير وتجارب داخلية |
| Production integration | لا |
| الدعم | لا يوجد دعم تجاري |
| Overage | غير مخصص للبيع |

تستخدم هذه الخطة للتطوير الداخلي أو إثبات أن API key يعمل.

لا تصلح لعميل production.

---

### 5.2 Starter / Pilot Starter

| بند | القيمة |
| --- | --- |
| Monthly units | 10,000 |
| السعر المقترح | 49 إلى 99 USD/month |
| الاستخدام | تجربة صغيرة أو pilot خفيف |
| Production integration | محدود |
| الدعم | Email أو دعم خفيف |
| Overage | يفضل الترقية بدل overage |

متى نستخدمها؟

- عميل يريد تجربة النظام.
- فريق صغير.
- لا يحتاج SLA.
- لا يحتاج قناة دعم مخصصة.
- لا يحتاج integration production حقيقي.

علامة الترقية:

إذا تجاوز العميل 10,000 units أو طلب production integration، ننقله إلى
Business.

---

### 5.3 Business

| بند | القيمة |
| --- | --- |
| Monthly units | 100,000 |
| Launch price | 199 USD/month |
| Standard price | 249 USD/month |
| Overage | 49 USD لكل 100,000 units إضافية |
| الاستخدام | Production team usage |
| الدعم | Basic priority support |
| Analytics | Basic usage visibility |
| SLA | Best effort أو محدود |

هذه هي خطة 100,000 وحدة.

مهم جدًا:

100,000 units = Business production tier.

ليست Enterprise كاملة.

#### ماذا تحتوي Business؟

- Production API key.
- Usage ledger.
- Quota controls.
- BYOK boundary.
- Basic usage summary.
- Basic support.
- إمكانية overage.

#### ماذا لا تحتوي Business افتراضيًا؟

- Dedicated Slack أو Teams.
- SSO/RBAC.
- Private deployment.
- Long audit retention.
- Custom SLA.
- Enterprise onboarding مكثف.

---

### 5.4 Enterprise Integration Starter

| بند | القيمة |
| --- | --- |
| Monthly units | 50,000 |
| السعر المقترح | 299 إلى 499 USD/month |
| الاستخدام | Enterprise pilot |
| الدعم | Onboarding خفيف |
| SLA | محدود |
| Usage visibility | نعم |
| Production integration | نعم، لكن بحجم أولي |

لماذا هذه الخطة 50,000 فقط لكنها أغلى من Starter؟

لأنها لا تبيع الحجم فقط. هي تبيع متابعة enterprise pilot، وضبط integration،
وتوجيه العميل في أول ربط حقيقي.

تستخدم هذه الخطة مع:

- شركة كبيرة تبدأ pilot.
- شركة اتصالات تختبر integration محدود.
- عميل يحتاج service key لا console فقط.
- عميل يحتاج متابعة تشغيلية أولى.

---

### 5.5 Enterprise Integration

| بند | القيمة |
| --- | --- |
| Monthly units | 500,000 |
| السعر المقترح | 999 USD/month minimum |
| Overage | 39 USD لكل 100,000 units إضافية |
| الاستخدام | Real enterprise integration |
| الدعم | Priority support |
| Usage visibility | Advanced |
| Audit | نعم |
| SLA | حسب العقد |
| Service identities | متعددة |

هذه بداية Enterprise الحقيقية.

تستخدم مع:

- شركات الاتصالات.
- منصات SaaS تريد تضمين Maestro.
- استعمال شهري كبير.
- حاجة إلى audit وquota visibility.
- متابعة تشغيلية من المشرفة.
- أكثر من service identity.

---

### 5.6 Enterprise Custom

| بند | القيمة |
| --- | --- |
| Monthly units | configurable |
| السعر | Custom annual contract |
| الاستخدام | مؤسسة كبيرة أو نشر خاص |
| SLA | مخصص |
| SSO/RBAC | حسب العقد |
| Private/VPC deployment | ممكن |
| Support channel | مخصص |
| Retention | مخصص |

تستخدم عندما يحتاج العميل:

- أكثر من 1M units/month.
- SSO/RBAC.
- Security review.
- Data residency.
- نشر private أو VPC.
- قناة دعم مباشرة.
- عقد سنوي.

قاعدة مهمة:

Enterprise Custom لا يملك quota ثابتة داخل catalog. يجب أن تكون configurable.

---

## 6. كم تكلف 100,000 وحدة؟

القرار المقترح:

| الصيغة | السعر |
| --- | ---: |
| Business launch | 199 USD/month |
| Business standard | 249 USD/month |
| Extra 100k units | 49 USD/month |
| Enterprise extra 100k | 39 USD/month |

### سعر الوحدة عند 199 USD

| الحجم | السعر |
| --- | ---: |
| 1 unit | 0.00199 USD |
| 1,000 units | 1.99 USD |
| 10,000 units | 19.90 USD |
| 100,000 units | 199 USD |

### سعر الوحدة عند 249 USD

| الحجم | السعر |
| --- | ---: |
| 1 unit | 0.00249 USD |
| 1,000 units | 2.49 USD |
| 10,000 units | 24.90 USD |
| 100,000 units | 249 USD |

---

## 7. تكلفة المهام على Business 199 USD

| المهمة | Units | تكلفة Maestro تقريبية |
| --- | ---: | ---: |
| Governance decision | 1 | 0.00199 USD |
| Analyze | 1 | 0.00199 USD |
| Batch item | 1 | 0.00199 USD لكل item |
| Compare | 2 | 0.00398 USD |
| Fate report | 2 | 0.00398 USD |
| Governance report | 3 | 0.00597 USD |
| Generate LLM report | 5 | 0.00995 USD |
| Auto-repair | 5 | 0.00995 USD |

ملاحظة:

هذه تكلفة Maestro فقط. إذا استدعت المهمة provider خارجيًا، فإن تكلفة
provider يدفعها العميل عبر BYOK.

---

## 8. هامش الربح المطلوب

الهامش المستهدف:

| الهامش | المعنى |
| --- | --- |
| 75% gross margin | حد أدنى صحي |
| 80% gross margin | هدف مفضل |
| أقل من 70% | يحتاج مراجعة |

على سعر 199 USD/month:

| هامش | أقصى تكلفة مباشرة | ربح إجمالي |
| --- | ---: | ---: |
| 75% | 49.75 USD | 149.25 USD |
| 80% | 39.80 USD | 159.20 USD |

على سعر 249 USD/month:

| هامش | أقصى تكلفة مباشرة | ربح إجمالي |
| --- | ---: | ---: |
| 75% | 62.25 USD | 186.75 USD |
| 80% | 49.80 USD | 199.20 USD |

قاعدة المشرفة:

إذا احتاج العميل دعمًا بشريًا متكررًا، فإن هذا الدعم يجب أن يدخل في add-on
أو خطة أعلى. لا يجب أن يستهلك الهامش بصمت.

---

## 9. الإضافات المدفوعة Add-ons

| الإضافة | السعر المقترح | المعنى |
| --- | ---: | --- |
| Extra 100k units | 49 USD/month | رصيد إضافي |
| Enterprise extra 100k | 39 USD/month | سعر حجم للمؤسسات |
| Usage analytics + export | 49 إلى 99 USD/month | تقارير CSV/JSON |
| Audit retention 12 months | 99 USD/month | حفظ logs أطول |
| Priority support | 199 إلى 399 USD/month | أولوية متابعة |
| Dedicated Slack/Teams | 300 USD/month | قناة مباشرة |
| SSO/RBAC | 300 إلى 500 USD/month | تحكم وصول مؤسسي |
| Onboarding | 500 إلى 2,000 USD مرة واحدة | تدريب وربط أولي |
| Private/VPC deployment | custom | نشر مخصص |

---

## 10. ماذا يعني الدعم الإضافي؟

الدعم الإضافي ليس مجرد رد على سؤال.

قد يشمل:

1. جلسة onboarding.
2. مراجعة أول integration.
3. ضبط scopes.
4. ضبط quotas.
5. مراجعة usage spikes.
6. مساعدة في BYOK provider setup.
7. تحليل أخطاء 429 quota.
8. تحليل أخطاء provider balance.
9. تقرير شهري للاستهلاك.
10. نصائح لتقليل units.
11. تصعيد أعطال production.
12. متابعة retention/export/audit.

قاعدة عملية:

كل دعم بشري متكرر له تكلفة. لذلك يجب أن يظهر في الخطة أو add-on.

---

## 11. كيف تجيب المشرفة عن أسئلة العملاء؟

### سؤال: هل 100,000 وحدة تعني 100,000 token؟

الجواب:

> لا. هي 100,000 Maestro usage units. هذه تقيس استعمال خدمات Maestro مثل
> الحوكمة والتحليل والتقارير. Provider tokens منفصلة بسبب BYOK.

### سؤال: لماذا 50,000 Enterprise Starter أغلى من Business؟

الجواب:

> لأنها خطة enterprise pilot وليست خطة حجم فقط. السعر يشمل متابعة الربط،
> ضبط service key، scopes، quota، وفهم الاستعمال الأولي.

### سؤال: ماذا يحدث إذا تجاوزنا 100,000 وحدة؟

الجواب:

> يمكن إضافة overage بسعر 49 USD لكل 100,000 وحدة إضافية، أو الترقية إذا
> أصبح التجاوز متكررًا.

### سؤال: هل الدعم مشمول؟

الجواب:

> الدعم الأساسي مشمول حسب الخطة. الدعم المتقدم مثل Slack channel، SLA،
> onboarding مكثف، أو audit retention يكون ضمن Enterprise أو add-ons.

### سؤال: هل ندفع لكم تكلفة LLM؟

الجواب:

> لا. تكلفة LLM أو provider تدفعونها مباشرة لحسابكم عند provider. Maestro
> يحاسب على وحدات Maestro فقط.

---

## 12. كيف تتابع المشرفة الاستهلاك؟

يجب متابعة:

- client_id.
- api_key_id.
- plan_id.
- quota_limit.
- quota_used.
- quota_remaining.
- units_charged.
- endpoint_class.
- pricing_version.
- billing_policy.
- provider_cost_included.
- status_code.
- quota_rejected_count.

تفسير سريع:

- زيادة `/cgt/govern` تعني استعمال أساسي.
- زيادة reports أو auto-repair تعني استعمال أعلى قيمة.
- زيادة `quota_rejected_count` تعني حاجة إلى overage أو ترقية.
- أخطاء provider ليست بالضرورة تكلفة Maestro بسبب BYOK.

---

## 13. أمثلة عملية

### مثال 1: Business طبيعي

العميل:

- لديه 100,000 units.
- استعمل 85,000.
- لا يوجد rejected_count.

القرار:

يبقى على Business.

### مثال 2: Business تجاوز الرصيد

العميل:

- لديه 100,000 units.
- استعمل 120,000.

القرار:

إما overage بـ 49 USD لكل 100,000 إضافية، أو ترقية إذا تكرر التجاوز.

### مثال 3: شركة اتصالات في pilot

العميل:

- يستعمل 30,000 units فقط.
- لكنه يحتاج integration key ومتابعة وربط.

القرار:

Enterprise Integration Starter، وليس Starter عاديًا.

### مثال 4: عميل صغير يريد SSO وقناة Slack

حتى لو استهلاكه 80,000 units فقط، فهو يحتاج قدرات مؤسسة.

القرار:

Business + add-ons أو Enterprise Integration.

---

## 14. قواعد التصعيد

تصعد المشرفة العميل إذا تحقق واحد أو أكثر:

1. تجاوز 80% من quota بشكل متكرر.
2. طلب production integration.
3. طلب أكثر من service identity.
4. طلب retention أطول.
5. طلب audit/export.
6. طلب support channel.
7. طلب SLA.
8. طلب SSO/RBAC.
9. استهلاك heavy endpoints بكثافة.
10. rejected_count متكرر.

---

## 15. قواعد لا يجب كسرها

1. لا نبيع provider tokens ضمن Maestro.
2. لا نقول إن LLM cost included.
3. لا نجعل 50,000 units هي Enterprise الكاملة.
4. لا نسعر Maestro كـ raw API gateway فقط.
5. لا ندخل USD prices في backend enforcement.
6. لا نقدم دعمًا بشريًا كثيفًا داخل خطة رخيصة بلا add-on.
7. لا نستخدم admin area كواجهة عميل enterprise.
8. لا نفصل quota عن usage ledger.
9. لا نطبق enforcement بلا اختبار rejection واضح.
10. لا نكسر BYOK policy.

---

## 16. ماذا تفعل المرحلة التقنية التالية؟

بعد هذا التقرير، المرحلة التقنية التالية هي:

PRICING-UNITS-03B — enforce pricing units through existing quota path.

المطلوب فيها:

1. حساب `pricing_decision(endpoint).units_charged`.
2. تمرير `units_charged` إلى `consume_quota(amount=...)`.
3. جعل endpoints المجانية لا تستهلك quota.
4. رفض الطلب إذا `quota_used + units_charged > quota_limit`.
5. حفظ BYOK metadata في usage logs.
6. عدم إدخال أسعار الدولار في الكود.
7. عدم إنشاء quota system جديد إذا كان الموجود يكفي.

---

## 17. ملخص تنفيذي للمشرفة

Business:
100,000 units/month.
199 USD launch أو 249 USD standard.

Enterprise Integration Starter:
50,000 units/month.
299 إلى 499 USD/month.
مناسب لـ enterprise pilot.

Enterprise Integration:
500,000 units/month.
999 USD/month minimum.
مناسب لـ production integration الحقيقي.

Enterprise Custom:
configurable.
عقد سنوي أو نشر خاص.

الهامش:
75% حد أدنى، 80% هدف مفضل.

الدعم:
أي دعم متقدم أو متكرر يجب أن يكون add-on أو خطة أعلى.
