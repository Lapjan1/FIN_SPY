import React from 'react';
import TopNav from '../components/TopNav';
import SiteFooter from '../components/SiteFooter';

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
          <TopNav />
        </nav>
        {children}
        <SiteFooter />
      </body>
    </html>
  );
}
