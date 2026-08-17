"""Opening a document somebody attached.

The upload endpoint existed and nothing could read what it stored. A reviewer
was shown the text `document:12` against the question it answered, and had no
way to open the transcript an assessment depends on — which is the same as the
document never having been attached.

Served through Django rather than by linking at MEDIA_URL. The stored name is a
uuid, so a link would be hard to guess, but hard to guess is not a permission
check: the file has to be refused to somebody it does not belong to.
"""

from django.http import FileResponse, Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from funding.models import SupportingDocument


class DocumentView(APIView):
    """One document, to the person it belongs to or to the office."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            document = SupportingDocument.objects.select_related(
                'application', 'application__student').get(pk=pk)
        except SupportingDocument.DoesNotExist:
            raise Http404

        user = request.user
        # Staff who review, decide or pay: an assessment is made from these.
        office = (user.reviews_applications or user.decides_applications
                  or user.handles_payments)
        # The person who uploaded it, or whose application carries it. Both,
        # because a document is uploaded before the application exists and
        # belongs to the person until a submission claims it.
        theirs = (document.owner_id == user.pk
                  or (document.application_id is not None
                      and document.application.student_id == user.pk))

        if not (office or theirs):
            # 404 rather than 403: whether a document exists is itself
            # something a stranger should not learn.
            raise Http404

        if not document.file:
            return Response({'detail': 'That document has no file stored.'}, status=410)

        # `as_attachment=False` so a PDF or a photograph opens in the browser
        # rather than downloading — a reviewer checking six documents should not
        # end up with six files on their desktop.
        return FileResponse(document.file.open('rb'), as_attachment=False,
                            filename=document.original_name)
