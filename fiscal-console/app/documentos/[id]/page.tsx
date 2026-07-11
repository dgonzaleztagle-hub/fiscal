import { notFound } from "next/navigation";
import { DocumentDetail } from "@/components/document-detail";
import { fiscalDocument } from "@/lib/fiscal-api";

export default async function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const document = await fiscalDocument(id);
  if (!document) notFound();
  return <DocumentDetail document={document} />;
}
