/**
 * How each long form is broken into steps.
 *
 * Its own module because it is shared: `Apply` renders from it and
 * `Steps.test.tsx` checks it against `APPLICATION_SECTIONS`, which the
 * backend generates from the schemas. A step map that names a section the
 * schema does not declare builds a step with no questions; a section no step
 * names is not rendered at all, and its questions leave the form in silence.
 */
import type { ApplicationType } from '../../api/schema.generated';

/**
 * Keyed by schema slug and naming sections, so a section renamed in the schema
 * shows up as a step that lost its questions rather than as questions that
 * vanished — and a section added without being listed still renders, on the
 * last step, rather than disappearing.
 */
export const STEPS: Partial<Record<ApplicationType, Array<{ title: string; sections: string[] }>>> = {
  admission: [
    { title: 'Student information', sections: ['Applicant', 'Address'] },
    { title: 'Program & institution', sections: ['Study', 'Registrar', 'Funding'] },
    { title: 'Bank deposit info', sections: ['Payment'] },
    { title: 'Documents & declaration', sections: ['Documents', 'Declaration'] },
  ],
  // Two steps, not four: the renewal is short because everything but this
  // term's answers is already on file and arrives pre-filled.
  continuing_funding: [
    { title: 'Information review', sections: ['Review your information'] },
    {
      title: 'Documents & declaration',
      sections: ['Upload required documents', 'Payment', 'Declaration'],
    },
  ],
  // Who and where, then what it cost, then how it is paid and signed. The
  // expenses and their receipts share a step because a line without a receipt
  // is not a claim, and putting them on separate steps hides that from the
  // person filling it in until it is too late to photograph anything.
  travel: [
    { title: 'Student & travel', sections: ['Student', 'Travel'] },
    { title: 'Expenses & receipts', sections: ['Expenses', 'Receipts'] },
    { title: 'Payment & declaration', sections: ['Payment', 'Declaration'] },
  ],
  // The three the office asked for: what is being appealed, why, and what
  // backs it up. Evidence and the declaration share the last step because the
  // signature is what submits the argument the evidence supports.
  appeal: [
    { title: 'Appeal context', sections: ['Student and academic context'] },
    { title: 'Detailed reason', sections: ['Reason for appeal'] },
    { title: 'Support & submission', sections: ['Supporting evidence', 'Declaration'] },
  ],
  // Three: which term the results are from, what the results were, and the
  // signature. The transcript sits with the grade it evidences rather than in a
  // documents step of its own — the band is awarded against the transcript, not
  // against the figure typed beside it.
  academic_scholarship: [
    { title: 'Program info', sections: ['Program information'] },
    { title: 'Achievements', sections: ['Achievements'] },
    { title: 'Payment & declaration', sections: ['Payment', 'Declaration'] },
  ],
  // Three, and the shortest of them first. Somebody filing this is having a
  // bad week: the questions that need thought are on their own step, and the
  // documents sit with the emergency they evidence rather than behind a fourth
  // page nobody reaches.
  emergency_relief: [
    { title: 'Your details', sections: ['Your details'] },
    { title: 'The emergency', sections: ['The emergency', 'Supporting documents'] },
    { title: 'Payment & declaration', sections: ['Payment', 'Declaration'] },
  ],
  // Four, in the order the office asks: still a student, what happened, what it
  // costs, and the signature. The attestation about being active in the
  // programme sits on the first step because it is a precondition — there is no
  // point describing an emergency to a bursary you cannot claim.
  hardship_bursary: [
    { title: 'Student info', sections: ['Student information'] },
    { title: 'Emergency case', sections: ['The emergency'] },
    { title: 'Fund breakdown', sections: ['Fund breakdown'] },
    { title: 'Payment & declaration', sections: ['Payment', 'Declaration'] },
  ],
  // Four, because a claim with no account behind it has to ask for everything
  // a student's record would already hold: who they are, where they are, what
  // they finished, and where the money goes.
  graduation_bursary: [
    {
      title: 'Personal info',
      sections: ['Student information', 'Current mailing address'],
    },
    { title: 'Graduation details', sections: ['Graduation details', 'Documents'] },
    { title: 'Banking & release', sections: ['Payment', 'Release of funds'] },
    { title: 'Declaration', sections: ['Declaration'] },
  ],
  // The three steps the office asked for. Payment rides on the last one: it is
  // two questions short of a step of its own, and it belongs beside the
  // declaration that releases the money rather than in front of the report
  // that justifies it.
  practicum: [
    { title: 'Employer & info', sections: ['Employer information', 'Student information'] },
    { title: 'Performance & roles', sections: ['Performance and roles'] },
    { title: 'Declaration', sections: ['Payment', 'Declaration'] },
  ],
};
