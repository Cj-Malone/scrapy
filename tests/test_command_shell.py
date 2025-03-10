from pathlib import Path

from twisted.trial import unittest
from twisted.internet import defer

from scrapy.utils.testsite import SiteTest
from scrapy.utils.testproc import ProcessTest

from tests import tests_datadir, NON_EXISTING_RESOLVABLE


class ShellTest(ProcessTest, SiteTest, unittest.TestCase):

    command = "shell"

    @defer.inlineCallbacks
    def test_empty(self):
        _, out, _ = yield self.execute(["-c", "item"])
        assert b"{}" in out

    @defer.inlineCallbacks
    def test_response_body(self):
        _, out, _ = yield self.execute([self.url("/text"), "-c", "response.body"])
        assert b"Works" in out

    @defer.inlineCallbacks
    def test_response_type_text(self):
        _, out, _ = yield self.execute([self.url("/text"), "-c", "type(response)"])
        assert b"TextResponse" in out

    @defer.inlineCallbacks
    def test_response_type_html(self):
        _, out, _ = yield self.execute([self.url("/html"), "-c", "type(response)"])
        assert b"HtmlResponse" in out

    @defer.inlineCallbacks
    def test_response_selector_html(self):
        xpath = "response.xpath(\"//p[@class='one']/text()\").get()"
        _, out, _ = yield self.execute([self.url("/html"), "-c", xpath])
        self.assertEqual(out.strip(), b"Works")

    @defer.inlineCallbacks
    def test_response_encoding_gb18030(self):
        _, out, _ = yield self.execute(
            [self.url("/enc-gb18030"), "-c", "response.encoding"]
        )
        self.assertEqual(out.strip(), b"gb18030")

    @defer.inlineCallbacks
    def test_redirect(self):
        _, out, _ = yield self.execute([self.url("/redirect"), "-c", "response.url"])
        assert out.strip().endswith(b"/redirected")

    @defer.inlineCallbacks
    def test_redirect_follow_302(self):
        _, out, _ = yield self.execute(
            [self.url("/redirect-no-meta-refresh"), "-c", "response.status"]
        )
        assert out.strip().endswith(b"200")

    @defer.inlineCallbacks
    def test_redirect_not_follow_302(self):
        _, out, _ = yield self.execute(
            [
                "--no-redirect",
                self.url("/redirect-no-meta-refresh"),
                "-c",
                "response.status",
            ]
        )
        assert out.strip().endswith(b"302")

    @defer.inlineCallbacks
    def test_fetch_redirect_follow_302(self):
        """Test that calling ``fetch(url)`` follows HTTP redirects by default."""
        url = self.url("/redirect-no-meta-refresh")
        code = f"fetch('{url}')"
        errcode, out, errout = yield self.execute(["-c", code])
        self.assertEqual(errcode, 0, out)
        assert b"Redirecting (302)" in errout
        assert b"Crawled (200)" in errout

    @defer.inlineCallbacks
    def test_fetch_redirect_not_follow_302(self):
        """Test that calling ``fetch(url, redirect=False)`` disables automatic redirects."""
        url = self.url("/redirect-no-meta-refresh")
        code = f"fetch('{url}', redirect=False)"
        errcode, out, errout = yield self.execute(["-c", code])
        self.assertEqual(errcode, 0, out)
        assert b"Crawled (302)" in errout

    @defer.inlineCallbacks
    def test_request_replace(self):
        url = self.url("/text")
        code = f"fetch('{url}') or fetch(response.request.replace(method='POST'))"
        errcode, out, _ = yield self.execute(["-c", code])
        self.assertEqual(errcode, 0, out)

    @defer.inlineCallbacks
    def test_scrapy_import(self):
        url = self.url("/text")
        code = f"fetch(scrapy.Request('{url}'))"
        errcode, out, _ = yield self.execute(["-c", code])
        self.assertEqual(errcode, 0, out)

    @defer.inlineCallbacks
    def test_local_file(self):
        filepath = Path(tests_datadir, "test_site", "index.html")
        _, out, _ = yield self.execute([str(filepath), "-c", "item"])
        assert b"{}" in out

    @defer.inlineCallbacks
    def test_local_nofile(self):
        filepath = "file:///tests/sample_data/test_site/nothinghere.html"
        errcode, out, err = yield self.execute(
            [filepath, "-c", "item"], check_code=False
        )
        self.assertEqual(errcode, 1, out or err)
        self.assertIn(b"No such file or directory", err)

    @defer.inlineCallbacks
    def test_dns_failures(self):
        if NON_EXISTING_RESOLVABLE:
            raise unittest.SkipTest("Non-existing hosts are resolvable")
        url = "www.somedomainthatdoesntexi.st"
        errcode, out, err = yield self.execute([url, "-c", "item"], check_code=False)
        self.assertEqual(errcode, 1, out or err)
        self.assertIn(b"DNS lookup failed", err)

    @defer.inlineCallbacks
    def test_shell_fetch_async(self):
        reactor_path = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
        url = self.url("/html")
        code = f"fetch('{url}')"
        args = ["-c", code, "--set", f"TWISTED_REACTOR={reactor_path}"]
        _, _, err = yield self.execute(args, check_code=True)
        self.assertNotIn(b"RuntimeError: There is no current event loop in thread", err)
