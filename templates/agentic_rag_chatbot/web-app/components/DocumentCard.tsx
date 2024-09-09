import React, { useState } from 'react';
import Modal from './Modal';

interface Document {
  id: number;
  name: string;
  type: string;
  url: string;
}

interface DocumentCardProps {
  document: Document;
}

const DocumentCard: React.FC<DocumentCardProps> = ({ document }) => {
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  const renderPreview = () => {
    switch (document.type) {
      case 'pdf':
      case 'txt':
      case 'md':
      case 'html':
        return <iframe src={document.url} className="w-full h-full border-0" />;
      default:
        return <p>Preview not available for this file type.</p>;
    }
  };

  return (
    <>
      <div className="border border-muted rounded-lg p-4 bg-background text-foreground h-full flex flex-col">
        <div className="flex-grow">
          <h3 className="text-lg font-semibold mb-2 line-clamp-3">
            {document.name}
          </h3>
          <p className="text-sm text-muted-foreground mb-4">
            Type: {document.type}
          </p>
        </div>
        <button
          onClick={() => setIsPreviewOpen(true)}
          className="bg-primary text-primary-foreground px-4 py-2 rounded-full hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary transition-colors duration-200 w-full mt-auto"
        >
          Preview
        </button>
      </div>

      <Modal isOpen={isPreviewOpen} onClose={() => setIsPreviewOpen(false)}>
        <h2 className="text-2xl font-bold mb-4 text-foreground">
          {document.name}
        </h2>
        <div className="h-[calc(100%-4rem)]">{renderPreview()}</div>
      </Modal>
    </>
  );
};

export default DocumentCard;
