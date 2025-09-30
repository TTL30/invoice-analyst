"use client";

interface PdfViewerProps {
  url?: string | null;
  className?: string;
}

export const PdfViewer = ({ url, className }: PdfViewerProps) => {
  if (!url) {
    return (
      <div className="card flex h-full items-center justify-center text-gray-400">
        Aucune prévisualisation disponible
      </div>
    );
  }

  return (
    <div className={`card flex h-full flex-col overflow-hidden ${className ?? ""}`}>
      <iframe src={url} className="h-full w-full" title="Facture" />
    </div>
  );
};
