import { useEffect, useRef, useState } from 'react';
import type { ClipboardEvent, KeyboardEvent } from 'react';
import { cn } from '@/lib/utils/cn';

export interface OtpCellsProps {
  length?: number;
  disabled?: boolean;
  error?: boolean;
  /** Fires once, when the last cell is filled (§11.1: "auto-submit on 6th digit"). */
  onComplete: (code: string) => void;
  label: string;
}

/** Six 54px auto-advancing cells (matching the auth system's control-xl
 * sizing): typing advances focus, backspace on an empty cell steps back,
 * pasting a full code splits across cells, and completing the last cell
 * auto-submits. */
export function OtpCells({ length = 6, disabled, error, onComplete, label }: OtpCellsProps) {
  const [digits, setDigits] = useState<string[]>(() => Array(length).fill(''));
  const inputRefs = useRef<Array<HTMLInputElement | null>>([]);
  const hasSubmitted = useRef(false);

  useEffect(() => {
    setDigits(Array(length).fill(''));
    hasSubmitted.current = false;
  }, [length]);

  function commitDigits(next: string[]) {
    setDigits(next);
    const code = next.join('');
    if (code.length === length && !next.includes('') && !hasSubmitted.current) {
      hasSubmitted.current = true;
      onComplete(code);
    }
  }

  function handleChange(index: number, rawValue: string) {
    const value = rawValue.replace(/\D/g, '');
    hasSubmitted.current = false;
    if (!value) {
      const next = [...digits];
      next[index] = '';
      commitDigits(next);
      return;
    }
    const next = [...digits];
    next[index] = value.at(-1) ?? '';
    commitDigits(next);
    if (index < length - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  }

  function handleKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Backspace' && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLInputElement>) {
    const pasted = event.clipboardData.getData('text').replace(/\D/g, '').slice(0, length);
    if (!pasted) return;
    event.preventDefault();
    hasSubmitted.current = false;
    const next = Array(length).fill('');
    for (let i = 0; i < pasted.length; i += 1) {
      next[i] = pasted[i];
    }
    commitDigits(next);
    const focusIndex = Math.min(pasted.length, length - 1);
    inputRefs.current[focusIndex]?.focus();
  }

  return (
    <fieldset className="flex gap-2 border-0 p-0">
      <legend className="sr-only">{label}</legend>
      {digits.map((digit, index) => (
        <input
          key={`otp-cell-${index}`}
          ref={(el) => {
            inputRefs.current[index] = el;
          }}
          type="text"
          inputMode="numeric"
          autoComplete={index === 0 ? 'one-time-code' : 'off'}
          maxLength={1}
          disabled={disabled}
          value={digit}
          aria-label={`Digit ${index + 1} of ${length}`}
          onChange={(event) => handleChange(index, event.target.value)}
          onKeyDown={(event) => handleKeyDown(index, event)}
          onPaste={handlePaste}
          className={cn(
            'h-[var(--size-control-xl)] w-[var(--size-control-xl)] rounded-m border text-center text-title text-ink-900 outline-none transition-colors duration-[var(--motion-fast)]',
            'disabled:bg-tint-100 disabled:text-gray-400',
            error
              ? 'border-[length:var(--border-width-error)] border-amber-700'
              : 'border-line-300 focus:border-2 focus:border-forest-900',
          )}
        />
      ))}
    </fieldset>
  );
}
