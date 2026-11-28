import styles from "./FacultyQuestion.module.css";

export function ProfessorCutout() {
  return (
    <div className={styles.professor} aria-hidden="true">
      <span className={styles.coat} />
      <span className={styles.lapels} />
      <span className={styles.neck} />
      <span className={styles.hair} />
      <span className={styles.face} />
      <span className={styles.fringe} />
      <span className={styles.glasses} />
      <span className={styles.mouth} />
    </div>
  );
}
