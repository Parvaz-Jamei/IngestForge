import pytest

from ingestforge.core.errors import SafeUrlError
from ingestforge.providers.fetch.safe_url import host_allowed, validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com",
        "http://localhost",
        "http://127.0.0.1",
        "http://169.254.169.254",
        "http://[::1]",
    ],
)
def test_reject_private_or_bad(url):
    with pytest.raises(SafeUrlError):
        validate_public_url(url)


def test_allow_public_url():
    assert validate_public_url("https://example.com/path", deny_private_networks=False).startswith(
        "https://example.com"
    )


def test_domain_policy():
    assert host_allowed("https://sub.example.com/a", ["example.com"], [])
    assert not host_allowed("https://bad.example.com/a", ["example.com"], ["bad.example.com"])
    assert not host_allowed("https://other.com/a", ["example.com"], [])
