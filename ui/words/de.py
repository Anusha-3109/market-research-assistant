"""The app's own words in German. The reader is addressed with "Sie".

The names are the same as in en.py.
"""

TEXTS = {
    # The language switch at the top right.
    "language.label": "Sprache",
    "language.help": "Die Sprache der App",

    # The menu behind the round badge at the top right.
    "account.signed_in_as": "Angemeldet als",
    "account.sign_out": "Abmelden",
    # --- the sidebar -------------------------------------------------------
    "sidebar.tagline": "Marktforschung vor dem Start",
    "sidebar.new_conversation": "Neue Unterhaltung",
    "sidebar.conversation": "Unterhaltung",
    "sidebar.conversations": "Unterhaltungen",
    "sidebar.none_yet": "Noch keine. Stellen Sie eine Frage, um eine zu beginnen.",
    "sidebar.older": "{count} ältere",

    # The views of a conversation.
    "view.snapshot": "Überblick",
    "view.ask": "Fragen",
    "view.report": "Bericht",

    # What is remembered about the user.
    "memory.title": "Was ich mir merke",
    "memory.nothing": "Noch nichts. Nennen Sie mir Ihr Land, Ihre Branche oder Ihre Idee, und ich merke es mir für das nächste Mal.",
    "memory.forget": "Alles vergessen",
    "memory.forget_help": "Löscht alles, was über Sie gespeichert ist. Ihre Unterhaltungen bleiben erhalten.",
    "profile.region": "Region",
    "profile.industry": "Branche",
    "profile.business_idea": "Geschäftsidee",
    "profile.report_style": "Berichtsstil",

    # The settings panel.
    "settings.title": "Einstellungen",
    "settings.model": "Modell",
    "settings.model_help": "Das Sprachmodell, das antwortet und recherchiert. Alle werden über OpenRouter erreicht.",
    "settings.temperature": "Temperatur",
    "settings.temperature_help": "Ein niedriger Wert gibt sachlichere, wiederholbare Antworten. Ein höherer Wert gibt abwechslungsreichere Formulierungen. Für Recherche ist ein niedriger Wert am besten.",
    "settings.length": "Maximale Antwortlänge",
    "settings.length_help": "Eine feste Grenze für eine Chat-Antwort: Kurz sind etwa 180 Wörter, Mittel etwa 450, Lang etwa 900. Eine Antwort, die die Grenze erreicht, wird abgeschnitten und sagt das auch. Berichte werden nie gekürzt. Für knappe Formulierungen wählen Sie stattdessen den Antwortstil Knapp.",
    "settings.style": "Antwortstil",
    "settings.style_help": "Wie Antworten formuliert werden. Fakten, Zahlen und Quellen ändern sich dadurch nie.",
    "settings.review": "Wettbewerber vor einem Bericht prüfen",
    "settings.review_help": "Wenn eingeschaltet, hält ein Bericht an, damit Sie die Liste der Wettbewerber bestätigen oder ändern können. Schalten Sie es für einen schnelleren Bericht aus.",
    "settings.locked": "Die Einstellungen sind gesperrt, solange der Assistent auf Ihre Entscheidung wartet.",
    "length.Short": "Kurz",
    "length.Medium": "Mittel",
    "length.Long": "Lang",
    "length.No limit": "Keine Grenze",
    "style.Balanced": "Ausgewogen",
    "style.Formal": "Förmlich",
    "style.Friendly": "Freundlich",
    "style.Concise": "Knapp",
    "style.about.Balanced": "Die normale Schreibweise des Assistenten",
    "style.about.Formal": "Professionelle Formulierungen, für ein Dokument, das Sie weitergeben",
    "style.about.Friendly": "Freundlich und einfach, mit erklärten Fachbegriffen",
    "style.about.Concise": "Die kürzeste nützliche Antwort, ohne Einleitung und Schlusswort",

    # The help panel.
    "help.title": "Hilfe",
    "help.body": "**Fordern Sie einen Bericht an**, indem Sie ein Produkt und ein Land nennen, zum Beispiel *gesunde Essenslieferung in Deutschland*.\n\n**Stellen Sie eine einzelne Frage** zu Preisen, Wettbewerbern, Nachrichten, Nachfrage oder einem Unternehmen.\n\n**Die App gibt keine** Anlageberatung und erfindet keine Zahlen. Was sie nicht findet, wird als \"not found\" gemeldet.\n\n**Berichte** können heruntergeladen oder nach Ihrer Bestätigung im Berichtsordner gespeichert werden.",
    "help.how": "So funktioniert es",

    # --- the Snapshot view ---------------------------------------------------
    "snapshot.open_report": "Bericht öffnen",
    "snapshot.ask": "Anschlussfrage stellen",
    "snapshot.from_one": "Überblick aus {count} Quelle erstellt",
    "snapshot.from_many": "Überblick aus {count} Quellen erstellt",
    "snapshot.tab.overview": "Übersicht",
    "snapshot.tab.competitors": "Wettbewerber",
    "snapshot.tab.pricing": "Preise",
    "snapshot.tab.trends": "Trends",
    "snapshot.tab.swot": "SWOT",
    "snapshot.confirmed": "Bestätigte Wettbewerber",
    "snapshot.of_candidates_one": "von {count} Kandidat",
    "snapshot.of_candidates_many": "von {count} Kandidaten",
    "snapshot.source": "Quelle",
    "snapshot.col.competitor": "Wettbewerber",
    "snapshot.col.offer": "Angebot",
    "snapshot.col.size": "Größe oder Finanzzahlen",
    "snapshot.col.price": "Ein Preis",
    "snapshot.no_competitors": "Für diesen Bericht wurden keine Wettbewerber bestätigt.",
    "snapshot.no_prices": "Es wurden keine Wettbewerber bestätigt, daher gibt es keine Preise.",
    "snapshot.trend": "Suchinteresse",
    "snapshot.trend_for": "Suchinteresse für „{term}“",
    "snapshot.no_trend": "Für diesen Bericht wurde kein Nachfragetrend gemessen.",
    "snapshot.measured": "gemessen",
    "snapshot.caution": " (wenige Suchanfragen, daher mit Vorsicht zu lesen)",
    "snapshot.swot": "SWOT",
    "snapshot.no_swot": "Der Bericht hat keinen SWOT-Abschnitt.",
    "swot.strengths": "Stärken",
    "swot.weaknesses": "Schwächen",
    "swot.opportunities": "Chancen",
    "swot.threats": "Risiken",

    # --- the assistant at the bottom right ------------------------------------
    "assistant.name": "Assistent",
    "assistant.open_help": "Den Assistenten fragen",
    "assistant.title": "Assistent · {title}",
    "assistant.scope_report": "Nur zu dieser Unterhaltung",
    "assistant.scope_general": "Kurze Fragen, ohne Websuche",
    "assistant.new_chat": "Neuer Chat",
    "assistant.minimise": "Minimieren",
    "assistant.empty_report": "Fragen Sie zum geöffneten Bericht: was ein Begriff bedeutet, was er über einen Wettbewerber sagt, was Sie als Nächstes prüfen sollten.",
    "assistant.empty_general": "Fragen Sie, wie die App funktioniert oder was ein Begriff bedeutet. Für Recherche nutzen Sie das Fragefeld einer Unterhaltung.",
    "assistant.box_report": "Fragen Sie etwas zu diesem Bericht…",
    "assistant.box_general": "Stellen Sie eine kurze Frage…",
    "assistant.cost": "Dieser Chat: {cost}",
    "assistant.not_added": "Wird nicht zur Unterhaltung hinzugefügt",
    "assistant.thinking": "Denkt nach…",
}
