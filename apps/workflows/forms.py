from django import forms

from apps.knowledge.permissions import visible_knowledge_bases


class WorkflowCreateForm(forms.Form):
    name = forms.CharField(max_length=160, label="名称")
    description = forms.CharField(required=False, widget=forms.Textarea, label="说明")
    knowledge_base = forms.ChoiceField(required=False, label="知识库")
    input_key = forms.SlugField(initial="input", label="输入变量名")
    prompt = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "请根据 {{ input }} 输出清晰结论"}),
        label="提示词模板",
    )
    use_retrieval = forms.BooleanField(required=False, initial=True, label="先检索绑定知识库")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["knowledge_base"].choices = [("", "不绑定知识库")] + [
            (str(item.id), item.name) for item in visible_knowledge_bases(user)
        ]

    def definition(self):
        key = self.cleaned_data["input_key"]
        nodes = [{"key": key, "type": "input", "input_key": key, "label": key}]
        source = f"{{{{ {key} }}}}"
        if self.cleaned_data["use_retrieval"]:
            nodes.append({"key": "context", "type": "retrieve", "query": source, "limit": 4})
            source = "{{ context }}\n\n" + source
        nodes.append({"key": "answer", "type": "llm", "prompt": self.cleaned_data["prompt"]})
        return {"nodes": nodes}
