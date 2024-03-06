import React from 'react';
import { FiExternalLink } from 'react-icons/fi';

import styles from './styles.module.scss';
import { Pipeline } from '../../types';


// interface ModalProps {
//   isOpen: boolean;
//   onClose: () => void;
//   children: React.ReactNode;
// }

// const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children }) => {
//   const modalRef = useRef<HTMLDivElement>(null);

//   useEffect(() => {
//     const handleOutsideClick = (event: MouseEvent) => {
//       if (modalRef.current && !modalRef.current.contains(event.target as Node)) {
//         onClose();
//       }
//     };

//     if (isOpen) {
//       document.addEventListener('mousedown', handleOutsideClick);
//     }

//     return () => {
//       document.removeEventListener('mousedown', handleOutsideClick);
//     };
//   }, [isOpen, onClose]);

//   if (!isOpen) return null;

//   return (
//     <div className={styles.modalOverlay}>
//       <div className={styles.modalContent} ref={modalRef}>
//         {children}
//       </div>
//     </div>
//   );
// };


interface CardProps {
  pipeline: Pipeline;
}

function Card({ pipeline }: CardProps) {
  // const [isModalOpen, setIsModalOpen] = useState(false);

  // console.log('isModalOpen = ', isModalOpen)
  // const handleCardClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
  //   e.preventDefault(); // Prevent the default anchor action
  //   setIsModalOpen(true); // Open the modal
  // };
  // useEffect(() => {
  //   console.log('Modal state updated, isModalOpen = ', isModalOpen);
  // }, [isModalOpen]); // This will log whenever isModalOpen changes
  // const handleCloseModal = () => {
  //   console.log('handleCloseModal called');
  //   setIsModalOpen(false);
  // };


  return (
    <a href="#" className={styles.container}  >
      <div className={styles.cardHeader}>
        <div className={styles.hoverRedirectIcon}>
          <FiExternalLink size="16" />
        </div>


        <div className={styles.projectInfo}>
          <p className={styles.cardTitle}>Pipeline:</p>
          <strong className={styles.cardProjectTitle}>{pipeline.name}</strong>
          {pipeline.status == 'finished' ? (
            <>
              <p className={styles.cardTitle}>Remote:</p>
              <p className={styles.cardAddress}>{pipeline.github_url}</p>

              <p className={styles.cardTitle}>Deployment:</p>
              <p className={styles.cardAddress}>{pipeline.deployment.uri}</p>
            </>
          ) : (
            <>
              <p className={styles.cardTitle}>Status:</p>
              <p className={styles.cardAddress}>{pipeline.status}</p>
            </>
          )}
        </div>
      </div>
    </a>
  );
}

export { Card };
