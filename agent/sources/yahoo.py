"""Yahoo Finance: public figures for stock-market-listed companies. No key."""

from datetime import date

import yfinance as yf

from agent.formatting import format_money
from agent.names import same_company
from agent.sources import SourceError


MAX_QUOTES_CHECKED = 3


def company_financials(company: str) -> str | None:
    """Find a listed company by name and return its key figures as text.

    Returns None when no listed company matches, which usually means the
    company is private.

    Yahoo's search returns anything that contains the words searched for:
    "Factor" finds "The Cheesecake Factory". A result is accepted only if
    its company name starts with the name that was asked for.
    """
    try:
        quotes = yf.Search(company, max_results=5).quotes
        shares = [quote for quote in quotes if quote.get("quoteType") == "EQUITY"]
        match = None
        for quote in shares[:MAX_QUOTES_CHECKED]:
            short_name = quote.get("shortname") or ""
            if short_name and not same_company(company, short_name):
                continue   # clearly another company; skip without a lookup
            info = yf.Ticker(quote["symbol"]).info or {}
            name = info.get("longName") or short_name or quote["symbol"]
            if same_company(company, name):
                match = (quote["symbol"], info, name)
                break
        if match is None:
            return None
        symbol, info, name = match
    except Exception as error:  # network problem or unexpected data
        raise SourceError(str(error)) from error

    price_currency = info.get("currency") or ""
    report_currency = info.get("financialCurrency") or price_currency
    employees = info.get("fullTimeEmployees")

    return "\n".join([
        f"Company: {name} (ticker {symbol})",
        f"Sector: {info.get('sector') or 'not found'}",
        f"Industry: {info.get('industry') or 'not found'}",
        f"Country: {info.get('country') or 'not found'}",
        f"Revenue (last 12 months): "
        f"{format_money(info.get('totalRevenue'), report_currency)}",
        f"Market value: {format_money(info.get('marketCap'), price_currency)}",
        f"Employees: {employees if employees else 'not found'}",
        f"Source: https://finance.yahoo.com/quote/{symbol}",
        f"Retrieved: {date.today().isoformat()}",
        "Check that the company name above is the company you meant. If it "
        "is a different company, ignore this result and report 'not found'.",
    ])
