import { Card, CardContent, CardHeader, CardTitle, PageHeader } from "@/components/ui";
import { SystemCheck } from "@/components/system-check";

const Item = ({ t, children }: { t: string; children: React.ReactNode }) => <li><b className="text-foreground">{t}</b> <span className="text-muted-foreground">{children}</span></li>;

export default function About() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="About ClipForge AI" subtitle="A free, local tool that turns long videos into Shorts and Reels with word-timed captions. No watermark, no subscription, no cloud." />
      <SystemCheck />
      <Card><CardHeader><CardTitle>What runs where</CardTitle></CardHeader><CardContent><ul className="space-y-2 text-sm">
        <Item t="FFmpeg">renders every export (layout, enhancement, burned-in captions, H.264/H.265).</Item>
        <Item t="faster-whisper">transcribes speech with word timestamps, English and Hindi, on your CPU.</Item>
        <Item t="OpenCV">detects faces and estimates the active speaker from mouth movement for smart framing.</Item>
        <Item t="Built-in analyzer">scores moments by hook, emotion, information, engagement, standalone context and ending. Works offline.</Item>
        <Item t="Gemini / Ollama (optional)">improve ranking and copy. Gemini uses your own key and its free tier has rate limits that Google sets and may change.</Item>
        <Item t="SQLite + local files">store projects in the <code>data/</code> folder next to the app.</Item></ul></CardContent></Card>
      <Card><CardHeader><CardTitle>Honest limits</CardTitle></CardHeader><CardContent><ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground">
        <li>YouTube URLs: ClipForge reads public metadata and captions only. It does not download YouTube videos; attach the file you own to render clips.</li>
        <li>Live streams: only direct stream addresses you are authorized to use. No DRM or login bypass. Pausing stops capture.</li>
        <li>The viral score estimates how well a clip is constructed. It does not predict or guarantee performance.</li>
        <li>Face tracking uses a classic OpenCV detector: front-facing faces work best; otherwise it falls back to center framing and says so.</li>
        <li>Landscape to 9:16 crops use a fraction of the source pixels; if that means upscaling, the export report tells you.</li>
        <li>Music and sound effects are only what you upload; nothing is added automatically.</li>
        <li>Only process content you own or have permission to use.</li></ul></CardContent></Card>
    </div>
  );
}
