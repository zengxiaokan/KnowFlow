from django.core.files.uploadedfile import SimpleUploadedFile

from apps.knowledge.forms import DocumentBatchUploadForm


def test_batch_upload_form_accepts_multiple_supported_files():
    form = DocumentBatchUploadForm(
        files={
            "files": [
                SimpleUploadedFile("first.md", b"# First"),
                SimpleUploadedFile("second.md", b"# Second"),
            ]
        }
    )

    assert form.is_valid(), form.errors
    assert [uploaded_file.name for uploaded_file in form.cleaned_data["files"]] == [
        "first.md",
        "second.md",
    ]


def test_batch_upload_form_rejects_too_many_files(settings):
    settings.MAX_BATCH_UPLOAD_COUNT = 1
    form = DocumentBatchUploadForm(
        files={
            "files": [
                SimpleUploadedFile("first.md", b"# First"),
                SimpleUploadedFile("second.md", b"# Second"),
            ]
        }
    )

    assert not form.is_valid()
    assert "一次最多上传 1 个文件" in form.errors["files"]
