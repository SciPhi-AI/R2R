import styles from './styles.module.scss';

interface NavItemHighlightProps {
  width: number;
  translateX: number;
  translateY: number;
}

export function NavItemHighlight({
  width,
  translateX,
  translateY,
}: NavItemHighlightProps) {
  return (
    <div
      className={styles.container}
      style={{
        width: `${width}px`,
        transform: `translate(${translateX}px, ${translateY}px)`,
      }}
    />
  );
}
