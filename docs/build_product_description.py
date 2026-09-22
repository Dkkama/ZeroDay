"""One-page product description for the preliminary submission form."""

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    Spacer,
)

OUT = Path(__file__).resolve().parent / "ZeroDay_Product_Description.pdf"

INK = HexColor("#1C2833")
MUTED = HexColor("#5C6B73")
TEAL = HexColor("#0E6B67")

pdfmetrics.registerFont(TTFont("Body", "/System/Library/Fonts/Supplemental/Georgia.ttf"))
pdfmetrics.registerFont(TTFont("Body-Bold", "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"))
pdfmetrics.registerFont(TTFont("Body-Italic", "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"))
pdfmetrics.registerFont(TTFont("Sans", "/System/Library/Fonts/Supplemental/Arial.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))


def S(name, **kw):
    base = dict(fontName="Body", fontSize=11, leading=16, textColor=INK, alignment=TA_LEFT)
    base.update(kw)
    return ParagraphStyle(name, **base)


styles = {
    "kicker": S("kicker", fontName="Sans", fontSize=8.5, leading=11, textColor=TEAL),
    "title": S("title", fontName="Sans-Bold", fontSize=26, leading=30),
    "sub": S("sub", fontName="Body-Italic", fontSize=11.5, leading=16, textColor=MUTED),
    "h": S("h", fontName="Sans-Bold", fontSize=13, leading=17, textColor=TEAL, spaceBefore=11, spaceAfter=4),
    "p": S("p", spaceAfter=8),
}


def P(text, style="p"):
    return Paragraph(text, styles[style])


def on_page(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(TEAL)
    canvas.rect(0, h - 8 * mm, w, 8 * mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Sans", 8)
    canvas.drawString(18 * mm, h - 5.2 * mm, "ZeroDay  ·  Project description")
    canvas.setFillColor(MUTED)
    canvas.setFont("Sans", 8)
    canvas.drawString(18 * mm, 8 * mm, "Averis × Monash Hackathon 2026")
    canvas.restoreState()


def build():
    doc = BaseDocTemplate(
        str(OUT),
        pagesize=A4,
        title="ZeroDay — project description",
        author="ZeroDay",
    )
    frame = Frame(18 * mm, 16 * mm, A4[0] - 36 * mm, A4[1] - 30 * mm, showBoundary=0)
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=on_page)])
    doc.build([
        Spacer(1, 4 * mm),
        P("PROJECT DESCRIPTION", "kicker"),
        P("ZeroDay", "title"),
        P("A desk for the people who read a shipping company’s mailbox.", "sub"),
        HRFlowable(width="100%", thickness=0.6, color=TEAL, spaceBefore=2, spaceAfter=10),
        P("<b>Purpose.</b> ZeroDay automates the first pass over that mailbox. It categorises each email by the action it needs, and when the action is a document check it compares the shipping instruction with the draft bill of lading. The clerk still decides the cases that are wrong or unclear. The aim is a mailbox that can be worked as a queue, instead of a pile that has to be reread."),
        P("1.  Who has the problem", "h"),
        P("The user is a shipping-documentation clerk. The inbox is not one kind of work. Some writers want two documents checked. Some are issuing a shipping instruction and only mention a draft bill as a later step. Some are asking about freight, local charges, or a cancelled invoice. Some mail is operational, and some is spam. The clerk has to tell these apart before any comparison can start."),
        P("2.  Finding the right email", "h"),
        P("Finding the right message takes time because staff must read each one and decide what action it needs. A document request that is overlooked never reaches the checking step. It sits in the same list as berthing reports, invoice questions, and junk, and the cost of a miss is not a wrong label. It is a shipment that leaves with an unchecked bill of lading."),
        P("ZeroDay puts every message into one of five actions: check the documents, issue a shipping instruction, answer an invoice question, file an operational update, or drop spam. Only the document checks enter the comparison queue. The others are still visible in the inbox, and they are not mixed into the work of comparing two files."),
        P("3.  Comparing two documents by hand", "h"),
        P("Manual comparison is repetitive and easy to get wrong. The shipping instruction is the source of truth. The draft bill of lading has to agree with it. Names, ports, quantities, and weight are checked across the two files, often under time pressure and often for the same parties on many shipments. A missed discrepancy leads to corrections, delays, and another round of email after the draft has already moved on."),
        P("When ZeroDay decides a message is a document check, it compares seven fields: shipper, consignee, notify party, port of loading, port of discharge, container count, and gross weight. A real difference is marked as a mismatch and opened for the clerk, with the two values side by side. If a file is missing, unreadable, or the wrong kind of document, the case is escalated. The system does not invent the missing value and call the documents a match."),
        P("4.  The same fact, written two ways", "h"),
        P("The same information can look different. One document may say “Port of Loading” while the other says “Load Port” or “POL”. One says “Consignee” and the other says “To the order of”. “6 x 40HC” and “6 x 20GP” are the same container count. A port written with a country and a location code is still that city. ZeroDay has to recognise those as the same field, and it has to refuse the opposite mistake: “APRIL FAR EAST” and “APRIL FINE PAPER TRADING” share a brand and are not the same shipper."),
        P("The comparison rules treat the organisation name, the city, the container count, and the total weight as the things that matter. Addresses, container size, vessel, and voyage do not create a mismatch on their own."),
        P("5.  What the clerk still does", "h"),
        P("The desk does not close a bad document by itself. The clerk sees the mismatch or the reason it was escalated, accepts the instruction, accepts the bill, or types the value that should stand, and validates the case. That decision is stored, and so is the program’s original decision. The mailbox stays manageable because the reading and the line-by-line check happen before a person opens the case, and the person remains the one who signs off."),
    ])
    print(OUT)


if __name__ == "__main__":
    build()
