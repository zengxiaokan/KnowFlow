from django import forms
from django.conf import settings

from .exceptions import UnsupportedDocumentError
from .parsers import file_type_for


class KnowledgeBaseForm(forms.Form):
    name = forms.CharField(max_length=160, label="知识库名称")
    description = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}), label="说明"
    )
    access_scope = forms.ChoiceField(
        choices=(("organization", "组织内可见"), ("restricted", "仅获授权成员")),
        initial="organization",
        label="访问范围",
    )


def validate_document_file(uploaded_file):
    if uploaded_file.size > settings.MAX_UPLOAD_BYTES:
        raise forms.ValidationError(
            f"文件不能超过 {settings.MAX_UPLOAD_BYTES // 1024 // 1024} MB"
        )
    try:
        file_type_for(uploaded_file.name)
    except UnsupportedDocumentError as exc:
        raise forms.ValidationError(str(exc)) from exc
    return uploaded_file


class DocumentUploadForm(forms.Form):
    file = forms.FileField(label="选择文档")

    def clean_file(self):
        return validate_document_file(self.cleaned_data["file"])


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        files = data if isinstance(data, list) else [data]
        return [super().clean(uploaded_file, initial) for uploaded_file in files]


class DocumentBatchUploadForm(forms.Form):
    files = MultipleFileField(
        label="选择文档",
        widget=MultipleFileInput(attrs={"accept": ".pdf,.docx,.md,.markdown"}),
    )

    def clean_files(self):
        uploaded_files = self.cleaned_data["files"]
        if len(uploaded_files) > settings.MAX_BATCH_UPLOAD_COUNT:
            raise forms.ValidationError(
                f"一次最多上传 {settings.MAX_BATCH_UPLOAD_COUNT} 个文件"
            )
        return [validate_document_file(uploaded_file) for uploaded_file in uploaded_files]
