from __future__ import annotations

import json

from .models import Explanation


def panel_html(card_id: int) -> str:
    return f"""
<style>
#anki-context-panel {{ margin: 1.4em auto 0; max-width: 760px; padding: .8em 1em;
  border: 1px solid var(--border, #aaa); border-radius: 7px; text-align: left;
  color: var(--fg, inherit); background: var(--canvas, transparent); font-size: .88em; line-height: 1.45; }}
#anki-context-panel .context-heading {{ font-weight: 600; margin-bottom: .45em; }}
#anki-context-panel .context-body {{ white-space: pre-wrap; }}
#anki-context-panel img {{ display: block; max-width: min(100%, 480px); max-height: 360px; object-fit: contain; margin: .4em 0 .7em; }}
#anki-context-panel .context-foot {{ font-size: .78em; opacity: .8; margin-top: .5em; }}
#anki-context-panel button {{ font: inherit; padding: .2em .55em; margin-top: .65em; cursor: pointer; }}
#anki-context-panel .context-warning {{ margin-top: .5em; color: #ad5700; }}
.night-mode #anki-context-panel .context-warning {{ color: #ffba66; }}
</style>
<section id="anki-context-panel" aria-live="polite">
  <div class="context-heading">AI Context</div>
  <div id="anki-context-image"></div>
  <div id="anki-context-body" class="context-body">Loading context…</div>
  <div id="anki-context-warning" class="context-warning"></div>
  <div id="anki-context-foot" class="context-foot"></div>
  <button type="button" onclick="pycmd('anki-context:generate:{int(card_id)}'); this.blur()">Generate / Regenerate</button>
</section>"""


def update_js(result: Explanation | None = None, *, message: str = "", error: bool = False) -> str:
    data = result.as_dict() if result else None
    payload = json.dumps({"data": data, "message": message, "error": error}, ensure_ascii=False)
    return f"""(function(p) {{
      const panel = document.getElementById('anki-context-panel'); if (!panel) return;
      const body = document.getElementById('anki-context-body');
      const imageBox = document.getElementById('anki-context-image');
      const warning = document.getElementById('anki-context-warning');
      const foot = document.getElementById('anki-context-foot');
      imageBox.replaceChildren(); warning.textContent = ''; foot.replaceChildren();
      if (!p.data) {{ body.textContent = p.message; return; }}
      body.textContent = p.data.explanation;
      if (p.data.factual_mismatch) warning.textContent = 'Possible card mismatch: ' + p.data.factual_mismatch;
      const im = p.data.image;
      if (im && im.url && im.url.startsWith('https://')) {{
        const img = document.createElement('img'); img.src = im.url; img.alt = im.title;
        imageBox.appendChild(img);
        const credit = document.createElement('a'); credit.href = im.page_url; credit.textContent = im.source + ' · ' + im.license + ' · ' + im.attribution;
        credit.target = '_blank'; credit.rel = 'noopener noreferrer'; foot.appendChild(credit);
      }} else if (p.data.image_checked) {{
        const note = document.createElement('span'); note.textContent = 'Image not found. ';
        foot.appendChild(note);
      }}
      if (p.data.sources && p.data.sources.length) {{
        const link = document.createElement('a'); link.href = p.data.sources[0]; link.target = '_blank';
        link.rel = 'noopener noreferrer'; link.textContent = 'Reference'; foot.appendChild(link);
      }}
    }})({payload});"""


def is_current_result(sequence: int, card_id: int, key: str, current_sequence: int,
                      active_card: int, active_key: str, state: str, side: str,
                      visible_card: int) -> bool:
    return (sequence == current_sequence and card_id == active_card == visible_card
            and key == active_key and state == "review" and side == "answer")
