import unittest

from nes_monitor.match import evaluate, should_fetch_body, skip_prefix


class MatchTests(unittest.TestCase):
    def test_explicit_calibers(self):
        samples = [
            "Springfield Operator 45 ACP",
            "HK USP Tactical .45 ACP",
            "1911 Colt defender in 45acp",
            "Chambered in .45",
            "Smith & Wesson Model 22 in 45 Colt",
            "USP 45",
            "Colt .45",
            "45 GAP",
            "45 Super",
        ]
        for title in samples:
            matched, reason = evaluate(title)
            self.assertTrue(matched, title)
            self.assertTrue(reason, title)

    def test_known_models_in_the_title(self):
        for title in ["Glock 30 Gen 4", "Glock 21", "Glock 41 MOS", "HK45", "FNX-45"]:
            matched, _reason = evaluate(title)
            self.assertTrue(matched, title)

    def test_model_mention_in_the_body_is_not_enough(self):
        matched, _reason = evaluate("WTS holster", "This fits my Glock 21")
        self.assertFalse(matched)

    def test_glock_45_is_9mm(self):
        title = "Glock 45 Gen 6"
        body = (
            "For sale NIB Glock 45 Gen 6. The GLOCK 45 combines a full-size frame "
            "with a compact slide. Chambered in 9mm."
        )
        self.assertFalse(evaluate(title, body)[0])
        self.assertFalse(should_fetch_body(title))

    def test_casual_glock_45_mention_is_not_a_caliber(self):
        title = "Glock 19 Gen 6 and a dot"
        body = "Near new Glock 19. Getting a 45 gen 6 for steel. $600 obo."
        self.assertFalse(evaluate(title, body)[0])
        self.assertFalse(should_fetch_body(title))

    def test_other_cartridges_and_prices(self):
        for title in [
            "Glock 19 Gen 6",
            "Walther P22Q 22 LR [$299]",
            "M&P 10mm M2.0",
            ".450 Bushmaster pistol",
            ".45-70 revolver",
            "Ace .45 Black Powder kit",
            "Glock 17 [$450]",
            "Sig P365 xmacro",
        ]:
            self.assertFalse(evaluate(title)[0], title)

    def test_black_powder_does_not_hide_a_real_45_acp(self):
        matched, _reason = evaluate("Conversion kit", "Black powder note, but the gun is 45 ACP")
        self.assertTrue(matched)

    def test_1911_needs_a_stated_caliber(self):
        title = "WW2 M1911A1 Colt Frame / Remington Rand Slide"
        body = "Colt frame from the 1945 production block, with slide and barrel."
        self.assertFalse(evaluate(title, body)[0])
        self.assertTrue(should_fetch_body(title))
        self.assertTrue(evaluate(title, "Complete pistol in 45 ACP")[0])

    def test_ambiguous_titles_need_the_post(self):
        self.assertTrue(should_fetch_body("Springfield Operator 1911"))
        self.assertTrue(should_fetch_body("3 pistols for sale"))
        self.assertFalse(should_fetch_body("Glock 30 Gen 4"))
        self.assertFalse(should_fetch_body("Cz p10c"))

    def test_sold_and_wtb_are_skipped(self):
        self.assertTrue(skip_prefix("SOLD", "Tisas 1911A1 45 ACP"))
        self.assertTrue(skip_prefix("WTB", "Looking for a 1911"))
        self.assertTrue(skip_prefix("", "WTB 1911"))
        self.assertFalse(skip_prefix("WTS", "Springfield Operator 1911"))
        self.assertFalse(skip_prefix("WTT", "Glock 21"))


if __name__ == "__main__":
    unittest.main()
