// import React, { useEffect, useState, lazy, Suspense } from 'react';

// import { IntegrationCard } from '@/components/Paused/IntegrationCard';
// import Layout from '@/components/Layout';
// import { Separator } from '@/components/ui/separator';
// import ProvidersNavMenu from '@/components/shared/ProvidersNavMenu';
// import { useFetchProviders } from '@/hooks/useFetchProviders';
// import { useModal } from '@/hooks/useModal';

// const SecretsModal = lazy(() => import('@/components/SecretsModal'));

// import styles from '@/styles/Index.module.scss';
// import { Provider } from '../../types';

// export default function Integrations() {
//   const { isOpen, toggleModal, secretProvider, handleSecretProvider } =
//     useModal();
//   const [integrationProviders, setIntegrationProvider] = useState<Provider[]>(
//     []
//   );

//   const { allProviders } = useFetchProviders();

//   return (
//     <Layout>
//       <main className={styles.main}>
//         <ProvidersNavMenu />
//         <Separator />

//         <div className={`${styles.gridView} ${styles.column}`}>
//           {Array.isArray(allProviders)
//             ? allProviders
//                 ?.filter((x) => {
//                   return x?.type == 'integration';
//                 })
//                 .map((provider) => (
//                   <IntegrationCard
//                     provider={provider}
//                     key={provider.id}
//                     onClick={() => handleSecretProvider(provider)}
//                   />
//                 ))
//             : null}
//           <Suspense fallback={<div>Loading...</div>}>
//             {isOpen && secretProvider && (
//               <SecretsModal
//                 isOpen={isOpen}
//                 toggleModal={toggleModal}
//                 provider={secretProvider}
//               />
//             )}
//           </Suspense>
//         </div>
//         <div className={styles.datasetHeaderRightAlign}>
//           {/* <PanelHeader text="Add Integration" /> */}
//         </div>
//       </main>
//     </Layout>
//   );
// }
