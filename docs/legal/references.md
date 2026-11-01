# SA law reference index

What this is: an index of every South African law FIN_SPY already cites,
with the sections that matter and where the repo implements them.
It is a research pointer for judges and auditors, not legal advice -
see `docs/DISCLAIMER.md` s6 and have an attorney/accountant review
before charging real customers.

## Admissibility and evidence

- ECTA 25 of 2002, s15: data messages are admissible; weight turns on
  reliability of generation, storage integrity, and originator
  identification. Implemented by: SHA256 vault, hash-chain audit,
  line-ID grounding, TSA timestamps, PAdES signatures.
  See `docs/METHOD_STATEMENT.md`, `docs/DISCLAIMER.md` s2/s6,
  `docs/legal/terms.md`.
- CPA 51 of 1977, s205: subpoena route for bank statements.
  See `docs/DISCLAIMER.md` s2/s5.

## Privacy and secrecy

- POPIA 4 of 2013: s1 (bank statements are personal + financial info),
  s8-14 (minimal, safeguards, justified retention, deletion),
  s11(1) (lawful bases incl. legal proceedings), s19 (safeguards),
  s26 (prior authorisation at scale), s72 (cross-border transfers).
  Implemented by: tenant isolation, per-account download scoping,
  audit skeleton + deletion certificates, POPIA export.
  See `docs/legal/privacy.md`, `docs/METHOD_STATEMENT.md`.
- Banks Act 94 of 1990, s33: bank secrecy, overridden by court order
  or POPIA legal basis. See `docs/DISCLAIMER.md` s2.

## Company books and mixing

- Companies Act 71 of 2008: s19 (company is a separate juristic
  person), s24 (keep records 7 years), s28 (accurate accounting
  records, offences for falsification), s29-30 (fair financial
  statements), s75-77 + s22 (directors' duties, reckless trading),
  s20(9) (piercing the veil). Implemented by: private/business-only
  default for companies, mixed-as-exception flags, drawings/loan
  treatment notes. Source: CIPC `CompaniesAct71_2008.pdf`.
  See `docs/DISCLAIMER.md` s2, `docs/decisions/0003-*`.

## Tax records and deductions

- Tax Administration Act 28 of 2011: s29 (keep records 5 years from
  filing, prove trade vs private), s46 (SARS 12-month requests).
- Income Tax Act 58 of 1962: s11(a) (wholly/exclusively for trade),
  s23(a)(b) (personal living expenses disallowed).
- VAT Act 89 of 1991: s55 (tax invoices), s28 (identifiable records).
  Implemented by: retention guidance (5y tax / 7y company), auditor
  export package, apportionment fields. See `docs/DISCLAIMER.md` s2-s4.

## Forensic mandates

- Lawful bases FIN_SPY preambles accept: engagement letter, board
  resolution, divorce discovery (Uniform Rule 35), curator/insolvency
  appointment, insurance investigation, CPA s205 subpoena, FICA
  disclosure, court order, Anton Piller order - each with chain of
  custody and per-investigation isolation (tenant isolation in code).
  See `docs/DISCLAIMER.md` s5.

## Retention anchors

- Tax records 5 years, company records 7 years (confirm with your
  accountant/attorney). Legal hold blocks deletion; deletion lists
  certificate hashes. See `docs/legal/privacy.md`,
  `docs/METHOD_STATEMENT.md`.
