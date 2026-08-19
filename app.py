"""
AI Invoice & Receipt Parser Agent - Streamlit UI

Two views (sidebar navigation):
  1. Process Document - upload a PDF/image, run it through the full
     InvoiceAgent pipeline, and see the validation result.
  2. Saved Documents - browse, search, and drill into previously saved
     (VALID) records.

This file only handles presentation. All real logic lives in
agent/document_agent.py and the services it coordinates.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal

import streamlit as st

from agent.document_agent import InvoiceAgent
from config.settings import settings
from database.database import init_db
from models.document_models import ValidationStatus
from utils.exceptions import DocumentParserError

st.set_page_config(
    page_title="AI Invoice & Receipt Parser Agent",
    page_icon="🧾",
    layout="wide",
)

init_db()


@st.cache_resource
def get_agent() -> InvoiceAgent:
    return InvoiceAgent()


PIPELINE_STAGES = [
    ("upload", "Upload & prepare file"),
    ("extraction", "AI vision extraction"),
    ("schema_validation", "Pydantic schema validation"),
    ("business_validation", "Business rule validation"),
    ("calculation_validation", "Calculation verification"),
    ("save", "Save to database"),
]


def money(value, currency: str | None = None) -> str:
    if value is None:
        return "—"
    try:
        amount = f"{Decimal(value):,.2f}"
    except Exception:
        amount = str(value)
    return f"{amount} {currency}" if currency else amount


# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------
st.sidebar.title("🧾 AI Invoice & Receipt Parser Agent")
page = st.sidebar.radio("Navigate", ["Process Document", "Saved Documents"])

config_problems = settings.validate()
if config_problems:
    with st.sidebar.expander("⚠️ Configuration warnings", expanded=True):
        for problem in config_problems:
            st.warning(problem)

st.sidebar.markdown("---")
st.sidebar.caption(
    f"Model: `{settings.vision_model}`  \n"
    f"Database: `{settings.database_url}`  \n"
    f"Calculation tolerance: `{settings.calculation_tolerance}`"
)

# ---------------------------------------------------------------------------
# Page: Process Document
# ---------------------------------------------------------------------------
if page == "Process Document":
    st.title("Process a new document")
    st.write(
        "Upload an invoice or receipt (PDF, PNG, JPG, or JPEG). The agent will "
        "extract its data with a multimodal Vision AI, validate it, "
        "independently re-check the math, and save it only if everything checks out."
    )

    uploaded_file = st.file_uploader(
        "Upload invoice/receipt",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=False,
    )

    col_a, col_b = st.columns([1, 4])
    process_clicked = col_a.button("Process Document", type="primary", disabled=uploaded_file is None)

    if uploaded_file is not None and not process_clicked:
        st.info(f"Ready to process **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB). "
                 "Click **Process Document** to begin.")

    if process_clicked and uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        agent = get_agent()

        progress_area = st.container()
        status_lines = {key: progress_area.empty() for key, _ in PIPELINE_STAGES}
        progress_bar = progress_area.progress(0)
        stage_order = [k for k, _ in PIPELINE_STAGES]

        def on_progress(stage_key: str, message: str):
            label = dict(PIPELINE_STAGES).get(stage_key, stage_key)
            if stage_key in status_lines:
                status_lines[stage_key].markdown(f"**{label}:** {message}")
            if stage_key in stage_order:
                idx = stage_order.index(stage_key)
                progress_bar.progress(min(1.0, (idx + 1) / len(stage_order)))

        try:
            with st.spinner("Running the document through the pipeline..."):
                validated, saved_id, save_error = agent.process_and_save(
                    file_bytes, uploaded_file.name, progress=on_progress
                )
            progress_bar.progress(1.0)
        except DocumentParserError as exc:
            st.error(f"❌ Processing failed: {exc}")
            st.stop()
        except Exception as exc:  # last-resort guard so the UI never hard-crashes
            st.error(f"❌ Unexpected error while processing the document: {exc}")
            st.stop()

        st.markdown("---")

        # --- Overall status banner -----------------------------------------
        status = validated.status
        if status == ValidationStatus.VALID:
            st.success(f"✅ **VALID** — {uploaded_file.name} passed all checks.")
        elif status == ValidationStatus.NEEDS_REVIEW:
            st.warning(f"🟡 **NEEDS REVIEW** — {uploaded_file.name} needs a human look before saving.")
        else:
            st.error(f"🔴 **INVALID** — {uploaded_file.name} failed validation and was not saved.")

        # --- Save confirmation -----------------------------------------------
        if status == ValidationStatus.VALID:
            if saved_id:
                st.success(f"💾 Saved to the database (id: `{saved_id}`).")
            elif save_error:
                st.error(f"⚠️ Document was VALID but could not be saved: {save_error}")
        else:
            st.info("This record was **not saved** because it is not VALID.")

        doc = validated.document

        # --- Document information ---------------------------------------------
        st.subheader("Document information")
        info_cols = st.columns(4)
        info_cols[0].metric("Type", (doc.document_type.value if doc.document_type else "unknown").title())
        info_cols[1].metric("Document #", doc.document_number or "—")
        info_cols[2].metric("Date", str(doc.document_date) if doc.document_date else "—")
        info_cols[3].metric("Currency", doc.currency or "—")

        vcol, ccol = st.columns(2)
        with vcol:
            st.markdown("**Vendor**")
            if doc.vendor:
                st.write(doc.vendor.name or "—")
                if doc.vendor.address:
                    st.caption(doc.vendor.address)
                contact = " · ".join(filter(None, [doc.vendor.phone, doc.vendor.email]))
                if contact:
                    st.caption(contact)
            else:
                st.write("—")
        with ccol:
            st.markdown("**Customer**")
            if doc.customer:
                st.write(doc.customer.name or "—")
                if doc.customer.address:
                    st.caption(doc.customer.address)
            else:
                st.write("—")

        # --- Line items ------------------------------------------------------
        st.subheader("Line items")
        if doc.line_items:
            rows = []
            for item in doc.line_items:
                rows.append({
                    "Product / Service": item.name or "—",
                    "Description": item.description or "—",
                    "SKU": item.sku or "—",
                    "Qty": item.quantity if item.quantity is not None else "—",
                    "Unit Price": money(item.unit_price),
                    "Discount": money(item.discount),
                    "Tax": money(item.tax),
                    "Subtotal": money(item.subtotal),
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No line items were extracted.")

        # --- Financial summary -----------------------------------------------
        st.subheader("Financial summary")
        fin_cols = st.columns(4)
        fin_cols[0].metric("Subtotal", money(doc.subtotal, doc.currency))
        fin_cols[1].metric("Tax", money(doc.tax, doc.currency))
        fin_cols[2].metric("Shipping", money(doc.shipping, doc.currency))
        fin_cols[3].metric("Discount", money(doc.discount, doc.currency))
        fin_cols2 = st.columns(4)
        fin_cols2[0].metric("Service charges", money(doc.service_charges, doc.currency))
        fin_cols2[1].metric("Other charges", money(doc.other_charges, doc.currency))
        fin_cols2[2].metric("Grand total", money(doc.grand_total, doc.currency))
        fin_cols2[3].metric("Amount paid / Balance due",
                             f"{money(doc.amount_paid, doc.currency)} / {money(doc.balance_due, doc.currency)}")

        # --- Calculation check -------------------------------------------------
        st.subheader("Calculation verification")
        calc = validated.calculation
        if calc:
            calc_cols = st.columns(3)
            calc_cols[0].metric("Calculated total", money(calc.calculated_total, doc.currency))
            calc_cols[1].metric("Extracted total", money(calc.extracted_total, doc.currency))
            diff_display = money(calc.difference, doc.currency) if calc.difference is not None else "—"
            calc_cols[2].metric("Difference", diff_display,
                                 delta="within tolerance" if calc.within_tolerance else "OUT OF TOLERANCE",
                                 delta_color="normal" if calc.within_tolerance else "inverse")

        # --- Issues ------------------------------------------------------------
        if validated.issues:
            st.subheader("Validation notes")
            errors = [i for i in validated.issues if i.severity == "error"]
            warnings = [i for i in validated.issues if i.severity == "warning"]
            if errors:
                st.markdown("**Errors (blocking):**")
                for i in errors:
                    st.error(f"[{i.stage}] {i.field + ': ' if i.field else ''}{i.message}")
            if warnings:
                st.markdown("**Warnings (needs review):**")
                for i in warnings:
                    st.warning(f"[{i.stage}] {i.field + ': ' if i.field else ''}{i.message}")

# ---------------------------------------------------------------------------
# Page: Saved Documents
# ---------------------------------------------------------------------------
else:
    st.title("Saved documents")
    agent = get_agent()

    with st.expander("Search & filter", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        f_number = f1.text_input("Document #")
        f_vendor = f2.text_input("Vendor")
        f_type = f3.selectbox("Type", ["Any", "invoice", "receipt", "unknown"])
        f_status = f4.selectbox("Status", ["Any", "VALID", "INVALID", "NEEDS_REVIEW"])
        f5, f6 = st.columns(2)
        f_date_from = f5.date_input("Date from", value=None)
        f_date_to = f6.date_input("Date to", value=None)

    try:
        results = agent.get_saved_documents(
            document_number=f_number or None,
            vendor=f_vendor or None,
            document_type=None if f_type == "Any" else f_type,
            status=None if f_status == "Any" else f_status,
            date_from=f_date_from if isinstance(f_date_from, date) else None,
            date_to=f_date_to if isinstance(f_date_to, date) else None,
        )
    except DocumentParserError as exc:
        st.error(f"Could not load saved documents: {exc}")
        results = []

    st.write(f"**{len(results)} document(s) found**")

    if results:
        table_rows = [{
            "Document #": r["document_number"] or "—",
            "Type": (r["document_type"] or "—").title(),
            "Vendor": r["vendor_name"] or "—",
            "Date": str(r["document_date"]) if r["document_date"] else "—",
            "Total": money(r["grand_total"], r["currency"]),
            "Status": r["validation_status"],
            "Created": r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else "—",
            "_id": r["id"],
        } for r in results]

        selected_id = st.selectbox(
            "Select a document to view full details:",
            options=[r["_id"] for r in table_rows],
            format_func=lambda doc_id: next(
                (f"{r['Document #']} — {r['Vendor']} — {r['Total']}" for r in table_rows if r["_id"] == doc_id),
                doc_id,
            ),
        )

        st.dataframe(
            [{k: v for k, v in r.items() if k != "_id"} for r in table_rows],
            use_container_width=True, hide_index=True,
        )

        if selected_id:
            st.markdown("---")
            st.subheader("Full record")
            details = agent.get_document_details(selected_id)
            if details:
                d1, d2, d3, d4 = st.columns(4)
                d1.metric("Type", (details["document_type"] or "—").title())
                d2.metric("Document #", details["document_number"] or "—")
                d3.metric("Date", str(details["document_date"]) if details["document_date"] else "—")
                d4.metric("Status", details["validation_status"])

                vcol, ccol = st.columns(2)
                with vcol:
                    st.markdown("**Vendor**")
                    st.write(details["vendor_name"] or "—")
                    if details["vendor_address"]:
                        st.caption(details["vendor_address"])
                    contact = " · ".join(filter(None, [details["vendor_phone"], details["vendor_email"]]))
                    if contact:
                        st.caption(contact)
                with ccol:
                    st.markdown("**Customer**")
                    st.write(details["customer_name"] or "—")
                    if details["customer_address"]:
                        st.caption(details["customer_address"])

                st.markdown("**Line items**")
                if details["items"]:
                    item_rows = [{
                        "Product / Service": i["product_name"] or "—",
                        "Description": i["description"] or "—",
                        "SKU": i["sku"] or "—",
                        "Qty": i["quantity"] if i["quantity"] is not None else "—",
                        "Unit Price": money(i["unit_price"]),
                        "Discount": money(i["discount"]),
                        "Tax": money(i["tax"]),
                        "Subtotal": money(i["subtotal"]),
                    } for i in details["items"]]
                    st.dataframe(item_rows, use_container_width=True, hide_index=True)
                else:
                    st.info("No line items recorded.")

                st.markdown("**Financial summary**")
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("Subtotal", money(details["subtotal"], details["currency"]))
                s2.metric("Tax", money(details["tax"], details["currency"]))
                s3.metric("Grand total", money(details["grand_total"], details["currency"]))
                s4.metric("Balance due", money(details["balance_due"], details["currency"]))

                if details["validation_message"]:
                    st.caption(f"Validation notes: {details['validation_message']}")
                st.caption(f"Source file: {details['source_filename']} · Saved: {details['created_at']}")
    else:
        st.info("No saved documents match your filters yet. Process a document to get started.")
