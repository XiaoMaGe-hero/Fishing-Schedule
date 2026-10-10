import { useState } from "react";
import { copy } from "../copy";

/** Site name and the video. The player itself is only loaded after a tap, so it never delays the page. */
export function Hero({ videoId }: { videoId: string }) {
  const [playing, setPlaying] = useState(false);
  return (
    <header className="hero">
      <div className="hero__title">
        <h1>{copy.siteName}</h1>
        <p>{copy.tagline}</p>
      </div>
      {videoId && (
        <div className="hero__video">
          {playing ? (
            <iframe
              src={`https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&playsinline=1`}
              title={copy.siteName}
              allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          ) : (
            <button type="button" className="hero__poster" onClick={() => setPlaying(true)} aria-label={copy.video.play}
                    style={{ backgroundImage: `url(https://i.ytimg.com/vi/${videoId}/hqdefault.jpg)` }}>
              <span className="hero__play" aria-hidden="true" />
            </button>
          )}
        </div>
      )}
    </header>
  );
}
