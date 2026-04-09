def build_prompt_input_from_emails(
    emails: list,
    vital_data: dict | None = None,
    reuters_data: dict | None = None,
    cnbc_data: dict | None = None,
) -> str:
    if not emails:
        return "No se encontraron correos en el rango definido."

    lines = []

    lines.append("=== FUENTE PRIORITARIA 1: VITAL KNOWLEDGE ===")
    if vital_data:
        lines.append(f"Remitente: {vital_data.get('source_from', '')}")
        lines.append(f"Asunto: {vital_data.get('source_subject', '')}")
        lines.append(f"Fecha: {vital_data.get('source_date', '')}")
        lines.append("")

        if vital_data.get("market_levels"):
            lines.append("MARKET LEVELS:")
            lines.append(vital_data["market_levels"])
            lines.append("")

        if vital_data.get("whats_happening"):
            lines.append("WHAT'S HAPPENING THIS MORNING:")
            lines.append(vital_data["whats_happening"])
            lines.append("")

        if vital_data.get("watching_today"):
            lines.append("WHAT WE'RE WATCHING TODAY:")
            lines.append(vital_data["watching_today"])
            lines.append("")

        if vital_data.get("thinking_about_markets"):
            lines.append("HOW WE'RE THINKING ABOUT MARKETS:")
            lines.append(vital_data["thinking_about_markets"])
            lines.append("")

        if vital_data.get("market_in_a_minute_macro"):
            lines.append("MARKET IN A MINUTE (MACRO):")
            lines.append(vital_data["market_in_a_minute_macro"])
            lines.append("")

        if vital_data.get("iran_section"):
            lines.append("IRAN:")
            lines.append(vital_data["iran_section"])
            lines.append("")

        if vital_data.get("us_macro_section"):
            lines.append("US MACRO:")
            lines.append(vital_data["us_macro_section"])
            lines.append("")

        if vital_data.get("international_macro_section"):
            lines.append("INTERNATIONAL MACRO:")
            lines.append(vital_data["international_macro_section"])
            lines.append("")

        if vital_data.get("weekly_overview"):
            lines.append("WEEKLY OVERVIEW:")
            for item in vital_data.get("weekly_overview", []):
                lines.append(
                    f"- Día: {item.get('day', '')} | Hora: {item.get('time', '')} | Evento: {item.get('event', '')} | Impacto: {item.get('impact', '')}"
                )
            lines.append("")

        if vital_data.get("daily_calendar"):
            lines.append("CALENDARIO DIARIO:")
            for item in vital_data.get("daily_calendar", []):
                lines.append(
                    f"- Día: {item.get('day', '')} | Hora: {item.get('time', '')} | Evento: {item.get('event', '')} | Impacto: {item.get('impact', '')}"
                )
            lines.append("")

    lines.append("=== FUENTE PRIORITARIA 2: REUTERS DAILY BRIEFING ===")
    if reuters_data:
        lines.append(f"Remitente: {reuters_data.get('source_from', '')}")
        lines.append(f"Asunto: {reuters_data.get('source_subject', '')}")
        lines.append(f"Fecha: {reuters_data.get('source_date', '')}")
        lines.append("Extracto:")
        lines.append(reuters_data.get("body_excerpt", ""))
        lines.append("")

        if reuters_data.get("fetched_links"):
            lines.append("LINKS REVISADOS:")
            for item in reuters_data.get("fetched_links", []):
                lines.append(f"- URL: {item.get('url', '')}")
                lines.append(f"  Título: {item.get('title', '')}")
                lines.append(f"  Resumen: {item.get('summary', '')}")
                for p in item.get("key_paragraphs", []):
                    lines.append(f"  Detalle: {p}")
            lines.append("")

    lines.append("=== FUENTE PRIORITARIA 3: CNBC BREAKING NEWS ===")
    if cnbc_data:
        lines.append(f"Remitente principal: {cnbc_data.get('source_from', '')}")
        lines.append(f"Asunto principal: {cnbc_data.get('source_subject', '')}")
        lines.append(f"Fecha principal: {cnbc_data.get('source_date', '')}")
        lines.append("")

        if cnbc_data.get("selected_emails"):
            lines.append("CORREOS CNBC SELECCIONADOS (ORDENADOS POR RECIENCIA):")
            for item in cnbc_data.get("selected_emails", []):
                lines.append(
                    f"- Rank {item.get('recency_rank', '')} | Fecha: {item.get('date', '')} | Asunto: {item.get('subject', '')}"
                )
            lines.append("")

        lines.append("EXTRACTO CONSOLIDADO:")
        lines.append(cnbc_data.get("body_excerpt", ""))
        lines.append("")

        if cnbc_data.get("fetched_links"):
            lines.append("LINKS CNBC REVISADOS:")
            for item in cnbc_data.get("fetched_links", []):
                lines.append(f"- URL: {item.get('url', '')}")
                lines.append(f"  Título: {item.get('title', '')}")
                lines.append(f"  Resumen: {item.get('summary', '')}")
                for p in item.get("key_paragraphs", []):
                    lines.append(f"  Detalle: {p}")
            lines.append("")

    lines.append("=== OTROS CORREOS DE MERCADO ===")
    for i, email in enumerate(emails, start=1):
        subject = email.get("subject", "").strip()
        sender = email.get("from", "").strip()
        date = email.get("date", "").strip()
        body = email.get("body", "").strip()

        sender_lower = sender.lower()
        if "vital knowledge" in sender_lower:
            continue
        if "dailybriefing@thomsonreuters.com" in sender_lower:
            continue
        if "breakingnews@response.cnbc.com" in sender_lower:
            continue

        lines.append(f"CORREO {i}")
        lines.append(f"Remitente: {sender}")
        lines.append(f"Asunto: {subject}")
        lines.append(f"Fecha: {date}")
        lines.append("Contenido:")
        lines.append(body[:2000])
        lines.append("-" * 60)

    return "\n".join(lines)