interface JsonBlockProps {
  title: string
  value: unknown
}

export function JsonBlock({ title, value }: JsonBlockProps) {
  return (
    <section className="card">
      <h2>{title}</h2>
      <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>
    </section>
  )
}
