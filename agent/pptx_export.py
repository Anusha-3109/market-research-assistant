"""A pitch deck as a PowerPoint file.

Takes the slides laid out in agent/report/formats.py and writes them as a
.pptx file: wide-screen pages with a title and a few lines each, and a bar
chart on the slide that has measurements. The chart is a real PowerPoint
chart, so its numbers can be read and edited in PowerPoint.
"""

from io import BytesIO

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches, Pt

# The app's own colours.
PEACH = RGBColor(0xFB, 0xDC, 0xCF)
CORAL = RGBColor(0xEC, 0x8F, 0x6A)
INK = RGBColor(0x1F, 0x2A, 0x2E)
GREY = RGBColor(0x56, 0x65, 0x6A)

WIDTH, HEIGHT = Inches(13.333), Inches(7.5)        # 16 to 9
BLANK_LAYOUT = 6


def _text(page, left, top, width, height, lines: list[str], size: int, bold: bool = False,
          colour=INK) -> None:
    """A box of text on a page, one paragraph per line."""
    frame = page.shapes.add_textbox(left, top, width, height).text_frame
    frame.word_wrap = True
    for number, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if number == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.space_after = Pt(size * 0.5)
        for run in paragraph.runs:
            run.font.size, run.font.bold, run.font.color.rgb = Pt(size), bold, colour


def _background(page, colour) -> None:
    fill = page.background.fill
    fill.solid()
    fill.fore_color.rgb = colour


def _chart(page, bars: list[tuple[str, float]]) -> None:
    data = CategoryChartData()
    data.categories = [label for label, _ in bars]
    data.add_series("Search interest", [value for _, value in bars])
    frame = page.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.8), Inches(2.6),
                                  Inches(11.7), Inches(4.3), data)
    chart = frame.chart
    chart.has_legend = False
    chart.plots[0].gap_width = 60
    colour = chart.plots[0].series[0].format.fill
    colour.solid()
    colour.fore_color.rgb = CORAL
    chart.category_axis.tick_labels.font.size = Pt(10)
    chart.value_axis.tick_labels.font.size = Pt(10)


def _size_for(bullets: list[str]) -> int:
    """The size of the letters on a page: smaller when there is more to
    read, so that the lines stay on the page."""
    letters = sum(len(bullet) for bullet in bullets) + 60 * len(bullets)
    if letters <= 700:
        return 20
    return 16 if letters <= 1200 else 13


def slides_to_pptx(slides: list) -> bytes:
    """Return the slides as the bytes of a PowerPoint file."""
    deck = Presentation()
    deck.slide_width, deck.slide_height = WIDTH, HEIGHT
    for number, slide in enumerate(slides):
        page = deck.slides.add_slide(deck.slide_layouts[BLANK_LAYOUT])
        if number == 0:
            # The title page: the title large, on the app's peach.
            _background(page, PEACH)
            _text(page, Inches(0.9), Inches(2.6), Inches(11.5), Inches(1.6), [slide.title], 44,
                  bold=True)
            _text(page, Inches(0.9), Inches(4.2), Inches(11.5), Inches(1), slide.bullets, 20,
                  colour=GREY)
            continue
        _text(page, Inches(0.8), Inches(0.6), Inches(11.7), Inches(1), [slide.title], 32, bold=True)
        _text(page, Inches(0.8), Inches(1.7), Inches(11.7), Inches(5.2),
              [bullet if slide.numbered else f"•  {bullet}" for bullet in slide.bullets], _size_for(slide.bullets))
        if slide.bars:
            _chart(page, slide.bars)
        _text(page, Inches(12.3), Inches(6.9), Inches(0.8), Inches(0.4), [str(number + 1)], 11,
              colour=GREY)
    buffer = BytesIO()
    deck.save(buffer)
    return buffer.getvalue()
