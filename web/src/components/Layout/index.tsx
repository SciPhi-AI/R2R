// components/Layout.tsx
import Head from 'next/head';
import React, { ReactNode } from 'react';

import styles from '@/styles/Index.module.scss';
import { MainMenu } from '@/components/shared/MainMenu';
import { SubNavigationMenu } from '@/components/shared/SubNavigationMenu';
import { Footer } from '@/components/Footer';

type Props = {
  children: ReactNode;
  localNav?: ReactNode;
  pageTitle?: string; // Optional prop for setting the page title
};

const Layout: React.FC<Props> = ({ children, localNav, pageTitle }) => {
  return (
    <div className={styles.container}>
      <Head>
        {/* Set a dynamic title if provided */}
        {pageTitle && <title>{pageTitle} | SciPhi</title>}
        {/* You can also include other page-specific meta tags, links, or scripts here */}
      </Head>
      <header className={styles.topBar}>
        <MainMenu />
      </header>
      <SubNavigationMenu />
      {children}
      <Footer />
    </div>
  );
};

export default Layout;
