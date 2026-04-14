import { atom } from 'jotai';

const _fallback: { tz: string } = { tz: 'America/New_York' };

const _detected: { tz: null | string; sawError: boolean | null } = { tz: null, sawError: null };

const _using: { tz: string } = { tz: 'UTC' };

export const detectTimezone = () => {
  let tz: string = _using.tz;

  if (_detected.tz || _detected.sawError) return tz;

  try {
    tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    _detected.tz = tz;
    _using.tz = tz;
  } catch (e) {
    tz = _fallback.tz;

    if (!_detected.sawError) {
      _detected.sawError = true;
      _using.tz = tz;

      // oxlint-disable-next-line no-console -- Intentional error logging for timezone detection failure.
      console.error(`Failed to get system timezone. Falling back to ${tz}:`, e);
    }
  }

  return tz;
};

export const currentTimezoneAtom = atom<string>(detectTimezone());
