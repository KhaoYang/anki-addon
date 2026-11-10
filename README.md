# AI Contextual Explanations for Anki

An Anki desktop add-on that adds a short explanation after you reveal a card's answer. It uses the front and back of the card, note fields, deck, and tags to explain the specific clue or passage. For visual arts cards, it can show a conservatively matched public-domain image. It never edits your notes or scheduling data.

## Install

The add-on targets current Anki desktop releases with Qt 6 and the `card_will_show`, `reviewer_did_show_answer`, and `webview_did_receive_js_message` hooks (24.11 or newer). It has no third-party Python dependencies. This project was built without Anki installed, so the reviewer UI still needs an in-app smoke test.

1. Run `py build.py` (or `python build.py`) in this repository.
2. In Anki, choose **Tools → Add-ons → Install from file** and select `dist/ai-contextual-explanations.ankiaddon`.
3. Restart Anki. Open **Tools → AI Context settings…**.
4. Choose OpenAI, Gemini, or Ollama and a model. For hosted providers, set `OPENAI_API_KEY` or `GEMINI_API_KEY` in the environment before starting Anki, or enter a key in settings. Environment keys take precedence.
5. Review a card and reveal its answer. The AI Context panel appears beneath the normal answer. Use **Regenerate** to replace its cached explanation.

OpenAI defaults to `gpt-4.1-mini`. When switching providers, change the model name to one available in your account or Ollama installation. For Ollama, run its local server first; the default URL is `http://127.0.0.1:11434`. The add-on only accepts localhost Ollama URLs.

## Settings and data

- **Generate after reveal** can be disabled for manual generation. (The panel button then starts the request.)
- **Artwork images** and **Wikisource search** can be enabled independently.
- Explanation length has short, standard, and detailed options.
- **Clear explanation cache** removes locally stored responses and image metadata.
- **Tools → AI Context: pre-generate deck…** prepares selected deck and subdeck cards in small UI batches, then generates uncached explanations in background. It shows progress, supports cancellation, and continues after individual failures. API call counts are estimates; no cost figure is shown because model pricing varies.

Settings and the SQLite cache live in the add-on's `user_files` directory. A key entered through settings is stored there in plain text with restrictive file permissions where supported. Prefer environment variables if that matters to you. No credentials are logged or put in the cache. OpenAI requests set `store: false`; other providers have their own data policies.

Cache keys include card ID, note ID, rendered question and answer, note fields, deck, tags, provider, model, length, retrieval setting, and prompt version. Editing relevant card content or changing the model creates a new entry. Separate cloze cards have separate keys.

## Artwork matching

The add-on searches Wikimedia Commons, the Metropolitan Museum of Art, and the Art Institute of Chicago. It checks title, artist, and available date and institution data. Commons detail crops and individual panels are excluded when looking for a whole work. Only public-domain or explicitly reusable Commons media, and public-domain museum objects, are displayed. When no match clears the threshold, the panel shows **Image not found**. Images are linked from their source and are not inserted into Anki notes or media. Image URL, source, license, and attribution are cached with the explanation.

The Met search uses the [v1.1 API](https://metmuseum.github.io/) introduced before retirement of v1 search in October 2026. Image URLs from the Art Institute follow its [IIIF guidance](https://api.artic.edu/docs/). Commons metadata uses MediaWiki's [imageinfo API](https://www.mediawiki.org/wiki/API:Imageinfo).

## Accuracy and limitations

The prompt asks the model to focus on the front and flag possible answer mismatches. Optional Wikisource search gives it short, linked source snippets; search results are evidence to inspect, not automatic fact verification. A model's mismatch report is labeled **Possible card mismatch**. This is particularly important for quoted text with ambiguous or incorrect attribution. No card answer is overwritten.

Artwork identification relies on the model returning a usable title and artist. Some museum works lack public-domain images or complete metadata; the matcher will then leave the image empty. Remote images require network access during review. The add-on does not yet offer persistent Anki media insertion, user choice among close image matches, or dependable price estimates. Factual retrieval currently covers a small Wikisource search rather than a full reference corpus.

## Development and tests

Run `py -m unittest discover -s tests -v` on Windows, or `python -m unittest discover -s tests -v` elsewhere. Core modules import without Anki. External API behavior is mocked in unit tests. Optional live image checks can be run with `python -c "from contextual_explanations.images import find_image; from contextual_explanations.models import Artwork; print(find_image(Artwork('The Garden of Earthly Delights','Hieronymus Bosch','1500')))"`.

For an Anki smoke test, install the archive, configure a working provider, review an ordinary and a cloze card, confirm the explanation appears only after answer reveal, advance while a request is pending, repeat a card to check cache reuse, and try the Bosch artwork card. Anki was unavailable in the build environment, so these checks are not claimed as completed.

## Troubleshooting

- **Authentication failed:** check the key and provider; environment variables override the settings field.
- **No explanation:** confirm a model is set, network access is available, and the provider supports JSON responses. Use Regenerate after correcting settings.
- **Image not found:** the artwork may lack a reusable image, the model may not have identified title and artist, or the match may be ambiguous.
- **Slow response:** increase the timeout or disable Wikisource search and images. Network operations run in background; review controls remain available.
