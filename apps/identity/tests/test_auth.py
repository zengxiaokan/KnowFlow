from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    WHITENOISE_AUTOREFRESH=True,
    WHITENOISE_USE_FINDERS=True,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class AuthenticationFlowTests(TestCase):
    def test_signup_page_renders_the_required_email_field(self):
        response = self.client.get(reverse("signup"))

        self.assertContains(response, 'name="email"')
        self.assertContains(response, "邮箱地址")

    def test_signup_creates_an_account_and_signs_the_user_in(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "new-member",
                "email": "new-member@example.com",
                "password1": "SafePassword!2026",
                "password2": "SafePassword!2026",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(User.objects.filter(username="new-member").exists())
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_login_accepts_valid_credentials(self):
        User.objects.create_user(username="member", password="SafePassword!2026")

        response = self.client.post(
            reverse("login"),
            {"username": "member", "password": "SafePassword!2026"},
        )

        self.assertRedirects(response, reverse("dashboard"))
