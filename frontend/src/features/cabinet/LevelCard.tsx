import { Fragment } from "react";

import type { Level } from "./types";

function progressHint(level: Level): string {
  if (level.is_manual) return "Уровень за этот месяц скорректирован администратором.";
  if (level.next_level_label && level.contracts_to_next !== null) {
    return `Ещё ${level.contracts_to_next} ${level.contracts_to_next_word} — и уровень ${level.next_level_label}.`;
  }
  return "Максимальный уровень этого месяца — выше уже некуда 🎉";
}

export function LevelCard({ level }: { level: Level }) {
  return (
    <section className="card card-wide level-card">
      <h2>Уровень партнёра в этом месяце</h2>
      <div className="level-summary">
        <span className={`level-badge level-badge-${level.level}`}>{level.label}</span>
        <span className="level-count">
          {level.is_manual
            ? "уровень установлен вручную"
            : `${level.contracts_count} ${level.contracts_word} с начала месяца`}
        </span>
      </div>
      <div className="level-track">
        {level.nodes.map((node, index) => (
          <Fragment key={node.level}>
            {index > 0 && (
              <div className="level-segment">
                <div className={`level-segment-fill fill-${level.segment_fills[index - 1] ?? 0}`} />
              </div>
            )}
            <div className="level-node">
              <span
                className={[
                  "level-node-dot",
                  node.is_reached && "is-reached",
                  node.is_current && "is-current",
                ]
                  .filter(Boolean)
                  .join(" ")}
              />
              <span className="level-node-label">
                {node.label}
                <small>{node.range_label}</small>
              </span>
            </div>
          </Fragment>
        ))}
      </div>
      <p className="hint">
        {progressHint(level)} Уровень фиксируется 1-го числа следующего месяца и определяет сумму
        основной выплаты по договорам этого месяца.
      </p>
    </section>
  );
}
