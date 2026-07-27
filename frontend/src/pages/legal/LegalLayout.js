import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

export const CONTACT_EMAIL = "jules.beatcut@gmail.com";
export const COMPANY_NAME = "société FAUT";

export default function LegalLayout({ title, updated, children, testid }) {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <Navbar />
      <main className="flex-1 mx-auto w-full max-w-3xl px-5 sm:px-8 py-14" data-testid={testid}>
        <p className="font-osd text-[11px] tracking-[0.2em] text-primary mb-3">[ BEATCUT ]</p>
        <h1 className="font-display text-3xl sm:text-4xl mb-2">{title}</h1>
        {updated && <p className="text-xs text-muted-foreground mb-10 font-osd">Dernière mise à jour : {updated}</p>}
        <div className="space-y-8 text-sm leading-relaxed text-muted-foreground [&_h2]:font-display [&_h2]:text-lg [&_h2]:text-foreground [&_h2]:mb-2 [&_b]:text-foreground [&_a]:text-primary [&_a]:underline [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1">
          {children}
        </div>
      </main>
      <Footer />
    </div>
  );
}
