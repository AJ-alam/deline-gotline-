import os
import uuid
import mimetypes
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
        content_type = getattr(content, 'content_type', None) or mimetypes.guess_type(name)[0] or 'application/octet-stream'

        client.storage.from_(self.bucket_name).upload(
            path=path,
            file=data,
            file_options={"content-type": content_type, "upsert": "false"},
        )
        return path

    def url(self, name):
        client = self._client()
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

    def _open(self, name, mode='rb'):
        raise NotImplementedError("SupabaseStorage does not support file reading via Django's file API.")
