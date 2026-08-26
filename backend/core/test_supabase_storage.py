"""The storage backend a deployment uses, which local work never touches.

`STORAGES` picks `SupabaseStorage` only when `SUPABASE_SERVICE_KEY` is set, so
every test and every developer runs on `FileSystemStorage` — where reading a
file back works perfectly. `_open` raised `NotImplementedError` for as long as
this class had existed, and nothing noticed: uploads returned 201, the object
really was in the bucket, and opening one was a 500 on the deployment alone.

That is the third time this project has shipped a document store that only
writes, and the first two were caught by a person clicking a link. So the tests
here drive the class directly with a stubbed client, because the alternative is
finding out from a reviewer who cannot open a transcript.
"""

from io import BytesIO
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings

from core.supabase_storage import SupabaseStorage

PDF = b'%PDF-1.4 a small but real-enough document\n%%EOF\n'


class FakeBucket:
    """Enough of `client.storage.from_(bucket)` to answer the calls made."""

    def __init__(self, objects=None, fail_download=False):
        self.objects = dict(objects or {})
        self.fail_download = fail_download
        self.uploaded = []
        self.removed = []

    def upload(self, path, file, file_options=None):
        self.objects[path] = file
        self.uploaded.append((path, file_options))
        return {'path': path}

    def download(self, path):
        if self.fail_download or path not in self.objects:
            raise RuntimeError('Object not found')
        return self.objects[path]

    def list(self, prefix=''):
        out = []
        for path, blob in self.objects.items():
            if path.startswith(prefix or ''):
                out.append({'name': path.rsplit('/', 1)[-1],
                            'metadata': {'size': len(blob)}})
        return out

    def remove(self, paths):
        for p in paths:
            self.objects.pop(p, None)
        self.removed.extend(paths)


class FakeClient:
    def __init__(self, bucket):
        self._bucket = bucket
        self.storage = self

    def from_(self, _name):
        return self._bucket


def storage_with(bucket):
    store = SupabaseStorage(bucket='dgg-documents')
    return store, patch.object(store, '_client', return_value=FakeClient(bucket))


@override_settings(SUPABASE_STORAGE_BUCKET='dgg-documents')
class ReadBackTests(SimpleTestCase):
    """A document that cannot be opened is a document that was never attached."""

    def test_a_stored_document_can_be_read_back(self):
        bucket = FakeBucket({'documents/2026/08/abc.pdf': PDF})
        store, client = storage_with(bucket)

        with client:
            handle = store.open('documents/2026/08/abc.pdf', 'rb')

        self.assertEqual(handle.read(), PDF)

    def test_what_comes_back_is_a_file_not_bytes(self):
        """`DocumentView` hands it to `FileResponse`, which needs to stream."""
        bucket = FakeBucket({'documents/2026/08/abc.pdf': PDF})
        store, client = storage_with(bucket)

        with client:
            handle = store.open('documents/2026/08/abc.pdf', 'rb')

        self.assertTrue(hasattr(handle, 'read'))
        self.assertTrue(hasattr(handle, 'chunks'))
        self.assertEqual(b''.join(handle.chunks()), PDF)

    def test_a_round_trip_through_save_and_open(self):
        """The two halves against each other: `_save` invents the stored name,
        so a test that opens a name it made up proves nothing about what upload
        actually wrote."""
        bucket = FakeBucket()
        store, client = storage_with(bucket)

        with client:
            stored = store.save('documents/2026/08/original.pdf', ContentFile(PDF))
            handle = store.open(stored, 'rb')

        self.assertEqual(handle.read(), PDF)
        self.assertNotIn('original', stored)

    def test_a_missing_object_raises_rather_than_returning_nothing(self):
        """An empty body with a 200 is a document that opens blank."""
        bucket = FakeBucket()
        store, client = storage_with(bucket)

        with client, self.assertRaises(FileNotFoundError):
            store.open('documents/2026/08/gone.pdf', 'rb')

    def test_a_write_mode_is_refused_rather_than_quietly_read(self):
        """Returning a readable handle for a write request discards whatever
        the caller writes into it."""
        bucket = FakeBucket({'documents/2026/08/abc.pdf': PDF})
        store, client = storage_with(bucket)

        for mode in ('wb', 'ab', 'rb+', 'xb'):
            with self.subTest(mode=mode), client, self.assertRaises(ValueError):
                store.open('documents/2026/08/abc.pdf', mode)


@override_settings(SUPABASE_STORAGE_BUCKET='dgg-documents')
class SizeTests(SimpleTestCase):

    def test_size_comes_from_the_listing(self):
        bucket = FakeBucket({'documents/2026/08/abc.pdf': PDF})
        store, client = storage_with(bucket)

        with client:
            self.assertEqual(store.size('documents/2026/08/abc.pdf'), len(PDF))

    def test_size_falls_back_to_the_object_rather_than_reporting_zero(self):
        """A zero length on a file that exists makes FileResponse send an empty
        body with a 200 — a blank document rather than an error."""
        bucket = FakeBucket({'documents/2026/08/abc.pdf': PDF})
        bucket.list = lambda prefix='': [{'name': 'abc.pdf', 'metadata': {}}]
        store, client = storage_with(bucket)

        with client:
            self.assertEqual(store.size('documents/2026/08/abc.pdf'), len(PDF))


@override_settings(SUPABASE_STORAGE_BUCKET='dgg-documents')
class WriteTests(SimpleTestCase):

    def test_the_stored_name_is_generated_not_the_one_supplied(self):
        """The uploaded name is a uuid: a stored name derived from what the
        applicant called the file is guessable and leaks what it is."""
        bucket = FakeBucket()
        store, client = storage_with(bucket)

        with client:
            stored = store.save('documents/2026/08/My Transcript.pdf',
                                ContentFile(PDF))

        self.assertTrue(stored.startswith('documents/2026/08/'))
        self.assertTrue(stored.endswith('.pdf'))
        self.assertNotIn('Transcript', stored)

    def test_the_content_type_is_carried_to_the_bucket(self):
        """Stored without one, a PDF comes back as application/octet-stream and
        downloads instead of opening."""
        bucket = FakeBucket()
        store, client = storage_with(bucket)

        with client:
            store.save('documents/2026/08/a.pdf', ContentFile(PDF))

        _path, options = bucket.uploaded[0]
        self.assertEqual(options['content-type'], 'application/pdf')
