import styles from './styles.module.scss';

interface NavItemHighlightProps {
  width: number;
  translateX: number;
}

export function NavItemHighlight({ width, translateX }: NavItemHighlightProps) {
  return (
    <div
      className={styles.container}
      style={{
        width: `${width}px`,
        transform: `translateX(${translateX}px)`,
      }}
    />
  );
}
