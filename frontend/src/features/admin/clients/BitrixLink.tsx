export function BitrixLink({ url }: { url?: string }) {
  if (!url || !/^https?:\/\//i.test(url)) return null;
  return (
    <a className="nav-link" href={url} target="_blank" rel="noopener noreferrer">
      Открыть в Битриксе
    </a>
  );
}
