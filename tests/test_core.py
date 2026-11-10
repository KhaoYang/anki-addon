import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
import unittest
from pathlib import Path
from unittest.mock import patch

from contextual_explanations.cache import Cache, cache_key
from contextual_explanations.config import Config
from contextual_explanations.images import _commons, find_image, match_score
from contextual_explanations.models import Artwork, CardContext, Explanation
from contextual_explanations.parsing import context_from_card, plain_text
from contextual_explanations.prompt import build_prompt
from contextual_explanations.providers import _parse_result, generate
from contextual_explanations.http import NetworkError, request_json
from contextual_explanations.references import retrieve
from contextual_explanations.service import Service
from contextual_explanations.batch import process_batch
from contextual_explanations.review_ui import is_current_result


def card(**changes):
    base = dict(card_id=10, note_id=2, question="Who painted The Garden of Earthly Delights?",
                answer="Hieronymus Bosch", fields={"Front": "The Garden of Earthly Delights", "Back": "Bosch"},
                deck="Art", tags=("visual-arts",), subject="visual arts", has_rendered_image=False)
    base.update(changes)
    return CardContext(**base)


class FakeNote:
    id = 2
    tags = ["lit"]
    def items(self):
        return [("Front", "<b>Who wrote</b> {{c1::Hamlet}}?"), ("Back", "Shakespeare"), ("Extra", "A tragedy")]


class FakeCard:
    id = 10
    def note(self): return FakeNote()
    def question(self): return "<div>Who wrote {{c1::Hamlet}}?</div>"
    def answer(self): return "<div>Who wrote Hamlet?</div><hr>Shakespeare"


class CoreTests(unittest.TestCase):
    def test_html_cloze_and_fields(self):
        self.assertEqual(plain_text("<style>bad</style><div>Go <b>now</b><br>{{c1::home::hint}}</div>[sound:a.mp3]"), "Go now\nhome")
        ctx = context_from_card(FakeCard(), "Literature")
        self.assertIn("Shakespeare", ctx.answer)
        self.assertIn("Extra", ctx.fields)

    def test_image_detection_only_rendered(self):
        class PicCard(FakeCard):
            def question(self): return "<img src='a.jpg'>"
        self.assertTrue(context_from_card(PicCard(), "Art").has_rendered_image)

    def test_prompt_specific_and_reference(self):
        c = card(question="Go take your seat in Charon's boat / you died afloat", answer="The Wild Honey Suckle (Philip Freneau)")
        prompt = build_prompt(c, "standard", [{"title": "On a Honey Bee", "snippet": "Charon's boat", "url": "https://en.wikisource.org/wiki/On_a_Honey_Bee"}])
        self.assertIn("Charon's boat", prompt)
        self.assertIn("On a Honey Bee", prompt)
        self.assertIn("The Wild Honey Suckle", prompt)

    @patch("contextual_explanations.references.request_json")
    def test_freneau_attribution_reference_when_available(self, get):
        get.return_value = {"query": {"search": [{"title": "On a Honey Bee", "snippet": "Go take your seat in Charon's boat"}]}}
        c = card(question="Go take your seat in Charon's boat / you died afloat", answer="The Wild Honey Suckle (Philip Freneau)")
        refs = retrieve(c)
        self.assertEqual(refs[0]["title"], "On a Honey Bee")
        self.assertIn("On_a_Honey_Bee", refs[0]["url"])

    def test_mismatch_from_source_is_preserved(self):
        result = _parse_result('{"explanation":"The lines concern a drowned bee and Charon.","factual_mismatch":"The source is On a Honey Bee, not The Wild Honey Suckle.","detected_subject":"literature"}')
        self.assertIn("On a Honey Bee", result.factual_mismatch)

    def test_cache_reuse_and_invalidation(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Cache(Path(d) / "c.db")
            c = card()
            key = cache_key(c, "openai", "test", "standard", True)
            cache.put(key, c.card_id, Explanation("Specific context"))
            self.assertEqual(cache.get(key).explanation, "Specific context")
            self.assertNotEqual(key, cache_key(card(question="Edited question"), "openai", "test", "standard", True))
            self.assertNotEqual(key, cache_key(card(card_id=11), "openai", "test", "standard", True))
            self.assertNotEqual(key, cache_key(card(has_rendered_image=True), "openai", "test", "standard", True))
            cache.close()

    def test_image_matching_versions(self):
        work = Artwork("The Garden of Earthly Delights", "Hieronymus Bosch", "1500")
        self.assertGreaterEqual(match_score(work, "The Garden of Earthly Delights", "Hieronymus Bosch", "1500"), .9)
        self.assertEqual(match_score(work, "The Garden of Earthly Delights", "Follower of Bosch", "1800"), 0)
        self.assertEqual(match_score(work, "The Garden of Earthly Delights", "Unknown", "1500"), 0)

    @patch("contextual_explanations.images.request_json")
    def test_commons_selects_full_bosch_work(self, get):
        def page(title):
            return {"title": "File:" + title, "imageinfo": [{"thumburl": "https://example.org/image.jpg",
                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Garden",
                    "extmetadata": {"Artist": {"value": "Hieronymus Bosch"},
                                    "LicenseShortName": {"value": "Public domain"},
                                    "DateTimeOriginal": {"value": "1500"}}}]}
        get.return_value = {"query": {"pages": [
            page("The Garden of Earthly Delights, central panel detail.jpg"),
            page("The Garden of Earthly Delights by Bosch High Resolution.jpg"),
            page("The Haywain by Hieronymus Bosch.jpg")]}}
        results = _commons(Artwork("The Garden of Earthly Delights", "Hieronymus Bosch", "1500"), 8)
        self.assertEqual(len(results), 1)
        self.assertIn("High Resolution", results[0].title)

    @patch("contextual_explanations.images._commons")
    @patch("contextual_explanations.images._met")
    @patch("contextual_explanations.images._aic")
    def test_image_failure(self, aic, met, commons):
        commons.side_effect = TimeoutError()
        met.return_value = []
        aic.return_value = []
        self.assertIsNone(find_image(Artwork("The Garden of Earthly Delights", "Bosch")))

    def test_switching_cards_discards_old_result(self):
        self.assertTrue(is_current_result(3, 10, "key", 3, 10, "key", "review", "answer", 10))
        self.assertFalse(is_current_result(3, 10, "key", 4, 11, "next", "review", "answer", 11))

    def test_batch_cancellation_and_failure(self):
        cancel = threading.Event()
        seen = []
        def create(item):
            seen.append(item)
            if item == 2:
                raise RuntimeError()
        def progress(done, failures):
            if done == 2:
                cancel.set()
        self.assertEqual(process_batch([1, 2, 3], create, cancel, progress), (2, 1))
        self.assertEqual(seen, [1, 2])

    @patch("contextual_explanations.providers.request_json")
    def test_openai_response_shape(self, get):
        get.return_value = {"output": [{"content": [{"type": "output_text", "text": '{"explanation":"Specific passage context."}'}]}]}
        self.assertEqual(generate("openai", "gpt-4.1-mini", "test-key", "prompt", 5).explanation, "Specific passage context.")
        self.assertEqual(get.call_args.kwargs["payload"]["text"]["format"]["type"], "json_object")
        self.assertFalse(get.call_args.kwargs["payload"]["store"])

    @patch("contextual_explanations.http.urlopen")
    def test_http_timeout_and_rate_limit(self, open_url):
        open_url.side_effect = URLError("timed out")
        with self.assertRaisesRegex(NetworkError, "timed out"):
            request_json("https://example.org", retries=0)
        open_url.side_effect = HTTPError("https://example.org", 429, "rate", {}, None)
        with self.assertRaisesRegex(NetworkError, "rate limit"):
            request_json("https://example.org", retries=0)

    @patch("contextual_explanations.service.generate")
    @patch("contextual_explanations.service.retrieve")
    def test_service_reuses_cache(self, retrieve, generate):
        with tempfile.TemporaryDirectory() as d:
            conf = Config(Path(d)); conf.values.update(images=False, references=False, rate_seconds=0)
            service = Service(conf, Cache(Path(d) / "c.db"))
            generate.return_value = Explanation("This panel shows Bosch's imagined earthly temptations.")
            service.create(card())
            service.create(card())
            self.assertEqual(generate.call_count, 1)
            service.cache.close()

    @patch("contextual_explanations.service.generate")
    def test_simultaneous_requests_share_cached_result(self, generate):
        with tempfile.TemporaryDirectory() as d:
            conf = Config(Path(d)); conf.values.update(images=False, references=False, rate_seconds=0)
            service = Service(conf, Cache(Path(d) / "c.db"))
            def slow(*args):
                time.sleep(.03)
                return Explanation("One explanation")
            generate.side_effect = slow
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(service.create, [card(), card()]))
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(results[0].explanation, results[1].explanation)
            service.cache.close()


if __name__ == "__main__":
    unittest.main()
