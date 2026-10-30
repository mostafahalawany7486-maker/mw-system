import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Languages, Check } from "lucide-react";
import { SUPPORTED_LANGUAGES } from "@/i18n/config";

export default function LanguageSwitcher() {
  const { i18n, t } = useTranslation("common");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const current = SUPPORTED_LANGUAGES.find((l) => l.code === i18n.language?.split("-")[0]) || SUPPORTED_LANGUAGES[0];

  const handleSelect = (code: string) => {
    // i18next.changeLanguage() triggers a "languageChanged" event that every
    // component using useTranslation() is subscribed to, so every visible
    // string updates immediately with no page reload — this is what makes
    // switching instant. Persistence to localStorage is handled by the
    // i18next-browser-languagedetector plugin (see i18n/config.ts), the
    // same localStorage-based pattern already used for the theme.
    i18n.changeLanguage(code);
    setOpen(false);
  };

  return (
    <div className="relative" ref={ref}>
      <button className="btn-secondary !px-2" onClick={() => setOpen((v) => !v)} aria-label={t("language.select")} title={t("language.select")}>
        <Languages size={18} />
      </button>
      {open && (
        <div className="absolute right-0 rtl:right-auto rtl:left-0 mt-2 w-40 card p-1 z-20">
          {SUPPORTED_LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              className="w-full flex items-center justify-between px-3 py-2 rounded-md text-sm hover:bg-ink-50 dark:hover:bg-ink-800/60 text-left rtl:text-right"
              onClick={() => handleSelect(lang.code)}
            >
              <span>{lang.label}</span>
              {current.code === lang.code && <Check size={14} className="text-brand-500" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
