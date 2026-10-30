"""
i18n tests: locale detection via Accept-Language, translation of
recognized error keys (auth, permission-denied, validation), and —
critically — backward compatibility: any raw English string that isn't
a recognized translation key must pass through completely unchanged
regardless of the requested locale, since dozens of existing service
call sites still raise HTTPException with literal English text.
"""
from app.core.i18n import translate, translate_error_detail, translate_validation_errors, TRANSLATIONS, SUPPORTED_LANGUAGES


def _auth_headers(client, lang=None):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin@12345"})
    assert resp.status_code == 200
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    if lang:
        headers["Accept-Language"] = lang
    return headers


# ---------------- Unit tests for the translation helpers ----------------
def test_translate_known_key_returns_localized_string():
    assert translate("errors.not_found", "en") == TRANSLATIONS["en"]["errors.not_found"]
    assert translate("errors.not_found", "ar") == TRANSLATIONS["ar"]["errors.not_found"]
    assert translate("errors.not_found", "ar") != translate("errors.not_found", "en")


def test_translate_unsupported_language_falls_back_to_english():
    assert translate("errors.not_found", "fr") == TRANSLATIONS["en"]["errors.not_found"]


def test_translate_unknown_key_returns_the_key_itself():
    assert translate("not.a.real.key", "en") == "not.a.real.key"


def test_translate_error_detail_passes_through_unrecognized_strings_unchanged():
    """This is the core backward-compatibility guarantee: every existing
    `raise HTTPException(detail="some raw English message")` call site
    across the codebase must keep working exactly as before."""
    raw = "This property has active rental contracts and cannot be deleted."
    assert translate_error_detail(raw, "en") == raw
    assert translate_error_detail(raw, "ar") == raw


def test_translate_error_detail_translates_recognized_keys():
    result_en = translate_error_detail("errors.not_found", "en")
    result_ar = translate_error_detail("errors.not_found", "ar")
    assert result_en == TRANSLATIONS["en"]["errors.not_found"]
    assert result_ar == TRANSLATIONS["ar"]["errors.not_found"]
    assert result_en != result_ar


def test_translate_error_detail_supports_key_with_suffix():
    result = translate_error_detail("errors.permission_denied:users.create", "en")
    assert TRANSLATIONS["en"]["errors.permission_denied"] in result
    assert "users.create" in result


def test_translate_error_detail_passes_through_non_string_detail():
    detail = {"code": "custom", "fields": ["a", "b"]}
    assert translate_error_detail(detail, "en") is detail


def test_translate_validation_errors_adds_localized_msg():
    errors = [{"type": "missing", "loc": ["body", "email"], "msg": "field required"}]
    localized = translate_validation_errors(errors, "ar")
    assert localized[0]["localized_msg"] == TRANSLATIONS["ar"]["validation.missing"]
    assert localized[0]["msg"] == "field required"  # original untouched


def test_en_and_ar_translation_dicts_have_identical_keys():
    """Prepared for unlimited languages: every language block must define
    the same set of keys, or a language switch would silently show
    English/raw keys for anything missing."""
    en_keys = set(TRANSLATIONS["en"].keys())
    ar_keys = set(TRANSLATIONS["ar"].keys())
    assert en_keys == ar_keys


def test_supported_languages_list_matches_translations_dict():
    assert set(SUPPORTED_LANGUAGES) == set(TRANSLATIONS.keys())


# ---------------- Integration tests via the API ----------------
def test_login_error_is_english_by_default(client, seeded_admin):
    resp = client.post("/api/v1/auth/login", json={"email": "nobody@test.com", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == TRANSLATIONS["en"]["errors.invalid_credentials"]


def test_login_error_is_arabic_with_accept_language_header(client, seeded_admin):
    resp = client.post(
        "/api/v1/auth/login", json={"email": "nobody@test.com", "password": "wrong"},
        headers={"Accept-Language": "ar"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == TRANSLATIONS["ar"]["errors.invalid_credentials"]


def test_content_language_header_reflects_requested_locale(client, seeded_admin):
    resp = client.post(
        "/api/v1/auth/login", json={"email": "nobody@test.com", "password": "wrong"},
        headers={"Accept-Language": "ar-SA"},
    )
    assert resp.headers.get("content-language") == "ar"


def test_permission_denied_error_is_translated_and_keeps_permission_code(client, seeded_admin):
    # Create a non-superuser with no permissions to trigger a 403.
    from app.core.security import hash_password
    from app.models.user import User
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "limited@test.com").first()
        if not existing:
            user = User(email="limited@test.com", hashed_password=hash_password("Limited@12345"), first_name="Limited", last_name="User", is_active=True, is_superuser=False)
            db.add(user)
            db.commit()
    finally:
        db.close()

    login = client.post("/api/v1/auth/login", json={"email": "limited@test.com", "password": "Limited@12345"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}", "Accept-Language": "ar"}
    resp = client.get("/api/v1/users", headers=headers)
    assert resp.status_code == 403
    assert TRANSLATIONS["ar"]["errors.permission_denied"] in resp.json()["detail"]
    assert "users.view" in resp.json()["detail"]


def test_unauthenticated_error_is_translated(client, seeded_admin):
    resp = client.get("/api/v1/users", headers={"Accept-Language": "ar"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == TRANSLATIONS["ar"]["errors.unauthenticated"]


def test_validation_error_response_includes_localized_errors(client, seeded_admin):
    headers = _auth_headers(client, lang="ar")
    resp = client.post("/api/v1/owners", json={}, headers=headers)  # missing the required owner_type field entirely
    assert resp.status_code == 422
    body = resp.json()
    assert body["detail"] == TRANSLATIONS["ar"]["errors.validation_failed"]
    assert "errors" in body
    assert all("localized_msg" in e for e in body["errors"])


def test_validation_error_backward_compatible_shape(client, seeded_admin):
    """The 'errors' array's original fields (type/loc/msg) must still be
    present exactly as before — only a new localized_msg field is added."""
    headers = _auth_headers(client)
    resp = client.post("/api/v1/owners", json={}, headers=headers)
    assert resp.status_code == 422
    body = resp.json()
    for err in body["errors"]:
        assert "type" in err and "loc" in err and "msg" in err


def test_raw_string_http_exceptions_still_work_unchanged(client, seeded_admin):
    """A representative existing (non-i18n-key) error path — deleting a
    nonexistent resource — must still return its original raw message,
    regardless of requested locale, since it was never converted to a key."""
    headers = _auth_headers(client, lang="ar")
    resp = client.get("/api/v1/owners/999999", headers=headers)
    assert resp.status_code == 404
    # Whatever the raw detail is, it must be identical between locales
    # (i.e. NOT silently translated, since "owner not found"-style
    # messages in most services are still raw strings, not keys).
    headers_en = _auth_headers(client, lang="en")
    resp_en = client.get("/api/v1/owners/999999", headers=headers_en)
    assert resp.json()["detail"] == resp_en.json()["detail"]
