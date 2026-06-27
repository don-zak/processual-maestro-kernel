# تقرير تطوير CGT v2 داخل Processual Maestro Kernel

## الهدف

نقل البرنامج من نواة CGT الانتقالية القديمة إلى طبقة CGT المطوّرة التي تضيف:

1. الاعتداد الوجودي: الأصل، الحامل، الأثر.
2. الممكن المقيد: القيد بوصفه شرط الممكن.
3. رافعة التدافع الديناميكية.
4. متجه المصير: الاستقرار، الهجنة، التشوّه، الاندثار، الانهيار، الازدهار.
5. مراتب الوجود: مزدهر، مستقر، هجين، مشوّه، عابر، مندثر.
6. إدخال مراتب المصير في تقارير CGT وقرارات الحوكمة دون كسر التوافق الخلفي.

## الملفات الجديدة

- `cgtlib/existence.py`
- `cgtlib/possibility.py`
- `cgtlib/lift.py`
- `cgtlib/fate.py`
- `tests/test_cgt_fate_layer.py`
- `tests/test_processual_cgt_bridge_v2.py`

## الملفات المعدلة

- `cgtlib/types.py`
- `cgtlib/evaluators.py`
- `cgtlib/invariants.py`
- `cgtlib/api.py`
- `cgtlib/__init__.py`
- `cgtlib/metadata.py`
- `processual_kernel/cgt_bridge.py`
- `processual_kernel/governor.py`
- `pyproject.toml`
- `TEST_RESULTS.txt`
- `RUN_RESULTS.txt`

## الصياغة الحسابية المضافة

### الاعتداد الوجودي

```math
\mathcal{E}_x = \sigma(a_O O_x + a_C C_x + a_A A_x - \Theta_E)
```

مع القاعدة الحدية:

```math
O_x=0,\ C_x=0,\ A_x=0 \Rightarrow \mathcal{E}_x=0
```

### الممكن المقيد

```math
P_x^{CGT}=P_x^{raw} Q_x C_x
```

### رافعة التدافع

```math
L(t)=\chi\tau(t)I(t)C(t)(1-Ov(t))
```

### متجه المصير

```math
\mathcal{F}_{\alpha\to\beta}=(S,Y,D,E,C,B)
```

حيث:

- `S`: الاستقرار.
- `Y`: الهجنة.
- `D`: التشوّه.
- `E`: الاندثار.
- `C`: الانهيار.
- `B`: الازدهار.

## التوافق الخلفي

تمت إضافة الحقول الجديدة إلى `StructuralTransitionReport` كحقول اختيارية ذات قيم افتراضية، لذلك تبقى البنية القديمة صالحة:

- `transmissibility`
- `retention`
- `self_potential`
- `lock_state`
- `delay_gate`
- `compatibility`
- `transition_channel`
- `aftermath`

والحقول الجديدة:

- `existence`
- `possibility`
- `dynamic_lift`
- `fate_vector`
- `existence_rank`

## أثر التطوير على الحوكمة

أصبحت الحوكمة تستفيد من `existence_rank` و `fate_vector`:

- `flourishing/stable`: ثقة أعلى في الاستعمال وإعادة التوظيف.
- `hybrid`: مراقبة وتدافع/مكوث بدل الإغلاق المبكر.
- `distorted`: إصلاح أو تبسيط قبل إعادة الاستخدام.
- `extinct`: أرشفة أو قطع مسار لا يملك حاملًا/أثرًا كافيًا.

## نتائج الاختبار

الأمر المستخدم:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
```

النتيجة:

```text
78 passed in 3.55s
```

## نتائج أمثلة التشغيل

تم تشغيل:

```bash
PYTHONDONTWRITEBYTECODE=1 python examples/basic_usage.py
PYTHONDONTWRITEBYTECODE=1 python examples/maestro_workflow.py
PYTHONDONTWRITEBYTECODE=1 python examples/adaptive_usage.py
```

والنتيجة: جميع الأمثلة اكتملت بنجاح.

## ملاحظة تسليم

تم تنظيف مجلدات التخزين المؤقت قبل التغليف النهائي، بما في ذلك:

- `__pycache__`
- `.pytest_cache`
- ملفات `.pyc`
