import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** The model's answer (Markdown). Raw HTML is never rendered. */
export function AnswerMarkdown({ text, streaming }: { text: string; streaming?: boolean }) {
  return (
    <div className={`answer-md text-[15px] ${streaming ? "is-streaming" : ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}
