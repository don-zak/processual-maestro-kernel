# تقرير تعميق تنفيذ Adaptive Governance Toolkit

تاريخ التسليم: 2026-05-03  
الإصدار: 1.6.0

## ملخص التنفيذ

تم تنفيذ جولة رفع كفاءة جديدة فوق v1.0.0. ركّز هذا الإصدار على حدود التشغيل الفعلية: فحص checkpoint دون side effects، تحويل توصيات adaptive إلى RuntimeCommand آمن، وإغلاق outcomes المعلّقة تلقائيًا بشكل محافظ. تم الحفاظ على سلامة الكرنل بعدم تعديل معادلات Ψ أو منطق `cgtlib` الداخلي.

## ما تم الحفاظ عليه

- عدم تعديل `ContinuityEngine` equations.
- عدم تعديل `MetricCoefficientMapper` equations.
- عدم تعديل cgtlib internals.
- عدم إلغاء human gates للقرارات الحرجة.
- استمرار توافق الاختبارات والأمثلة السابقة.

## إضافات 0.9.0

### 1. Adaptive Operations Governor

أضيف الملف:

```text
processual_kernel/adaptive/ops_governance.py
```

ويضيف طبقة read-only لا تغيّر الكرنل، بل تقرأ الأدلة وتصدر قرارات تشغيلية حول:

```text
runtime mode transitions
post-patch verification
adaptive evidence packs
```

### 2. Runtime Mode Transition Decisions

أضيفت الأنواع والواجهات:

```python
AdaptiveModeTransitionDecision
toolkit.propose_runtime_mode_transition(...)
toolkit.apply_runtime_mode_transition(...)
```

الغرض: منع الانتقال إلى `CONTROLLED_ADAPTIVE` إلا بعد اجتياز quality gate وruntime invariants وعدم وجود pending outcomes أو approvals. كما أن high/critical workflows لا تنتقل تلقائيًا، بل تحتاج human approval.

### 3. Post-Patch Verification and Rollback

أضيف:

```python
PatchVerificationResult
toolkit.verify_applied_patches(..., rollback_on_regression=True)
```

الغرض: بعد تطبيق patch في controlled mode، تتم مراجعة outcomes والمقاييس مثل false retry/reroute وhandoff failure وoutcome coverage. إذا ظهرت regression، يمكن التراجع عبر rollback آمن دون لمس معادلات Ψ أو `cgtlib`.

### 4. Adaptive Evidence Pack

أضيف:

```python
AdaptiveEvidencePack
toolkit.build_adaptive_evidence_pack(...)
```

وهو يجمع evidence قابل للتصدير في JSON يحتوي:

```text
profile
policy
tempo
metrics
quality gate
runtime invariants
checkpoints
drift alerts
handoff suggestions
policy critiques
policy patches
approvals
workflow history
transition decision
```

### 5. Audit events إضافية

تم توسيع `AuditEventType` ليغطي:

```text
adaptive_mode_transition
patch_verification
adaptive_evidence_pack
```

### 6. اختبارات جديدة

أضيف الملف:

```text
tests/test_adaptive_ops_governance_v08.py
```

ويغطي:

- السماح بالانتقال من `RECOMMEND` إلى `CONTROLLED_ADAPTIVE` عند وجود evidence نظيف.
- منع ترقية critical workflows تلقائيًا وفتح human approval.
- rollback تلقائي اختياري عند فشل patch verification.
- التأكد من أن rollback لا يلمس `dt` أو `alpha`.
- تصدير evidence pack كامل قابل للقراءة والتدقيق.

## نتائج الاختبارات

```text
python -m pytest -q
39 passed
```

## نتائج تشغيل الأمثلة

```text
python examples/basic_usage.py
python examples/maestro_workflow.py
python examples/adaptive_usage.py
```

كلها تعمل بنجاح.

## الملفات الأساسية المعدلة أو المضافة

```text
processual_kernel/adaptive/ops_governance.py
processual_kernel/adaptive_toolkit.py
processual_kernel/adaptive_types.py
processual_kernel/audit.py
processual_kernel/adaptive/policy_profiles.py
processual_kernel/adaptive/__init__.py
processual_kernel/__init__.py
tests/test_adaptive_ops_governance_v08.py
README.md
IMPLEMENTATION_REPORT_AR.md
pyproject.toml
```

## الخلاصة

الإصدار 0.9.0 يضيف حوكمة تشغيلية أعلى للدورة adaptive: ليس فقط profile → policy → checkpoint → review، بل أيضًا transition decisions → patch verification → rollback عند regression → evidence pack للتدقيق. كل ذلك بقي حول الكرنل، مع استمرار منع تعديل القلب الرياضي أو تجاوز الحواجز البشرية الحرجة.


---

# تقرير تنفيذ v0.9.0 — Adaptive Operating Contracts & Evidence Validation

## الهدف

تعميق توجهات الورقة التقنية بعد v0.8.0 بتحويل الحوكمة التشغيلية إلى عقود صريحة قابلة للتحقق، وربط evidence packs وfinal review بمؤشرات استقرار وتعافي أوضح. تم الحفاظ على القاعدة المعمارية: الأدوات تعمل حول الكرنل ولا تعدّل معادلات Ψ أو منطق `cgtlib`.

## الإضافات

- إضافة `AdaptiveOperatingContractManager`.
- إضافة `OperatingContract` و `OperatingContractValidation`.
- إضافة `AdaptiveConvergenceMonitor` و `AdaptiveConvergenceReport`.
- إضافة `RecoveryPlaybook` و `RecoveryPlaybookStep`.
- إضافة `EvidencePackValidationResult`.
- تحديث `AdaptiveCycleReport` ليحمل:
  - operating contract
  - contract validation
  - convergence report
- تحديث `AdaptiveReviewReport` ليحمل:
  - operating contract
  - contract validation
  - convergence report
  - recovery playbook
  - evidence pack validation
- تحديث `AdaptiveEvidencePack` إلى schema `adaptive-evidence-pack-0.9.0`.
- إضافة أحداث audit جديدة:
  - `operating_contract`
  - `operating_contract_validation`
  - `recovery_playbook`
  - `evidence_pack_validation`
  - `adaptive_convergence`

## اختبارات جديدة

أضيف الملف:

```text
tests/test_adaptive_operating_contracts_v09.py
```

ويغطي:

- منع تعديل حقول القلب مثل `dt` عبر operating contract.
- منع auto-reroute للعمليات التي تحتاج human gate.
- قفل critical workflows على `RESTRICTED_CRITICAL`.
- ربط `run_adaptive_cycle` بالعقد والتحقق والتقارب.
- بناء final review مع recovery playbook.
- تصدير evidence pack والتحقق من سلامة schema والعدادات.
- كشف count mismatch داخل evidence pack.

## نتائج الاختبارات

```text
python -m pytest -q
39 passed
```

## تشغيل الأمثلة

```text
python examples/basic_usage.py
python examples/maestro_workflow.py
python examples/adaptive_usage.py
```

كلها تعمل بنجاح.

## خلاصة السلامة

- لا تعديل على `dt` أو `alpha` أو معادلات Ψ.
- لا تعديل على `cgtlib`.
- critical workflows لا تُرقّى إلى controlled adaptive تلقائيًا.
- risky actions مثل archive/reroute/reactivate/quarantine تبقى human-gated حسب العقد.
- evidence pack أصبح قابلًا للتحقق قبل التسليم أو المراجعة الخارجية.

# تقرير تنفيذ v1.0.0 — Adaptive Certification & Integrity

## هدف الجولة

تعميق توجهات الورقة التقنية بإضافة طبقة اعتماد وسلامة فوق evidence packs وعقود التشغيل. هذه الطبقة لا تغيّر الكرنل، ولا تطبق سياسات تلقائيًا، بل تصدر تقارير قابلة للتدقيق حول سلامة الأدلة وجاهزية الانتقال أو التفويض.

## الإضافات

```text
processual_kernel/adaptive/certification.py
```

أضيفت الأنواع:

```python
CertificationLevel
AdaptiveIntegrityReport
AdaptiveCertificationReport
ActionAuthorizationReport
```

وأضيفت الواجهات:

```python
toolkit.validate_adaptive_integrity(pack)
toolkit.certify_adaptive_readiness(workflow_id, pack=pack)
toolkit.authorize_adaptive_action(workflow_id, action, auto_execute=False)
```

## ضمانات السلامة

- أي checksum mismatch في evidence pack يجعل integrity غير صالح.
- أي count mismatch أو artifact ناقص يمنع certification.
- certification لا تمر إذا فشلت quality gates أو runtime invariants أو operating contract validation.
- critical archive لا يُنفّذ تلقائيًا؛ يتحول إلى `HumanApprovalRequest`.
- `authorize_adaptive_action` لا ينفذ إلا الإجراءات المسموحة بالعقد وغير الخاضعة لبوابة بشرية.

## الاختبارات المضافة

```text
tests/test_adaptive_certification_v10.py
```

وتغطي:

- كشف العبث في evidence pack عبر checksum/count mismatch.
- تفويض وتنفيذ إجراء آمن فقط.
- منع archive لمسار critical مع إنشاء طلب موافقة بشرية.
- إدراج integrity/certification داخل final adaptive review.

## نتيجة الاختبارات

```text
43 passed
```



# تقرير تنفيذ v1.1.0 — Efficiency Hardening & Runtime Boundary

## هدف الجولة

رفع كفاءة البرنامج تشغيليًا عبر إضافة فحص جدولة read-only، وجسر Runtime آمن، وجمع outcomes تلقائي محافظ للقرارات المعلّقة. هذه الجولة لا تغيّر معادلات Ψ ولا منطق `cgtlib`، ولا تنفذ أي إجراء adaptive إلا بعد المرور بعقد التشغيل والتفويض.

## الإضافات

```text
processual_kernel/adaptive/checkpoint_controller.py
processual_kernel/adaptive/runtime_adapter.py
```

أضيفت الأنواع:

```python
CheckpointScheduleDecision
RuntimeCommand
RuntimeCommandResult
AutoOutcomeReport
```

وأضيفت الواجهات:

```python
toolkit.checkpoint_schedule_decision(...)
toolkit.execute_checkpoint_recommendation(...)
toolkit.auto_evaluate_pending_outcomes(...)
```

## ضمانات السلامة

- فحص الجدولة لا ينشئ checkpoint ولا يغيّر حالة workflow.
- أوامر Runtime لا تُنفّذ إلا إذا كانت authorized من `OperatingContract`.
- `dry_run=True` يبقى الافتراضي الآمن لأوامر Runtime.
- الأوامر التي تحتاج human gate تُحوّل إلى `HumanApprovalRequest` ولا تنفذ تلقائيًا.
- outcome sweep محافظ، ويمكن تجاوزه بنتائج runtime حقيقية عند توفرها.
- evidence pack أصبح يضم runtime commands وauto outcome reports للتدقيق.

## الاختبارات المضافة

```text
tests/test_adaptive_efficiency_v11.py
```

وتغطي:

- فحص checkpoint schedule دون side effects.
- تنفيذ dry-run لا يغيّر workflow state.
- تنفيذ pause مصرح به فقط عبر runtime adapter.
- إغلاق outcomes المعلّقة تلقائيًا عند اكتمال workflow.
- ظهور runtime commands وauto outcome reports داخل evidence pack.

## نتيجة الاختبارات

```text
48 passed
```

## تشغيل الأمثلة

```text
python examples/basic_usage.py
python examples/maestro_workflow.py
python examples/adaptive_usage.py
```

كلها تعمل بنجاح.


# تقرير تنفيذ v1.2.0 — Efficiency Coalescing & Idempotent Runtime Commands

## هدف الجولة

رفع كفاءة البرنامج تشغيليًا عبر منع تكرار العمل adaptive غير الضروري: عواصف checkpoints المتقاربة، وتكرار تنفيذ نفس Runtime command عند retry أو إعادة إرسال نفس التوصية. هذه الجولة لا تغيّر القلب الرياضي ولا منطق `cgtlib`، وكل التنفيذ mutating يبقى خلف `OperatingContract` و `authorize_adaptive_action`.

## الإضافات

```text
processual_kernel/adaptive/efficiency.py
```

أضيفت الأنواع:

```python
CheckpointCoalescingDecision
RuntimeCommandDeduplicationResult
AdaptiveEfficiencyReport
```

وأضيفت/وسّعت الواجهات:

```python
toolkit.checkpoint_schedule_decision(..., coalesce_window_seconds=30.0)
toolkit.maybe_checkpoint(..., coalesce_window_seconds=0.0)
toolkit.execute_checkpoint_recommendation(..., prevent_duplicate=True, idempotency_key=None)
toolkit.adaptive_efficiency_report(workflow_id)
```

## ضمانات السلامة

- coalescing لا يلغي final checkpoints ولا critical risk events مثل `critical_agent_failure` و `human_escalation`.
- `maybe_checkpoint` يحافظ على السلوك القديم افتراضيًا، ولا يستخدم coalescing إلا إذا مرّر المضيف `coalesce_window_seconds > 0`.
- idempotency لا يسجل dry-run كأمر mutating، ولا يمنع dry-run من التكرار.
- أمر runtime لا يدخل idempotency cache إلا بعد تنفيذ mutating ناجح.
- duplicate mutating command يرجع `RuntimeCommandResult` غير منفّذ مع سبب واضح ولا يغيّر حالة workflow.
- حزمة الأدلة أصبحت تحمل coalescing/deduplication/efficiency reports للتدقيق.

## الاختبارات المضافة

```text
tests/test_adaptive_efficiency_v12.py
```

وتغطي:

- coalescing للأحداث غير الحرجة المتكررة.
- عدم coalescing للأحداث الحرجة.
- منع duplicate checkpoints عند استخدام `maybe_checkpoint` المحروس.
- منع تنفيذ Runtime command mutating مكرر بنفس idempotency key.
- تضمين آثار الرفع في evidence pack والتحقق من schema `adaptive-evidence-pack-1.2.0`.

## نتيجة الاختبارات

```text
52 passed
```

## تشغيل الأمثلة

```text
python examples/basic_usage.py
python examples/maestro_workflow.py
python examples/adaptive_usage.py
```

كلها تعمل بنجاح.

# تقرير تنفيذ v1.3.0 — Backpressure, Runtime Batching & Bounded Outcome Sweeps

## هدف الجولة

رفع كفاءة التشغيل adaptive عبر تقليل تكرار polling والدفعات mutating الكبيرة وتقييم outcomes دفعة واحدة عند وجود backlog. هذه الجولة لا تعدل معادلات Ψ، ولا تغير منطق `cgtlib`، ولا تتجاوز `OperatingContract` أو human approval gates.

## الإضافات

```text
processual_kernel/adaptive/efficiency.py
```

أضيفت الأنواع:

```python
CheckpointBackpressureHint
RuntimeCommandBatchPlan
OutcomeSweepPlan
```

وتم توسيع:

```python
AdaptiveEfficiencyReport
AdaptiveEvidencePack
```

وأضيفت/وسّعت الواجهات:

```python
toolkit.runtime_command_batch_plan(...)
toolkit.auto_evaluate_pending_outcomes(..., max_items=None)
toolkit.adaptive_efficiency_report(workflow_id)
```

## تحسينات الكفاءة

- استمرار coalescing عبر نافذة backpressure عند تكرار نفس event عدة مرات.
- إصدار backpressure hints حتى يعرف runtime المضيف متى يعيد فحص الجدولة بدل تكرار polling.
- تخطيط دفعات runtime commands قبل التنفيذ، مع منع الإفراط في الأوامر mutating.
- جعل outcome sweeps قابلة للتنفيذ على دفعات bounded لتقليل الحمل في workflows الكبيرة.
- تضمين كل artifacts الجديدة داخل evidence pack.

## ضمانات السلامة

- final checkpoints وcritical events لا تخضع لـ backpressure.
- Runtime batch planning لا ينفذ شيئًا؛ هو read-only planning فقط.
- تنفيذ runtime الفعلي يبقى خلف `authorize_adaptive_action` و`OperatingContract`.
- outcome batching لا يختلق outcomes؛ هو يحدد عدد القرارات التي سيتم تقييمها في sweep واحد.
- schema evidence pack أصبح `adaptive-evidence-pack-1.3.0` مع validation للعدادات الجديدة.

## الاختبارات المضافة

```text
tests/test_adaptive_efficiency_v13.py
```

وتغطي:

- بقاء repeated event storm داخل backpressure/coalescing عبر أكثر من تكرار.
- تخطيط دفعات Runtime command ومنع تجاوز حد mutating commands.
- تنفيذ outcomes sweep على دفعات bounded.
- تضمين artifacts الجديدة داخل evidence pack والتحقق من schema `adaptive-evidence-pack-1.3.0`.

## نتيجة الاختبارات

```text
56 passed
```



# تقرير تنفيذ v1.4.0 — Priority Outcome Sweeps & Adaptive Workload Budgets

## هدف الجولة

رفع كفاءة التشغيل adaptive عبر تقليل sweeps الفارغة ومنع الأعمال الاختيارية المكلفة من التوسع بلا حدود. هذه الجولة لا تعدل معادلات Ψ، ولا تغير منطق `cgtlib`، ولا تتجاوز `OperatingContract` أو human approval gates.

## الإضافات

```text
processual_kernel/adaptive/efficiency.py
processual_kernel/adaptive_toolkit.py
processual_kernel/adaptive_types.py
```

أضيف النوع:

```python
AdaptiveWorkloadBudgetDecision
```

وتم توسيع:

```python
OutcomeSweepPlan
AdaptiveEfficiencyReport
AdaptiveEvidencePack
```

وأضيفت الواجهة:

```python
toolkit.adaptive_workload_budget_decision(...)
```

## تحسينات الكفاءة

- اختيار أقدم pending outcomes المستحقة أولًا بدل المرور على عناصر حديثة جدًا ثم تخطيها.
- توثيق القرارات المؤجلة في `deferred_count` داخل `OutcomeSweepPlan`.
- إضافة `selected_decision_ids` لتصبح sweeps قابلة للتدقيق وإعادة التتبع.
- إضافة workload budget اختياري للأعمال adaptive المكلفة مثل replay أو evidence export.
- توسيع تقرير الكفاءة ليعرض عدد الأعمال المؤجلة بسبب الميزانية وعدد outcomes المؤجلة بسبب age window.

## ضمانات السلامة

- Workload budget لا يعطي تفويضًا لأي runtime mutation؛ هو يمنع أو يؤجل العمل الاختياري فقط.
- Runtime execution لا يزال خلف `authorize_adaptive_action` و`OperatingContract`.
- outcome prioritization لا يختلق outcomes ولا يتجاوز age window؛ هو فقط يختار العناصر المستحقة بترتيب أقدمية واضح.
- كل قرار workload budget يسجل في audit ويدخل في evidence pack.
- schema evidence pack أصبح `adaptive-evidence-pack-1.4.0`.

## الاختبارات المضافة

```text
tests/test_adaptive_efficiency_v14.py
```

وتغطي:

- اختيار أقدم القرارات المستحقة في outcome sweep.
- تأجيل القرارات الحديثة وتوثيقها.
- حجب الأعمال الاختيارية عند نفاد workload budget.
- تضمين artifacts الجديدة داخل evidence pack والتحقق من schema `adaptive-evidence-pack-1.4.0`.

## نتيجة الاختبارات

```text
59 passed
```


# تقرير تنفيذ v1.5.0 — Runtime Conflict Planning & Evidence Digests

## هدف الجولة

رفع كفاءة التشغيل adaptive عبر منع تضارب أوامر Runtime قبل التنفيذ وتقليل كلفة مراجعة evidence packs عبر digest/checksum manifest خفيف. هذه الجولة لا تعدل معادلات Ψ، ولا تغير منطق `cgtlib`، ولا تنفذ أي mutation خارج `OperatingContract` و authorization gates.

## الإضافات

```text
processual_kernel/adaptive/efficiency.py
processual_kernel/adaptive_toolkit.py
processual_kernel/adaptive/ops_governance.py
processual_kernel/adaptive_types.py
```

أضيفت الأنواع:

```python
RuntimeCommandConflictPlan
AdaptiveEvidenceDigest
```

وأضيفت الواجهات:

```python
toolkit.runtime_command_conflict_plan(...)
toolkit.adaptive_evidence_digest(...)
```

## تحسينات الكفاءة

- منع تضارب أوامر Runtime mutating داخل نفس subject قبل الوصول إلى التنفيذ.
- إبقاء الإجراء الأعلى أولوية مثل `escalate` عند وجود أوامر متضاربة، وتأجيل الأوامر الأقل أولوية.
- إنشاء digest مستقر لحزمة الأدلة عبر checksums لكل artifact وchecksum للعدادات.
- تمكين المراجعة السريعة لحزم الأدلة قبل فتح artifacts الثقيلة.
- تضمين خطط التضارب والـ digests داخل evidence pack وداخل تقرير الكفاءة.

## ضمانات السلامة

- `RuntimeCommandConflictPlan` لا ينفذ الأوامر؛ هو تخطيط read-only فقط.
- تنفيذ Runtime الفعلي لا يزال خلف `authorize_adaptive_action` و `OperatingContract`.
- `AdaptiveEvidenceDigest` لا يحذف أو يضغط الأدلة الأصلية؛ هو manifest إضافي قابل للتحقق.
- كل artifact جديد يدخل في audit/store/evidence validation.
- schema evidence pack أصبح `adaptive-evidence-pack-1.5.0`.

## الاختبارات المضافة

```text
tests/test_adaptive_efficiency_v15.py
```

وتغطي:

- اختيار الأمر الأعلى أولوية عند تضارب أوامر Runtime mutating.
- ثبات digest لنفس evidence pack وتغيره عند تغير الأدلة.
- تضمين artifacts الجديدة داخل evidence pack والتحقق من schema `adaptive-evidence-pack-1.5.0`.

## نتيجة الاختبارات

```text
62 passed
```


# تقرير تنفيذ v1.6.0 — Runtime Throttling & Evidence Delta Review

## الهدف

رفع الكفاءة التشغيلية دون تغيير القلب الرياضي أو منطق `cgtlib`، عبر تقليل churn في أوامر runtime وتقليل كلفة مراجعة حزم الأدلة المتكررة.

## الإضافات

- إضافة `RuntimeCommandThrottlePlan` لمنع تتابع أوامر mutating متشابهة لنفس workflow/subject داخل نافذة cooldown.
- إضافة `toolkit.runtime_command_throttle_plan(...)` كخطة read-only قابلة للتدقيق.
- إضافة `throttle_cooldown_seconds` إلى `execute_checkpoint_recommendation(...)` ليصبح منع churn جزءًا من مسار التنفيذ الاختياري.
- حماية أوامر السلامة مثل `ESCALATE` و `FINALIZE` من throttling.
- إضافة `AdaptiveEvidenceDelta` للمقارنة بين digests وتحديد artifacts التي تغيّرت أو أضيفت أو حذفت.
- إضافة `toolkit.adaptive_evidence_delta(...)`.
- تضمين `runtime_throttles` و `evidence_deltas` داخل `AdaptiveEvidencePack`.
- تحديث schema إلى `adaptive-evidence-pack-1.8.0` و `adaptive-evidence-digest-1.8.0`.

## السلامة

- لا تعديل على معادلات Ψ.
- لا تعديل على `cgtlib`.
- throttling لا يطبّق على `ESCALATE` و `FINALIZE`.
- throttling لا يمنح صلاحية تنفيذ؛ التفويض والعقود البشرية تبقى قبل التنفيذ.
- evidence delta لا يحذف الأدلة الأصلية، بل يضيف مسار مراجعة أخف.

## الاختبارات

تمت إضافة `tests/test_adaptive_efficiency_v16.py` لتغطية:

- منع churn لأوامر mutating مع السماح بالتصعيد.
- احترام `execute_checkpoint_recommendation(...)` للـ throttling بعد التفويض.
- إنتاج evidence delta وتضمينه داخل evidence pack.

نتيجة الاختبارات النهائية:

```text
65 passed
```


# تقرير تنفيذ v1.7.0 — AES-256-GCM Report Encryption

## الهدف

رفع كفاءة وسلامة تسليم التقارير عبر إضافة تشفير AES-256-GCM لحزم الأدلة والتقارير الحساسة، مع بقاء التشفير خارج القلب الرياضي وخارج `cgtlib`.

## الإضافات

- إضافة `processual_kernel/adaptive/encryption.py`.
- إضافة `AdaptiveReportEncryptor`.
- إضافة `EncryptedAdaptiveReport` و `AdaptiveReportDecryptionResult`.
- إضافة واجهات:
  - `toolkit.generate_report_encryption_key()`
  - `toolkit.encrypt_adaptive_report(...)`
  - `toolkit.decrypt_adaptive_report(...)`
  - `toolkit.build_encrypted_adaptive_evidence_pack(...)`
- استخدام AES-256-GCM بمفتاح 256-bit و nonce بطول 96-bit لكل تقرير.
- ربط التشفير بـ AAD يشمل `workflow_id`, `report_kind`, `key_id`, ونسخة schema الأصلية.
- عدم حفظ مفتاح التشفير في audit أو evidence pack.
- تضمين encrypted report envelopes داخل evidence pack عبر `encrypted_reports`.
- إضافة `cryptography>=41` إلى dependencies.
- تحديث schema إلى:
  - `adaptive-evidence-pack-1.8.0`
  - `adaptive-evidence-digest-1.8.0`
  - `adaptive-evidence-delta-1.8.0`
  - `adaptive-report-encryption-1.8.0`
  - `adaptive-report-decryption-1.8.0`

## السلامة

- لا تعديل على معادلات Ψ.
- لا تعديل على `cgtlib`.
- لا تنفيذ adaptive جديد بسبب التشفير؛ التشفير يحمي التقارير فقط.
- المفاتيح تُدار خارجيًا ولا تُضمّن في الحزمة أو الأدلة.
- AES-GCM يرفض ciphertext معدّلًا أو مفتاحًا خاطئًا عبر authentication failure.
- نتيجة فك التشفير لا تُخزّن كـ plaintext داخل audit/store؛ يتم تسجيل metadata فقط.

## الاختبارات

تمت إضافة `tests/test_adaptive_report_encryption_v17.py` لتغطية:

- تشفير وفك تشفير evidence pack بنجاح.
- رفض مفتاح خاطئ أو ciphertext معدّل.
- رفض المفاتيح غير 256-bit.
- تضمين encrypted report metadata داخل evidence pack دون حفظ المفتاح.

نتيجة الاختبارات النهائية:

```text
68 passed
```


# تقرير تنفيذ v1.8.0 — HTML Review UI & Encrypted Report Indexes

## الهدف

رفع كفاءة مراجعة تقارير Adaptive Governance عبر واجهة HTML مستقلة وفهارس خفيفة للتقارير المشفّرة، دون فك تشفير التقارير ودون تخزين أو عرض مفاتيح AES.

## الإضافات

- إضافة `AdaptiveEncryptedReportIndex` لفهرسة التقارير المشفّرة عبر `report_kind`, `key_id`, و `ciphertext_sha256` فقط.
- إضافة `AdaptiveUiSnapshot` لتجهيز ملخص آمن للواجهة.
- إضافة `processual_kernel/adaptive/ui.py`.
- إضافة HTML مستقل في `ui/maestro_adaptive_dashboard_v1.8.0.html`.
- إضافة واجهات Toolkit لتوليد snapshot وHTML.
- تحديث evidence pack ليحمل `encrypted_report_indexes` و `ui_snapshots`.
- تحديث schema إلى 1.8.0 لمسارات evidence/report review.

## السلامة

- لا تعديل على معادلات Ψ.
- لا تعديل على `cgtlib`.
- الواجهة لا تطلب مفاتيح AES ولا تفك تشفير التقارير.
- الفهارس لا تحتوي raw keys ولا plaintext.
- UI snapshot يعرض counts/status/checksums/recommendations فقط.

## الاختبارات

تمت إضافة `tests/test_adaptive_ui_efficiency_v18.py` لتغطية:

- توليد فهرس تقارير مشفّرة آمن وخفيف.
- تضمين الفهارس وUI snapshots داخل evidence pack.
- توليد HTML مستقل للمراجعة دون كشف `ciphertext_b64` أو المفاتيح.

نتيجة الاختبارات النهائية:

```text
70 passed
```
