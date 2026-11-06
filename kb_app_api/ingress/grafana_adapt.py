"""Map Grafana Unified Alerting webhook payloads into ingress envelopes."""
from __future__ import annotations

from typing import Any


def looks_like_grafana_webhook(raw: dict[str, Any]) -> bool:
    if not isinstance(raw, dict):
        return False
    if raw.get("source") == "grafana":
        return True
    alerts = raw.get("alerts")
    status = str(raw.get("status") or "").lower()
    if isinstance(alerts, list) and status in ("firing", "resolved", "ok"):
        return True
    # Grafana sometimes sends state=alerting without status on older templates.
    if isinstance(alerts, list) and raw.get("commonLabels") is not None:
        return True
    return False


def adapt_grafana_webhook(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a Grafana contact-point webhook body into a normalized-ish envelope.
    Keeps the original body under payload for the agent / UI detail expand.
    """
    status = str(raw.get("status") or raw.get("state") or "").lower()
    if status in ("ok", "resolved", "normal"):
        event_type = "alert.resolved"
        status_norm = "resolved"
    else:
        event_type = "alert.firing"
        status_norm = "firing"

    common = raw.get("commonLabels") if isinstance(raw.get("commonLabels"), dict) else {}
    annotations = (
        raw.get("commonAnnotations")
        if isinstance(raw.get("commonAnnotations"), dict)
        else {}
    )
    alerts = raw.get("alerts") if isinstance(raw.get("alerts"), list) else []
    first = alerts[0] if alerts and isinstance(alerts[0], dict) else {}
    first_labels = first.get("labels") if isinstance(first.get("labels"), dict) else {}
    first_ann = (
        first.get("annotations") if isinstance(first.get("annotations"), dict) else {}
    )

    alertname = str(
        common.get("alertname")
        or first_labels.get("alertname")
        or raw.get("title")
        or "Grafana alert"
    )
    severity = str(
        common.get("severity")
        or first_labels.get("severity")
        or common.get("priority")
        or ""
    ).lower()
    instance = str(
        common.get("instance")
        or common.get("host")
        or first_labels.get("instance")
        or first_labels.get("host")
        or ""
    )

    summary = str(raw.get("title") or "").strip()
    if not summary:
        summary = f"[{status_norm.upper()}] {alertname}"
        if instance:
            summary = f"{summary} · {instance}"

    detail_parts: list[str] = []
    msg = str(raw.get("message") or "").strip()
    if msg:
        detail_parts.append(msg)
    for key in ("summary", "description", "runbook_url"):
        val = annotations.get(key) or first_ann.get(key)
        if val and str(val) not in detail_parts:
            detail_parts.append(str(val))
    if not detail_parts and alerts:
        # Compact per-alert lines for expand-in-UI.
        for alert in alerts[:12]:
            if not isinstance(alert, dict):
                continue
            labels = alert.get("labels") if isinstance(alert.get("labels"), dict) else {}
            name = labels.get("alertname") or alertname
            inst = labels.get("instance") or labels.get("host") or ""
            line = f"- {alert.get('status') or status_norm}: {name}"
            if inst:
                line += f" ({inst})"
            detail_parts.append(line)

    fingerprint = str(first.get("fingerprint") or "")
    group_key = str(raw.get("groupKey") or raw.get("group_key") or "")
    dedupe = f"grafana:{group_key or fingerprint or alertname}:{status_norm}"

    links: list[dict[str, str]] = []
    for title, url_key in (
        ("Generator", "generatorURL"),
        ("Silence", "silenceURL"),
        ("Dashboard", "dashboardURL"),
        ("Panel", "panelURL"),
    ):
        url = first.get(url_key) or raw.get(url_key)
        if url:
            links.append({"title": title, "url": str(url)})
    external = raw.get("externalURL")
    if external and not any(l.get("url") == str(external) for l in links):
        links.append({"title": "Grafana", "url": str(external)})

    hints: dict[str, Any] = {
        "severity": severity or None,
        "alertname": alertname,
        "status": status_norm,
        "instance": instance or None,
        "group_key": group_key or None,
        "fingerprint": fingerprint or None,
    }
    # Drop nulls for cleaner match/extract.
    hints = {k: v for k, v in hints.items() if v not in (None, "")}

    return {
        "source": "grafana",
        "type": event_type,
        "summary": summary,
        "detail": "\n\n".join(detail_parts) if detail_parts else None,
        "hints": hints,
        "payload": raw,
        "links": links,
        "dedupe_key": dedupe,
        "adapter_key": "grafana",
    }
