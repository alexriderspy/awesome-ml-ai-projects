from pathlib import Path

OUT = Path(__file__).parent / "practice" / "observatory-handbook.pdf"

PAGES = [
    ("Welcome to Harrow Point Community Observatory", [
        "This handbook is for members of the Harrow Point Community Observatory. Read it once before your first night under the dome, and keep it handy after that.",
        "The observatory was founded in 1987 by Edith Marlowe, a retired physics teacher who wanted the town's children to see Saturn's rings for themselves. The first telescope sat in her garden shed.",
        "Today the dome stands on Harrow Point ridge at an elevation of 412 metres, well above the fog that settles in the valley on autumn nights. The site is about 9 km from the town centre by road.",
        "We are entirely volunteer-run. At the start of 2026 we had 140 paying members, of whom 23 are certified dome keepers.",
    ]),
    ("Our Telescopes", [
        "The main instrument is a 16-inch (406 mm) Ritchey-Chretien reflector that members call Lantern. It sits on a computerised equatorial mount and is used for both visual observing and imaging.",
        "For daytime sessions we have a 5-inch refractor fitted with a hydrogen-alpha filter, which shows solar prominences and filaments. It is stored in the grey cabinet beside the warm room.",
        "Members can also borrow one of three 8-inch Dobsonian telescopes for use at home, for up to two weeks at a time.",
        "Every use of Lantern must be booked in the paper logbook in the warm room at least 48 hours ahead. Bookings are limited to two hours per member per night when the sky is clear.",
    ]),
    ("Membership and Fees", [
        "Membership runs from January to December. Annual fees are 60 euros for adults, 25 euros for students and 95 euros for a family membership covering up to two adults and their children.",
        "Fees are due by 31 January. Members who have not paid by 1 March lose their key card access until the fee is settled.",
        "New members pay a refundable deposit of 20 euros for their key card. The deposit is returned when the card is handed back.",
        "Members over 70 years of age receive a 50 percent discount on the adult fee.",
    ]),
    ("Observing Nights and Rules", [
        "Public observing nights are held on the first Friday of every month, from 8 pm until 11 pm. Members are encouraged to volunteer at least twice a year to help visitors at the eyepiece.",
        "Only red lights are allowed inside the dome and on the observing field after dark. White torches and phone screens ruin the night vision of everyone nearby.",
        "Nobody may operate Lantern without a certified dome keeper present. To become a dome keeper, a member must complete three supervised sessions and pass a short practical check with the chief keeper.",
        "Food is not allowed in the dome. Hot drinks are fine in the warm room.",
    ]),
    ("Safety and Weather", [
        "The dome must be closed if wind gusts exceed 40 km/h or if relative humidity rises above 85 percent. Condensation on the primary mirror is far more expensive than a lost night.",
        "The weather station on the roof logs wind and humidity every minute; the readings are shown on the screen in the warm room.",
        "Never point any telescope at the Sun unless it is the hydrogen-alpha refractor with its filter fitted and checked by a dome keeper.",
        "In an emergency, call the duty keeper on the number posted inside the warm room door. The nearest hospital is in Calder Bridge, 14 km away.",
    ]),
    ("Outreach and Astrophotography", [
        "School groups visit on Tuesday mornings during term time. Each visit is capped at 30 pupils, and teachers book through the outreach coordinator.",
        "The astrophotography club meets on the second Wednesday of each month. The club camera is a cooled monochrome camera with a seven-position filter wheel, kept in the locked drawer under the imaging desk.",
        "Raw image files on the observatory computer are deleted after 90 days. Copy anything you want to keep to your own drive before then.",
        "Each December the club prints a calendar of the year's best member images. Sales of the calendar paid for the dome's new shutter motor in 2024.",
    ]),
]


def build(out: Path = OUT) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    story = []
    for i, (title, paras) in enumerate(PAGES):
        story.append(Paragraph(title, styles["Heading1"]))
        for p in paras:
            story += [Paragraph(p, styles["BodyText"]), Spacer(1, 8)]
        if i < len(PAGES) - 1:
            story.append(PageBreak())

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 9)
        canvas.drawString(72, 30, f"Harrow Point Community Observatory - Member Handbook 2026 - page {doc.page}")

    out.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(out), pagesize=A4, title="Harrow Point Member Handbook").build(
        story, onFirstPage=footer, onLaterPages=footer)
    return out


if __name__ == "__main__":
    print(f"wrote {build()}")
