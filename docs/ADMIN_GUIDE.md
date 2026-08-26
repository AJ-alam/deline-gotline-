# DGG Student Funding — Administrator & Finance Guide

For administrators (`admin`), Finance (`finance`), and whoever runs the
deployment. Day-to-day assessment work is in [STAFF_GUIDE.md](STAFF_GUIDE.md);
the design and its reasons are in [PROJECT_STATE.md](PROJECT_STATE.md).

Written against the code as it stands. §9 lists what the portal does not have,
because the previous version of this guide described several things that were
never built.

Last rewritten: 23 August 2026.

---

## 1. What an administrator can do that nobody else can

Everything a support worker and the Director can do, plus:

- change a **funding rate**, and suspend one;
- change somebody's **role**, and close or reopen an account;
- **edit a filed application** on the applicant's behalf;
- **set an award breakdown by hand**;
- open the **payment run** (shared with Finance).

Each of these either changes what somebody is paid or changes who may decide
that, so each is restricted to `admin` and each writes an `AuditEntry`.

---

## 2. Accounts and roles

**People** (`/people`). All staff can search it; only an administrator can
change anything.

- **Search** by name, email or beneficiary number. Tick *Include closed
  accounts* to see deactivated ones.
- **Change a role** from the dropdown on the row. Django admin-site access
  (`is_staff`) follows the role rather than being set separately, so the two
  cannot disagree about who is privileged.
- **Close an account** rather than deleting it. Nothing is ever deleted:
  decisions, events and audit entries name the person who made them, and
  removing the row would leave a funding decision signed by nobody.

Three refusals are enforced in the service, not the screen
(`accounts/services/administration.py`):

1. You cannot remove your own administrator access.
2. You cannot deactivate your own account.
3. The **last** active administrator cannot be demoted or deactivated — an
   office with nobody able to grant access has to go to a database console to
   recover.

The screen shows the server's own wording for a refusal, because the reason tells
you what to do instead.

### What a student may change about themselves

Students maintain their own profile (`/profile`), which no staff screen shows.
Three parts of it touch the office:

- **Their details** — name, contact, address, beneficiary and treaty numbers.
  Not the email they sign in with, and not their role.
- **The six screening answers.** Re-answering them re-runs
  `eligibility.assess` and re-decides the account's funding streams. The client
  supplies answers only: the streams are the office's rule applied to them, and
  a request that names its own streams is ignored. An outcome of "nothing"
  is recorded rather than refused — that is usually a student telling us they
  have started receiving SFA — and their next submission is then refused with a
  409 pointing them at the office. Nothing already filed is affected.
- **Their bank account**, which writes the same `BankAccount` record the payment
  run reads.

Both of the last two write an `AuditEntry` (`account.screening_updated`,
`account.banking_updated`), because both change what somebody is paid and both
are edited by the person being paid. Neither entry contains an account number.

The two eligibility booleans (`is_indian_act_registered`,
`is_deline_beneficiary`) are read-only on `/api/me/` and move only with the
screening: `streams.saved_streams` falls back to them on accounts opened before
the tags existed, so a student who could PATCH one could hand themselves PSSSP
without the screening ever running.

### Creating a staff account

There is no screen for this. Registration at `/register` creates **students
only** — the role is read-only on that path.

```bash
cd backend
./venv/Scripts/python.exe manage.py createsuperuser     # creates an administrator
./venv/Scripts/python.exe manage.py changepassword <email>
```

Then set the intended role on **People**. To onboard a support worker: create
the account as above, then change its role from Administrator to Student Support
Worker.

---

## 3. Funding rates

**Policy rates** (`/policy`). Every award is computed from these. All staff can
read them — a support worker explaining an amount needs to see the rate behind
it — and only an administrator can change one.

Every rate comes from the DGG Bursary & Awards Program Procedure (§7–§9). The
figures seeded during the rebuild were placeholders and are gone.

- **Change** sets a new value. Leave *Takes effect* blank for today, or give a
  future date.
- **A change never alters a decision already made.** An application is priced
  under the rates and the rule set in force when it was priced.
- **A no-op is refused** — saving the value a rate already has would write a
  history entry recording nothing.
- **History** lists every change with the old value, the new value, the
  effective date and who made it.
- **Suspending** a rate (`is_active = false`) keeps its history.
- The unit is derived from the key (`policy_admin.unit_for`), so a percentage
  displays as `80%` and not as `$80.00`. That was a real bug on the one screen
  where administrators change what students are paid.

**A missing rate does not award zero — it refuses.** Recording an award names
the missing rate keys on screen so the gap is fixable without reading logs.

### Rule sets

The same page lists **policy versions**. A `RuleSet` stores each rule's effect as
JSON in the database, deliberately, so a decision stays replayable against the
rules that governed it.

The consequence catches people out: **editing `seed_rules.py` does not change
the rule set already in force.** Publishing a new version is the migration.

```bash
./venv/Scripts/python.exe manage.py seed_rules --publish
./venv/Scripts/python.exe manage.py seed_rules --publish --effective-from 2026-09-01
```

The old version is superseded rather than overwritten, which is what keeps an
earlier decision replayable. There is no publish button in the portal (§9).

---

## 4. Editing a filed application

**Edit application**, top right of the application screen. Administrators only —
not the support workers who assess applications, because somebody who can both
rewrite the answers and advance the application can price whatever they like
without a second person seeing it.

- Refused once the application is **decided**: its answers are the record the
  decision was made from, and rewriting them leaves an award defended by answers
  that were never priced.
- The form opens on the stored answers, through the same renderer and the same
  schema validation as a submission. Documents can be added, replaced or removed
  in place.
- The SIN and the four banking fields are split off exactly as on a submission.
  They open blank because they are never returned; **blank means unchanged.**
- Answers the schema does not define — such as the `confirmed_tuition` the
  registrar wrote — are carried through untouched and never taken from the
  client, so an edit cannot raise the tuition an award is funded against.
- **The note is not decoration.** It is what the applicant is shown, and what the
  audit entry carries: *"corrected the campus, confirmed by phone"* is a record;
  *"amended"* is not.
- An amendment is an event, not a transition: the application stays exactly
  where it sits in the queue. If it is sitting with the Director, the Director is
  told it changed under them.

---

## 5. Setting an award by hand

**Edit breakdown**, on the Award card. Administrators only.

The rules price the ordinary case. They cannot know that an institution charges
a fee no rate covers, or that the office agreed something at the counter — and
the only other ways to express that were to edit a policy rate, which changes
what every student is paid, or to pay the wrong amount.

- Opens on whatever is currently awarded, so the office corrects rather than
  retypes. Rows can be added and removed; the total is added up on screen and
  again on the server, from the same lines.
- Categories come from the server (`tuition`, `living`, `books`, `travel`,
  `bursary`, `scholarship`, `back_pay`).
- Recorded as a decision like any other: it supersedes rather than overwrites,
  and every line says who entered it.
- **Refused once any of it has been paid**, and refused on a declined
  application — there is nothing to break down.

---

## 5b. Reading a full SIN or bank account

**Show full details**, on the Payment card and beside the identifiers on the
application screen. Administrators only.

The application screen masks both by default — `•••••996`, `••••3210` — and that
does not change. What is new is that the real values can be read at all: the
service behind this had unit tests and no endpoint, so until 27 August 2026 the
whole number was unreadable from the portal by anybody, including the
administrator doing the federal PSSSP return the number is collected for.

- **One click, no typed justification.** The office asked for these to be
  visible; a reason box demanded on every read is a box that fills with a full
  stop.
- **Every read is recorded** — one `AuditEntry` for the identifier and a
  separate one for the banking, naming you, the applicant and the time. Two
  entries rather than one, so the log can answer "who has seen this person's
  SIN" on its own.
- **Only administrators.** Not the support workers who assess applications, and
  not Finance — the payment file already carries the account they need.
- **Opening the application screen records nothing.** The masked values are on
  the detail response; the real ones are a separate, deliberate act.
- The bank details come from the `BankAccount` record the payment run reads, not
  from the application's answers, where they deliberately no longer live. A
  guest claim with no account behind it shows the details held encrypted against
  the application instead, marked as held.

---

## 6. The payment run

**Payments** (`/payments`). Finance and administrators. The people who assess an
application are not the people who release the money; keeping those apart is the
ordinary control on a funding body.

The screen shows what is ready, and what is blocked, **before** anything is
committed.

An award reaches the run when its application is `approved` or `sent_to_finance`
and the award line is `pending` under the decision **currently in force**. Lines
from a superseded decision are excluded — otherwise an application priced twice
would be paid twice.

### Why an award is blocked

| Reason | What to do |
|---|---|
| The student has no bank account on file | **Should no longer happen on a new application.** Every form that pays now asks for a bank account, so this means the application was filed before 27 August 2026 — three forms that pay money (`continuing_funding`, `academic_scholarship`, `hardship_bursary`) used to ask for none. To clear it: the student saves their payment details on their own profile, or an administrator edits the application and fills them in. The run caches nothing, so the award is offered for payment as soon as the account exists. On a very old database, `purge_banking_answers` moves details that were left in `answers`. |
| No student is attached to this application | A guest application. Attach it to an account (§8). |
| Payment was requested to another person | The graduation claim's release-of-funds tick. Nothing here can pay a third party; the office arranges it. What authorises a release is still an open question (§9). |
| Not attached to a pricing decision | Should not occur. Re-price the application. Reported rather than dropped, because money must not vanish quietly. |

### Dispatching

**Send N awards to finance** builds the CSV, hands it to the browser, and in the
same transaction:

- assigns each award its permanent reference (`DGG-YYYYMMDD-000123`) if it has
  none — a reference that changes is not a reference;
- marks every dispatched award **PAID**;
- moves each approved application to `sent_to_finance`, through the workflow, so
  the transition is an event like any other;
- writes an audit entry.

The selection is locked, so two people pressing the button at the same moment
cannot send the same award twice. Blocked awards stay pending and are named in
the result — never quietly excluded.

The file is one row per **application** — one amount to pay, once. It used to be
one row per award *line*, so an application priced across two streams and two
categories became four rows against one bank account; the office asked for the
opposite, which is to be told the amount to pay rather than the rules that
produced it. `Covers` keeps the categories as a readable list, so a reconciler
can still see what one payment is made up of without the file pretending to be a
ledger. Grouped by application rather than by student, because a student with
two funded applications is owed two payments that must each trace to the
decision behind them.

```
Reference, Student, Beneficiary number, Application, Amount, Covers,
Account holder, Transit, Institution, Account number, Approved on
```

The account columns are the same record shown on the payment screen — masked
there, whole here, because the file is what the bank acts on.

The run is manual. Nothing dispatches on a schedule, and no email is sent to
finance (§9).

---

## 6a. Approval letters

The office's three templates — DGG-CDFN (PSSSP), DGG-UCEPP and DGGR-SFSP — are
produced from the award itself and sent with the approval email. Staff open them
from **Approval letter** on the Award card.

- **Which letters an approval earns** follows the money, not the application's
  stream: a semester funded under PSSSP with a DGGR top-up produces both.
- **When it is sent** follows the award, not the approval. Priced first, it is
  in the approval email; approved first, it is sent when the pricing lands.
  Re-pricing and a hand-set breakdown both send a corrected letter, because the
  student is holding one with superseded figures.
- **The figures are the award's.** Nothing is retyped, and the caps quoted in
  the CDFN footnote and the UCEPP amount cell are the policy rates
  (`psssp_tuition.max_per_semester`, `ucepp_tuition.max_per_semester`).
  Correcting a rate corrects every letter printed afterwards. A rate that is
  unset drops the sentence rather than printing $0.00.
- **Settings:** `DIRECTOR_NAME`, `DIRECTOR_TITLE`, `DIRECTOR_EMAIL` for the
  signatory; `SUPPORT_ADDRESS` and `SUPPORT_PHONE` for the footer.
- **The PDF** is at `GET /api/applications/{id}/approval-letter/pdf/`, read by
  the same permission as the letter itself, and is attached to the approval
  email as well. It is generated from the same letter the portal shows — there
  is no second copy of the wording anywhere.
- **The fonts are shipped with the application** (`funding/assets/fonts`,
  DejaVu Serif, Bitstream Vera licence). They are not optional: reportlab's
  built-in fonts cannot render `Délı̨nę` and print black boxes instead. If the
  files are missing the endpoint answers 503 naming the problem rather than
  sending a letter with the government's name in squares.
- **Semester funding only.** A travel claim or graduation bursary produces no
  letter: the office has supplied no template for a one-off award. The endpoint
  answers 409 naming the reason.

---

## 6b. The annual report

**Reports** (`/reports`). Finance, the Director and an administrator.

The screen and the exported document are deliberately different. The office
reads the screen — a headline that reconciles, then one card per question it
actually asks. The head department reads the PDF, which is the formal report:
five ruled tables on the office letterhead. Reproducing those tables on screen
made a page nobody in the office could take anything from at a glance, which is
what the office said about the version before it.

**Export the annual report** produces the document. It is the same figures: the
screen computes nothing of its own, so the two cannot disagree.

### Narrowing to one funding programme

The chips above the figures narrow the **whole screen** — every card, not
just the breakdown — to one programme, and **the export follows the
filter**, so what you are looking at is what you send.

A narrowed export is a different document from the annual report and says
so: its first page states that it covers one programme only, and its
filename carries the programme (`DGG-annual-report-2026-dggr.pdf`). Send it
on without that and the head department reads one programme as the whole
year.

One figure does **not** divide by programme: the costs an administrator
enters by hand — staff wages and the like — are recorded for the year, not
against a programme. A filtered report shows the whole of them and labels
them so, which means the three filtered reports do not add up to the whole
year on that line. Everything paid to students does.

The fiscal year runs **1 April to 31 March**, as the office's own report title
does. The year picker takes the calendar year the fiscal year starts in.

### What is on it

- **Enrolment by semester**, split into university, college and trades school,
  with trades and upgrading counted *within* those totals rather than beside
  them. The total adds the seasons up, so it counts **enrolments**: a student
  who studied in two semesters appears in both. The headcount behind those
  enrolments is reported separately.
- **Graduate awards** by residency and credential.
- **Institutions attended**, with the programmes and how many students.
- **Funding by student number** — what each student received, identified by
  beneficiary number, which is what the head department reconciles against. A
  student with none on file is listed rather than dropped, so the rows still
  add up to the year. **A row is a number, not a person:** where two people
  hold one beneficiary number their funding is shown together on that
  number's row, and the screen and the document both say how many people
  that is. **Students funded** at the top of the screen is the headcount,
  not the number of rows.
- **Funding programme breakdown** — which of the three programmes paid for
  what. Read the two halves of it differently, because they are counted
  differently:
  - **Applications and students** are counted against the application's
    primary programme — the same column the review queue filters on.
  - **Money** is attributed to the programme whose *rule* paid it. Pricing
    draws on every programme an applicant qualifies for and DGGR tops up
    rather than replaces, so one application routinely spends from two
    programmes and appears in both. A programme showing money but no
    applications has topped up somebody else's.
  - **Not tied to one programme** is the bursaries, travel and
    scholarships, whose rules apply to everybody and name no programme.
    That money is reported on its own rather than guessed into one.
- **Financial summary** by category and season: **gross, repaid and net**.

### Reconciling against a financial statement

Money that comes back — a student withdraws, a cheque is returned — is recorded
as a repayment against the award it came from (`POST /api/reports/repayments/`,
administrator only). It never edits the award: `Award.amount` is what was
decided and what the approval letter already told the student. The report shows
what went out, what came back, and the difference.

A repayment must say why, and cannot exceed what was granted. Re-pricing an
application does not lose it: the money still came back.

### Costs the system cannot see

'Administration — Staff Wages/Benefits' and anything like it is entered by an
administrator on the Reports screen. Entering the same description again for the
same year **corrects** the figure rather than adding a second line. Any date
inside a fiscal year is taken as that fiscal year, so a figure entered against
15 June lands on the year beginning 1 April. Entered
costs are listed separately from the computed figures and added into the grand
total in the open, so the office can check the arithmetic.

### Not classified

University against college comes from the **registrar**, on the enrolment
verification. It is optional there on purpose — a reporting question must never
stop an institution confirming an enrolment — so enrolments confirmed before the
question existed, or where the registrar skipped it, are counted under **Not
classified**. The screen says how many. Nothing guesses it from the institution's
name.

---

## 7. Email

Outbound mail is queued in an `OutboundEmail` table and drained by a management
command. **Nothing drains it by itself** — this is how 143 messages once
accumulated unsent.

```bash
./venv/Scripts/python.exe manage.py send_queued_emails --limit 50
./venv/Scripts/python.exe manage.py email_status        # is mail configured and deliverable
```

Schedule `send_queued_emails` on any deployment. Settings:
`EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`.

Three failure modes worth knowing:

1. **An unscheduled worker.** Everything queues, nothing sends, nothing errors.
2. **The console backend on Windows.** Every message contains `Délı̨nę`; cp1252
   cannot encode it, so every message fails with `UnicodeEncodeError`.
3. **`FRONTEND_URL` wrong.** It is baked into the registrar's link at the moment
   the message is queued, so a wrong value sends registrars to a dead address.
   Vite is pinned to port 5173 (`strictPort`) for the same reason.

What the portal sends: application received (student, and a guest variant),
enrolment request to the registrar, more information requested, information
provided, decision approved/declined, application amended, amended while
awaiting decision, awaiting-decision notice to the Director, and a notice to the
Director when an administrator decided without forwarding.

---

## 8. Guest applications

The graduation bursary and the practicum award are claimed with no account. To
link one to a portal account afterwards:

```http
POST /api/applications/{id}/attach/
{ "student_id": 42 }
```

Staff only, and only onto an application with no owner — this is not for
reassigning an application away from the person who made it. Attaching also
promotes the bank details the guest gave (held encrypted against the
application) onto the account, so finance stops reporting them as having none.

**There is no screen for this.** Six backend tests, no UI (§9).

---

## 9. What this system does not have

- **No audit-log screen or endpoint.** `AuditEntry` rows are written for
  amendments, hand-set awards, attachments, role changes, rate changes,
  enrolment requests, dispatches, and a student's own screening and banking
  changes — and are readable only from the database.
- **No Excel export.** The payment-run CSV, the approval-letter PDF and the
  annual-report PDF are the exports (§6b).
- **No money split by funding stream.** The home screen divides the
  *applications* across the three pots and deliberately not the awards: an award
  line carries no stream, and pricing draws on every stream the applicant
  qualifies for, so no sum of money belongs to one of them. A per-stream budget
  would need the streams recorded on the award lines, which is a change to how
  awards are priced and not a change to a screen.
- **No scheduled or emailed finance report,** and no "confirm payments
  processed" link. Dispatch is what marks awards paid.
- **No duplicate detection.**
- **No approve-by-email for the Director.** The only tokenised link in the
  system goes to a registrar.
- **No appeal escalation ladder.** An appeal is its own application.
- **No deadline administration.** `ApplicationDeadline` decides whether a
  submission is late, and only `seed_demo` and the Django shell create one.
  No deadline reminders are sent.
- **No back-pay generation,** and no late-approval path — `late_approved_by` and
  `late_approved_at` have no writer.
- **The residency check flags one contradiction only:** declared not resident,
  address in the NWT. Saying yes and giving an address elsewhere is not flagged
  — see PROJECT_STATE §5 for why that was not assumed.
- **No rule-set publishing from the portal.** `seed_rules --publish` only.

- **No password reset flow,** for staff or students.
- **No staff view of a student's profile.** Students maintain their own; the
  office corrects a *filed application* through the amendment path, where the
  change is attached to the application it affects and the applicant is told.
- **A UCEPP application is priced by three living allowances at once.** If the
  office ever assigns UCEPP by hand, the student is paid `psssp_living`,
  `ucepp_living` and `dggr_living` for the same semester — the tuition rules
  share one balance and cannot double-fund, but the living rules do not. Nothing
  assigns UCEPP today, so this is latent; assigning one by hand makes it real,
  and the approval letter will state all three. See PROJECT_STATE §5.
- **UCEPP is never assigned automatically.** The screening question that would
  do it was added and removed at the owner's request. Do not re-add it without
  asking.
- **Uploads are local disk** (`MEDIA_ROOT`). They will not survive a Vercel
  deploy without object storage.

---

## 10. Running and checking it

```bash
cd backend
./venv/Scripts/python.exe manage.py migrate
./venv/Scripts/python.exe manage.py seed_demo        # refuses if applications exist
./venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000

npm run dev            # pinned to 5173
```

Demo accounts, all password `DemoPass123!`: `admin@dgg.test`,
`director@dgg.test`, `worker@dgg.test`, `finance@dgg.test`, `student@dgg.test`,
`student2@dgg.test`.

### Management commands

| Command | What it does |
|---|---|
| `seed_demo` | Demo accounts, rates, deadlines, a published rule set |
| `seed_policies` | The office's rates, deadlines and rule set — and nothing fictional. The production step |
| `seed_rules --publish` | Publish a new rule-set version — required after any rule change |
| `purge_applications` | Clear case data before a real intake. Reports by default; `--yes` writes |
| `send_queued_emails --limit N` | Drain the outbox |
| `email_status` | Report whether mail is configured and deliverable |
| `check_awards` | Applications priced more than once, and orphaned awards |
| `purge_banking_answers` | Move bank details out of `answers` onto account records |
| `prune_stale_answers` | Remove answers whose question a schema no longer defines |
| `generate_types --check` | Assert the TypeScript types match the schemas |

### Clearing a database before a real intake

`purge_applications` deletes applications and everything hanging off one —
events, awards, decisions, repayments, encrypted identifiers, document rows,
enrolment verifications — plus in-portal notices and the outbound email queue.
It never touches the office's configuration: the rates and their history, the
deadlines, the rule sets and the entered report costs all stay.

Reporting is the default. **Nothing is written without `--yes`**, and the banner
names the database it is pointed at every time, including on a dry run — the
difference between the local database and production is one environment
variable, so read that line before you read anything else.

```bash
# What would go, on whichever database DATABASE_URL names
manage.py purge_applications

# Case data goes; every account stays
manage.py purge_applications --yes

# Also delete student accounts the audit scripts invented. Staff always stay
manage.py purge_applications --drop-test-accounts --yes

# Cut down to a named set of accounts. Deletes staff. Report first, always
manage.py purge_applications --keep-only=admin@…,director@… --yes
```

`--keep-only` is refused if an address matches no account, and refused if no
active administrator would survive — nothing inside the portal can create the
next administrator, and a portal with no accounts refuses every login in a way
that reads as a broken deployment.

Two things it does not do. **The uploaded files are not deleted** — Django
removes the row and never the blob, so the objects stay in the Supabase bucket
and are reported so you can decide. And **an account's name comes off the
office's history**: a rate change or a staff-administration audit entry survives
the person who made it, with the "who" left blank. The command counts those
before it writes.

### Checks

```bash
npm run verify          # typecheck (tsc -b), lint, CSS, tests
npm run build
cd backend && ./venv/Scripts/python.exe manage.py test
```

`npx tsc --noEmit` checks **zero files** — `tsconfig.json` has `"files": []` and
only project references. Use `npm run typecheck`.

The twenty live audits in `backend/scripts/` drive real HTTP against a running
server and are the only thing on this project that has reliably found real bugs.
See PROJECT_STATE.md §7.

`readiness_audit.py` is the one to run before handing this to anybody. It walks
the whole money path in the order the office uses it and checks the joins
between the parts: every form that pays asks where to send it, the registrar's
confirmed tuition reaches the award, the award's own lines and the office's
stream split and the annual report's programme table all describe the same
money, the approval letters add up to the award as a page and a PDF and an
email, the payment run shows the account before releasing it and cannot send the
same money twice, and an administrator can read a full SIN and a full bank
account while nobody else can.

---

## 11. Before deploying

1. **`FIELD_ENCRYPTION_KEY`** must be set or the process refuses to start. It is
   deliberately not derived from `SECRET_KEY`: rotating `SECRET_KEY` would
   otherwise make every stored SIN unreadable.
2. **`SECRET_KEY`** must be set, at least 32 characters. Production refuses the
   built-in development key.
3. **`FRONTEND_URL`** must be the public address, or registrar links point at
   localhost.
4. **`send_queued_emails`** must be scheduled.
5. **`seed_rules --publish`** after any change to the rules themselves.
6. Object storage for `MEDIA_ROOT` if uploads must survive a deploy.

Support details shown on the public help page are settings, so a deployment can
correct them without a release: `SUPPORT_EMAIL`, `SUPPORT_PHONE`,
`SUPPORT_ADDRESS`.
