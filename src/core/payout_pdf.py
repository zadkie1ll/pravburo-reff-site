from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

from src.services.payouts import PayoutRow

FONT_DIR = Path(__file__).parents[1] / "assets" / "fonts"

COLUMN_WIDTHS = (25, 55, 55, 30, 45)
HEADERS = ("Дата", "Клиент", "Тип выплаты", "Сумма", "Статус")


def build_payouts_pdf(agent_label: str, filters_label: str, rows: list[PayoutRow]) -> bytes:
    pdf = FPDF(orientation="L", format="A4")
    pdf.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "История выплат", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 11)
    pdf.cell(0, 8, agent_label, new_x="LMARGIN", new_y="NEXT")
    if filters_label:
        pdf.cell(0, 8, filters_label, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("DejaVu", "", 10)
    table_rows = [HEADERS] + [
        (
            row.payout_date_label,
            row.client_name,
            row.type_label,
            row.amount_label,
            row.status_label,
        )
        for row in rows
    ]
    if not rows:
        table_rows.append(("Нет данных за выбранный период", "", "", "", ""))

    with pdf.table(
        table_rows,
        col_widths=COLUMN_WIDTHS,
        text_align="LEFT",
        headings_style=FontFace(family="DejaVu", emphasis="BOLD"),
    ):
        pass

    return bytes(pdf.output())
