import argparse
from scrapy.commands import fetch
from scrapy.utils.response import open_in_browser


class Command(fetch.Command):
    def short_desc(self):
        return "Open URL in browser, as seen by Scrapy"

    def long_desc(self):
        return (
            "Fetch a URL using the Scrapy downloader and show its contents in a browser"
        )

    def add_options(self, parser):
        super().add_options(parser)
        parser.add_argument("--headers", help=argparse.SUPPRESS)

    def _print_response(self, response, opts):
        open_in_browser(response)
