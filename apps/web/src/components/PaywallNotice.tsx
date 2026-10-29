import React from 'react';

export default function PaywallNotice({ detail }: { detail?: string }) {
  return (
    <div className="border border-amber-800 bg-amber-950 p-4 rounded space-y-2">
      <h2 className="font-semibold">Trial uploads exhausted</h2>
      <p className="text-sm text-slate-300">
        {detail || 'Your free trial covered 20 uploads.'} Upgrade to keep uploading:
        Individual R149/mo for 200 uploads, SME R599/mo for 1000 uploads.
      </p>
      <a href="/account" className="inline-block bg-blue-600 px-4 py-2 rounded text-sm">
        See plans
      </a>
    </div>
  );
}
