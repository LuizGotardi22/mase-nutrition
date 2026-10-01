"""Configurações da loja MASE NUTRITION."""
import os
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _lista(nome, padrao=""):
    return [v.strip() for v in os.environ.get(nome, padrao).split(",") if v.strip()]


NA_VERCEL = bool(os.environ.get("VERCEL"))  # a Vercel define VERCEL=1 automaticamente
DEBUG = os.environ.get("DEBUG", "False" if NA_VERCEL else "True").lower() == "true"

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key"
    else:
        raise RuntimeError("Defina SECRET_KEY no ambiente (.env) para rodar em produção.")

ALLOWED_HOSTS = _lista("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = _lista("CSRF_TRUSTED_ORIGINS")
if NA_VERCEL:
    ALLOWED_HOSTS += [".vercel.app"]
    CSRF_TRUSTED_ORIGINS += ["https://*.vercel.app"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "loja",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "loja.middleware.LoginObrigatorioMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
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
                "loja.context_processors.loja",
            ],
        },
    },
]

if os.environ.get("DATABASE_URL"):
    import urllib.parse

    _u = urllib.parse.urlparse(os.environ["DATABASE_URL"])
    _consulta = urllib.parse.parse_qs(_u.query)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _u.path.lstrip("/"),
            "USER": urllib.parse.unquote(_u.username or ""),
            "PASSWORD": urllib.parse.unquote(_u.password or ""),
            "HOST": _u.hostname,
            "PORT": _u.port or 5432,
            "OPTIONS": {"sslmode": _consulta["sslmode"][0]} if _consulta.get("sslmode") else {},
            "DISABLE_SERVER_SIDE_CURSORS": True,  # compatível com pooler de conexões (serverless)
        }
    }
elif os.environ.get("DB_NAME"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["DB_NAME"],
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Arquivos estáticos: armazenamento padrão. Na Vercel o collectstatic roda no deploy e o CDN serve os arquivos.

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------- Loja ----------
STORE_NAME = "MASE NUTRITION"
_dominio_vercel = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL", "")
SITE_URL = (os.environ.get("SITE_URL") or (f"https://{_dominio_vercel}" if _dominio_vercel else "http://localhost:8000")).rstrip("/")
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "5511999999999")

MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "")
# Chave PÚBLICA (não é segredo, vai no HTML) usada pelo formulário de cartão embutido para tokenizar o cartão
# sem que o número/CVV passem pelo seu servidor. Pegue as duas em: mercadopago.com.br > seu negócio > credenciais.
MP_PUBLIC_KEY = os.environ.get("MP_PUBLIC_KEY", "")
PIX_EXPIRA_MINUTOS = int(os.environ.get("PIX_EXPIRA_MINUTOS", "60"))

FRETE_FIXO = Decimal(os.environ.get("FRETE_FIXO", "19.90"))
FRETE_GRATIS_ACIMA = Decimal(os.environ.get("FRETE_GRATIS_ACIMA", "0"))

# Frete: cotação real pelo Melhor Envio (opcional). Sem token, usa a tabela "Frete por estado" do painel.
CEP_ORIGEM = "".join(ch for ch in os.environ.get("CEP_ORIGEM", "") if ch.isdigit())
MELHOR_ENVIO_TOKEN = os.environ.get("MELHOR_ENVIO_TOKEN", "")
MELHOR_ENVIO_SANDBOX = os.environ.get("MELHOR_ENVIO_SANDBOX", "False").lower() == "true"

# Se True, quem entra no site precisa fazer login ou criar conta antes de ver qualquer página. Padrão False: o site é público, como a maioria das lojas (Minha Conta é opcional).
LOGIN_OBRIGATORIO = os.environ.get("LOGIN_OBRIGATORIO", "False").lower() == "true"

# Arquivos enviados (materiais técnicos). NÃO são servidos publicamente: passam por uma view que confere o acesso.
MEDIA_ROOT = BASE_DIR / "media"

# Compra amarrada ao prescritor: True = o cliente precisa informar o cupom do profissional de saúde. Padrão False (compra livre).
PRESCRITOR_OBRIGATORIO = os.environ.get("PRESCRITOR_OBRIGATORIO", "False").lower() == "true"

# Programa Mase Contínua: benefício (%) sobre os produtos em compras recorrentes. Valor de exemplo: defina o real.
CONTINUA_BENEFICIO_PERCENTUAL = Decimal(os.environ.get("CONTINUA_BENEFICIO_PERCENTUAL", "5"))

# E-mail (avisos de leads e cadastros). Sem EMAIL_HOST, os e-mails aparecem no terminal.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST else "django.core.mail.backends.console.EmailBackend",
)
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() == "true"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "site@masenutrition.com.br")
# Destino padrão dos avisos quando a rota do contato não tem e-mail próprio
EMAIL_COMERCIAL = os.environ.get("EMAIL_COMERCIAL", "")

# Redes sociais (só aparecem no site as que estiverem preenchidas)
REDES_SOCIAIS = [
    ("LinkedIn", os.environ.get("SOCIAL_LINKEDIN", "")),
    ("Instagram", os.environ.get("SOCIAL_INSTAGRAM", "")),
    ("YouTube", os.environ.get("SOCIAL_YOUTUBE", "")),
    ("Facebook", os.environ.get("SOCIAL_FACEBOOK", "")),
    ("Threads", os.environ.get("SOCIAL_THREADS", "")),
    ("X", os.environ.get("SOCIAL_X", "")),
]

# Contas de clientes. Local: arquivo JSON (senhas só como hash). Na Vercel (ou com DATABASE_URL) o disco não é
# permanente, então as contas ficam no banco de dados. Force com CONTAS_EM_JSON=True/False se precisar.
CONTAS_EM_JSON = os.environ.get(
    "CONTAS_EM_JSON", "False" if (NA_VERCEL or os.environ.get("DATABASE_URL")) else "True"
).lower() == "true"
CONTAS_JSON_PATH = Path(os.environ.get("CONTAS_JSON_PATH", BASE_DIR / "data" / "contas.json"))
AUTHENTICATION_BACKENDS = (
    ["loja.backends.ContasJsonBackend"] if CONTAS_EM_JSON else []
) + ["django.contrib.auth.backends.ModelBackend"]
