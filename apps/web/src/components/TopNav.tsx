import React from 'react';
import SessionNav from './SessionNav';

export default function TopNav() {
  return (
    <div className="flex gap-4 text-sm items-center">
      <a href="/dashboard">Dashboard</a>
      <a href="/transactions">Transactions</a>
      <a href="/upload">Upload</a>
      <a href="/inbox">Inbox</a>
      <a href="/chat">Chat</a>
      <a href="/review">Review</a>
      <a href="/books">Books</a>
      <a href="/debt">Debt</a>
      <a href="/reports">Reports</a>
      <a href="/help">Help</a>
      <SessionNav />
      <a href="/account" className="bg-blue-600 px-3 py-1 rounded">Account</a>
    </div>
  );
}
