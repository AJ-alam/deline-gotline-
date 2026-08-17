"""How to reach the office, and the questions it is asked most.

Served rather than written into the client for the same reason every other
piece of content here is: an address in a React component is an address the
office cannot change, and the one thing a help page must never be is out of
date. The contact details come from settings so a deployment can override them
without a release; the questions live here so they are reviewed like code and
can move to a table the day the office wants to edit them itself.

Public, deliberately. Help is most needed by someone who cannot sign in.
"""

from django.conf import settings

# The office's own answers, checked against what the portal actually does. An
# answer that describes an intention rather than the behaviour is worse than no
# answer: it sends somebody to wait for an email that is not coming.
FAQ = (
    {
        'question': 'How is my enrollment verified?',
        'answer': (
            'When your application arrives we email your registrar a single-use '
            'link and ask them to confirm your enrolment and the tuition you '
            'have been billed. Your application cannot be forwarded or approved '
            'until that comes back, because tuition is funded against the '
            "institution's figure rather than an estimate. You do not need to do "
            'anything — the status on your application shows whether we are '
            'still waiting.'
        ),
    },
    {
        'question': 'How do I claim travel?',
        'answer': (
            'Open a travel claim from My applications and list each expense on '
            'its own line with what it cost. Attach every receipt — you can '
            'select several files at once — and we add the lines up for you; the '
            'total is not something you type. Travel is reimbursed against the '
            'receipts, up to the published maximum for the purpose of the trip.'
        ),
    },
)


def contact() -> dict:
    """Where to write, ring or post. Overridable per deployment."""
    return {
        'email': settings.SUPPORT_EMAIL,
        'phone': settings.SUPPORT_PHONE,
        'address': settings.SUPPORT_ADDRESS,
    }


def payload() -> dict:
    return {'contact': contact(), 'faq': [dict(entry) for entry in FAQ]}
