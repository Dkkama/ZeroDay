"""Build the preliminary-round documentation PDF."""

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
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    ListFlowable,
    ListItem,
    HRFlowable,
)

OUT = Path(__file__).resolve().parent / "ZeroDay_Documentation.pdf"

INK = HexColor("#1C2833")
MUTED = HexColor("#5C6B73")
TEAL = HexColor("#0E6B67")
TEAL_SOFT = HexColor("#E7F3F2")
LINE = HexColor("#D5DEE3")
ROW = HexColor("#F6F8F8")

pdfmetrics.registerFont(TTFont("Body", "/System/Library/Fonts/Supplemental/Georgia.ttf"))
pdfmetrics.registerFont(TTFont("Body-Bold", "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"))
pdfmetrics.registerFont(TTFont("Body-Italic", "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"))
pdfmetrics.registerFont(TTFont("Sans", "/System/Library/Fonts/Supplemental/Arial.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))


def S(name, **kw):
    base = dict(fontName="Body", fontSize=10.5, leading=15.5, textColor=INK, alignment=TA_LEFT)
    base.update(kw)
    return ParagraphStyle(name, **base)


styles = {
    "kicker": S("kicker", fontName="Sans", fontSize=8.5, leading=11, textColor=TEAL, tracking=0.6),
    "title": S("title", fontName="Sans-Bold", fontSize=26, leading=30, textColor=INK),
    "sub": S("sub", fontName="Body-Italic", fontSize=11, leading=15, textColor=MUTED),
    "h": S("h", fontName="Sans-Bold", fontSize=14, leading=18, textColor=TEAL, spaceBefore=12, spaceAfter=4),
    "h2": S("h2", fontName="Sans-Bold", fontSize=11.5, leading=15, textColor=INK, spaceBefore=8, spaceAfter=2),
    "p": S("p", spaceAfter=7),
    "small": S("small", fontName="Sans", fontSize=8.5, leading=11.5, textColor=MUTED),
    "th": S("th", fontName="Sans-Bold", fontSize=8, leading=11, textColor=white),
    "td": S("td", fontName="Sans", fontSize=8, leading=11, textColor=INK),
    "tdm": S("tdm", fontName="Sans", fontSize=8, leading=11, textColor=MUTED),
    "li": S("li", fontSize=10.5, leading=15, leftIndent=0, spaceAfter=2),
    "flow": S("flow", fontName="Sans", fontSize=9, leading=13, textColor=INK),
}


def P(text, style="p"):
    return Paragraph(text, styles[style])


def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(t, styles["li"]), leftIndent=12, bulletColor=TEAL) for t in items],
        bulletType="bullet",
        start="•",
        leftIndent=14,
        bulletFontName="Sans",
        bulletFontSize=8,
        spaceBefore=1,
        spaceAfter=6,
    )


def section(title, blocks):
    return KeepTogether([P(title, "h"), *blocks])


def on_page(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(TEAL)
    canvas.rect(0, h - 8 * mm, w, 8 * mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Sans", 8)
    canvas.drawString(18 * mm, h - 5.2 * mm, "ZeroDay  ·  Averis × Monash Hackathon 2026")
    canvas.setFillColor(MUTED)
    canvas.setFont("Sans", 8)
    canvas.drawString(18 * mm, 8 * mm, "Preliminary documentation")
    canvas.drawRightString(w - 18 * mm, 8 * mm, str(doc.page))
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 12 * mm, w - 18 * mm, 12 * mm)
    canvas.restoreState()


def score_table():
    header = [
        P("Run", "th"),
        P("Final", "th"),
        P("Category", "th"),
        P("Planted defects", "th"),
        P("Escalations", "th"),
    ]
    rows = [
        ["Model selection<br/>gemini-3-flash, 520 emails", "1.0000", "1.0000", "46 / 46", "20 / 20"],
        ["Live desk on Vertex<br/>same 520 emails", "0.9978", "1.0000", "46 / 46", "20 / 20"],
    ]
    data = [header]
    for row in rows:
        data.append([P(c, "td") for c in row])
    col = [78 * mm, 22 * mm, 24 * mm, 32 * mm, 28 * mm]
    table = Table(data, colWidths=col, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("BACKGROUND", (0, 1), (-1, 1), TEAL_SOFT),
        ("BACKGROUND", (0, 2), (-1, 2), white),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
    ]))
    return table


def component_table():
    header = [P("Piece", "th"), P("Role", "th")]
    rows = [
        ["Clerk desk", "React interface: Dashboard, Inbox, Review, Audit, Settings."],
        ["API", "FastAPI on Cloud Run. One public URL serves the desk and /api."],
        ["Database", "Firestore in asia-southeast1. One document per email, audit row, and job."],
        ["Production model", "Vertex AI, gemini-3-flash-preview. Three prompts at once, eight emails each."],
        ["Model selection", "Cursor cloud agents, used to test models. Not on the request path a clerk uses."],
        ["Mail in", "Zip of the inbox, or IMAP. Classification starts when the zip is dropped."],
    ]
    data = [header] + [[P(a, "td"), P(b, "td")] for a, b in rows]
    table = Table(data, colWidths=[38 * mm, 146 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("BACKGROUND", (0, 1), (-1, 1), TEAL_SOFT),
        ("BACKGROUND", (0, 3), (-1, 3), TEAL_SOFT),
        ("BACKGROUND", (0, 5), (-1, 5), TEAL_SOFT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
    ]))
    return table


def build():
    doc = BaseDocTemplate(
        str(OUT),
        pagesize=A4,
        title="ZeroDay — preliminary documentation",
        author="ZeroDay",
    )
    frame = Frame(18 * mm, 16 * mm, A4[0] - 36 * mm, A4[1] - 30 * mm, showBoundary=0)
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=on_page)])

    story = [
        Spacer(1, 2 * mm),
        P("PRELIMINARY DOCUMENTATION", "kicker"),
        P("ZeroDay", "title"),
        P("A desk that reads a shipping mailbox, decides what each email is asking for, and checks a draft bill of lading against the shipping instruction.", "sub"),
        Spacer(1, 2 * mm),
        HRFlowable(width="100%", thickness=0.6, color=TEAL, spaceAfter=8),
        P("ZeroDay is a working clerk console for the Averis shipping-document problem. Staff lose time finding the right email, and they lose more time comparing two documents by hand. Names, ports, quantities, and weight must match, while the same fact is often written under a different label. A request that is never opened never reaches that check. A mismatch that is missed becomes a correction, a delay, and another round of email."),
        P("The prototype takes a mailbox as a zip, or over IMAP. It classifies every message, compares the shipping instruction with the draft bill of lading when that is the job, and escalates when it cannot decide. A clerk accepts the instruction, the bill, or a typed correction. Every program decision and every human change is written to an audit log. The desk is public on Cloud Run, the data lives in Firestore, and the live model is Gemini 3 Flash on Vertex AI."),
        P("<b>Open it.</b> https://zeroday-316196081380.asia-southeast1.run.app — clerk@zeroday.local / clerk123. Source: https://github.com/Dkkama/ZeroDay", "p"),

        P("1.  The problem", "h"),
        P("The user is a shipping-documentation clerk. The inbox mixes several kinds of work, and only one of them is a document check."),
        bullets([
            "<b>Check the documents.</b> The writer has attached a shipping instruction and a draft bill of lading and wants them compared. The instruction is the source of truth.",
            "<b>Issue a shipping instruction.</b> The writer is sending instructions now and may ask for a draft bill later. That later sentence is not a compare job. There is often no attachment.",
            "<b>Answer an invoice question.</b> Freight, local charges, detention, a missing goods receipt, a cancelled invoice.",
            "<b>Operational mail and spam.</b> Berthing reports, reminders, holiday notices, and junk. These must not enter the document queue.",
        ]),
        P("Manual comparison fails in a specific way. One document says “Port of Loading” and the other says “Load Port” or “POL”. One says “To the order of” and the other says “Consignee”. “6 x 40HC” and “6 x 20GP” are the same container count. “APRIL FAR EAST” and “APRIL FINE PAPER TRADING” are not the same shipper. A blank, a line of question marks, or a commercial invoice saved under a bill-of-lading filename is uncertainty, not a mismatch. Guessing a value there is worse than sending the case to a person."),
        P("The preliminary prototype has to show that this loop works on the real 520-email set, not on a handful of hand-picked examples."),

        P("2.  Technical architecture", "h"),
        P("The desk is one service. The browser never holds a model key and never talks to Firestore. Cloud Run serves the React application and the API on the same origin. Firestore is the system of record, because a JSON file on a Cloud Run instance disappears when the instance shuts down and cannot be shared by two clerks."),
        component_table(),
        Spacer(1, 3 * mm),
        P("Path of one email", "h2"),
        bullets([
            "A zip is dropped on the Dashboard or the Inbox, or IMAP fetches new messages. The zip must contain inbox JSON plus an attachments folder. macOS archive junk is ignored.",
            "Each attachment is turned into text. PDFs, spreadsheets, and plain text are handled. A file with no readable text is marked unreadable rather than filled in.",
            "The selected model receives up to eight emails in one prompt, with the classification rules and an instruction not to copy a value from one case to another. Three such prompts run at once, capped at five prompts a minute.",
            "The result is a category, a status (ok, mismatch, or needs review), the mismatched field names, and the seven field values from each document.",
            "Firestore stores the email, and an audit row records that the program classified it. The Inbox and the Review queue read that document.",
            "The clerk opens a review, picks the instruction value, the bill value, or types one, then validates. The screen moves to the next case immediately. The write follows. The audit row records the person, the field, and the time.",
        ]),
        P("Cursor is a separate path used while we were choosing the model. It keeps three cloud machines warm and sends the same eight-email prompt. It is not required to run the public desk. Vertex calls Gemini directly with the Cloud Run service account, in the same Google project as Firestore and Cloud Run (hackathon-2026-509207, region asia-southeast1)."),

        P("3.  Implementation", "h"),
        P("The comparison rules live in one prompt, sdoc_eval/prompts/v1.md, shared by the evaluation harness and the desk. That is deliberate. A rule we could not score was a rule we did not trust in the product."),
        P("Categories and the compare", "h2"),
        P("Five categories: document check, shipping-instruction request, invoice question, general operations, and spam. A document check is compared only when both files are present, readable, and actually an instruction and a draft bill. Otherwise the status is needs-review, with a reason: wrong document type, missing attachment, unreadable, or missing value. A work order that only asks someone to send a draft which does not exist yet stays a document check with status ok. It is not an error and it is not an instruction request."),
        P("Seven fields are compared: shipper, consignee, notify party, port of loading, port of discharge, container count, and gross weight. Vessel, voyage, commodity, and booking number are ignored because they are not the scored decision. Party names are compared without the address block. Ports are compared on the city, so a UN/LOCODE in parentheses does not create a false mismatch. Container size is ignored. Weight is the document total, in kilograms, with commas and the unit stripped."),
        P("How Vertex is called", "h2"),
        P("One email is one Gemini request. Two to eight emails share one request. Nine emails are one request of eight and a second request for the remainder. A full inbox is the same rule repeated, three requests in flight, five per minute. The limit in production is 2048 emails, which is headroom rather than a product limit. If Google returns a rate-limit error, that batch waits and is tried again. An email missing from the model’s JSON is retried. It is not filled in with a default category."),
        P("The clerk interface", "h2"),
        P("Dashboard shows volume and how many document checks need a person. Inbox lists every message, with the preview opening under the row. Review is the queue of mismatches and escalations. Clicking the instruction or the bill updates the screen at once and saves behind that click, so the clerk is not waiting on Firestore between fields. Validate marks the row fixed and opens the next one. Audit can be exported. Settings holds the model switch, the zip drop zone, IMAP, and the job list."),
        P("Cloud Run is configured with 2 vCPU, 2 GB of memory, and a public URL. It scales to zero when nobody is using it. A classification of hundreds of emails is longer than one web request, so the full Vertex run was executed against the same Firestore database the site reads. Judges opening the inbox are looking at those stored decisions, not at a slide."),

        P("4.  What we measured", "h"),
        P("The official score weights category quality at 30 percent, defect detection at 20 percent, and an end-to-end check at 50 percent. End-to-end success means a planted defect was both routed to a document check and flagged on exactly the right fields. We ran that scorer twice."),
        score_table(),
        Spacer(1, 3 * mm),
        P("The selection run is why the live model is Gemini 3 Flash. We cared about the balance of accuracy and cost on this mailbox, not about a general leaderboard. Category accuracy on that run was perfect across 220 document checks, 125 instruction requests, 75 invoice questions, 60 operational messages, and 40 spam messages. All 20 cases that should be escalated were escalated, including wrong document type, missing files, unreadable files, and missing values. All 46 planted defects were exact."),
        P("The live Vertex pass used the production calling pattern, not the evaluation machines. Category accuracy was again perfect, all 46 planted defects were exact, and all 20 escalations were caught. The final score is 0.9978 because of one false alarm, email 498. Both documents say the discharge port is Ho Chi Minh City, Vietnam. Vertex still flagged that field. The email was in the same eight-email prompt as another Ho Chi Minh shipment that does have a real weight error, and the prompt uses “Ho Chi Minh versus Conakry” as its example of a port mismatch. The two port lines on email 498 are the same string. That is a model error. Section 6 describes the check that would have rejected it."),
        P("We also checked the calling pattern itself. One email returns a single decision. Nine emails return eight decisions from the first prompt and the ninth from the leftover prompt. The 520-email inbox is the table above."),

        P("5.  Challenges", "h"),
        P("Choosing the model", "h2"),
        P("We spent a long time here because the model is the product. We already had a Cursor subscription, so the first design sent every email through Cursor. That was the wrong shape. Each call started a fresh virtual machine. The typical email took about a minute, and some calls died at the three-minute limit. Cursor is a good place to run a controlled test. It is a poor place to boot a computer every time a clerk receives mail."),
        P("We kept Cursor for the test harness: three machines stayed warm, eight emails rode in each follow-up, and we could compare models on the full inbox without rewriting the prompt. Gemini 3 Flash was the best balance of score and cost. The prototype then calls that model on Vertex, paid for with Google Cloud credits, with no virtual machine in the path."),
        P("Choosing where it runs", "h2"),
        P("We did not have a hosting account we could keep on for free. After the first workshop we found that Cloud Run is covered by the Google Cloud trial credits. That settled the rest of the stack. Vertex, Firestore, and the website sit in one project, and the Cloud Run service account is allowed to call the model and the database. We did not want a second vendor for the database once the documents turned out to be a few kilobytes each."),
        P("Understanding the work", "h2"),
        P("The problem statement is a clerk’s job, and none of us do that job. The dangerous confusion is between “please check these two documents” and “here is the shipping instruction, send me a draft later.” Both mention a bill of lading. Only the first one is a comparison. We rewrote the prompt against the mailbox until those two stopped collapsing into each other, and until a missing file was escalated instead of marked as a clean match. The label problem (Port of Loading versus Load Port, consignee versus to-the-order-of) is the same kind of trap. The prompt now states the equivalence rules in the words the scorer uses."),
        P("Quota, retries, and a label we should not have saved", "h2"),
        P("The first Vertex attempt sent eight emails as eight simultaneous calls. Google answered with HTTP 429, resource exhausted. Retrying immediately made the burst worse. We stopped that run. The working pattern is the one in section 3: eight emails inside one prompt, three prompts at a time, and a wait when the quota is hit. That finished the inbox with no failed emails."),
        P("An earlier Cursor test stored a timeout as if it were a real classification. Email 18 is a request to send a draft bill, with no attachment. The machines timed out twice. The fallback record was a generic operational email, and the desk saved it as success. The prompt is explicit that this message is a document check. The later Vertex pass classified it correctly. A failed call still needs to stay unfinished, so a fallback can never look like an answer. That is not finished, and we are not claiming that it is."),
        P("Three writers at once also collided inside Firestore. The audit counter is one document, and parallel saves aborted with “too much contention.” The counter now retries. The emails themselves are separate documents, so the classifications were not lost."),
        P("A long job cannot live only inside a Cloud Run request. The service scales to zero, and a background thread dies when the request ends. The 520-email Vertex run wrote into the production database from a process that was allowed to keep running. The website then showed the results. A later version should use a real job, not a thread tied to a page view."),

        P("6.  Future roadmap", "h"),
        P("The preliminary desk is the core loop: mail in, classify, compare or escalate, human decision, audit. Turning it into a product is the work after this round, not a replacement of that loop."),
        bullets([
            "<b>Sign-in and a real workspace.</b> The demo login is one shared clerk. A product needs accounts, a company workspace, and more than one person in the same queue without sharing a password.",
            "<b>The company mailbox.</b> IMAP with a stored password is enough to prove ingest. The next step is mailbox OAuth, so a team connects the documentation inbox instead of pasting credentials into Settings.",
            "<b>Do not save a guess.</b> A timed-out model call stays unprocessed and is retried. A mismatch is written only when the two extracted values differ, which would have rejected the false port flag on email 498.",
            "<b>A job that outlives the page.</b> Classifying a large inbox runs as a Cloud Run job, with the same Firestore the desk reads, and the website only displays progress.",
            "<b>Learn from the clerk.</b> Validated corrections are the best examples we can add to the prompt. They are already in the audit log.",
            "<b>Final round.</b> Extend this desk. The public URL, the prompt, the score, and the queue are the base. Authentication, the mailbox, and the stricter save rules are the extension.",
        ]),
        P("The practical value is already visible in the queue. A clerk can see which messages are document checks, open the two values side by side, and leave a record of who resolved them. The credible path beyond the hackathon is to put that queue on the mailbox the team already uses, with real accounts, without changing the decision the model is asked to make."),

        P("7.  Where the evidence is", "h"),
        bullets([
            "Live desk: https://zeroday-316196081380.asia-southeast1.run.app",
            "Demo clerk: clerk@zeroday.local / clerk123",
            "Source and setup: https://github.com/Dkkama/ZeroDay",
            "Prompt: sdoc_eval/prompts/v1.md",
            "Selection score: sdoc_eval/outputs/flash25_v2/score.json (final 1.0000)",
            "The inbox currently loaded in Firestore is the Vertex pass (final 0.9978).",
        ]),
        Spacer(1, 2 * mm),
        P("Judges can log in, open Review, and walk a mismatch without running a model call. The decisions are already stored. Settings shows the Vertex provider and will accept a new zip of one email, nine emails, or the full inbox.", "p"),
    ]
    doc.build(story)
    print(OUT)


if __name__ == "__main__":
    build()
