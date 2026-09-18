import json

from django import forms

from apps.knowledge.permissions import visible_knowledge_bases

SAMPLE_DEFINITION = (
    '{"nodes":[{"key":"input","type":"input","input_key":"topic"},'
    '{"key":"draft","type":"llm","prompt":"请总结：{{ input }}"}]}'
)


class WorkflowCreateForm(forms.Form):
    name = forms.CharField(max_length=160, label="名称")
    description = forms.CharField(required=False, widget=forms.Textarea, label="说明")
    knowledge_base = forms.ChoiceField(required=False, label="知识库")
    definition = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 12,
                "spellcheck": "false",
                "placeholder": SAMPLE_DEFINITION,
            }
        ),
        label="节点定义（JSON）",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["knowledge_base"].choices = [("", "不绑定知识库")] + [
            (str(item.id), item.name) for item in visible_knowledge_bases(user)
        ]

    def clean_definition(self):
        try:
            value = json.loads(self.cleaned_data["definition"])
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("请输入有效 JSON") from exc
        if not isinstance(value, dict):
            raise forms.ValidationError("定义必须是 JSON 对象")
        return value
