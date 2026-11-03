import React from 'react';

export default function SiteFooter() {
  return (
    <footer className="text-center py-4 text-sm text-slate-400 border-t border-slate-800 mt-8">
      <a href="/about" className="underline">About</a> ·{' '}
      <a href="/contact" className="underline">Contact</a> ·{' '}
      <a href="/privacy" className="underline">Privacy</a> ·{' '}
      <a href="/terms" className="underline">Terms</a> ·{' '}
      <a href="/refund" className="underline">Refund</a>
    </footer>
  );
}
