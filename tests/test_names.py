"""Tests for comparing company names."""

import pytest

from agent.names import name_key, same_company


def test_name_key_ignores_case_accents_spaces_and_punctuation():
    assert name_key("Löwenanteil GmbH") == "lowenanteilgmbh"
    assert name_key("Marley-Spoon") == name_key("marley spoon")


@pytest.mark.parametrize("brand, company", [
    ("HelloFresh", "HelloFresh SE"),
    ("Hello Fresh", "HelloFresh SE"),
    ("HelloFresh", "Hello Fresh SE"),
    ("Marley Spoon", "Marley Spoon Group SE"),
    ("Cheesecake Factory", "The Cheesecake Factory Incorporated"),
    ("Löwenanteil", "Lowenanteil GmbH"),
])
def test_a_company_name_that_starts_with_the_brand_is_the_same_company(brand, company):
    assert same_company(brand, company)


@pytest.mark.parametrize("brand, company", [
    ("Factor", "The Cheesecake Factory Incorporated"),   # brand inside another word
    ("Bulk", "Dry Bulk Carriers Inc"),                   # brand in the middle
    ("Marley Spoon", "468 SPAC II SE"),                  # unrelated
    ("Hello", "HelloFresh SE"),                          # only part of a word
    ("HelloFresh", ""),
    ("", "HelloFresh SE"),
])
def test_a_company_name_that_only_resembles_the_brand_is_not(brand, company):
    assert not same_company(brand, company)
