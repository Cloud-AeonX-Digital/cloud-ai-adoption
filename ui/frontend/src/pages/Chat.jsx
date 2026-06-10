import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2 } from 'lucide-react';
import { api } from '../api';

const SUGGESTIONS = [
  'Is cmt-backend running on Cloud Monitoring Tool?',
  'What happened to Cloud Monitoring Tool in the last 3 days?',
  'What is the CPU utilization on i-00902943a502495a5?',
  'Show me recent postgresql incidents',
];

export default function Chat() {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Hi! Ask me anything about your infrastructure — service status, recent incidents, metrics, or request an action.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  async function send(question) {
    const q = (question || input).trim();
    if (!q || loading) return;
    setInput('');
    setMessages(m => [...m, { role: 'user', text: q }]);
    setLoading(true);
    try {
      const res = await api.chat(q);
      const toolsNote = res.tools_used?.length
        ? `\n\n_Tools used: ${res.tools_used.join(', ')}_` : '';
      const approvalNote = res.approval_id
        ? `\n\n✅ Approval created — check the Approvals tab.` : '';
      setMessages(m => [...m, { role: 'assistant', text: res.answer + toolsNote + approvalNote, tools: res.tools_used }]);
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', text: `Error: ${e.message}`, error: true }]);
    }
    setLoading(false);
  }

  return (
    <div className="flex flex-col h-full max-w-3xl mx-auto px-4 py-6">
      <h1 className="text-xl font-semibold mb-4">Infrastructure Assistant</h1>

      {/* Message thread */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0">
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
              m.role === 'user' ? 'bg-blue-500' : 'bg-surface border border-app'}`}>
              {m.role === 'user' ? <User size={14} className="text-white" /> : <Bot size={14} className="text-muted" />}
            </div>
            <div className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
              m.role === 'user'
                ? 'bg-blue-500 text-white rounded-tr-none'
                : m.error
                  ? 'bg-red-50 text-red-700 border border-red-200 rounded-tl-none'
                  : 'bg-surface border border-app rounded-tl-none'
            }`}>
              {m.text}
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

      {/* Suggestions (only when empty) */}
      {messages.length === 1 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {SUGGESTIONS.map((s, i) => (
            <button key={i} onClick={() => send(s)}
              className="text-xs px-3 py-1.5 bg-surface border border-app rounded-full hover:border-blue-400 text-muted hover:text-primary transition-colors">
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2">
        <input
          className="flex-1 bg-surface border border-app rounded-lg px-4 py-2.5 text-sm outline-none focus:border-blue-400 transition-colors"
          placeholder="Ask about any host, service, metric, or incident…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          disabled={loading}
        />
        <button onClick={() => send()} disabled={!input.trim() || loading}
          className="px-4 py-2.5 bg-blue-500 hover:bg-blue-600 disabled:opacity-40 text-white rounded-lg transition-colors">
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
