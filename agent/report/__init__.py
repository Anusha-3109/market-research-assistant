"""The report workflow: a fixed sequence of steps that produces a market
research report.

The chat agent decides freely what to do next. That suits conversation, but
for a long task it skipped steps and mixed up sources. Here the order of
steps is fixed in code (a LangGraph graph), every step's result is checked
in code, and the language model is only asked to do one small job at a time.
"""
