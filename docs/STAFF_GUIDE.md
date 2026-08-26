# DGG Student Funding — Staff Guide

For the people who assess applications: student support workers, the Director of
Education, and administrators. Finance and account administration are in
[ADMIN_GUIDE.md](ADMIN_GUIDE.md).

Written against the code as it stands. Where the portal does not do something
the office might reasonably expect, §10 says so rather than leaving it to be
discovered.

Last rewritten: 23 August 2026.

---

## 1. Signing in

One door for everybody: **`/signin`**. There is no separate staff login. Your
role decides what the portal shows you and what the API will let you do; signing
in as a support worker takes you to the queue, signing in as a student takes you
to the student's dashboard.

Accounts are created two ways, and neither is a screen in the portal:

- **Students** create their own at `/register`, after answering the six
  eligibility questions.
- **Staff accounts** are made at the command line
  (`manage.py createsuperuser`, which creates an administrator) and then given
  the right role by an administrator on the **People** page. See the admin
  guide, §2.

There is no password reset flow and no "invite a colleague" screen. A forgotten
staff password is reset with `manage.py changepassword <email>`.

---

## 2. What each role may do

Roles are `student`, `support_worker`, `director`, `finance`, `admin`. The
capabilities are named for the action rather than the job title
(`accounts/api/permissions.py`), and the portal only shows a button where the
API would allow the act.

| | support worker | director | finance | admin |
|---|---|---|---|---|
| See every application | ✓ | ✓ | ✓ | ✓ |
| Mark reviewed, request information | ✓ | | | ✓ |
| Request/reissue an enrolment confirmation | ✓ | | | ✓ |
| Forward to the Director | ✓ | | | ✓ |
| Approve / decline | | ✓ | | ✓ |
| Preview an award | ✓ | ✓ | | ✓ |
| Record an award (pricing) | | ✓ | | ✓ |
| Set an award breakdown by hand | | | | ✓ |
| Edit a filed application | | | | ✓ |
| Attach a guest application to an account | ✓ | | | ✓ |
| See funding rates | ✓ | ✓ | ✓ | ✓ |
| Change a funding rate | | | | ✓ |
| See the People directory | ✓ | ✓ | ✓ | ✓ |
| Change a role, close an account | | | | ✓ |
| Payment run | | | ✓ | ✓ |

An administrator holds every capability, which is deliberate: the office is
small, and a role that can do everything except the one thing needed today is a
role people work around.

**Nobody sees a bank account number or a Social Insurance Number on any screen.**
Staff see `••••3210` and `•••••996`. Reading a full SIN is possible only from a
Django shell (`funding.services.identifiers.reveal`), which demands a reason and
writes an audit entry before returning anything — there is no endpoint and no
button (§10).

---

## 3. Getting around

The sidebar is built from your role.

| Destination | Who sees it | What it is |
|---|---|---|
| Home | everyone | Queues, money, flags |
| Applications (`/review`) | support worker, director, admin | The queue |
| Notifications | everyone | Your own notices only |
| Payments | finance, admin | The payment run |
| Policy rates | all staff | Rates, and the rule-set versions |
| People | all staff | The account directory |
| Printable forms | everyone | Blank forms to fill in by hand |
| Help & FAQ | everyone | Office contact details |

Staff have no `/applications` entry: that route is the *student's* list of their
own applications. It used to be reachable by staff who arrived by another route,
and read as a plausible but wrong queue.

---

## 4. The Home screen

Three queues and two flags, all scoped to applications that are still open, so a
number here can always be brought down by doing work.

- **To review** — status `submitted`. Links to the queue filtered to it.
- **Awaiting decision** — forwarded, waiting on the Director.
- **Awaiting enrolment confirmation** — a registrar has been asked and has not
  answered. Nothing can be awarded for tuition on these.

Then **Awarded / Awaiting payment / Paid**. "Awarded" counts only the pricing in
force on applications that have actually been approved — a pricing on an
application still under review is not money the office has committed to.

**By funding stream** divides the applications across the three pots — PSSSP,
UCEPP and DGGR — with how many of each are still open. Each one opens the queue
filtered to that stream. All three are listed whether or not anything is in
them: UCEPP is assigned by nothing, so its row is always nought, and that is
worth seeing rather than hiding. A stream outside the three — which nothing in
the portal creates, but a database can hold — is counted so the rows still add
up, and is shown without a link, because the queue cannot filter on it.

**These are counts, not money, and there is no money split by stream.** An award
line does not belong to a stream and could not be made to: pricing draws on
every stream the applicant qualifies for, and DGGR tops up rather than replaces,
so a PSSSP application routinely carries DGGR money. A figure here labelled DGGR
would read as what DGGR paid, and it would not be that. What a stream tells you
is which deadline the submission was measured against.

**Needs a look** shows `submitted late` and `residency mismatch`.

**Residency mismatch** is an application whose answers disagree with each other:
the applicant said at sign-up that they do **not** live in the Northwest
Territories, and the address on the application is in the Northwest Territories.
The application is not blocked and nothing about the award changes — it is asking
you to look. Open it and the reason is stated in full on the application screen.

Somebody who answered *"Not yet — I am moving there"* is not flagged: an NWT
address is what you would expect from them. Neither is a student who says they
live in the NWT, whatever address they give — a student studying away may
reasonably give one elsewhere, and a flag that fires on ordinary applications is
a queue that cannot be cleared. If you correct the address through the amendment
path, the flag is re-decided: it clears if the answers now agree.

---

## 5. The queue

`/review`. One request, filtered in the database. Filter by status, by
application type and by funding stream; the list pages at 50.

The filters are in the address, so a filtered queue can be bookmarked or sent to
a colleague, and the tiles on the home screen arrive here already filtered. A
value in the address that no filter offers is ignored rather than passed to the
server.

Each row: applicant, type, status, submitted date, awarded total, the enrolment
badge, and flags. The enrolment badge is on the row on purpose — an application
whose institution has not confirmed cannot be forwarded or approved, and it is
worth knowing that without opening it.

Click the applicant's name to open the application.

---

## 6. Working an application

`/review/{id}`. Top to bottom: actions, award, payment, enrolment, any request
for more information, documents, answers, history.

### The actions offered

The buttons come from the same table the server enforces
(`funding/services/workflow.ALLOWED_ACTIONS`, emitted into the frontend as
`NEXT_ACTIONS`), so what you are offered is what will be accepted.

| Current status | What may follow |
|---|---|
| Submitted | Mark reviewed · Request more information · Decline |
| Under review | Request more information · Forward to Director · Approve · Decline |
| More information requested | (the student answers) · Decline |
| Awaiting decision | Approve · Decline · Request more information |
| Approved | Send to finance — recorded by the payment run itself |
| Declined | nothing |
| Sent to finance | nothing |

Two rules behind that table:

- **Approving straight from `submitted` is refused.** A support worker's review
  comes first (§13 of the policy).
- **A decision does not require forwarding.** An administrator may approve or
  decline a reviewed application directly. Forwarding tells the Director an
  application is *waiting for them*; forwarding and then deciding it a second
  later was a lie the screen used to tell. When an administrator decides, the
  Director is told anyway.

### Requesting more information

The portal will not send the request until you have typed what you need. The
note reaches the student by email and in the portal, and it is the only thing
they have to act on — without it the notice reads "Please review your
application", which is a request to guess.

The student can then correct answers and attach or replace documents on their
own application, and it returns to `under_review` with an `Information received`
event. That is the only write a student may make to a filed application.

**Declining also requires a reason,** for the same reason: it is carried into
what the applicant is told.

### The enrolment verification (was Form B)

Admission and continuing-funding applications fund tuition, and **tuition is
funded against the registrar's figure, never the student's estimate.**

- The request goes out automatically on submission. **Both forms ask the
  student for the registrar's address**, so this no longer depends on what the
  office already holds. On the renewal the box arrives pre-filled from the
  student's profile, or from the last application that named one, and the
  student confirms or corrects it — a correction is the address that gets the
  email.
- The card distinguishes **not requested** from **not required**. "Not
  requested" is the one that needs doing. Since both forms ask, you should now
  only see it on a renewal filed before August 2026, or where the request could
  not be queued.
- Enter the registrar's address and press **Request confirmation**. Leave it
  blank to write to the address already on file again — that covers a bounced
  address and an expired link.
- The link is single-use and valid for **30 days**. A registrar needs no
  account.
- Until it comes back confirmed, **Forward** and **Approve** are refused with a
  409 naming the enrolment as the blocker. Declining is not blocked: an
  application that will never be approved should not be held open waiting on a
  registrar who may never answer.

### The award

- **Preview** prices the application without recording anything — every rule that
  applied, with the amount and the reason, and every rule that did not, with why
  not. Support workers and the Director can both preview.
- **Record award** (Director or administrator) writes an `AwardDecision`. It
  **supersedes** any earlier one rather than overwriting it, so an appeal can be
  argued against the figures that were in force.
- Re-pricing an approved application is allowed until the money goes out.
  Re-pricing a **declined** application is refused — there is nothing to price —
  and so is re-pricing one whose award has already been dispatched, because the
  fresh lines would be offered to the payment run a second time.
- If a rate the rules need is missing, the pricing is refused and the missing
  rate keys are named on screen. Set them on Policy rates.
- A recorded pricing on an application that is not yet approved is labelled as
  such: *"Nothing has been awarded yet."* A pricing is not a promise.

### The approval letter

Once an application is approved and priced, **Approval letter** on the Award
card opens the office's own letter, filled in — the same one the student is
sent. **Download PDF** gives you the letter as a file to keep, print or forward;
**Print** sends the page straight to the printer.

- **It goes out by itself, whichever order you work in.** Price and then
  approve, and the letter is in the body of the approval email. Approve and
  then price, and it is sent on its own the moment you record the award —
  there is nothing to describe until then. Nobody has to send it, and a student
  who cannot sign in still has it.
- **Re-pricing sends a corrected one.** So does setting the breakdown by hand.
  The student is holding a letter with the old figures on it, and it says the
  new one replaces it.
- **One approval can produce two letters.** DGGR tops up rather than replaces,
  so a semester funded under PSSSP with a DGGR top-up produces the CDFN letter
  and the DGGR letter. Each carries only its own programme's money, and together
  they account for the whole award.
- **Semester funding only.** All three templates describe program costs and a
  monthly allowance for a term. A travel claim or a graduation bursary has
  neither and the office has supplied no template for them, so the screen says
  so rather than producing a letter that does not fit.
- **Nothing on it is typed here.** Every figure is the award's; the caps quoted
  are the policy rates. Correcting a rate on Policy rates corrects the letter.
- **The student gets the PDF too**, attached to the approval email, as well as
  the letter in the body of the message.
- **The Director's name is a deployment setting** (`DIRECTOR_NAME`), so a change
  of post does not need a release.

**Edit breakdown** (administrators only) sets the lines by hand — for a fee no
rate covers, or something the office agreed at the counter. See the admin
guide, §5.

### Payment card

Says only whether an account is on file, and shows `••••3210`. A missing bank
account is what holds an approved award out of the payment run, so it is worth
seeing here rather than discovering at dispatch.

### Documents

Click the filename to open it. Documents are served through a permission-checked
endpoint, not a public media URL — a stranger gets a 404, because the existence
of a document is itself something they should not learn.

### Answers, identifiers, history

Answers are shown grouped by section, labelled with the question as it was
asked. Expense tables render as tables; multi-file answers say how many files.
Encrypted identifiers show their last three digits. History lists every event
with who did it, when, and any note — including `Amended` entries when the
office corrected the application.

---

## 7. What the student keeps on file

Students have a **profile** (`/profile`) that staff do not see and cannot edit.
It matters to your work in three ways.

- **Forms arrive pre-filled from it.** Where they study, their programme dates,
  their student ID and their registrar's address are typed once and carried into
  every later application. The student can still change any of it on the form,
  and the server validates what comes back exactly as if it had been typed — a
  pre-filled answer carries no more authority than a typed one.
- **The registrar's address on the profile is what pre-fills the renewal.** The
  renewal asks for the address itself now, so a student who keeps it on their
  profile confirms it rather than typing it each semester. It used to be carried
  silently from the last application, which meant somebody whose admission was on
  paper had nothing to carry and the enrolment request was skipped without a
  word — that is closed. Keeping the profile current is still the difference
  between confirming a box and retyping one.
- **Students can re-answer the six screening questions.** This is how somebody
  tells the office they have started receiving SFA, which withdraws both C-DFN
  streams from their *account* from that point on. It does not touch any
  application already filed, and it cannot change what the streams are — the
  student supplies answers, the office's rule decides. Every re-answer is
  written to the audit trail with what changed and what it changed the streams
  to.

Staff correct a *filed* application through the amendment path (§6), where the
change is attached to the application it affects and the applicant is told. There
is no screen for editing somebody else's profile.

---

## 8. Guest applications

The graduation bursary and the practicum award can be claimed with no account at
all, from `/apply-once/{type}`. They arrive in the queue like anything else, with
no student attached.

Once the person has a portal account, staff can link the two — which also moves
the bank details they gave onto their account, so finance stops reporting them
as having none. **This exists in the API only** (`POST /api/applications/{id}/attach/`)
and has no screen (§10).

---

## 9. Notifications

Your own only. There is no way for staff to read another person's notices; the
application's history is where you look to see what happened to it.

Staff are notified when an application is forwarded to them, when a student
provides information that was asked for, and when an administrator decides an
application without forwarding it.

Notices carry a `kind`, so what a notice *is* never depends on words in its
title.

---

## 10. What this portal does not do

Recorded because the previous version of this guide described several of these
as though they existed.

- **No duplicate detection.** Nothing hashes applicants or flags two accounts as
  the same person. There is no Duplicates tab.
- **No approve-by-email.** The Director decides in the portal. The only
  tokenised email link in the system goes to a registrar for the enrolment
  verification.
- **No appeal escalation ladder.** An appeal is filed as its own application and
  worked like any other.
- **No Excel export.** The payment run produces a CSV; approval letters and the
  annual report are PDFs. The annual report is on **Reports**, which Finance,
  the Director and administrators see — see the admin guide, §6b.
- **No deadline editor.** `ApplicationDeadline` rows decide whether a submission
  is late, and nothing but `seed_demo` and the Django shell can create one. No
  deadline reminders are sent.
- **No back-pay generation** for a late approval, and no "director approves a
  late submission" path — the columns exist and nothing writes them.
- **No screen for the audit trail.** `AuditEntry` rows are written for
  amendments, hand-set awards, attachments, role changes, rate changes and
  dispatches, and are readable only from the database.
- **No staff-created applications.** Staff cannot file a form on a student's
  behalf; they can correct one after it is filed (admin only).
- **No staff view of a student's profile.** Students maintain their own (§7).
  What the office needs to see about an application is on the application.
- **No SIN reveal in the portal.** Shell only, with a reason, audited.
- **Uploads live on local disk.** They will not survive a deploy without object
  storage.

---

## 11. When something looks wrong

| Symptom | What it means |
|---|---|
| "Forward" and "Approve" refused with a 409 | The institution has not confirmed the enrolment. Check the enrolment card. |
| The enrolment card says *not requested* | Nobody has been asked. Enter the registrar's address and request it. |
| The registrar says their link does not work | Single use, 30 days. Send the request again. |
| Recording an award reports missing rates | The named rate keys are unset. Policy rates → set them. |
| An award never reaches the payment run | The student has no bank account on file, or the applicant asked for the money to go to somebody else. Both are reported as blocked on the payment run. |
| A student says they got a notice saying nothing | An older record from before notes were required. Ask again with a note. |
| Nobody is receiving email | The outbox is not being drained. See the admin guide, §7. |
