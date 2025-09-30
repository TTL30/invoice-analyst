"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";

interface PdfDropzoneProps {
  onFileSelected: (file: File | null) => void;
  file?: File | null;
}

export const PdfDropzone = ({ onFileSelected, file }: PdfDropzoneProps) => {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onFileSelected(acceptedFiles[0]);
      }
    },
    [onFileSelected],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
  });

  return (
    <div
      {...getRootProps()}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-16 text-center transition ${
        isDragActive ? "border-teal-600 bg-teal-50" : "border-gray-300 bg-white"
      }`}
    >
      <input {...getInputProps()} />
      <p className="text-base font-semibold text-gray-900">
        {file ? file.name : "Déposez votre PDF ici ou cliquez pour sélectionner"}
      </p>
      <p className="mt-2 text-sm text-gray-600">Format PDF uniquement • Taille maximale 15 Mo</p>
    </div>
  );
};
