'use client';
import React, { useState } from 'react';
import RequireSession, { SessionBar } from '../../components/RequireSession';
import { ChatReply, Me, postChat } from '../../lib/api';

type Msg = { role: 'user' | 'assistant'; content: string; model?: string };

export default function ChatPage() {
  return (
    <RequireSession>
      {({ uid, me }) => <ChatInner uid={uid} me={me} />}
    </RequireSession>
  );
}

function ChatInner({ uid, me }: { uid: string; me: Me }) {
  const tenantId = me.user.tenant_id;
  const [input, setInput] = useState('');
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');

  async function send() {
    const question = input.trim();
    if (!question) return;
    setInput('');
    setWorking(true);
    setError('');
    const history = [...msgs, { role: 'user' as const, content: question }];
    setMsgs(history);
    try {
      const reply: ChatReply = await postChat(
        uid,
        tenantId,
        history.map((m) => ({ role: m.role, content: m.content })),
      );
      const cites = reply.citations.length > 0
        ? `\n\nSources: ${reply.citations.map((c) => c.txn_id || c.document_id).filter(Boolean).join(', ')}`
        : '';
      setMsgs([...history, { role: 'assistant', content: reply.answer + cites, model: reply.model }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chat failed');
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="max-w-3xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Chat - ask your books, get cited answers</h1>
        <p className="text-sm text-slate-400 mt-1">
          Answers come from your ledger tools, never invented. Try: totals, top vendors, subscriptions, duplicates, fees, flags, spend on X.
        </p>
      </div>

      <SessionBar me={me} />

      <div className="border border-slate-800 rounded p-4 space-y-3 min-h-64">
        {msgs.length === 0 ? (
          <p className="text-sm text-slate-400">Ask anything about your money - every number is cited.</p>
        ) : null}
        {msgs.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
            <div className={`inline-block max-w-full text-left p-3 rounded text-sm whitespace-pre-wrap ${m.role === 'user' ? 'bg-blue-900' : 'bg-slate-900'}`}>
              {m.content}
              {m.model ? <div className="text-xs text-slate-500 mt-1">via {m.model}</div> : null}
            </div>
          </div>
        ))}
        {working ? <p className="text-sm text-slate-400">Thinking...</p> : null}
      </div>
      <div className="flex gap-2 items-center">
        <input
          className="flex-1 p-2 bg-slate-900 border border-slate-700 rounded"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') send(); }}
          placeholder="e.g. what subscriptions do I have?"
        />
        <button onClick={send} disabled={working || !input.trim()} className="bg-blue-600 px-4 py-2 rounded disabled:opacity-50">
          Send
        </button>
      </div>

      {error ? <div className="border border-red-800 bg-red-950 p-3 rounded text-sm">{error}</div> : null}
    </main>
  );
}
