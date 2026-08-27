from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from real_estate_monitor.config import Settings
from real_estate_monitor.models import ListingSnapshot
from real_estate_monitor.notify import EmailNotifier
from real_estate_monitor.scrapers import available_sites, build_scraper

REPORT_TIMEZONE = timezone(timedelta(hours=2))
DEFAULT_SITE_TIMEOUT_SECONDS = 900
PRICE_NUMBER_PATTERN = r"\d+(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"

SITE_NAMES = {
    "drumelia": "Drumelia",
    "homerun": "Homerun",
    "dmproperties": "DM Properties",
    "panorama": "Panorama",
    "marbella_ev": "Marbella EV",
}

PROPERTY_TYPE_TERMS = {
    "duplex_penthouse": (
        "duplex penthouse",
        "duplex penthouses",
        "atico duplex",
        "ático duplex",
        "duplex atico",
        "duplex ático",
    ),
    "penthouse": ("penthouse", "penthouses", "atico", "ático"),
    "apartment": ("apartment", "apartments", "apartamento", "apartamentos", "piso", "pisos", "ground floor"),
    "villa": ("villa", "villas", "chalet", "chalets"),
    "townhouse": ("townhouse", "town house", "townhouses", "adosado", "adosados"),
    "plot": ("plot", "plots", "land", "parcel", "parcela", "parcelas"),
}

PROPERTY_TYPE_LABELS = {
    "duplex_penthouse": "duplex penthouse",
    "penthouse": "penthouse",
    "apartment": "apartment",
    "villa": "villa",
    "townhouse": "townhouse",
    "plot": "plot",
}

FEATURE_TERMS = {
    "renovation_needed": (
        "needs renovation",
        "need of renovation",
        "in need of renovation",
        "renovation needed",
        "renovation project",
        "renovation opportunity",
        "to renovate",
        "to be renovated",
        "requires renovation",
        "requires refurbishment",
        "refurbishment project",
        "reform project",
        "to reform",
        "needs reform",
        "in need of reform",
        "needs updating",
        "to update",
        "requires updating",
        "potential to renovate",
        "renovation potential",
        "investment opportunity",
        "partial renovation needed",
        "reforma",
        "para reformar",
        "necesita reforma",
        "necesita renovacion",
        "necesita renovación",
        "a reformar",
    ),
    "renovated": (
        "renovated",
        "refurbished",
        "reformed",
        "newly renovated",
        "recently renovated",
        "fully renovated",
        "completely renovated",
        "reformado",
        "reformada",
        "renovado",
        "renovada",
    ),
    "beachfront": (
        "beachfront",
        "frontline beach",
        "front line beach",
        "beachside",
        "beach-side",
        "first line beach",
        "beach front",
        "seafront",
        "sea front",
        "primera linea",
        "primera línea",
    ),
    "sea_views": (
        "sea view",
        "sea views",
        "sea-view",
        "sea-views",
        "views to the sea",
        "vistas al mar",
        "vista al mar",
        "panoramic sea",
    ),
    "new_build": (
        "new build",
        "new-build",
        "new development",
        "brand new",
        "brand-new",
        "newly built",
        "obra nueva",
        "nueva construccion",
        "nueva construcción",
    ),
    "key_ready": (
        "key ready",
        "key-ready",
        "ready to move",
        "move-in ready",
        "turnkey",
        "turn key",
        "llave en mano",
    ),
    "gated_community": (
        "gated community",
        "gated complex",
        "secure community",
        "24-hour security",
        "24 hour security",
        "urbanizacion cerrada",
        "urbanización cerrada",
    ),
    "project": (
        "project",
        "building license",
        "building licence",
        "license",
        "licence",
        "licencia",
        "approved project",
    ),
}

TERM_GROUPS = {**FEATURE_TERMS, **PROPERTY_TYPE_TERMS}

LOCATION_TERMS = {
    "marbella": ("marbella", "marbella all"),
    "nueva_andalucia": ("nueva andalucia", "nueva andalucía", "golf valley"),
    "golden_mile": ("golden mile", "milla de oro"),
    "puente_romano": ("puente romano", "marina puente romano"),
    "la_zagaleta": ("la zagaleta", "zagaleta"),
    "benahavis": ("benahavis", "benahavís"),
    "estepona": ("estepona",),
    "sotogrande": ("sotogrande",),
    "san_pedro": ("san pedro", "san pedro de alcantara", "san pedro de alcántara"),
    "aloha": ("aloha",),
    "sierra_blanca": ("sierra blanca",),
    "la_quinta": ("la quinta",),
    "nagueles": ("nagueles", "nagüeles"),
}

LOCATION_LABELS = {
    "marbella": "Marbella",
    "nueva_andalucia": "Nueva Andalucia",
    "golden_mile": "Golden Mile",
    "puente_romano": "Puente Romano",
    "la_zagaleta": "La Zagaleta",
    "benahavis": "Benahavis",
    "estepona": "Estepona",
    "sotogrande": "Sotogrande",
    "san_pedro": "San Pedro",
    "aloha": "Aloha",
    "sierra_blanca": "Sierra Blanca",
    "la_quinta": "La Quinta",
    "nagueles": "Nagueles",
}

FRONTLINE_BEACH_TERMS = (
    "beachfront",
    "frontline beach",
    "front line beach",
    "first line beach",
    "beach front",
    "seafront",
    "sea front",
    "primera linea de playa",
    "primera línea de playa",
)

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "any",
    "bed",
    "bedroom",
    "bedrooms",
    "beds",
    "between",
    "below",
    "budget",
    "for",
    "from",
    "in",
    "least",
    "less",
    "need",
    "needed",
    "needs",
    "million",
    "millions",
    "minimum",
    "of",
    "over",
    "properties",
    "property",
    "than",
    "the",
    "to",
    "under",
    "with",
}


@dataclass(frozen=True)
class CustomReportRequest:
    query: str
    recipient: str
    min_price: int | None
    max_price: int | None
    min_beds: float | None
    max_beds: float | None
    property_type: str | None
    locations: tuple[str, ...]
    features: tuple[str, ...]
    required_groups: tuple[str, ...]
    required_phrases: tuple[str, ...]
    required_terms: tuple[str, ...]
    require_frontline_beach: bool = False


@dataclass(frozen=True)
class SiteCustomReport:
    site: str
    scraped_count: int
    listings: list[ListingSnapshot]
    error: str | None = None


@dataclass(frozen=True)
class CustomReportResult:
    request: CustomReportRequest
    sections: list[SiteCustomReport]
    markdown_path: Path
    html_path: Path

    @property
    def total_matches(self) -> int:
        return sum(len(section.listings) for section in self.sections)


def parse_custom_report_request(query: str, recipient: str) -> CustomReportRequest:
    cleaned_query = " ".join(query.strip().split())
    normalized = _normalize(_separate_number_words(cleaned_query))
    keyword_query = _strip_price_phrases(normalized)
    property_type = _parse_property_type(normalized)
    locations = tuple(location for location, terms in LOCATION_TERMS.items() if any(term in normalized for term in terms))
    features = tuple(
        feature
        for feature, terms in FEATURE_TERMS.items()
        if any(term in normalized for term in terms)
        or (feature == "renovation_needed" and _has_renovation_needed_intent(normalized))
    )
    required_groups = features + ((property_type,) if property_type else ())
    required_phrases = _required_phrases(normalized, property_type)
    grouped_terms = {term for group in required_groups for term in TERM_GROUPS[group]}
    grouped_terms.update(required_phrases)
    grouped_terms.update(term for location in locations for term in LOCATION_TERMS[location])
    words = tuple(
        word
        for word in re.findall(r"[a-z0-9]+", keyword_query)
        if len(word) > 2 and word not in STOP_WORDS and not any(word in term for term in grouped_terms)
    )
    return CustomReportRequest(
        query=cleaned_query,
        recipient=recipient.strip(),
        min_price=_parse_min_price(normalized),
        max_price=_parse_max_price(normalized),
        min_beds=_parse_min_beds(normalized),
        max_beds=_parse_max_beds(normalized),
        property_type=property_type,
        locations=locations,
        features=features,
        required_groups=required_groups,
        required_phrases=required_phrases,
        required_terms=words,
        require_frontline_beach=any(term in normalized for term in FRONTLINE_BEACH_TERMS),
    )


async def build_and_send_custom_report(
    query: str,
    recipient: str,
    settings: Settings,
    *,
    output_dir: Path | None = None,
    site_timeout_seconds: int = DEFAULT_SITE_TIMEOUT_SECONDS,
) -> CustomReportResult:
    request = parse_custom_report_request(query, recipient)
    sections = await scrape_custom_report_sections(request, settings, site_timeout_seconds=site_timeout_seconds)
    output_dir = output_dir or settings.report_dir / "custom"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _slugify(request.query)
    markdown = build_custom_markdown_report(request, sections)
    html = build_custom_html_report(request, sections)
    markdown_path = output_dir / f"{slug}-{stamp}.md"
    html_path = output_dir / f"{slug}-{stamp}.html"
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")

    recipient_settings = replace(settings, email_enabled=True, email_to=request.recipient)
    await EmailNotifier(recipient_settings).send(_report_title(request), markdown, html=html)
    return CustomReportResult(request=request, sections=sections, markdown_path=markdown_path, html_path=html_path)


async def scrape_custom_report_sections(
    request: CustomReportRequest,
    settings: Settings,
    *,
    site_timeout_seconds: int = DEFAULT_SITE_TIMEOUT_SECONDS,
) -> list[SiteCustomReport]:
    sections: list[SiteCustomReport] = []
    for site in available_sites():
        scraper = build_scraper(site, settings)
        try:
            listings = await asyncio.wait_for(scraper.scrape(), timeout=site_timeout_seconds)
        except Exception as exc:
            sections.append(SiteCustomReport(site=site, scraped_count=0, listings=[], error=str(exc)))
            continue
        matches = sorted(
            [listing for listing in listings if listing_matches_request(listing, request)],
            key=lambda listing: (listing.price or 0, listing.external_id),
        )
        sections.append(SiteCustomReport(site=site, scraped_count=len(listings), listings=matches))
    return sections


def listing_matches_request(listing: ListingSnapshot, request: CustomReportRequest) -> bool:
    if request.min_price is not None and (listing.price is None or listing.price < request.min_price):
        return False
    if request.max_price is not None and (listing.price is None or listing.price >= request.max_price):
        return False
    if request.min_beds is not None and (listing.beds is None or listing.beds < request.min_beds):
        return False
    if request.max_beds is not None and (listing.beds is None or listing.beds >= request.max_beds):
        return False
    text = _listing_text(listing)
    if request.property_type and not _matches_property_type(text, request.property_type):
        return False
    for location in request.locations:
        if not any(term in text for term in LOCATION_TERMS[location]):
            return False
    if request.require_frontline_beach and not _matches_frontline_beach(text):
        return False
    for feature in request.features:
        if feature == "beachfront" and request.require_frontline_beach:
            continue
        if not any(term in text for term in FEATURE_TERMS[feature]):
            return False
    for phrase in request.required_phrases:
        if phrase not in text:
            return False
    for term in request.required_terms:
        if term not in text:
            return False
    return True


def build_custom_markdown_report(request: CustomReportRequest, sections: list[SiteCustomReport]) -> str:
    generated = _report_datetime()
    total = sum(len(section.listings) for section in sections)
    lines = [_report_title(request), generated, "", *_interpretation_markdown_lines(request), "", f"Matches found: {total}", ""]
    for section in sections:
        lines.append(
            f"{_site_display_name(section.site)} ({len(section.listings)} matches from {section.scraped_count} scraped)"
        )
        if section.error:
            lines.append(f"Scrape failed: {section.error}")
        elif not section.listings:
            lines.append("No matching properties found.")
        for listing in section.listings:
            lines.append(f"- {listing.external_id} | {_money(listing.price)} | {listing.title} | {listing.url}")
        lines.append("")
    return "\n".join(lines)


def build_custom_html_report(request: CustomReportRequest, sections: list[SiteCustomReport]) -> str:
    generated = _report_datetime()
    total = sum(len(section.listings) for section in sections)
    blocks = "\n".join(_site_block(section) for section in sections)
    title = _report_title(request)
    return f"""<!doctype html>
<html>
  <body style="margin:0;background:#f9f9f9;font-family:Futura,'Avenir Next',Arial,sans-serif;color:#181818;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f9f9f9;padding:28px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="820" cellspacing="0" cellpadding="0" style="width:820px;max-width:96%;background:#ffffff;border:1px solid #e7e1d8;">
            <tr>
              <td style="background:#181818;padding:30px 34px;color:#ffffff;">
                <div style="font-size:12px;letter-spacing:.22em;color:#c7af87;text-transform:uppercase;">Drumelia Real Estate</div>
                <h1 style="margin:9px 0 0;font-size:30px;line-height:1.2;font-weight:500;color:#ffffff;">{escape(title)}</h1>
                <div style="margin-top:8px;font-size:13px;color:#c7af87;">{escape(generated)}</div>
              </td>
            </tr>
            <tr>
              <td style="padding:24px 34px 0;">
                <div style="border:1px solid #e7e1d8;background:#f7f7f7;padding:14px 16px;display:inline-block;">
                  <div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8a857f;">Matches</div>
                  <div style="font-size:24px;line-height:1.2;font-weight:500;color:#181818;">{total}</div>
                </div>
                {_interpretation_html(request)}
              </td>
            </tr>
            <tr>
              <td style="padding:0 34px 34px;">{blocks}</td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _site_block(section: SiteCustomReport) -> str:
    if section.error:
        body = f"""
        <tr>
          <td colspan="4" style="padding:13px 12px;border-bottom:1px solid #e7e1d8;color:#84442e;">Scrape failed: {escape(section.error)}</td>
        </tr>
        """
    elif section.listings:
        body = "\n".join(_listing_row(listing) for listing in section.listings)
    else:
        body = """
        <tr>
          <td colspan="4" style="padding:13px 12px;border-bottom:1px solid #e7e1d8;color:#8a857f;">No matching properties found.</td>
        </tr>
        """
    return f"""
    <div style="margin-top:22px;">
      <h2 style="margin:0 0 6px;font-size:18px;font-weight:500;color:#181818;">{escape(_site_display_name(section.site))}</h2>
      <div style="margin:0 0 10px;color:#8a857f;font-size:12px;">{len(section.listings)} matches from {section.scraped_count} scraped listings</div>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;border:1px solid #e7e1d8;">
        <thead>
          <tr style="background:#181818;">
            <th align="left" style="padding:10px 12px;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#c7af87;">Photo</th>
            <th align="left" style="padding:10px 12px;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#c7af87;">Reference</th>
            <th align="left" style="padding:10px 12px;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#c7af87;">Listing</th>
            <th align="left" style="padding:10px 12px;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#c7af87;">Price</th>
          </tr>
        </thead>
        <tbody>{body}</tbody>
      </table>
    </div>
    """


def _listing_row(listing: ListingSnapshot) -> str:
    image = _image_url(listing)
    photo = (
        f'<img src="{escape(image)}" width="86" style="display:block;width:86px;height:58px;object-fit:cover;">'
        if image
        else ""
    )
    return f"""
    <tr>
      <td style="padding:10px 12px;border-bottom:1px solid #e7e1d8;vertical-align:top;">{photo}</td>
      <td style="padding:10px 12px;border-bottom:1px solid #e7e1d8;vertical-align:top;color:#181818;">{escape(listing.external_id)}</td>
      <td style="padding:10px 12px;border-bottom:1px solid #e7e1d8;vertical-align:top;"><a href="{escape(listing.url)}" style="color:#181818;text-decoration:underline;">{escape(listing.title)}</a></td>
      <td style="padding:10px 12px;border-bottom:1px solid #e7e1d8;vertical-align:top;color:#181818;white-space:nowrap;">{_money(listing.price)}</td>
    </tr>
    """


def _parse_max_price(query: str) -> int | None:
    range_match = re.search(
        rf"(?:between|from)\s*(?:€|eur)?\s*({PRICE_NUMBER_PATTERN})\s*(?:€|eur)?\s*(millions|million|m|k)?\s*(?:and|to|-)\s*(?:€|eur)?\s*({PRICE_NUMBER_PATTERN})\s*(?:€|eur)?\s*(millions|million|m|k)?",
        query,
    )
    if range_match:
        upper_suffix = range_match.group(4) or range_match.group(2) or ""
        return _price_value(range_match.group(3), upper_suffix)
    match = re.search(
        rf"(?:under|below|less than|up to|max(?:imum)?)\s*(?:€|eur)?\s*({PRICE_NUMBER_PATTERN})\s*(?:€|eur)?\s*(millions|million|m|k)?",
        query,
    )
    if not match:
        return None
    return _price_value(match.group(1), match.group(2) or "")


def _parse_min_price(query: str) -> int | None:
    range_match = re.search(
        rf"(?:between|from)\s*(?:€|eur)?\s*({PRICE_NUMBER_PATTERN})\s*(?:€|eur)?\s*(millions|million|m|k)?\s*(?:and|to|-)\s*(?:€|eur)?\s*({PRICE_NUMBER_PATTERN})\s*(?:€|eur)?\s*(millions|million|m|k)?",
        query,
    )
    if range_match:
        lower_suffix = range_match.group(2) or range_match.group(4) or ""
        return _price_value(range_match.group(1), lower_suffix)
    match = re.search(
        rf"(?:over|above|more than|from|min(?:imum)?|budget min(?:imum)?)\s*(?:€|eur)?\s*({PRICE_NUMBER_PATTERN})\s*(?:€|eur)?\s*(millions|million|m|k)?",
        query,
    )
    if not match:
        return None
    return _price_value(match.group(1), match.group(2) or "")


def _parse_min_beds(query: str) -> float | None:
    if re.search(r"(?:less than|below|under|max(?:imum)?)\s*\d+(?:[.,]\d+)?\s*(?:bed|beds|bedroom|bedrooms)", query):
        return None
    match = re.search(r"(?:at least|min(?:imum)?|from)\s*(\d+(?:[.,]\d+)?)\s*(?:bed|beds|bedroom|bedrooms)", query)
    if not match:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*\+?\s*(?:bed|beds|bedroom|bedrooms)", query)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _parse_max_beds(query: str) -> float | None:
    match = re.search(r"(?:less than|below|under|max(?:imum)?)\s*(\d+(?:[.,]\d+)?)\s*(?:bed|beds|bedroom|bedrooms)", query)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _parse_property_type(query: str) -> str | None:
    ordered_types = ("duplex_penthouse", "penthouse", "townhouse", "apartment", "villa", "plot")
    for property_type in ordered_types:
        if any(term in query for term in PROPERTY_TYPE_TERMS[property_type]):
            return property_type
    return None


def _required_phrases(query: str, property_type: str | None) -> tuple[str, ...]:
    if property_type == "duplex_penthouse":
        return ("duplex penthouse",)
    if property_type == "penthouse":
        return ("penthouse",)
    return ()


def _has_renovation_needed_intent(query: str) -> bool:
    return bool(
        re.search(
            r"(?:need(?:s|ed)?|require(?:s|d)?|for|to|potential|opportunity|project).{0,28}"
            r"(?:renovat|refurbish|reform|updat)",
            query,
        )
        or re.search(
            r"(?:renovat|refurbish|reform|updat).{0,28}"
            r"(?:need(?:s|ed)?|require(?:s|d)?|potential|opportunity|project)",
            query,
        )
    )


def _matches_property_type(text: str, property_type: str) -> bool:
    if property_type == "duplex_penthouse":
        return any(term in text for term in PROPERTY_TYPE_TERMS["duplex_penthouse"])
    if property_type == "penthouse":
        return any(term in text for term in PROPERTY_TYPE_TERMS["penthouse"])
    if property_type == "apartment":
        apartment_terms = PROPERTY_TYPE_TERMS["apartment"] + PROPERTY_TYPE_TERMS["penthouse"] + PROPERTY_TYPE_TERMS["duplex_penthouse"]
        return any(term in text for term in apartment_terms)
    return any(term in text for term in PROPERTY_TYPE_TERMS[property_type])


def _interpretation_markdown_lines(request: CustomReportRequest) -> list[str]:
    lines = ["Search interpreted as:"]
    for label in _interpretation_parts(request):
        lines.append(f"- {label}")
    return lines


def _interpretation_html(request: CustomReportRequest) -> str:
    items = "".join(
        f'<span style="display:inline-block;margin:0 6px 6px 0;padding:7px 9px;background:#ffffff;border:1px solid #e7e1d8;color:#181818;font-size:12px;">{escape(label)}</span>'
        for label in _interpretation_parts(request)
    )
    if not items:
        items = '<span style="color:#8a857f;font-size:13px;">No strict filters detected.</span>'
    return f"""
    <div style="margin-top:16px;">
      <div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#8a857f;margin-bottom:8px;">Search interpreted as</div>
      <div>{items}</div>
    </div>
    """


def _interpretation_parts(request: CustomReportRequest) -> list[str]:
    parts: list[str] = []
    if request.property_type:
        parts.append(f"Type: {PROPERTY_TYPE_LABELS[request.property_type]}")
    if request.locations:
        parts.append("Location: " + ", ".join(LOCATION_LABELS[location] for location in request.locations))
    if request.min_price is not None and request.max_price is not None:
        parts.append(f"Price: {_money(request.min_price)} to {_money(request.max_price)}")
    elif request.min_price is not None:
        parts.append(f"Price: from {_money(request.min_price)}")
    elif request.max_price is not None:
        parts.append(f"Price: under {_money(request.max_price)}")
    if request.min_beds is not None:
        parts.append(f"Bedrooms: at least {_format_number(request.min_beds)}")
    if request.max_beds is not None:
        parts.append(f"Bedrooms: less than {_format_number(request.max_beds)}")
    if request.features:
        labels = ", ".join(feature.replace("_", " ") for feature in request.features)
        parts.append(f"Features: {labels}")
    if request.required_terms:
        parts.append("Keywords: " + ", ".join(request.required_terms))
    return parts or ["No strict filters detected"]


def _format_number(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def _price_value(raw_number: str, suffix: str) -> int:
    number = _price_number(raw_number, suffix)
    if suffix in {"m", "million", "millions"}:
        return int(number * 1_000_000)
    if suffix == "k":
        return int(number * 1_000)
    if number < 1000:
        return int(number * 1_000_000)
    return int(number)


def _price_number(raw_number: str, suffix: str) -> float:
    if _looks_like_grouped_thousands(raw_number):
        return float(re.sub(r"[.,]", "", raw_number))
    normalized = raw_number.replace(",", ".")
    return float(normalized)


def _looks_like_grouped_thousands(raw_number: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", raw_number))


def _strip_price_phrases(query: str) -> str:
    price = rf"(?:€|eur)?\s*{PRICE_NUMBER_PATTERN}\s*(?:€|eur)?\s*(?:millions|million|m|k)?"
    range_pattern = rf"(?:between|from)\s*{price}\s*(?:and|to|-)\s*{price}"
    comparator_pattern = rf"(?:budget\s*)?(?:under|below|less than|up to|max(?:imum)?|over|above|more than|from|min(?:imum)?)\s*{price}"
    query = re.sub(range_pattern, " ", query)
    query = re.sub(comparator_pattern, " ", query)
    return query


def _listing_text(listing: ListingSnapshot) -> str:
    raw_text = " ".join(str(value) for value in listing.raw.values() if value is not None)
    return _normalize(" ".join([listing.title or "", listing.location or "", listing.url or "", raw_text]))


def _matches_frontline_beach(text: str) -> bool:
    if any(term in text for term in FRONTLINE_BEACH_TERMS):
        return True
    if "frontline" in text or "front line" in text or "first line" in text:
        return bool(re.search(r"(frontline|front line|first line).{0,24}(beach|playa|sea|seafront)", text))
    return False


def _normalize(value: str) -> str:
    return value.lower().replace("–", "-").replace("—", "-")


def _separate_number_words(value: str) -> str:
    return re.sub(r"([A-Za-z])(\d)", r"\1 \2", value)


def _image_url(listing: ListingSnapshot) -> str | None:
    for key in ("image", "image_url", "photo", "thumbnail"):
        value = listing.raw.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    return None


def _report_title(request: CustomReportRequest) -> str:
    return request.query[:1].upper() + request.query[1:]


def _report_datetime() -> str:
    return datetime.now(REPORT_TIMEZONE).strftime("%d %b %Y, %H:%M")


def _site_display_name(site: str) -> str:
    return SITE_NAMES.get(site, site.replace("_", " ").title())


def _money(value: int | None) -> str:
    if value is None:
        return "unknown"
    return f"€{value:,}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "custom-report"
