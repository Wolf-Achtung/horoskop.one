"""Regression tests for the audit fixes: security headers, CORS wildcard
guard, and full I-Ging hexagram reachability."""
import datetime as dt

from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


class TestSecurityHeaders:
    def test_health_response_carries_all_security_headers(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "geolocation=(self)" in r.headers["permissions-policy"]
        assert "max-age=" in r.headers["strict-transport-security"]
        csp = r.headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_cache_stats_endpoint_removed(self):
        # Previously an unauthenticated info-disclosure endpoint; must be gone.
        assert client.get("/cache-stats").status_code == 404


class TestCorsResolution:
    def test_explicit_origin_list_keeps_credentials_enabled(self):
        origins, allow_credentials = main._resolve_cors(
            "https://horoskop.one,https://www.horoskop.one", main.DEFAULT_ORIGINS
        )
        assert origins == ["https://horoskop.one", "https://www.horoskop.one"]
        assert allow_credentials is True

    def test_wildcard_disables_credentials(self):
        origins, allow_credentials = main._resolve_cors("*", main.DEFAULT_ORIGINS)
        assert origins == ["*"]
        assert allow_credentials is False

    def test_empty_env_falls_back_to_defaults_with_credentials(self):
        origins, allow_credentials = main._resolve_cors("", main.DEFAULT_ORIGINS)
        assert origins == main.DEFAULT_ORIGINS
        assert allow_credentials is True


class TestIChingFullReachability:
    def test_all_64_hexagrams_are_reachable(self):
        # Every hexagram 1..64 must be producible by some date — the original
        # `% 64` implementation could only ever yield 1..63.
        seen = set()
        for year in range(1900, 2101):
            for daynum in range(1, 367):
                try:
                    d = dt.date(year, 1, 1) + dt.timedelta(days=daynum - 1)
                except ValueError:
                    continue
                seen.add(main.iching_index(d))
        assert seen == set(range(1, 65))
