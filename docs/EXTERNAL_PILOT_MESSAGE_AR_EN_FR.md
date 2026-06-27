# External Pilot Message / رسالة عرض فترة اختبار / Message de proposition de pilote

## العربية

**الموضوع: مقترح فترة اختبار محدودة لبرنامج Processual Maestro Kernel v2.0.0**

السلام عليكم،

نقترح عليكم الاطلاع على برنامج **Processual Maestro Kernel v2.0.0**، وهو نواة تجريب وحوكمة لمزودي الذكاء الاصطناعي المتعددين، موجهة لاختبار ومقارنة مخرجات نماذج اللغة الكبيرة LLM عبر مؤشرات قابلة للمراجعة مثل:

* score
* rank
* reward
* policy
* fate_vector

لا يقتصر البرنامج على إرسال الطلبات إلى مزود واحد، بل يعمل كطبقة وسيطة تسمح بتجربة عدة مزودين، مقارنة نتائجهم، وتوليد تقارير تقنية بصيغ JSON و Markdown يمكن اعتمادها في التقييم والمراجعة.

نقترح فترة اختبار محدودة من **14 إلى 30 يومًا** تشمل:

* تشغيل نسخة تجريبية محلية أو عبر Docker.
* اختبار endpoint الخاص بحالة المزودين.
* اختبار endpoint الخاص بالمقارنة والحوكمة.
* تنفيذ مجموعة مهام واقعية مختارة من طرفكم.
* تقييم قدرة النظام على مقارنة مزود محلي مثل Ollama/OpenCode مع مزود خارجي مثل OpenRouter أو غيره.
* تسليم تقرير نتائج في نهاية الفترة التجريبية.

يمكن تنفيذ التجربة دون مشاركة أي مفاتيح API خاصة بنا. وفي حال رغبتكم في اختبار مزودين تجاريين مثل OpenAI أو Gemini أو Anthropic أو DeepSeek، يمكن استعمال مفاتيح اختبار مخصصة من طرفكم، أو الاكتفاء بتشغيل مزود محلي ومزود خارجي مجاني أو محدود.

الهدف من هذه الفترة هو التحقق من قابلية البرنامج للاستعمال في بيئة تقنية حقيقية، وقياس فائدته في حوكمة مخرجات الذكاء الاصطناعي، مقارنة المزودين، وتتبع جودة النتائج عبر مؤشرات واضحة وقابلة للتوثيق.

يسعدنا تزويدكم بحزمة العرض التقنية والوثائق المختصرة للبدء في التقييم.

مع خالص التحية.

---

## English

**Subject: Proposal for a Limited Pilot of Processual Maestro Kernel v2.0.0**

Dear Sir/Madam,

We would like to introduce **Processual Maestro Kernel v2.0.0**, an experimental governance kernel for multi-provider artificial intelligence systems. It is designed to test, compare, and evaluate the outputs of large language model providers through reviewable indicators such as:

* score
* rank
* reward
* policy
* fate_vector

The system is not limited to sending prompts to a single provider. Instead, it acts as an intermediate governance layer that allows multiple providers to be tested, compared, and evaluated through structured JSON and Markdown reports.

We propose a limited pilot period of **14 to 30 days**, including:

* Running a local or Docker-based test instance.
* Testing the provider status endpoint.
* Testing the comparison and governance endpoint.
* Running a set of realistic tasks selected by your technical team.
* Comparing a local provider such as Ollama/OpenCode with an external provider such as OpenRouter or another compatible provider.
* Delivering a final technical report at the end of the pilot period.

The pilot can be conducted without sharing any of our private API keys. If you would like to test commercial providers such as OpenAI, Gemini, Anthropic, or DeepSeek, dedicated test keys may be provided by your side, or the pilot may be limited to a local provider and an external free or limited provider.

The purpose of the pilot is to assess the system’s practical value in a real technical environment, especially for AI output governance, provider comparison, quality tracking, and auditable reporting.

We would be pleased to provide the technical presentation package and short documentation required to begin the evaluation.

Kind regards.

---

## Français

**Objet : Proposition d’une période pilote limitée pour Processual Maestro Kernel v2.0.0**

Madame, Monsieur,

Nous souhaitons vous présenter **Processual Maestro Kernel v2.0.0**, un noyau expérimental de gouvernance pour systèmes d’intelligence artificielle multi-fournisseurs. Il est conçu pour tester, comparer et évaluer les sorties de différents fournisseurs de modèles de langage LLM à travers des indicateurs vérifiables tels que :

* score
* rank
* reward
* policy
* fate_vector

Le programme ne se limite pas à envoyer des requêtes à un seul fournisseur. Il agit comme une couche intermédiaire de gouvernance permettant de tester plusieurs fournisseurs, de comparer leurs résultats et de produire des rapports techniques structurés aux formats JSON et Markdown.

Nous proposons une période pilote limitée de **14 à 30 jours**, comprenant :

* Le déploiement d’une instance de test locale ou via Docker.
* Le test de l’endpoint relatif à l’état des fournisseurs.
* Le test de l’endpoint de comparaison et de gouvernance.
* L’exécution d’un ensemble de tâches réalistes choisies par votre équipe technique.
* La comparaison d’un fournisseur local comme Ollama/OpenCode avec un fournisseur externe comme OpenRouter ou tout autre fournisseur compatible.
* La remise d’un rapport technique final à la fin de la période pilote.

Cette expérimentation peut être réalisée sans partager nos clés API privées. Si vous souhaitez tester des fournisseurs commerciaux tels qu’OpenAI, Gemini, Anthropic ou DeepSeek, des clés de test dédiées peuvent être fournies par votre côté, ou bien le pilote peut se limiter à un fournisseur local et à un fournisseur externe gratuit ou limité.

L’objectif de cette période pilote est d’évaluer l’intérêt pratique du système dans un environnement technique réel, notamment pour la gouvernance des sorties d’IA, la comparaison des fournisseurs, le suivi de la qualité et la production de rapports auditables.

Nous serions ravis de vous fournir le dossier de présentation technique ainsi que la documentation synthétique nécessaire pour démarrer l’évaluation.

Cordialement.
