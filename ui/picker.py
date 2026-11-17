"""The picker screens behind the start cards.

Clicking a start card opens a picker: a box to type in, and rows of chips
(products, countries, companies ...) that fill the box for you. Nothing is
sent to the assistant until "Research" is pressed, so opening a picker and
trying chips costs nothing.

What a picker offers is described as plain data (PICKERS), and the sentence
it builds is made by plain functions (sentence, toggle), so both are tested
without a browser. render_picker() draws one.
"""

from dataclasses import dataclass
from urllib.parse import quote

import streamlit as st

# --- the chips ----------------------------------------------------------------------------
# Each entry is (what is shown in front of the name, the name).
# For products, ideas and industries that is an icon; for countries a
# two-letter code; for companies the website its logo is read from.
#
# Products, companies and business ideas are grouped by industry: a picker
# shows the chips of the industry chosen in its first row. Countries are the
# same for every industry.


@dataclass(frozen=True)
class Industry:
    """One industry and the chips it offers."""

    name: str
    icon: str
    products: tuple[tuple[str, str], ...]
    companies: tuple[tuple[str, str], ...]
    ideas: tuple[tuple[str, str], ...]


def _icons(*pairs: tuple[str, str]) -> tuple[tuple[str, str], ...]:
    """Write ("restaurant", "Meal kits") instead of the full icon code."""
    return tuple((f":material/{icon}:", name) for icon, name in pairs)


CATALOGUE = (
    Industry(
        "Food and drink", ":material/restaurant:",
        products=_icons(
            ("restaurant", "Meal kits"), ("water_drop", "Oat milk"), ("cookie", "Vegan snacks"),
            ("coffee", "Specialty coffee"), ("nutrition", "Protein bars"),
            ("emoji_food_beverage", "Kombucha"), ("eco", "Plant-based meat"),
            ("ac_unit", "Frozen ready meals"), ("bakery_dining", "Gluten-free bread"),
            ("local_bar", "Alcohol-free beer")),
        companies=(
            ("hellofresh.de", "HelloFresh"), ("prepmymeal.com", "Prepmymeal"),
            ("oatly.com", "Oatly"), ("marleyspoon.de", "Marley Spoon"), ("huel.com", "Huel"),
            ("tchibo.de", "Tchibo"), ("alpro.com", "Alpro"), ("nestle.com", "Nestlé"),
            ("danone.com", "Danone"), ("beyondmeat.com", "Beyond Meat")),
        ideas=_icons(
            ("bakery_dining", "Vegan bakery"), ("local_cafe", "Specialty coffee shop"),
            ("lunch_dining", "Meal prep service"), ("icecream", "Plant-based ice cream shop")),
    ),
    Industry(
        "Beauty and skincare", ":material/spa:",
        products=_icons(
            ("spa", "Natural skincare"), ("wb_sunny", "Sunscreen"), ("science", "Face serum"),
            ("content_cut", "Hair care"), ("soap", "Solid shampoo"), ("face", "Men's grooming"),
            ("brush", "Vegan makeup"), ("local_florist", "Perfume"),
            ("clean_hands", "Hand cream"), ("bathtub", "Bath and body care")),
        companies=(
            ("loreal.com", "L'Oréal"), ("nivea.de", "Nivea"), ("theordinary.com", "The Ordinary"),
            ("weleda.com", "Weleda"), ("lush.com", "Lush"), ("rituals.com", "Rituals"),
            ("sephora.com", "Sephora"), ("douglas.de", "Douglas"),
            ("thebodyshop.com", "The Body Shop"), ("cerave.com", "CeraVe")),
        ideas=_icons(
            ("spa", "Online skincare brand"), ("soap", "Refill shampoo shop"),
            ("face", "Men's grooming subscription"), ("local_florist", "Natural perfume brand")),
    ),
    Industry(
        "Pet care", ":material/pets:",
        products=_icons(
            ("pets", "Pet food"), ("cookie", "Dog treats"), ("inventory_2", "Cat litter"),
            ("medication", "Pet supplements"), ("shield", "Pet insurance"), ("toys", "Dog toys"),
            ("restaurant", "Fresh dog food"), ("content_cut", "Pet grooming products"),
            ("bed", "Dog beds"), ("location_on", "Pet trackers")),
        companies=(
            ("fressnapf.de", "Fressnapf"), ("zooplus.de", "Zooplus"),
            ("royalcanin.com", "Royal Canin"), ("purina.com", "Purina"),
            ("pedigree.com", "Pedigree"), ("butternutbox.com", "Butternut Box"),
            ("tails.com", "Tails.com"), ("petsathome.com", "Pets at Home")),
        ideas=_icons(
            ("pets", "Dog food subscription"), ("home", "Dog daycare"),
            ("content_cut", "Mobile pet grooming service"), ("storefront", "Pet accessories shop")),
    ),
    Industry(
        "Health and fitness", ":material/fitness_center:",
        products=_icons(
            ("fitness_center", "Protein powder"), ("medication", "Vitamins and supplements"),
            ("watch", "Fitness trackers"), ("self_improvement", "Yoga mats"),
            ("exercise", "Home gym equipment"), ("local_drink", "Electrolyte drinks"),
            ("directions_run", "Running shoes"), ("blender", "Meal replacement shakes"),
            ("bedtime", "Sleep aids"), ("pedal_bike", "Exercise bikes")),
        companies=(
            ("myprotein.com", "Myprotein"), ("garmin.com", "Garmin"),
            ("onepeloton.com", "Peloton"), ("gymshark.com", "Gymshark"),
            ("decathlon.com", "Decathlon"), ("foodspring.de", "Foodspring"),
            ("whoop.com", "Whoop"), ("esn.com", "ESN")),
        ideas=_icons(
            ("nutrition", "Protein snack brand"), ("self_improvement", "Boutique yoga studio"),
            ("exercise", "Online fitness coaching service"),
            ("medication", "Supplement subscription")),
    ),
    Industry(
        "Baby and kids", ":material/child_care:",
        products=_icons(
            ("child_care", "Organic baby food"), ("baby_changing_station", "Diapers"),
            ("water_drop", "Baby formula"), ("stroller", "Strollers"), ("toys", "Wooden toys"),
            ("spa", "Baby skincare"), ("checkroom", "Kids' clothing"),
            ("videocam", "Baby monitors"), ("menu_book", "Children's books"),
            ("directions_car", "Car seats")),
        companies=(
            ("hipp.de", "HiPP"), ("pampers.com", "Pampers"), ("holle.ch", "Holle"),
            ("bugaboo.com", "Bugaboo"), ("cybex-online.com", "Cybex"), ("lego.com", "LEGO"),
            ("ellaskitchen.co.uk", "Ella's Kitchen"), ("babymarkt.de", "Babymarkt")),
        ideas=_icons(
            ("child_care", "Organic baby food brand"), ("checkroom", "Baby clothing rental"),
            ("toys", "Wooden toy shop"), ("restaurant", "Kids' cooking school")),
    ),
    Industry(
        "Fashion", ":material/checkroom:",
        products=_icons(
            ("checkroom", "Sustainable clothing"), ("directions_walk", "Sneakers"),
            ("recycling", "Second-hand fashion"), ("sports_gymnastics", "Activewear"),
            ("shopping_bag", "Handbags"), ("diamond", "Jewellery"), ("eyeglasses", "Eyewear"),
            ("landscape", "Outdoor jackets"), ("watch", "Watches"), ("dry_cleaning", "Workwear")),
        companies=(
            ("zara.com", "Zara"), ("hm.com", "H&M"), ("zalando.de", "Zalando"),
            ("vinted.com", "Vinted"), ("nike.com", "Nike"), ("adidas.com", "Adidas"),
            ("patagonia.com", "Patagonia"), ("armedangels.com", "Armedangels")),
        ideas=_icons(
            ("recycling", "Second-hand clothing shop"),
            ("sports_gymnastics", "Sustainable activewear brand"),
            ("diamond", "Custom jewellery shop"), ("directions_walk", "Sneaker cleaning service")),
    ),
    Industry(
        "Home and living", ":material/chair:",
        products=_icons(
            ("bed", "Mattresses"), ("candle", "Scented candles"), ("potted_plant", "Houseplants"),
            ("lightbulb", "Smart home devices"), ("cleaning_services", "Cleaning products"),
            ("kitchen", "Kitchen appliances"), ("king_bed", "Bed linen"), ("chair", "Furniture"),
            ("local_laundry_service", "Laundry detergent"), ("yard", "Garden tools")),
        companies=(
            ("ikea.com", "IKEA"), ("emma-sleep.com", "Emma"), ("westwing.de", "Westwing"),
            ("dyson.com", "Dyson"), ("bosch-home.com", "Bosch"), ("philips.com", "Philips"),
            ("home24.de", "Home24"), ("otto.de", "Otto")),
        ideas=_icons(
            ("local_florist", "Flower delivery service"), ("candle", "Scented candle brand"),
            ("potted_plant", "Houseplant subscription"),
            ("cleaning_services", "Refill cleaning products shop")),
    ),
)
BY_NAME = {industry.name: industry for industry in CATALOGUE}
DEFAULT_INDUSTRY = CATALOGUE[0].name

COUNTRIES = (
    ("DE", "Germany"), ("GB", "United Kingdom"), ("FR", "France"), ("NL", "Netherlands"),
    ("ES", "Spain"), ("IT", "Italy"), ("PL", "Poland"), ("AT", "Austria"),
    ("CH", "Switzerland"), ("SE", "Sweden"), ("BE", "Belgium"), ("US", "United States"),
)
# For "Set your market": the industries themselves, plus one narrower field
# that many first-time founders name.
INDUSTRIES = tuple((industry.icon, industry.name) for industry in CATALOGUE) + (
    (":material/local_shipping:", "Meal delivery"),)

# The rows whose chips change with the industry chosen at the top.
BY_INDUSTRY = ("product", "company", "idea")


def chips(group: str, industry: str = DEFAULT_INDUSTRY) -> tuple[tuple[str, str], ...]:
    """The chips of one row. `industry` matters only for products, companies
    and ideas."""
    if group == "country":
        return COUNTRIES
    if group == "industry":
        return INDUSTRIES
    chosen = BY_NAME[industry]
    return {"product": chosen.products, "company": chosen.companies, "idea": chosen.ideas}[group]


def uses_industry(picker: "Picker") -> bool:
    """True if the picker has a row that depends on the industry, and so
    shows the industry row."""
    return any(group in BY_INDUSTRY for _, group in picker.rows)


# Countries that are written with "the" in a sentence.
WITH_THE = {"United Kingdom", "Netherlands", "United States"}


@dataclass(frozen=True)
class Picker:
    """One picker screen.

    title, line: the headline (the bold part between ** **) and the line
                 under it.
    icon:        shown at the start of the box.
    rows:        the chip rows, as (label above the row, group name).
    template:    the sentence the picks become; {product}, {country} ...
                 are replaced by the chosen names.
    placeholder: shown in the empty box, as an example of typing your own.
    button:      the word on the button.
    """

    title: str
    line: str
    icon: str
    rows: tuple[tuple[str, str], ...]
    template: str
    placeholder: str
    button: str = "Research"


PRODUCT_AND_COUNTRY = (("Then a product", "product"), ("And a country", "country"))
ONE_COMPANY = (("Then a company", "company"),)

# The keys are the titles of the start cards (ui/start.py).
PICKERS = {
    "Write a report": Picker(
        "Write a **report**.",
        "Six sections, verified competitors, every fact linked to its source.",
        ":material/description:", PRODUCT_AND_COUNTRY,
        "Give me a market research report for {product} in {country}.",
        "Type your own, e.g. a market research report for meal kits in Germany"),
    "Check demand": Picker(
        "Check **demand**.",
        "Is search interest rising, falling or stable over the last 12 months?",
        ":material/trending_up:", PRODUCT_AND_COUNTRY,
        "Is interest in {product} rising in {country}?",
        "Type your own, e.g. Is interest in meal kits rising in Germany?"),
    "Compare prices": Picker(
        "Compare **prices**.",
        "Read from the company's own website, with the page it came from.",
        ":material/sell:", ONE_COMPANY,
        "What does {company} charge?",
        "Type your own, e.g. What does Prepmymeal charge?"),
    "Follow the news": Picker(
        "Follow the **news**.",
        "Launches, closures, funding and regulation from the last month.",
        ":material/newspaper:", PRODUCT_AND_COUNTRY,
        "What has changed recently in the {product} market in {country}?",
        "Type your own, e.g. What changed in organic baby food in France?"),
    "Find competitors": Picker(
        "Find **competitors**.",
        "Companies that sell this product in this country, each one checked.",
        ":material/groups:", PRODUCT_AND_COUNTRY,
        "Who are the main companies selling {product} in {country}?",
        "Type your own, e.g. Who sells vegan protein snacks in the UK?"),
    "Research a company": Picker(
        "Research a **company**.",
        "Revenue, employees and market value, from public figures.",
        ":material/apartment:", ONE_COMPANY,
        "How big is {company}? Give me its revenue and number of employees.",
        "Type your own, e.g. How big is HelloFresh?"),
    "Size a market": Picker(
        "Size a **market**.",
        "Market value and growth, labelled with the area and year they cover.",
        ":material/straighten:", PRODUCT_AND_COUNTRY,
        "How big is the {product} market in {country}?",
        "Type your own, e.g. How big is the vegan snack market in the UK?"),
    "Test my idea": Picker(
        "Test my **idea**.",
        "A full report written for your business idea, with a SWOT analysis.",
        ":material/lightbulb:", (("Then an idea", "idea"), ("And a country", "country")),
        "I want to open {idea} in {country}. Give me a market research report.",
        "Type your own, e.g. I want to open a vegan bakery in the Netherlands"),
    "Set your market": Picker(
        "Set your **market**.",
        "Tell the assistant once; later conversations know it without asking.",
        ":material/person_pin_circle:",
        (("Pick your country", "country"), ("And your industry", "industry")),
        "I am based in {country} and I work in {industry}.",
        "Type your own, e.g. I am based in Germany and I work in meal delivery",
        button="Save"),
}


# --- from picks to a sentence ---------------------------------------------------------------

def in_a_sentence(group: str, name: str) -> str:
    """A chip's name as it reads inside a sentence: 'Oat milk' becomes
    'oat milk', 'Netherlands' becomes 'the Netherlands', 'Vegan bakery'
    becomes 'a vegan bakery'. Company names are left as they are."""
    if group == "company":
        return name
    if group == "country":
        return f"the {name}" if name in WITH_THE else name
    lowered = name[:1].lower() + name[1:]
    if group == "idea":
        article = "an" if lowered[:1] in "aeiou" else "a"
        return f"{article} {lowered}"
    return lowered


def sentence(picker: Picker, picks: dict[str, str]) -> str | None:
    """The sentence for the chips picked so far, or None while a row has
    nothing picked yet."""
    groups = [group for _, group in picker.rows]
    if any(group not in picks for group in groups):
        return None
    return picker.template.format(
        **{group: in_a_sentence(group, picks[group]) for group in groups})


def toggle(picks: dict[str, str], group: str, name: str) -> dict[str, str]:
    """The picks after a chip is clicked: one chip per row, and clicking
    the chosen chip again takes it back."""
    picks = dict(picks)
    if picks.get(group) == name:
        del picks[group]
    else:
        picks[group] = name
    return picks


def missing_hint(picker: Picker, picks: dict[str, str]) -> str:
    """What to say under the box while a row is still unpicked."""
    waiting = [label for label, group in picker.rows if group not in picks]
    if not picks or not waiting:
        return ""
    wanted = waiting[0].lower()
    for start in ("or ", "and ", "then ", "pick "):
        wanted = wanted.removeprefix(start)
    return f"Now pick {wanted}."


# --- drawing --------------------------------------------------------------------------------

TEXT_KEY = "picker_text"
BACK = "__back__"


def open_picker(thread_id: str, card: str) -> None:
    """Remember which picker is open. It belongs to one empty conversation,
    like the guide."""
    st.session_state["picker"] = {"thread": thread_id, "card": card, "picks": {},
                                  "industry": DEFAULT_INDUSTRY}
    st.session_state[TEXT_KEY] = ""


def change_industry(state: dict, name: str) -> None:
    """Show another industry's chips. Picks that belonged to the old
    industry are dropped; the country, and whatever is typed in the box,
    stay."""
    if state["industry"] == name:
        return
    state["industry"] = name
    state["picks"] = {group: pick for group, pick in state["picks"].items()
                      if group not in BY_INDUSTRY}


def _clicked(state: dict, picker: Picker, group: str, name: str) -> None:
    """A chip was clicked. Runs before the page is drawn again, which is
    the only moment the text in the box may be changed from code."""
    state["picks"] = toggle(state["picks"], group, name)
    built = sentence(picker, state["picks"])
    if built:
        st.session_state[TEXT_KEY] = built


def logo_styles(companies) -> str:
    """CSS that puts each company's own favicon in front of its chip.

    Two pictures are layered: the favicon on top, and under it a tile with
    the company's first letter. A site without a favicon shows the letter.
    """
    rules = []
    for index, (site, name) in enumerate(companies):
        letter = quote(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
            '<text x="10" y="14" font-size="11" font-weight="600" font-family="sans-serif" '
            f'text-anchor="middle" fill="#55544f">{name[0]}</text></svg>')
        rules.append(
            f'.st-key-pick_company_{index} button::before {{ background-image: '
            f'url("https://{site}/favicon.ico"), url("data:image/svg+xml,{letter}"); }}')
    return "<style>" + "\n".join(rules) + "</style>"


def _chip(state: dict, picker: Picker, group: str, index: int) -> None:
    lead, name = chips(group, state["industry"])[index]
    chosen = state["picks"].get(group) == name
    mark = "✓" if chosen else "+"
    icon = lead if group in ("product", "idea", "industry") else None
    label = f"`{lead}` {name} {mark}" if group == "country" else f"{name} {mark}"
    st.button(label, key=f"pick_{group}_{index}", icon=icon,
              type="primary" if chosen else "secondary",
              on_click=_clicked, args=(state, picker, group, name))


def _industry_row(state: dict) -> None:
    """The first row: which industry's products, companies or ideas to show."""
    st.caption("PICK AN INDUSTRY")
    with st.container(key="picker_row_field", horizontal=True,
                      horizontal_alignment="center", gap="small"):
        for index, industry in enumerate(CATALOGUE):
            st.button(industry.name, key=f"field_{index}", icon=industry.icon,
                      type="primary" if state["industry"] == industry.name else "secondary",
                      on_click=change_industry, args=(state, industry.name))


def render_picker(state: dict) -> str | None:
    """Draw the open picker. Returns the sentence to send when the button
    is pressed, BACK when "Back to start" is pressed, otherwise None."""
    picker = PICKERS[state["card"]]

    if st.button("Back to start", key="picker_back", icon=":material/arrow_back:"):
        return BACK

    with st.container(key="picker_head"):
        st.title(picker.title, anchor=False)
        st.markdown(picker.line)

    with st.container(key="picker_box", horizontal=True, vertical_alignment="center"):
        typed = st.text_input("Your question", key=TEXT_KEY, placeholder=picker.placeholder,
                              icon=picker.icon, label_visibility="collapsed")
        pressed = st.button(picker.button, key="picker_go", type="primary",
                            icon=":material/check:" if picker.button == "Save"
                            else ":material/arrow_forward:", icon_position="right")

    with st.container(key="picker_panel"):
        if uses_industry(picker):
            _industry_row(state)
        for label, group in picker.rows:
            st.caption(label.upper())
            with st.container(key=f"picker_row_{group}", horizontal=True,
                              horizontal_alignment="center", gap="small"):
                for index in range(len(chips(group, state["industry"]))):
                    _chip(state, picker, group, index)
        hint = missing_hint(picker, state["picks"])
        if hint:
            st.caption(hint)
    if any(group == "company" for _, group in picker.rows):
        st.html(logo_styles(chips("company", state["industry"])))

    if pressed:
        if typed and typed.strip():
            return typed.strip()
        st.warning("Pick the chips or type your own words first.")
    return None
