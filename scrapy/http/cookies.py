import re
import time
from http.cookiejar import CookieJar as _CookieJar, DefaultCookiePolicy

from scrapy.utils.httpobj import urlparse_cached
from scrapy.utils.python import to_unicode


# Defined in the http.cookiejar module, but undocumented:
# https://github.com/python/cpython/blob/v3.9.0/Lib/http/cookiejar.py#L527
IPV4_RE = re.compile(r"\.\d+$", re.ASCII)


class CookieJar:
    def __init__(self, policy=None, check_expired_frequency=10000):
        self.policy = policy or DefaultCookiePolicy()
        self.jar = _CookieJar(self.policy)
        self.jar._cookies_lock = _DummyLock()
        self.check_expired_frequency = check_expired_frequency
        self.processed = 0

    def extract_cookies(self, response, request):
        wreq = WrappedRequest(request)
        wrsp = WrappedResponse(response)
        return self.jar.extract_cookies(wrsp, wreq)

    def add_cookie_header(self, request):
        wreq = WrappedRequest(request)
        self.policy._now = self.jar._now = int(time.time())

        # the cookiejar implementation iterates through all domains
        # instead we restrict to potential matches on the domain
        req_host = urlparse_cached(request).hostname
        if not req_host:
            return

        if not IPV4_RE.search(req_host):
            hosts = potential_domain_matches(req_host)
            if "." not in req_host:
                hosts += [req_host + ".local"]
        else:
            hosts = [req_host]

        cookies = []
        for host in hosts:
            if host in self.jar._cookies:
                cookies += self.jar._cookies_for_domain(host, wreq)

        attrs = self.jar._cookie_attrs(cookies)
        if attrs:
            if not wreq.has_header("Cookie"):
                wreq.add_unredirected_header("Cookie", "; ".join(attrs))

        self.processed += 1
        if self.processed % self.check_expired_frequency == 0:
            # This is still quite inefficient for large number of cookies
            self.jar.clear_expired_cookies()

    @property
    def _cookies(self):
        return self.jar._cookies

    def clear_session_cookies(self, *args, **kwargs):
        return self.jar.clear_session_cookies(*args, **kwargs)

    def clear(self, domain=None, path=None, name=None):
        return self.jar.clear(domain, path, name)

    def __iter__(self):
        return iter(self.jar)

    def __len__(self):
        return len(self.jar)

    def set_policy(self, pol):
        return self.jar.set_policy(pol)

    def make_cookies(self, response, request):
        wreq = WrappedRequest(request)
        wrsp = WrappedResponse(response)
        return self.jar.make_cookies(wrsp, wreq)

    def set_cookie(self, cookie):
        self.jar.set_cookie(cookie)

    def set_cookie_if_ok(self, cookie, request):
        self.jar.set_cookie_if_ok(cookie, WrappedRequest(request))


def potential_domain_matches(domain):
    """Potential domain matches for a cookie

    >>> potential_domain_matches('www.example.com')
    ['www.example.com', 'example.com', '.www.example.com', '.example.com']

    """
    matches = [domain]
    try:
        start = domain.index(".") + 1
        end = domain.rindex(".")
        while start < end:
            matches.append(domain[start:])
            start = domain.index(".", start) + 1
    except ValueError:
        pass
    return matches + ["." + d for d in matches]


class _DummyLock:
    def acquire(self):
        pass

    def release(self):
        pass


class WrappedRequest:
    """Wraps a scrapy Request class with methods defined by urllib2.Request class to interact with CookieJar class

    see http://docs.python.org/library/urllib2.html#urllib2.Request
    """

    def __init__(self, request):
        self.request = request

    def get_full_url(self):
        return self.request.url

    def get_host(self):
        return urlparse_cached(self.request).netloc

    def get_type(self):
        return urlparse_cached(self.request).scheme

    def is_unverifiable(self):
        """Unverifiable should indicate whether the request is unverifiable, as defined by RFC 2965.

        It defaults to False. An unverifiable request is one whose URL the user did not have the
        option to approve. For example, if the request is for an image in an
        HTML document, and the user had no option to approve the automatic
        fetching of the image, this should be true.
        """
        return self.request.meta.get("is_unverifiable", False)

    @property
    def full_url(self):
        return self.get_full_url()

    @property
    def host(self):
        return self.get_host()

    @property
    def type(self):
        return self.get_type()

    @property
    def unverifiable(self):
        return self.is_unverifiable()

    @property
    def origin_req_host(self):
        return urlparse_cached(self.request).hostname

    def has_header(self, name):
        return name in self.request.headers

    def get_header(self, name, default=None):
        return to_unicode(self.request.headers.get(name, default), errors="replace")

    def header_items(self):
        return [
            (
                to_unicode(k, errors="replace"),
                [to_unicode(x, errors="replace") for x in v],
            )
            for k, v in self.request.headers.items()
        ]

    def add_unredirected_header(self, name, value):
        self.request.headers.appendlist(name, value)


class WrappedResponse:
    def __init__(self, response):
        self.response = response

    def info(self):
        return self

    def get_all(self, name, default=None):
        return [
            to_unicode(v, errors="replace") for v in self.response.headers.getlist(name)
        ]
