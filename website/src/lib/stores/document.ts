import { writable } from "svelte/store";
import { browser } from "$app/environment";


interface Redaction {
  page: number,
  text: string,
  rects: [number, number, number, number][]
}

export interface DocumentData {
  path: string,
  redactions: Redaction[]
}

const defaultValue: DocumentData[] = [{ path: "", redactions: [] }];
const documentData = writable(defaultValue);

if (browser) {
  const stored = localStorage.getItem("document_data");

  if (stored) {
    try {
      documentData.set(JSON.parse(stored));
    } catch (e) {
      console.error("Invalid JSON in document_data:", e);
    }
  }

  documentData.subscribe((value) => {
    localStorage.setItem("document_data", JSON.stringify(value));
  });
}

export { documentData };
