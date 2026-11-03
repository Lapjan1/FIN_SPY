'use client';
import React, { useState } from 'react';
import RequireSession, { SessionBar } from '../../components/RequireSession';
import { FeedbackInput, Me, submitFeedback } from '../../lib/api';

const inputCls = 'w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-slate-100';
const labelCls = 'block text-sm font-semibold text-slate-200 mb-1';

export default function ContactPage() {
  return (
    <RequireSession>
      {({ uid, me }) => <ContactInner uid={uid} me={me} />}
    </RequireSession>
  );
}

function ContactInner({ uid, me }: { uid: string; me: Me }) {
  const [category, setCategory] = useState<FeedbackInput['category']>('bug');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [documentId, setDocumentId] = useState('');
  const [sending, setSending] = useState(false);
  const [sentId, setSentId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    setSending(true);
    setError(null);
    try {
      const res = await submitFeedback(uid, {
        category,
        subject: subject.trim(),
        message: message.trim(),
        document_id: documentId.trim() || undefined,
        page_url: typeof window !== 'undefined' ? window.location.pathname : undefined,
      });
      setSentId(res.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Send failed');
    } finally {
      setSending(false);
    }
  }

  const valid = subject.trim().length >= 1 && subject.trim().length <= 120
    && message.trim().length >= 10 && message.trim().length <= 4000;

  return (
    <main className="max-w-2xl mx-auto p-6 space-y-6">
      <SessionBar me={me} />
      <div>
        <h1 className="text-2xl font-bold">Contact us - report a bug or ask a question</h1>
        <p className="text-sm text-slate-400 mt-1">
          Hit something we have not programmed yet, or a layout that extracts wrong?
          Tell us here. Please do not paste account numbers or full statements -
          a document ID from the Inbox is enough for us to find it.
        </p>
      </div>

      {sentId ? (
        <div className="border border-green-800 bg-green-950 rounded p-4 text-sm text-green-200">
          Received - reference <span className="font-mono">{sentId}</span>. We read every
          report and reply to your account email.
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <label className={labelCls} htmlFor="fb-category">What is this about?</label>
            <select
              id="fb-category"
              className={inputCls}
              value={category}
              onChange={(e) => setCategory(e.target.value as FeedbackInput['category'])}
            >
              <option value="bug">Bug - something broke or looks wrong</option>
              <option value="bank-layout">Bank layout - my statement extracts badly</option>
              <option value="question">Question - how do I...?</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label className={labelCls} htmlFor="fb-subject">Subject</label>
            <input
              id="fb-subject"
              className={inputCls}
              value={subject}
              maxLength={120}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Rows missing after upload"
            />
          </div>
          <div>
            <label className={labelCls} htmlFor="fb-doc">Document ID (optional)</label>
            <input
              id="fb-doc"
              className={inputCls}
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              placeholder="From the Inbox, if this is about one statement"
            />
          </div>
          <div>
            <label className={labelCls} htmlFor="fb-message">Message (10-4000 characters)</label>
            <textarea
              id="fb-message"
              className={`${inputCls} min-h-32`}
              rows={6}
              value={message}
              maxLength={4000}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="What happened, what you expected, which bank and page if relevant"
            />
          </div>
          {error ? (
            <p className="text-sm text-red-300" role="alert">{error}</p>
          ) : null}
          <button
            onClick={send}
            disabled={sending || !valid}
            className="bg-blue-600 px-4 py-2 rounded disabled:opacity-50"
          >
            {sending ? 'Sending' : 'Send report'}
          </button>
          <p className="text-xs text-slate-500">Max 5 reports per hour. Abuse gets accounts suspended per the Terms.</p>
        </div>
      )}

    </main>
  );
}
