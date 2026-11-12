# AI Market Research Assistant

## Target user

First-time founders who want to test a business idea before launch and
cannot afford an analyst or paid research reports. Also useful for small
business owners who are considering a new product or a new region.

## Problem

Before launching, a founder needs to understand competitors, pricing,
customer needs and market trends. Today this means searching many
websites by hand, copying notes into a document, and trying to make sense
of them. It takes days, the result is unstructured, and it is often
unclear where each number came from.

## Solution

An AI agent that takes a business idea and a target country, searches
live web and news sources, identifies competitors, collects pricing and
trends, performs a SWOT analysis, and produces a structured report in
which every fact has a reference. The SWOT is analysis built on those
facts and is labelled as such. The user can then ask follow-up questions
to go deeper on any section.

## Why an agent

- The research needs current data, which a language model alone does not
  have.
- The data comes from several sources: web search, news and company
  financials.
- Each step depends on the previous one: the agent has to find the
  competitors first, then decide what to look up about each of them.

A single prompt cannot do this because it has no live data. Plain RAG
cannot do it because there is no fixed set of documents to search. An
agent with tools can decide what to look up next and when it has enough
to write the report.

## Inputs

- The product or industry (required)
- The target country or region (required; the agent asks if it is missing)
- A short description of the user's own idea (optional; if it is missing,
  the SWOT is written for a new entrant in this market)

## Output

A report in English with six fixed sections:

1. Market overview
2. Competitors
3. Pricing
4. Trends
5. SWOT analysis
6. References

## Scope

**The assistant does:**

- Research a market in a given country using public sources
- Identify and compare competitors
- Summarise pricing and trends with sources
- Produce a SWOT analysis for the user's idea
- Answer follow-up questions about the report
- Save the report to a file after the user approves

**The assistant does not:**

- Give investment or financial advice
- Produce its own estimates or invent numbers; it reports figures
  published by others with the source, or says "not found"
- Use paid databases such as Statista or Gartner
- Answer questions unrelated to market research

## Example questions

1. "I want to launch a healthy meal delivery business in Germany. Give me
   a market research report."
2. "Go deeper on pricing for the top three competitors you found."
3. "Is there a market for vegan protein snacks?" (no country given, so
   the agent asks for one)
4. "Should I invest my savings in this business?" (the assistant declines
   and offers market facts instead)
5. "Save this report." (the assistant asks for approval before writing
   the file)

## Known limitations

- It uses public data only, so market-size figures are estimates
  published by others, not verified statistics.
- Prices found on the web may be incomplete or out of date; each price is
  shown with its source and the date it was found.
- Small private companies publish little data, so coverage of them is
  thinner than for large public ones.
- The quality of the report depends on what web search returns for that
  industry and country.
- Reports are in English only, so local-language sources may be missed.
