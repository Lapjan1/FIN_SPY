import React from 'react';
import SessionNav from '../components/SessionNav';

export const metadata = {
  title: 'FIN_SPY - Financial Surveillance & Peak Insights',
  description: 'Upload any SA bank PDF, every number traces to exact bbox SHA256 vault + hash-chain audit, dynamic books, leak spy, KPIs + debt snowball/avalanche, built with Meta Muse',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body className="bg-slate-950 text-slate-100 min-h-screen">
        <nav className="border-b border-slate-800 p-4 flex justify-between items-center">
          <a href="/" className="font-bold text-xl">FIN_SPY</a>
          <div className="flex gap-4 text-sm">
            <a href="/dashboard">Dashboard</a>
            <a href="/transactions">Transactions</a>
            <a href="/upload">Upload</a>
            <a href="/inbox">Inbox</a>
            <a href="/chat">Chat</a>
            <a href="/review">Review</a>
            <a href="/help">Help</a>
            <a href="/privacy">Privacy</a>
            <a href="/terms">Terms</a>
            <a href="/refund">Refund</a>
            <SessionNav />
            <a href="/account" className="bg-blue-600 px-3 py-1 rounded">Account</a>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
