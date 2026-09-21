import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


SECRET_KEY = env("SECRET_KEY", "unsafe-development-key")
DEBUG = env("DEBUG", "false").lower() == "true"
LOCAL_DEMO_MODE = env("KNOWFLOW_LOCAL_DEMO", "false").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "channels",
    "rest_framework",
    "drf_spectacular",
    "django_htmx",
    "apps.identity",
    "apps.knowledge",
    "apps.chat",
    "apps.workflows",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "knowflow"),
        "USER": env("POSTGRES_USER", "knowflow"),
        "PASSWORD": env("POSTGRES_PASSWORD", "knowflow-local-only"),
        "HOST": env("POSTGRES_HOST", "db"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }
}

if LOCAL_DEMO_MODE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "local-demo.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env("REDIS_URL", "redis://redis:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 900

if LOCAL_DEMO_MODE:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = False

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "KnowFlow API",
    "DESCRIPTION": "Enterprise knowledge base and workflow platform API",
    "VERSION": "0.1.0",
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

MAX_UPLOAD_BYTES = int(env("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
MAX_BATCH_UPLOAD_COUNT = int(env("MAX_BATCH_UPLOAD_COUNT", "20"))
MAX_DOCUMENT_PAGES = 100
VECTOR_DIMENSIONS = 1024
RAG_CANDIDATE_COUNT = 8
RAG_CITATION_COUNT = 4
RAG_MAX_COSINE_DISTANCE = float(env("RAG_MAX_COSINE_DISTANCE", "0.65"))
CHAT_HISTORY_MESSAGE_LIMIT = int(env("CHAT_HISTORY_MESSAGE_LIMIT", "6"))
CHAT_HISTORY_MESSAGE_CHARS = int(env("CHAT_HISTORY_MESSAGE_CHARS", "1200"))
CHUNK_SIZE = 700
CHUNK_OVERLAP = 80

DEEPSEEK_API_KEY = env("DEEPSEEK_API_KEY")
DEEPSEEK_API_BASE = env("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = env("DEEPSEEK_MODEL", "deepseek-flash")
SILICONFLOW_API_KEY = env("SILICONFLOW_API_KEY")
SILICONFLOW_API_BASE = env("SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1")
SILICONFLOW_EMBEDDING_MODEL = env("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")
CHAT_PROVIDER = env("CHAT_PROVIDER", "apps.knowledge.providers.DeepSeekChatProvider")
EMBEDDING_PROVIDER = env(
    "EMBEDDING_PROVIDER", "apps.knowledge.providers.SiliconFlowEmbeddingProvider"
)

if LOCAL_DEMO_MODE:
    CHAT_PROVIDER = "apps.knowledge.providers.DemoChatProvider"
    EMBEDDING_PROVIDER = "apps.knowledge.providers.DeterministicEmbeddingProvider"
