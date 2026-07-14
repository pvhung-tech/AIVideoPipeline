interface FoundationPageProps {
  title: string;
  description: string;
}

export function FoundationPage({
  title,
  description,
}: FoundationPageProps) {
  return (
    <section className="panelGrid" aria-label={`${title} workspace`}>
      <article className="panel wide">
        <h2>{title}</h2>
        <p>{description}</p>
      </article>
    </section>
  );
}
