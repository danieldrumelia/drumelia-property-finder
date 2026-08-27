from real_estate_monitor.custom_reports import (
    build_custom_markdown_report,
    listing_matches_request,
    parse_custom_report_request,
)
from real_estate_monitor.models import ListingSnapshot


def test_parse_custom_report_request_under_5_million() -> None:
    request = parse_custom_report_request(
        "renovated beachfront apartments under 5 million",
        "agent@drumelia.com",
    )

    assert request.max_price == 5_000_000
    assert request.property_type == "apartment"
    assert request.features == ("renovated", "beachfront")
    assert request.recipient == "agent@drumelia.com"


def test_listing_matches_natural_language_request() -> None:
    request = parse_custom_report_request(
        "renovated beachfront apartments under 5 million",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D1234",
        url="https://www.example.com/properties/beachfront-apartment/D1234",
        title="Fully renovated beachfront apartment with sea views",
        price=1_950_000,
    )

    assert listing_matches_request(listing, request)


def test_listing_rejects_expensive_match() -> None:
    request = parse_custom_report_request(
        "renovated beachfront apartments under 5 million",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D1234",
        url="https://www.example.com/properties/beachfront-apartment/D1234",
        title="Fully renovated beachfront apartment with sea views",
        price=5_500_000,
    )

    assert not listing_matches_request(listing, request)


def test_frontline_beach_request_rejects_frontline_golf_villa() -> None:
    request = parse_custom_report_request(
        "frontline beach villas under €3.5 million",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D2345",
        url="https://www.example.com/properties/frontline-golf-villa/D2345",
        title="Frontline golf villa close to the beach",
        price=2_950_000,
    )

    assert not listing_matches_request(listing, request)


def test_frontline_beach_request_accepts_frontline_beach_villa() -> None:
    request = parse_custom_report_request(
        "frontline beach villas under €3.5 million",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D2346",
        url="https://www.example.com/properties/frontline-beach-villa/D2346",
        title="Frontline beach villa with direct sea access",
        price=3_250_000,
    )

    assert listing_matches_request(listing, request)


def test_parse_custom_report_request_price_range_and_bedrooms() -> None:
    request = parse_custom_report_request(
        "villas between 4 and 5 million with at least 3 bedrooms",
        "agent@drumelia.com",
    )

    assert request.min_price == 4_000_000
    assert request.max_price == 5_000_000
    assert request.min_beds == 3
    assert request.property_type == "villa"
    assert request.required_terms == ()


def test_parse_custom_report_request_accepts_dotted_euro_minimum_budget() -> None:
    request = parse_custom_report_request(
        "Villa on the golden mile, budget minimum 5.000.000€",
        "agent@drumelia.com",
    )

    assert request.min_price == 5_000_000
    assert request.max_price is None
    assert request.property_type == "villa"
    assert request.locations == ("golden_mile",)
    assert request.required_terms == ()


def test_parse_custom_report_request_accepts_comma_grouped_euro_budget() -> None:
    request = parse_custom_report_request(
        "villa in Golden Mile over €5,000,000",
        "agent@drumelia.com",
    )

    assert request.min_price == 5_000_000
    assert request.property_type == "villa"
    assert request.locations == ("golden_mile",)
    assert request.required_terms == ()


def test_parse_custom_report_request_under_3_million_needs_renovation() -> None:
    request = parse_custom_report_request(
        "Any property under 3 million in need of renovation",
        "agent@drumelia.com",
    )

    assert request.max_price == 3_000_000
    assert request.property_type is None
    assert request.features == ("renovation_needed",)
    assert request.required_terms == ()


def test_renovation_needed_request_matches_reform_opportunity() -> None:
    request = parse_custom_report_request(
        "Any property under 3 million in need of renovation",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D1111",
        url="https://www.example.com/properties/apartment/D1111",
        title="Apartment with great potential to reform near the beach",
        price=1_250_000,
    )

    assert listing_matches_request(listing, request)


def test_renovation_needed_request_does_not_match_finished_renovated_listing() -> None:
    request = parse_custom_report_request(
        "Any property under 3 million in need of renovation",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D1112",
        url="https://www.example.com/properties/apartment/D1112",
        title="Fully renovated apartment ready to move in",
        price=1_250_000,
    )

    assert not listing_matches_request(listing, request)


def test_dotted_euro_budget_matches_golden_mile_villa() -> None:
    request = parse_custom_report_request(
        "Villa on the golden mile, budget minimum 5.000.000€",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D9999",
        url="https://www.example.com/properties/marbella-golden-mile/villa/D9999",
        title="Elegant villa in Marbella Golden Mile",
        price=5_500_000,
    )

    assert listing_matches_request(listing, request)


def test_price_range_and_bedroom_request_matches_villa() -> None:
    request = parse_custom_report_request(
        "villas between 4 and 5 million with at least 3 bedrooms",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D3456",
        url="https://www.example.com/properties/villa/D3456",
        title="Elegant villa in Marbella",
        price=4_500_000,
        beds=4,
    )

    assert listing_matches_request(listing, request)


def test_price_range_and_bedroom_request_rejects_outside_range() -> None:
    request = parse_custom_report_request(
        "villas between 4 and 5 million with at least 3 bedrooms",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D3457",
        url="https://www.example.com/properties/villa/D3457",
        title="Elegant villa in Marbella",
        price=3_900_000,
        beds=4,
    )

    assert not listing_matches_request(listing, request)


def test_price_range_and_bedroom_request_rejects_too_few_bedrooms() -> None:
    request = parse_custom_report_request(
        "villas between 4 and 5 million with at least 3 bedrooms",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D3458",
        url="https://www.example.com/properties/villa/D3458",
        title="Elegant villa in Marbella",
        price=4_500_000,
        beds=2,
    )

    assert not listing_matches_request(listing, request)


def test_parse_custom_report_request_from_range_and_less_than_bedrooms() -> None:
    request = parse_custom_report_request(
        "duplex penthouses from1-3 million with less than 3 bedrooms in Marbella",
        "agent@drumelia.com",
    )

    assert request.min_price == 1_000_000
    assert request.max_price == 3_000_000
    assert request.min_beds is None
    assert request.max_beds == 3
    assert request.property_type == "duplex_penthouse"
    assert request.locations == ("marbella",)
    assert request.required_phrases == ("duplex penthouse",)
    assert request.required_terms == ()


def test_from_range_and_less_than_bedrooms_matches_duplex_penthouse() -> None:
    request = parse_custom_report_request(
        "duplex penthouses from1-3 million with less than 3 bedrooms in Marbella",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D4567",
        url="https://www.example.com/properties/marbella/duplex-penthouse/D4567",
        title="Duplex penthouse in Marbella",
        price=2_400_000,
        beds=2,
    )

    assert listing_matches_request(listing, request)


def test_from_range_and_less_than_bedrooms_rejects_three_bedrooms() -> None:
    request = parse_custom_report_request(
        "duplex penthouses from1-3 million with less than 3 bedrooms in Marbella",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D4568",
        url="https://www.example.com/properties/marbella/duplex-penthouse/D4568",
        title="Duplex penthouse in Marbella",
        price=2_400_000,
        beds=3,
    )

    assert not listing_matches_request(listing, request)


def test_duplex_penthouse_request_rejects_middle_floor_apartment() -> None:
    request = parse_custom_report_request(
        "duplex penthouses from1-3 million with less than 3 bedrooms in Marbella",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D4569",
        url="https://www.example.com/properties/marbella/apartment/D4569",
        title="Middle floor apartment in Marbella",
        price=2_100_000,
        beds=2,
    )

    assert not listing_matches_request(listing, request)


def test_penthouse_request_rejects_middle_floor_apartment() -> None:
    request = parse_custom_report_request(
        "penthouses from 1-3 million in Marbella",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D4570",
        url="https://www.example.com/properties/marbella/apartment/D4570",
        title="Middle floor apartment in Marbella",
        price=2_100_000,
        beds=2,
    )

    assert not listing_matches_request(listing, request)


def test_apartment_request_can_include_penthouse() -> None:
    request = parse_custom_report_request(
        "apartments under 3 million in Marbella",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D4571",
        url="https://www.example.com/properties/marbella/duplex-penthouse/D4571",
        title="Duplex penthouse in Marbella",
        price=2_100_000,
        beds=2,
    )

    assert listing_matches_request(listing, request)


def test_location_request_rejects_other_area() -> None:
    request = parse_custom_report_request(
        "villas in La Zagaleta under 10 million",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D4572",
        url="https://www.example.com/properties/nueva-andalucia/villa/D4572",
        title="Contemporary villa in Nueva Andalucia",
        price=4_500_000,
    )

    assert not listing_matches_request(listing, request)


def test_location_request_accepts_matching_area() -> None:
    request = parse_custom_report_request(
        "villas in La Zagaleta under 10 million",
        "agent@drumelia.com",
    )
    listing = ListingSnapshot(
        site="drumelia",
        external_id="D4573",
        url="https://www.example.com/properties/la-zagaleta/villa/D4573",
        title="Contemporary villa in La Zagaleta",
        price=4_500_000,
    )

    assert listing_matches_request(listing, request)


def test_build_markdown_report_shows_interpreted_query() -> None:
    request = parse_custom_report_request(
        "new build villas in Nueva Andalucia with sea views under 5 million",
        "agent@drumelia.com",
    )

    markdown = build_custom_markdown_report(request, [])

    assert "Search interpreted as:" in markdown
    assert "- Type: villa" in markdown
    assert "- Location: Nueva Andalucia" in markdown
    assert "- Features: sea views, new build" in markdown
