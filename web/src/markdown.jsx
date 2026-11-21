import React from "react";

export function Markdown({ text }) {
  const blocks = parseBlocks(String(text || ""));
  if (!blocks.length) return null;
  return (
    <div className="md">
      {blocks.map((block, index) => (
        <Block key={index} block={block} />
      ))}
    </div>
  );
}

function parseBlocks(source) {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let text = [];
  const flush = () => {
    if (!text.length) return;
    blocks.push({ kind: "text", text: text.join("\n") });
    text = [];
  };
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (line.startsWith("```")) {
      flush();
      const code = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      index += 1;
      blocks.push({ kind: "code", text: code.join("\n") });
      continue;
    }
    if (isTableLine(line) && index + 1 < lines.length && isSeparator(lines[index + 1])) {
      flush();
      const header = splitCells(line);
      index += 2;
      const rows = [];
      while (index < lines.length && isTableLine(lines[index]) && !isSeparator(lines[index])) {
        rows.push(splitCells(lines[index]));
        index += 1;
      }
      blocks.push({ kind: "table", header, rows });
      continue;
    }
    text.push(line);
    index += 1;
  }
  flush();
  return blocks;
}

function isTableLine(line) {
  const trimmed = line.trim();
  return trimmed.includes("|") && trimmed.replace(/\|/g, "").trim().length > 0;
}

function isSeparator(line) {
  return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
}

function splitCells(line) {
  let raw = line.trim();
  if (raw.startsWith("|")) raw = raw.slice(1);
  if (raw.endsWith("|")) raw = raw.slice(0, -1);
  return raw.split("|").map((cell) => cell.trim());
}

function Block({ block }) {
  if (block.kind === "code") {
    return (
      <pre>
        <code>{block.text}</code>
      </pre>
    );
  }
  if (block.kind === "table") {
    return (
      <div className="md-table">
        <table>
          <thead>
            <tr>
              {block.header.map((cell, index) => (
                <th key={index}>{inline(cell)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex}>{inline(cell)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  return <TextBlock text={block.text} />;
}

function TextBlock({ text }) {
  const lines = text.split("\n");
  const out = [];
  let paragraph = [];
  let list = null;

  function flushParagraph() {
    if (!paragraph.length) return;
    const linesToShow = paragraph;
    paragraph = [];
    out.push(<p key={out.length}>{linesToShow.map((line, index) => (
      <React.Fragment key={index}>
        {index > 0 && <br />}
        {inline(line)}
      </React.Fragment>
    ))}</p>);
  }

  function flushList() {
    if (!list) return;
    const { ordered, items } = list;
    list = null;
    const Tag = ordered ? "ol" : "ul";
    out.push(
      <Tag key={out.length}>
        {items.map((item, index) => (
          <li key={index}>{inline(item)}</li>
        ))}
      </Tag>,
    );
  }

  for (const line of lines) {
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    const item = /^\s*(?:[-*+]|\d+\.)\s+(.*)$/.exec(line);
    if (heading) {
      flushParagraph();
      flushList();
      const Tag = heading[1].length === 1 ? "h3" : heading[1].length === 2 ? "h4" : "h5";
      out.push(<Tag key={out.length}>{inline(heading[2])}</Tag>);
      continue;
    }
    if (item && line.trim()) {
      flushParagraph();
      const ordered = /^\s*\d+\./.test(line);
      if (!list || list.ordered !== ordered) {
        flushList();
        list = { ordered, items: [] };
      }
      list.items.push(item[1]);
      continue;
    }
    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }
    flushList();
    paragraph.push(line);
  }
  flushParagraph();
  flushList();
  return <>{out}</>;
}

function inline(text) {
  const pattern = /(`[^`\n]+`)|(\*\*[^*]+\*\*)|(~~[^~]+~~)|(\[[^\]]+\]\(https?:\/\/[^)\s]+\))|(\*[^*\n]+\*)/g;
  const nodes = [];
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > last) nodes.push(text.slice(last, index));
    const token = match[0];
    if (token.startsWith("`")) nodes.push(<code key={index}>{token.slice(1, -1)}</code>);
    else if (token.startsWith("**")) nodes.push(<strong key={index}>{token.slice(2, -2)}</strong>);
    else if (token.startsWith("~~")) nodes.push(<s key={index}>{token.slice(2, -2)}</s>);
    else if (token.startsWith("[")) {
      const link = /^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/.exec(token);
      nodes.push(
        <a key={index} href={link[2]} target="_blank" rel="noreferrer">
          {link[1]}
        </a>,
      );
    } else nodes.push(<em key={index}>{token.slice(1, -1)}</em>);
    last = index + token.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}
