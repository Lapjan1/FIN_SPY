'use client';
import React, { useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { documentFileOptions } from '../lib/api';

// Signature demo moment: click any number -> grid -> PDF page with highlighted bbox.
// Bboxes are in PDF points; overlay normalizes by stored page dims.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

type Props = {
  userId?: string;
  docId: string | null;
  docSha256: string;
  pageNo: number;
  pageWidth: number | null;
  pageHeight: number | null;
  lineIds: string[];
  bboxes: Array<{ line_id: string; x0: number; y0: number; x1: number; y1: number }>;
};

export default function SourceViewer({ userId = '', docId, docSha256, pageNo, pageWidth, pageHeight, lineIds, bboxes }: Props) {
  const [numPages, setNumPages] = useState(0);
  const [failed, setFailed] = useState('');
  const canScale = pageWidth != null && pageHeight != null && pageWidth > 0 && pageHeight > 0;

  if (!docId) {
    return (
      <div className="border rounded p-4 bg-slate-900 text-slate-400 text-sm">
        No source document linked to this transaction yet.
      </div>
    );
  }

  return (
    <div className="border rounded p-2 bg-slate-900 text-slate-100">
      <div className="text-xs opacity-70">
        Doc: {docSha256.slice(0, 12)}... Page: {pageNo}{numPages ? ` of ${numPages}` : ''} Lines: {lineIds.join(', ')}
        {!canScale && ' (page dims missing - overlay scaled to page, approximate)'}
      </div>
      <div className="mt-2 relative inline-block max-w-full overflow-auto">
        <Document
          file={documentFileOptions(userId, docId)}
          onLoadSuccess={({ numPages: n }: { numPages: number }) => setNumPages(n)}
          onLoadError={(e: Error) => setFailed(e.message)}
          loading={<div className="text-sm p-8">Loading PDF...</div>}
        >
          <Page pageNumber={pageNo} width={640} renderTextLayer renderAnnotationLayer={false} />
        </Document>
        {failed ? (
          <div className="text-sm text-red-300 p-4">PDF failed to load: {failed}</div>
        ) : (
          <div className="absolute inset-0 pointer-events-none">
            {bboxes.map((b) => {
              const w = pageWidth || 595;
              const h = pageHeight || 842;
              return (
                <div
                  key={b.line_id}
                  title={b.line_id}
                  className="absolute border-2 border-yellow-400 bg-yellow-400/20"
                  style={{
                    left: `${(b.x0 / w) * 100}%`,
                    top: `${(b.y0 / h) * 100}%`,
                    width: `${Math.max(((b.x1 - b.x0) / w) * 100, 1)}%`,
                    height: `${Math.max(((b.y1 - b.y0) / h) * 100, 0.8)}%`,
                  }}
                />
              );
            })}
          </div>
        )}
      </div>
      <div className="text-xs mt-1 opacity-70">Footer: report page {pageNo} hash prefix {docSha256.slice(0, 8)} - traceability verified</div>
    </div>
  );
}
