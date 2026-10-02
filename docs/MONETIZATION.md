# Monetization

## The decision

**GitHub Sponsors from launch. MIT for the software. Paid enterprise support and
a signed manifest, sold, only when someone asks.**

No hosted execution. No account. No telemetry. The gate is a local process the
user can read, and keeping it that way is what makes the licence and the
business the same decision rather than two.

One exception, and it is narrow. A static, read-only report of a single gate run
may be published at a public URL. It runs nothing, has no backend and takes no
input. It renders a JSON file that the publisher generated from their own local
run, with local paths removed and no telemetry of any kind. A visitor cannot
change a result, and the numbers are re-derivable by anyone who runs the gate
themselves.

## Why nothing is sold as a service

A hosted oracle would have to trust a remote measurement, and the entire value
of the product is that the measurement is locally re-derivable. Selling a
service that re-implements the gate would mean the consumer could no longer
verify the thing they bought. That is the failure mode this product was built
to prevent.

A published report is not that, which is why the exception above is not a walk
back of this paragraph. A hosted oracle replaces the local measurement with a
remote one you must trust. A published report is the local measurement, on a
page: it carries the per-run `seal` and the per-skill residuals, so a reader
checks it against a run they make themselves rather than taking it on faith. The
objection was never to having a URL. It was to the measurement leaving the
machine that made it.

It would also put a payment processor, a privacy policy, a data-retention
question and a compliance surface between the user and a Python script that
takes two seconds to run. For a solo operator that is a bad trade at any
revenue level below the point where a hosted version has a paying audience
large enough to matter.

## What is actually sold

| Offer | What it is | Why someone pays |
| --- | --- | --- |
| Sponsorship | Recurring support, no service attached | Keeps the traps and the ledger maintained as the instrument grows. |
| Maintained pin | A signed `ledger.json` manifest plus an upgrade commitment | Teams who cannot let a checksum drift silently on their own schedule. |
| Integration help | Porting a measured fact into another engine's rule system | The mapping is the hard part; the arithmetic is already in `references/`. |
| CI adoption | A workflow that runs the gate on every change, with a diff of residuals | A team that wants the gate to fail their build rather than their release. |

Everything on this list is a human decision plus a signature. None of it sits on
the measurement path, so a lapsed sponsorship can never change a result.

## Payment rails, if a rail is ever needed

Not wired, and deliberately so. Recorded here so the decision is made before
the first transaction rather than during it.

The choice is the **legal model**, not the brand:

- **Stripe** is a payment service provider. The seller is the operator, who
  then owns EU VAT and OSS filing. Lowest headline fee at 2.9% + $0.30, highest
  compliance cost.
- **Paddle and Lemon Squeezy** are merchants of record. They become the seller
  on the receipt and handle VAT, GST and invoicing. Roughly 5% + $0.50.

| stage | rail |
| --- | --- |
| sponsorship and one-off support | Lemon Squeezy |
| subscription past roughly $1k/month | Paddle |
| past roughly $10k/month, mostly US, or VAT already handled | Stripe |

Two cautions. Lemon Squeezy was acquired by Stripe in July 2024, which is good
for reliability. Paddle reportedly adds a currency-conversion margin on
international payouts, putting the effective rate nearer 7-8% on global sales.
And Stripe-only from day one carries a real compliance cost that has been
estimated in the range of $5,000 to $20,000 a year in accountant plus tax
software — which is why a merchant of record is the right starting point for a
one-person operation.

## What is not claimed

No passive revenue. No "it runs while you sleep". Sponsorship is a person
choosing to fund maintenance, and it stops the day they stop. Any statement
about income from this repository needs a date and a source.

The published report page is not an offer and earns nothing. It carries no
advertising and no tracking, so it does not change any figure on this page.
