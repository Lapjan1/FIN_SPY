'use client';
import React, { useEffect, useState } from 'react';
import { BankAccount, fetchBankAccounts } from '../lib/api';

type Props = {
  uid: string;
  value: string;
  onChange: (acct: string) => void;
};

/** Global bank-account picker. Options: all accounts, unknown, or one
 *  account. Every data screen reads the same stored selection. */
export default function AccountSelector({ uid, value, onChange }: Props) {
  const [accounts, setAccounts] = useState<BankAccount[]>([]);

  useEffect(() => {
    fetchBankAccounts(uid)
      .then(setAccounts)
      .catch(() => setAccounts([]));
  }, [uid]);

  function label(a: BankAccount): string {
    if (!a.account_number) return `Unknown account (${a.txn_count})`;
    const bank = a.bank_name || 'Bank';
    return `${bank} ${a.account_number} (${a.txn_count})`;
  }

  return (
    <label className="space-y-1 text-sm">
      <span className="text-xs text-slate-400">Bank account</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="block p-2 bg-slate-900 border border-slate-700 rounded min-w-64"
        aria-label="Bank account"
      >
        <option value="">All accounts</option>
        {accounts.map((a) => (
          <option key={a.account_number || 'unknown'} value={a.account_number || '__unknown'}>
            {label(a)}
          </option>
        ))}
      </select>
    </label>
  );
}
