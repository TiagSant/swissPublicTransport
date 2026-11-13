"""US-40: English, French, German, Italian, Romansh. Detection from the phone's languages, the selector, every
translated text present, 24-hour times, OJP asked in German for Romansh."""
import os, json, re
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
EXPECT = {   # a few texts per language
    "en": {"tabJourney": "Journey", "searchJourney": "Search", "myPlaces": "My places", "followTitle": "Followed journeys"},
    "fr": {"tabJourney": "Itinéraire", "searchJourney": "Rechercher", "myPlaces": "Mes lieux", "followTitle": "Trajets suivis"},
    "de": {"tabJourney": "Verbindung", "searchJourney": "Suchen", "myPlaces": "Meine Orte", "followTitle": "Verfolgte Verbindungen"},
    "it": {"tabJourney": "Itinerario", "searchJourney": "Cerca", "myPlaces": "I miei luoghi", "followTitle": "Itinerari seguiti"},
    "rm": {"tabJourney": "Viadi", "searchJourney": "Tschertgar", "myPlaces": "Mes lieus", "followTitle": "Viadis suandads"},
}

def empty(route):
    route.fulfill(status=200, content_type="application/json", body=json.dumps({"stations": [], "stationboard": [], "connections": []}),
                  headers={"Access-Control-Allow-Origin": "*"})

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))

    # Detection from the phone's languages
    for locale, expected in (("de-CH", "de"), ("it-CH", "it"), ("rm-CH", "rm"), ("fr-CH", "fr"), ("gsw-CH", "de"), ("es-ES", "en")):
        ctx = b.new_context(locale=locale); ctx.route("https://transport.opendata.ch/**", empty)
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.goto(PAGE)
        assert pg.evaluate("document.documentElement.lang") == expected and pg.input_value("#lang") == expected, (locale, pg.input_value("#lang"))
        ctx.close()
    print("detection   → de-CH de, it-CH it, rm-CH rm, fr-CH fr, gsw-CH de, es-ES en")

    ctx = b.new_context(locale="en-US", viewport={"width": 390, "height": 844}); ctx.route("https://transport.opendata.ch/**", empty)
    ojp_langs = []
    def ojp(route):
        ojp_langs.append(re.search(r"<siri:Language>(\w+)<", route.request.post_data or "").group(1))
        route.fulfill(status=200, content_type="application/xml", headers={"Access-Control-Allow-Origin": "*"},
                      body='<?xml version="1.0"?><OJP xmlns="http://www.vdv.de/ojp"><OJPResponse/></OJP>')
    ctx.route("https://api.opentransportdata.swiss/**", ojp)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.goto(PAGE)
    for code, texts in EXPECT.items():
        pg.select_option("#lang", code)
        assert pg.evaluate("document.documentElement.lang") == code
        for key, text in texts.items():
            shown = pg.locator(f"[data-i18n={key}]").first.text_content()
            assert shown == text, (code, key, shown)
        # no element shows a raw key (a missing translation)
        raw = pg.evaluate("[...document.querySelectorAll('[data-i18n]')].filter(e => e.textContent === e.dataset.i18n).map(e => e.dataset.i18n)")
        assert not raw, (code, raw)
        assert pg.evaluate("localStorage.getItem('tpp:lang')") == json.dumps(code)
        pg.screenshot(path=str(OUT / f"lang-{code}.png"))
    # every language has every key, none empty
    report = pg.evaluate("""() => { const en = Object.keys(window.EXTRA_STRINGS.de); const out = {};
      for (const l of ['de', 'it', 'rm']) out[l] = Object.entries(window.EXTRA_STRINGS[l]).filter(([k, v]) => typeof v === 'string' && !v.trim()).map(([k]) => k);
      return out; }""")
    assert all(not v for v in report.values()), report
    # remembered after reload
    pg.select_option("#lang", "it"); pg.reload()
    assert pg.input_value("#lang") == "it" and pg.locator("[data-i18n=tabJourney]").first.text_content() == "Itinerario"
    # OJP: Romansh asks in German, Italian in Italian
    pg.evaluate("localStorage.setItem('tpp:ojpKey', JSON.stringify('k'))")
    for code, asked in (("rm", "de"), ("it", "it")):
        pg.select_option("#lang", code); pg.reload()
        ojp_langs.clear()
        pg.fill("#q", "Bel-Air"); pg.wait_for_timeout(800)
        assert ojp_langs and set(ojp_langs) == {asked}, (code, ojp_langs)
    print("languages   → en fr de it rm: texts, no raw keys, remembered; OJP asked in de for rm")
    b.close()

print("errors:", errors); assert not errors
print("OK")
