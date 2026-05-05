# tests/test_address_parsing.py
#
# Tests for address parsing and normalisation helpers in models.py.
# These cover the most common apartment formats found in Houston-area addresses.

from planning_center_reports.models import (
    _complex_key,
    _extract_apt,
    _is_bad_address,
    _parse_apt_number,
    _street_only,
)


class TestExtractApt:
    def test_apt_prefix_numeric(self):
        assert _extract_apt("12935 TX-249, APT 102, Houston, TX, 77086") == "102"

    def test_apt_prefix_alphanumeric(self):
        assert _extract_apt("165 West Road, Apt 41B, Houston, TX, 77037") == "41B"

    def test_hash_prefix(self):
        assert _extract_apt("500 Main St, #7, Houston, TX") == "7"

    def test_bare_numeric_between_commas(self):
        # "430 Cypress Creek Pkwy, 46, Houston, TX" — unit is just "46"
        assert _extract_apt("430 Cypress Creek Pkwy, 46, Houston, TX, 77090") == "46"

    def test_no_unit_returns_empty(self):
        assert _extract_apt("20608 I-45, Spring, TX, 77373") == ""

    def test_empty_input_returns_empty(self):
        assert _extract_apt("") == ""

    def test_none_input_returns_empty(self):
        assert _extract_apt(None) == ""


class TestParseAptNumber:
    def test_numeric_unit_sorts_correctly(self):
        # Lower numeric prefix should sort before higher
        key_9  = _parse_apt_number("12935 TX-249, APT 9, Houston, TX")
        key_10 = _parse_apt_number("12935 TX-249, APT 10, Houston, TX")
        assert key_9 < key_10

    def test_no_unit_sorts_last(self):
        key_unit = _parse_apt_number("12935 TX-249, APT 9, Houston, TX")
        key_none = _parse_apt_number("20608 I-45, Spring, TX")
        assert key_unit < key_none

    def test_returns_tuple(self):
        result = _parse_apt_number("12935 TX-249, APT 102, Houston, TX")
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestComplexKey:
    def test_same_complex_different_units_share_key(self):
        addr1 = "430 Cypress Creek Pkwy, 46, Houston, TX, 77090"
        addr2 = "430 Cypress Creek Pkwy, 13A, Houston, TX, 77090"
        assert _complex_key(addr1) == _complex_key(addr2)

    def test_different_complexes_have_different_keys(self):
        addr1 = "430 Cypress Creek Pkwy, 46, Houston, TX"
        addr2 = "12935 TX-249, APT 102, Houston, TX"
        assert _complex_key(addr1) != _complex_key(addr2)

    def test_empty_returns_empty(self):
        assert _complex_key("") == ""

    def test_none_returns_empty(self):
        assert _complex_key(None) == ""

    def test_keys_are_lowercase(self):
        key = _complex_key("430 Cypress Creek Pkwy, 46, Houston, TX")
        assert key == key.lower()


class TestStreetOnly:
    def test_removes_apt_prefix(self):
        result = _street_only("12935 TX-249, APT 102, Houston, TX, 77086")
        assert "APT" not in result
        assert "102" not in result
        assert "12935 TX-249" in result

    def test_removes_bare_unit(self):
        result = _street_only("430 Cypress Creek Pkwy, 46, Houston, TX, 77090")
        # The bare "46" unit should be stripped
        assert ", 46," not in result
        assert "Cypress Creek" in result

    def test_no_unit_unchanged(self):
        addr = "20608 I-45, Spring, TX, 77373"
        assert _street_only(addr) == addr

    def test_empty_returns_empty(self):
        assert _street_only("") == ""

    def test_none_returns_empty(self):
        assert _street_only(None) == ""


class TestIsBadAddress:
    def test_empty_is_bad(self):
        assert _is_bad_address("") is True

    def test_none_is_bad(self):
        assert _is_bad_address(None) is True

    def test_city_only_is_bad(self):
        assert _is_bad_address("Houston, TX") is True

    def test_city_state_zip_is_bad(self):
        assert _is_bad_address("Houston, TX 77086") is True

    def test_full_address_is_good(self):
        assert _is_bad_address("430 Cypress Creek Pkwy, 46, Houston, TX, 77090") is False

    def test_single_family_is_good(self):
        assert _is_bad_address("20608 I-45, Spring, TX, 77373") is False
