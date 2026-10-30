"""
Backend internationalization (i18n).

Architecture: a flat `TRANSLATIONS` dict keyed by ISO language code, each
mapping translation keys to localized strings. Adding a new language is
purely additive — add one more `"xx": {...}` block with the same keys;
nothing else in the codebase needs to change (unlimited-language-ready).

This intentionally does NOT try to translate every hardcoded error
string in every service in one pass — that would touch 100+ call sites
across every module and carries real regression risk. Instead:
- `translate_error_detail()` is applied generically in main.py's global
  exception handler: if an HTTPException's `detail` happens to be a
  recognized translation KEY (e.g. "errors.not_found"), it's translated;
  any raw English string not in the dictionary passes through completely
  unchanged, so every existing `raise HTTPException(detail="...")` call
  site keeps working exactly as before (100% backward compatible).
- New/updated call sites can opt in by raising with a translation key
  instead of a literal string (see auth.py and api/deps.py for the
  flagship examples — login errors and permission-denied errors, which
  are the two error paths every user hits most often).
- `translate_validation_errors()` is applied generically to every
  Pydantic validation failure (422) app-wide, which is the highest-
  leverage single change for "Validation" coverage — it works for every
  existing and future endpoint's request schema without touching any of
  them individually.
"""
from typing import Optional
from fastapi import Request

SUPPORTED_LANGUAGES = ["en", "ar"]
DEFAULT_LANGUAGE = "en"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # Common CRUD / auth errors (flagship keys — extend this dict, don't create a second one)
        "errors.not_found": "The requested item was not found.",
        "errors.already_exists": "An item with these details already exists.",
        "errors.permission_denied": "You don't have permission to perform this action.",
        "errors.invalid_credentials": "Invalid email or password.",
        "errors.account_inactive": "This account has been deactivated. Contact an administrator.",
        "errors.account_locked": "Account locked due to too many failed attempts. Try again after",
        "errors.token_expired": "Your session has expired. Please sign in again.",
        "errors.token_invalid": "Invalid or malformed authentication token.",
        "errors.unauthenticated": "Authentication is required to access this resource.",
        "errors.validation_failed": "One or more fields need your attention.",
        "errors.unexpected": "An unexpected error occurred. Please try again or contact support.",
        "errors.rate_limited": "Too many attempts. Please wait a moment and try again.",
        # Pydantic validation error type -> human message
        "validation.missing": "This field is required.",
        "validation.string_type": "This field must be text.",
        "validation.int_type": "This field must be a whole number.",
        "validation.float_type": "This field must be a number.",
        "validation.value_error": "This value isn't valid.",
        "validation.greater_than": "This value must be greater than the minimum allowed.",
        "validation.less_than": "This value must be less than the maximum allowed.",
        "validation.string_too_short": "This value is too short.",
        "validation.string_too_long": "This value is too long.",
        "validation.date_parsing": "Enter a valid date.",
        "validation.email": "Enter a valid email address.",
    },
    "ar": {
        "errors.not_found": "لم يتم العثور على العنصر المطلوب.",
        "errors.already_exists": "يوجد عنصر بهذه التفاصيل بالفعل.",
        "errors.permission_denied": "لا تملك صلاحية القيام بهذا الإجراء.",
        "errors.invalid_credentials": "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
        "errors.account_inactive": "تم إيقاف هذا الحساب. يرجى التواصل مع المسؤول.",
        "errors.account_locked": "تم قفل الحساب بسبب محاولات فاشلة متكررة. حاول مرة أخرى بعد",
        "errors.token_expired": "انتهت صلاحية الجلسة. يرجى تسجيل الدخول مرة أخرى.",
        "errors.token_invalid": "رمز المصادقة غير صالح أو غير صحيح.",
        "errors.unauthenticated": "يلزم تسجيل الدخول للوصول إلى هذا المورد.",
        "errors.validation_failed": "بعض الحقول تحتاج إلى مراجعة.",
        "errors.unexpected": "حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى أو التواصل مع الدعم.",
        "errors.rate_limited": "محاولات كثيرة جدًا. يرجى الانتظار قليلاً والمحاولة مرة أخرى.",
        "validation.missing": "هذا الحقل مطلوب.",
        "validation.string_type": "يجب أن يكون هذا الحقل نصًا.",
        "validation.int_type": "يجب أن يكون هذا الحقل رقمًا صحيحًا.",
        "validation.float_type": "يجب أن يكون هذا الحقل رقمًا.",
        "validation.value_error": "هذه القيمة غير صالحة.",
        "validation.greater_than": "يجب أن تكون هذه القيمة أكبر من الحد الأدنى المسموح.",
        "validation.less_than": "يجب أن تكون هذه القيمة أقل من الحد الأقصى المسموح.",
        "validation.string_too_short": "هذه القيمة قصيرة جدًا.",
        "validation.string_too_long": "هذه القيمة طويلة جدًا.",
        "validation.date_parsing": "أدخل تاريخًا صالحًا.",
        "validation.email": "أدخل بريدًا إلكترونيًا صالحًا.",
    },
}


def get_locale_from_request(request: Request) -> str:
    """Reads the person's preferred language the standard REST way — the
    `Accept-Language` header — falling back to English. The frontend's
    axios client attaches this automatically from the selected UI
    language (see frontend/src/api/client.ts), so language selection
    made in the UI is honored on every API call without any extra
    per-endpoint wiring."""
    header = request.headers.get("accept-language", "")
    primary = header.split(",")[0].strip().split("-")[0].lower() if header else ""
    return primary if primary in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def translate(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    return TRANSLATIONS.get(lang, {}).get(key, TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key))


def translate_error_detail(detail, lang: str) -> object:
    """If `detail` is a recognized translation key, translate it.
    Also supports a `"key:suffix"` convention for messages that need a
    bit of dynamic content appended (e.g. a specific permission code) —
    only the key portion is translated, the suffix passes through as-is.
    Any string that isn't a recognized key (with or without a suffix) is
    returned completely unchanged — this is what keeps every existing
    `raise HTTPException(detail="some raw string")` call site working
    exactly as before."""
    if not isinstance(detail, str):
        return detail
    if detail in TRANSLATIONS[DEFAULT_LANGUAGE]:
        return translate(detail, lang)
    if ":" in detail:
        key, _, suffix = detail.partition(":")
        if key in TRANSLATIONS[DEFAULT_LANGUAGE]:
            return f"{translate(key, lang)} ({suffix})"
    return detail


_PYDANTIC_ERROR_KEY_MAP = {
    "missing": "validation.missing",
    "string_type": "validation.string_type",
    "int_type": "validation.int_type",
    "int_parsing": "validation.int_type",
    "float_type": "validation.float_type",
    "float_parsing": "validation.float_type",
    "value_error": "validation.value_error",
    "greater_than": "validation.greater_than",
    "greater_than_equal": "validation.greater_than",
    "less_than": "validation.less_than",
    "less_than_equal": "validation.less_than",
    "string_too_short": "validation.string_too_short",
    "string_too_long": "validation.string_too_long",
    "date_parsing": "validation.date_parsing",
    "value_error.email": "validation.email",
}


def translate_validation_errors(errors: list[dict], lang: str) -> list[dict]:
    """Adds a `localized_msg` field to each Pydantic error entry, using
    the selected language. The original `msg`/`type`/`loc` fields are
    left untouched (nothing in the frontend currently parses this array,
    but preserving its shape is the safe, backward-compatible choice)."""
    translated = []
    for err in errors:
        err = dict(err)
        key = _PYDANTIC_ERROR_KEY_MAP.get(err.get("type", ""))
        err["localized_msg"] = translate(key, lang) if key else err.get("msg")
        translated.append(err)
    return translated


def first_validation_message(errors: list[dict], lang: str) -> Optional[str]:
    localized = translate_validation_errors(errors, lang)
    if not localized:
        return None
    first = localized[0]
    field = first.get("loc", [])[-1] if first.get("loc") else ""
    return f"{field}: {first['localized_msg']}" if field else first["localized_msg"]
