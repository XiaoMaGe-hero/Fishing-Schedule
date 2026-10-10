import { copy } from "../copy";
import type { TodayCard } from "../data/derive";
import { formatTime } from "../data/time";
import { TideSpark } from "./TideSpark";

/** One card per spot: the best window left today, or a plain "not today". */
export function TodayCards({ cards }: { cards: TodayCard[] }) {
  return (
    <section className="today" aria-labelledby="today-heading">
      <h2 id="today-heading">{copy.today.heading}</h2>
      <div className="today__cards">
        {cards.map(({ spot, window, passed, tide }) => (
          <article key={spot.id} className={`today-card ${window ? "today-card--go" : "today-card--no"}`} data-spot={spot.id}>
            <h3>{spot.name}</h3>
            {window ? (
              <>
                <p className="today-card__time">
                  {formatTime(new Date(window.start_utc))}<span aria-hidden="true">–</span>
                  <span className="visually-hidden"> to </span>{formatTime(new Date(window.end_utc))}
                </p>
                <p className="today-card__score">
                  <strong>{Math.round(window.score)}</strong> {copy.today.scoreOutOf}
                </p>
              </>
            ) : (
              <>
                <p className="today-card__none">{passed ? copy.today.passed : copy.today.notRecommended}</p>
                <p className="today-card__hint">{passed ? copy.today.passedHint : copy.today.notRecommendedHint}</p>
              </>
            )}
            <TideSpark tide={tide} windowStart={window?.start_utc} windowEnd={window?.end_utc} />
            {spot.notes && <p className="today-card__notes">{spot.notes}</p>}
          </article>
        ))}
      </div>
    </section>
  );
}
