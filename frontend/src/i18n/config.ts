import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import commonEn from "@/locales/en/common.json";
import navEn from "@/locales/en/nav.json";
import authEn from "@/locales/en/auth.json";
import dashboardEn from "@/locales/en/dashboard.json";
import propertiesEn from "@/locales/en/properties.json";
import validationEn from "@/locales/en/validation.json";
import reportsEn from "@/locales/en/reports.json";
import pdfEn from "@/locales/en/pdf.json";
import emailEn from "@/locales/en/email.json";

import commonAr from "@/locales/ar/common.json";
import navAr from "@/locales/ar/nav.json";
import authAr from "@/locales/ar/auth.json";
import dashboardAr from "@/locales/ar/dashboard.json";
import propertiesAr from "@/locales/ar/properties.json";
import validationAr from "@/locales/ar/validation.json";
import reportsAr from "@/locales/ar/reports.json";
import pdfAr from "@/locales/ar/pdf.json";
import emailAr from "@/locales/ar/email.json";

// Unlimited-language architecture: every supported language is one entry
// in this list, and one folder under src/locales/<code>/ containing the
// same set of namespace JSON files as English. Adding a third, fourth,
// fifth language never touches this file's logic — only this array and
// the corresponding imports above grow.
export const SUPPORTED_LANGUAGES = [
  { code: "en", label: "English", dir: "ltr" as const },
  { code: "ar", label: "العربية", dir: "rtl" as const },
];

export const DEFAULT_LANGUAGE = "en";
export const LANGUAGE_STORAGE_KEY = "pms_language";

const resources = {
  en: { common: commonEn, nav: navEn, auth: authEn, dashboard: dashboardEn, properties: propertiesEn, validation: validationEn, reports: reportsEn, pdf: pdfEn, email: emailEn },
  ar: { common: commonAr, nav: navAr, auth: authAr, dashboard: dashboardAr, properties: propertiesAr, validation: validationAr, reports: reportsAr, pdf: pdfAr, email: emailAr },
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: DEFAULT_LANGUAGE,
    supportedLngs: SUPPORTED_LANGUAGES.map((l) => l.code),
    defaultNS: "common",
    ns: ["common", "nav", "auth", "dashboard", "properties", "validation", "reports", "pdf", "email"],
    interpolation: { escapeValue: false }, // React already escapes
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: LANGUAGE_STORAGE_KEY,
      caches: ["localStorage"],
    },
    react: { useSuspense: false }, // avoid a Suspense boundary requirement app-wide
  });

export function applyDocumentDirection(lang: string) {
  const meta = SUPPORTED_LANGUAGES.find((l) => l.code === lang) || SUPPORTED_LANGUAGES[0];
  document.documentElement.lang = meta.code;
  document.documentElement.dir = meta.dir;
}

// Apply immediately on load (covers page refresh with a previously-saved language).
applyDocumentDirection(i18n.language?.split("-")[0] || DEFAULT_LANGUAGE);

i18n.on("languageChanged", (lng) => applyDocumentDirection(lng.split("-")[0]));

export default i18n;
