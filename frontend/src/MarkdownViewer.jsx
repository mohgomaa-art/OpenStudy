/**
 * OpenStudy Rich Markdown Viewer
 * Renders markdown with: KaTeX math, Mermaid diagrams, syntax highlighting,
 * callout blocks, medical learning blocks, and interactive flashcards.
 * Includes auto-heal engine for LLM syntax errors.
 */
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import 'katex/dist/katex.min.css';

// ── Inline SVG icon helper ────────────────────────────────────────────────────
const Icon = ({ d, size = 16, color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

const ICONS = {
  copy:     'M8 4H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-2M8 4a2 2 0 012-2h4a2 2 0 012 2M8 4h8',
  check:    'M20 6L9 17l-5-5',
  info:     'M12 2a10 10 0 100 20A10 10 0 0012 2zm0 9v5m0-9h.01',
  warning:  'M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zm1.71 4.14v4m0 4h.01',
  tip:      'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
  success:  'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  question: 'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  important:'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  flip:     'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
  collapse: 'M19 9l-7 7-7-7',
  expand:   'M9 18l6-6-6-6',
  pill:     'M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18',
  scope:    'M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18',
  brain:    'M9.5 2a2.5 2.5 0 00-2.5 2.5V5H6a4 4 0 00-4 4v5a4 4 0 004 4h.5v.5a2.5 2.5 0 005 0V18h1v.5a2.5 2.5 0 005 0V18H18a4 4 0 004-4V9a4 4 0 00-4-4h-1v-.5A2.5 2.5 0 0014.5 2h-5z',
  heal:     'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z',
};

// ── Callout config ────────────────────────────────────────────────────────────
const CALLOUT_CONFIG = {
  NOTE:      { color: '#3b82f6', bg: 'rgba(59,130,246,0.08)',  border: 'rgba(59,130,246,0.25)',  icon: 'info',      label: 'Note' },
  INFO:      { color: '#3b82f6', bg: 'rgba(59,130,246,0.08)',  border: 'rgba(59,130,246,0.25)',  icon: 'info',      label: 'Info' },
  TIP:       { color: '#10b981', bg: 'rgba(16,185,129,0.08)',  border: 'rgba(16,185,129,0.25)',  icon: 'tip',       label: 'Tip' },
  SUCCESS:   { color: '#10b981', bg: 'rgba(16,185,129,0.08)',  border: 'rgba(16,185,129,0.25)',  icon: 'success',   label: 'Success' },
  WARNING:   { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)',  border: 'rgba(245,158,11,0.25)',  icon: 'warning',   label: 'Warning' },
  CAUTION:   { color: '#ef4444', bg: 'rgba(239,68,68,0.08)',   border: 'rgba(239,68,68,0.25)',   icon: 'warning',   label: 'Caution' },
  IMPORTANT: { color: '#8b5cf6', bg: 'rgba(139,92,246,0.08)', border: 'rgba(139,92,246,0.25)', icon: 'important', label: 'Important' },
  QUESTION:  { color: '#06b6d4', bg: 'rgba(6,182,212,0.08)',  border: 'rgba(6,182,212,0.25)',  icon: 'question',  label: 'Question' },
};

// ══════════════════════════════════════════════════════════════════════════════
// AUTO-HEAL ENGINE  v2
// Fixes common LLM markdown syntax errors before rendering.
// Each rule records what it changed so callers can show a repair badge.
// ══════════════════════════════════════════════════════════════════════════════
const CUSTOM_TYPES = ['disease', 'drug', 'osce', 'mnemonic', 'flashcard', 'clinical', 'differential'];

function healContentWithReport(raw) {
  if (!raw) return { text: raw, repairs: [] };
  const repairs = [];
  let text = raw;

  // ── Rule 1: Alias normalisation (before type casing, so aliases become real types) ──
  const aliasBefore = text;
  text = text.replace(/```\s*ddx\s*/gi, '```differential\n');
  text = text.replace(/```\s*flash\s*/gi, '```flashcard\n');
  text = text.replace(/```\s*card\s*/gi, '```flashcard\n');
  if (text !== aliasBefore) repairs.push('Aliased non-standard block type (ddx/flash/card)');

  // ── Rule 2: Normalize custom block type casing + trailing spaces ──
  const typePattern = new RegExp('```\\s*(' + CUSTOM_TYPES.join('|') + ')\\s*', 'gi');
  const caseFixed = text.replace(typePattern, (_, type) => '```' + type.toLowerCase() + '\n');
  if (caseFixed !== text) repairs.push('Normalized custom block type casing');
  text = caseFixed;

  // ── Rule 3: Normalize Obsidian callout casing — `[! note]` → `[!NOTE]` ──
  text = text.replace(/\[!\s*([a-z]+)\s*\]/gi, (_, t) => `[!${t.toUpperCase()}]`);

  // ── Rule 4: Fix missing heading space — `##Title` → `## Title` ──
  const headingFixed = text.replace(/^(#{1,6})([^\s#])/gm, '$1 $2');
  if (headingFixed !== text) repairs.push('Fixed missing heading space (##Title → ## Title)');
  text = headingFixed;

  // ── Rule 5: Fix mermaid body (inside fences) ──
  text = text.replace(/(```mermaid\n)([\s\S]*?)(```)/gi, (_, open, body, close) => {
    const healed = body
      .replace(/-->\s*(\n|$)/gm, '\n')
      .replace(/\s*-->\s*-->/g, ' -->')
      .replace(/^\s*graph\s+(?!TD|LR|TB|RL|BT)\w+/im, 'graph TD')
      .replace(/\[\[([^\]]+)\]\]/g, '[$1]')
      .replace(/[^\x20-\x7E\n\r\t]/g, '');
    if (healed !== body) repairs.push('Fixed Mermaid syntax (trailing arrows / wiki-links / non-ASCII)');
    return open + healed + close;
  });

  // ── Rule 6: Fix table separator — header row with no separator below ──
  const isSepRow = (row) => /^\|[\s|:\-]+\|$/.test(row.trim());
  text = text.replace(/((?:^\|.+\|\s*\n)+)/gm, (tableBlock) => {
    const rows = tableBlock.trimEnd().split('\n').filter(Boolean);
    if (rows.length === 0) return tableBlock;
    if (rows.length >= 2 && isSepRow(rows[1])) return tableBlock; // already correct
    // Insert a separator after header row
    const cols = (rows[0].match(/\|/g) || []).length - 1;
    const sep = '|' + ' --- |'.repeat(Math.max(1, cols));
    repairs.push('Fixed missing table separator row');
    return rows[0] + '\n' + sep + '\n' + rows.slice(1).join('\n') + (tableBlock.endsWith('\n') ? '\n' : '');
  });

  // ── Rule 7: Unified fence state machine — close all unclosed fences ──
  //    Line-by-line scan with an explicit stack; replaces old Rules 2+3.
  {
    const typeSet = new Set(CUSTOM_TYPES);
    const lines = text.split('\n');
    const stack = [];  // { kind: 'custom'|'code', token }
    for (const line of lines) {
      const openMatch = line.match(/^```(\S+)/);
      const closeMatch = !openMatch && /^```\s*$/.test(line);
      if (openMatch) {
        const token = openMatch[1].toLowerCase();
        stack.push({ kind: typeSet.has(token) ? 'custom' : 'code', token });
      } else if (closeMatch) {
        if (stack.length > 0) stack.pop();
        // stray closer when stack empty — leave as-is
      }
    }
    if (stack.length > 0) {
      text = text + stack.map(() => '\n```').join('');
      repairs.push(`Auto-closed ${stack.length} unclosed fenced block(s): ${stack.map(s => s.token).join(', ')}`);
    }
  }

  // ── Rule 8: Fix unbalanced display math `$$` — odd count means unclosed ──
  {
    const count = (text.match(/\$\$/g) || []).length;
    if (count % 2 !== 0) {
      text = text + '\n$$';
      repairs.push('Closed unclosed display math ($$)');
    }
  }

  // ── Rule 10: Expand inline bullet lists written on one line by the LLM ──
  // LLMs often write "* Foo * Bar * Baz" on a single line. Markdown parsers
  // interpret the asterisks as italic delimiters. We split such lines into
  // proper newline-separated list items so remark-gfm renders them correctly.
  // Trigger: line contains 2+ occurrences of " * " (space-star-space).
  {
    const inlineBulletBefore = text;
    text = text.replace(/^(.*)$/gm, (line) => {
      // Must contain at least 2 " * " sequences to be an inline bullet list
      if ((line.match(/ \* /g) || []).length < 1) return line;
      // Don't touch lines that are already proper list items (start with - or *)
      if (/^\s*[-*]\s/.test(line)) return line;
      // Don't touch lines that are purely bold/italic (* without a following space boundary)
      // Split the line on bullet separators: " * " or line-start "* "
      // We process the whole line: prefix may be blockquote "> " markers
      const quotePrefix = line.match(/^((?:>\s*)+)/)?.[1] || '';
      const rest = line.slice(quotePrefix.length);
      // Split into: optional bold header + bullet items
      // e.g. "**Header:** * A * B * C" → header="**Header:** ", items=["A","B","C"]
      const parts = rest.split(/ \* /);
      if (parts.length < 2) return line;
      // First part may be a bold label like "**Label:**" or empty
      const [first, ...bulletParts] = parts;
      const firstTrimmed = first.trim();
      const isLabel = firstTrimmed === '' || /^\*\*.*\*\*:?\s*$/.test(firstTrimmed) || /^[^*]+:$/.test(firstTrimmed);
      if (!isLabel) {
        // first part is itself a bullet item — treat all parts as bullets
        const allItems = [firstTrimmed, ...bulletParts.map(s => s.trim())].filter(Boolean);
        return allItems.map(item => `${quotePrefix}- ${item}`).join('\n');
      }
      const items = bulletParts.map(s => s.trim()).filter(Boolean);
      if (items.length === 0) return line;
      const header = firstTrimmed ? `${quotePrefix}${firstTrimmed}\n` : '';
      return header + items.map(item => `${quotePrefix}- ${item}`).join('\n');
    });
    if (text !== inlineBulletBefore) repairs.push('Expanded inline bullet list (* a * b → - a\\n- b)');
  }

  return { text, repairs };
}

function healContent(raw) {
  return healContentWithReport(raw).text;
}

// ── HealReport badge ──────────────────────────────────────────────────────────
function HealReport({ repairs }) {
  const [open, setOpen] = useState(false);
  if (!repairs || repairs.length === 0) return null;
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', marginBottom: 8,
      background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.2)',
      borderRadius: 8, overflow: 'hidden', fontSize: 11,
    }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px',
          background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left',
          color: '#f59e0b', fontWeight: 600,
        }}
      >
        <Icon d={ICONS.heal} size={12} color="#f59e0b" />
        {repairs.length} syntax fix{repairs.length > 1 ? 'es' : ''} applied
        <span style={{ marginLeft: 'auto', opacity: 0.6 }}>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <ul style={{ margin: 0, padding: '4px 10px 8px 28px', color: '#94a3b8', listStyle: 'disc' }}>
          {repairs.map((r, i) => <li key={i} style={{ marginBottom: 2 }}>{r}</li>)}
        </ul>
      )}
    </div>
  );
}

// ── Mermaid renderer ──────────────────────────────────────────────────────────
function MermaidBlock({ code }) {
  const ref = useRef(null);
  const [error, setError] = useState(null);
  const [healed, setHealed] = useState(false);
  const [zoomed, setZoomed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const tryRender = (src, isHealed) => {
      import('mermaid').then(({ default: mermaid }) => {
        mermaid.initialize({
          startOnLoad: false,
          theme: 'default',
          securityLevel: 'loose',
          fontFamily: "'Inter', sans-serif",
        });
        const id = 'mermaid-' + Math.random().toString(36).slice(2);
        mermaid.render(id, src)
          .then(({ svg }) => {
            if (!cancelled && ref.current) {
              ref.current.innerHTML = svg;
              if (isHealed) setHealed(true);
            }
          })
          .catch(e => {
            if (cancelled) return;
            if (!isHealed) {
              // Auto-heal attempt
              const fixed = src
                .replace(/-->\s*(\n|$)/gm, '\n')
                .replace(/\s*-->\s*-->/g, ' -->')
                .replace(/^\s*graph\s+(?!TD|LR|TB|RL|BT)\w+/im, 'graph TD')
                .replace(/\[\[([^\]]+)\]\]/g, '[$1]')   // wiki-links
                .replace(/[^\x20-\x7E\n\r\t]/g, '');    // non-ASCII chars
              if (fixed !== src) {
                tryRender(fixed, true);
              } else {
                setError(e.message);
              }
            } else {
              setError(e.message);
            }
          });
      });
    };

    tryRender(code, false);
    return () => { cancelled = true; };
  }, [code]);

  if (error) {
    return (
      <div className="md-mermaid-error">
        <span style={{ fontSize: 11, color: '#ef4444', fontFamily: 'monospace' }}>
          Diagram syntax error — could not auto-fix: {error}
        </span>
        <pre style={{ fontSize: 11, marginTop: 6, color: '#94a3b8', whiteSpace: 'pre-wrap' }}>{code}</pre>
      </div>
    );
  }
  return (
    <>
      {healed && (
        <div style={{ fontSize: 10, color: '#f59e0b', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
          <Icon d={ICONS.heal} size={11} color="#f59e0b" /> Auto-healed diagram syntax
        </div>
      )}
      <div className="md-mermaid-container" ref={ref} onClick={() => setZoomed(true)} title="Click to zoom" />
      {zoomed && (
        <div className="md-mermaid-overlay" onClick={() => setZoomed(false)}>
          <div className="md-mermaid-zoom" dangerouslySetInnerHTML={{ __html: ref.current ? ref.current.innerHTML : '' }} />
        </div>
      )}
    </>
  );
}

// ── Code block with syntax highlighting ──────────────────────────────────────
function RichCodeBlock({ language, code, isDark }) {
  const [copied, setCopied] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const lines = code.split('\n');
  const isLong = lines.length > 20;

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  if (language === 'mermaid') return <MermaidBlock code={code} />;

  const hlTheme = isDark ? oneDark : oneLight;

  return (
    <div className="md-code-block">
      <div className="md-code-header">
        <div className="md-code-lang-badge">{language || 'code'}</div>
        <div style={{ display: 'flex', gap: 6 }}>
          {isLong && (
            <button className="md-code-btn" onClick={() => setCollapsed(c => !c)}>
              <Icon d={collapsed ? ICONS.expand : ICONS.collapse} size={12} />
              {collapsed ? 'Expand' : 'Collapse'}
            </button>
          )}
          <button className="md-code-btn" onClick={handleCopy}>
            <Icon d={copied ? ICONS.check : ICONS.copy} size={12} />
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
      </div>
      {!collapsed && (
        <SyntaxHighlighter
          language={language || 'text'}
          style={hlTheme}
          showLineNumbers={lines.length > 3}
          wrapLines
          customStyle={{
            margin: 0,
            borderRadius: '0 0 10px 10px',
            fontSize: '12.5px',
            lineHeight: 1.55,
            background: isDark ? '#0d1117' : '#f6f8fa',
          }}
          lineNumberStyle={{ color: isDark ? '#484f58' : '#adb5bd', minWidth: '2.5em' }}
        >
          {code}
        </SyntaxHighlighter>
      )}
      {collapsed && (
        <div className="md-code-collapsed-hint">{lines.length} lines hidden — click Expand to show</div>
      )}
    </div>
  );
}

// ── Callout block ─────────────────────────────────────────────────────────────
function CalloutBlock({ type, children }) {
  const cfg = CALLOUT_CONFIG[type ? type.toUpperCase() : 'NOTE'] || CALLOUT_CONFIG.NOTE;
  return (
    <div className="md-callout" style={{
      '--callout-color': cfg.color,
      '--callout-bg': cfg.bg,
      '--callout-border': cfg.border,
    }}>
      <div className="md-callout-header">
        <Icon d={ICONS[cfg.icon] || ICONS.info} size={15} color={cfg.color} />
        <span className="md-callout-label" style={{ color: cfg.color }}>{cfg.label}</span>
      </div>
      <div className="md-callout-body">{children}</div>
    </div>
  );
}

// ── Medical field pill ────────────────────────────────────────────────────────
function MedField({ label, value, color }) {
  if (!value || !value.trim()) return null;
  return (
    <div className="md-med-field">
      <div className="md-med-field-label" style={{ color }}>{label}</div>
      <div className="md-med-field-value">
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[rehypeRaw, rehypeKatex]}
        >
          {value}
        </ReactMarkdown>
      </div>
    </div>
  );
}

// ── parseFields with multi-line support ───────────────────────────────────────
function parseFields(data) {
  const fields = {};
  const lines = data.split('\n');
  let currentKey = null;

  for (const line of lines) {
    if (!line.trim()) continue;
    const idx = line.indexOf(':');
    if (idx > 0) {
      const key = line.slice(0, idx).trim().toLowerCase();
      const val = line.slice(idx + 1).trim();
      // Reject multi-word keys that aren't field names (likely prose)
      if (key.split(' ').length <= 3) {
        currentKey = key;
        fields[currentKey] = val;
        continue;
      }
    }
    // Continuation line — append to current field
    if (currentKey && fields[currentKey] !== undefined) {
      fields[currentKey] += (fields[currentKey] ? '\n' : '') + line.trim();
    }
  }
  return fields;
}

// ── Disease Card ──────────────────────────────────────────────────────────────
function DiseaseCard({ data }) {
  const f = parseFields(data);
  return (
    <div className="md-medical-card md-disease-card">
      <div className="md-medical-card-header" style={{ borderColor: '#ef444430' }}>
        <Icon d={ICONS.scope} size={16} color="#ef4444" />
        <span style={{ color: '#ef4444', fontWeight: 700 }}>{f.disease || f.name || 'Disease'}</span>
      </div>
      <div className="md-medical-grid">
        <MedField label="Presentation"   value={f.presentation}    color="#f59e0b" />
        <MedField label="Diagnosis"      value={f.diagnosis}       color="#3b82f6" />
        <MedField label="Treatment"      value={f.treatment}       color="#10b981" />
        <MedField label="Complications"  value={f.complications}   color="#ef4444" />
        <MedField label="Mnemonic"       value={f.mnemonic}        color="#8b5cf6" />
        <MedField label="Notes"          value={f.notes}           color="#64748b" />
        <MedField label="Pathophysiology" value={f.pathophysiology} color="#f97316" />
        <MedField label="Epidemiology"   value={f.epidemiology}    color="#06b6d4" />
      </div>
    </div>
  );
}

// ── Drug Card ─────────────────────────────────────────────────────────────────
function DrugCard({ data }) {
  const f = parseFields(data);
  return (
    <div className="md-medical-card md-drug-card">
      <div className="md-medical-card-header" style={{ borderColor: '#8b5cf630' }}>
        <Icon d={ICONS.pill} size={16} color="#8b5cf6" />
        <span style={{ color: '#8b5cf6', fontWeight: 700 }}>{f.drug || f.name || 'Drug'}</span>
      </div>
      <div className="md-medical-grid">
        <MedField label="Class"             value={f.class}                              color="#8b5cf6" />
        <MedField label="MOA"               value={f.moa || f['mechanism of action']}    color="#3b82f6" />
        <MedField label="Side Effects"      value={f['side effects'] || f.se || f['adverse effects']} color="#f59e0b" />
        <MedField label="Contraindications" value={f.contraindications || f.contra}      color="#ef4444" />
        <MedField label="Dose"              value={f.dose || f.dosage}                   color="#10b981" />
        <MedField label="Indications"       value={f.indications || f.uses}              color="#06b6d4" />
        <MedField label="Notes"             value={f.notes}                              color="#64748b" />
      </div>
    </div>
  );
}

// ── OSCE Card ─────────────────────────────────────────────────────────────────
function OsceCard({ data }) {
  const f = parseFields(data);
  return (
    <div className="md-medical-card md-osce-card">
      <div className="md-medical-card-header" style={{ borderColor: '#06b6d430' }}>
        <Icon d={ICONS.brain} size={16} color="#06b6d4" />
        <span style={{ color: '#06b6d4', fontWeight: 700 }}>OSCE</span>
        {f.station && <span className="md-osce-station-name">{f.station}</span>}
      </div>
      <div className="md-medical-grid">
        <MedField label="Scenario"    value={f.scenario}   color="#06b6d4" />
        <MedField label="History"     value={f.history}    color="#3b82f6" />
        <MedField label="Examination" value={f.exam}       color="#10b981" />
        <MedField label="Findings"    value={f.findings}   color="#f59e0b" />
        <MedField label="Management"  value={f.management} color="#8b5cf6" />
        <MedField label="Marks"       value={f.marks}      color="#64748b" />
      </div>
    </div>
  );
}

// ── Mnemonic ──────────────────────────────────────────────────────────────────
function MnemonicBlock({ data }) {
  const f = parseFields(data);
  const lines = data.split('\n').map(s => s.trim()).filter(Boolean);

  // Extract letter-meaning pairs from lines like "A - Airway", "A: Airway", "A = Airway"
  const pairs = [];
  const letterLineRe = /^([A-Za-z0-9])\s*[:\-—=]\s*(.+)$/;

  const itemLines = lines.filter(l => {
    const lower = l.toLowerCase();
    return !lower.startsWith('acronym:') &&
           !lower.startsWith('letters:') &&
           !lower.startsWith('title:') &&
           !lower.startsWith('name:');
  });

  for (const line of itemLines) {
    const match = line.replace(/^[-*•]\s*/, '').match(letterLineRe);
    if (match) {
      pairs.push({ letter: match[1].toUpperCase(), meaning: match[2].trim() });
    }
  }

  // If pairs found, use them directly; otherwise fall back to letters+meanings fields
  if (pairs.length === 0 && f.letters) {
    const letters = f.letters.replace(/[^A-Za-z0-9]/g, '').split('');
    const meanings = (f.meanings || '').split(/[,\n]/).map(s => s.trim()).filter(Boolean);
    letters.forEach((letter, i) => pairs.push({ letter: letter.toUpperCase(), meaning: meanings[i] || '—' }));
  }

  return (
    <div className="md-mnemonic-block">
      <div className="md-mnemonic-header">{f.title || f.name || f.acronym || 'Mnemonic'}</div>
      {pairs.length > 0 ? (
        <div className="md-mnemonic-table">
          {pairs.map(({ letter, meaning }, i) => (
            <div key={i} className="md-mnemonic-row">
              <span className="md-mnemonic-letter">{letter}</span>
              <span className="md-mnemonic-meaning">{meaning}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="md-mnemonic-body">{data}</div>
      )}
    </div>
  );
}

// ── Clinical Vignette ─────────────────────────────────────────────────────────
function ClinicalBlock({ data }) {
  const f = parseFields(data);
  // Only use vignette field if explicitly provided — never dump raw data
  const vignette = f.vignette || f.scenario || f.presentation;
  return (
    <div className="md-clinical-card">
      <div className="md-clinical-header">
        <span>Clinical Vignette</span>
        {(f.case || f.title || f.name) && (
          <span className="md-clinical-case">{f.case || f.title || f.name}</span>
        )}
      </div>
      {vignette && <div className="md-clinical-vignette">{vignette}</div>}
      {(f.question || f.stem) && (
        <div className="md-clinical-question">{f.question || f.stem}</div>
      )}
      {(f.answer || f.diagnosis || f.management) && (
        <details className="md-clinical-answer">
          <summary>Reveal Answer</summary>
          <div style={{ marginTop: 8 }}>
            {f.answer || f.diagnosis || f.management}
          </div>
        </details>
      )}
    </div>
  );
}

// ── Differential Diagnosis ────────────────────────────────────────────────────
function DifferentialBlock({ data, isDark }) {
  const lines = data.split('\n').filter(Boolean);
  const f = parseFields(data);
  const contentLines = lines.filter(l => !l.match(/^(title|name|presentation):/i));
  let itemIdx = 0;
  const comps = buildComponents(isDark);

  return (
    <div className="md-differential-card">
      <div className="md-differential-header">
        <span>{f.title || f.name || 'Differential Diagnosis'}</span>
        {f.presentation && <span className="md-differential-pres">{f.presentation}</span>}
      </div>
      <div className="md-differential-content">
        {contentLines.map((line, i) => {
          const trimmed = line.trim();
          const hasBullet = /^([-*•]\s*|\d+\.\s+)/.test(trimmed);
          // Category: ends with colon, is bold-only, or is all-caps (and no bullet)
          const isCategory = !hasBullet && (
            trimmed.endsWith(':') ||
            trimmed.endsWith(':**') ||
            /^\*\*[^*]+\*\*$/.test(trimmed) ||
            /^[A-Z][A-Z\s\-/]+$/.test(trimmed)
          );

          if (isCategory) {
            const cleanCategory = trimmed.replace(/\*\*/g, '').replace(/:\s*$/, '');
            return (
              <div key={i} className="md-differential-category">
                {cleanCategory}
              </div>
            );
          } else {
            const cleanItem = trimmed.replace(/^([-*•]\s*|\d+\.\s+)/, '');
            const currentIdx = itemIdx++;
            const opacity = Math.max(0.15, 1 - currentIdx * 0.12);
            return (
              <div key={i} className="md-differential-item">
                <span className="md-differential-rank" style={{ opacity }}>
                  {currentIdx + 1}
                </span>
                <span style={{ fontSize: '13px', flex: 1 }}>
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[rehypeRaw, rehypeKatex]}
                    components={comps}
                  >
                    {cleanItem}
                  </ReactMarkdown>
                </span>
              </div>
            );
          }
        })}
      </div>
    </div>
  );
}

// ── Flashcard (3D flip) ───────────────────────────────────────────────────────
function FlashCard({ data }) {
  const [flipped, setFlipped] = useState(false);
  const [mastered, setMastered] = useState(false);
  const f = parseFields(data);
  const lines = data.split('\n').filter(Boolean);
  // Accept many field name variants
  const front = f.front || f.question || f.q || f['front side'] || lines[0] || '?';
  const back  = f.back  || f.answer  || f.a || f['back side']  || f.explanation || lines[1] || '...';
  return (
    <div className="md-flashcard-wrapper">
      <div
        className={'md-flashcard' + (flipped ? ' md-flashcard-flipped' : '') + (mastered ? ' md-flashcard-mastered' : '')}
        onClick={() => setFlipped(v => !v)}
      >
        <div className="md-flashcard-inner">
          <div className="md-flashcard-front">
            <div className="md-flashcard-label">QUESTION</div>
            <div className="md-flashcard-text">{front}</div>
            <div className="md-flashcard-hint">Click to reveal answer</div>
          </div>
          <div className="md-flashcard-back">
            <div className="md-flashcard-label">ANSWER</div>
            <div className="md-flashcard-text">{back}</div>
          </div>
        </div>
      </div>
      <div className="md-flashcard-controls">
        <button
          className={'md-flashcard-btn' + (mastered ? ' md-flashcard-btn-mastered' : '')}
          onClick={e => { e.stopPropagation(); setMastered(m => !m); setFlipped(false); }}
        >
          <Icon d={ICONS.check} size={13} />
          {mastered ? 'Mastered' : 'Mark mastered'}
        </button>
        <button className="md-flashcard-btn" onClick={e => { e.stopPropagation(); setFlipped(false); }}>
          <Icon d={ICONS.flip} size={13} />
          Reset
        </button>
      </div>
    </div>
  );
}

// ── Custom block dispatcher ───────────────────────────────────────────────────
function CustomBlock({ type, body, isDark }) {
  switch (type) {
    case 'disease':      return <DiseaseCard data={body} />;
    case 'drug':         return <DrugCard data={body} />;
    case 'osce':         return <OsceCard data={body} />;
    case 'mnemonic':     return <MnemonicBlock data={body} />;
    case 'flashcard':    return <FlashCard data={body} />;
    case 'clinical':     return <ClinicalBlock data={body} />;
    case 'differential': return <DifferentialBlock data={body} isDark={isDark} />;
    default:             return <pre style={{ fontSize: 12 }}>{body}</pre>;
  }
}

// ── Callout detector from blockquote AST node ─────────────────────────────────
// Recursively walk AST to find [!TYPE] in any child node
function parseCalloutType(node) {
  try {
    const walk = (n) => {
      if (n?.value && typeof n.value === 'string') {
        const m = n.value.match(/^\[!([A-Za-z]+)\]/);
        if (m) return m[1].toUpperCase();
      }
      if (n?.children) {
        for (const child of n.children) {
          const result = walk(child);
          if (result) return result;
        }
      }
      return null;
    };
    return walk(node);
  } catch { return null; }
}

// ── Callout prefix cleaner ───────────────────────────────────────────────────
function removeCalloutPrefix(children) {
  if (!children) return children;
  const arr = React.Children.toArray(children);
  if (arr.length === 0) return children;

  const firstChild = arr[0];
  if (typeof firstChild === 'string') {
    const cleaned = firstChild.replace(/^\[![A-Za-z]+\]\s*/i, '');
    if (cleaned.trim() === '') { arr.shift(); return arr; }
    arr[0] = cleaned;
    return arr;
  }

  if (React.isValidElement(firstChild)) {
    const childProps = firstChild.props;
    if (childProps?.children !== undefined) {
      const cleanedSubChildren = removeCalloutPrefix(childProps.children);
      const hasContent = React.Children.toArray(cleanedSubChildren).some(c =>
        typeof c === 'string' ? c.trim().length > 0 : true
      );
      if (!hasContent) { arr.shift(); return arr; }
      arr[0] = React.cloneElement(firstChild, { children: cleanedSubChildren });
      return arr;
    }
  }
  return children;
}

// ── Build react-markdown components map ───────────────────────────────────────
function buildComponents(isDark) {
  return {
    // Fix: don't use deprecated `inline` prop — detect by presence of language class
    code({ node, className: cls, children }) {
      const lang = /language-(\w+)/.exec(cls || '')?.[1] || '';
      // Guard: children can be undefined in react-markdown v10 edge cases;
      // String(undefined) === "undefined" which renders as literal text.
      const code = String(children ?? '').replace(/\n$/, '');
      if (!code) return null;
      // Block code has a language class or contains newlines; inline code has neither
      const isBlock = !!cls || code.includes('\n');
      if (!isBlock) return <code className="md-inline-code">{code}</code>;
      return <RichCodeBlock language={lang} code={code} isDark={isDark} />;
    },
    blockquote({ node, children }) {
      // Callouts are pre-processed into inline HTML divs in healContent(),
      // so any remaining blockquote is a genuine quote — render it plainly.
      // But keep a fallback in case the LLM used a non-standard callout format
      // that slipped through pre-processing.
      const type = parseCalloutType(node);
      if (type && CALLOUT_CONFIG[type]) {
        // Strip the [!TYPE] marker text from the first child before rendering
        const cfg = CALLOUT_CONFIG[type];
        return (
          <div className="md-callout" style={{
            '--callout-color': cfg.color, '--callout-bg': cfg.bg, '--callout-border': cfg.border,
          }}>
            <div className="md-callout-header">
              <Icon d={ICONS[cfg.icon] || ICONS.info} size={15} color={cfg.color} />
              <span className="md-callout-label" style={{ color: cfg.color }}>{cfg.label}</span>
            </div>
            <div className="md-callout-body">
              {React.Children.toArray(children).map((child, i) => {
                if (i === 0 && React.isValidElement(child)) {
                  // Strip the [!TYPE] text from inside the first <p>
                  const inner = React.Children.toArray(child.props?.children || []);
                  const cleaned = inner.map((c, j) =>
                    j === 0 && typeof c === 'string'
                      ? c.replace(/^\[![A-Za-z]+\]\s*/, '')
                      : c
                  ).filter(c => typeof c !== 'string' || c.trim());
                  return React.cloneElement(child, { key: i, children: cleaned });
                }
                return child;
              })}
            </div>
          </div>
        );
      }
      return <blockquote className="md-blockquote">{children}</blockquote>;
    },
    table:  ({ children })       => <div className="md-table-wrapper"><table className="md-table">{children}</table></div>,
    thead:  ({ children })       => <thead className="md-thead">{children}</thead>,
    th:     ({ children })       => <th className="md-th">{children}</th>,
    td:     ({ children })       => <td className="md-td">{children}</td>,
    tr:     ({ children })       => <tr className="md-tr">{children}</tr>,
    h1:     ({ children })       => <h1 className="md-h1">{children}</h1>,
    h2:     ({ children })       => <h2 className="md-h2">{children}</h2>,
    h3:     ({ children })       => <h3 className="md-h3">{children}</h3>,
    h4:     ({ children })       => <h4 className="md-h4">{children}</h4>,
    h5:     ({ children })       => <h5 className="md-h5">{children}</h5>,
    h6:     ({ children })       => <h6 className="md-h6">{children}</h6>,
    p:      ({ children })       => <p className="md-p">{children}</p>,
    a: ({ children, href }) => {
      const handleClick = (e) => {
        const isTauri = typeof window !== 'undefined' &&
          (window.__TAURI__ !== undefined || window.__TAURI_INTERNALS__ !== undefined);
        if (isTauri && href && (href.startsWith('http://') || href.startsWith('https://'))) {
          e.preventDefault();
          fetch('http://localhost:8000/api/utils/open-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: href })
          }).catch(console.error);
        }
      };
      return (
        <a className="md-link" href={href} onClick={handleClick}
           target="_blank" rel="noopener noreferrer">{children}</a>
      );
    },
    ul:     ({ children })       => <ul className="md-ul">{children}</ul>,
    ol:     ({ children })       => <ol className="md-ol">{children}</ol>,
    li:     ({ children, checked }) => {
      if (checked !== null && checked !== undefined) {
        return (
          <li className="md-task-item">
            <span className={'md-task-checkbox' + (checked ? ' md-task-checked' : '')}>
              {checked && <Icon d={ICONS.check} size={10} color="white" />}
            </span>
            <span className={checked ? 'md-task-done' : ''}>{children}</span>
          </li>
        );
      }
      return <li className="md-li">{children}</li>;
    },
    hr:     ()                   => <hr className="md-hr" />,
    strong: ({ children })       => <strong className="md-strong">{children}</strong>,
    em:     ({ children })       => <em className="md-em">{children}</em>,
    img:    ({ src, alt })       => (
      <div className="md-img-wrapper">
        <img className="md-img" src={src} alt={alt} loading="lazy" />
        {alt && <div className="md-img-caption">{alt}</div>}
      </div>
    ),
  };
}

export default function MarkdownViewer({ content = '', isDark = false, className = '' }) {
  // Run auto-heal engine; memoized so it only re-runs when content changes
  const { text: healed, repairs } = useMemo(
    () => healContentWithReport(content),
    [content]
  );

  if (!content) return null;

  // Strip emojis except standard math/layout symbols
  const cleanContent = healed.replace(
    /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2700}-\u{27BF}\u{1F900}-\u{1F9FF}\u{1F1E6}-\u{1F1FF}\u{2600}-\u{26FF}\u{2300}-\u{23FF}\u{2b50}\u{2b06}]/gu,
    ''
  );

  // Split content around custom blocks
  const segments = [];
  let lastIndex = 0;
  const re = new RegExp(
    '```\\s*(' + CUSTOM_TYPES.join('|') + ')\\s*\\n?((?:(?!```)[\\s\\S])*?)```',
    'gi'
  );
  let match;
  while ((match = re.exec(cleanContent)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ kind: 'md', text: cleanContent.slice(lastIndex, match.index) });
    }
    segments.push({ kind: 'custom', type: match[1].toLowerCase(), body: match[2].trim() });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < cleanContent.length) {
    segments.push({ kind: 'md', text: cleanContent.slice(lastIndex) });
  }

  // If nothing split (no custom blocks), treat whole thing as markdown
  if (segments.length === 0) {
    segments.push({ kind: 'md', text: cleanContent });
  }

  const comps = buildComponents(isDark);

  return (
    <div className={'md-viewer ' + (isDark ? 'md-viewer-dark' : 'md-viewer-light') + ' ' + className}>
      <HealReport repairs={repairs} />
      {segments.map((seg, i) => {
        if (seg.kind === 'custom') {
          return <CustomBlock key={i} type={seg.type} body={seg.body} isDark={isDark} />;
        }
        if (!seg.text?.trim()) return null;
        return (
          <div key={i} className="md-content-wrapper">
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[rehypeRaw, rehypeKatex]}
              components={comps}
            >
              {seg.text}
            </ReactMarkdown>
          </div>
        );
      })}
    </div>
  );
}
