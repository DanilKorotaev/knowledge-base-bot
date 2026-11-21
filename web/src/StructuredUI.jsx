import React, { useState } from "react";
import { Markdown } from "./markdown.jsx";

function textOf(node) {
  return node.text || node.label || "";
}

export function StructuredUI({ document, onEvent, busy }) {
  const screen = document?.screen || document;
  const [values, setValues] = useState({});
  if (!screen || typeof screen !== "object") return null;

  function setValue(id, value) {
    setValues((current) => ({ ...current, [id]: value }));
  }

  function currentValue(node) {
    if (Object.prototype.hasOwnProperty.call(values, node.id)) return values[node.id];
    return node.value;
  }

  async function fire(node, extra) {
    if (!onEvent || !node.action_id) return;
    const payloadValues = node.submit ? { ...values, ...extra } : extra;
    await onEvent({
      action_id: node.action_id,
      component_id: node.id,
      client_schema_version: document?.schema_version || 1,
      values: payloadValues || null,
    });
  }

  return (
    <div className="sui">
      <Node node={screen} valueOf={currentValue} setValue={setValue} fire={fire} busy={busy} />
    </div>
  );
}

function Node({ node, valueOf, setValue, fire, busy }) {
  if (!node || typeof node !== "object") return null;
  const type = node.type;
  if (type === "vstack" || type === "hstack") {
    const children = node.children || [];
    const metrics = children.length >= 2 && children.every((child) => child.type === "metric" || child.type === "timer");
    const className = metrics ? "sui-metrics" : type === "hstack" ? "sui-row" : "sui-stack";
    return (
      <div className={className}>
        {children.map((child) => (
          <Node key={child.id} node={child} valueOf={valueOf} setValue={setValue} fire={fire} busy={busy} />
        ))}
      </div>
    );
  }
  if (type === "markdown") return <Markdown text={textOf(node)} />;
  if (type === "text") return <p className="sui-text">{textOf(node)}</p>;
  if (type === "callout") return <p className={`sui-callout ${node.variant || "info"}`}>{textOf(node)}</p>;
  if (type === "divider") return <hr />;
  if (type === "spacer") return <div style={{ height: node.size || 8 }} />;
  if (type === "metric" || type === "timer") {
    return (
      <div className="sui-metric">
        {node.label && <span>{node.label}</span>}
        <strong>{metricValue(node)}</strong>
      </div>
    );
  }
  if (type === "progress") {
    const max = Number(node.max || 1);
    const value = Number(node.value || 0);
    return <progress max={max} value={value} />;
  }
  if (type === "link") {
    return (
      <a href={node.url} target="_blank" rel="noreferrer">
        {node.label || node.url}
      </a>
    );
  }
  if (type === "image" && node.url) return <img src={node.url} alt={node.alt || ""} />;
  if (type === "file") return <p className="muted">{node.name || node.label || "Файл"}</p>;
  if (type === "button") {
    return (
      <button type="button" disabled={busy} onClick={() => fire(node)}>
        {node.label}
      </button>
    );
  }
  if (type === "confirm") {
    return (
      <div className="sui-stack">
        <p>{node.text}</p>
        <button type="button" disabled={busy} onClick={() => fire(node, { confirmed: true })}>
          {node.label}
        </button>
      </div>
    );
  }
  if (type === "checkbox") {
    return (
      <label className="check">
        <input
          type="checkbox"
          checked={Boolean(valueOf(node))}
          onChange={(event) => setValue(node.id, event.target.checked)}
        />
        {node.label}
      </label>
    );
  }
  if (type === "text_field") {
    return (
      <label>
        {node.label}
        <input value={valueOf(node) ?? ""} onChange={(event) => setValue(node.id, event.target.value)} />
      </label>
    );
  }
  if (type === "select" || type === "radio_group") {
    return (
      <label>
        {node.label}
        <select value={valueOf(node) ?? ""} onChange={(event) => setValue(node.id, event.target.value)}>
          <option value="">—</option>
          {(node.options || []).map((option) => (
            <option key={option.value || option.id || option.label} value={option.value || option.id}>
              {option.label || option.value}
            </option>
          ))}
        </select>
      </label>
    );
  }
  if (type === "date" || type === "time") {
    return (
      <label>
        {node.label}
        <input type={type} value={valueOf(node) ?? ""} onChange={(event) => setValue(node.id, event.target.value)} />
      </label>
    );
  }
  if (type === "slider" || type === "stepper") {
    return (
      <label>
        {node.label}: {valueOf(node) ?? node.value ?? node.min ?? 0}
        <input
          type="range"
          min={node.min ?? 0}
          max={node.max ?? 100}
          step={node.step ?? 1}
          value={valueOf(node) ?? node.value ?? node.min ?? 0}
          onChange={(event) => setValue(node.id, Number(event.target.value))}
        />
      </label>
    );
  }
  if (type === "table") return <Table node={node} />;
  if (type === "chart") return <Chart node={node} />;
  return <p className="muted">{type}</p>;
}

function metricValue(node) {
  if (typeof node.text === "string" && node.text) return node.text;
  const value = node.value;
  if (value == null || value === "") return "—";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  if (typeof value === "boolean") return value ? "да" : "нет";
  return "—";
}

function cellText(row, column, index) {
  const raw = Array.isArray(row) ? row[index] : row?.[column?.key || column?.id];
  if (raw == null) return "";
  const text = String(raw);
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    const date = new Date(`${text}T00:00:00`);
    if (!Number.isNaN(date.getTime())) {
      return date.toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" });
    }
  }
  return text;
}

function Table({ node }) {
  const columns = node.columns || [];
  const rows = node.rows || [];
  const width = Math.max(columns.length, ...rows.map((row) => (Array.isArray(row) ? row.length : 0)), 0);
  const heads = columns.length
    ? columns
    : Array.from({ length: width }, (_, index) => ({ id: index, label: "" }));
  return (
    <div className="table-wrap">
      {node.label && <p className="sui-text">{node.label}</p>}
      <table>
        {columns.length > 0 && (
          <thead>
            <tr>
              {heads.map((column, index) => (
                <th key={column.id || column.key || index}>{column.label || column.key || ""}</th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {heads.map((column, cellIndex) => (
                <td key={column.id || column.key || cellIndex}>{cellText(row, column, cellIndex)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Chart({ node }) {
  const series = node.series || [];
  const max = Math.max(1, ...series.map((point) => Number(point.y ?? point.v ?? 0)));
  return (
    <div className="sui-chart">
      {series.map((point, index) => {
        const value = Number(point.y ?? point.v ?? 0);
        return (
          <div key={index} className="bar" title={point.label || point.x || ""}>
            <span style={{ height: `${Math.max(4, (value / max) * 72)}px` }} />
          </div>
        );
      })}
    </div>
  );
}
