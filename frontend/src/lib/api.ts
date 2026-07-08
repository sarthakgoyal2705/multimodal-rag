export interface DocumentMeta {
  id: string;
  name: string;
  type: string;
  pages: number;
  chunks: number;
  images: number;
  indexed_date: string | null;
  status: string;
}

export interface Pathway {
  id: string;
  name: string;
  description: string;
  document_count: number;
  has_diagram: boolean;
  diagram_path: string | null;
}

export interface ChatChunk {
  text: string;
  source_pdf: string;
  page_number: number;
  score: number;
  modality: string;
  image_path: string | null;
}

export async function fetchDocuments(): Promise<DocumentMeta[]> {
  const res = await fetch("/api/documents");
  if (!res.ok) throw new Error("Failed to fetch documents");
  return res.json();
}

export async function uploadDocument(file: File): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  
  const res = await fetch("/api/upload", {
    method: "POST",
    body: formData,
  });
  
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}

export async function deleteDocument(docId: string): Promise<any> {
  const res = await fetch(`/api/documents/${docId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Delete failed");
  return res.json();
}

export async function fetchPathways(): Promise<Pathway[]> {
  const res = await fetch("/api/pathways");
  if (!res.ok) throw new Error("Failed to fetch pathways");
  return res.json();
}
