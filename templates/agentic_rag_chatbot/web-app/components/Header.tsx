import React, { useState } from 'react';
import { Logo } from '@/components/Logo';
import Link from 'next/link';
import Modal from '@/components/Modal';
import DocumentCard from '@/components/DocumentCard';

const Header: React.FC<{}> = ({}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const sampleDocuments = [
    {
      id: 1,
      name: 'Retrieval-Augmented Generation for Large Language Models: A Survey',
      type: 'pdf',
      url: '/data/gao-rag-survey.pdf',
    },
    {
      id: 2,
      name: 'R2R',
      type: 'html',
      url: '/data/r2r.html',
    },
    {
      id: 3,
      name: 'R2R Installation',
      type: 'html',
      url: '/data/r2r-installation.html',
    },
    {
      id: 4,
      name: 'What is Retrieval-Augmented Generation (RAG)?',
      type: 'txt',
      url: '/data/gcp-rag.txt',
    },
    {
      id: 5,
      name: 'What is retrieval-augmented generation?',
      type: 'md',
      url: '/data/ibm-rag.md',
    },
    {
      id: 6,
      name: 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks',
      type: 'pdf',
      url: '/data/lewis-rag.pdf',
    },
    {
      id: 7,
      name: 'What Is Retrieval-Augmented Generation, aka RAG?',
      type: 'html',
      url: '/data/nvidia-blog-rag.html',
    },
    {
      id: 8,
      name: 'Retrieval-augmented generation',
      type: 'html',
      url: '/data/wikipedia-rag.html',
    },
  ];

  return (
    <>
      <header className="fixed top-0 left-0 right-0 h-16 bg-header border-b border-header-border flex items-center justify-between px-4 z-10">
        <div className="flex items-center">
          <Logo width={30} height={30} />
          <Link href="https://sciphi.ai" passHref>
            <h1
              className="ml-2 text-xl font-semibold text-header-text"
              onClick={(e) => {
                e.preventDefault();
                window.location.reload();
              }}
            >
              SciPhi
            </h1>
          </Link>
        </div>
        <div className="hidden md:flex items-center space-x-2">
          <button className="px-3 py-2 bg-primary text-primary-foreground rounded-full hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary transition-colors duration-200 text-sm">
            <a
              href="https://app.sciphi.ai/deploy?view=r2r-projects"
              target="_blank"
              rel="noopener noreferrer"
            >
              Deploy It!
            </a>
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-3 py-2 bg-primary text-primary-foreground rounded-full hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary transition-colors duration-200 text-sm"
          >
            Sample Docs
          </button>
        </div>
        <div className="md:hidden">
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="text-header-text focus:outline-none"
          >
            <svg
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
        </div>
      </header>

      {/* Mobile menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden fixed top-16 left-0 right-0 bg-header border-b border-header-border p-4 z-20">
          <button className="w-full mb-4 px-4 py-2 bg-primary text-primary-foreground rounded-full hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary transition-colors duration-200">
            <a
              href="https://sciphi.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="mr-4 px-4 py-2 bg-primary text-primary-foreground rounded-full hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary transition-colors duration-200"
            >
              Deploy It
            </a>
          </button>
          <button
            onClick={() => setIsModalOpen(true)}
            className="w-full mb-4 px-4 py-2 bg-primary text-primary-foreground rounded-full hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary transition-colors duration-200"
          >
            Sample Docs
          </button>
        </div>
      )}

      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)}>
        <h2 className="text-2xl font-bold mb-4 text-foreground">
          Sample Documents
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {sampleDocuments.map((doc) => (
            <DocumentCard key={doc.id} document={doc} />
          ))}
        </div>
      </Modal>
    </>
  );
};

export default Header;
