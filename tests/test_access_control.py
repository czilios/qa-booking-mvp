import pytest

from app.access_control import AccessCategory, api_docs_enabled, classify_access


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("GET", "/availability", AccessCategory.PUBLIC),
        ("POST", "/inquiries", AccessCategory.PUBLIC),
        ("GET", "/login", AccessCategory.AUTH_EXCEPTION),
        ("POST", "/login", AccessCategory.AUTH_EXCEPTION),
        ("POST", "/logout", AccessCategory.AUTH_EXCEPTION),
        ("GET", "/", AccessCategory.TECHNICAL),
        ("GET", "/health", AccessCategory.TECHNICAL),
        ("GET", "/static/site.css", AccessCategory.TECHNICAL),
        ("GET", "/docs", AccessCategory.TECHNICAL),
        ("GET", "/docs/oauth2-redirect", AccessCategory.TECHNICAL),
        ("GET", "/redoc", AccessCategory.TECHNICAL),
        ("GET", "/openapi.json", AccessCategory.TECHNICAL),
        ("GET", "/reservations/123", AccessCategory.OPERATOR_ONLY),
        ("POST", "/ui/reservations", AccessCategory.OPERATOR_ONLY),
    ],
)
def test_access_policy_classifies_routes(method, path, expected):
    assert classify_access(path, method) is expected


def test_api_documentation_is_disabled_only_in_production():
    assert api_docs_enabled("production") is False
    assert api_docs_enabled("PRODUCTION") is False
    assert api_docs_enabled("local") is True
    assert api_docs_enabled("test") is True
