import styles from './styles.module.scss';

export function ProjectHeader() {
  return (
    <div className={styles.container}>
      <button className={styles.newProjectButton}>New Pipeline</button>
    </div>
  );
}
