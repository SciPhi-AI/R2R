import { HiOutlineSearch } from 'react-icons/hi';

import styles from './styles.module.scss';

function SearchBar() {
  return (
    <div className={styles.container}>
      <HiOutlineSearch size="18" className={styles.iconSearch} />

      <input
        placeholder="Search..."
        type="text"
        className={styles.searchInput}
      />
    </div>
  );
}

export { SearchBar };
