import ReactMarkdown from "react-markdown";

// AI output is untrusted text. Keep the supported Markdown deliberately small:
// no raw HTML, links, images, embeds, or executable content.
const ELEMENTS = ["h1", "h2", "h3", "h4", "p", "strong", "em", "ul", "ol", "li", "br", "blockquote", "code", "hr"];

const components = {
  h1: ({ children }) => <h2 className="pt-3 text-lg font-bold text-white first:pt-0">{children}</h2>,
  h2: ({ children }) => <h3 className="pt-3 text-base font-semibold text-white first:pt-0">{children}</h3>,
  h3: ({ children }) => <h3 className="pt-3 text-sm font-semibold uppercase tracking-wide text-emerald-400 first:pt-0">{children}</h3>,
  h4: ({ children }) => <h4 className="pt-2 font-semibold text-slate-100">{children}</h4>,
  p: ({ children }) => <p className="whitespace-pre-line leading-relaxed">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-slate-100">{children}</strong>,
  em: ({ children }) => <em className="text-slate-200">{children}</em>,
  ul: ({ children }) => <ul className="list-outside list-disc space-y-1 pl-5 marker:text-emerald-400">{children}</ul>,
  ol: ({ children }) => <ol className="list-outside list-decimal space-y-1 pl-5 marker:font-semibold marker:text-emerald-400">{children}</ol>,
  li: ({ children }) => <li className="pl-0.5 leading-relaxed">{children}</li>,
  blockquote: ({ children }) => <blockquote className="border-l-2 border-emerald-500/50 pl-3 text-slate-300">{children}</blockquote>,
  code: ({ children }) => <code className="rounded bg-slate-800 px-1 py-0.5 text-xs text-slate-100">{children}</code>,
  hr: () => <hr className="border-slate-700" />,
};

const sectionHeadings = (text) => String(text || "")
  .replace(/\r\n?/g, "\n")
  .replace(/^[ \t]*\*\*([A-Z][A-Z0-9 \t/&(),.-]{2,}):?\*\*[ \t]*$/gm,
    (_, title) => `### ${title.trim().replace(/:$/, "")}`);

export function AiMarkdown({ text, className = "" }) {
  return <div data-testid="ai-markdown" className={`space-y-3 break-words text-sm leading-relaxed text-slate-200 ${className}`}>
    <ReactMarkdown allowedElements={ELEMENTS} skipHtml components={components}>
      {sectionHeadings(text)}
    </ReactMarkdown>
  </div>;
}
