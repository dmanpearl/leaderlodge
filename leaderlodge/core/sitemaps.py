from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticPageSitemap(Sitemap):
    changefreq = "weekly"
    protocol = "https"

    pages = [
        ("core:dashboard", 0.9),
        ("core:about", 0.8),
        ("core:about_insights", 0.7),
        ("core:about_scoring", 0.7),
    ]

    def items(self):
        return self.pages

    def location(self, item):
        url_name, _ = item
        return reverse(url_name)

    def priority(self, item):
        _, prio = item
        return prio
