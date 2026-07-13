import { ReceivedDetail } from "@/components/received-detail";

export default async function ReceivedDetailPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <ReceivedDetail documentId={id} />; }
