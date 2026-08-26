# DGG Student Funding — where this project stands

Written for whoever picks this up next, human or otherwise. It covers what the
system is, what was done to it and why, what works today, and what is still
open. Where a decision looks odd, the reason is given: most of them were made
because the obvious alternative had already caused a bug.

Last updated: 26 August 2026.

---

## 1. What this is

A funding portal for the Délı̨nę Got'ı̨nę Government Education Department. Students
apply for post-secondary funding, staff review it, a director decides, finance
pays it. Money comes from three streams:

| Stream | What it is |
|---|---|
| **PSSSP** | Federal C-DFN programme. Tuition and living allowance. |
| **UCEPP** | Federal C-DFN programme, for upgrading programmes. Has rates and rules; nothing assigns it automatically. |
| **DGGR** | The government's own bursary funds. Tops up rather than replaces. |

Every rate now comes from the DGG Bursary & Awards Program Procedure. The figures
seeded during the rebuild were placeholders and are gone; §7–§9 of the policy is
the source, and `funding/migrations/0013_policy_rates.py` moves an existing
database onto them with a `PolicyChange` per edit.

Ten application types, from the admission application through to a graduation
bursary. Internally they were once "Form A" through "Form H"; those letters are
gone from the code and survive only as comments explaining what a type used to
be called.

**Stack.** Django 5.2 + DRF + SimpleJWT on the backend; React 19 + Vite 8 +
react-router 7 on the frontend. SQLite locally. No ORM-level multi-tenancy, no
Celery, no Redis — an outbox table and a management command do the queueing.

---

## 2. History: the rebuild

The original system was roughly 18,000 lines carrying an admin component of
6,966 lines that held 94 pieces of state and polled seven endpoints every
thirty seconds. Its central problem was that **a field's identity was its
display string**: the React form mapped state onto labels, those became
`FormField` rows, and award calculation resolved them back by substring
matching. Renaming a label could change what a student was paid.

The owner's instruction was not to improve it but to replace it — *"if you are
trying to make the mud beautiful you will also be raped by mud"* — and to
discard the existing database rather than migrate it.

What replaced it:

- **23 models → 8.** One `Application` with a `type`, not nine Form* variants.
- **Typed schemas in code** (`backend/funding/schemas/`), not EAV rows. One
  definition drives API validation, the rendered form, the printable form and
  the generated TypeScript types.
- **A rules engine** (`backend/funding/rules/`) with a closed predicate language
  and a closed set of effect calculators, versioned in `RuleSet`/`Rule` rows.
- **Immutable decisions.** `AwardDecision` supersedes rather than overwrites, so
  an appeal can be argued against the figures that were in force.
- **Event-sourced workflow.** Status is a fold over `ApplicationEvent`;
  `funding.services.workflow.record` is the only writer of the status column.

Net effect on the diff at the time of cut-over: 260 files, +14,038 / −30,721.

---

## 3. How it is arranged

```
backend/
  accounts/     users, roles, eligibility screening, staff administration
  funding/      the domain: applications, rules, decisions, policy, deadlines
    api/        views and serializers only — no business rules
    rules/      conditions, effects, engine
    schemas/    what each application type asks
    services/   where the rules actually live
  notifications/ outbound email queue and in-portal notices
  core/         settings, urls
src/
  api/          one client; schema.generated.ts is generated, never edited
  app/          shell, routes, icons
  components/   ui primitives and the one schema-driven form renderer
  features/     auth, dashboard, applications, review, enrolment, finance,
                policy, people, profile, notifications, forms
```

**The rule that keeps it honest:** business rules live in `services/` and
`rules/`. A view resolves permissions, calls a service and serialises the
result. When something important has gone wrong here, it was almost always
because a rule leaked into a component or a serializer.

---

## 4. What works today

Verified by 973 backend tests, 253 frontend tests, and the live audit scripts in
`backend/scripts/` that drive the running server over HTTP.

- **Registration** gated on the six-question eligibility screening, enforced
  server-side. Someone who qualifies for nothing is told so and cannot register.
  The streams they qualify for are now **saved on the account**
  (`User.eligible_streams`) rather than re-derived on every application — the
  SFA answer is part of the decision and no column records it, so recomputing
  from the two booleans silently gave a student on SFA their PSSSP back.
  **The six questions are fixed at the owner's request** (17 Aug 2026); see §8
  for what the policy would add and why it is not asked.
- **Applications** — schema-driven, one renderer for all ten types. The
  admission form is stepped into four pages; continuing funding into two
  (information review, then documents and declaration).
- **Documents** upload for real (PDF or photo, 10MB cap, allowlisted types,
  stored under a generated filename).
- **Form B (enrolment verification)** is generated from the application,
  pre-filled, and emailed to the registrar automatically. The application
  **cannot be forwarded or approved until it comes back confirmed** — tuition is
  funded against the registrar's figure, never the student's estimate. Both
  types that need one — the admission application and the continuing-funding
  renewal — now **ask the student who to send it to**, so it goes out on
  submission whatever the office already holds. The renewal used to carry the
  address at send time from the profile or an earlier application and asked for
  nothing; a student with neither was told their registrar had been contacted
  and nobody was (§5, §6).
- **Review → decision → pricing**, with a full trace of every rule considered.
- **Payment run** producing a CSV; the same money cannot be dispatched twice.
- **Policy rates** editable by admins, with history and a refusal to record a
  no-op change.
- **Guest applications** for the two one-off awards (practicum, graduation
  bursary) with no account at all.
- **Travel claims** are itemised: an expense breakdown of as many lines as the
  trip had, receipts attached as several files rather than one, and a total the
  server adds up from the lines. Three steps — student and travel, expenses and
  receipts, payment and declaration.
- **The office can correct a filed application.** An administrator — not the
  support workers who assess them — edits the answers from the application
  screen, says what they changed, and the applicant is told by email and in the
  portal. Refused once the application is decided: its answers are the record
  the decision was made from. The edit goes through the same schema and the
  same splitting of the SIN and banking as a submission.
- **Requests for more information** — a reviewer asks in their own words, the
  student is notified with a link, opens the application, corrects answers and
  attaches or replaces documents, and it goes back into the queue.
- **Documents can be opened** by the student they belong to and by the office,
  through a permission-checked endpoint rather than a guessable media path.
- **Help & FAQ** — how to reach the office, and the questions it is asked
  most. Served from the API and readable without signing in.
- **Email** through Hostinger SMTP, verified delivering to a real inbox.
- **Bank details** are asked for on the forms that need them and stored on the
  `BankAccount` record the payment run reads, never in `answers` (§5).
- **The annual report to the head department.** The office's own mock-up, built
  from the data: enrolment by semester split into university and college with
  trades and upgrading as subsets, graduate awards by residency and credential,
  the institutions and programmes attended, and a financial summary that
  reconciles — gross, repaid, net. Read by Finance, the Director and an
  administrator; downloadable as a PDF on the office letterhead. An
  administrator enters the costs the system cannot see.
- **The funding programme breakdown, and the programme filter.** Which of
  the three programmes paid for what, and a filter that narrows the whole
  screen — and the export with it — to one of them. **Counts and money are
  attributed differently, on purpose:** an application has one primary
  stream, but pricing draws on every stream the applicant qualifies for, so
  a DGGR top-up on a PSSSP application is spent from both. Money therefore
  follows the *rule* that paid it, which is exact for the seven tuition and
  living rules because each names one stream. The bursary, travel and
  scholarship rules name none; that money is reported under **Not tied to
  one programme** rather than pushed into a programme that did not pay it.
  The breakdown reconciles to the report net, and `report_audit.py` checks
  that it still does against a real database.
- **Approval letters.** The office supplied three templates — DGG-CDFN (PSSSP),
  DGG-UCEPP and DGGR-SFSP — and an approved application produces the letters it
  earns, in full: as a page in the portal, as a **PDF** to download or forward,
  and in the body of the approval email with the PDF attached. The letterhead is
  the office's own artwork.
- **A student profile** (`/profile`) holding four kinds of fact, saved
  separately: their own details; the six screening answers, which re-run the
  office's rule and re-decide the funding streams; where they study, which
  pre-fills every later form; and where they are paid, which goes to the same
  `BankAccount` record the payment run reads. The point of all of it is the next
  application: what is on the profile arrives already filled in, and every box
  stays editable. It also closes the renewal gap in §6 — a student whose
  admission was on paper can now put their registrar's address on file, so the
  enrolment request has somewhere to go.

---

## 5. Decisions that will look strange without the reason

**An administrator may decide without forwarding.** Deciding used to require
`FORWARDED` first. That was not a safeguard — the endpoint asks
`decides_applications`, which a support worker fails — it was a lie: the forward
tells the director an application is *waiting for them*, immediately before it
is decided without them. `APPROVED` and `DECLINED` now follow `UNDER_REVIEW`
directly, and the director is told either way. Approving straight from
`SUBMITTED` is still refused: §13 puts a support worker's review first.

**There is no separate book allowance.** §7(A) and §8(A) fund mandatory books
and supplies out of the same per-semester tuition cap as the tuition. A flat
$500 on top paid an award the policy does not describe, whether or not the cap
had already covered the books. The rule and its rate are gone.

**Travel is capped by dependants, not only by purpose.** §7(C): $2,000 a trip
without dependants, $3,500 with them. The rate key is
`max_{travel_purpose}_{dependants}`. 'Compassionate' travel was offered as a
choice and has no programme behind it — it resolved a rate key that does not
exist, so the claim priced at nothing and reported an unconfigured rate rather
than an ineligible purpose.

**The funding stream is never sent by the client.** It gates
`applies_to_streams` on the tuition and living-allowance rules, so it decides
what someone is paid. `funding/services/streams.py` reads the tags saved at
sign-up and withdraws the C-DFN streams if this term's SFA answer says so.
`Application.stream` is the *primary* stream — the one whose deadline the
submission is measured against; pricing draws on everything the applicant
qualifies for, via `rules/engine._streams_for`.

**The stream split counts applications and never money.** The office's home
screen divides the applications across the three pots. It could not divide the
money the same way: an `Award` line carries no stream, and it could not honestly
be given one, because `rules.engine._streams_for` gates a rule against *every*
stream the applicant qualifies for and DGGR tops up rather than replaces — so a
PSSSP application routinely carries DGGR money. Summing awards by
`Application.stream` would publish "DGGR $12,000" on a screen where that reads
as what DGGR paid. The primary stream is a fact about the application; it is not
an attribution of the money. Every stream has a row even at nought — a split
that omits the empty pots is a list of what happens to exist, and UCEPP being
nought is itself worth seeing, since nothing assigns it. A stored value outside
the three is carried under its own name rather than dropped, so the rows always
add up to the total beside them — and that row is deliberately *not* a link: the
queue filters on the choice set and answers 400 to anything else, so a link
would drop its filter and open every application in the office under a tile
reading four. The tiles are tested by clicking them and watching what the queue
asks the server, not by asserting an `href` exists, which is how a link that
opened a 401 page on every document survived 809 tests.

**The report never guesses what an institution is.** University against
college, and trades against upgrading, are asked of the *registrar* on the
enrolment verification — they are the institution and they know. Neither is
required: the registrar's answer governs tuition, and a confirmation that could
not be submitted because of a reporting question would hold up an award. An
enrolment nobody classified is counted and reported as **not classified**, with
the screen saying how many. The alternative was matching words in a typed
institution name, and "Northern Lights College" grants degrees — a report figure
decided by a display string, going to a funder.

**The enrolment total counts enrolments, not people.** The office's own table
adds its seasons — 20 + 5 + 40 + 30 = 95 — and its summary calls that "95
semester enrolments". Counting distinct students instead produced a total
*smaller* than the column above it, which on a report to a funder reads as an
arithmetic mistake. A student who studied in two semesters had two enrolments
and appears in both. The headcount behind them is still wanted, so it is
reported beside the table as `distinct_students` rather than hidden inside it.

**Trades and upgrading are subsets, not extra columns.** The office's own note
on its table. A total that added them reports more students than attended, and
the seeded data cannot show it because those columns are nought on every
enrolment confirmed before the question existed — so the guard is a unit test
that classifies applications itself, not the live audit.

**Every money figure on the report is gross, repaid and net.** The office asked
for something that reconciles against a financial statement, and a report that
only counts money leaving overstates the year. `AwardRepayment` records what
came back against the award it came from — never editing `Award.amount`, which
is what was decided and what an approval letter has already told the student
they were granted. The award is the record; the repayment sits beside it.

**A hand-entered cost is never mixed into a computed total.** Staff wages are
real and nothing here could know them, so the Director enters them —
`ReportedCost`, one figure per label per fiscal year, carrying who entered it.
The report shows direct funding, entered costs and the grand total as three
separate figures. Entering the same label again for the same year *corrects* it
rather than adding a second line: two staff-wage rows make a grand total that
depends on which the reader adds up. DRF's own unique-together validator had to
be turned off for that, because it refused the correction outright.

**An approval letter belongs to a programme, not to an application.** One
approval routinely earns two: DGGR tops up rather than replaces, so a student
funded under PSSSP with a DGGR top-up is owed the CDFN letter *and* the DGGR
letter — which is what the DGGR letter's own wording is for, "students who are
already in receipt of primary funding". Keying the letter on
`Application.stream` would have sent one letter naming a total that two
programmes paid. Which programme funded a line is read from the rule that
produced it, *in the rule set that priced it* — `psssp_living` names psssp — so
a letter reprinted next year still says what it said. A line nothing can
attribute (a hand-set award, whose rule code is `manual_N`) goes on the
application's primary stream, because dropping it would produce letters adding
up to less than the award. Only the six tuition and living rules name a single
stream; the bursary and travel rules name none, which is the same fact that
keeps the dashboard's stream split to counts.

**The letter follows the award, not the approval email.** It rides along with
the approval email in the ordinary case — price, then approve. Nothing in
`workflow.ALLOWED_ACTIONS` requires that order, though: the office may approve
and price afterwards, and on that path there was no award to describe when the
email went out and nothing ever sent one, so the student got no letter at all,
in silence. `record_decision` now sends it when a pricing lands on an
application already approved. The same call covers a re-pricing and a hand-set
breakdown: the figures on the letter the student is holding have changed, and a
superseded letter nobody corrects names money the office is no longer paying.
Pricing an application *nobody* has approved still sends nothing — a pricing is
not a promise.

**The letters are semester funding only.** All three templates are built around
program costs and a monthly allowance "for the [term]". A travel claim or a
graduation bursary has neither, and the office has supplied no template for
them, so those approvals produce no letter rather than a "Semester Stipend"
table listing somebody's graduation cheque. The endpoint answers 409 saying so.

**Every figure in a letter is the award's own, and every rate is read.** Nothing
in the letter service recomputes an amount — a letter disagreeing with the award
it describes would be the `awarded_total`/dashboard fault again, in a document
the office signs. The caps quoted in the CDFN footnote and the UCEPP amount cell
are `psssp_tuition.max_per_semester` and `ucepp_tuition.max_per_semester`, read
from the policy rates: a figure typed into the letter as well is a second copy
that can disagree, which is how a "$500 limit" on a screen came to sit beside a
$3,000 seeded rate. A missing rate drops the sentence rather than printing
$0.00 — a letter telling a student the cap on their funding is nothing.

**"Monthly Allowance" says the rate and the months.** The rule is
`rate_per_month`: the rate is monthly, the award line stored is `rate × months`,
so the cell could hold either figure and the word "Monthly" above a semester
total is exactly this project's recurring fault. It prints
"$1,700.00/month × 4 months" against the semester amount, and the office chose
that. The figures come from `Award.detail`, written by the effect as data —
reading them back out of the rule's explanation *sentence* would put a display
string in charge of what a letter says somebody is paid. A line priced before
that column existed, or set by hand, shows the amount alone rather than
inventing a rate.

**The three templates differ, and the differences are honoured.** The UCEPP
letter carries no total row; only the DGGR letter carries a date; CDFN and UCEPP
titles end "for the" and take the term, while the DGGR title is already a
sentence and does not — appending it read as "Top-Up Funds Fall 2026-2027". The
identifier is "Treaty #:" on two and "Beneficiary #:" on the third, printed
blank where the account has none, because the office writes it on by hand and a
letter with no line for it cannot be completed. Every one of these was wrong in
the first build and found by rendering a real letter in a browser beside the
office's PDF.

**The PDF is a renderer, not a second letter.** `services/letter_pdf` lays out
whatever `letters_for` returns and decides nothing about what a letter says. It
draws on the canvas directly rather than through platypus because the letter is
a fixed sequence of blocks under a letterhead, not a stream of content to flow.
reportlab and Pillow were already pinned dependencies; `pypdf` was added for the
tests, which read the finished document back rather than trusting it.

**A residency contradiction is flagged, in one direction only.** The office
reported it: a student said they do not live in the Northwest Territories and
then gave an address in the Northwest Territories, and nothing said so.
`residency_flag` had existed since the first migration with two readers — the
application screen and the dashboard's "needs a look" count — and **no writer at
all**, so the count could only ever be zero. It was listed as open because
implementing it needed a residency policy nobody had stated; the office has now
stated one, and `funding.services.residency` implements exactly that and no
more.

Only the reported direction. "Not yet — I am moving there" is one of the three
answers the screening offers, and somebody moving to the NWT who gives an NWT
address is describing the move rather than contradicting themselves; a blank
answer is not a denial either. The reverse — saying yes and giving an address
elsewhere — is deliberately **not** flagged: a student may be studying away or
give a parent's address, and a flag that fires on ordinary circumstances is a
queue nobody can clear, which is how this flag came to be ignored in the first
place. The province is matched whole rather than as a substring, because "nt"
sits inside Ontario, Kent and Vermont; the postal fallback covers X0E/X0G/X1A
and deliberately excludes X0A–X0C, which are Nunavut.

Re-decided rather than stamped once, unlike lateness: this is a statement about
the answers the application currently holds, so correcting the address clears
the flag and correcting it the other way raises one. Stamped at submission, when
a student provides information, and on an amendment — the last explicitly,
because an amendment is an event rather than a transition and does not pass
through `workflow.record`.

**A UCEPP semester is priced by three living-allowance rules at once.** Found
by rendering the UCEPP letter, which nothing had ever produced. An application
in the UCEPP stream pays `psssp_living` *and* `ucepp_living` *and* `dggr_living`
for the same four months — $4,800 + $2,800 + $2,800 on the seeded rates. The
tuition side is protected, because `remaining_tuition` is shared and decremented
so no two streams fund the same dollar; **living has no such guard**, and each
rule pays independently against the months.

This is pre-existing pricing, not a fault in the letters — `_streams_for` gates
on every stream the applicant qualifies for, and a beneficiary registered under
the Indian Act qualifies for PSSSP and DGGR whatever their application's stream
says. It is unreachable today because nothing assigns UCEPP; it becomes
reachable the moment the office assigns one by hand, which §8 says is the only
way UCEPP is meant to be used. The letters are what made it visible: three
letters, one semester, three living allowances, over the Director's signature.
**Not changed here** — what a student on an upgrading programme should be paid
is the office's decision, and §8 already lists UCEPP as open.

**The PDF ships its own font, and refuses without one.** reportlab's built-in
Times is Latin-1 and cannot encode a single one of the nine characters the
office's wording uses: the first working draft printed "Délı̨nę Got’ı̨nę" as
"Dél■■n■ Got’■■n■" on the government's own letterhead. The system fonts that do
cover it are Windows-only and not redistributable, so a Linux deployment would
have printed the boxes instead, silently. DejaVu Serif is shipped in
`funding/assets/fonts` under the Bitstream Vera licence, and `_register_fonts`
refuses — loudly, with the missing code points named — rather than falling back
to a built-in. Same rule as a missing rate: refuse, do not print nought.

*Text extraction cannot catch this.* With the built-in font the text layer is
still correct and a parser reads the place name back perfectly while the page
displays black squares, so the guard is structural: the finished document must
embed a DejaVu subset, and `letter_pdf.BODY` must not be a base-14 name. The
first sabotage of this passed, which is how the gap was found.

**The letterhead is one raster, not artwork drawn twice.** The crest and
wordmark are the office's SVG; the ribbon beside it is drawn to match the
supplied templates. Both are rasterised into a single 200dpi PNG used by the
PDF — a second hand-coded copy of the ribbon in reportlab bezier calls would be
artwork with two definitions, which is the drift this project keeps recording.

**The letters carry a posting address.** The office's templates have a blank
address block under the date, because these go out on paper as well as by email:
a letter with nowhere to write an address cannot go in a window envelope. Taken
from the application's own answers first and the account second — the address on
the form is the one the applicant gave for *this* application — and omitted
entirely rather than printed as empty rules when there is nothing on file.

**The letter is HTML the browser prints, and also a PDF.** Three renderers,
one letter: the portal page, the email body, and `letter_pdf`. None of them
composes anything — all three lay out the same dict from `letters_for`, so the
copy in somebody's inbox, the copy they print and the copy the office files
cannot say different things about what was awarded. The blank forms are still
printed by the browser rather than generated, because those are driven by the
schemas and a generator there *would* be a second description; a letter is a
fixed document the office signs and sends, which is not the same thing.

**An email address is required; a phone number is not.** Email is how every
notice this portal sends arrives — a decision, a request for more information, a
guest claim's reference number — so it is the one contact detail an application
cannot do without, and it is required on every form that asks for it. A phone
number is a second way of being reached, and requiring it turns a preference
into a refusal: `admission` and `graduation_bursary` both demanded one, and the
graduation award is claimed with **no account at all**, so somebody who would
rather be written to could not file it. Both are optional now.
`emergency_relief` is the single exception and stays required: it is same-day
hardship, the office may need to reach somebody today, and an email address is
not a way to do that. `test_schemas.ContactRulesTests` asserts the rule across
*every* schema and asserts the exception separately — a rule whose exception
nothing pins loses it the next time somebody applies the rule flat, and a test
naming only the two forms that were wrong passes the day a third is written.
Institution and registrar addresses are outside the rule: `registrar_email` is
required because it is where the enrolment request is sent, which has nothing to
do with reaching the applicant.

**SFA status is not stored on the person.** It changes every term. It lives in
each application's answers, and the forms whose award depends on it ask it
directly. The screening question of the same name is a different thing: it
decides what the account *qualifies* for, and the profile lets a student
re-answer it when their circumstances change.

**The enrolment profile pre-fills forms and is read by nothing that prices
one.** The previous system kept `institution`, `program` and
`enrollment_status` on the user, and award calculation fell back to them
whenever an answer was missing — so last year's facts priced this year's
application and nothing on any screen said so. `EnrolmentProfile` exists on the
condition that exactly one module reads it: `funding.services.prefill`, plus
`workflow.registrar_email_for`, which decides who is *asked* to confirm an
enrolment and not what the answer is worth. `test_profile.ProfileNeverPricesTests`
prices an application, rewrites the profile underneath it, re-prices, and also
scans `funding/` for any other reader — because a test that priced one
application proves one application.

**Every form that pays asks where to send it.** The rule used to be written as
"required on every form that collects it", and enforced by reading the five
forms that collected it. Three that pay money collected none at all and so were
never in scope: `continuing_funding` — tuition and a living allowance, every
semester — `academic_scholarship` and `hardship_bursary`. Nothing but a
filled-in banking section creates a `BankAccount`, so a student whose *first*
application was one of those three had no account, and every award on it was
priced, approved and then held out of the payment file reading "has no bank
account on file" — on a screen the applicant never sees. The office reported it
as the payment dashboard showing errors.

Two tests asserted the absence, both saying "this cannot be claimed without an
account, so finance already has somewhere to pay". A portal account is not a
`BankAccount`. That premise was never checked because every test and every audit
that touched those forms used a student who had already filed an admission
application — and an admission has always asked. Filing one as a freshly
registered student is what shows it, which is now what
`scripts/readiness_audit.py` does.

The rule is derived from the seeded rules rather than from a list kept by hand:
`test_schemas.BankingIsAskedWhereverMoneyIsPaidTests` reads
`seed_rules.RULES` for the types that produce money and demands banking on each,
so a rule added for a new type tomorrow fails until that form asks. A hand-kept
list of five is exactly what missed these three.

**An administrator can read a full SIN and a full bank account.**
`identifiers.reveal` was written in the first build with a reason argument, an
audit entry and unit tests — and **no endpoint**. From the portal the whole
number was unreadable by anybody, so an administrator doing the federal PSSSP
return, which is why the SIN is collected at all, saw `•••••996` and had no way
to see more. The same class as `residency_flag` and `ShareLink`: a capability
with no route in. It hid longer than those because a masked value looks like a
working screen rather than a missing one, and the detail screen said in so many
words that reading the full number was recorded — describing something that
could not be done.

`POST /api/applications/{id}/identifiers/`, administrators only. A POST because
reading writes an audit entry, and a GET that changes the record is one a
browser or a proxy may repeat by itself. Not `reviews_applications`, which
includes the support workers who assess applications; not finance, whose payment
file already carries the account they need.

The audit entry is kept and the typed justification is dropped. A box demanded
on every read is a box filled with a full stop, and what the log actually needs
is who read whose and when — which is written either way, one entry for the
identifier and a separate one for the banking, because a single entry covering
both cannot answer "who has seen this person's SIN". The detail endpoint still
masks both: returning them there would put a regulated number in every staff
response, every browser cache and every log, and would need an entry per page
view, which makes the log useless.

**Finance sees the account before releasing the money.** The payment run listed
student, application, what it covers and how much, and not one digit of where
the money was going — the account was in the dispatched CSV and nowhere else. So
checking a transit number against a student's file meant sending the batch
first, and every award in a sent batch is marked PAID and drops off the run: the
check could only be made after it was too late to act on. The row now carries
the holder, the transit and institution numbers, and the account masked to the
last four. Masked, because this screen lists everybody waiting to be paid; the
file the bank acts on still carries the whole number, and
`test_finance.WhatFinanceSeesBeforeReleasingMoneyTests` asserts the screen and
the file describe the same account.

**The renewal asks who its registrar is, and no longer infers one.** This
reverses an earlier decision on purpose, so both halves are recorded.
`continuing_funding` used not to ask: the address was resolved at send time from
the student's profile, then from the most recent earlier application that
carried one, and the reasoning was that retyping it every semester is how a typo
reaches an institution. That is a real risk and it was the wrong trade. What it
missed is the student with nothing to carry — a first renewal in the portal, an
admission taken on paper, a profile never opened. For them the request was
skipped **in silence**, while the form's own summary said "we ask your registrar
to confirm your enrolment"; tuition is funded against the registrar's figure, so
the application could then never be priced for tuition by anybody, and no screen
said why. Twice now that has reached the office as a live fault, and each fix
addressed a different route in (staff can issue by hand; the profile can hold an
address) without closing the hole itself.

The typo risk is answered by pre-filling rather than by not asking:
`prefill.FROM_PROFILE` already offered `registrar_email`, and
`FROM_EARLIER_APPLICATIONS` now does too, so a returning student confirms what
is on file exactly as they do for their institution and programme. It is
required, for the same reason it is required on the admission application.

`workflow.registrar_email_for` is unchanged and its fallbacks are not dead: they
serve applications filed before this change, the preview endpoint's half-filled
draft, and staff reissuing against an address that bounced. Migration 0016
writes the address that *would* have been used onto renewals already in a
database — without it, `amend` re-cleans the whole answer set and an
administrator opening an older renewal is told the registrar email is missing on
a question the student was never asked.

**A student may re-answer the screening; they may not write the outcome.**
`PUT /api/me/eligibility/` takes the six answers and runs
`eligibility.assess` — the streams that come back are the office's rule applied
to them. The two eligibility booleans became read-only on `/api/me/` in the same
change: `streams.saved_streams` falls back to them, so a student who could PATCH
`is_indian_act_registered` could hand themselves PSSSP without the screening
ever running. Every re-answer writes an `AuditEntry`, because these are six
answers that decide what a person is paid, edited by the person being paid.

**An outcome of "nothing" is saved rather than refused.** It is tempting to
refuse it — an account with no streams cannot file anything — but the
circumstance it usually describes is real: a student has started receiving SFA,
which withdraws both C-DFN streams. Refusing to record that leaves the portal
funding somebody under a stream they have told us they no longer hold. They are
shown the screening's own words and pointed at the office.

**An empty box means "nothing on file", whatever kind of box it is.** The
profile posts every field in a section, filled or not, so a DRF DateField or
IntegerField meeting `''` refused a save on boxes the student never typed in.
`BlankMeansNothingOnFile` derives the rule from the field type — a date or a
count added tomorrow behaves the same way — and both serializers behind the
screen share it. Names are the deliberate exception: a person must have one.

**A screening answer has to be one the question offered.** `_yes` reads anything
it does not recognise as a no, so an unoffered value decided a funding stream by
falling through a comparison. `eligibility.unrecognised_answers` is checked at
both doors — registration and the profile — because a rule enforced at one of
two entrances is not enforced.

**An empty `eligible_streams` is only a missing answer when nobody has ever
answered.** The fallback to the two booleans used to fire on any account with no
tags, which was safe while the only way to have none was to predate them. Once a
student could re-answer the screening it was not: somebody who had just told us
they no longer qualify was handed PSSSP straight back, which is the fault
`eligible_streams` was added to stop, arriving from the other direction.
`eligibility_assessed_at` is what now separates "screened, and the answer is
nothing" from "never screened".

**The banking shapes the forms promise are enforced on the profile and only
logged on a form.** `schemas.common.banking` has always said "Five digits",
"Three digits", "Seven to twelve digits" in its help text and nothing checked
it. `banking.unpayable_reasons` is the one definition, with two deliberately
different manners: the profile screen refuses, because it exists to get the
account right and a student looking at the boxes is the cheapest moment to fix a
transposed digit; `banking.record` only warns, because a submitted application
must never be lost to a bad account number — `finance.preview` already reports
an award that cannot be paid.

**The SIN never enters `answers`.** `Application.answers` is returned whole by
the detail endpoint, printed on the paper form, and used to pre-fill the
registrar's copy. The SIN is split off at validation, encrypted with Fernet and
written to `ApplicantIdentifier`; clients get `•••••996`. Reading the whole
number is a separate call requiring a reason, which writes an audit entry first.
**A deployed process refuses to start without `FIELD_ENCRYPTION_KEY`** rather
than deriving one from `SECRET_KEY` — rotating `SECRET_KEY` would otherwise make
every stored number unreadable.

**Bank details leave `answers` the same way the SIN does.** The four banking
fields are still asked on the forms; they are marked `private=True` in the
schema, split off at validation by `Schema.split_private()` and routed by
`funding/services/banking.py` — to the student's `BankAccount` when there is an
account behind the application, or encrypted against the application as an
`ApplicantIdentifier` when it is a guest submission, where `banking.promote()`
picks them up if the office later attaches it. Staff see `••••3210` on the
detail screen, not the number. `manage.py purge_banking_answers` moved the 47
older rows that still carried the details; run it against any database filled
before this change.

**A required boolean and a declaration are different types.** A `BOOLEAN` field
answered "no" is a valid answer; a signed declaration answered "no" is not. A
required `BOOLEAN` used to accept `False` server-side, so an application could
be filed with its declaration refused. `FieldType.CONFIRM` rejects anything but
a positive confirmation.

**Nothing sits above a form but the form.** Step headings, blurbs and section
headings restated each other three times over. The step title carries the
context; a section heading appears only when a step has more than one section.
The screenshots the office supplies are rough sketches of *content*, not
designs to reproduce.

**Approved applications offer no action.** "Send to finance" only recorded a
transition — it looked like it paid someone and did not, while moving the
application past the status the payment run selected on. The run records that
transition itself when the batch goes out.

**Lateness is decided once, at submission.** Editing a deadline afterwards must
not make a filed application retroactively late; an appeal argues against the
date that was in force.

**A travel claim's total is never asked for.** `travel_assistance` pays
`amount_requested` up to the cap for the purpose of travel, so it is the figure
that gets paid. Asked alongside the expense lines it can disagree with them, and
the amount paid is then one that nothing on the form itemises. It is a
`computed` field: `schemas/travel.total_claimed` adds up the lines, a value
submitted for it is discarded before validation rather than refused, and the
form never renders an input for it. Two field types exist for this form —
`FieldType.TABLE` (rows of the same few questions, each cell cleaned by an
ordinary `Field`) and `FieldType.FILES` (several documents answering one
question, stored as a list of the same `document:N` references a single `FILE`
stores one of).

**A filed application has exactly one write, and it is named.** `revise` — the
student it belongs to, only while the status is `info_requested`, validated by
the same schema as the original. Opening `IsStaffOrOwner` by *method* instead
would have handed a student `transition` and `price` on their own application:
approving their own funding and setting the amount. It is opened by action name
for that reason, and `test_more_information.OwnerPermissionTests` tests that
layer directly — the outcome alone is guarded twice, so a test watching only the
outcome passes whether or not the permission does anything.

**A revision is the whole answer set, not a patch.** A partial update needs a
second, weaker notion of "complete", and the weaker one is always the one that
lets something through. Private answers are split off exactly as on submission,
so a corrected bank account does not land in `answers`.

**Documents are served by Django, not linked at MEDIA_URL.** The stored name is
a uuid, so a link is hard to guess — but hard to guess is not a permission
check. A stranger gets 404 rather than 403: that a document exists is itself
something they should not learn.

**Every sum over awards says which decision it means.** `Award.objects.current()`
scopes to the decision in force; `Award.objects.paid()` deliberately does not,
because a payment made under a decision since superseded still happened.
Reaching for `Award.objects` directly in anything that totals money is the bug
this exists to stop. An award with no decision behind it is *reported as
blocked* by the payment run rather than filtered out — nothing creates one, but
that is a reason to expect none, not a reason to let money vanish quietly.
`manage.py check_awards` says whether a given database was affected.

**The help page is public, and its contents come from the server.** The people
who most need a phone number are the ones who cannot sign in, so a help page
behind a login is help for everybody except them. The contact details are
settings (`SUPPORT_EMAIL`, `SUPPORT_PHONE`, `SUPPORT_ADDRESS`) so a deployment
can correct an address without a release; the questions live in `core/support.py`
and can move to a table the day the office wants to edit them itself. The
answers are asserted against what the portal actually does — an answer
describing an intention sends somebody to wait for an email that is not coming.
When the request fails the page still prints the mailing address, because that
is the one thing it exists to provide.

**The hardship bursary's cap is not printed on its form.** The office's screen
says "$500 limit" in two places; the seeded rate says $3,000. The cap is a
policy rate it edits without a deploy, so the figure lives there and nowhere
else — a number in two places is a number that can disagree, which is how a
display string came to decide what somebody was paid. Same reason the
scholarship's award amounts are absent from its form. See §8.

**Two attestations, both `CONFIRM`.** The hardship form asks the applicant to
confirm they are still active in their programme before describing anything, and
again that the information is accurate. Neither is a `BOOLEAN`: a required
boolean accepts False, so "no, I am not active in my programme" would file.

**Steps and sections are checked against each other.** `generate_types` emits
`APPLICATION_SECTIONS`, and `features/applications/Steps.test.tsx` asserts every
step names a section the schema declares *and* that no section is left unnamed.
An unnamed section is not rendered at all — its questions leave the form in
silence, which is what happened to the practicum step map when its schema was
rewritten. The step map lives in `features/applications/steps.ts` rather than in
the component so both can import it.

**No rate is published that nothing reads.** `funding.test_rules.NoUnreadRateTests`
prices a representative application of every type across both course loads, both
dependant states and all three streams, records every rate `PolicyBook` actually
resolves, and fails on any seeded rate nothing touched. Worked out by watching
rather than by parsing the rule definitions: re-implementing the template
expansion would be a second copy of the thing being guarded.

**Emergency relief can be filed with nothing attached.** Its documents question
is optional, alone among the forms that ask for one. A form that withholds help
until a landlord writes a letter is the opposite of what it is for. Its phone
number is required, also alone: this is the one form where the office may need
to reach somebody the same day, and an email address is not a way to do that.

**The scholarship's achievement bands are rates, thresholds included.**
`high_threshold_percent` and `mid_threshold_percent` were published as editable
policy rates while the rule carried 80 and 70 written into it — so the policy
screen let an administrator move a threshold, save it, record a history entry,
and change nothing. `Tiered` now takes `at_least_key` and reads the threshold
from the rate. A threshold whose rate is missing awards nothing and reports the
gap, rather than handing the top band to everybody.

The award amounts are not quoted on the form either, for the same reason: they
are rates, and a copy in help text is a second place for them to disagree. The
office's own mock-up already quoted figures that did not match the seeded rates.

**An appeal can never be submitted late.** It only became possible to badge one
when the appeal form started asking for a semester: `deadlines.stamp` gives any
application carrying one a term, and a term with a deadline behind it gets a
lateness flag. An appeal filed in December about a Fall decision would have been
marked late — which is not a fault, it is the entire purpose of the form.
`deadlines.NEVER_LATE` withholds the judgement and keeps the fact: the term is
still recorded, because that is how staff find the decision being argued with.

**`doc_supporting` is plural on every form that asks for it.** It was a single
file on the appeal, on emergency relief and on hardship — the same question, on
three forms where people have several papers. One key, one meaning: an appeal is
argued from a transcript *and* a letter *and* a medical note.

**A graduation claim's total is not asked for and neither is the amount.** The
credential *is* the amount: `graduation_bursary` is a `flat_rate` rule keyed on
`{credential}`, so the stored choice values are the rate keys. A label may be
reworded freely; a value may not.

**"Payment goes to another person" holds the award out of the payment file.**
Nothing in the run can redirect a payment — that is an authorisation the office
grants — so `finance.preview` reports a released award as blocked, naming who was
asked for. The alternative was worse than a flag nothing reads: the applicant
asks for the money to go elsewhere, is not refused, and it goes into their own
account anyway. What a release of funds actually requires is still an open
question for the office (§8).

**The document endpoint accepts an upload from someone with no account.** It
used to require a login, which protected nothing and made the graduation award
unsubmittable: the form requires proof of completion, is claimable without an
account, and every upload was refused — so a required answer could never be
given. What bounds it is the 10MB cap, the type allowlist, the generated
filename, a refusal to attach to anybody's application, and a `guest_document`
throttle at the same ceiling as the guest submission itself.

**A declaration's date opens on today.** `Field.defaults_to_today`, filled by
the client rather than by `services/prefill`. The employer's practicum report is
the case: it is filed by a supervisor with no account, and prefill returns
nothing for a guest — which is most of the people who file it. It is built from
the local date parts, not `toISOString()`, which converts to UTC first and is a
day out for part of every day seven hours west of it.

**`travel_purpose` is asked although the office's paper form does not ask it.**
It resolves the rate key `max_{travel_purpose}`. Dropping it to match the
screenshot would leave every claim uncapped.

**Notifications carry a `kind`.** Inferring one from words in the title is the
same mistake as identity-by-display-string.

**Vite is pinned to port 5173 with `strictPort`.** Its default is to hop to the
next free port, and `FRONTEND_URL` is baked into the registrar's link at the
moment it is queued — a wandering dev server sent registrars links to a dead
port.

**An application cannot be filed without somewhere to pay it.** `banking()`
was optional on three of the five forms that collect it, which put the shortfall
at the far end of the money path: the award was priced, approved, and then held
out of the payment file reading "has no bank account on file" — on a screen the
applicant never sees, weeks after they could have answered in a second. It is
required on all five now. The office's rule, and the reason the payment run no
longer needs to report it.

That rule is only workable because nothing is retyped. `account_number` is
written once and read only by the finance export, so requiring it back would
have made every *second* application unsubmittable — the student would be asked
for a number the portal deliberately refuses to show them. Two things close
that: `prefill` fills `account_holder`, `transit_number` and
`institution_number` from the student's `BankAccount` (never the number), and
`Schema.clean(private_on_file=...)` accepts a blank private answer when the
server already holds it. It is the same "absent means unchanged" rule that the
edit path already used for a SIN, extended to a new application by somebody with
details on file. `banking.on_file_for` is the single definition of what is
already held, so the form and the validator cannot disagree about it.

**The payment run reports what needs a person, not a wall of red.** With banking
required, "no bank account on file" cannot arise. What is left is rare and
genuinely needs somebody: a release of funds to another person, a guest claim
not yet attached to an account, an award whose pricing went missing. It is
reported quietly and still never dropped — a payment missing from the file is a
person who does not get paid, which is the reason the list exists at all.

**Finance is told an amount, not a breakdown.** The payment file carried one
row per award *line*, on the reasoning that "a single lump sum cannot be traced
back to the rule that produced it". The office reversed that: an application
priced across two streams and two categories became four rows against one bank
account, and finance had to add them up to learn what one transfer was worth.
`finance.payment_batches` now groups into one payment per **application** — not
per student, because a student with two funded applications is owed two
payments that must each trace to the decision behind them, and merging them
produces a figure no decision accounts for. The breakdown is not lost: it is on
the application, on the approval letter and in the decision history, which are
the office's records rather than a payment instruction. A `Covers` column keeps
the categories readable, and the reference is `DGG-<date>-A<application>` —
quoting one line's reference against a lump sum would name a part as the whole.
The award ids travel in the API response as `award_ids`, because the check that
a superseded pricing is never re-offered is what stops money going out twice and
it must survive the row becoming a payment rather than a line.

**Emptying the database has two mechanisms, and they are kept apart.**
`purge_applications --drop-test-accounts` reasons about which addresses are
throwaway and protects staff on principle — `admin@dgg.test` is on a test domain
and is the account that administers the site. `--keep-only=a@x,b@y` does neither:
it names who survives and deletes everyone else, staff included, for the
cut-over where a database that has been tested against becomes the one the
office signs into. Asking for both at once is refused rather than resolved in
some order, because two mechanisms answering "is this account safe?" differently
in one run makes a safeguard into a coin toss.

Two guards, both load-bearing and both verified by removing them and watching
tests fail. *A keep address that matches no account is refused* — a typo does
not announce itself, it simply matches nothing, and the account it was meant to
protect is deleted with the rest. *A keep list that leaves no active
administrator is refused* — registration makes students, staff are made by an
administrator, and §10 already records how a portal with no accounts reads:
"No active account found with the given credentials", which looks exactly like a
broken deployment and is a working one nobody can enter. Both guards run in
`survey`, before the first delete rather than partway through one.

**Deleting an account empties the office's history of whose name was on it.**
Nine of the eleven foreign keys into `User` are SET_NULL, and four of those sit
on rows a purge deliberately *keeps*: `PolicyChange.changed_by`,
`RuleSet.created_by`, `ReportedCost.recorded_by`, and the audit entries that are
not about an application. So the rate change survives and the person who made it
does not. That is the right trade — PROTECT would make the account undeletable,
and the entry matters more than the attribution — but it is a real loss, so the
report counts it per model instead of letting a column quietly empty itself.
`--keep-only` also names every account it would delete in full rather than
truncating at twenty, because this is the path that deletes staff and a
truncated list hides exactly the account somebody wanted to check.

---

## 6. Bugs that were found the hard way

Recorded because each represents a class that can recur.

| What | Why it mattered |
|---|---|
| `DjangoFilterBackend` enabled globally but no `filterset_fields` on the viewset | Every `?status=` was silently ignored and the full list returned, with a 200. Student and staff filters had never worked. |
| `axios.create({ headers: { 'Content-Type': 'application/json' } })` | Applied to file uploads too, so FormData got no multipart boundary. *"The submitted data was not a file."* 466 backend tests and three live audits passed while it was broken — none of them tested how the **client** asks. |
| `npx tsc --noEmit` | Checks **zero files**: `tsconfig.json` has `"files": []` and only project references. Every "typecheck clean" claim from it was vacuous. Use `npm run typecheck` (`tsc -b`). |
| Console email backend on Windows | Every message contains `Délı̨nę`; cp1252 cannot encode it, so all 143 queued messages failed with `UnicodeEncodeError`. |
| `generate_types` resolved output against `Path.cwd().parent` | Run from the repo root it wrote the file **outside the repo** and reported success. |
| `.chip:hover` (0,2,0) beating `.chip--on` (0,1,0) | Hover won on `color` and lost on `background`: dark text on a black chip. Specificity, not ordering. |
| Models with no reader | `ApplicationDeadline`, `SupportingDocument` had tests and no endpoint; `ShareLink` and `ActionToken` had nothing at all and were deleted. |
| `finance.pending_awards()` filtered on `status=APPROVED` alone | Sending an application to finance moved it out of the very query the payment run selected on, so the award was stranded — $17,100 of it in the seeded data — approved, unpaid, and invisible. Now `PAYABLE_STATUSES` covers both. |
| Nothing ever created a `BankAccount` from an application | Only `seed_demo` did. A student who filled in the payment section was still reported to finance as having no account on file, and their approved award held — while the details they typed sat unused in `answers`. |
| `CappedTuition` explanation subtracted before it reported | It told the reviewer the *remaining* balance was what had been awarded. The amount paid was right; the sentence defending it on appeal was not. |
| Required booleans could not be answered "no" | The frontend's `missing` check used `!answers[key]`, so "No" read as unanswered and the step would not advance. Fixed with an explicit `isAnswered()` and a Yes/No radiogroup. |
| No test had ever submitted a `continuing_funding` application | Rewriting the form broke nothing, because nothing was watching. Removing banking from `answers` broke nothing either. Every real defect in this round came from the live audits or from deliberately sabotaging a fix to see whether its test noticed. |
| A filed application could not be changed by anybody | Staff could ask for more information — the note was recorded and reached the student — and there was no path by which the student could act on it. The application sat in "more information needed" until somebody declined it. |
| Uploaded documents could never be opened again | The upload endpoint existed and nothing read what it stored. A reviewer was shown the text `document:12` against the question it answered, which is the same as the document never having been attached. Six forms required documents before anyone noticed. |
| Award totals counted every pricing an application had ever had | `AwardDecision` supersedes rather than overwrites and its `Award` lines are kept, so an appeal can argue against the figures that were in force. Nothing summing awards said *which* decision it meant. A student approved once for $2,000 was shown $4,000 the moment anybody re-priced; the office's totals were inflated to match; and the payment run offered both sets of `PENDING` rows, so the money would have gone out twice. `Application.awarded_total` was right throughout — which is why the application said $2,000 and the dashboard above it said $4,000, and why nobody spotted it. Reported by the owner against his own record. Fixed with `Award.objects.current()`; `paid()` is deliberately *not* scoped, because money that left the bank under a superseded decision still left the bank. |
| Emergency relief had a signature and no declaration | Every other form asks the applicant to confirm something before signing. This one collected a signature with nothing above it to sign, which is a signature attesting to nothing. Found by listing which schemas carry a `CONFIRM` rather than by reading them one at a time — `admission` and `hardship_bursary` are still in the same state. |
| Editing a rule in `seed_rules.py` does not change the rule set already in force | A `RuleSet` stores each rule's effect as JSON in the database, deliberately: a decision has to stay replayable against the rules that governed it. So pointing the scholarship tiers at editable thresholds fixed nothing on any existing database — and no unit test could notice, because the suite seeds a fresh rule set on every run. Only the live audit, run against a persistent database, saw it. Publishing a new version is the migration: `manage.py seed_rules --publish`. |
| The guest submission path never stored an encrypted identifier | It called `split_private`, which lifts a SIN out of `answers` precisely so it can be stored somewhere safer — and then stored it nowhere. Invisible while no guest form asked for one. The graduation award asks, and a regulated number the applicant typed would have been silently discarded. |
| The document endpoint required a login, on a form claimable without one | The graduation award requires proof of completion and is filed by people with no account. The upload control rendered, every request was 401, and the required answer could never be given: the form was unsubmittable in a browser while the whole suite passed. No test had ever asked for a file as a guest. |
| `jsonable` stringified anything that was not a JSON scalar | Fine while every answer was one. The moment a field held a list — expense rows, several receipts — the answer stored was the text `"[{'amount': Decimal('812.50')}]"`, readable by nothing and derivable from by nothing. Caught before it shipped only because the travel claim was audited over real HTTP rather than through the schema alone. |
| A renewal from a student new to the portal could never be approved | The enrolment request goes out at submission, but only when a registrar address is known — the renewal form does not ask for one, it is carried from the student's last application. Somebody whose admission was on paper has nothing to carry, so the request was skipped **in silence**: tuition could never be confirmed, so the application could never be forwarded or approved, by anybody. `verification.issue` had one caller and no endpoint, so the comment promising staff could reissue described something that did not exist — which also left a bounced address and an expired request with no way back. Staff can now issue and reissue it, and the screen distinguishes "not requested" from "not required". Found by wiping the database: with accumulated data every student always had an address to carry. **Closed properly on 27 Aug 2026 by asking:** the renewal now has a `registrar_email` field, pre-filled from the profile and from the last application that named one, so the request goes out on submission for everybody. Both earlier fixes gave the office a way to recover *after* the silence; neither stopped it. `scripts/renewal_registrar_audit.py` drives the case that could not be reproduced by anyone with history — a student registered seconds earlier, filing a renewal, through to an award built on the registrar's figure. |
| The screen said an enrolment was "not required" when it had merely never been asked for | Two different situations reported identically, and the one that reads as "nothing to do here" was the one that needed doing. |
| Staff opening /applications got the student's page | "My applications", "Everything you have submitted", and a catalogue inviting a support worker to apply for funding. Their navigation points at /review, so it took arriving by another route to see it — and with rows in the database it read as a plausible queue. Only an empty database made it obvious. |
| A confirmed enrolment made an application uneditable by anyone | The registrar's `confirmed_tuition` is written onto `answers`; the admission schema has no such question, because the student is never asked it. Re-posting the stored answers was then refused — for a key the *server* had put there — so from the moment an institution answered, neither the office nor the student could change anything. `verification.py` asserted in a comment that every confirmable key was a schema field; two of the four were not. Answers the schema does not define are now carried through an edit untouched and never taken from the client, so an edit cannot raise the tuition an award is funded against. |
| A required SIN or bank account made every edit impossible | The same class, on the other side: private answers are split off at submission and never returned, so a form opened on a stored application opens with them blank — and required, they were reported missing on every edit of every form that asks for one. Absent now means unchanged, on the server *and* in the renderer: the schema publishes `private`, and `SchemaForm` stops counting a withheld answer as an unfilled one. Fixing only the server changed nothing visible, because the Save button stayed disabled. |
| Asking for more information collected no words | The server has carried the reviewer's note into the email and the portal notice since the path existed. The screen posted the transition with nothing attached, so every student was told "Please review your application" — a request to guess. Declining collected no reason either. Both now ask, and refuse to send until something is typed. |
| A single-file question could be replaced but not emptied | `Remove` existed on the multi-file control and not on the single-file one, so a student told to take down a document attached to the wrong question could only put a different one in its place. |
| Attached documents could not be opened, again | The detail screen linked each one with a plain `<a href target="_blank">`. The endpoint is authorised by the bearer token and a browser *navigation* carries no header, so every click — every role, every document — opened the API's 401 page. The link sat directly under the comment describing the first version of this bug. 809 unit tests and 425 audit checks passed throughout because every one of them sends the header, and the frontend test asserted the `href` existed rather than that anything opened. Fetched through the client now, handed to a tab as a blob. Found by clicking it in a browser. |
| Nothing ever marked an award paid | `Award.Status.PAID` was read in two places and written by none: `dispatch()` stopped at SENT_TO_FINANCE. So `Award.objects.paid()` — which exists precisely so money paid under a superseded decision still counts — returned nothing on every database, and the student's dashboard read **PAID $0.00** beside an awarded total in the millions. Dispatch marks PAID now; the office's tile was counting SENT_TO_FINANCE and is renamed to match. Same class as `residency_flag`: a state with readers and no writer. |
| Two test faults that made a correct document look wrong | Counting `/Type /Page` in the PDF bytes also matches `/Type /Pages`, the page-tree node, so every page count came back one too high; and `stringWidth` needs the font registered, which normally happens on the first render, so a measurement written before one passed or errored depending on which test ran first. Both were in the tests rather than the product, and both would have been "fixed" by loosening the assertion. |
| A flag with two readers and no writer, for four months | `residency_flag` was serialised onto every application, counted on the staff dashboard under "needs a look", and written by nothing but a test fixture. The count could only ever be zero, so the one number on that screen that never moved read as "no problems" rather than "not implemented". Reported by the office as a live fault — a student who said they do not live in the NWT and gave an NWT address — which is the same class as `Award.Status.PAID` being read in two places and written by none. |
| Money that came back vanished when an application was re-priced | A repayment is recorded against an award line. Re-pricing supersedes that line, `Award.objects.awarded()` scopes to the decision in force, and the repayment stopped being counted — the year went back to reporting its gross as its net, silently, and money a student had returned ceased to exist on the report. The same fact `Award.objects.paid()` exists to respect: money that left the bank still left it, and money that came back still came back. Repayments are now gathered against every award of the year's applications, whatever decision they belong to. |
| A hand-entered cost dated 15 June appeared on no report at all | The report looks for costs filed against 1 April, the serializer accepted any date, and a figure the office had entered simply disappeared. Normalised to the fiscal year the date falls in rather than refused — the office is naming a year, and losing money quietly is worse than being forgiving about how a year is written. |
| A variable shadowed 400 lines away | The report section of `lifecycle_audit.py` named a local `after`, and `after` already held an application payload read hundreds of lines further down. The audit crashed with a bare `KeyError: 'answers'` in a check that had nothing to do with reporting. Long scripts do not have small scopes. |
| A sabotage that could not fail, twice over | Two guards on the report looked untested because the *audit* could not move them: trades and upgrading are nought on a database whose enrolments all predate the question, and the repayment arithmetic compared two figures that were both zero. An arithmetic check on a figure that is always nought is the residency count again. The audit now records a repayment against its own award so the figures have somewhere to move, and the subset rule is pinned by a unit test that classifies its own applications. A third sabotage appeared to pass only because the dev server was started `--noreload` and never picked the change up. |
| The PDF printed the government's own name as black boxes | reportlab's built-in Times is Latin-1 and silently substitutes anything it cannot encode, so "Délı̨nę Got’ı̨nę" came out as "Dél■■n■ Got’■■n■" — on the letterhead of the government whose name it is. Every automated check passed: the *text layer* is correct and a PDF parser reads the characters back perfectly, because what is missing is the glyphs. Found by looking at the rendered page. The guard is structural — the document must embed the shipped font — and the first sabotage of that guard passed too, because it renamed the shipped font rather than reverting to the built-in. |
| An `.pdf` URL that the router could never match | DRF's router appends a trailing slash, so `approval-letter.pdf` answered 404 — indistinguishable from the application not existing. The path is `approval-letter/pdf/`; the downloaded file takes its name from Content-Disposition regardless. |
| The approval letter was never sent when the office approved before pricing (now audited both ways round) | The letter travels inside the approval email, and at that moment an application priced afterwards has no award to describe — so `letters_for` refused, the email went out without it, and nothing sent one when the pricing arrived. The student got no letter at all, silently, on a path nothing forbids. Every test and every audit priced first, because that is the order the lifecycle audit walks, so all of them passed. Found by asking what the *other* order does rather than by re-reading the code that assumed one. Same class as the renewal whose enrolment request was skipped in silence. |
| The print stylesheet hid elements that do not exist | `.app-sidebar`, `.app-header`, `.app-shell__nav` — none of them are in this codebase; the shell uses `.shell__side` and `.shell__bar`. Every printed approval letter would have carried the portal's navigation down its left-hand side. No test can see this: printing is not something the suite exercises, and the CSS was valid. `forms/printable.css` already had the right selectors and was the thing to copy rather than to reinvent. |
| A `beforeEach` that handed the runner a teardown function | `beforeEach(() => uploadDocument.mockReset())` — a concise arrow body *returns* the mock, and vitest treats a value returned from `beforeEach` as a teardown callback. So the runner itself called the mock after every test, outside any catch. Against a rejecting implementation that is an unhandled rejection, and it failed the very tests that prove rejections are handled. This is what PROJECT_STATE recorded as "upload failure path has no frontend test; vitest reports the rejection as unhandled despite the component catching it" — the component was correct throughout and the gap was in the test file's own setup. Both failure-path tests are written now. |
| The dashboard's queue tiles linked to a queue that ignored the link | "To review" and "Awaiting decision" have pointed at `/review?status=…` since the screen was written, and `ReviewQueue` held its filters in component state and read the query string nowhere — `useSearchParams` appeared in no file in `src/`. So every one of those links landed on the whole list, filtered by nothing, and with rows in the database it read as a plausible queue that was merely larger than the number that had been clicked. The same class as the global `DjangoFilterBackend` with no `filterset_fields`: a filter silently not applied still answers 200 with everything. Found while adding a third tile that would have linked the same way. The filters live in the URL now, so a queue can also be sent to a colleague. |
| A percentage published as an amount of money | Every `PolicySetting` was seeded `unit='$'` and the rates screen formatted all of them with `formatMoney`, ignoring `unit` entirely — so an 80% achievement threshold reached administrators as "$80.00", on the one screen where they change what students are paid. `policy_admin.unit_for` derives it from the key; migration 0009 corrects rows already stored. |
| The name pre-filled as nothing on the first form anybody files | `prefill.FROM_ACCOUNT` mapped `full_name`; `admission` and `travel` ask `first_name` and `last_name`. A key the schema does not define is skipped in silence, so on exactly those two forms a returning student retyped what the portal already held — no error, no log. The date of birth and address were on the account and never offered back on any form. The test asserts across every schema, because a test for either form alone passes. |
| An empty box read as a malformed one | The profile posts every field in a section, so a student who has never given their date of birth posts `date_of_birth: ''` — and a DRF DateField reads that as a malformed date, an IntegerField as a malformed number. Every student, on their first Save, was told their date of birth was wrong on a box they had left alone, and could not save the section at all. Registration collects no date of birth, so this was the common path rather than an edge of one. The same fault sat on the enrolment section's dates and counts. Invisible from the inside because a CharField takes `''` silently: the tests that cleared a field cleared a text one. `BlankMeansNothingOnFile` now derives the rule from the field type and is shared by both serializers, and the tests assert across *every* editable field rather than against one. Same class as "a required SIN made every edit impossible". |
| A screening answer nobody offered was read as "no" | `eligibility._yes` treats anything it does not recognise as a negative, silently. So `receives_sfa: 'maybe'` — or a number, which a DRF CharField will quietly stringify into `'5'` — decided a funding stream by falling through a comparison, and looked from the outside exactly like somebody answering no. Identity-by-display-string in miniature: a value nobody offered, meaning something nobody chose. Both doors that take these answers now check them against the choices the question actually offered. Found by asserting that a non-string is refused, which it was not. |
| An empty stream list read as "never screened" | The fallback to `is_indian_act_registered` / `is_deline_beneficiary` fired whenever `eligible_streams` was empty — correct while the only accounts with no tags were ones that predated them. The profile made emptiness a *current answer*: a student who re-answered the screening to say they now receive SFA, and is not a beneficiary, qualifies for nothing — and was handed PSSSP straight back by the fallback. Found by a test asserting the consequence ("an account with no streams cannot file an application") rather than the write, which passed on its own. `eligibility_assessed_at` now separates the two cases. |
| A DRF response whose body is `None` | `GET /api/me/banking/` returned a bare `None` for "no account on file": 200, no content type, and a client that cannot parse it. "Nothing on file" is the common case for a new student, so the one answer the endpoint gives most often arrived as a transport error. Caught by a test calling `.json()` on it, which is what the client does. |
| Three forms that pay money asked for no bank account | `continuing_funding`, `academic_scholarship` and `hardship_bursary`. Nothing but a filled-in banking section creates a `BankAccount`, so a student whose **first** application was one of those three had none — the award was priced, approved and then held out of the payment file reading "has no bank account on file", on a screen the applicant never sees and weeks after they could have answered in a second. Reported by the office as the payment dashboard showing errors. Two tests asserted the absence on the grounds that "this cannot be claimed without an account, so finance already has somewhere to pay" — a portal account is not a `BankAccount`, and the premise was never checked because every test and audit touching those forms used a student who had already filed an admission, which does ask. The guard is now derived from `seed_rules.RULES` rather than from a list of five kept by hand. |
| `identifiers.reveal` had unit tests, an audit entry, a reason argument — and no endpoint | So the full SIN was unreadable from the portal by anybody, including the administrator doing the federal return the number is collected for. The same class as `residency_flag` and `ShareLink`, but it survived longer: a masked `•••••996` looks like a working screen, and the detail page said in so many words that reading the full number was recorded against your name — describing an act nothing could perform. Found by asking the question the office asked, rather than by reading the module, whose docstring described the endpoint as though it existed. |
| The payment run showed no account on the screen that releases the money | Student, application, what it covers, how much — and nowhere the money was going. The account was only in the dispatched CSV, and dispatching marks every award in the batch PAID and drops it off the run, so the only moment finance could check a transit number was after the one moment it could still act on it. |
| The check that stops money going out twice had stopped checking | `surface_audit` read `row['id']` from the payment run as an `Award` primary key and filtered the award table by it. The file became one payment per **application**, so that id is an application — and `award_ids` was added to the row at the same time, with a comment saying it exists precisely so this invariant stays observable. The audit was never updated. Where the two id ranges did not overlap it matched nothing and passed vacuously, which is every accumulated database; on a freshly migrated one the numbers are small and collide, and it reported unrelated awards as superseded. Found by running the whole suite against a database built from nothing. **No money was ever at risk** — two independent guards hold: superseding cancels the previous lines, and `Award.objects.awarded()` scopes to the decision in force. Each was sabotaged separately and the behaviour held; the repaired check fires only when both are broken, at which point it reports $25,200 offered against a $12,600 decision. |
| A curly apostrophe killed an audit script outright | Windows console output defaults to cp1252 with a *strict* encoder, so a `print` of a check description containing `’` raised `UnicodeEncodeError` and ended the run — the same encoding fault that once failed 143 queued emails, arriving through stdout instead of through SMTP. Scripts that reconfigure stdout survive it; ones that do not die on their own output. |
| A database URL whose password contained `#` | `urlsplit` reads `#` as the start of a fragment, so everything from it was discarded: the host parsed as `postgres`, with no port and no database name. Percent-encoding is the fix. Nothing said so — `dj_database_url` returned a config dict happily, and the failure arrived later as a connection error naming a host nobody had configured. |
| The Supabase direct host is IPv6-only | `db.<ref>.supabase.co` has an AAAA record and no A record. Neither a machine on an IPv4-only network nor a Vercel function can reach it, and the resolver's answer is "Name or service not known" — which reads as a deleted project rather than an unroutable one. The pooler (`aws-N-<region>.pooler.supabase.com`, user `postgres.<ref>`) is the IPv4 route, and is what `.env.example` had documented all along. |
| `FIELD_ENCRYPTION_KEY` was read from a setting nothing declared | `identifiers._key()` reads it with `getattr(settings, …)`, and `settings.py` never assigned it. So the environment variable could be set correctly on the host, shown in the dashboard, and be invisible to Django — a deployed process would still have refused every application asking for a SIN. Config that is set and unread looks exactly like config that is correct. Same class as a flag with readers and no writer, in the opposite direction. |
| `build.sh` called a management command that did not exist | `python manage.py seed_policies` had been a deploy step for as long as `build.sh` had existed, and no such command was ever written. A deploy step naming a missing command fails at the moment of cut-over and is silent until then. |
| `migrate` leaves a fresh database unable to price anything | Migration 0013 returns early when no `PolicySetting` exists, deliberately: seeding from a migration would give the test suite rates before a test asked for any, so a test proving what happens when a rate is *missing* would find one and pass for the wrong reason. Correct for the suite, and it means a production database that has only been migrated has no rates, no deadlines and no rule set. `seed_policies` is now that step, and `funding.office_config` is the one copy of the figures both it and `seed_demo` read. |
| Production had been pointed at Gmail for 75 days | `EMAIL_HOST` on the deployment was still `smtp.gmail.com` with no credentials, while the project had moved to Hostinger. The first real delivery attempt came back `535 … BadCredentials … gsmtp`, from a provider nobody had meant to be using. Environment set once at the start of a project and never revisited is not configuration, it is sediment. |
| The live domain served a different deployment entirely | `dgg.nexauratechs.com` resolved to Hostinger (`platform: hostinger`), serving a stale single-bundle frontend from a shared-hosting vhost, while the Vercel project that held all the configuration was never in the request path. Every `/api/*` request returned `index.html` with `Content-Type: text/html` and a 200 — a frontend talking to itself. A 200 is not evidence that the thing answering is the thing you deployed. |
| A document store that could only write | `SupabaseStorage._open` raised `NotImplementedError` from the day the class was written. Uploading returned 201 and the object was genuinely in the bucket; opening it was a 500. Invisible to all 1,186 tests and to every developer, because `STORAGES` selects this backend only when `SUPABASE_SERVICE_KEY` is set and local work runs on `FileSystemStorage`, where reading works. The third time this project has shipped a write-only document store, and the first not found by a person clicking a link. Two faults in front of it — an empty `SUPABASE_URL`, then a `service_role` key from another project — had to be cleared before it could even be reached, which is the ordinary shape of this: a broken thing behind a broken thing reads as one problem. |
| `cleanUrls: true` in `vercel.json` 404'd every deep link | The SPA fallback rewrote `/(.*)` to `/index.html`, and `cleanUrls` 308-redirects any `.html` path to its extensionless form — so the fallback resolved to a redirect instead of the document and Vercel answered `NOT_FOUND` for /login, /dashboard, /profile and /enrolment/&lt;token&gt;. Wrong since the commit that introduced the file. It survived because of **who** uses a deep link: staff and students load `/` and navigate inside the router, where no request reaches Vercel at all. The registrar arrives cold from an email, on a path, with no account and no other route in — the one user who cannot report that the link is dead. Tuition is funded against their figure, so the entire tuition path ran through the single URL nobody could see was broken. `vercel.json` is imported by nothing, type-checked by nothing and touched by none of the 1200 tests; `core.test_vercel_config` now reads it, and asserts the pairing rather than banning `cleanUrls` outright. |
| The scheduler that drained the outbox simply vanished | Every email the portal had ever queued sat in `outbound_email` unsent — 112 of them — while the portal looked entirely healthy from every screen. `send_queued_emails` is driven by an external cron because nothing serverless can run a management command on a timer, and an external dependency is one nobody redeploys, reviews or tests: it disappeared from the Hostinger account leaving no trace, and the only symptom was a registrar who never wrote back. The office reported it as "Form B is not being sent" — that is the one message whose absence is *visible*, because tuition cannot be confirmed without it — but nothing at all was being sent. **A queue whose worker lives somewhere else has no failure mode visible from the thing being measured.** |
| `email_status` existed, and could not be run where it mattered | The command reports all three ways email fails silently, and predates the deployment it needed to describe. Nothing on serverless runs a management command — the same fact that put the drain behind HTTP — so the one deployment where email was actually broken was the only place the diagnostic could not be run. It is now `GET /api/tasks/email-status/` as well, over one shared assessment in `notifications/diagnostics.py`. A diagnostic that runs only where the fault is absent is not a diagnostic. |
| Two sabotages of this round's work were **not** caught by the tests written for them | Both concerned discarding a client-supplied computed total. The tests passed with the guard removed, because a second mechanism — deriving over the top, and an empty initial value — happened to produce the right answer anyway. Written as they were, they asserted the outcome and not the defence. Both now exercise the path where only the guard stands: a total that does not parse, and a total that arrives pre-filled. |
| Rotating `TASK_TOKEN` silently stopped every outbound email | The token is written *literally into the Hostinger cron command* and stored in Vercel as a **Sensitive** variable, which is write-only: nobody can read it back, so rotating it means setting a new value and editing the cron in the same pass. On 25 Aug 2026 the env was re-created, the cron began answering 403, and mail stopped for 19 hours with every screen looking healthy. Two facts have to be changed together and only one of them lives in this repository. The tell for a stopped scheduler is not the pending count but the *shape* of `sent_at`: 112 messages sharing five adjacent minutes is a hand flush, not a schedule. |
| A queued email outlived the row it pointed at | `verification.issue` deletes the previous `EnrollmentVerification` when a request is re-issued — deliberately, so two links are never live at once — but nothing cancels the already-queued email carrying the deleted row's token. With a healthy cron the window is five minutes. With the queue stopped for 19 hours the row was superseded while its email waited, and registrars received links that were dead before they arrived. `resolve()` reports them with the same "This link is not valid." it gives an unknown token, so a superseded link is indistinguishable from a forged one — to the recipient and to whoever debugs it. |
| The award editor was offered on exactly the applications with no award | "Edit breakdown" was gated on `canAmend`, which is the rule for *amending answers*: admin, and not `DECIDED_STATUSES`. The award rule is different and the server states it plainly — `set_award` refuses only `DECLINED`, because "approved stays editable until the money is paid, which is what the editor is for". So the button was hidden on `approved` and `sent_to_finance`, the two statuses where an award exists, and offered on the ones where there is nothing to seed it with. The editor therefore opened empty, and saving replaced the whole decision with the single line typed into it. The seeding was never broken; it was unreachable. A client repeating a server rule repeated the wrong one. |
| A hand-set award silently destroyed a semester's funding, in production | Application #56 — an `admission`, already `sent_to_finance` — carried one line: `scholarship 400.00 rule=manual_1`. No tuition, no living. Re-pricing it would award $42,300. The empty editor above produced it, and because `scholarship` is not in `SEMESTER_CATEGORIES` the approval letter was then correctly refused, which the student saw as "The approval letter could not be loaded." Two faults meeting: one wrote the data, the other hid the reason. |
| The living allowance is paid per month of a "semester" nobody bounds | `rules.engine._months` returns `(years x 12) + months + 1` from `semester_start`/`semester_end`, with a sensible default of 4 when the dates are missing or reversed — and **no upper bound**. Application #56's enrolment verification carried `2026-08-29` to `2030-03-26`, so a fall semester priced at 44 months x $950 = **$41,800** of living allowance. Application #54 has the opposite, `semester_start == semester_end`. Both were accepted in silence. The registrar is asked to confirm these dates and nothing checks that a semester is a semester. Still open: the bound is the office's to state. |
| The approval letter's four reasons were all shown as "could not be loaded" | `ApprovalLetter.tsx` read `problem.response.data.detail` — the shape **axios** throws, not the shape `toApiError` re-throws. `ApiError` carries the server's wording in `.message` and has no `.response` at all, so the expression was always `undefined` and every failure fell through to the generic sentence, including the informative 409s. The comment directly above it said the server's wording "is what tells somebody what to do next, so it is shown rather than replaced with a generic failure". The test passed throughout because it rejected with a hand-made `{response:{data:{detail}}}` — a shape no caller ever produces. **A fabricated error shape proves nothing about the real one**, and this is the third entry in this table where a test asserted against something the client does not actually do. |
| The payment run listed one blocked line per award, not per person | `finance.preview` blocks each award *line*, which is right — a line is what does or does not reach the file — but the reason is about the student. An application priced into five lines said "Both Journey has no bank account on file" five times, and the screen reported "28 awards cannot be paid" for eight people. The reader cannot tell twenty-eight problems from eight. |
| The dashboard and the payment run quoted different figures for one pot | Production showed **$80,650.00 awaiting payment** on Home and **$0.00 ready to pay** on the payment run, both true and neither explaining the other: the dashboard counts every `PENDING` award, the run counts only unblocked ones, and every award was blocked for want of a bank account. Putting the blocked figure on the dashboard broke `test_the_whole_summary_is_a_handful_of_queries` — `finance.preview` does a bank lookup per award — so the payment run is where the difference is now stated, being the screen that can also say why. |
| Three fixes sat in the working tree while production ran without them | `groupBlocked` had already been written, with a comment describing the duplicate-blocked symptom exactly, and the office was still looking at the unfixed screen. Undeployed work is indistinguishable from work never done, and "it is fixed" means nothing until a deployment carries it. |
| Banking was optional on three of the five forms that pay out | The consequence surfaced at the wrong end and to the wrong person: an award priced, approved, and then held out of the payment file reading "has no bank account on file" — twenty-eight lines of it on a screen the applicant never sees. The question is now asked where the person who knows the answer is sitting, and refused without. **A required answer collected late is an answer nobody can act on.** |
| Making banking required would have made every second application unsubmittable | `account_number` is written once and read only by the finance export, so a returning student would be asked for a number the portal deliberately refuses to show them, and there is no value they could type that the screen could confirm. The rule only works with `prefill` reading `BankAccount` for the three returnable fields and `clean(private_on_file=...)` accepting a blank fourth. **Tightening a requirement without checking what the server is willing to hand back is how a form becomes impossible to fill in.** |
| The audit written to prove a bug failed once the bug was fixed | `banking_prefill_audit` asserted that banking is *absent* from the prefill and that admission is *refused* without it. Both became false, correctly, and six checks failed. Rewritten to pin the new rule from both ends — blank is accepted when an account is on file, and somebody with nothing on file still cannot file. An audit that reproduces a defect has to be turned around when the defect goes, or it becomes a test asserting the fault is still there. |

---

## 7. Running it

```bash
# backend
cd backend
./venv/Scripts/python.exe manage.py migrate
./venv/Scripts/python.exe manage.py seed_demo        # refuses if applications exist
./venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000

# frontend
npm run dev            # pinned to 5173
```

Demo accounts, all password `DemoPass123!`:
`admin@dgg.test`, `director@dgg.test`, `worker@dgg.test`, `finance@dgg.test`,
`student@dgg.test`.

**Checks:**

```bash
manage.py prune_stale_answers       # answers whose question a schema dropped
npm run verify                      # typecheck (tsc -b), lint, CSS check, tests
npm run build
cd backend && ./venv/Scripts/python.exe manage.py test
./venv/Scripts/python.exe manage.py generate_types --check   # types vs schemas
./venv/Scripts/python.exe manage.py email_status             # is mail deliverable
```

**Live audits** — they drive real HTTP against a running server, and they are
the only thing on this project that has reliably found real bugs. Start the
server, then:

```bash
cd backend
./venv/Scripts/python.exe scripts/journey_audit.py       # 144 checks: one
        # student from sign-up to payment — the tags the screening saves, a
        # clean approval, the more-information loop run twice (an answer, then
        # a document), the breakdown across every stream they qualify for, the
        # office rewriting it and adding rows, an amendment on their behalf,
        # forwarding versus deciding, and every application type
./venv/Scripts/python.exe scripts/lifecycle_audit.py     # 205 checks: sign-up
        # through review, decision, award, payment run, notices, permissions,
        # the stream split against the queue each of its tiles links to, and
        # the approval letters — who may read them, whether they add up to the
        # award they describe, and a second application worked in the other
        # order: approved before it is priced, which is the path on which the
        # letter was once never sent at all
./venv/Scripts/python.exe scripts/continuing_audit.py    # 34 checks: the
        # continuing-funding form, its prefill, banking routing and exposure
./venv/Scripts/python.exe scripts/information_audit.py   # 30 checks: a
        # reviewer asking for more, the student editing and re-attaching,
        # and the office opening what was attached
./venv/Scripts/python.exe scripts/hardship_audit.py      # 47 checks: the
        # hardship bursary — both attestations, the itemised breakdown and the
        # cap the office moves
./venv/Scripts/python.exe scripts/emergency_audit.py     # 42 checks: emergency
        # relief — filing with nothing attached, the cap the office can move,
        # and the bank details reaching finance without reaching `answers`
./venv/Scripts/python.exe scripts/scholarship_audit.py   # 37 checks: the
        # achievement scholarship, and an administrator moving a threshold on
        # the policy screen actually moving what is paid
./venv/Scripts/python.exe scripts/appeal_audit.py        # 45 checks: the appeal
        # through every role that touches it — student, worker, director,
        # finance — and the things that make it unlike the others
./venv/Scripts/python.exe scripts/graduation_audit.py    # 31 checks: the
        # graduation award as a claimant with no account — the encrypted
        # SIN, the credential that decides the amount, release of funds
./venv/Scripts/python.exe scripts/practicum_audit.py     # 12 checks: the
        # summer student / practicum award and the employer report that
        # releases it — including the refusals
./venv/Scripts/python.exe scripts/travel_audit.py       # 55 checks: the travel
        # claim — the expense table and multi-file receipts as they survive the
        # round trip, and the total the server derives from the lines
./venv/Scripts/python.exe scripts/amendment_audit.py    # 56 checks: the office
        # correcting a filed application and the applicant answering back —
        # who may edit, what the applicant is told, and documents added,
        # replaced and removed
./venv/Scripts/python.exe scripts/profile_audit.py      # 96 checks: the student
        # profile — a newly registered student with nothing on file, filling it
        # in, a form opening pre-filled from it, a renewal whose enrolment
        # request reaches the registrar address the profile holds, re-answering
        # the screening and the next application's stream following, banking
        # reaching finance, and none of it reachable by anybody else
./venv/Scripts/python.exe scripts/report_audit.py       # 67 checks: the
        # annual report — who may read money, the programme breakdown
        # reconciling against the financial table two different ways, the
        # three filtered reports counting every application exactly once,
        # a mistyped programme refused rather than reported as an empty
        # year, and a narrowed export that says on its face and in its
        # filename that it is not the whole year
./venv/Scripts/python.exe scripts/money_chain_audit.py   # 16 checks: one
        # figure followed the whole way — the tuition the registrar confirmed
        # reaching the award, the award reaching the letters to the penny, and
        # the report reconciling. Deliberately gives the student a different
        # estimate from the registrar's figure, so a chain that quietly uses
        # the student's number is visible
./venv/Scripts/python.exe scripts/award_editor_audit.py  # 14 checks: what the
        # server allows a hand-set award to do at each status, and that saving
        # one line replaces every auto-generated one
./venv/Scripts/python.exe scripts/banking_prefill_audit.py  # 22 checks: the
        # payment details a student saves on their profile, and whether the
        # next form opens with them
./venv/Scripts/python.exe scripts/readiness_audit.py    # 95 checks: the whole
        # money path in the order the office uses it, and the joins between the
        # parts — every paying form asks where to send it and a student whose
        # *first* application is any of them can still be paid; the registrar's
        # figure reaching the award; the award's lines, the office's stream
        # split and the report's programme table describing the same money; the
        # letters adding up to the award, as a page, a PDF and an email; the
        # payment run's account, file and no-double-dispatch; an award blocked
        # for want of an account being recovered by recording one; and what an
        # administrator may read, what nobody else may, and what is written down
        # about it
./venv/Scripts/python.exe scripts/renewal_registrar_audit.py  # 25 checks: a
        # renewal from a student registered seconds earlier — no admission on
        # file, no profile, nothing to carry — through the registrar's email
        # and link to an award built on the tuition they confirmed. The one
        # case a returning student cannot reproduce, and the one that was
        # silently broken
./venv/Scripts/python.exe scripts/surface_audit.py      # 336 checks: what the
        # ten form audits never touch — registration, the eligibility
        # screening, token refresh, `attach/`, `enrolment-preview`, the
        # document read endpoint, every pre-fill slug, and every endpoint
        # against every role
```

`lifecycle_audit.py` reads the outbox and the verification rows through the ORM
as well as over HTTP, so `--base` alone is not enough to point it at a second
database: set `DATABASE_URL` to the same one, or its ORM half goes on reading
`db.sqlite3` and reports a registrar link that was never queued *there*.

Each defaults to `127.0.0.1:8000`. Eight of them used to default to a different
hardcoded port each — 8011, 8013, 8015, 8020, 8021, 8050 — so following the
instruction above produced a ConnectionError against a server that was running
perfectly well.

All twenty pass in full — 1,416 checks, counted by running them (27 Aug 2026), against both an accumulated database and one built from nothing. Run them both ways: three of the faults recorded in §6 are only visible on an empty one. The isolation check in `lifecycle_audit.py`
used to report that it could not run, every time, because `seed_demo` created a
single student: it now seeds a second one and the audit files an application as
them, so "a student cannot open an application that is not theirs" is tried in
both directions rather than skipped.

Each prints a pass/fail line per check and exits non-zero on any failure. Earlier
audits (`contract_audit.py`, `audit.py`, `formb_audit.py`, `deep_audit.py`) ran
from a session scratchpad and are gone; what they covered is folded into
`lifecycle_audit.py`. Keep new ones in `backend/scripts/` for the same reason.

---

## 8. Open items

**Needs a decision from the office:**

- ~~`residency_flag` is read in two places and written by nothing.~~ **Closed.**
  The office stated the rule — declared not resident, address in the NWT — and
  `funding.services.residency` implements it. The reverse direction is still an
  open question: see §5 for why it was not assumed.
- `late_approved_by` / `late_approved_at` — the "director approves a late
  submission" path does not exist, now that the late flag works.
- **UCEPP is never assigned automatically.** §8 makes it the
  upgrading-programme stream, and that is the only thing separating it from
  PSSSP — one screening question would assign it. The three questions that
  would carry §6 of the policy (the upgrading programme, PSSSP/UCEPP from
  another organisation, funding under another land claim agreement) were added
  on 17 Aug 2026 and **removed again at the owner's request**: the sign-up page
  stays as it is. So UCEPP still has no route in, and §6(A)(e) and §6(C)(d) are
  not enforced. Do not re-add the questions without asking.
- ~~The "reports" screen has been asked about repeatedly and never scoped.~~
  **Built.** The office supplied a mock-up of the annual report it sends its
  head department, and `funding.services.reporting` produces it. Two things on
  their wish list are open: how many students *stayed* enrolled against how many
  withdrew, which needs a withdrawal to be a thing the system records; and
  whether the report should count a student's enrolment against the year the
  semester falls in rather than the year they applied.
- ~~The hardship bursary's "$500 limit".~~ **Closed.** §9(G) says "up to $500".
  The rate is $500.
- **The hardship bursary asks for no documents.** Its screen has no upload, so
  neither does the form. Every neighbouring form has one, so this is recorded
  rather than assumed.
- **The emergency relief declaration is provisional.** The office supplied
  screens for five forms and none for this one, so its declaration was written
  here to fill a gap — it had a signature and nothing above it to sign. The
  wording needs replacing with the office's own.
- **`admission` still has no declaration.** Same gap, same reason it matters,
  not yet closed. `hardship_bursary` has one now.
- **Which decision an appeal is about.** The office's form identifies it by
  student, semester and academic year, and never names the decision itself. That
  is enough to find one term's application; it is ambiguous for a student who
  appeals two things in the same term.
- **Release of funds.** The graduation award lets a claimant say the money
  should go to someone else, and records who. Nothing pays a third party: the
  award is held out of the payment file with a reason, for the office to handle.
  What authorises a release — a signed form, identification, a witness — is a
  policy nobody has stated.
- **Who fills the practicum employer report.** The summer student / practicum
  award now carries it — organisation, supervisor and title, roles, performance,
  the employer's declaration and their signature — as one form the student and
  supervisor complete together. The office has not said whether the supervisor
  should instead receive it on their own emailed link, the way the registrar
  receives the enrolment verification. Building that flow before they say so
  would be inventing the answer.

- **Emergency relief has no programme in the policy.** The Bursary & Awards
  Program Procedure describes the hardship bursary as the only discretionary
  help. The form exists here and its $1,500 cap was invented during the rebuild.
  Kept rather than deleted, because removing a form students may be using is the
  office's call — but nothing in the policy authorises it.
- **The extra tuition bursary's annual limits are not enforced.** §9(B) caps it
  at $12,000 a year per student and $36,000 a year across everybody, and
  prioritises continuing recipients on a first-come basis. Only the per-semester
  side ($5,000 threshold, 25%, $4,000 cap) is implemented: nothing here tracks a
  year's awards across semesters or a programme-wide budget.
- **The graduation travel bursary's detail is not modelled.** §7(D) allows up to
  two family members, three nights at $350, and requires a completed two-year
  programme. The cap ($5,000) is applied; the conditions behind it are not.
- **Travel assistance's own conditions are not checked** either: §7(C) requires
  in-person full-time study at least 200km from home, and allows two round-trips
  a year. Nothing counts trips or measures distance.

**Needs a decision from the office — added 26 August 2026:**

- **What is the longest a semester may be?** `rules.engine._months` pays the
  living allowance per month between `semester_start` and `semester_end` and
  bounds nothing, so a confirmation carrying programme dates priced 44 months
  at $950 (§6). A bound has to be a number the office states; refusing anything
  above it and reporting the refusal — the same manner as a missing rate — is
  the shape of the fix, but the number is not a developer's to invent. Until it
  exists, **every living-allowance figure depends on two dates a registrar
  types and nothing checks.**
- **May an application reach finance unpriced?** Application #53 is an appeal at
  `sent_to_finance` with no decision at all. Nothing is paid, because there are
  no award lines, but the workflow permitted the transition.

**Production hygiene, outstanding as of 26 August 2026:**

- **`seed_demo` accounts are live on the deployment.** `admin@dgg.test`,
  `director@dgg.test`, `finance@dgg.test` and `worker@dgg.test` all exist in
  production with the password published in this repository. §10 says exactly
  this must not happen. `admin@dgg.test` also carries the **director** role
  while being named "Alice Administrator", so it is not what its address says.
  The only real account is the administrator on a personal address.
- **Production holds 56 applications, 62 award lines and 8 `@example.com`
  students**, all invented by audit scripts run against it. `purge_applications
  --drop-test-accounts` clears the case data and the throwaway students; the
  four demo staff accounts have to go by hand, because the purge never deletes
  staff on principle.

**Known gaps:**

- `POST /applications/{id}/attach/` (link a guest application to an account) has
  six backend tests and **no UI**.
- `MEDIA_ROOT` is local disk. Uploads will not survive a Vercel deploy without
  object storage.
- 108 files are uncommitted as of this writing.

**Before deploying:**

1. `FIELD_ENCRYPTION_KEY` must be set or the process refuses to encrypt. It is
   declared in `settings.py`; setting the environment variable alone was
   invisible to Django until 25 Aug 2026 (§6).
2. `FRONTEND_URL` must be the public address, or registrar links point at
   localhost.
3. `send_queued_emails` must be scheduled — nothing drains the outbox by itself.
   This is how 143 messages accumulated unsent. On a serverless deployment
   nothing can run a management command on a timer, so
   `POST /api/tasks/send-emails/` behind `TASK_TOKEN` is the same drain over
   HTTP, driven by an external cron (§10). `GET /api/tasks/email-status/`,
   behind the same token, says whether that cron is actually running: messages
   waiting with `sent` at nought is a scheduler never set up, or stopped. It
   reports no secret and changes nothing.
4. `SECRET_KEY` must be set; production refuses the built-in one.
5. `manage.py seed_rules --publish` after any change to the rules themselves.
   A `RuleSet` holds its effects as JSON, so editing `seed_rules.py` changes
   what a *new* set contains and leaves the one in force untouched. The old
   version is superseded rather than overwritten, which is what keeps an
   earlier decision replayable.
6. `manage.py seed_policies` on a database that has only been migrated. Without
   it there are no rates, no deadlines and no rule set, so nothing can be
   priced — `migrate` installs none of them on purpose (§6).
7. `DATABASE_URL` must percent-encode the password and name the **pooler**
   host, not `db.<ref>.supabase.co` (§6). Session mode (5432) for migrations,
   transaction mode (6543) for the deployed function.

---

## 10. Where it is deployed

**Live at `https://dgg.nexauratechs.com`.** Frontend and Django are one Vercel
project (`deline-gotline-`, team `hammads-projects-47adac19`); `api/index.py` is
the WSGI entrypoint and `vercel.json` rewrites `/api/*`, `/admin/*` and
`/static/*` to it. The stable alias
`deline-gotline-hammads-projects-47adac19.vercel.app` is what the cron talks to,
deliberately: it survives the custom domain moving.

The domain is a Hostinger-managed zone. `dgg` is an ALIAS to
`cname.vercel-dns.com.`; every mail record (`@` and `khata` MX, SPF, DKIM,
DMARC) belongs to Hostinger and must stay untouched — `contact@nexauratechs.com`
is the address the portal sends from.

**Database.** Supabase Postgres, project `zstiqoqvovryhkytawzr`, region
`ap-northeast-1`. Reached through the pooler; see §6 for the two independent
reasons the direct host cannot be used from either a developer's machine or a
Vercel function.

**The region is Tokyo, and that is a decision to revisit before real students
use it.** The portal stores Social Insurance Numbers and bank account details
for Canadian students, and `ap-northeast-1` is Japan. Raised on 25 Aug 2026 with
the database holding two accounts and no applications — the cheapest it will
ever be to move — and the owner's answer was that this is a testing phase and
Supabase as it stands is enough. Recorded rather than re-argued: it is a
reasonable call for a client demo and a different question for a live intake,
and the cost of moving grows with every application filed. `ca-central-1` is the
Canadian region. Nothing in the code knows where the database is, so the move is
a new project, `migrate`, `seed_policies`, and a connection string.

**Two requirements files, held together by a test.** `api/requirements.txt` is
what the function installs and `backend/requirements.txt` is what a developer
does. `core.test_requirements` fails when they disagree, and names the two
packages that belong to one side only. `cryptography` is pinned explicitly in
both: `identifiers.py` imports Fernet directly and was relying on `supabase`
happening to pull it in.

**Email leaves the building on a cron.** Hostinger shared hosting
(`u510647961`) runs, every five minutes:

```
curl -sS -m 60 -X POST -H "X-Task-Token: …" \
  https://deline-gotline-hammads-projects-47adac19.vercel.app/api/tasks/send-emails/ \
  >> /home/u510647961/dgg-email-drain.log 2>&1
```

This line went missing at some point before 25 August 2026 and took every
outbound email with it; see §6. It is the whole delivery mechanism, it lives
outside the repository, and nothing in a deploy or a test suite touches it — so
**check it exists before believing email works.**
`GET /api/tasks/email-status/` answers that from inside the deployment.

Hostinger rather than Vercel because the project is on the Hobby plan, where
cron fires **once a day** — a student waiting a day to be told their application
was approved is not a queue that works. The endpoint refuses with 503 when
`TASK_TOKEN` is unset rather than falling through to a comparison of two empty
strings, which would leave anybody able to flush the office's mail queue.

**No fictional accounts in the production database.** `seed_policies` creates
none, deliberately: `seed_demo`'s are invented people sharing one published
password, which is fine on a laptop and is a set of live credentials on a public
site. The office's accounts are made by hand.

That leaves a gap worth naming, because it cost an afternoon: a correctly
deployed portal with an empty `User` table refuses every login with *"No active
account found with the given credentials"* — which reads as a broken deployment
and is in fact a working one nobody has an account on. **Seeding the office's
configuration and creating the first administrator are one step, not two.**
Until an admin exists, the only thing the portal can do is register students.

**Uploads go to Supabase Storage, bucket `dgg-documents`, private.** Never to
`MEDIA_ROOT`: on Vercel that is inside the function bundle, read-only and thrown
away on the next deploy, so a student would attach a transcript, be told it was
accepted, and the file would not exist. `STORAGES` picks `SupabaseStorage`
whenever `SUPABASE_SERVICE_KEY` is set, which is why local work needs nothing
configured.

The bucket is private because `DocumentView` already decides who may read a
document; the backend signs its own URLs. A public bucket would widen access and
buy nothing.

Getting there took three separate faults, and the order they surfaced in is the
point — each one hid the next:

1. `SUPABASE_URL` was empty. From inside the storage client that is
   `[Errno 16] Device or resource busy` out of httpx, which names nothing.
2. The `service_role` key was signed by a different project's JWT secret:
   `403 signature verification failed`. The keys were rotated the same morning.
3. **`SupabaseStorage._open` raised `NotImplementedError`** — and had since the
   class was written. Uploads returned 201, the object really was in the bucket,
   and opening one was a 500 *on the deployment only*, because every test and
   every developer runs on `FileSystemStorage`, where reading works perfectly.

The third is the one worth remembering. It is the same defect as "uploaded
documents could never be opened again" and "attached documents could not be
opened, again" — the third time this project has shipped a document store that
only writes, and the first two were both found by a person clicking a link.
`core.test_supabase_storage` now drives the class directly against a stubbed
client, including a save-then-open round trip: opening a name the test invented
proves nothing about what `_save` actually wrote.

---

## 9. How the owner wants this worked on

Stated repeatedly, and worth honouring:

- **Write, test, rewrite, test again** — do not move to the next thing until the
  current one passes. Asked for explicitly and by name ("use your looping
  skills").
- **Delete what is not needed.** Dead files, dead models, dead CSS.
- **Do not decorate a broken thing.** The rebuild happened because the previous
  approach was to make the existing mess presentable.
- **Report failures honestly**, including one's own. Several entries in §6 were
  mistakes made during this work and found by testing rather than by review.
