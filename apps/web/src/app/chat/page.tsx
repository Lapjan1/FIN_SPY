'use client';
import React, { useEffect, useState } from 'react';
import { ChatReply, fetchMe, postChat } from '../../lib/api';

type Msg = { role: 'user' | 'assistant'; content: string; model?: string };

export default function ChatPage() {
  const [userId, setUserId] = useState('');
  const [tenantId, setTenantId] = useState('');
  const [input, setInput] = useState('');
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const saved = typeof window !== 'undefined' ? window.localStorage.getItem('finspy-user-id') : '';
    if (saved) {
      setUserId(saved);
      fetchMe(saved).then(
        (me) => setTenantId(me.user.tenant_id),
        () => setTenantId(''),
      );
    }
  }, []);

  async function connect() {
    if (!userId) {
      setError('Enter your user id first (see Account page after login).');
      return;
    }
    setError('');
    try {
      window.localStorage.setItem('finspy-user-id', userId);
      const me = await fetchMe(userId);
      setTenantId(me.user.tenant_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Connect failed');
    }
  }

  async function send() {
    const question = input.trim();
    if (!question || !tenantId) return;
    setInput('');
    setWorking(true);
    setError('');
    const history = [...msgs, { role: 'user' as const, content: question }];
    setMsgs(history);
    try {
      const reply: ChatReply = await postChat(
        userId,
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

      {!tenantId ? (
        <div className="flex gap-2 items-center">
          <input
            className="flex-1 p-2 bg-slate-900 border border-slate-700 rounded"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="user id (X-User-Id)"
          />
          <button onClick={connect} className="bg-blue-600 px-4 py-2 rounded">Connect</button>
        </div>
      ) : (
        <>
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
        </>
      )}

      {error ? <div className="border border-red-800 bg-red-950 p-3 rounded text-sm">{error}</div> : null}
    </main>
  );
}
