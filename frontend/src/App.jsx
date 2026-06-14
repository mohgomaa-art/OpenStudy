import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { WebviewWindow } from '@tauri-apps/api/webviewWindow';
import { getCurrentWindow } from '@tauri-apps/api/window';
import {
  Search, Menu, X, Plus, MessageSquare, ChevronRight, Settings,
  Command, Cpu, Zap, Maximize2, Minimize2, MoreHorizontal,
  Paperclip, Send, Bot, User, Code, FileText, Link2,
  Activity, ArrowRight, Eye, Layout, SplitSquareHorizontal,
  TerminalSquare, Network, BrainCircuit, Fingerprint,
  ChevronDown, Hexagon, Database, Globe, Check, Copy, Trash2,
  Minus, Square, FolderOpen, RefreshCw, BookOpen, Clock, Target, Award,
  Layers, ClipboardList, Type, GitFork, Workflow, Calendar, HeartPulse,
  ListOrdered, Table, Grid, CheckSquare, Swords, Stethoscope, Move, Folder, File, ExternalLink,
  Mail, Share2, AtSign, Info
} from 'lucide-react';
import MarkdownViewer from './MarkdownViewer';

const isTauri = typeof window !== 'undefined' && (window.__TAURI__ !== undefined || window.__TAURI_INTERNALS__ !== undefined);

const API = 'http://localhost:8000';
const uid = () => Math.random().toString(36).slice(2, 9);

const THEME_META = {
  'apple-minimal': { name: 'Vision Pro Matte', swatch: '#e5e5ea', font: 'font-sans tracking-tight antialiased', isLight: true },
  'midnight-pro': { name: 'Midnight Pro', swatch: '#121212', font: 'font-sans tracking-tight antialiased', isLight: false },
  'medical-pro': { name: 'Academic Research', swatch: '#ffffff', font: 'font-serif tracking-tight', isLight: true },
  'exec-command': { name: 'Executive Console', swatch: '#0a0d14', font: 'font-mono tracking-tight', isLight: false }
};

const TEXT_SIZE_MAP = {
  small: '13px',
  medium: '15px',
  large: '18px',
  xlarge: '21px'
};

const VISUAL_CATALOG = [
  { key: 'mind_map',              label: 'Mind Map',       emoji: '🧠', category: 'study',   desc: 'Radial concept branches' },
  { key: 'flashcard',             label: 'Flashcards',     emoji: '🃏', category: 'study',   desc: '3-D flip study cards' },
  { key: 'summary_sheet',         label: 'Summary Sheet',  emoji: '📋', category: 'study',   desc: 'High-yield cheat sheet' },
  { key: 'mnemonic_card',         label: 'Mnemonic',       emoji: '🔤', category: 'study',   desc: 'Acronym memory aid' },
  { key: 'concept_tree',          label: 'Concept Tree',   emoji: '🌳', category: 'study',   desc: 'Hierarchical tree' },
  { key: 'flowchart',             label: 'Flowchart',      emoji: '🔀', category: 'process', desc: 'Clinical pathway' },
  { key: 'cycle_diagram',         label: 'Cycle Diagram',  emoji: '🔄', category: 'process', desc: 'Circular process loop' },
  { key: 'timeline',              label: 'Timeline',       emoji: '📅', category: 'process', desc: 'Chronological events' },
  { key: 'pathophysiology_flow',  label: 'Patho Flow',     emoji: '🩺', category: 'process', desc: 'Disease cascade' },
  { key: 'sequence_builder',      label: 'Sequence',       emoji: '📶', category: 'process', desc: 'Step ordering game' },
  { key: 'comparison_table',      label: 'Compare Table',  emoji: '📊', category: 'compare', desc: 'Side-by-side matrix' },
  { key: 'ddx_matrix',            label: 'DDx Matrix',     emoji: '🔬', category: 'compare', desc: 'Differential diagnosis' },
  { key: 'anatomy_cross_section', label: 'Anatomy',        emoji: '🫀', category: 'compare', desc: 'Cross-section explorer' },
  { key: 'mcq_single_best',       label: 'MCQ Quiz',       emoji: '✅', category: 'quiz',    desc: 'Multiple choice test' },
  { key: 'true_false_streak',     label: 'T/F Streak',     emoji: '⚡', category: 'quiz',    desc: 'Speed fact check' },
  { key: 'boss_battle',           label: 'Boss Battle',    emoji: '👾', category: 'quiz',    desc: 'RPG quiz fight' },
  { key: 'clinical_vignette',     label: 'Case Study',     emoji: '🏥', category: 'quiz',    desc: 'Clinical reasoning' },
  { key: 'wordle_game',           label: 'Med Wordle',     emoji: '🔠', category: 'quiz',    desc: 'Term guessing game' },
  { key: 'drag_drop',             label: 'Drag & Drop',    emoji: '🎯', category: 'quiz',    desc: 'Category matching' },
];

const CAT_META = {
  study:   { label: 'Study',   accent: '#6366f1' },
  process: { label: 'Process', accent: '#10b981' },
  compare: { label: 'Compare', accent: '#f59e0b' },
  quiz:    { label: 'Quiz',    accent: '#ef4444' },
};

const VISUAL_ICONS = {
  mind_map:              BrainCircuit,
  flashcard:             Layers,
  summary_sheet:         ClipboardList,
  mnemonic_card:         Type,
  concept_tree:          GitFork,
  flowchart:             Workflow,
  cycle_diagram:         RefreshCw,
  timeline:              Calendar,
  pathophysiology_flow:  HeartPulse,
  sequence_builder:      ListOrdered,
  comparison_table:      Table,
  ddx_matrix:            Grid,
  anatomy_cross_section: Eye,
  mcq_single_best:       CheckSquare,
  true_false_streak:     Zap,
  boss_battle:           Swords,
  clinical_vignette:     Stethoscope,
  wordle_game:           Grid,
  drag_drop:             Move,
};

// Helper: detect Arabic characters for RTL direction
const containsArabic = (s) => s && /[\u0600-\u06FF]/.test(s);

const STATIC_THEME = {
  bgMain: 't-bg-main',
  bgSidebar: 't-bg-sidebar',
  surface: 't-surface',
  surfaceHover: 'hover-t-surface',
  border: 't-border',
  textMain: 't-text-main',
  textMuted: 't-text-muted',
  accentMain: 't-accent-main',
  accentBg: 't-accent-bg',
  userBubble: 't-user-bubble t-border',
  glass: 't-glass',
  shadow: 't-shadow',
  shadowInner: 't-shadow-inner',
  textMainHover: 'hover-t-text-main',
  textMutedHover: 'hover-t-text-muted',
  placeholderMuted: 'placeholder-t-text-muted',
};

const IconButton = ({ icon: Icon, onClick, className = '', title, t, disabled }) => (
  <button 
    onClick={onClick}
    title={title}
    disabled={disabled}
    className={`p-2 rounded-lg transition-all duration-200 ${t.textMuted} ${t.textMainHover} ${t.surfaceHover} disabled:opacity-50 cursor-pointer ${className}`}
  >
    <Icon size={18} strokeWidth={2} />
  </button>
);

const CodeBlock = ({ code, t }) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(code.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`my-6 rounded-xl overflow-hidden border ${t.border} bg-[#0d0d0d] font-mono text-sm shadow-sm`}>
      <div className={`flex items-center justify-between px-4 py-2 border-b border-neutral-800 bg-[#141414]`}>
        <div className="flex items-center gap-2">
          <Code size={14} className="text-neutral-400" />
          <span className="text-xs text-neutral-300 font-medium">{code.title || code.language}</span>
        </div>
        <button onClick={handleCopy} className="text-neutral-500 hover:text-neutral-300 transition-colors">
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </button>
      </div>
      <div className="p-4 overflow-x-auto text-neutral-300">
        <pre className="!m-0 !p-0 leading-relaxed"><code>{code.content}</code></pre>
      </div>
    </div>
  );
};

const CitationBlock = ({ citation, t }) => (
  <div className={`my-4 flex flex-wrap gap-2`}>
    {citation.sources.map((src, idx) => (
      <div key={idx} className={`group flex items-center gap-2 px-3 py-1.5 rounded-md border ${t.border} ${t.surface} ${t.surfaceHover} cursor-pointer transition-all hover:border-current`}>
        <span className={`text-[10px] font-bold ${t.textMuted}`}>{idx + 1}</span>
        <span className={`text-xs font-medium ${t.textMain}`}>{src.title}</span>
      </div>
    ))}
  </div>
);

const PROVIDER_LABELS = {
  gemini: 'Gemini', openai: 'OpenAI', anthropic: 'Anthropic',
  groq: 'Groq', openrouter: 'OpenRouter', ollama: 'Ollama',
};

const RateLimitCard = ({ data, t, onRetry, onOpenSettings, userText }) => {
  const initial = Math.max(0, Math.ceil(data?.retry_in_seconds || 0));
  const [remaining, setRemaining] = useState(initial);

  useEffect(() => {
    if (remaining <= 0) return;
    const id = setInterval(() => setRemaining(r => Math.max(0, r - 1)), 1000);
    return () => clearInterval(id);
  }, [remaining]);

  const totalKeys = data?.total_keys || 0;
  const availableKeys = data?.available_keys || 0;
  const keys = data?.rotator?.keys || [];
  const canRetryNow = remaining <= 0 || availableKeys > 0;
  const isNoKey = totalKeys === 0;
  const provider = data?.provider || 'gemini';
  const isGemini = provider === 'gemini';
  const providerLabel = PROVIDER_LABELS[provider] || 'API';

  return (
    <div className={`relative mt-2 rounded-2xl border ${t.border} ${t.surface} overflow-hidden shadow-sm`}>
      <div className={`px-5 py-3.5 border-b ${t.border} flex items-center gap-3`}>
        <div className="w-8 h-8 rounded-xl bg-amber-500/15 flex items-center justify-center shrink-0">
          <Clock size={16} className="text-amber-500" />
        </div>
        <div className="flex-1 min-w-0">
          <div className={`text-[13px] font-bold ${t.textMain} leading-tight`}>
            {isNoKey ? `No ${providerLabel} key configured` : 'Rate limit reached'}
          </div>
          <div className={`text-[11px] ${t.textMuted} mt-0.5`}>
            {isNoKey
              ? `Add a ${providerLabel} API key in settings to start chatting.`
              : isGemini
                ? `${availableKeys} of ${totalKeys} keys available — ${totalKeys - availableKeys} cooling down.`
                : 'Your API key may be invalid or over quota.'}
          </div>
        </div>
      </div>

      {!isNoKey && (
        <div className="px-5 py-4">
          {isGemini ? (
            <>
              {remaining > 0 ? (
                <div className="flex items-baseline gap-3">
                  <div className={`text-3xl font-bold ${t.textMain} tabular-nums tracking-tight`}>{remaining}s</div>
                  <div className={`text-[11px] ${t.textMuted}`}>until the next key is free</div>
                </div>
              ) : (
                <div className={`text-[12.5px] ${t.textMain}`}>A key should be available now — hit retry to continue.</div>
              )}
              {keys.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {keys.map((k, idx) => {
                    const cooling = (k.cooldown_remaining || 0) > 0;
                    return (
                      <div
                        key={idx}
                        className={`flex items-center gap-1.5 px-2 py-0.5 rounded-md border ${t.border} text-[10px] font-mono ${cooling ? 'opacity-60' : ''}`}
                      >
                        <div className={`w-1.5 h-1.5 rounded-full ${cooling ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                        <span className={t.textMuted}>{k.masked}</span>
                        {cooling && <span className={t.textMuted}>{Math.ceil(k.cooldown_remaining)}s</span>}
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          ) : (
            <div className={`text-[12.5px] ${t.textMain}`}>Check your {providerLabel} API key — it may be invalid or over quota. Try again or update your key in settings.</div>
          )}
        </div>
      )}

      <div className={`px-5 py-3 border-t ${t.border} flex items-center gap-2`}>
        {!isNoKey && (
          <button
            onClick={() => { if (canRetryNow && userText && onRetry) onRetry(userText); }}
            disabled={!canRetryNow || !userText}
            className={`flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-bold transition-colors ${canRetryNow ? 'bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer' : `${t.surface} border ${t.border} ${t.textMuted} cursor-not-allowed`}`}
          >
            <RefreshCw size={12} />
            {canRetryNow ? 'Retry now' : `Wait ${remaining}s`}
          </button>
        )}
        <button
          onClick={() => onOpenSettings && onOpenSettings()}
          className={`${isNoKey ? 'flex-1 bg-indigo-600 hover:bg-indigo-500 text-white' : `${t.surface} border ${t.border} ${t.textMain} ${t.surfaceHover}`} inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-semibold transition-colors cursor-pointer`}
        >
          <Plus size={12} />
          {isNoKey ? 'Add a key' : 'Add another key'}
        </button>
      </div>
    </div>
  );
};

const ToolTimeline = ({ timeline, t }) => (
  <div className={`mb-4 pl-4 border-l-2 ${t.border} space-y-3`}>
    {timeline.map((step, idx) => (
      <div key={idx} className="flex items-center gap-3">
        <div className={`w-1.5 h-1.5 rounded-full ${step.status === 'done' ? 'bg-neutral-400' : 'bg-blue-500 animate-pulse'}`} />
        <span className={`text-xs font-medium ${t.textMain}`}>{step.step}</span>
        <span className={`text-[10px] ${t.textMuted}`}>{step.time}</span>
      </div>
    ))}
  </div>
);

const MessageContent = React.memo(({ content, t }) => {
  const parsed = useMemo(() => {
    return content.split('\n').map((line, i) => {
      const dir = containsArabic(line) ? 'rtl' : 'ltr';
      if (line.startsWith('###')) return <h3 key={i} dir={dir} className={`text-sm font-bold mt-5 mb-2 uppercase tracking-wider ${t.textMain}`}>{line.replace('###', '')}</h3>;
      if (line.startsWith('1.') || line.startsWith('2.') || line.startsWith('3.')) return <p key={i} dir={dir} className="ml-4 mb-2 flex text-[14px]"><span className="mr-3 text-neutral-400">•</span>{line.substring(3)}</p>;
      if (line.includes('`')) {
        const parts = line.split('`');
        return (
          <p key={i} dir={dir} className="mb-4 text-[15px] leading-relaxed">
            {parts.map((part, j) => j % 2 === 1 ? <code key={j} className={`px-1.5 py-0.5 rounded-md ${t.surface} border ${t.border} text-[13px] font-mono`}>{part}</code> : part)}
          </p>
        );
      }
      return <p key={i} dir={dir} className="mb-4 text-[15px] leading-relaxed">{line}</p>;
    });
  }, [content, t]);

  return <div className={`${t.textMain}`}>{parsed}</div>;
});

const VisualFrame = ({ filename, title, t, activeTheme }) => {
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const [iframeHeight, setIframeHeight] = useState(480);
  const iframeRef = useRef(null);
  const src = `${API}/api/visual/view/${filename}`;

  useEffect(() => {
    setLoading(true);
    setMissing(false);
    setIframeHeight(480);
    let cancelled = false;
    fetch(src, { method: 'HEAD' })
      .then(r => { if (!cancelled) { r.ok ? setLoading(false) : (setMissing(true), setLoading(false)); } })
      .catch(() => { if (!cancelled) { setMissing(true); setLoading(false); } });
    return () => { cancelled = true; };
  }, [src]);

  // Accept height reports, but only allow growing — never shrink, no runaway loop
  useEffect(() => {
    const handler = (e) => {
      if (!e.data || typeof e.data.__visualHeight !== 'number') return;
      if (iframeRef.current && e.source !== iframeRef.current.contentWindow) return;
      const reported = e.data.__visualHeight;
      // Cap at 4000px and only grow (never shrink), breaks feedback loops
      setIframeHeight(prev => Math.min(4000, Math.max(prev, reported + 24)));
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  // Push theme change into the iframe
  useEffect(() => {
    if (!iframeRef.current || loading || missing) return;
    const themeMap = {
      'midnight-pro': 'arcane',
      'exec-command': 'nightshift',
      'apple-minimal': 'clinical',
      'medical-pro': 'clinical',
    };
    try {
      iframeRef.current.contentWindow?.postMessage(
        { __setTheme: themeMap[activeTheme] || 'clinical' }, '*'
      );
    } catch {}
  }, [activeTheme, loading, missing]);

  if (loading) return (
    <div className={`w-full py-12 text-center text-xs ${t.textMuted} flex items-center justify-center gap-2.5`}>
      <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      Rendering visual...
    </div>
  );
  if (missing) return (
    <div className={`w-full py-8 text-center text-xs ${t.textMuted}`}>Visual no longer available.</div>
  );
  return (
    <iframe
      ref={iframeRef}
      src={src}
      className="w-full border-0 block"
      style={{ height: iframeHeight, transition: 'height 0.25s ease' }}
      title={title}
      sandbox="allow-scripts allow-same-origin"
    />
  );
};

const MessageArea = ({ messages, t, activeTheme = 'apple-minimal', onRetry, onOpenSettings, backendOk = true }) => {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 no-scrollbar">
        <div className="max-w-xl w-full text-center space-y-6 animate-message">
          <div className="flex justify-center mb-2">
            <div className={`flex items-center justify-center w-14 h-14 rounded-2xl border ${t.border} ${t.surface} ${t.textMain} shadow-md`}>
              <svg viewBox="8 8 84 84" width="36" height="36" fill="none" aria-hidden="true">
                <g stroke="currentColor" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18,32 L46,45 L46,80 L18,67 Z" />
                  <path d="M82,32 L54,45 L54,80 L82,67 Z" />
                  <path d="M50,85 L50,25 L40,35 M50,25 L60,35" strokeWidth="3.8" />
                  <circle cx="50" cy="15" r="2.6" fill="currentColor" stroke="none" />
                  <circle cx="28" cy="24" r="1.6" fill="currentColor" stroke="none" />
                  <circle cx="72" cy="24" r="1.6" fill="currentColor" stroke="none" />
                </g>
              </svg>
            </div>
          </div>
          <div className="space-y-2">
            <h1 className={`text-2xl font-bold tracking-tight ${t.textMain}`}>OpenStudy</h1>
            <p className={`text-sm ${t.textMuted} max-w-md mx-auto leading-relaxed`}>
              Your local AI study companion. Ask questions, upload documents, and generate interactive learning visuals.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto no-scrollbar scroll-smooth py-8" style={{ contain: 'paint' }}>
      <div className="max-w-4xl mx-auto px-4 md:px-8 space-y-10 pb-32">
        {messages.map((msg, idx) => (
          <div key={msg.id} className="space-y-4 animate-message" style={{ animationDelay: `${idx * 0.05}s` }}>
            {/* Main message row (avatar + bubble) */}
            <div className={`flex gap-6 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className="flex-shrink-0 mt-1">
                  <div className={`w-8 h-8 rounded-full border ${t.border} ${t.surface} flex items-center justify-center shadow-sm`}>
                    <Bot size={16} className={t.textMain} />
                  </div>
                </div>
              )}

              <div
                dir={msg.role === 'user' ? (containsArabic(msg.components?.[0]?.content) ? 'rtl' : 'ltr') : undefined}
                className={`max-w-[85%] ${msg.role === 'user' ? `${t.userBubble} px-5 py-3.5 rounded-2xl border` : ''}`}
              >
                {msg.isThinking && (
                  <div className={`flex items-center gap-3 ${t.textMuted}`}>
                    <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    <span className="text-sm font-medium">Synthesizing...</span>
                  </div>
                )}
                
                {msg.timeline && <ToolTimeline timeline={msg.timeline} t={t} />}

                {msg.rateLimit ? (
                  <RateLimitCard
                    data={msg.rateLimit}
                    t={t}
                    onRetry={onRetry}
                    onOpenSettings={onOpenSettings}
                    userText={(() => {
                      for (let i = idx - 1; i >= 0; i--) {
                        if (messages[i]?.role === 'user') return messages[i].components?.[0]?.content || '';
                      }
                      return '';
                    })()}
                  />
                ) : msg.components?.map((comp, c_idx) => {
                  if (comp.type === 'text') {
                    return (
                      <div key={c_idx} className="relative mt-2">
                         <MarkdownViewer content={comp.content} isDark={!THEME_META[activeTheme]?.isLight} />
                         {(!comp.content || comp.content.length === 0) && <div className="text-red-500">Empty Content</div>}
                      </div>
                    );
                  }
                  if (comp.type === 'citation') return <CitationBlock key={c_idx} citation={comp} t={t} />;
                  if (comp.type === 'code') return <CodeBlock key={c_idx} code={comp} t={t} />;
                  return null;
                })}
              </div>
            </div>

            {/* Visuals */}
            {(msg.visuals?.length > 0 ? msg.visuals : msg.visual ? [msg.visual] : []).map((vis, visIdx) => (
              <div
                key={vis.filename || visIdx}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData('text/plain', JSON.stringify({
                    title: vis.title,
                    filename: vis.filename,
                    type: 'visual'
                  }));
                }}
                className={`rounded-xl border ${t.border} ${t.surface} shadow-sm mt-4 cursor-grab active:cursor-grabbing transition-shadow hover:shadow-md overflow-hidden`}
              >
                <div className={`flex items-center justify-between px-4 py-2 border-b ${t.border} bg-neutral-500/5`}>
                  <div className="flex items-center gap-2">
                    <Network size={14} className={t.textMain} />
                    <span className={`text-xs font-semibold ${t.textMain}`}>{vis.title}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${t.surfaceHover} border ${t.border} ${t.textMuted} font-mono`}>{vis.template}</span>
                  </div>
                  <button
                    onClick={() => {
                      if (isTauri) {
                        invoke('open_visualizer', { filePath: vis.filename }).catch(console.error);
                      } else {
                        window.open(`${API}/api/visual/view/${vis.filename}`, '_blank');
                      }
                    }}
                    title="Open visual in a separate window"
                    className={`text-xs ${t.textMain} hover:underline font-medium cursor-pointer flex items-center gap-1`}
                  >
                    Open full <ExternalLink size={11} />
                  </button>
                </div>
                <VisualFrame filename={vis.filename} title={vis.title} t={t} activeTheme={activeTheme} />
              </div>
            ))}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

const ChatInput = ({ t, onSend, disabled, sessionId }) => {
  const [text, setText] = useState('');
  const [references, setReferences] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedVisuals, setSelectedVisuals] = useState([]);
  const [textDir, setTextDir] = useState('ltr');
  const [attaching, setAttaching] = useState(false);
  const pickerRef = useRef(null);
  const fileInputRef = useRef(null);

  const handleAddContext = () => {
    if (disabled || attaching) return;
    fileInputRef.current?.click();
  };

  const handleAttachFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    const imageExts = ['png', 'jpg', 'jpeg', 'tiff', 'gif', 'webp', 'bmp'];
    if (imageExts.includes(ext)) {
      alert('Image files cannot be used as chat context (no text to extract). Please upload a PDF, DOCX, PPTX, or TXT file.');
      return;
    }
    setAttaching(true);
    try {
      const fd = new FormData();
      fd.append('files', file);
      if (sessionId) fd.append('session_id', sessionId);
      const res = await fetch(`${API}/api/documents/upload`, { method: 'POST', body: fd });
      if (res.ok) {
        let storedName = file.name;
        try {
          const data = await res.json();
          storedName = data.files?.[0]?.filename || data.saved_files?.[0] || file.name;
        } catch {}
        setReferences(prev => prev.some(r => r.filename === storedName)
          ? prev
          : [...prev, { type: 'document', filename: storedName, title: file.name }]);
      }
    } catch {}
    finally { setAttaching(false); }
  };

  // Close picker on outside click
  useEffect(() => {
    if (!pickerOpen) return;
    const handler = (e) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) setPickerOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [pickerOpen]);

  const handleInput = (e) => {
    const val = e.target.value;
    setText(val);
    setTextDir(containsArabic(val) ? 'rtl' : 'ltr');
    e.target.style.height = '44px';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
  };

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = () => setIsDragging(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    try {
      const data = JSON.parse(e.dataTransfer.getData('text/plain'));
      if (data && (data.type === 'visual' || data.type === 'document')) {
        if (!references.some(r => r.filename === data.filename)) setReferences(prev => [...prev, data]);
      }
    } catch {}
  };

  const removeReference = (idx) => setReferences(references.filter((_, i) => i !== idx));

  const submit = () => {
    if (disabled || !text.trim()) return;
    let finalQuery = text;
    if (references.length > 0) {
      const refList = references.map(r => `[${r.title}](${r.filename})`).join(', ');
      finalQuery = `Referencing Context: ${refList}\n\n${text}`;
    }
    onSend(finalQuery, selectedVisuals.map(v => v.key));
    setText('');
    setReferences([]);
    setSelectedVisuals([]);
    const el = document.getElementById('chat-input-textarea');
    if (el) el.style.height = '44px';
  };

  // Group by category
  const grouped = VISUAL_CATALOG.reduce((acc, v) => {
    (acc[v.category] = acc[v.category] || []).push(v);
    return acc;
  }, {});

  const toggleVisual = (v) => {
    setSelectedVisuals(prev =>
      prev.some(x => x.key === v.key) ? prev.filter(x => x.key !== v.key) : [...prev, v]
    );
  };

  return (
    <div className="absolute bottom-0 left-0 right-0 p-6 z-20 pointer-events-none flex justify-center">
      <div className="w-full max-w-5xl pointer-events-auto" ref={pickerRef}>

        {/* ── Visual Type Picker Popup ── */}
        {pickerOpen && (
          <div
            className={`mb-3 rounded-2xl border ${t.border} shadow-2xl overflow-hidden ${t.bgSidebar} ${t.glass}`}
          >
            {/* Popup header */}
            <div className={`flex items-center justify-between px-5 py-3 border-b ${t.border}`}>
              <div className="flex items-center gap-2">
                <span className={`text-[11px] font-bold uppercase tracking-widest ${t.textMuted}`}>Generate Visuals</span>
                {selectedVisuals.length > 0 && (
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                    {selectedVisuals.length} selected
                  </span>
                )}
              </div>
              <button
                onClick={() => { setSelectedVisuals([]); setPickerOpen(false); }}
                className={`text-[10px] font-bold ${t.textMuted} ${t.textMainHover} transition-colors px-2.5 py-1 rounded-lg border ${t.border} cursor-pointer`}
              >
                Clear All
              </button>
            </div>

            {/* Category groups */}
            <div className="p-4 space-y-4">
              {Object.entries(grouped).map(([cat, visuals]) => {
                const meta = CAT_META[cat];
                return (
                  <div key={cat}>
                    <div className="text-[10px] font-bold uppercase tracking-widest mb-2.5" style={{ color: meta.accent }}>
                      {meta.label}
                    </div>
                    <div className="grid grid-cols-6 gap-2">
                      {visuals.map(v => {
                        const isSelected = selectedVisuals.some(x => x.key === v.key);
                        const IconComponent = VISUAL_ICONS[v.key] || Layout;
                        return (
                          <button
                            key={v.key}
                            onClick={() => toggleVisual(v)}
                            title={v.desc}
                            className="flex flex-col items-center gap-1.5 py-3 px-1 rounded-xl border cursor-pointer transition-all duration-150 group hover:bg-[var(--hover-bg)] hover:border-[var(--hover-border)]"
                            style={{
                              '--hover-bg': `${meta.accent}12`,
                              '--hover-border': `${meta.accent}40`,
                              '--accent-color': meta.accent,
                              background: isSelected ? `${meta.accent}18` : 'var(--t-surface)',
                              borderColor: isSelected ? `${meta.accent}55` : 'var(--t-border)',
                            }}
                          >
                            <IconComponent
                              size={18}
                              style={{ color: isSelected ? meta.accent : undefined }}
                              className="transition-colors duration-150 text-[#94a3b8] group-hover:text-[var(--accent-color)]"
                            />
                            <span
                              className="text-[9px] font-semibold leading-tight text-center truncate w-full px-1 transition-colors duration-150 text-[#94a3b8] group-hover:text-[var(--accent-color)]"
                              style={{ color: isSelected ? meta.accent : undefined }}
                            >
                              {v.label}
                            </span>
                            {isSelected && (
                              <div className="w-1.5 h-1.5 rounded-full" style={{ background: meta.accent }} />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
            {selectedVisuals.length > 0 && (
              <div className={`flex items-center justify-between px-5 py-2.5 border-t ${t.border} bg-indigo-500/5`}>
                <span className={`text-[10px] font-medium ${t.textMuted}`}>
                  {selectedVisuals.map(v => v.label).join(', ')}
                </span>
                <button
                  onClick={() => setPickerOpen(false)}
                  className="text-[11px] font-bold px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer transition-colors"
                >
                  Done
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Main input bar ── */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`relative flex flex-col gap-2 p-1.5 rounded-2xl border ${t.border} ${t.surface} ${t.glass} shadow-lg transition-all duration-300 focus-within:border-neutral-400/50 ${isDragging ? 'ring-2 ring-indigo-500/30 border-indigo-500/50' : ''}`}
        >
          {/* Context chips row */}
          {references.length > 0 && (
            <div className="flex flex-wrap gap-2 px-2 pt-1.5 pb-0.5">
              {references.map((ref, i) => (
                <div key={i} className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${t.surface} border ${t.border} ${t.textMain} shadow-sm`}>
                  {ref.type === 'visual' ? <Network size={12} /> : <FileText size={12} />}
                  <span className="truncate max-w-[150px]">{ref.title}</span>
                  <button onClick={() => removeReference(i)} className="p-0.5 rounded-full hover:bg-neutral-200 dark:hover:bg-neutral-800 transition-colors">
                    <X size={10} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-end gap-2 w-full">
            {/* Left actions */}
            <div className="flex gap-1 pl-1 pb-1 relative z-10">
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.docx,.pptx,.txt,.md"
                onChange={handleAttachFile}
                disabled={disabled || attaching}
              />
              <IconButton
                icon={attaching ? RefreshCw : Plus}
                t={t}
                title={attaching ? 'Uploading…' : 'Attach file as context'}
                disabled={disabled || attaching}
                onClick={handleAddContext}
                className={attaching ? 'animate-spin' : ''}
              />
            </div>

            {/* Textarea */}
            <textarea
              id="chat-input-textarea"
              value={text}
              dir={textDir}
              onChange={handleInput}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }}
              disabled={disabled}
              placeholder="Ask OpenStudy anything..."
              className={`flex-1 max-h-48 min-h-[44px] bg-transparent border-none focus:ring-0 resize-none py-3 px-2 ${t.textMain} ${t.placeholderMuted} outline-none text-[15px] font-medium leading-relaxed disabled:opacity-50`}
              rows={1}
              style={{ scrollbarWidth: 'none' }}
            />

            {/* Right actions */}
            <div className="flex gap-1.5 pr-2 pb-1 relative z-10 items-center">

              {/* Selected visuals chips */}
              {selectedVisuals.length > 0 && (
                selectedVisuals.length === 1 ? (() => {
                  const v = selectedVisuals[0];
                  const IconComponent = VISUAL_ICONS[v.key] || Layout;
                  const meta = CAT_META[v.category];
                  return (
                    <div
                      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border text-[11px] font-bold"
                      style={{ background: `${meta.accent}15`, borderColor: `${meta.accent}45`, color: meta.accent }}
                    >
                      <button onClick={() => setPickerOpen(p => !p)} className="flex items-center gap-1.5 cursor-pointer">
                        <IconComponent size={12} strokeWidth={2.5} />
                        <span>{v.label}</span>
                      </button>
                      <button onClick={() => setSelectedVisuals([])} className="opacity-60 hover:opacity-100 cursor-pointer ml-1">
                        <X size={10} />
                      </button>
                    </div>
                  );
                })() : (
                  <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border text-[11px] font-bold bg-indigo-500/15 border-indigo-500/40 text-indigo-400">
                    <button onClick={() => setPickerOpen(p => !p)} className="flex items-center gap-1.5 cursor-pointer">
                      <Layout size={12} strokeWidth={2.5} />
                      <span>{selectedVisuals.length} visuals</span>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setSelectedVisuals([]); }}
                      className="opacity-60 hover:opacity-100 cursor-pointer ml-0.5"
                    >
                      <X size={10} />
                    </button>
                  </div>
                )
              )}

              {/* Visual picker toggle */}
              <button
                onClick={() => setPickerOpen(v => !v)}
                title="Choose visual type"
                className={`p-2 rounded-xl transition-all duration-200 cursor-pointer ${
                  pickerOpen
                    ? 'bg-indigo-500/15 border border-indigo-500/40 text-indigo-400'
                    : `${t.textMuted} ${t.textMainHover} ${t.surfaceHover}`
                }`}
              >
                <Layout size={18} strokeWidth={2} />
              </button>

              <button
                onClick={submit}
                disabled={disabled || !text.trim()}
                title="Send message (Enter)"
                className="p-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-white transition-colors shadow-sm disabled:opacity-50"
              >
                <ArrowRight size={18} strokeWidth={2.5} />
              </button>
            </div>
          </div>
        </div>

        <div className="text-center mt-2.5">
          <span className={`text-[11px] font-medium ${t.textMuted} tracking-wide`}>OpenStudy • Local AI Companion</span>
        </div>
      </div>
    </div>
  );
};

export default function App({ isDashboard = false }) {
  const [activeTheme, setActiveTheme] = useState('apple-minimal');
  const [textSize, setTextSize] = useState('medium');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const fileInputRef = useRef(null);

  // Backend State
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActive] = useState(null);
  const [messages, setMessages] = useState([]);
  const [ragUploading, setRagUploading] = useState(false);
  const [sending, setSending] = useState(false);
  const [backendOk, setBackendOk] = useState(true);
  const [studyLibraryOpen, setStudyLibraryOpen] = useState(false);
  const [nodes, setNodes] = useState([]);
  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const exportDropdownRef = useRef(null);

  // Settings modal
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState('gemini');
  const [aboutOpen, setAboutOpen] = useState(false);
  const [settingsData, setSettingsData] = useState({
    active_provider: 'gemini',
    providers: {
      gemini:     { api_keys: [''], model: 'gemini-2.5-flash' },
      openai:     { api_keys: [''], model: 'gpt-4o' },
      anthropic:  { api_keys: [''], model: 'claude-sonnet-4-6' },
      groq:       { api_keys: [''], model: 'llama-3.3-70b-versatile' },
      openrouter: { api_keys: [''], model: 'openai/gpt-4o' },
      ollama:     { api_keys: [], model: 'llama3', base_url: 'http://localhost:11434' },
    },
    system_prompt: '',
    prep_prompt: '',
    visual_theme: 'auto',
    // legacy
    gemini_api_keys: [''],
    gemini_model: 'gemini-2.5-flash',
  });
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsSaved, setSettingsSaved] = useState(false);
  
  // Library Modal Search/Filter/Pagination States
  const [logsSearch, setLogsSearch] = useState('');
  const [logsFilter, setLogsFilter] = useState('all'); // 'all' | 'ready' | 'pending'
  const [logsPage, setLogsPage] = useState(1);

  const meta = THEME_META[activeTheme];
  const t = { ...STATIC_THEME, font: meta.font };

  useEffect(() => {
    document.body.style.overflow = 'hidden';
    document.documentElement.setAttribute('data-theme', activeTheme);
    return () => {
      document.body.style.overflow = 'unset';
      document.documentElement.removeAttribute('data-theme');
    };
  }, [activeTheme]);


  const loadStudyLibrary = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/study/library`);
      if (res.ok) {
        const data = await res.json();
        setNodes(data.nodes || []);
      }
    } catch (e) {
      console.error("Failed to load study library:", e);
    }
  }, []);

  useEffect(() => {
    if (studyLibraryOpen) {
      loadStudyLibrary();
    }
  }, [studyLibraryOpen, loadStudyLibrary]);

  // Close export dropdown on outside click
  useEffect(() => {
    if (!exportDropdownOpen) return;
    const handler = (e) => {
      if (exportDropdownRef.current && !exportDropdownRef.current.contains(e.target)) {
        setExportDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [exportDropdownOpen]);

  const handleExportChat = useCallback(async (format) => {
    if (!activeSession || exporting) return;
    setExportDropdownOpen(false);
    setExporting(true);
    try {
      const res = await fetch(`${API}/api/chat/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSession.session_id, format }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'success' && data.download_path) {
          window.open(`${API}/api/documents/download?path=${encodeURIComponent(data.download_path)}`, '_blank');
        } else {
          alert('Export failed.');
        }
      } else {
        alert('Export request failed.');
      }
    } catch (err) {
      console.error(err);
      alert('Could not reach backend.');
    } finally {
      setExporting(false);
    }
  }, [activeSession, exporting]);

  const refreshStatsAndNodes = useCallback(async () => {
    // Backend health check — used to detect connection-refused state for toasts.
    try {
      const healthRes = await fetch(`${API}/`);
      setBackendOk(healthRes.ok);
    } catch {
      setBackendOk(false);
    }
  }, []);

  // Poll backend health
  useEffect(() => {
    refreshStatsAndNodes();
    const interval = setInterval(refreshStatsAndNodes, 5000);
    return () => clearInterval(interval);
  }, [refreshStatsAndNodes]);

  const loadSessions = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/chat/sessions`);
      if (!r.ok) return false;
      const d = await r.json();
      setSessions(d.sessions || []);
      return true;
    } catch {
      return false;
    }
  }, []);

  // Self-recovering session loader: backend (Python child process) often
  // isn't ready when React first mounts in Tauri, so the initial GET fails.
  // Retry with backoff until it succeeds, then poll periodically for changes.
  useEffect(() => {
    let cancelled = false;
    let pollTimer = null;
    let retryTimer = null;

    const tryLoad = async (attempt) => {
      if (cancelled) return;
      const ok = await loadSessions();
      if (cancelled) return;
      if (ok) {
        // Backend warm — switch to a slow change-detection poll.
        pollTimer = setInterval(() => { if (!cancelled) loadSessions(); }, 12000);
      } else {
        const delay = Math.min(1000 * 2 ** Math.min(attempt, 4), 8000);
        retryTimer = setTimeout(() => tryLoad(attempt + 1), delay);
      }
    };

    tryLoad(0);
    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [loadSessions]);

  const newSession = useCallback(() => {
    const id = uid();
    const session = { session_id: id, title: 'New Workspace', messages: [] };
    setActive(session);
    setMessages([]);
  }, []);

  // Global Keyboard Shortcuts — must be after newSession is defined
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'l') {
        e.preventDefault();
        setStudyLibraryOpen(prev => !prev);
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        newSession();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [newSession]);

  const loadSession = useCallback(async (s) => {
    // Fetch latest session data from backend to ensure full history
    try {
      const r = await fetch(`${API}/api/chat/sessions`);
      if (r.ok) {
        const d = await r.json();
        const fresh = (d.sessions || []).find(x => x.session_id === s.session_id);
        if (fresh) s = fresh;
      }
    } catch {}
    setActive(s);
    const msgs = (s.messages || []).map(m => ({ ...m, id: m.id || uid() }));
    setMessages(msgs);
  }, []);

  const saveSession = useCallback(async (session, msgs) => {
    if (!session) return;
    const title = msgs.find(m => m.role === 'user')?.components?.[0]?.content?.slice(0, 50) || 'Workspace';
    try {
      await fetch(`${API}/api/chat/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: session.session_id, title, messages: msgs }),
      });
      loadSessions();
    } catch {}
  }, [loadSessions]);

  const handleSend = useCallback(async (text, visualTypes = []) => {
    if (!text.trim() || sending) return;
    let session = activeSession;
    if (!session) {
      session = { session_id: uid(), title: text.slice(0, 50), messages: [] };
      setActive(session);
    }

    const assistantId = uid();
    const userMsg = {
      id: uid(),
      role: 'user',
      components: [{ type: 'text', content: text }],
    };
    const thinkingMsg = {
      id: assistantId,
      role: 'assistant',
      isThinking: true,
      components: [],
    };

    const next = [...messages, userMsg, thinkingMsg];
    setMessages(next);
    setSending(true);

    let streamedReply = '';
    let finalVisuals = [];
    let noKey = false;
    let streamFailed = false;
    let rateLimit = null;

    try {
      const res = await fetch(`${API}/api/chat/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({
          session_id: session.session_id,
          message: text,
          visual_types: visualTypes.length > 0 ? visualTypes : null,
          theme: activeTheme,
        }),
      });
      if (!res.ok || !res.body) throw new Error(`stream open failed (${res.status})`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      let currentEvent = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() || '';
        for (const raw of lines) {
          const line = raw.replace(/\r$/, '');
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            const payload = line.slice(5).trim();
            if (!payload) continue;
            let parsed;
            try { parsed = JSON.parse(payload); } catch { continue; }
            if (currentEvent === 'token' && typeof parsed.token === 'string') {
              streamedReply += parsed.token;
              setMessages(curr => curr.map(m => m.id === assistantId
                ? { ...m, isThinking: false, components: [{ type: 'text', content: streamedReply }] }
                : m));
            } else if (currentEvent === 'done') {
              if (typeof parsed.reply === 'string' && parsed.reply.length >= streamedReply.length) {
                streamedReply = parsed.reply;
              }
              if (parsed.visuals && parsed.visuals.length > 0) finalVisuals = parsed.visuals;
              else if (parsed.visual) finalVisuals = [parsed.visual];
            } else if (currentEvent === 'no_api_key') {
              noKey = true;
            } else if (currentEvent === 'rate_limit') {
              rateLimit = parsed;
            } else if (currentEvent === 'error') {
              streamFailed = true;
              streamedReply = parsed.error || parsed.detail || 'An error occurred.';
            }
          } else if (line === '') {
            currentEvent = '';
          }
        }
      }

      let aiMsg;
      if (rateLimit) {
        aiMsg = {
          id: assistantId,
          role: 'assistant',
          isThinking: false,
          components: [],
          rateLimit,
        };
      } else if (noKey) {
        aiMsg = {
          id: assistantId,
          role: 'assistant',
          isThinking: false,
          components: [],
          rateLimit: { retry_in_seconds: 0, total_keys: 0, available_keys: 0, reason: 'no_key' },
          needsKey: true,
        };
      } else if (streamFailed) {
        aiMsg = {
          id: assistantId,
          role: 'assistant',
          isThinking: false,
          components: [{ type: 'text', content: streamedReply || 'The model returned an error.' }],
          error: streamedReply,
        };
      } else {
        aiMsg = {
          id: assistantId,
          role: 'assistant',
          isThinking: false,
          components: [{ type: 'text', content: streamedReply || 'No response.' }],
          visuals: finalVisuals,
          visual: finalVisuals[0] || null,
        };
      }

      const final = [...messages, userMsg, aiMsg];
      setMessages(final);
      saveSession(session, final);
    } catch (err) {
      const errMsg = {
        id: assistantId,
        role: 'assistant',
        isThinking: false,
        components: [{ type: 'text', content: 'Could not reach backend.' }],
      };
      setMessages([...messages, userMsg, errMsg]);
    } finally {
      setSending(false);
    }
  }, [activeSession, messages, saveSession, sending]);

  const handleRagUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // Reset input so same file can be re-selected later
    e.target.value = '';
    setRagUploading(true);
    const formData = new FormData();
    formData.append('files', file);
    setTimeout(async () => {
      try {
        await fetch(`${API}/api/documents/upload`, { method: 'POST', body: formData });
      } catch (err) {
        console.error(err);
      } finally {
        setRagUploading(false);
      }
    }, 50);
  };

  // Load settings from backend
  const loadSettings = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/settings`);
      if (res.ok) {
        const data = await res.json();
        const prov = data.providers || {};
        const ensure = (name, def) => ({
          api_keys: (prov[name]?.api_keys?.length ? prov[name].api_keys : ['']),
          model: prov[name]?.model || def.model,
          ...(def.base_url !== undefined ? { base_url: prov[name]?.base_url || def.base_url } : {}),
        });
        setSettingsData({
          active_provider: data.active_provider || 'gemini',
          providers: {
            gemini:     ensure('gemini',     { model: 'gemini-2.5-flash' }),
            openai:     ensure('openai',     { model: 'gpt-4o' }),
            anthropic:  ensure('anthropic',  { model: 'claude-sonnet-4-6' }),
            groq:       ensure('groq',       { model: 'llama-3.3-70b-versatile' }),
            openrouter: ensure('openrouter', { model: 'openai/gpt-4o' }),
            ollama:     ensure('ollama',     { model: 'llama3', base_url: 'http://localhost:11434' }),
          },
          system_prompt: data.system_prompt || '',
          prep_prompt:   data.prep_prompt   || '',
          visual_theme:  data.visual_theme  || 'auto',
          gemini_api_keys: data.gemini_api_keys?.length ? data.gemini_api_keys : [''],
          gemini_model: data.gemini_model || 'gemini-2.5-flash',
        });
      }
    } catch {}
  }, []);

  const handleSaveSettings = async () => {
    setSettingsSaving(true);
    setSettingsSaved(false);
    try {
      // Build clean providers payload — filter blank keys
      const cleanProviders = {};
      for (const [name, cfg] of Object.entries(settingsData.providers || {})) {
        cleanProviders[name] = {
          ...cfg,
          api_keys: (cfg.api_keys || []).filter(k => k.trim()),
        };
      }
      const payload = {
        active_provider: settingsData.active_provider,
        providers: cleanProviders,
        system_prompt: settingsData.system_prompt,
        prep_prompt: settingsData.prep_prompt,
        visual_theme: settingsData.visual_theme || 'auto',
        // legacy fields
        gemini_api_keys: cleanProviders.gemini?.api_keys || [],
        gemini_model: cleanProviders.gemini?.model || 'gemini-2.5-flash',
      };
      const res = await fetch(`${API}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setSettingsSaved(true);
        setTimeout(() => setSettingsSaved(false), 3000);
      }
    } catch {}
    finally { setSettingsSaving(false); }
  };

  const openDashboard = useCallback(() => {
    if (isTauri) {
      invoke('open_dashboard').catch(console.error);
    } else {
      window.open('/dashboard.html', '_blank');
    }
  }, []);

  const handleOpenUrl = useCallback(async (url) => {
    if (isTauri) {
      try {
        await fetch(`${API}/api/utils/open-url`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url })
        });
      } catch (e) {
        console.error("Failed to open URL externally:", e);
      }
    } else {
      window.open(url, '_blank');
    }
  }, []);

  useEffect(() => {
    loadSettings();
    if (!activeSession) newSession();
  }, [loadSettings]);

  const textStyles = {
    '--md-font-size': TEXT_SIZE_MAP[textSize],
    '--chat-font-size': TEXT_SIZE_MAP[textSize],
    '--sidebar-w': sidebarOpen ? '256px' : '0px',
  };

  return (
    <div 
      className={`${isDashboard ? 'h-full w-full' : 'h-screen w-screen'} flex overflow-hidden transition-colors duration-500 ease-in-out ${t.bgMain} ${t.textMain} ${meta.font}`}
      style={textStyles}
    >
      
      {/* Background Matte Noise */}
      <div className="fixed inset-0 pointer-events-none z-0 bg-noise opacity-[0.04] dark:opacity-[0.02]" />

      {/* --- Left Sidebar (Workspace) --- */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-0'} flex flex-col border-r ${t.border} ${t.bgSidebar} ${t.glass} transition-all duration-300 z-10 overflow-hidden shrink-0`}>
        
        {/* Header */}
        <div data-tauri-drag-region className={`h-16 flex items-center justify-between px-4 border-b ${t.border} cursor-move select-none`}>
          <div className="flex items-center gap-3 w-48 pointer-events-none">
            <div className={`flex items-center justify-center w-9 h-9 rounded-xl border ${t.border} ${t.surface} ${t.textMain} shadow-sm`} aria-label="OpenStudy">
              <svg viewBox="8 8 84 84" width="22" height="22" fill="none" aria-hidden="true">
                <g stroke="currentColor" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18,32 L46,45 L46,80 L18,67 Z" />
                  <path d="M82,32 L54,45 L54,80 L82,67 Z" />
                  <path d="M50,85 L50,25 L40,35 M50,25 L60,35" strokeWidth="3.8" />
                  <circle cx="50" cy="15" r="2.6" fill="currentColor" stroke="none" />
                  <circle cx="28" cy="24" r="1.6" fill="currentColor" stroke="none" />
                  <circle cx="72" cy="24" r="1.6" fill="currentColor" stroke="none" />
                </g>
              </svg>
            </div>
            <div className="flex flex-col leading-tight">
              <span className={`font-bold text-sm tracking-tight ${t.textMain}`}>OpenStudy</span>
              <span className={`text-[9px] font-semibold uppercase tracking-widest ${t.textMuted}`}>Study Companion</span>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="flex-1 overflow-y-auto py-4 px-3 space-y-1 no-scrollbar">
          {!isDashboard && (
            <button onClick={() => setStudyLibraryOpen(true)} title="Study Concept Library (Ctrl+L)" className={`w-full flex items-center justify-between p-2.5 rounded-lg border border-transparent ${t.surfaceHover} transition-colors group mb-2 cursor-pointer`}>
               <div className="flex items-center gap-3">
                 <BookOpen size={16} className={t.textMuted} />
                 <span className={`text-sm font-medium ${t.textMain}`}>Study Library</span>
               </div>
               <div className={`opacity-0 group-hover:opacity-100 flex items-center gap-1 text-[10px] font-mono ${t.textMuted}`}>
                 <Command size={10} /> L
               </div>
            </button>
          )}
          
          <button onClick={newSession} title="Start a new chat workspace" className={`w-full flex items-center justify-between p-2.5 rounded-lg border border-transparent ${t.surfaceHover} transition-colors group mb-2 cursor-pointer`}>
             <div className="flex items-center gap-3">
               <Plus size={16} className={t.textMuted} />
               <span className={`text-sm font-medium ${t.textMain}`}>New Workspace</span>
             </div>
             <div className={`opacity-0 group-hover:opacity-100 flex items-center gap-1 text-[10px] font-mono ${t.textMuted}`}>
               <Command size={10} /> N
             </div>
          </button>
          
          <button onClick={() => fileInputRef.current?.click()} title="Upload document to knowledge base (PDF, DOCX, PPTX, images)" className={`w-full flex items-center justify-between p-2.5 rounded-lg border border-transparent ${t.surfaceHover} transition-colors group mb-4 cursor-pointer bg-transparent text-left`}>
             <div className="flex items-center gap-3">
               <Database size={16} className={t.textMuted} />
               <span className={`text-sm font-medium ${t.textMain}`}>
                 {ragUploading ? 'Uploading...' : 'Upload Document'}
               </span>
             </div>
             <input ref={fileInputRef} type="file" className="hidden" accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg,.tiff" onChange={handleRagUpload} disabled={ragUploading} />
          </button>

          <div className={`text-[10px] font-bold uppercase tracking-wider ${t.textMuted} pl-2 pt-2 pb-1`}>Recent</div>
          {sessions.map((s) => (
             <div 
               key={s.session_id} 
               onClick={() => loadSession(s)} 
               className={`flex items-center justify-between p-2.5 rounded-lg cursor-pointer ${t.surfaceHover} ${activeSession?.session_id === s.session_id ? t.surface : ''} transition-colors group/item`}
             >
               <div className="flex items-center gap-3 min-w-0">
                 <MessageSquare size={14} className={t.textMuted} />
                 <span className={`text-sm font-medium ${t.textMain} truncate`}>{s.title || 'Workspace'}</span>
               </div>
               <button 
                 onClick={async (e) => {
                   e.stopPropagation();
                   if (confirm(`Are you sure you want to delete "${s.title || 'Workspace'}"?`)) {
                     try {
                       await fetch(`${API}/api/chat/sessions/${s.session_id}`, { method: 'DELETE' });
                       if (activeSession?.session_id === s.session_id) {
                         newSession();
                       } else {
                         loadSessions();
                       }
                     } catch (err) {
                       console.error("Failed to delete session:", err);
                     }
                   }
                 }}
                 className="opacity-0 group-hover/item:opacity-100 p-1 rounded hover:bg-red-500/10 text-neutral-400 hover:text-red-500 transition-all shrink-0"
                 title="Delete Workspace"
               >
                 <Trash2 size={12} />
               </button>
             </div>
          ))}
        </div>

        {/* User & Settings */}
        <div className={`p-4 border-t ${t.border} space-y-4`}>
          <div>
             <div className={`text-[10px] font-bold uppercase tracking-wider ${t.textMuted} mb-2 pl-1`}>Environment</div>
             <div className="flex gap-2">
               {Object.entries(THEME_META).map(([key, theme]) => (
                 <button 
                   key={key} 
                   onClick={() => setActiveTheme(key)}
                   title={theme.name}
                   className={`w-5 h-5 rounded-full border border-neutral-400/20 shadow-sm transition-transform hover:scale-110 ${activeTheme === key ? 'ring-2 ring-current ring-offset-1 ring-offset-transparent scale-110' : ''}`}
                   style={{ backgroundColor: theme.swatch }}
                 />
               ))}
             </div>
          </div>
          <div>
             <div className={`text-[10px] font-bold uppercase tracking-wider ${t.textMuted} mb-2 pl-1`}>Text Size</div>
             <div className={`flex gap-1 p-0.5 rounded-lg border ${t.border} ${t.surface}`}>
               {['small', 'medium', 'large', 'xlarge'].map((size) => (
                 <button
                   key={size}
                   onClick={() => setTextSize(size)}
                   title={`Text size: ${size}`}
                   className={`flex-1 text-center py-1 rounded text-[11px] font-bold uppercase transition-all ${textSize === size ? `${t.accentBg} shadow-sm` : `${t.textMuted} ${t.textMainHover}`}`}
                   style={textSize === size ? { background: 'var(--t-accent-main)', color: meta?.isLight ? '#fff' : '#000' } : {}}
                 >
                   {size === 'small' ? 'A-' : size === 'medium' ? 'A' : size === 'large' ? 'A+' : 'A++'}
                 </button>
               ))}
             </div>
          </div>
          <div
            onClick={() => { loadSettings(); setSettingsOpen(true); }}
            title="Open settings"
            className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer ${t.surfaceHover} transition-colors`}
          >
             <div className={`w-8 h-8 rounded-full bg-neutral-200 dark:bg-neutral-800 flex items-center justify-center`}>
               <User size={14} className={t.textMain} />
             </div>
             <div className="flex-1 min-w-0">
               <div className={`text-sm font-medium ${t.textMain} truncate`}>Settings</div>
               <div className={`text-xs ${t.textMuted} truncate`}>API Keys & Models</div>
             </div>
             <Settings size={14} className={t.textMuted} />
          </div>
          <div
            onClick={() => setAboutOpen(true)}
            title="About the developer"
            className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer ${t.surfaceHover} transition-colors`}
          >
             <Info size={14} className={t.textMuted} />
             <span className={`text-xs font-medium ${t.textMuted}`}>About</span>
          </div>
        </div>
      </div>

      {/* --- Main Chat Content --- */}
      <div className="flex-1 flex flex-col relative z-0 min-w-0 bg-transparent">
        <header className={`h-16 flex items-center justify-between px-4 border-b ${t.border} ${t.glass} z-10 sticky top-0`}>
          <div className="flex items-center gap-2">
            <IconButton icon={sidebarOpen ? Menu : ChevronRight} onClick={() => setSidebarOpen(!sidebarOpen)} title="Toggle sidebar" t={t} />
            <button
              onClick={() => { loadSettings(); setSettingsOpen(true); }}
              title="Open settings"
              className={`px-3 py-1.5 rounded-md ${t.surface} border ${t.border} flex items-center gap-2 text-xs font-medium cursor-pointer shadow-sm ${t.surfaceHover} transition-colors`}
            >
              <span className={`flex items-center gap-1.5 ${t.textMain}`}>
                {(() => {
                  const p = settingsData.active_provider || 'gemini';
                  const m = settingsData.providers?.[p]?.model || settingsData.gemini_model || 'Gemini';
                  const provColors = { gemini: '#4285F4', openai: '#10A37F', anthropic: '#D97706', groq: '#F43F5E', openrouter: '#8B5CF6', ollama: '#64748B' };
                  const labels = {
                    'gemini-2.5-flash': 'Gemini 2.5 Flash', 'gemini-2.5-pro': 'Gemini 2.5 Pro',
                    'gemini-2.0-flash': 'Gemini 2.0 Flash', 'gemini-1.5-pro': 'Gemini 1.5 Pro',
                    'gemini-1.5-flash': 'Gemini 1.5 Flash', 'gpt-4o': 'GPT-4o',
                    'gpt-4o-mini': 'GPT-4o Mini', 'gpt-4.1': 'GPT-4.1',
                    'claude-sonnet-4-6': 'Claude Sonnet', 'claude-opus-4-8': 'Claude Opus',
                    'claude-haiku-4-5-20251001': 'Claude Haiku',
                    'llama-3.3-70b-versatile': 'Llama 3.3 70B', 'llama-3.1-8b-instant': 'Llama 3.1 8B',
                    'mixtral-8x7b-32768': 'Mixtral 8x7B', 'gemma2-9b-it': 'Gemma 2 9B',
                    'llama3': 'Llama 3', 'llama3.1': 'Llama 3.1', 'mistral': 'Mistral', 'phi3': 'Phi-3', 'gemma2': 'Gemma 2', 'codellama': 'CodeLlama',
                  };
                  const label = labels[m] || m.split('/').pop() || m;
                  const dot = provColors[p];
                  return <><span className="w-2 h-2 rounded-full shrink-0" style={{ background: dot }} />{label}</>;
                })()}
              </span>
              <ChevronDown size={12} className={t.textMuted} />
            </button>

            {activeSession && (
              <div className="relative flex items-center" ref={exportDropdownRef}>
                <button 
                  onClick={() => setExportDropdownOpen(!exportDropdownOpen)} title="Export this chat as PDF or PNG"
                  disabled={exporting}
                  className={`px-3 py-1.5 rounded-md ${t.surface} ${t.surfaceHover} border ${t.border} flex items-center gap-1.5 text-xs font-semibold cursor-pointer shadow-sm transition-all ${t.textMain} disabled:opacity-50`}
                >
                  <FileText size={13} className={t.textMuted} />
                  <span>{exporting ? 'Exporting...' : 'Export Chat'}</span>
                  <ChevronDown size={10} className={t.textMuted} />
                </button>
                {exportDropdownOpen && (
                  <div className={`absolute left-0 top-full mt-1.5 w-36 rounded-xl border ${t.border} ${t.bgSidebar} ${t.glass} shadow-xl py-1 z-50`}>
                    <button 
                      onClick={() => handleExportChat('pdf')} 
                      className={`w-full text-left px-3.5 py-2 text-xs ${t.surfaceHover} ${t.textMain} font-semibold transition-colors flex items-center gap-2 cursor-pointer`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                      PDF Document
                    </button>
                    <button 
                      onClick={() => handleExportChat('png')} 
                      className={`w-full text-left px-3.5 py-2 text-xs ${t.surfaceHover} ${t.textMain} font-semibold transition-colors flex items-center gap-2 cursor-pointer`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                      PNG Image
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
          
          <div data-tauri-drag-region className="flex-1 h-full mx-4 cursor-move" />

          <div className="flex items-center gap-1">
            {!isDashboard && (
              <>
                <div className="w-px h-4 bg-neutral-400/30 mx-1" />
                <IconButton icon={Minus} onClick={() => getCurrentWindow().minimize()} title="Minimize" t={t} />
                <IconButton icon={Square} onClick={() => getCurrentWindow().isMaximized().then(max => max ? getCurrentWindow().unmaximize() : getCurrentWindow().maximize())} title="Maximize / Restore" t={t} />
                <IconButton icon={X} onClick={() => getCurrentWindow().close()} title="Close" className="hover:!bg-red-500 hover:!text-white" t={t} />
              </>
            )}
          </div>
        </header>

        <div className="flex-1 relative flex overflow-hidden">
            <MessageArea
              messages={messages}
              t={t}
              activeTheme={activeTheme}
              onRetry={(text) => handleSend(text, null)}
              onOpenSettings={() => { loadSettings(); setSettingsOpen(true); }}
              backendOk={backendOk}
            />
           <ChatInput t={t} onSend={handleSend} disabled={sending} sessionId={activeSession?.session_id} />
        </div>
      </div>

      {/* Right Context Panel removed with RAG/Prep — see backend rewrite plan. */}

      {/* --- Study Concept Library Logs Modal --- */}
      {studyLibraryOpen && (
        <div className="fixed inset-0 bg-neutral-900/60 dark:bg-black/60 backdrop-blur-md z-50 flex items-center justify-center p-4 md:p-8 animate-message">
          <div className={`w-full max-w-5xl h-[85vh] rounded-2xl border ${t.border} ${t.bgSidebar} ${t.glass} shadow-2xl flex flex-col overflow-hidden`}>
            
            {/* Modal Header */}
            <div className={`p-5 border-b ${t.border} flex items-center justify-between`}>
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-500`}>
                  <BookOpen size={16} />
                </div>
                <div>
                  <h2 className={`text-base font-bold ${t.textMain}`}>Study Concept logs Library</h2>
                  <p className={`text-[11px] ${t.textMuted} mt-0.5`}>Review and filter all structured medical study concepts</p>
                </div>
              </div>
              <button 
                onClick={() => setStudyLibraryOpen(false)}
                className={`p-2 rounded-lg ${t.surfaceHover} transition-all cursor-pointer ${t.textMuted} ${t.textMainHover}`}
              >
                <X size={18} />
              </button>
            </div>

            {/* Filter and Search controls */}
            <div className={`p-4 border-b ${t.border} bg-neutral-500/5 flex flex-col md:flex-row gap-3 items-center justify-between`}>
              <div className="relative w-full md:w-80">
                <Search size={14} className={`absolute left-3 top-1/2 -translate-y-1/2 ${t.textMuted}`} />
                <input 
                  type="text"
                  value={logsSearch}
                  onChange={e => { setLogsSearch(e.target.value); setLogsPage(1); }}
                  placeholder="Search title or content..."
                  className={`w-full text-xs pl-9 pr-3 py-2 rounded-lg border ${t.border} bg-transparent ${t.textMain} ${t.placeholderMuted} outline-none focus:border-neutral-400`}
                />
              </div>

              <div className="flex gap-2 w-full md:w-auto justify-end">
                {['all', 'ready', 'pending'].map(f => (
                  <button
                    key={f}
                    onClick={() => { setLogsFilter(f); setLogsPage(1); }}
                    className={`px-3 py-1.5 rounded-lg border text-[11px] font-semibold uppercase transition-all cursor-pointer ${logsFilter === f ? 'bg-indigo-500/15 border-indigo-500/30 text-indigo-500' : `${t.border} ${t.surface} ${t.textMuted} ${t.textMainHover}`}`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            {/* Table Area */}
            <div className="flex-1 overflow-auto p-4">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className={`border-b ${t.border} text-[10px] font-bold uppercase tracking-wider ${t.textMuted} bg-neutral-500/5`}>
                    <th className="p-3">Title / Concept</th>
                    <th className="p-3 text-center">Status</th>
                    <th className="p-3 text-center">Played</th>
                    <th className="p-3 text-center">Accuracy</th>
                    <th className="p-3">Generated Fact Preview</th>
                  </tr>
                </thead>
                <tbody className={t.textMain}>
                  {(() => {
                    // Filter logic
                    let list = nodes;
                    if (logsFilter === 'ready') list = list.filter(n => n.fact);
                    if (logsFilter === 'pending') list = list.filter(n => !n.fact);
                    if (logsSearch.trim()) {
                      const q = logsSearch.toLowerCase();
                      list = list.filter(n => 
                        (n.title && n.title.toLowerCase().includes(q)) || 
                        (n.fact && n.fact.toLowerCase().includes(q))
                      );
                    }

                    // Pagination logic
                    const ITEMS_PER_PAGE = 8;
                    const totalPages = Math.ceil(list.length / ITEMS_PER_PAGE) || 1;
                    const pageNodes = list.slice((logsPage - 1) * ITEMS_PER_PAGE, logsPage * ITEMS_PER_PAGE);

                    if (list.length === 0) {
                      return (
                        <tr>
                          <td colSpan={5} className={`p-8 text-center ${t.textMuted}`}>No concepts found</td>
                        </tr>
                      );
                    }

                    return (
                      <>
                        {pageNodes.map((node, i) => {
                          const acc = node.questions_asked ? Math.round((node.correct_answers / node.questions_asked) * 100) : null;
                          const accColor = acc > 70 ? 'text-green-500' : acc > 40 ? 'text-amber-500' : 'text-red-500';
                          return (
                            <tr key={i} className={`border-b ${t.border} hover:bg-neutral-500/5 transition-colors`}>
                              <td className="p-3 font-semibold max-w-[150px] truncate" title={node.title}>{node.title}</td>
                              <td className="p-3 text-center">
                                <span className={`inline-block px-2.5 py-0.5 rounded-full text-[9px] font-bold uppercase border ${node.fact ? 'bg-green-500/10 border-green-500/20 text-green-500' : 'bg-red-500/10 border-red-500/20 text-red-500'}`}>
                                  {node.fact ? 'ready' : 'pending'}
                                </span>
                              </td>
                              <td className="p-3 text-center font-medium">{node.times_played || 0}</td>
                              <td className="p-3 text-center font-bold">
                                {acc !== null ? <span className={accColor}>{acc}%</span> : <span className={t.textMuted}>-</span>}
                              </td>
                              <td className="p-3 max-w-[280px] truncate text-neutral-500 dark:text-neutral-400" title={node.fact}>{node.fact || 'Waiting for extraction...'}</td>
                            </tr>
                          );
                        })}
                        {/* Pagination controls inside tbody as a row */}
                        <tr>
                          <td colSpan={5} className="p-3 pt-6">
                            <div className="flex items-center justify-between">
                              <span className={`text-[10px] ${t.textMuted}`}>Showing {(logsPage-1)*ITEMS_PER_PAGE + 1}-{Math.min(logsPage*ITEMS_PER_PAGE, list.length)} of {list.length}</span>
                              <div className="flex gap-2">
                                <button 
                                  disabled={logsPage === 1}
                                  onClick={() => setLogsPage(p => p - 1)}
                                  className={`px-3 py-1 rounded border ${t.border} ${t.surface} hover:${t.surfaceHover} text-[10px] font-bold uppercase transition-all cursor-pointer disabled:opacity-50`}
                                >
                                  Prev
                                </button>
                                <span className={`text-xs px-2 flex items-center justify-center font-bold ${t.textMain}`}>Page {logsPage} of {totalPages}</span>
                                <button 
                                  disabled={logsPage === totalPages}
                                  onClick={() => setLogsPage(p => p + 1)}
                                  className={`px-3 py-1 rounded border ${t.border} ${t.surface} hover:${t.surfaceHover} text-[10px] font-bold uppercase transition-all cursor-pointer disabled:opacity-50`}
                                >
                                  Next
                                </button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      </>
                    );
                  })()}
                </tbody>
              </table>
            </div>

          </div>
        </div>
      )}

      {/* --- Settings Modal --- */}
      {settingsOpen && (() => {
        const PROVIDERS = [
          { key: 'gemini',     label: 'Gemini',     color: '#4285F4', link: 'https://aistudio.google.com/apikey',    linkLabel: 'Google AI Studio', models: [
            { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash', desc: 'Fast · Recommended' },
            { id: 'gemini-2.5-pro',   label: 'Gemini 2.5 Pro',   desc: 'Most capable' },
            { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash', desc: 'Balanced' },
            { id: 'gemini-1.5-pro',   label: 'Gemini 1.5 Pro',   desc: 'Stable' },
            { id: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash', desc: 'Lightweight' },
          ], note: 'Free tier: 15 req/min · 1,500/day per key. Rotate multiple keys to maximize throughput.' },
          { key: 'openai',     label: 'OpenAI',     color: '#10A37F', link: 'https://platform.openai.com/api-keys',  linkLabel: 'OpenAI Platform', models: [
            { id: 'gpt-4o',          label: 'GPT-4o',       desc: 'Recommended' },
            { id: 'gpt-4o-mini',     label: 'GPT-4o Mini',  desc: 'Cheaper & fast' },
            { id: 'gpt-4.1',         label: 'GPT-4.1',      desc: 'Latest' },
            { id: 'o1',              label: 'o1',            desc: 'Reasoning' },
            { id: 'o3-mini',         label: 'o3-mini',       desc: 'Fast reasoning' },
          ], note: 'Requires a paid OpenAI account. Billing starts on first API call.' },
          { key: 'anthropic',  label: 'Anthropic',  color: '#D97706', link: 'https://console.anthropic.com/settings/keys', linkLabel: 'Anthropic Console', models: [
            { id: 'claude-sonnet-4-6',  label: 'Claude Sonnet 4.6', desc: 'Recommended' },
            { id: 'claude-opus-4-8',    label: 'Claude Opus 4.8',   desc: 'Most powerful' },
            { id: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5', desc: 'Fast & cheap' },
          ], note: 'Requires an Anthropic account. Free trial credits available on signup.' },
          { key: 'groq',       label: 'Groq',       color: '#F43F5E', link: 'https://console.groq.com/keys',         linkLabel: 'Groq Console', models: [
            { id: 'llama-3.3-70b-versatile',  label: 'Llama 3.3 70B',   desc: 'Recommended' },
            { id: 'llama-3.1-8b-instant',     label: 'Llama 3.1 8B',    desc: 'Fastest' },
            { id: 'mixtral-8x7b-32768',       label: 'Mixtral 8x7B',    desc: 'Good quality' },
            { id: 'gemma2-9b-it',             label: 'Gemma 2 9B',      desc: 'Compact' },
          ], note: 'Groq is free with rate limits. Extremely fast inference.' },
          { key: 'openrouter', label: 'OpenRouter', color: '#8B5CF6', link: 'https://openrouter.ai/keys',           linkLabel: 'OpenRouter Dashboard', freeText: true, models: [
            { id: 'openai/gpt-4o',            label: 'GPT-4o',           desc: 'Via OpenRouter' },
            { id: 'anthropic/claude-3-5-sonnet', label: 'Claude 3.5 Sonnet', desc: 'Via OpenRouter' },
            { id: 'google/gemini-2.5-flash',  label: 'Gemini 2.5 Flash', desc: 'Via OpenRouter' },
            { id: 'meta-llama/llama-3.3-70b-instruct', label: 'Llama 3.3 70B', desc: 'Via OpenRouter' },
            { id: 'mistralai/mistral-large',  label: 'Mistral Large',    desc: 'Via OpenRouter' },
          ], note: 'OpenRouter aggregates 200+ models. Pick a preset or enter any model ID below.' },
          { key: 'ollama',     label: 'Ollama',     color: '#64748B', link: 'https://ollama.ai',                    linkLabel: 'ollama.ai', freeText: true, models: [
            { id: 'llama3',           label: 'Llama 3',       desc: 'Default' },
            { id: 'llama3.1',         label: 'Llama 3.1',     desc: 'Latest' },
            { id: 'mistral',          label: 'Mistral',       desc: 'Fast' },
            { id: 'phi3',             label: 'Phi-3',         desc: 'Compact' },
            { id: 'gemma2',           label: 'Gemma 2',       desc: 'Google' },
            { id: 'codellama',        label: 'CodeLlama',     desc: 'Code' },
          ], note: 'Runs 100% locally. No API key needed. Install Ollama then pull a model.', noKey: true },
        ];
        const activeTab = settingsTab;
        const prov = PROVIDERS.find(p => p.key === activeTab) || PROVIDERS[0];
        const provCfg = settingsData.providers?.[activeTab] || { api_keys: [''], model: prov.models[0].id };
        const setProvCfg = (updater) => setSettingsData(prev => ({
          ...prev,
          providers: { ...prev.providers, [activeTab]: typeof updater === 'function' ? updater(provCfg) : updater }
        }));
        const isActiveProvider = settingsData.active_provider === activeTab;

        return (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-50 flex items-center justify-center p-4 md:p-8 animate-message">
            <div className={`w-full max-w-3xl max-h-[90vh] rounded-2xl border ${t.border} shadow-2xl flex flex-col overflow-hidden ${t.bgSidebar} ${t.glass}`}>

              {/* Header */}
              <div className={`flex items-center justify-between px-6 py-4 border-b ${t.border}`}>
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center">
                    <Settings size={15} className="text-indigo-400" />
                  </div>
                  <div>
                    <h2 className={`text-sm font-bold ${t.textMain}`}>AI Provider Settings</h2>
                    <p className={`text-[11px] ${t.textMuted} mt-0.5`}>Configure API keys and models for each provider</p>
                  </div>
                </div>
                <button onClick={() => setSettingsOpen(false)} title="Close" className={`p-2 rounded-lg ${t.surfaceHover} ${t.textMuted} ${t.textMainHover} cursor-pointer`}><X size={16} /></button>
              </div>

              {/* Provider Tabs */}
              <div className={`flex gap-1 px-4 pt-3 pb-0 border-b ${t.border} overflow-x-auto no-scrollbar`}>
                {PROVIDERS.map(p => {
                  const hasKey = p.noKey || (settingsData.providers?.[p.key]?.api_keys?.some(k => k && k.trim()));
                  return (
                    <button
                      key={p.key}
                      onClick={() => setSettingsTab(p.key)}
                      className={`flex items-center gap-1.5 px-3 py-2 text-[11px] font-bold rounded-t-lg border-b-2 transition-all whitespace-nowrap cursor-pointer ${
                        activeTab === p.key
                          ? 'border-indigo-500 text-indigo-400'
                          : `border-transparent ${t.textMuted} ${t.textMainHover}`
                      }`}
                    >
                      <span className={`w-2 h-2 rounded-full shrink-0 ${hasKey ? 'bg-emerald-500' : 'border border-neutral-500'}`} />
                      {p.label}
                      {settingsData.active_provider === p.key && (
                        <span className="text-[8px] font-black px-1 py-0.5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">ACTIVE</span>
                      )}
                    </button>
                  );
                })}
              </div>

              <div className="flex-1 overflow-y-auto p-6 space-y-5 no-scrollbar">

                {/* Provider activation + info */}
                <div className={`flex items-start justify-between gap-4 p-4 rounded-xl border ${t.border} ${t.surface}`}>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="w-3 h-3 rounded-full" style={{ background: prov.color }} />
                      <span className={`text-xs font-bold ${t.textMain}`}>{prov.label}</span>
                    </div>
                    <p className={`text-[11px] ${t.textMuted} leading-relaxed`}>{prov.note}</p>
                    {!prov.noKey && (
                      <button
                        onClick={() => handleOpenUrl(prov.link)}
                        className="mt-2.5 inline-flex items-center gap-1.5 text-[11px] font-bold px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors cursor-pointer"
                      >
                        Get API key — {prov.linkLabel} <ExternalLink size={11} />
                      </button>
                    )}
                    {prov.noKey && (
                      <button
                        onClick={() => handleOpenUrl(prov.link)}
                        className="mt-2.5 inline-flex items-center gap-1.5 text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 transition-colors cursor-pointer"
                      >
                        Visit {prov.linkLabel} <ExternalLink size={10} />
                      </button>
                    )}
                  </div>
                  <button
                    onClick={() => setSettingsData(p => ({ ...p, active_provider: activeTab }))}
                    className={`shrink-0 px-4 py-2 rounded-xl text-[11px] font-bold border transition-all cursor-pointer ${
                      isActiveProvider
                        ? 'bg-indigo-600/20 border-indigo-500/40 text-indigo-400'
                        : `${t.surface} ${t.border} ${t.textMuted} hover:border-indigo-500/40 hover:text-indigo-400`
                    }`}
                  >
                    {isActiveProvider ? '✓ Active Provider' : 'Set as Active'}
                  </button>
                </div>

                {/* API Keys (not for Ollama) */}
                {!prov.noKey && (() => {
                  const keyPlaceholders = {
                    gemini: 'AIza...', openai: 'sk-...', anthropic: 'sk-ant-...', groq: 'gsk_...', openrouter: 'sk-or-...',
                  };
                  const keyPlaceholder = keyPlaceholders[activeTab] || 'API Key...';
                  return (
                  <div>
                    <div className={`text-[10px] font-bold uppercase tracking-widest ${t.textMuted} mb-2`}>
                      API Keys
                      {activeTab === 'gemini'
                        ? <span className={`ml-2 normal-case font-normal opacity-60`}>(up to 10 — rotated automatically)</span>
                        : <span className={`ml-2 normal-case font-normal opacity-60`}>(up to 10 — first key is used)</span>}
                    </div>
                    <div className="space-y-2">
                      {(provCfg.api_keys?.length ? provCfg.api_keys : ['']).map((key, idx) => {
                        const isMasked = typeof key === 'string' && key.startsWith('...');
                        return (
                          <div key={idx} className="flex items-center gap-2">
                            <span className={`text-[10px] font-bold ${t.textMuted} opacity-60 w-4 text-right shrink-0`}>{idx + 1}</span>
                            <input
                              type="text"
                              value={key}
                              readOnly={isMasked}
                              onChange={e => {
                                if (isMasked) return;
                                const keys = [...(provCfg.api_keys || [''])];
                                keys[idx] = e.target.value;
                                setProvCfg(c => ({ ...c, api_keys: keys }));
                              }}
                              placeholder={keyPlaceholder}
                              className={`flex-1 text-xs px-3 py-2 rounded-lg border ${t.border} ${isMasked ? 'opacity-70 cursor-default' : ''} ${t.surface} ${t.textMain} ${t.placeholderMuted} outline-none focus:border-indigo-500/50 font-mono`}
                            />
                            {isMasked && (
                              <button
                                onClick={() => {
                                  const keys = [...(provCfg.api_keys || [''])];
                                  keys[idx] = '';
                                  setProvCfg(c => ({ ...c, api_keys: keys }));
                                }}
                                title="Replace this key"
                                className={`p-1.5 rounded-lg hover:bg-indigo-500/15 hover:text-indigo-400 ${t.textMuted} transition-colors cursor-pointer text-[10px] font-bold`}
                              >
                                Replace
                              </button>
                            )}
                            <button
                              onClick={() => {
                                const keys = (provCfg.api_keys || ['']).filter((_, i) => i !== idx);
                                setProvCfg(c => ({ ...c, api_keys: keys.length ? keys : [''] }));
                              }}
                              disabled={(provCfg.api_keys || []).length <= 1}
                              title="Remove this key"
                              className={`p-1.5 rounded-lg hover:bg-red-500/15 hover:text-red-400 ${t.textMuted} transition-colors cursor-pointer disabled:opacity-30`}
                            >
                              <X size={13} />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                    {(provCfg.api_keys || []).length < 10 && (
                      <button
                        onClick={() => setProvCfg(c => ({ ...c, api_keys: [...(c.api_keys || []), ''] }))}
                        className="mt-2 flex items-center gap-1.5 text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 transition-colors cursor-pointer"
                      >
                        <Plus size={12} /> Add another key ({(provCfg.api_keys || []).length}/10)
                      </button>
                    )}
                  </div>
                  );
                })()}

                {/* Ollama base URL */}
                {prov.noKey && (
                  <div>
                    <div className={`text-[10px] font-bold uppercase tracking-widest ${t.textMuted} mb-2`}>Ollama Host URL</div>
                    <input
                      type="text"
                      value={provCfg.base_url || 'http://localhost:11434'}
                      onChange={e => setProvCfg(c => ({ ...c, base_url: e.target.value }))}
                      placeholder="http://localhost:11434"
                      className={`w-full text-xs px-3 py-2 rounded-lg border ${t.border} ${t.surface} ${t.textMain} ${t.placeholderMuted} outline-none focus:border-indigo-500/50 font-mono`}
                    />
                    <p className={`mt-1.5 text-[10px] ${t.textMuted} opacity-70`}>Run <code className="font-mono bg-neutral-500/10 px-1 rounded">ollama pull llama3</code> to download a model first.</p>
                  </div>
                )}

                {/* Model Selector */}
                <div>
                  <div className={`text-[10px] font-bold uppercase tracking-widest ${t.textMuted} mb-2`}>Model</div>
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                    {prov.models.map(m => (
                      <button
                        key={m.id}
                        onClick={() => setProvCfg(c => ({ ...c, model: m.id }))}
                        title={m.desc}
                        className={`flex flex-col items-start gap-0.5 px-3 py-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                          provCfg.model === m.id && !prov.freeText
                            ? 'bg-indigo-500/12 border-indigo-500/35 text-indigo-300'
                            : `${t.surface} ${t.border} ${t.textMuted} hover:border-neutral-400/40`
                        }`}
                      >
                        <span className="text-[11px] font-bold truncate w-full">{m.label}</span>
                        <span className="text-[9px] opacity-60">{m.desc}</span>
                      </button>
                    ))}
                  </div>
                  {prov.freeText && (
                    <div className="mt-3">
                      <div className={`text-[10px] font-bold uppercase tracking-widest ${t.textMuted} mb-1.5`}>Custom model name</div>
                      <input
                        type="text"
                        value={provCfg.model || ''}
                        onChange={e => setProvCfg(c => ({ ...c, model: e.target.value }))}
                        placeholder={prov.key === 'ollama' ? 'e.g. qwen3:8b, deepseek-r1:8b, llava' : 'e.g. openai/gpt-4o, meta-llama/llama-3.3-70b-instruct'}
                        className={`w-full text-xs px-3 py-2 rounded-lg border ${t.border} ${t.surface} ${t.textMain} ${t.placeholderMuted} outline-none focus:border-indigo-500/50 font-mono`}
                      />
                      {prov.key === 'openrouter' && (
                        <p className={`mt-1 text-[10px] ${t.textMuted} opacity-60`}>Format: <code className="font-mono bg-neutral-500/10 px-1 rounded">provider/model-name</code></p>
                      )}
                    </div>
                  )}
                </div>

                {/* Visual generation note — shown for non-Gemini providers */}
                {activeTab !== 'gemini' && (
                  <div className={`flex items-start gap-2.5 px-3.5 py-3 rounded-xl border border-amber-500/25 bg-amber-500/8`}>
                    <span className="text-amber-400 text-sm leading-tight mt-0.5">⚠</span>
                    <p className={`text-[11px] ${t.textMuted} leading-relaxed`}>
                      <span className="font-bold text-amber-400">Visual generation requires a Gemini key.</span>{' '}
                      Mind maps, flashcards, and all other study visuals are generated via Gemini regardless of the active chat provider. Add a Gemini key on the Gemini tab to enable visuals.
                    </p>
                  </div>
                )}

              </div>

              {/* System Prompt — global, applies to all providers */}
              <div className={`px-6 py-4 border-t ${t.border}`}>
                <div className={`text-[10px] font-bold uppercase tracking-widest ${t.textMuted} mb-1.5`}>Custom System Prompt <span className="normal-case font-normal opacity-60 ml-1">(applies to all providers)</span></div>
                <p className={`text-[10px] ${t.textMuted} opacity-60 mb-2`}>Overrides the default study companion persona. Leave blank for default.</p>
                <textarea
                  value={settingsData.system_prompt}
                  onChange={e => setSettingsData(p => ({ ...p, system_prompt: e.target.value }))}
                  placeholder="You are a specialist in... (leave blank for default)"
                  rows={3}
                  className={`w-full text-xs px-3 py-2.5 rounded-lg border ${t.border} ${t.surface} ${t.textMain} ${t.placeholderMuted} outline-none focus:border-indigo-500/40 resize-none leading-relaxed`}
                />
              </div>

              {/* Footer */}
              <div className={`px-6 py-4 border-t ${t.border} flex items-center justify-between`}>
                <p className={`text-[10px] ${t.textMuted} opacity-60`}>Click Save to apply — no app restart needed.</p>
                <button
                  onClick={handleSaveSettings}
                  disabled={settingsSaving}
                  className="flex items-center gap-2 px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all cursor-pointer disabled:opacity-50 shadow-md"
                >
                  {settingsSaving ? (
                    <><div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Saving...</>
                  ) : settingsSaved ? (
                    <><Check size={13} /> Saved!</>
                  ) : (
                    <><Check size={13} /> Save Settings</>
                  )}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* --- About Me Modal --- */}
      {aboutOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-message">
          <div className={`w-full max-w-md rounded-2xl border ${t.border} shadow-2xl flex flex-col overflow-hidden ${t.bgSidebar} ${t.glass}`}>
            <div className={`flex items-center justify-between px-6 py-4 border-b ${t.border}`}>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center">
                  <Info size={15} className="text-indigo-400" />
                </div>
                <div>
                  <h2 className={`text-sm font-bold ${t.textMain}`}>About the Developer</h2>
                  <p className={`text-[11px] ${t.textMuted}`}>NotebookMG Companion</p>
                </div>
              </div>
              <button onClick={() => setAboutOpen(false)} title="Close" className={`p-2 rounded-lg ${t.surfaceHover} ${t.textMuted} ${t.textMainHover} cursor-pointer`}><X size={16} /></button>
            </div>
            <div className="p-6 space-y-5">
              <div className="flex flex-col items-center gap-3 text-center">
                <div className={`w-16 h-16 rounded-2xl border-2 ${t.border} ${t.surface} flex items-center justify-center shadow-lg`}>
                  <svg viewBox="8 8 84 84" width="36" height="36" fill="none" aria-hidden="true">
                    <g stroke="currentColor" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18,32 L46,45 L46,80 L18,67 Z" />
                      <path d="M82,32 L54,45 L54,80 L82,67 Z" />
                      <path d="M50,85 L50,25 L40,35 M50,25 L60,35" strokeWidth="3.8" />
                      <circle cx="50" cy="15" r="2.6" fill="currentColor" stroke="none" />
                    </g>
                  </svg>
                </div>
                <div>
                  <div className={`text-base font-bold ${t.textMain}`}>Mohamed Gomaa</div>
                  <div className={`text-[11px] ${t.textMuted} mt-0.5`}>Creator of NotebookMG Companion</div>
                </div>
              </div>
              <div className="space-y-2">
                {[
                  { icon: Code,      label: 'GitHub Repository', href: 'https://github.com/mohgomaa-art/NotebookMG', sub: 'mohgomaa-art/NotebookMG' },
                  { icon: User,      label: 'GitHub Profile',    href: 'https://github.com/mohgomaa-art',             sub: 'github.com/mohgomaa-art' },
                  { icon: Mail,      label: 'Email',             href: 'mailto:mohamelgomaa@gmail.com',               sub: 'mohamelgomaa@gmail.com' },
                  { icon: Share2,    label: 'Instagram',         href: 'https://instagram.com/moh.gomaa.art',         sub: '@moh.gomaa.art' },
                  { icon: Globe,     label: 'Facebook',          href: 'https://facebook.com/moh.gomaa.art',          sub: 'moh.gomaa.art' },
                  { icon: AtSign,    label: 'X / Twitter',       href: 'https://x.com/moh.gomaa.art',                 sub: '@moh.gomaa.art' },
                ].map(({ icon: Icon, label, href, sub }) => (
                  <button
                    key={href}
                    onClick={() => handleOpenUrl(href.startsWith('mailto') ? href : href)}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl border ${t.border} ${t.surface} ${t.surfaceHover} transition-all cursor-pointer text-left`}
                  >
                    <Icon size={15} className={t.textMuted} />
                    <div className="flex-1 min-w-0">
                      <div className={`text-[12px] font-semibold ${t.textMain}`}>{label}</div>
                      <div className={`text-[10px] ${t.textMuted} truncate`}>{sub}</div>
                    </div>
                    <ExternalLink size={11} className={`${t.textMuted} shrink-0`} />
                  </button>
                ))}
              </div>
              <p className={`text-center text-[10px] ${t.textMuted} opacity-60`}>
                Built with Tauri v2 · FastAPI · React 19 · Gemini API
              </p>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
