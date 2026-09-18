from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label="邮箱地址")

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"placeholder": "请输入用户名", "autocomplete": "username"}
        )
        self.fields["email"].widget.attrs.update(
            {"placeholder": "name@example.com", "autocomplete": "email"}
        )
        self.fields["password1"].widget.attrs.update(
            {"placeholder": "至少 8 位", "autocomplete": "new-password"}
        )
        self.fields["password2"].widget.attrs.update(
            {"placeholder": "再次输入密码", "autocomplete": "new-password"}
        )


class SignInForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"placeholder": "请输入用户名", "autocomplete": "username"}
        )
        self.fields["password"].widget.attrs.update(
            {"placeholder": "请输入密码", "autocomplete": "current-password"}
        )


class InvitationForm(forms.Form):
    email = forms.EmailField(label="成员邮箱")
    role = forms.ChoiceField(
        choices=[
            ("editor", "编辑者：可管理知识库与工作流"),
            ("viewer", "查看者：可使用已授权知识库"),
        ],
        label="角色",
    )
