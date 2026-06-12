export default function Studio() {
  return (
    <div className="h-screen w-full bg-background">
      <iframe
        src="/studio.html"
        title="Studio BEATCUT"
        data-testid="studio-iframe"
        className="block w-full h-full border-0"
        allow="autoplay; clipboard-write"
      />
    </div>
  );
}
