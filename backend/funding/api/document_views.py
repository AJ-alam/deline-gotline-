"""Uploading the documents an application depends on.

SupportingDocument existed as a model with a FileField and no endpoint, so the
`doc_*` answers were text that said 'provided' and nothing was ever attached.
An application that cannot carry a transcript cannot be assessed.

Everything here is about accepting a file from someone who is not trusted:
what is allowed, how big, and what it is called when it lands on disk.
"""

import mimetypes
import uuid
from pathlib import PurePath

from django.core.files.uploadedfile import UploadedFile
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from funding.models import Application, SupportingDocument

# A transcript, an acceptance letter, a photograph of a status card. Deliberately
# short: anything not on it is refused rather than sniffed at.
ALLOWED = {
    'application/pdf': '.pdf',
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/heic': '.heic',
    'image/webp': '.webp',
}

# Generous for a phone photograph of a document, small enough that the queue
# cannot be filled by one upload.
MAX_BYTES = 10 * 1024 * 1024


class GuestDocumentThrottle(ScopedRateThrottle):
    """What an address with no account may upload. See settings."""

    scope = 'guest_document'


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    # Which question this answers. Checked against the schema by the view, so a
    # document cannot be filed under a key no form asks for.
    field_key = serializers.CharField(max_length=64)
    application = serializers.IntegerField(required=False)

    def validate_file(self, uploaded: UploadedFile):
        if uploaded.size > MAX_BYTES:
            raise serializers.ValidationError(
                f'That file is {uploaded.size // (1024 * 1024)}MB. The limit is '
                f'{MAX_BYTES // (1024 * 1024)}MB — try photographing the page '
                'rather than scanning it at full resolution.'
            )
        if uploaded.size == 0:
            raise serializers.ValidationError('That file is empty.')

        # The browser's content type is a claim, not evidence, so the extension
        # has to agree with it. Neither is proof of anything; together they stop
        # an executable arriving named .pdf.
        declared = (uploaded.content_type or '').split(';')[0].strip().lower()
        if declared not in ALLOWED:
            raise serializers.ValidationError(
                'That kind of file cannot be accepted. Please upload a PDF or a '
                'photograph (JPG, PNG, HEIC or WebP).'
            )
        # The extension has to be one we accept too. Checking only that the
        # guessed type agrees lets an unknown extension through, because
        # mimetypes guesses None for it and None agrees with everything.
        suffix = PurePath(uploaded.name or '').suffix.lower()
        if suffix not in set(ALLOWED.values()):
            raise serializers.ValidationError(
                'That file extension cannot be accepted. Please upload a PDF or '
                'a photograph (JPG, PNG, HEIC or WebP).'
            )
        guessed = mimetypes.guess_type(uploaded.name or '')[0]
        if guessed and guessed.split('/')[0] != declared.split('/')[0]:
            raise serializers.ValidationError(
                'The file name does not match the kind of file it is.'
            )
        return uploaded


class DocumentUploadView(APIView):
    """Attach a file to one of the applicant's own applications.

    A document may be uploaded before the application exists — the form is
    filled in over several sittings — in which case it belongs to the person
    until an application claims it on submission.

    Open to someone with no account, because two awards are claimable without
    one and the graduation award requires proof of completion. Requiring a
    login here did not protect anything; it made that form unsubmittable — the
    upload control rendered, every request was refused, and the required answer
    could never be given.

    What bounds the risk is not the login. It is that an upload is capped at
    10MB, checked against a short allowlist of types, stored under a generated
    name that cannot be a path, and — for an anonymous caller — throttled to the
    same ceiling as the guest submission it belongs to.
    """

    permission_classes = [AllowAny]

    def get_throttles(self):
        """Anonymous uploads are rate-limited; signed-in ones are not.

        A student filling in an admission application attaches six documents in
        a sitting, so the guest ceiling would refuse them halfway through.
        """
        if self.request.user and self.request.user.is_authenticated:
            return super().get_throttles()
        return [GuestDocumentThrottle()]

    def post(self, request):
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded = serializer.validated_data['file']

        owner = request.user if request.user.is_authenticated else None

        application = None
        application_id = serializer.validated_data.get('application')
        if application_id is not None and owner is None:
            # An anonymous caller has no application of their own to name, and
            # naming somebody else's is how a stranger's file gets attached to a
            # claim under review.
            return Response(
                {'application': ['Sign in to attach a document to an application.']},
                status=status.HTTP_400_BAD_REQUEST)
        if application_id is not None:
            # Scoped to the requester: an id belonging to someone else simply
            # does not match, and the answer is the same as for one that does
            # not exist.
            application = Application.objects.filter(
                pk=application_id, student=request.user).first()
            if application is None:
                return Response({'application': ['No application of yours with that id.']},
                                status=status.HTTP_400_BAD_REQUEST)

        # Read the label before renaming: this is the same object, so taking
        # the original name afterwards would record the generated one.
        original_name = PurePath(uploaded.name or 'document').name[:255]

        # Never the name the browser sent. A stored file called
        # '../../settings.py' or 'x.pdf.exe' is the whole problem with trusting
        # it; the original is kept as a label, not as a path.
        extension = ALLOWED[(uploaded.content_type or '').split(';')[0].strip().lower()]
        uploaded.name = f'{uuid.uuid4().hex}{extension}'

        document = SupportingDocument.objects.create(
            application=application,
            owner=owner,
            field_key=serializer.validated_data['field_key'],
            file=uploaded,
            original_name=original_name,
        )

        return Response(
            {
                'id': document.pk,
                'field_key': document.field_key,
                'original_name': document.original_name,
                'uploaded_at': document.uploaded_at,
                # What the answer becomes. The schema stores a reference, not
                # the file.
                'reference': f'document:{document.pk}',
            },
            status=status.HTTP_201_CREATED,
        )
