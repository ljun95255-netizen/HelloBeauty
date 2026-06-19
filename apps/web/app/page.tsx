import { MotionEffects } from "./motion-effects";

const assetBaseUrl = process.env.NEXT_PUBLIC_ASSET_BASE_URL ?? "/assets/beauty";
const beautyAsset = (path: string) => `${assetBaseUrl.replace(/\/$/, "")}/${path}`;

const heroImages = [
  beautyAsset("fresh_japanese/fresh_japanese_02.jpeg"),
  beautyAsset("clear_korean/clear_korean_03.jpeg"),
  beautyAsset("retro_hongkong/retro_hongkong_04.jpeg"),
  beautyAsset("lazy_french/lazy_french_05.jpeg"),
  beautyAsset("american_hotgirl/american_hotgirl_06.jpeg"),
];

const methodRows = [
  {
    label: "Optimize",
    title: "One-click intelligent optimization",
    body: "JESR-Fidelity improves skin tone, texture, lighting, and overall portrait polish without turning the result into a generic filter.",
    status: "Core module",
  },
  {
    label: "Retouch",
    title: "Targeted fine retouching",
    body: "Facial detail, contour, hair texture, and local imperfections are refined through JESR-Fidelity while keeping identity recognizable.",
    status: "Core module",
  },
  {
    label: "Creative",
    title: "JESR-Creative styling",
    body: "Creative looks are generated through JESR-Creative, giving the system a stronger fashion and editorial direction when a local or mounted model is available.",
    status: "Diffusion path",
  },
  {
    label: "JESR",
    title: "Short-session style recipes",
    body: "JESR applies to the creative-style loop: sparse likes, dislikes, and pain tags become session-level JSON recipes instead of new model training.",
    status: "Style alignment",
  },
  {
    label: "Trust",
    title: "Portrait data boundaries",
    body: "This promotional page shows static samples only. The product workflow keeps upload, preview, export, and storage paths deliberately constrained.",
    status: "Privacy layer",
  },
];

const galleryItems = [
  {
    title: "Fresh Japanese 01",
    note: "Light, soft, and built for everyday social portraits.",
    src: beautyAsset("fresh_japanese/fresh_japanese_02.jpeg"),
    tone: "fresh japanese",
  },
  {
    title: "Fresh Japanese 02",
    note: "A clean skin finish with gentle color and restrained polish.",
    src: beautyAsset("fresh_japanese/fresh_japanese_11.jpeg"),
    tone: "fresh japanese",
  },
  {
    title: "Fresh Japanese 03",
    note: "Bright facial presence without heavy makeup intensity.",
    src: beautyAsset("fresh_japanese/fresh_japanese_23.jpeg"),
    tone: "fresh japanese",
  },
  {
    title: "Clear Korean 01",
    note: "Luminous skin tone, softer contour, and a more refined finish.",
    src: beautyAsset("clear_korean/clear_korean_03.jpeg"),
    tone: "clear korean",
  },
  {
    title: "Clear Korean 02",
    note: "Balanced brightness and delicate facial detail for polished portraits.",
    src: beautyAsset("clear_korean/clear_korean_14.jpeg"),
    tone: "clear korean",
  },
  {
    title: "Clear Korean 03",
    note: "A clean visual language with subtle makeup and controlled glow.",
    src: beautyAsset("clear_korean/clear_korean_25.jpeg"),
    tone: "clear korean",
  },
  {
    title: "Retro Hong Kong 01",
    note: "Warmer contrast, cinematic color, and a stronger editorial mood.",
    src: beautyAsset("retro_hongkong/retro_hongkong_04.jpeg"),
    tone: "retro hong kong",
  },
  {
    title: "Retro Hong Kong 02",
    note: "Film-like atmosphere with deeper shadows and richer facial dimension.",
    src: beautyAsset("retro_hongkong/retro_hongkong_16.jpeg"),
    tone: "retro hong kong",
  },
  {
    title: "Retro Hong Kong 03",
    note: "A bold nostalgic style that still keeps the portrait recognizable.",
    src: beautyAsset("retro_hongkong/retro_hongkong_27.jpeg"),
    tone: "retro hong kong",
  },
  {
    title: "Lazy French 01",
    note: "Low-saturation color, relaxed styling, and less obvious retouching.",
    src: beautyAsset("lazy_french/lazy_french_05.jpeg"),
    tone: "lazy french",
  },
  {
    title: "Lazy French 02",
    note: "A quiet, personal look built around restraint rather than perfection.",
    src: beautyAsset("lazy_french/lazy_french_17.jpeg"),
    tone: "lazy french",
  },
  {
    title: "Lazy French 03",
    note: "Subtle polish for portraits that should feel natural and unforced.",
    src: beautyAsset("lazy_french/lazy_french_29.jpeg"),
    tone: "lazy french",
  },
  {
    title: "American Hot Girl 01",
    note: "Stronger makeup presence and higher social-media impact.",
    src: beautyAsset("american_hotgirl/american_hotgirl_06.jpeg"),
    tone: "american hot girl",
  },
  {
    title: "American Hot Girl 02",
    note: "Higher contrast, sharper presence, and more confident styling.",
    src: beautyAsset("american_hotgirl/american_hotgirl_18.jpeg"),
    tone: "american hot girl",
  },
  {
    title: "American Hot Girl 03",
    note: "A bolder creative direction for expressive portrait output.",
    src: beautyAsset("american_hotgirl/american_hotgirl_12.jpeg"),
    tone: "american hot girl",
  },
];

const closingNotes = [
  "Turns short-session portrait retouching into a structured, lower-friction interaction problem.",
  "Separates JESR-Fidelity from JESR-Creative so each model path has a clear role.",
  "Uses JESR to express creative-style preference as editable recipes instead of new model weights.",
  "Supports a more practical path for small portrait studios to offer diverse AIGC styles.",
];

export default function HomePage() {
  return (
    <>
      <MotionEffects />
      <a href="#main-content" className="skip-nav">
        Skip navigation
      </a>
      <header className="marketing-header">
        <div className="marketing-header-inner">
          <a className="marketing-brand hover-underline" href="#main-content">
            hellobeauty
          </a>
          <nav className="marketing-nav" aria-label="Primary">
            <a className="hover-underline" href="#method">
              Method
            </a>
            <a className="hover-underline" href="#gallery">
              Looks
            </a>
            <a className="hover-underline" href="#research">
              Research
            </a>
          </nav>
        </div>
      </header>

      <main className="marketing-shell" id="main-content">
        <section className="marketing-hero" data-home-block="hero">
          <div className="hero-background" aria-hidden="true">
            {heroImages.map((image, index) => (
              <img
                alt=""
                className={`hero-bg-image hero-bg-image-${index + 1}`}
                key={image}
                src={image}
              />
            ))}
          </div>
          <div className="hero-shade" aria-hidden="true" />

          <div className="marketing-hero-copy editorial-animate-in">
            <p className="eyebrow">AIGC portrait retouch prototype</p>
            <h1>hellobeauty</h1>
            <p>
              A research-facing portrait-retouching concept for an AIGC beauty
              system: fast everyday enhancement, targeted facial refinement,
              and expressive creative styles in one clear visual story.
            </p>
            <p>
              One-click optimization and targeted retouching are handled by
              JESR-Fidelity. Creative styling is handled by JESR-Creative, with
              JESR used as the recipe path for
              short-session style preference alignment.
            </p>
            <div className="hero-proof-list" aria-label="hellobeauty proof points">
              <span>JESR-Fidelity</span>
              <span>JESR-Creative</span>
              <span>JESR style recipes</span>
            </div>
          </div>

          <div className="hero-meta editorial-animate-in" aria-label="system scope">
            <span>One-click optimize</span>
            <span>Targeted retouch</span>
            <span>Creative style</span>
            <span>Privacy-aware</span>
          </div>
        </section>

        <section className="marketing-workflow" id="method" data-home-block="workflow">
          <div className="section-heading">
            <p className="eyebrow">Method</p>
            <h2>Research significance: make personalized portrait retouching practical for short sessions, small teams, and diverse style demand.</h2>
          </div>

          <div className="research-row-list">
            {methodRows.map((row) => (
              <article className="research-row" key={row.label}>
                <span className="research-label">{row.label}</span>
                <div className="research-copy">
                  <h3>{row.title}</h3>
                  <p>{row.body}</p>
                </div>
                <span className="research-status">{row.status}</span>
              </article>
            ))}
          </div>

          <div className="research-marquee" aria-hidden="true">
            <span>JESR-Fidelity / Targeted retouch / JESR-Creative / JESR recipes / </span>
            <span>JESR-Fidelity / Targeted retouch / JESR-Creative / JESR recipes / </span>
          </div>
        </section>

        <section className="marketing-gallery" id="gallery" data-home-block="gallery">
          <div className="section-heading">
            <p className="eyebrow">Looks</p>
            <h2>Real portrait samples showing the boundary between natural, polished, expressive, and believable.</h2>
          </div>
          <div className="gallery-grid">
            {galleryItems.map((item, index) => (
              <article className={`compare-card compare-card-${index + 1}`} key={item.title}>
                <div className="compare-media">
                  <img alt={`${item.title} hellobeauty sample`} src={item.src} />
                </div>
                <div className="compare-copy">
                  <span>{item.tone}</span>
                  <h3>{item.title}</h3>
                  <p>{item.note}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="marketing-conversion" id="research" data-home-block="research">
          <div className="conversion-intro">
            <p className="eyebrow">Research</p>
            <h2>The research significance is to make personalized portrait retouching practical: one-click optimization and targeted retouching stay inside JESR-Fidelity, while creative styles use JESR-Creative and JESR recipes to reduce repeated training cost.</h2>
          </div>
          <div className="brand-marquee" aria-hidden="true">
            <span>hellobeauty</span>
            <span>hellobeauty</span>
            <span>hellobeauty</span>
          </div>
          <div className="conversion-notes">
            {closingNotes.map((note) => (
              <p key={note}>{note}</p>
            ))}
          </div>
        </section>
      </main>

      <footer className="hellobeauty-footer">
        <p>hellobeauty / AIGC Portrait Retouch</p>
        <p>Research prototype / JESR-Fidelity / JESR-Creative / JESR recipes</p>
      </footer>
    </>
  );
}
