import React, { useState } from 'react';
import { Logo } from '@/components/Logo';
import Link from 'next/link';
import Modal from '@/components/Modal';
import DocumentCard from '@/components/DocumentCard';

interface HeaderProps {
  onLogoClick: () => void;
}

const Header: React.FC<HeaderProps> = ({ onLogoClick }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <>
      <header className="fixed top-0 left-0 right-0 h-16 bg-header border-b border-header-border flex items-center justify-between px-4 z-10">
        <div className="flex items-center">
          <Logo width={60} height={60} onClick={onLogoClick} />
          <Link href="/" passHref>
            <h1
              className="ml-2 text-2xl font-semibold text-header-text cursor-pointer"
              onClick={onLogoClick}
            >
              R2R - YC S24 GraphRAG Agent
            </h1>
          </Link>
        </div>
        <div className="hidden md:flex items-center space-x-2"></div>
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
    </>
  );
};

export default Header;
