from django import forms
from django.conf import settings

from .exceptions import UnsupportedDocumentError
from .models import KnowledgeBase, KnowledgeBaseMembership
from .parsers import file_type_for


class KnowledgeBaseForm(forms.Form):
    name = forms.CharField(max_length=160, label="知识库名称")
    description = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}), label="说明"
    )
    assistant_prompt = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 4, "placeholder": "例如：回答简洁，先给结论，再列要点。"}
        ),
        label="助手提示词",
        help_text="仅影响该知识库的回答风格与任务规则；回答仍只能依据检索到的资料。",
    )
    access_scope = forms.ChoiceField(
        choices=KnowledgeBase.AccessScope.choices,
        label="访问范围",
        help_text="组织内可见会向组织成员开放；仅获授权成员需要显式授权。",
    )


class DocumentRenameForm(forms.Form):
    title = forms.CharField(max_length=255, label="文档名称")


class KnowledgeBaseMemberForm(forms.Form):
    role = forms.ChoiceField(
        choices=KnowledgeBaseMembership.Role.choices,
        initial=KnowledgeBaseMembership.Role.READER,
        label="知识库角色",
    )


def validate_document_file(uploaded_file):
    if uploaded_file.size > settings.MAX_UPLOAD_BYTES:
        raise forms.ValidationError(f"文件不能超过 {settings.MAX_UPLOAD_BYTES // 1024 // 1024} MB")
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
            raise forms.ValidationError(f"一次最多上传 {settings.MAX_BATCH_UPLOAD_COUNT} 个文件")
        return [validate_document_file(uploaded_file) for uploaded_file in uploaded_files]
