import { notFound } from "next/navigation";
import { SectionContent } from "@/components/section-content";
import { Shell } from "@/components/shell";
import { navigationSections, type NavigationSection } from "@/lib/demo-data";

export const dynamic = "force-dynamic";

export function generateStaticParams() {
  return Object.keys(navigationSections).map((section) => ({ section }));
}

export default async function SectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (!(section in navigationSections)) notFound();
  return <Shell><SectionContent section={section as NavigationSection} /></Shell>;
}
