import { copy } from "../copy";
import type { Block, Freshness as FreshnessInfo } from "../data/derive";
import { ageText } from "./Freshness";

/** Who the data comes from, how old each part is, and the caution every forecast needs. */
export function Footer({ freshness }: { freshness: Record<Block, FreshnessInfo> }) {
  const c = copy.footer;
  return (
    <footer className="footer">
      <p className="footer__disclaimer">{c.disclaimer}</p>
      <h2>{c.sourcesHeading}</h2>
      <ul className="footer__sources">
        {c.sources.map((s) => (
          <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{s.name}</a><span>{s.what}</span></li>
        ))}
      </ul>
      <h2>{c.updatesHeading}</h2>
      <dl className="footer__updates">
        {(Object.keys(c.blocks) as Block[]).map((block) => (
          <div key={block} data-freshness={freshness[block].state}>
            <dt>{c.blocks[block]}</dt>
            <dd>{freshness[block].age ? copy.freshness.updated(ageText(freshness[block])).replace(/^Updated /, "") : copy.freshness.never}</dd>
          </div>
        ))}
      </dl>
      <p className="footer__credit">{c.mapCredit}</p>
    </footer>
  );
}
