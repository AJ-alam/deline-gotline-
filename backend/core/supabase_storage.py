"""Uploaded documents, kept in Supabase Storage rather than on the function's disk.

`MEDIA_ROOT` on a serverless deployment is inside the function bundle: read-only,
and thrown away on the next deploy. A student would attach a transcript, be told
it was accepted, and the file would not exist.

Selected by `settings.STORAGES` whenever `SUPABASE_SERVICE_KEY` is set, so local
work stays on `FileSystemStorage` with nothing to configure.
"""

import os
import uuid
import mimetypes
from io import BytesIO

from django.core.files.base import File
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from django.conf import settings


@deconstructible
class SupabaseStorage(Storage):
    def __init__(self, bucket=None):
        self.bucket_name = bucket or getattr(settings, 'SUPABASE_STORAGE_BUCKET', 'dgg-documents')

    def _client(self):
        from supabase import create_client
        return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

    def _save(self, name, content):
        client = self._client()
        ext = os.path.splitext(name)[1]
        folder = os.path.dirname(name)
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        path = f"{folder}/{unique_filename}" if folder else unique_filename

        content.seek(0)
        data = content.read()
        content_type = (
            getattr(content, 'content_type', None)
            or mimetypes.guess_type(name)[0]
            or 'application/octet-stream'
        )

        client.storage.from_(self.bucket_name).upload(
            path=path,
            file=data,
            file_options={"content-type": content_type, "upsert": "false"},
        )
        return path

    def url(self, name):
        """
        Return a URL for the file.
        - If the bucket is public: returns the permanent public URL.
        - If the bucket is private: returns a signed URL valid for 1 hour.
        Falls back to signed URL on any error with the public URL approach.
        """
        if not name:
            return ''

        client = self._client()

        # Try signed URL first (works for both public and private buckets)
        try:
            result = client.storage.from_(self.bucket_name).create_signed_url(
                path=name,
                expires_in=3600,  # 1 hour
            )
            # supabase-py v1 returns dict, v2 returns object
            if isinstance(result, dict):
                signed_url = result.get('signedURL') or result.get('signedUrl') or result.get('signed_url')
            else:
                signed_url = getattr(result, 'signed_url', None) or getattr(result, 'signedURL', None)

            if signed_url:
                return signed_url
        except Exception:
            pass

        # Fallback: public URL (works only if bucket is set to public)
        return client.storage.from_(self.bucket_name).get_public_url(name)

    def exists(self, name):
        try:
            client = self._client()
            result = client.storage.from_(self.bucket_name).list(os.path.dirname(name))
            filename = os.path.basename(name)
            return any(f.get('name') == filename for f in (result or []))
        except Exception:
            return False

    def delete(self, name):
        try:
            client = self._client()
            client.storage.from_(self.bucket_name).remove([name])
        except Exception:
            pass

    def size(self, name):
        client = self._client()
        listing = client.storage.from_(self.bucket_name).list(os.path.dirname(name))
        filename = os.path.basename(name)
        for entry in listing or []:
            if entry.get('name') == filename:
                meta = entry.get('metadata') or {}
                if meta.get('size') is not None:
                    return int(meta['size'])
        # Falling back to the object itself rather than returning 0: a zero size
        # on a file that exists makes `FileResponse` send an empty body with a
        # 200, which is a document that opens blank rather than an error anybody
        # can act on.
        return len(self._download(name))

    def _download(self, name) -> bytes:
        client = self._client()
        try:
            return client.storage.from_(self.bucket_name).download(name)
        except Exception as exc:
            # Storage's documented contract for a name that is not there. The
            # row said there was a file, so this is a genuine fault worth
            # raising rather than an empty document worth serving.
            raise FileNotFoundError(
                f'{name!r} is not in the {self.bucket_name!r} bucket.') from exc

    def _open(self, name, mode='rb'):
        """Read a stored document back.

        This raised `NotImplementedError` until 25 Aug 2026, which meant every
        upload succeeded and no upload could ever be opened — the third time
        this project has shipped a document store that only writes. It is
        invisible locally, because local work uses `FileSystemStorage` and reads
        perfectly; only a deployment with `SUPABASE_SERVICE_KEY` set takes this
        path.

        `DocumentView` streams the result with `FileResponse`, so what comes
        back has to be a real file object rather than bytes.
        """
        if any(flag in mode for flag in ('w', 'a', '+', 'x')):
            # Writing goes through `_save`, which generates the stored name.
            # Silently returning a readable handle for a write request would
            # discard whatever the caller wrote.
            raise ValueError(
                f'SupabaseStorage opens files read-only; got mode {mode!r}.')

        return File(BytesIO(self._download(name)), name=name)
