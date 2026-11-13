"""Yahoo Finance: public figures for stock-market-listed companies. No key."""

from datetime import date

import yfinance as yf

from agent.formatting import format_money
from agent.sources import SourceError


def company_financials(company: str) -> str | None:
    """Find a listed company by name and return its key figures as text.

    Returns None when no listed company matches, which usually means the
    company is private.
    """
    try:
        quotes = yf.Search(company, max_results=5).quotes
        shares = [quote for quote in quotes if quote.get("quoteType") == "EQUITY"]
        if not shares:
            return None
        symbol = shares[0]["symbol"]
        info = yf.Ticker(symbol).info or {}
    except Exception as error:  # network problem or unexpected data
        raise SourceError(str(error)) from error

    name = info.get("longName") or shares[0].get("shortname") or symbol
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
