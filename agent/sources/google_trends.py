"""Google Trends: how often people search for a term in a country, over the
last 12 months. No key needed.

This uses `pytrends`, an unofficial library. Google does not offer a public
interface for Trends and sometimes blocks automated requests, which is why
this source has a backup.
"""

from urllib.parse import quote

from pytrends.request import TrendReq

from agent.config import SOURCE_TIMEOUT_SECONDS
from agent.sources import SourceError
from agent.trends import TrendSeries

TIMEFRAME = "today 12-m"
# On Google's 0-100 index, a typical week under 10 means the term is rarely
# searched and one busy week dominates the chart.
LOW_VOLUME_AVERAGE = 10


def interest(term: str, country) -> TrendSeries:
    """Return weekly search interest for a term in a country.

    Args:
        term: The search term, for example "meal kit".
        country: A country record from agent.countries.find_country.
    """
    try:
        client = TrendReq(hl="en-US", tz=0, timeout=(5, SOURCE_TIMEOUT_SECONDS))
        client.build_payload([term], timeframe=TIMEFRAME, geo=country.alpha_2)
        table = client.interest_over_time()
    except Exception as error:  # blocked, rate limited or network problem
        raise SourceError(str(error) or type(error).__name__) from error

    if table.empty or term not in table:
        raise SourceError("no search data for this term")

    # Google marks the current, unfinished week as partial; leave it out.
    if "isPartial" in table:
        table = table[~table["isPartial"].astype(bool)]

    points = [(day.strftime("%Y-%m-%d"), float(value))
              for day, value in table[term].items()]
    if not points or max(value for _, value in points) == 0:
        raise SourceError("not enough searches to measure")

    return TrendSeries(
        label=f"Google search interest for '{term}' in {country.name}",
        unit="index from 0 to 100, where 100 is the busiest week in the "
             "period (not a number of searches)",
        points=points,
        low_volume_below=LOW_VOLUME_AVERAGE,
        url=("https://trends.google.com/trends/explore"
             f"?date={quote(TIMEFRAME)}&geo={country.alpha_2}&q={quote(term)}"),
    )
