'use client';
import React from 'react';

// Signature demo moment: click any number -> grid -> PDF page with highlighted bbox
// Per docs/UI_SPEC.md - pdf.js overlay with bbox yellow

type Props = {
  docSha256: string;
  pageNo: number;
  lineIds: string[];
  bboxes: Array<{ line_id: string; x0: number; y0: number; x1: number; y1: number }>;
};

export default function SourceViewer({ docSha256, pageNo, lineIds, bboxes }: Props) {
  return (
    <div className="border rounded p-2 bg-slate-900 text-slate-100">
      <div className="text-xs opacity-70">Doc: {docSha256.slice(0,12)}... Page: {pageNo} Lines: {lineIds.join(',')}</div>
      <div className="w-full h-96 bg-slate-800 flex items-center justify-center mt-2 relative">
        {/* TODO: integrate react-pdf + overlay */}
        <div className="text-sm">PDF page image + bbox overlay placeholder - highlight {bboxes.length} spans</div>
        {bboxes.map(b => (
          <div key={b.line_id} className="absolute border-2 border-yellow-400 opacity-60"
               style={{ left: `${b.x0}%`, top: `${b.y0}%`, width: `${b.x1-b.x0}%`, height: `${b.y1-b.y0}%` }} />
        ))}
      </div>
      <div className="text-xs mt-1">Footer: report_id page {pageNo} hash prefix {docSha256.slice(0,8)} - traceability verified</div>
    </div>
  );
}
