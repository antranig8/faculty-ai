type AccessPageProps = {
  searchParams: Promise<{
    error?: string;
    next?: string;
  }>;
};

export default async function AccessPage({ searchParams }: AccessPageProps) {
  const params = await searchParams;
  const next = params.next?.startsWith("/") ? params.next : "/";

  return (
    <main className="access-screen">
      <form className="access-panel" action="/api/access" method="post">
        <div>
          <p className="eyebrow">Faculty AI</p>
          <h1>Access required</h1>
        </div>
        <input type="hidden" name="next" value={next} />
        <label>
          Access code
          <input name="accessCode" type="password" autoComplete="current-password" autoFocus required />
        </label>
        {params.error ? <p className="access-error">Invalid access code.</p> : null}
        <button className="primary-button" type="submit">Continue</button>
      </form>
    </main>
  );
}
