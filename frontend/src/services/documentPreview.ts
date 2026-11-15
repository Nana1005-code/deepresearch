export function documentPreviewUrl(identifier: string): string {
  const url = new URL(window.location.href);
  url.search = "";
  url.hash = "";
  url.searchParams.set("documentPreview", identifier);
  return url.href;
}

export function documentOriginalUrl(identifier: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
  return `${base}/documents/${encodeURIComponent(identifier)}/original`;
}

// Reserve the tab during the file-selection gesture, before awaiting the upload.
export function reserveDocumentPreview(): Window | null {
  const tab = window.open(documentPreviewUrl("loading"), "_blank");
  if (tab) tab.opener = null;
  return tab;
}
