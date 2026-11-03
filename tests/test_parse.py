import unittest

from nes_monitor.parse import activity_url, first_post_text, is_newer, page_url, parse_listings, parse_rss_bodies

FORUM = "https://www.northeastshooters.com/xen/forums/wts-wtt-handguns.213/"

PAGE = """
<div class="structItem structItem--thread js-inlineModContainer js-threadListItem-519583" data-author="medic12">
  <div class="structItem-title">
    <a href="/xen/forums/wts-wtt-handguns.213/?prefix_id=1" class="labelLink" rel="nofollow"><span class="label label--primary" dir="auto">WTS</span></a>
    <a href="/xen/threads/springfield-operator-1911.519583/" data-preview-url="/xen/threads/springfield-operator-1911.519583/preview">
      Springfield Operator 1911
    </a>
  </div>
  <a href="/xen/members/medic12.1799/" class="username " dir="auto">medic12</a>
  <time class="u-dt" datetime="2026-11-01T22:24:18-0500"></time>
  <time class="structItem-latestDate u-dt" datetime="2026-11-03T14:47:27-0500"></time>
</div>
<div class="structItem js-threadListItem-519575">
  <div class="structItem-title">
    <a href="/xen/forums/wts-wtt-handguns.213/?prefix_id=4" class="labelLink"><span class="label label--red" dir="auto">SOLD</span></a>
    <a href="/xen/threads/glock-19.519575/" data-preview-url="/xen/threads/glock-19.519575/preview">Glock 19</a>
  </div>
  <a href="/xen/members/kag.1/" class="username ">KAG Arms</a>
  <time class="u-dt" datetime="2026-11-01T17:50:56-0500"></time>
</div>
"""

RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <item>
      <title>Springfield Operator 1911</title>
      <link>https://www.northeastshooters.com/xen/threads/springfield-operator-1911.519583/</link>
      <guid>urn:xenforo:thread:519583</guid>
      <content:encoded><![CDATA[<div class="bbWrapper">Operator in 45 ACP.<br />Price $1100</div>]]></content:encoded>
    </item>
  </channel>
</rss>
"""

PREVIEW = """
<div class="bbWrapper"><b>Description :</b> New 45 ACP.
  <div class="bbImage">photo</div>
  Still the same pistol.
</div>
<div class="after">ignore</div>
"""


class ParseTests(unittest.TestCase):
    def test_page_url_sorts_by_start_date(self):
        self.assertIn("order=post_date", page_url(FORUM, 1))
        self.assertIn("/page-2/", page_url(FORUM, 2))
        self.assertNotIn("order=", activity_url(FORUM, 1))

    def test_bump_time_is_separate_from_post_time(self):
        first = parse_listings(PAGE, FORUM)[0]
        self.assertEqual(first.posted_at, "2026-11-01T22:24:18-0500")
        self.assertEqual(first.bumped_at, "2026-11-03T14:47:27-0500")
        self.assertTrue(is_newer(first.bumped_at, first.posted_at))
        self.assertFalse(is_newer(first.posted_at, first.bumped_at))
        second = parse_listings(PAGE, FORUM)[1]
        self.assertEqual(second.bumped_at, second.posted_at)

    def test_listings(self):
        listings = parse_listings(PAGE, FORUM)
        self.assertEqual([item.thread_id for item in listings], [519583, 519575])
        first = listings[0]
        self.assertEqual(first.title, "Springfield Operator 1911")
        self.assertEqual(first.prefix, "WTS")
        self.assertEqual(first.author, "medic12")
        self.assertEqual(first.posted_at, "2026-11-01T22:24:18-0500")
        self.assertTrue(first.url.endswith("/xen/threads/springfield-operator-1911.519583/"))
        self.assertTrue(first.preview_url.endswith("/preview"))
        self.assertEqual(listings[1].prefix, "SOLD")

    def test_rss_body(self):
        bodies = parse_rss_bodies(RSS)
        self.assertIn("45 ACP", bodies[519583])

    def test_nested_post_html(self):
        text = first_post_text(PREVIEW)
        self.assertIn("New 45 ACP", text)
        self.assertIn("Still the same pistol", text)
        self.assertNotIn("ignore", text)


if __name__ == "__main__":
    unittest.main()
