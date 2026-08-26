import { useTranslation } from 'react-i18next'

/** Segment status -> colour. Kept here (not in MapView) so screens can use it
 *  without pulling the map engine into the initial bundle. */
export const RISK_COLORS = {
  clear: '#34d399',
  caution: '#fbbf24',
  high_risk: '#fb7185',
  blocked: '#f43f5e',
}

export function riskColor(status, risk = 0) {
  if (RISK_COLORS[status]) return RISK_COLORS[status]
  if (risk >= 0.6) return RISK_COLORS.high_risk
  if (risk >= 0.3) return RISK_COLORS.caution
  return RISK_COLORS.clear
}

/** "3h 22m" from a minute count. */
export function formatEta(mins, t) {
  const m = Math.max(0, Math.round(mins || 0))
  return t('home.eta_value', { h: Math.floor(m / 60), m: m % 60 })
}

export function relativeTime(iso, t) {
  const then = new Date(iso).getTime()
  if (!Number.isFinite(then)) return ''
  const secs = Math.floor((Date.now() - then) / 1000)
  if (secs < 60) return t('common.just_now')
  if (secs < 3600) return t('common.minutes_ago', { count: Math.floor(secs / 60) })
  if (secs < 86400) return t('common.hours_ago', { count: Math.floor(secs / 3600) })
  return t('common.days_ago', { count: Math.floor(secs / 86400) })
}

export function riskLabel(risk, t) {
  if (risk >= 0.6) return t('home.risk_high')
  if (risk >= 0.3) return t('home.risk_medium')
  return t('home.risk_low')
}

export function riskPillClass(risk) {
  if (risk >= 0.6) return 'pill danger'
  if (risk >= 0.3) return 'pill warn'
  return 'pill ok'
}

/** Coloured badge for a report's sync state. */
export function StateBadge({ state }) {
  const { t } = useTranslation()
  const cls =
    state === 'synced'
      ? 'pill ok'
      : state === 'failed'
        ? 'pill danger'
        : state === 'relaying'
          ? 'pill accent'
          : 'pill warn'
  return (
    <span className={cls}>
      <span className={`dot${state === 'relaying' ? ' pulse' : ''}`} />
      {t(`report.state.${state}`, state)}
    </span>
  )
}

export function Stat({ value, label, tone }) {
  return (
    <div className="stat">
      <b style={tone ? { color: tone } : undefined}>{value}</b>
      <span>{label}</span>
    </div>
  )
}
