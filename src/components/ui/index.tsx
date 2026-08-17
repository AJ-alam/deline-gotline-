/**
 * UI primitives.
 *
 * There were none before: Button, Table, Modal and Badge were re-hand-rolled
 * inline at every use, which is where 1,112 inline style objects came from and
 * why nothing looked quite the same twice.
 */

import { useEffect, useRef } from 'react';
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react';

import { type Tone } from './format';
import './ui.css';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

export function Button({
  variant = 'secondary',
  size,
  block,
  busy,
  children,
  className = '',
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: 'sm';
  block?: boolean;
  busy?: boolean;
}) {
  const classes = [
    'btn',
    `btn--${variant}`,
    size === 'sm' && 'btn--sm',
    block && 'btn--block',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button className={classes} disabled={disabled || busy} {...rest}>
      {busy && <span className="spinner" aria-hidden="true" />}
      {children}
    </button>
  );
}

/**
 * A labelled control.
 *
 * The label is tied to the input by id, and the error is announced — a form
 * that only turns a border red is unusable with a screen reader.
 */
export function Field({
  id,
  label,
  required,
  hint,
  error,
  wide,
  children,
}: {
  id: string;
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  /** Take the full width of the grid — for answers a half column truncates. */
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={wide ? 'field field--wide' : 'field'}>
      {/* Identified as well as associated: a group of radios cannot be the
          target of htmlFor, and points back at this with aria-labelledby. */}
      <label className="field__label" id={`${id}-label`} htmlFor={id}>
        {label}
        {required && (
          <span className="field__required" aria-hidden="true">
            *
          </span>
        )}
      </label>
      {children}
      {hint && !error && (
        <span className="field__hint" id={`${id}-hint`}>
          {hint}
        </span>
      )}
      {error && (
        <span className="field__error" id={`${id}-error`} role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

export function Input({
  invalid,
  className = '',
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      className={`input ${invalid ? 'input--invalid' : ''} ${className}`.trim()}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  );
}

export function Textarea({
  invalid,
  className = '',
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }) {
  return (
    <textarea
      className={`textarea ${invalid ? 'textarea--invalid' : ''} ${className}`.trim()}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  );
}

export function Select({
  invalid,
  className = '',
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
  return (
    <select
      className={`select ${invalid ? 'select--invalid' : ''} ${className}`.trim()}
      aria-invalid={invalid || undefined}
      {...rest}
    >
      {children}
    </select>
  );
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function Card({ title, actions, children }: { title?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="card">
      {(title || actions) && (
        <header className="card__header row row--between">
          {title && <h2>{title}</h2>}
          {actions}
        </header>
      )}
      <div className="card__body">{children}</div>
    </section>
  );
}

/**
 * A modal.
 *
 * Built on the native `<dialog>` rather than a positioned div, so focus
 * trapping, Escape, returning focus to whatever opened it, and making the rest
 * of the page inert all come from the browser instead of being reimplemented
 * badly. Clicking the backdrop closes it, which `<dialog>` does not do by
 * itself.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = ref.current;
    // jsdom has no dialog implementation; guarding keeps this renderable in tests.
    if (!element || typeof element.showModal !== 'function') return;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="dialog"
      aria-labelledby="dialog-title"
      // Escape and the close button both fire this; the parent owns `open`, so
      // it has to hear about a close it did not initiate.
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      <header className="dialog__header">
        <div>
          <h2 id="dialog-title" className="dialog__title">
            {title}
          </h2>
          {description && <p className="dialog__description">{description}</p>}
        </div>
        <button type="button" className="dialog__close" onClick={onClose} aria-label="Close">
          &times;
        </button>
      </header>
      <div className="dialog__body">{children}</div>
    </dialog>
  );
}

export function Alert({ tone = 'info', children }: { tone?: 'error' | 'info' | 'ok'; children: ReactNode }) {
  return (
    <div className={`alert alert--${tone}`} role={tone === 'error' ? 'alert' : undefined}>
      {children}
    </div>
  );
}
