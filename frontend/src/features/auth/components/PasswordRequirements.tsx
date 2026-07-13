import { useLocale } from '@/lib/i18n/useLocale';
import type { StringKey } from '@/lib/i18n/strings/en';
import { cn } from '@/lib/utils/cn';
import { Icon } from '@/design-system';

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
              'flex items-center gap-2 text-caption font-medium',
              met ? 'text-leaf-700' : 'text-gray-600',
            )}
          >
            <span
              className={cn(
                'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border',
                met
                  ? 'border-leaf-300 bg-leaf-100 text-leaf-700'
                  : 'border-line-300 bg-tint-100 text-gray-600',
              )}
              aria-hidden
            >
              <Icon name={met ? 'check' : 'x'} size={12} />
            </span>
            <span>{t(rule.labelKey)}</span>
            <span className="sr-only">{met ? 'Requirement met' : 'Requirement not met'}</span>
          </li>
        );
      })}
    </ul>
  );
}
