import { ArticleRow, ExtractionResponse } from "../types/invoice";

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB limit for localStorage
const STORAGE_VERSION = 1;

export interface PersistedExtractionState {
  version: number;
  timestamp: number;
  formValues: {
    filename: string;
    supplierName: string;
    supplierAddress: string;
    invoiceNumber: string;
    invoiceDate: string;
    packageCount: number | null;
    total_ht: number;
    tva: number;
    total_ttc: number;
  };
  articles: ArticleRow[];
  result: ExtractionResponse | null;
  fileData: {
    name: string;
    type: string;
    base64: string;
  } | null;
  annotatedPdfBase64: string | null;
  activePdf: "annotated" | "original";
  hideDetails: boolean;
}

/**
 * Convert File to base64 string
 */
export async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = (reader.result as string).split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/**
 * Convert base64 string back to File
 */
export function base64ToFile(base64: string, filename: string, mimeType: string): File {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  const blob = new Blob([byteArray], { type: mimeType });
  return new File([blob], filename, { type: mimeType });
}

/**
 * Save extraction state to localStorage
 */
export async function saveExtractionState(
  userId: string,
  state: Omit<PersistedExtractionState, "version" | "timestamp" | "fileData"> & { file: File | null }
): Promise<boolean> {
  try {
    let fileData = null;

    // Convert file to base64 if it exists and is under size limit
    if (state.file) {
      if (state.file.size > MAX_FILE_SIZE) {
        console.warn("File too large to persist in localStorage");
      } else {
        const base64 = await fileToBase64(state.file);
        fileData = {
          name: state.file.name,
          type: state.file.type,
          base64,
        };
      }
    }

    const persistedState: PersistedExtractionState = {
      version: STORAGE_VERSION,
      timestamp: Date.now(),
      formValues: state.formValues,
      articles: state.articles,
      result: state.result,
      fileData,
      annotatedPdfBase64: state.annotatedPdfBase64,
      activePdf: state.activePdf,
      hideDetails: state.hideDetails,
    };

    const key = `extraction-workspace-${userId}`;
    localStorage.setItem(key, JSON.stringify(persistedState));
    return true;
  } catch (error) {
    console.error("Error saving extraction state:", error);
    return false;
  }
}

/**
 * Load extraction state from localStorage
 */
export function loadExtractionState(userId: string): PersistedExtractionState | null {
  try {
    const key = `extraction-workspace-${userId}`;
    const stored = localStorage.getItem(key);

    if (!stored) {
      return null;
    }

    const state: PersistedExtractionState = JSON.parse(stored);

    // Check version compatibility
    if (state.version !== STORAGE_VERSION) {
      console.warn("Stored extraction state version mismatch, clearing");
      clearExtractionState(userId);
      return null;
    }

    // Check if data is too old (e.g., older than 7 days)
    const maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days
    if (Date.now() - state.timestamp > maxAge) {
      console.warn("Stored extraction state too old, clearing");
      clearExtractionState(userId);
      return null;
    }

    return state;
  } catch (error) {
    console.error("Error loading extraction state:", error);
    return null;
  }
}

/**
 * Clear extraction state from localStorage
 */
export function clearExtractionState(userId: string): void {
  try {
    const key = `extraction-workspace-${userId}`;
    localStorage.removeItem(key);
  } catch (error) {
    console.error("Error clearing extraction state:", error);
  }
}

/**
 * Convert base64 PDF to blob URL
 */
export function base64ToUrl(base64: string, mimeType: string = "application/pdf"): string | null {
  try {
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: mimeType });
    return URL.createObjectURL(blob);
  } catch (error) {
    console.error("Error converting base64 to URL:", error);
    return null;
  }
}
