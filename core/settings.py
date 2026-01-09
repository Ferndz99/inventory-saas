import os
from datetime import timedelta
from pathlib import Path
import environ


"""
--------------------
ROUTE AND ENVIRONMENT CONFIGURATION
--------------------
"""
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

BACKEND_URL = "http://localhost:8000"

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


"""
--------------------
SECURITY CONFIGURATION AND MAIN ENVIRONMENT
--------------------
"""
SECRET_KEY = env("SECRET_KEY")

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])  # type: ignore

FRONTEND_DOMAIN = "http://localhost:3000"

"""
--------------------
AUTHENTICATION CONFIGURATION
--------------------
Custom user model and JWT settings.
"""
PRIVATE_KEY = None
with open(BASE_DIR / env("PRIVATE_KEY_PATH"), "rb") as f:  # type: ignore
    PRIVATE_KEY = f.read()

PUBLIC_KEY = None
with open(BASE_DIR / env("PUBLIC_KEY_PATH"), "rb") as f:  # type: ignore
    PUBLIC_KEY = f.read()

ALGORITHM = env("ALGORITHM")

ACCESS_TOKEN_LIFETIME = int(env("ACCESS_TOKEN_LIFETIME"))  # type: ignore

REFRESH_TOKEN_LIFETIME = int(env("REFRESH_TOKEN_LIFETIME"))  # type: ignore

AUTH_USER_MODEL = "accounts.Account"


"""
--------------------
DJANGO MONEY CONFIGURATION
--------------------
Define the allowed currencies.
"""
CURRENCIES = ("CLP", "USD")

CURRENCY_CHOICES = [
    ("CLP", "CLP $"),
    ("USD", "USD US$"),
]

"""
--------------------
APPLICATION DEFINITION (INSTALLED_APPS)
--------------------
List of internal (Django) and third-party applications used in the project.
"""
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    "debug_toolbar",
    "djoser",
    "django_filters",
    "djmoney",
    # local
    "accounts",
    "inventory",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]


"""
--------------------
DEBUG TOOLBAR CONFIGURATION
--------------------
Allow debug_toolbar to be displayed only for these IPs.
"""
INTERNAL_IPS = [
    "127.0.0.1",
]

"""
--------------------
DJANGO REST FRAMEWORK (DRF) CONFIGURATION
--------------------
Defines the default behavior of the API, including permissions, authentication, pagination, filtering, and rendering.
"""
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "EXCEPTION_HANDLER": "core.exceptions.RFC9457_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ]
    if not DEBUG
    else [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "nested_multipart_parser.drf.DrfNestedParser",
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour" if DEBUG else "50/hour",
        "user": "1000/hour" if DEBUG else "500/hour",
    },
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
    "DATE_FORMAT": "%Y-%m-%d",
    "TIME_FORMAT": "%H:%M:%S",
    "COERCE_DECIMAL_TO_STRING": False,
    "NON_FIELD_ERRORS_KEY": "error",
    "UNICODE_JSON": True,
}

"""
--------------------
SIMPLE JWT CONFIGURATION
--------------------
Settings for JSON Web Token authentication, including token lifetimes and signing keys.
"""
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=ACCESS_TOKEN_LIFETIME),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=REFRESH_TOKEN_LIFETIME),
    "ALGORITHM": ALGORITHM,
    "SIGNING_KEY": PRIVATE_KEY,
    "VERIFYING_KEY": PUBLIC_KEY,
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


"""
--------------------
DJOSER CONFIGURATION
--------------------
Settings for user management, including registration, activation, and password reset."""
DJOSER = {
    "LOGIN_FIELD": "email",
    "ACTIVATION_URL": "activate/{uid}/{token}",
    "SEND_ACTIVATION_EMAIL": True,
    "SEND_CONFIRMATION_EMAIL": True,
    "USER_CREATE_PASSWORD_RETYPE": True,
    "SET_PASSWORD_RETYPE": True,
    "PASSWORD_RESET_CONFIRM_URL": "password-reset/{uid}/{token}",
    "PASSWORD_RESET_CONFIRM_RETYPE": True,
    "PASSWORD_RESET_SHOW_EMAIL_NOT_FOUND": True,
    "PASSWORD_CHANGED_EMAIL_CONFIRMATION": True,
    "TOKEN_MODEL": None,
    "HIDE_USERS": True,
    "PERMISSIONS": {
        "activation": ["rest_framework.permissions.AllowAny"],
        "password_reset": ["rest_framework.permissions.AllowAny"],
        "password_reset_confirm": ["rest_framework.permissions.AllowAny"],
        "set_password": ["djoser.permissions.CurrentUserOrAdmin"],
        "username_reset": ["rest_framework.permissions.AllowAny"],
        "username_reset_confirm": ["rest_framework.permissions.AllowAny"],
        "set_username": ["djoser.permissions.CurrentUserOrAdmin"],
        "user_create": ["rest_framework.permissions.AllowAny"],
        "user_delete": ["djoser.permissions.CurrentUserOrAdmin"],
        "user": ["djoser.permissions.CurrentUserOrAdmin"],
        "user_list": ["djoser.permissions.CurrentUserOrAdmin"],
        "token_create": ["rest_framework.permissions.AllowAny"],
        "token_destroy": ["rest_framework.permissions.IsAuthenticated"],
    },
    "SERIALIZERS": {
        "activation": "djoser.serializers.ActivationSerializer",
        "password_reset": "djoser.serializers.SendEmailResetSerializer",
        "password_reset_confirm": "djoser.serializers.PasswordResetConfirmSerializer",
        "password_reset_confirm_retype": "djoser.serializers.PasswordResetConfirmRetypeSerializer",
        "set_password": "djoser.serializers.SetPasswordSerializer",
        "set_password_retype": "djoser.serializers.SetPasswordRetypeSerializer",
        "set_username": "djoser.serializers.SetUsernameSerializer",
        "set_username_retype": "djoser.serializers.SetUsernameRetypeSerializer",
        "username_reset": "djoser.serializers.SendEmailResetSerializer",
        "username_reset_confirm": "djoser.serializers.UsernameResetConfirmSerializer",
        "username_reset_confirm_retype": "djoser.serializers.UsernameResetConfirmRetypeSerializer",
        "user_create": "djoser.serializers.UserCreateSerializer",
        "user_create_password_retype": "djoser.serializers.UserCreatePasswordRetypeSerializer",
        "user_delete": "djoser.serializers.UserDeleteSerializer",
        "user": "djoser.serializers.UserSerializer",
        "current_user": "djoser.serializers.UserSerializer",
        "token": "djoser.serializers.TokenSerializer",
        "token_create": "djoser.serializers.TokenCreateSerializer",
        "provider_auth": "djoser.social.serializers.ProviderAuthSerializer",
    },
}


"""
--------------------
NESTED PARSER
--------------------
"""
DRF_NESTED_MULTIPART_PARSER = {
    "separator": "mixed-dot",
    "raise_duplicate": True,
    "assign_duplicate": False,
    "querydict": False,
}


"""
--------------------
EMAIL CONFIGURATION
--------------------
"""
DEFAULT_FROM_EMAIL = env("EMAIL_HOST_USER")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_PORT = env("EMAIL_PORT")
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend"
)


"""
--------------------
DRF-SPECTACULAR CONFIGURATION (API DOCUMENTATION)
--------------------
Metadata for generating OpenAPI documentation.
"""
SPECTACULAR_SETTINGS = {
    "TITLE": "Your Project API",
    "DESCRIPTION": "Your project description",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SECURITY": [
        {"BearerAuth": []},
    ],
    "AUTHENTICATION_WHITELIST": [
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
}


"""
--------------------
CORS HEADERS CONFIGURATION
--------------------
Manages which origins (domains) can make requests to the API.
Allows all requests in DEBUG mode, restricts them in Production.
"""
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://localhost:8000"]
    if DEBUG
    else ["https://example.com"],  # type: ignore
)
CORS_ALLOW_CREDENTIALS = True


"""
--------------------
CACHE CONFIGURATION
--------------------
Use a simple local memory cache (LocMemCache) for development.
"""
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}


"""
--------------------
LOGGING CONFIGURATION
--------------------
Optimized logging for microservices running in Docker.
Logs are sent to stdout so Docker/Kubernetes can aggregate them.
"""
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "colored": {
            "()": "colorlog.ColoredFormatter",
            "format": "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%H:%M:%S",
            "log_colors": {
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
        "json": {
            "format": '{{"timestamp": "{asctime}", "level": "{levelname}", "logger": "{name}", "message": "{message}"}}',
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "colored" if DEBUG else "json",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "app.log"),
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "json",
        },
    },
    "loggers": {
        "app": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "django": {
            "handlers": ["console", "file"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.template": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}


"""
--------------------
PRODUCTION SECURITY CONFIGURATIONS
--------------------
Ensure that cookies, redirects, and HSTS headers are configured for HTTPS.
These settings only apply if DEBUG is False.
"""
if not DEBUG:
    # HTTPS
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # Cookies
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_HTTPONLY = True

    # Otras configuraciones de seguridad
    X_FRAME_OPTIONS = "DENY"
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True


"""
--------------------
URL AND TEMPLATE CONFIGURATION
--------------------
"""
ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "core.wsgi.application"


"""
--------------------
DATABASE CONFIGURATION
--------------------
By default, it uses SQLite for development.
"""
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="tech_ecommerce"),  # type: ignore
        "USER": env("DB_USER", default="postgres"),  # type: ignore
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="localhost"),  # type: ignore
        "PORT": env("DB_PORT", default="5432"),  # type: ignore
    }
}


"""
--------------------
PASSWORD VALIDATION
--------------------
Django's default rules for validating password security.
"""
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


"""
--------------------
INTERNATIONALIZATION AND TIME ZONE
--------------------
"""
LANGUAGE_CODE = "en-us"

TIME_ZONE = "America/Santiago"

USE_I18N = True

USE_TZ = True


"""
--------------------
STATIC AND MEDIA FILES
--------------------
Configuration for serving CSS, JS, static images, and user-uploaded files.
"""
STATIC_URL = "static/"
