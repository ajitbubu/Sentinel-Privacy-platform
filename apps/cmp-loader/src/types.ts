export interface PurposeConfig {
  slug: string;
  name: string;
  description: string | null;
  required: boolean;
}

export interface LanguageOption {
  code: string;
  name: string;
  rtl: boolean;
}

export interface SiteConfig {
  site: { key: string; slug: string; auto_block: boolean };
  data_fiduciary: {
    name: string;
    address: string | null;
    grievance_officer: string | null;
    grievance_email: string | null;
    grievance_phone: string | null;
  };
  language: {
    code: string;
    native_name: string;
    rtl: boolean;
    available: LanguageOption[];
    translation_reviewed: boolean | null;
    machine_translated: boolean;
  };
  notice: {
    title: string | null;
    message: string | null;
    accept: string;
    reject: string;
    customise: string;
    withdraw: string;
  };
  appearance: {
    position: string;
    background: string;
    text: string;
    button: string;
  } | null;
  purposes: PurposeConfig[];
  banner_version_id: string | null;
  banner_version: number | null;
  published: boolean;
}

/** What we persist locally. Deliberately small and non-identifying. */
export interface StoredConsent {
  /** Pseudonymous id issued by the collector. */
  pid: string;
  /** purpose slug -> granted */
  purposes: Record<string, boolean>;
  /** Language the notice was served in when this choice was made. */
  lang: string;
  /** Banner version the choice was made against; drives re-consent. */
  bv: number | null;
  /** Receipt id, so a person can quote it in a grievance. */
  rid: string;
  /** Seconds since epoch. */
  ts: number;
}

export type InteractionType =
  | 'accept_all'
  | 'reject_all'
  | 'save_preferences'
  | 'close'
  | 'withdraw';
