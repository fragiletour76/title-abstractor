import json

def _to_str(x):
    """Convert value to string, handling None, dicts, and primitives"""
    if x is None or x == "":
        return ""
    if isinstance(x, str):
        return x  # Return strings as-is
    if isinstance(x, (int, float, bool)):
        return str(x)
    if isinstance(x, dict):
        return x.get("name") or x.get("value") or str(x)
    if isinstance(x, (list, tuple)):
        return "; ".join([_to_str(i) for i in x if _to_str(i)])
    return str(x)

def _fmt_names(names, aka_list=None):
    """Format party names with aka"""
    if not names:
        return "N/A"
    names = names if isinstance(names, list) else [names]
    aka_list = aka_list or []
    
    out = []
    for i, n in enumerate(names):
        base = _to_str(n)
        aka = ""
        if i < len(aka_list):
            aka_val = _to_str(aka_list[i]).strip()
            if aka_val:
                aka = f" (a/k/a {aka_val})"
        if base:
            out.append(f"{base}{aka}")
    return "; ".join(out) if out else "N/A"

def render_entry_md(doc, n):
    """Render a single document entry as markdown"""
    p = doc.get("parties", {}) or {}
    dts = doc.get("dates", {}) or {}
    rec = doc.get("recording", {}) or {}
    mon = doc.get("monetary", {}) or {}
    prop = doc.get("property", {}) or {}
    ldc = doc.get("legalDescriptionComparison", {}) or {}
    cls = doc.get("clauses", {}) or {}
    q = doc.get("quality", {}) or {}
    
    # Document header
    doc_type = doc.get('documentType', 'DOCUMENT')
    heading = f"## {n}. {doc_type}\n\n"
    
    # Parties
    from_label = p.get("fromLabel", "From")
    to_label = p.get("toLabel", "To")
    from_names = _fmt_names(p.get("from", []), p.get("aka"))
    to_names = _fmt_names(p.get("to", []))
    parties_block = f"**{from_label}:** {from_names}  \n**{to_label}:** {to_names}\n\n"
    
    # Key details table
    table = (
        "| Field | Value |\n"
        "|:------|:------|\n"
        f"| **Instrument Date** | {_to_str(dts.get('instrumentDate','N/A'))} |\n"
        f"| **Acknowledged Date** | {_to_str(dts.get('acknowledgedDate','N/A'))} |\n"
        f"| **Record Date** | {_to_str(dts.get('recordDate','N/A'))} |\n"
        f"| **Instrument Location** | {_to_str(rec.get('locationInstrumentNumber','N/A'))} |\n"
        f"| **County** | {_to_str(rec.get('county','N/A'))} |\n"
    )
    
    # Add monetary fields if present
    if mon.get('considerationAmount'):
        table += f"| **Consideration** | {_to_str(mon['considerationAmount'])} |\n"
    if mon.get('mortgageAmount'):
        table += f"| **Mortgage Amount** | {_to_str(mon['mortgageAmount'])} |\n"
    if mon.get('transferTaxes'):
        table += f"| **Transfer Taxes** | {_to_str(mon['transferTaxes'])} |\n"
    
    table += "\n"
    
    # Property description
    subject_text = _to_str(prop.get("legalDescription", ""))
    if ldc.get("isSameAsPrior"):
        num = ldc.get("sameAsEntryNumber")
        if num:
            subject_text = f"Same premises as described in entry #{num}"
    
    if not subject_text:
        subject_text = "N/A"
    
    property_section = f"### Property Description\n{subject_text}\n\n"
    
    # Tax Parcel
    if prop.get("taxParcelId"):
        property_section += f"**Tax Parcel ID:** {_to_str(prop['taxParcelId'])}\n\n"
    
    # Clauses (handle both string and array formats)
    clauses_section = ""
    
    if cls.get("beingSamePremises"):
        clauses_section += f"**Being Same Premises:**  \n{_to_str(cls['beingSamePremises'])}\n\n"
    
    # Handle subjectTo as string or array
    subject_to = cls.get("subjectTo")
    if subject_to:
        if isinstance(subject_to, str):
            clauses_section += f"**Subject To:**  \n{subject_to}\n\n"
        elif isinstance(subject_to, list) and subject_to:
            clauses_section += "**Subject To:**\n" + "\n".join([f"- {_to_str(s)}" for s in subject_to]) + "\n\n"
    
    # Handle togetherWith as string or array
    together_with = cls.get("togetherWith")
    if together_with:
        if isinstance(together_with, str):
            clauses_section += f"**Together With:**  \n{together_with}\n\n"
        elif isinstance(together_with, list) and together_with:
            clauses_section += "**Together With:**\n" + "\n".join([f"- {_to_str(s)}" for s in together_with]) + "\n\n"
    
    # Handle exceptingAndReserving as string or array
    excepting = cls.get("exceptingAndReserving")
    if excepting:
        if isinstance(excepting, str):
            clauses_section += f"**Excepting and Reserving:**  \n{excepting}\n\n"
        elif isinstance(excepting, list) and excepting:
            clauses_section += "**Excepting and Reserving:**\n" + "\n".join([f"- {_to_str(s)}" for s in excepting]) + "\n\n"
    
    # Confidence
    conf = q.get('confidence', 0)
    quality_section = f"**Confidence:** {conf}%\n\n"
    
    return heading + parties_block + table + property_section + clauses_section + quality_section

def render_markdown(json_payload):
    """Render all documents as markdown"""
    docs = json_payload.get("documents", [])
    
    if not docs:
        return "No documents found in the processed file."
    
    out = []
    for i, doc in enumerate(docs, start=1):
        out.append(render_entry_md(doc, i))
    
    footer = f"\n---\n\n**Total pages processed:** {json_payload.get('review',{}).get('totalPagesProcessed',0)}"
    
    return "\n---\n\n".join(out) + footer
