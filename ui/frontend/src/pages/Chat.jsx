import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2 } from 'lucide-react';
import { api } from '../api';

const BOT_NAME = 'Aivex';

// Minimal markdown → JSX: bold, tables, bullet lists
function MdText({ text }) {
  if (!text) return null;

  const lines = text.split('\n');
  const elements = [];
  let tableRows = [];
  let inTable = false;

  const flushTable = () => {
    if (!tableRows.length) return;
    const [header, , ...body] = tableRows;
    const cols = header.split('|').map(c => c.trim()).filter(Boolean);
    elements.push(
      <div key={elements.length} className="overflow-x-auto my-1">
        <table className="text-xs border-collapse w-full">
          <thead>
            <tr>{cols.map((c, i) => <th key={i} className="border border-app px-2 py-1 bg-surface2 text-left font-semibold">{renderInline(c)}</th>)}</tr>
          </thead>
          <tbody>
            {body.map((row, ri) => {
              const cells = row.split('|').map(c => c.trim()).filter(Boolean);
              return <tr key={ri}>{cells.map((c, ci) => <td key={ci} className="border border-app px-2 py-1">{renderInline(c)}</td>)}</tr>;
            })}
          </tbody>
        </table>
      </div>
    );
    tableRows = [];
    inTable = false;
  };

  const renderInline = (s) => {
    const parts = s.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((p, i) => p.startsWith('**') && p.endsWith('**')
      ? <strong key={i}>{p.slice(2, -2)}</strong> : p);
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.includes('|') && line.trim().startsWith('|')) {
      inTable = true;
      tableRows.push(line);
      continue;
    }
    if (inTable) flushTable();

    if (!line.trim()) { elements.push(<br key={i} />); continue; }
    if (line.startsWith('- ') || line.startsWith('• ')) {
      elements.push(<div key={i} className="ml-3">• {renderInline(line.slice(2))}</div>);
    } else {
      elements.push(<div key={i}>{renderInline(line)}</div>);
    }
  }
  if (inTable) flushTable();
  return <div className="space-y-0.5">{elements}</div>;
}

const BOT_NAME = 'Aivex';

const SUGGESTIONS = [
  'Is the backend service running on my app server?',
  'What incidents happened on my servers in the last 3 days?',
  'What are the top AWS services by cost this week?',
  'Are there any idle or wasted resources in my account?',
  'Any open security groups or public S3 buckets?',
];

const HINT = `💡 Tip — for accurate answers include:
  • Server / host name
  • Instance ID (e.g. "i-0abc1234...")
  • AWS account name or ID (e.g. "Aeonx Sandbox" or "719395381450")
  • Service name (e.g. "backend", "database", "Bedrock")`;

export default function Chat({ initialQuestion = '', initialContext = {} }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: `Hi, I'm ${BOT_NAME} — AeonX's infrastructure AI. Ask me about service health, recent incidents, metrics, or request an action.\n\n${HINT}` }
  ]);
  const [input, setInput] = useState(initialQuestion);
  const [loading, setLoading] = useState(false);
  const [context] = useState(initialContext);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  // Auto-send if launched with a pre-filled question (from ApprovalDetail)
  useEffect(() => {
    if (initialQuestion) send(initialQuestion);
  }, []); // eslint-disable-line

  async function send(question) {
    const q = (question || input).trim();
    if (!q || loading) return;
    setInput('');
    setMessages(m => [...m, { role: 'user', text: q }]);
    setLoading(true);
    try {
      const res = await api.chat(q, context);
      const toolsNote = res.tools_used?.length
        ? `\n\n— Tools: ${res.tools_used.join(', ')}` : '';
      const approvalNote = res.approval_id
        ? `\n\n✅ Approval queued — check the Approvals tab.` : '';
      setMessages(m => [...m, {
        role: 'assistant',
        text: res.answer + approvalNote,
        meta: toolsNote,
        tools: res.tools_used,
      }]);
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', text: `Error: ${e.message}`, error: true }]);
    }
    setLoading(false);
  }

  return (
    <div className="flex flex-col h-full max-w-3xl mx-auto px-4 py-6">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center">
          <Bot size={16} className="text-white" />
        </div>
        <div>
          <h1 className="text-base font-bold leading-none">{BOT_NAME}</h1>
          <p className="text-xs text-muted mt-0.5">AeonX Infrastructure AI</p>
        </div>
      </div>

      {/* Message thread */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0">
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
              m.role === 'user' ? 'bg-blue-500' : 'bg-surface border border-app'}`}>
              {m.role === 'user'
                ? <User size={14} className="text-white" />
                : <Bot size={14} className="text-muted" />}
            </div>
            <div className="flex flex-col gap-1 max-w-[80%]">
              <div className={`rounded-xl px-4 py-2.5 text-sm ${
                m.role === 'user'
                  ? 'bg-blue-500 text-white rounded-tr-none whitespace-pre-wrap'
                  : m.error
                    ? 'bg-red-50 text-red-700 border border-red-200 rounded-tl-none whitespace-pre-wrap'
                    : 'bg-surface border border-app rounded-tl-none'
              }`}>{m.role === 'user' || m.error ? m.text : <MdText text={m.text} />}</div>
              {m.meta && (
                <span className="text-[10px] text-muted px-1">{m.meta}</span>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-surface border border-app flex items-center justify-center">
              <Bot size={14} className="text-muted" />
            </div>
            <div className="bg-surface border border-app rounded-xl rounded-tl-none px-4 py-2.5">
              <Loader2 size={16} className="animate-spin text-muted" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions (only on first load, no initial context) */}
      {messages.length === 1 && !initialQuestion && (
        <div className="flex flex-wrap gap-2 mb-3">
          {SUGGESTIONS.map((s, i) => (
            <button key={i} onClick={() => send(s)}
              className="text-xs px-3 py-1.5 bg-surface border border-app rounded-full hover:border-blue-400 text-muted hover:text-primary transition-colors text-left">
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2">
        <input
          className="flex-1 bg-surface border border-app rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-400 transition-colors"
          placeholder={`Ask ${BOT_NAME} — include host name, instance ID, account for best results…`}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          disabled={loading}
          autoFocus={!!initialQuestion}
        />
        <button onClick={() => send()} disabled={!input.trim() || loading}
          className="px-4 py-2.5 bg-blue-500 hover:bg-blue-600 disabled:opacity-40 text-white rounded-lg transition-colors">
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
