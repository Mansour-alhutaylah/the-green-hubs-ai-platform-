import { useLocale } from '@/lib/i18n/useLocale';
import type { StringKey } from '@/lib/i18n/strings/en';
import { cn } from '@/lib/utils/cn';

export interface PasswordRequirementsProps {
  password: string;
}

interface Rule {
  key: string;
  labelKey: StringKey;
  test: (value: string) => boolean;
}

const RULES: Rule[] = [
  { key: 'length', labelKey: 'auth.reset.requirement.length', test: (v) => v.length >= 8 },
  { key: 'uppercase', labelKey: 'auth.reset.requirement.uppercase', test: (v) => /[A-Z]/.test(v) },
  { key: 'number', labelKey: 'auth.reset.requirement.number', test: (v) => /\d/.test(v) },
];

/** Reset Password's live requirements checklist — calm, enterprise style
 * (a quiet dot, not a red/green traffic light), updating as the user types. */
export function PasswordRequirements({ password }: PasswordRequirementsProps) {
  const { t } = useLocale();
  return (
    <ul className="-mt-1.5 mb-6 grid gap-1.5">
      {RULES.map((rule) => {
        const met = rule.test(password);
        return (
          <li
            key={rule.key}
            className={cn(
              'flex items-center gap-2 text-[12.5px]',
              met ? 'text-leaf-700' : 'text-gray-600',
            )}
          >
            <span
              className={cn('h-1.5 w-1.5 shrink-0 rounded-full', met ? 'bg-leaf-500' : 'bg-line-300')}
              aria-hidden
            />
            {t(rule.labelKey)}
          </li>
        );
      })}
    </ul>
  );
}
