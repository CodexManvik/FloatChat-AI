import type { Metadata } from "next";
import { Chat } from "@/components/chat";
import { getStats } from "@/lib/api";
import { formatDate } from "@/lib/format";

export const metadata: Metadata = {
  title: "Ask",
  description: "Ask questions about Argo ocean-float data and watch every step of the answer.",
};

export default async function ChatPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q } = await searchParams;
  let coverage = "Argo floats in the Indian Ocean, last 12 months. Answers can be wrong; the run log shows how each was made.";
  try {
    const stats = await getStats();
    coverage = `Argo floats in the Indian Ocean, ${formatDate(stats.start_date)} to ${formatDate(stats.end_date)}. The run log shows how each answer was made.`;
  } catch {
    // keep the generic line if the API is asleep
  }
  return <Chat key={q ?? ""} initialQuestion={q} coverage={coverage} />;
}
