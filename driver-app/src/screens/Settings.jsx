import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLiveQuery } from 'dexie-react-hooks'
import { db } from '../db/db.js'
import { LANGUAGES } from '../i18n/index.js'
import { useInstallPrompt } from '../hooks/useInstallPrompt.js'
import { API_URL, MOCK_MODE, NODE_LABEL, VEHICLE_ID, setVehicleId } from '../config.js'
import { Check } from '../components/icons.jsx'

export default function Settings() {
  const { t, i18n } = useTranslation()
  const { canInstall, installed, install } = useInstallPrompt()
  const [vehicle, setVehicle] = useState(VEHICLE_ID)
  const [saved, setSaved] = useState(false)

  const total = useLiveQuery(() => db.reports.count(), [], 0)
  const syncedCount = useLiveQuery(() => db.reports.where('state').equals('synced').count(), [], 0)

  const saveVehicle = () => {
    setVehicleId(vehicle.trim())
    setSaved(true)
    setTimeout(() => setSaved(false), 1800)
  }

  const clearSynced = async () => {
    await db.reports.where('state').equals('synced').delete()
  }

  return (
    <main className="screen">
      {/* ---- language ---- */}
      <section className="card">
        <h3>{t('settings.language')}</h3>
        <div className="col" style={{ gap: 7 }}>
          {LANGUAGES.map(l => {
            const active = i18n.resolvedLanguage === l.code
            return (
              <button
                key={l.code}
                className="chip"
                style={{ minHeight: 48 }}
                aria-pressed={active}
                onClick={() => i18n.changeLanguage(l.code)}
              >
                <span className="grow">
                  <span style={{ fontWeight: 700 }}>{l.native}</span>
                  <span className="muted tiny"> · {l.label}</span>
                </span>
                {active && <Check width="16" height="16" />}
              </button>
            )
          })}
        </div>
      </section>

      {/* ---- install ---- */}
      <section className="card">
        <h3>{t('settings.install')}</h3>
        {installed ? (
          <div className="banner ok">
            <Check width="15" height="15" /> {t('settings.installed')}
          </div>
        ) : (
          <>
            <p className="small muted" style={{ margin: '0 0 10px' }}>
              {t('settings.install_hint')}
            </p>
            {canInstall ? (
              <button className="btn primary block" onClick={install}>
                {t('settings.install')}
              </button>
            ) : (
              <div className="banner">{t('settings.install_unavailable')}</div>
            )}
          </>
        )}
      </section>

      {/* ---- vehicle / node ---- */}
      <section className="card">
        <h3>{t('settings.vehicle_id')}</h3>
        <div className="row" style={{ gap: 8 }}>
          <input
            className="input grow mono"
            value={vehicle}
            onChange={e => setVehicle(e.target.value)}
            aria-label={t('settings.vehicle_id')}
          />
          <button className="btn" onClick={saveVehicle}>
            {saved ? t('common.saved') : t('common.save')}
          </button>
        </div>
        <div className="row between small muted" style={{ marginTop: 12 }}>
          <span>{t('settings.node_label')}</span>
          <span className="pill accent">{NODE_LABEL}</span>
        </div>
        <p className="tiny muted" style={{ margin: '6px 0 0' }}>
          {t('mesh.topology')}
        </p>
      </section>

      {/* ---- storage ---- */}
      <section className="card">
        <h3>{t('settings.storage')}</h3>
        <div className="row between small">
          <span className="muted">{t('settings.storage_reports', { count: total })}</span>
          <span className="pill ok">{syncedCount} synced</span>
        </div>
        <button
          className="btn ghost block"
          style={{ marginTop: 10 }}
          onClick={clearSynced}
          disabled={syncedCount === 0}
        >
          {t('settings.clear_synced')}
        </button>
      </section>

      {/* ---- data source ---- */}
      <section className="card">
        <h3>{t('settings.api')}</h3>
        <div className="row between small">
          <span className={MOCK_MODE ? 'pill warn' : 'pill ok'}>
            {MOCK_MODE ? t('settings.mock_mode') : t('settings.live_mode')}
          </span>
          <span className="mono tiny muted truncate">{API_URL}</span>
        </div>
      </section>

      {/* ---- about ---- */}
      <section className="card">
        <h3>{t('settings.about')}</h3>
        <p className="small muted" style={{ margin: 0 }}>
          {t('settings.about_text')}
        </p>
        <p className="tiny muted" style={{ margin: '8px 0 0' }}>
          {t('settings.version', { v: __APP_VERSION__ })}
        </p>
      </section>
    </main>
  )
}
