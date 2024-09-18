import React, { FC } from "react";
import Markdown from "react-markdown";
import { Message } from "@/types";

function formatMarkdownNewLines(markdown: string) {
  return markdown
    .replace(/\[(\d+)]/g, '[$1]($1)')
    .split(`"queries":`)[0]
    .replace(/\\u[\dA-F]{4}/gi, (match: string) => {
      return String.fromCharCode(parseInt(match.replace(/\\u/g, ''), 16));
    });
}

export default FC<{
  message: Message;
}> = ({ message }) =>
  <Markdown
    components={{
      h1: (props) => <h1 className="prose-heading" {...props} />,
      h2: (props) => <h2 className="prose-heading" {...props} />,
      h3: (props) => <h3 style={{ color: "black" }} {...props} />,
      h4: (props) => <h4 style={{ color: "black" }} {...props} />,
      h5: (props) => <h5 style={{ color: "black" }} {...props} />,
      h6: (props) => <h6 style={{ color: "black" }} {...props} />,
      strong: (props) => (
        <strong style={{ color: "black", fontWeight: "bold" }} {...props} />
      ),
      p: (props) => <p style={{ color: "black" }} {...props} />,
      li: (props) => <li style={{ color: "black" }} {...props} />,
      blockquote: (props) => (
        <blockquote style={{ color: "black" }} {...props} />
      ),
      em: (props) => <em style={{ color: "black" }} {...props} />,
      code: (props) => <code style={{ color: "black" }} {...props} />,
      pre: (props) => <pre style={{ color: "black" }} {...props} />
    }}
    >
    {formatMarkdownNewLines(message)}
  </Markdown>;
