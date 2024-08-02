import React from 'react';

import { Message } from '@/types';

const MessageBubble: React.FC<{ message: Message; isStreaming?: boolean }> = ({
  message,
  isStreaming,
}) => {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end mb-4">
        <div className="bg-zinc-800 text-white rounded-lg p-3 max-w-xs lg:max-w-md">
          <p>{message.content}</p>
        </div>
      </div>
    );
  } else if (message.role === 'assistant') {
    return (
      <div className="flex justify-start mb-4">
        <div
          className={`bg-gray-200 rounded-lg p-3 max-w-xs lg:max-w-md ${message.isStreaming ? 'animate-pulse' : ''}`}
        >
          <p>
            {message.content}
            {message.isStreaming && (
              <span className="inline-block animate-pulse">▋</span>
            )}
          </p>
        </div>
      </div>
    );
  }
  return null;
};

export default MessageBubble;
