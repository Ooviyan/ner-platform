import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import en from './locales/en.json'
import as from './locales/as.json'
import bn from './locales/bn.json'
import ne from './locales/ne.json'
import lus from './locales/lus.json'

/**
 * Languages chosen for the North Eastern Region corridor this app serves.
 * `lus` is the ISO 639-3 code for Mizo (Lushai); `as` Assamese, `bn` Bengali,
 * `ne` Nepali.
 */
export const LANGUAGES = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'as', label: 'Assamese', native: 'অসমীয়া' },
  { code: 'bn', label: 'Bengali', native: 'বাংলা' },
  { code: 'ne', label: 'Nepali', native: 'नेपाली' },
  { code: 'lus', label: 'Mizo', native: 'Mizo ṭawng' },
]

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      as: { translation: as },
      bn: { translation: bn },
      ne: { translation: ne },
      lus: { translation: lus },
    },
    fallbackLng: 'en',
    // 'en-US' must resolve to our 'en' bundle, and alert.lang must be a plain code.
    load: 'languageOnly',
    supportedLngs: LANGUAGES.map(l => l.code),
    nonExplicitSupportedLngs: true,
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'ner.lang',
      caches: ['localStorage'],
    },
  })

export default i18n
