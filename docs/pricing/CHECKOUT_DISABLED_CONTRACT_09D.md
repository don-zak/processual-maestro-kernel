# PRICING-CHECKOUT-09D — Checkout-Disabled Approval Contract

Status: `draft_review`.
Checkout approved: `false`.
Public pricing approved: `false`.
Currency approved: `false`.
Tax treatment approved: `false`.
Merchant of Record approved: `false`.
Lemon Squeezy wiring approved: `false`.

This document defines the internal checkout-disabled contract for future approval
work. It does not enable checkout, does not approve public pricing, does not approve
currency, does not approve tax handling, does not approve Merchant of Record
treatment, and does not authorize payment provider wiring.

## 1. Contract purpose

The purpose of 09D is to describe what a future checkout implementation must require
before any self-service payment path can be introduced.

This contract is intentionally disabled. It is a readiness checklist and approval
boundary, not a payment implementation.

## 2. Non-activation guardrails

Until a later approval phase is completed:

- checkout remains disabled;
- public pricing remains unapproved;
- currency remains unapproved;
- tax treatment remains unapproved;
- Merchant of Record treatment remains unapproved;
- Lemon Squeezy wiring remains unapproved;
- payment provider identifiers remain forbidden;
- real payment sessions remain forbidden;
- public self-service payment remains forbidden;
- subscription activation from payment remains forbidden;
- automatic paid trial conversion remains forbidden;
- production payment webhook handling remains forbidden.

## 3. Forbidden implementation work in 09D

The 09D phase must not add:

- payment provider identifiers;
- provider-specific product identifiers;
- provider-specific price identifiers;
- provider-specific checkout links;
- provider-specific webhook secrets;
- real payment sessions;
- real checkout routes;
- real subscription activation from payment;
- public price-book approval;
- final public pricing;
- approved currency values;
- approved tax logic;
- public self-service purchase buttons.

If any of these items are needed, they must wait for a later approval phase.

## 4. Required future approval inputs

Before checkout can move from disabled to approval-ready, the following decisions must
be completed:

- approved public offer names;
- approved public price book;
- approved price for each public offer;
- approved currency;
- approved tax-inclusive or tax-exclusive wording;
- approved Merchant of Record model;
- approved refund policy;
- approved paid trial policy;
- approved subscription renewal behavior;
- approved cancellation behavior;
- approved invoice wording;
- approved support boundaries;
- approved usage limits;
- approved overage or no-overage policy;
- approved rollover or no-rollover policy;
- approved Enterprise review boundary;
- approved telecom-grade integration exclusion;
- approved public legal terms.

## 5. Future checkout contract fields

A later approval phase may define a checkout contract with the following neutral
fields:

| Field | Purpose | Approval requirement |
| --- | --- | --- |
| offer_code | Stable internal offer reference | Must map to an approved public offer. |
| offer_name | Public-facing approved offer name | Must be approved before publication. |
| billing_period | Monthly, annual, trial, or custom | Must match commercial terms. |
| approved_price | Public approved price | Must not exist before approval. |
| approved_currency | Public approved currency | Must not exist before approval. |
| tax_mode | Tax-inclusive, tax-exclusive, or MoR-managed | Must be approved before checkout. |
| refund_policy_code | Approved refund policy reference | Must map to approved wording. |
| trial_policy_code | Approved trial behavior reference | Must map to approved terms. |
| renewal_behavior | Manual, automatic, or custom | Must be approved before payment. |
| cancellation_behavior | Cancellation handling | Must be approved before payment. |
| enterprise_review_required | Enterprise/custom path gate | Must protect custom offers. |
| integration_scope_required | Integration scoping gate | Must protect production integrations. |
| checkout_enabled | Final activation flag | Must remain false until approval. |

These fields are intentionally neutral and do not bind the project to a payment
provider.

## 6. Checkout-disabled behavior expectations

While checkout remains disabled, public surfaces may show review-safe information only:

- offers may be marked as pending review;
- checkout calls must not be available;
- purchase buttons must not create payment sessions;
- paid trial wording must not imply automatic activation;
- Enterprise must remain contact, review, and scoping based;
- telecom-grade integration must remain separately scoped;
- the pricing page must not render internal consultation prices;
- the pricing page must not render provider payment identifiers.

## 7. Safe future route expectations

If checkout routes are introduced later, the first approval-ready version should start
disabled and should return an explicit disabled response until public approval is
complete.

A safe disabled response should communicate:

- checkout is not enabled;
- the offer is still under review;
- payment is not being collected;
- the customer should request access or contact the team;
- Enterprise and telecom-grade integration require review.

The disabled route should not create payment sessions or activate subscriptions.

## 8. Approval gate for PRICING-APPROVAL-10A

The next approval phase can only begin after the team confirms:

- final public offers;
- final prices;
- final currency;
- final tax treatment;
- final Merchant of Record model;
- final refund policy;
- final paid trial behavior;
- final renewal behavior;
- final cancellation behavior;
- final support limits;
- final usage limits;
- final Enterprise review rules;
- final telecom-grade integration exclusion;
- final public terms;
- final payment provider decision.

Without these decisions, checkout must remain disabled.

## 9. Publication restrictions

This document must not be used as:

- public pricing approval;
- checkout approval;
- payment provider approval;
- Lemon Squeezy configuration;
- tax approval;
- Merchant of Record approval;
- public refund approval;
- public terms approval;
- subscription activation approval;
- paid trial conversion approval.

Public checkout can only be introduced after a later approval phase explicitly
approves pricing, currency, taxes, Merchant of Record treatment, refund wording,
support limits, usage limits, paid trial behavior, cancellation behavior, payment
provider wiring, and checkout behavior.
